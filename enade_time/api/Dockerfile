# API FastAPI read-only do ENADE-Time Distribuído (Fase 5 — empacotamento).
#
# Build a partir da RAIZ do projeto, não de dentro de api/, porque o pacote
# é importado como `api.main:app` e precisa do diretório `api/` inteiro:
#     docker build -f api/Dockerfile -t enade-api .
#
# Uso normal: `docker compose --profile api up -d` (ver docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências primeiro: camada cacheada enquanto o requirements não mudar.
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

COPY api/ /app/api/

# Não roda como root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Sem --reload: em container o código não é montado do host.
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
