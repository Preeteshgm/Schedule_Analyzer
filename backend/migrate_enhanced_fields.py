# migrate_enhanced_fields_fixed.py
from app import create_app, db
from sqlalchemy import text

def migrate_enhanced_fields_fixed():
    """Add enhanced P6 fields to existing database - PostgreSQL compatible"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Adding enhanced P6 fields to activities table (PostgreSQL)...")
            
            # PostgreSQL-compatible column definitions
            new_columns = [
                ('baseline_start_date', 'TIMESTAMP'),
                ('baseline_finish_date', 'TIMESTAMP'),
                ('constraint_type', 'VARCHAR(50)'),
                ('constraint_date', 'TIMESTAMP'),
                ('calendar_id', 'VARCHAR(50)'),
                ('cost_account', 'VARCHAR(100)'),
                ('responsible_manager', 'VARCHAR(100)'),
                ('priority_type', 'INTEGER'),
                ('suspend_date', 'TIMESTAMP'),
                ('resume_date', 'TIMESTAMP'),
                ('additional_data', 'JSONB')  # Using JSONB for better performance
            ]
            
            for column_name, column_type in new_columns:
                try:
                    # Check if column exists first
                    check_query = text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='activities' AND column_name=:column_name
                    """)
                    result = db.session.execute(check_query, {'column_name': column_name}).fetchone()
                    
                    if result is None:
                        # Column doesn't exist, add it
                        add_query = text(f'ALTER TABLE activities ADD COLUMN {column_name} {column_type}')
                        db.session.execute(add_query)
                        db.session.commit()  # Commit each column individually
                        print(f"   ✅ Added {column_name} ({column_type})")
                    else:
                        print(f"   ⚪ {column_name} already exists, skipping")
                        
                except Exception as e:
                    print(f"   ❌ Error adding {column_name}: {e}")
                    db.session.rollback()  # Rollback just this column
                    continue
            
            print("✅ Enhanced fields migration completed!")
            
            # Verify the columns were added
            print("\n🔍 Verifying new columns...")
            verify_query = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name='activities' 
                AND column_name IN ('baseline_start_date', 'baseline_finish_date', 'constraint_type', 
                                   'constraint_date', 'calendar_id', 'cost_account', 'responsible_manager', 
                                   'priority_type', 'suspend_date', 'resume_date', 'additional_data')
                ORDER BY column_name
            """)
            
            results = db.session.execute(verify_query).fetchall()
            
            if results:
                print("   New columns found:")
                for row in results:
                    print(f"     - {row[0]} ({row[1]})")
            else:
                print("   ⚠️ No new columns found - check for errors above")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration error: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    migrate_enhanced_fields_fixed()