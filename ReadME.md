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
	- **Flask-SQLAlchemy** – ORM para o banco de dados SQLite.
	- **Bootstrap 5 & CSS3** – Interface visual moderna, responsiva e com alertas dinâmicos.
	- **Chart.js** – Renderização de gráficos para dashboards de indicadores.
	- **Werkzeug** – Gerenciamento e segurança no upload de arquivos físicos (Certificados e Materiais).
	- **Google Generative AI (Gemini)** – Motor de Inteligência Artificial para o assistente virtual de estudos.
	- **Google Calendar API** – Integração via OAuth2 para agendamento automatizado.

---

## 🧩 Estrutura do Projeto

mentoria/
	│
	├── app.py                # Cérebro da aplicação, rotas, integrações (IA/Agenda) e controle do sino de notificações
	├── models.py             # Estrutura do Banco de Dados (Usuário, Curso, Acompanhamento, Sessão e QADuvida)
	├── traducoes.py          # Dicionário de internacionalização (i18n) para PT, EN e ES
	├── client_secret.json    # Credenciais OAuth2 para integração com APIs do Google
	├── templates/            # Páginas e interfaces HTML (Jinja2)
	│   ├── index.html        # Página inicial (login, recuperação e motivação)
	│   ├── base.html         # Template base estrutural contendo o Sino de Notificações Inteligente
	│   ├── dashboard.html    # Painel Executivo e Matriz de Riscos
	│   ├── acompanhamento.html # Gestão de progresso, Assistente Gemini, Q&A, uploads e modais expandidos
	│   ├── sessoes.html      # Controle de encontros de mentoria
	│   ├── admin_usuarios.html # Governança de acessos, com suporte a múltiplos mentores e reset de segurança
	│   ├── admin_cursos.html # Catálogo de portfólio e auditoria
	│   ├── admin_banco.html  # Gestão administrativa do banco de dados, backups e auditoria
    │   ├── admin_solicitacoes.html # Gestão de solicitações de mentoria (Apenas Mentor Administrador)
	│   ├── cadastrar_perguntas.html # Configuração de segurança
	│   ├── perguntas_seguranca.html # Recuperação de senha baseada em perguntas
    │   └── trocar_senha.html # Interface de troca de senha obrigatória
	├── static/               # Arquivos estáticos globais (CSS, JS, Imagens)
	├── uploads/              # Diretório de armazenamento seguro de arquivos anexados
	├── atualizar_*.py        # Scripts de migração e atualização de tabelas do BD
	└── README.md             # Documentação oficial do projeto


🔐 Controle de Acesso e Perfis

O sistema opera sob rigorosa governança, segmentado em quatro grupos de permissão:

* Aluno: Visualiza seu próprio painel, atualiza % de progresso, anexa arquivos e altera status
básicos (Iniciado, Parado, Finalizado). Interage via Q&A, utiliza a IA de estudos e visualiza
(apenas leitura) o Parecer do Mentor.

* Mentor: Acompanha seus alunos, gerencia sessões e possui poder de alterar status
avançados (Pendente, Desistência) e gerenciar Prioridades. Possui acesso de edição ao
Parecer Oficial, respondendo ativamente aos alunos via Q&A.

* Mentor Administrador: Governança total do catálogo de cursos, recebe e aprova
solicitações de mentoria e acessa a visão executiva de todos os usuários. Visualização restrita da página de Solicitações.

* Administrador: Controle absoluto do sistema e da tabela core de usuários. Visualização restrita da página de Solicitações (não tem acesso).


🛡️ Política de Senhas e Segurança

* Exigência de complexidade: Mínimo de 10 caracteres contendo letra maiúscula,
minúscula, número e caractere especial.

* Validade e Expiração: Troca obrigatória a cada 90 dias (com avisos visuais integrados ao dashboard).

* Recuperação de Conta: Fluxo baseado em 3 perguntas de segurança customizáveis, exigindo no mínimo 2 acertos.

* Reset de Segurança: Administradores e Mentores Administradores podem forçar o recadastro das perguntas de segurança de um usuário,
garantindo a recuperação de contas.

* Criptografia: Irreversível no banco de dados.


🧮 Módulos e Funcionalidades Principais

📊 1. Dashboard Executivo e Indicadores

* Painel de 4 Cards: Exibe total de alunos, treinamentos finalizados com certificado,
finalizados sem certificado e acompanhamentos em risco.

* Matriz de Risco (Saúde do Aluno): Tabela visual dinâmica que classifica o andamento dos
estudos em Saudável (Verde), Em Atenção (Amarelo) ou Risco Crítico (Vermelho).

* Filtros de visualização: Visão individual (Aluno) vs. Visão Macro (Mentor/Admin).


🤖 2. Inovações e Integrações Inteligentes

* Assistente Gemini Notebook: Chat de Inteligência Artificial integrado capaz de gerar
simulados, revisar conceitos e analisar dúvidas do aluno baseado nas anotações do
estudo, utilizando dados de contexto via banco de dados (Grounding) de forma inteligente.

* Agenda Automática: Integração com o Google Calendar via OAuth2, permitindo que o
aluno bloqueie horários de estudo na própria agenda com apenas um clique.

* Multilíngue Dinâmico (i18n): Sistema totalmente traduzido e adaptável em tempo real
para Português (PT), Inglês (EN) e Espanhol (ES).

