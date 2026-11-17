# Imagem da plataforma para contêineres (AWS App Runner / ECS, GCP Cloud Run, Azure App Service / Container Apps).
# Gerar, a partir da pasta da plataforma:
#   docker build -f deploy/conteiner/Dockerfile -t mentoria .                       (MySQL)
#   docker build -f deploy/conteiner/Dockerfile --build-arg BANCO=postgresql -t mentoria .
# O banco é sempre gerenciado pela nuvem (DATABASE_URL). Arquivos enviados e backups só ficam guardados com
# volumes montados em /app/uploads e /app/instance (DISCO_PERSISTENTE=1); sem eles, o disco some a cada reinício.
FROM python:3.12-slim

ARG BANCO=mysql
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080

# Ferramentas de backup do banco escolhido (mysqldump / pg_dump)
RUN apt-get update \
 && if [ "$BANCO" = "postgresql" ]; then apt-get install -y --no-install-recommends postgresql-client; \
    elif [ "$BANCO" = "mysql" ]; then apt-get install -y --no-install-recommends default-mysql-client; fi \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$BANCO" = "postgresql" ]; then pip install --no-cache-dir -r requirements-postgresql.txt; fi
COPY . .

# Usuário sem privilégios
RUN useradd --create-home --uid 1000 mentoria && mkdir -p /app/instance /app/uploads && chown -R mentoria /app/instance /app/uploads
USER mentoria

EXPOSE 8080
CMD exec gunicorn --preload --workers 2 --threads 4 --timeout 180 --bind 0.0.0.0:${PORT} app:app
