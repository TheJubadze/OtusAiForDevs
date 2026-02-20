#!/bin/bash
set -e

# Start Ollama server in background
ollama serve &
OLLAMA_PID=$!

# Wait until Ollama is ready
echo "Waiting for Ollama to start..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done
echo "Ollama is ready."

# Pull models if not already cached
echo "Checking models..."
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
echo "Модели готовы!"

# Start MCP server (keeps the container alive)
exec python server.py
