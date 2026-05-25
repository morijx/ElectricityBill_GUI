"""Equal allocation strategy."""

from __future__ import annotations

from .base import AllocationStrategyBase
from ..models.energy_flow import EnergyData, EnergyFlow


class EqualAllocationStrategy(AllocationStrategyBase):
    """Equal energy allocation among all apartments.
    
    This strategy divides solar and battery energy equally among
    all apartments, regardless of their individual consumption.
    
    Useful for community energy sharing models where fairness
    is prioritized over consumption-based allocation.
    """
    
    def allocate_solar(self, energy_data: EnergyData, 
                       consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate solar energy equally among consumers."""
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
        
        # Count active consumers (those with consumption > 0)
        active_consumers = []
        if energy_flow.owner_consumption > 0:
            active_consumers.append(('owner', energy_flow.owner_consumption))
        
        for apt_id, consumption in energy_flow.tenant_consumptions.items():
            if consumption > 0:
                active_consumers.append((apt_id, consumption))
        
        num_consumers = len(active_consumers)
        
        if num_consumers == 0 or solar_available <= 0:
            energy_flow.solar_to_grid = solar_available
            return energy_flow
        
        # Equal share per consumer
        equal_share = solar_available / num_consumers
        
        # Allocate to owner
        if energy_flow.owner_consumption > 0:
            energy_flow.solar_to_owner = min(equal_share, energy_flow.owner_consumption)
        
        # Allocate to tenants
        remaining_solar = solar_available - energy_flow.solar_to_owner
        for apt_id, consumption in energy_flow.tenant_consumptions.items():
            if consumption > 0 and remaining_solar > 0:
                allocation = min(equal_share, consumption, remaining_solar)
                energy_flow.solar_to_tenants[apt_id] = allocation
                remaining_solar -= allocation
        
        # Export remaining
        if remaining_solar > 0:
            energy_flow.solar_to_grid = remaining_solar
        
        return energy_flow
    
    def allocate_battery(self, energy_flow: EnergyFlow,
                         consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate battery discharge equally."""
        if self.battery is None:
            return energy_flow
        
        battery_available = energy_flow.battery_discharge_available
        if battery_available <= 0:
            return energy_flow
        
        # Calculate remaining consumption after solar
        owner_remaining = max(0, energy_flow.owner_consumption - energy_flow.solar_to_owner)
        tenant_remaining = {
            apt_id: max(0, consumption - energy_flow.solar_to_tenants.get(apt_id, 0))
            for apt_id, consumption in energy_flow.tenant_consumptions.items()
        }
        
        # Count active consumers
        active_consumers = []
        if owner_remaining > 0:
            active_consumers.append('owner')
        
        for apt_id, remaining in tenant_remaining.items():
            if remaining > 0:
                active_consumers.append(apt_id)
        
        num_consumers = len(active_consumers)
        
        if num_consumers == 0:
            return energy_flow
        
        # Equal share
        equal_share = battery_available / num_consumers
        
        # Allocate to owner
        if owner_remaining > 0:
            energy_flow.battery_to_owner = min(equal_share, owner_remaining)
        
        remaining_battery = battery_available - energy_flow.battery_to_owner
        
        # Allocate to tenants
        for apt_id, remaining in tenant_remaining.items():
            if remaining > 0 and remaining_battery > 0:
                allocation = min(equal_share, remaining, remaining_battery)
                energy_flow.battery_to_tenants[apt_id] = allocation
                remaining_battery -= allocation
        
        return energy_flow
    
    def allocate_grid(self, energy_flow: EnergyFlow) -> EnergyFlow:
        """Allocate grid import to cover remaining consumption."""
        owner_covered = energy_flow.solar_to_owner + energy_flow.battery_to_owner
        energy_flow.grid_to_owner = max(0, energy_flow.owner_consumption - owner_covered)
        
        for apt_id, consumption in energy_flow.tenant_consumptions.items():
            solar_covered = energy_flow.solar_to_tenants.get(apt_id, 0.0)
            battery_covered = energy_flow.battery_to_tenants.get(apt_id, 0.0)
            energy_flow.grid_to_tenants[apt_id] = max(
                0, consumption - solar_covered - battery_covered
            )
        
        energy_flow.grid_to_shared = energy_flow.shared_consumption
        
        return energy_flow
