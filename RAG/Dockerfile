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

# Create directories for data
RUN mkdir -p /app/data /app/chroma_db

# Environment variables
ENV CHROMA_PATH=/app/chroma_db
ENV COLLECTION_NAME=documents
ENV LLM_MODEL=qwen2.5:3b
ENV OLLAMA_HOST=http://ollama:11434

EXPOSE 8000

CMD ["python", "server.py"]
