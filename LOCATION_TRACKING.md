# Location Tracking Feature 

Iraa can now track your location automatically for weather and location-based services!

---

## Features

###  Automatic Location Detection
- **IP-based geolocation** - Automatically detects your city from your IP address
- **No GPS required** - Works on any device with internet
- **Free services** - Uses free geolocation APIs (ip-api.com, ipapi.co)

###  Location Management
- **Save location** - Set your preferred city manually
- **Auto-save** - Automatically saves detected location
- **Persistent storage** - Location saved in `.location_cache.json`

###  Smart Weather Integration
- **Auto-weather** - Say "weather" without city name
- **My location** - Say "weather at my location"
- **Fallback** - Always asks if location can't be detected

---

## How It Works

### Initial Detection:
```
1. Iraa detects your IP address
2. Queries free geolocation service
3. Gets your city/region/country
4. Saves it automatically
5. Uses it for future queries
```

**Your location detected:** Jaipur, India 

---

## Usage Examples

### 1. Weather with Auto-Location

**Without location tracking:**
```
You: "Weather"
Iraa: "Which location would you like to know the weather for?"
You: "Jaipur"
Iraa: [weather report]
```

**With location tracking:**
```
You: "Weather"
Iraa: "Which location would you like to know the weather for? You can say a city name or say 'my location' for your current location."
You: "My location"
Iraa: "Using your location: Jaipur."
Iraa: [weather report for Jaipur automatically!]
```

**Even better - direct query:**
```
You: "What's the weather" (no city mentioned)
Iraa: [detects you're in Jaipur]
Iraa: "Sure sir, the weather in Jaipur: [weather report]"
```

### 2. Set Your Location Manually

```
You: "Set my location"
Iraa: "What city should I set as your location?"
You: "Delhi"
Iraa: "Location set to Delhi. What else can I help you with?"
```

### 3. Check Your Location

```
You: "What is my location"
Iraa: "Your location is set to Jaipur. What else can I do for you?"
```

---

## Voice Commands

### Location Management:
-  **"Set my location"** - Set preferred city
-  **"Set location"** - Same as above
-  **"What is my location"** - Check saved location
-  **"Where am I"** - Check saved location

### Weather with Location:
-  **"Weather"** → then **"my location"**
-  **"Weather at my location"**
-  **"Weather here"**
-  **"Current location weather"**

---

## API Endpoints

### 1. Get Current Location
```bash
GET /location/current?user_id=me
```

**Response:**
```json
{
  "user_id": "me",
  "city": "Jaipur",
  "details": {
    "city": "Jaipur",
    "region": "Rajasthan",
    "country": "India",
    "saved_at": "..."
  },
  "status": "detected"
}
```

### 2. Set Location
```bash
POST /location/set
{
  "city": "Delhi",
  "user_id": "me"
}
```

**Response:**
```json
{
  "user_id": "me",
  "city": "Delhi",
  "status": "saved"
}
```

### 3. Detect Location (IP-based)
```bash
GET /location/detect
```

**Response:**
```json
{
  "city": "Jaipur",
  "region": "Rajasthan",
  "country": "India",
  "latitude": "26.9124",
  "longitude": "75.7873",
  "zip": "302001",
  "timezone": "Asia/Kolkata"
}
```

---

## Arduino/Robot Integration

### Automatic Weather for Robot Location:

```cpp
// Option 1: Get location first, then weather
String location = getLocation();  // Detects: "Jaipur"
String weather = getWeather(location);

// Option 2: Just ask for weather
String response = askIraa("weather at my location");
// Iraa automatically uses robot's location!
```

### Set Robot Location:
```cpp
// Set once during setup
setLocation("Jaipur");

// Then all weather queries use Jaipur
String weather = askIraa("weather");
// Returns: Weather in Jaipur
```

---

## Technical Details

### Files Created:
1. **`location_utils.py`** - Location detection and management
2. **`migrate_location_table.py`** - Database migration script

### Services Used:
- **ip-api.com** - Free IP geolocation (primary)
- **ipapi.co** - Free IP geolocation (fallback)

### Storage:
Stored in MySQL `user_location` table:
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

### Privacy:
-  No GPS tracking
-  Only uses IP address
-  Stored in your database
-  Can be manually set
-  Can be cleared anytime

---

## Flow Diagram

