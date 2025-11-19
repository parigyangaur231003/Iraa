# jokes.py
"""
Lightweight jokes module for Iraa.
Tries LLM first (Groq model), falls back to a static list if unavailable.
"""

import random

# Try to import your Groq LLM if it's configured
try:
    from llm_groq import complete
    USE_LLM = True
except Exception:
    USE_LLM = False
    complete = None


# ---------- fallback list ----------
FALLBACK_JOKES = [
    "Why do Java developers wear glasses? Because they don't C#.",
    "Why did the computer show up at work late? It had a hard drive.",
    "I told my laptop I needed a break, and now it won't stop sending me KitKat ads.",
    "Why was the cell phone wearing glasses? Because it lost its contacts!",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Parallel lines have so much in common… it’s a shame they’ll never meet.",
    "Why did the developer go broke? Because he used up all his cache.",
    "Why was the computer cold? It left its Windows open!",
    "What do you call 8 hobbits? A hobbyte.",
    "There are 10 kinds of people: those who understand binary and those who don’t."
]


# ---------- main function ----------
def tell_joke() -> str:
    """
    Return a short, clean joke (string).
    """
    if USE_LLM and complete:
        try:
            resp = complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a witty AI who tells clean, short jokes "
                            "suitable for working professionals. Each joke must fit in one sentence."
                        ),
                    },
                    {"role": "user", "content": "Tell me a joke."},
                ],
                temperature=0.7,
            )
            return resp.strip()
        except Exception:
            pass

    # fallback random joke
    return random.choice(FALLBACK_JOKES)