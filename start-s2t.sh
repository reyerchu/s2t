#!/bin/bash
cd /var/www/defintek.io/public_html/s2t

# Activate virtual environment for backend
source venv/bin/activate

# Start the backend server in the background
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload &

# Start the frontend server
cd frontend
npm start
