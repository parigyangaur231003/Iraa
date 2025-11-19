# api.py
"""
FastAPI application for Iraa - AI Voice Assistant
Provides RESTful API endpoints for all Iraa functionalities
"""
import os
import re
import sys
from typing import Optional, Dict, List, Callable
from datetime import datetime
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

# Add current directory to path for imports
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Import Iraa services
from agent import detect_intent, handle_smalltalk, handle_personal_status, handle_question
from google_meet import create_instant_meet
from google_calendar import create_event, iso_in_tz
from google_gmail import send_email, list_recent
from services_telegram import send_message, read_messages
from services_email import draft_email
from jokes import tell_joke
from time_utils import greeting
from db import (
    log_chat,
    save_email,
    save_telegram,
    save_flight,
    save_news,
    save_stock,
    get_chat_history,
    delete_chat_history,
)
from google_oauth import connected_email

try:
    from services_pdf import create_and_send_pdf_via_telegram, create_llm_pdf_and_send_via_telegram
except Exception:
    create_and_send_pdf_via_telegram = None
    create_llm_pdf_and_send_via_telegram = None

try:
    from services_spotify import (
        search_tracks,
        open_track,
        describe_track,
        pause_playback,
        resume_playback,
        next_track,
        is_playing,
        SpotifyApiError,
        SpotifyAuthError,
        SpotifyPlaybackError,
    )
except Exception:
    search_tracks = None
    open_track = None
    describe_track = None
    pause_playback = None
    resume_playback = None
    next_track = None
    is_playing = None
    SpotifyApiError = Exception
    SpotifyAuthError = Exception
    SpotifyPlaybackError = Exception

try:
    from services_calls import call_me as call_me_service
except Exception:
    call_me_service = None

try:
    from llm_groq import complete
except Exception:
    complete = None

try:
    from serp_api import get_flight_info, get_news, get_stock_info, get_weather
except Exception:
    get_flight_info = None
    get_news = None
    get_stock_info = None
    get_weather = None

