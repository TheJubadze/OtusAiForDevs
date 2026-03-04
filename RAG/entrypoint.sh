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

# Warm up: load models into GPU memory before server starts
echo "Warming up models..."
curl -s -X POST http://localhost:11434/api/embeddings \
    -H 'Content-Type: application/json' \
    -d '{"model":"nomic-embed-text","prompt":"warmup"}' > /dev/null
curl -s -X POST http://localhost:11434/api/chat \
    -H 'Content-Type: application/json' \
    -d '{"model":"qwen2.5:3b","messages":[{"role":"user","content":"hi"}],"stream":false}' > /dev/null
echo "Модели готовы!"

# Start MCP server (keeps the container alive)
exec python3 server.py
