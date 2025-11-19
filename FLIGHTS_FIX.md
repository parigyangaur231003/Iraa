# SerpAPI Google Flights 400 Error Fix

## Issue
The SerpAPI Google Flights API is returning 400 Bad Request errors when using `departure_id` and `arrival_id` parameters.

## Possible Causes
1. **Airport Code Format**: SerpAPI may require specific airport ID formats, not just IATA codes
2. **API Changes**: SerpAPI's Google Flights API format may have changed
3. **Date Format**: The date format might need to be different
4. **Parameter Requirements**: Some required parameters might be missing

## Testing Steps
1. Test with a known working airport code combination (e.g., JFK to LAX)
2. Try without the date parameter first
3. Check if SerpAPI account has proper access to Google Flights API
4. Verify API key has sufficient credits/quota

## Temporary Workaround
Since SerpAPI Google Flights is having issues, consider:
- Using a direct Google Flights web search instead
- Implementing a simpler fallback that just tells the user to check Google Flights
- Using a different flight API service

## Current Implementation
The code now:
- Normalizes city names to airport codes (Jaipur → JAI, Delhi → DEL)
- Uses `departure_id` and `arrival_id` parameters
- Tries multiple fallback formats
- Provides detailed error messages

## Next Steps
1. Test the API directly with curl to see the exact error format
2. Check SerpAPI documentation for latest parameter requirements
3. Consider alternative flight data sources if SerpAPI continues to have issues