```
┌─────────────┐
│    USER     │ "Weather"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    IRAA     │ Checks location cache
└──────┬──────┘
       │
       ├─ YES → Use saved location
       │         "Weather in Jaipur"
       │
       └─ NO  → Detect from IP
                ├─ Success → "Weather in Jaipur"
                │            Save for next time
                │
                └─ Fail   → Ask user for city
```

---

## Benefits

### For Users:
 **No repetition** - Don't say city every time
 **Automatic** - Detects once, uses forever
 **Flexible** - Can override anytime
 **Fast** - No extra questions

### For Robots:
 **Context-aware** - Knows where it is
 **Smart weather** - Automatic local weather
 **Less interaction** - Fewer prompts
 **Better UX** - More intelligent behavior

### For API:
 **Location context** - Available for all endpoints
 **User profiles** - Per-user location storage
 **Scalable** - Handles multiple users

---

## Database Setup

Before using location tracking, you need to create the `user_location` table:

```bash
# Run the migration script
pipenv run python migrate_location_table.py
```

**Expected output:**
```
============================================================
Iraa Location Tracking Migration
============================================================

Creating user_location table...
 user_location table created successfully!

 Migration completed successfully!
```

Alternatively, run the full schema:
```bash
mysql -u root -p iraa_db < schema.sql
```

---

## Testing

### Test Location Detection:
```bash
python3 location_utils.py
```

**Expected output:**
```
Testing location detection...
[location] Detected location: Jaipur, India
Your location: Jaipur, India
```

### Test with Iraa:
```bash
pipenv run python app.py

# Say: "hello assistant"
# Say: "what is my location"
# Expected: "Your location is set to Jaipur"

# Say: "weather"
# Say: "my location"
# Expected: Automatic weather for Jaipur!
```

### Test API:
```bash
# Detect location
curl http://localhost:8000/location/detect

# Get current location
curl http://localhost:8000/location/current?user_id=me

# Set location
curl -X POST http://localhost:8000/location/set \
  -H "Content-Type: application/json" \
  -d '{"city":"Delhi","user_id":"me"}'
```

---

## Configuration

### Default Location:
Set via voice command or API, stored in `.location_cache.json`

### Manual Override:
```python
from location_utils import set_default_location
set_default_location("me", "Mumbai")
```

### Clear Location:
```sql
DELETE FROM user_location WHERE user_id = 'your_user_id';
```

Or via Python:
```python
from db import conn
with conn() as c:
    c.cursor().execute("DELETE FROM user_location WHERE user_id=%s", ('me',))
    c.commit()
```

---

## Troubleshooting

### "I couldn't detect your location"
**Cause:** Geolocation services unavailable
**Solution:** Set location manually with "set my location"

### Wrong location detected
**Cause:** IP-based location not accurate
**Solution:** Say "set my location" and specify correct city

### Location not persisting
**Cause:** `.location_cache.json` not writable
**Solution:** Check file permissions

---

## Future Enhancements

1. **GPS Integration** - Use actual GPS coordinates
2. **Multiple Locations** - Home, office, etc.
3. **Location History** - Track location changes
4. **Timezone Handling** - Auto-adjust time based on location
5. **Local News** - Automatic local news
6. **Nearby Services** - Find restaurants, etc.

---

## Privacy & Security

### What We Store:
- City name
- Region/State (optional)
- Country (optional)
- Timestamp of save

### What We Don't Store:
-  Exact coordinates
-  Street address
-  GPS data
-  Personal information

### How to Delete:
```sql
-- Delete specific user location
DELETE FROM user_location WHERE user_id = 'your_user_id';

-- Delete all location data
TRUNCATE TABLE user_location;
```

---

## Example Scenarios

### Scenario 1: First Time User
```
User: "Weather"
[Iraa detects IP → Jaipur]
Iraa: "Weather in Jaipur: 28°C, Sunny"
[Saves Jaipur for future]
```

### Scenario 2: Returning User
```
User: "Weather"
[Iraa reads saved location: Jaipur]
Iraa: "Weather in Jaipur: 30°C, Cloudy"
[No detection needed!]
```

### Scenario 3: Traveling User
```
User: "Set my location"
Iraa: "What city?"
User: "Mumbai"
Iraa: "Location set to Mumbai"

User: "Weather"
[Uses Mumbai now]
Iraa: "Weather in Mumbai: 32°C, Humid"
```

---

**Your Iraa now knows where you are! **

No more repeating your city for every weather query!
