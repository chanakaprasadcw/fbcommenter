#!/bin/bash

# Configuration
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="/tmp/chrome_dev_test"
PORT=9222

echo "Launching Chrome with Remote Debugging enabled on port $PORT..."
echo "User Data Directory: $USER_DATA_DIR"
echo "NOTE: This will open a separate Chrome instance. Please log in to Facebook in this window."

"$CHROME_PATH" --remote-debugging-port=$PORT --user-data-dir="$USER_DATA_DIR"
