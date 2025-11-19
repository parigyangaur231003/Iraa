"""SerpAPI integration for Google Flights, News, and Stocks."""
import os
import requests
from typing import Dict, List, Optional

SERP_API_KEY = os.getenv("SERP_API_KEY")
SERP_API_URL = "https://serpapi.com/search"

def _make_request(params: Dict) -> Optional[Dict]:
    """Make a request to SerpAPI."""
    if not SERP_API_KEY:
        raise RuntimeError("SERP_API_KEY is not set in environment variables. Please add it to your .env file.")
    
    params["api_key"] = SERP_API_KEY
    
    # Debug: print the request URL (without API key for security)
    debug_params = {k: v for k, v in params.items() if k != "api_key"}
    print(f"[serp_api] Request params: {debug_params}")
    
    try:
        response = requests.get(SERP_API_URL, params=params, timeout=30)
        
        # If we get an error, capture the full error response
        if not response.ok:
            error_text = response.text
            print(f"[serp_api] Error response: {error_text[:500]}")
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_detail = error_json.get("error", "Unknown error")
                    raise RuntimeError(f"SerpAPI error: {error_detail}")
            except:
                pass
            response.raise_for_status()
        
        return response.json()
    except requests.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.text
                print(f"[serp_api] Full error response: {error_body}")
            except:
                pass
        raise RuntimeError(f"SerpAPI request failed: {error_msg}")

def _normalize_location(location: str) -> str:
    """Normalize location input to airport code or city name for SerpAPI."""
    location = location.strip().upper()
    
    # Common city to airport code mapping
    city_to_airport = {
        "JAIPUR": "JAI", "DELHI": "DEL", "MUMBAI": "BOM", "BANGALORE": "BLR",
        "BENGALURU": "BLR", "CHENNAI": "MAA", "KOLKATA": "CCU", "HYDERABAD": "HYD",
        "PUNE": "PNQ", "AHMEDABAD": "AMD", "GOA": "GOI", "KOCHI": "COK",
        "NEW YORK": "JFK", "NEWYORK": "JFK", "LOS ANGELES": "LAX", "LOSANGELES": "LAX",
        "CHICAGO": "ORD", "LONDON": "LHR", "PARIS": "CDG", "TOKYO": "NRT",
        "DUBAI": "DXB", "SINGAPORE": "SIN", "BANGKOK": "BKK", "HONG KONG": "HKG",
        "SYDNEY": "SYD", "MELBOURNE": "MEL", "TORONTO": "YYZ", "VANCOUVER": "YVR"
    }
    
    # Check if it's already an airport code (3-4 letters)
    if len(location) <= 4 and location.isalpha():
        return location
    
    # Try to find airport code for city name
    if location in city_to_airport:
        return city_to_airport[location]
    
    # If no mapping found, return original (SerpAPI might handle it)
    return location

