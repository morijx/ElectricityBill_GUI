"""
Electricity Billing System - Consolidated GUI Module

This module contains the complete GUI application using PySide6.
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import date, timedelta
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFrame, QSplitter,
    QMessageBox, QFileDialog, QApplication,
    QGroupBox, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar,
    QTabWidget, QRadioButton, QButtonGroup, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QFont, QAction

# Import from consolidated modules
from app.models_consolidated import (
    Project, Property, Apartment, Meter, AllocationConfig,
    AllocationStrategyType, SwissTariff, TariffComponent, TariffType,
    BillingPeriod, MeterType
)
from app.services_consolidated import (
    CSVImporter, AllocationEngine, BillingEngine, PDFGenerator, DatabaseService
)


# ============================================================================
# NAVIGATION AND BASE CLASSES
# ============================================================================

class NavigationList(QListWidget):
    """Sidebar navigation list."""
    
    page_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.currentRowChanged.connect(self._on_row_changed)
        
        self.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
    
    def add_page(self, name: str, icon: str = "") -> None:
        """Add a navigation item."""
        item = QListWidgetItem(name)
        if icon:
            item.setIcon(QIcon(icon))
        self.addItem(item)
    
    def _on_row_changed(self, row: int) -> None:
        """Emit page changed signal."""
        self.page_changed.emit(row)


class BasePage(QWidget):
    """Base class for all pages."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the page UI."""
        layout = QVBoxLayout(self)
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title_label)
    
    def on_show(self) -> None:
        """Called when page is shown."""
        pass
    
    def on_hide(self) -> None:
        """Called when page is hidden."""
        pass


# ============================================================================
# PROJECT SETUP PAGE
# ============================================================================

class ProjectSetupPage(BasePage):
    """Project setup and configuration page."""
    
    project_updated = Signal()
    
    def __init__(self, project: Project, parent=None):
        super().__init__("Project Setup", parent)
        self.project = project
        self.property_edit: QLineEdit = None
        self.address_edit: QLineEdit = None
        self.city_edit: QLineEdit = None
        self.zip_edit: QLineEdit = None
        self.desc_edit: QTextEdit = None
        self.apt_count_spin: QSpinBox = None
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        # Property info section
        group = QGroupBox("Property Information")
        form = QFormLayout()
        
        self.property_edit = QLineEdit()
        self.property_edit.setText(self.project.property_info.name if self.project.property_info else "")
        form.addRow("Property Name:", self.property_edit)
        
        self.address_edit = QLineEdit()
        self.address_edit.setText(self.project.property_info.address if self.project.property_info else "")
        form.addRow("Address:", self.address_edit)
        
        self.city_edit = QLineEdit()
        self.city_edit.setText(self.project.property_info.city if self.project.property_info else "")
        form.addRow("City:", self.city_edit)
        
        self.zip_edit = QLineEdit()
        self.zip_edit.setText(self.project.property_info.zip_code if self.project.property_info else "")
        form.addRow("ZIP Code:", self.zip_edit)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        # Apartments section
        apt_group = QGroupBox("Apartments")
        apt_layout = QVBoxLayout()
        
        apt_form = QFormLayout()
        self.apt_count_spin = QSpinBox()
        self.apt_count_spin.setRange(1, 20)
        self.apt_count_spin.setValue(len(self.project.property_info.apartments) if self.project.property_info else 1)
        self.apt_count_spin.valueChanged.connect(self._update_apartments)
        apt_form.addRow("Number of Apartments:", self.apt_count_spin)
        
        apt_group.setLayout(apt_form)
        apt_layout.addWidget(apt_group)
        
        # Owner apartment selection
        self.owner_combo = QComboBox()
        self._update_owner_combo()
        owner_form = QFormLayout()
        owner_form.addRow("Owner Apartment:", self.owner_combo)
        layout.addLayout(owner_form)
        
        self.save_btn = QPushButton("Save Project")
        self.save_btn.clicked.connect(self._save_project)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
    
    def _update_apartments(self, count: int) -> None:
        """Update apartment count."""
        if not self.project.property_info:
            self.project.property_info = Property()
        
        current = len(self.project.property_info.apartments)
        if count > current:
            for i in range(current, count):
                apt = Apartment(
                    name=f"Apartment {i+1}",
                    number=str(i+1),
                    floor=i // 3,
                )
                self.project.property_info.add_apartment(apt)
        elif count < current:
            for _ in range(current - count):
                self.project.property_info.apartments.pop()
        
        self._update_owner_combo()
        self.project_updated.emit()
    
    def _update_owner_combo(self) -> None:
        """Update owner apartment combo box."""
        if hasattr(self, 'owner_combo') and self.project.property_info:
            self.owner_combo.clear()
            for apt in self.project.property_info.apartments:
                self.owner_combo.addItem(f"{apt.name} ({apt.number})")
    
    def _save_project(self) -> None:
        """Save project settings."""
        if self.project.property_info:
            self.project.property_info.name = self.property_edit.text()
            self.project.property_info.address = self.address_edit.text()
            self.project.property_info.city = self.city_edit.text()
            self.project.property_info.zip_code = self.zip_edit.text()
        
        self.project.modified_date = date.today()
        QMessageBox.information(self, "Success", "Project saved successfully!")
        self.project_updated.emit()


