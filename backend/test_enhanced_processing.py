# Create this file: test_enhanced_processing.py
# Use this to test your enhanced XER processing

import os
import sys
from app import create_app, db, Project, Schedule

def test_enhanced_parsing():
    """
    Test the enhanced XER parsing functionality
    """
    app = create_app()
    
    with app.app_context():
        try:
            print("🧪 Testing Enhanced XER Processing")
            print("=" * 50)
            
            # Step 1: Test raw parser directly
            print("\n📋 Step 1: Testing Raw XER Parser...")
            
            # You'll need to provide a path to an actual XER file for testing
            test_xer_file = input("Enter path to test XER file (or press Enter to skip): ").strip()
            
            if test_xer_file and os.path.exists(test_xer_file):
                from core.raw_xer_parser import RawXERParser
                
                parser = RawXERParser(test_xer_file)
                tables = parser.parse_file()
                
                if tables:
                    print(f"✅ Raw parser extracted {len(tables)} tables")
                    print(f"📊 Activity codes: {len(parser.activity_codes)} activities")
                    print(f"📋 UDFs: {len(parser.udf_mapping)} records")
                    
                    # Show table summary
                    for table_name, df in tables.items():
                        print(f"  - {table_name}: {len(df)} records")
                else:
                    print("❌ Raw parser failed to extract tables")
                    return False
            else:
                print("⏭️ Skipping raw parser test (no file provided)")
            
            # Step 2: Test database integration
            print("\n💾 Step 2: Testing Database Integration...")
            
            # Check if enhanced columns exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('activities')]
            
            enhanced_columns = [
                'activity_codes', 'udf_values', 'target_start_date', 
                'target_end_date', 'remaining_duration', 'resource_names'
            ]
            
            missing_columns = [col for col in enhanced_columns if col not in existing_columns]
            
            if missing_columns:
                print(f"❌ Missing columns: {missing_columns}")
                print("Run the migration script first: python migrate_enhanced_schema.py")
                return False
            else:
                print("✅ All enhanced columns present in database")
            
            # Step 3: Test file processor
            print("\n📁 Step 3: Testing File Processor...")
            
            from core.file_processor import create_file_processor
            
            processor = create_file_processor('uploads')
            
            if test_xer_file and os.path.exists(test_xer_file):
                valid, message = processor.validate_file(test_xer_file)
                print(f"File validation: {valid} - {message}")
                
                if valid:
                    file_info = processor.get_file_info(test_xer_file)
                    print(f"File size: {file_info.get('file_size_mb', 0):.2f} MB")
            
            # Step 4: Test data mapper
            print("\n🗺️ Step 4: Testing Data Mapper...")
            
            from core.xer_data_mapper import create_xer_data_mapper, validate_db_models
            
            db_models = {
                'db': db,
                'Activity': __import__('app').Activity,
                'WBS': __import__('app').WBS,
                'Relationship': __import__('app').Relationship,
                'Schedule': __import__('app').Schedule
            }
            
            if validate_db_models(db_models):
                print("✅ Database models validation passed")
                
                mapper = create_xer_data_mapper(db_models)
                print("✅ Data mapper created successfully")
            else:
                print("❌ Database models validation failed")
                return False
            
            # Step 5: Test full integration (if test file provided)
            if test_xer_file and os.path.exists(test_xer_file):
                print("\n🚀 Step 5: Testing Full Integration...")
                
                # Create test project and schedule
                test_project = Project(
                    name=f"Test Project - Enhanced Processing",
                    description="Testing enhanced XER processing",
                    created_by="test_script"
                )
                
                db.session.add(test_project)
                db.session.commit()
                
                test_schedule = Schedule(
                    name=f"Test Schedule - {os.path.basename(test_xer_file)}",
                    description="Testing enhanced XER processing",
                    project_id=test_project.id,
                    created_by="test_script",
                    status="parsing"
                )
                
                db.session.add(test_schedule)
                db.session.commit()
                
                print(f"Created test schedule ID: {test_schedule.id}")
                
                # Test the enhanced parsing function
                from app import parse_xer_file
                
                success, message, stats = parse_xer_file(test_xer_file, test_schedule.id)
                
                if success:
                    print(f"✅ Full integration test passed!")
                    print(f"📊 Results: {message}")
                    print(f"📈 Stats:")
                    for key, value in stats.items():
                        print(f"  - {key}: {value}")
                    
                    # Check what was actually saved
                    from app import Activity, WBS, Relationship
                    
                    activities_count = Activity.query.filter_by(schedule_id=test_schedule.id).count()
                    wbs_count = WBS.query.filter_by(schedule_id=test_schedule.id).count()
                    rel_count = Relationship.query.filter_by(schedule_id=test_schedule.id).count()
                    
                    print(f"\n📊 Database Verification:")
                    print(f"  - Activities saved: {activities_count}")
                    print(f"  - WBS items saved: {wbs_count}")
                    print(f"  - Relationships saved: {rel_count}")
                    
                    # Check for activity codes and UDFs
                    activities_with_codes = Activity.query.filter_by(schedule_id=test_schedule.id).filter(Activity.activity_codes.isnot(None)).count()
                    activities_with_udfs = Activity.query.filter_by(schedule_id=test_schedule.id).filter(Activity.udf_values.isnot(None)).count()
                    
                    print(f"  - Activities with codes: {activities_with_codes}")
                    print(f"  - Activities with UDFs: {activities_with_udfs}")
                    
                    # Clean up test data
                    cleanup = input("\nDelete test data? (y/n): ").strip().lower()
                    if cleanup == 'y':
                        db.session.delete(test_schedule)
                        db.session.delete(test_project)
                        db.session.commit()
                        print("🗑️ Test data cleaned up")
                    
                else:
                    print(f"❌ Full integration test failed: {message}")
                    return False
            
            print("\n🎉 All tests completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_api_endpoints():
    """
    Test API endpoints (requires running Flask app)
    """
    print("\n🌐 Testing API Endpoints...")
    print("Make sure your Flask app is running on http://localhost:5000")
    
    try:
        import requests
        
        # Test health endpoint
        response = requests.get("http://localhost:5000/api/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print("❌ Health endpoint failed")
            return False
        
        # Test debug endpoint
        response = requests.get("http://localhost:5000/api/debug")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Debug endpoint: {data.get('project_count', 0)} projects")
        else:
            print("❌ Debug endpoint failed")
        
        return True
        
    except ImportError:
        print("⚠️ requests library not installed - skipping API tests")
        print("Install with: pip install requests")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def show_implementation_status():
    """
    Show current implementation status
    """
    print("\n📊 Implementation Status Check")
    print("=" * 40)
    
    # Check if files exist
    files_to_check = [
        'core/raw_xer_parser.py',
        'core/file_processor.py', 
        'core/xer_data_mapper.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - Missing!")
    
    # Check app.py integration
    try:
        from core.file_processor import create_file_processor
        from core.xer_data_mapper import create_xer_data_mapper
        print("✅ Core modules import successfully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
    
    # Check if enhanced Activity model is in use
    try:
        from app import Activity
        activity_columns = Activity.__table__.columns.keys()
        enhanced_columns = ['activity_codes', 'udf_values', 'target_start_date']
        
        if all(col in activity_columns for col in enhanced_columns):
            print("✅ Enhanced Activity model detected")
        else:
            print("❌ Activity model not enhanced yet")
            print("Update your Activity model in app.py")
    except Exception as e:
        print(f"⚠️ Could not check Activity model: {e}")

if __name__ == "__main__":
    print("🚀 Enhanced XER Processing Test Suite")
    print("=" * 50)
    
    # Show implementation status first
    show_implementation_status()
    
    # Run main tests
    test_choice = input("\nRun full test suite? (y/n): ").strip().lower()
    
    if test_choice == 'y':
        success = test_enhanced_parsing()
        
        if success:
            # Test API endpoints if requested
            api_test = input("\nTest API endpoints? (requires running Flask app) (y/n): ").strip().lower()
            if api_test == 'y':
                test_api_endpoints()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 Enhanced XER processing is ready to use!")
            print("\nNext steps:")
            print("1. Update your React frontend to display activity codes")
            print("2. Test with your actual XER files")
            print("3. Enjoy the enhanced functionality!")
        else:
            print("❌ Some issues detected - check the output above")
    else:
        print("Test skipped - use this script when ready to test")