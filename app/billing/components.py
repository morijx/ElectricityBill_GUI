"""Bill component definitions."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BillComponent:
    """A single component of an electricity bill.
    
    Represents one line item such as energy cost, grid fees, etc.
    """
    
    name: str
    description: str
    category: str  # energy, grid, network, basic, tax, feed_in, etc.
    
    quantity: float = 0.0
    unit: str = "kWh"
    unit_price: float = 0.0  # CHF per unit
    amount: float = 0.0  # Total amount in CHF
    
    # For percentage-based components (like VAT)
    is_percentage: bool = False
    percentage_rate: float = 0.0
    base_amount: float = 0.0
    
    # Solar/grid breakdown
    solar_quantity: float = 0.0
    grid_quantity: float = 0.0
    solar_discount_per_kwh: float = 0.0
    
    # Time of use breakdown
    peak_quantity: float = 0.0
    off_peak_quantity: float = 0.0
    peak_price: float = 0.0
    off_peak_price: float = 0.0
    
    def calculate(self) -> float:
        """Calculate the total amount for this component."""
        if self.is_percentage:
            self.amount = self.base_amount * (self.percentage_rate / 100.0)
        elif self.peak_quantity > 0 or self.off_peak_quantity > 0:
            # Time of use pricing
            self.amount = (
                self.peak_quantity * self.peak_price +
                self.off_peak_quantity * self.off_peak_price
            )
            # Apply solar discount
            if self.solar_quantity > 0 and self.solar_discount_per_kwh > 0:
                self.amount -= self.solar_quantity * self.solar_discount_per_kwh
        else:
            # Simple linear pricing
            self.amount = self.quantity * self.unit_price
            # Apply solar discount
            if self.solar_quantity > 0 and self.solar_discount_per_kwh > 0:
                self.amount -= self.solar_quantity * self.solar_discount_per_kwh
        
        return self.amount
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "amount": self.amount,
            "is_percentage": self.is_percentage,
            "percentage_rate": self.percentage_rate if self.is_percentage else None,
        }


@dataclass
class BillComponents:
    """Collection of all bill components for an invoice."""
    
    # Energy costs
    energy: BillComponent = field(default_factory=lambda: BillComponent(
        name="Energy",
        description="Electricity consumption",
        category="energy",
    ))
    
    # Grid/network costs
    grid_usage: BillComponent = field(default_factory=lambda: BillComponent(
        name="Grid Usage",
        description="Distribution grid usage fee",
        category="grid",
    ))
    
    network_tariff: BillComponent = field(default_factory=lambda: BillComponent(
        name="Network Tariff",
        description="Network infrastructure fee",
        category="network",
    ))
    
    # Fixed fees
    basic_fee: BillComponent = field(default_factory=lambda: BillComponent(
        name="Basic Fee",
        description="Monthly basic fee",
        category="basic",
        unit="month",
    ))
    
    metering_fee: BillComponent = field(default_factory=lambda: BillComponent(
        name="Metering Fee",
        description="Meter operation and reading",
        category="basic",
        unit="month",
    ))
    
    # Renewable energy fees
    renewable_fee: BillComponent = field(default_factory=lambda: BillComponent(
        name="Renewable Energy Fee",
        description="KEV/PR feed-in promotion",
        category="renewable",
    ))
    
    concession_fee: BillComponent = field(default_factory=lambda: BillComponent(
        name="Concession Fee",
        description="Municipal concession",
        category="concession",
    ))
    
    # Feed-in revenue
    feed_in: BillComponent = field(default_factory=lambda: BillComponent(
        name="Feed-in Remuneration",
        description="Solar export to grid",
        category="feed_in",
    ))
    
    # Taxes
    vat: BillComponent = field(default_factory=lambda: BillComponent(
        name="VAT",
        description="Value added tax",
        category="tax",
        is_percentage=True,
        percentage_rate=8.1,  # Swiss standard rate
    ))
    
    # All components list
    all_components: list[BillComponent] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Initialize the components list."""
        self.all_components = [
            self.energy,
            self.grid_usage,
            self.network_tariff,
            self.basic_fee,
            self.metering_fee,
            self.renewable_fee,
            self.concession_fee,
            self.feed_in,
            self.vat,
        ]
    
    def add_component(self, component: BillComponent) -> None:
        """Add a custom component."""
        self.all_components.append(component)
    
    def calculate_all(self) -> dict[str, float]:
        """Calculate all components and return amounts by category."""
        results = {}
        for comp in self.all_components:
            comp.calculate()
            if comp.category not in results:
                results[comp.category] = 0.0
            # Feed-in is revenue (negative cost)
            if comp.category == "feed_in":
                results[comp.category] -= comp.amount
            else:
                results[comp.category] += comp.amount
        return results
    
    def get_subtotal(self) -> float:
        """Get subtotal before VAT."""
        total = 0.0
        for comp in self.all_components:
            if comp.category != "tax":
                comp.calculate()
                if comp.category == "feed_in":
                    total -= comp.amount
                else:
                    total += comp.amount
        return total
    
    def get_vat_amount(self) -> float:
        """Calculate VAT amount."""
        subtotal = self.get_subtotal()
        self.vat.base_amount = subtotal
        return self.vat.calculate()
    
    def get_total(self) -> float:
        """Get total including VAT."""
        return self.get_subtotal() + self.get_vat_amount()
    
    def get_itemized_list(self) -> list[BillComponent]:
        """Get list of all components with calculated amounts."""
        for comp in self.all_components:
            comp.calculate()
        return self.all_components
