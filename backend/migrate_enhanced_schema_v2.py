# Create this file: migrate_enhanced_schema_v2.py
# Fixed version that handles PostgreSQL properly

from app import create_app, db
from sqlalchemy import text

def migrate_to_enhanced_schema_v2():
    """
    Fixed migration for PostgreSQL - handles connection properly
    """
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Enhanced Schema Migration V2")
            print("=" * 40)
            
            # Get fresh connection
            connection = db.engine.connect()
            trans = connection.begin()
            
            try:
                # Check database type
                db_url = str(db.engine.url)
                print(f"📊 Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
                
                # Define new columns - only the ones we really need
                new_columns = [
                    ('activity_codes', 'JSONB'),
                    ('udf_values', 'JSONB'), 
                    ('target_start_date', 'TIMESTAMP'),
                    ('target_end_date', 'TIMESTAMP'),
                    ('baseline_end_date', 'TIMESTAMP'),
                    ('remaining_duration', 'FLOAT'),
                    ('original_duration', 'FLOAT'),
                    ('percent_complete', 'FLOAT'),
                    ('resource_names', 'VARCHAR(500)')
                ]
                
                # Check existing columns first
                check_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'activities'
                ORDER BY ordinal_position;
                """
                
                result = connection.execute(text(check_sql))
                existing_columns = [row[0] for row in result.fetchall()]
                
                print(f"📋 Found {len(existing_columns)} existing columns")
                
                # Add new columns
                added_count = 0
                
                for col_name, col_type in new_columns:
                    if col_name not in existing_columns:
                        try:
                            add_sql = f'ALTER TABLE activities ADD COLUMN {col_name} {col_type};'
                            print(f"  🔧 Adding: {col_name} ({col_type})")
                            
                            connection.execute(text(add_sql))
                            added_count += 1
                            print(f"  ✅ Added: {col_name}")
                            
                        except Exception as e:
                            print(f"  ❌ Failed {col_name}: {e}")
                    else:
                        print(f"  ➖ Exists: {col_name}")
                
                # Commit the transaction
                trans.commit()
                print(f"\n✅ Transaction committed: {added_count} columns added")
                
                # Verify with fresh query
                result = connection.execute(text(check_sql))
                final_columns = [row[0] for row in result.fetchall()]
                
                print(f"📊 Total columns after migration: {len(final_columns)}")
                
                # Check for our specific columns
                required_columns = [col[0] for col in new_columns]
                found_columns = [col for col in required_columns if col in final_columns]
                missing_columns = [col for col in required_columns if col not in final_columns]
                
                print(f"✅ Found enhanced columns: {found_columns}")
                if missing_columns:
                    print(f"❌ Still missing: {missing_columns}")
                    return False
                else:
                    print(f"🎉 All enhanced columns successfully added!")
                    return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Transaction error: {e}")
                return False
            finally:
                connection.close()
                
        except Exception as e:
            print(f"❌ Migration error: {e}")
            return False

def update_activity_model_in_app():
    """
    Instructions for updating the Activity model
    """
    print("\n📝 NEXT STEP: Update Activity Model in app.py")
    print("=" * 50)
    print("You need to update your Activity model in app.py to include these fields:")
    print()
    
    model_additions = """
    # Add these lines to your Activity model in app.py:
    
    # NEW: Enhanced data fields (JSON columns)
    activity_codes = db.Column(db.JSON)                        
    udf_values = db.Column(db.JSON)                            
    
    # NEW: Enhanced date fields from XER
    target_start_date = db.Column(db.DateTime)                 
    target_end_date = db.Column(db.DateTime)                   
    baseline_end_date = db.Column(db.DateTime)                 
    
    # NEW: Additional duration and progress fields
    remaining_duration = db.Column(db.Float, default=0)        
    original_duration = db.Column(db.Float, default=0)         
    percent_complete = db.Column(db.Float, default=0)          
    
    # NEW: Resource field
    resource_names = db.Column(db.String(500))                 
    """
    
    print(model_additions)
    print("\nAlso update the to_dict() method to include these new fields.")

def test_database_columns():
    """
    Test if columns are accessible
    """
    app = create_app()
    
    with app.app_context():
        try:
            print("\n🧪 Testing Database Columns")
            print("=" * 30)
            
            connection = db.engine.connect()
            
            # Test each new column
            test_columns = [
                'activity_codes', 'udf_values', 'target_start_date',
                'target_end_date', 'remaining_duration', 'resource_names'
            ]
            
            for col in test_columns:
                try:
                    test_sql = f"SELECT {col} FROM activities LIMIT 1;"
                    connection.execute(text(test_sql))
                    print(f"  ✅ {col} - accessible")
                except Exception as e:
                    print(f"  ❌ {col} - error: {e}")
            
            connection.close()
            
        except Exception as e:
            print(f"❌ Test error: {e}")

if __name__ == "__main__":
    print("🚀 Enhanced Schema Migration V2 (Fixed)")
    print("=" * 50)
    
    # Run the migration
    success = migrate_to_enhanced_schema_v2()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ DATABASE MIGRATION SUCCESSFUL!")
        print("=" * 50)
        
        # Test the columns
        test_database_columns()
        
        # Show next steps
        update_activity_model_in_app()
        
        print("\n🎯 NEXT STEPS:")
        print("1. Update your Activity model in app.py (see above)")
        print("2. Update your parse_xer_file function in app.py")
        print("3. Run: python test_enhanced_processing.py")
        
    else:
        print("\n❌ Migration failed - check errors above")