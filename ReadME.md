Markdown
# 🧠 Projeto Mentoria de Estudos - Gestão e Acompanhamento

## 📘 Visão Geral
	Este projeto é uma **plataforma web robusta de mentoria de estudos** desenvolvida em **Python (Flask)**. O sistema
	foi projetado para centralizar o acompanhamento de alunos, gerenciar catálogos de treinamentos, auditar histórico
	de ações, calcular riscos de abandono e fornecer painéis executivos de resultados. 

	O foco é oferecer governança total para os mentores e uma experiência organizada, inteligente e motivadora para os
	alunos, contando com integrações modernas de Inteligência Artificial e produtividade.

---

## 🚀 Tecnologias Utilizadas
	- **Python 3.14.6**
	- **Flask** – Framework web principal.
	- **Flask-Login** – Controle de sessões e autenticação.
	- **Flask-Bcrypt** – Criptografia avançada de senhas.
	- **Flask-SQLAlchemy** – ORM: o mesmo código roda em SQLite, MySQL/MariaDB ou PostgreSQL (DATABASE_URL).
	- **Flask-Migrate (Alembic)** – versões da estrutura do banco (pasta migrations/).
	- **Bootstrap 5 & CSS3** – Interface visual moderna, responsiva e com alertas dinâmicos.
	- **Chart.js** – Renderização de gráficos para dashboards de indicadores.
	- **Werkzeug** – Gerenciamento e segurança no upload de arquivos físicos (Certificados e Materiais).
	- **Google Generative AI (Gemini)** – Motor de Inteligência Artificial para o assistente virtual de estudos.
	- **Google Calendar API** – Integração via OAuth2 para agendamento automatizado.

---

