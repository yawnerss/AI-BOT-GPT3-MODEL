# Quick Start - Vercel Deployment

## The Fix for "No flask entrypoint found"

Your error is simple to fix! Vercel needs your Flask app in `api/index.py`.

### Step-by-Step Fix (5 minutes)

1. **Create the api directory:**
   ```bash
   mkdir -p api
   touch api/__init__.py
   ```

2. **Copy your Flask code:**
   ```bash
   # Copy your main Python file into api/index.py
   cp your_flask_app.py api/index.py
   ```

3. **Edit api/index.py - Make 2 changes:**

   **Change #1** - Update file paths (around line 22-24):
   ```python
   # FROM:
   CLIPFLY_TOKEN_FILE = "token.txt"
   CLIPFLY_IMAGES_DIR = "generated_images"
   
   # TO:
   CLIPFLY_TOKEN_FILE = "/tmp/token.txt"
   CLIPFLY_IMAGES_DIR = "/tmp/generated_images"
   ```

   **Change #2** - Remove the bottom section (around line 2400):
   ```python
   # REMOVE OR COMMENT OUT THIS ENTIRE BLOCK:
   # if __name__ == '__main__':
   #     if ADMIN_USER_ID not in USERS:
   #         USERS[ADMIN_USER_ID] = {...}
   #     ensure_image_directory()
   #     print("=" * 60)
   #     ...
   #     app.run(host='0.0.0.0', port=5000, debug=True)
   ```

4. **Verify these files exist:**
   - ✅ `api/__init__.py` (empty file)
   - ✅ `api/index.py` (your Flask code with 2 changes)
   - ✅ `vercel.json` (configuration)
   - ✅ `requirements.txt` (dependencies)

5. **Deploy:**
   ```bash
   vercel --prod
   ```

That's it! ✨

## What Changed?

| Before | After |
|--------|-------|
| `app.py` or `main.py` in root | `api/index.py` |
| `token.txt` | `/tmp/token.txt` |
| `if __name__ == '__main__':` block | Removed |

## File Structure

```
your-project/
├── api/
│   ├── __init__.py          # Empty file
│   └── index.py             # Your Flask app (modified)
├── vercel.json              # Vercel config
├── requirements.txt         # Dependencies
├── pyproject.toml          # Python project config
└── .vercelignore           # Files to ignore
```

## Verify It Works Locally

```bash
# Install Vercel CLI
npm i -g vercel

# Test locally
vercel dev

# Should show:
# > Ready! Available at http://localhost:3000
```

## Common Mistakes

❌ **Wrong:** Flask file in root as `app.py`  
✅ **Right:** Flask file at `api/index.py`

❌ **Wrong:** Keeping `if __name__ == '__main__':` block  
✅ **Right:** Remove it or comment it out

❌ **Wrong:** Using relative paths like `"token.txt"`  
✅ **Right:** Use absolute paths like `"/tmp/token.txt"`

## Environment Variables

Set in Vercel Dashboard (Settings → Environment Variables):

```
SECRET_KEY=your-random-secret-key-here
ADMIN_PASSWORD=your-admin-password
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

## Test Your Deployment

After deploying:

```bash
# Your URL will be something like:
# https://your-project.vercel.app

curl https://your-project.vercel.app/health

# Should return:
# {"status": "ok", ...}
```

## Need Help?

- Error persists? Check `api/index.py` has `app = Flask(__name__)` at the top
- Import errors? Ensure all imports are in `requirements.txt`
- 404 errors? Check `vercel.json` routes configuration

---

**The key fix:** Move your Flask code to `api/index.py` and remove the `if __name__ == '__main__':` block!
