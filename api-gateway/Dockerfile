# ─────────────────────────────────────────────────────────────
# Stage 1 : builder — installe les dépendances dans un venv
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Évite les fichiers .pyc et les buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Outils système minimaux pour compiler certains packages C
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Crée un virtualenv isolé
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Installe les dépendances en une seule couche (cache Docker)
COPY requirements.txt .
RUN pip install --upgrade pip==24.0 && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────
# Stage 2 : runtime — image finale légère sans outils de build
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Dépendance runtime uniquement (libpq pour asyncpg/psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copie le venv depuis le builder
COPY --from=builder /opt/venv /opt/venv

# Copie le code applicatif
COPY . .

# Utilisateur non-root pour la sécurité
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
