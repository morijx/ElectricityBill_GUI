"""PDF invoice generator using reportlab."""

from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from ..models.billing import Invoice, BillingPeriod
from ..models.property import Apartment


class PDFGenerator:
    """Generate professional PDF invoices.
    
    Creates Swiss-style utility bill PDFs with:
    - Header with property info
    - Recipient details
    - Consumption summary
    - Itemized cost breakdown
    - Charts (if available)
    - Payment information
    """
    
    def __init__(self, output_dir: str | Path = ".") -> None:
        """Initialize PDF generator.
        
        Args:
            output_dir: Directory for generated PDFs
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Styles
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self) -> None:
        """Set up custom paragraph styles."""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=20,
        )
        
        # Heading style
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#0078d4'),
            spaceBefore=15,
            spaceAfter=10,
        )
        
        # Normal style
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
        )
        
        # Right-aligned for amounts
        self.right_style = ParagraphStyle(
            'RightAlign',
            parent=self.normal_style,
            alignment=TA_RIGHT,
        )
        
        # Center style
        self.center_style = ParagraphStyle(
            'CenterAlign',
            parent=self.normal_style,
            alignment=TA_CENTER,
        )
    
    def generate_invoice(self, invoice: Invoice, 
                        property_name: str = "",
                        property_address: str = "") -> Path:
        """Generate a PDF invoice.
        
        Args:
            invoice: Invoice object to render
            property_name: Name of the property
            property_address: Address of the property
            
        Returns:
            Path to generated PDF file
        """
        filename = f"invoice_{invoice.invoice_number}.pdf"
        filepath = self.output_dir / filename
        
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Header
        elements.extend(self._create_header(property_name, property_address))
        
        # Invoice info
        elements.extend(self._create_invoice_info(invoice))
        
        # Recipient
        if invoice.recipient_name:
            elements.extend(self._create_recipient(invoice))
        
        # Consumption summary
        elements.extend(self._create_consumption_summary(invoice))
        
        # Cost breakdown
        elements.extend(self._create_cost_breakdown(invoice))
        
        # Total
        elements.extend(self._create_total(invoice))
        
        # Payment info
        elements.extend(self._create_payment_info(invoice))
        
        # Build PDF
        doc.build(elements)
        
        return filepath
    
    def _create_header(self, property_name: str, 
                       property_address: str) -> list:
        """Create document header."""
        elements = []
        
        # Property name as title
        title = Paragraph(property_name or "Electricity Bill", self.title_style)
        elements.append(title)
        
        if property_address:
            address = Paragraph(property_address, self.normal_style)
            elements.append(address)
        
        elements.append(Spacer(1, 1*cm))
        
        return elements
    
    def _create_invoice_info(self, invoice: Invoice) -> list:
        """Create invoice information table."""
        elements = []
        
        data = [
            ["Invoice Number:", invoice.invoice_number],
            ["Issue Date:", invoice.issue_date.strftime("%d.%m.%Y")],
            ["Due Date:", invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else ""],
            ["Billing Period:", f"{invoice.period_start.strftime('%m/%Y')} - {invoice.period_end.strftime('%m/%Y')}"],
        ]
        
        table = Table(data, colWidths=[4*cm, 6*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a1a1a')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_recipient(self, invoice: Invoice) -> list:
        """Create recipient address block."""
        elements = []
        
        elements.append(Paragraph("Bill To:", self.heading_style))
        
        recipient_text = f"<b>{invoice.recipient_name}</b><br/>"
        if invoice.recipient_address:
            recipient_text += f"{invoice.recipient_address}<br/>"
        
        recipient = Paragraph(recipient_text, self.normal_style)
        elements.append(recipient)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_consumption_summary(self, invoice: Invoice) -> list:
        """Create consumption summary table."""
        elements = []
        
        elements.append(Paragraph("Consumption Summary", self.heading_style))
        
        summary = invoice.summary
        data = [
            ["Description", "Value"],
            ["Total Consumption", f"{summary.total_consumption_kwh:.1f} kWh"],
            ["Solar Energy", f"{summary.solar_consumption_kwh:.1f} kWh"],
            ["Grid Energy", f"{summary.grid_consumption_kwh:.1f} kWh"],
            ["Battery Energy", f"{summary.battery_consumption_kwh:.1f} kWh"],
        ]
        
        if summary.feed_in_kwh > 0:
            data.append(["Feed-in to Grid", f"{summary.feed_in_kwh:.1f} kWh"])
        
        table = Table(data, colWidths=[10*cm, 4*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_cost_breakdown(self, invoice: Invoice) -> list:
        """Create itemized cost breakdown."""
        elements = []
        
        elements.append(Paragraph("Cost Breakdown", self.heading_style))
        
        data = [["Description", "Amount (CHF)"]]
        
        for item in invoice.items:
            if item.category != "tax" and not item.is_percentage:
                data.append([
                    item.description,
                    f"{item.amount:.2f}" if item.amount >= 0 else f"-{abs(item.amount):.2f}"
                ])
        
        # Add feed-in as negative
        if invoice.summary.feed_in_revenue > 0:
            data.append([
                "Feed-in Revenue",
                f"-{invoice.summary.feed_in_revenue:.2f}"
            ])
        
        table = Table(data, colWidths=[10*cm, 4*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_total(self, invoice: Invoice) -> list:
        """Create total amount section."""
        elements = []
        
        summary = invoice.summary
        
        data = [
            ["Subtotal:", f"{summary.subtotal:.2f} CHF"],
            ["VAT (8.1%):", f"{summary.vat_amount:.2f} CHF"],
            ["TOTAL DUE:", f"{summary.total_due:.2f} CHF"],
        ]
        
        table = Table(data, colWidths=[10*cm, 4*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 12),
            ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor('#1a1a1a')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 1*cm))
        
        return elements
    
    def _create_payment_info(self, invoice: Invoice) -> list:
        """Create payment information section."""
        elements = []
        
        elements.append(Paragraph("Payment Information", self.heading_style))
        
        payment_text = f"""
        Please pay the total amount of <b>{invoice.summary.total_due:.2f} CHF</b> 
        by <b>{invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else 'N/A'}</b>.
        <br/><br/>
        For questions about this bill, please contact the property management.
        """
        
        payment = Paragraph(payment_text, self.normal_style)
        elements.append(payment)
        
        return elements
    
    def generate_summary_report(self, 
                               invoices: list[Invoice],
                               property_name: str = "") -> Path:
        """Generate a summary report for all invoices."""
        filename = f"summary_report_{date.today().strftime('%Y%m%d')}.pdf"
        filepath = self.output_dir / filename
        
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Title
        title = Paragraph(f"Summary Report - {property_name}", self.title_style)
        elements.append(title)
        
        # Summary table
        data = [
            ["Apartment", "Consumption (kWh)", "Solar (kWh)", "Total (CHF)"]
        ]
        
        total_consumption = 0
        total_solar = 0
        total_amount = 0
        
        for invoice in invoices:
            summary = invoice.summary
            apt_name = invoice.recipient_name or f"Apt {len(data)}"
            
            data.append([
                apt_name,
                f"{summary.total_consumption_kwh:.1f}",
                f"{summary.solar_consumption_kwh:.1f}",
                f"{summary.total_due:.2f}"
            ])
            
            total_consumption += summary.total_consumption_kwh
            total_solar += summary.solar_consumption_kwh
            total_amount += summary.total_due
        
        # Totals row
        data.append([
            "TOTAL",
            f"{total_consumption:.1f}",
            f"{total_solar:.1f}",
            f"{total_amount:.2f}"
        ])
        
        table = Table(data, colWidths=[5*cm, 3*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078d4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(table)
        
        doc.build(elements)
        
        return filepath
