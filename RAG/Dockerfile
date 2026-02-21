# Base: official Ollama image (includes CUDA runtime for GPU support)
FROM ollama/ollama:latest

WORKDIR /app

# Install Python and build tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Application code
COPY rag/ ./rag/
COPY server.py .

# Pre-built index (unicorn traffic rules)
COPY pdd_db/ ./pdd_db/

# Startup script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/data

# Environment defaults
ENV CHROMA_PATH=/app/pdd_db
ENV COLLECTION_NAME=pdd
ENV LLM_MODEL=qwen2.5:3b
ENV OLLAMA_HOST=http://localhost:11434
ENV MCP_TRANSPORT=sse
ENV OLLAMA_KEEP_ALIVE=-1

EXPOSE 8000

ENTRYPOINT []
CMD ["./entrypoint.sh"]
