#!/usr/bin/env python3
"""
Migration script to add user_location table to Iraa database.
Run this after updating schema.sql to add the location tracking feature.
"""
import sys
from db import conn

def migrate():
    """Add user_location table to database."""
    try:
        with conn() as c:
            cur = c.cursor()
            
            # Check if table already exists
            cur.execute("SHOW TABLES LIKE 'user_location'")
            if cur.fetchone():
                print(" user_location table already exists")
                return True
            
            # Create the table
            print("Creating user_location table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_location (
                    user_id VARCHAR(255) NOT NULL PRIMARY KEY,
                    city VARCHAR(255) NOT NULL,
                    region VARCHAR(255),
                    country VARCHAR(255),
                    latitude DECIMAL(10, 7),
                    longitude DECIMAL(10, 7),
                    timezone VARCHAR(100),
                    zip VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_city (city)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            c.commit()
            
            print(" user_location table created successfully!")
            return True
            
    except Exception as e:
        print(f" Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Iraa Location Tracking Migration")
    print("=" * 60)
    print()
    
    success = migrate()
    
    print()
    if success:
        print(" Migration completed successfully!")
        print()
        print("Next steps:")
        print("  1. Test location detection: python3 location_utils.py")
        print("  2. Run Iraa and try: 'what is my location'")
        print("  3. Try weather without city: 'weather'")
        sys.exit(0)
    else:
        print(" Migration failed!")
        print("Please check the error above and try again.")
        sys.exit(1)