* Tematização Avançada: Arquitetura CSS responsiva com opções de temas visuais
(Claro, Escuro, Futurista e Vintage) sincronizados com todos os componentes da interface.

* Tour Interativo (Onboarding): Fluxo guiado para novos usuários utilizando `Intro.js`, contextualizado por perfil de acesso.


📚 3. Catálogo e Ciclo de Vida de Cursos

* Cadastro detalhado: Nome, Plataforma (ex: Microsoft Learn), URL, Carga Horária e exigência de certificado.

* Categorização: Segmentação estratégica em Hard Skills e Soft Skills.

* Auditoria de Criação: O sistema "carimba" ocultamente a Data de Inclusão e o Usuário
(Login) Criador.

* Desativação e Governança: Cursos obsoletos podem ter o status alterado para Desativado.
A desativação abre um painel de auditoria exigindo obrigatoriamente um Motivo, registrando
o autor e a data da ação.


🎯 4. Acompanhamento de Estudos (Core do Negócio)

* Gestão de Datas: Registro de Início, Término e Data Limite.

* Upload Duplo: Suporte para envio seguro tanto de Certificados quanto de Materiais de Apoio.

* Sistema de Q&A (Dúvidas e Respostas): Troca de mensagens bidirecional agrupada por curso,
com visualização em linha do tempo invertida (mensagem mais recente sempre no topo) para facilitar o suporte.

* Modais Expandidos (Anotações e Pareceres):
	* Alunos e Mentores podem utilizar Editores Expandidos (Modais Inteligentes em Tela Cheia via Bootstrap) para leitura/escrita confortável.
	* Formatação Preservada: Os modais respeitam quebras de linha (`white-space: pre-wrap`) garantindo visualização idêntica ao texto digitado.
	* Modais contam com rastreio automático do timestamp (Data e Hora) da última atualização.

* Notificações Inteligentes (Sino): Alertas dinâmicos no cabeçalho sobre novas
mensagens de Q&A e alertas do sistema. As notificações agrupam interações do mesmo curso, indicam os
autores das mensagens e realizam redirecionamento parametrizado (abrindo o pop-up
exato da interação automaticamente). A limpeza do sino ocorre via gatilho de leitura ao
consultar o curso.

⚖️ Regras de Negócio e Travas Sistêmicas

* Trava de Certificação: Se um curso exigir certificação, a barra de progresso não salva em
100% até que o arquivo físico do certificado seja anexado pelo aluno.

* Bloqueio de Matrícula Obsoleta: Impede que mentores vinculem alunos a cursos com status "Desativado".

* Cascata de Desativação (Trigger): Se um curso sai de linha, todos os alunos que estavam
com o status "Iniciado" ou "Parado" neste curso são automaticamente passados para
"Desativado". O sistema injeta uma nota automática de auditoria nas observações do
aluno justificando a mudança com base no motivo do mentor.

* Governança Multi-Mentor: Um aluno pode ter múltiplos mentores alocados via painel de usuários (através de checkboxes de seleção múltipla).

* Rotina de Backup em Background: O sistema executa um "Watcher" assíncrono capaz de realizar backups programados do banco de dados SQLite sem impactar a performance do portal.


🗓️ 5. Gestão de Sessões e Administração

* Módulo dedicado para agendamento, registro de pautas e acompanhamento de reuniões
de mentoria.

* Histórico de Feedback das sessões, agrupando comentários em linha do tempo.

* Interface administrativa robusta (CRUD) de usuários e redefinições de credenciais.

* Módulo de Manutenção de Banco de Dados para administração completa via painel.


⚙️ Instruções de Instalação e Execução

1️⃣ Preparação do Ambiente

Certifique-se de ter o Python instalado. Abra o terminal na raiz do projeto e crie o ambiente
virtual:
	Bash
	python -m venv venv
	Ative o ambiente:

	Windows: `venv\Scripts\activate`
	Linux/Mac: `source venv/bin/activate`

2️⃣ Instalação de Dependências

	Bash
	pip install flask flask-login flask-bcrypt flask-sqlalchemy werkzeug google-generativeai google-auth-oauthlib google-api-python-client

3️⃣ Configuração de APIs Externas

* Google Generative AI: Adicione sua API_KEY ou defina a variável de ambiente `GEMINI_API_KEY` para ativar o Gemini Notebook.
* Google Calendar: Insira o arquivo `client_secret.json` na raiz do projeto para habilitar a autenticação OAuth2 do calendário.

4️⃣ Sincronização do Banco de Dados (Migrações)

Como o projeto evoluiu estruturalmente, execute os scripts de atualização das tabelas na
ordem abaixo para aplicar as colunas de auditoria, históricos e relações de chat (Q&A).

	Bash
	python atualizar_tipo_curso.py
	python atualizar_status_curso.py
	python atualizar_data_curso.py
	python atualizar_criador_curso.py
	python atualizar_auditoria.py
	python atualizar.py

5️⃣ Start da Aplicação

	Inicie o servidor Flask principal:
	Bash
	python app.py
	Acesse a aplicação via navegador no endereço: http://127.0.0.1:5000

	
✨ Autor

	Luis Kenji Ido – Mentor de Estudos e Arquiteto deste Software [03.09.2026]

	Versão do Python: 3.14.6
	Versão do Editor: Visual Studio Code 1.130.0

🛡️ Licença
	Este projeto é de uso educacional e profissional para gestão.