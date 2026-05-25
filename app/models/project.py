"""Project configuration and allocation settings."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional
from uuid import uuid4

from .property import Property
from .tariff import SwissTariff
from .system import SolarSystem, Battery


class AllocationStrategy(Enum):
    """Energy allocation strategies."""
    PRIORITY = "priority"  # Owner first, then tenants
    PROPORTIONAL = "proportional"  # Proportional to consumption
    EQUAL = "equal"  # Equal sharing
    CUSTOM = "custom"  # Custom rules


class BatteryAllocationMode(Enum):
    """Battery energy allocation modes."""
    OWNER_FIRST = "owner_first"  # Owner gets battery energy first
    PROPORTIONAL = "proportional"  # Proportional to consumption
    PEAK_SHAVING = "peak_shaving"  # Used for peak load reduction
    OPTIMIZED = "optimized"  # Cost-optimized distribution


@dataclass
class AllocationConfig:
    """Configuration for energy allocation rules."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Default Allocation"
    
    # Strategy selection
    strategy: AllocationStrategy = AllocationStrategy.PRIORITY
    
    # Priority order (list of apartment IDs, lower index = higher priority)
    priority_order: list[str] = field(default_factory=list)
    
    # Solar allocation
    solar_self_consumption_priority: bool = True  # Self-consume before selling
    owner_solar_priority: bool = True  # Owner gets solar first
    tenant_solar_discount: float = 0.02  # CHF/kWh discount for tenants
    max_solar_to_tenants: Optional[float] = None  # Max kWh to tenants
    
    # Battery allocation
    battery_mode: BatteryAllocationMode = BatteryAllocationMode.OWNER_FIRST
    battery_reserve_kwh: float = 0.0  # Keep this much in reserve
    battery_to_owner_first: bool = True
    
    # Shared area allocation
    shared_area_allocation: str = "proportional"  # proportional, equal, fixed
    shared_area_percentage: dict[str, float] = field(default_factory=dict)
    
    # Custom rules
    custom_rules: dict[str, float] = field(default_factory=dict)
    
    def get_apartment_priority(self, apartment_id: str) -> int:
        """Get priority for an apartment (lower = higher priority)."""
        if apartment_id in self.priority_order:
            return self.priority_order.index(apartment_id)
        return 999  # Default low priority


@dataclass
class Project:
    """Main project container."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "New Project"
    created_date: date = field(default_factory=lambda: date.today())
    last_modified: date = field(default_factory=lambda: date.today())
    
    # Property information
    property: Optional[Property] = None
    
    # Energy systems
    solar_system: Optional[SolarSystem] = None
    battery: Optional[Battery] = None
    
    # Tariff configuration
    tariff: Optional[SwissTariff] = None
    
    # Allocation configuration
    allocation_config: AllocationConfig = field(default_factory=AllocationConfig)
    
    # Billing periods available
    billing_periods: list[str] = field(default_factory=list)
    
    # File paths for imported data
    data_files: dict[str, str] = field(default_factory=dict)
    
    # Settings
    currency: str = "CHF"
    language: str = "en"  # en, de
    timezone: str = "Europe/Zurich"
    
    def __post_init__(self) -> None:
        if self.property is None:
            self.property = Property()
        if self.tariff is None:
            self.tariff = SwissTariff()
            self.tariff.create_default_components()
    
    def update_modified_date(self) -> None:
        """Update the last modified date."""
        from datetime import date
        self.last_modified = date.today()
    
    @property
    def has_solar(self) -> bool:
        """Check if project has solar system."""
        return self.solar_system is not None
    
    @property
    def has_battery(self) -> bool:
        """Check if project has battery system."""
        return self.battery is not None
    
    @property
    def apartment_count(self) -> int:
        """Get number of apartments."""
        if self.property is None:
            return 0
        return self.property.apartment_count
    
    def get_owner_apartment_id(self) -> Optional[str]:
        """Get the owner apartment ID."""
        if self.property is None:
            return None
        owner_apt = self.property.get_owner_apartment()
        return owner_apt.id if owner_apt else None