# ============================================================================
# DATA IMPORT PAGE
# ============================================================================

class DataImportPage(BasePage):
    """CSV data import page."""
    
    data_imported = Signal(object)  # Emits list of EnergyData
    
    def __init__(self, parent=None):
        super().__init__("Import Data", parent)
        self.importer = CSVImporter()
        self.imported_data = []
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        # Instructions
        instructions = QLabel(
            "Import CSV files with 15-minute interval energy data.\n"
            "Supported: Grid import/export, Solar production, Battery, Apartment meters"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # File selection
        file_group = QGroupBox("CSV Files")
        file_layout = QVBoxLayout()
        
        self.file_list = QTableWidget(0, 2)
        self.file_list.setHorizontalHeaderLabels(["File", "Type"])
        self.file_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        file_layout.addWidget(self.file_list)
        
        btn_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("Add CSV Files")
        self.add_file_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_file_btn)
        
        self.remove_file_btn = QPushButton("Remove Selected")
        self.remove_file_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_file_btn)
        
        file_layout.addLayout(btn_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Import button
        self.import_btn = QPushButton("Import Data")
        self.import_btn.clicked.connect(self._import_data)
        layout.addWidget(self.import_btn)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        layout.addStretch()
    
    def _add_files(self) -> None:
        """Add CSV files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select CSV Files", "", "CSV Files (*.csv)"
        )
        
        for file_path in files:
            path = Path(file_path)
            # Auto-detect type from filename
            file_type = "Unknown"
            name_lower = path.name.lower()
            if 'solar' in name_lower or 'pv' in name_lower:
                file_type = "Solar"
            elif 'grid' in name_lower and 'export' in name_lower:
                file_type = "Grid Export"
            elif 'grid' in name_lower:
                file_type = "Grid Import"
            elif 'battery' in name_lower:
                file_type = "Battery"
            elif 'apt' in name_lower or 'apartment' in name_lower:
                file_type = "Apartment"
            
            row = self.file_list.rowCount()
            self.file_list.insertRow(row)
            self.file_list.setItem(row, 0, QTableWidgetItem(path.name))
            self.file_list.setItem(row, 1, QTableWidgetItem(file_type))
            self.file_list.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(path))
    
    def _remove_selected(self) -> None:
        """Remove selected files."""
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.removeRow(row)
    
    def _import_data(self) -> None:
        """Import all selected files."""
        self.progress.setVisible(True)
        self.progress.setMaximum(self.file_list.rowCount())
        self.progress.setValue(0)
        
        self.imported_data = []
        errors = []
        
        for row in range(self.file_list.rowCount()):
            path_str = self.file_list.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if path_str:
                try:
                    path = Path(path_str)
                    data = self.importer.import_file(path)
                    self.imported_data.append(data)
                except Exception as e:
                    errors.append(f"{path.name}: {str(e)}")
            
            self.progress.setValue(row + 1)
        
        self.progress.setVisible(False)
        
        if errors:
            QMessageBox.warning(
                self, "Import Warnings",
                f"Some files failed to import:\n\n" + "\n".join(errors)
            )
        
        if self.imported_data:
            QMessageBox.information(
                self, "Import Complete",
                f"Successfully imported {len(self.imported_data)} file(s)"
            )
            self.data_imported.emit(self.imported_data)


# ============================================================================
# TARIFF CONFIGURATION PAGE
# ============================================================================

class TariffConfigPage(BasePage):
    """Tariff configuration page."""
    
    tariff_updated = Signal()
    
    def __init__(self, project: Project, parent=None):
        super().__init__("Tariff Configuration", parent)
        self.project = project
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        if not isinstance(self.project.tariff, SwissTariff):
            self.project.tariff = SwissTariff()
        
        tariff = self.project.tariff
        
        # Energy prices
        energy_group = QGroupBox("Energy Prices (CHF/kWh)")
        energy_form = QFormLayout()
        
        self.peak_price_spin = QDoubleSpinBox()
        self.peak_price_spin.setRange(0, 1)
        self.peak_price_spin.setValue(tariff.energy_price_peak)
        self.peak_price_spin.setSingleStep(0.01)
        energy_form.addRow("Peak Price:", self.peak_price_spin)
        
        self.offpeak_price_spin = QDoubleSpinBox()
        self.offpeak_price_spin.setRange(0, 1)
        self.offpeak_price_spin.setValue(tariff.energy_price_off_peak)
        self.offpeak_price_spin.setSingleStep(0.01)
        energy_form.addRow("Off-Peak Price:", self.offpeak_price_spin)
        
        energy_group.setLayout(energy_form)
        layout.addWidget(energy_group)
        
        # Fees
        fees_group = QGroupBox("Fees & Charges")
        fees_form = QFormLayout()
        
        self.grid_fee_spin = QDoubleSpinBox()
        self.grid_fee_spin.setRange(0, 0.5)
        self.grid_fee_spin.setValue(tariff.grid_fee)
        fees_form.addRow("Grid Fee (CHF/kWh):", self.grid_fee_spin)
        
        self.network_spin = QDoubleSpinBox()
        self.network_spin.setRange(0, 0.5)
        self.network_spin.setValue(tariff.network_tariff)
        fees_form.addRow("Network Tariff (CHF/kWh):", self.network_spin)
        
        self.basic_fee_spin = QDoubleSpinBox()
        self.basic_fee_spin.setRange(0, 100)
        self.basic_fee_spin.setValue(tariff.basic_fee_monthly)
        fees_form.addRow("Basic Fee (CHF/month):", self.basic_fee_spin)
        
        self.renewable_spin = QDoubleSpinBox()
        self.renewable_spin.setRange(0, 0.1)
        self.renewable_spin.setValue(tariff.renewable_fee)
        fees_form.addRow("Renewable Fee (CHF/kWh):", self.renewable_spin)
        
        fees_group.setLayout(fees_form)
        layout.addWidget(fees_group)
        
        # Feed-in and VAT
        other_group = QGroupBox("Feed-in & Taxes")
        other_form = QFormLayout()
        
        self.feedin_spin = QDoubleSpinBox()
        self.feedin_spin.setRange(0, 0.5)
        self.feedin_spin.setValue(tariff.feed_in_remuneration)
        other_form.addRow("Feed-in Rate (CHF/kWh):", self.feedin_spin)
        
        self.vat_spin = QDoubleSpinBox()
        self.vat_spin.setRange(0, 30)
        self.vat_spin.setValue(tariff.vat_rate)
        other_form.addRow("VAT (%):", self.vat_spin)
        
        other_group.setLayout(other_form)
        layout.addWidget(other_group)
        
        # Save button
        self.save_btn = QPushButton("Save Tariff")
        self.save_btn.clicked.connect(self._save_tariff)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
    
    def _save_tariff(self) -> None:
        """Save tariff configuration."""
        if isinstance(self.project.tariff, SwissTariff):
            tariff = self.project.tariff
            tariff.energy_price_peak = self.peak_price_spin.value()
            tariff.energy_price_off_peak = self.offpeak_price_spin.value()
            tariff.grid_fee = self.grid_fee_spin.value()
            tariff.network_tariff = self.network_spin.value()
            tariff.basic_fee_monthly = self.basic_fee_spin.value()
            tariff.renewable_fee = self.renewable_spin.value()
            tariff.feed_in_remuneration = self.feedin_spin.value()
            tariff.vat_rate = self.vat_spin.value()
            
            # Recreate components with new values
            tariff.create_default_components()
            
            QMessageBox.information(self, "Success", "Tariff saved successfully!")
            self.tariff_updated.emit()


# ============================================================================
# ALLOCATION SETTINGS PAGE
# ============================================================================

class AllocationSettingsPage(BasePage):
    """Energy allocation settings page."""
    
    config_updated = Signal()
    
    def __init__(self, project: Project, parent=None):
        super().__init__("Allocation Settings", parent)
        self.project = project
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        if not self.project.allocation_config:
            self.project.allocation_config = AllocationConfig()
        
        config = self.project.allocation_config
        
        # Strategy selection
        strategy_group = QGroupBox("Allocation Strategy")
        strategy_layout = QVBoxLayout()
        
        self.strategy_group = QButtonGroup()
        
        self.priority_radio = QRadioButton("Priority (Owner First)\nOwner gets solar energy first, tenants get surplus at discount")
        self.priority_radio.setChecked(config.strategy == AllocationStrategyType.PRIORITY)
        strategy_layout.addWidget(self.priority_radio)
        
        self.equal_radio = QRadioButton("Equal Sharing\nSolar energy divided equally among all apartments")
        self.equal_radio.setChecked(config.strategy == AllocationStrategyType.EQUAL)
        strategy_layout.addWidget(self.equal_radio)
        
        self.proportional_radio = QRadioButton("Proportional\nSolar energy distributed based on consumption share")
        self.proportional_radio.setChecked(config.strategy == AllocationStrategyType.PROPORTIONAL)
        strategy_layout.addWidget(self.proportional_radio)
        
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)
        
        # Solar discount
        discount_group = QGroupBox("Solar Discount for Tenants")
        discount_form = QFormLayout()
        
        self.discount_spin = QDoubleSpinBox()
        self.discount_spin.setRange(0, 0.2)
        self.discount_spin.setValue(config.solar_discount)
        self.discount_spin.setSuffix(" CHF/kWh")
        discount_form.addRow("Discount:", self.discount_spin)
        
        discount_group.setLayout(discount_form)
        layout.addWidget(discount_group)
        
        # Battery settings
        battery_group = QGroupBox("Battery Allocation")
        battery_form = QFormLayout()
        
        self.battery_combo = QComboBox()
        self.battery_combo.addItems(["Owner Priority", "Equal Sharing", "Proportional"])
        battery_idx = ["owner", "equal", "proportional"].index(config.battery_priority)
        self.battery_combo.setCurrentIndex(battery_idx)
        battery_form.addRow("Strategy:", self.battery_combo)
        
        battery_group.setLayout(battery_form)
        layout.addWidget(battery_group)
        
        # Save button
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save_config)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
    
    def _save_config(self) -> None:
        """Save allocation configuration."""
        if self.project.allocation_config:
            config = self.project.allocation_config
            
            if self.priority_radio.isChecked():
                config.strategy = AllocationStrategyType.PRIORITY
            elif self.equal_radio.isChecked():
                config.strategy = AllocationStrategyType.EQUAL
            else:
                config.strategy = AllocationStrategyType.PROPORTIONAL
            
            config.solar_discount = self.discount_spin.value()
            config.battery_priority = ["owner", "equal", "proportional"][self.battery_combo.currentIndex()]
            
            # Set owner apartment
            if self.project.property_info and self.project.property_info.apartments:
                config.owner_apartment_id = self.project.property_info.apartments[0].id
            
            QMessageBox.information(self, "Success", "Allocation settings saved!")
            self.config_updated.emit()


# ============================================================================
# CALCULATION AND RESULTS PAGE
# ============================================================================

class CalculationPage(BasePage):
    """Calculation preview and results page."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__("Calculate & Preview", parent)
        self.project = project
        self.billing_result = None
        self.allocations = {}
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        # Period selection
        period_group = QGroupBox("Billing Period")
        period_form = QFormLayout()
        
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.start_date_edit.setText((date.today() - timedelta(days=365)).isoformat())
        period_form.addRow("Start Date:", self.start_date_edit)
        
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.end_date_edit.setText(date.today().isoformat())
        period_form.addRow("End Date:", self.end_date_edit)
        
        period_group.setLayout(period_form)
        layout.addWidget(period_group)
        
        # Calculate button
        self.calc_btn = QPushButton("Calculate Bills")
        self.calc_btn.clicked.connect(self._calculate)
        layout.addWidget(self.calc_btn)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Apartment", "Total kWh", "Solar kWh", "Grid kWh", "Cost (CHF)", "Savings"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)
        
        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        
        layout.addStretch()
    
    def _calculate(self) -> None:
        """Perform billing calculation."""
        try:
            # Parse dates
            start = date.fromisoformat(self.start_date_edit.text())
            end = date.fromisoformat(self.end_date_edit.text())
            period = BillingPeriod(start_date=start, end_date=end, months=max(1, (end.year - start.year) * 12 + end.month - start.month))
            
            # Get sample data (in real app, use imported data)
            if not self.project.property_info or not self.project.property_info.apartments:
                QMessageBox.warning(self, "Error", "Please set up property and apartments first")
                return
            
            # Simulate consumption data
            consumption_data = {}
            for apt in self.project.property_info.apartments:
                consumption_data[apt.id] = 500.0  # Sample: 500 kWh per apartment
            
            solar_production = 800.0  # Sample: 800 kWh total
            grid_import = sum(consumption_data.values()) - solar_production * 0.6
            grid_export = solar_production * 0.4
            
            # Allocate energy
            engine = AllocationEngine()
            self.allocations = engine.allocate(
                consumption_data=consumption_data,
                solar_production=solar_production,
                grid_import=grid_import,
                grid_export=grid_export,
                strategy_type=self.project.allocation_config.strategy if self.project.allocation_config else AllocationStrategyType.PRIORITY,
                config=self.project.allocation_config
            )
            
            # Calculate billing
            if not isinstance(self.project.tariff, SwissTariff):
                self.project.tariff = SwissTariff()
                self.project.tariff.create_default_components()
            
            billing_engine = BillingEngine(self.project.tariff)
            self.billing_result = billing_engine.calculate_billing_result(
                property_info=self.project.property_info,
                allocations=self.allocations,
                period=period,
                total_solar=solar_production,
                total_grid_import=grid_import,
                total_grid_export=grid_export,
                total_battery=0
            )
            
            # Display results
            self.results_table.setRowCount(len(self.allocations))
            for row, (apt_id, alloc) in enumerate(self.allocations.items()):
                self.results_table.setItem(row, 0, QTableWidgetItem(alloc.apartment_name))
                self.results_table.setItem(row, 1, QTableWidgetItem(f"{alloc.total_consumption_kwh:.1f}"))
                self.results_table.setItem(row, 2, QTableWidgetItem(f"{alloc.solar_consumption_kwh:.1f}"))
                self.results_table.setItem(row, 3, QTableWidgetItem(f"{alloc.grid_consumption_kwh:.1f}"))
                self.results_table.setItem(row, 4, QTableWidgetItem(f"{alloc.total_cost_chf:.2f}"))
                self.results_table.setItem(row, 5, QTableWidgetItem(f"{alloc.solar_discount_chf:.2f}"))
            
            # Summary
            summary = (
                f"Total Consumption: {self.billing_result.total_consumption_kwh:.1f} kWh\n"
                f"Solar Production: {self.billing_result.total_solar_kwh:.1f} kWh\n"
                f"Self-Consumption Rate: {self.billing_result.self_consumption_rate*100:.1f}%\n"
                f"Total Costs: CHF {self.billing_result.total_costs_chf:.2f}"
            )
            self.summary_label.setText(summary)
            
            QMessageBox.information(self, "Success", "Calculation completed!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed: {str(e)}")


# ============================================================================
# PDF EXPORT PAGE
# ============================================================================

class PDFExportPage(BasePage):
    """PDF generation and export page."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__("Export PDFs", parent)
        self.project = project
        self.pdf_generator = PDFGenerator()
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        instructions = QLabel(
            "Generate professional PDF invoices for each apartment.\n"
            "Invoices include detailed cost breakdowns and charts."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Output directory
        dir_group = QGroupBox("Output Directory")
        dir_layout = QHBoxLayout()
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("Select output folder...")
        dir_layout.addWidget(self.dir_edit)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(self.browse_btn)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        self.summary_check = QCheckBox("Generate summary PDF for entire property")
        self.summary_check.setChecked(True)
        options_layout.addWidget(self.summary_check)
        
        self.individual_check = QCheckBox("Generate individual PDF for each apartment")
        self.individual_check.setChecked(True)
        options_layout.addWidget(self.individual_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Generate button
        self.generate_btn = QPushButton("Generate PDFs")
        self.generate_btn.clicked.connect(self._generate_pdfs)
        layout.addWidget(self.generate_btn)
        
        # Results
        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)
        layout.addWidget(self.results_label)
        
        layout.addStretch()
    
    def _browse_dir(self) -> None:
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if dir_path:
            self.dir_edit.setText(dir_path)
    
    def _generate_pdfs(self) -> None:
        """Generate PDF invoices."""
        output_dir = Path(self.dir_edit.text()) if self.dir_edit.text() else Path.home() / "ElectricityBills"
        output_dir.mkdir(exist_ok=True)
        
        generated = []
        
        try:
            # Generate individual invoices
            if self.individual_check.isChecked() and hasattr(self.parent(), 'calculation_page'):
                calc_page = self.parent().calculation_page
                if calc_page.billing_result:
                    for invoice in calc_page.billing_result.invoices:
                        pdf_path = output_dir / f"Invoice_{invoice.apartment_name.replace(' ', '_')}.pdf"
                        self.pdf_generator.generate_invoice_pdf(invoice, pdf_path)
                        generated.append(str(pdf_path))
            
            # Generate summary
            if self.summary_check.isChecked() and hasattr(self.parent(), 'calculation_page'):
                calc_page = self.parent().calculation_page
                if calc_page.billing_result:
                    summary_path = output_dir / "Billing_Summary.pdf"
                    self.pdf_generator.generate_summary_pdf(calc_page.billing_result, summary_path)
                    generated.append(str(summary_path))
            
            if generated:
                self.results_label.setText(f"Generated {len(generated)} PDF(s):\n\n" + "\n".join(generated))
                QMessageBox.information(self, "Success", f"Generated {len(generated)} PDF(s)")
            else:
                self.results_label.setText("No data to export. Please calculate bills first.")
                QMessageBox.warning(self, "Warning", "Please calculate bills before exporting PDFs")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"PDF generation failed: {str(e)}")


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electricity Billing System")
        self.setMinimumSize(1000, 700)
        
        # Initialize project
        self.project = Project(name="New Project")
        
        # Setup UI
        self.setup_ui()
        
        # Connect pages
        self.navigation.page_changed.connect(self._on_page_changed)
    
    def setup_ui(self) -> None:
        """Set up the main window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Navigation sidebar
        self.navigation = NavigationList()
        self.navigation.add_page("Project Setup")
        self.navigation.add_page("Import Data")
        self.navigation.add_page("Tariff Config")
        self.navigation.add_page("Allocation")
        self.navigation.add_page("Calculate")
        self.navigation.add_page("Export PDFs")
        main_layout.addWidget(self.navigation)
        
        # Page stack
        self.stack = QStackedWidget()
        
        # Create pages
        self.project_page = ProjectSetupPage(self.project)
        self.import_page = DataImportPage()
        self.tariff_page = TariffConfigPage(self.project)
        self.allocation_page = AllocationSettingsPage(self.project)
        self.calculation_page = CalculationPage(self.project)
        self.pdf_page = PDFExportPage(self.project)
        
        self.stack.addWidget(self.project_page)
        self.stack.addWidget(self.import_page)
        self.stack.addWidget(self.tariff_page)
        self.stack.addWidget(self.allocation_page)
        self.stack.addWidget(self.calculation_page)
        self.stack.addWidget(self.pdf_page)
        
        main_layout.addWidget(self.stack)
        
        # Menu bar
        self._create_menu_bar()
    
    def _create_menu_bar(self) -> None:
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Project", self)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)
        
        save_action = QAction("Save Project", self)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load Project", self)
        load_action.triggered.connect(self._load_project)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _on_page_changed(self, index: int) -> None:
        """Handle page change."""
        self.stack.setCurrentIndex(index)
    
    def _new_project(self) -> None:
        """Create new project."""
        reply = QMessageBox.question(
            self, "New Project",
            "Create a new project? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.project = Project(name="New Project")
            self.project_page = ProjectSetupPage(self.project)
            self.stack.replaceWidget(0, self.project_page)
            self.tariff_page = TariffConfigPage(self.project)
            self.stack.replaceWidget(2, self.tariff_page)
            self.allocation_page = AllocationSettingsPage(self.project)
            self.stack.replaceWidget(3, self.allocation_page)
            self.calculation_page = CalculationPage(self.project)
            self.stack.replaceWidget(4, self.calculation_page)
            self.pdf_page = PDFExportPage(self.project)
            self.stack.replaceWidget(5, self.pdf_page)
            self.navigation.setCurrentRow(0)
    
    def _save_project(self) -> None:
        """Save project to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON Files (*.json)"
        )
        
        if file_path:
            path = Path(file_path)
            self.project.save_config(path)
            QMessageBox.information(self, "Success", "Project saved successfully!")
    
    def _load_project(self) -> None:
        """Load project from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "JSON Files (*.json)"
        )
        
        if file_path:
            path = Path(file_path)
            try:
                self.project = Project.load_config(path)
                
                # Recreate pages with loaded project
                self.project_page = ProjectSetupPage(self.project)
                self.stack.replaceWidget(0, self.project_page)
                self.tariff_page = TariffConfigPage(self.project)
                self.stack.replaceWidget(2, self.tariff_page)
                self.allocation_page = AllocationSettingsPage(self.project)
                self.stack.replaceWidget(3, self.allocation_page)
                self.calculation_page = CalculationPage(self.project)
                self.stack.replaceWidget(4, self.calculation_page)
                self.pdf_page = PDFExportPage(self.project)
                self.stack.replaceWidget(5, self.pdf_page)
                
                QMessageBox.information(self, "Success", "Project loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project: {str(e)}")
    
    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self, "About Electricity Billing System",
            "Electricity Billing System v1.0\n\n"
            "A modular application for calculating and generating\n"
            "electricity bills for multi-unit properties with solar energy,\n"
            "batteries, and flexible energy-sharing logic.\n\n"
            "Built with Python and PySide6"
        )


def run_gui() -> int:
    """Run the GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set dark palette
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    return app.exec()
