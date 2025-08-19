from app import create_app, db
from sqlalchemy import text

def init_database():
    """Initialize the database with all tables"""
    
    # Create the Flask app
    app = create_app()
    
    with app.app_context():
        try:
            # Import models from app (they're defined inline now)
            from app import Project, Schedule, Activity, Relationship, WBS, AssessmentResult
            
            # Instead of dropping all tables, let's create only new ones
            print("🔨 Creating database tables...")
            
            # Check what tables exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            print(f"📋 Existing tables: {existing_tables}")
            
            # For development, we'll drop CASCADE to handle dependencies
            if existing_tables:
                print("🗑️  Dropping existing tables with CASCADE...")
                try:
                    # Drop tables in reverse dependency order
                    tables_to_drop = [
                        'assessment_results',
                        'activity_relationships',  # This seems to exist
                        'relationships', 
                        'activities',
                        'wbs',
                        'schedules',
                        'projects'
                    ]
                    
                    for table in tables_to_drop:
                        if table in existing_tables:
                            db.session.execute(text(f'DROP TABLE IF EXISTS {table} CASCADE'))
                            print(f"   Dropped {table}")
                    
                    db.session.commit()
                    
                except Exception as drop_error:
                    print(f"⚠️  Drop error (continuing): {drop_error}")
                    db.session.rollback()
            
            print("🔨 Creating new tables...")
            db.create_all()
            
            # List created tables
            inspector = db.inspect(db.engine)
            new_tables = inspector.get_table_names()
            print("✅ Database tables created:")
            for table in sorted(new_tables):
                print(f"   - {table}")
            
            # Create sample data
            existing_projects = Project.query.count()
            
            if existing_projects == 0:
                sample_project = Project(
                    name="Sample Construction Project",
                    description="Example project for testing schedule analysis",
                    created_by="system"
                )
                
                db.session.add(sample_project)
                db.session.commit()
                
                print("✅ Sample project created")
            else:
                print(f"ℹ️  Found {existing_projects} existing projects")
                
            # Test the connection
            total_projects = Project.query.count()
            total_schedules = Schedule.query.count()
            total_activities = Activity.query.count()
            total_relationships = Relationship.query.count()
            
            print(f"📊 Database status:")
            print(f"   Projects: {total_projects}")
            print(f"   Schedules: {total_schedules}")
            print(f"   Activities: {total_activities}")
            print(f"   Relationships: {total_relationships}")
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    print("🚀 Database Initialization")
    print("=" * 35)
    
    if init_database():
        print("\n✅ Database initialization completed!")
        print("💡 You can now run: python run.py")
    else:
        print("\n❌ Database initialization failed")