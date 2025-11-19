# Iraa Wake Words 

## Available Wake Words

You can activate Iraa using any of these phrases:

| Wake Word | Example Usage |
|-----------|---------------|
| **"Hello assistant"** | "Hello assistant, what's the weather?" |
| **"Assistant"** | "Assistant, tell me a joke" |
| **"Ira"** | "Ira, what time is it?" |
| **"Iraa"** | "Iraa, read my emails" |
| **"Hey Ira"** | "Hey Ira, set a reminder" |
| **"Hey Iraa"** | "Hey Iraa, create a meeting" |
| **"Hey buddy"** | "Hey buddy, help me with something" |

---

## How It Works

1. **Iraa is always listening** for wake words
2. When you say any wake word, Iraa activates
3. After activation, you can have a conversation
4. Say **"thank you"**, **"bye"**, or **"stop"** to end the conversation

---

## Examples

### Activation Examples:

```
You: "Hey Ira"
Iraa: "Good morning sir. How can I help you today?"

You: "Assistant"
Iraa: "Hello Sir! Great to have you back again. How can I help you today?"

You: "Hey buddy"
Iraa: "Good afternoon sir. How can I help you today?"
```

### Full Conversation:

```
You: "Hey Iraa"
Iraa: "Good evening sir. How can I help you today?"

You: "What's the weather?"
Iraa: "Weather in Jaipur: Temperature: 28°C. Condition: Clear..."

You: "Send an email"
Iraa: "Sure sir, I'll help you write an email..."

You: "Thank you"
Iraa: "You're welcome, sir."
[Iraa goes to sleep, waiting for next wake word]
```

---

## Sleep Commands

End the conversation with:
- **"Thank you"** → "You're welcome, sir."
- **"Bye"** or **"Goodbye"** → "Goodbye, sir."
- **"Stop"** → "Understood, sir. I'm going to sleep now."

---

## Exit Command

To completely stop Iraa:
- **"Exit"** → "Stopping Iraa. See you soon, sir."

---

## Technical Details

**File:** `app.py`

**Code:**
```python
wake_words = [
    "hello assistant",
    "assistant",
    "ira",
    "iraa",
    "hey ira",
    "hey iraa",
    "hey buddy"
]

if not any(wake_word in wake for wake_word in wake_words):
    continue  # Keep listening
```

The wake word detection is case-insensitive and works with partial matches within the spoken phrase.

---

## Adding More Wake Words

To add more wake words, edit `app.py`:

1. Find the `wake_words` list (around line 173)
2. Add your wake word to the list:
   ```python
   wake_words = [
       "hello assistant",
       "assistant",
       "ira",
       "iraa",
       "hey ira",
       "hey iraa",
       "hey buddy",
       "your new wake word here"  # Add here
   ]
   ```
3. Save and restart Iraa

---

## Best Practices

 **Use clear pronunciation** - Speak clearly for better recognition  
 **Use natural phrases** - All wake words sound natural  
 **Keep it short** - Wake words are designed to be quick  
 **Be consistent** - Pick your favorite and use it  

---

## Troubleshooting

### Wake word not working?

1. **Check microphone** - Ensure it's working and not muted
2. **Speak clearly** - Pronounce the wake word clearly
3. **Check volume** - Make sure audio input is sufficient
4. **Try alternatives** - Use different wake words
5. **Check logs** - Look at `[DEBUG] Listening for wake word` output

### False activations?

If Iraa activates by mistake:
- Adjust wake word list to be more specific
- Remove very short wake words like "ira" if needed
- Use longer phrases like "hey iraa" instead

---

## Multi-language Support

Currently, wake words are in English. For other languages:
1. Add wake words in your language to the list
2. Ensure your speech recognition model supports the language
3. Test pronunciation variations

---

**Your Iraa now responds to multiple wake words!** 
