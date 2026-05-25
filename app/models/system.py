"""Solar system and battery models."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class SolarSystem:
    """Represents a solar PV system."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Solar System"
    
    # Technical specifications
    peak_power_kwp: float = 0.0  # Peak power in kWp
    panel_area_sqm: Optional[float] = None
    panel_efficiency: float = 0.20  # Panel efficiency (20% typical)
    inverter_efficiency: float = 0.96  # Inverter efficiency
    
    # Installation details
    installation_date: Optional[datetime] = None
    orientation_degrees: float = 180.0  # South = 180
    tilt_angle_degrees: float = 30.0  # Roof tilt
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None
    
    # Meter association
    production_meter_id: Optional[str] = None
    
    # Performance
    expected_annual_production_kwh: Optional[float] = None
    
    def estimate_hourly_production(self, hour: int, month: int, 
                                   irradiance_factor: float = 1.0) -> float:
        """Estimate hourly production based on simplified model."""
        # Simplified model - real implementation would use weather data
        # Peak sun hours typically 10-14
        if 10 <= hour <= 14:
            base_factor = 1.0
        elif 8 <= hour <= 16:
            base_factor = 0.5
        elif 6 <= hour <= 18:
            base_factor = 0.2
        else:
            return 0.0
        
        # Seasonal adjustment (Switzerland)
        seasonal_factors = {
            1: 0.4, 2: 0.5, 3: 0.7, 4: 0.9, 5: 1.1, 6: 1.2,
            7: 1.2, 8: 1.1, 9: 0.9, 10: 0.7, 11: 0.5, 12: 0.4
        }
        seasonal = seasonal_factors.get(month, 0.8)
        
        return (self.peak_power_kwp * base_factor * seasonal * 
                self.inverter_efficiency * irradiance_factor)


@dataclass
class BatteryState:
    """Current state of the battery."""
    
    timestamp: datetime
    soc_percentage: float = 0.0  # State of charge (0-100%)
    soc_kwh: float = 0.0  # State of charge in kWh
    voltage: float = 0.0  # Battery voltage
    current: float = 0.0  # Positive = charging, negative = discharging
    power: float = 0.0  # Positive = charging, negative = discharging
    temperature: float = 20.0  # Celsius
    cycle_count: int = 0
    
    @property
    def is_charging(self) -> bool:
        """Check if battery is charging."""
        return self.current > 0
    
    @property
    def is_discharging(self) -> bool:
        """Check if battery is discharging."""
        return self.current < 0


@dataclass
class Battery:
    """Represents a battery energy storage system."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Battery System"
    
    # Capacity
    nominal_capacity_kwh: float = 0.0
    usable_capacity_kwh: float = 0.0  # Typically 90% of nominal
    max_soc: float = 100.0  # Maximum state of charge (%)
    min_soc: float = 10.0  # Minimum state of charge (%)
    
    # Power ratings
    max_charge_power_kw: float = 0.0
    max_discharge_power_kw: float = 0.0
    
    # Efficiency
    charge_efficiency: float = 0.95  # Charging efficiency
    discharge_efficiency: float = 0.95  # Discharging efficiency
    
    # Degradation
    degradation_rate: float = 0.02  # Annual capacity loss (%)
    installation_date: Optional[datetime] = None
    
    # Meters
    charge_meter_id: Optional[str] = None
    discharge_meter_id: Optional[str] = None
    
    # Control strategy
    priority_mode: str = "self_consumption"  # self_consumption, time_of_use, etc.
    reserve_percentage: float = 10.0  # Reserve for emergencies
    
    # Current state
    current_state: Optional[BatteryState] = None
    
    def __post_init__(self) -> None:
        if self.usable_capacity_kwh == 0.0 and self.nominal_capacity_kwh > 0:
            self.usable_capacity_kwh = self.nominal_capacity_kwh * 0.9
    
    def available_capacity(self) -> float:
        """Get available discharge capacity in kWh."""
        if self.current_state is None:
            return 0.0
        current_soc = self.current_state.soc_kwh
        min_soc_kwh = self.nominal_capacity_kwh * (self.min_soc / 100.0)
        return max(0.0, current_soc - min_soc_kwh) * self.discharge_efficiency
    
    def available_charge_capacity(self) -> float:
        """Get available charge capacity in kWh."""
        if self.current_state is None:
            return 0.0
        current_soc = self.current_state.soc_kwh
        max_soc_kwh = self.nominal_capacity_kwh * (self.max_soc / 100.0)
        return max(0.0, max_soc_kwh - current_soc) / self.charge_efficiency
    
    def can_discharge(self, power_kw: float, duration_hours: float) -> bool:
        """Check if battery can discharge at given power for duration."""
        energy_needed = power_kw * duration_hours
        return self.available_capacity() >= energy_needed
    
    def update_soc(self, energy_kwh: float, is_charging: bool) -> float:
        """Update state of charge and return new SOC."""
        if self.current_state is None:
            return 0.0
        
        if is_charging:
            actual_energy = energy_kwh * self.charge_efficiency
            new_soc = self.current_state.soc_kwh + actual_energy
            max_soc_kwh = self.nominal_capacity_kwh * (self.max_soc / 100.0)
            new_soc = min(new_soc, max_soc_kwh)
        else:
            actual_energy = energy_kwh / self.discharge_efficiency
            new_soc = self.current_state.soc_kwh - actual_energy
            min_soc_kwh = self.nominal_capacity_kwh * (self.min_soc / 100.0)
            new_soc = max(new_soc, min_soc_kwh)
        
        self.current_state.soc_kwh = new_soc
        self.current_state.soc_percentage = (new_soc / self.nominal_capacity_kwh) * 100.0
        return new_soc
