FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the Cloud Run port
EXPOSE 8080

# Start the Agent
CMD ["sh", "-c", "uvicorn agents.concierge_agent:app --host 0.0.0.0 --port ${PORT:-8080}"]
