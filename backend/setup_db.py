import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import Config

def setup_database():
    """Setup PostgreSQL database"""
    
    config = Config()
    
    # Check if we're using PostgreSQL
    if 'postgresql' not in config.SQLALCHEMY_DATABASE_URI:
        print("ℹ️  Using SQLite - no setup needed")
        return True
    
    print("🐘 Setting up PostgreSQL database...")
    print(f"📍 Host: {config.DB_HOST}:{config.DB_PORT}")
    print(f"👤 User: {config.DB_USER}")
    print(f"🗄️  Database: {config.DB_NAME}")
    
    try:
        # Connect to PostgreSQL server (not to specific database)
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database='postgres'  # Connect to default postgres database
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (config.DB_NAME,))
        exists = cursor.fetchone()
        
        if exists:
            print(f"✅ Database '{config.DB_NAME}' already exists")
        else:
            # Create database
            cursor.execute(f'CREATE DATABASE "{config.DB_NAME}"')
            print(f"✅ Created database '{config.DB_NAME}'")
        
        cursor.close()
        conn.close()
        
        # Test connection to new database
        test_conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        test_conn.close()
        
        print("✅ Database connection successful!")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL Error: {e}")
        print("\n💡 Common fixes:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Check your password in .env file")
        print("   3. Verify PostgreSQL is listening on port 5432")
        print("   4. Try connecting with pgAdmin first")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Database Setup")
    print("=" * 30)
    
    if setup_database():
        print("\n✅ Ready to initialize tables!")
        print("💡 Next steps:")
        print("   1. python setup_db.py  ← (you are here)")
        print("   2. python init_db.py")
        print("   3. python run.py")
    else:
        print("\n❌ Setup failed - check your PostgreSQL connection")