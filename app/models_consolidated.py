"""
Electricity Billing System - Consolidated Models Module

This module contains all data models for the electricity billing system including:
- Property and apartment models
- Energy flow and metering data
- Tariff structures (Swiss-specific)
- Billing records and invoices
- Project configuration and allocation strategies
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time, date
from enum import Enum
from typing import Optional, Dict, List, Any, TypeVar, Generic
from uuid import uuid4
from pathlib import Path
import json


# ============================================================================
# ENUMS AND TYPE DEFINITIONS
# ============================================================================

class TariffType(Enum):
    """Types of tariff components."""
    ENERGY = "energy"
    GRID = "grid"
    NETWORK = "network"
    BASIC = "basic"
    PEAK = "peak"
    OFF_PEAK = "off_peak"
    FEED_IN = "feed_in"
    TAX = "tax"
    VAT = "vat"
    RENEWABLE = "renewable"
    METERING = "metering"
    CONCESSION = "concession"


class TimeOfUsePeriod(Enum):
    """Time of use periods."""
    PEAK = "peak"
    OFF_PEAK = "off_peak"
    NIGHT = "night"
    WEEKEND = "weekend"


class MeterType(Enum):
    """Types of meters."""
    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    SOLAR_PRODUCTION = "solar_production"
    BATTERY_CHARGE = "battery_charge"
    BATTERY_DISCHARGE = "battery_discharge"
    APARTMENT_CONSUMPTION = "apartment_consumption"
    SHARED_CONSUMPTION = "shared_consumption"
    EV_CHARGING = "ev_charging"


class AllocationStrategyType(Enum):
    """Available allocation strategies."""
    PRIORITY = "priority"  # Owner-first allocation
    EQUAL = "equal"  # Equal sharing
    PROPORTIONAL = "proportional"  # Proportional to consumption
    CUSTOM = "custom"  # Custom rules


# ============================================================================
# TARIFF MODELS
# ============================================================================

@dataclass
class TariffPeriod:
    """Defines a time period for time-of-use tariffs."""
    name: str = ""
    start_time: time = field(default_factory=lambda: time(0, 0))
    end_time: time = field(default_factory=lambda: time(23, 59))
    days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    price_per_kwh: float = 0.0
    
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
            return current_minutes >= start_minutes or current_minutes < end_minutes


@dataclass
class TariffComponent:
    """A single component of the electricity tariff."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    component_type: TariffType = TariffType.ENERGY
    price: float = 0.0
    unit: str = "kWh"
    is_percentage: bool = False
    applies_to: List[str] = field(default_factory=list)
    periods: List[TariffPeriod] = field(default_factory=list)
    has_time_of_use: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    def calculate_cost(self, consumption_kwh: float, 
                       hour: Optional[int] = None,
                       minute: Optional[int] = None,
                       weekday: Optional[int] = None) -> float:
        """Calculate cost for given consumption."""
        if self.is_percentage:
            return consumption_kwh * (self.price / 100.0)
        
        if self.has_time_of_use and hour is not None:
            m = minute or 0
            wd = weekday or 0
            for period in self.periods:
                if period.is_active(hour, m, wd):
                    return consumption_kwh * period.price_per_kwh
            return consumption_kwh * self.price
        
        return consumption_kwh * self.price


