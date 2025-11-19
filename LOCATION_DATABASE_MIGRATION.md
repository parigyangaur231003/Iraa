# Location Database Migration - Summary

## What Changed?

User location data is now stored in MySQL database instead of JSON file.

---

## Files Modified:

### 1. **schema.sql**
Added new `user_location` table:
```sql
CREATE TABLE user_location (
    user_id VARCHAR(255) PRIMARY KEY,
    city VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    country VARCHAR(255),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    timezone VARCHAR(100),
    zip VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 2. **db.py**
Added two new functions:
- `save_user_location()` - Save/update user location
- `get_user_location()` - Retrieve user location

### 3. **location_utils.py**
Updated to use database functions instead of JSON file:
- Removed JSON file dependency
- Now calls `db.save_user_location()` and `db.get_user_location()`
- Saves full location details (latitude, longitude, timezone, etc.)

### 4. **agent.py**
Updated `action_weather()` to:
- Automatically detect user location when no city is mentioned
- No longer asks "which location?" if detection succeeds
- Only prompts for city if auto-detection fails

### 5. **LOCATION_TRACKING.md**
Updated documentation to reflect database storage

---

## New Files:

### 1. **migrate_location_table.py**
Migration script to create the `user_location` table in existing database.

Run with:
```bash
pipenv run python migrate_location_table.py
```

---

## Benefits of Database Storage:

 **Persistent** - Data survives across deployments  
 **Scalable** - Handles multiple users efficiently  
 **Structured** - Proper data types and constraints  
 **Queryable** - Can run SQL queries on location data  
 **Backup-friendly** - Included in database backups  
 **No file conflicts** - No JSON file locking issues  

---

## Migration Steps (Already Completed):

1.  Updated `schema.sql` with new table
2.  Added database functions to `db.py`
3.  Updated `location_utils.py` to use database
4.  Created migration script `migrate_location_table.py`
5.  Ran migration successfully
6.  Tested location detection and storage
7.  Updated documentation

---

## Database Schema Details:

```sql
CREATE TABLE user_location (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Fields:**
- `user_id` - Primary key, identifies the user
- `city` - Required field, city name
- `region` - Optional, state/province
- `country` - Optional, country name
- `latitude` - Optional, decimal coordinates
- `longitude` - Optional, decimal coordinates
- `timezone` - Optional, IANA timezone
- `zip` - Optional, postal/zip code
- `created_at` - Auto-generated timestamp
- `updated_at` - Auto-updated on changes

---

## Testing:

### Verify Table Creation:
```bash
pipenv run python -c "from db import conn; c = conn(); cur = c.cursor(); cur.execute('SHOW TABLES LIKE \"user_location\"'); print(' Table exists' if cur.fetchone() else ' Table not found'); c.close()"
```

### Test Location Detection:
```bash
pipenv run python location_utils.py
```

### Check Stored Data:
```sql
SELECT * FROM user_location;
```

---

## API Integration:

The existing API endpoints in `api.py` already work with the database:

- `GET /location/current?user_id=me` - Get saved location
- `POST /location/set` - Save location manually
- `GET /location/detect` - Detect via IP

---

## Weather Integration:

Now when user says **"weather"** without mentioning a city:

1.  Iraa checks database for saved location
2.  If found, uses that city automatically
3.  If not found, detects via IP
4.  Saves detected location to database
5.  Returns weather for that location

**No more asking "which location?"** 

---

## Data Migration from JSON (If Needed):

If you had existing `.location_cache.json` data:

```python
import json
from db import save_user_location

# Read old JSON cache
with open('.location_cache.json', 'r') as f:
    cache = json.load(f)

# Migrate to database
for user_id, data in cache.items():
    save_user_location(
        user_id=user_id,
        city=data['city'],
        region=data.get('region', ''),
        country=data.get('country', '')
    )
    print(f"Migrated {user_id}: {data['city']}")
```

---

## Cleanup:

You can now safely delete:
- `.location_cache.json` (if it exists)
- No longer needed after database migration

---

## Database Maintenance:

### View all locations:
```sql
SELECT user_id, city, region, country, updated_at 
FROM user_location 
ORDER BY updated_at DESC;
```

### Clear old locations:
```sql
DELETE FROM user_location 
WHERE updated_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### Update location:
```sql
UPDATE user_location 
SET city = 'Mumbai', region = 'Maharashtra', country = 'India'
WHERE user_id = 'me';
```

---

## Summary:

 **user_location** table created in MySQL  
 Location data now stored in database  
 Auto-detection working perfectly  
 Weather works without asking for city  
 All API endpoints functional  
 Documentation updated  

**Location tracking is now production-ready with database storage!** 
