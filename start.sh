#!/bin/sh
set -e

CERT_DIR="/app/data/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"

# Generate self-signed TLS certificate if not present
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
  echo "[start] Generating self-signed TLS certificate..."
  mkdir -p "$CERT_DIR"
  openssl req -x509 -newkey rsa:2048 -keyout "$KEY_FILE" -out "$CERT_FILE" \
    -days 3650 -nodes \
    -subj "/CN=queue-app" \
    -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
  echo "[start] Certificate generated at $CERT_FILE"
fi

# Set VAPID_EMAIL from environment if provided
if [ -n "$VAPID_EMAIL" ]; then
  export VAPID_EMAIL_ENV="$VAPID_EMAIL"
fi

echo "[start] Starting Queue app..."

# Start HTTP server (background)
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 1 \
  &

# Start HTTPS server (foreground)
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8443 \
  --workers 1 \
  --ssl-keyfile "$KEY_FILE" \
  --ssl-certfile "$CERT_FILE"
