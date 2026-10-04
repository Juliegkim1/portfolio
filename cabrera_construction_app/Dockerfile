# Production image for Cloud Run. Builds the frontend, then serves it and
# the API from one FastAPI process (see app/backend/app/main.py's static
# mount) — no separate reverse proxy needed for a single-subdomain deployment.
#
# Build context is cabrera_construction_app/ (THIS file's own directory, not
# app/) — it needs to see app/ AND templates/, which are siblings, not
# parent/child: `gcloud builds submit --tag <image> .` run from here.

FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY app/backend/pyproject.toml app/backend/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY app/backend/app ./app
RUN uv sync --frozen

COPY --from=frontend-build /frontend/dist /app/frontend_dist
COPY templates /templates

ENV TEMPLATES_DIR=/templates
ENV FRONTEND_DIST_DIR=/app/frontend_dist

# Cloud Run sets $PORT at runtime (defaults to 8080) and expects the
# container to listen on it.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
