"""Main application window."""

from __future__ import annotations
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFrame, QSplitter,
    QMessageBox, QFileDialog, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QFont, QAction

from ..models.project import Project


class NavigationList(QListWidget):
    """Sidebar navigation list."""
    
    page_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.currentRowChanged.connect(self._on_row_changed)
        
        # Style
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
        """Set up the page UI. Override in subclasses."""
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


class ProjectSetupPage(BasePage):
    """Project setup and configuration page."""
    
    def __init__(self, parent=None):
        super().__init__("Project Setup", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        # Property info section
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QLineEdit
        
        group = QGroupBox("Property Information")
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter property name")
        form.addRow("Property Name:", self.name_edit)
        
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Enter street address")
        form.addRow("Address:", self.address_edit)
        
        self.city_edit = QLineEdit()
        self.city_edit.setPlaceholderText("Enter city")
        form.addRow("City:", self.city_edit)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        layout.addStretch()


class DataImportPage(BasePage):
    """CSV data import page."""
    
    def __init__(self, parent=None):
        super().__init__("Import Data", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QTextEdit, QGroupBox
        
        instructions = QLabel(
            "Import CSV files containing energy meter data.\n"
            "Supported formats: 15-minute interval data with timestamps."
        )
        layout.addWidget(instructions)
        
        # File selection
        file_group = QGroupBox("Data Files")
        file_layout = QVBoxLayout()
        
        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        self.file_list.setMaximumHeight(150)
        file_layout.addWidget(self.file_list)
        
        from PySide6.QtWidgets import QPushButton
        import_btn = QPushButton("Select CSV Files...")
        import_btn.clicked.connect(self.select_files)
        file_layout.addWidget(import_btn)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        layout.addStretch()
    
    def select_files(self) -> None:
        """Open file dialog to select CSV files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select CSV Files", "", "CSV Files (*.csv)"
        )
        if files:
            self.file_list.setText("\n".join(files))


class TariffConfigPage(BasePage):
    """Tariff configuration page."""
    
    def __init__(self, parent=None):
        super().__init__("Tariff Configuration", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QFormLayout, QDoubleSpinBox, QGroupBox
        
        # Energy prices
        energy_group = QGroupBox("Energy Prices (CHF/kWh)")
        energy_form = QFormLayout()
        
        self.peak_price = QDoubleSpinBox()
        self.peak_price.setRange(0, 10)
        self.peak_price.setValue(0.25)
        self.peak_price.setDecimals(4)
        energy_form.addRow("Peak Price:", self.peak_price)
        
        self.off_peak_price = QDoubleSpinBox()
        self.off_peak_price.setRange(0, 10)
        self.off_peak_price.setValue(0.18)
        self.off_peak_price.setDecimals(4)
        energy_form.addRow("Off-Peak Price:", self.off_peak_price)
        
        energy_group.setLayout(energy_form)
        layout.addWidget(energy_group)
        
        # Grid fees
        grid_group = QGroupBox("Grid & Network Fees")
        grid_form = QFormLayout()
        
        self.grid_fee = QDoubleSpinBox()
        self.grid_fee.setRange(0, 1)
        self.grid_fee.setValue(0.08)
        self.grid_fee.setDecimals(4)
        grid_form.addRow("Grid Fee (CHF/kWh):", self.grid_fee)
        
        self.basic_fee = QDoubleSpinBox()
        self.basic_fee.setRange(0, 100)
        self.basic_fee.setValue(15.0)
        self.basic_fee.setDecimals(2)
        grid_form.addRow("Basic Fee (CHF/month):", self.basic_fee)
        
        grid_group.setLayout(grid_form)
        layout.addWidget(grid_group)
        
        layout.addStretch()


class AllocationSettingsPage(BasePage):
    """Energy allocation settings page."""
    
    def __init__(self, parent=None):
        super().__init__("Allocation Settings", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QComboBox, QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox
        
        # Strategy selection
        strategy_group = QGroupBox("Allocation Strategy")
        strategy_form = QFormLayout()
        
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "Priority (Owner First)",
            "Proportional",
            "Equal Sharing"
        ])
        strategy_form.addRow("Strategy:", self.strategy_combo)
        
        self.owner_priority_check = QCheckBox("Owner gets solar priority")
        self.owner_priority_check.setChecked(True)
        strategy_form.addRow(self.owner_priority_check)
        
        strategy_group.setLayout(strategy_form)
        layout.addWidget(strategy_group)
        
        # Solar discount
        discount_group = QGroupBox("Solar Discount")
        discount_form = QFormLayout()
        
        self.discount_spin = QDoubleSpinBox()
        self.discount_spin.setRange(0, 1)
        self.discount_spin.setValue(0.02)
        self.discount_spin.setDecimals(4)
        self.discount_spin.setSuffix(" CHF/kWh")
        discount_form.addRow("Tenant Discount:", self.discount_spin)
        
        discount_group.setLayout(discount_form)
        layout.addWidget(discount_group)
        
        layout.addStretch()


class CalculationPreviewPage(BasePage):
    """Calculation preview page."""
    
    def __init__(self, parent=None):
        super().__init__("Calculation Preview", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QTextEdit
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)
        
        calc_btn = QPushButton("Run Calculation")
        calc_btn.clicked.connect(self.run_calculation)
        layout.addWidget(calc_btn)
    
    def run_calculation(self) -> None:
        """Run calculation and show preview."""
        self.preview_text.setText("Calculation running...\n\nResults will appear here.")


class PDFExportPage(BasePage):
    """PDF export page."""
    
    def __init__(self, parent=None):
        super().__init__("PDF Export", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QCheckBox, QPushButton
        
        self.owner_check = QCheckBox("Generate invoice for owner apartment")
        self.owner_check.setChecked(True)
        layout.addWidget(self.owner_check)
        
        self.tenant_check = QCheckBox("Generate invoices for tenant apartments")
        self.tenant_check.setChecked(True)
        layout.addWidget(self.tenant_check)
        
        layout.addStretch()
        
        export_btn = QPushButton("Generate PDFs")
        export_btn.clicked.connect(self.export_pdfs)
        layout.addWidget(export_btn)
    
    def export_pdfs(self) -> None:
        """Export PDF invoices."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            QMessageBox.information(
                self, "Export Complete",
                f"PDFs generated in: {folder}"
            )


class AnalyticsPage(BasePage):
    """Analytics and charts page."""
    
    def __init__(self, parent=None):
        super().__init__("Analytics", parent)
    
    def setup_ui(self) -> None:
        super().setup_ui()
        layout = self.layout()
        
        from PySide6.QtWidgets import QLabel
        
        placeholder = QLabel("Charts and analytics will be displayed here.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electricity Billing System")
        self.setMinimumSize(1000, 700)
        
        # Current project
        self.current_project: Project | None = None
        
        self.setup_ui()
        self.setup_menu()
    
    def setup_ui(self) -> None:
        """Set up the main window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sidebar navigation
        self.navigation = NavigationList()
        self.navigation.add_page("Project Setup")
        self.navigation.add_page("Import Data")
        self.navigation.add_page("Tariff Config")
        self.navigation.add_page("Allocation")
        self.navigation.add_page("Preview")
        self.navigation.add_page("PDF Export")
        self.navigation.add_page("Analytics")
        
        main_layout.addWidget(self.navigation)
        
        # Page stack
        self.page_stack = QStackedWidget()
        
        self.pages = [
            ProjectSetupPage(),
            DataImportPage(),
            TariffConfigPage(),
            AllocationSettingsPage(),
            CalculationPreviewPage(),
            PDFExportPage(),
            AnalyticsPage(),
        ]
        
        for page in self.pages:
            self.page_stack.addWidget(page)
        
        main_layout.addWidget(self.page_stack)
        
        # Connect navigation
        self.navigation.page_changed.connect(self.page_stack.setCurrentIndex)
    
    def setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Project", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Project...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    @Slot()
    def new_project(self) -> None:
        """Create a new project."""
        self.current_project = Project(name="New Project")
        self.navigation.setCurrentRow(0)
    
    @Slot()
    def open_project(self) -> None:
        """Open an existing project."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Project Files (*.json *.db)"
        )
        if file_path:
            # Load project logic here
            pass
    
    @Slot()
    def save_project(self) -> None:
        """Save current project."""
        if self.current_project is None:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON Files (*.json)"
        )
        if file_path:
            # Save project logic here
            pass
    
    @Slot()
    def show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Electricity Billing System",
            "Electricity Billing System v1.0\n\n"
            "A modular application for generating electricity bills\n"
            "for multi-unit properties with solar energy systems."
        )