# Initialize FastAPI app
app = FastAPI(
    title="Iraa AI Assistant API",
    description="RESTful API for Iraa - Your AI-powered voice assistant",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_ID = "me"

# ========== Pydantic Models ==========

class TextRequest(BaseModel):
    text: str = Field(..., description="Input text")
    user_id: Optional[str] = Field(default="me", description="User ID")

class EmailRequest(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    user_id: Optional[str] = Field(default="me", description="User ID")

class EmailDraftRequest(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    purpose: str = Field(..., description="Purpose of the email")
    user_id: Optional[str] = Field(default="me", description="User ID")

class MeetingRequest(BaseModel):
    title: str = Field(default="Instant Meeting", description="Meeting title")
    user_id: Optional[str] = Field(default="me", description="User ID")

class EventRequest(BaseModel):
    title: str = Field(..., description="Event title")
    start: str = Field(..., description="Start time (natural language or ISO format)")
    end: str = Field(..., description="End time (natural language or ISO format)")
    user_id: Optional[str] = Field(default="me", description="User ID")

class TelegramRequest(BaseModel):
    message: str = Field(..., description="Message to send")
    chat_id: Optional[str] = Field(default=None, description="Telegram chat ID")

class FlightRequest(BaseModel):
    origin: str = Field(..., description="Origin city or airport code")
    destination: str = Field(..., description="Destination city or airport code")
    date: Optional[str] = Field(default=None, description="Travel date (YYYY-MM-DD)")
    user_id: Optional[str] = Field(default="me", description="User ID")

class NewsRequest(BaseModel):
    query: str = Field(..., description="News search query")
    num_results: Optional[int] = Field(default=5, description="Number of results")
    user_id: Optional[str] = Field(default="me", description="User ID")

class StockRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, GOOGL)")
    user_id: Optional[str] = Field(default="me", description="User ID")

class WeatherRequest(BaseModel):
    location: str = Field(..., description="Location (city name, zip code, etc.)")
    user_id: Optional[str] = Field(default="me", description="User ID")

class LocationRequest(BaseModel):
    city: str = Field(..., description="City name")
    user_id: Optional[str] = Field(default="me", description="User ID")

class QuestionRequest(BaseModel):
    question: str = Field(..., description="Question to ask")
    user_id: Optional[str] = Field(default="me", description="User ID")

class ChatHistoryDeleteRequest(BaseModel):
    user_id: Optional[str] = Field(default="me", description="User ID")
    role: Optional[str] = Field(default=None, description="Filter by role (user/assistant)")
    contains: Optional[str] = Field(default=None, description="Keyword filter")
    before: Optional[datetime] = Field(default=None, description="Delete entries created before this timestamp")

class PDFInstructionRequest(BaseModel):
    instruction: str = Field(..., description="Instruction for the PDF content")
    filename: Optional[str] = Field(default="document.pdf", description="Filename to use for the PDF")
    caption: Optional[str] = Field(default=None, description="Optional caption to include on Telegram")
    chat_id: Optional[str] = Field(default=None, description="Override Telegram chat ID")
    temperature: Optional[float] = Field(default=0.4, ge=0.0, le=1.0, description="LLM creativity level")

class PDFTextRequest(BaseModel):
    text: str = Field(..., description="Plain text content for the PDF")
    filename: Optional[str] = Field(default="document.pdf", description="Filename to use for the PDF")
    caption: Optional[str] = Field(default=None, description="Optional caption to include on Telegram")
    chat_id: Optional[str] = Field(default=None, description="Override Telegram chat ID")

class SpotifySearchRequest(BaseModel):
    query: str = Field(..., description="Track, artist, or album to search for")
    limit: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum number of tracks to return")

class SpotifyPlayRequest(BaseModel):
    track_url: str = Field(..., description="Spotify track URL to open")
    name: Optional[str] = Field(default=None, description="Track name (for logging only)")
    artists: Optional[str] = Field(default=None, description="Track artist names")
    album: Optional[str] = Field(default=None, description="Album name")

class CallRequest(BaseModel):
    user_id: Optional[str] = Field(default="me", description="User ID for logging")
    note: Optional[str] = Field(default=None, description="Optional context for the call request")

# ========== Helper Utilities ==========

def _collect_agent_output(handler: Callable, *args) -> str:
    """Capture speech-style output from agent handlers as plain text."""
    collected: List[str] = []
    def _collector(message: str):
        if not message:
            return
        msg = message.strip()
        if msg:
            collected.append(msg)
    handler(_collector, *args)  # type: ignore[misc]
    return " ".join(collected).strip()

def _answer_question_text(question: str, require_llm: bool = True) -> str:
    """Run the agent's question handler and capture its response."""
    if not complete:
        if require_llm:
            raise HTTPException(status_code=503, detail="LLM service not available")
        return "I'm sorry, sir. The AI assistant is not available right now. Please check your configuration."
    return _collect_agent_output(handle_question, question)

def _weather_response(user_text: str) -> str:
    """Attempt to answer a weather prompt inline."""
    if not get_weather:
        return "Weather service is unavailable right now."
    match = re.search(r"(?:in|for|at)\s+([\w\s]+?)(?:\s+weather|$)", user_text or "", re.IGNORECASE)
    if match:
        location = match.group(1).strip()
        if location:
            try:
                weather_result = get_weather(location)
                temp = weather_result.get("temperature", "N/A")
                condition = weather_result.get("condition", "N/A")
                return f"Weather in {location}: {temp}, {condition}."
            except Exception:
                pass
    return "I can check the weather for you. Please specify the location."

def _resolve_conversation_response(intent: str, user_text: str, allow_llm_fallback: bool = True) -> str:
    """Build a natural response for casual intents detected via API endpoints."""
    try:
        if intent == "smalltalk":
            return _collect_agent_output(handle_smalltalk, user_text)
        if intent == "personal_status":
            return _collect_agent_output(handle_personal_status, user_text)
        if intent == "ask_time":
            now = datetime.now()
            return f"It's {now.strftime('%I:%M %p')} right now, sir."
        if intent == "joke":
            try:
                return tell_joke()
            except Exception:
                return "Why do programmers prefer dark mode? Because light attracts bugs."
        if intent == "weather":
            return _weather_response(user_text)
        if intent == "question":
            require_llm = not allow_llm_fallback
            return _answer_question_text(user_text, require_llm=require_llm)
        return f"I detected a {intent} request. This requires additional parameters via specific endpoints."
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[api] conversational response error: {exc}")
        return "I ran into an error while generating that response. Please try again."

# ========== Health & Info Endpoints ==========

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Iraa AI Assistant API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "health": "/health",
            "greeting": "/greeting",
            "intent": "/intent",
            "email": "/email/*",
            "meetings": "/meeting/*",
            "calendar": "/calendar/*",
            "telegram": "/telegram/*",
            "flights": "/flights",
            "news": "/news",
            "stocks": "/stock",
            "joke": "/joke",
            "question": "/question"
        }
    }

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve a blank favicon to avoid browser 404 logs."""
    return Response(content=b"", media_type="image/x-icon")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "llm": complete is not None,
            "serp_api": get_flight_info is not None
        }
    }

@app.get("/greeting")
async def get_greeting():
    """Get time-appropriate greeting"""
    return {
        "greeting": greeting(),
        "timestamp": datetime.now().isoformat()
    }

# ========== Intent Detection ==========

@app.post("/intent")
async def detect_user_intent(request: TextRequest):
    """Detect intent from user text"""
    try:
        intent = detect_intent(request.text)
        log_chat(request.user_id, "user", request.text)
        return {
            "text": request.text,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Email Endpoints ==========

@app.post("/email/draft")
async def create_email_draft(request: EmailDraftRequest):
    """Create an email draft"""
    try:
        subject, body = draft_email(request.to_email, request.purpose)
        return {
            "to": request.to_email,
            "subject": subject,
            "body": body,
            "status": "draft_created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/email/send")
async def send_email_endpoint(request: EmailRequest):
    """Send an email via Gmail"""
    try:
        # Check if Google is connected
        email = connected_email(request.user_id)
        if not email:
            raise HTTPException(status_code=401, detail="Google account not connected")
        
        result = send_email(request.user_id, request.to_email, request.subject, request.body)
        
        # Save to database
        try:
            save_email(request.user_id, request.to_email, request.subject, request.body, "sent")
        except Exception as db_err:
            print(f"[api] Could not save email to DB: {db_err}")
        
        return {
            "status": "sent",
            "to": request.to_email,
            "subject": request.subject,
            "message_id": result.get("id") if isinstance(result, dict) else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/email/list")
async def list_emails(user_id: str = "me", max_results: int = 10):
    """List recent emails"""
    try:
        # Check if Google is connected
        email = connected_email(user_id)
        if not email:
            raise HTTPException(status_code=401, detail="Google account not connected")
        
        emails = list_recent(user_id, max_results=max_results)
        return {
            "emails": emails,
            "count": len(emails)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Meeting Endpoints ==========

@app.post("/meeting/instant")
async def create_instant_meeting(request: MeetingRequest):
    """Create an instant Google Meet"""
    try:
        # Check if Google is connected
        email = connected_email(request.user_id)
        if not email:
            raise HTTPException(status_code=401, detail="Google account not connected")
        
        link = create_instant_meet(request.user_id, request.title)
        
        # Automatically send to Telegram if configured
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        telegram_sent = False
        
        if bot_token and chat_id and chat_id != "your_telegram_chat_id":
            try:
                result = send_message(f"Instant Meeting Link:\n{link}")
                telegram_sent = result.get("ok", False)
            except Exception as telegram_err:
                print(f"[api] Telegram send error: {telegram_err}")
        
        return {
            "status": "created",
            "title": request.title,
            "link": link,
            "telegram_sent": telegram_sent
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Calendar Endpoints ==========

@app.post("/calendar/event")
async def create_calendar_event(request: EventRequest):
    """Create a calendar event"""
    try:
        # Check if Google is connected
        email = connected_email(request.user_id)
        if not email:
            raise HTTPException(status_code=401, detail="Google account not connected")
        
        # Parse times
        start_iso = iso_in_tz(request.start)
        end_iso = iso_in_tz(request.end)
        
        event = create_event(request.user_id, request.title, start_iso, end_iso)
        
        return {
            "status": "created",
            "event_id": event.get("id"),
            "title": request.title,
            "start": start_iso,
            "end": end_iso,
            "link": event.get("htmlLink"),
            "meet_link": event.get("hangoutLink")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Telegram Endpoints ==========

@app.post("/telegram/send")
async def send_telegram_message(request: TelegramRequest):
    """Send a message via Telegram"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=401, detail="Telegram bot token not configured")
        
        result = send_message(request.message, request.chat_id)
        
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("description", "Failed to send message"))
        
        return {
            "status": "sent",
            "message": request.message,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/telegram/messages")
async def get_telegram_messages(limit: int = 10):
    """Get recent Telegram messages"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=401, detail="Telegram bot token not configured")
        
        messages = read_messages(limit=limit)
        return {
            "messages": messages,
            "count": len(messages)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Flight Endpoints ==========

@app.post("/flights")
async def search_flights(request: FlightRequest):
    """Search for flights"""
    if not get_flight_info:
        raise HTTPException(status_code=503, detail="Flight search service not available")
    
    try:
        result = get_flight_info(request.origin, request.destination, request.date)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Save to database
        try:
            flights = result.get("flights", [])
            for flight in flights[:5]:
                airline = flight.get("airline", "Unknown")
                price = str(flight.get("price", "N/A"))
                duration = str(flight.get("duration", "N/A"))
                stops = flight.get("stops", 0)
                save_flight(
                    request.user_id,
                    result.get("origin", request.origin),
                    result.get("destination", request.destination),
                    request.date,
                    airline,
                    price,
                    duration,
                    stops
                )
        except Exception as db_err:
            print(f"[api] Could not save flights to DB: {db_err}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== News Endpoints ==========

@app.post("/news")
async def search_news(request: NewsRequest):
    """Search for news articles"""
    if not get_news:
        raise HTTPException(status_code=503, detail="News search service not available")
    
    try:
        result = get_news(request.query, num_results=request.num_results)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Save to database
        try:
            articles = result.get("articles", [])
            for article in articles:
                title = article.get("title", "No title")
                source = article.get("source", "")
                
                # Extract clean source name
                if isinstance(source, dict):
                    source_name = str(source.get("name") or source.get("title") or "Unknown source").strip()
                else:
                    source_name = str(source) if source else "Unknown source"
                
                snippet = article.get("snippet", "")
                link = article.get("link", "")
                save_news(request.user_id, request.query, title, source_name, snippet, link)
        except Exception as db_err:
            print(f"[api] Could not save news to DB: {db_err}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Stock Endpoints ==========

@app.post("/stock")
async def get_stock_information(request: StockRequest):
    """Get stock information"""
    if not get_stock_info:
        raise HTTPException(status_code=503, detail="Stock information service not available")
    
    try:
        result = get_stock_info(request.symbol)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Save to database
        try:
            symbol = result.get("symbol", request.symbol)
            name = result.get("name", "Unknown")
            price = str(result.get("price", "N/A"))
            change = str(result.get("change", "N/A"))
            change_percent = str(result.get("change_percent", "N/A"))
            market_cap = str(result.get("market_cap", "N/A"))
            volume = str(result.get("volume", "N/A"))
            save_stock(request.user_id, symbol, name, price, change, change_percent, market_cap, volume)
        except Exception as db_err:
            print(f"[api] Could not save stock to DB: {db_err}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Weather Endpoints ==========

@app.post("/weather")
async def get_weather_information(request: WeatherRequest):
    """Get weather information for a location"""
    if not get_weather:
        raise HTTPException(status_code=503, detail="Weather service not available")
    
    try:
        result = get_weather(request.location)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "location": result.get("location", request.location),
            "temperature": result.get("temperature", "N/A"),
            "condition": result.get("condition", "N/A"),
            "precipitation": result.get("precipitation", "N/A"),
            "humidity": result.get("humidity", "N/A"),
            "wind": result.get("wind", "N/A"),
            "forecast": result.get("forecast", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Location Endpoints ==========

@app.get("/location/current")
async def get_user_current_location(user_id: str = "me"):
    """Get user's current/saved location"""
    try:
        from location_utils import get_current_location, get_user_location
        
        city = get_current_location(user_id)
        location_details = get_user_location(user_id)
        
        return {
            "user_id": user_id,
            "city": city,
            "details": location_details,
            "status": "detected" if city != "Unknown" else "unknown"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/location/set")
async def set_user_location(request: LocationRequest):
    """Set user's default location"""
    try:
        from location_utils import set_default_location
        
        success = set_default_location(request.user_id, request.city)
        
        if success:
            return {
                "user_id": request.user_id,
                "city": request.city,
                "status": "saved"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save location")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/location/detect")
async def detect_location():
    """Detect location from IP address"""
    try:
        from location_utils import get_location_from_ip
        
        location = get_location_from_ip()
        
        if location:
            return location
        else:
            raise HTTPException(status_code=404, detail="Could not detect location")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== PDF Endpoints ==========

@app.post("/pdf/llm")
async def create_pdf_via_llm(request: PDFInstructionRequest):
    """Generate a PDF with LLM text and send it to Telegram."""
    if not create_llm_pdf_and_send_via_telegram:
        raise HTTPException(status_code=503, detail="PDF generation service not available")
    
    try:
        filename = (request.filename or "document.pdf").strip() or "document.pdf"
        temperature = request.temperature if request.temperature is not None else 0.4
        result = create_llm_pdf_and_send_via_telegram(  # type: ignore[misc]
            instruction=request.instruction,
            filename=filename,
            caption=request.caption,
            chat_id=request.chat_id,
            temperature=temperature,
        )
        return {
            "status": result.get("status"),
            "pdf_id": result.get("pdf_id"),
            "filename": os.path.basename(result.get("file_path") or filename),
            "telegram_response": result.get("telegram_response"),
            "preview": result.get("llm_text", "")[:500],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pdf/manual")
async def create_pdf_from_text(request: PDFTextRequest):
    """Create a PDF from provided text and send it to Telegram."""
    if not create_and_send_pdf_via_telegram:
        raise HTTPException(status_code=503, detail="PDF generation service not available")
    
    try:
        filename = (request.filename or "document.pdf").strip() or "document.pdf"
        result = create_and_send_pdf_via_telegram(  # type: ignore[misc]
            request.text,
            filename,
            request.caption,
            request.chat_id,
        )
        return {
            "status": result.get("status"),
            "pdf_id": result.get("pdf_id"),
            "filename": os.path.basename(result.get("file_path") or filename),
            "telegram_response": result.get("telegram_response"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Calling Endpoints ==========

@app.post("/call/me")
async def call_me_endpoint(request: CallRequest = Body(default=None)):
    """Trigger a Twilio call to the configured phone number."""
    if not call_me_service:
        raise HTTPException(status_code=503, detail="Calling service not configured")

    if request is None:
        request = CallRequest()
    
    try:
        result = call_me_service()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    status = (result or {}).get("status")
    if status not in {"queued", "completed"}:
        raise HTTPException(status_code=400, detail=result.get("reason", "Call request failed"))
    
    log_chat(request.user_id or "me", "assistant", "Initiated call-me request via API")
    return {
        "status": status,
        "call_sid": result.get("call_sid"),
        "note": request.note,
    }

# ========== Spotify Endpoints ==========

def _ensure_spotify_available():
    if not search_tracks or not open_track:
        raise HTTPException(status_code=503, detail="Spotify service not available")

def _handle_spotify_error(exc: Exception):
    if isinstance(exc, SpotifyAuthError):
        raise HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, (SpotifyApiError, SpotifyPlaybackError)):
        raise HTTPException(status_code=503, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))

@app.post("/spotify/search")
async def spotify_search(request: SpotifySearchRequest):
    """Search Spotify for tracks."""
    _ensure_spotify_available()
    limit = request.limit or 5
    try:
        tracks = search_tracks(request.query, limit=limit)  # type: ignore[misc]
        return {
            "count": len(tracks),
            "tracks": tracks
        }
    except Exception as exc:
        _handle_spotify_error(exc)

@app.post("/spotify/play")
async def spotify_play_track(request: SpotifyPlayRequest):
    """Open a Spotify track in the user's default player/browser."""
    _ensure_spotify_available()
    track = {
        "url": request.track_url,
        "name": request.name or "",
        "artists": request.artists or "",
        "album": request.album,
    }
    try:
        opened = open_track(track)  # type: ignore[misc]
    except Exception as exc:
        _handle_spotify_error(exc)
    
    if not opened:
        raise HTTPException(status_code=400, detail="Failed to open Spotify track URL")
    
    description = describe_track(track) if describe_track else request.name or ""
    return {
        "status": "opened",
        "description": description,
        "url": request.track_url
    }

def _spotify_control(action: str):
    if action == "pause":
        func = pause_playback
    elif action == "resume":
        func = resume_playback
    else:
        func = next_track
    if not func:
        raise HTTPException(status_code=503, detail="Spotify playback controls unavailable")
    try:
        func()  # type: ignore[misc]
    except Exception as exc:
        _handle_spotify_error(exc)

@app.post("/spotify/pause")
async def spotify_pause():
    """Pause Spotify playback (macOS only)."""
    _spotify_control("pause")
    return {"status": "paused"}

@app.post("/spotify/resume")
async def spotify_resume():
    """Resume Spotify playback."""
    _spotify_control("resume")
    return {"status": "playing"}

@app.post("/spotify/next")
async def spotify_next():
    """Skip to the next Spotify track."""
    _spotify_control("next")
    return {"status": "skipped"}

@app.get("/spotify/status")
async def spotify_status():
    """Check whether Spotify is currently playing."""
    if not is_playing:
        raise HTTPException(status_code=503, detail="Spotify status unavailable")
    try:
        playing = is_playing()  # type: ignore[misc]
    except Exception as exc:
        _handle_spotify_error(exc)
    return {"playing": bool(playing)}

# ========== Other Endpoints ==========

@app.get("/joke")
async def get_joke():
    """Get a random joke"""
    try:
        joke = tell_joke()
        return {
            "joke": joke
        }
    except Exception as e:
        return {
            "joke": "Why do programmers prefer dark mode? Because light attracts bugs."
        }

@app.post("/question")
async def ask_question(request: QuestionRequest):
    """Ask a question using LLM"""
    try:
        log_chat(request.user_id, "user", request.question)
        answer = _answer_question_text(request.question, require_llm=True)
        log_chat(request.user_id, "assistant", answer)
        return {
            "question": request.question,
            "answer": answer
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history")
async def read_chat_history(
    user_id: str = "me",
    limit: int = 20,
    role: Optional[str] = None,
    contains: Optional[str] = None,
):
    """Read chat history entries"""
    try:
        role_filter = role if role in {"user", "assistant"} else None
        keyword = (contains or "").strip() or None
        limit = max(1, min(limit, 100))
        rows = get_chat_history(user_id, limit=limit, role=role_filter, contains=keyword)
        entries = []
        for row in rows:
            created_at = row.get("created_at")
            entries.append(
                {
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "role": row.get("role"),
                    "text": row.get("text"),
                    "created_at": created_at.isoformat() if created_at else None,
                }
            )
        return {"count": len(entries), "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat/history")
async def delete_chat_history_entries(request: ChatHistoryDeleteRequest):
    """Delete chat history entries"""
    try:
        role_filter = request.role if request.role in {"user", "assistant"} else None
        keyword = (request.contains or "").strip() or None
        user_id = request.user_id or "me"
        deleted = delete_chat_history(user_id, role=role_filter, contains=keyword, before=request.before)
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/time")
async def get_current_time():
    """Get current time"""
    now = datetime.now()
    return {
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%B %d, %Y"),
        "iso": now.isoformat()
    }

# ========== Voice/Audio Endpoints for Arduino/Robot ==========

from fastapi import File, UploadFile
import tempfile
import subprocess
from fastapi.responses import FileResponse

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voice: Optional[str] = Field(default="samantha", description="Voice name (samantha, karen, etc.)")

@app.post("/tts/speak")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Samantha voice - Returns audio file"""
    import tempfile
    import subprocess
    from fastapi.responses import FileResponse
    
    try:
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            audio_file = tmp.name
        
        # Use macOS say command to generate audio file with Samantha voice
        voice = request.voice.capitalize() if request.voice else "Samantha"
        process = subprocess.run(
            ["say", "-v", voice, "-o", audio_file, request.text],
            capture_output=True,
            timeout=30
        )
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        # Return audio file
        return FileResponse(
            audio_file,
            media_type="audio/aiff",
            filename="speech.aiff",
            headers={"Content-Disposition": "attachment; filename=speech.aiff"}
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Speech generation timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="TTS service not available (macOS 'say' command required)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tts/text")
async def get_speech_text(request: TTSRequest):
    """Get text response without audio - lightweight for Arduino"""
    return {
        "text": request.text,
        "voice": request.voice or "samantha",
        "length": len(request.text)
    }

class ConversationRequest(BaseModel):
    text: str = Field(..., description="User input text")
    user_id: Optional[str] = Field(default="me", description="User ID")
    return_audio: Optional[bool] = Field(default=False, description="Return audio file")

@app.post("/conversation")
async def handle_conversation(request: ConversationRequest):
    """Complete conversation handler - detects intent and returns response with optional audio"""
    try:
        # Detect intent
        intent = detect_intent(request.text)
        log_chat(request.user_id, "user", request.text)
        
        response_text = ""
        
        # Handle based on intent
        if intent == "smalltalk":
            response_text = "Hello! How can I assist you?"
        elif intent == "ask_time":
            now = datetime.now()
            response_text = f"The time is {now.strftime('%I:%M %p')}."
        elif intent == "joke":
            try:
                response_text = tell_joke()
            except:
                response_text = "Why do programmers prefer dark mode? Because light attracts bugs."
        elif intent == "question" and complete:
            response_text = complete(request.text)
        else:
            response_text = f"I detected a {intent} request. This requires additional parameters via specific endpoints."
        
        log_chat(request.user_id, "assistant", response_text)
        
        result = {
            "intent": intent,
            "response": response_text,
            "timestamp": datetime.now().isoformat()
        }
        
        # If audio requested, include audio URL
        if request.return_audio:
            result["audio_url"] = f"/tts/speak"
            result["audio_request"] = {"text": response_text, "voice": "samantha"}
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Speech-to-Text (STT) Endpoints ==========

@app.post("/stt/transcribe")
async def speech_to_text(audio: UploadFile = File(...)):
    """Convert audio file to text using Google Speech Recognition"""
    try:
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        
        # Import speech recognition
        try:
            from speech_io import transcribe_wav
        except ImportError:
            import speech_recognition as sr
            
            def transcribe_wav(filename: str) -> dict:
                r = sr.Recognizer()
                try:
                    with sr.AudioFile(filename) as source:
                        audio_data = r.record(source)
                    text = r.recognize_google(audio_data)
                    return {"text": text}
                except sr.UnknownValueError:
                    return {"text": ""}
                except sr.RequestError as e:
                    raise Exception(f"Speech recognition API error: {e}")
        
        # Transcribe
        result = transcribe_wav(tmp_path)
        
        # Clean up
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return {
            "text": result.get("text", ""),
            "success": bool(result.get("text")),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice/conversation")
async def voice_conversation(audio: UploadFile = File(...), user_id: str = "me"):
    """Complete voice conversation - audio in, text response out (perfect for Arduino)"""
    try:
        # Step 1: Convert audio to text (STT)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        
        try:
            from speech_io import transcribe_wav
        except ImportError:
            import speech_recognition as sr
            
            def transcribe_wav(filename: str) -> dict:
                r = sr.Recognizer()
                try:
                    with sr.AudioFile(filename) as source:
                        audio_data = r.record(source)
                    text = r.recognize_google(audio_data)
                    return {"text": text}
                except sr.UnknownValueError:
                    return {"text": ""}
                except Exception:
                    return {"text": ""}
        
        result = transcribe_wav(tmp_path)
        user_text = result.get("text", "")
        
        # Clean up audio file
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if not user_text:
            return {
                "success": False,
                "error": "Could not understand audio",
                "user_text": "",
                "response": "I couldn't understand what you said. Please try again."
            }
        
        # Step 2: Process the text and get response
        intent = detect_intent(user_text)
        log_chat(user_id, "user", user_text)
        
        response_text = _resolve_conversation_response(intent, user_text, allow_llm_fallback=True)
        
        log_chat(user_id, "assistant", response_text)
        
        return {
            "success": True,
            "user_text": user_text,
            "intent": intent,
            "response": response_text,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice/full")
async def voice_to_voice(audio: UploadFile = File(...), user_id: str = "me"):
    """Complete voice-to-voice conversation - Audio in, Samantha voice audio out! →
    
    Perfect for robots: User speaks → Get Samantha's voice response
    """
    import tempfile
    import subprocess
    from fastapi.responses import FileResponse
    
    try:
        # Step 1: Save uploaded audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        
        # Step 2: Convert audio to text (STT)
        try:
            from speech_io import transcribe_wav
        except ImportError:
            import speech_recognition as sr
            
            def transcribe_wav(filename: str) -> dict:
                r = sr.Recognizer()
                try:
                    with sr.AudioFile(filename) as source:
                        audio_data = r.record(source)
                    text = r.recognize_google(audio_data)
                    return {"text": text}
                except sr.UnknownValueError:
                    return {"text": ""}
                except Exception:
                    return {"text": ""}
        
        result = transcribe_wav(tmp_path)
        user_text = result.get("text", "")
        
        # Clean up input audio
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if not user_text:
            # Return error audio
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
                error_audio = tmp.name
            subprocess.run(
                ["say", "-v", "Samantha", "-o", error_audio, 
                 "I couldn't understand what you said. Please try again."],
                capture_output=True,
                timeout=30
            )
            return FileResponse(
                error_audio,
                media_type="audio/aiff",
                filename="response.aiff",
                headers={
                    "X-User-Text": "[unintelligible]",
                    "X-Intent": "error",
                    "X-Response-Text": "I couldn't understand what you said. Please try again."
                }
            )
        
        # Step 3: Process the text and generate response
        intent = detect_intent(user_text)
        log_chat(user_id, "user", user_text)
        
        response_text = ""
        
        response_text = _resolve_conversation_response(intent, user_text, allow_llm_fallback=True)
        
        log_chat(user_id, "assistant", response_text)
        
        # Step 4: Convert response to Samantha voice audio
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            response_audio = tmp.name
        
        # Generate audio with Samantha voice
        process = subprocess.run(
            ["say", "-v", "Samantha", "-o", response_audio, response_text],
            capture_output=True,
            timeout=30
        )
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to generate voice response")
        
        # Return Samantha voice audio with metadata in headers
        return FileResponse(
            response_audio,
            media_type="audio/aiff",
            filename="samantha_response.aiff",
            headers={
                "X-User-Text": user_text,
                "X-Intent": intent,
                "X-Response-Text": response_text,
                "Content-Disposition": "attachment; filename=samantha_response.aiff"
            }
        )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Voice generation timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Voice service not available (macOS required)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Run Server ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
