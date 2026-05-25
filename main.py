#!/usr/bin/env python3
"""
Electricity Billing System - Main Entry Point (Consolidated Version)

A streamlined Python desktop application for generating electricity bills
for multi-unit properties with solar energy systems, batteries, and
flexible energy-sharing logic.

This version uses consolidated modules for simpler structure:
- app/models_consolidated.py: All data models
- app/services_consolidated.py: All services (import, allocation, billing, PDF, DB)
- app/gui_consolidated.py: Complete GUI application
"""

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('electricity_billing.log'),
    ]
)
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    missing = []
    
    try:
        import PySide6
    except ImportError:
        missing.append('PySide6')
    
    try:
        import pandas
    except ImportError:
        missing.append('pandas')
    
    try:
        import reportlab
    except ImportError:
        missing.append('reportlab')
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.error("Please install them using: pip install -r requirements.txt")
        return False
    
    return True


def run_gui():
    """Run the GUI application."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from app.gui_consolidated import run_gui as consolidated_run_gui
    
    return consolidated_run_gui()


def run_cli_demo():
    """Run a CLI demonstration of the core functionality."""
    from datetime import date, timedelta
    from app.models_consolidated import (
        Property, Apartment, SwissTariff, Project, 
        AllocationConfig, AllocationStrategyType, BillingPeriod
    )
    from app.services_consolidated import AllocationEngine, BillingEngine
    
    print("=" * 60)
    print("Electricity Billing System - Demo")
    print("=" * 60)
    
    # Create a sample property
    property_data = Property(name="Sample Building", address="Musterstrasse 1", city="Zurich")
    
    # Add owner apartment
    owner_apt = Apartment(
        name="Owner Apartment",
        number="1",
        is_owner_occupied=True,
        priority=1,
    )
    property_data.add_apartment(owner_apt)
    
    # Add tenant apartment
    tenant_apt = Apartment(
        name="Tenant Apartment",
        number="2",
        tenant_name="Max Muster",
        is_owner_occupied=False,
        priority=2,
        discount_rate=0.02,
    )
    property_data.add_apartment(tenant_apt)
    
    print(f"\nProperty: {property_data.name}")
    print(f"Apartments: {property_data.apartment_count}")
    print(f"  - Owner: {owner_apt.name}")
    print(f"  - Tenant: {tenant_apt.name} ({tenant_apt.tenant_name})")
    
    # Create project
    project = Project(
        name="Demo Project",
        property=property_data,
        tariff=SwissTariff(),
    )
    project.tariff.create_default_components()
    
    # Configure allocation (owner first, then tenant gets surplus at discount)
    project.allocation_config = AllocationConfig(
        strategy=AllocationStrategy.PRIORITY,
        owner_solar_priority=True,
        tenant_solar_discount=0.02,  # 2 Rappen discount per kWh
        priority_order=[owner_apt.id, tenant_apt.id],
    )
    
    print(f"\nAllocation Strategy: {project.allocation_config.strategy.value}")
    print(f"Owner Solar Priority: {project.allocation_config.owner_solar_priority}")
    print(f"Tenant Solar Discount: CHF {project.allocation_config.tenant_solar_discount}/kWh")
    
    # Create sample energy flows (simulating one day with 15-min intervals)
    energy_flows = []
    base_time = project.created_date
    
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            timestamp = base_time + timedelta(hours=hour, minutes=minute)
            interval = TimeInterval.from_timestamp(timestamp)
            
            flow = EnergyFlow(
                timestamp=timestamp,
                interval=interval,
                solar_available=0.5 if 8 <= hour <= 18 else 0.0,  # Solar during day
                grid_import_available=1.0,
                owner_consumption=0.3,  # Owner uses 0.3 kWh per 15 min
                tenant_consumptions={tenant_apt.id: 0.2},  # Tenant uses 0.2 kWh
            )
            
            # Simple allocation simulation
            solar = flow.solar_available
            if flow.owner_consumption > 0 and solar > 0:
                flow.solar_to_owner = min(solar, flow.owner_consumption)
                solar -= flow.solar_to_owner
            
            if tenant_apt.id in flow.tenant_consumptions and solar > 0:
                flow.solar_to_tenants[tenant_apt.id] = min(solar, flow.tenant_consumptions[tenant_apt.id])
                solar -= flow.solar_to_tenants[tenant_apt.id]
            
            flow.solar_to_grid = solar
            
            # Grid covers remainder
            flow.grid_to_owner = max(0, flow.owner_consumption - flow.solar_to_owner)
            flow.grid_to_tenants[tenant_apt.id] = max(
                0, 
                flow.tenant_consumptions[tenant_apt.id] - flow.solar_to_tenants.get(tenant_apt.id, 0)
            )
            
            energy_flows.append(flow)
    
    print(f"\nSimulated {len(energy_flows)} time intervals (1 day)")
    
    # Calculate bills
    billing_engine = BillingEngine(project)
    period = BillingPeriod.from_year_month(2024, 1)
    
    results = billing_engine.calculate_all_bills(energy_flows, period)
    
    print("\n" + "=" * 60)
    print("Billing Results")
    print("=" * 60)
    
    for apt_id, result in results.items():
        apt = next(a for a in property_data.apartments if a.id == apt_id)
        print(f"\n{apt.name}:")
        print(f"  Total Consumption: {result.total_consumption_kwh:.2f} kWh")
        print(f"  Solar Consumption: {result.solar_consumption_kwh:.2f} kWh")
        print(f"  Grid Consumption:  {result.grid_consumption_kwh:.2f} kWh")
        print(f"  Energy Cost:       CHF {result.energy_cost:.2f}")
        print(f"  Grid Fee:          CHF {result.grid_cost:.2f}")
        print(f"  Basic Fee:         CHF {result.basic_fee:.2f}")
        print(f"  Subtotal:          CHF {result.subtotal:.2f}")
        print(f"  VAT (8.1%):        CHF {result.vat_amount:.2f}")
        print(f"  TOTAL DUE:         CHF {result.total_due:.2f}")
        
        if result.export_to_grid_kwh > 0:
            print(f"  Feed-in Revenue:   CHF {result.feed_in_revenue:.2f} ({result.export_to_grid_kwh:.2f} kWh)")
        
        if result.solar_savings > 0:
            print(f"  Solar Savings:     CHF {result.solar_savings:.2f}")
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)
    
    return True


def main():
    """Main entry point."""
    logger.info("Starting Electricity Billing System")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--demo':
            run_cli_demo()
            return 0
        elif sys.argv[1] == '--help':
            print("Electricity Billing System")
            print("\nUsage:")
            print("  python main.py          Run GUI application")
            print("  python main.py --demo   Run CLI demonstration")
            print("  python main.py --help   Show this help")
            return 0
    
    # Default: run GUI
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
