"""Base allocation strategy interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from ..models.energy_flow import EnergyData, EnergyFlow
from ..models.property import Property, Apartment
from ..models.project import AllocationConfig
from ..models.system import Battery


class AllocationStrategyBase(ABC):
    """Abstract base class for energy allocation strategies.
    
    This class defines the interface that all allocation strategies must implement.
    Strategies determine how solar energy, battery energy, and grid energy are
    distributed among apartments/tenants.
    """
    
    def __init__(self, config: AllocationConfig, property_data: Property,
                 battery: Optional[Battery] = None) -> None:
        """Initialize the allocation strategy.
        
        Args:
            config: Allocation configuration settings
            property_data: Property information with apartments
            battery: Optional battery system
        """
        self.config = config
        self.property = property_data
        self.battery = battery
    
    @abstractmethod
    def allocate_solar(self, energy_data: EnergyData, 
                       consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate solar energy to consumers.
        
        Args:
            energy_data: Raw energy data for the interval
            consumptions: Dictionary mapping apartment IDs to consumption (kWh)
            
        Returns:
            EnergyFlow with solar allocations populated
        """
        pass
    
    @abstractmethod
    def allocate_battery(self, energy_flow: EnergyFlow,
                         consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate battery discharge energy to consumers.
        
        Args:
            energy_flow: Energy flow with existing allocations
            consumptions: Dictionary mapping apartment IDs to consumption (kWh)
            
        Returns:
            EnergyFlow with battery allocations populated
        """
        pass
    
    @abstractmethod
    def allocate_grid(self, energy_flow: EnergyFlow) -> EnergyFlow:
        """Allocate grid import to cover remaining consumption.
        
        Args:
            energy_flow: Energy flow with solar/battery allocations
            
        Returns:
            EnergyFlow with grid allocations populated
        """
        pass
    
    def process_interval(self, energy_data: EnergyData,
                        consumptions: dict[str, float],
                        shared_consumption: float = 0.0) -> EnergyFlow:
        """Process a single time interval through all allocation steps.
        
        This is the main entry point for the allocation strategy. It performs
        allocation in the following order:
        1. Solar energy allocation
        2. Battery energy allocation
        3. Grid import allocation
        
        Args:
            energy_data: Raw energy data for the interval
            consumptions: Dictionary mapping apartment IDs to consumption (kWh)
            shared_consumption: Shared/common area consumption (kWh)
            
        Returns:
            Complete EnergyFlow with all allocations
        """
        # Initialize energy flow
        energy_flow = EnergyFlow(
            timestamp=energy_data.timestamp,
            interval=energy_data.interval,
            solar_available=energy_data.solar_production,
            grid_import_available=energy_data.grid_import,
            battery_discharge_available=energy_data.battery_discharge,
            shared_consumption=shared_consumption,
        )
        
        # Set consumptions
        owner_apt = self.property.get_owner_apartment()
        if owner_apt:
            energy_flow.owner_consumption = consumptions.get(owner_apt.id, 0.0)
        
        for apt_id, consumption in consumptions.items():
            apt = next((a for a in self.property.apartments if a.id == apt_id), None)
            if apt and not apt.is_owner_occupied:
                energy_flow.tenant_consumptions[apt_id] = consumption
        
        # Step 1: Allocate solar
        energy_flow = self.allocate_solar(energy_data, consumptions)
        
        # Step 2: Allocate battery
        energy_flow = self.allocate_battery(energy_flow, consumptions)
        
        # Step 3: Allocate grid
        energy_flow = self.allocate_grid(energy_flow)
        
        return energy_flow
    
    def get_owner_priority(self) -> bool:
        """Check if owner has priority in allocation."""
        return self.config.owner_solar_priority
    
    def get_tenant_discount(self) -> float:
        """Get the solar discount rate for tenants."""
        return self.config.tenant_solar_discount
    
    def _get_sorted_apartments_by_priority(self) -> list[Apartment]:
        """Get apartments sorted by priority."""
        apartments = self.property.apartments.copy()
        
        # Sort by priority from config
        apartments.sort(key=lambda apt: self.config.get_apartment_priority(apt.id))
        
        return apartments
