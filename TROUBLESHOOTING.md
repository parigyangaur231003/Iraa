# Iraa Troubleshooting Guide

## When Operations Don't Work

I've added extensive debug logging. When you run Iraa, watch the console output for messages like:

- `[DEBUG] User said: '...'` - Shows what Iraa heard
- `[DEBUG] Detected intent: ...` - Shows which intent was detected
- `[action_email] Starting email action` - Shows when operations start
- `[action_email] Error: ...` - Shows specific errors

## Quick Diagnostic

Run this to test all operations:
```bash
pipenv run python check_setup.py
```

## Common Issues & Solutions

### 1. Operations Start But Don't Complete

**Symptoms:** Iraa starts asking questions but then stops

**Look for:**
- `[action_*] Received recipient: ''` - Empty input means speech recognition didn't catch your voice
- `[action_*] Parsed start: ...` - Check if time parsing worked

**Solutions:**
- Speak more clearly and wait for Iraa to finish speaking
- Make sure microphone is working
- Check console output to see what Iraa heard

### 2. "Google is not connected" Error

**Solution:**
```bash
pipenv run python google_terminal_test.py
```

Or say: **"authorize google"** when Iraa is running

### 3. Telegram "chat not found" Error

**Problem:** Your `TELEGRAM_CHAT_ID` is incorrect or placeholder

**Solution:**
1. Send a message to your bot on Telegram
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find the `"chat":{"id":123456789}` value
4. Update `TELEGRAM_CHAT_ID` in your `.env` file

### 4. Time Parsing Errors

**Problem:** Iraa can't understand the time format

**Valid formats:**
- "today 2 PM" or "today 14:30"
- "tomorrow 9 AM"
- "2025-11-15 14:30"
- "in 1 hour" or "in 30 minutes"

**Solution:** Use one of the formats above, or check the error message Iraa speaks

### 5. Email Sending Fails

**Check console for:**
- `[email] Error: ...` - This shows the actual Gmail API error

**Common errors:**
- Token expired → Re-run authorization
- API not enabled → Enable Gmail API in Google Cloud Console
- Permission denied → Check OAuth scopes

### 6. Calendar Events Fail

**Check console for:**
- `[action_calendar] Start time parse error: ...` - Time format issue
- `[agent] Calendar error: ...` - API error

**Common fixes:**
- Use proper time formats (see above)
- Check Google Calendar API is enabled
- Verify OAuth tokens are valid

## What to Watch in Console

When Iraa is running, watch for these debug messages:

```
[DEBUG] User said: 'send email'
[DEBUG] Detected intent: email
[action_email] Starting email action
[action_email] Google connected: True, email: your@email.com
[action_email] Asking for recipient
[action_email] Received recipient: 'john@example.com'
[action_email] Asking for purpose
[action_email] Received purpose: 'meeting follow up'
[action_email] Drafting email...
[action_email] Send result: {'status': 'sent', 'id': '...'}
```

If you see an error at any step, that's where the problem is!

## Testing Individual Operations

### Test Email:
```bash
pipenv run python -c "from google_gmail import list_recent; print(list_recent('me'))"
```

### Test Calendar:
```bash
pipenv run python google_terminal_test.py
```
(Choose option 4 to test calendar)

### Test Telegram:
Check your `.env` file has correct values:
```bash
grep TELEGRAM .env
```

## Still Not Working?

1. **Check console output** - All errors are logged with `[action_*]` or `[DEBUG]` prefixes
2. **Listen to Iraa** - Iraa now speaks error messages clearly
3. **Run diagnostics** - `pipenv run python check_setup.py`
4. **Test manually** - Use `google_terminal_test.py` to test Google services

