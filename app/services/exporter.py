"""Export service for PDFs and data."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import pandas as pd

from ..models.billing import Invoice
from ..models.project import Project
from ..pdf.generator import PDFGenerator


class ExportService:
    """Service for exporting invoices and data.
    
    Handles:
    - PDF invoice generation
    - CSV export of calculations
    - Summary reports
    """
    
    def __init__(self, project: Project, output_dir: str | Path = "./output") -> None:
        """Initialize export service.
        
        Args:
            project: Current project
            output_dir: Directory for exported files
        """
        self.project = project
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.pdf_generator = PDFGenerator(self.output_dir / "invoices")
    
    def export_invoices(self, invoices: list[Invoice]) -> list[Path]:
        """Export invoices to PDF.
        
        Args:
            invoices: List of invoices to export
            
        Returns:
            List of paths to generated PDFs
        """
        pdf_paths = []
        
        property_name = self.project.property.name if self.project.property else ""
        property_address = ""
        if self.project.property:
            parts = filter(None, [
                self.project.property.address,
                self.project.property.zip_code,
                self.project.property.city,
            ])
            property_address = " ".join(parts)
        
        for invoice in invoices:
            try:
                path = self.pdf_generator.generate_invoice(
                    invoice=invoice,
                    property_name=property_name,
                    property_address=property_address,
                )
                pdf_paths.append(path)
            except Exception as e:
                # Log error but continue with other invoices
                print(f"Error generating PDF for {invoice.invoice_number}: {e}")
        
        return pdf_paths
    
    def export_summary_report(self, invoices: list[Invoice]) -> Optional[Path]:
        """Export a summary report for all invoices.
        
        Args:
            invoices: List of invoices to include in summary
            
        Returns:
            Path to generated PDF, or None if failed
        """
        try:
            property_name = self.project.property.name if self.project.property else ""
            return self.pdf_generator.generate_summary_report(invoices, property_name)
        except Exception as e:
            print(f"Error generating summary report: {e}")
            return None
    
    def export_data_csv(self, 
                       energy_flows: list,
                       billing_results: dict) -> dict[str, Path]:
        """Export calculation data to CSV files.
        
        Args:
            energy_flows: List of EnergyFlow objects
            billing_results: Dictionary of BillingResult objects
            
        Returns:
            Dictionary mapping file type to path
        """
        paths = {}
        
        # Export energy flows
        flow_data = []
        for flow in energy_flows:
            row = {
                'timestamp': flow.timestamp.isoformat(),
                'solar_available': flow.solar_available,
                'solar_to_owner': flow.solar_to_owner,
                'solar_to_grid': flow.solar_to_grid,
                'grid_import': flow.grid_import_available,
                'owner_consumption': flow.owner_consumption,
                'total_tenant_consumption': flow.total_tenant_consumption(),
            }
            
            # Add tenant-specific allocations
            for apt_id, solar in flow.solar_to_tenants.items():
                row[f'solar_to_{apt_id[:8]}'] = solar
            
            flow_data.append(row)
        
        if flow_data:
            flow_df = pd.DataFrame(flow_data)
            flow_path = self.output_dir / "energy_flows.csv"
            flow_df.to_csv(flow_path, index=False)
            paths['energy_flows'] = flow_path
        
        # Export billing results
        billing_data = []
        for apt_id, result in billing_results.items():
            row = {
                'apartment_id': apt_id,
                'apartment_name': result.apartment_name,
                'total_consumption_kwh': result.total_consumption_kwh,
                'solar_consumption_kwh': result.solar_consumption_kwh,
                'grid_consumption_kwh': result.grid_consumption_kwh,
                'energy_cost': result.energy_cost,
                'grid_cost': result.grid_cost,
                'basic_fee': result.basic_fee,
                'subtotal': result.subtotal,
                'vat_amount': result.vat_amount,
                'total_due': result.total_due,
                'solar_savings': result.solar_savings,
            }
            billing_data.append(row)
        
        if billing_data:
            billing_df = pd.DataFrame(billing_data)
            billing_path = self.output_dir / "billing_results.csv"
            billing_df.to_csv(billing_path, index=False)
            paths['billing_results'] = billing_path
        
        return paths
    
    def create_export_package(self,
                             invoices: list[Invoice],
                             energy_flows: list,
                             billing_results: dict) -> dict[str, list[Path]]:
        """Create a complete export package with all outputs.
        
        Args:
            invoices: List of invoices
            energy_flows: List of energy flows
            billing_results: Dictionary of billing results
            
        Returns:
            Dictionary with categorized export paths
        """
        results = {
            'pdfs': [],
            'csvs': [],
        }
        
        # Generate PDFs
        invoice_pdfs = self.export_invoices(invoices)
        results['pdfs'].extend(invoice_pdfs)
        
        summary_pdf = self.export_summary_report(invoices)
        if summary_pdf:
            results['pdfs'].append(summary_pdf)
        
        # Generate CSVs
        csv_paths = self.export_data_csv(energy_flows, billing_results)
        results['csvs'].extend(csv_paths.values())
        
        return results
