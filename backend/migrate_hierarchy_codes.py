# migrate_hierarchy_codes.py
# Run this file to add hierarchy code columns to your existing database

from app import create_app, db
from sqlalchemy import text

def migrate_database_for_hierarchy_codes():
    """
    Add new columns for hierarchy codes to existing database
    """
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Migrating database for hierarchy codes...")
            
            # Add new columns to WBS table
            print("\n📁 Updating WBS table...")
            try:
                db.session.execute(text('ALTER TABLE wbs ADD COLUMN wbs_code VARCHAR(50)'))
                print("   ✅ Added wbs_code to WBS table")
            except Exception as e:
                print(f"   ⚠️ wbs_code column may already exist: {e}")
            
            try:
                db.session.execute(text('ALTER TABLE wbs ADD COLUMN sort_order INTEGER DEFAULT 0'))
                print("   ✅ Added sort_order to WBS table")
            except Exception as e:
                print(f"   ⚠️ sort_order column may already exist: {e}")
            
            # Add new columns to activities table
            print("\n📋 Updating Activities table...")
            try:
                db.session.execute(text('ALTER TABLE activities ADD COLUMN activity_code VARCHAR(50)'))
                print("   ✅ Added activity_code to activities table")
            except Exception as e:
                print(f"   ⚠️ activity_code column may already exist: {e}")
            
            try:
                db.session.execute(text('ALTER TABLE activities ADD COLUMN wbs_code VARCHAR(50)'))
                print("   ✅ Added wbs_code reference to activities table")
            except Exception as e:
                print(f"   ⚠️ wbs_code column may already exist: {e}")
            
            try:
                db.session.execute(text('ALTER TABLE activities ADD COLUMN sort_order INTEGER DEFAULT 0'))
                print("   ✅ Added sort_order to activities table")
            except Exception as e:
                print(f"   ⚠️ sort_order column may already exist: {e}")
            
            # Commit changes
            db.session.commit()
            print("\n✅ Database migration completed successfully!")
            
            # Verify the changes
            inspector = db.inspect(db.engine)
            
            wbs_columns = [col['name'] for col in inspector.get_columns('wbs')]
            activities_columns = [col['name'] for col in inspector.get_columns('activities')]
            
            print("\n📊 Verification:")
            print(f"   WBS columns: {len(wbs_columns)} - {wbs_columns}")
            print(f"   Activities columns: {len(activities_columns)} - {activities_columns}")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration error: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("🚀 Database Migration for Hierarchy Codes")
    print("=" * 50)
    
    if migrate_database_for_hierarchy_codes():
        print("\n✅ Migration completed successfully!")
        print("💡 Next step: Update your models in app.py")
    else:
        print("\n❌ Migration failed - check the errors above")