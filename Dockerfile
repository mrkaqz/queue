FROM python:3.11-slim

# System deps for edge-tts and openssl
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app/ ./app/

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Data volume (SQLite DB + audio cache + certs)
VOLUME ["/app/data"]

EXPOSE 8080 8443

ENTRYPOINT ["/start.sh"]
