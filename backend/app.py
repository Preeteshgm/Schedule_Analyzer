import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config import Config

import pandas as pd
from anytree import Node, RenderTree

import pandas as pd
from datetime import datetime as dt
import tempfile

from core.file_processor import create_file_processor
from core.xer_data_mapper import create_xer_data_mapper, validate_db_models

# Initialize extensions
db = SQLAlchemy()

# File upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xer'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 50MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define models inline to avoid circular imports
class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    status = db.Column(db.String(50), default='active')
    
    # Relationship to schedules
    schedules = db.relationship("Schedule", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_date': self.created_date.isoformat(),
            'created_by': self.created_by,
            'status': self.status,
            'schedule_count': len(self.schedules) if self.schedules else 0
        }

class Schedule(db.Model):
    __tablename__ = 'schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    file_name = db.Column(db.String(255))  # Original XER filename
    file_size = db.Column(db.Integer)      # File size in bytes
    total_activities = db.Column(db.Integer, default=0)
    total_relationships = db.Column(db.Integer, default=0)
    total_wbs_items = db.Column(db.Integer, default=0)  # NEW: Track WBS count
    project_start_date = db.Column(db.DateTime)
    project_finish_date = db.Column(db.DateTime)
    data_date = db.Column(db.DateTime)     # Schedule data date
    proj_id = db.Column(db.String(50))     # NEW: P6 Project ID from XER
    proj_short_name = db.Column(db.String(255))  # NEW: P6 Project short name
    status = db.Column(db.String(50), default='imported')  # imported, parsing, parsed, error
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    
    # Relationships
    project = db.relationship("Project", back_populates="schedules")
    activities = db.relationship("Activity", back_populates="schedule", cascade="all, delete-orphan")
    relationships = db.relationship("Relationship", back_populates="schedule", cascade="all, delete-orphan") 
    wbs_items = db.relationship("WBS", back_populates="schedule", cascade="all, delete-orphan")
    assessment_results = db.relationship("AssessmentResult", back_populates="schedule", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'project_id': self.project_id,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'total_activities': self.total_activities,
            'total_relationships': self.total_relationships,
            'total_wbs_items': self.total_wbs_items,
            'project_start_date': self.project_start_date.isoformat() if self.project_start_date else None,
            'project_finish_date': self.project_finish_date.isoformat() if self.project_finish_date else None,
            'data_date': self.data_date.isoformat() if self.data_date else None,
            'proj_id': self.proj_id,
            'proj_short_name': self.proj_short_name,
            'status': self.status,
            'created_date': self.created_date.isoformat(),
            'created_by': self.created_by
        }

