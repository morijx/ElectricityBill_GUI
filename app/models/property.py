"""Property and apartment models."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class MeterType(Enum):
    """Types of meters in the system."""
    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    APARTMENT = "apartment"
    SOLAR_PRODUCTION = "solar_production"
    BATTERY_CHARGE = "battery_charge"
    BATTERY_DISCHARGE = "battery_discharge"
    SHARED_AREA = "shared_area"
    EV_CHARGING = "ev_charging"


@dataclass
class Meter:
    """Represents an energy meter in the property."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    meter_type: MeterType = MeterType.APARTMENT
    serial_number: Optional[str] = None
    location: Optional[str] = None
    multiplier: float = 1.0  # For CT ratios etc.
    
    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.meter_type.value}_{self.id[:8]}"


@dataclass
class Apartment:
    """Represents a rental unit/apartment in the property."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    number: Optional[str] = None
    floor: Optional[int] = None
    area_sqm: Optional[float] = None
    tenant_name: Optional[str] = None
    tenant_email: Optional[str] = None
    meter_id: Optional[str] = None
    is_owner_occupied: bool = False  # True if owner lives here
    priority: int = 1  # Lower = higher priority for solar allocation
    fixed_fee: float = 0.0  # Monthly fixed fee in CHF
    discount_rate: float = 0.0  # Discount on solar energy (CHF/kWh)
    
    def __post_init__(self) -> None:
        if not self.name and self.number:
            self.name = f"Apartment {self.number}"
        elif not self.name:
            self.name = f"Unit_{self.id[:6]}"


@dataclass
class Property:
    """Represents a multi-unit property with energy systems."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    address: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "CH"
    
    # Meters
    meters: list[Meter] = field(default_factory=list)
    
    # Apartments
    apartments: list[Apartment] = field(default_factory=list)
    
    # Energy systems
    solar_system_id: Optional[str] = None
    battery_id: Optional[str] = None
    
    # Shared area meter
    shared_meter_id: Optional[str] = None
    
    def add_meter(self, meter: Meter) -> None:
        """Add a meter to the property."""
        self.meters.append(meter)
    
    def add_apartment(self, apartment: Apartment) -> None:
        """Add an apartment to the property."""
        self.apartments.append(apartment)
    
    def get_apartment_by_meter(self, meter_id: str) -> Optional[Apartment]:
        """Get apartment associated with a meter."""
        for apt in self.apartments:
            if apt.meter_id == meter_id:
                return apt
        return None
    
    def get_owner_apartment(self) -> Optional[Apartment]:
        """Get the owner-occupied apartment."""
        for apt in self.apartments:
            if apt.is_owner_occupied:
                return apt
        return None
    
    def get_tenant_apartments(self) -> list[Apartment]:
        """Get all tenant apartments (non-owner)."""
        return [apt for apt in self.apartments if not apt.is_owner_occupied]
    
    @property
    def apartment_count(self) -> int:
        """Return number of apartments."""
        return len(self.apartments)