def get_flight_info(origin: str, destination: str, date: Optional[str] = None) -> Dict:
    """
    Get flight information from Google Flights.
    
    Args:
        origin: Origin airport code or city name
        destination: Destination airport code or city name
        date: Departure date (YYYY-MM-DD format, optional)
    
    Returns:
        Dict with flight information
    """
    # Normalize locations to airport codes
    origin_code = _normalize_location(origin)
    dest_code = _normalize_location(destination)
    
    # SerpAPI Google Flights API format
    # Must use departure_id and arrival_id with valid airport codes (3-letter IATA codes)
    # The codes must be valid IATA airport codes
    
    params = {
        "engine": "google_flights",
        "departure_id": origin_code,
        "arrival_id": dest_code,
        "hl": "en",
        "gl": "us"
    }
    
    if date:
        # Date must be in YYYY-MM-DD format
        params["outbound_date"] = date
    
    print(f"[serp_api] Flight search: {origin} ({origin_code}) -> {destination} ({dest_code}), date: {date}")
    print(f"[serp_api] Request params (debug): engine=google_flights, departure_id={origin_code}, arrival_id={dest_code}, outbound_date={date}")
    
    # First try without date (sometimes date causes 400 errors)
    params_no_date = {k: v for k, v in params.items() if k != "outbound_date"}
    
    try:
        # Try without date first
        result = _make_request(params_no_date)
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[serp_api] Request without date failed: {error_msg}")
        
        # If that fails, try with date if provided
        if date and ("400" in error_msg or "Bad Request" in error_msg):
            try:
                print(f"[serp_api] Retrying with date parameter...")
                result = _make_request(params)
            except RuntimeError as e2:
                error_msg2 = str(e2)
                print(f"[serp_api] Request with date also failed: {error_msg2}")
                error_detail = (
                    f"SerpAPI Google Flights API returned 400 Bad Request. "
                    f"Tried airport codes: '{origin_code}' (from {origin}) and '{dest_code}' (from {destination}). "
                    f"This could mean: (1) These airport codes aren't recognized by SerpAPI, "
                    f"(2) Your SerpAPI account doesn't have access to Google Flights, "
                    f"(3) The API format has changed. "
                    f"Error: {error_msg2}"
                )
                raise RuntimeError(error_detail)
        else:
            # If it's not a 400, or if we don't have a date, raise original error
            if "400" in error_msg:
                error_detail = (
                    f"SerpAPI returned 400 Bad Request with airport codes '{origin_code}' and '{dest_code}'. "
                    f"This usually indicates invalid airport codes or API access issues."
                )
                raise RuntimeError(error_detail)
            raise
    
    if not result:
        return {"error": "No flight information available"}
    
    # Check for errors in response
    if "error" in result:
        return {"error": result.get("error", "Unknown error from SerpAPI")}
    
    # Parse flight results - SerpAPI Google Flights returns data in various formats
    flights = []
    
    # Try different response structures
    if "flights" in result:
        for flight in result.get("flights", [])[:5]:
            if isinstance(flight, dict):
                flight_info = {
                    "airline": flight.get("airline", "Unknown"),
                    "departure_time": flight.get("departure_airport", {}).get("time", "N/A") if isinstance(flight.get("departure_airport"), dict) else "N/A",
                    "arrival_time": flight.get("arrival_airport", {}).get("time", "N/A") if isinstance(flight.get("arrival_airport"), dict) else "N/A",
                    "duration": flight.get("duration", "N/A"),
                    "price": flight.get("price", flight.get("total_price", "N/A")),
                    "stops": flight.get("stops", flight.get("number_of_stops", 0))
                }
                flights.append(flight_info)
    
    # Also check best_flights array
    best_flights = result.get("best_flights", [])
    if best_flights and not flights:
        for best in best_flights[:5]:
            if isinstance(best, dict):
                if "flights" in best:
                    # Extract from nested flights array
                    for leg in best.get("flights", []):
                        if isinstance(leg, dict):
                            flight_info = {
                                "airline": leg.get("airline", "Unknown"),
                                "departure_time": "N/A",
                                "arrival_time": "N/A",
                                "duration": leg.get("duration", best.get("total_duration", "N/A")),
                                "price": best.get("price", best.get("total_price", "N/A")),
                                "stops": best.get("stops", best.get("number_of_stops", 0))
                            }
                            flights.append(flight_info)
                else:
                    # Direct flight info
                    flight_info = {
                        "airline": best.get("airline", "Unknown"),
                        "departure_time": "N/A",
                        "arrival_time": "N/A",
                        "duration": best.get("duration", best.get("total_duration", "N/A")),
                        "price": best.get("price", best.get("total_price", "N/A")),
                        "stops": best.get("stops", best.get("number_of_stops", 0))
                    }
                    flights.append(flight_info)
    
    return {
        "origin": origin_code,
        "destination": dest_code,
        "date": date,
        "flights": flights,
        "best_flights": best_flights[:3] if best_flights else []
    }

