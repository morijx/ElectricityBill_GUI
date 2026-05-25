"""
Electricity Billing System - Consolidated Services Module

This module contains all service logic including:
- CSV Import and data processing
- Energy allocation strategies
- Billing calculations
- PDF generation
- Database operations
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod
import sqlite3
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Import models from consolidated module
from app.models_consolidated import (
    MeterType, AllocationStrategyType, TariffType,
    Project, Property, Apartment, Meter, SolarSystem, Battery,
    EnergyFlow, EnergyData, AllocatedEnergy,
    Tariff, SwissTariff, TariffComponent, TariffPeriod,
    BillingPeriod, Invoice, InvoiceItem, BillingResult,
    DATABASE_SCHEMA
)

logger = logging.getLogger(__name__)


# ============================================================================
# CSV IMPORT SERVICE
# ============================================================================

class CSVImporter:
    """Handles importing CSV files with energy data."""
    
    def __init__(self):
        self.supported_columns = {
            'timestamp': ['timestamp', 'datetime', 'date', 'time', 'Zeitstempel'],
            'grid_import': ['grid_import', 'grid_in', 'import', 'bezug', 'netzbezug'],
            'grid_export': ['grid_export', 'grid_out', 'export', 'einspeisung', 'netzeinspeisung'],
            'solar': ['solar', 'pv', 'photovoltaic', 'produktion', 'production', 'ertrag'],
            'battery_charge': ['battery_charge', 'bat_charge', 'batterie_laden', 'ladung'],
            'battery_discharge': ['battery_discharge', 'bat_discharge', 'batterie_entladen', 'entladung'],
            'apartment_': ['apt_', 'apartment_', 'wohnung_', 'unit_'],
        }
    
    def detect_column_mapping(self, df: pd.DataFrame) -> Dict[str, str]:
        """Detect column mapping based on column names."""
        mapping = {}
        columns_lower = {col.lower().strip(): col for col in df.columns}
        
        for category, keywords in self.supported_columns.items():
            for keyword in keywords:
                for col_lower, col_original in columns_lower.items():
                    if keyword in col_lower:
                        if category.startswith('apartment_'):
                            apt_id = col_lower.replace('apartment_', '').replace('apt_', '').replace('wohnung_', '').replace('unit_', '')
                            mapping[f'apartment_{apt_id}'] = col_original
                        else:
                            mapping[category] = col_original
                        break
        
        return mapping
    
    def import_file(self, file_path: Path, 
                   column_mapping: Optional[Dict[str, str]] = None,
                   meter_type: Optional[MeterType] = None,
                   apartment_id: Optional[str] = None) -> EnergyData:
        """Import a CSV file and return EnergyData."""
        df = pd.read_csv(file_path)
        
        if column_mapping is None:
            column_mapping = self.detect_column_mapping(df)
        
        # Find timestamp column
        timestamp_col = None
        for col in df.columns:
            if any(kw in col.lower() for kw in ['timestamp', 'datetime', 'date', 'zeit']):
                timestamp_col = col
                break
        
        if not timestamp_col:
            raise ValueError("No timestamp column found in CSV")
        
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df = df.sort_values(timestamp_col)
        
        # Determine meter type and name
        if meter_type is None:
            if 'solar' in column_mapping:
                meter_type = MeterType.SOLAR_PRODUCTION
            elif 'grid_import' in column_mapping:
                meter_type = MeterType.GRID_IMPORT
            elif 'grid_export' in column_mapping:
                meter_type = MeterType.GRID_EXPORT
            elif 'battery_charge' in column_mapping:
                meter_type = MeterType.BATTERY_CHARGE
            elif 'battery_discharge' in column_mapping:
                meter_type = MeterType.BATTERY_DISCHARGE
            else:
                meter_type = MeterType.APARTMENT_CONSUMPTION
        
        meter_name = f"{meter_type.value}_{file_path.stem}"
        meter_id = f"meter_{file_path.stem}_{meter_type.value}"
        
        energy_data = EnergyData(
            meter_id=meter_id,
            meter_name=meter_name,
            meter_type=meter_type,
        )
        
        # Extract value column
        value_col = None
        for col in df.columns:
            if col != timestamp_col:
                value_col = col
                break
        
        if not value_col:
            raise ValueError("No value column found in CSV")
        
        # Create energy flows
        interval_minutes = 15  # Default
        for _, row in df.iterrows():
            try:
                flow = EnergyFlow(
                    timestamp=row[timestamp_col].to_pydatetime(),
                    meter_id=meter_id,
                    value_kwh=float(row[value_col]),
                    interval_minutes=interval_minutes,
                )
                energy_data.add_flow(flow)
            except Exception as e:
                logger.warning(f"Skipping row due to error: {e}")
                continue
        
        logger.info(f"Imported {len(energy_data.data)} records from {file_path}")
        return energy_data
    
    def import_multiple_files(self, file_paths: List[Path],
                             mappings: Optional[Dict[str, Dict[str, str]]] = None) -> List[EnergyData]:
        """Import multiple CSV files."""
        results = []
        for path in file_paths:
            try:
                mapping = mappings.get(path.name) if mappings else None
                data = self.import_file(path, mapping)
                results.append(data)
            except Exception as e:
                logger.error(f"Failed to import {path}: {e}")
                continue
        return results


# ============================================================================
# ENERGY ALLOCATION ENGINE
# ============================================================================

class AllocationStrategy(ABC):
    """Base class for energy allocation strategies."""
    
    @abstractmethod
    def allocate(self, 
                 consumption_data: Dict[str, float],
                 solar_production: float,
                 grid_import: float,
                 grid_export: float,
                 battery_data: Optional[Dict[str, float]] = None,
                 config: Optional[Any] = None) -> Dict[str, AllocatedEnergy]:
        """Allocate energy to apartments."""
        pass


class PriorityAllocationStrategy(AllocationStrategy):
    """Owner-first priority allocation strategy."""
    
    def allocate(self,
                 consumption_data: Dict[str, float],
                 solar_production: float,
                 grid_import: float,
                 grid_export: float,
                 battery_data: Optional[Dict[str, float]] = None,
                 config: Optional[Any] = None) -> Dict[str, AllocatedEnergy]:
        """
        Allocate energy with owner getting priority for solar.
        
        Logic:
        1. Owner consumes solar first
        2. Surplus solar goes to tenants (with discount)
        3. Remaining consumption comes from grid
        """
        results = {}
        owner_id = config.owner_apartment_id if config else None
        
        # Sort apartments: owner first, then others
        apt_order = []
        if owner_id and owner_id in consumption_data:
            apt_order.append(owner_id)
        apt_order.extend([aid for aid in consumption_data.keys() if aid != owner_id])
        
        remaining_solar = solar_production
        total_consumption = sum(consumption_data.values())
        
        for apt_id in apt_order:
            consumption = consumption_data.get(apt_id, 0.0)
            is_owner = (apt_id == owner_id)
            
            # Calculate solar allocation
            if is_owner:
                # Owner gets priority - takes as much solar as needed
                solar_allocated = min(consumption, remaining_solar)
                remaining_solar -= solar_allocated
            else:
                # Tenant gets surplus solar only
                solar_allocated = min(consumption, remaining_solar)
                remaining_solar -= solar_allocated
            
            # Grid consumption
            grid_consumed = consumption - solar_allocated
            
            # Battery allocation (if available)
            battery_allocated = 0.0
            if battery_data and 'discharge' in battery_data:
                battery_available = battery_data['discharge'] * (consumption / total_consumption if total_consumption > 0 else 0)
                battery_allocated = min(battery_available, consumption - solar_allocated)
            
            # Calculate costs
            solar_discount = config.solar_discount if config else 0.02
            grid_price = 0.25  # Default CHF/kWh
            solar_price = grid_price - solar_discount
            
            solar_cost = solar_allocated * solar_price
            grid_cost = grid_consumed * grid_price
            battery_cost = battery_allocated * (grid_price * 0.95)  # Slight discount for battery
            
            results[apt_id] = AllocatedEnergy(
                apartment_id=apt_id,
                apartment_name=f"Apartment {apt_id}",
                total_consumption_kwh=consumption,
                grid_consumption_kwh=grid_consumed,
                solar_consumption_kwh=solar_allocated,
                battery_consumption_kwh=battery_allocated,
                solar_discount_chf=solar_allocated * solar_discount,
                grid_cost_chf=grid_cost,
                solar_cost_chf=solar_cost,
                battery_cost_chf=battery_cost,
                total_cost_chf=solar_cost + grid_cost + battery_cost,
                feed_in_kwh=remaining_solar if apt_id == apt_order[-1] else 0,
                breakdown={
                    'solar_kwh': solar_allocated,
                    'grid_kwh': grid_consumed,
                    'battery_kwh': battery_allocated,
                }
            )
        
        return results


class EqualAllocationStrategy(AllocationStrategy):
    """Equal sharing allocation strategy."""
    
    def allocate(self,
                 consumption_data: Dict[str, float],
                 solar_production: float,
                 grid_import: float,
                 grid_export: float,
                 battery_data: Optional[Dict[str, float]] = None,
                 config: Optional[Any] = None) -> Dict[str, AllocatedEnergy]:
        """Allocate energy equally among all apartments."""
        results = {}
        num_apartments = len(consumption_data)
        
        if num_apartments == 0:
            return results
        
        solar_per_apt = solar_production / num_apartments
        battery_discharge = battery_data.get('discharge', 0.0) if battery_data else 0.0
        battery_per_apt = battery_discharge / num_apartments
        
        grid_price = 0.25
        solar_price = grid_price - 0.02
        
        for apt_id, consumption in consumption_data.items():
            solar_allocated = min(solar_per_apt, consumption)
            battery_allocated = min(battery_per_apt, consumption - solar_allocated)
            grid_consumed = consumption - solar_allocated - battery_allocated
            
            solar_cost = solar_allocated * solar_price
            battery_cost = battery_allocated * (grid_price * 0.95)
            grid_cost = grid_consumed * grid_price
            
            results[apt_id] = AllocatedEnergy(
                apartment_id=apt_id,
                apartment_name=f"Apartment {apt_id}",
                total_consumption_kwh=consumption,
                grid_consumption_kwh=max(0, grid_consumed),
                solar_consumption_kwh=solar_allocated,
                battery_consumption_kwh=battery_allocated,
                solar_discount_chf=solar_allocated * 0.02,
                grid_cost_chf=max(0, grid_cost),
                solar_cost_chf=solar_cost,
                battery_cost_chf=battery_cost,
                total_cost_chf=solar_cost + max(0, grid_cost) + battery_cost,
                feed_in_kwh=max(0, solar_per_apt - consumption) / num_apartments,
                breakdown={'solar_kwh': solar_allocated, 'grid_kwh': max(0, grid_consumed), 'battery_kwh': battery_allocated}
            )
        
        return results


class ProportionalAllocationStrategy(AllocationStrategy):
    """Proportional allocation based on consumption."""
    
    def allocate(self,
                 consumption_data: Dict[str, float],
                 solar_production: float,
                 grid_import: float,
                 grid_export: float,
                 battery_data: Optional[Dict[str, float]] = None,
                 config: Optional[Any] = None) -> Dict[str, AllocatedEnergy]:
        """Allocate energy proportionally to consumption."""
        results = {}
        total_consumption = sum(consumption_data.values())
        
        if total_consumption == 0:
            return results
        
        battery_discharge = battery_data.get('discharge', 0.0) if battery_data else 0.0
        grid_price = 0.25
        solar_price = grid_price - 0.02
        
        for apt_id, consumption in consumption_data.items():
            proportion = consumption / total_consumption
            solar_allocated = min(solar_production * proportion, consumption)
            battery_allocated = min(battery_discharge * proportion, consumption - solar_allocated)
            grid_consumed = consumption - solar_allocated - battery_allocated
            
            solar_cost = solar_allocated * solar_price
            battery_cost = battery_allocated * (grid_price * 0.95)
            grid_cost = grid_consumed * grid_price
            
            results[apt_id] = AllocatedEnergy(
                apartment_id=apt_id,
                apartment_name=f"Apartment {apt_id}",
                total_consumption_kwh=consumption,
                grid_consumption_kwh=max(0, grid_consumed),
                solar_consumption_kwh=solar_allocated,
                battery_consumption_kwh=battery_allocated,
                solar_discount_chf=solar_allocated * 0.02,
                grid_cost_chf=max(0, grid_cost),
                solar_cost_chf=solar_cost,
                battery_cost_chf=battery_cost,
                total_cost_chf=solar_cost + max(0, grid_cost) + battery_cost,
                feed_in_kwh=max(0, solar_production * proportion - consumption),
                breakdown={'solar_kwh': solar_allocated, 'grid_kwh': max(0, grid_consumed), 'battery_kwh': battery_allocated}
            )
        
        return results


class AllocationEngine:
    """Main allocation engine that uses strategies."""
    
    def __init__(self):
        self.strategies: Dict[AllocationStrategyType, AllocationStrategy] = {
            AllocationStrategyType.PRIORITY: PriorityAllocationStrategy(),
            AllocationStrategyType.EQUAL: EqualAllocationStrategy(),
            AllocationStrategyType.PROPORTIONAL: ProportionalAllocationStrategy(),
        }
    
    def allocate(self,
                 consumption_data: Dict[str, float],
                 solar_production: float,
                 grid_import: float,
                 grid_export: float,
                 battery_data: Optional[Dict[str, float]] = None,
                 strategy_type: AllocationStrategyType = AllocationStrategyType.PRIORITY,
                 config: Optional[Any] = None) -> Dict[str, AllocatedEnergy]:
        """Perform energy allocation using specified strategy."""
        strategy = self.strategies.get(strategy_type)
        if not strategy:
            strategy = self.strategies[AllocationStrategyType.PRIORITY]
        
        return strategy.allocate(
            consumption_data=consumption_data,
            solar_production=solar_production,
            grid_import=grid_import,
            grid_export=grid_export,
            battery_data=battery_data,
            config=config
        )


# ============================================================================
# BILLING CALCULATION ENGINE
# ============================================================================

class BillingEngine:
    """Calculates electricity bills based on allocated energy and tariffs."""
    
    def __init__(self, tariff: SwissTariff):
        self.tariff = tariff
    
    def calculate_invoice(self,
                         allocated: AllocatedEnergy,
                         period: BillingPeriod,
                         apartment: Apartment) -> Invoice:
        """Generate an invoice for one apartment."""
        invoice = Invoice(
            apartment_id=allocated.apartment_id,
            apartment_name=apartment.name or allocated.apartment_name,
            billing_period=period,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.tariff.currency,
        )
        
        # Get VAT component
        vat_component = self.tariff.get_component(TariffType.VAT)
        if vat_component:
            invoice.vat_rate = vat_component.price
        
        # Add energy items
        if allocated.solar_consumption_kwh > 0:
            solar_price = self._get_energy_price() - allocated.solar_discount_chf / max(allocated.solar_consumption_kwh, 0.001)
            invoice.add_item(InvoiceItem(
                description="Solar Energy",
                quantity=allocated.solar_consumption_kwh,
                unit="kWh",
                unit_price=round(solar_price, 4),
                total=allocated.solar_cost_chf,
                category="energy"
            ))
        
        if allocated.grid_consumption_kwh > 0:
            grid_price = self._get_energy_price()
            invoice.add_item(InvoiceItem(
                description="Grid Energy",
                quantity=allocated.grid_consumption_kwh,
                unit="kWh",
                unit_price=round(grid_price, 4),
                total=allocated.grid_cost_chf,
                category="energy"
            ))
        
        if allocated.battery_consumption_kwh > 0:
            invoice.add_item(InvoiceItem(
                description="Battery Energy",
                quantity=allocated.battery_consumption_kwh,
                unit="kWh",
                unit_price=round(allocated.battery_cost_chf / max(allocated.battery_consumption_kwh, 0.001), 4),
                total=allocated.battery_cost_chf,
                category="energy"
            ))
        
        # Add basic fee (pro-rated for period)
        basic_component = self.tariff.get_component(TariffType.BASIC)
        if basic_component:
            monthly_fee = basic_component.price
            period_fee = monthly_fee * period.months
            invoice.add_item(InvoiceItem(
                description="Basic Fee",
                quantity=period.months,
                unit="month",
                unit_price=monthly_fee,
                total=period_fee,
                category="fixed"
            ))
        
        # Add grid/network fees
        grid_component = self.tariff.get_component(TariffType.GRID)
        if grid_component and allocated.total_consumption_kwh > 0:
            grid_fee = grid_component.calculate_cost(allocated.total_consumption_kwh)
            invoice.add_item(InvoiceItem(
                description="Grid Usage Fee",
                quantity=allocated.total_consumption_kwh,
                unit="kWh",
                unit_price=grid_component.price,
                total=grid_fee,
                category="grid"
            ))
        
        network_component = self.tariff.get_component(TariffType.NETWORK)
        if network_component and allocated.total_consumption_kwh > 0:
            network_fee = network_component.calculate_cost(allocated.total_consumption_kwh)
            invoice.add_item(InvoiceItem(
                description="Network Tariff",
                quantity=allocated.total_consumption_kwh,
                unit="kWh",
                unit_price=network_component.price,
                total=network_fee,
                category="grid"
            ))
        
        # Add feed-in credit
        if allocated.feed_in_kwh > 0:
            feed_in_component = self.tariff.get_component(TariffType.FEED_IN)
            feed_in_price = feed_in_component.price if feed_in_component else 0.10
            feed_in_revenue = allocated.feed_in_kwh * feed_in_price
            
            invoice.add_item(InvoiceItem(
                description="Feed-in Remuneration",
                quantity=allocated.feed_in_kwh,
                unit="kWh",
                unit_price=-feed_in_price,  # Negative = credit
                total=-feed_in_revenue,
                category="revenue"
            ))
        
        invoice.calculate_totals()
        return invoice
    
    def _get_energy_price(self) -> float:
        """Get base energy price from tariff."""
        energy_component = self.tariff.get_component(TariffType.ENERGY)
        if energy_component:
            return energy_component.price
        return 0.25  # Default
    
    def calculate_billing_result(self,
                                property_info: Property,
                                allocations: Dict[str, AllocatedEnergy],
                                period: BillingPeriod,
                                total_solar: float,
                                total_grid_import: float,
                                total_grid_export: float,
                                total_battery: float) -> BillingResult:
        """Calculate complete billing result for a property."""
        result = BillingResult(
            billing_period=period,
            property_id=property_info.id,
            property_name=property_info.name,
            total_consumption_kwh=sum(a.total_consumption_kwh for a in allocations.values()),
            total_solar_kwh=total_solar,
            total_grid_import_kwh=total_grid_import,
            total_grid_export_kwh=total_grid_export,
            total_battery_kwh=total_battery,
        )
        
        # Calculate self-consumption rate
        if total_solar > 0:
            used_solar = sum(a.solar_consumption_kwh for a in allocations.values())
            result.self_consumption_rate = used_solar / total_solar
        
        # Generate invoices
        for apt_id, allocation in allocations.items():
            apartment = property_info.get_apartment(apt_id)
            if not apartment:
                apartment = Apartment(id=apt_id, name=allocation.apartment_name)
            
            invoice = self.calculate_invoice(allocation, period, apartment)
            result.invoices.append(invoice)
            result.total_costs_chf += invoice.total
            result.total_revenue_chf += abs(sum(item.total for item in invoice.items if item.category == 'revenue'))
        
        return result


# ============================================================================
# PDF GENERATION SERVICE
# ============================================================================

class PDFGenerator:
    """Generates professional PDF invoices."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=12,
            spaceAfter=6,
        ))
    
    def generate_invoice_pdf(self, invoice: Invoice, output_path: Path) -> Path:
        """Generate PDF for a single invoice."""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Header
        elements.append(Paragraph("Electricity Bill", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.3*cm))
        
        # Invoice info table
        invoice_info = [
            ['Invoice Number:', invoice.invoice_number or invoice.id[:8]],
            ['Issue Date:', invoice.issue_date.strftime('%d.%m.%Y')],
            ['Due Date:', (invoice.due_date or invoice.issue_date).strftime('%d.%m.%Y')],
            ['Billing Period:', f"{invoice.billing_period.start_date.strftime('%d.%m.%Y')} - {invoice.billing_period.end_date.strftime('%d.%m.%Y')}"] if invoice.billing_period else ['Billing Period:', 'N/A'],
        ]
        
        info_table = Table(invoice_info, colWidths=[4*cm, 6*cm])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.5*cm))
        
        # Customer info
        elements.append(Paragraph(f"Customer: {invoice.apartment_name}", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*cm))
        
        # Items table
        data = [['Description', 'Quantity', 'Unit', 'Unit Price', 'Total']]
        for item in invoice.items:
            data.append([
                item.description,
                f"{item.quantity:,.2f}",
                item.unit,
                f"CHF {item.unit_price:.4f}",
                f"CHF {item.total:,.2f}"
            ])
        
        # Subtotal
        data.append(['', '', '', 'Subtotal:', f"CHF {invoice.subtotal:,.2f}"])
        data.append(['', '', '', f'VAT ({invoice.vat_rate}%):', f"CHF {invoice.vat_amount:,.2f}"])
        data.append(['', '', '', 'Total:', f"CHF {invoice.total:,.2f}"])
        
        items_table = Table(data, colWidths=[5*cm, 2.5*cm, 2*cm, 3*cm, 3*cm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -4), 0.5, colors.grey),
            ('GRID', (0, -3), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -4), 10),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 1*cm))
        
        # Footer
        if invoice.notes:
            elements.append(Paragraph("Notes:", self.styles['SectionHeader']))
            elements.append(Paragraph(invoice.notes, self.styles['Normal']))
        
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("Thank you for your business!", self.styles['Normal']))
        
        doc.build(elements)
        logger.info(f"Generated PDF: {output_path}")
        return output_path
    
    def generate_summary_pdf(self,
                           billing_result: BillingResult,
                           output_path: Path) -> Path:
        """Generate summary PDF for entire property."""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph(f"Billing Summary: {billing_result.property_name}", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.3*cm))
        
        # Period info
        period_str = f"{billing_result.billing_period.start_date.strftime('%d.%m.%Y')} - {billing_result.billing_period.end_date.strftime('%d.%m.%Y')}"
        elements.append(Paragraph(f"Period: {period_str}", self.styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Summary statistics
        summary_data = [
            ['Metric', 'Value'],
            ['Total Consumption', f"{billing_result.total_consumption_kwh:,.2f} kWh"],
            ['Solar Production', f"{billing_result.total_solar_kwh:,.2f} kWh"],
            ['Grid Import', f"{billing_result.total_grid_import_kwh:,.2f} kWh"],
            ['Grid Export', f"{billing_result.total_grid_export_kwh:,.2f} kWh"],
            ['Battery Usage', f"{billing_result.total_battery_kwh:,.2f} kWh"],
            ['Self-Consumption Rate', f"{billing_result.self_consumption_rate*100:.1f}%"],
            ['Total Costs', f"CHF {billing_result.total_costs_chf:,.2f}"],
            ['Total Revenue', f"CHF {billing_result.total_revenue_chf:,.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[7*cm, 5*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 1*cm))
        
        # Per-apartment breakdown
        elements.append(Paragraph("Per-Apartment Breakdown", self.styles['SectionHeader']))
        
        apt_data = [['Apartment', 'Consumption', 'Solar', 'Grid', 'Total Cost']]
        for invoice in billing_result.invoices:
            apt = next((i for i in billing_result.invoices if i.apartment_id == invoice.apartment_id), None)
            if apt:
                total_consumption = sum(item.quantity for item in apt.items if item.category == 'energy')
                solar = next((item.quantity for item in apt.items if 'solar' in item.description.lower()), 0)
                grid = next((item.quantity for item in apt.items if 'grid' in item.description.lower()), 0)
                apt_data.append([
                    invoice.apartment_name,
                    f"{total_consumption:,.1f} kWh",
                    f"{solar:,.1f} kWh",
                    f"{grid:,.1f} kWh",
                    f"CHF {invoice.total:,.2f}"
                ])
        
        apt_table = Table(apt_data, colWidths=[4*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        apt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(apt_table)
        
        doc.build(elements)
        logger.info(f"Generated summary PDF: {output_path}")
        return output_path


# ============================================================================
# DATABASE SERVICE
# ============================================================================

class DatabaseService:
    """Handles SQLite database operations."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
    
    def connect(self) -> None:
        """Connect to database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def create_tables(self) -> None:
        """Create database tables."""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        cursor.executescript(DATABASE_SCHEMA)
        self.conn.commit()
    
    def save_project(self, project: Project) -> None:
        """Save project to database."""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO projects (id, name, description, created_date, modified_date, config_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project.id,
            project.name,
            project.description,
            str(project.created_date),
            str(project.modified_date),
            json.dumps({
                'allocation_config': {
                    'strategy': project.allocation_config.strategy.value if project.allocation_config else 'priority',
                    'solar_discount': project.allocation_config.solar_discount if project.allocation_config else 0.02,
                } if project.allocation_config else {}
            })
        ))
        self.conn.commit()
    
    def load_projects(self) -> List[Dict]:
        """Load all projects."""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects")
        return [dict(row) for row in cursor.fetchall()]
    
    def save_invoice(self, invoice: Invoice, project_id: str) -> None:
        """Save invoice to database."""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (id, project_id, apartment_id, invoice_number, 
                                 billing_period_start, billing_period_end, issue_date,
                                 subtotal, vat_rate, vat_amount, total, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice.id,
            project_id,
            invoice.apartment_id,
            invoice.invoice_number,
            str(invoice.billing_period.start_date) if invoice.billing_period else None,
            str(invoice.billing_period.end_date) if invoice.billing_period else None,
            str(invoice.issue_date),
            invoice.subtotal,
            invoice.vat_rate,
            invoice.vat_amount,
            invoice.total,
            invoice.currency,
        ))
        self.conn.commit()


# Import json for database service
import json
