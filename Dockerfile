FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY start.sh /start.sh
RUN chmod +x /start.sh

VOLUME ["/app/data"]
EXPOSE 8080 8443
ENTRYPOINT ["/start.sh"]
