# Using Iraa API with Arduino Robot

This guide shows how to use the Iraa FastAPI with your Arduino robot to get Samantha voice responses.

## New Voice Endpoints Added

### 1. `/conversation` - Complete Conversation Handler
**Perfect for Arduino - Single API call for everything**

**Request:**
```json
POST http://your-hostinger-url.com/conversation
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

### 2. `/tts/speak` - Get Audio File with Samantha Voice
**For downloading audio files**

**Request:**
```json
POST http://your-hostinger-url.com/tts/speak
{
  "text": "Hello! How can I help you?",
  "voice": "samantha"
}
```

**Response:** Returns `.aiff` audio file

### 3. `/tts/text` - Get Text Only (Lightweight)
**Best for Arduino with limited memory**

**Request:**
```json
POST http://your-hostinger-url.com/tts/text
{
  "text": "Hello! How can I help you?",
  "voice": "samantha"
}
```

### 4. `/stt/transcribe` - Speech to Text (NEW!)
**Convert audio to text**

**Request:**
```
POST http://your-hostinger-url.com/stt/transcribe
Content-Type: multipart/form-data

audio: [WAV audio file]
```

**Response:**
```json
{
  "text": "what time is it",
  "success": true,
  "timestamp": "2025-11-02T14:30:00"
}
```

### 5. `/voice/conversation` - Complete Voice Flow (BEST!)
**Send audio, get text response - Perfect for voice robots!**

**Request:**
```
POST http://your-hostinger-url.com/voice/conversation
Content-Type: multipart/form-data

audio: [WAV audio file]
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

## Arduino Example Code

### Voice Robot with Microphone (Complete Solution)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "I2S.h"  // For INMP441 microphone

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Iraa API URL
const char* voiceAPI = "http://your-domain.com/voice/conversation";

// I2S Microphone pins (for INMP441)
#define I2S_WS 15
#define I2S_SD 32
#define I2S_SCK 14

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  
  // Initialize I2S for microphone
  I2S.setAllPins(I2S_SCK, I2S_WS, I2S_SD);
  I2S.begin(I2S_PHILIPS_MODE, 16000, 16);
}

void loop() {
  Serial.println("Listening... Speak now!");
  
  // Record audio (3 seconds)
  byte* audioData = recordAudio(3);
  
  if (audioData != NULL) {
    // Send audio to Iraa and get response
    String response = sendVoiceToIraa(audioData);
    
    if (response != "") {
      Serial.println("Iraa says: " + response);
      // Now you can:
      // 1. Display on screen
      // 2. Send to TTS module to speak
      // 3. Control robot based on response
    }
    
    free(audioData);
  }
  
  delay(2000);
}

byte* recordAudio(int seconds) {
  int sampleRate = 16000;
  int bufferSize = sampleRate * seconds * 2; // 16-bit audio
  byte* buffer = (byte*)malloc(bufferSize);
  
  if (buffer == NULL) {
    Serial.println("Failed to allocate memory");
    return NULL;
  }
  
  // Record audio samples
  for (int i = 0; i < bufferSize; i += 2) {
    int sample = I2S.read();
    buffer[i] = sample & 0xFF;
    buffer[i + 1] = (sample >> 8) & 0xFF;
  }
  
  return buffer;
}

