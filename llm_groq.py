import requests, os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"

DEFAULT_TEMPERATURE = 0.1

def complete(messages, temperature=DEFAULT_TEMPERATURE):
    if not GROQ_API_KEY:
        return "Subject: Draft\nBody:\nI could not access the LLM right now."
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()
