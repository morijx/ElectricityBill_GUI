"""Tariff models for Swiss electricity billing."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Optional
from uuid import uuid4


class TariffType(Enum):
    """Types of tariff components."""
    ENERGY = "energy"  # Energy price per kWh
    GRID = "grid"  # Grid usage fee
    NETWORK = "network"  # Network tariff
    BASIC = "basic"  # Basic monthly fee
    PEAK = "peak"  # Peak time tariff
    OFF_PEAK = "off_peak"  # Off-peak tariff
    FEED_IN = "feed_in"  # Feed-in remuneration
    TAX = "tax"  # Taxes
    VAT = "vat"  # Value added tax
    RENEWABLE = "renewable"  # Renewable energy fee (KEV/PR)
    METERING = "metering"  # Metering fee
    CONcession = "concession"  # Concession fees


class TimeOfUsePeriod(Enum):
    """Time of use periods."""
    PEAK = "peak"
    OFF_PEAK = "off_peak"
    NIGHT = "night"
    WEEKEND = "weekend"


@dataclass
class TariffPeriod:
    """Defines a time period for time-of-use tariffs."""
    
    name: str = ""
    start_time: time = field(default_factory=lambda: time(0, 0))
    end_time: time = field(default_factory=lambda: time(23, 59))
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # Mon=0, Sun=6
    price_per_kwh: float = 0.0  # CHF/kWh
    
    def is_active(self, hour: int, minute: int, weekday: int) -> bool:
        """Check if this period is active at the given time."""
        if weekday not in self.days:
            return False
        
        current_minutes = hour * 60 + minute
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        
        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes < end_minutes
        else:
            # Spans midnight
            return current_minutes >= start_minutes or current_minutes < end_minutes


@dataclass
class TariffComponent:
    """A single component of the electricity tariff."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    component_type: TariffType = TariffType.ENERGY
    price: float = 0.0  # Price in CHF
    unit: str = "kWh"  # kWh, month, year, etc.
    is_percentage: bool = False  # True if price is a percentage
    applies_to: list[str] = field(default_factory=list)  # What this applies to
    
    # Time of use
    periods: list[TariffPeriod] = field(default_factory=list)
    has_time_of_use: bool = False
    
    # Minimum/maximum
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    def calculate_cost(self, consumption_kwh: float, 
                       hour: Optional[int] = None,
                       minute: Optional[int] = None,
                       weekday: Optional[int] = None) -> float:
        """Calculate cost for given consumption."""
        if self.is_percentage:
            # Percentage-based (e.g., VAT)
            return consumption_kwh * (self.price / 100.0)
        
        if self.has_time_of_use and hour is not None:
            # Find applicable period
            m = minute or 0
            wd = weekday or 0
            for period in self.periods:
                if period.is_active(hour, m, wd):
                    return consumption_kwh * period.price_per_kwh
            # Default to base price if no period matches
            return consumption_kwh * self.price
        
        # Simple linear pricing
        return consumption_kwh * self.price


@dataclass
class SwissTariff:
    """Swiss electricity tariff configuration."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Standard Swiss Tariff"
    year: int = 2024
    currency: str = "CHF"
    utility_company: Optional[str] = None
    
    # Standard components
    components: list[TariffComponent] = field(default_factory=list)
    
    # Time of use periods
    peak_hours: tuple[int, int] = (7, 20)  # 7:00 - 20:00
    off_peak_hours: tuple[int, int] = (20, 7)  # 20:00 - 7:00
    
    # Default values (can be overridden by components)
    energy_price_peak: float = 0.25  # CHF/kWh
    energy_price_off_peak: float = 0.18  # CHF/kWh
    grid_fee: float = 0.08  # CHF/kWh
    network_tariff: float = 0.05  # CHF/kWh
    basic_fee_monthly: float = 15.0  # CHF/month
    feed_in_remuneration: float = 0.10  # CHF/kWh
    renewable_fee: float = 0.023  # CHF/kWh (KEV/PR)
    vat_rate: float = 8.1  # Percent (Swiss standard rate)
    
    def add_component(self, component: TariffComponent) -> None:
        """Add a tariff component."""
        self.components.append(component)
    
    def get_component(self, component_type: TariffType) -> Optional[TariffComponent]:
        """Get a component by type."""
        for comp in self.components:
            if comp.component_type == component_type:
                return comp
        return None
    
    def create_default_components(self) -> None:
        """Create default Swiss tariff components."""
        self.components = [
            TariffComponent(
                name="Energy (Peak)",
                component_type=TariffType.ENERGY,
                price=self.energy_price_peak,
                unit="kWh",
                has_time_of_use=True,
                periods=[
                    TariffPeriod(
                        name="Peak",
                        start_time=time(self.peak_hours[0], 0),
                        end_time=time(self.peak_hours[1], 0),
                        days=[0, 1, 2, 3, 4],  # Weekdays
                        price_per_kwh=self.energy_price_peak,
                    ),
                    TariffPeriod(
                        name="Off-Peak",
                        start_time=time(0, 0),
                        end_time=time(23, 59),
                        price_per_kwh=self.energy_price_off_peak,
                    ),
                ],
            ),
            TariffComponent(
                name="Grid Usage",
                component_type=TariffType.GRID,
                price=self.grid_fee,
                unit="kWh",
            ),
            TariffComponent(
                name="Network Tariff",
                component_type=TariffType.NETWORK,
                price=self.network_tariff,
                unit="kWh",
            ),
            TariffComponent(
                name="Basic Fee",
                component_type=TariffType.BASIC,
                price=self.basic_fee_monthly,
                unit="month",
            ),
            TariffComponent(
                name="Feed-in Remuneration",
                component_type=TariffType.FEED_IN,
                price=self.feed_in_remuneration,
                unit="kWh",
            ),
            TariffComponent(
                name="Renewable Energy Fee (KEV/PR)",
                component_type=TariffType.RENEWABLE,
                price=self.renewable_fee,
                unit="kWh",
            ),
            TariffComponent(
                name="VAT",
                component_type=TariffType.VAT,
                price=self.vat_rate,
                unit="percent",
                is_percentage=True,
            ),
        ]
    
    @property
    def total_energy_price(self) -> float:
        """Get total energy price including all components (excluding VAT)."""
        total = 0.0
        for comp in self.components:
            if comp.component_type in [TariffType.ENERGY, TariffType.GRID, 
                                        TariffType.NETWORK, TariffType.RENEWABLE]:
                if not comp.is_percentage:
                    total += comp.price
        return total