@dataclass
class Tariff(ABC):
    """Abstract base class for all tariff types."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Tariff"
    year: int = 2024
    currency: str = "CHF"
    
    @abstractmethod
    def calculate_cost(self, consumption_kwh: float, **kwargs) -> float:
        """Calculate cost for given consumption."""
        pass
    
    @abstractmethod
    def get_components(self) -> List[TariffComponent]:
        """Get all tariff components."""
        pass


@dataclass
class SwissTariff(Tariff):
    """Swiss electricity tariff configuration."""
    name: str = "Standard Swiss Tariff"
    year: int = 2024
    currency: str = "CHF"
    utility_company: Optional[str] = None
    components: List[TariffComponent] = field(default_factory=list)
    peak_hours: tuple[int, int] = (7, 20)
    off_peak_hours: tuple[int, int] = (20, 7)
    energy_price_peak: float = 0.25
    energy_price_off_peak: float = 0.18
    grid_fee: float = 0.08
    network_tariff: float = 0.05
    basic_fee_monthly: float = 15.0
    feed_in_remuneration: float = 0.10
    renewable_fee: float = 0.023
    vat_rate: float = 8.1
    
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
                        days=[0, 1, 2, 3, 4],
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
    
    def calculate_cost(self, consumption_kwh: float, **kwargs) -> float:
        """Calculate cost for given consumption."""
        total = 0.0
        for comp in self.components:
            hour = kwargs.get('hour')
            minute = kwargs.get('minute')
            weekday = kwargs.get('weekday')
            total += comp.calculate_cost(consumption_kwh, hour, minute, weekday)
        return total
    
    def get_components(self) -> List[TariffComponent]:
        """Get all tariff components."""
        return self.components
    
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


# ============================================================================
# PROPERTY AND METER MODELS
# ============================================================================

@dataclass
class Meter:
    """Represents an energy meter."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    meter_type: MeterType = MeterType.APARTMENT_CONSUMPTION
    location: str = ""
    serial_number: Optional[str] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'meter_type': self.meter_type.value,
            'location': self.location,
            'serial_number': self.serial_number,
            'is_active': self.is_active,
        }


@dataclass
class Apartment:
    """Represents an apartment/unit in a property."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    number: str = ""
    floor: int = 0
    area_sqm: float = 0.0
    occupants: int = 1
    meters: List[Meter] = field(default_factory=list)
    tenant_name: Optional[str] = None
    is_owner_occupied: bool = False
    
    def add_meter(self, meter: Meter) -> None:
        """Add a meter to this apartment."""
        self.meters.append(meter)
    
    def get_consumption_meter(self) -> Optional[Meter]:
        """Get the primary consumption meter."""
        for meter in self.meters:
            if meter.meter_type == MeterType.APARTMENT_CONSUMPTION:
                return meter
        return self.meters[0] if self.meters else None


@dataclass
class SolarSystem:
    """Represents a solar PV system."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Solar System"
    capacity_kwp: float = 0.0
    installation_date: Optional[date] = None
    inverter_efficiency: float = 0.96
    meter: Optional[Meter] = None


