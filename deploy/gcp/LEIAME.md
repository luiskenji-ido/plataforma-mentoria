# Publicar no Google Cloud (GCP)

**Recomendado: máquina virtual**, porque nela tudo funciona (agentes, Orquestrador, backups).

## 1. Máquina virtual (Compute Engine) — tudo funciona
1. Crie uma VM **Ubuntu 24.04** (e2-small ou maior) e libere HTTP/HTTPS no firewall.
2. Siga o guia do servidor Ubuntu: [`deploy/ubuntu`](../ubuntu) e a seção "Instalação em servidor Ubuntu 24.04" do ReadME.
3. Rode `python3 instalar.py` e escolha **GCP · máquina virtual**. Banco no mesmo servidor ou no **Cloud SQL**
   (MySQL ou PostgreSQL).
4. Cópia dos backups fora do servidor: bucket do **Cloud Storage** montado com o gcsfuse ou sincronizado pelo rclone.

## 2. Contêiner (Cloud Run) — com limitações
| Recurso | Situação |
|---|---|
| Telas, cadastros, e-mail, Google, Microsoft 365, Assistente | funcionam |
| Arquivos enviados e backups | só com volume (**Cloud Storage** ou **Filestore**) montado em `/app/uploads` e `/app/instance` |
| Agentes (Segurança, Banco, Funcionalidades, OmniTest) e Orquestrador | desligados (o Cloud Run encerra processos fora da requisição) |
| Lembretes e backups agendados | **Cloud Run Job** com `python tarefas_agendadas.py`, disparado de hora em hora pelo **Cloud Scheduler** |

Passos:
1. Banco: **Cloud SQL** MySQL 8 ou PostgreSQL, com o banco `mentoria`; ligue o serviço ao Cloud SQL.
2. Imagem: `docker build -f deploy/conteiner/Dockerfile -t mentoria .` e envie ao **Artifact Registry**.
3. Variáveis (senhas no **Secret Manager**): `HOSPEDAGEM=gcp_conteiner`, `DATABASE_URL`, `SECRET_KEY`, `APP_BASE_URL`,
   `MENTORIA_PRODUCAO=1`, `ATRAS_DE_PROXY=1`; com volume: `DISCO_PERSISTENTE=1` e `BACKUP_DIR=/app/instance/backups`.
4. Primeira vez: um Cloud Run Job com `python instalar.py --respostas respostas.json` (ou `flask db upgrade`).
5. A porta vem da variável `PORT` (o Dockerfile já usa).

Depois de publicar, confira **Administração › Sistema › Ambiente e compatibilidade**.
