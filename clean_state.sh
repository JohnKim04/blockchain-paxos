#!/bin/bash
# script to clean up all state files
# usage: ./clean_state.sh

echo "Cleaning up state files..."
rm -f state_node_*.json
echo "✓ All state files removed"
echo ""
echo "You can now start fresh nodes."