@dataclass
class Battery:
    """Represents a battery storage system."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Battery"
    capacity_kwh: float = 0.0
    max_charge_power_kw: float = 0.0
    max_discharge_power_kw: float = 0.0
    efficiency: float = 0.95
    charge_meter: Optional[Meter] = None
    discharge_meter: Optional[Meter] = None


# ============================================================================
# ENERGY FLOW MODELS
# ============================================================================

@dataclass
class EnergyFlow:
    """Represents energy flow data at a specific timestamp."""
    timestamp: datetime
    meter_id: str
    value_kwh: float
    interval_minutes: int = 15
    
    @property
    def power_kw(self) -> float:
        """Calculate average power in kW for this interval."""
        return self.value_kwh / (self.interval_minutes / 60.0)


@dataclass
class EnergyData:
    """Container for time-series energy data."""
    meter_id: str
    meter_name: str
    meter_type: MeterType
    data: List[EnergyFlow] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_flow(self, flow: EnergyFlow) -> None:
        """Add an energy flow record."""
        self.data.append(flow)
        if self.start_time is None or flow.timestamp < self.start_time:
            self.start_time = flow.timestamp
        if self.end_time is None or flow.timestamp > self.end_time:
            self.end_time = flow.timestamp
    
    def get_total_kwh(self) -> float:
        """Get total energy in kWh."""
        return sum(f.value_kwh for f in self.data)
    
    def get_data_for_period(self, start: datetime, end: datetime) -> List[EnergyFlow]:
        """Get data within a specific period."""
        return [f for f in self.data if start <= f.timestamp <= end]


# ============================================================================
# ALLOCATION MODEELS
# ============================================================================

@dataclass
class AllocationConfig:
    """Configuration for energy allocation."""
    strategy: AllocationStrategyType = AllocationStrategyType.PRIORITY
    owner_apartment_id: Optional[str] = None
    solar_discount: float = 0.02  # CHF discount for tenant solar energy
    battery_priority: str = "owner"  # "owner", "equal", "proportional"
    custom_percentages: Dict[str, float] = field(default_factory=dict)
    include_shared_consumption: bool = True
    shared_consumption_allocation: str = "proportional"  # "equal", "proportional", "fixed"
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.strategy == AllocationStrategyType.CUSTOM:
            total = sum(self.custom_percentages.values())
            return abs(total - 1.0) < 0.01
        return True


@dataclass
class AllocatedEnergy:
    """Result of energy allocation for one apartment."""
    apartment_id: str
    apartment_name: str
    total_consumption_kwh: float = 0.0
    grid_consumption_kwh: float = 0.0
    solar_consumption_kwh: float = 0.0
    battery_consumption_kwh: float = 0.0
    solar_discount_chf: float = 0.0
    grid_cost_chf: float = 0.0
    solar_cost_chf: float = 0.0
    battery_cost_chf: float = 0.0
    total_cost_chf: float = 0.0
    feed_in_kwh: float = 0.0
    feed_in_revenue_chf: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# BILLING MODELS
# ============================================================================

@dataclass
class BillingPeriod:
    """Defines a billing period."""
    start_date: date
    end_date: date
    months: int = 1
    
    @property
    def days(self) -> int:
        """Get number of days in period."""
        return (self.end_date - self.start_date).days + 1


@dataclass
class InvoiceItem:
    """A single item on an invoice."""
    description: str
    quantity: float
    unit: str
    unit_price: float
    total: float
    category: str = ""


@dataclass
class Invoice:
    """Represents an electricity bill/invoice."""
    id: str = field(default_factory=lambda: str(uuid4()))
    invoice_number: str = ""
    apartment_id: str = ""
    apartment_name: str = ""
    billing_period: Optional[BillingPeriod] = None
    issue_date: date = field(default_factory=date.today)
    due_date: Optional[date] = None
    items: List[InvoiceItem] = field(default_factory=list)
    subtotal: float = 0.0
    vat_rate: float = 8.1
    vat_amount: float = 0.0
    total: float = 0.0
    currency: str = "CHF"
    notes: str = ""
    
    def add_item(self, item: InvoiceItem) -> None:
        """Add an invoice item."""
        self.items.append(item)
        self.subtotal += item.total
    
    def calculate_totals(self) -> None:
        """Calculate VAT and total."""
        self.vat_amount = self.subtotal * (self.vat_rate / 100.0)
        self.total = self.subtotal + self.vat_amount


@dataclass
class BillingResult:
    """Complete billing result for a property."""
    billing_period: BillingPeriod
    property_id: str
    property_name: str
    invoices: List[Invoice] = field(default_factory=list)
    total_consumption_kwh: float = 0.0
    total_solar_kwh: float = 0.0
    total_grid_import_kwh: float = 0.0
    total_grid_export_kwh: float = 0.0
    total_battery_kwh: float = 0.0
    self_consumption_rate: float = 0.0
    total_revenue_chf: float = 0.0
    total_costs_chf: float = 0.0


# ============================================================================
# PROJECT MODELS
# ============================================================================

@dataclass
class Property:
    """Represents a multi-unit property."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    address: str = ""
    city: str = ""
    zip_code: str = ""
    country: str = "CH"
    apartments: List[Apartment] = field(default_factory=list)
    solar_system: Optional[SolarSystem] = None
    battery: Optional[Battery] = None
    grid_meter: Optional[Meter] = None
    shared_meters: List[Meter] = field(default_factory=list)
    
    def add_apartment(self, apartment: Apartment) -> None:
        """Add an apartment to the property."""
        self.apartments.append(apartment)
    
    def remove_apartment(self, apartment_id: str) -> bool:
        """Remove an apartment by ID."""
        for i, apt in enumerate(self.apartments):
            if apt.id == apartment_id:
                self.apartments.pop(i)
                return True
        return False
    
    def get_apartment(self, apartment_id: str) -> Optional[Apartment]:
        """Get an apartment by ID."""
        for apt in self.apartments:
            if apt.id == apartment_id:
                return apt
        return None
    
    def get_owner_apartment(self) -> Optional[Apartment]:
        """Get the owner-occupied apartment."""
        for apt in self.apartments:
            if apt.is_owner_occupied:
                return apt
        return None