class Activity(db.Model):
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    task_id = db.Column(db.String(50), nullable=False)
    task_name = db.Column(db.Text)
    task_code = db.Column(db.String(100))
    activity_code = db.Column(db.String(50))                   # Existing: Generated activity code
    wbs_id = db.Column(db.String(50))
    wbs_code = db.Column(db.String(50))                        # Existing: Parent WBS code reference
    proj_id = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=0)              # Existing: For maintaining order
    
    # Duration fields
    duration_days = db.Column(db.Float, default=0)
    total_float_days = db.Column(db.Float, default=0)
    free_float_days = db.Column(db.Float, default=0)
    
    # Existing date fields
    early_start_date = db.Column(db.DateTime)
    early_end_date = db.Column(db.DateTime)
    late_start_date = db.Column(db.DateTime)
    late_end_date = db.Column(db.DateTime)
    actual_start_date = db.Column(db.DateTime)
    actual_end_date = db.Column(db.DateTime)
    
    # Progress fields
    progress_pct = db.Column(db.Float, default=0)
    task_type = db.Column(db.String(50))
    status_code = db.Column(db.String(50))
    hierarchy_path = db.Column(db.Text)
    
    # Existing enhanced fields (if you had any)
    baseline_start_date = db.Column(db.DateTime)               # Existing
    baseline_finish_date = db.Column(db.DateTime)              # Existing (if you have this)
    constraint_type = db.Column(db.String(50))                 # Existing
    constraint_date = db.Column(db.DateTime)                   # Existing
    calendar_id = db.Column(db.String(50))                     # Existing (if you have this)
    cost_account = db.Column(db.String(100))                   # Existing (if you have this)
    responsible_manager = db.Column(db.String(100))            # Existing (if you have this)
    priority_type = db.Column(db.Integer)                      # Existing (if you have this)
    suspend_date = db.Column(db.DateTime)                      # Existing (if you have this)
    resume_date = db.Column(db.DateTime)                       # Existing (if you have this)
    additional_data = db.Column(db.JSON)                       # Existing (if you have this)
    
    # *** NEW ENHANCED FIELDS - ADD THESE ***
    activity_codes = db.Column(db.JSON)                        # NEW: Activity code assignments
    udf_values = db.Column(db.JSON)                            # NEW: User-defined field values
    target_start_date = db.Column(db.DateTime)                 # NEW: Target/planned start
    target_end_date = db.Column(db.DateTime)                   # NEW: Target/planned end
    baseline_end_date = db.Column(db.DateTime)                 # NEW: Baseline end date
    remaining_duration = db.Column(db.Float, default=0)        # NEW: Remaining duration
    original_duration = db.Column(db.Float, default=0)         # NEW: Original duration
    percent_complete = db.Column(db.Float, default=0)          # NEW: Alternative progress field
    resource_names = db.Column(db.String(500))                 # NEW: Assigned resources
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="activities")
    
    def to_dict(self):
        """Enhanced to_dict with all new fields"""
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'task_code': self.task_code,
            'activity_code': self.activity_code,
            'wbs_id': self.wbs_id,
            'wbs_code': self.wbs_code,
            'proj_id': self.proj_id,
            'sort_order': self.sort_order,
            'duration_days': self.duration_days,
            'total_float_days': self.total_float_days,
            'free_float_days': self.free_float_days,
            'early_start_date': self.early_start_date.isoformat() if self.early_start_date else None,
            'early_end_date': self.early_end_date.isoformat() if self.early_end_date else None,
            'late_start_date': self.late_start_date.isoformat() if self.late_start_date else None,
            'late_end_date': self.late_end_date.isoformat() if self.late_end_date else None,
            'actual_start_date': self.actual_start_date.isoformat() if self.actual_start_date else None,
            'actual_end_date': self.actual_end_date.isoformat() if self.actual_end_date else None,
            'progress_pct': self.progress_pct,
            'task_type': self.task_type,
            'status_code': self.status_code,
            'hierarchy_path': self.hierarchy_path,
            'baseline_start_date': self.baseline_start_date.isoformat() if self.baseline_start_date else None,
            'baseline_finish_date': self.baseline_finish_date.isoformat() if self.baseline_finish_date else None,
            'constraint_type': self.constraint_type,
            'constraint_date': self.constraint_date.isoformat() if self.constraint_date else None,
            'calendar_id': self.calendar_id,
            'cost_account': self.cost_account,
            'responsible_manager': self.responsible_manager,
            'priority_type': self.priority_type,
            'suspend_date': self.suspend_date.isoformat() if self.suspend_date else None,
            'resume_date': self.resume_date.isoformat() if self.resume_date else None,
            'additional_data': self.additional_data,
            
            # *** NEW ENHANCED FIELDS ***
            'activity_codes': self.activity_codes,                # NEW
            'udf_values': self.udf_values,                        # NEW
            'target_start_date': self.target_start_date.isoformat() if self.target_start_date else None,  # NEW
            'target_end_date': self.target_end_date.isoformat() if self.target_end_date else None,        # NEW
            'baseline_end_date': self.baseline_end_date.isoformat() if self.baseline_end_date else None,  # NEW
            'remaining_duration': self.remaining_duration,        # NEW
            'original_duration': self.original_duration,          # NEW
            'percent_complete': self.percent_complete,            # NEW
            'resource_names': self.resource_names                 # NEW
        }

class Relationship(db.Model):
    __tablename__ = 'relationships'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    pred_task_id = db.Column(db.String(50), nullable=False)    # Predecessor activity ID
    succ_task_id = db.Column(db.String(50), nullable=False)    # Successor activity ID
    pred_type = db.Column(db.String(10), default='FS')         # FS, SS, FF, SF
    lag_days = db.Column(db.Float, default=0)
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="relationships")
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'pred_task_id': self.pred_task_id,
            'succ_task_id': self.succ_task_id,
            'pred_type': self.pred_type,
            'lag_days': self.lag_days
        }

