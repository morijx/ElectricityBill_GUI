"""Energy flow data models."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4


@dataclass
class TimeInterval:
    """Represents a time interval for energy data."""
    
    start: datetime
    end: datetime
    duration_minutes: int = 15
    
    def __post_init__(self) -> None:
        if self.duration_minutes is None:
            delta = self.end - self.start
            self.duration_minutes = int(delta.total_seconds() / 60)
    
    @property
    def duration_hours(self) -> float:
        """Return duration in hours."""
        return self.duration_minutes / 60.0
    
    @classmethod
    def from_timestamp(cls, timestamp: datetime, 
                       duration_minutes: int = 15) -> "TimeInterval":
        """Create interval from start timestamp."""
        end = timestamp + timedelta(minutes=duration_minutes)
        return cls(start=timestamp, end=end, duration_minutes=duration_minutes)


@dataclass
class EnergyData:
    """Raw energy data point for a single interval."""
    
    timestamp: datetime
    interval: Optional[TimeInterval] = None
    
    # Energy values in kWh for the interval
    grid_import: float = 0.0
    grid_export: float = 0.0
    solar_production: float = 0.0
    battery_charge: float = 0.0
    battery_discharge: float = 0.0
    consumption: float = 0.0  # Total consumption (apartments + shared)
    
    # Meter-specific readings
    meter_readings: dict[str, float] = field(default_factory=dict)
    
    # Derived values
    net_grid_flow: float = 0.0  # Import - Export
    solar_self_consumption: float = 0.0
    solar_surplus: float = 0.0
    battery_soc: float = 0.0  # State of charge percentage
    
    def __post_init__(self) -> None:
        if self.interval is None:
            self.interval = TimeInterval.from_timestamp(self.timestamp)
        self.net_grid_flow = self.grid_import - self.grid_export
    
    @property
    def hour(self) -> int:
        """Get hour of timestamp."""
        return self.timestamp.hour
    
    @property
    def minute(self) -> int:
        """Get minute of timestamp."""
        return self.timestamp.minute
    
    @property
    def weekday(self) -> int:
        """Get weekday (0=Monday, 6=Sunday)."""
        return self.timestamp.weekday()


@dataclass
class EnergyFlow:
    """Processed energy flow for allocation calculations."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    interval: Optional[TimeInterval] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Source energy
    solar_available: float = 0.0  # Total solar production
    grid_import_available: float = 0.0
    battery_discharge_available: float = 0.0
    
    # Consumption by entity
    owner_consumption: float = 0.0
    tenant_consumptions: dict[str, float] = field(default_factory=dict)
    shared_consumption: float = 0.0
    
    # Allocated energy
    solar_to_owner: float = 0.0
    solar_to_tenants: dict[str, float] = field(default_factory=dict)
    solar_to_battery: float = 0.0
    solar_to_grid: float = 0.0  # Excess fed to grid
    
    grid_to_owner: float = 0.0
    grid_to_tenants: dict[str, float] = field(default_factory=dict)
    grid_to_shared: float = 0.0
    
    battery_to_owner: float = 0.0
    battery_to_tenants: dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        if self.interval is None:
            self.interval = TimeInterval.from_timestamp(self.timestamp)
    
    def total_tenant_consumption(self) -> float:
        """Sum of all tenant consumptions."""
        return sum(self.tenant_consumptions.values())
    
    def total_solar_allocated(self) -> float:
        """Total solar energy allocated."""
        total = self.solar_to_owner + sum(self.solar_to_tenants.values())
        total += self.solar_to_battery + self.solar_to_grid
        return total
    
    def total_consumption(self) -> float:
        """Total consumption across all entities."""
        return (self.owner_consumption + self.total_tenant_consumption() 
                + self.shared_consumption)