def get_news(query: str, num_results: int = 5) -> Dict:
    """
    Get news from Google News.
    
    Args:
        query: News search query
        num_results: Number of results to return (default: 5)
    
    Returns:
        Dict with news articles
    """
    params = {
        "engine": "google_news",
        "q": query,
        "hl": "en",
        "gl": "us",
        "num": num_results
    }
    
    print(f"[serp_api] News search: query='{query}', num_results={num_results}")
    print(f"[serp_api] Request params (debug): engine=google_news, q={query}")
    
    try:
        result = _make_request(params)
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[serp_api] News API error: {error_msg}")
        
        # If Google News fails, try regular Google search as fallback
        if "400" in error_msg or "Bad Request" in error_msg:
            print(f"[serp_api] Trying fallback with Google search engine...")
            try:
                params_fallback = {
                    "engine": "google",
                    "q": f"{query} news",
                    "hl": "en",
                    "gl": "us",
                    "num": num_results
                }
                result = _make_request(params_fallback)
                print(f"[serp_api] Fallback Google search succeeded!")
            except RuntimeError as e2:
                error_msg2 = str(e2)
                error_detail = (
                    f"SerpAPI News search failed with both google_news and google engines. "
                    f"Query: '{query}'. "
                    f"Error: {error_msg2}. "
                    f"This might indicate an API configuration issue or invalid query format."
                )
                raise RuntimeError(error_detail)
        else:
            raise
    
    if not result:
        return {"error": "No news available"}
    
    # Check for errors in response
    if "error" in result:
        return {"error": result.get("error", "Unknown error from SerpAPI")}
    
    articles = []
    
    # Try news_results first (google_news format)
    if "news_results" in result:
        for article in result.get("news_results", [])[:num_results]:
            if isinstance(article, dict):
                article_info = {
                    "title": article.get("title", "No title"),
                    "source": article.get("source", "Unknown"),
                    "date": article.get("date", "Unknown date"),
                    "snippet": article.get("snippet", article.get("description", "No description")),
                    "link": article.get("link", "")
                }
                articles.append(article_info)
    
    # If no news_results, try organic_results from Google search
    if not articles and "organic_results" in result:
        for item in result.get("organic_results", [])[:num_results]:
            if isinstance(item, dict):
                article_info = {
                    "title": item.get("title", "No title"),
                    "source": item.get("source", "Unknown"),
                    "date": item.get("date", "Unknown date"),
                    "snippet": item.get("snippet", item.get("description", "No description")),
                    "link": item.get("link", "")
                }
                articles.append(article_info)
    
    return {
        "query": query,
        "articles": articles
    }

def get_weather(location: str) -> Dict:
    """
    Get weather information for a location using Google search.
    
    Args:
        location: City name, zip code, or location (e.g., "New York", "London", "90210")
    
    Returns:
        Dict with weather information
    """
    location = location.strip()
    
    params = {
        "engine": "google",
        "q": f"weather {location}",
        "hl": "en",
        "gl": "us"
    }
    
    print(f"[serp_api] Weather search: location='{location}'")
    print(f"[serp_api] Request params (debug): engine=google, q=weather {location}")
    
    try:
        result = _make_request(params)
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[serp_api] Weather API error: {error_msg}")
        raise RuntimeError(f"Weather search failed for '{location}'. Error: {error_msg}")
    
    if not result:
        return {"error": "No weather information available"}
    
    # Check for errors in response
    if "error" in result:
        return {"error": result.get("error", "Unknown error from SerpAPI")}
    
    # Parse weather data from Google's answer box
    weather_data = {
        "location": location,
        "temperature": "N/A",
        "condition": "N/A",
        "precipitation": "N/A",
        "humidity": "N/A",
        "wind": "N/A",
        "forecast": []
    }
    
    # Try to extract from answer_box (Google's weather widget)
    if "answer_box" in result:
        answer = result["answer_box"]
        
        # Current weather
        weather_data["temperature"] = answer.get("temperature", "N/A")
        weather_data["condition"] = answer.get("weather", answer.get("title", "N/A"))
        weather_data["precipitation"] = answer.get("precipitation", "N/A")
        weather_data["humidity"] = answer.get("humidity", "N/A")
        weather_data["wind"] = answer.get("wind", "N/A")
        
        # Location name from result
        if "location" in answer:
            weather_data["location"] = answer["location"]
        
        # Forecast
        if "forecast" in answer:
            for day in answer.get("forecast", [])[:3]:  # Next 3 days
                if isinstance(day, dict):
                    forecast_info = {
                        "day": day.get("day", "N/A"),
                        "temperature": day.get("temperature", "N/A"),
                        "weather": day.get("weather", "N/A")
                    }
                    weather_data["forecast"].append(forecast_info)
    
    # Alternative: Try knowledge_graph for location-based weather
    elif "knowledge_graph" in result:
        kg = result["knowledge_graph"]
        if "weather" in kg:
            weather = kg["weather"]
            weather_data["temperature"] = weather.get("temperature", "N/A")
            weather_data["condition"] = weather.get("weather", "N/A")
            weather_data["precipitation"] = weather.get("precipitation", "N/A")
            weather_data["humidity"] = weather.get("humidity", "N/A")
            weather_data["wind"] = weather.get("wind", "N/A")
    
    return weather_data

