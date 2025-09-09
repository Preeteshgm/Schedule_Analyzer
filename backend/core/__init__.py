# Package init
# Create this file: core/__init__.py
# This makes the core folder a Python package so imports work

"""
Enhanced XER Processing Core Module
Provides raw XER parsing and database integration for schedule analysis
"""

__version__ = "1.0.0"
__author__ = "Schedule Analysis Team"

# Import main classes for easy access
try:
    from .raw_xer_parser import RawXERParser, parse_xer_file_enhanced
    from .file_processor import FileProcessor, create_file_processor
    from .xer_data_mapper import XERDataMapper, create_xer_data_mapper
    
    __all__ = [
        'RawXERParser',
        'parse_xer_file_enhanced', 
        'FileProcessor',
        'create_file_processor',
        'XERDataMapper',
        'create_xer_data_mapper'
    ]
    
except ImportError as e:
    # If imports fail, at least the package structure works
    print(f"Warning: Some core modules not available: {e}")
    __all__ = []