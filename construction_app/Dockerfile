FROM python:3.11-slim

WORKDIR /app

# System deps for ReportLab (libz) and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (API-only — no Kivy)
COPY api-requirements.txt .
RUN pip install --no-cache-dir -r api-requirements.txt

# Copy app source
COPY . .

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