@dataclass
class Project:
    """Main project container."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "New Project"
    description: str = ""
    created_date: date = field(default_factory=date.today)
    modified_date: date = field(default_factory=date.today)
    property_info: Optional[Property] = None
    tariff: Optional[Tariff] = None
    allocation_config: Optional[AllocationConfig] = None
    billing_periods: List[BillingPeriod] = field(default_factory=list)
    database_path: Optional[Path] = None
    
    def __post_init__(self) -> None:
        """Post-initialization setup."""
        if self.allocation_config is None:
            self.allocation_config = AllocationConfig()
        if self.tariff is None:
            self.tariff = SwissTariff()
            if isinstance(self.tariff, SwissTariff):
                self.tariff.create_default_components()
        if self.property_info is None:
            self.property_info = Property()
    
    def save_config(self, path: Path) -> None:
        """Save project configuration to JSON."""
        config = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_date': str(self.created_date),
            'modified_date': str(self.modified_date),
            'allocation_config': {
                'strategy': self.allocation_config.strategy.value if self.allocation_config else 'priority',
                'solar_discount': self.allocation_config.solar_discount if self.allocation_config else 0.02,
                'battery_priority': self.allocation_config.battery_priority if self.allocation_config else 'owner',
            } if self.allocation_config else {},
        }
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
    
    @classmethod
    def load_config(cls, path: Path) -> 'Project':
        """Load project configuration from JSON."""
        with open(path, 'r') as f:
            config = json.load(f)
        
        project = cls(
            id=config.get('id', str(uuid4())),
            name=config.get('name', 'Imported Project'),
            description=config.get('description', ''),
        )
        
        if 'allocation_config' in config:
            ac = config['allocation_config']
            project.allocation_config = AllocationConfig(
                strategy=AllocationStrategyType(ac.get('strategy', 'priority')),
                solar_discount=ac.get('solar_discount', 0.02),
                battery_priority=ac.get('battery_priority', 'owner'),
            )
        
        return project
    
    def set_owner_apartment(self, apartment_id: str) -> None:
        """Set which apartment is owner-occupied."""
        if self.property_info:
            for apt in self.property_info.apartments:
                apt.is_owner_occupied = (apt.id == apartment_id)
            if self.allocation_config:
                self.allocation_config.owner_apartment_id = apartment_id
    
    def get_owner_apartment_id(self) -> Optional[str]:
        """Get the ID of the owner-occupied apartment."""
        if not self.property_info:
            return None
        owner_apt = self.property_info.get_owner_apartment()
        return owner_apt.id if owner_apt else None


# ============================================================================
# DATABASE SCHEMA
# ============================================================================

DATABASE_SCHEMA = """
-- Electricity Billing System Database Schema

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_date DATE,
    modified_date DATE,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT,
    address TEXT,
    city TEXT,
    zip_code TEXT,
    country TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS apartments (
    id TEXT PRIMARY KEY,
    property_id TEXT,
    name TEXT,
    number TEXT,
    floor INTEGER,
    area_sqm REAL,
    occupants INTEGER,
    tenant_name TEXT,
    is_owner_occupied BOOLEAN,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS meters (
    id TEXT PRIMARY KEY,
    apartment_id TEXT,
    name TEXT,
    meter_type TEXT,
    location TEXT,
    serial_number TEXT,
    is_active BOOLEAN,
    FOREIGN KEY (apartment_id) REFERENCES apartments(id)
);

CREATE TABLE IF NOT EXISTS tariffs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT,
    year INTEGER,
    currency TEXT,
    config_json TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS energy_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id TEXT,
    timestamp DATETIME,
    value_kwh REAL,
    interval_minutes INTEGER,
    FOREIGN KEY (meter_id) REFERENCES meters(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    apartment_id TEXT,
    invoice_number TEXT,
    billing_period_start DATE,
    billing_period_end DATE,
    issue_date DATE,
    due_date DATE,
    subtotal REAL,
    vat_rate REAL,
    vat_amount REAL,
    total REAL,
    currency TEXT,
    pdf_path TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (apartment_id) REFERENCES apartments(id)
);

CREATE INDEX IF NOT EXISTS idx_energy_data_timestamp ON energy_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_energy_data_meter ON energy_data(meter_id);
CREATE INDEX IF NOT EXISTS idx_invoices_period ON invoices(billing_period_start, billing_period_end);
"""
