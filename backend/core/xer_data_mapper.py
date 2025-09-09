"""
XER Data Mapper for Schedule Analysis Web App
Maps raw XER data to database models and handles bulk database operations
"""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class XERDataMapper:
    """
    Maps raw XER data extracted by RawXERParser to database models
    Handles data transformation, validation, and bulk database operations
    """
    
    def __init__(self, db_models: Dict):
        """
        Initialize mapper with database models
        
        Args:
            db_models: Dictionary containing database models and db instance
                      Expected keys: 'db', 'Activity', 'WBS', 'Relationship', 'Schedule'
        """
        self.db = db_models['db']
        self.Activity = db_models['Activity']
        self.WBS = db_models['WBS']
        self.Relationship = db_models['Relationship']
        self.Schedule = db_models['Schedule']
        
        self.mapped_data = {}
        self.processing_stats = {}
    
    def map_xer_data(self, tables: Dict[str, pd.DataFrame], schedule_id: int, 
                    activity_codes: Dict, udf_mapping: Dict) -> Tuple[bool, str, Dict]:
        """
        Map extracted XER tables to database format
        
        Args:
            tables: Dictionary of extracted XER tables
            schedule_id: Target schedule ID
            activity_codes: Activity code assignments
            udf_mapping: UDF value assignments
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, mapped_data)
        """
        try:
            logger.info(f"🗺️ Mapping XER data for schedule {schedule_id}")
            
            self.mapped_data = {
                'schedule_id': schedule_id,
                'project_data': {},
                'wbs_items': [],
                'activities': [],
                'relationships': [],
                'activity_codes': activity_codes,
                'udf_mapping': udf_mapping
            }
            
            # Step 1: Map project data
            project_success = self._map_project_data(tables)
            
            # Step 2: Map WBS structure
            wbs_success = self._map_wbs_data(tables, schedule_id)
            
            # Step 3: Map activities with enhanced data
            activities_success = self._map_activities_data(tables, schedule_id, activity_codes, udf_mapping)
            
            # Step 4: Map relationships
            relationships_success = self._map_relationships_data(tables, schedule_id)
            
            if not all([project_success, wbs_success, activities_success, relationships_success]):
                return False, "Failed to map some XER data components", {}
            
            message = f"Successfully mapped XER data: {len(self.mapped_data['activities'])} activities, {len(self.mapped_data['wbs_items'])} WBS items"
            logger.info(f"✅ {message}")
            
            return True, message, self.mapped_data
            
        except Exception as e:
            logger.error(f"❌ XER data mapping error: {e}")
            return False, f"Data mapping error: {str(e)}", {}
    
    def _map_project_data(self, tables: Dict[str, pd.DataFrame]) -> bool:
        """Map PROJECT table data"""
        try:
            if 'PROJECT' not in tables or len(tables['PROJECT']) == 0:
                logger.warning("No PROJECT data found")
                return True  # Not critical
            
            project_df = tables['PROJECT']
            project_row = project_df.iloc[0]  # Take first project
            
            self.mapped_data['project_data'] = {
                'proj_id': str(project_row.get('proj_id', '')),
                'proj_short_name': str(project_row.get('proj_short_name', 'Imported Project')),
                'plan_start_date': self._parse_date(project_row.get('plan_start_date')),
                'plan_end_date': self._parse_date(project_row.get('plan_end_date')),
                'scd_end_date': self._parse_date(project_row.get('scd_end_date'))
            }
            
            logger.info(f"✅ Mapped project data: {self.mapped_data['project_data']['proj_short_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Error mapping project data: {e}")
            return False
    
    def _map_wbs_data(self, tables: Dict[str, pd.DataFrame], schedule_id: int) -> bool:
        """Map PROJWBS table data"""
        try:
            if 'PROJWBS' not in tables or len(tables['PROJWBS']) == 0:
                logger.warning("No WBS data found")
                return True  # Not critical, can have activities without WBS
            
            projwbs_df = tables['PROJWBS']
            logger.info(f"📁 Mapping {len(projwbs_df)} WBS items...")
            
            for _, row in projwbs_df.iterrows():
                try:
                    wbs_id = row.get('wbs_id')
                    if not wbs_id:
                        continue
                    
                    parent_wbs_id = row.get('parent_wbs_id')
                    proj_id = row.get('proj_id')
                    
                    # Detect project root WBS
                    is_root = (pd.isna(parent_wbs_id) or str(parent_wbs_id) == str(proj_id))
                    
                    wbs_data = {
                        'schedule_id': schedule_id,
                        'wbs_id': str(wbs_id),
                        'wbs_name': str(row.get('wbs_name', f'WBS {wbs_id}'))[:500],
                        'wbs_short_name': str(row.get('wbs_short_name', ''))[:100],
                        'parent_wbs_id': str(parent_wbs_id) if not is_root and pd.notna(parent_wbs_id) else None,
                        'proj_id': str(proj_id) if pd.notna(proj_id) else '',
                        'proj_node_flag': 'Y' if is_root else 'N',
                        'level': 0,  # Will be calculated during hierarchy building
                        'full_path': ''  # Will be built during hierarchy building
                    }
                    
                    self.mapped_data['wbs_items'].append(wbs_data)
                    
                except Exception as e:
                    logger.warning(f"Error mapping WBS item: {e}")
                    continue
            
            logger.info(f"✅ Mapped {len(self.mapped_data['wbs_items'])} WBS items")
            return True
            
        except Exception as e:
            logger.error(f"Error mapping WBS data: {e}")
            return False
    
    def _map_activities_data(self, tables: Dict[str, pd.DataFrame], schedule_id: int, 
                           activity_codes: Dict, udf_mapping: Dict) -> bool:
        """Map TASK table data with enhanced fields"""
        try:
            if 'TASK' not in tables or len(tables['TASK']) == 0:
                logger.warning("No activities data found")
                return False  # Critical for schedule analysis
            
            task_df = tables['TASK']
            logger.info(f"📋 Mapping {len(task_df)} activities...")
            
            for _, row in task_df.iterrows():
                try:
                    task_id = row.get('task_id')
                    if not task_id:
                        continue
                    
                    # Duration conversions (hours to days)
                    duration_hours = float(row.get('target_drtn_hr_cnt', 0) or 0)
                    duration_days = duration_hours / 8 if duration_hours > 0 else 0
                    
                    remaining_hours = float(row.get('remain_drtn_hr_cnt', 0) or 0)
                    remaining_days = remaining_hours / 8 if remaining_hours > 0 else 0
                    
                    # Float calculations
                    total_float_hours = float(row.get('total_float_hr_cnt', 0) or 0)
                    total_float_days = total_float_hours / 8
                    
                    free_float_hours = float(row.get('free_float_hr_cnt', 0) or 0)
                    free_float_days = free_float_hours / 8
                    
                    # Date fields
                    dates = {
                        'early_start_date': self._parse_date(row.get('early_start_date')),
                        'early_end_date': self._parse_date(row.get('early_end_date')),
                        'late_start_date': self._parse_date(row.get('late_start_date')),
                        'late_end_date': self._parse_date(row.get('late_end_date')),
                        'actual_start_date': self._parse_date(row.get('act_start_date')),
                        'actual_end_date': self._parse_date(row.get('act_end_date')),
                        'target_start_date': self._parse_date(row.get('target_start_date')),
                        'target_end_date': self._parse_date(row.get('target_end_date'))
                    }
                    
                    # Progress
                    progress_pct = float(row.get('phys_complete_pct', 0) or 0)
                    
                    # Get enhanced data for this activity
                    task_activity_codes = activity_codes.get(task_id, {})
                    task_udfs = udf_mapping.get(task_id, {})
                    
                    # Create activity data structure
                    activity_data = {
                        'schedule_id': schedule_id,
                        'task_id': str(task_id),
                        'task_name': str(row.get('task_name', f'Activity {task_id}'))[:500],
                        'task_code': str(row.get('task_code', ''))[:100],
                        'wbs_id': str(row.get('wbs_id', '')),
                        'proj_id': str(row.get('proj_id', '')),
                        'duration_days': duration_days,
                        'remaining_duration': remaining_days,
                        'original_duration': duration_days,  # Store original for comparison
                        'total_float_days': total_float_days,
                        'free_float_days': free_float_days,
                        'progress_pct': progress_pct,
                        'percent_complete': progress_pct,  # Alternative field
                        'task_type': str(row.get('task_type', ''))[:50],
                        'status_code': str(row.get('status_code', ''))[:50],
                        'hierarchy_path': '',  # Will be built during hierarchy building
                        
                        # Enhanced data fields
                        'activity_codes': task_activity_codes if task_activity_codes else None,
                        'udf_values': task_udfs if task_udfs else None,
                        
                        # Date fields
                        **dates,
                        
                        # Additional fields from XER
                        'resource_names': self._extract_resource_names(row, task_id, tables),
                        'constraint_type': str(row.get('cstr_type', ''))[:50] if row.get('cstr_type') else None,
                        'constraint_date': self._parse_date(row.get('cstr_date'))
                    }
                    
                    self.mapped_data['activities'].append(activity_data)
                    
                except Exception as e:
                    logger.warning(f"Error mapping activity {row.get('task_id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"✅ Mapped {len(self.mapped_data['activities'])} activities")
            return True
            
        except Exception as e:
            logger.error(f"Error mapping activities data: {e}")
            return False
    
    def _map_relationships_data(self, tables: Dict[str, pd.DataFrame], schedule_id: int) -> bool:
        """Map TASKPRED table data"""
        try:
            if 'TASKPRED' not in tables or len(tables['TASKPRED']) == 0:
                logger.warning("No relationships data found")
                return True  # Not critical, can have activities without relationships
            
            taskpred_df = tables['TASKPRED']
            logger.info(f"🔗 Mapping {len(taskpred_df)} relationships...")
            
            for _, row in taskpred_df.iterrows():
                try:
                    pred_task_id = row.get('pred_task_id')
                    succ_task_id = row.get('task_id')
                    
                    if not pred_task_id or not succ_task_id:
                        continue
                    
                    # Convert relationship type
                    pred_type = row.get('pred_type', 'PR_FS')
                    if pred_type.startswith('PR_'):
                        pred_type = pred_type[3:]  # Remove 'PR_' prefix
                    
                    # Convert lag (hours to days)
                    lag_hours = float(row.get('lag_hr_cnt', 0) or 0)
                    lag_days = lag_hours / 8
                    
                    relationship_data = {
                        'schedule_id': schedule_id,
                        'pred_task_id': str(pred_task_id),
                        'succ_task_id': str(succ_task_id),
                        'pred_type': pred_type,
                        'lag_days': lag_days
                    }
                    
                    self.mapped_data['relationships'].append(relationship_data)
                    
                except Exception as e:
                    logger.warning(f"Error mapping relationship: {e}")
                    continue
            
            logger.info(f"✅ Mapped {len(self.mapped_data['relationships'])} relationships")
            return True
            
        except Exception as e:
            logger.error(f"Error mapping relationships data: {e}")
            return False
    
    def _parse_date(self, date_value) -> Optional[datetime]:
        """Parse date value from XER data"""
        if pd.isna(date_value) or date_value is None:
            return None
        
        try:
            return pd.to_datetime(date_value, errors='coerce')
        except:
            return None
    
    def _extract_resource_names(self, activity_row, task_id: str, tables: Dict) -> Optional[str]:
        """Extract resource names for an activity from TASKRSRC table"""
        try:
            if 'TASKRSRC' not in tables or 'RSRC' not in tables:
                return None
            
            taskrsrc_df = tables['TASKRSRC']
            rsrc_df = tables['RSRC']
            
            # Get resource assignments for this activity
            activity_resources = taskrsrc_df[taskrsrc_df['task_id'] == task_id]
            
            if len(activity_resources) == 0:
                return None
            
            # Get resource names
            resource_ids = activity_resources['rsrc_id'].tolist()
            resource_names = []
            
            for rsrc_id in resource_ids:
                rsrc_info = rsrc_df[rsrc_df['rsrc_id'] == rsrc_id]
                if len(rsrc_info) > 0:
                    rsrc_name = rsrc_info.iloc[0].get('rsrc_name', f'Resource {rsrc_id}')
                    resource_names.append(str(rsrc_name))
            
            return ', '.join(resource_names) if resource_names else None
            
        except Exception as e:
            logger.debug(f"Could not extract resources for {task_id}: {e}")
            return None
    
    def save_to_database(self, mapped_data: Dict) -> Tuple[bool, str, Dict]:
        """Save mapped data to database using bulk operations"""
        try:
            logger.info("💾 Saving mapped data to database...")
            
            schedule_id = mapped_data['schedule_id']
            stats = {
                'wbs_items_saved': 0,
                'activities_saved': 0,
                'relationships_saved': 0
            }
            
            # Step 1: Update schedule with project data
            self._update_schedule_info(schedule_id, mapped_data['project_data'])
            
            # Step 2: Save WBS items
            if mapped_data['wbs_items']:
                stats['wbs_items_saved'] = self._save_wbs_items(mapped_data['wbs_items'])
            
            # Step 3: Save activities
            if mapped_data['activities']:
                stats['activities_saved'] = self._save_activities(mapped_data['activities'])
            
            # Step 4: Save relationships
            if mapped_data['relationships']:
                stats['relationships_saved'] = self._save_relationships(mapped_data['relationships'])
            
            # Step 5: Update schedule totals
            schedule = self.Schedule.query.get(schedule_id)
            if schedule:
                schedule.total_activities = stats['activities_saved']
                schedule.total_relationships = stats['relationships_saved']
                schedule.total_wbs_items = stats['wbs_items_saved']
                schedule.status = 'parsed'
                self.db.session.commit()
            
            message = f"Database save completed: {stats['activities_saved']} activities, {stats['wbs_items_saved']} WBS items, {stats['relationships_saved']} relationships"
            logger.info(f"✅ {message}")
            
            return True, message, stats
            
        except Exception as e:
            logger.error(f"❌ Database save error: {e}")
            self.db.session.rollback()
            return False, f"Database save error: {str(e)}", {}
    
    def _update_schedule_info(self, schedule_id: int, project_data: Dict) -> None:
        """Update schedule with project information"""
        try:
            schedule = self.Schedule.query.get(schedule_id)
            if schedule and project_data:
                schedule.proj_id = project_data.get('proj_id', '')
                schedule.proj_short_name = project_data.get('proj_short_name', schedule.name)
                
                if project_data.get('plan_start_date'):
                    schedule.project_start_date = project_data['plan_start_date']
                if project_data.get('plan_end_date'):
                    schedule.project_finish_date = project_data['plan_end_date']
                    
                self.db.session.commit()
                logger.info(f"✅ Updated schedule info: {schedule.proj_short_name}")
                
        except Exception as e:
            logger.warning(f"Error updating schedule info: {e}")
    
    def _save_wbs_items(self, wbs_data: List[Dict]) -> int:
        """Save WBS items using bulk operations"""
        try:
            logger.info(f"💾 Saving {len(wbs_data)} WBS items...")
            
            wbs_objects = []
            for wbs_item in wbs_data:
                wbs_obj = self.WBS(**wbs_item)
                wbs_objects.append(wbs_obj)
            
            # Bulk save in batches
            batch_size = 1000
            saved_count = 0
            
            for i in range(0, len(wbs_objects), batch_size):
                batch = wbs_objects[i:i+batch_size]
                self.db.session.add_all(batch)
                self.db.session.commit()
                saved_count += len(batch)
                logger.info(f"  💾 Saved WBS batch: {len(batch)} items")
            
            logger.info(f"✅ Saved {saved_count} WBS items")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving WBS items: {e}")
            self.db.session.rollback()
            return 0
    
    def _save_activities(self, activities_data: List[Dict]) -> int:
        """Save activities using bulk operations"""
        try:
            logger.info(f"💾 Saving {len(activities_data)} activities...")
            
            activity_objects = []
            for activity_item in activities_data:
                activity_obj = self.Activity(**activity_item)
                activity_objects.append(activity_obj)
            
            # Bulk save in batches
            batch_size = 1000
            saved_count = 0
            
            for i in range(0, len(activity_objects), batch_size):
                batch = activity_objects[i:i+batch_size]
                self.db.session.add_all(batch)
                self.db.session.commit()
                saved_count += len(batch)
                logger.info(f"  💾 Saved activity batch: {len(batch)} activities")
            
            logger.info(f"✅ Saved {saved_count} activities")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving activities: {e}")
            self.db.session.rollback()
            return 0
    
    def _save_relationships(self, relationships_data: List[Dict]) -> int:
        """Save relationships using bulk operations"""
        try:
            logger.info(f"💾 Saving {len(relationships_data)} relationships...")
            
            relationship_objects = []
            for rel_item in relationships_data:
                rel_obj = self.Relationship(**rel_item)
                relationship_objects.append(rel_obj)
            
            # Bulk save in batches
            batch_size = 2000
            saved_count = 0
            
            for i in range(0, len(relationship_objects), batch_size):
                batch = relationship_objects[i:i+batch_size]
                self.db.session.add_all(batch)
                self.db.session.commit()
                saved_count += len(batch)
                logger.info(f"  💾 Saved relationship batch: {len(batch)} relationships")
            
            logger.info(f"✅ Saved {saved_count} relationships")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving relationships: {e}")
            self.db.session.rollback()
            return 0
    
    def build_hierarchy_and_codes(self, schedule_id: int) -> bool:
        """Build hierarchy paths and generate codes"""
        try:
            logger.info("🌳 Building hierarchy and generating codes...")
            
            # Step 1: Generate WBS hierarchy codes
            wbs_success = self._generate_wbs_codes(schedule_id)
            
            # Step 2: Generate activity codes based on WBS
            activity_success = self._generate_activity_codes(schedule_id)
            
            # Step 3: Build hierarchy paths
            hierarchy_success = self._build_hierarchy_paths(schedule_id)
            
            self.db.session.commit()
            
            success = all([wbs_success, activity_success, hierarchy_success])
            if success:
                logger.info("✅ Hierarchy and codes built successfully")
            else:
                logger.warning("⚠️ Some hierarchy building steps failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error building hierarchy: {e}")
            return False
    
    def _generate_wbs_codes(self, schedule_id: int) -> bool:
        """Generate hierarchical WBS codes (1.0, 1.1, 1.1.1, etc.)"""
        try:
            wbs_items = self.WBS.query.filter_by(schedule_id=schedule_id).all()
            
            if not wbs_items:
                return True
            
            # Create WBS map
            wbs_map = {wbs.wbs_id: wbs for wbs in wbs_items}
            
            # Find root WBS items
            root_wbs = [wbs for wbs in wbs_items if wbs.proj_node_flag == 'Y' or not wbs.parent_wbs_id]
            root_wbs.sort(key=lambda w: w.wbs_name or '')
            
            # Assign codes to root items
            for index, wbs in enumerate(root_wbs):
                wbs_code = f"{index + 1}.0"
                wbs.wbs_code = wbs_code
                wbs.sort_order = index + 1
                wbs.level = 0
                
                # Recursively assign codes to children
                self._assign_child_wbs_codes(wbs, wbs_code, wbs_map, wbs_items)
            
            logger.info(f"✅ Generated WBS codes for {len(wbs_items)} items")
            return True
            
        except Exception as e:
            logger.error(f"Error generating WBS codes: {e}")
            return False
    
    def _assign_child_wbs_codes(self, parent_wbs, parent_code: str, wbs_map: Dict, wbs_items: List):
        """Recursively assign WBS codes to children"""
        try:
            # Find children
            children = [wbs for wbs in wbs_items if wbs.parent_wbs_id == parent_wbs.wbs_id]
            children.sort(key=lambda w: w.wbs_name or '')
            
            for index, child in enumerate(children):
                # Generate child code
                if parent_code.endswith('.0'):
                    child_code = f"{parent_code[:-2]}.{index + 1}"
                else:
                    child_code = f"{parent_code}.{index + 1}"
                
                child.wbs_code = child_code
                child.sort_order = index + 1
                child.level = (parent_wbs.level or 0) + 1
                
                # Recursively assign to grandchildren
                self._assign_child_wbs_codes(child, child_code, wbs_map, wbs_items)
                
        except Exception as e:
            logger.warning(f"Error assigning child WBS codes: {e}")
    
    def _generate_activity_codes(self, schedule_id: int) -> bool:
        """Generate activity codes based on WBS hierarchy"""
        try:
            activities = self.Activity.query.filter_by(schedule_id=schedule_id).all()
            wbs_items = self.WBS.query.filter_by(schedule_id=schedule_id).all()
            
            # Create WBS code lookup
            wbs_code_map = {wbs.wbs_id: wbs.wbs_code for wbs in wbs_items if wbs.wbs_code}
            
            # Group activities by WBS
            activities_by_wbs = {}
            for activity in activities:
                wbs_id = activity.wbs_id
                if wbs_id not in activities_by_wbs:
                    activities_by_wbs[wbs_id] = []
                activities_by_wbs[wbs_id].append(activity)
            
            # Generate activity codes
            for wbs_id, wbs_activities in activities_by_wbs.items():
                wbs_code = wbs_code_map.get(wbs_id)
                if not wbs_code:
                    continue
                
                # Sort activities
                wbs_activities.sort(key=lambda a: (
                    a.early_start_date or datetime(1900, 1, 1),
                    a.task_id
                ))
                
                # Assign codes
                for index, activity in enumerate(wbs_activities):
                    activity_code = f"{wbs_code}.{index + 1}"
                    activity.activity_code = activity_code
                    activity.wbs_code = wbs_code
                    activity.sort_order = index + 1
            
            logger.info(f"✅ Generated activity codes for {len(activities)} activities")
            return True
            
        except Exception as e:
            logger.error(f"Error generating activity codes: {e}")
            return False
    
    def _build_hierarchy_paths(self, schedule_id: int) -> bool:
        """Build hierarchy paths with codes"""
        try:
            wbs_items = self.WBS.query.filter_by(schedule_id=schedule_id).all()
            activities = self.Activity.query.filter_by(schedule_id=schedule_id).all()
            
            # Create WBS lookup
            wbs_map = {wbs.wbs_id: wbs for wbs in wbs_items}
            
            def get_wbs_path(wbs_id: str) -> str:
                """Get WBS path with codes"""
                path_parts = []
                current_wbs_id = wbs_id
                visited = set()
                
                while current_wbs_id and current_wbs_id in wbs_map:
                    if current_wbs_id in visited:
                        break
                    
                    visited.add(current_wbs_id)
                    wbs = wbs_map[current_wbs_id]
                    
                    if wbs.wbs_code:
                        path_parts.append(f"{wbs.wbs_code} {wbs.wbs_name}")
                    else:
                        path_parts.append(wbs.wbs_name or 'Unnamed WBS')
                    
                    current_wbs_id = wbs.parent_wbs_id
                
                return " > ".join(reversed(path_parts))
            
            # Update WBS full paths
            for wbs in wbs_items:
                wbs.full_path = get_wbs_path(wbs.wbs_id)
            
            # Update activity hierarchy paths
            for activity in activities:
                if activity.wbs_id and activity.wbs_id in wbs_map:
                    wbs_path = get_wbs_path(activity.wbs_id)
                    activity_code = activity.activity_code or activity.task_id
                    activity.hierarchy_path = f"{wbs_path} > {activity_code} {activity.task_name}"
                else:
                    activity_code = activity.activity_code or activity.task_id
                    activity.hierarchy_path = f"Unassigned > {activity_code} {activity.task_name}"
            
            logger.info(f"✅ Built hierarchy paths for {len(wbs_items)} WBS and {len(activities)} activities")
            return True
            
        except Exception as e:
            logger.error(f"Error building hierarchy paths: {e}")
            return False


# Utility functions
def create_xer_data_mapper(db_models: Dict) -> XERDataMapper:
    """
    Factory function to create XERDataMapper instance
    
    Args:
        db_models: Dictionary containing database models
        
    Returns:
        XERDataMapper: Configured mapper instance
    """
    return XERDataMapper(db_models)


def validate_db_models(db_models: Dict) -> bool:
    """
    Validate that all required database models are provided
    
    Args:
        db_models: Dictionary containing database models
        
    Returns:
        bool: True if all required models are present
    """
    required_keys = ['db', 'Activity', 'WBS', 'Relationship', 'Schedule']
    
    for key in required_keys:
        if key not in db_models:
            logger.error(f"Missing required database model: {key}")
            return False
    
    return True


# Example usage and testing
if __name__ == "__main__":
    # Example of how to use the mapper
    print("XER Data Mapper - Ready for integration")
    print("Use create_xer_data_mapper() to create an instance")