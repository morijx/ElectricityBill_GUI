"""Billing and invoice models."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4


@dataclass
class BillingPeriod:
    """Represents a billing period."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    start_date: date = field(default_factory=lambda: date.today())
    end_date: date = field(default_factory=lambda: date.today())
    days_in_period: int = 0
    
    def __post_init__(self) -> None:
        if self.days_in_period == 0:
            delta = self.end_date - self.start_date
            self.days_in_period = delta.days + 1  # Include both start and end
    
    @property
    def months_in_period(self) -> float:
        """Approximate months in period."""
        return self.days_in_period / 30.44
    
    @classmethod
    def from_year_month(cls, year: int, month: int) -> "BillingPeriod":
        """Create billing period for a specific month."""
        if month == 12:
            end_date = date(year, 12, 31)
        else:
            from datetime import timedelta
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        start_date = date(year, month, 1)
        return cls(start_date=start_date, end_date=end_date)
    
    @classmethod
    def from_year(cls, year: int) -> "BillingPeriod":
        """Create billing period for a full year."""
        return cls(
            start_date=date(year, 1, 1),
            end_date=date(year, 12, 31),
        )


@dataclass
class InvoiceItem:
    """A single line item on an invoice."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    category: str = ""  # energy, grid, tax, etc.
    
    # Quantity and pricing
    quantity: float = 0.0
    unit: str = "kWh"
    unit_price: float = 0.0  # CHF per unit
    amount: float = 0.0  # Total amount (quantity * unit_price)
    
    # For percentage-based items
    is_percentage: bool = False
    percentage_base: float = 0.0  # Amount this percentage applies to
    
    # Time of use breakdown
    peak_quantity: float = 0.0
    off_peak_quantity: float = 0.0
    
    # Solar vs grid breakdown
    solar_quantity: float = 0.0
    grid_quantity: float = 0.0
    solar_discount: float = 0.0  # Discount applied to solar (CHF/kWh)
    
    def calculate_amount(self) -> float:
        """Calculate the total amount for this item."""
        if self.is_percentage:
            self.amount = self.percentage_base * (self.unit_price / 100.0)
        else:
            base_amount = self.quantity * self.unit_price
            # Apply solar discount if applicable
            if self.solar_quantity > 0 and self.solar_discount > 0:
                base_amount -= self.solar_quantity * self.solar_discount
            self.amount = base_amount
        return self.amount


@dataclass
class InvoiceSummary:
    """Summary totals for an invoice."""
    
    # Energy consumption
    total_consumption_kwh: float = 0.0
    solar_consumption_kwh: float = 0.0
    grid_consumption_kwh: float = 0.0
    battery_consumption_kwh: float = 0.0
    
    # Costs before VAT
    energy_cost: float = 0.0
    grid_cost: float = 0.0
    network_cost: float = 0.0
    basic_fee: float = 0.0
    renewable_fee: float = 0.0
    other_fees: float = 0.0
    
    # Feed-in
    feed_in_kwh: float = 0.0
    feed_in_revenue: float = 0.0
    
    # Totals
    subtotal: float = 0.0
    vat_amount: float = 0.0
    vat_rate: float = 8.1  # Swiss standard rate
    total_due: float = 0.0
    
    # Savings
    solar_savings: float = 0.0  # Savings compared to grid-only
    
    def calculate_totals(self) -> None:
        """Calculate all totals."""
        self.subtotal = (
            self.energy_cost + self.grid_cost + self.network_cost +
            self.basic_fee + self.renewable_fee + self.other_fees -
            self.feed_in_revenue
        )
        self.vat_amount = self.subtotal * (self.vat_rate / 100.0)
        self.total_due = self.subtotal + self.vat_amount


@dataclass
class Invoice:
    """Complete electricity invoice."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    invoice_number: str = ""
    
    # References
    property_id: str = ""
    apartment_id: str = ""
    billing_period_id: str = ""
    
    # Dates
    issue_date: date = field(default_factory=lambda: date.today())
    due_date: Optional[date] = None
    period_start: date = field(default_factory=lambda: date.today())
    period_end: date = field(default_factory=lambda: date.today())
    
    # Tenant/recipient info
    recipient_name: Optional[str] = None
    recipient_address: Optional[str] = None
    recipient_email: Optional[str] = None
    
    # Line items
    items: list[InvoiceItem] = field(default_factory=list)
    
    # Summary
    summary: InvoiceSummary = field(default_factory=InvoiceSummary)
    
    # Status
    is_paid: bool = False
    paid_date: Optional[date] = None
    
    # Notes
    notes: Optional[str] = None
    
    def __post_init__(self) -> None:
        if not self.invoice_number:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            self.invoice_number = f"INV-{timestamp}"
        if self.due_date is None:
            from datetime import timedelta
            self.due_date = self.issue_date + timedelta(days=30)
    
    def add_item(self, item: InvoiceItem) -> None:
        """Add a line item to the invoice."""
        item.calculate_amount()
        self.items.append(item)
    
    def calculate_summary(self) -> InvoiceSummary:
        """Calculate invoice summary from items."""
        summary = InvoiceSummary()
        
        for item in self.items:
            if item.category == "energy":
                summary.energy_cost += item.amount
                summary.total_consumption_kwh += item.quantity
                summary.solar_consumption_kwh += item.solar_quantity
                summary.grid_consumption_kwh += item.grid_quantity
            elif item.category == "grid":
                summary.grid_cost += item.amount
            elif item.category == "network":
                summary.network_cost += item.amount
            elif item.category == "basic":
                summary.basic_fee += item.amount
            elif item.category == "renewable":
                summary.renewable_fee += item.amount
            elif item.category == "feed_in":
                summary.feed_in_kwh += item.quantity
                summary.feed_in_revenue += item.amount
            elif item.category == "other":
                summary.other_fees += item.amount
        
        summary.calculate_totals()
        self.summary = summary
        return summary
    
    @property
    def total_consumption(self) -> float:
        """Get total consumption from summary."""
        return self.summary.total_consumption_kwh
    
    @property
    def total_amount(self) -> float:
        """Get total amount due."""
        return self.summary.total_due
