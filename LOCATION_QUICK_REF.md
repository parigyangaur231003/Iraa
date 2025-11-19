# Location Tracking - Quick Reference

## Setup (One-time)

```bash
# Run migration to create table
pipenv run python migrate_location_table.py
```

---

## User Commands

| Voice Command | Result |
|--------------|--------|
| "weather" | Auto-detects location, returns weather |
| "weather in Delhi" | Returns weather for Delhi |
| "what is my location" | Tells current saved location |
| "set my location" | Prompts for city, saves it |

---

## Database Functions

```python
from db import save_user_location, get_user_location

# Save location
save_user_location(
    user_id="me",
    city="Jaipur",
    region="Rajasthan",
    country="India",
    latitude=26.9124,
    longitude=75.7873,
    timezone="Asia/Kolkata",
    zip_code="302001"
)

# Get location
location = get_user_location("me")
# Returns: {'user_id': 'me', 'city': 'Jaipur', ...}
```

---

## Location Utils

```python
from location_utils import get_current_location, get_location_from_ip

# Get user's current location (from DB or auto-detect)
city = get_current_location("me")  # Returns: "Jaipur"

# Detect location from IP
location_data = get_location_from_ip()
# Returns: {'city': 'Jaipur', 'region': 'Rajasthan', 'country': 'India', ...}
```

---

## SQL Queries

```sql
-- View all locations
SELECT * FROM user_location;

-- Get specific user location
SELECT * FROM user_location WHERE user_id = 'me';

-- Update location
UPDATE user_location 
SET city = 'Mumbai' 
WHERE user_id = 'me';

-- Delete location
DELETE FROM user_location WHERE user_id = 'me';
```

---

## API Endpoints

```bash
# Get current location
curl http://localhost:8000/location/current?user_id=me

# Set location
curl -X POST http://localhost:8000/location/set \
  -H "Content-Type: application/json" \
  -d '{"city":"Delhi","user_id":"me"}'

# Detect via IP
curl http://localhost:8000/location/detect
```

---

## Weather Flow

```
User: "weather"
  ↓
1. Check DB for saved location
  ↓ (not found)
2. Detect via IP → "Jaipur"
  ↓
3. Save to DB
  ↓
4. Return weather for Jaipur
```

---

## Table Schema

```sql
user_location (
    user_id VARCHAR(255) PRIMARY KEY,
    city VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    country VARCHAR(255),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    timezone VARCHAR(100),
    zip VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

---

## Testing

```bash
# Test detection
pipenv run python location_utils.py

# Verify table
pipenv run python -c "from db import get_user_location; print(get_user_location('test_user'))"

# Check database
mysql -u root -p iraa_db -e "SELECT * FROM user_location"
```

---

## Benefits

 No JSON files  
 Database-backed  
 Auto-detection  
 No repeated questions  
 Coordinates stored  
 Multi-user support  

---

**Now Iraa remembers where you are!** 