class WBS(db.Model):
    __tablename__ = 'wbs'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    wbs_id = db.Column(db.String(50), nullable=False)          # P6 WBS ID (unique within project)
    wbs_name = db.Column(db.Text)                              # WBS name/description
    wbs_short_name = db.Column(db.String(100))                 # WBS code segment (e.g., "G", "G.G", "AC")
    wbs_code = db.Column(db.String(50))                        # NEW: Hierarchy code (1.0, 1.1, 1.1.1)
    parent_wbs_id = db.Column(db.String(50))                   # Parent WBS ID (NULL for project root)
    proj_id = db.Column(db.String(50))                         # Project ID from P6
    proj_node_flag = db.Column(db.String(1))                   # 'Y' if this is project root WBS
    level = db.Column(db.Integer, default=0)                   # Hierarchy level (0=project, 1=level1, etc.)
    sort_order = db.Column(db.Integer, default=0)              # NEW: For maintaining order in exports
    full_path = db.Column(db.Text)                             # Full hierarchy path (e.g., "Project > General > All Clusters")
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="wbs_items")
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'wbs_id': self.wbs_id,
            'wbs_name': self.wbs_name,
            'wbs_short_name': self.wbs_short_name,
            'wbs_code': self.wbs_code,                          # NEW
            'parent_wbs_id': self.parent_wbs_id,
            'proj_id': self.proj_id,
            'proj_node_flag': self.proj_node_flag,
            'level': self.level,
            'sort_order': self.sort_order,                      # NEW
            'full_path': self.full_path
        }

class AssessmentResult(db.Model):
    __tablename__ = 'assessment_results'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    category_number = db.Column(db.Integer, nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(20))  # CRITICAL, HIGH, MEDIUM, LOW
    total_score = db.Column(db.Float, default=0)
    max_score = db.Column(db.Float, default=0)
    percentage = db.Column(db.Float, default=0)
    status = db.Column(db.String(50))    # EXCELLENT, GOOD, FAIR, POOR
    metrics = db.Column(db.JSON)         # Store detailed metrics as JSON
    recommendations = db.Column(db.JSON) # Store recommendations array
    assessed_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="assessment_results")
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'category_number': self.category_number,
            'category_name': self.category_name,
            'priority': self.priority,
            'total_score': self.total_score,
            'max_score': self.max_score,
            'percentage': self.percentage,
            'status': self.status,
            'metrics': self.metrics,
            'recommendations': self.recommendations,
            'assessed_date': self.assessed_date.isoformat() if self.assessed_date else None
        }

def parse_xer_file(file_path, schedule_id):
    """
    Enhanced XER parsing using raw parser and data mapper
    Supports activity codes, UDFs, and enhanced data extraction
    """
    try:
        print(f"🚀 Enhanced XER parsing: {file_path}")
        
        # Get schedule from database
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return False, "Schedule not found", {}
        
        # Create database models dictionary
        db_models = {
            'db': db,
            'Activity': Activity,
            'WBS': WBS,
            'Relationship': Relationship,
            'Schedule': Schedule
        }
        
        # Validate database models
        from core.xer_data_mapper import validate_db_models
        if not validate_db_models(db_models):
            return False, "Database models validation failed", {}
        
        # Create file processor
        from core.file_processor import create_file_processor
        file_processor = create_file_processor(UPLOAD_FOLDER)
        
        # Process the file
        success, message, stats = file_processor.process_file(
            file_path=file_path,
            schedule_id=schedule_id,
            db_models=db_models
        )
        
        if success:
            print(f"✅ Enhanced parsing successful: {message}")
            
            # Add enhanced processing information to stats
            enhanced_stats = stats.copy()
            enhanced_stats.update({
                'parsing_method': 'Enhanced Raw XER Parser',
                'supports_activity_codes': True,
                'supports_udfs': True,
                'supports_enhanced_dates': True,
                'library_free': True,  # No PyP6Xer dependency
                'file_size_mb': round(stats.get('file_size_mb', 0), 2)
            })
            
            return success, message, enhanced_stats
        else:
            print(f"❌ Enhanced parsing failed: {message}")
            return success, message, stats
            
    except Exception as e:
        print(f"❌ Enhanced XER parsing error: {e}")
        import traceback
        traceback.print_exc()
        
        # Update schedule status to error
        try:
            schedule = Schedule.query.get(schedule_id)
            if schedule:
                schedule.status = 'error'
                db.session.commit()
        except:
            pass
        
        return False, f"Enhanced parsing error: {str(e)}", {}

