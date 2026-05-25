"""Priority-based allocation strategy - Owner first, then tenants."""

from __future__ import annotations
from typing import Optional

from .base import AllocationStrategyBase
from ..models.energy_flow import EnergyData, EnergyFlow
from ..models.property import Apartment


class PriorityAllocationStrategy(AllocationStrategyBase):
    """Priority-based energy allocation.
    
    This strategy implements the specific use case where:
    1. Owner (you) gets first priority for solar energy
    2. Surplus solar is sold to tenants at a discount
    3. If no surplus, tenants pay normal grid prices
    4. Battery follows similar priority rules
    
    This is ideal for building owners who live in one unit and rent others.
    """
    
    def allocate_solar(self, energy_data: EnergyData, 
                       consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate solar energy with owner priority.
        
        Solar allocation order:
        1. Owner's consumption
        2. Battery charging (if configured)
        3. Tenants by priority order
        4. Grid export (excess)
        """
        # Create fresh energy flow if not already created
        energy_flow = EnergyFlow(
            timestamp=energy_data.timestamp,
            interval=energy_data.interval,
            solar_available=energy_data.solar_production,
        )
        
        # Set consumptions
        owner_apt = self.property.get_owner_apartment()
        if owner_apt:
            energy_flow.owner_consumption = consumptions.get(owner_apt.id, 0.0)
        
        for apt_id, consumption in consumptions.items():
            apt = next((a for a in self.property.apartments if a.id == apt_id), None)
            if apt and not apt.is_owner_occupied:
                energy_flow.tenant_consumptions[apt_id] = consumption
        
        solar_available = energy_data.solar_production
        remaining_solar = solar_available
        
        # Step 1: Allocate to owner first
        if energy_flow.owner_consumption > 0 and remaining_solar > 0:
            solar_to_owner = min(remaining_solar, energy_flow.owner_consumption)
            energy_flow.solar_to_owner = solar_to_owner
            remaining_solar -= solar_to_owner
        
        # Step 2: Charge battery with excess (if battery exists and needs charging)
        if remaining_solar > 0 and self.battery is not None:
            battery_capacity = self.battery.available_charge_capacity()
            if battery_capacity > 0:
                solar_to_battery = min(remaining_solar, battery_capacity)
                energy_flow.solar_to_battery = solar_to_battery
                remaining_solar -= solar_to_battery
        
        # Step 3: Allocate remaining to tenants by priority
        if remaining_solar > 0:
            sorted_apartments = self._get_sorted_apartments_by_priority()
            
            for apt in sorted_apartments:
                if apt.is_owner_occupied:
                    continue  # Already handled
                
                tenant_consumption = energy_flow.tenant_consumptions.get(apt.id, 0.0)
                if tenant_consumption > 0 and remaining_solar > 0:
                    # Check if there's a max limit for tenants
                    max_tenant = self.config.max_solar_to_tenants
                    current_tenant_total = sum(energy_flow.solar_to_tenants.values())
                    
                    if max_tenant and current_tenant_total >= max_tenant:
                        break
                    
                    solar_to_tenant = min(remaining_solar, tenant_consumption)
                    
                    # Apply max limit if configured
                    if max_tenant:
                        remaining_allowance = max_tenant - current_tenant_total
                        solar_to_tenant = min(solar_to_tenant, remaining_allowance)
                    
                    energy_flow.solar_to_tenants[apt.id] = solar_to_tenant
                    remaining_solar -= solar_to_tenant
        
        # Step 4: Export remaining to grid
        if remaining_solar > 0:
            energy_flow.solar_to_grid = remaining_solar
        
        return energy_flow
    
    def allocate_battery(self, energy_flow: EnergyFlow,
                         consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate battery discharge with owner priority.
        
        Battery allocation order:
        1. Owner's remaining consumption (after solar)
        2. Tenants by priority order
        """
        if self.battery is None:
            return energy_flow
        
        battery_available = energy_data.battery_discharge = energy_flow.battery_discharge_available
        remaining_battery = battery_available
        
        # Calculate remaining consumption after solar
        owner_remaining = max(0, energy_flow.owner_consumption - energy_flow.solar_to_owner)
        tenant_remaining = {
            apt_id: max(0, consumption - energy_flow.solar_to_tenants.get(apt_id, 0))
            for apt_id, consumption in energy_flow.tenant_consumptions.items()
        }
        
        # Step 1: Allocate to owner first
        if owner_remaining > 0 and remaining_battery > 0:
            battery_to_owner = min(remaining_battery, owner_remaining)
            energy_flow.battery_to_owner = battery_to_owner
            remaining_battery -= battery_to_owner
        
        # Step 2: Allocate to tenants by priority
        if remaining_battery > 0:
            sorted_apartments = self._get_sorted_apartments_by_priority()
            
            for apt in sorted_apartments:
                if apt.is_owner_occupied:
                    continue
                
                remaining = tenant_remaining.get(apt.id, 0.0)
                if remaining > 0 and remaining_battery > 0:
                    battery_to_tenant = min(remaining_battery, remaining)
                    energy_flow.battery_to_tenants[apt.id] = battery_to_tenant
                    remaining_battery -= battery_to_tenant
        
        return energy_flow
    
    def allocate_grid(self, energy_flow: EnergyFlow) -> EnergyFlow:
        """Allocate grid import to cover remaining consumption.
        
        Grid covers all consumption not covered by solar or battery.
        """
        # Calculate remaining consumption for owner
        owner_covered = energy_flow.solar_to_owner + energy_flow.battery_to_owner
        owner_remaining = max(0, energy_flow.owner_consumption - owner_covered)
        energy_flow.grid_to_owner = owner_remaining
        
        # Calculate remaining consumption for each tenant
        for apt_id, consumption in energy_flow.tenant_consumptions.items():
            solar_covered = energy_flow.solar_to_tenants.get(apt_id, 0.0)
            battery_covered = energy_flow.battery_to_tenants.get(apt_id, 0.0)
            remaining = max(0, consumption - solar_covered - battery_covered)
            energy_flow.grid_to_tenants[apt_id] = remaining
        
        # Shared area consumption from grid
        energy_flow.grid_to_shared = energy_flow.shared_consumption
        
        return energy_flow
