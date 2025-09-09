"""
Enhanced File Processor for Schedule Analysis Web App
Handles file validation, processing, and integration with raw XER parser
"""

import os
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class FileProcessor:
    """
    Enhanced file processor that coordinates file validation,
    XER parsing, and database integration
    """
    
    def __init__(self, upload_folder: str = 'uploads'):
        self.upload_folder = upload_folder
        self.supported_extensions = {'.xer'}
        self.max_file_size = 200 * 1024 * 1024  # 200MB
        
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate uploaded file for processing
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
            
            # Check file extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in self.supported_extensions:
                return False, f"Unsupported file type: {ext}. Only .xer files are supported."
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, "File is empty"
            
            if file_size > self.max_file_size:
                size_mb = file_size / 1024 / 1024
                max_mb = self.max_file_size / 1024 / 1024
                return False, f"File too large: {size_mb:.1f}MB. Maximum allowed: {max_mb}MB"
            
            # Basic file format validation for XER
            if ext == '.xer':
                valid_xer, xer_error = self._validate_xer_format(file_path)
                if not valid_xer:
                    return False, f"Invalid XER format: {xer_error}"
            
            logger.info(f"✅ File validation passed: {file_path} ({file_size / 1024 / 1024:.2f}MB)")
            return True, "File validation successful"
            
        except Exception as e:
            logger.error(f"❌ File validation error: {e}")
            return False, f"File validation error: {str(e)}"
    
    def _validate_xer_format(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate basic XER file format
        
        Args:
            file_path: Path to XER file
            
        Returns:
            Tuple[bool, str]: (is_valid_xer, error_message)
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        # Read first few lines to check XER format
                        lines = [f.readline().strip() for _ in range(10)]
                    
                    # Check for XER header format
                    if not lines:
                        return False, "File appears to be empty"
                    
                    # Look for XER header patterns
                    has_ermhdr = any('ERMHDR' in line for line in lines)
                    has_table_marker = any(line.startswith('%T\t') for line in lines)
                    
                    if has_ermhdr or has_table_marker:
                        logger.info(f"✅ Valid XER format detected (encoding: {encoding})")
                        return True, "Valid XER format"
                    
                except UnicodeDecodeError:
                    continue
            
            return False, "No valid XER format markers found"
            
        except Exception as e:
            return False, f"XER validation error: {str(e)}"
    
    def process_file(self, file_path: str, schedule_id: int, db_models: Dict) -> Tuple[bool, str, Dict]:
        """
        Process uploaded file and integrate with database
        
        Args:
            file_path: Path to the uploaded file
            schedule_id: Database schedule ID
            db_models: Dictionary containing database models
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, processing_stats)
        """
        try:
            logger.info(f"🚀 Starting file processing: {file_path}")
            
            # Step 1: Validate file
            valid, validation_message = self.validate_file(file_path)
            if not valid:
                return False, validation_message, {}
            
            # Step 2: Process based on file type
            _, ext = os.path.splitext(file_path.lower())
            
            if ext == '.xer':
                return self._process_xer_file(file_path, schedule_id, db_models)
            else:
                return False, f"Unsupported file type for processing: {ext}", {}
                
        except Exception as e:
            logger.error(f"❌ File processing error: {e}")
            return False, f"File processing error: {str(e)}", {}
    
    def _process_xer_file(self, file_path: str, schedule_id: int, db_models: Dict) -> Tuple[bool, str, Dict]:
        """
        Process XER file using enhanced raw parser
        
        Args:
            file_path: Path to XER file
            schedule_id: Database schedule ID
            db_models: Dictionary containing database models
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, processing_stats)
        """
        try:
            from .raw_xer_parser import RawXERParser
            from .xer_data_mapper import XERDataMapper
            
            logger.info(f"📋 Processing XER file with enhanced parser...")
            
            # Step 1: Parse XER file
            parser = RawXERParser(file_path)
            tables = parser.parse_file()
            
            if not tables:
                return False, "Failed to extract any data from XER file", {}
            
            # Step 2: Map XER data to database format
            mapper = XERDataMapper(db_models)
            mapping_success, mapping_message, mapped_data = mapper.map_xer_data(
                tables, 
                schedule_id,
                parser.activity_codes,
                parser.udf_mapping
            )
            
            if not mapping_success:
                return False, f"Data mapping failed: {mapping_message}", {}
            
            # Step 3: Save to database
            save_success, save_message, save_stats = mapper.save_to_database(mapped_data)
            
            if not save_success:
                return False, f"Database save failed: {save_message}", {}
            
            # Step 4: Build hierarchy and relationships
            hierarchy_success = mapper.build_hierarchy_and_codes(schedule_id)
            
            # Compile final statistics
            final_stats = {
                'file_size_mb': os.path.getsize(file_path) / 1024 / 1024,
                'tables_extracted': len(tables),
                'parsing_method': 'Enhanced Raw XER Parser',
                **save_stats,
                'hierarchy_built': hierarchy_success,
                'activity_codes_captured': len(parser.activity_codes),
                'udfs_captured': len(parser.udf_mapping),
                'processing_time': datetime.now().isoformat()
            }
            
            message = f"Successfully processed XER file: {save_stats.get('activities_saved', 0)} activities imported"
            logger.info(f"✅ {message}")
            
            return True, message, final_stats
            
        except Exception as e:
            logger.error(f"❌ XER processing error: {e}")
            import traceback
            traceback.print_exc()
            return False, f"XER processing error: {str(e)}", {}
    
    def cleanup_temp_files(self, file_path: str, keep_original: bool = True) -> bool:
        """
        Clean up temporary files after processing
        
        Args:
            file_path: Path to the processed file
            keep_original: Whether to keep the original uploaded file
            
        Returns:
            bool: Success status
        """
        try:
            if not keep_original and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ Cleaned up file: {file_path}")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Dict:
        """
        Get detailed information about an uploaded file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict: File information
        """
        try:
            if not os.path.exists(file_path):
                return {'error': 'File not found'}
            
            stat = os.stat(file_path)
            
            file_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_size_bytes': stat.st_size,
                'file_size_mb': stat.st_size / 1024 / 1024,
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'file_extension': os.path.splitext(file_path)[1].lower(),
                'is_supported': os.path.splitext(file_path)[1].lower() in self.supported_extensions
            }
            
            return file_info
            
        except Exception as e:
            return {'error': f'Error getting file info: {str(e)}'}


