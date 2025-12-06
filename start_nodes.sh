#!/bin/bash
# Script to start all 5 nodes in separate terminal windows
# Usage: ./start_nodes.sh

# Check if running on macOS (Darwin) or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python3 node.py 1"'
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python3 node.py 2"'
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python3 node.py 3"'
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python3 node.py 4"'
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python3 node.py 5"'
    echo "Started 5 nodes in separate Terminal windows"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux (requires xterm or similar)
    xterm -e "python3 node.py 1" &
    xterm -e "python3 node.py 2" &
    xterm -e "python3 node.py 3" &
    xterm -e "python3 node.py 4" &
    xterm -e "python3 node.py 5" &
    echo "Started 5 nodes in separate xterm windows"
else
    echo "Unsupported OS. Please start nodes manually:"
    echo "  Terminal 1: python3 node.py 1"
    echo "  Terminal 2: python3 node.py 2"
    echo "  Terminal 3: python3 node.py 3"
    echo "  Terminal 4: python3 node.py 4"
    echo "  Terminal 5: python3 node.py 5"
fi

