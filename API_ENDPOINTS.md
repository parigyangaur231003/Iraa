# Iraa API Endpoints - Complete Reference

## Voice/Audio Endpoints (For Arduino Robot)

###  Speech-to-Text Endpoints

#### 1. `/stt/transcribe` - Convert Audio to Text
**Purpose:** Send recorded audio, get transcribed text back

**Request:**
```bash
POST http://your-domain.com/stt/transcribe
Content-Type: multipart/form-data

audio: [WAV file]
```

**Response:**
```json
{
  "text": "what time is it",
  "success": true,
  "timestamp": "2025-11-02T14:30:00"
}
```

**Use Case:** When you just need to convert voice to text

---

#### 2. `/voice/conversation` - Complete Voice Interaction
**Purpose:** Send audio, get intelligent text response (STT + AI + Response)

**Request:**
```bash
POST http://your-domain.com/voice/conversation
Content-Type: multipart/form-data

audio: [WAV file]
user_id: robot1
```

**Response:**
```json
{
  "success": true,
  "user_text": "what time is it",
  "intent": "ask_time",
  "response": "The time is 02:30 PM.",
  "timestamp": "2025-11-02T14:30:00"
}
```

**Use Case:** Voice assistant with text response
**Flow:** Audio Input → Speech Recognition → Intent Detection → AI Response → Text Output

---

#### 2b. `/voice/full` - Complete Voice-to-Voice →  BEST FOR VOICE ROBOTS!
**Purpose:** Send audio, get Samantha voice audio back (Complete voice conversation!)

**Request:**
```bash
POST http://your-domain.com/voice/full
Content-Type: multipart/form-data

audio: [WAV file]
user_id: robot1
```

**Response:** Samantha voice audio file (AIFF format) with metadata in headers:
- `X-User-Text`: What the user said
- `X-Intent`: Detected intent
- `X-Response-Text`: Text version of the response

**Use Case:** **PERFECT FOR YOUR ROBOT!** User speaks → Robot responds in Samantha's voice
**Flow:** Audio Input → Speech Recognition → Intent Detection → AI Response → Samantha Voice Audio Output

**Why this is perfect:**
 Single API call for everything
 Voice in, voice out (natural conversation)
 Samantha's voice output
 No need for text-to-speech on Arduino
 Just record → send → play response!

---

###  Text-to-Speech Endpoints

#### 3. `/tts/speak` - Generate Samantha Voice Audio
**Purpose:** Convert text to Samantha voice audio file

**Request:**
```json
POST http://your-domain.com/tts/speak
{
  "text": "Hello! How can I help you?",
  "voice": "samantha"
}
```

**Response:** Audio file (AIFF format)

**Use Case:** When robot needs to download and play Samantha voice

---

#### 4. `/tts/text` - Text Response Only
**Purpose:** Get text formatted for speaking (no audio generation)

**Request:**
```json
POST http://your-domain.com/tts/text
{
  "text": "Hello! How can I help you?",
  "voice": "samantha"
}
```

**Response:**
```json
{
  "text": "Hello! How can I help you?",
  "voice": "samantha",
  "length": 27
}
```

**Use Case:** Lightweight endpoint for Arduino with local TTS module

---

###  Text Conversation Endpoints

#### 5. `/conversation` - Text-Based Conversation
**Purpose:** Send text, get intelligent response

**Request:**
```json
POST http://your-domain.com/conversation
{
  "text": "what time is it",
  "user_id": "robot1",
  "return_audio": false
}
```

**Response:**
```json
{
  "intent": "ask_time",
  "response": "The time is 02:30 PM.",
  "timestamp": "2025-11-02T14:30:00"
}
```

**Use Case:** Text input/output only (good for testing or text displays)

---

## Robot Integration Patterns

### Pattern 1: Full Voice Assistant (Recommended)
```
User speaks → Arduino records → /voice/conversation → Display/speak response
```

**Arduino Flow:**
1. Record audio with microphone (INMP441 or similar)
2. POST audio to `/voice/conversation`
3. Get text response
4. Display on LCD or play via TTS module

**Benefits:**
- Single API call
- Complete conversation handling
- Automatic intent detection
- Low latency

---

### Pattern 2: Separate STT + Conversation
```
User speaks → /stt/transcribe → Get text → /conversation → Response
```

**Arduino Flow:**
1. Record audio
2. POST to `/stt/transcribe` to get text
3. POST text to `/conversation` to get response
4. Display/speak response

**Benefits:**
- More control over each step
- Can save/log transcribed text
- Good for debugging

---

### Pattern 3: Voice In, Voice Out (Advanced)
```
User speaks → /voice/conversation → /tts/speak → Play audio
```

**Arduino Flow:**
1. Record audio
2. POST to `/voice/conversation` to get text response
3. POST response text to `/tts/speak` to get Samantha audio
4. Download and play audio file

**Benefits:**
- Complete voice experience
- Samantha voice output
- Natural conversation

