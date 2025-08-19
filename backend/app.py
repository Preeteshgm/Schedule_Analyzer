import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config import Config

from xerparser import Xer
import pandas as pd
from datetime import datetime as dt
import tempfile

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
    project_start_date = db.Column(db.DateTime)
    project_finish_date = db.Column(db.DateTime)
    data_date = db.Column(db.DateTime)     # Schedule data date
    status = db.Column(db.String(50), default='imported')  # imported, analyzing, ready, error
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    activities = db.relationship("Activity", back_populates="schedule", cascade="all, delete-orphan")
    relationships = db.relationship("Relationship", back_populates="schedule", cascade="all, delete-orphan") 
    wbs_items = db.relationship("WBS", back_populates="schedule", cascade="all, delete-orphan")
    assessment_results = db.relationship("AssessmentResult", back_populates="schedule", cascade="all, delete-orphan")
    
    # Relationship to project
    project = db.relationship("Project", back_populates="schedules")
    
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
            'project_start_date': self.project_start_date.isoformat() if self.project_start_date else None,
            'project_finish_date': self.project_finish_date.isoformat() if self.project_finish_date else None,
            'data_date': self.data_date.isoformat() if self.data_date else None,
            'status': self.status,
            'created_date': self.created_date.isoformat(),
            'created_by': self.created_by,
            'activity_count': len(self.activities) if self.activities else 0,
            'relationship_count': len(self.relationships) if self.relationships else 0,
            'wbs_count': len(self.wbs_items) if self.wbs_items else 0,
            'assessment_count': len(self.assessment_results) if self.assessment_results else 0
        }

