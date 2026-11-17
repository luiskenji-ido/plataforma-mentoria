# Publicar na AWS

> **Primeira vez na AWS?** Siga o roteiro completo, com imagens: [`Roteiro_deploy_AWS.docx`](Roteiro_deploy_AWS.docx)
> (da criação da conta gratuita ao site no ar com HTTPS e backups, em 12 etapas; ilustrações em `imagens/`).

Há dois caminhos. **Recomendado: máquina virtual**, porque nela tudo funciona (agentes, Orquestrador, backups).

## 1. Máquina virtual (EC2 ou Lightsail) — tudo funciona
1. Crie uma instância **Ubuntu 24.04** (2 GB de RAM ou mais) e libere as portas 80 e 443 no grupo de segurança.
2. Siga o guia do servidor Ubuntu: [`deploy/ubuntu`](../ubuntu) e a seção "Instalação em servidor Ubuntu 24.04" do ReadME.
3. Rode `python3 instalar.py` e escolha **AWS · máquina virtual**. Banco no mesmo servidor ou no **Amazon RDS**
   (MySQL ou PostgreSQL): no RDS, responda "não" a "o banco fica neste mesmo servidor?" e informe o endereço do RDS.
4. Pasta de backups padrão: `/var/backups/mentoria`. Para a cópia fora do servidor, monte um bucket S3 com o
   rclone (ou um volume EFS) e informe a pasta em "cópia dos backups FORA do servidor".

## 2. Contêiner (App Runner ou ECS Fargate) — com limitações
| Recurso | Situação |
|---|---|
| Telas, cadastros, e-mail, Google, Microsoft 365, Assistente | funcionam |
| Arquivos enviados e backups | só com volume **EFS** montado em `/app/uploads` e `/app/instance` (ECS) |
| Agentes (Segurança, Banco, Funcionalidades, OmniTest) e Orquestrador | desligados (o contêiner encerra processos em segundo plano) |
| Lembretes e backups agendados | tarefa agendada do **EventBridge Scheduler** rodando `python tarefas_agendadas.py` na mesma imagem |

Passos:
1. Banco gerenciado: crie um **RDS** MySQL 8 (charset utf8mb4) ou PostgreSQL e o banco `mentoria`.
2. Imagem: `docker build -f deploy/conteiner/Dockerfile -t mentoria .` (PostgreSQL: `--build-arg BANCO=postgresql`)
   e envie ao **ECR**.
3. Variáveis do serviço (use o **Secrets Manager** para senhas):
   `HOSPEDAGEM=aws_conteiner`, `DATABASE_URL`, `SECRET_KEY`, `APP_BASE_URL`, `MENTORIA_PRODUCAO=1`, `ATRAS_DE_PROXY=1`;
   com EFS: `DISCO_PERSISTENTE=1` e `BACKUP_DIR=/app/instance/backups`.
4. Primeira vez: rode uma tarefa única com a mesma imagem e o comando `python instalar.py --respostas respostas.json`
   (ou `flask db upgrade`) para criar a estrutura.
5. Porta do contêiner: 8080.

Depois de publicar, confira **Administração › Sistema › Ambiente e compatibilidade**.
