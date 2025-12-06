#!/bin/bash
# Script to help set up .env file

if [ ! -f .env.example ]; then
    echo "Error: .env.example not found"
    exit 1
fi

echo "Setting up .env file..."
cp .env.example .env

echo ""
echo "✅ .env file created!"
echo ""
echo "⚠️  IMPORTANT: You need to add your Gemini API key!"
echo ""
echo "To get your Gemini API key:"
echo "1. Go to: https://aistudio.google.com/apikey"
echo "2. Click 'Create API Key'"
echo "3. Copy the key and add it to .env as GEMINI_API_KEY=your_key_here"