def get_stock_info(symbol: str) -> Dict:
    """
    Get stock information.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL", "GOOGL", "MSFT")
    
    Returns:
        Dict with stock information
    """
    symbol = symbol.upper().strip()
    
    params = {
        "engine": "google_finance",
        "q": symbol,
        "hl": "en"
    }
    
    print(f"[serp_api] Stock search: symbol='{symbol}'")
    print(f"[serp_api] Request params (debug): engine=google_finance, q={symbol}")
    
    try:
        result = _make_request(params)
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[serp_api] Stock API error: {error_msg}")
        
        # If Google Finance fails, try regular Google search as fallback
        if "400" in error_msg or "Bad Request" in error_msg:
            print(f"[serp_api] Trying fallback with Google search engine...")
            try:
                params_fallback = {
                    "engine": "google",
                    "q": f"{symbol} stock price",
                    "hl": "en",
                    "gl": "us"
                }
                result = _make_request(params_fallback)
                print(f"[serp_api] Fallback Google search succeeded!")
            except RuntimeError as e2:
                error_msg2 = str(e2)
                error_detail = (
                    f"SerpAPI Stock search failed with both google_finance and google engines. "
                    f"Symbol: '{symbol}'. "
                    f"Error: {error_msg2}. "
                    f"This might indicate an API configuration issue or invalid stock symbol."
                )
                raise RuntimeError(error_detail)
        else:
            raise
    
    if not result:
        return {"error": "No stock information available"}
    
    # Check for errors in response
    if "error" in result:
        return {"error": result.get("error", "Unknown error from SerpAPI")}
    
    # Parse stock data - try multiple response structures
    stock_info = {
        "symbol": symbol,
        "name": "Unknown",
        "price": "N/A",
        "change": "N/A",
        "change_percent": "N/A",
        "market_cap": "N/A",
        "volume": "N/A"
    }
    
    # Extract from google_finance format
    if "title" in result:
        stock_info["name"] = result.get("title", "Unknown")
    if "price" in result:
        stock_info["price"] = result.get("price", "N/A")
    if "price_movement" in result:
        movement = result.get("price_movement", {})
        if isinstance(movement, dict):
            stock_info["change"] = movement.get("percentage", movement.get("change", "N/A"))
    
    # Try to get more details from stock_data
    if "stock_data" in result:
        stock_data = result.get("stock_data", {})
        if isinstance(stock_data, dict):
            stock_info.update({
                "name": stock_data.get("name", stock_data.get("title", stock_info["name"])),
                "price": stock_data.get("price", stock_info["price"]),
                "change": stock_data.get("change", stock_info["change"]),
                "change_percent": stock_data.get("change_percent", stock_data.get("percentage", stock_info["change_percent"])),
                "market_cap": stock_data.get("market_cap", stock_info["market_cap"]),
                "volume": stock_data.get("volume", stock_info["volume"])
            })
    
    # Fallback: Try to extract from organic_results if using Google search
    if stock_info["price"] == "N/A" and "organic_results" in result:
        for item in result.get("organic_results", []):
            if isinstance(item, dict):
                snippet = item.get("snippet", "")
                # Try to extract price from snippet
                import re
                price_match = re.search(r'\$?(\d+\.?\d*)', snippet)
                if price_match:
                    stock_info["price"] = f"${price_match.group(1)}"
                break
    
    return stock_info

