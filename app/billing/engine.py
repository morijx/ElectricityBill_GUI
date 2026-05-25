"""Main billing calculation engine."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .components import BillComponents
from .swiss_tariff import SwissTariffCalculator
from ..models.property import Property, Apartment
from ..models.tariff import SwissTariff
from ..models.project import Project, AllocationConfig
from ..models.energy_flow import EnergyFlow, EnergyData
from ..models.billing import Invoice, InvoiceItem, InvoiceSummary, BillingPeriod


@dataclass
class BillingResult:
    """Result of billing calculation for an apartment."""
    
    apartment_id: str
    apartment_name: str
    period: BillingPeriod
    
    # Consumption breakdown
    total_consumption_kwh: float = 0.0
    solar_consumption_kwh: 0.0
    grid_consumption_kwh: float = 0.0
    battery_consumption_kwh: float = 0.0
    
    # Export (for owner with feed-in)
    export_to_grid_kwh: float = 0.0
    
    # Costs
    energy_cost: float = 0.0
    grid_cost: float = 0.0
    network_cost: float = 0.0
    basic_fee: float = 0.0
    renewable_fee: float = 0.0
    other_fees: float = 0.0
    feed_in_revenue: float = 0.0
    
    # Totals
    subtotal: float = 0.0
    vat_amount: float = 0.0
    total_due: float = 0.0
    
    # Savings
    solar_savings: float = 0.0
    
    # Bill components
    components: Optional[BillComponents] = None
    
    def to_invoice(self, project: Project, 
                   recipient_name: Optional[str] = None,
                   recipient_address: Optional[str] = None) -> Invoice:
        """Convert billing result to invoice."""
        apt = next(
            (a for a in project.property_info.apartments if a.id == self.apartment_id),
            None
        )
        
        invoice = Invoice(
            property_id=project.property_info.id,
            apartment_id=self.apartment_id,
            billing_period_id=self.period.id,
            period_start=self.period.start_date,
            period_end=self.period.end_date,
            recipient_name=recipient_name or (apt.tenant_name if apt else None),
            recipient_address=recipient_address,
        )
        
        # Add items from components
        if self.components:
            for comp in self.components.get_itemized_list():
                item = InvoiceItem(
                    description=comp.description,
                    category=comp.category,
                    quantity=comp.quantity,
                    unit=comp.unit,
                    unit_price=comp.unit_price,
                    solar_quantity=comp.solar_quantity,
                    grid_quantity=comp.grid_quantity,
                    solar_discount=comp.solar_discount_per_kwh,
                    is_percentage=comp.is_percentage,
                    percentage_base=comp.base_amount if comp.is_percentage else 0,
                )
                invoice.add_item(item)
        
        invoice.calculate_summary()
        return invoice


class BillingEngine:
    """Main billing calculation engine.
    
    Orchestrates the complete billing process:
    1. Takes allocated energy flows
    2. Applies tariff calculations
    3. Generates invoices per apartment
    """
    
    def __init__(self, project: Project) -> None:
        """Initialize billing engine with project configuration."""
        self.project = project
        self.tariff_calculator = SwissTariffCalculator(project.tariff)
    
    def calculate_apartment_bill(self,
                                  apartment: Apartment,
                                  energy_flows: list[EnergyFlow],
                                  period: BillingPeriod) -> BillingResult:
        """Calculate bill for a single apartment.
        
        Args:
            apartment: The apartment to bill
            energy_flows: List of allocated energy flows for the period
            period: Billing period
            
        Returns:
            BillingResult with all calculations
        """
        result = BillingResult(
            apartment_id=apartment.id,
            apartment_name=apartment.name,
            period=period,
        )
        
        # Sum up energy flows
        total_consumption = 0.0
        solar_consumption = 0.0
        grid_consumption = 0.0
        battery_consumption = 0.0
        export_to_grid = 0.0
        
        for flow in energy_flows:
            if apartment.is_owner_occupied:
                # Owner's consumption
                total_consumption += flow.owner_consumption
                solar_consumption += flow.solar_to_owner
                battery_consumption += flow.battery_to_owner
                grid_consumption += flow.grid_to_owner
                
                # Owner gets feed-in revenue for excess solar
                export_to_grid += flow.solar_to_grid
            else:
                # Tenant's consumption
                tenant_consumption = flow.tenant_consumptions.get(apartment.id, 0.0)
                total_consumption += tenant_consumption
                solar_consumption += flow.solar_to_tenants.get(apartment.id, 0.0)
                battery_consumption += flow.battery_to_tenants.get(apartment.id, 0.0)
                grid_consumption += flow.grid_to_tenants.get(apartment.id, 0.0)
        
        result.total_consumption_kwh = total_consumption
        result.solar_consumption_kwh = solar_consumption
        result.grid_consumption_kwh = grid_consumption
        result.battery_consumption_kwh = battery_consumption
        result.export_to_grid_kwh = export_to_grid
        
        # Calculate costs using Swiss tariff
        months = period.months_in_period
        solar_discount = self.project.allocation_config.tenant_solar_discount
        
        # For tenants, only apply discount if they got solar energy
        if not apartment.is_owner_occupied:
            effective_discount = solar_discount
        else:
            effective_discount = 0.0  # Owner doesn't get discount on own solar
        
        components = self.tariff_calculator.build_complete_bill(
            consumption_kwh=total_consumption,
            solar_kwh=solar_consumption,
            grid_kwh=grid_consumption,
            export_kwh=export_to_grid if apartment.is_owner_occupied else 0.0,
            months=months,
            solar_discount=effective_discount if not apartment.is_owner_occupied else 0.0,
        )
        
        result.components = components
        
        # Extract component values
        result.energy_cost = components.energy.amount
        result.grid_cost = components.grid_usage.amount
        result.network_cost = components.network_tariff.amount
        result.basic_fee = components.basic_fee.amount + components.metering_fee.amount
        result.renewable_fee = components.renewable_fee.amount
        result.feed_in_revenue = components.feed_in.amount
        
        # Calculate totals
        result.subtotal = components.get_subtotal()
        result.vat_amount = components.get_vat_amount()
        result.total_due = components.get_total()
        
        # Calculate solar savings (compared to all-grid scenario)
        if total_consumption > 0:
            avg_price = result.energy_cost / total_consumption if total_consumption > 0 else 0
            result.solar_savings = solar_consumption * avg_price * (
                solar_discount / avg_price if avg_price > 0 else 0
            )
        
        return result
    
    def calculate_all_bills(self,
                           energy_flows: list[EnergyFlow],
                           period: BillingPeriod) -> dict[str, BillingResult]:
        """Calculate bills for all apartments.
        
        Args:
            energy_flows: List of allocated energy flows for the period
            period: Billing period
            
        Returns:
            Dictionary mapping apartment IDs to BillingResults
        """
        results = {}
        
        for apartment in self.project.property_info.apartments:
            result = self.calculate_apartment_bill(apartment, energy_flows, period)
            results[apartment.id] = result
        
        return results
    
    def generate_invoices(self,
                         results: dict[str, BillingResult]) -> list[Invoice]:
        """Generate invoices from billing results.
        
        Args:
            results: Dictionary of billing results by apartment ID
            
        Returns:
            List of Invoice objects
        """
        invoices = []
        
        for apt_id, result in results.items():
            apartment = next(
                (a for a in self.project.property_info.apartments if a.id == apt_id),
                None
            )
            
            if apartment:
                invoice = result.to_invoice(
                    self.project,
                    recipient_name=apartment.tenant_name,
                    recipient_email=apartment.tenant_email,
                )
                invoices.append(invoice)
        
        return invoices
    
    def calculate_shared_area_allocation(self,
                                         shared_consumption_kwh: float,
                                         total_apartment_consumption: float) -> dict[str, float]:
        """Allocate shared area consumption to apartments.
        
        Args:
            shared_consumption_kwh: Total shared area consumption
            total_apartment_consumption: Sum of all apartment consumptions
            
        Returns:
            Dictionary mapping apartment IDs to their share of shared consumption
        """
        allocation_mode = self.project.allocation_config.shared_area_allocation
        allocations = {}
        
        if total_apartment_consumption <= 0:
            # Equal split if no consumption data
            n_apartments = len(self.project.property_info.apartments)
            if n_apartments > 0:
                equal_share = shared_consumption_kwh / n_apartments
                for apt in self.project.property_info.apartments:
                    allocations[apt.id] = equal_share
            return allocations
        
        if allocation_mode == "proportional":
            # Proportional to consumption
            for apt in self.project.property_info.apartments:
                # Will be filled in when actual consumption is known
                allocations[apt.id] = 0.0
        elif allocation_mode == "equal":
            # Equal split
            n_apartments = len(self.project.property_info.apartments)
            equal_share = shared_consumption_kwh / n_apartments
            for apt in self.project.property_info.apartments:
                allocations[apt.id] = equal_share
        elif allocation_mode == "fixed":
            # Fixed percentages from config
            for apt_id, percentage in self.project.allocation_config.shared_area_percentage.items():
                allocations[apt_id] = shared_consumption_kwh * (percentage / 100.0)
        
        return allocations
