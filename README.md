# Iraa - Intelligent Remote Assistant Agent

Iraa is a voice-first AI assistant for working professionals, designed to help with email, calendar management, Google Meet, Telegram, and more through natural voice interactions.

## Features

-  **Voice-First Interface**: Natural speech-to-text and text-to-speech interactions
-  **Email Management**: Compose, draft, and send emails via Gmail
-  **Calendar Integration**: Create events and schedule meetings
-  **Google Meet**: Create instant meetings or schedule them
-  **Telegram Integration**: Send and read messages
-  **Spotify Playback**: Search for tracks and open them in Spotify
-  **Smart Reminders**: Hydration, lunch, breaks, and tea time
-  **Secure Authentication**: OAuth2 for Google services with encrypted credential storage

## Prerequisites

- Python 3.11+
- MySQL database
- pipenv (optional but recommended)

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd Iraa
```

2. **Install dependencies**:
```bash
pipenv install
# or
pip install -r requirements.txt
```

3. **Set up MySQL database**:
```bash
mysql -u root -p < schema.sql
```

4. **Configure environment variables**:
Create a `.env` file in the project root:
```env
# MySQL Configuration
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=iraa_db

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8765/
GOOGLE_OAUTH_DEBUG=false

# Groq API (for LLM)
GROQ_API_KEY=your_groq_api_key

# Spotify
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_AUTO_PAUSE_LISTENING=false  # set true to auto-pause Spotify while Iraa is recording

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Security
SECRET_KEY=your_base64_encoded_32_byte_key

# Timezone
TIMEZONE=Asia/Kolkata
```

## Quick Start

1. **Set up Google OAuth**:
```bash
pipenv run python google_terminal_test.py
```

2. **Run the application**:
```bash
pipenv run python app.py
```

3. **Interact with Iraa**:
   - Say "Hey Iraa" to wake up the assistant
   - Follow voice prompts to compose emails, schedule meetings, etc.

## Usage Examples

### Email
- "Send an email to john@example.com about the project update"
- Iraa will draft the email and ask for confirmation

### Calendar
- "Add a meeting to my calendar for tomorrow at 2 PM"
- "Create an event called Project Review for 2025-11-15 10:00"

### Google Meet
- "Start a Google Meet now"
- "Schedule a meeting for later today"

### Telegram
- "Send a Telegram message"
- "Read my Telegram messages"

### Spotify
- "Play some music on Spotify"
- "Play Shape of You on Spotify"

### Other Commands
- "What time is it?"
- "Tell me a joke"
- "Hello", "Good morning", "Thank you"

## Project Structure

```
Iraa/
├── app.py                  # Main application entry point
├── agent.py                # Intent detection and action handlers
├── db.py                   # Database operations
├── google_oauth.py         # Google OAuth2 authentication
├── google_calendar.py      # Calendar integration
├── google_gmail.py         # Gmail integration
├── google_meet.py          # Google Meet integration
├── services_email.py       # Email service layer
├── services_telegram.py    # Telegram integration
├── services_spotify.py     # Spotify search and playback helper
├── speech_io.py            # Speech-to-text and text-to-speech
├── llm_groq.py            # Groq LLM integration
├── scheduler_jobs.py      # Background scheduled tasks
├── credentials.py         # Credential storage
├── secure_store.py        # Encryption utilities
├── time_utils.py          # Time/date utilities
├── jokes.py               # Joke generation
├── schema.sql             # Database schema
├── Pipfile                # Python dependencies
└── README.md             # This file
```

## Key Dependencies

- `requests` - HTTP client for API calls
- `mysql-connector-python` - MySQL database connectivity
- `cryptography` - Secure credential encryption
- `pyttsx3` - Text-to-speech
- `sounddevice` - Audio input
- `speechrecognition` - Speech-to-text
- `apscheduler` - Task scheduling
- `pytz` - Timezone support

## Development

### Running Tests
```bash
pipenv run python google_terminal_test.py  # Test Google integration
pipenv run python speech_io.py            # Test audio
```

### Database Setup
The schema includes the following tables:
- `chat_history` - Conversation logs
- `oauth_tokens` - OAuth2 tokens
- `user_credentials` - Encrypted credentials
- `emails` - Email drafts and sent items
- `meets` - Google Meet links
- `events` - Calendar events
- `schedules` - Tasks and reminders
- `telegram_msgs` - Telegram message history

## Troubleshooting

### Audio Issues
- Check microphone permissions in system settings
- Verify audio input devices: `python speech_io.py`

### OAuth Issues
- Ensure `GOOGLE_REDIRECT_URI` matches Google Console settings
- For desktop apps, use loopback URLs: `http://127.0.0.1:8765/`
- Check `GOOGLE_OAUTH_DEBUG=true` for detailed logs

### Database Connection
- Verify MySQL is running
- Check credentials in `.env`
- Ensure database exists: `mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS iraa_db;"`

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]

## Support

[Add support information here]
