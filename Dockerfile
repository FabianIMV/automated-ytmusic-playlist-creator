# ---- Etapa 1: compilar el frontend (Vite + React + TypeScript) ----
FROM node:22-alpine AS frontend

WORKDIR /build/frontend

# Dependencias primero, para aprovechar la caché de capas
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Las variables VITE_* se incrustan en el JavaScript durante el build.
# Render las pasa como build args porque están declaradas aquí con ARG (ver render.yaml).
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

RUN npm run build


# ---- Etapa 2: imagen final (API FastAPI + frontend compilado) ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist \
    DATA_DIR=/app/data

WORKDIR /app

# Usuario sin privilegios para ejecutar la app
RUN groupadd --system app \
 && useradd --system --gid app --no-create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY playlist_creator/ ./playlist_creator/
COPY --from=frontend /build/frontend/dist ./frontend/dist

RUN mkdir -p /app/data && chown app:app /app/data

USER app

EXPOSE 8000

# La imagen no trae curl; se usa Python para consultar /api/health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=4)"

# Forma shell para expandir ${PORT} (lo inyecta el PaaS). "exec" hace que uvicorn reciba las señales de parada.
CMD exec uvicorn playlist_creator.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