def export_schedule_to_xer(schedule_id, output_path):
    """
    Export schedule back to XER format with proper hierarchy codes
    This maintains the WBS structure and activity codes for P6 compatibility
    """
    try:
        print(f"📤 Exporting schedule {schedule_id} to XER format...")
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return False, "Schedule not found"
        
        # Get data with proper ordering
        wbs_items = WBS.query.filter_by(schedule_id=schedule_id).order_by(WBS.sort_order.asc()).all()
        activities = Activity.query.filter_by(schedule_id=schedule_id).order_by(
            Activity.wbs_code.asc(), Activity.sort_order.asc()
        ).all()
        relationships = Relationship.query.filter_by(schedule_id=schedule_id).all()
        
        # Build XER content with proper hierarchy codes
        xer_content = []
        
        # XER Header
        xer_content.append("ERMHDR\t1.0\t2024\tUNK\tUNK\tUNK")
        
        # Project table
        xer_content.append("%T\tPROJECT")
        xer_content.append("%F\tproj_id\tproj_short_name\tplan_start_date\tplan_end_date")
        project_start = schedule.project_start_date.strftime('%Y-%m-%d %H:%M') if schedule.project_start_date else ''
        project_end = schedule.project_finish_date.strftime('%Y-%m-%d %H:%M') if schedule.project_finish_date else ''
        xer_content.append(f"%R\t{schedule.proj_id}\t{schedule.proj_short_name}\t{project_start}\t{project_end}")
        xer_content.append("%E")
        
        # WBS table with hierarchy codes
        xer_content.append("%T\tPROJWBS")
        xer_content.append("%F\twbs_id\twbs_name\tparent_wbs_id\tproj_id\twbs_short_name\tlevel")
        for wbs in wbs_items:
            parent_id = wbs.parent_wbs_id if wbs.parent_wbs_id else ''
            wbs_code = wbs.wbs_code if wbs.wbs_code else wbs.wbs_short_name
            xer_content.append(f"%R\t{wbs.wbs_id}\t{wbs.wbs_name}\t{parent_id}\t{wbs.proj_id}\t{wbs_code}\t{wbs.level}")
        xer_content.append("%E")
        
        # Activities table with activity codes
        xer_content.append("%T\tTASK")
        xer_content.append("%F\ttask_id\ttask_name\twbs_id\ttask_code\ttarget_drtn_hr_cnt\tearly_start_date\tearly_end_date\tphys_complete_pct\ttotal_float_hr_cnt")
        for activity in activities:
            duration_hrs = (activity.duration_days or 0) * 8
            float_hrs = (activity.total_float_days or 0) * 8
            early_start = activity.early_start_date.strftime('%Y-%m-%d %H:%M') if activity.early_start_date else ''
            early_end = activity.early_end_date.strftime('%Y-%m-%d %H:%M') if activity.early_end_date else ''
            task_code = activity.activity_code if activity.activity_code else activity.task_code
            xer_content.append(f"%R\t{activity.task_id}\t{activity.task_name}\t{activity.wbs_id}\t{task_code}\t{duration_hrs}\t{early_start}\t{early_end}\t{activity.progress_pct}\t{float_hrs}")
        xer_content.append("%E")
        
        # Relationships table
        if relationships:
            xer_content.append("%T\tTASKPRED")
            xer_content.append("%F\tpred_task_id\ttask_id\tpred_type\tlag_hr_cnt")
            for rel in relationships:
                lag_hrs = (rel.lag_days or 0) * 8
                # Convert back to P6 format
                pred_type_p6 = f"PR_{rel.pred_type}" if not rel.pred_type.startswith('PR_') else rel.pred_type
                xer_content.append(f"%R\t{rel.pred_task_id}\t{rel.succ_task_id}\t{pred_type_p6}\t{lag_hrs}")
            xer_content.append("%E")
        
        # Write to file
        with open(output_path, 'w', encoding='latin-1') as f:
            f.write('\n'.join(xer_content))
        
        print(f"✅ XER export completed: {output_path}")
        return True, f"Exported to {output_path}"
        
    except Exception as e:
        print(f"❌ XER export error: {e}")
        return False, f"Export error: {str(e)}"
    
