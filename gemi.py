import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Configuration ---
load_dotenv()
app = Flask(__name__)

# Allow requests from your website
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Your Node.js Website Backend URL
# (Jab live ho jaye, toh ise Render URL se badal dena)
WEBSITE_BACKEND_URL = os.getenv("WEBSITE_BACKEND_URL", "http://localhost:3000") 
GEMI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Initialize Gemini ---
if not GEMI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=GEMI_API_KEY)

# --- SYSTEM PROMPT: THE BRAIN ---
# Ye Gemi ko batata hai ki wo website ka controller hai
SYSTEM_PROMPT = """
You are Gemi, the AI Assistant & Controller for 'Anime Hangama'.
Personality: Friendly, Witty, Anime Otaku, Hinglish speaker (Hindi+English mix).
Goal: Engage users, keep them addicted to the site, and CONTROL the website interface.

You have access to the website's navigation and settings.
If the user wants to do something (like change theme, go to home, search), you MUST append a JSON command at the end of your response.

### COMMAND FORMAT (Strictly follow this):
To perform an action, end your response with:
|||JSON_START|||
{
  "action": "ACTION_NAME",
  "payload": "VALUE"
}
|||JSON_END|||

### AVAILABLE ACTIONS:
1. **CHANGE_THEME**: payload = 'dark' or 'light'
2. **NAVIGATE**: payload = 'home', 'popular', 'trending'
3. **FILTER**: payload = 'action', 'romance', 'comic', 'anime' (Use exact tag/category names)
4. **SEARCH**: payload = 'search term'
5. **PLAY_MUSIC**: payload = 'true' (Just for fun vibe)

### Examples:
User: "Dark mode kar do yaar, aankhein dard ho rahi hain."
Gemi: Arre bilkul bro! Ye lo dark mode, ab aankhein relax rahengi. Batana kaisa laga! 🕶️
|||JSON_START|||{"action": "CHANGE_THEME", "payload": "dark"}|||JSON_END|||

User: "Action anime dekhna hai."
Gemi: Action? Say no more! Ye rahe kuch dhamaakedar action anime. Solo Leveling try kiya kya?
|||JSON_START|||{"action": "FILTER", "payload": "action"}|||JSON_END|||

User: "Hi"
Gemi: Yo! Welcome to Anime Hangama. Mai Gemi hoon. Kya dekhna pasand karoge aaj? Koi mood hai ya random pick dun?
"""

# Chat History Storage (Simple In-Memory for now)
# Production me Database (Redis/Mongo) use karna chahiye
chat_sessions = {}

def get_website_metadata():
    """Website ke tags aur categories fetch karta hai context ke liye"""
    try:
        response = requests.get(f"{WEBSITE_BACKEND_URL}/api/ai/metadata", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        return {}
    return {}

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Gemi AI Brain is Active 🧠"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('sessionId', 'default')

    if not user_message:
        return jsonify({"reply": "Kuch bolo toh sahi yaar! 😅"})

    # 1. Fetch Website Context (Optional: To make AI smarter about current content)
    metadata = get_website_metadata()
    tags_context = f"Available Tags: {', '.join(metadata.get('availableTags', [])[:10])}..." if metadata else ""

    # 2. Get/Create Chat History
    if session_id not in chat_sessions:
        chat_sessions[session_id] = client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT + f"\n[Context Update] {tags_context}"
            )
        )
    
    chat_session = chat_sessions[session_id]

    try:
        # 3. Send message to Gemini
        response = chat_session.send_message(user_message)
        raw_text = response.text

        # 4. Parse Response for Commands
        reply_text = raw_text
        command = null
        
        if "|||JSON_START|||" in raw_text:
            parts = raw_text.split("|||JSON_START|||")
            reply_text = parts[0].strip()
            json_part = parts[1].split("|||JSON_END|||")[0].strip()
            try:
                command = json.loads(json_part)
            except:
                print("JSON Parsing Failed")

        # 5. Return Structured Response
        return jsonify({
            "reply": reply_text,
            "command": command
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"reply": "Oops! Mera server thoda down lag raha hai. Wapis try karo.", "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