class Activity(db.Model):
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    task_id = db.Column(db.String(50), nullable=False)         # P6 Activity ID
    task_name = db.Column(db.Text)
    wbs_id = db.Column(db.String(50))                          # Links to WBS.wbs_id
    duration_days = db.Column(db.Float, default=0)
    total_float_days = db.Column(db.Float, default=0)
    free_float_days = db.Column(db.Float, default=0)
    early_start_date = db.Column(db.DateTime)
    early_end_date = db.Column(db.DateTime)
    late_start_date = db.Column(db.DateTime)
    late_end_date = db.Column(db.DateTime)
    actual_start_date = db.Column(db.DateTime)
    actual_end_date = db.Column(db.DateTime)
    progress_pct = db.Column(db.Float, default=0)
    task_type = db.Column(db.String(50))
    status_code = db.Column(db.String(50))
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="activities")
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'wbs_id': self.wbs_id,
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
            'status_code': self.status_code
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
    wbs_name = db.Column(db.Text)                              # WBS name
    parent_wbs_id = db.Column(db.String(50))                   # Parent WBS ID (NULL for root)
    proj_id = db.Column(db.String(50))                         # Project ID from P6
    
    # Relationship to schedule
    schedule = db.relationship("Schedule", back_populates="wbs_items")
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'wbs_id': self.wbs_id,
            'wbs_name': self.wbs_name,
            'parent_wbs_id': self.parent_wbs_id,
            'proj_id': self.proj_id
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
    Enhanced XER parser that properly extracts PROJWBS table for P6 hierarchy
    Returns: (success: bool, message: str, stats: dict)
    """
    try:
        print(f"🔄 Enhanced XER parsing with WBS: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}", {}
        
        # Check file size
        file_size = os.path.getsize(file_path)
        print(f"📁 File size: {file_size / 1024 / 1024:.2f} MB")
        
        if file_size == 0:
            return False, "File is empty", {}
        
        # STEP 1: Read XER file with proper encoding
        print("📖 Reading XER file...")
        
        encodings_to_try = ['latin-1', 'utf-8', 'cp1252', 'iso-8859-1']
        successful_encoding = None
        lines = []
        
        for encoding in encodings_to_try:
            try:
                print(f"🔤 Trying encoding: {encoding}")
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                # Check if it's a valid XER file
                if lines and lines[0].strip().startswith('ERMHDR'):
                    print(f"✅ Valid XER file detected with {encoding} encoding")
                    successful_encoding = encoding
                    break
                else:
                    print(f"❌ {encoding}: File doesn't start with ERMHDR")
                    
            except UnicodeDecodeError:
                print(f"❌ {encoding} failed: UnicodeDecodeError")
                continue
            except Exception as e:
                print(f"❌ {encoding} failed with error: {e}")
                continue
        
        if not successful_encoding:
            return False, "Unable to read XER file with any supported encoding", {}
        
        print(f"📄 Successfully read {len(lines)} lines")
        
        # STEP 2: Parse XER structure
        print("🏗️ Parsing XER structure...")
        
        current_table = None
        tables = {}
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('%T'):
                # Table start: %T<TAB>TABLE_NAME
                parts = line.split('\t')
                if len(parts) >= 2:
                    current_table = parts[1]
                    tables[current_table] = {'columns': [], 'data': []}
                    print(f"📋 Found table: {current_table}")
                    
            elif line.startswith('%F') and current_table:
                # Field definition: %F<TAB>FIELD_NAME<TAB>DATA_TYPE
                parts = line.split('\t')
                if len(parts) >= 2:
                    field_name = parts[1]
                    tables[current_table]['columns'].append(field_name)
                    
            elif line.startswith('%R') and current_table:
                # Data row: %R<TAB>VALUE1<TAB>VALUE2<TAB>...
                parts = line.split('\t')[1:]  # Skip %R
                tables[current_table]['data'].append(parts)
                
            elif line.startswith('%E'):
                # Table end
                if current_table:
                    print(f"✅ Completed table {current_table}: {len(tables[current_table]['data'])} rows")
                current_table = None
        
        print(f"📊 Parsed {len(tables)} tables from XER file")
        print(f"📋 Available tables: {list(tables.keys())}")
        
        # STEP 3: Extract PROJECT information
        print("📋 Extracting project information...")
        project_info = {'name': 'Imported Project', 'proj_id': None}
        
        if 'PROJECT' in tables:
            project_table = tables['PROJECT']
            if project_table['data']:
                col_map = {col: i for i, col in enumerate(project_table['columns'])}
                first_project = project_table['data'][0]
                
                project_info = {
                    'name': first_project[col_map.get('proj_short_name', 0)] if 'proj_short_name' in col_map else 'Imported Project',
                    'proj_id': first_project[col_map.get('proj_id', 0)] if 'proj_id' in col_map else None
                }
                
                print(f"📊 Project: {project_info['name']} (ID: {project_info['proj_id']})")
        
        # STEP 4: Extract PROJWBS (THE CRITICAL TABLE FOR HIERARCHY!)
        print("🏗️ Extracting PROJWBS (WBS hierarchy)...")
        wbs_items = []
        
        if 'PROJWBS' in tables:
            wbs_table = tables['PROJWBS']
            col_map = {col: i for i, col in enumerate(wbs_table['columns'])}
            
            print(f"📁 PROJWBS columns: {wbs_table['columns']}")
            print(f"🏗️ Processing {len(wbs_table['data'])} WBS items...")
            
            for row_num, row in enumerate(wbs_table['data']):
                if row_num % 1000 == 0 and row_num > 0:
                    print(f"   Processing WBS item {row_num}...")
                
                try:
                    # Helper function to safely get values
                    def get_value(col_name, default=''):
                        try:
                            if col_name in col_map and col_map[col_name] < len(row):
                                val = row[col_map[col_name]].strip()
                                return val if val else default
                            return default
                        except:
                            return default
                    
                    wbs_id = get_value('wbs_id')
                    wbs_name = get_value('wbs_name') or get_value('wbs_short_name', 'Unnamed WBS')
                    parent_wbs_id = get_value('parent_wbs_id')
                    proj_id = get_value('proj_id', project_info.get('proj_id', ''))
                    
                    # Handle empty parent_wbs_id (root level)
                    if not parent_wbs_id or parent_wbs_id == proj_id:
                        parent_wbs_id = None
                    
                    if not wbs_id:  # Skip rows without wbs_id
                        continue
                    
                    wbs_item = WBS(
                        schedule_id=schedule_id,
                        wbs_id=wbs_id,
                        wbs_name=wbs_name,
                        parent_wbs_id=parent_wbs_id,
                        proj_id=proj_id
                    )
                    
                    wbs_items.append(wbs_item)
                    
                except Exception as e:
                    print(f"⚠️ Error processing WBS row {row_num}: {e}")
                    continue
            
            print(f"✅ Successfully processed {len(wbs_items)} WBS items")
        else:
            print("⚠️ No PROJWBS table found in XER file")
        
        # STEP 5: Extract TASK (Activities)
        print("🎯 Extracting activities...")
        activities_data = []
        
        if 'TASK' in tables:
            task_table = tables['TASK']
            col_map = {col: i for i, col in enumerate(task_table['columns'])}
            
            print(f"📋 TASK columns: {task_table['columns']}")
            print(f"🎯 Processing {len(task_table['data'])} activities...")
            
            for row_num, row in enumerate(task_table['data']):
                if row_num % 5000 == 0 and row_num > 0:
                    print(f"   Processing activity {row_num}...")
                
                try:
                    # Helper functions
                    def get_value(col_name, default=''):
                        try:
                            if col_name in col_map and col_map[col_name] < len(row):
                                val = row[col_map[col_name]].strip()
                                return val if val else default
                            return default
                        except:
                            return default
                    
                    def get_float(col_name, default=0.0):
                        try:
                            val = get_value(col_name, '0')
                            return float(val) if val and val != '' else default
                        except:
                            return default
                    
                    def get_date(col_name):
                        try:
                            val = get_value(col_name)
                            if val and val != '':
                                # Try to parse date (P6 dates are usually in YYYY-MM-DD format)
                                return datetime.strptime(val[:10], '%Y-%m-%d') if len(val) >= 10 else None
                            return None
                        except:
                            return None
                    
                    # Extract activity data
                    task_id = get_value('task_id')
                    task_name = get_value('task_name')
                    
                    if not task_id:  # Skip rows without task_id
                        continue
                    
                    # Convert hours to days (assuming 8-hour days)
                    duration_hours = get_float('target_drtn_hr_cnt', 0)
                    duration_days = duration_hours / 8 if duration_hours > 0 else 0
                    
                    total_float_hours = get_float('total_float_hr_cnt', 0)
                    total_float_days = total_float_hours / 8
                    
                    free_float_hours = get_float('free_float_hr_cnt', 0)
                    free_float_days = free_float_hours / 8
                    
                    progress_pct = get_float('phys_complete_pct', 0)
                    
                    # Extract dates
                    early_start_date = get_date('early_start_date')
                    early_end_date = get_date('early_end_date')
                    late_start_date = get_date('late_start_date')
                    late_end_date = get_date('late_end_date')
                    actual_start_date = get_date('act_start_date')
                    actual_end_date = get_date('act_end_date')
                    
                    activity_data = Activity(
                        schedule_id=schedule_id,
                        task_id=task_id,
                        task_name=task_name,
                        wbs_id=get_value('wbs_id'),
                        duration_days=duration_days,
                        total_float_days=total_float_days,
                        free_float_days=free_float_days,
                        early_start_date=early_start_date,
                        early_end_date=early_end_date,
                        late_start_date=late_start_date,
                        late_end_date=late_end_date,
                        actual_start_date=actual_start_date,
                        actual_end_date=actual_end_date,
                        progress_pct=progress_pct,
                        task_type=get_value('task_type'),
                        status_code=get_value('status_code')
                    )
                    
                    activities_data.append(activity_data)
                    
                except Exception as e:
                    print(f"⚠️ Error processing activity {row_num}: {e}")
                    continue
            
            print(f"✅ Successfully processed {len(activities_data)} activities")
        else:
            print("⚠️ No TASK table found in XER file")
        
        # STEP 6: Extract TASKPRED (Relationships)
        print("🔗 Extracting relationships...")
        relationships_data = []
        
        if 'TASKPRED' in tables:
            rel_table = tables['TASKPRED']
            col_map = {col: i for i, col in enumerate(rel_table['columns'])}
            
            print(f"📋 TASKPRED columns: {rel_table['columns']}")
            print(f"🔗 Processing {len(rel_table['data'])} relationships...")
            
            for row_num, row in enumerate(rel_table['data']):
                if row_num % 10000 == 0 and row_num > 0:
                    print(f"   Processing relationship {row_num}...")
                
                try:
                    def get_value(col_name, default=''):
                        try:
                            if col_name in col_map and col_map[col_name] < len(row):
                                val = row[col_map[col_name]].strip()
                                return val if val else default
                            return default
                        except:
                            return default
                    
                    def get_float(col_name, default=0.0):
                        try:
                            val = get_value(col_name, '0')
                            return float(val) if val and val != '' else default
                        except:
                            return default
                    
                    # Try different possible column names
                    pred_task_id = (get_value('pred_task_id') or 
                                  get_value('pred_task_uid') or 
                                  get_value('predecessor_task_id'))
                    
                    task_id = (get_value('task_id') or 
                              get_value('task_uid') or 
                              get_value('successor_task_id'))
                    
                    # Skip if we don't have both IDs
                    if not pred_task_id or not task_id:
                        continue
                    
                    # Extract lag and pred_type
                    lag_hours = get_float('lag_hr_cnt', 0)
                    lag_days = lag_hours / 8
                    
                    pred_type = get_value('pred_type', 'FS')
                    
                    relationship_data = Relationship(
                        schedule_id=schedule_id,
                        pred_task_id=pred_task_id,
                        succ_task_id=task_id,
                        pred_type=pred_type,
                        lag_days=lag_days
                    )
                    
                    relationships_data.append(relationship_data)
                    
                except Exception as e:
                    print(f"⚠️ Error processing relationship {row_num}: {e}")
                    continue
            
            print(f"✅ Successfully processed {len(relationships_data)} relationships")
        else:
            print("⚠️ No TASKPRED table found in XER file")
        
        # STEP 7: Save to database with proper order (WBS first, then activities, then relationships)
        print("💾 Saving to database...")
        
        try:
            # Save WBS items first (they're referenced by activities)
            if wbs_items:
                batch_size = 500
                for i in range(0, len(wbs_items), batch_size):
                    batch = wbs_items[i:i+batch_size]
                    db.session.add_all(batch)
                    db.session.commit()
                    if len(wbs_items) > batch_size:
                        print(f"   Saved WBS items: {min(i+batch_size, len(wbs_items))}/{len(wbs_items)}")
                
                print(f"✅ Saved all {len(wbs_items)} WBS items")
            
            # Save activities (they reference WBS items)
            if activities_data:
                batch_size = 500
                for i in range(0, len(activities_data), batch_size):
                    batch = activities_data[i:i+batch_size]
                    db.session.add_all(batch)
                    db.session.commit()
                    if len(activities_data) > batch_size:
                        print(f"   Saved activities: {min(i+batch_size, len(activities_data))}/{len(activities_data)}")
                
                print(f"✅ Saved all {len(activities_data)} activities")
            
            # Save relationships (they reference activities)
            if relationships_data:
                batch_size = 500
                for i in range(0, len(relationships_data), batch_size):
                    batch = relationships_data[i:i+batch_size]
                    db.session.add_all(batch)
                    db.session.commit()
                    if len(relationships_data) > batch_size:
                        print(f"   Saved relationships: {min(i+batch_size, len(relationships_data))}/{len(relationships_data)}")
                
                print(f"✅ Saved all {len(relationships_data)} relationships")
            
            # Update schedule with parsed information
            schedule = Schedule.query.get(schedule_id)
            if schedule:
                schedule.total_activities = len(activities_data)
                schedule.total_relationships = len(relationships_data)
                schedule.status = 'parsed'
                db.session.commit()
                
                print(f"✅ Updated schedule {schedule.id}")
            
        except Exception as db_error:
            print(f"❌ Database save error: {db_error}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False, f"Database error: {str(db_error)}", {}
        
        # STEP 8: Return success with comprehensive stats
        stats = {
            'activities': len(activities_data),
            'relationships': len(relationships_data),
            'wbs_items': len(wbs_items),
            'project_name': project_info.get('name', 'Unknown'),
            'project_id': project_info.get('proj_id'),
            'encoding_used': successful_encoding,
            'tables_found': list(tables.keys())
        }
        
        print(f"🎉 XER file parsed successfully with complete hierarchy!")
        print(f"📊 Final stats: {len(activities_data)} activities, {len(relationships_data)} relationships, {len(wbs_items)} WBS items")
        
        return True, f"XER file parsed successfully! Imported {len(activities_data)} activities, {len(relationships_data)} relationships, and {len(wbs_items)} WBS items with complete P6 hierarchy.", stats
        
    except Exception as e:
        print(f"❌ Unexpected error in enhanced XER parser: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Unexpected error: {str(e)}", {}

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
            print("🔍 API: Fetching projects...")
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
            print("🔍 API: Creating project...")
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
    def get_schedule_activities(schedule_id):
        """Get activities for a specific schedule with proper WBS hierarchy"""
        try:
            # Verify schedule exists
            schedule = Schedule.query.get_or_404(schedule_id)
            
            print(f"🔍 Fetching activities for schedule {schedule_id}: {schedule.name}")
            
            # Get pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 1000, type=int), 2000)  # Increased limit
            
            # Get filter parameters
            search = request.args.get('search', '')
            status = request.args.get('status', 'all')
            
            # STEP 1: Get all activities for this schedule
            print("📋 Fetching activities...")
            activity_query = Activity.query.filter(Activity.schedule_id == schedule_id)
            
            # Apply search filter
            if search:
                activity_query = activity_query.filter(
                    db.or_(
                        Activity.task_id.ilike(f'%{search}%'),
                        Activity.task_name.ilike(f'%{search}%')
                    )
                )
            
            # Apply status filter
            if status != 'all':
                if status == 'Not Started':
                    activity_query = activity_query.filter(Activity.progress_pct == 0)
                elif status == 'In Progress':
                    activity_query = activity_query.filter(
                        db.and_(Activity.progress_pct > 0, Activity.progress_pct < 100)
                    )
                elif status == 'Completed':
                    activity_query = activity_query.filter(Activity.progress_pct >= 100)
            
            # Order by early start date, then by task_id
            activity_query = activity_query.order_by(Activity.early_start_date.asc(), Activity.task_id.asc())
            
            # Execute paginated query
            activities_paginated = activity_query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            print(f"✅ Found {activities_paginated.total} total activities, showing {len(activities_paginated.items)}")
            
            # STEP 2: Get WBS structure for this schedule
            print("📁 Fetching WBS structure...")
            wbs_items = WBS.query.filter_by(schedule_id=schedule_id).all()
            print(f"✅ Found {len(wbs_items)} WBS items")
            
            # STEP 3: Get project information
            project_info = {
                'project_id': schedule.project.id if schedule.project else None,
                'project_name': schedule.project.name if schedule.project else 'Unknown Project',
                'schedule_name': schedule.name,
                'schedule_id': schedule.id
            }
            
            # STEP 4: Format activities data
            activities_data = []
            for activity in activities_paginated.items:
                activities_data.append({
                    'task_id': activity.task_id,
                    'task_name': activity.task_name or 'Unnamed Activity',
                    'wbs_id': activity.wbs_id or '',
                    'duration_days': float(activity.duration_days) if activity.duration_days else 0,
                    'early_start_date': activity.early_start_date.isoformat() if activity.early_start_date else None,
                    'early_end_date': activity.early_end_date.isoformat() if activity.early_end_date else None,
                    'late_start_date': activity.late_start_date.isoformat() if activity.late_start_date else None,
                    'late_end_date': activity.late_end_date.isoformat() if activity.late_end_date else None,
                    'actual_start_date': activity.actual_start_date.isoformat() if activity.actual_start_date else None,
                    'actual_end_date': activity.actual_end_date.isoformat() if activity.actual_end_date else None,
                    'progress_pct': float(activity.progress_pct) if activity.progress_pct else 0,
                    'total_float_days': float(activity.total_float_days) if activity.total_float_days else 0,
                    'free_float_days': float(activity.free_float_days) if activity.free_float_days else 0,
                    'task_type': activity.task_type,
                    'status_code': activity.status_code
                })
            
            # STEP 5: Format WBS structure data
            wbs_structure = []
            for wbs in wbs_items:
                wbs_structure.append({
                    'wbs_id': wbs.wbs_id,
                    'wbs_name': wbs.wbs_name or f'WBS {wbs.wbs_id}',
                    'parent_wbs_id': wbs.parent_wbs_id,
                    'proj_id': project_info['project_id']  # Add project reference
                })
            
            print(f"📊 Returning: {len(activities_data)} activities, {len(wbs_structure)} WBS items")
            
            return jsonify({
                'success': True,
                'activities': activities_data,
                'wbs_structure': wbs_structure,
                'project_info': project_info,
                'pagination': {
                    'page': activities_paginated.page,
                    'pages': activities_paginated.pages,
                    'per_page': activities_paginated.per_page,
                    'total': activities_paginated.total,
                    'has_next': activities_paginated.has_next,
                    'has_prev': activities_paginated.has_prev
                }
            })
            
        except Exception as e:
            print(f"❌ API Error getting activities: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'activities': [],
                'wbs_structure': [],
                'project_info': {},
                'pagination': {'total': 0}
            }), 500
        
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