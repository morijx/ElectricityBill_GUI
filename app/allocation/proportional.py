"""Proportional allocation strategy."""

from __future__ import annotations

from .base import AllocationStrategyBase
from ..models.energy_flow import EnergyData, EnergyFlow


class ProportionalAllocationStrategy(AllocationStrategyBase):
    """Proportional energy allocation based on consumption.
    
    This strategy allocates solar and battery energy proportionally
    based on each apartment's share of total consumption.
    
    Formula: allocation = (apartment_consumption / total_consumption) * available_energy
    """
    
    def allocate_solar(self, energy_data: EnergyData, 
                       consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate solar energy proportionally to consumption."""
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
        total_consumption = energy_flow.total_consumption()
        
        if total_consumption <= 0 or solar_available <= 0:
            # No consumption or no solar - export all
            energy_flow.solar_to_grid = solar_available
            return energy_flow
        
        # Calculate proportional allocations
        if energy_flow.owner_consumption > 0:
            owner_share = energy_flow.owner_consumption / total_consumption
            energy_flow.solar_to_owner = min(
                solar_available * owner_share,
                energy_flow.owner_consumption
            )
        
        remaining_solar = solar_available - energy_flow.solar_to_owner
        
        for apt_id, consumption in energy_flow.tenant_consumptions.items():
            if consumption > 0 and remaining_solar > 0:
                tenant_share = consumption / total_consumption
                allocation = min(
                    remaining_solar * tenant_share,
                    consumption
                )
                energy_flow.solar_to_tenants[apt_id] = allocation
                remaining_solar -= allocation
        
        # Export remaining
        if remaining_solar > 0:
            energy_flow.solar_to_grid = remaining_solar
        
        return energy_flow
    
    def allocate_battery(self, energy_flow: EnergyFlow,
                         consumptions: dict[str, float]) -> EnergyFlow:
        """Allocate battery discharge proportionally."""
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
        
        total_remaining = owner_remaining + sum(tenant_remaining.values())
        
        if total_remaining <= 0:
            return energy_flow
        
        # Allocate proportionally
        if owner_remaining > 0:
            owner_share = owner_remaining / total_remaining
            energy_flow.battery_to_owner = min(
                battery_available * owner_share,
                owner_remaining
            )
        
        remaining_battery = battery_available - energy_flow.battery_to_owner
        
        for apt_id, remaining in tenant_remaining.items():
            if remaining > 0 and remaining_battery > 0:
                tenant_share = remaining / total_remaining
                allocation = min(
                    remaining_battery * tenant_share,
                    remaining
                )
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
