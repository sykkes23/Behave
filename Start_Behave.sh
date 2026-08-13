#!/bin/bash
echo "Starting Behave AI Laboratory..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null
then
    echo "Error: python3 is not installed or not in your PATH."
    echo "Please install Python 3 to run Behave."
    read -p "Press enter to continue..."
    exit 1
fi

# Start the demo agent in the background
echo "Starting local demo agent (Agent v1 & v2)..."
python3 demo_agent.py &
DEMO_AGENT_PID=$!

# Start the Flask app in the background
echo "Starting Behave Dashboard..."
python3 app.py &
APP_PID=$!

echo "Waiting for services to start..."
sleep 2

# Open browser
echo "Opening dashboard..."
if command -v xdg-open &> /dev/null
then
    xdg-open http://127.0.0.1:5000
elif command -v open &> /dev/null
then
    open http://127.0.0.1:5000
else
    echo "Please open your browser to http://127.0.0.1:5000"
fi

echo "Behave is running. Press Ctrl+C to stop."
wait $APP_PID

# Cleanup on exit
kill $DEMO_AGENT_PID
