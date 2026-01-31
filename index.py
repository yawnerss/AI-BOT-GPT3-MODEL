from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "JhonWilson AI is running!",
        "version": "1.0.0"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "JhonWilson AI - Unrestricted"
    })

@app.route('/api/test')
def test():
    return jsonify({
        "test": "success",
        "message": "API is working!"
    })

# For Vercel - this is critical!
# The 'app' variable must be at module level
