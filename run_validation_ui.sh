#!/bin/bash

# Workshop Lambda Validation UI Launcher
echo "🚀 Starting Workshop Lambda Validation UI..."
echo "Make sure your AWS credentials are configured!"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit not found. Please install dependencies first:"
    echo "pip install -e ."
    exit 1
fi

# Launch the Streamlit app
streamlit run src/workshop_validation_ui.py --server.port 8501 --server.address 0.0.0.0

echo "✅ UI stopped."