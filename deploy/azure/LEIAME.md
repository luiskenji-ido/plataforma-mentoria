# Publicar no Azure

**Recomendado: máquina virtual**, porque nela tudo funciona (agentes, Orquestrador, backups).

## 1. Máquina virtual — tudo funciona
1. Crie uma VM **Ubuntu 24.04** (B2s ou maior) e libere as portas 80 e 443.
2. Siga o guia do servidor Ubuntu: [`deploy/ubuntu`](../ubuntu) e a seção "Instalação em servidor Ubuntu 24.04" do ReadME.
3. Rode `python3 instalar.py` e escolha **Azure · máquina virtual**. Banco no mesmo servidor ou gerenciado:
   **Azure Database for MySQL** ou **for PostgreSQL**, ou **Azure SQL** (SQL Server).
4. Cópia dos backups fora do servidor: compartilhamento do **Azure Files** montado na VM.

## 2. Contêiner (App Service ou Container Apps) — com limitações
| Recurso | Situação |
|---|---|
| Telas, cadastros, e-mail, Google, Microsoft 365, Assistente | funcionam |
| Arquivos enviados e backups | só com **Azure Files** montado em `/app/uploads` e `/app/instance` |
| Agentes (Segurança, Banco, Funcionalidades, OmniTest) e Orquestrador | desligados (processos em segundo plano são encerrados) |
| Lembretes e backups agendados | **Container Apps Job** agendado (cron `0 * * * *`) com `python tarefas_agendadas.py` |

Passos:
1. Banco gerenciado (MySQL, PostgreSQL ou Azure SQL). No **Azure SQL**, o backup é automático (point-in-time) e a
   plataforma não gera arquivos de backup: a tela de Ambiente mostra o backup como desligado de propósito.
   Para SQL Server o driver ODBC 18 precisa estar na imagem (veja `requirements-sqlserver.txt`).
2. Imagem: `docker build -f deploy/conteiner/Dockerfile -t mentoria .` e envie ao **Azure Container Registry**.
3. Variáveis (senhas no **Key Vault**): `HOSPEDAGEM=azure_conteiner`, `DATABASE_URL`, `SECRET_KEY`, `APP_BASE_URL`,
   `MENTORIA_PRODUCAO=1`, `ATRAS_DE_PROXY=1`; com Azure Files: `DISCO_PERSISTENTE=1` e `BACKUP_DIR=/app/instance/backups`.
4. Primeira vez: um Job com `python instalar.py --respostas respostas.json` (ou `flask db upgrade`).
5. Porta do contêiner: 8080 (App Service: configuração `WEBSITES_PORT=8080`).

Depois de publicar, confira **Administração › Sistema › Ambiente e compatibilidade**.