def generate_wbs_hierarchy_codes(schedule_id):
    """
    Generate hierarchical WBS codes (1.0, 1.1, 1.1.1, etc.)
    Store them in the database with proper XER export compatibility
    """
    try:
        print("🔢 Generating WBS hierarchy codes...")
        
        # Get all WBS items for this schedule
        wbs_items = WBS.query.filter_by(schedule_id=schedule_id).all()
        
        if not wbs_items:
            print("⚠️ No WBS items found")
            return False
        
        # Create WBS lookup map
        wbs_map = {wbs.wbs_id: wbs for wbs in wbs_items}
        
        # Sort by level and name for consistent ordering
        wbs_items.sort(key=lambda w: (w.level or 0, w.wbs_name or ''))
        
        # Find root WBS items (project level)
        root_wbs = [wbs for wbs in wbs_items if wbs.proj_node_flag == 'Y' or wbs.level == 0 or not wbs.parent_wbs_id]
        
        print(f"🌳 Found {len(root_wbs)} root WBS items")
        
        # Assign codes to root items
        for index, wbs in enumerate(root_wbs):
            wbs_code = f"{index + 1}.0"
            wbs.wbs_code = wbs_code
            wbs.sort_order = index + 1
            print(f"   📁 {wbs.wbs_name} = {wbs_code}")
            
            # Recursively assign codes to children
            assign_child_wbs_codes(wbs, wbs_code, wbs_map, wbs_items)
        
        # Save all WBS updates to database
        db.session.commit()
        print(f"✅ Generated and saved WBS codes for {len(wbs_items)} items")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating WBS codes: {e}")
        db.session.rollback()
        return False


def assign_child_wbs_codes(parent_wbs, parent_code, wbs_map, wbs_items):
    """
    Recursively assign WBS codes to child WBS items
    """
    # Find children of current WBS
    children = [wbs for wbs in wbs_items if wbs.parent_wbs_id == parent_wbs.wbs_id]
    
    # Sort children by name for consistent ordering
    children.sort(key=lambda w: w.wbs_name or '')
    
    for index, child in enumerate(children):
        # Generate child code
        if parent_code.endswith('.0'):
            # Replace .0 with actual number for first level
            child_code = f"{parent_code[:-2]}.{index + 1}"
        else:
            # Append to existing code
            child_code = f"{parent_code}.{index + 1}"
        
        # Store the code
        child.wbs_code = child_code
        child.sort_order = index + 1
        print(f"     📂‚ {child.wbs_name} = {child_code}")
        
        # Recursively assign codes to children
        assign_child_wbs_codes(child, child_code, wbs_map, wbs_items)


def generate_activity_codes(schedule_id):
    """
    Generate activity codes based on WBS codes (1.1.1.1, 1.1.1.2, etc.)
    Store them in the activity_code field for XER export compatibility
    """
    try:
        print("🎯 Generating activity codes based on WBS hierarchy...")
        
        # Get all activities and WBS items for this schedule
        activities = Activity.query.filter_by(schedule_id=schedule_id).all()
        wbs_items = WBS.query.filter_by(schedule_id=schedule_id).all()
        
        # Create WBS lookup map with codes
        wbs_code_map = {wbs.wbs_id: wbs.wbs_code for wbs in wbs_items if wbs.wbs_code}
        
        # Group activities by WBS
        activities_by_wbs = {}
        for activity in activities:
            wbs_id = activity.wbs_id
            if wbs_id not in activities_by_wbs:
                activities_by_wbs[wbs_id] = []
            activities_by_wbs[wbs_id].append(activity)
        
        # Generate activity codes for each WBS
        total_coded = 0
        for wbs_id, wbs_activities in activities_by_wbs.items():
            wbs_code = wbs_code_map.get(wbs_id)
            if not wbs_code:
                print(f"⚠️ No WBS code found for WBS ID: {wbs_id}")
                continue
            
            # Sort activities by start date and task_id for consistent ordering
            wbs_activities.sort(key=lambda a: (
                a.early_start_date or datetime(1900, 1, 1),  # 🔗 Fixed
                a.task_id
            ))
            
            # Assign activity codes
            for index, activity in enumerate(wbs_activities):
                activity_code = f"{wbs_code}.{index + 1}"
                activity.activity_code = activity_code
                activity.wbs_code = wbs_code  # Store reference to parent WBS code
                activity.sort_order = index + 1
                total_coded += 1
                
                if index < 3:  # Show first 3 for debugging
                    print(f"     🎯 {activity.task_name[:30]}... = {activity_code}")
        
        # Save all activity updates to database
        db.session.commit()
        print(f"✅ Generated and saved activity codes for {total_coded} activities")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating activity codes: {e}")
        db.session.rollback()
        return False


