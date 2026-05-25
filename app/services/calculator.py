"""Calculation service for energy and cost calculations."""

from __future__ import annotations
from typing import Optional

import pandas as pd

from ..models.project import Project
from ..models.energy_flow import EnergyFlow, EnergyData
from ..models.billing import BillingPeriod
from ..allocation.base import AllocationStrategyBase
from ..allocation.priority import PriorityAllocationStrategy
from ..billing.engine import BillingEngine, BillingResult


class CalculationService:
    """Service for performing energy and billing calculations.
    
    Orchestrates the complete calculation workflow:
    1. Import/prepare energy data
    2. Run allocation strategy
    3. Calculate bills per apartment
    4. Generate results
    """
    
    def __init__(self, project: Project) -> None:
        """Initialize calculation service with project."""
        self.project = project
        self.allocation_strategy: Optional[AllocationStrategyBase] = None
        self.billing_engine = BillingEngine(project)
        
        # Results storage
        self.energy_flows: list[EnergyFlow] = []
        self.billing_results: dict[str, BillingResult] = {}
    
    def setup_allocation_strategy(self) -> None:
        """Set up the allocation strategy based on project config."""
        from ..models.project import AllocationStrategy
        
        strategy_type = self.project.allocation_config.strategy
        
        if strategy_type == AllocationStrategy.PRIORITY:
            self.allocation_strategy = PriorityAllocationStrategy(
                config=self.project.allocation_config,
                property_data=self.project.property,
                battery=self.project.battery,
            )
        elif strategy_type == AllocationStrategy.PROPORTIONAL:
            from ..allocation.proportional import ProportionalAllocationStrategy
            self.allocation_strategy = ProportionalAllocationStrategy(
                config=self.project.allocation_config,
                property_data=self.project.property,
                battery=self.project.battery,
            )
        elif strategy_type == AllocationStrategy.EQUAL:
            from ..allocation.equal import EqualAllocationStrategy
            self.allocation_strategy = EqualAllocationStrategy(
                config=self.project.allocation_config,
                property_data=self.project.property,
                battery=self.project.battery,
            )
    
    def process_energy_data(self, df: pd.DataFrame,
                           apartment_meter_map: dict[str, str]) -> list[EnergyFlow]:
        """Process raw energy data into allocated energy flows.
        
        Args:
            df: DataFrame with imported energy data
            apartment_meter_map: Mapping of apartment IDs to meter column names
            
        Returns:
            List of EnergyFlow objects with allocations
        """
        if self.allocation_strategy is None:
            self.setup_allocation_strategy()
        
        energy_flows = []
        
        for idx, row in df.iterrows():
            # Create EnergyData from row
            energy_data = EnergyData(
                timestamp=pd.to_datetime(row.get('timestamp', idx)),
                grid_import=row.get('grid_import', 0.0),
                grid_export=row.get('grid_export', 0.0),
                solar_production=row.get('solar_production', 0.0),
                battery_charge=row.get('battery_charge', 0.0),
                battery_discharge=row.get('battery_discharge', 0.0),
            )
            
            # Extract apartment consumptions
            consumptions = {}
            for apt_id, col_name in apartment_meter_map.items():
                if col_name in row:
                    consumptions[apt_id] = float(row[col_name])
            
            # Get shared consumption if available
            shared_consumption = float(row.get('shared_consumption', 0.0))
            
            # Process through allocation strategy
            energy_flow = self.allocation_strategy.process_interval(
                energy_data=energy_data,
                consumptions=consumptions,
                shared_consumption=shared_consumption,
            )
            
            energy_flows.append(energy_flow)
        
        self.energy_flows = energy_flows
        return energy_flows
    
    def calculate_bills(self, period: BillingPeriod) -> dict[str, BillingResult]:
        """Calculate bills for all apartments.
        
        Args:
            period: Billing period for calculations
            
        Returns:
            Dictionary mapping apartment IDs to BillingResults
        """
        if not self.energy_flows:
            raise ValueError("No energy flows to process. Run process_energy_data first.")
        
        self.billing_results = self.billing_engine.calculate_all_bills(
            energy_flows=self.energy_flows,
            period=period,
        )
        
        return self.billing_results
    
    def get_summary(self) -> dict:
        """Get calculation summary statistics."""
        if not self.energy_flows:
            return {}
        
        total_solar = sum(f.solar_available for f in self.energy_flows)
        total_solar_allocated = sum(f.total_solar_allocated() for f in self.energy_flows)
        total_grid_import = sum(f.grid_import_available for f in self.energy_flows)
        total_consumption = sum(f.total_consumption() for f in self.energy_flows)
        
        return {
            "total_solar_production_kwh": total_solar,
            "total_solar_allocated_kwh": total_solar_allocated,
            "total_grid_import_kwh": total_grid_import,
            "total_consumption_kwh": total_consumption,
            "self_consumption_rate": total_solar_allocated / total_solar if total_solar > 0 else 0,
            "number_of_intervals": len(self.energy_flows),
        }
