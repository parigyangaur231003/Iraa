# Weather Feature - Iraa 

Weather functionality has been added to Iraa using SerpAPI!

##  What's Been Added

### 1. **Backend Function** (`serp_api.py`)
- `get_weather(location)` - Fetches weather data from Google via SerpAPI
- Returns: temperature, condition, precipitation, humidity, wind, forecast

### 2. **Voice Assistant** (`agent.py`)
- `action_weather()` - Interactive voice weather checking
- Iraa asks for location and speaks the weather

### 3. **Main App** (`app.py`)
- Weather integrated into conversation flow
- Intent: "weather"

### 4. **API Endpoint** (`api.py`)
- `POST /weather` - RESTful endpoint for weather data

## How to Use

### Voice Interaction (with Iraa):

1. Say: **"Hello assistant"** (wake word)
2. Iraa: "Hello Sir! How can I help you?"
3. Say: **"weather"** or **"what's the weather"**
4. Iraa: "Which location would you like to know the weather for?"
5. Say: **"London"** or **"New York"** or any city
6. Iraa speaks the weather!

### Example Conversation:

```
You: "Hello assistant"
Iraa: "Hello Sir! How can I help you?"

You: "What's the weather?"
Iraa: "Which location would you like to know the weather for?"

You: "New York"
Iraa: "Weather for New York."
Iraa: "Weather in New York:"
Iraa: "Temperature: 72°F."
Iraa: "Condition: Partly cloudy."
Iraa: "Precipitation: 10%."
Iraa: "Humidity: 65%."
Iraa: "Wind: 8 mph."
Iraa: "Forecast:"
Iraa: "Monday: 75°F, Sunny."
Iraa: "Tuesday: 70°F, Cloudy."
```

## API Usage

### Endpoint: `POST /weather`

**Request:**
```json
{
  "location": "London",
  "user_id": "me"
}
```

**Response:**
```json
{
  "location": "London",
  "temperature": "15°C",
  "condition": "Partly cloudy",
  "precipitation": "20%",
  "humidity": "75%",
  "wind": "10 mph",
  "forecast": [
    {
      "day": "Monday",
      "temperature": "16°C",
      "weather": "Sunny"
    },
    {
      "day": "Tuesday",
      "temperature": "14°C",
      "weather": "Cloudy"
    }
  ]
}
```

### Test with curl:
```bash
curl -X POST http://localhost:8000/weather \
  -H "Content-Type: application/json" \
  -d '{"location": "London"}'
```

## Voice Robot Integration

### Arduino/Robot can now ask for weather!

**Option 1: Text Conversation**
```cpp
String response = askIraa("what's the weather in London");
// Response: "Weather in London: 15°C, Partly cloudy."
```

**Option 2: Direct API Call**
```cpp
POST http://your-domain.com/weather
{
  "location": "London"
}
```

**Option 3: Voice-to-Voice** 
```cpp
// User speaks: "what's the weather in London"
// Robot plays Samantha's voice: "Weather in London: 15°C, Partly cloudy"
```

## Supported Intent Keywords

Iraa recognizes these phrases as weather requests:
- "weather"
- "what's the weather"
- "weather in [city]"
- "weather for [city]"
- "how's the weather"
- "temperature"
- "climate"

## Locations Supported

Any location that Google recognizes:
- City names: "London", "New York", "Tokyo"
- With country: "London UK", "Paris France"
- Zip codes: "90210", "10001"
- Neighborhoods: "Manhattan", "Brooklyn"

## Data Provided

### Current Weather:
-  Temperature (°F or °C)
-  Weather condition (Sunny, Cloudy, Rainy, etc.)
-  Precipitation chance (%)
-  Humidity (%)
-  Wind speed (mph or km/h)

### Forecast:
-  Next 3 days
-  Day name
-  Temperature
-  Weather condition

## Requirements

### Environment Variable:
```env
SERP_API_KEY=your_serp_api_key
```

Add this to your `.env` file.

### Get SERP API Key:
1. Go to https://serpapi.com/
2. Sign up for free account
3. Get your API key
4. Add to `.env` file

## Testing

### Test in Python:
```python
from serp_api import get_weather
result = get_weather("London")
print(result)
```

### Test with Iraa:
```bash
pipenv run python app.py
# Say: "hello assistant"
# Say: "weather"
# Say: "London"
```

### Test API:
```bash
pipenv run python api.py
# Visit: http://localhost:8000/docs
# Try the /weather endpoint
```

## Integration with Other Features

Weather works seamlessly with:
-  Voice conversations
-  Text conversations
-  API calls
-  Arduino/Robot integration
-  Telegram (can send weather updates)
-  Email (can include in emails)

### Example: Send weather via Telegram
After getting weather, you can say:
"Send that to Telegram"

### Example: Email weather report
"Email me the weather forecast"

## Advanced Usage

### Weather in conversation endpoint:
```bash
POST /voice/conversation
{
  "text": "what's the weather in Tokyo"
}
```

Response includes weather automatically!

### Weather in voice endpoint:
User speaks: "what's the weather in Tokyo"
Samantha responds with weather information!

## Troubleshooting

### "SerpAPI key is not configured"
**Solution:** Add SERP_API_KEY to your `.env` file

### "I couldn't get weather information"
**Solution:** Check location name spelling, verify API key is valid

### "Weather will be connected next"
**Solution:** Make sure you've restarted the app after adding weather feature

### "No weather information available"
**Solution:** Try a more specific location or popular city name

## Next Steps

1.  Add SERP_API_KEY to `.env`
2.  Restart Iraa: `pipenv run python app.py`
3.  Test: Say "weather" to Iraa
4.  Deploy to Hostinger with updated code
5.  Arduino can now get weather via API!

---

**Weather feature is now live! **