## 🧩 Estrutura do Projeto
```text
mentoria/
	│
	├── app.py							# Cérebro da aplicação, rotas, integrações (IA/Agenda) e controle do sino de notificações                     		
	├── models.py						# Estrutura do Banco de Dados (Usuário, Curso, Acompanhamento, Sessão, QADuvida, Projeto, Tarefa, Grupo)   	              		
	├── traducoes.py					# Dicionário de internacionalização (i18n) para PT, EN e ES               		
	├── client_secret.json				# Credenciais OAuth2 para integração com APIs do Google		         		
	├── templates/						# Páginas e interfaces HTML (Jinja2)               		
	│   ├── index.html					# Página inicial (login, recuperação e motivação)             		
	│   ├── base.html					# Template base estrutural contendo o Sino de Notificações Inteligente              		
	│   ├── dashboard.html				# Painel Executivo e Matriz de Riscos         		
	│   ├── acompanhamento.html			# Gestão de progresso, Assistente Gemini, Q&A, uploads e modais expandidos    		
	│   ├── sessoes.html				# Controle de encontros de mentoria   
	│   ├── projetos.html				# Gestão de Projetos/TCC com Subtarefas em cascata e equipes de apoio        		
	│   ├── admin_usuarios.html			# Governança de acessos, com suporte a múltiplos mentores e reset de segurança    		
	│   ├── admin_cursos.html			# Catálogo de portfólio e auditoria      		
	│   ├── admin_banco.html			# Gestão administrativa do banco de dados, backups e auditoria          	
    │   ├── admin_solicitacoes.html		# Gestão de solicitações de mentoria (Apenas Mentor Administrador)  	
	│   ├── cadastrar_perguntas.html	# Configuração de segurança  	
	│   ├── perguntas_seguranca.html 	# Recuperação de senha baseada em perguntas 	
    │   └── trocar_senha.html			# Interface de troca de senha obrigatória 			
	├── static/							# Arquivos estáticos globais (CSS, JS, Imagens)               			
	├── uploads/						# Diretório de armazenamento seguro de arquivos anexados              			
	├── atualizar_*.py					# Scripts de migração e atualização de tabelas do BD        			
	└── README.md						# Documentação oficial do projeto             			

🔐 Controle de Acesso e Perfis

	O sistema opera sob rigorosa governança, segmentado em quatro grupos de permissão:

	Aluno: Visualiza seu próprio painel, atualiza % de progresso, anexa arquivos e altera status básicos (Iniciado, Parado, Finalizado). Interage via Q&A, utiliza a IA de estudos e visualiza (apenas leitura) o Parecer do Mentor.

	Mentor: Acompanha seus alunos, gerencia sessões e possui poder de alterar status avançados (Pendente, Desistência) e gerenciar Prioridades. Possui acesso de edição ao Parecer Oficial, respondendo ativamente aos alunos via Q&A.

	Mentor Administrador: Governança total do catálogo de cursos, recebe e aprova solicitações de mentoria e acessa a visão executiva de todos os usuários. Visualização restrita da página de Solicitações.

	Administrador: Controle absoluto do sistema e da tabela core de usuários. Visualização restrita da página de Solicitações (não tem acesso).

🛡️ Política de Senhas e Segurança

	Exigência de complexidade: Mínimo de 10 caracteres contendo letra maiúscula, minúscula, número e caractere especial.

	Validade e Expiração: Troca obrigatória a cada 90 dias (com avisos visuais integrados ao dashboard).

	Recuperação de Conta: Fluxo baseado em 3 perguntas de segurança customizáveis, exigindo no mínimo 2 acertos.

	Reset de Segurança: Administradores e Mentores Administradores podem forçar o recadastro das perguntas de segurança de um usuário, garantindo a recuperação de contas.

	Criptografia: Irreversível no banco de dados.

🧮 Módulos e Funcionalidades Principais

	📊 1. Dashboard Executivo e Indicadores

			Painel de 4 Cards + Resumo de Projetos: Exibe total de alunos, treinamentos finalizados, saúde dos cursos e indicadores rápidos de projetos em andamento/concluídos.

			Matriz de Risco (Saúde do Aluno): Tabela visual dinâmica que classifica o andamento dos estudos em Saudável (Verde), Em Atenção (Amarelo) ou Risco Crítico (Vermelho).

			Filtros de visualização: Visão individual (Aluno) vs. Visão Macro (Mentor/Admin).


	🤖 2. Inovações e Integrações Inteligentes

			Assistente Gemini Notebook: Chat de Inteligência Artificial integrado capaz de gerar simulados, revisar conceitos e analisar dúvidas.

			Agenda Automática: Integração com o Google Calendar via OAuth2.

			Multilíngue Dinâmico (i18n): Sistema totalmente traduzido e adaptável em tempo real para Português (PT), Inglês (EN) e Espanhol (ES).

			Tematização Avançada: Arquitetura CSS responsiva com opções de temas visuais (Claro, Escuro, Futurista e Vintage).

			Tour Interativo (Onboarding): Fluxo guiado para novos usuários utilizando Intro.js.


	📚 3. Catálogo e Ciclo de Vida de Cursos

			Cadastro detalhado: Nome, Plataforma, URL, Carga Horária e exigência de certificado.

			Categorização: Segmentação estratégica em Hard Skills e Soft Skills.

			Auditoria de Criação e Desativação: Rastreabilidade com "carimbo" de Data e Login do autor.


	🎯 4. Acompanhamento de Estudos (Core do Negócio)

			Gestão de Datas e Upload Duplo de arquivos (Certificados e Materiais).

			Sistema de Q&A (Dúvidas e Respostas) com linha do tempo.

			Modais Expandidos Inteligentes com rastreio automático de última atualização.

			Notificações Inteligentes (Sino).


	🗓️ 5. Gestão de Sessões e Administração

			Módulo dedicado para agendamento, registro de pautas e acompanhamento de reuniões de mentoria.

			Histórico de Feedback das sessões.

			Interface administrativa robusta (CRUD) e Módulo de Manutenção de Banco de Dados.


	📋 6. Gestão de Projetos e TCC (Work Breakdown Structure)

			Hierarquia de Tarefas (Cascata): Criação de Tarefas Principais e Subtarefas, com recálculo matemático inteligente e automático (a média de progresso das filhas atualiza a pai, que em cascata atualiza a conclusão do projeto).

			Múltiplos Responsáveis: Definição estruturada de um Líder de tarefa e seleção múltipla para Equipe de Apoio via modal responsivo.

			Governança de Exclusão: Botão de exclusão total de projeto restrito por perfil (apenas Mentores e Admins), executando rotina de limpeza completa (Drop constraint) para todas as tarefas vinculadas.

			Interface Estilo Excel: Tabela visual dinâmica com diferenciação visual entre tarefas (indentação em formato de árvore) e ações em bloco.


	⚖️ Regras de Negócio e Travas Sistêmicas

		Trava de Certificação: A barra de progresso não salva em 100% até que o arquivo físico do certificado seja anexado.

		Bloqueio de Matrícula Obsoleta: Impede alocação em cursos com status "Desativado".

		Cascata de Desativação (Trigger): Mudança em massa de status com notas de auditoria automáticas.

		Governança Multi-Mentor: Checkboxes de seleção múltipla para mentores.

		Rotina de Backup em Background: Watcher assíncrono para backups programados do SQLite sem impactar a performance.

⚙️ Instruções de Instalação e Execução

	1️⃣ Preparação do Ambiente
		Certifique-se de ter o Python instalado. Abra o terminal na raiz do projeto e crie o ambiente virtual:
		python -m venv venv
		Ative o ambiente:
		Windows: venv\Scripts\activate
		Linux/Mac: source venv/bin/activate

	2️⃣ Instalação de Dependências
		pip install flask flask-login flask-bcrypt flask-sqlalchemy werkzeug google-generativeai google-auth-oauthlib google-api-python-client

	3️⃣ Configuração de APIs Externas

		Google Generative AI: Adicione sua API_KEY ou defina a variável de ambiente GEMINI_API_KEY.

		Google Calendar: Insira o arquivo client_secret.json na raiz do projeto.

	4️⃣ Sincronização do Banco de Dados (Migrações)
		Execute os scripts de atualização das tabelas na ordem abaixo:
		python atualizar_tipo_curso.py
		python atualizar_status_curso.py
		python atualizar_data_curso.py
		python atualizar_criador_curso.py
		python atualizar_auditoria.py
		python atualizar.py
		python atualizar_banco.py

	🤖 Assistente da Plataforma (chat, só para o Administrador)
		Menu Administração › Sistema › Assistente da Plataforma, ou o botão de chat no canto de qualquer página.
		Responde com base na Base de conhecimento e cita as fontes como [1], [2]:
		- Agentes gerentes (atualizada sozinha): aprendizados aplicados dos gerentes Técnico, de Segurança, de Banco de
		  Dados e de Funcionalidades, os parâmetros de regras e os módulos de cada perfil.
		- Guia das telas (atualizado sozinho, guia_telas.py): onde cada tela fica no menu, quem acessa e o passo a passo
		  do Tour guiado. É o que permite ao Assistente responder perguntas de "como faço" em passos numerados.
		- Documentos do projeto: na aba Base de conhecimento, envie o PRD, o PTD e o DTD (.md, .txt, .html, .docx ou .pdf).
		  Reenviar com o mesmo tipo e título cria a versão seguinte e desativa a anterior.
		O chat abre pelo ícone ao lado de Administração. Para ler PDF, instale o pacote pypdf (pip install pypdf).
		Tom de colega de suporte: resposta acolhedora, passos numerados com o caminho no menu e os botões em negrito.
		Contas de teste (@local.com) e servidores sem IA respondem com o passo a passo do Guia das telas, sem mostrar
		o erro técnico (que fica em Provedores de IA e custos).
		Código: base_conhecimento.py (fontes, trechos e busca), chat_assistente.py (conversa e IA).

	💲 Provedores de IA e custos (Administração › Sistema › Provedores de IA e custos)
		Para cada uso (Assistente, Assistente do Acompanhamento e Agente Orquestrador): liga/desliga, modelo principal e
		até duas reservas (Claude ou Gemini). Padrão do Assistente: Claude Haiku 5.5, com o Gemini Flash e o Gemini Flash
		Lite (mais estável quando o Google está sobrecarregado) de reserva.
		Teto de gasto mensal e aviso em Parâmetros de regras (grupo Inteligência artificial); ao atingir o teto as IAs
		param até o mês seguinte. A mesma primeira pergunta reaproveita a resposta (sem custo).
		Chaves em Agentes IA › Credenciais: ANTHROPIC_API_KEY e GEMINI_API_KEY. Código: provedores_ia.py.

	🧭 Tour guiado
		Motor único em templates/_tour_motor.html: segue o menu de cada perfil, abre as abas ({aba: '#painel'}) e explica
		sozinho os botões e abas que nenhum passo cobre. Os agentes OmniTest cobram balões no lugar, seções, abas e botões;
		o Agente Gerente Técnico aprende o mapa de cada perfil e os erros do tour (conhecimento_tour.py) e ensina os agentes,
		que conferem primeiro os erros já vistos e avisam quando foram corrigidos.

	🏢 Identidade da instituição (Administração › Sistema › Identidade da instituição)
		Cada cliente tem a sua própria instalação. Nenhum nome de instituição ou de programa fica no código: as telas,
		os e-mails, os convites, os certificados e o Assistente leem os dados cadastrados nesta tela:
		- Nome da instituição (ex.: "Instituto Exemplo") – termo de adesão, certificados, verificação pública;
		- Apelido (sigla) – forma curta dos botões e rótulos, ex.: "Reuniões IEX × B2B", "Gestão IEX";
		- Nome da plataforma ou do programa – menu, título das páginas, assinatura dos e-mails e convites;
		- Logo, site, e-mail de contato e o cargo de quem assina o certificado pela instituição.
		Enquanto a identidade não for salva, as telas mostram nomes genéricos e o Administrador vê um aviso.
		Nos textos traduzidos use os marcadores {apelido}, {instituicao} e {plataforma}: t() e tt() trocam pelo
		cadastrado. Nos templates: {{ marca.apelido }}, {{ marca.nome }}, {{ marca.plataforma }}. Código: identidade.py.

	🗄️ Banco de dados (SQLite, MySQL, PostgreSQL)
		O endereço vem de DATABASE_URL (arquivo .env). Sem ela, usa o SQLite de desenvolvimento (instance/mentoria.db).
		- MySQL / MariaDB: mysql+pymysql://usuario:senha@localhost:3306/mentoria?charset=utf8mb4
		- PostgreSQL:      postgresql+psycopg://usuario:senha@localhost:5432/mentoria (pip install "psycopg[binary]")
		Estrutura: migrations/ (Flask-Migrate). O app aplica as migrações pendentes ao iniciar; banco novo é criado e
		marcado na versão atual. Depois de mudar models.py, gere a migração:
		    PULAR_ATUALIZACAO_BANCO=1 flask --app app db migrate -m "o que mudou"
		Trocar de motor numa instalação com dados: copiar_banco.py copia todas as tabelas e confere as quantidades.
		    python copiar_banco.py --de sqlite:///mentoria.db --para "mysql+pymysql://..."   (--substituir apaga o destino)
		Backup (Manutenção › DB): SQLite gera .db; MySQL gera .sql.gz pelo mysqldump (pacote mysql-client); PostgreSQL
		gera .dump pelo pg_dump (pacote postgresql-client). A senha vai num arquivo temporário, nunca na linha de comando.
		Um .db também restaura num MySQL ou PostgreSQL. No SQL Server o backup é do próprio servidor do banco (ou do Azure).
		Drivers opcionais: requirements-postgresql.txt (psycopg) e requirements-sqlserver.txt (pyodbc + ODBC Driver 18).
		Textos longos usam LONGTEXT no MySQL (o TEXT de lá guarda só 64 KB). Código: banco_config.py.

	🧭 Instalador e hospedagens (cada cliente escolhe a nuvem e o banco)
		python3 instalar.py pergunta a hospedagem, o banco, a conexão e as pastas de backup, grava o .env, cria o banco e
		a estrutura, copia os dados de um SQLite antigo (opcional) e cria os backups agendados padrão. Pode rodar de novo.
		Hospedagens (HOSPEDAGEM no .env) e o que funciona em cada uma:
		- Servidor próprio ou máquina virtual na AWS (EC2/Lightsail), GCP (Compute Engine) ou Azure: tudo funciona.
		- Contêiner (AWS App Runner/ECS, GCP Cloud Run, Azure App Service/Container Apps): banco gerenciado; arquivos e
		  backups só com volume montado; agentes e Orquestrador desligados; tarefas por agendador da nuvem.
		- PythonAnywhere: MySQL incluso (PostgreSQL pago, sem SQL Server); agentes OmniTest desligados (sem Chromium).
		Bancos por hospedagem: máquina virtual = MySQL, PostgreSQL, SQL Server ou SQLite; contêiner = MySQL, PostgreSQL ou
		SQL Server gerenciados; PythonAnywhere = MySQL, PostgreSQL ou SQLite.
		Pastas de backup padrão (BACKUP_DIR): máquina virtual /var/backups/mentoria; PythonAnywhere ~/backups/mentoria;
		contêiner /dados/backups (volume); computador instance/backups. Subpastas diario (guarda 7), semanal (4),
		mensal (12) e manuais. BACKUP_DIR_EXTERNO recebe uma segunda cópia de cada backup fora do servidor (disco de
		rede, volume da nuvem ou pasta do rclone), com a mesma retenção.
		Guias: deploy/ubuntu, deploy/aws, deploy/gcp, deploy/azure, deploy/pythonanywhere; imagem em deploy/conteiner/Dockerfile.
		Tela: Administração › Sistema › Ambiente e compatibilidade mostra a hospedagem, o banco, as pastas e cada recurso
		ligado, com atenção ou desligado (com o motivo e como ligar). As rotas dos agentes e o backup consultam a mesma
		verificação e se desligam sozinhos onde não funcionam. Código: ambiente.py e instalar.py.

	🐧 Instalação em servidor Ubuntu 24.04 (uma instalação por cliente)
		Arquivos prontos em deploy/ubuntu/ (systemd, nginx, tarefas de hora em hora e o modelo do .env).
		1. Pacotes (MySQL; para PostgreSQL troque por postgresql postgresql-client):
		    sudo apt update && sudo apt install -y python3-venv python3-dev build-essential git nginx mysql-server mysql-client
		2. Usuário do sistema, código e pasta de backups:
		    sudo adduser --system --group --home /srv/mentoria mentoria
		    sudo -u mentoria git clone <repositório> /srv/mentoria   (ou copie os arquivos)
		    cd /srv/mentoria && sudo -u mentoria python3 -m venv .venv
		    sudo -u mentoria .venv/bin/pip install -r requirements.txt
		    sudo mkdir -p /var/backups/mentoria && sudo chown mentoria: /var/backups/mentoria
		3. Instalador: sudo -u mentoria .venv/bin/python instalar.py
		   Escolha "Servidor próprio" (ou a máquina virtual da sua nuvem), o banco e "o banco fica neste mesmo servidor".
		   Ele grava o .env (só o dono lê) e o SQL que cria o banco e o usuário; rode o comando que ele mostrar
		   (ex.: sudo mysql -e "source /srv/mentoria/instance/criar_banco_mysql.sql"), apague o arquivo e rode o instalador de novo para criar a
		   estrutura e os backups agendados. Vindo de uma instalação SQLite (ex.: PythonAnywhere), informe o arquivo
		   mentoria.db quando ele perguntar e copie também a pasta uploads/.
		6. Serviços:
		    sudo cp deploy/ubuntu/mentoria.service deploy/ubuntu/mentoria-tarefas.* /etc/systemd/system/
		    sudo systemctl daemon-reload && sudo systemctl enable --now mentoria mentoria-tarefas.timer
		7. nginx e HTTPS: copie deploy/ubuntu/nginx-mentoria.conf para /etc/nginx/sites-available/mentoria, ajuste o
		   domínio, ative o site, sudo nginx -t && sudo systemctl reload nginx e depois sudo certbot --nginx -d <domínio>.
		8. Primeiro acesso: entre como Administrador e preencha Administração › Sistema › Identidade da instituição.
		Atualizar a versão: git pull, pip install -r requirements.txt, flask --app app db upgrade e
		sudo systemctl restart mentoria. Backups: o instalador cria Diário, Semanal e Mensal (Manutenção › DB para
		mudar); as tarefas de hora em hora executam. Configure BACKUP_DIR_EXTERNO para a cópia fora do servidor.

	5️⃣ Start da Aplicação
		Inicie o servidor Flask principal:
		python app.py
		Acesse a aplicação via navegador no endereço: http://127.0.0.1:5000

✨ Autor

Luis Kenji Ido – Mentor de Estudos e Arquiteto deste Software [03.09.2026]

	Versão do Python: 3.14.6
	Versão do Editor: Visual Studio Code 1.130.0

🛡️ Licença
	Este projeto é de uso educacional e profissional para gestão.