**Requirements:**
- More memory (audio buffering)
- Audio playback module (DFPlayer Mini)
- SD card for audio storage

---

## Complete Robot Example

### Simple Voice Robot
```cpp
// 1. User speaks into microphone
byte* audio = recordAudio(3); // 3 seconds

// 2. Send to Iraa
String response = sendToAPI("/voice/conversation", audio);
// Response: "The time is 02:30 PM"

// 3. Display on LCD
lcd.print(response);

// 4. Optional: Speak via TTS module
textToSpeech(response);
```

### Hardware Needed:
- **ESP32** (WiFi + processing power)
- **INMP441** I2S Microphone
- **16x2 LCD** or OLED display
- **DFPlayer Mini** (optional, for Samantha voice)
- **Speaker** (optional)
- **SD Card** (optional, for audio storage)

---

## Other API Endpoints

### Email
- `POST /email/draft` - Create email draft
- `POST /email/send` - Send email
- `GET /email/list` - List recent emails

### Meetings
- `POST /meeting/instant` - Create instant Google Meet
  - **Automatically sends link to Telegram!**

### Calendar
- `POST /calendar/event` - Create calendar event

### Telegram
- `POST /telegram/send` - Send message
- `GET /telegram/messages` - Get messages

### Information
- `POST /flights` - Search flights
- `POST /news` - Get news articles
- `POST /stock` - Get stock prices
- `POST /question` - Ask AI question
- `GET /joke` - Get a joke
- `GET /time` - Current time

### Utility
- `GET /` - API info
- `GET /health` - Health check
- `GET /greeting` - Time-appropriate greeting
- `POST /intent` - Detect user intent

---

## Supported Intents

The API automatically detects these intents from user input:

- `smalltalk` - Greetings, thank you, bye
- `ask_time` - What time is it
- `joke` - Tell me a joke
- `question` - General questions (uses LLM)
- `email` - Email operations
- `meet_instant` - Create instant meeting
- `calendar` - Calendar events
- `telegram_send` - Send Telegram
- `flights` - Flight search
- `news` - News search
- `stocks` - Stock information

---

## Testing Your API

### Using curl (Terminal)

**Test voice endpoint:**
```bash
curl -X POST http://your-domain.com/voice/conversation \
  -F "audio=@recording.wav" \
  -F "user_id=robot1"
```

**Test text conversation:**
```bash
curl -X POST http://your-domain.com/conversation \
  -H "Content-Type: application/json" \
  -d '{"text":"what time is it","user_id":"robot1"}'
```

**Test TTS:**
```bash
curl -X POST http://your-domain.com/tts/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Iraa","voice":"samantha"}' \
  -o output.aiff
```

### Using Web Interface

Visit: `http://your-domain.com/docs`

Interactive Swagger UI with:
- Test all endpoints
- See request/response schemas
- Try different parameters
- View example responses

---

## Audio Format Requirements

### For Speech-to-Text (Input)
- **Format:** WAV
- **Sample Rate:** 16000 Hz (16 kHz) recommended
- **Channels:** Mono (1 channel)
- **Bit Depth:** 16-bit PCM
- **Duration:** 1-10 seconds recommended

### For Text-to-Speech (Output)
- **Format:** AIFF (macOS) or WAV
- **Voice:** Samantha (default)
- **Quality:** High-quality voice synthesis

---

## Error Handling

### Common Error Codes

- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (missing API keys)
- `404` - Endpoint not found
- `500` - Server error
- `503` - Service unavailable (TTS not available, etc.)

### Example Error Response
```json
{
  "detail": "Speech recognition API error: Network timeout"
}
```

---

## Production Tips

### For Hostinger Deployment:
1. Use HTTPS with SSL certificate
2. Set environment variables securely
3. Enable CORS for specific origins
4. Add rate limiting
5. Monitor API usage
6. Set up logging
7. Use process manager (supervisor)

### For Arduino:
1. Handle network timeouts
2. Add retry logic
3. Cache responses when possible
4. Use smaller audio buffers
5. Compress audio if needed
6. Monitor memory usage
7. Add LED indicators for status

---

## Quick Start Checklist

- [ ] Deploy API to Hostinger
- [ ] Get domain URL
- [ ] Test endpoints with curl or browser
- [ ] Set up Arduino with WiFi
- [ ] Connect microphone (INMP441)
- [ ] Upload Arduino code
- [ ] Test voice recording
- [ ] Test API communication
- [ ] Add display (LCD/OLED)
- [ ] Optional: Add speaker + DFPlayer
- [ ] Test complete flow
- [ ] Deploy robot! 

---

## Support & Documentation

- **API Docs:** http://your-domain.com/docs
- **ReDoc:** http://your-domain.com/redoc
- **Arduino Guide:** ARDUINO_GUIDE.md
- **Deployment Guide:** DEPLOYMENT_GUIDE.md
