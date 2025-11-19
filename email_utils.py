"""Utility functions for parsing and validating email addresses from speech recognition."""
import re
from typing import Tuple, Optional

def normalize_email_from_speech(text: str) -> str:
    """
    Convert speech-recognized email formats to proper email addresses.
    
    Examples:
    - "john at gmail dot com" -> "john@gmail.com"
    - "john at gmail.com" -> "john@gmail.com"
    - "john@gmail.com" -> "john@gmail.com"
    - "john dot doe at example dot com" -> "john.doe@example.com"
    """
    if not text:
        return ""
    
    text = text.strip().lower()
    
    # If it already looks like a valid email, return it
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
        return text
    
    # Replace common speech patterns
    # "at" -> "@"
    text = re.sub(r'\s+at\s+', '@', text)
    text = re.sub(r'\s+@\s+', '@', text)
    
    # "dot" -> "."
    text = re.sub(r'\s+dot\s+', '.', text)
    text = re.sub(r'\s+\.\s+', '.', text)
    
    # Remove extra spaces
    text = re.sub(r'\s+', '', text)
    
    # Handle cases like "john@gmail dot com" -> "john@gmail.com"
    text = re.sub(r'@([a-zA-Z0-9]+)\s*dot\s*([a-zA-Z]+)', r'@\1.\2', text)
    text = re.sub(r'@([a-zA-Z0-9]+)\s*\.\s*([a-zA-Z]+)', r'@\1.\2', text)
    
    # Clean up any remaining spaces
    text = text.replace(' ', '')
    
    return text

def validate_email(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def parse_and_validate_email(speech_input: str) -> Tuple[Optional[str], str]:
    """
    Parse email from speech input and validate it.
    
    Returns:
        (email_address, error_message)
        If valid: (email, "")
        If invalid: (None, error_message)
    """
    if not speech_input or not speech_input.strip():
        return None, "No email address provided"
    
    # Normalize the email
    normalized = normalize_email_from_speech(speech_input)
    
    # Validate
    if not validate_email(normalized):
        return None, f"Invalid email format. I heard: '{speech_input}'. Please try saying it like 'john at gmail dot com' or 'john@gmail.com'"
    
    return normalized, ""

