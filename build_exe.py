#!/usr/bin/env python3
"""
Build script for creating standalone Windows executable using PyInstaller.

Usage:
    python build_exe.py [--clean]
"""

import sys
import os
import shutil
from pathlib import Path


def build_executable(clean: bool = False) -> None:
    """Build the standalone executable."""
    
    # Check for PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        os.system("pip install pyinstaller")
    
    project_root = Path(__file__).parent.absolute()
    output_dir = project_root / "dist"
    build_dir = project_root / "build"
    spec_file = project_root / "electricity_billing.spec"
    
    if clean:
        print("Cleaning previous builds...")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        if build_dir.exists():
            shutil.rmtree(build_dir)
        if spec_file.exists():
            spec_file.unlink()
    
    # Build command
    cmd = f'''pyinstaller --name="ElectricityBilling" \\
        --windowed \\
        --onefile \\
        --add-data "app;app" \\
        --hidden-import=pyside6 \\
        --hidden-import=pandas \\
        --hidden-import=reportlab \\
        --hidden-import=matplotlib \\
        --hidden-import=pydantic \\
        --icon=NONE \\
        --noconfirm \\
        main.py'''
    
    print(f"Building executable...\n{cmd}\n")
    os.system(cmd)
    
    print("\n" + "=" * 60)
    print("Build complete!")
    print(f"Executable location: {output_dir / 'ElectricityBilling.exe'}")
    print("=" * 60)


if __name__ == "__main__":
    clean_build = "--clean" in sys.argv
    build_executable(clean=clean_build)
