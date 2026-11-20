# syntax=docker/dockerfile:1.7
# Imagem da plataforma para contêineres (AWS ECS/Fargate/App Runner, GCP Cloud Run, Azure Container Apps) e docker-compose.
# A MESMA imagem roda em dev, homologação e produção: tudo o que muda vem do ambiente (.env.example).
#
#   docker build -t mentoria .                                   (MySQL, padrão)
#   docker build --build-arg BANCO=postgresql -t mentoria .      (acrescenta o driver do PostgreSQL)
#
# Processos (mesma imagem, comando diferente):
#   web      gunicorn --config gunicorn.conf.py app:app          (padrão)
#   worker   python tarefas_agendadas.py --continuo              (backups, lembretes, requisições de mudança)
#   migrar   flask --app app db upgrade                          (uma vez por versão, antes do web)
#
# Segurança: usuário sem privilégios (uid 10001), sistema de arquivos só de leitura (monte /tmp e /app/instance como
# tmpfs), nenhum segredo na imagem nem nos build args (SECRET_KEY, banco, SMTP, chaves de IA chegam pelo ambiente).

ARG PYTHON_IMAGE=python:3.12.11-slim-bookworm

# ---------------------------------------------------------------- estágio 1: dependências (com ferramentas de build)
FROM ${PYTHON_IMAGE} AS build
ARG BANCO=mysql
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
# Só os arquivos de dependências: esta camada fica em cache enquanto eles não mudam
COPY requirements.txt requirements-postgresql.txt requirements.lock* ./
RUN if [ -f requirements.lock ]; then pip install --require-hashes -r requirements.lock; else pip install -r requirements.txt; fi \
 && if [ "$BANCO" = "postgresql" ]; then pip install "psycopg[binary]>=3.2,<4"; fi

# ---------------------------------------------------------------- estágio 2: execução (só o necessário)
FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 mentoria \
 && useradd --system --uid 10001 --gid mentoria --home-dir /app --shell /usr/sbin/nologin mentoria
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MENTORIA_CONTEINER=1 \
    MENTORIA_TAREFAS_NO_WEB=0 \
    MIGRAR_AO_INICIAR=0 \
    LOG_FORMATO=json
WORKDIR /app
# Código da aplicação (o .dockerignore tira testes, git, segredos, bancos locais, uploads e relatórios)
COPY --chown=root:root . .
# Bytecode gerado na imagem: com o sistema de arquivos só de leitura nada é escrito ao importar
RUN python -m compileall -q -j 0 /app /opt/venv >/dev/null \
 && mkdir -p /app/instance /app/uploads \
 && chown mentoria:mentoria /app/instance /app/uploads
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8080'), timeout=4)"]
# tini como PID 1: repassa o SIGTERM ao gunicorn (desligamento gracioso) e recolhe processos filhos
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