def build_enhanced_hierarchy_paths(schedule_id):
    """
    Build enhanced hierarchy paths with codes for display and navigation
    """
    try:
        print("🌐 Building enhanced hierarchy paths with codes...")
        
        # Get all WBS items and activities
        wbs_items = WBS.query.filter_by(schedule_id=schedule_id).all()
        activities = Activity.query.filter_by(schedule_id=schedule_id).all()
        
        # Create WBS lookup map
        wbs_map = {wbs.wbs_id: wbs for wbs in wbs_items}
        
        # Function to build WBS path with codes
        def get_wbs_path_with_codes(wbs_id):
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
        
        # Update WBS full paths with codes
        for wbs in wbs_items:
            wbs.full_path = get_wbs_path_with_codes(wbs.wbs_id)
        
        # Update Activity hierarchy paths with codes
        for activity in activities:
            if activity.wbs_id and activity.wbs_id in wbs_map:
                wbs_path = get_wbs_path_with_codes(activity.wbs_id)
                activity_code = activity.activity_code or activity.task_id
                activity.hierarchy_path = f"{wbs_path} > {activity_code} {activity.task_name}"
            else:
                activity_code = activity.activity_code or activity.task_id
                activity.hierarchy_path = f"Unassigned > {activity_code} {activity.task_name}"
        
        # Save all updates to database
        db.session.commit()
        print(f"✅ Built enhanced hierarchy paths for {len(wbs_items)} WBS and {len(activities)} activities")
        
        return True
        
    except Exception as e:
        print(f"❌ Error building enhanced hierarchy paths: {e}")
        db.session.rollback()
        return False


