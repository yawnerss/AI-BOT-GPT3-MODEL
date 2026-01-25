from flask import Flask, render_template_string, request, jsonify, Response, session, redirect, url_for
import requests
import json
import os
from datetime import datetime
import time
import secrets
from urllib.parse import urlparse, parse_qs
import uuid
import hashlib
from functools import wraps
import asyncio
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Default bot settings
BOT_SETTINGS = {
    'name': 'JhonWilson AI',
    'avatar': '🤖',
    'avatar_type': 'text',
    'avatar_url': '',
    'tagline': 'Intelligent Assistant'
}

# Admin credentials
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'cute')
ADMIN_USER_ID = 'admin'

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7480489708:AAHSYSODivqJcXkS9aVDPHyZjyxrEExD8Qw')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7383039587')

# ClipFly Configuration
CLIPFLY_BASE_URL = "https://www.clipfly.ai"
CLIPFLY_TOKEN_FILE = "token.txt"  # File containing ClipFly API tokens
CLIPFLY_IMAGES_DIR = "generated_images"
MAX_WAIT_TIME = 300  # Max wait time for generation in seconds
CHECK_INTERVAL = 1   # Check interval in seconds

# Available AI Models
AVAILABLE_MODELS = {
    "1": {"id": "nanobanana", "name": "🍌 Nanobanana (Basic)", "desc": "Fast, basic quality"},
    "2": {"id": "nanobanana2", "name": "🍌 Nanobanana Pro", "desc": "Enhanced quality"},
    "3": {"id": "Seedream4", "name": "🌱 Seedream 4 (UNDER MAINTENANCE)", "desc": "Artistic style"},
    "4": {"id": "qwen", "name": "🤖 Qwen", "desc": "Balanced quality"},
    "5": {"id": "gpt_1low", "name": "⚡ GPT-1 Low", "desc": "Fast generation"},
    "6": {"id": "gpt_1medium", "name": "🎯 GPT-1 Medium", "desc": "Better quality"},
    "7": {"id": "flux_kontext_pro", "name": "✨ Flux Kontext Pro", "desc": "Premium quality"},
    "8": {"id": "flux_2_pro", "name": "🚀 Flux Kontext Pro 2", "desc": "Version 2 of Kontext Pro"},
    "9": {"id": "clipfly_2", "name": "🎬 Clipfly 2", "desc": "Clipfly version"},
    "10": {"id": "midjourney_v7", "name": "🎨 Midjourney V7", "desc": "Midjourney V7 - more detailed textures"}
}

DEFAULT_MODEL = "nanobanana"

# User and conversation storage (in production, use a database)
USERS = {}
CONVERSATIONS = {}
MAX_CONVERSATIONS = 5000
FREE_CREDITS = 500  # Default free credits for new users

# Store user image generation preferences
USER_IMAGE_MODELS = {}  # user_id -> model_id
USER_IMAGE_COUNTS = {}  # user_id -> image_count (1-10)

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=10)

logger = logging.getLogger(__name__)
# ClipFly token manager
def load_clipfly_tokens():
    """Load ClipFly tokens from file"""
    try:
        if not os.path.exists(CLIPFLY_TOKEN_FILE):
            logger.warning(f"{CLIPFLY_TOKEN_FILE} not found!")
            return []
        
        with open(CLIPFLY_TOKEN_FILE, "r") as f:
            tokens = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    token = line.replace("Bearer ", "").strip()
                    if token:
                        tokens.append(token)
            
            print(f"Loaded {len(tokens)} ClipFly tokens from {CLIPFLY_TOKEN_FILE}")
            return tokens
    except Exception as e:
        print(f"Error loading ClipFly tokens: {e}")
        return []

def remove_clipfly_token(token: str):
    """Remove exhausted token"""
    try:
        tokens = load_clipfly_tokens()
        if token in tokens:
            tokens.remove(token)
            with open(CLIPFLY_TOKEN_FILE, "w") as f:
                for t in tokens:
                    f.write(f"{t}\n")
            print(f"Removed exhausted token. Remaining: {len(tokens)}")
            return True
        return False
    except Exception as e:
        print(f"Error removing token: {e}")
        return False

def ensure_image_directory():
    """Create images directory if it doesn't exist"""
    if not os.path.exists(CLIPFLY_IMAGES_DIR):
        os.makedirs(CLIPFLY_IMAGES_DIR)

def download_image(url: str, filename: str):
    """Download image from URL"""
    try:
        ensure_image_directory()
        filepath = os.path.join(CLIPFLY_IMAGES_DIR, filename)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.clipfly.ai/",
        }
        
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"Image saved: {filepath}")
            return filepath
        else:
            print(f"Failed to download image: HTTP {response.status_code}")
        return None
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def delete_image(filepath: str):
    """Delete image file"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Image deleted: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error deleting image: {e}")
        return False

def get_clipfly_headers(token: str):
    """Get API headers for ClipFly"""
    return {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "https://www.clipfly.ai",
        "Referer": "https://www.clipfly.ai/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

def generate_image_with_token(token: str, prompt: str, model_id: str = "nanobanana", gnum: int = 1):
    """Send image generation request to ClipFly"""
    url = f"{CLIPFLY_BASE_URL}/api/v1/user/ai-tasks/image-generator/create"
    headers = get_clipfly_headers(token)
    
    payload = {
        "gnum": gnum,
        "height": 1280,
        "is_scale": 0,
        "model_id": model_id,
        "negative_prompt": "",
        "prompt": prompt,
        "size_id": "9:16",
        "style_id": "",
        "type": 21,
        "width": 720
    }
    
    try:
        print(f"Sending generation request...")
        print(f"Prompt: {prompt}")
        print(f"Model: {model_id}")
        print(f"Image Count: {gnum}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if not response.text:
            return {
                "success": False,
                "error": "Empty response from server",
                "need_switch_token": False
            }
        
        data = response.json()
        message = data.get("message", "")
        code = data.get("code", 0)
        print(f"Response code: {code}, message: {message}")
        
        if "CREDIT_BALANCE_NOT_ENOUGH" in message or "not enough" in message.lower():
            return {
                "success": False,
                "error": "CREDIT_BALANCE_NOT_ENOUGH",
                "need_switch_token": True
            }
        
        if response.status_code == 200 and code == 0:
            task_data = data.get("data", [])
            task_id = None
            queue_id = None
            
            if task_data and len(task_data) > 0:
                task_id = task_data[0].get("id")
                queue_id = task_data[0].get("queue_id")
                print(f"Task created - ID: {task_id}, Queue ID: {queue_id}")
            
            return {
                "success": True,
                "data": data,
                "task_id": task_id,
                "queue_id": queue_id,
                "need_switch_token": False
            }
        else:
            return {
                "success": False,
                "error": f"API error: {message} (code: {code})",
                "need_switch_token": False
            }
            
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {"success": False, "error": "Invalid JSON response", "need_switch_token": False}
    except Exception as e:
        print(f"Error generating image: {e}")
        return {"success": False, "error": str(e), "need_switch_token": False}

def generate_image_with_auto_reload(tokens_list: list, prompt: str, model_id: str = "nanobanana", gnum: int = 1):
    """Send image generation request with automatic token reload"""
    exhausted_tokens = []
    
    for token in tokens_list:
        print(f"Attempting generation with token (balance: {len(tokens_list) - len(exhausted_tokens)} tokens remaining)...")
        
        result = generate_image_with_token(token, prompt, model_id, gnum)
        
        if result.get("need_switch_token"):
            print(f"Token exhausted - insufficient balance. Removing and trying next token...")
            exhausted_tokens.append(token)
            remove_clipfly_token(token)
            continue
        
        if result.get("success"):
            result["token"] = token
            return result
        else:
            error = result.get("error", "Unknown error")
            if any(keyword in error.upper() for keyword in ["CREDIT", "BALANCE", "NOT_ENOUGH"]):
                print(f"Token has insufficient balance. Removing and trying next token...")
                exhausted_tokens.append(token)
                remove_clipfly_token(token)
                continue
            else:
                return result
    
    if exhausted_tokens:
        return {
            "success": False,
            "error": f"All {len(exhausted_tokens)} token(s) exhausted - insufficient balance",
            "need_switch_token": True,
            "exhausted_count": len(exhausted_tokens)
        }
    else:
        return {
            "success": False,
            "error": "No valid tokens available",
            "need_switch_token": False
        }

def get_queue_list(token: str, queue_id: int = None):
    """Get generation queue status"""
    url = f"{CLIPFLY_BASE_URL}/api/v1/user/ai-tasks/ai-generator/queue-list"
    headers = get_clipfly_headers(token)
    
    params = {
        "page": 1,
        "page_size": 20,
        "paranoid": 1
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        data = response.json()
        return {
            "success": response.status_code == 200 and data.get("code") == 0,
            "data": data,
            "queue_id": queue_id
        }
    except Exception as e:
        print(f"Error getting queue: {e}")
        return {"success": False, "error": str(e)}

def find_task_in_queue(queue_data: dict, task_id: int = None, queue_id: int = None):
    """Find a specific task in the queue response"""
    try:
        data_dict = queue_data.get("data", {})
        data_list = data_dict.get("data", []) if isinstance(data_dict, dict) else data_dict
        
        if not isinstance(data_list, list):
            print(f"Unexpected data format in queue response: {type(data_list)}")
            return None
        
        if not data_list:
            print("No data in queue response")
            return None
        
        for queue_item in data_list:
            if not isinstance(queue_item, dict):
                continue
                
            item_queue_id = queue_item.get("id")
            
            if queue_id and item_queue_id == queue_id:
                tasks = queue_item.get("tasks", [])
                if tasks:
                    return tasks[0]
            
            tasks = queue_item.get("tasks", [])
            for task in tasks:
                if task_id and task.get("id") == task_id:
                    return task
        
        if data_list and isinstance(data_list[0], dict) and data_list[0].get("tasks"):
            return data_list[0]["tasks"][0]
        
        return None
        
    except Exception as e:
        print(f"Error finding task in queue: {e}")
        return None

def extract_image_url(task: dict):
    """Extract image URL from task data"""
    try:
        after_material = task.get("after_material", {})
        if after_material:
            urls = after_material.get("urls", {})
            if urls:
                url = urls.get("url", "")
                if url:
                    if url.startswith("http"):
                        return url
                    else:
                        return f"{CLIPFLY_BASE_URL}{url}"
        
        result_url = task.get("result_url", "")
        if result_url:
            if result_url.startswith("http"):
                return result_url
            else:
                return f"{CLIPFLY_BASE_URL}{result_url}"
        
        output_url = task.get("output_url", "")
        if output_url:
            if output_url.startswith("http"):
                return output_url
            else:
                return f"{CLIPFLY_BASE_URL}{output_url}"
        
        ext = task.get("ext", {})
        if ext and isinstance(ext, dict):
            for key in ["url", "image_url", "output"]:
                if key in ext and ext[key]:
                    url = ext[key]
                    if url.startswith("http"):
                        return url
                    else:
                        return f"{CLIPFLY_BASE_URL}{url}"
        
        print(f"Could not find image URL in task")
        return None
        
    except Exception as e:
        print(f"Error extracting image URL: {e}")
        return None

def generate_user_id():
    """Generate unique user ID"""
    return str(uuid.uuid4())[:8]

def generate_conversation_id():
    """Generate unique conversation ID"""
    return str(uuid.uuid4())

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session['user_id'] != ADMIN_USER_ID:
            return jsonify({"success": False, "error": "Admin access required"})
        return f(*args, **kwargs)
    return decorated_function

def create_new_conversation(user_id):
    """Create a new conversation for a user"""
    conv_id = generate_conversation_id()
    CONVERSATIONS[conv_id] = {
        'id': conv_id,
        'user_id': user_id,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'title': 'New Chat',
        'messages': [],
        'history': []
    }
    
    # Link conversation to user
    if user_id in USERS:
        if 'conversations' not in USERS[user_id]:
            USERS[user_id]['conversations'] = []
        USERS[user_id]['conversations'].append(conv_id)
    
    # Limit total conversations
    if len(CONVERSATIONS) > MAX_CONVERSATIONS:
        oldest = min(CONVERSATIONS.keys(), key=lambda k: CONVERSATIONS[k]['created_at'])
        del CONVERSATIONS[oldest]
    
    return conv_id

def update_conversation_title(conv_id, first_message):
    """Auto-generate conversation title from first message"""
    if conv_id in CONVERSATIONS:
        title = first_message[:50] + ('...' if len(first_message) > 50 else '')
        CONVERSATIONS[conv_id]['title'] = title
        CONVERSATIONS[conv_id]['updated_at'] = datetime.now().isoformat()

def user_has_credits(user_id):
    """Check if user has credits"""
    if user_id == ADMIN_USER_ID:
        return True  # Admin has infinite credits
    
    if user_id in USERS:
        return USERS[user_id]['credits'] > 0
    return False

def use_credit(user_id):
    """Use one credit from user"""
    if user_id == ADMIN_USER_ID:
        return True  # Admin doesn't use credits
    
    if user_id in USERS and USERS[user_id]['credits'] > 0:
        USERS[user_id]['credits'] -= 1
        return True
    return False

def add_credits(user_id, amount):
    """Add credits to user"""
    if user_id in USERS:
        USERS[user_id]['credits'] += amount
        return True
    return False

def send_telegram_notification(visitor_info):
    """Send visitor notification to Telegram"""
    if not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram Chat ID not set")
        return
    
    try:
        fb_user = visitor_info.get('fb_user') or 'Direct Visitor'
        source = visitor_info.get('source', 'Unknown')
        ip = visitor_info.get('ip', 'Unknown')
        timestamp = datetime.fromisoformat(visitor_info.get('timestamp', datetime.now().isoformat()))
        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        fb_user = str(fb_user).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        source = str(source).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        
        message = f"""🔔 New Visitor Alert

