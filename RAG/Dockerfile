FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY rag/ ./rag/
COPY server.py .

# Copy pre-built index (unicorn traffic rules)
COPY pdd_db/ ./pdd_db/

# Create directory for user-mounted docs
RUN mkdir -p /app/data

# Environment variables (defaults for unicorn demo)
ENV CHROMA_PATH=/app/pdd_db
ENV COLLECTION_NAME=pdd
ENV LLM_MODEL=qwen2.5:3b
ENV OLLAMA_HOST=http://ollama:11434
ENV MCP_TRANSPORT=stdio

EXPOSE 8000

CMD ["python", "server.py"]
