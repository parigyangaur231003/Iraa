# location_utils.py
"""
Location tracking and detection utilities for Iraa.
Provides IP-based geolocation and user location management.
"""
import requests
import os
from typing import Optional, Dict

def get_location_from_ip() -> Optional[Dict[str, str]]:
    """
    Get location information based on IP address using free geolocation service.
    
    Returns:
        Dict with keys: city, region, country, latitude, longitude
        None if location cannot be determined
    """
    try:
        # Try multiple free geolocation services
        services = [
            "http://ip-api.com/json/",  # Free, no API key needed
            "https://ipapi.co/json/",    # Free, no API key needed
        ]
        
        for service_url in services:
            try:
                print(f"[location] Trying geolocation service: {service_url}")
                response = requests.get(service_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse based on service
                    if "ip-api.com" in service_url:
                        if data.get("status") == "success":
                            location = {
                                "city": data.get("city", "Unknown"),
                                "region": data.get("regionName", "Unknown"),
                                "country": data.get("country", "Unknown"),
                                "latitude": str(data.get("lat", "")),
                                "longitude": str(data.get("lon", "")),
                                "zip": data.get("zip", ""),
                                "timezone": data.get("timezone", "")
                            }
                            print(f"[location] Detected location: {location['city']}, {location['country']}")
                            return location
                    
                    elif "ipapi.co" in service_url:
                        if "error" not in data:
                            location = {
                                "city": data.get("city", "Unknown"),
                                "region": data.get("region", "Unknown"),
                                "country": data.get("country_name", "Unknown"),
                                "latitude": str(data.get("latitude", "")),
                                "longitude": str(data.get("longitude", "")),
                                "zip": data.get("postal", ""),
                                "timezone": data.get("timezone", "")
                            }
                            print(f"[location] Detected location: {location['city']}, {location['country']}")
                            return location
                            
            except Exception as e:
                print(f"[location] Service failed: {service_url} - {e}")
                continue
        
        print("[location] All geolocation services failed")
        return None
        
    except Exception as e:
        print(f"[location] Error getting location from IP: {e}")
        return None

def save_user_location(user_id: str, city: str, region: str = "", country: str = "", 
                       latitude: float = None, longitude: float = None, 
                       timezone: str = "", zip_code: str = "") -> bool:
    """
    Save user's preferred location to database.
    
    Args:
        user_id: User identifier
        city: City name
        region: Region/state (optional)
        country: Country name (optional)
        latitude: Latitude (optional)
        longitude: Longitude (optional)
        timezone: Timezone (optional)
        zip_code: ZIP/postal code (optional)
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        from db import save_user_location as db_save_location
        db_save_location(user_id, city, region, country, latitude, longitude, timezone, zip_code)
        print(f"[location] Saved location for {user_id}: {city}")
        return True
        
    except Exception as e:
        print(f"[location] Error saving location: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_user_location(user_id: str) -> Optional[Dict[str, str]]:
    """
    Get user's saved location from database.
    
    Args:
        user_id: User identifier
    
    Returns:
        Dict with location info or None
    """
    try:
        from db import get_user_location as db_get_location
        return db_get_location(user_id)
    except Exception as e:
        print(f"[location] Error reading location: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_current_location(user_id: str) -> str:
    """
    Get current location for user. Checks saved location first, then tries IP-based detection.
    
    Args:
        user_id: User identifier
    
    Returns:
        City name string, or "Unknown" if cannot determine
    """
    try:
        # First, check if user has a saved location
        saved_location = get_user_location(user_id)
        if saved_location:
            city = saved_location.get("city", "")
            if city:
                print(f"[location] Using saved location: {city}")
                return city
        
        # If no saved location, try IP-based detection
        detected_location = get_location_from_ip()
        if detected_location:
            city = detected_location.get("city", "Unknown")
            
            # Auto-save the detected location with full details for future use
            save_user_location(
                user_id,
                city,
                detected_location.get("region", ""),
                detected_location.get("country", ""),
                float(detected_location.get("latitude", 0)) if detected_location.get("latitude") else None,
                float(detected_location.get("longitude", 0)) if detected_location.get("longitude") else None,
                detected_location.get("timezone", ""),
                detected_location.get("zip", "")
            )
            
            return city
        
        return "Unknown"
        
    except Exception as e:
        print(f"[location] Error getting current location: {e}")
        import traceback
        traceback.print_exc()
        return "Unknown"

def set_default_location(user_id: str, city: str) -> bool:
    """
    Set user's default location.
    
    Args:
        user_id: User identifier
        city: City name to set as default
    
    Returns:
        True if successful
    """
    return save_user_location(user_id, city)

# Test function
if __name__ == "__main__":
    print("Testing location detection...")
    
    # Test IP-based location
    location = get_location_from_ip()
    if location:
        print(f"Your location: {location['city']}, {location['country']}")
    else:
        print("Could not detect location")
    
    # Test saving location
    save_user_location("test_user", "New York", "NY", "USA")
    
    # Test reading location
    saved = get_user_location("test_user")
    print(f"Saved location: {saved}")
    
    # Test getting current location
    current = get_current_location("test_user")
    print(f"Current location: {current}")
