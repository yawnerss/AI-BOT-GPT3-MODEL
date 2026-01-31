#!/bin/bash

# This script prepares your Flask app for Vercel deployment

echo "========================================="
echo "VERCEL DEPLOYMENT PREPARATION SCRIPT"
echo "========================================="
echo ""

# Instructions
cat << 'EOF'
TO FIX THE "No flask entrypoint found" ERROR:

1. Create the api directory:
   mkdir -p api

2. Copy your Flask code into api/index.py:
   cp your_app.py api/index.py

3. Edit api/index.py and make these changes:

   Line ~22-24, change:
   FROM:
     CLIPFLY_TOKEN_FILE = "token.txt"
     CLIPFLY_IMAGES_DIR = "generated_images"
   
   TO:
     CLIPFLY_TOKEN_FILE = "/tmp/token.txt"
     CLIPFLY_IMAGES_DIR = "/tmp/generated_images"

   Bottom of file (~line 2400), REMOVE or COMMENT OUT:
     # if __name__ == '__main__':
     #     # Initialize admin user
     #     if ADMIN_USER_ID not in USERS:
     #         USERS[ADMIN_USER_ID] = {...}
     #     
     #     ensure_image_directory()
     #     print("=" * 60)
     #     ...
     #     app.run(host='0.0.0.0', port=5000, debug=True)

4. Create api/__init__.py (empty file):
   touch api/__init__.py

5. Ensure vercel.json exists with:
   {
     "version": 2,
     "builds": [
       {"src": "api/index.py", "use": "@vercel/python"}
     ],
     "routes": [
       {"src": "/(.*)", "dest": "api/index.py"}
     ]
   }

6. Ensure requirements.txt has:
   flask>=2.3.0
   requests>=2.31.0
   gunicorn>=21.0.0
   python-dotenv>=1.0.0

7. Deploy:
   vercel --prod

FINAL FILE STRUCTURE:
your-project/
├── api/
│   ├── __init__.py          (empty)
│   └── index.py             (your Flask app with modifications)
├── vercel.json
├── requirements.txt
├── pyproject.toml
└── README.md

THAT'S IT!
EOF

echo ""
echo "========================================="
echo "Quick commands:"
echo "mkdir -p api"
echo "touch api/__init__.py" 
echo "# Then copy your Flask code to api/index.py"
echo "# Make the 2 changes mentioned above"
echo "vercel --prod"
echo "========================================="