👤 User: {fb_user}
📱 Source: {source}
🌐 IP: {ip}
⏰ Time: {time_str}

Visit your chatbot now!"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Telegram notification sent for {fb_user}")
        else:
            print(f"❌ Telegram error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Telegram notification failed: {e}")

def send_telegram_conversation(user_id, conv_id, message):
    """Send conversation data to Telegram bot"""
    if not TELEGRAM_BOT_TOKEN:
        return
    
    try:
        user = USERS.get(user_id, {})
        conv = CONVERSATIONS.get(conv_id, {})
        
        telegram_message = f"""💬 New Conversation

👤 User: {user.get('username', 'Anonymous')}
🆔 User ID: {user_id}
💬 Conversation ID: {conv_id}
📝 Message: {message[:200]}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💰 Credits Left: {user.get('credits', 0)}"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': telegram_message
        }
        
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram conversation notification failed: {e}")
        return False

# Update the HTML template to include image generation commands
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{{ bot_name }}</title>
    <style>
        /* Complete CSS Styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --primary-light: rgba(99, 102, 241, 0.1);
            --secondary: #8b5cf6;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --bg-main: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-main: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border: #475569;
            --shadow: rgba(0, 0, 0, 0.4);
            --radius-sm: 6px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 20px;
            --sidebar-width: 280px;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-main);
            color: var(--text-main);
            height: 100vh;
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        /* Login Page */
        .login-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 1rem;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        }
        
        .login-box {
            width: 100%;
            max-width: 400px;
            background: var(--bg-secondary);
            border-radius: var(--radius-xl);
            padding: 2.5rem;
            box-shadow: 0 20px 40px var(--shadow);
            border: 1px solid var(--border);
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .login-logo {
            width: 80px;
            height: 80px;
            margin: 0 auto 1.5rem;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            border: 4px solid rgba(255, 255, 255, 0.1);
        }
        
        .login-logo img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .login-title {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .login-subtitle {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .login-form {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .form-group label {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-main);
        }
        
        .form-group input {
            padding: 0.875rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }
        
        .login-btn {
            padding: 1rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border: none;
            border-radius: var(--radius-md);
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            transition: all 0.2s;
            margin-top: 0.5rem;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        
        .login-btn:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }
        
        .login-footer {
            margin-top: 1.5rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .credit-info {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        #loginStatus {
            margin-top: 1rem;
            padding: 0.75rem;
            border-radius: var(--radius-md);
            font-size: 0.875rem;
            text-align: center;
            display: none;
        }
        
        #loginStatus.success {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #10b981;
            display: block;
        }
        
        #loginStatus.error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
            display: block;
        }
        
        /* Main Layout */
        .app-layout {
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            transition: transform 0.3s ease;
        }
        
        @media (max-width: 1024px) {
            .sidebar {
                position: fixed;
                left: 0;
                top: 0;
                bottom: 0;
                z-index: 1000;
                transform: translateX(-100%);
            }
            
            .sidebar.visible {
                transform: translateX(0);
            }
        }
        
        .sidebar-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 1rem;
            color: white;
            flex-shrink: 0;
        }
        
        .user-details {
            flex: 1;
            min-width: 0;
        }
        
        .user-name {
            font-weight: 600;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .credit-display {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .credit-count {
            font-weight: 700;
            color: var(--success);
        }
        
        .logout-btn {
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-main);
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .logout-btn:hover {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        .new-chat-btn {
            width: 100%;
            padding: 0.875rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            transition: all 0.2s;
        }
        
        .new-chat-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        
        .conversations-list {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
        }
        
        .conversation-item {
            padding: 0.875rem;
            border-radius: var(--radius-md);
            margin-bottom: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
            border: 1px solid transparent;
        }
        
        .conversation-item:hover {
            background: var(--bg-tertiary);
        }
        
        .conversation-item.active {
            background: var(--primary-light);
            border-color: var(--primary);
        }
        
        .conversation-title {
            font-weight: 500;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .conversation-date {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .conversation-delete {
            position: absolute;
            right: 0.5rem;
            top: 50%;
            transform: translateY(-50%);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1rem;
            line-height: 1;
            display: none;
            align-items: center;
            justify-content: center;
        }
        
        .conversation-item:hover .conversation-delete {
            display: flex;
        }
        
        .conversation-delete:hover {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        .sidebar-bottom {
            padding: 1rem;
            border-top: 1px solid var(--border);
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .container {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
            padding: 1rem;
            overflow: hidden;
        }
        
        .header {
            margin-bottom: 1rem;
        }
        
        .header-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .sidebar-toggle {
            display: none;
            background: none;
            border: none;
            color: var(--text-main);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.5rem;
        }
        
        @media (max-width: 1024px) {
            .sidebar-toggle {
                display: block;
            }
        }
        
        .logo-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            flex-shrink: 0;
        }
        
        .logo-icon img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .logo-text h1 {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.125rem;
        }
        
        .logo-text p {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .settings {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .credit-badge {
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border: 1px solid var(--border);
        }
        
        .credit-count-header {
            font-weight: 700;
            color: var(--success);
        }
        
        #mode {
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 0.875rem;
            cursor: pointer;
            min-width: 120px;
        }
        
        .clear-btn {
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .clear-btn:hover {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        .admin-btn {
            padding: 0.5rem 0.75rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .admin-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        
        .status {
            margin: 0.5rem 0;
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            font-size: 0.75rem;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        
        .status.success {
            background: rgba(16, 185, 129, 0.1);
            border-color: rgba(16, 185, 129, 0.3);
            color: #10b981;
        }
        
        .status.error {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
            color: #ef4444;
        }
        
        .status.warning {
            background: rgba(245, 158, 11, 0.1);
            border-color: rgba(245, 158, 11, 0.3);
            color: #f59e0b;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            margin: 0 -1rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        
        .message {
            display: flex;
            max-width: 85%;
        }
        
        .message.user {
            align-self: flex-end;
        }
        
        .message.bot {
            align-self: flex-start;
        }
        
        .message-wrapper {
            display: flex;
            gap: 0.75rem;
            max-width: 100%;
        }
        
        .message.user .message-wrapper {
            flex-direction: row-reverse;
        }
        
        .avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .avatar.user {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            font-size: 0.875rem;
        }
        
        .avatar.bot {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            font-size: 0.875rem;
        }
        
        .avatar img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .message-content {
            padding: 0.875rem 1rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-lg);
            color: var(--text-main);
            line-height: 1.5;
            word-wrap: break-word;
            max-width: 100%;
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            border-bottom-right-radius: var(--radius-sm);
        }
        
        .message.bot .message-content {
            border-bottom-left-radius: var(--radius-sm);
        }
        
        .message-content strong {
            color: inherit;
        }
        
        .message-content em {
            color: var(--text-secondary);
            font-style: italic;
        }
        
        .message-content code {
            background: rgba(0, 0, 0, 0.2);
            padding: 0.125rem 0.375rem;
            border-radius: var(--radius-sm);
            font-family: 'Courier New', monospace;
            font-size: 0.875em;
        }
        
        .message-content pre {
            background: rgba(0, 0, 0, 0.3);
            padding: 1rem;
            border-radius: var(--radius-md);
            overflow-x: auto;
            margin: 0.5rem 0;
            border: 1px solid var(--border);
        }
        
        .message-content pre code {
            background: none;
            padding: 0;
            border-radius: 0;
            font-size: 0.875rem;
        }
        
        .code-header {
            background: rgba(0, 0, 0, 0.2);
            padding: 0.5rem 1rem;
            margin: -1rem -1rem 1rem;
            border-bottom: 1px solid var(--border);
            font-family: 'Courier New', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        .typing-dot {
            width: 6px;
            height: 6px;
            background: var(--text-secondary);
            border-radius: 50%;
            animation: typing 1.4s infinite both;
        }
        
        .typing-dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
            30% { opacity: 1; transform: translateY(-4px); }
        }
        
        .timestamp {
            margin-top: 0.25rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-align: right;
        }
        
        .input-area {
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }
        
        .input-wrapper {
            display: flex;
            gap: 0.75rem;
        }
        
        #userInput {
            flex: 1;
            padding: 0.875rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 1rem;
            font-family: inherit;
            resize: none;
            line-height: 1.5;
            min-height: 52px;
            max-height: 150px;
        }
        
        #userInput:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }
        
        #sendBtn {
            padding: 0 1.5rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        #sendBtn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        
        #sendBtn:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.9);
            z-index: 2000;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        
        .modal.show {
            display: flex;
        }
        
        .modal-content {
            background: var(--bg-secondary);
            border-radius: var(--radius-xl);
            width: 100%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            border: 1px solid var(--border);
            box-shadow: 0 25px 50px var(--shadow);
        }
        
        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
            font-size: 1.25rem;
            font-weight: 600;
            text-align: center;
        }
        
        .modal-buttons {
            padding: 1.5rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.75rem;
        }
        
        .btn-cancel {
            flex: 1;
            padding: 0.875rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-cancel:hover {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        .btn-save {
            flex: 1;
            padding: 0.875rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-save:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border);
            padding: 0 1.5rem;
        }
        
        .tab-btn {
            padding: 1rem;
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            position: relative;
            transition: all 0.2s;
        }
        
        .tab-btn:hover {
            color: var(--text-main);
        }
        
        .tab-btn.active {
            color: var(--primary);
        }
        
        .tab-btn.active::after {
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--primary);
        }
        
        .tab-content {
            padding: 1.5rem;
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .avatar-type-toggle {
            display: flex;
            gap: 0.5rem;
        }
        
        .avatar-type-btn {
            flex: 1;
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .avatar-type-btn.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .avatar-preview {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 0.5rem;
            overflow: hidden;
            border: 2px solid var(--border);
        }
        
        .avatar-preview img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        /* Image Generation Styles */
        .image-container {
            margin-top: 1rem;
            border-radius: var(--radius-md);
            overflow: hidden;
            max-width: 100%;
        }
        
        .image-container img {
            width: 100%;
            height: auto;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
        }
        
        .image-info {
            margin-top: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-align: center;
        }
        
        .generation-progress {
            background: var(--primary-light);
            padding: 1rem;
            border-radius: var(--radius-md);
            margin: 0.5rem 0;
            border: 1px solid rgba(99, 102, 241, 0.3);
        }
        
        .progress-bar {
            width: 100%;
            height: 4px;
            background: var(--bg-tertiary);
            border-radius: 2px;
            margin: 0.5rem 0;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-radius: 2px;
            transition: width 0.3s ease;
        }
        
        .model-selector {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 1rem 0;
        }
        
        .model-btn {
            padding: 0.5rem 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-main);
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .model-btn:hover {
            background: var(--primary);
            color: white;
        }
        
        .model-btn.active {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-color: var(--primary);
            color: white;
        }
        
        @media (max-width: 768px) {
            .model-selector {
                flex-direction: column;
            }
            
            .model-btn {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    {% if not logged_in %}
    <!-- Login Page -->
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <div class="login-logo" id="loginAvatar">
                    {% if bot_avatar_type == 'image' and bot_avatar_url %}
                        <img src="{{ bot_avatar_url }}" alt="{{ bot_name }}">
                    {% else %}
                        {{ bot_avatar }}
                    {% endif %}
                </div>
                <h1 class="login-title">{{ bot_name }}</h1>
                <p class="login-subtitle">{{ bot_tagline }}</p>
            </div>
            
            <form class="login-form" onsubmit="loginUser(event)">
                <div class="form-group">
                    <label for="loginUsername">Username</label>
                    <input type="text" id="loginUsername" placeholder="Enter username" required autocomplete="username">
                </div>
                
                <div class="form-group">
                    <label for="loginPassword">Password</label>
                    <input type="password" id="loginPassword" placeholder="Enter password" required autocomplete="current-password">
                </div>
                
                <button type="submit" class="login-btn" id="loginBtn">
                    <span>🔐</span>
                    <span>Login / Register</span>
                </button>
                
                <div class="login-footer">
                    <div class="credit-info">
                        <span>🎁</span>
                        <span>New users get {{ free_credits }} free credits</span>
                    </div>
                    <p style="margin-top: 1rem;">Admin login: username: <strong>admin</strong></p>
                </div>
            </form>
            
            <div id="loginStatus"></div>
        </div>
    </div>
    
    <script>
        async function loginUser(event) {
            event.preventDefault();
            
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            const loginBtn = document.getElementById('loginBtn');
            const status = document.getElementById('loginStatus');
            
            if (!username || !password) {
                showLoginStatus('Please fill all fields', 'error');
                return;
            }
            
            loginBtn.disabled = true;
            loginBtn.innerHTML = '<span>⏳</span><span>Logging in...</span>';
            status.className = '';
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showLoginStatus('✅ Login successful! Redirecting...', 'success');
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1000);
                } else {
                    showLoginStatus('❌ ' + (data.error || 'Login failed'), 'error');
                }
            } catch (err) {
                showLoginStatus('❌ Connection error', 'error');
            } finally {
                loginBtn.disabled = false;
                loginBtn.innerHTML = '<span>🔐</span><span>Login / Register</span>';
            }
        }
        
        function showLoginStatus(msg, type = 'success') {
            const status = document.getElementById('loginStatus');
            status.textContent = msg;
            status.className = type;
            
            if (type === 'success') {
                setTimeout(() => {
                    status.className = '';
                    status.textContent = '';
                }, 3000);
            }
        }
        
        // Auto-focus on username input
        document.getElementById('loginUsername').focus();
        
        // Allow login with Enter key
        document.getElementById('loginPassword').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                loginUser(e);
            }
        });
    </script>
    
    {% else %}
    <!-- Main Chat Interface -->
    <div class="app-layout">
        <!-- Sidebar -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="user-info">
                    <div class="user-avatar">{{ user_avatar }}</div>
                    <div class="user-details">
                        <div class="user-name">{{ username }}</div>
                        <div class="credit-display">
                            <span>Credits:</span>
                            <span class="credit-count" id="creditCount">{{ user_credits }}</span>
                        </div>
                    </div>
                    <button class="logout-btn" onclick="logout()">🚪 Logout</button>
                </div>
                <button class="new-chat-btn" onclick="createNewChat()">
                    <span>➕</span>
                    <span>New Chat</span>
                </button>
            </div>
            
            <div class="conversations-list" id="conversationsList">
                <!-- Conversations will be loaded here -->
            </div>
            
            <div class="sidebar-bottom">
                <div style="text-align: center; color: var(--text-secondary); font-size: 0.75rem; padding: 0.5rem;">
                    Powered by <strong style="color: var(--primary);">{{ bot_name }}</strong>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content" id="mainContent">
            <div class="container">
                <div class="header">
                    <div class="header-top">
                        <div class="logo">
                            <button class="sidebar-toggle" onclick="toggleSidebar()">
                                <span id="sidebarIcon">☰</span>
                            </button>
                            <div class="logo-icon" id="headerAvatar">
                                {% if bot_avatar_type == 'image' and bot_avatar_url %}
                                    <img src="{{ bot_avatar_url }}" alt="Bot Avatar">
                                {% else %}
                                    {{ bot_avatar }}
                                {% endif %}
                            </div>
                            <div class="logo-text">
                                <h1>{{ bot_name }}</h1>
                                <p>{{ bot_tagline }}</p>
                            </div>
                        </div>
                        <div class="settings">
                            <div class="credit-badge">
                                <span>Credits:</span>
                                <span class="credit-count-header" id="creditCountHeader">{{ user_credits }}</span>
                            </div>
                            <select id="mode">
                                <option value="chat">💬 Chat Mode</option>
                                <option value="code">💻 Code Mode</option>
                                <option value="hybrid">⚡ Hybrid Mode</option>
                                <option value="image">🖼️ Image Mode</option>
                            </select>
                            <button class="clear-btn" onclick="clearCurrentChat()">🗑️ Clear</button>
                            {% if is_admin %}
                            <button class="admin-btn" onclick="openAdmin()">👑 Admin</button>
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <div class="status" id="status">Ready</div>

                <div class="chat-container" id="chat">
                    <!-- Initial message will be loaded by JavaScript -->
                </div>

                <div class="input-area">
                    <div class="input-wrapper">
                        <textarea id="userInput" rows="1" placeholder="Type your message here... Press Enter to send, Shift+Enter for new line"></textarea>
                        <button id="sendBtn" onclick="sendMessage()">
                            <span>🚀</span>
                            <span>Send</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Admin Modal -->
    <div id="adminModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">Admin Panel</div>
            
            <div class="form-group">
                <label>Admin Password</label>
                <input type="password" id="adminPassword" placeholder="Enter admin password">
            </div>
            
            <div id="adminSettings" style="display: none;">
                <div class="tabs">
                    <button class="tab-btn active" onclick="showTab('botSettings')">🤖 Bot Settings</button>
                    <button class="tab-btn" onclick="showTab('userManagement')">👥 User Management</button>
                    <button class="tab-btn" onclick="showTab('imageSettings')">🖼️ Image Settings</button>
                </div>
                
                <div id="botSettings" class="tab-content active">
                    <div class="form-group">
                        <label>Bot Name</label>
                        <input type="text" id="botName" value="{{ bot_name }}">
                    </div>
                    
                    <div class="form-group">
                        <label>Avatar Type</label>
                        <div class="avatar-type-toggle">
                            <button type="button" class="avatar-type-btn {% if bot_avatar_type == 'text' %}active{% endif %}" onclick="setAvatarType('text')">Text/Emoji</button>
                            <button type="button" class="avatar-type-btn {% if bot_avatar_type == 'image' %}active{% endif %}" onclick="setAvatarType('image')">Image URL</button>
                        </div>
                    </div>

                    <div class="form-group" id="textAvatarGroup" style="{% if bot_avatar_type == 'image' %}display:none;{% endif %}">
                        <label>Bot Avatar (text/emoji)</label>
                        <input type="text" id="botAvatar" value="{{ bot_avatar }}" maxlength="4">
                    </div>

                    <div class="form-group" id="imageAvatarGroup" style="{% if bot_avatar_type == 'text' %}display:none;{% endif %}">
                        <label>Avatar Image URL</label>
                        <input type="text" id="botAvatarUrl" value="{{ bot_avatar_url }}" placeholder="https://example.com/avatar.jpg">
                        <div class="avatar-preview" id="avatarPreview">
                            {% if bot_avatar_type == 'image' and bot_avatar_url %}
                                <img src="{{ bot_avatar_url }}" alt="Preview">
                            {% else %}
                                Preview
                            {% endif %}
                        </div>
                    </div>

                    <div class="form-group">
                        <label>Bot Tagline</label>
                        <input type="text" id="botTagline" value="{{ bot_tagline }}">
                    </div>
                </div>
                
                <div id="userManagement" class="tab-content">
                    <div class="form-group">
                        <label>Search User</label>
                        <input type="text" id="searchUser" placeholder="Search by username or ID..." oninput="searchUsers()">
                    </div>
                    
                    <div id="userList" style="max-height: 300px; overflow-y: auto; margin-top: 1rem;">
                        <h3 style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.5rem;">Users ({{ users_count if users_count else 0 }})</h3>
                        <div id="userData"></div>
                    </div>
                    
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Add Credits to Selected User</label>
                        <div style="display: flex; gap: 0.75rem; align-items: center;">
                            <input type="number" id="addCreditsAmount" placeholder="Amount" min="1" max="1000" style="flex: 1; padding: 0.75rem;">
                            <button onclick="addCreditsToUser()" style="padding: 0.75rem 1.5rem; background: var(--primary); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; font-weight: 600; white-space: nowrap;">Add Credits</button>
                        </div>
                        <div id="selectedUserInfo" style="margin-top: 0.75rem; padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-md); display: none;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong id="selectedUserName"></strong>
                                    <span id="selectedUserId" style="font-size: 0.75rem; opacity: 0.7; margin-left: 0.5rem;"></span>
                                </div>
                                <span id="selectedUserCredits" style="font-weight: 600;"></span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="imageSettings" class="tab-content">
                    <div class="form-group">
                        <label>ClipFly Tokens</label>
                        <div style="margin-top: 0.5rem; padding: 1rem; background: var(--bg-tertiary); border-radius: var(--radius-md);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <span>Available Tokens: <strong id="tokenCount">0</strong></span>
                                <button onclick="refreshTokens()" style="padding: 0.5rem 1rem; background: var(--primary); color: white; border: none; border-radius: var(--radius-sm); cursor: pointer;">Refresh</button>
                            </div>
                            <div id="tokenList" style="max-height: 200px; overflow-y: auto; margin-top: 0.5rem; font-size: 0.75rem;"></div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Add New Token</label>
                        <textarea id="newTokens" placeholder="Paste tokens here (one per line)" rows="3" style="width: 100%; padding: 0.75rem; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-main);"></textarea>
                        <button onclick="addTokens()" style="width: 100%; margin-top: 0.5rem; padding: 0.75rem; background: var(--success); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; font-weight: 600;">Add Tokens</button>
                    </div>
                </div>
            </div>
            
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeAdmin()">Cancel</button>
                <button class="btn-save" id="adminAction" onclick="verifyPassword()">Unlock</button>
            </div>
        </div>
    </div>

    <!-- Image Generation Modal -->
    <div id="imageModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">🖼️ Image Generation</div>
            
            <div class="form-group">
                <label>Prompt</label>
                <textarea id="imagePrompt" rows="3" placeholder="Describe the image you want to generate..." style="width: 100%; padding: 0.75rem; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-main);"></textarea>
            </div>
            
            <div class="form-group">
                <label>AI Model</label>
                <div class="model-selector" id="modelSelector">
                    <!-- Models will be populated by JavaScript -->
                </div>
            </div>
            
            <div class="form-group">
                <label>Number of Images (1-10)</label>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <input type="range" id="imageCount" min="1" max="10" value="1" style="flex: 1;">
                    <span id="imageCountValue">1</span>
                </div>
            </div>
            
            <div id="generationStatus" style="display: none;">
                <div class="generation-progress">
                    <div id="statusText">Initializing...</div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill" style="width: 0%;"></div>
                    </div>
                    <div id="progressText">0%</div>
                </div>
            </div>
            
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeImageModal()">Cancel</button>
                <button class="btn-save" id="generateBtn" onclick="generateImage()">Generate</button>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let currentConversationId = null;
        let conversations = {};
        let processing = false;
        let currentBotMessage = null;
        let botAvatar = '{{ bot_avatar }}';
        let botAvatarType = '{{ bot_avatar_type }}';
        let botAvatarUrl = '{{ bot_avatar_url }}';
        let botName = '{{ bot_name }}';
        let isAdmin = {{ 'true' if is_admin else 'false' }};
        let currentUserId = '{{ user_id }}';
        let selectedUserId = null;
        let currentModelId = 'nanobanana';
        let currentImageCount = 1;
        let currentImageTaskId = null;
        let imageGenerationInterval = null;
        
        // DOM Elements
        const input = document.getElementById('userInput');
        const chat = document.getElementById('chat');
        const sendBtn = document.getElementById('sendBtn');
        const status = document.getElementById('status');
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('mainContent');
        const sidebarIcon = document.getElementById('sidebarIcon');
        const modeSelect = document.getElementById('mode');
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initialize();
            
            // Auto-focus input
            if (input) {
                input.focus();
                
                // Auto-resize textarea
                input.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
                });
                
                // Enter to send, Shift+Enter for new line
                input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const text = input.value.trim();
                // Check if it's a command before sending
                if (text.startsWith('/')) {
                handleCommand(text);
                input.value = '';
                input.style.height = 'auto';
                } else {
                sendMessage();
        }
    }
});
                
                
            }
            
            // Click outside to close sidebar on mobile
            document.addEventListener('click', function(e) {
                if (window.innerWidth <= 1024 && sidebar && !sidebar.contains(e.target) && !e.target.closest('.sidebar-toggle')) {
                    sidebar.classList.remove('visible');
                }
            });
            
            // Close sidebar when switching conversation on mobile
            document.addEventListener('conversationSwitched', function() {
                if (window.innerWidth <= 1024) {
                    sidebar.classList.remove('visible');
                }
            });
            
            // Initialize models in image modal
            initializeModels();
            
            // Setup image count slider
            const imageCountSlider = document.getElementById('imageCount');
            const imageCountValue = document.getElementById('imageCountValue');
            
            if (imageCountSlider && imageCountValue) {
                imageCountSlider.addEventListener('input', function() {
                    imageCountValue.textContent = this.value;
                    currentImageCount = parseInt(this.value);
                });
            }
            
            // Load user preferences
            loadUserPreferences();
        });
        
        // Check for commands in input
function checkForCommands() {
    if (!input) return;
    
    const text = input.value;
    
    // Don't show help when user is just typing "/"
    // Only trigger when user types "/help" specifically
    if (text === '/help') {
        showHelp();
    }
    
    // For other commands, we'll handle them when user presses Enter
    // or clicks the command in suggestions
}
        
        // Show image generation modal
        function showImageGenerationModal(prompt = '') {
            const modal = document.getElementById('imageModal');
            const promptInput = document.getElementById('imagePrompt');
            
            if (modal && promptInput) {
                promptInput.value = prompt;
                modal.classList.add('show');
                
                // Load user preferences
                loadUserPreferences();
                
                // Set selected model
                const modelBtns = document.querySelectorAll('.model-btn');
                modelBtns.forEach(btn => {
                    if (btn.dataset.modelId === currentModelId) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
                
                // Set image count
                const imageCountSlider = document.getElementById('imageCount');
                const imageCountValue = document.getElementById('imageCountValue');
                if (imageCountSlider && imageCountValue) {
                    imageCountSlider.value = currentImageCount;
                    imageCountValue.textContent = currentImageCount;
                }
                
                promptInput.focus();
            }
        }
        
        // Close image modal
        function closeImageModal() {
            const modal = document.getElementById('imageModal');
            const statusDiv = document.getElementById('generationStatus');
            
            if (modal) {
                modal.classList.remove('show');
            }
            
            if (statusDiv) {
                statusDiv.style.display = 'none';
            }
            
            // Clear any running intervals
            if (imageGenerationInterval) {
                clearInterval(imageGenerationInterval);
                imageGenerationInterval = null;
            }
            
            // Reset generation status
            document.getElementById('statusText').textContent = 'Initializing...';
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('progressText').textContent = '0%';
            
            // Re-enable generate button
            const generateBtn = document.getElementById('generateBtn');
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate';
            }
        }
        
        // Initialize models in modal
        function initializeModels() {
            const models = {
                "1": {"id": "nanobanana", "name": "🍌 Nanobanana (Basic)", "desc": "Fast, basic quality"},
                "2": {"id": "nanobanana2", "name": "🍌 Nanobanana Pro", "desc": "Enhanced quality"},
                "3": {"id": "Seedream4", "name": "🌱 Seedream 4", "desc": "Artistic style"},
                "4": {"id": "qwen", "name": "🤖 Qwen", "desc": "Balanced quality"},
                "5": {"id": "gpt_1low", "name": "⚡ GPT-1 Low", "desc": "Fast generation"},
                "6": {"id": "gpt_1medium", "name": "🎯 GPT-1 Medium", "desc": "Better quality"},
                "7": {"id": "flux_kontext_pro", "name": "✨ Flux Kontext Pro", "desc": "Premium quality"},
                "8": {"id": "flux_2_pro", "name": "🚀 Flux Kontext Pro 2", "desc": "Version 2 of Kontext Pro"},
                "9": {"id": "clipfly_2", "name": "🎬 Clipfly 2", "desc": "Clipfly version"},
                "10": {"id": "midjourney_v7", "name": "🎨 Midjourney V7", "desc": "Midjourney V7 - more detailed textures"}
            };
            
            const modelSelector = document.getElementById('modelSelector');
            if (modelSelector) {
                modelSelector.innerHTML = '';
                
                for (const [key, model] of Object.entries(models)) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'model-btn';
                    button.dataset.modelId = model.id;
                    button.textContent = model.name;
                    button.title = model.desc;
                    
                    button.onclick = function() {
                        // Remove active class from all buttons
                        document.querySelectorAll('.model-btn').forEach(btn => {
                            btn.classList.remove('active');
                        });
                        
                        // Add active class to clicked button
                        this.classList.add('active');
                        currentModelId = model.id;
                        
                        // Save preference
                        saveUserPreference('model', model.id);
                    };
                    
                    modelSelector.appendChild(button);
                }
            }
        }
        
        // Load user preferences
        async function loadUserPreferences() {
            try {
                const response = await fetch('/api/user/preferences');
                const data = await response.json();
                
                if (data.success) {
                    currentModelId = data.preferences.model || 'nanobanana';
                    currentImageCount = data.preferences.image_count || 1;
                    
                    // Update UI
                    const modelBtns = document.querySelectorAll('.model-btn');
                    modelBtns.forEach(btn => {
                        if (btn.dataset.modelId === currentModelId) {
                            btn.classList.add('active');
                        }
                    });
                    
                    const imageCountSlider = document.getElementById('imageCount');
                    const imageCountValue = document.getElementById('imageCountValue');
                    if (imageCountSlider && imageCountValue) {
                        imageCountSlider.value = currentImageCount;
                        imageCountValue.textContent = currentImageCount;
                    }
                }
            } catch (err) {
                console.error('Error loading preferences:', err);
            }
        }
        
        // Save user preference
        async function saveUserPreference(key, value) {
            try {
                await fetch('/api/user/preferences', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ [key]: value })
                });
            } catch (err) {
                console.error('Error saving preference:', err);
            }
        }
        
        // Generate image
        async function generateImage() {
            const promptInput = document.getElementById('imagePrompt');
            const statusDiv = document.getElementById('generationStatus');
            const statusText = document.getElementById('statusText');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const generateBtn = document.getElementById('generateBtn');
            
            if (!promptInput || !promptInput.value.trim()) {
                showStatus('Please enter a prompt', 'warning');
                return;
            }
            
            const prompt = promptInput.value.trim();
            
            // Check credits for non-admin users
            if (!isAdmin) {
                const hasCredits = await checkUserCredits();
                if (!hasCredits) {
                    return;
                }
            }
            
            // Disable generate button
            if (generateBtn) {
                generateBtn.disabled = true;
                generateBtn.textContent = 'Generating...';
            }
            
            // Show status
            if (statusDiv) {
                statusDiv.style.display = 'block';
            }
            
            if (statusText) {
                statusText.textContent = 'Starting generation...';
            }
            
            // Save image count preference
            saveUserPreference('image_count', currentImageCount);
            
            try {
                const response = await fetch('/api/generate-image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: prompt,
                        model_id: currentModelId,
                        image_count: currentImageCount,
                        conversation_id: currentConversationId
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showStatus('✅ Image generation started!', 'success');
                    
                    // Update status
                    if (statusText) {
                        statusText.textContent = 'Generation in progress...';
                    }
                    
                    // Start polling for status
                    currentImageTaskId = data.task_id;
                    startPollingImageStatus(data.task_id, prompt);
                    
                    // Add user message to chat
                    addImageGenerationMessage(prompt, currentModelId, currentImageCount);
                    
                } else {
                    showStatus('❌ ' + (data.error || 'Failed to start generation'), 'error');
                    
                    // Re-enable generate button
                    if (generateBtn) {
                        generateBtn.disabled = false;
                        generateBtn.textContent = 'Generate';
                    }
                    
                    // Hide status
                    if (statusDiv) {
                        statusDiv.style.display = 'none';
                    }
                }
            } catch (err) {
                console.error('Error generating image:', err);
                showStatus('❌ Connection error', 'error');
                
                // Re-enable generate button
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.textContent = 'Generate';
                }
                
                // Hide status
                if (statusDiv) {
                    statusDiv.style.display = 'none';
                }
            }
        }
        
        // Start polling for image status
        function startPollingImageStatus(taskId, prompt) {
            let progress = 0;
            let maxProgress = 100;
            
            imageGenerationInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/image-status/${taskId}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        const statusDiv = document.getElementById('generationStatus');
                        const statusText = document.getElementById('statusText');
                        const progressFill = document.getElementById('progressFill');
                        const progressText = document.getElementById('progressText');
                        const generateBtn = document.getElementById('generateBtn');
                        
                        if (data.status === 'completed') {
                            // Generation completed
                            clearInterval(imageGenerationInterval);
                            
                            if (statusText) {
                                statusText.textContent = 'Generation complete!';
                            }
                            
                            if (progressFill) {
                                progressFill.style.width = '100%';
                            }
                            
                            if (progressText) {
                                progressText.textContent = '100%';
                            }
                            
                            // Show completion message
                            setTimeout(() => {
                                closeImageModal();
                                showStatus('✅ Image generation complete!', 'success');
                                
                                // Add bot response with image
                                if (data.image_url) {
                                    addImageResultMessage(prompt, data.image_url, data.model_name);
                                }
                                
                                // Update credits
                                if (!isAdmin) {
                                    getCurrentCredits();
                                }
                            }, 1000);
                            
                        } else if (data.status === 'failed') {
                            // Generation failed
                            clearInterval(imageGenerationInterval);
                            
                            if (statusText) {
                                statusText.textContent = 'Generation failed';
                            }
                            
                            showStatus('❌ ' + (data.error || 'Image generation failed'), 'error');
                            
                            // Re-enable generate button
                            if (generateBtn) {
                                generateBtn.disabled = false;
                                generateBtn.textContent = 'Generate';
                            }
                            
                        } else if (data.status === 'processing') {
                            // Still processing
                            progress = Math.min(progress + 5, 90);
                            
                            if (statusText) {
                                statusText.textContent = 'Generating image...';
                            }
                            
                            if (progressFill) {
                                progressFill.style.width = progress + '%';
                            }
                            
                            if (progressText) {
                                progressText.textContent = progress + '%';
                            }
                        }
                    } else {
                        // Error checking status
                        console.error('Error checking status:', data.error);
                    }
                } catch (err) {
                    console.error('Error polling status:', err);
                }
            }, 2000); // Poll every 2 seconds
            
            // Auto-timeout after 5 minutes
            setTimeout(() => {
                if (imageGenerationInterval) {
                    clearInterval(imageGenerationInterval);
                    
                    const statusDiv = document.getElementById('generationStatus');
                    const statusText = document.getElementById('statusText');
                    const generateBtn = document.getElementById('generateBtn');
                    
                    if (statusText) {
                        statusText.textContent = 'Generation timeout';
                    }
                    
                    showStatus('⏱️ Image generation timed out', 'warning');
                    
                    // Re-enable generate button
                    if (generateBtn) {
                        generateBtn.disabled = false;
                        generateBtn.textContent = 'Generate';
                    }
                }
            }, 300000); // 5 minutes timeout
        }
        
        // Add image generation message to chat
        function addImageGenerationMessage(prompt, modelId, imageCount) {
            if (!chat) return;
            
            const msg = document.createElement('div');
            msg.className = 'message user';
            
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar user';
            avatar.textContent = '👤';
            
            const content = document.createElement('div');
            content.className = 'message-content';
            
            let modelName = modelId;
            for (const [key, model] of Object.entries(AVAILABLE_MODELS)) {
                if (model.id === modelId) {
                    modelName = model.name;
                    break;
                }
            }
            
            content.innerHTML = `
                <strong>🖼️ Generate Image</strong><br><br>
                <strong>Prompt:</strong> ${escapeHtml(prompt)}<br>
                <strong>Model:</strong> ${modelName}<br>
                <strong>Count:</strong> ${imageCount} image${imageCount > 1 ? 's' : ''}<br><br>
                <em>⏳ Generating...</em>
            `;
            
            wrapper.appendChild(avatar);
            wrapper.appendChild(content);
            msg.appendChild(wrapper);
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        }
        
        // Add image result message to chat
        function addImageResultMessage(prompt, imageUrl, modelName) {
            if (!chat) return;
            
            const msg = document.createElement('div');
            msg.className = 'message bot';
            
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar bot';
            if (botAvatarType === 'image' && botAvatarUrl) {
                avatar.innerHTML = `<img src="${botAvatarUrl}" alt="Bot">`;
            } else {
                avatar.textContent = botAvatar;
            }
            
            const content = document.createElement('div');
            content.className = 'message-content';
            
            content.innerHTML = `
                <strong>🖼️ Generated Image</strong><br><br>
                <strong>Prompt:</strong> ${escapeHtml(prompt)}<br>
                <strong>Model:</strong> ${modelName}<br><br>
                <div class="image-container">
                    <img src="${imageUrl}" alt="Generated Image" onerror="this.onerror=null; this.src='https://placehold.co/600x400/1e293b/94a3b8?text=Image+Not+Available';">
                </div>
                <div class="image-info">
                    Generated at ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </div>
            `;
            
            wrapper.appendChild(avatar);
            wrapper.appendChild(content);
            msg.appendChild(wrapper);
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        }
        
        // Show model selection
        function showModelSelection() {
            // Clear input
            if (input) {
                input.value = '';
            }
            
            // Create message for model selection
            createMessage('bot', `
                <strong>🎨 Select AI Model</strong><br><br>
                Available Models:<br><br>
                ${Object.entries(AVAILABLE_MODELS).map(([key, model]) => 
                    `<strong>${key}.</strong> ${model.name} - ${model.desc}`
                ).join('<br>')}
                <br><br>
                <strong>Usage:</strong> <code>/setmodel &lt;number&gt;</code><br>
                <strong>Example:</strong> <code>/setmodel 2</code> for Nanobanana Pro<br><br>
                <strong>Current Model:</strong> ${currentModelId === 'nanobanana' ? 'Nanobanana (Default)' : currentModelId}
            `);
        }
        
        // Show image count selection
        function showImageCountSelection() {
            // Clear input
            if (input) {
                input.value = '';
            }
            
            // Create message for image count selection
            createMessage('bot', `
                <strong>🖼️ Select Image Count</strong><br><br>
                You can generate 1-10 images per request.<br><br>
                <strong>Usage:</strong> <code>/setcount &lt;number&gt;</code><br>
                <strong>Example:</strong> <code>/setcount 3</code> for 3 images<br><br>
                <strong>Current Count:</strong> ${currentImageCount} image${currentImageCount > 1 ? 's' : ''}
            `);
        }
        
        // Show current model
        function showCurrentModel() {
            // Clear input
            if (input) {
                input.value = '';
            }
            
            let modelName = currentModelId;
            let modelDesc = '';
            
            for (const [key, model] of Object.entries(AVAILABLE_MODELS)) {
                if (model.id === currentModelId) {
                    modelName = model.name;
                    modelDesc = model.desc;
                    break;
                }
            }
            
            // Create message for current model
            createMessage('bot', `
                <strong>🎨 Your Current Model</strong><br><br>
                <strong>Model:</strong> ${modelName}<br>
                <strong>ID:</strong> <code>${currentModelId}</code><br>
                <strong>Description:</strong> ${modelDesc}<br><br>
                Use <code>/model</code> to see all models<br>
                Use <code>/setmodel &lt;number&gt;</code> to change
            `);
        }
        
        // Show current image count
        function showCurrentImageCount() {
            // Clear input
            if (input) {
                input.value = '';
            }
            
            // Create message for current image count
            createMessage('bot', `
                <strong>🖼️ Your Current Image Count</strong><br><br>
                <strong>Count:</strong> ${currentImageCount} image${currentImageCount > 1 ? 's' : ''}<br><br>
                Your next generation will produce ${currentImageCount} image${currentImageCount > 1 ? 's' : ''}.<br><br>
                Use <code>/setcount</code> to change it.
            `);
        }
        
        // Show token status
        async function showTokenStatus() {
            // Clear input
            if (input) {
                input.value = '';
            }
            
            try {
                const response = await fetch('/api/token-status');
                const data = await response.json();
                
                if (data.success) {
                    let tokenInfo = `✅ Available tokens: ${data.token_count}<br><br>`;
                    
                    if (data.tokens && data.tokens.length > 0) {
                        data.tokens.slice(0, 5).forEach((token, i) => {
                            tokenInfo += `${i + 1}. <code>${token.slice(0, 20)}...${token.slice(-10)}</code><br>`;
                        });
                        
                        if (data.tokens.length > 5) {
                            tokenInfo += `<br>...and ${data.tokens.length - 5} more`;
                        }
                    }
                    
                    createMessage('bot', `
                        <strong>🔑 Token Status</strong><br><br>
                        ${tokenInfo}
                    `);
                }
            } catch (err) {
                console.error('Error getting token status:', err);
                createMessage('bot', '❌ Error getting token status');
            }
        }
        
        // Show help
function showHelp() {
    // Clear input
    if (input) {
        input.value = '';
    }
    
    // Create the help message without HTML tags
    const helpText = `
📖 **Image Generation Commands**

🖼️ **Image Generation:**
• \`/gen <prompt>\` - Generate AI images
• \`/model\` - Show available AI models
• \`/setmodel <number>\` - Set default model
• \`/mymodel\` - Show your current model
• \`/setcount <number>\` - Set image count (1-10)
• \`/mycount\` - Show your current image count
• \`/tokens\` - Check available tokens

💬 **Chat Commands:**
• Type normal messages for chat
• Use dropdown to switch modes (Chat/Code/Hybrid/Image)
• Each image uses 1 credit (admin has unlimited)

**Example:** \`/gen a beautiful sunset over mountains\`
    `;
    
    createMessage('bot', helpText);
}
        
        // Toggle sidebar
        function toggleSidebar() {
            if (sidebar) {
                sidebar.classList.toggle('visible');
                if (sidebarIcon) {
                    sidebarIcon.textContent = sidebar.classList.contains('visible') ? '✕' : '☰';
                }
            }
        }
        
        // Update credits display
        function updateCreditsDisplay(credits) {
            const creditCount = document.getElementById('creditCount');
            const creditCountHeader = document.getElementById('creditCountHeader');
            if (creditCount) creditCount.textContent = credits;
            if (creditCountHeader) creditCountHeader.textContent = credits;
        }
        
        // Check if user has credits - renamed to avoid conflict with Python function
        async function checkUserCredits() {
            if (isAdmin) return true;
            
            try {
                const response = await fetch('/api/check-credits');
                const data = await response.json();
                
                if (!data.has_credits) {
                    showStatus('❌ Insufficient credits!', 'error');
                    return false;
                }
                return true;
            } catch (err) {
                console.error('Credit check error:', err);
                showStatus('❌ Error checking credits. Please refresh the page.', 'error');
                return false;
            }
        }
        
        // Get current credits
        async function getCurrentCredits() {
            try {
                const response = await fetch('/api/get-credits');
                const data = await response.json();
                if (data.success) {
                    updateCreditsDisplay(data.credits);
                    return data.credits;
                }
            } catch (err) {
                console.error('Error getting credits:', err);
            }
            return 0;
        }
        
        // Logout
        async function logout() {
            try {
                // Clear all global variables
                currentConversationId = null;
                conversations = {};
                processing = false;
                currentBotMessage = null;
                selectedUserId = null;
                
                // Disable send button
                if (sendBtn) {
                    sendBtn.disabled = true;
                }
                
                // Clear input
                if (input) {
                    input.value = '';
                    input.disabled = true;
                }
                
                // Show logout status
                showStatus('🔄 Logging out...', 'warning');
                
                // Send logout request
                const response = await fetch('/logout');
                if (response.ok) {
                    showStatus('✅ Logout successful! Redirecting...', 'success');
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    throw new Error('Logout failed');
                }
            } catch (err) {
                console.error('Logout error:', err);
                showStatus('❌ Logout failed. Please try again.', 'error');
                
                // Re-enable input
                if (input) {
                    input.disabled = false;
                }
                if (sendBtn) {
                    sendBtn.disabled = false;
                }
            }
        }
        
        // Initialize app
        async function initialize() {
            await loadConversations();
            if (Object.keys(conversations).length === 0) {
                await createNewChat();
            } else {
                const sorted = Object.values(conversations).sort((a, b) => 
                    new Date(b.updated_at) - new Date(a.updated_at)
                );
                if (sorted.length > 0) {
                    await switchConversation(sorted[0].id);
                }
            }
        }
        
        // Load conversations
        async function loadConversations() {
            try {
                const response = await fetch('/api/conversations');
                const data = await response.json();
                if (data.success) {
                    conversations = data.conversations;
                    renderConversationsList();
                }
            } catch (err) {
                console.error('Failed to load conversations:', err);
                showStatus('❌ Failed to load conversations', 'error');
            }
        }
        
        // Render conversations list
        function renderConversationsList() {
            const list = document.getElementById('conversationsList');
            if (!list) return;
            
            const sortedConvs = Object.values(conversations).sort((a, b) => 
                new Date(b.updated_at) - new Date(a.updated_at)
            );

            if (sortedConvs.length === 0) {
                list.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">💬</div>
                        <p>No conversations yet</p>
                        <p style="font-size: 0.875rem; margin-top: 0.5rem;">Start a new chat!</p>
                    </div>
                `;
                return;
            }

            list.innerHTML = sortedConvs.map(conv => {
                const date = new Date(conv.updated_at);
                const now = new Date();
                const diffMs = now - date;
                const diffMins = Math.floor(diffMs / 60000);
                const diffHours = Math.floor(diffMs / 3600000);
                const diffDays = Math.floor(diffMs / 86400000);
                
                let timeAgo;
                if (diffMins < 1) timeAgo = 'Just now';
                else if (diffMins < 60) timeAgo = `${diffMins}m ago`;
                else if (diffHours < 24) timeAgo = `${diffHours}h ago`;
                else if (diffDays < 7) timeAgo = `${diffDays}d ago`;
                else timeAgo = date.toLocaleDateString();
                
                const isActive = conv.id === currentConversationId;
                
                return `
                    <div class="conversation-item ${isActive ? 'active' : ''}" 
                         onclick="switchConversation('${conv.id}')">
                        <div class="conversation-title">${escapeHtml(conv.title)}</div>
                        <div class="conversation-date">${timeAgo}</div>
                        <button class="conversation-delete" onclick="event.stopPropagation(); deleteConversation('${conv.id}')">×</button>
                    </div>
                `;
            }).join('');
        }
        
        // Create new chat
        async function createNewChat() {
            try {
                const response = await fetch('/api/conversation/new', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    conversations[data.conversation_id] = {
                        id: data.conversation_id,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                        title: 'New Chat',
                        messages: [],
                        history: []
                    };
                    
                    await switchConversation(data.conversation_id);
                    renderConversationsList();
                    showStatus('✅ New conversation created');
                    
                    // Auto-hide sidebar on mobile
                    if (window.innerWidth <= 1024) {
                        toggleSidebar();
                    }
                }
            } catch (err) {
                showStatus('❌ Failed to create conversation', 'error');
            }
        }
        
        // Switch conversation
        async function switchConversation(convId) {
            try {
                const response = await fetch(`/api/conversation/${convId}`);
                const data = await response.json();
                
                if (data.success) {
                    currentConversationId = convId;
                    conversations[convId] = data.conversation;
                    
                    renderConversation(data.conversation);
                    renderConversationsList();
                    
                    // Dispatch event for sidebar closing on mobile
                    document.dispatchEvent(new Event('conversationSwitched'));
                    
                    showStatus('✅ Conversation loaded');
                }
            } catch (err) {
                showStatus('❌ Failed to load conversation', 'error');
            }
        }
        
        // Render conversation messages
function renderConversation(conv) {
    if (!chat) return;
    
    chat.innerHTML = '';
    
    // Only show welcome message if conversation is empty
    if (!conv.messages || conv.messages.length === 0) {
        const avatarHtml = botAvatarType === 'image' && botAvatarUrl 
            ? `<img src="${botAvatarUrl}" alt="Bot">`
            : botAvatar;
        
        let welcomeMessage = `
            <div class="message bot">
                <div class="message-wrapper">
                    <div class="avatar bot">${avatarHtml}</div>
                    <div class="message-content">
                        <strong>Hello {{ username }}! I'm ${botName}</strong><br><br>
                        I'm an intelligent assistant that can:<br>
                        • Chat and answer questions<br>
                        • Write and debug code<br>
                        • Generate AI images with ClipFly<br><br>
                        <strong>Image Generation Commands:</strong><br>
                        • <code>/gen &lt;prompt&gt;</code> - Generate images<br>
                        • <code>/model</code> - Show AI models<br>
                        • <code>/setcount</code> - Set image count<br>
                        • <code>/help</code> - Show all commands<br><br>
                        ${!isAdmin ? `<em>You have {{ user_credits }} credits remaining.</em><br><br>` : ''}
                        <em>How can I assist you today?</em>
                    </div>
                </div>
            </div>
        `;
        
        chat.innerHTML = welcomeMessage;
    }
    
    // Render saved messages
    if (conv.messages && conv.messages.length > 0) {
        conv.messages.forEach(msg => {
            const msgEl = document.createElement('div');
            msgEl.className = 'message ' + msg.role;
            
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar ' + msg.role;
            
            if (msg.role === 'user') {
                avatar.textContent = '👤';
            } else {
                if (botAvatarType === 'image' && botAvatarUrl) {
                    avatar.innerHTML = `<img src="${botAvatarUrl}" alt="Bot">`;
                } else {
                    avatar.textContent = botAvatar;
                }
            }
            
            const content = document.createElement('div');
            content.className = 'message-content';
            content.innerHTML = msg.role === 'bot' ? formatText(msg.content) : escapeHtml(msg.content);
            
            wrapper.appendChild(avatar);
            wrapper.appendChild(content);
            msgEl.appendChild(wrapper);
            chat.appendChild(msgEl);
        });
    }
    
    chat.scrollTop = chat.scrollHeight;
}
        
        // Delete conversation
        async function deleteConversation(convId) {
            if (!confirm('Are you sure you want to delete this conversation?')) return;
            
            try {
                const response = await fetch(`/api/conversation/${convId}`, { method: 'DELETE' });
                const data = await response.json();
                
                if (data.success) {
                    delete conversations[convId];
                    
                    if (currentConversationId === convId) {
                        const remaining = Object.keys(conversations);
                        if (remaining.length > 0) {
                            await switchConversation(remaining[0]);
                        } else {
                            await createNewChat();
                        }
                    } else {
                        renderConversationsList();
                    }
                    
                    showStatus('✅ Conversation deleted');
                }
            } catch (err) {
                showStatus('❌ Failed to delete conversation', 'error');
            }
        }
        
        // Clear current chat
        async function clearCurrentChat() {
            if (!currentConversationId) return;
            if (!confirm('Clear all messages in this conversation?')) return;
            
            try {
                const response = await fetch(`/api/conversation/${currentConversationId}/clear`, { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    conversations[currentConversationId].messages = [];
                    conversations[currentConversationId].history = [];
                    renderConversation(conversations[currentConversationId]);
                    showStatus('✅ Conversation cleared');
                }
            } catch (err) {
                showStatus('❌ Failed to clear conversation', 'error');
            }
        }
        
        // Show status message
        function showStatus(msg, type = 'success') {
            if (!status) return;
            
            status.textContent = msg;
            status.className = 'status ' + type;
            
            if (type === 'success') {
                setTimeout(() => {
                    if (status) {
                        status.textContent = 'Ready';
                        status.className = 'status';
                    }
                }, 3000);
            }
        }
        
        // Create message element
        function createMessage(type, initial = '') {
            if (!chat) return null;
            
            const msg = document.createElement('div');
            msg.className = 'message ' + type;
            
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar ' + type;
            
            if (type === 'user') {
                avatar.textContent = '👤';
            } else {
                if (botAvatarType === 'image' && botAvatarUrl) {
                    avatar.innerHTML = `<img src="${botAvatarUrl}" alt="Bot">`;
                } else {
                    avatar.textContent = botAvatar;
                }
            }
            
            const content = document.createElement('div');
            content.className = 'message-content';
            
            if (type === 'bot' && !initial) {
                content.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
            } else {
                content.innerHTML = type === 'bot' ? formatText(initial) : escapeHtml(initial);
            }
            
            wrapper.appendChild(avatar);
            wrapper.appendChild(content);
            msg.appendChild(wrapper);
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
            
            return content;
        }
        
        // Update bot message
        function updateBotMessage(content, text) {
            if (!content) return;
            content.innerHTML = formatText(text);
            if (chat) chat.scrollTop = chat.scrollHeight;
        }
        
        // Send message function
        async function sendMessage() {
            if (processing) {
                return;
            }
            
            if (!currentConversationId) {
                showStatus('❌ Please create or select a conversation first', 'error');
                return;
            }
            
            const msg = input.value.trim();
            
            if (!msg) {
                showStatus('Please type a message', 'warning');
                return;
            }
            
            // Check if it's a command
            if (msg.startsWith('/')) {
                await handleCommand(msg);
                input.value = '';
                input.style.height = 'auto';
                return;
            }
            
            // Check credits for non-admin users for regular chat
            const mode = document.getElementById('mode').value;
            if (mode !== 'image' && !isAdmin) {
                const hasCredits = await checkUserCredits();
                if (!hasCredits) {
                    return;
                }
            }

            processing = true;
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;
            
            createMessage('user', msg);
            currentBotMessage = createMessage('bot');

            try {
                const conv = conversations[currentConversationId];
                
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: msg,
                        mode: mode,
                        history: conv.history || [],
                        conversation_id: currentConversationId
                    })
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Server error: ${response.status} - ${errorText}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullText = '';

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                break;
                            }
                            
                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.token) {
                                    fullText += parsed.token;
                                    updateBotMessage(currentBotMessage, fullText);
                                } else if (parsed.error) {
                                    throw new Error(parsed.error);
                                }
                            } catch (e) {
                                // Ignore JSON parsing errors for incomplete chunks
                            }
                        }
                    }
                }

                // Save to conversation
                conv.history = conv.history || [];
                conv.messages = conv.messages || [];
                
                conv.history.push({role: 'user', content: msg});
                conv.history.push({role: 'assistant', content: fullText});
                conv.messages.push({role: 'user', content: msg});
                conv.messages.push({role: 'bot', content: fullText});
                conv.updated_at = new Date().toISOString();
                
                // Update title if first message
                if (conv.messages.length === 2) {
                    conv.title = msg.substring(0, 50) + (msg.length > 50 ? '...' : '');
                }
                
                // Save conversation
                await saveConversation(currentConversationId);
                renderConversationsList();
                
                // Update credits display for non-admin users
                if (!isAdmin && mode !== 'image') {
                    await getCurrentCredits();
                }
                
                const time = document.createElement('div');
                time.className = 'timestamp';
                time.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                if (currentBotMessage) {
                    currentBotMessage.appendChild(time);
                }
                
                showStatus('✅ Message sent');

            } catch (err) {
                console.error('Error in sendMessage:', err);
                if (currentBotMessage) {
                    updateBotMessage(currentBotMessage, '❌ Error: ' + err.message);
                }
                showStatus('❌ Error: ' + err.message, 'error');
            } finally {
                sendBtn.disabled = false;
                processing = false;
                if (input) {
                    input.focus();
                }
            }
        }
        
        // Handle commands
async function handleCommand(command) {
    const parts = command.split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);
    
    switch (cmd) {
        case '/gen':
            if (args.length > 0) {
                showImageGenerationModal(args.join(' '));
            } else {
                showImageGenerationModal('');
            }
            break;
            
        case '/model':
            showModelSelection();
            break;
            
        case '/setmodel':
            if (args.length > 0) {
                const modelNum = args[0];
                if (AVAILABLE_MODELS[modelNum]) {
                    currentModelId = AVAILABLE_MODELS[modelNum].id;
                    saveUserPreference('model', currentModelId);
                    createMessage('bot', `✅ Model updated to ${AVAILABLE_MODELS[modelNum].name}`);
                } else {
                    createMessage('bot', '❌ Invalid model number. Use `/model` to see available models.');
                }
            } else {
                createMessage('bot', '❌ Please specify a model number. Example: `/setmodel 2`');
            }
            break;
            
        case '/mymodel':
            showCurrentModel();
            break;
            
        case '/setcount':
            if (args.length > 0) {
                const count = parseInt(args[0]);
                if (count >= 1 && count <= 10) {
                    currentImageCount = count;
                    saveUserPreference('image_count', count);
                    createMessage('bot', `✅ Image count updated to ${count}`);
                } else {
                    createMessage('bot', '❌ Please specify a number between 1 and 10.');
                }
            } else {
                createMessage('bot', '❌ Please specify a number. Example: `/setcount 3`');
            }
            break;
            
        case '/mycount':
            showCurrentImageCount();
            break;
            
        case '/tokens':
            showTokenStatus();
            break;
            
        case '/help':
            showHelp();
            break;
            
        default:
            // Don't show error for just "/"
            if (cmd !== '/') {
                createMessage('bot', `❌ Unknown command: ${cmd}. Type /help for available commands.`);
            }
    }
}
        
        // Save conversation
        async function saveConversation(convId) {
            try {
                await fetch(`/api/conversation/${convId}/save`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(conversations[convId])
                });
            } catch (err) {
                console.error('Failed to save conversation:', err);
            }
        }
        
        // Utility functions
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function formatText(text) {
            let html = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            
            // Handle code blocks
            html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, function(match, lang, code) {
                const langLabel = lang ? `<div class="code-header">${lang}</div>` : '';
                return `<pre>${langLabel}<code>${escapeHtml(code.trim())}</code></pre>`;
            });
            
            // Handle inline code
            html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
            
            // Handle bold text
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            
            // Handle italic text
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
            
            // Handle line breaks
            html = html.replace(/\n/g, '<br>');
            
            return html;
        }
        
        // Admin Panel Functions
        function setAvatarType(type) {
            document.querySelectorAll('.avatar-type-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            if (type === 'text') {
                document.getElementById('textAvatarGroup').style.display = 'block';
                document.getElementById('imageAvatarGroup').style.display = 'none';
            } else {
                document.getElementById('textAvatarGroup').style.display = 'none';
                document.getElementById('imageAvatarGroup').style.display = 'block';
            }
        }
        
        function showTab(tabId) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab and mark button as active
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
            
            // Load users if user management tab is selected
            if (tabId === 'userManagement') {
                loadUsers();
            }
            
            // Load tokens if image settings tab is selected
            if (tabId === 'imageSettings') {
                loadTokens();
            }
        }
        
        function openAdmin() {
            if (!isAdmin) return;
            
            document.getElementById('adminModal').classList.add('show');
            document.getElementById('adminPassword').focus();
            document.getElementById('adminPassword').value = '';
            document.getElementById('adminSettings').style.display = 'none';
            document.getElementById('adminAction').textContent = 'Unlock';
            document.getElementById('adminAction').onclick = verifyPassword;
            
            // Show bot settings tab by default
            showTab('botSettings');
        }
        
        function closeAdmin() {
            document.getElementById('adminModal').classList.remove('show');
            document.getElementById('adminPassword').value = '';
            document.getElementById('adminSettings').style.display = 'none';
            document.getElementById('adminAction').textContent = 'Unlock';
            document.getElementById('adminAction').onclick = verifyPassword;
        }
        
        async function verifyPassword() {
            const password = document.getElementById('adminPassword').value;
            
            if (!password) {
                showStatus('Please enter admin password', 'error');
                return;
            }
            
            try {
                const response = await fetch('/admin/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('adminSettings').style.display = 'block';
                    document.getElementById('adminAction').textContent = 'Save Changes';
                    document.getElementById('adminAction').onclick = saveSettings;
                    showStatus('✅ Admin access granted');
                } else {
                    showStatus('❌ Invalid password', 'error');
                }
            } catch (err) {
                showStatus('❌ Connection error', 'error');
            }
        }
        
        async function saveSettings() {
            const newName = document.getElementById('botName').value.trim();
            const newAvatar = document.getElementById('botAvatar').value.trim();
            const newAvatarUrl = document.getElementById('botAvatarUrl').value.trim();
            const newTagline = document.getElementById('botTagline').value.trim();
            const avatarType = document.querySelector('.avatar-type-btn.active').textContent.includes('Image') ? 'image' : 'text';
            
            if (!newName) {
                showStatus('Bot name is required', 'warning');
                return;
            }

            if (avatarType === 'text' && !newAvatar) {
                showStatus('Avatar text is required', 'warning');
                return;
            }

            if (avatarType === 'image' && !newAvatarUrl) {
                showStatus('Avatar image URL is required', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/admin/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: newName,
                        avatar: newAvatar,
                        avatar_type: avatarType,
                        avatar_url: newAvatarUrl,
                        tagline: newTagline
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showStatus('✅ Settings saved! Reloading...');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showStatus('❌ Save failed: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                showStatus('❌ Connection error', 'error');
            }
        }
        
        async function loadUsers() {
            try {
                const response = await fetch('/admin/users');
                const data = await response.json();
                
                if (data.success) {
                    const userData = document.getElementById('userData');
                    if (data.users.length === 0) {
                        userData.innerHTML = `
                            <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">👥</div>
                                <p>No users found</p>
                                <p style="font-size: 0.875rem; margin-top: 0.5rem;">Users will appear here when they register</p>
                            </div>
                        `;
                        return;
                    }
                    
                    let html = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';
                    data.users.forEach(u => {
                        const date = new Date(u.created_at);
                        const dateStr = date.toLocaleDateString();
                        const isSelected = u.id === selectedUserId;
                        
                        html += `
                            <div class="user-item" 
                                 data-user-id="${u.id}" 
                                 data-user-name="${u.username}"
                                 data-user-credits="${u.credits}"
                                 onclick="selectUser(this)"
                                 style="background: ${isSelected ? 'var(--primary-light)' : 'var(--bg-tertiary)'}; 
                                        padding: 1rem; 
                                        border-radius: var(--radius-md); 
                                        border: 1px solid ${isSelected ? 'var(--primary)' : 'var(--border)'}; 
                                        cursor: pointer;
                                        transition: all 0.2s;">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                                    <div style="flex: 1;">
                                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                            <strong style="color: ${u.credits > 0 ? 'var(--primary)' : 'var(--danger)'};">${u.username}</strong>
                                            <span style="font-size: 0.75rem; background: var(--bg-secondary); padding: 0.125rem 0.5rem; border-radius: var(--radius-sm); color: var(--text-secondary);">ID: ${u.id}</span>
                                        </div>
                                        <div style="font-size: 0.75rem; color: var(--text-secondary);">
                                            Created: ${dateStr} • Conversations: ${u.conversation_count || 0}
                                        </div>
                                    </div>
                                    <span style="font-weight: 700; color: ${u.credits > 0 ? 'var(--success)' : 'var(--danger)'}; font-size: 1.125rem;">
                                        ${u.credits}
                                    </span>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    userData.innerHTML = html;
                }
            } catch (err) {
                console.error('Could not load users:', err);
                showStatus('❌ Failed to load users', 'error');
            }
        }
        
        // Token management functions
        async function loadTokens() {
            try {
                const response = await fetch('/admin/tokens');
                const data = await response.json();
                
                if (data.success) {
                    const tokenCount = document.getElementById('tokenCount');
                    const tokenList = document.getElementById('tokenList');
                    
                    if (tokenCount) {
                        tokenCount.textContent = data.token_count;
                    }
                    
                    if (tokenList) {
                        if (data.tokens.length === 0) {
                            tokenList.innerHTML = '<div style="text-align: center; padding: 1rem; color: var(--text-muted);">No tokens available</div>';
                        } else {
                            let html = '<div style="display: flex; flex-direction: column; gap: 0.25rem;">';
                            data.tokens.forEach((token, i) => {
                                html += `
                                    <div style="padding: 0.5rem; background: var(--bg-secondary); border-radius: var(--radius-sm); font-family: monospace; font-size: 0.7rem; word-break: break-all;">
                                        ${i + 1}. ${token.slice(0, 20)}...${token.slice(-10)}
                                    </div>
                                `;
                            });
                            html += '</div>';
                            tokenList.innerHTML = html;
                        }
                    }
                }
            } catch (err) {
                console.error('Error loading tokens:', err);
            }
        }
        
        async function refreshTokens() {
            await loadTokens();
        }
        
        async function addTokens() {
            const newTokensInput = document.getElementById('newTokens');
            const tokensText = newTokensInput.value.trim();
            
            if (!tokensText) {
                showStatus('Please enter tokens', 'warning');
                return;
            }
            
            const tokens = tokensText.split('\n').map(t => t.trim()).filter(t => t && !t.startsWith('#'));
            
            if (tokens.length === 0) {
                showStatus('No valid tokens found', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/admin/add-tokens', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tokens: tokens })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showStatus(`✅ Added ${data.added_count} new tokens`, 'success');
                    newTokensInput.value = '';
                    await loadTokens();
                } else {
                    showStatus('❌ Failed to add tokens: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                console.error('Error adding tokens:', err);
                showStatus('❌ Connection error', 'error');
            }
        }
        
        function selectUser(element) {
            // Remove selection from all users
            document.querySelectorAll('.user-item').forEach(item => {
                item.style.background = 'var(--bg-tertiary)';
                item.style.borderColor = 'var(--border)';
            });
            
            // Select this user
            element.style.background = 'var(--primary-light)';
            element.style.borderColor = 'var(--primary)';
            
            // Set selected user info
            selectedUserId = element.dataset.userId;
            
            // Update selected user info display
            const selectedUserInfo = document.getElementById('selectedUserInfo');
            const selectedUserName = document.getElementById('selectedUserName');
            const selectedUserIdSpan = document.getElementById('selectedUserId');
            const selectedUserCredits = document.getElementById('selectedUserCredits');
            
            selectedUserName.textContent = element.dataset.userName;
            selectedUserIdSpan.textContent = 'ID: ' + element.dataset.userId;
            selectedUserCredits.textContent = element.dataset.userCredits + ' credits';
            selectedUserCredits.style.color = element.dataset.userCredits > 0 ? 'var(--success)' : 'var(--danger)';
            
            selectedUserInfo.style.display = 'block';
        }
        
        function searchUsers() {
            const query = document.getElementById('searchUser').value.toLowerCase();
            const userItems = document.querySelectorAll('.user-item');
            
            userItems.forEach(item => {
                const username = item.dataset.userName.toLowerCase();
                const userId = item.dataset.userId.toLowerCase();
                
                if (username.includes(query) || userId.includes(query)) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        
        async function addCreditsToUser() {
            if (!selectedUserId) {
                showStatus('Please select a user first', 'warning');
                return;
            }
            
            const amount = parseInt(document.getElementById('addCreditsAmount').value);
            if (!amount || amount < 1 || amount > 1000) {
                showStatus('Please enter a valid amount (1-1000)', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/admin/add-credits', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: selectedUserId, amount })
                });
                
                const data = await response.json();
                if (data.success) {
                    showStatus(`✅ Added ${amount} credits to user`, 'success');
                    
                    // Update selected user credits display
                    const selectedUserCredits = document.getElementById('selectedUserCredits');
                    const currentCredits = parseInt(selectedUserCredits.textContent.split(' ')[0]);
                    selectedUserCredits.textContent = (currentCredits + amount) + ' credits';
                    selectedUserCredits.style.color = 'var(--success)';
                    
                    // Update the user item in the list
                    document.querySelectorAll('.user-item').forEach(item => {
                        if (item.dataset.userId === selectedUserId) {
                            item.dataset.userCredits = (parseInt(item.dataset.userCredits) + amount).toString();
                            const creditSpan = item.querySelector('span[style*="font-weight: 700"]');
                            if (creditSpan) {
                                creditSpan.textContent = item.dataset.userCredits;
                                creditSpan.style.color = item.dataset.userCredits > 0 ? 'var(--success)' : 'var(--danger)';
                            }
                        }
                    });
                    
                    document.getElementById('addCreditsAmount').value = '';
                } else {
                    showStatus('❌ ' + (data.error || 'Failed to add credits'), 'error');
                }
            } catch (err) {
                showStatus('❌ Connection error', 'error');
            }
        }
        
        // Preview avatar URL
        const avatarUrlInput = document.getElementById('botAvatarUrl');
        if (avatarUrlInput) {
            avatarUrlInput.addEventListener('input', function() {
                const preview = document.getElementById('avatarPreview');
                if (this.value) {
                    preview.innerHTML = `<img src="${this.value}" alt="Preview" onerror="this.parentElement.innerHTML='❌ Invalid Image'">`;
                } else {
                    preview.innerHTML = 'Preview';
                }
            });
        }
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && document.getElementById('adminModal').classList.contains('show')) {
                closeAdmin();
            }
            if (e.key === 'Escape' && document.getElementById('imageModal').classList.contains('show')) {
                closeImageModal();
            }
        });
        
        // Auto-focus on message input when clicking anywhere
        document.addEventListener('click', function(e) {
            if (!e.target.closest('#adminModal') && 
                !e.target.closest('.sidebar') && 
                !e.target.closest('.sidebar-toggle') &&
                !e.target.closest('#imageModal') &&
                input) {
                input.focus();
            }
        });
        
        // Handle window resize
        window.addEventListener('resize', function() {
            if (window.innerWidth > 1024 && sidebar) {
                sidebar.classList.add('visible');
            } else if (sidebar) {
                sidebar.classList.remove('visible');
                if (sidebarIcon) sidebarIcon.textContent = '☰';
            }
        });
        
        // Initialize responsive behavior
        if (window.innerWidth <= 1024 && sidebar) {
            sidebar.classList.remove('visible');
            if (sidebarIcon) sidebarIcon.textContent = '☰';
        }
    </script>
    {% endif %}
</body>
</html>
"""

