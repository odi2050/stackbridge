FROM python:3.12-slim
ARG APP_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="StackBridge" \
      org.opencontainers.image.description="Document Import Studio for BookStack" \
      org.opencontainers.image.version="${APP_VERSION}"
ENV STACKBRIDGE_VERSION="${APP_VERSION}" \
    AI_MAX_INPUT_TOKENS=3000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng pandoc libreoffice-writer && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY scripts/docker-entrypoint.sh /usr/local/bin/stackbridge-entrypoint
RUN chmod +x /usr/local/bin/stackbridge-entrypoint
EXPOSE 5050
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:5050/api/health', timeout=3)"]
ENTRYPOINT ["/usr/local/bin/stackbridge-entrypoint"]
CMD ["waitress-serve","--host=0.0.0.0","--port=5050","--threads=8","app:app"]
