from flask import Flask, render_template_string, request, jsonify, Response, session
import requests
import json
import os
from datetime import datetime
import time
import secrets
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Default bot settings
BOT_SETTINGS = {
    'name': 'JhonWilson AI',
    'avatar': 'AI',
    'avatar_type': 'text',  # 'text' or 'image'
    'avatar_url': '',
    'tagline': 'Intelligent Assistant'
}

# Admin credentials
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7480489708:AAHSYSODivqJcXkS9aVDPHyZjyxrEExD8Qw')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7383039587')  # Your chat ID

# Visitor tracking
VISITORS = []
MAX_VISITORS = 1000  # Keep last 1000 visitors

def send_telegram_notification(visitor_info):
    """Send visitor notification to Telegram"""
    if not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram Chat ID not set. Visit /get-chat-id to get your chat ID")
        return
    
    try:
        # Format message
        fb_user = visitor_info.get('fb_user') or 'Direct Visitor'
        source = visitor_info.get('source', 'Unknown')
        ip = visitor_info.get('ip', 'Unknown')
        timestamp = datetime.fromisoformat(visitor_info.get('timestamp', datetime.now().isoformat()))
        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Escape special characters for Markdown
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
            print(f"❌ Telegram error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Telegram notification failed: {e}")

# HTML Template with auto-focus and admin panel
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ bot_name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --bg-main: #0f172a;
            --bg-chat: #1e293b;
            --bg-user: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            --bg-bot: #334155;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --border: #334155;
            --shadow: rgba(0, 0, 0, 0.3);
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-main);
            color: var(--text-main);
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-width: 100%;
            margin: 0 auto;
        }
        
        .header {
            background: var(--bg-chat);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(10px);
        }
        
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .logo-icon {
            width: 36px;
            height: 36px;
            background: var(--bg-user);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            color: white;
            overflow: hidden;
        }

        .logo-icon img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .logo-text h1 {
            font-size: 1.25rem;
            font-weight: 700;
            background: var(--bg-user);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .logo-text p {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.125rem;
        }
        
        .settings {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .settings select, .settings button {
            padding: 0.5rem 0.75rem;
            background: var(--bg-bot);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 0.813rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .settings select:hover, .settings button:hover {
            background: #475569;
            border-color: var(--primary);
        }

        .admin-btn {
            background: #f59e0b;
            border-color: #f59e0b;
        }

        .admin-btn:hover {
            background: #d97706;
            border-color: #d97706;
        }

        .visitor-badge {
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid var(--primary);
            border-radius: 8px;
            padding: 0.5rem 0.75rem;
            font-size: 0.75rem;
            color: var(--primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .visitor-count {
            background: var(--primary);
            color: white;
            border-radius: 12px;
            padding: 0.125rem 0.5rem;
            font-weight: 600;
        }
        
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
            max-width: 75%;
            display: flex;
            gap: 0.75rem;
            align-items: flex-start;
        }
        
        .message.user .message-wrapper {
            flex-direction: row-reverse;
        }
        
        .avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            font-weight: 600;
            flex-shrink: 0;
            overflow: hidden;
        }

        .avatar img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .avatar.user {
            background: var(--bg-user);
        }
        
        .avatar.bot {
            background: var(--bg-bot);
        }
        
        .message-content {
            padding: 0.875rem 1.125rem;
            border-radius: 16px;
            line-height: 1.6;
            word-wrap: break-word;
            position: relative;
        }
        
        .message.user .message-content {
            background: var(--bg-user);
            border-bottom-right-radius: 4px;
        }
        
        .message.bot .message-content {
            background: var(--bg-bot);
            border-bottom-left-radius: 4px;
        }
        
        .typing-indicator {
            display: inline-flex;
            gap: 4px;
            padding: 0.5rem 0;
        }
        
        .typing-dot {
            width: 8px;
            height: 8px;
            background: var(--text-muted);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }
        
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.7; }
            30% { transform: translateY(-10px); opacity: 1; }
        }
        
        .timestamp {
            font-size: 0.688rem;
            color: var(--text-muted);
            margin-top: 0.375rem;
            opacity: 0.7;
        }
        
        pre {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 0.75rem 0;
            font-size: 0.813rem;
            border: 1px solid #333;
        }
        
        pre code {
            background: transparent;
            color: #d4d4d4;
            padding: 0;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.813rem;
            line-height: 1.6;
        }
        
        .code-header {
            background: #0d0d0d;
            padding: 0.375rem 0.75rem;
            font-size: 0.688rem;
            color: #888;
            border-bottom: 1px solid #333;
            margin: -1rem -1rem 0.75rem -1rem;
            border-radius: 8px 8px 0 0;
        }
        
        code {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background: #2d2d2d;
            color: #e6db74;
            padding: 0.188rem 0.375rem;
            border-radius: 4px;
            font-size: 0.813rem;
        }
        
        .input-area {
            padding: 1rem 1.5rem;
            background: var(--bg-chat);
            border-top: 1px solid var(--border);
        }
        
        .input-wrapper {
            display: flex;
            gap: 0.75rem;
            align-items: flex-end;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        #userInput {
            flex: 1;
            padding: 0.875rem 1.125rem;
            background: var(--bg-bot);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--text-main);
            font-size: 0.938rem;
            outline: none;
            resize: none;
            max-height: 120px;
            font-family: inherit;
            transition: all 0.2s;
        }
        
        #userInput:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        #userInput::placeholder {
            color: var(--text-muted);
        }
        
        #sendBtn {
            padding: 0.875rem 1.5rem;
            background: var(--bg-user);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-size: 0.938rem;
            font-weight: 600;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        #sendBtn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
        }
        
        #sendBtn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .status {
            padding: 0.5rem;
            background: #10b981;
            color: white;
            text-align: center;
            font-size: 0.813rem;
            transition: all 0.3s;
        }
        
        .status.error {
            background: #ef4444;
        }
        
        .status.warning {
            background: #f59e0b;
        }

        /* Admin Modal */
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
        }

        .modal-content {
            background: var(--bg-chat);
            padding: 2rem;
            border-radius: 16px;
            width: 90%;
            max-width: 500px;
            border: 1px solid var(--border);
        }

        .modal-header {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            background: var(--bg-user);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-muted);
            font-size: 0.875rem;
        }

        .form-group input {
            width: 100%;
            padding: 0.75rem;
            background: var(--bg-bot);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 0.938rem;
            outline: none;
        }

        .form-group input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }

        .avatar-preview {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: var(--bg-bot);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0.5rem 0;
            overflow: hidden;
            border: 2px solid var(--border);
        }

        .avatar-preview img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .avatar-type-toggle {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }

        .avatar-type-btn {
            flex: 1;
            padding: 0.5rem;
            background: var(--bg-bot);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-main);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.813rem;
        }

        .avatar-type-btn.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        .modal-buttons {
            display: flex;
            gap: 0.75rem;
            margin-top: 1.5rem;
        }

        .modal-buttons button {
            flex: 1;
            padding: 0.75rem;
            border: none;
            border-radius: 8px;
            font-size: 0.938rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-save {
            background: var(--bg-user);
            color: white;
        }

        .btn-cancel {
            background: var(--bg-bot);
            color: var(--text-main);
        }

        .btn-save:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .btn-cancel:hover {
            background: #475569;
        }
        
        /* Tablet */
        @media (max-width: 1024px) {
            .chat-container {
                padding: 1rem;
            }
            
            .message-wrapper {
                max-width: 85%;
            }
        }
        
        /* Mobile */
        @media (max-width: 640px) {
            .header {
                padding: 0.75rem 1rem;
            }
            
            .logo-icon {
                width: 32px;
                height: 32px;
                font-size: 12px;
            }
            
            .logo-text h1 {
                font-size: 1.125rem;
            }
            
            .logo-text p {
                font-size: 0.688rem;
            }
            
            .settings {
                width: 100%;
            }
            
            .settings select, .settings button {
                flex: 1;
                font-size: 0.75rem;
                padding: 0.5rem;
            }
            
            .chat-container {
                padding: 1rem 0.75rem;
            }
            
            .message-wrapper {
                max-width: 90%;
            }
            
            .avatar {
                width: 28px;
                height: 28px;
                font-size: 0.875rem;
            }
            
            .message-content {
                padding: 0.75rem 1rem;
                font-size: 0.938rem;
            }
            
            .input-area {
                padding: 0.75rem 1rem;
            }
            
            #userInput, #sendBtn {
                font-size: 1rem;
            }
            
            #sendBtn {
                padding: 0.875rem 1.25rem;
            }

            .modal-content {
                width: 95%;
                padding: 1.5rem;
            }
        }
        
        /* Small mobile */
        @media (max-width: 375px) {
            .message-wrapper {
                max-width: 95%;
            }
            
            .settings select, .settings button {
                font-size: 0.688rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div class="logo">
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
            </div>
            <div class="settings">
                <div class="visitor-badge">
                    <span>Visitors</span>
                    <span class="visitor-count" id="visitorCount">0</span>
                </div>
                <select id="mode">
                    <option value="chat">Chat Mode</option>
                    <option value="code">Coding Mode</option>
                    <option value="hybrid">Hybrid Mode</option>
                </select>
                <button onclick="resetChat()">Reset</button>
                <button class="admin-btn" onclick="openAdmin()">Admin</button>
            </div>
        </div>

        <div class="status" id="status">Ready</div>

        <div class="chat-container" id="chat">
            <div class="message bot">
                <div class="message-wrapper">
                    <div class="avatar bot">
                        {% if bot_avatar_type == 'image' and bot_avatar_url %}
                            <img src="{{ bot_avatar_url }}" alt="Bot">
                        {% else %}
                            {{ bot_avatar }}
                        {% endif %}
                    </div>
                    <div class="message-content">
                        <strong>Hello! I'm {{ bot_name }}</strong><br><br>
                        I'm an intelligent chatbot that can help you with:<br>
                        • General conversation and questions<br>
                        • Writing and debugging code<br>
                        • Explaining complex topics<br>
                        • Building applications and tools<br>
                        • Problem solving and analysis<br><br>
                        <em>How can I assist you today?</em>
                    </div>
                </div>
            </div>
        </div>

        <div class="input-area">
            <div class="input-wrapper">
                <textarea id="userInput" rows="1" placeholder="Type your message..."></textarea>
                <button id="sendBtn" onclick="send()">Send</button>
            </div>
        </div>
    </div>

    <!-- Admin Modal -->
    <div id="adminModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">Admin Panel</div>
            <div class="form-group">
                <label>Admin Password</label>
                <input type="password" id="adminPassword" placeholder="Enter password">
            </div>
            <div id="adminSettings" style="display: none;">
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
                <div id="visitorList" style="max-height: 300px; overflow-y: auto; margin-top: 1rem;">
                    <h3 style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 0.5rem;">Recent Visitors</h3>
                    <div id="visitorData" style="font-size: 0.813rem; color: var(--text-muted);"></div>
                </div>
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeAdmin()">Cancel</button>
                <button class="btn-save" id="adminAction" onclick="verifyPassword()">Unlock</button>
            </div>
        </div>
    </div>

    <script>
        let history = [];
        let processing = false;
        let currentBotMessage = null;
        let botAvatar = '{{ bot_avatar }}';
        let botAvatarType = '{{ bot_avatar_type }}';
        let botAvatarUrl = '{{ bot_avatar_url }}';
        let botName = '{{ bot_name }}';
        let fbUser = '{{ fb_user }}';
        let fbSource = '{{ fb_source }}';

        // Show Facebook user info if detected
        if (fbUser && fbUser !== 'None') {
            setTimeout(() => {
                showStatus('Welcome ' + fbUser + ' from Facebook!', 'success');
            }, 500);
        }

        // Update visitor count on load
        fetch('/api/visitor-count')
            .then(r => r.json())
            .then(data => {
                document.getElementById('visitorCount').textContent = data.count;
            })
            .catch(e => console.log('Could not load visitor count'));

        // Preview avatar URL
        const avatarUrlInput = document.getElementById('botAvatarUrl');
        if (avatarUrlInput) {
            avatarUrlInput.addEventListener('input', function() {
                const preview = document.getElementById('avatarPreview');
                if (this.value) {
                    preview.innerHTML = `<img src="${this.value}" alt="Preview" onerror="this.parentElement.innerHTML='Invalid Image'">`;
                } else {
                    preview.innerHTML = 'Preview';
                }
            });
        }

        const input = document.getElementById('userInput');
        const chat = document.getElementById('chat');
        const sendBtn = document.getElementById('sendBtn');
        const status = document.getElementById('status');

        // AUTO-FOCUS: Focus input on any keypress
        document.addEventListener('keydown', function(e) {
            // Skip if modal is open or if typing in another input
            if (document.getElementById('adminModal').classList.contains('show')) return;
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            // Focus input and let the key be typed
            if (e.key.length === 1 || e.key === 'Backspace') {
                input.focus();
            }
        });

        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
            }
        });

        function showStatus(msg, type = 'success') {
            status.textContent = msg;
            status.className = 'status ' + (type !== 'success' ? type : '');
            if (type === 'success') {
                setTimeout(() => {
                    status.textContent = 'Ready';
                    status.className = 'status';
                }, 3000);
            }
        }

        function createMessage(type, initial = '') {
            const msg = document.createElement('div');
            msg.className = 'message ' + type;
            
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar ' + type;
            
            if (type === 'user') {
                avatar.textContent = 'U';
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

        function updateBotMessage(content, text) {
            content.innerHTML = formatText(text);
            chat.scrollTop = chat.scrollHeight;
        }

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
            
            html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, function(match, lang, code) {
                const langLabel = lang ? `<div class="code-header">${lang}</div>` : '';
                return `<pre>${langLabel}<code>${code.trim()}</code></pre>`;
            });
            
            html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
            html = html.replace(/\n/g, '<br>');
            
            return html;
        }

        async function send() {
            if (processing) return;
            
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
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: msg,
                        mode: document.getElementById('mode').value,
                        history: history
                    })
                });

                if (!response.ok) throw new Error('Server error');

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
                            if (data === '[DONE]') break;
                            
                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.token) {
                                    fullText += parsed.token;
                                    updateBotMessage(currentBotMessage, fullText);
                                } else if (parsed.error) {
                                    throw new Error(parsed.error);
                                }
                            } catch (e) {
                                if (e.message !== 'Unexpected end of JSON input') {
                                    console.error('Parse error:', e);
                                }
                            }
                        }
                    }
                }

                history.push({role: 'user', content: msg});
                history.push({role: 'assistant', content: fullText});
                
                const time = document.createElement('div');
                time.className = 'timestamp';
                time.textContent = new Date().toLocaleTimeString();
                currentBotMessage.appendChild(time);
                
                showStatus('Message sent');

            } catch (err) {
                console.error('Error:', err);
                updateBotMessage(currentBotMessage, 'Connection failed: ' + err.message);
                showStatus('Connection error', 'error');
            } finally {
                sendBtn.disabled = false;
                processing = false;
                input.focus();
            }
        }

        function resetChat() {
            if (confirm('Reset conversation?')) {
                history = [];
                const avatarHtml = botAvatarType === 'image' && botAvatarUrl 
                    ? `<img src="${botAvatarUrl}" alt="Bot">`
                    : botAvatar;
                
                chat.innerHTML = `
                    <div class="message bot">
                        <div class="message-wrapper">
                            <div class="avatar bot">${avatarHtml}</div>
                            <div class="message-content">
                                <strong>Chat Reset</strong><br><br>
                                I'm ${botName}, ready to help you with anything.
                            </div>
                        </div>
                    </div>
                `;
                showStatus('Chat reset');
            }
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
        function openAdmin() {
            document.getElementById('adminModal').classList.add('show');
            document.getElementById('adminPassword').focus();
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
                    showStatus('Admin access granted');
                    
                    // Load visitor data
                    loadVisitors();
                } else {
                    showStatus('Invalid password', 'error');
                }
            } catch (err) {
                showStatus('Connection error', 'error');
            }
        }

        async function saveSettings() {
            const newName = document.getElementById('botName').value.trim();
            const newAvatar = document.getElementById('botAvatar').value.trim();
            const newAvatarUrl = document.getElementById('botAvatarUrl').value.trim();
            const newTagline = document.getElementById('botTagline').value.trim();
            const avatarType = document.querySelector('.avatar-type-btn.active').textContent.includes('Image') ? 'image' : 'text';
            
            if (!newName) {
                showStatus('Bot name required', 'warning');
                return;
            }

            if (avatarType === 'text' && !newAvatar) {
                showStatus('Avatar text required', 'warning');
                return;
            }

            if (avatarType === 'image' && !newAvatarUrl) {
                showStatus('Avatar image URL required', 'warning');
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
                    showStatus('Settings saved! Reloading...');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showStatus('Save failed', 'error');
                }
            } catch (err) {
                showStatus('Connection error', 'error');
            }
        }

        async function loadVisitors() {
            try {
                const response = await fetch('/admin/visitors');
                const data = await response.json();
                
                if (data.success) {
                    const visitorData = document.getElementById('visitorData');
                    if (data.visitors.length === 0) {
                        visitorData.innerHTML = '<p style="opacity: 0.6;">No visitors yet</p>';
                        return;
                    }
                    
                    let html = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';
                    data.visitors.forEach(v => {
                        const source = v.source || 'Direct';
                        const fbUser = v.fb_user || 'Unknown';
                        const time = new Date(v.timestamp).toLocaleString();
                        
                        html += `
                            <div style="background: var(--bg-bot); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border);">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                                    <strong style="color: var(--primary);">${fbUser}</strong>
                                    <span style="opacity: 0.7; font-size: 0.75rem;">${time}</span>
                                </div>
                                <div style="font-size: 0.75rem; opacity: 0.8;">
                                    Source: ${source} ${v.ip ? '• IP: ' + v.ip : ''}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    visitorData.innerHTML = html;
                }
            } catch (err) {
                console.error('Could not load visitors:', err);
            }
        }

        // Close modal on Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeAdmin();
            }
        });

        window.onload = () => input.focus();
    </script>
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
                
                # Stream the response word by word
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
        # Get visitor info
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip:
            ip = ip.split(',')[0].strip()
        
        user_agent = request.headers.get('User-Agent', '')
        referer = request.headers.get('Referer', '')
        
        # Detect Facebook
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
        
        # Try to extract Facebook user info from fbclid or URL params
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
        
        VISITORS.insert(0, visitor)
        
        # Keep only last MAX_VISITORS
        if len(VISITORS) > MAX_VISITORS:
            VISITORS.pop()
        
        # Send Telegram notification
        send_telegram_notification(visitor)
        
        return fb_user, source
        
    except Exception as e:
        print(f"Tracking error: {e}")
        return None, 'Unknown'

@app.route('/')
def home():
    fb_user, fb_source = track_visitor(request)
    
    return render_template_string(
        HTML_TEMPLATE,
        bot_name=BOT_SETTINGS['name'],
        bot_avatar=BOT_SETTINGS['avatar'],
        bot_avatar_type=BOT_SETTINGS['avatar_type'],
        bot_avatar_url=BOT_SETTINGS['avatar_url'],
        bot_tagline=BOT_SETTINGS['tagline'],
        fb_user=fb_user,
        fb_source=fb_source
    )

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        msg = data.get('message', '').strip()
        
        if not msg:
            return jsonify({"error": "Empty message"})
        
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
        return jsonify({"error": str(e)})

@app.route('/api/visitor-count', methods=['GET'])
def visitor_count():
    return jsonify({"count": len(VISITORS)})

@app.route('/get-chat-id')
def get_chat_id():
    """Helper page to get Telegram chat ID"""
    return f"""
    <html>
    <head><title>Get Telegram Chat ID</title></head>
    <body style="font-family: Arial; padding: 40px; max-width: 800px; margin: 0 auto;">
        <h1>🤖 Get Your Telegram Chat ID</h1>
        <p>Follow these steps to receive visitor notifications:</p>
        
        <h2>Step 1: Start Your Bot</h2>
        <ol>
            <li>Open Telegram and search for: <code>@JhonWilsonAI_bot</code> (or your bot name)</li>
            <li>Click "Start" or send <code>/start</code></li>
            <li>Send any message to your bot</li>
        </ol>
        
        <h2>Step 2: Get Your Chat ID</h2>
        <p>Click this link to get updates from your bot:</p>
        <a href="https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates" 
           target="_blank" 
           style="display: inline-block; padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
           Get Chat ID
        </a>
        
        <h2>Step 3: Find Your Chat ID</h2>
        <p>Look for the "chat" section and copy your "id" number. It looks like:</p>
        <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">{{"chat":{{"id":123456789}}}}</pre>
        
        <h2>Step 4: Set Your Chat ID</h2>
        <p>Add this to your environment variables or update the code:</p>
        <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">TELEGRAM_CHAT_ID=your_chat_id_here</pre>
        
        <h2>Alternative: Quick Setup</h2>
        <p>Or update directly in chat.py:</p>
        <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID')</pre>
        
        <hr>
        <p><a href="/">← Back to Chat</a></p>
    </body>
    </html>
    """

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    data = request.json
    password = data.get('password', '')
    
    if password == ADMIN_PASSWORD:
        session['admin'] = True
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

@app.route('/admin/visitors', methods=['GET'])
def admin_visitors():
    if not session.get('admin'):
        return jsonify({"success": False, "error": "Unauthorized"})
    
    # Return last 50 visitors
    recent_visitors = VISITORS[:50]
    return jsonify({"success": True, "visitors": recent_visitors})

@app.route('/admin/save', methods=['POST'])
def admin_save():
    if not session.get('admin'):
        return jsonify({"success": False, "error": "Unauthorized"})
    
    data = request.json
    
    BOT_SETTINGS['name'] = data.get('name', BOT_SETTINGS['name'])
    BOT_SETTINGS['avatar'] = data.get('avatar', BOT_SETTINGS['avatar'])
    BOT_SETTINGS['avatar_type'] = data.get('avatar_type', BOT_SETTINGS['avatar_type'])
    BOT_SETTINGS['avatar_url'] = data.get('avatar_url', BOT_SETTINGS['avatar_url'])
    BOT_SETTINGS['tagline'] = data.get('tagline', BOT_SETTINGS['tagline'])
    
    return jsonify({"success": True})

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"\n{'='*60}")
    print(f"{BOT_SETTINGS['name']} - Created by JHONWILSON")
    print(f"Server running on port {port}")
    print(f"Admin Password: {ADMIN_PASSWORD}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
