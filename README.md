# Electricity Billing System

A modular Python desktop application for generating electricity bills for multi-unit properties with solar energy systems, batteries, and flexible energy-sharing logic.

## Features

- **Multi-unit support**: 2-10 apartments with individual meters
- **Solar energy allocation**: Configurable priority rules for solar distribution
- **Battery management**: Flexible battery usage allocation
- **Swiss electricity billing**: Complete Swiss tariff structure support
- **CSV import**: 15-minute interval energy data import
- **PDF generation**: Professional utility bill reports
- **Analytics**: Charts and visualizations for energy flows
- **SQLite persistence**: Project and configuration storage

## Architecture

```
app/
├── gui/           # PySide6 GUI components
├── models/        # Data models (pydantic/dataclasses)
├── services/      # Business logic services
├── billing/       # Billing calculation engine
├── allocation/    # Energy allocation strategies
├── pdf/           # PDF report generation
├── charts/        # Matplotlib/Plotly visualizations
├── database/      # SQLite database layer
├── utils/         # Utilities and helpers
└── main.py        # Application entry point
```

## Installation

### Prerequisites

- Python 3.12+
- pip package manager

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
python main.py
```

### Building Standalone EXE (Windows)

```bash
pyinstaller --name="ElectricityBilling" --windowed --onefile --add-data "app;app" main.py
```

Or use the provided build script:

```bash
python build_exe.py
```

## License

MIT License