def create_file_processor(upload_folder: str = 'uploads') -> FileProcessor:
    """
    Factory function to create a FileProcessor instance
    
    Args:
        upload_folder: Directory for uploaded files
        
    Returns:
        FileProcessor: Configured file processor instance
    """
    # Ensure upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    return FileProcessor(upload_folder)


# Utility functions for file operations
def secure_filename(filename: str) -> str:
    """
    Generate a secure filename for file uploads
    
    Args:
        filename: Original filename
        
    Returns:
        str: Secure filename
    """
    import re
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Replace unsafe characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}{ext}"


def generate_unique_filename(original_filename: str, upload_folder: str) -> str:
    """
    Generate a unique filename to avoid conflicts
    
    Args:
        original_filename: Original uploaded filename
        upload_folder: Directory where file will be saved
        
    Returns:
        str: Unique filename
    """
    timestamp = int(datetime.now().timestamp())
    secure_name = secure_filename(original_filename)
    name, ext = os.path.splitext(secure_name)
    
    unique_filename = f"{timestamp}_{name}{ext}"
    
    # Ensure it doesn't exist
    counter = 1
    while os.path.exists(os.path.join(upload_folder, unique_filename)):
        unique_filename = f"{timestamp}_{name}_{counter}{ext}"
        counter += 1
    
    return unique_filename


# Example usage and testing
if __name__ == "__main__":
    # Test the file processor
    processor = create_file_processor()
    
    # Test file validation
    test_file = "test.xer"
    if os.path.exists(test_file):
        valid, message = processor.validate_file(test_file)
        print(f"Validation: {valid} - {message}")
        
        if valid:
            file_info = processor.get_file_info(test_file)
            print(f"File info: {file_info}")
    else:
        print("No test file found - create a test.xer file to test validation")