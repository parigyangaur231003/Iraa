# Iraa Setup Guide - Fixing Operations

## Issues Fixed

I've improved error handling so Iraa will now tell you exactly what's wrong when operations fail. Here's what you need to set up:

## Required Setup

### 1. Google Services (Email, Calendar, Meet)

**All Google operations require OAuth authentication.**

#### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable these APIs:
   - Gmail API
   - Google Calendar API
   - Google Meet API (if available)
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Choose "Desktop app" as application type
6. Download the credentials JSON or copy Client ID and Client Secret

#### Step 2: Add to .env file

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://127.0.0.1:8765/
```

#### Step 3: Authorize Iraa

**Option A: Run the test script**
```bash
pipenv run python google_terminal_test.py
```

**Option B: Say "authorize google" when Iraa is running**
- Iraa will open a browser for authorization
- Complete the OAuth flow
- Iraa will save your tokens

#### Step 4: Verify Connection

Say: **"Which account am I connected to?"**

Iraa should respond with your email address.

### 2. Telegram (Send/Read Messages)

#### Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Save the **Bot Token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Step 2: Get Your Chat ID

1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"chat":{"id":123456789}` - that's your Chat ID

#### Step 3: Add to .env file

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Testing Operations

### Test Email
Say: **"Send an email"**
- Iraa will ask who to send to and what it's about
- If Google isn't connected, Iraa will tell you

### Test Calendar
Say: **"Add to calendar"** or **"Create event"**
- Iraa will ask for title, start time, end time
- Format: "today 14:30" or "2025-11-15 15:00"

### Test Google Meet
Say: **"Start a meet"** or **"Create instant meeting"**
- Iraa will create a meeting and give you the link

### Test Telegram
Say: **"Send telegram message"** or **"Read telegram messages"**
- If Telegram isn't configured, Iraa will tell you

## Common Errors & Solutions

### "Google is not connected"
**Solution:** Say "authorize google" and complete the OAuth flow

### "No Google tokens found"
**Solution:** Run `pipenv run python google_terminal_test.py` to set up tokens

### "Telegram is not configured"
**Solution:** Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to your `.env` file

### "I couldn't send the email" / Calendar errors
**Possible causes:**
1. Google OAuth tokens expired - re-run authorization
2. API not enabled in Google Cloud Console
3. Insufficient permissions - check OAuth scopes

## Troubleshooting

### Check Google Connection
```bash
pipenv run python -c "from google_oauth import connected_email; print(connected_email('me'))"
```
Should print your email address or empty string.

### Check Telegram Config
```bash
pipenv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Token:', bool(os.getenv('TELEGRAM_BOT_TOKEN'))); print('Chat ID:', bool(os.getenv('TELEGRAM_CHAT_ID')))"
```

### Test Google Services
```bash
pipenv run python google_terminal_test.py
```
This will test Gmail, Calendar, and Meet APIs.

## What Iraa Will Tell You

Iraa now provides clear error messages:
-  "Google is not connected. Please say 'authorize google' first."
-  "Telegram is not configured. Please set TELEGRAM_BOT_TOKEN..."
-  "I couldn't send the email. Error: [specific error]"
-  "I couldn't add the event. Error: [specific error]"

Listen to what Iraa says - it will guide you to fix the issue!