def add_new_activity_to_wbs(schedule_id, wbs_id, activity_data):
    """
    Add a new activity to a specific WBS with proper hierarchy code assignment
    This function ensures new activities follow the existing code structure
    """
    try:
        print(f"➕ Adding new activity to WBS {wbs_id}")
        
        # Get the WBS item
        wbs = WBS.query.filter_by(schedule_id=schedule_id, wbs_id=wbs_id).first()
        if not wbs or not wbs.wbs_code:
            return False, "WBS not found or no WBS code assigned"
        
        # Find existing activities in this WBS
        existing_activities = Activity.query.filter_by(
            schedule_id=schedule_id, 
            wbs_id=wbs_id
        ).order_by(Activity.sort_order.desc()).all()
        
        # Determine next activity number
        if existing_activities:
            last_activity = existing_activities[0]
            next_number = (last_activity.sort_order or 0) + 1
        else:
            next_number = 1
        
        # Generate activity code
        new_activity_code = f"{wbs.wbs_code}.{next_number}"
        
        # Create new activity
        new_activity = Activity(
            schedule_id=schedule_id,
            task_id=activity_data.get('task_id'),
            task_name=activity_data.get('task_name'),
            activity_code=new_activity_code,
            wbs_id=wbs_id,
            wbs_code=wbs.wbs_code,
            sort_order=next_number,
            # ... other activity fields
        )
        
        db.session.add(new_activity)
        db.session.commit()
        
        # Rebuild hierarchy path for this activity
        build_enhanced_hierarchy_paths(schedule_id)
        
        print(f"✅ Added activity {new_activity_code} to WBS {wbs.wbs_code}")
        return True, new_activity_code
        
    except Exception as e:
        print(f"❌ Error adding new activity: {e}")
        db.session.rollback()
        return False, str(e)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
    
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    
    # FIXED CORS Configuration
    CORS(app, 
         origins=["http://localhost:5173", "http://127.0.0.1:5173"],
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    # Create tables within app context
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database and models loaded successfully")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
    
    
    # Routes
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'message': 'Schedule Foundation API is running'})
    
    @app.route('/api/debug')
    def debug():
        try:
            project_count = Project.query.count()
            schedule_count = Schedule.query.count()
            return jsonify({
                'status': 'success', 
                'project_count': project_count,
                'schedule_count': schedule_count,
                'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set'),
                'cors_enabled': True,
                'server_time': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # Project routes
    @app.route('/api/projects', methods=['GET'])
    def get_projects():
        try:
            print("📋 API: Fetching projects...")
            projects = Project.query.all()
            print(f"✅ API: Found {len(projects)} projects")
            
            result = [project.to_dict() for project in projects]
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ API Error in get_projects: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/projects', methods=['POST'])
    def create_project():
        try:
            print("📋 API: Creating project...")
            data = request.get_json()
            print(f"📝 API: Received data: {data}")
            
            if not data or not data.get('name'):
                return jsonify({'error': 'Project name is required'}), 400
            
            project = Project(
                name=data['name'],
                description=data.get('description', ''),
                created_by=data.get('created_by', 'unknown')
            )
            
            db.session.add(project)
            db.session.commit()
            
            print(f"✅ API: Created project: {project.name}")
            return jsonify(project.to_dict()), 201
            
        except Exception as e:
            print(f"❌ API Error creating project: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/projects/<int:project_id>', methods=['GET'])
    def get_project(project_id):
        try:
            project = Project.query.get_or_404(project_id)
            return jsonify(project.to_dict())
        except Exception as e:
            print(f"❌ API Error getting project {project_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Schedule routes
    @app.route('/api/projects/<int:project_id>/schedules', methods=['GET'])
    def get_project_schedules(project_id):
        try:
            project = Project.query.get_or_404(project_id)
            schedules = Schedule.query.filter_by(project_id=project_id).all()
            return jsonify([schedule.to_dict() for schedule in schedules])
        except Exception as e:
            print(f"❌ API Error getting schedules for project {project_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/projects/<int:project_id>/schedules', methods=['POST'])
    def create_schedule(project_id):
        try:
            project = Project.query.get_or_404(project_id)
            
            data = request.get_json()
            
            if not data or not data.get('name'):
                return jsonify({'error': 'Schedule name is required'}), 400
            
            schedule = Schedule(
                name=data['name'],
                description=data.get('description', ''),
                project_id=project_id,
                created_by=data.get('created_by', 'unknown')
            )
            
            db.session.add(schedule)
            db.session.commit()
            
            return jsonify(schedule.to_dict()), 201
            
        except Exception as e:
            print(f"❌ API Error creating schedule: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/schedules/<int:schedule_id>', methods=['GET'])
    def get_schedule(schedule_id):
        try:
            schedule = Schedule.query.get_or_404(schedule_id)
            return jsonify(schedule.to_dict())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # File Upload Routes
    @app.route('/api/projects/<int:project_id>/upload-xer', methods=['POST'])
    def upload_xer_file(project_id):
        try:
            # Verify project exists
            project = Project.query.get_or_404(project_id)
            
            # Check if file is present
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate file
            if not allowed_file(file.filename):
                return jsonify({'error': 'Only .xer files are allowed'}), 400
            
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > MAX_FILE_SIZE:
                return jsonify({
                    'error': f'File too large: {file_size / 1024 / 1024:.1f}MB. Maximum allowed: {MAX_FILE_SIZE / 1024 / 1024:.1f}MB'
                }), 413
            
            # Save file with unique name
            filename = secure_filename(file.filename)
            unique_filename = f"{project_id}_{int(datetime.now().timestamp())}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            
            # Create schedule record first
            schedule_name = request.form.get('schedule_name') or f"Imported from {filename}"
            schedule_description = request.form.get('description') or f"Schedule imported from {filename}"
            
            schedule = Schedule(
                name=schedule_name,
                description=schedule_description,
                project_id=project_id,
                file_name=unique_filename,
                file_size=file_size,
                status='parsing',  # Set status to parsing
                created_by=request.form.get('created_by', 'file_upload')
            )
            
            db.session.add(schedule)
            db.session.commit()
            
            # Parse XER file and populate database
            success, message, stats = parse_xer_file(file_path, schedule.id)
            
            if success:
                return jsonify({
                    'message': 'File uploaded and parsed successfully',
                    'schedule': schedule.to_dict(),
                    'file_path': file_path,
                    'stats': stats
                }), 201
            else:
                # Update schedule status to error
                schedule.status = 'error'
                db.session.commit()
                
                return jsonify({
                    'error': message,
                    'schedule': schedule.to_dict()
                }), 500
                
        except Exception as e:
            print(f"❌ API Error uploading file: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/schedules/<int:schedule_id>/delete', methods=['DELETE'])
    def delete_schedule(schedule_id):
        """Delete schedule and associated file"""
        try:
            schedule = Schedule.query.get_or_404(schedule_id)
            
            # Delete file if exists
            if schedule.file_name:
                file_path = os.path.join(UPLOAD_FOLDER, schedule.file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # Delete from database
            db.session.delete(schedule)
            db.session.commit()
            
            return jsonify({'message': 'Schedule deleted successfully'})
            
        except Exception as e:
            print(f"❌ API Error deleting schedule: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/schedules/<int:schedule_id>/export-xer', methods=['POST'])
    def export_xer_endpoint(schedule_id):
        """Export schedule to XER format via API"""
        try:
            schedule = Schedule.query.get_or_404(schedule_id)
            
            # Generate output filename
            safe_name = "".join(c for c in schedule.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            output_filename = f"{safe_name}_{schedule_id}.xer"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)
            
            # Export to XER
            success, message = export_schedule_to_xer(schedule_id, output_path)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Schedule exported successfully',
                    'filename': output_filename,
                    'path': output_path
                })
            else:
                return jsonify({
                    'success': False,
                    'error': message
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Test route
    @app.route('/test-create-project')
    def test_create():
        try:
            project = Project(
                name=f"Test Project {Project.query.count() + 1}",
                description="Auto-generated test project",
                created_by="test_system"
            )
            db.session.add(project)
            db.session.commit()
            return jsonify({'message': 'Test project created', 'project': project.to_dict()})
        except Exception as e:
            print(f"❌ API Error in test route: {e}")
            return jsonify({'error': str(e)}), 500
    

    @app.route('/api/schedules/<int:schedule_id>/activities', methods=['GET'])
    def get_schedule_activities_with_hierarchy(schedule_id):
        """Load ALL activities without pagination limits"""
        try:
            schedule = Schedule.query.get_or_404(schedule_id)
            
            # Get filters
            search = request.args.get('search', '')
            status_filter = request.args.get('status', 'all')
            
            print(f"🔍 Loading ALL activities for schedule {schedule_id}")
            
            # Build query with filters
            query = Activity.query.filter(Activity.schedule_id == schedule_id)
            
            if search:
                query = query.filter(
                    db.or_(
                        Activity.task_id.ilike(f'%{search}%'),
                        Activity.task_name.ilike(f'%{search}%'),
                        Activity.task_code.ilike(f'%{search}%'),
                        Activity.wbs_id.ilike(f'%{search}%'),
                        Activity.hierarchy_path.ilike(f'%{search}%')
                    )
                )
            
            if status_filter != 'all':
                if status_filter == 'not_started':
                    query = query.filter(Activity.progress_pct == 0)
                elif status_filter == 'in_progress':
                    query = query.filter(
                        db.and_(Activity.progress_pct > 0, Activity.progress_pct < 100)
                    )
                elif status_filter == 'completed':
                    query = query.filter(Activity.progress_pct >= 100)
            
            # ✅ GET ALL ACTIVITIES - NO PAGINATION
            activities = query.order_by(
                Activity.hierarchy_path.asc(),
                Activity.early_start_date.asc().nullslast(), 
                Activity.task_id.asc()
            ).all()
            
            # Get WBS structure
            wbs_items = WBS.query.filter_by(schedule_id=schedule_id).all()
            
            print(f"✅ Loaded ALL {len(activities)} activities and {len(wbs_items)} WBS items")
            
            # Return response without pagination info
            return jsonify({
                'success': True,
                'activities': [activity.to_dict() for activity in activities],
                'wbs_structure': [wbs.to_dict() for wbs in wbs_items],
                'total_loaded': len(activities)
            })
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        
    @app.route('/api/schedules/<int:schedule_id>/relationships', methods=['GET'])
    def get_schedule_relationships(schedule_id):
        """Get relationships for a specific schedule with pagination"""
        try:
            # Verify schedule exists
            schedule = Schedule.query.get_or_404(schedule_id)
            
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 100, type=int)
            
            # Limit per_page
            per_page = min(per_page, 1000)
            
            # Query relationships
            query = Relationship.query.filter_by(schedule_id=schedule_id).order_by(Relationship.pred_task_id)
            
            # Paginate
            pagination = query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            relationships = pagination.items
            
            # Get summary statistics
            total_relationships = Relationship.query.filter_by(schedule_id=schedule_id).count()
            
            # Count by relationship type
            fs_count = Relationship.query.filter_by(schedule_id=schedule_id, pred_type='FS').count()
            ss_count = Relationship.query.filter_by(schedule_id=schedule_id, pred_type='SS').count()
            ff_count = Relationship.query.filter_by(schedule_id=schedule_id, pred_type='FF').count()
            sf_count = Relationship.query.filter_by(schedule_id=schedule_id, pred_type='SF').count()
            
            return jsonify({
                'relationships': [rel.to_dict() for rel in relationships],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                },
                'summary': {
                    'total_relationships': total_relationships,
                    'fs_relationships': fs_count,
                    'ss_relationships': ss_count,
                    'ff_relationships': ff_count,
                    'sf_relationships': sf_count
                },
                'schedule': schedule.to_dict()
            })
            
        except Exception as e:
            print(f"❌ API Error getting relationships: {e}")
            return jsonify({'error': str(e)}), 500

    return app


# For development
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)