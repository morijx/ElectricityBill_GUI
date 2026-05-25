"""CSV data importer service."""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ColumnMapping:
    """Mapping for CSV columns."""
    
    timestamp_col: Optional[str] = None
    grid_import_col: Optional[str] = None
    grid_export_col: Optional[str] = None
    solar_production_col: Optional[str] = None
    battery_charge_col: Optional[str] = None
    battery_discharge_col: Optional[str] = None
    consumption_col: Optional[str] = None
    
    # Apartment meter columns (meter_id -> column_name)
    apartment_columns: dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of CSV import operation."""
    
    success: bool
    file_path: str
    row_count: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    interval_minutes: int = 15
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    # Imported data
    data: Optional[pd.DataFrame] = None
    
    # Detected columns
    detected_columns: list[str] = field(default_factory=list)
    suggested_mapping: Optional[ColumnMapping] = None


class CSVImporter:
    """Service for importing energy data from CSV files.
    
    Supports various CSV formats with configurable column mapping.
    Handles validation, missing data, and interval detection.
    """
    
    # Common column name patterns
    TIMESTAMP_PATTERNS = ['timestamp', 'time', 'date', 'datetime', 'zeitstempel']
    GRID_IMPORT_PATTERNS = ['grid_import', 'import', 'bezug', 'netzbezug']
    GRID_EXPORT_PATTERNS = ['grid_export', 'export', 'einspeisung', 'netzeinspeisung']
    SOLAR_PATTERNS = ['solar', 'pv', 'production', 'produktion', 'ertrag']
    BATTERY_CHARGE_PATTERNS = ['battery_charge', 'bat_charge', 'ladung']
    BATTERY_DISCHARGE_PATTERNS = ['battery_discharge', 'bat_discharge', 'entladung']
    CONSUMPTION_PATTERNS = ['consumption', 'verbrauch', 'load', 'last']
    
    def __init__(self) -> None:
        """Initialize the CSV importer."""
        self.current_mapping = ColumnMapping()
    
    def detect_column_type(self, column_name: str) -> str:
        """Detect what type of data a column contains based on name."""
        col_lower = column_name.lower().replace(' ', '_').replace('-', '_')
        
        for pattern in self.TIMESTAMP_PATTERNS:
            if pattern in col_lower:
                return 'timestamp'
        
        for pattern in self.GRID_IMPORT_PATTERNS:
            if pattern in col_lower:
                return 'grid_import'
        
        for pattern in self.GRID_EXPORT_PATTERNS:
            if pattern in col_lower:
                return 'grid_export'
        
        for pattern in self.SOLAR_PATTERNS:
            if pattern in col_lower:
                return 'solar_production'
        
        for pattern in self.BATTERY_CHARGE_PATTERNS:
            if pattern in col_lower:
                return 'battery_charge'
        
        for pattern in self.BATTERY_DISCHARGE_PATTERNS:
            if pattern in col_lower:
                return 'battery_discharge'
        
        for pattern in self.CONSUMPTION_PATTERNS:
            if pattern in col_lower:
                return 'consumption'
        
        return 'unknown'
    
    def suggest_mapping(self, df: pd.DataFrame) -> ColumnMapping:
        """Suggest column mappings based on column names."""
        mapping = ColumnMapping()
        
        for col in df.columns:
            col_type = self.detect_column_type(col)
            
            if col_type == 'timestamp' and mapping.timestamp_col is None:
                mapping.timestamp_col = col
            elif col_type == 'grid_import' and mapping.grid_import_col is None:
                mapping.grid_import_col = col
            elif col_type == 'grid_export' and mapping.grid_export_col is None:
                mapping.grid_export_col = col
            elif col_type == 'solar_production' and mapping.solar_production_col is None:
                mapping.solar_production_col = col
            elif col_type == 'battery_charge' and mapping.battery_charge_col is None:
                mapping.battery_charge_col = col
            elif col_type == 'battery_discharge' and mapping.battery_discharge_col is None:
                mapping.battery_discharge_col = col
            elif col_type == 'consumption' and mapping.consumption_col is None:
                mapping.consumption_col = col
        
        return mapping
    
    def validate_timestamps(self, df: pd.DataFrame, 
                           timestamp_col: str) -> tuple[bool, list[str]]:
        """Validate timestamp column."""
        errors = []
        
        try:
            # Try to parse timestamps
            pd.to_datetime(df[timestamp_col])
        except Exception as e:
            errors.append(f"Invalid timestamp format: {str(e)}")
            return False, errors
        
        # Check for duplicates
        if df[timestamp_col].duplicated().any():
            errors.append("Duplicate timestamps detected")
        
        # Check for gaps
        timestamps = pd.to_datetime(df[timestamp_col]).sort_values()
        if len(timestamps) > 1:
            diffs = timestamps.diff()[1:]
            median_diff = diffs.median()
            
            # Flag large gaps (more than 2x median interval)
            large_gaps = (diffs > median_diff * 2).sum()
            if large_gaps > 0:
                pass  # Could add warning but not error
        
        return len(errors) == 0, errors
    
    def detect_interval(self, df: pd.DataFrame, 
                       timestamp_col: str) -> int:
        """Detect the data interval in minutes."""
        if len(df) < 2:
            return 15  # Default
        
        timestamps = pd.to_datetime(df[timestamp_col]).sort_values()
        diffs = timestamps.diff()[1:]
        median_diff = diffs.median()
        
        return int(median_diff.total_seconds() / 60)
    
    def handle_missing_data(self, df: pd.DataFrame,
                           numeric_columns: list[str],
                           method: str = 'interpolate') -> pd.DataFrame:
        """Handle missing data in numeric columns."""
        df_copy = df.copy()
        
        for col in numeric_columns:
            if col in df_copy.columns:
                if method == 'interpolate':
                    df_copy[col] = df_copy[col].interpolate(method='linear')
                elif method == 'forward_fill':
                    df_copy[col] = df_copy[col].ffill()
                elif method == 'zero':
                    df_copy[col] = df_copy[col].fillna(0)
        
        return df_copy
    
    def import_file(self, file_path: str | Path,
                   mapping: Optional[ColumnMapping] = None) -> ImportResult:
        """Import a CSV file with energy data.
        
        Args:
            file_path: Path to the CSV file
            mapping: Optional column mapping (auto-detected if not provided)
            
        Returns:
            ImportResult with imported data and metadata
        """
        path = Path(file_path)
        result = ImportResult(success=False, file_path=str(path))
        
        if not path.exists():
            result.errors.append(f"File not found: {path}")
            return result
        
        try:
            # Read CSV
            df = pd.read_csv(path)
            result.row_count = len(df)
            result.detected_columns = list(df.columns)
            
            # Auto-detect mapping if not provided
            if mapping is None:
                mapping = self.suggest_mapping(df)
            result.suggested_mapping = mapping
            
            # Validate timestamp
            if mapping.timestamp_col is None:
                result.errors.append("No timestamp column identified")
                return result
            
            valid, errors = self.validate_timestamps(df, mapping.timestamp_col)
            if not valid:
                result.errors.extend(errors)
                return result
            
            # Detect interval
            result.interval_minutes = self.detect_interval(df, mapping.timestamp_col)
            
            # Parse timestamps
            df[mapping.timestamp_col] = pd.to_datetime(df[mapping.timestamp_col])
            result.start_date = df[mapping.timestamp_col].min()
            result.end_date = df[mapping.timestamp_col].max()
            
            # Handle missing data in numeric columns
            numeric_cols = [
                mapping.grid_import_col,
                mapping.grid_export_col,
                mapping.solar_production_col,
                mapping.battery_charge_col,
                mapping.battery_discharge_col,
                mapping.consumption_col,
            ] + list(mapping.apartment_columns.values())
            
            numeric_cols = [c for c in numeric_cols if c is not None]
            df = self.handle_missing_data(df, numeric_cols)
            
            result.data = df
            result.success = True
            
        except Exception as e:
            result.errors.append(f"Import error: {str(e)}")
        
        return result
    
    def create_energy_dataframe(self, 
                                timestamp_col: pd.Series,
                                grid_import: pd.Series = None,
                                grid_export: pd.Series = None,
                                solar: pd.Series = None,
                                battery_charge: pd.Series = None,
                                battery_discharge: pd.Series = None,
                                apartments: dict[str, pd.Series] = None) -> pd.DataFrame:
        """Create a standardized energy data DataFrame."""
        data = {'timestamp': timestamp_col}
        
        if grid_import is not None:
            data['grid_import'] = grid_import.fillna(0)
        else:
            data['grid_import'] = 0
        
        if grid_export is not None:
            data['grid_export'] = grid_export.fillna(0)
        else:
            data['grid_export'] = 0
        
        if solar is not None:
            data['solar_production'] = solar.fillna(0)
        else:
            data['solar_production'] = 0
        
        if battery_charge is not None:
            data['battery_charge'] = battery_charge.fillna(0)
        
        if battery_discharge is not None:
            data['battery_discharge'] = battery_discharge.fillna(0)
        
        if apartments:
            for apt_id, series in apartments.items():
                data[f'apartment_{apt_id}'] = series.fillna(0)
        
        return pd.DataFrame(data)