String sendVoiceToIraa(byte* audioData) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(voiceAPI);
    
    // Create multipart form data
    String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    
    // Build form data with audio file
    String formData = "--" + boundary + "\r\n";
    formData += "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.wav\"\r\n";
    formData += "Content-Type: audio/wav\r\n\r\n";
    
    // Note: This is simplified - full implementation needs WAV header
    
    int httpResponseCode = http.POST(formData);
    
    if (httpResponseCode == 200) {
      String payload = http.getString();
      
      StaticJsonDocument<1000> doc;
      deserializeJson(doc, payload);
      
      String response = doc["response"];
      String userText = doc["user_text"];
      
      Serial.println("You said: " + userText);
      http.end();
      return response;
    } else {
      Serial.print("Error: ");
      Serial.println(httpResponseCode);
      http.end();
    }
  }
  return "";
}
```

### ESP32/ESP8266 with WiFi (Text-Only Mode)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Iraa API URL (replace with your Hostinger URL)
const char* iraaAPI = "http://your-domain.com/conversation";

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
}

void loop() {
  // Example: Ask Iraa what time it is
  String response = askIraa("what time is it");
  
  if (response != "") {
    Serial.println("Iraa says: " + response);
    // Here you can:
    // 1. Display on LCD screen
    // 2. Send to text-to-speech module
    // 3. Control robot actions based on response
  }
  
  delay(5000); // Wait 5 seconds before next request
}

String askIraa(String userInput) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(iraaAPI);
    http.addHeader("Content-Type", "application/json");
    
    // Create JSON request
    StaticJsonDocument<200> doc;
    doc["text"] = userInput;
    doc["user_id"] = "robot1";
    doc["return_audio"] = false;
    
    String requestBody;
    serializeJson(doc, requestBody);
    
    // Send POST request
    int httpResponseCode = http.POST(requestBody);
    
    if (httpResponseCode == 200) {
      String payload = http.getString();
      
      // Parse JSON response
      StaticJsonDocument<1000> responseDoc;
      deserializeJson(responseDoc, payload);
      
      String response = responseDoc["response"];
      String intent = responseDoc["intent"];
      
      Serial.println("Intent: " + intent);
      http.end();
      return response;
    } else {
      Serial.print("Error: ");
      Serial.println(httpResponseCode);
      http.end();
      return "";
    }
  }
  return "";
}
```

### Arduino with GSM Module (SIM800L/SIM900)

```cpp
#include <SoftwareSerial.h>
#include <ArduinoJson.h>

SoftwareSerial gsmSerial(7, 8); // RX, TX

const char* apn = "internet"; // Your APN
const char* iraaAPI = "your-domain.com";
const int port = 80;

void setup() {
  Serial.begin(9600);
  gsmSerial.begin(9600);
  delay(1000);
  
  // Initialize GSM
  initGSM();
}

void loop() {
  String response = askIraaGSM("tell me a joke");
  if (response != "") {
    Serial.println("Iraa: " + response);
  }
  delay(10000);
}

void initGSM() {
  gsmSerial.println("AT");
  delay(1000);
  gsmSerial.println("AT+SAPBR=3,1,\"Contype\",\"GPRS\"");
  delay(1000);
  gsmSerial.println("AT+SAPBR=3,1,\"APN\",\"" + String(apn) + "\"");
  delay(1000);
  gsmSerial.println("AT+SAPBR=1,1");
  delay(2000);
  Serial.println("GSM Initialized");
}

String askIraaGSM(String userInput) {
  // Initialize HTTP
  gsmSerial.println("AT+HTTPINIT");
  delay(1000);
  
  gsmSerial.println("AT+HTTPPARA=\"CID\",1");
  delay(1000);
  
  gsmSerial.println("AT+HTTPPARA=\"URL\",\"http://" + String(iraaAPI) + "/conversation\"");
  delay(1000);
  
  // Prepare JSON
  String json = "{\"text\":\"" + userInput + "\",\"user_id\":\"robot1\",\"return_audio\":false}";
  
  gsmSerial.println("AT+HTTPPARA=\"CONTENT\",\"application/json\"");
  delay(1000);
  
  gsmSerial.println("AT+HTTPDATA=" + String(json.length()) + ",10000");
  delay(1000);
  gsmSerial.println(json);
  delay(1000);
  
  // Send POST request
  gsmSerial.println("AT+HTTPACTION=1");
  delay(5000);
  
  // Read response
  gsmSerial.println("AT+HTTPREAD");
  delay(2000);
  
  String response = "";
  while (gsmSerial.available()) {
    response += (char)gsmSerial.read();
  }
  
  gsmSerial.println("AT+HTTPTERM");
  delay(1000);
  
  // Parse JSON from response
  int jsonStart = response.indexOf('{');
  if (jsonStart > 0) {
    String jsonResponse = response.substring(jsonStart);
    StaticJsonDocument<1000> doc;
    deserializeJson(doc, jsonResponse);
    return doc["response"].as<String>();
  }
  
  return "";
}
```

