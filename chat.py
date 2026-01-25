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

# User and conversation storage (in production, use a database)
USERS = {}
CONVERSATIONS = {}
MAX_CONVERSATIONS = 5000
FREE_CREDITS = 500  # Default free credits for new users

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

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{{ bot_name }}</title>
    <style>
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
            background: var(--bg-main);
            padding: 20px;
            background-image: 
                radial-gradient(at 40% 20%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
                radial-gradient(at 80% 0%, rgba(139, 92, 246, 0.1) 0px, transparent 50%),
                radial-gradient(at 0% 50%, rgba(99, 102, 241, 0.05) 0px, transparent 50%);
        }
        
        .login-box {
            background: var(--bg-secondary);
            padding: clamp(1.5rem, 5vw, 2.5rem);
            border-radius: var(--radius-xl);
            width: 100%;
            max-width: 400px;
            border: 1px solid var(--border);
            box-shadow: 0 20px 60px var(--shadow);
            backdrop-filter: blur(10px);
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .login-logo {
            width: 70px;
            height: 70px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-radius: var(--radius-lg);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            color: white;
            font-weight: 700;
            font-size: 1.5rem;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
        }
        
        .login-logo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: var(--radius-lg);
        }
        
        .login-title {
            font-size: clamp(1.5rem, 4vw, 2rem);
            font-weight: 800;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .login-subtitle {
            color: var(--text-secondary);
            font-size: clamp(0.875rem, 2vw, 1rem);
            line-height: 1.5;
        }
        
        .login-form .form-group {
            margin-bottom: 1.5rem;
        }
        
        .login-form label {
            display: block;
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .login-form input {
            width: 100%;
            padding: 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 1rem;
            outline: none;
            transition: all 0.2s;
        }
        
        .login-form input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
            background: var(--bg-secondary);
        }
        
        .login-btn {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border: none;
            border-radius: var(--radius-md);
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 32px rgba(99, 102, 241, 0.4);
        }
        
        .login-btn:active {
            transform: translateY(0);
        }
        
        .login-footer {
            margin-top: 2rem;
            text-align: center;
            font-size: 0.875rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        
        .login-footer strong {
            color: var(--primary);
            font-weight: 600;
        }
        
        .credit-info {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--primary-light);
            padding: 0.5rem 1rem;
            border-radius: var(--radius-md);
            margin-top: 1rem;
            font-size: 0.875rem;
        }
        
        #loginStatus {
            margin-top: 1rem;
            text-align: center;
            font-size: 0.875rem;
            padding: 0.75rem;
            border-radius: var(--radius-md);
            display: none;
        }
        
        #loginStatus.success {
            display: block;
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        
        #loginStatus.error {
            display: block;
            background: rgba(239, 68, 68, 0.1);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
        
        /* Main App Layout */
        .app-layout {
            display: flex;
            height: 100vh;
            position: relative;
        }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: fixed;
            left: 0;
            top: 0;
            height: 100vh;
            z-index: 100;
            overflow: hidden;
        }
        
        .sidebar.hidden {
            transform: translateX(-100%);
        }
        
        .sidebar-header {
            padding: 1.25rem;
            border-bottom: 1px solid var(--border);
            background: var(--bg-secondary);
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            position: relative;
        }
        
        .user-avatar {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 1.125rem;
            flex-shrink: 0;
        }
        
        .user-details {
            flex: 1;
            min-width: 0;
            padding-right: 70px; /* Space for logout button */
        }
        
        .user-name {
            font-size: 0.938rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .logout-btn {
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            padding: 0.4rem 0.75rem;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: var(--radius-sm);
            color: var(--danger);
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
            font-weight: 500;
            z-index: 10;
        }
        
        .logout-btn:hover {
            background: rgba(239, 68, 68, 0.2);
            border-color: var(--danger);
            transform: translateY(-1px);
        }
        
        .credit-display {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 0.75rem;
            background: var(--primary-light);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: var(--radius-md);
            font-size: 0.75rem;
            color: var(--primary);
            font-weight: 500;
        }
        
        .credit-count {
            background: var(--primary);
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: 10px;
            font-weight: 700;
            font-size: 0.7rem;
        }
        
        .new-chat-btn {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            font-size: 0.938rem;
            margin-bottom: 1rem;
        }
        
        .new-chat-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
        }
        
        .new-chat-btn:active {
            transform: translateY(0);
        }
        
        .sidebar-bottom {
            padding: 1rem;
            border-top: 1px solid var(--border);
            margin-top: auto;
            background: var(--bg-secondary);
        }
        
        .conversations-list {
            flex: 1;
            overflow-y: auto;
            padding: 0 1rem 1rem;
        }
        
        .conversations-list::-webkit-scrollbar {
            width: 6px;
        }
        
        .conversations-list::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .conversations-list::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 3px;
        }
        
        .conversation-item {
            padding: 0.875rem;
            margin-bottom: 0.5rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            position: relative;
        }
        
        .conversation-item:hover {
            background: #475569;
            border-color: var(--primary);
            transform: translateX(2px);
        }
        
        .conversation-item.active {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border-color: var(--primary);
        }
        
        .conversation-title {
            font-size: 0.813rem;
            font-weight: 500;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            padding-right: 1.75rem;
        }
        
        .conversation-date {
            font-size: 0.688rem;
            opacity: 0.8;
        }
        
        .conversation-delete {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            width: 20px;
            height: 20px;
            background: rgba(239, 68, 68, 0.9);
            border: none;
            border-radius: var(--radius-sm);
            color: white;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 0.688rem;
            transition: all 0.2s;
        }
        
        .conversation-item:hover .conversation-delete {
            display: flex;
        }
        
        .conversation-delete:hover {
            background: var(--danger);
            transform: scale(1.1);
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100vh;
            margin-left: var(--sidebar-width);
            transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        
        .main-content.full-width {
            margin-left: 0;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-width: 100%;
            position: relative;
        }
        
        /* Header */
        .header {
            background: var(--bg-secondary);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 50;
            backdrop-filter: blur(10px);
        }
        
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex: 1;
            min-width: 0;
        }
        
        .sidebar-toggle {
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        
        .sidebar-toggle:hover {
            background: #475569;
            border-color: var(--primary);
        }
        
        .logo-icon {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.125rem;
            font-weight: 700;
            color: white;
            overflow: hidden;
            flex-shrink: 0;
        }
        
        .logo-icon img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: var(--radius-md);
        }
        
        .logo-text {
            min-width: 0;
        }
        
        .logo-text h1 {
            font-size: 1.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.125rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .logo-text p {
            font-size: 0.813rem;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .settings {
            display: flex;
            gap: 0.75rem;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .credit-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.875rem;
            background: var(--primary-light);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: var(--radius-md);
            font-size: 0.813rem;
            color: var(--primary);
            font-weight: 500;
        }
        
        .credit-count-header {
            background: var(--primary);
            color: white;
            padding: 0.125rem 0.625rem;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.75rem;
        }
        
        select, .settings button {
            padding: 0.625rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
        }
        
        select:hover, .settings button:hover {
            background: #475569;
            border-color: var(--primary);
        }
        
        select:focus, .settings button:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }
        
        .admin-btn {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            border: none;
            color: white;
        }
        
        .admin-btn:hover {
            background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
        }
        
        .clear-btn {
            background: var(--bg-tertiary);
            border-color: var(--border);
        }
        
        .clear-btn:hover {
            background: #475569;
            border-color: var(--warning);
            color: var(--warning);
        }
        
        /* Status Bar */
        .status {
            padding: 0.75rem 1.5rem;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            text-align: center;
            font-size: 0.875rem;
            transition: all 0.3s;
            border-bottom: 1px solid var(--border);
        }
        
        .status.error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--danger);
        }
        
        .status.warning {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
        }
        
        .status.success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
        }
        
        /* Chat Container */
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            background: var(--bg-main);
            scroll-behavior: smooth;
        }
        
        .chat-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .chat-container::-webkit-scrollbar-track {
            background: var(--bg-main);
        }
        
        .chat-container::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }
        
        .chat-container::-webkit-scrollbar-thumb:hover {
            background: #475569;
        }
        
        .message {
            margin-bottom: 1.5rem;
            display: flex;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-wrapper {
            max-width: 85%;
            display: flex;
            gap: 1rem;
            align-items: flex-start;
        }
        
        .message.user .message-wrapper {
            flex-direction: row-reverse;
        }
        
        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            font-weight: 600;
            flex-shrink: 0;
            overflow: hidden;
        }
        
        .avatar img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
        }
        
        .avatar.user {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
        }
        
        .avatar.bot {
            background: var(--bg-tertiary);
            color: var(--text-main);
        }
        
        .message-content {
            padding: 1rem 1.25rem;
            border-radius: var(--radius-lg);
            line-height: 1.6;
            word-wrap: break-word;
            position: relative;
            font-size: 0.938rem;
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border-bottom-right-radius: var(--radius-sm);
        }
        
        .message.bot .message-content {
            background: var(--bg-tertiary);
            color: var(--text-main);
            border-bottom-left-radius: var(--radius-sm);
        }
        
        .typing-indicator {
            display: inline-flex;
            gap: 6px;
            padding: 0.5rem 0;
        }
        
        .typing-dot {
            width: 8px;
            height: 8px;
            background: var(--text-secondary);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }
        
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.7; }
            30% { transform: translateY(-10px); opacity: 1; }
        }
        
        /* Input Area */
        .input-area {
            padding: 1.25rem 1.5rem;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            position: sticky;
            bottom: 0;
            backdrop-filter: blur(10px);
        }
        
        .input-wrapper {
            display: flex;
            gap: 1rem;
            align-items: flex-end;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        #userInput {
            flex: 1;
            padding: 1rem 1.25rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            color: var(--text-main);
            font-size: 0.938rem;
            outline: none;
            resize: none;
            max-height: 150px;
            font-family: inherit;
            line-height: 1.5;
            transition: all 0.2s;
        }
        
        #userInput:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
            background: var(--bg-secondary);
        }
        
        #userInput::placeholder {
            color: var(--text-muted);
        }
        
        #sendBtn {
            padding: 1rem 1.75rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border: none;
            border-radius: var(--radius-lg);
            cursor: pointer;
            font-size: 0.938rem;
            font-weight: 600;
            transition: all 0.3s;
            white-space: nowrap;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            min-width: 100px;
        }
        
        #sendBtn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4);
        }
        
        #sendBtn:active:not(:disabled) {
            transform: translateY(0);
        }
        
        #sendBtn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(5px);
        }
        
        .modal.show {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .modal-content {
            background: var(--bg-secondary);
            padding: clamp(1.5rem, 4vw, 2.5rem);
            border-radius: var(--radius-xl);
            width: 100%;
            max-width: 500px;
            border: 1px solid var(--border);
            max-height: 85vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px var(--shadow);
        }
        
        .modal-header {
            font-size: clamp(1.5rem, 3vw, 1.75rem);
            font-weight: 700;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .form-group input {
            width: 100%;
            padding: 0.875rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-size: 0.938rem;
            outline: none;
            transition: all 0.2s;
        }
        
        .form-group input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
            background: var(--bg-secondary);
        }
        
        .avatar-preview {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0.75rem 0;
            overflow: hidden;
            border: 2px solid var(--border);
        }
        
        .avatar-preview img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
        }
        
        .avatar-type-toggle {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .avatar-type-btn {
            flex: 1;
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .avatar-type-btn.active {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-color: var(--primary);
            color: white;
        }
        
        .tabs {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.75rem;
        }
        
        .tab-btn {
            padding: 0.75rem 1.5rem;
            background: transparent;
            border: 1px solid transparent;
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .tab-btn.active {
            background: var(--primary-light);
            border-color: var(--primary);
            color: var(--primary);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .modal-buttons {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
        }
        
        .modal-buttons button {
            flex: 1;
            padding: 1rem;
            border: none;
            border-radius: var(--radius-md);
            font-size: 0.938rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-save {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
        }
        
        .btn-cancel {
            background: var(--bg-tertiary);
            color: var(--text-main);
            border: 1px solid var(--border);
        }
        
        .btn-save:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
        }
        
        .btn-cancel:hover {
            background: #475569;
            border-color: var(--border);
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .main-content {
                margin-left: 0;
            }
            
            .sidebar {
                transform: translateX(-100%);
            }
            
            .sidebar.visible {
                transform: translateX(0);
            }
            
            .message-wrapper {
                max-width: 90%;
            }
        }
        
        @media (max-width: 768px) {
            :root {
                --sidebar-width: 260px;
            }
            
            .header {
                padding: 1rem;
            }
            
            .logo-text h1 {
                font-size: 1.125rem;
            }
            
            .logo-text p {
                font-size: 0.75rem;
            }
            
            .settings {
                gap: 0.5rem;
            }
            
            select, .settings button {
                padding: 0.5rem 0.75rem;
                font-size: 0.813rem;
            }
            
            .chat-container {
                padding: 1rem;
            }
            
            .message-wrapper {
                max-width: 95%;
                gap: 0.75rem;
            }
            
            .avatar {
                width: 36px;
                height: 36px;
                font-size: 0.875rem;
            }
            
            .message-content {
                padding: 0.875rem 1rem;
                font-size: 0.875rem;
            }
            
            .input-area {
                padding: 1rem;
            }
            
            .input-wrapper {
                gap: 0.75rem;
            }
            
            #userInput {
                padding: 0.875rem 1rem;
            }
            
            #sendBtn {
                padding: 0.875rem 1.25rem;
                min-width: 80px;
            }
            
            .modal-content {
                padding: 1.5rem;
            }
            
            .modal-buttons {
                flex-direction: column;
            }
            
            .modal-buttons button {
                width: 100%;
            }
        }
        
        @media (max-width: 480px) {
            .sidebar-header {
                padding: 1rem;
            }
            
            .user-info {
                flex-direction: column;
                text-align: center;
                gap: 0.75rem;
            }
            
            .user-details {
                width: 100%;
                padding-right: 0;
            }
            
            .logout-btn {
                position: static;
                width: 100%;
                margin-top: 0.5rem;
            }
            
            .header-top {
                flex-direction: column;
                align-items: stretch;
                gap: 0.75rem;
            }
            
            .logo {
                justify-content: center;
                text-align: center;
            }
            
            .settings {
                justify-content: center;
            }
            
            .credit-badge {
                order: -1;
                width: 100%;
                justify-content: center;
            }
            
            .message-wrapper {
                max-width: 100%;
            }
            
            .avatar {
                width: 32px;
                height: 32px;
                font-size: 0.813rem;
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
            </div>
            
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeAdmin()">Cancel</button>
                <button class="btn-save" id="adminAction" onclick="verifyPassword()">Unlock</button>
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
        
        // DOM Elements
        const input = document.getElementById('userInput');
        const chat = document.getElementById('chat');
        const sendBtn = document.getElementById('sendBtn');
        const status = document.getElementById('status');
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('mainContent');
        const sidebarIcon = document.getElementById('sidebarIcon');
        
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
                        sendMessage();
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
        });
        
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
            
            const avatarHtml = botAvatarType === 'image' && botAvatarUrl 
                ? `<img src="${botAvatarUrl}" alt="Bot">`
                : botAvatar;
            
            let welcomeMessage = `
                <div class="message bot">
                    <div class="message-wrapper">
                        <div class="avatar bot">${avatarHtml}</div>
                        <div class="message-content">
                            <strong>Hello {{ username }}! I'm ${botName}</strong><br><br>
                            I'm an intelligent chatbot that can help you with:<br>
                            • General conversation and questions<br>
                            • Writing and debugging code<br>
                            • Explaining complex topics<br>
                            • Building applications and tools<br>
                            • Problem solving and analysis<br><br>
                            ${!isAdmin ? `<em>You have {{ user_credits }} credits remaining.</em><br><br>` : ''}
                            <em>How can I assist you today?</em>
                        </div>
                    </div>
                </div>
            `;
            
            chat.innerHTML = welcomeMessage;
            
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
            
            // Check credits for non-admin users
            if (!isAdmin) {
                const hasCredits = await checkUserCredits();
                if (!hasCredits) {
                    return;
                }
            }
            
            const msg = input.value.trim();
            
            if (!msg) {
                showStatus('Please type a message', 'warning');
                return;
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
                        mode: document.getElementById('mode').value,
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
                
                // Update credits display
                if (!isAdmin) {
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
        });
        
        // Auto-focus on message input when clicking anywhere
        document.addEventListener('click', function(e) {
            if (!e.target.closest('#adminModal') && 
                !e.target.closest('.sidebar') && 
                !e.target.closest('.sidebar-toggle') &&
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

Always provide clear, well-structured responses with proper code formatting when relevant.

Created by: JHONWILSON"""

    def process_streaming(self, msg, mode, hist):
        try:
            prompt = self.code_prompt.format(bot_name=BOT_SETTINGS['name'])
            
            if mode == 'code':
                msg = f"{prompt}\n\nUser: {msg}"
            elif mode == 'hybrid':
                msg = f"{prompt}\n\n{msg}"
            
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

Chat Mode: General conversation and assistance
Code Mode: Programming and development focus
Hybrid Mode: Balanced approach for both

Examples:
• "Build a Flask REST API"
• "Explain how databases work"
• "Write a Python web scraper"
• "Create a React application"
• "Help me debug this code"

Features:
• Real-time streaming responses
• Support for any programming language
• Complex problem solving
• Code generation and debugging
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
        "conversations_count": len(CONVERSATIONS)
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok", 
        "users": len(USERS), 
        "conversations": len(CONVERSATIONS),
        "bot_name": BOT_SETTINGS['name']
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
    
    # Print startup info
    print("=" * 50)
    print(f"🤖 {BOT_SETTINGS['name']} Server Starting...")
    print(f"📱 Admin username: admin")
    print(f"🔐 Admin password: {ADMIN_PASSWORD}")
    print(f"🎁 New user credits: {FREE_CREDITS}")
    print(f"👥 Registered users: {len(USERS)}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
