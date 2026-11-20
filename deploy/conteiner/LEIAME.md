# Plataforma em contêiner (nuvem e desenvolvimento local)

A mesma imagem (`Dockerfile` da raiz) roda em desenvolvimento, homologação e produção. Tudo o que muda entre eles
vem de variáveis de ambiente (`.env.example` lista todas, só com valores de exemplo).

## Processos e serviços de apoio

| Processo | Comando | Papel |
|---|---|---|
| web | `gunicorn --config gunicorn.conf.py app:app` (padrão da imagem) | atende os pedidos; escala na horizontal |
| worker | `python tarefas_agendadas.py --continuo` | backups, lembretes e requisições de mudança (uma réplica) |
| migrar | `flask --app app db upgrade` | aplica as migrações, uma vez por versão, antes do web |

| Serviço de apoio | Para quê | Na AWS |
|---|---|---|
| MySQL 8.4 | dados | Amazon RDS for MySQL |
| Redis 7 | limite de tentativas de login entre réplicas, batimento do worker | ElastiCache for Redis |
| S3 / MinIO | arquivos enviados (aulas, anexos, gravações, TCC, acervo, logos) | Amazon S3 (papel IAM da tarefa) |

O contêiner não guarda estado: sessões ficam no cookie assinado, arquivos no bucket, limites no Redis. Pode ser
reiniciado ou multiplicado a qualquer momento.

## Saúde, logs e desligamento

- `GET /healthz`: o processo responde (sonda de liveness; não depende do banco).
- `GET /readyz`: banco, Redis e bucket respondem (sonda de readiness; 503 tira a réplica do balanceador).
- Logs: uma linha JSON por evento na saída padrão, com `request_id`; segredos e e-mails mascarados.
- SIGTERM: o gunicorn para de aceitar conexões, termina os pedidos em andamento (até `GUNICORN_GRACEFUL_TIMEOUT`)
  e fecha as conexões do banco. O worker termina a tarefa em andamento e sai.

## Segurança da imagem

- Base `python:3.12.11-slim-bookworm` fixada; dois estágios (ferramentas de build só no primeiro).
- Usuário sem privilégios (uid 10001); funciona com o sistema de arquivos só de leitura (monte `/tmp` e
  `/app/instance` como tmpfs).
- Nenhum segredo na imagem ou nos build args: `SECRET_KEY` (obrigatória, o contêiner não sobe sem ela), banco,
  SMTP e chaves de IA chegam pelo ambiente; `client_secret.json` do Google é montado como segredo e indicado em
  `GOOGLE_CLIENT_SECRETS_FILE`.
- `ENTRYPOINT` em forma exec com `tini`: o SIGTERM chega ao gunicorn.

## Comandos

```bash
cp .env.example .env        # defina SECRET_KEY: python -c "import secrets; print(secrets.token_hex(32))"
docker compose up --build   # http://localhost:8080 (MySQL, Redis, MinIO, migração, web e worker)
docker compose down -v      # para tudo e apaga os dados locais
```

Imagem sozinha:

```bash
docker build -t mentoria .
docker run --rm -p 8080:8080 --read-only --tmpfs /tmp --tmpfs /app/instance --env-file .env mentoria
```

## Testes

```bash
pip install -r requirements-dev.txt
pytest tests/unit          # unidade: sem rede, banco ou disco (segundos)
pytest tests/integration   # integração: app + MySQL 8.4 real em contêiner (Testcontainers)
pytest tests/e2e           # ponta a ponta: constrói a imagem e testa com MySQL, Redis e MinIO (docker compose)
pytest tests/unit tests/integration --cov --cov-report=term   # cobertura
```

Sem Docker, a integração roda contra outro banco: `TEST_DATABASE_URL=sqlite:////tmp/it.db pytest tests/integration`.

## O que fica de fora no contêiner

- Agentes de teste (Playwright) e Orquestrador executor: precisam de git, navegador e disco persistente. A tela
  Ambiente mostra isso; rode-os num servidor ou no computador.
- Backups pela própria plataforma: no contêiner use os snapshots do banco gerenciado (RDS). Com volume persistente,
  `DISCO_PERSISTENTE=1` e `BACKUP_DIR` religam os backups.
