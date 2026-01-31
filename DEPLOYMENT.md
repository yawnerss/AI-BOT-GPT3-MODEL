# Vercel Deployment Guide

## Quick Fix for "No flask entrypoint found" Error

The error occurs because Vercel needs the Flask app in a specific location. Here's how to fix it:

### Option 1: Use api/index.py (Recommended for Vercel)

1. **Create the directory structure:**
   ```bash
   mkdir -p api
   ```

2. **Move or copy your main Flask file:**
   ```bash
   # If your file is named app.py, main.py, or similar:
   cp your_flask_file.py api/index.py
   ```

3. **Ensure the file exports `app`:**
   At the end of `api/index.py`, make sure you have:
   ```python
   # At the very end of the file
   app = Flask(__name__)
   # ... all your routes ...
   
   # NO if __name__ == '__main__': block needed for Vercel!
   # Just make sure 'app' variable is defined
   ```

4. **Create `vercel.json`:**
   ```json
   {
     "version": 2,
     "builds": [
       {
         "src": "api/index.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "api/index.py"
       }
     ]
   }
   ```

5. **Create `requirements.txt`:**
   ```txt
   flask>=2.3.0
   requests>=2.31.0
   gunicorn>=21.0.0
   python-dotenv>=1.0.0
   ```

6. **Deploy:**
   ```bash
   vercel --prod
   ```

### Option 2: Add app script to pyproject.toml

Update your `pyproject.toml`:

```toml
[project.scripts]
app = "api.index:app"
```

### Option 3: Use a standard filename

Rename your Flask file to one of these:
- `app.py`
- `index.py`  
- `main.py`
- `wsgi.py`

And place it in the root directory or one of these locations:
- Root: `/app.py`
- `src/app.py`
- `app/app.py`
- `api/app.py`

## File Structure for Vercel

```
your-project/
├── api/
│   ├── __init__.py          # Empty file
│   └── index.py             # Your Flask app (main file)
├── vercel.json              # Vercel configuration
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Optional: Project metadata
├── .vercelignore           # Files to ignore
└── README.md
```

## Important Notes for Serverless

### 1. File Paths
Use `/tmp/` for temporary files in serverless:
```python
CLIPFLY_TOKEN_FILE = "/tmp/token.txt"
CLIPFLY_IMAGES_DIR = "/tmp/generated_images"
```

### 2. Remove Main Block
Don't include this in `api/index.py`:
```python
# ❌ Remove this for Vercel:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 3. Session Storage
For production, use a proper session backend:
```python
# Option: Use Flask-Session with Redis
from flask_session import Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL'))
```

### 4. Database
Replace in-memory storage with a database:
```python
# Instead of:
USERS = {}
CONVERSATIONS = {}

# Use:
# - Vercel Postgres
# - MongoDB Atlas
# - Supabase
# - PlanetScale
```

## Environment Variables

Set these in Vercel Dashboard:

```bash
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=your-admin-password
TELEGRAM_BOT_TOKEN=your-telegram-token
TELEGRAM_CHAT_ID=your-chat-id
```

## Testing Locally

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally
vercel dev

# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

## Common Issues

### 1. "No flask entrypoint found"
✅ **Solution:** Use `api/index.py` and ensure `app` variable is defined

### 2. "Module not found"
✅ **Solution:** Check `requirements.txt` has all dependencies

### 3. "Function timeout"
✅ **Solution:** Optimize long-running operations or upgrade Vercel plan

### 4. "Session data lost"
✅ **Solution:** Use Redis or database-backed sessions

### 5. "File system read-only"
✅ **Solution:** Use `/tmp/` directory for temporary files

## Minimal Working Example

**api/index.py:**
```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello from Vercel!'

@app.route('/health')
def health():
    return {'status': 'ok'}

# No if __name__ == '__main__' needed!
```

**vercel.json:**
```json
{
  "version": 2,
  "builds": [{"src": "api/index.py", "use": "@vercel/python"}],
  "routes": [{"src": "/(.*)", "dest": "api/index.py"}]
}
```

**requirements.txt:**
```txt
flask
```

Deploy:
```bash
vercel --prod
```

## Migration Checklist

- [ ] Create `api/` directory
- [ ] Move Flask app to `api/index.py`
- [ ] Remove `if __name__ == '__main__':` block
- [ ] Create `vercel.json`
- [ ] Update file paths to use `/tmp/`
- [ ] Add all dependencies to `requirements.txt`
- [ ] Set environment variables in Vercel
- [ ] Test locally with `vercel dev`
- [ ] Deploy with `vercel --prod`
- [ ] Set up proper database (not in-memory)
- [ ] Configure session backend

## Next Steps

After successful deployment:

1. **Add Database:** Replace in-memory storage
2. **Add Redis:** For sessions and caching
3. **Add Monitoring:** Use Vercel Analytics
4. **Add Logging:** Use proper logging service
5. **Add Tests:** Ensure reliability
6. **Add CI/CD:** Automate deployments

Need help? Check the [Vercel Flask Documentation](https://vercel.com/docs/frameworks/backend/flask)