class Assistant:
    def __init__(self):
        self.url = "https://app.deepenglish.com/api/chat-new"
        self.headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0"
        }
        
        self.code_prompt = """You are {bot_name} - an intelligent chatbot created by JHONWILSON.

You are capable of:
- Natural conversation on any topic
- Writing complete, production-ready code in any programming language
- Debugging and optimizing existing code
- Explaining complex concepts in simple terms
- Designing system architectures
- Solving problems and providing analysis
- Building applications from scratch
- Generating AI images with ClipFly (use /gen command)

Always provide clear, well-structured responses with proper code formatting when relevant.

Created by: JHONWILSON"""

    def process_streaming(self, msg, mode, hist):
        try:
            prompt = self.code_prompt.format(bot_name=BOT_SETTINGS['name'])
            
            if mode == 'code':
                msg = f"{prompt}\n\nUser: {msg}"
            elif mode == 'hybrid':
                msg = f"{prompt}\n\n{msg}"
            elif mode == 'image':
                msg = f"{prompt}\n\nUser wants to generate an image: {msg}. Please guide them to use the /gen command or explain image generation features."
            
            msgs = hist[-5:] if len(hist) > 5 else hist.copy()
            msgs.append({"role": "user", "content": msg})
            
            payload = {
                "userInput": msg,
                "englishLevel": "B1",
                "isAutoReply": False,
                "messages": msgs,
                "projectName": "jhonwilson-ai",
                "temperature": 0.3 if mode == 'code' else 0.7,
                "useCorrection": False
            }
            
            res = requests.post(self.url, headers=self.headers, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            if "message" in data and data.get("success"):
                reply = data["message"]
                
                words = reply.split(' ')
                for i, word in enumerate(words):
                    yield json.dumps({"token": word + (' ' if i < len(words)-1 else '')}) + '\n'
                    time.sleep(0.03)
                
                yield "data: [DONE]\n\n"
            else:
                yield json.dumps({"error": "No response from AI"}) + '\n'
                
        except Exception as e:
            yield json.dumps({"error": str(e)}) + '\n'

ai = Assistant()

# Image generation task storage
IMAGE_GENERATION_TASKS = {}
IMAGE_GENERATION_RESULTS = {}

def track_visitor(request):
    """Track visitor information from request"""
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip:
            ip = ip.split(',')[0].strip()
        
        user_agent = request.headers.get('User-Agent', '')
        referer = request.headers.get('Referer', '')
        
        fb_user = request.args.get('fbclid') or request.args.get('fb_user') or None
        source = 'Direct'
        
        if 'facebook' in referer.lower() or 'fb' in referer.lower():
            source = 'Facebook'
        elif 'facebook' in user_agent.lower() or 'FB' in user_agent:
            source = 'Facebook App'
        elif fb_user:
            source = 'Facebook Link'
        elif referer:
            source = urlparse(referer).netloc or 'Referral'
        
        if not fb_user and 'fbclid' in request.url:
            fb_user = 'FB User'
        
        visitor = {
            'timestamp': datetime.now().isoformat(),
            'ip': ip,
            'source': source,
            'fb_user': fb_user,
            'user_agent': user_agent[:100],
            'referer': referer[:200]
        }
        
        # Store in session for later use
        session['visitor_info'] = visitor
        
        send_telegram_notification(visitor)
        
        return fb_user, source
        
    except Exception as e:
        print(f"Tracking error: {e}")
        return None, 'Unknown'

@app.route('/')
def home():
    if 'user_id' not in session:
        fb_user, fb_source = track_visitor(request)
        
        return render_template_string(
            HTML_TEMPLATE,
            bot_name=BOT_SETTINGS['name'],
            bot_avatar=BOT_SETTINGS['avatar'],
            bot_avatar_type=BOT_SETTINGS['avatar_type'],
            bot_avatar_url=BOT_SETTINGS['avatar_url'],
            bot_tagline=BOT_SETTINGS['tagline'],
            logged_in=False,
            free_credits=FREE_CREDITS
        )
    
    # User is logged in
    user_id = session['user_id']
    username = session['username']
    is_admin = user_id == ADMIN_USER_ID
    user_credits = USERS[user_id]['credits'] if user_id in USERS else 0
    
    return render_template_string(
        HTML_TEMPLATE,
        bot_name=BOT_SETTINGS['name'],
        bot_avatar=BOT_SETTINGS['avatar'],
        bot_avatar_type=BOT_SETTINGS['avatar_type'],
        bot_avatar_url=BOT_SETTINGS['avatar_url'],
        bot_tagline=BOT_SETTINGS['tagline'],
        logged_in=True,
        username=username,
        user_id=user_id,
        user_avatar=username[0].upper() if username else 'U',
        user_credits=user_credits,
        is_admin=is_admin,
        users_count=len(USERS) - 1  # Exclude admin
    )

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"success": False, "error": "Username and password required"})
        
        hashed_password = hash_password(password)
        
        # Check if admin
        if username == 'admin' and password == ADMIN_PASSWORD:
            session['user_id'] = ADMIN_USER_ID
            session['username'] = 'admin'
            
            # Initialize admin user if not exists
            if ADMIN_USER_ID not in USERS:
                USERS[ADMIN_USER_ID] = {
                    'id': ADMIN_USER_ID,
                    'username': 'admin',
                    'password': hash_password(ADMIN_PASSWORD),
                    'credits': 999999,  # Infinite credits for admin
                    'created_at': datetime.now().isoformat(),
                    'conversations': []
                }
            
            return jsonify({"success": True, "is_admin": True})
        
        # Check existing user
        user_found = None
        for user_id, user in USERS.items():
            if user['username'] == username and user['password'] == hashed_password:
                user_found = user_id
                break
        
        # Create new user if not found
        if not user_found:
            user_id = generate_user_id()
            USERS[user_id] = {
                'id': user_id,
                'username': username,
                'password': hashed_password,
                'credits': FREE_CREDITS,
                'created_at': datetime.now().isoformat(),
                'conversations': []
            }
            user_found = user_id
        
        # Set session
        session['user_id'] = user_found
        session['username'] = username
        
        return jsonify({"success": True, "is_admin": False})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        user_id = session['user_id']
        
        # Check credits for non-admin users
        if user_id != ADMIN_USER_ID and not user_has_credits(user_id):
            return jsonify({"error": "Insufficient credits"}), 403
        
        data = request.json
        msg = data.get('message', '').strip()
        conv_id = data.get('conversation_id')
        
        if not msg:
            return jsonify({"error": "Empty message"}), 400
        
        # Use credit for non-admin users
        if user_id != ADMIN_USER_ID:
            if not use_credit(user_id):
                return jsonify({"error": "Failed to use credit"}), 500
        
        # Update conversation title if first message
        if conv_id and conv_id in CONVERSATIONS:
            if len(CONVERSATIONS[conv_id]['messages']) == 0:
                update_conversation_title(conv_id, msg)
        
        # Send notification to Telegram
        send_telegram_conversation(user_id, conv_id, msg)
        
        if msg.lower() == 'help':
            help_text = f"""{BOT_SETTINGS['name']} - Help

Modes:
• Chat Mode: General conversation and assistance
• Code Mode: Programming and development focus
• Hybrid Mode: Balanced approach for both
• Image Mode: AI image generation focus

Image Generation Commands:
• /gen <prompt> - Generate AI images
• /model - Show available AI models
• /setmodel <number> - Set default model
• /mymodel - Show your current model
• /setcount <number> - Set image count (1-10)
• /mycount - Show your current image count
• /tokens - Check available tokens
• /help - Show this help

Examples:
• "Build a Flask REST API"
• "Explain how databases work"
• "Write a Python web scraper"
• "/gen a beautiful sunset over mountains"

Features:
• Real-time streaming responses
• Support for any programming language
• Complex problem solving
• Code generation and debugging
• AI image generation with ClipFly
• Persistent conversation history

Created by JHONWILSON"""
            
            def generate():
                words = help_text.split(' ')
                for i, word in enumerate(words):
                    yield f"data: {json.dumps({'token': word + (' ' if i < len(words)-1 else '')})}\n\n"
                    time.sleep(0.02)
                yield "data: [DONE]\n\n"
            
            return Response(generate(), mimetype='text/event-stream')
        
        def generate():
            for chunk in ai.process_streaming(
                msg,
                data.get('mode', 'chat'),
                data.get('history', [])
            ):
                yield f"data: {chunk}\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Image Generation API endpoints