## Available Intents

The API automatically detects these intents:

- `smalltalk` - Greetings, thank you, etc.
- `ask_time` - Current time
- `joke` - Tell a joke
- `question` - General questions (uses LLM)
- `email` - Email operations
- `meet_instant` - Create instant meeting
- `calendar` - Calendar events
- `telegram_send` - Send Telegram message
- `flights` - Flight information
- `news` - News articles
- `stocks` - Stock prices

## Robot Integration Tips

### 1. **Text-Only Mode (Recommended for Arduino)**
```cpp
// Arduino just displays/processes text
String response = askIraa("what's the weather");
displayOnLCD(response);
```

### 2. **Audio Mode (Requires Audio Module)**
```cpp
// Get audio file URL and download
// Requires DFPlayer Mini or similar audio module
String audioURL = getAudioURL("hello");
downloadAndPlay(audioURL);
```

### 3. **Action-Based Mode**
```cpp
String intent = getIntent("turn on lights");
if (intent == "smalltalk") {
  digitalWrite(LED_PIN, HIGH);
}
```

## Example Use Cases

### 1. Time Display Robot
```cpp
String time = askIraa("what time is it");
// Display: "The time is 02:30 PM"
```

### 2. Joke-Telling Robot
```cpp
String joke = askIraa("tell me a joke");
// Display joke on screen or speak it
```

### 3. News Reader Robot
```cpp
// This requires the /news endpoint
// POST to http://your-domain.com/news
// {"query": "technology", "num_results": 3}
```

### 4. Smart Home Assistant
```cpp
String response = askIraa("what's the temperature");
// Process response and control devices
```

## Hardware Requirements

### Minimum Setup:
- ESP32 or ESP8266 board
- WiFi connection
- Optional: LCD display (16x2 or OLED)

### Advanced Setup:
- ESP32-CAM (for vision)
- DFPlayer Mini (for Samantha voice audio)
- Servo motors (for movement)
- Ultrasonic sensor (for interaction)
- Microphone module (for voice input)

## Troubleshooting

### Connection Issues
```cpp
if (WiFi.status() != WL_CONNECTED) {
  Serial.println("WiFi disconnected!");
  WiFi.reconnect();
}
```

### Timeout Issues
```cpp
http.setTimeout(10000); // 10 second timeout
```

### Memory Issues
```cpp
// Use smaller JSON documents
StaticJsonDocument<200> doc; // Instead of 1000
```

## Next Steps

1. Deploy your API to Hostinger
2. Get your domain URL
3. Update Arduino code with your URL
4. Test endpoints using `/docs` interface first
5. Upload code to Arduino
6. Monitor Serial output for debugging

## Sample API Responses

### Time Request
```json
{
  "intent": "ask_time",
  "response": "The time is 02:30 PM.",
  "timestamp": "2025-11-02T14:30:00"
}
```

### Joke Request
```json
{
  "intent": "joke",
  "response": "Why do programmers prefer dark mode? Because light attracts bugs.",
  "timestamp": "2025-11-02T14:30:00"
}
```

### Question Request
```json
{
  "intent": "question",
  "response": "The weather is typically determined by atmospheric conditions...",
  "timestamp": "2025-11-02T14:30:00"
}
```

---

**Note:** The Samantha voice audio generation currently works on macOS servers. For Linux deployment, you'll need to use alternative TTS engines like:
- Google Cloud TTS
- Amazon Polly
- ElevenLabs API
- Coqui TTS
