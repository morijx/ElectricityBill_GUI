"""Swiss tariff calculator."""

from __future__ import annotations
from typing import Optional

from .components import BillComponent, BillComponents
from ..models.tariff import SwissTariff, TariffType
from ..models.energy_flow import EnergyFlow


class SwissTariffCalculator:
    """Calculator for Swiss electricity tariffs.
    
    Handles all Swiss-specific tariff calculations including:
    - Energy prices (peak/off-peak)
    - Grid usage fees
    - Network tariffs
    - Renewable energy fees (KEV/PR)
    - Concession fees
    - VAT
    """
    
    def __init__(self, tariff: SwissTariff) -> None:
        """Initialize with a Swiss tariff configuration."""
        self.tariff = tariff
    
    def calculate_energy_cost(self, total_kwh: float,
                              solar_kwh: float = 0.0,
                              grid_kwh: float = 0.0,
                              solar_discount: float = 0.0) -> BillComponent:
        """Calculate energy cost component."""
        component = BillComponent(
            name="Energy",
            description="Electricity consumption cost",
            category="energy",
            quantity=total_kwh,
            solar_quantity=solar_kwh,
            grid_quantity=grid_kwh,
            solar_discount_per_kwh=solar_discount,
        )
        
        # Get energy price from tariff
        energy_comp = self.tariff.get_component(TariffType.ENERGY)
        if energy_comp:
            component.unit_price = energy_comp.price
        else:
            component.unit_price = self.tariff.energy_price_peak
        
        return component
    
    def calculate_grid_cost(self, consumption_kwh: float) -> BillComponent:
        """Calculate grid usage fee."""
        component = BillComponent(
            name="Grid Usage",
            description="Distribution grid usage fee",
            category="grid",
            quantity=consumption_kwh,
        )
        
        grid_comp = self.tariff.get_component(TariffType.GRID)
        if grid_comp:
            component.unit_price = grid_comp.price
        else:
            component.unit_price = self.tariff.grid_fee
        
        return component
    
    def calculate_network_cost(self, consumption_kwh: float) -> BillComponent:
        """Calculate network tariff."""
        component = BillComponent(
            name="Network Tariff",
            description="Network infrastructure fee",
            category="network",
            quantity=consumption_kwh,
        )
        
        network_comp = self.tariff.get_component(TariffType.NETWORK)
        if network_comp:
            component.unit_price = network_comp.price
        else:
            component.unit_price = self.tariff.network_tariff
        
        return component
    
    def calculate_basic_fee(self, months: float = 1.0) -> BillComponent:
        """Calculate basic monthly fee."""
        component = BillComponent(
            name="Basic Fee",
            description="Monthly basic fee",
            category="basic",
            quantity=months,
            unit="month",
        )
        
        basic_comp = self.tariff.get_component(TariffType.BASIC)
        if basic_comp:
            component.unit_price = basic_comp.price
        else:
            component.unit_price = self.tariff.basic_fee_monthly
        
        return component
    
    def calculate_renewable_fee(self, consumption_kwh: float) -> BillComponent:
        """Calculate renewable energy fee (KEV/PR)."""
        component = BillComponent(
            name="Renewable Energy Fee",
            description="Feed-in promotion (KEV/PR)",
            category="renewable",
            quantity=consumption_kwh,
        )
        
        renewable_comp = self.tariff.get_component(TariffType.RENEWABLE)
        if renewable_comp:
            component.unit_price = renewable_comp.price
        else:
            component.unit_price = self.tariff.renewable_fee
        
        return component
    
    def calculate_feed_in(self, export_kwh: float) -> BillComponent:
        """Calculate feed-in remuneration."""
        component = BillComponent(
            name="Feed-in Remuneration",
            description="Solar export to grid",
            category="feed_in",
            quantity=export_kwh,
        )
        
        feed_in_comp = self.tariff.get_component(TariffType.FEED_IN)
        if feed_in_comp:
            component.unit_price = feed_in_comp.price
        else:
            component.unit_price = self.tariff.feed_in_remuneration
        
        return component
    
    def calculate_vat(self, subtotal: float) -> BillComponent:
        """Calculate VAT."""
        component = BillComponent(
            name="VAT",
            description=f"Value added tax ({self.tariff.vat_rate}%)",
            category="tax",
            is_percentage=True,
            percentage_rate=self.tariff.vat_rate,
            base_amount=subtotal,
        )
        
        return component
    
    def build_complete_bill(self, 
                           consumption_kwh: float,
                           solar_kwh: float = 0.0,
                           grid_kwh: float = 0.0,
                           export_kwh: float = 0.0,
                           months: float = 1.0,
                           solar_discount: float = 0.0) -> BillComponents:
        """Build complete bill with all Swiss components.
        
        Args:
            consumption_kwh: Total consumption in kWh
            solar_kwh: Solar energy consumed in kWh
            grid_kwh: Grid energy consumed in kWh
            export_kwh: Energy exported to grid in kWh
            months: Number of months in billing period
            solar_discount: Discount per kWh for solar energy
            
        Returns:
            BillComponents with all calculated values
        """
        components = BillComponents()
        
        # Energy cost
        components.energy = self.calculate_energy_cost(
            total_kwh=consumption_kwh,
            solar_kwh=solar_kwh,
            grid_kwh=grid_kwh,
            solar_discount=solar_discount,
        )
        
        # Grid usage
        components.grid_usage = self.calculate_grid_cost(consumption_kwh)
        
        # Network tariff
        components.network_tariff = self.calculate_network_cost(consumption_kwh)
        
        # Basic fee (pro-rated for period)
        components.basic_fee = self.calculate_basic_fee(months)
        
        # Renewable fee
        components.renewable_fee = self.calculate_renewable_fee(consumption_kwh)
        
        # Feed-in revenue
        components.feed_in = self.calculate_feed_in(export_kwh)
        
        # VAT (calculated last)
        subtotal = components.get_subtotal()
        components.vat = self.calculate_vat(subtotal)
        
        return components