@app.route('/api/generate-image', methods=['POST'])
@login_required
def api_generate_image():
    try:
        user_id = session['user_id']
        
        # Check credits for non-admin users
        if user_id != ADMIN_USER_ID and not user_has_credits(user_id):
            return jsonify({"success": False, "error": "Insufficient credits"}), 403
        
        data = request.json
        prompt = data.get('prompt', '').strip()
        model_id = data.get('model_id', 'nanobanana')
        image_count = min(max(int(data.get('image_count', 1)), 1), 10)
        conv_id = data.get('conversation_id')
        
        if not prompt:
            return jsonify({"success": False, "error": "Prompt is required"}), 400
        
        # Use credit for non-admin users (1 credit per image)
        if user_id != ADMIN_USER_ID:
            if not use_credit(user_id):
                return jsonify({"success": False, "error": "Failed to use credit"}), 500
        
        # Load tokens
        tokens = load_clipfly_tokens()
        if not tokens:
            return jsonify({"success": False, "error": "No ClipFly tokens available"}), 500
        
        if len(tokens) < image_count:
            return jsonify({"success": False, "error": f"Not enough tokens. Need {image_count}, have {len(tokens)}"}), 400
        
        # Generate task ID
        task_id = str(uuid.uuid4())[:12]
        
        # Store task info
        IMAGE_GENERATION_TASKS[task_id] = {
            'user_id': user_id,
            'prompt': prompt,
            'model_id': model_id,
            'image_count': image_count,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'conversation_id': conv_id,
            'progress': 0,
            'token': tokens[0] if tokens else None
        }
        
        # Start generation in background thread
        def generate_images():
            try:
                print(f"Starting image generation for task {task_id}")
                
                # Update task status
                IMAGE_GENERATION_TASKS[task_id]['status'] = 'processing'
                IMAGE_GENERATION_TASKS[task_id]['progress'] = 10
                
                # Generate image
                result = generate_image_with_auto_reload(
                    tokens,
                    prompt,
                    model_id,
                    gnum=image_count
                )
                
                if result.get("success"):
                    task_data = result.get("data", {})
                    api_task_id = result.get("task_id")
                    queue_id = result.get("queue_id")
                    token = result.get("token")
                    
                    # Update task with API info
                    IMAGE_GENERATION_TASKS[task_id]['api_task_id'] = api_task_id
                    IMAGE_GENERATION_TASKS[task_id]['queue_id'] = queue_id
                    IMAGE_GENERATION_TASKS[task_id]['token'] = token
                    IMAGE_GENERATION_TASKS[task_id]['progress'] = 30
                    
                    # Wait for generation to complete
                    start_time = time.time()
                    image_url = None
                    
                    while time.time() - start_time < MAX_WAIT_TIME:
                        # Check queue status
                        queue_response = get_queue_list(token, queue_id)
                        
                        if queue_response.get("success"):
                            task = find_task_in_queue(
                                queue_response.get("data", {}),
                                task_id=api_task_id,
                                queue_id=queue_id
                            )
                            
                            if task:
                                status = task.get("status")
                                
                                if status == 2:  # Completed
                                    image_url = extract_image_url(task)
                                    if image_url:
                                        IMAGE_GENERATION_TASKS[task_id]['status'] = 'completed'
                                        IMAGE_GENERATION_TASKS[task_id]['progress'] = 100
                                        IMAGE_GENERATION_TASKS[task_id]['image_url'] = image_url
                                        
                                        # Store result
                                        IMAGE_GENERATION_RESULTS[task_id] = {
                                            'image_url': image_url,
                                            'model_id': model_id,
                                            'prompt': prompt,
                                            'completed_at': datetime.now().isoformat()
                                        }
                                        break
                                elif status == 3:  # Failed
                                    error = task.get("error_msg", "Unknown error")
                                    IMAGE_GENERATION_TASKS[task_id]['status'] = 'failed'
                                    IMAGE_GENERATION_TASKS[task_id]['error'] = error
                                    break
                        
                        # Update progress
                        elapsed = time.time() - start_time
                        progress = min(30 + int((elapsed / MAX_WAIT_TIME) * 60), 90)
                        IMAGE_GENERATION_TASKS[task_id]['progress'] = progress
                        
                        time.sleep(CHECK_INTERVAL)
                    
                    if not image_url:
                        IMAGE_GENERATION_TASKS[task_id]['status'] = 'failed'
                        IMAGE_GENERATION_TASKS[task_id]['error'] = 'Generation timeout'
                    
                else:
                    error = result.get("error", "Unknown error")
                    IMAGE_GENERATION_TASKS[task_id]['status'] = 'failed'
                    IMAGE_GENERATION_TASKS[task_id]['error'] = error
                    print(f"Image generation failed: {error}")
                    
            except Exception as e:
                print(f"Error in image generation thread: {e}")
                IMAGE_GENERATION_TASKS[task_id]['status'] = 'failed'
                IMAGE_GENERATION_TASKS[task_id]['error'] = str(e)
        
        # Start background thread
        thread = threading.Thread(target=generate_images)
        thread.daemon = True
        thread.start()
        
        # Send notification to Telegram
        send_telegram_conversation(user_id, conv_id, f"🖼️ Image generation started: {prompt}")
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Image generation started"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/image-status/<task_id>', methods=['GET'])
@login_required
def api_image_status(task_id):
    try:
        user_id = session['user_id']
        
        if task_id not in IMAGE_GENERATION_TASKS:
            return jsonify({"success": False, "error": "Task not found"}), 404
        
        task = IMAGE_GENERATION_TASKS[task_id]
        
        # Check if user owns this task
        if task['user_id'] != user_id and user_id != ADMIN_USER_ID:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        response = {
            "success": True,
            "task_id": task_id,
            "status": task['status'],
            "progress": task.get('progress', 0)
        }
        
        if task['status'] == 'completed':
            response['image_url'] = task.get('image_url')
            # Get model name
            model_name = task['model_id']
            for key, model in AVAILABLE_MODELS.items():
                if model['id'] == task['model_id']:
                    model_name = model['name']
                    break
            response['model_name'] = model_name
            
        elif task['status'] == 'failed':
            response['error'] = task.get('error', 'Unknown error')
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/token-status', methods=['GET'])
@login_required
def api_token_status():
    try:
        tokens = load_clipfly_tokens()
        return jsonify({
            "success": True,
            "token_count": len(tokens),
            "tokens": tokens[:5]  # Only return first 5 for security
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/user/preferences', methods=['GET'])
@login_required
def api_get_user_preferences():
    try:
        user_id = session['user_id']
        
        preferences = {
            'model': USER_IMAGE_MODELS.get(user_id, 'nanobanana'),
            'image_count': USER_IMAGE_COUNTS.get(user_id, 1)
        }
        
        return jsonify({
            "success": True,
            "preferences": preferences
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/user/preferences', methods=['POST'])
@login_required
def api_save_user_preferences():
    try:
        user_id = session['user_id']
        data = request.json
        
        if 'model' in data:
            USER_IMAGE_MODELS[user_id] = data['model']
        
        if 'image_count' in data:
            count = int(data['image_count'])
            if 1 <= count <= 10:
                USER_IMAGE_COUNTS[user_id] = count
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# User API endpoints
@app.route('/api/check-credits', methods=['GET'])
@login_required
def check_credits():
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({"has_credits": False, "error": "No user session"})
        
        # Admin has infinite credits
        if user_id == ADMIN_USER_ID:
            return jsonify({"has_credits": True, "is_admin": True})
        
        if user_id in USERS:
            credits = USERS[user_id].get('credits', 0)
            has_credits = credits > 0
            return jsonify({"has_credits": has_credits, "credits": credits})
        else:
            return jsonify({"has_credits": False, "error": "User not found"})
            
    except Exception as e:
        return jsonify({"has_credits": False, "error": str(e)})

@app.route('/api/get-credits', methods=['GET'])
@login_required
def get_credits():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"success": False, "error": "No user session"})
        
        if user_id in USERS:
            credits = USERS[user_id].get('credits', 0)
            return jsonify({"success": True, "credits": credits})
        else:
            return jsonify({"success": False, "error": "User not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Conversation API endpoints
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    user_id = session['user_id']
    user_conversations = {}
    
    for conv_id, conv in CONVERSATIONS.items():
        if conv['user_id'] == user_id:
            user_conversations[conv_id] = conv
    
    return jsonify({"success": True, "conversations": user_conversations})

@app.route('/api/conversation/new', methods=['POST'])
@login_required
def new_conversation():
    user_id = session['user_id']
    conv_id = create_new_conversation(user_id)
    return jsonify({"success": True, "conversation_id": conv_id})

@app.route('/api/conversation/<conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    if conv_id in CONVERSATIONS and CONVERSATIONS[conv_id]['user_id'] == session['user_id']:
        return jsonify({"success": True, "conversation": CONVERSATIONS[conv_id]})
    return jsonify({"success": False, "error": "Conversation not found"})

@app.route('/api/conversation/<conv_id>/save', methods=['POST'])
@login_required
def save_conversation(conv_id):
    data = request.json
    if conv_id in CONVERSATIONS and CONVERSATIONS[conv_id]['user_id'] == session['user_id']:
        CONVERSATIONS[conv_id].update(data)
        CONVERSATIONS[conv_id]['updated_at'] = datetime.now().isoformat()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Conversation not found"})

@app.route('/api/conversation/<conv_id>/clear', methods=['POST'])
@login_required
def clear_conversation(conv_id):
    if conv_id in CONVERSATIONS and CONVERSATIONS[conv_id]['user_id'] == session['user_id']:
        CONVERSATIONS[conv_id]['messages'] = []
        CONVERSATIONS[conv_id]['history'] = []
        CONVERSATIONS[conv_id]['updated_at'] = datetime.now().isoformat()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Conversation not found"})

@app.route('/api/conversation/<conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    if conv_id in CONVERSATIONS and CONVERSATIONS[conv_id]['user_id'] == session['user_id']:
        # Remove from user's conversations list
        user_id = CONVERSATIONS[conv_id]['user_id']
        if user_id in USERS and conv_id in USERS[user_id]['conversations']:
            USERS[user_id]['conversations'].remove(conv_id)
        
        # Delete conversation
        del CONVERSATIONS[conv_id]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Conversation not found"})

# Admin API endpoints
@app.route('/admin/verify', methods=['POST'])
@login_required
@admin_required
def verify_admin():
    data = request.json
    password = data.get('password', '')
    
    if password == ADMIN_PASSWORD:
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/admin/save', methods=['POST'])
@login_required
@admin_required
def save_admin_settings():
    try:
        data = request.json
        
        BOT_SETTINGS['name'] = data.get('name', BOT_SETTINGS['name'])
        BOT_SETTINGS['avatar'] = data.get('avatar', BOT_SETTINGS['avatar'])
        BOT_SETTINGS['avatar_type'] = data.get('avatar_type', BOT_SETTINGS['avatar_type'])
        BOT_SETTINGS['avatar_url'] = data.get('avatar_url', BOT_SETTINGS['avatar_url'])
        BOT_SETTINGS['tagline'] = data.get('tagline', BOT_SETTINGS['tagline'])
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users_list = []
    for user_id, user in USERS.items():
        if user_id != ADMIN_USER_ID:  # Exclude admin from list
            users_list.append({
                'id': user_id,
                'username': user['username'],
                'credits': user['credits'],
                'created_at': user['created_at'],
                'conversation_count': len(user.get('conversations', []))
            })
    
    # Sort by creation date (newest first)
    users_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({"success": True, "users": users_list})

@app.route('/admin/add-credits', methods=['POST'])
@login_required
@admin_required
def admin_add_credits():
    try:
        data = request.json
        user_id = data.get('user_id')
        amount = int(data.get('amount', 0))
        
        if not user_id or amount <= 0:
            return jsonify({"success": False, "error": "Invalid request"})
        
        if user_id not in USERS:
            return jsonify({"success": False, "error": "User not found"})
        
        add_credits(user_id, amount)
        return jsonify({"success": True, "new_credits": USERS[user_id]['credits']})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Token management endpoints
@app.route('/admin/tokens', methods=['GET'])
@login_required
@admin_required
def admin_get_tokens():
    try:
        tokens = load_clipfly_tokens()
        return jsonify({
            "success": True,
            "token_count": len(tokens),
            "tokens": tokens
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/admin/add-tokens', methods=['POST'])
@login_required
@admin_required
def admin_add_tokens():
    try:
        data = request.json
        new_tokens = data.get('tokens', [])
        
        if not new_tokens:
            return jsonify({"success": False, "error": "No tokens provided"})
        
        # Load existing tokens
        existing_tokens = load_clipfly_tokens()
        
        # Add new tokens
        added_count = 0
        for token in new_tokens:
            token = token.strip()
            if token and token not in existing_tokens:
                existing_tokens.append(token)
                added_count += 1
        
        # Save tokens
        with open(CLIPFLY_TOKEN_FILE, "w") as f:
            for token in existing_tokens:
                f.write(f"{token}\n")
        
        return jsonify({
            "success": True,
            "added_count": added_count,
            "total_tokens": len(existing_tokens)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/debug')
@login_required
def debug():
    user_id = session.get('user_id')
    username = session.get('username')
    user_data = USERS.get(user_id, {})
    
    return jsonify({
        "user_id": user_id,
        "username": username,
        "user_data": user_data,
        "session": dict(session),
        "users_count": len(USERS),
        "conversations_count": len(CONVERSATIONS),
        "image_tasks_count": len(IMAGE_GENERATION_TASKS)
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok", 
        "users": len(USERS), 
        "conversations": len(CONVERSATIONS),
        "image_tasks": len(IMAGE_GENERATION_TASKS),
        "bot_name": BOT_SETTINGS['name'],
        "clipfly_tokens": len(load_clipfly_tokens())
    })

if __name__ == '__main__':
    # Initialize admin user
    if ADMIN_USER_ID not in USERS:
        USERS[ADMIN_USER_ID] = {
            'id': ADMIN_USER_ID,
            'username': 'admin',
            'password': hash_password(ADMIN_PASSWORD),
            'credits': 999999,
            'created_at': datetime.now().isoformat(),
            'conversations': []
        }
    
    # Ensure image directory exists
    ensure_image_directory()
    
    # Print startup info
    print("=" * 60)
    print(f"🤖 {BOT_SETTINGS['name']} Server Starting...")
    print(f"📱 Admin username: admin")
    print(f"🔐 Admin password: {ADMIN_PASSWORD}")
    print(f"🎁 New user credits: {FREE_CREDITS}")
    print(f"👥 Registered users: {len(USERS)}")
    print(f"🖼️ ClipFly tokens: {len(load_clipfly_tokens())}")
    print("=" * 60)
    print("Image Generation Commands:")
    print("  /gen <prompt> - Generate AI images")
    print("  /model - Show available AI models")
    print("  /setmodel <number> - Set default model")
    print("  /setcount <number> - Set image count (1-10)")
    print("  /tokens - Check available tokens")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
