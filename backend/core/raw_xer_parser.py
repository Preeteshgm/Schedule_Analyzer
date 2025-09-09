"""
Enhanced Raw XER Parser for Schedule Analysis Web App
Based on direct table extraction approach - no external dependencies
"""

import pandas as pd
import os
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RawXERParser:
    """
    Direct XER file parser that extracts all tables without external dependencies
    Designed for web app integration with comprehensive error handling
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.xer_lines = []
        self.tables = {}
        self.activity_codes = {}
        self.udf_mapping = {}
        
    def parse_file(self) -> Dict[str, pd.DataFrame]:
        """
        Main parsing method - extracts all tables from XER file
        Returns dictionary of DataFrames
        """
        try:
            # Load file
            success = self._load_xer_file()
            if not success:
                return {}
            
            # Extract all tables
            self._extract_all_tables()
            
            # Build activity code mappings
            self._build_activity_code_mappings()
            
            # Build UDF mappings
            self._build_udf_mappings()
            
            # Enhance activity data
            self._enhance_activity_data()
            
            logger.info(f"✅ Successfully parsed XER file: {len(self.tables)} tables extracted")
            return self.tables
            
        except Exception as e:
            logger.error(f"❌ Error parsing XER file: {e}")
            return {}
    
    def _load_xer_file(self) -> bool:
        """Load and validate XER file"""
        try:
            if not os.path.exists(self.file_path):
                logger.error(f"File not found: {self.file_path}")
                return False
            
            file_size = os.path.getsize(self.file_path)
            logger.info(f"📁 Loading XER file: {file_size / 1024 / 1024:.2f} MB")
            
            # Try different encodings
            encodings = ['utf-8', 'latin1', 'cp1252', 'utf-16']
            
            for encoding in encodings:
                try:
                    with open(self.file_path, "r", encoding=encoding, errors="ignore") as file:
                        self.xer_lines = file.readlines()
                    logger.info(f"✅ File loaded with {encoding}: {len(self.xer_lines)} lines")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to load with {encoding}: {e}")
                    continue
            
            logger.error("Failed to load file with any encoding")
            return False
            
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            return False
    
    def _extract_table(self, table_name: str) -> Optional[pd.DataFrame]:
        """
        Extract a specific table from XER lines
        Handles missing columns and malformed data gracefully
        """
        try:
            start_idx = None
            end_idx = None
            
            # Find table boundaries
            for idx, line in enumerate(self.xer_lines):
                if line.startswith(f"%T\t{table_name}"):
                    start_idx = idx + 1
                elif start_idx and line.startswith("%T"):  # Next table starts
                    end_idx = idx
                    break
            
            if start_idx is None:
                return None  # Table not found
            
            end_idx = end_idx or len(self.xer_lines)
            table_lines = self.xer_lines[start_idx:end_idx]
            
            if not table_lines:
                return None
            
            # Extract headers
            header_line = None
            data_start = 0
            
            for i, line in enumerate(table_lines):
                if line.startswith("%F"):
                    header_line = line
                    data_start = i + 1
                    break
            
            if header_line is None:
                logger.warning(f"No headers found for table {table_name}")
                return None
            
            headers = header_line.strip().split("\t")[1:]  # Remove %F
            
            # Extract data rows
            data_rows = []
            for line in table_lines[data_start:]:
                if line.startswith("%R"):
                    row_data = line.strip().split("\t")[1:]  # Remove %R
                    data_rows.append(row_data)
                elif line.startswith("%E"):  # End of table
                    break
            
            if not data_rows:
                return None
            
            # Handle column mismatches
            max_columns = max(len(row) for row in data_rows) if data_rows else 0
            
            # Adjust headers to match data
            if len(headers) < max_columns:
                headers.extend([f"col_{i}" for i in range(len(headers), max_columns)])
            elif len(headers) > max_columns:
                headers = headers[:max_columns]
            
            # Normalize row lengths
            normalized_rows = []
            for row in data_rows:
                # Pad short rows
                while len(row) < len(headers):
                    row.append(None)
                # Trim long rows
                if len(row) > len(headers):
                    row = row[:len(headers)]
                normalized_rows.append(row)
            
            # Create DataFrame
            df = pd.DataFrame(normalized_rows, columns=headers)
            
            # Clean up empty string values
            df = df.replace('', None)
            
            return df
            
        except Exception as e:
            logger.error(f"Error extracting table {table_name}: {e}")
            return None
    
    def _extract_all_tables(self) -> None:
        """Extract all important tables from XER file"""
        
        # Core tables
        core_tables = [
            'PROJECT', 'TASK', 'PROJWBS', 'TASKPRED',
            'CALENDAR', 'RSRC', 'TASKRSRC', 'RSRCRATE'
        ]
        
        # Classification and UDF tables
        classification_tables = [
            'ACTVTYPE', 'ACTVCODE', 'TASKACTV',
            'UDFTYPE', 'UDFVALUE'
        ]
        
        # Additional useful tables
        additional_tables = [
            'ACCOUNT', 'TASKFIN', 'TRSRCFIN',
            'MEMOTYPE', 'TASKMEMO', 'PROJMEMO',
            'NONWORK', 'WORKTIME'
        ]
        
        all_tables = core_tables + classification_tables + additional_tables
        
        logger.info(f"🔍 Extracting {len(all_tables)} table types...")
        
        for table_name in all_tables:
            df = self._extract_table(table_name)
            if df is not None:
                self.tables[table_name] = df
                logger.info(f"  ✅ {table_name}: {len(df):,} records")
            else:
                logger.info(f"  ➖ {table_name}: Not found")
        
        # Find any additional tables we might have missed
        found_tables = set()
        for line in self.xer_lines:
            if line.startswith("%T\t"):
                table_name = line.strip().split("\t")[1]
                found_tables.add(table_name)
        
        missing_tables = found_tables - set(all_tables)
        if missing_tables:
            logger.info(f"📋 Additional tables found: {sorted(missing_tables)}")
            for table_name in sorted(missing_tables):
                df = self._extract_table(table_name)
                if df is not None:
                    self.tables[table_name] = df
                    logger.info(f"  ✅ {table_name}: {len(df):,} records")
    
    def _build_activity_code_mappings(self) -> None:
        """Build activity code mappings from ACTVTYPE, ACTVCODE, TASKACTV tables"""
        try:
            if not all(table in self.tables for table in ['ACTVTYPE', 'ACTVCODE', 'TASKACTV']):
                logger.info("📝 Activity code tables not available")
                return
            
            actvtype_df = self.tables['ACTVTYPE']
            actvcode_df = self.tables['ACTVCODE']
            taskactv_df = self.tables['TASKACTV']
            
            # Build type lookup
            type_lookup = {}
            if 'actv_code_type_id' in actvtype_df.columns and 'actv_code_type' in actvtype_df.columns:
                type_lookup = {
                    str(row["actv_code_type_id"]): row["actv_code_type"] 
                    for _, row in actvtype_df.iterrows()
                    if row["actv_code_type_id"] is not None
                }
            
            # Build code value lookup
            value_lookup = {}
            if 'actv_code_id' in actvcode_df.columns and 'actv_code_name' in actvcode_df.columns:
                value_lookup = {
                    str(row["actv_code_id"]): row["actv_code_name"] 
                    for _, row in actvcode_df.iterrows()
                    if row["actv_code_id"] is not None
                }
            
            # Build task activity code assignments
            for _, row in taskactv_df.iterrows():
                task_id = row.get("task_id")
                type_id = str(row.get("actv_code_type_id")) if row.get("actv_code_type_id") is not None else None
                code_id = str(row.get("actv_code_id")) if row.get("actv_code_id") is not None else None
                
                if not all([task_id, type_id, code_id]):
                    continue
                
                type_name = type_lookup.get(type_id)
                code_value = value_lookup.get(code_id)
                
                if type_name and code_value:
                    if task_id not in self.activity_codes:
                        self.activity_codes[task_id] = {}
                    self.activity_codes[task_id][type_name] = code_value
            
            logger.info(f"📝 Activity codes: {len(self.activity_codes)} activities with codes")
            
        except Exception as e:
            logger.error(f"Error building activity code mappings: {e}")
    
    def _build_udf_mappings(self) -> None:
        """Build UDF (User Defined Field) mappings"""
        try:
            if not all(table in self.tables for table in ['UDFTYPE', 'UDFVALUE']):
                logger.info("📋 UDF tables not available")
                return
            
            udftype_df = self.tables['UDFTYPE']
            udfvalue_df = self.tables['UDFVALUE']
            
            # Build UDF type lookup
            udf_type_lookup = {}
            if 'udf_type_id' in udftype_df.columns and 'udf_type_name' in udftype_df.columns:
                udf_type_lookup = {
                    str(row["udf_type_id"]): row["udf_type_name"] 
                    for _, row in udftype_df.iterrows()
                    if row["udf_type_id"] is not None
                }
            
            # Build UDF value assignments
            for _, row in udfvalue_df.iterrows():
                fk_id = row.get("fk_id")  # This links to task_id for activities
                udf_type_id = str(row.get("udf_type_id")) if row.get("udf_type_id") is not None else None
                udf_text = row.get("udf_text")
                
                if not all([fk_id, udf_type_id]):
                    continue
                
                udf_name = udf_type_lookup.get(udf_type_id)
                if udf_name and udf_text:
                    if fk_id not in self.udf_mapping:
                        self.udf_mapping[fk_id] = {}
                    self.udf_mapping[fk_id][udf_name] = udf_text
            
            logger.info(f"📋 UDFs: {len(self.udf_mapping)} records with UDFs")
            
        except Exception as e:
            logger.error(f"Error building UDF mappings: {e}")
    
    def _enhance_activity_data(self) -> None:
        """Enhance TASK table with activity codes and UDFs"""
        if 'TASK' not in self.tables:
            return
        
        task_df = self.tables['TASK']
        
        # Add activity codes
        if self.activity_codes:
            # Find all unique activity code types
            all_code_types = set()
            for codes in self.activity_codes.values():
                all_code_types.update(codes.keys())
            
            # Add columns for each activity code type
            for code_type in sorted(all_code_types):
                col_name = f"AC_{code_type}"
                task_df[col_name] = task_df['task_id'].map(
                    lambda tid: self.activity_codes.get(tid, {}).get(code_type)
                )
            
            logger.info(f"📝 Added {len(all_code_types)} activity code columns to TASK table")
        
        # Add UDFs
        if self.udf_mapping:
            # Find all unique UDF types
            all_udf_types = set()
            for udfs in self.udf_mapping.values():
                all_udf_types.update(udfs.keys())
            
            # Add columns for each UDF
            for udf_type in sorted(all_udf_types):
                col_name = f"UDF_{udf_type}"
                task_df[col_name] = task_df['task_id'].map(
                    lambda tid: self.udf_mapping.get(tid, {}).get(udf_type)
                )
            
            logger.info(f"📋 Added {len(all_udf_types)} UDF columns to TASK table")
        
        # Update the table in our collection
        self.tables['TASK'] = task_df
    
    def get_processing_summary(self) -> Dict[str, any]:
        """Get summary of processing results"""
        summary = {
            'file_path': self.file_path,
            'file_size_mb': os.path.getsize(self.file_path) / 1024 / 1024 if os.path.exists(self.file_path) else 0,
            'tables_extracted': len(self.tables),
            'activities_with_codes': len(self.activity_codes),
            'activities_with_udfs': len(self.udf_mapping),
            'table_details': {}
        }
        
        for table_name, df in self.tables.items():
            summary['table_details'][table_name] = {
                'records': len(df),
                'columns': len(df.columns)
            }
        
        return summary


def parse_xer_file_enhanced(file_path: str) -> Tuple[bool, str, Dict]:
    """
    Enhanced XER parsing function for web app integration
    Returns: (success, message, data_dict)
    """
    try:
        logger.info(f"🚀 Starting enhanced XER parsing: {file_path}")
        
        # Initialize parser
        parser = RawXERParser(file_path)
        
        # Parse file
        tables = parser.parse_file()
        
        if not tables:
            return False, "Failed to extract any tables from XER file", {}
        
        # Get processing summary
        summary = parser.get_processing_summary()
        
        # Prepare return data
        data_dict = {
            'tables': tables,
            'summary': summary,
            'activity_codes': parser.activity_codes,
            'udf_mapping': parser.udf_mapping
        }
        
        message = f"Successfully parsed XER file: {len(tables)} tables extracted"
        logger.info(f"✅ {message}")
        
        return True, message, data_dict
        
    except Exception as e:
        error_msg = f"Error parsing XER file: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg, {}


# Test function for development
def test_parser(file_path: str):
    """Test the parser with a sample file"""
    success, message, data = parse_xer_file_enhanced(file_path)
    
    if success:
        print(f"✅ SUCCESS: {message}")
        print(f"📊 Summary: {data['summary']}")
        
        # Show sample data
        if 'TASK' in data['tables']:
            task_df = data['tables']['TASK']
            print(f"\n📋 Sample Activities (first 3):")
            cols = ['task_id', 'task_name', 'task_type', 'target_drtn_hr_cnt']
            available_cols = [col for col in cols if col in task_df.columns]
            print(task_df[available_cols].head(3))
            
            # Show activity code columns
            ac_cols = [col for col in task_df.columns if col.startswith('AC_')]
            if ac_cols:
                print(f"\n📝 Activity Code Columns: {ac_cols}")
        
    else:
        print(f"❌ ERROR: {message}")


if __name__ == "__main__":
    # Example usage
    test_file = "/path/to/your/test.xer"
    if os.path.exists(test_file):
        test_parser(test_file)
    else:
        print("Please provide a valid XER file path for testing")