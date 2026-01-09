#!/bin/bash

# Set environment variables
export NODE_ENV=production
export PATH=$PATH:/usr/local/bin:/usr/bin

# Change to the s2t directory
cd /home/reyerchu/s2t/s2t

# Build the frontend for production
cd frontend
npm run build

# Copy the build to the web directory
cp -r build/* /var/www/defintek.io/public_html/s2t/

# Go back to main directory
cd ..

# Start the Python backend server in the background
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload &
