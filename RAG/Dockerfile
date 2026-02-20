# Stage 1: grab Ollama binary from official image
FROM ollama/ollama:latest AS ollama-bin

# Stage 2: main image
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Ollama binary from official image
COPY --from=ollama-bin /usr/bin/ollama /usr/bin/ollama

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

EXPOSE 8000

CMD ["./entrypoint.sh"]
