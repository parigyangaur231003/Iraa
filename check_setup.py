#!/usr/bin/env python3
"""
Iraa Setup Diagnostic Tool
Checks if all required services are configured correctly
"""
import os
import sys

print("=" * 60)
print("Iraa Setup Diagnostic Tool")
print("=" * 60)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print(" .env file loaded")
except Exception as e:
    print(f"  Could not load .env: {e}")

errors = []
warnings = []

# 1. Check Google OAuth
print("\n1. Google OAuth Configuration:")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

if not GOOGLE_CLIENT_ID:
    errors.append("GOOGLE_CLIENT_ID is missing")
    print("   GOOGLE_CLIENT_ID: NOT SET")
else:
    print(f"   GOOGLE_CLIENT_ID: Set ({GOOGLE_CLIENT_ID[:10]}...)")

if not GOOGLE_CLIENT_SECRET:
    errors.append("GOOGLE_CLIENT_SECRET is missing")
    print("   GOOGLE_CLIENT_SECRET: NOT SET")
else:
    print(f"   GOOGLE_CLIENT_SECRET: Set")

if not GOOGLE_REDIRECT_URI:
    warnings.append("GOOGLE_REDIRECT_URI not set, using default")
    print("    GOOGLE_REDIRECT_URI: Using default (http://127.0.0.1:8765/)")
else:
    print(f"   GOOGLE_REDIRECT_URI: {GOOGLE_REDIRECT_URI}")

# Check if Google is connected
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from google_oauth import connected_email, load_tokens
    email = connected_email("me")
    if email:
        print(f"   Google account connected: {email}")
    else:
        warnings.append("Google account not connected - run 'authorize google' or google_terminal_test.py")
        print("    Google account: NOT CONNECTED")
        print("     → Run: pipenv run python google_terminal_test.py")
        print("     → Or say 'authorize google' when Iraa is running")
except Exception as e:
    warnings.append(f"Could not check Google connection: {e}")
    print(f"    Could not verify Google connection: {e}")

# 2. Check Telegram
print("\n2. Telegram Configuration:")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not TELEGRAM_BOT_TOKEN:
    warnings.append("TELEGRAM_BOT_TOKEN is missing - Telegram features will not work")
    print("    TELEGRAM_BOT_TOKEN: NOT SET (Telegram features disabled)")
else:
    print(f"   TELEGRAM_BOT_TOKEN: Set ({TELEGRAM_BOT_TOKEN[:10]}...)")

if not TELEGRAM_CHAT_ID:
    warnings.append("TELEGRAM_CHAT_ID is missing - Telegram features will not work")
    print("    TELEGRAM_CHAT_ID: NOT SET (Telegram features disabled)")
else:
    print(f"   TELEGRAM_CHAT_ID: Set ({TELEGRAM_CHAT_ID})")

# 3. Check Database
print("\n3. Database Configuration:")
try:
    from db import conn
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1")
    print("   Database connection: OK")
except Exception as e:
    errors.append(f"Database connection failed: {e}")
    print(f"   Database connection: FAILED ({e})")
    print("     → Run: mysql -u root -p < schema.sql")

# 4. Check Required Environment Variables
print("\n4. Other Configuration:")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    warnings.append("GROQ_API_KEY not set - LLM features may not work")
    print("    GROQ_API_KEY: NOT SET (LLM features disabled)")
else:
    print(f"   GROQ_API_KEY: Set")

SERP_API_KEY = os.getenv("SERP_API_KEY", "").strip()
if not SERP_API_KEY:
    warnings.append("SERP_API_KEY not set - Flights, News, and Stocks features will not work")
    print("    SERP_API_KEY: NOT SET (Flights/News/Stocks features disabled)")
    print("     → Get your key from: https://serpapi.com/")
else:
    print(f"   SERP_API_KEY: Set ({SERP_API_KEY[:10]}...)")

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    errors.append("SECRET_KEY is missing - credential encryption will fail")
    print("   SECRET_KEY: NOT SET")
    print("     → Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
else:
    print("   SECRET_KEY: Set")

# Summary
print("\n" + "=" * 60)
print("Summary:")
print("=" * 60)

if errors:
    print(f"\n CRITICAL ERRORS ({len(errors)}):")
    for err in errors:
        print(f"   • {err}")
    print("\n   Please fix these errors before running Iraa.")
else:
    print("\n No critical errors found!")

if warnings:
    print(f"\n  WARNINGS ({len(warnings)}):")
    for warn in warnings:
        print(f"   • {warn}")

if not errors and not warnings:
    print("\n All systems ready! You can run Iraa now:")
    print("   pipenv run python app.py")
elif not errors:
    print("\n  Some features may not work, but Iraa can still run.")
    print("   Fix warnings to enable all features.")
else:
    print("\n Please fix errors before running Iraa.")

print("\n" + "=" * 60)

