# 🔧 FIXED: How to Deploy Flask on Vercel

## The Problem
You got a 404 error because Vercel couldn't find your Flask app properly.

## The Solution

### Option 1: Simplified Approach (RECOMMENDED)

Use the new `rewrites` configuration instead of `builds`:

**1. File Structure:**
```
your-project/
├── api/
│   ├── __init__.py
│   └── index.py
├── requirements.txt
└── vercel.json
```

**2. vercel.json:**
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/api/index"
    }
  ]
}
```

**3. api/index.py:**
```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Working!"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# IMPORTANT: No if __name__ == '__main__' block!
```

**4. requirements.txt:**
```
flask
```

**5. Deploy:**
```bash
vercel --prod
```

### Option 2: Using WSGI (Alternative)

**vercel.json:**
```json
{
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

**api/index.py:**
```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello World!'

# Vercel looks for 'app' or 'application'
# This MUST be at module level
```

### Common Issues & Fixes

#### ❌ Issue 1: 404 NOT_FOUND
**Cause:** Flask app not properly exposed

**Fix:**
```python
# Make sure this is at the TOP of api/index.py, not inside any function
app = Flask(__name__)

# All routes MUST be defined at module level
@app.route('/')
def home():
    return 'Hello!'

# NO if __name__ == '__main__': block!
```

#### ❌ Issue 2: Module not found
**Cause:** Missing dependencies

**Fix:**
```bash
# Make sure requirements.txt has ALL dependencies
flask
requests
gunicorn
# ... etc
```

#### ❌ Issue 3: Import errors
**Cause:** Circular imports or missing __init__.py

**Fix:**
```bash
# Ensure api/__init__.py exists (can be empty)
touch api/__init__.py
```

## Test Locally First

```bash
# Install dependencies
pip install -r requirements.txt

# Test with Vercel dev server
vercel dev

# Should show: http://localhost:3000
# Visit http://localhost:3000 in browser
```

## Debugging on Vercel

1. **Check Function Logs:**
   - Go to Vercel Dashboard
   - Click your project
   - Go to "Deployments"
   - Click the latest deployment
   - Click "Functions" tab
   - Click "api/index" to see logs

2. **Check Runtime Logs:**
   ```bash
   vercel logs
   ```

3. **Test specific routes:**
   ```bash
   curl https://your-app.vercel.app/
   curl https://your-app.vercel.app/health
   curl https://your-app.vercel.app/api/test
   ```

## Full Working Example

Here's a complete, tested example:

**api/index.py:**
```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "message": "JhonWilson AI - Unrestricted",
        "status": "running",
        "endpoints": ["/", "/health", "/api/test"]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/test')
def api_test():
    return jsonify({
        "test": "success",
        "method": request.method,
        "path": request.path
    })

# CRITICAL: app must be at module level
# NO if __name__ == '__main__': block needed
```

**api/__init__.py:**
```python
# Empty file - just needs to exist
```

**vercel.json:**
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/api/index"
    }
  ]
}
```

**requirements.txt:**
```
flask==3.0.0
```

## Deploy & Test

```bash
# Deploy
vercel --prod

# Wait for deployment to complete
# You'll get a URL like: https://your-project.vercel.app

# Test
curl https://your-project.vercel.app/
curl https://your-project.vercel.app/health
```

## For Your Full App

Once the minimal version works, you can:

1. **Copy all your original code** into `api/index.py`
2. **Make these changes:**
   - Change file paths to `/tmp/...`
   - Remove `if __name__ == '__main__':` block
   - Keep `app = Flask(__name__)` at module level
3. **Add all dependencies** to `requirements.txt`
4. **Redeploy:** `vercel --prod`

## Quick Checklist

- [ ] `api/index.py` exists
- [ ] `api/__init__.py` exists (can be empty)
- [ ] `app = Flask(__name__)` is at module level (not in function)
- [ ] NO `if __name__ == '__main__':` block
- [ ] All routes defined at module level
- [ ] All dependencies in `requirements.txt`
- [ ] `vercel.json` uses `rewrites` configuration
- [ ] Tested locally with `vercel dev`

## Still Getting 404?

Run these checks:

```bash
# 1. Verify file exists
ls -la api/index.py

# 2. Check Python syntax
python3 api/index.py
# Should NOT error

# 3. Test import
python3 -c "from api.index import app; print(app)"
# Should print: <Flask 'api.index'>

# 4. Local test
vercel dev
# Then visit http://localhost:3000
```

If local test works but Vercel doesn't:
- Check Vercel function logs in dashboard
- Ensure all environment variables are set
- Try removing and re-adding the project

---

**TL;DR:** Use the simplified approach with `rewrites` in `vercel.json`, put your Flask code in `api/index.py`, remove the `if __name__` block, and deploy!
