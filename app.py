# Importações para Upload de Arquivos e Datas
import os
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename


# Importações do Flask
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, session, jsonify

# Importações do Google Calendar
from google_auth_oauthlib.flow import Flow
import os
import httplib2
import socks
import google_auth_httplib2

import google.oauth2.credentials
from googleapiclient.discovery import build
import datetime


# Configuração da Inteligência Artificial
# Substitua o texto abaixo pela chave enorme que você copiou no Passo 1
import os

from dotenv import load_dotenv

load_dotenv()

# As chamadas às IAs (Claude, Gemini e ChatGPT/OpenAI) ficam em provedores_ia.py: ordem de modelos por uso, reserva e teto de gasto.

# Isso permite testarmos o login do Google no nosso computador (localhost) sem HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Dizemos ao Google que só queremos criar/ver eventos na agenda
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
# O Google pode devolver também permissões já concedidas antes (Agenda + Gmail): isso não é erro
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

# Thread (Tarefa em Segundo Plano)
import threading
import secrets
import shutil
import time

# Importações de Segurança e Login (Aqui está o LoginManager que faltava!)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# Importações do Banco de Dados
from models import db, Usuario, Curso, Acompanhamento, SessaoMentoria, FeedbackSessao, QADuvida, HistoricoProgresso, aluno_mentor, HistoricoSenha, SegurancaUsuario, SolicitacaoMentoria, RegistroBackup, Projeto, Tarefa, Grupo, grupo_usuario, RegistroBackup, Projeto, Tarefa, Grupo, grupo_usuario, Frequencia, AvaliacaoProjeto, Empresa, Turma, turma_aluno, turma_mentor, turma_curso, CheckinAula
import os
import time

# Importações para Upload de Arquivos
import os
from werkzeug.utils import secure_filename


# Inicializando o aplicativo Flask (o "motor" do nosso site)
app = Flask(__name__)

# ---------------------------------------------------------
# IMPORTAÇÃO DO MÓDULO DE TRADUÇÕES
# ---------------------------------------------------------
from traducoes import t
from traducoes_literais import tt
import perfis_acesso
from notificacoes import notificar, usuarios_gestao, eh_conta_de_teste

# ---------------------------------------------------------
# INJETOR DE TRADUÇÃO PARA OS TEMPLATES (HTML)
# Torna a função 't' disponível globalmente em todas as páginas
# ---------------------------------------------------------
@app.context_processor
def utility_processor():
    def inject_traducao():
        # Verifica se o usuário está logado e pega o idioma dele, senão usa português ('pt')
        idioma_atual = current_user.idioma if current_user.is_authenticated else 'pt'
        # tt('Texto em português'): telas antigas traduzidas pelo próprio texto (traducoes_literais.py)
        return {'t': lambda chave: t(chave, idioma_atual), 'tt': lambda texto: tt(texto, idioma_atual)}
    return inject_traducao()

# =========================================================================
# PROCESSADOR DE CONTEXTO GLOBAL PARA AS NOTIFICAÇÕES DO SINO (Q&A + FEEDBACK)
# =========================================================================
# ==============================================================================
# REGRAS NOMEADAS — quem pode o quê e os números das regras de negócio
# ==============================================================================
# O Gerente de Funcionalidades aprende sozinho toda regra nomeada deste arquivo (constante em MAIÚSCULAS): quando
# uma muda, os agentes passam a esperar o novo comportamento. Regra escrita direto no meio do código fica invisível
# para ele; o Agente Dev (agentes_funcionalidades/varredura_regras.py) aponta esses casos em toda execução.
# Aluno, Gestor B2B (Admin B2B) e Avaliador da banca são perfis de escopo (veem só o que é deles) e podem ser
# comparados direto; todo PODER dado a um perfil usa uma regra PERFIS_* daqui. As PERFIS_* chegam também às telas.
PERFIS_VEEM_TODAS_DUVIDAS = ['Administrador', 'Mentor Administrador', 'Admin B2B']     # sino: dúvidas de todos os alunos
PERFIS_SEM_AVISOS_DA_EQUIPE = ['Aluno', 'Avaliador Banca']                             # sem avisos de bloqueio e sem aba de alertas
PERFIS_VEEM_TODOS_BLOQUEADOS = ['Administrador', 'Mentor Administrador']              # sino: todos os bloqueados (os outros, só os seus alunos)
PERFIS_GESTAO_DEMANDAS = ['Administrador', 'Mentor Administrador', 'Admin B2B']        # respondem e tratam o Portal de Demandas
PERFIS_VEEM_TODOS_JOVENS = ['Administrador', 'Mentor Administrador']                  # veem todos os jovens (LGPD: os outros, só os seus)
PERFIS_CRIAM_ADMINISTRADOR = ['Administrador']                                         # só eles cadastram ou promovem Administradores
PERFIS_VEEM_SO_SEUS_ALUNOS = ['Mentor', 'Professor']                                   # acompanhamento, sessões e avaliação só dos alunos vinculados
PERFIS_VEEM_SO_PROJETOS_DO_GRUPO = ['Aluno', 'Mentor']                                 # painel: só os projetos dos grupos de que fazem parte
PERFIS_GESTAO_CADASTROS = ['Administrador', 'Mentor Administrador']                   # usuários e grupos
PERFIS_ORIENTADORES = ['Mentor', 'Mentor Administrador', 'Professor']                 # podem ser vinculados ao aluno como mentor/professor(a)
PERFIS_EXCLUEM_PROJETO = ['Mentor', 'Mentor Administrador', 'Professor', 'Administrador']
PERFIS_EXCLUEM_ANEXO_TAREFA = ['Administrador', 'Mentor Administrador', 'Mentor']
PERFIS_EXCLUEM_MATERIAL_ACOMPANHAMENTO = ['Administrador', 'Mentor Administrador', 'Professor', 'Mentor']
PERFIS_VEEM_TODAS_SESSOES = ['Administrador', 'Mentor Administrador']
PERFIS_VEEM_TODAS_ATIVIDADES = ['Administrador', 'Mentor Administrador']              # atividades extras de todas as empresas
PERFIS_VEEM_RELATORIO_ATIVIDADE = ['Administrador', 'Mentor Administrador', 'Admin B2B']
PERFIS_EXPORTAM_ESG = ['Administrador', 'Mentor Administrador', 'Admin B2B']           # relatório ESG (Excel e PDF)
PERFIS_GESTAO_LOGOS = ['Administrador', 'Mentor Administrador']                       # logo de qualquer empresa (o Gestor B2B, só da sua)
PERFIS_GESTAO_TRILHA_TCC = ['Administrador', 'Mentor Administrador']
PERFIS_ADMINISTRACAO_SISTEMA = ['Administrador']                                       # parâmetros, perfis, banco, backups, identidade e agentes
PERFIS_USAM_ASSISTENTE = ['Administrador']                                             # Assistente da Plataforma (chat da base de conhecimento)
PERFIS_DECIDEM_SOLICITACOES = ['Mentor Administrador']                                 # aprova ou recusa os pedidos de mentoria
PERFIS_REGISTRAM_FREQUENCIA = ['Aluno', 'Mentor', 'Professor']                        # registro de presença diária obrigatório
PERFIS_GESTORES_DE_TURMA = ['Administrador', 'Admin B2B']                             # podem ser o gestor de uma turma
PERFIS_GESTAO_ENTREGAS_TCC = ['Administrador', 'Mentor Administrador']                # enviam a entrega por qualquer projeto
PERFIS_PUBLICAM_BANCAS = ['Administrador', 'Mentor Administrador']
PERFIS_EMITEM_CERTIFICADOS = ['Administrador', 'Mentor Administrador']                # emitem o certificado de qualquer pessoa

NOTA_MAXIMA = 10                          # notas de 0 a 10 (projeto, diário e banca)
AVALIACAO_NOTA_MINIMA, AVALIACAO_NOTA_MAXIMA = 1, 5     # avaliações e feedbacks de 1 a 5 estrelas
MINIMO_CARACTERES_DESCRICAO = 10          # motivo, descrição, resumo e resolução obrigatórios
MINIMO_CARACTERES_COMENTARIO = 3
MINIMO_CARACTERES_TITULO = 3
MINIMO_CARACTERES_MOTIVO_REMARCACAO = 5   # remarcar a banca
DURACAO_MINIMA_ATIVIDADE_MIN = 10         # atividade extra
DURACAO_MINIMA_REUNIAO_MIN = 5
DURACAO_MAXIMA_EVENTO_MIN = 12 * 60       # atividade extra e reunião
CICLO_AVALIACAO_MAXIMO_DIAS = 90
RETENCAO_BACKUP_MAXIMA = 365              # cópias guardadas por agendamento de backup


# Quem responde às dúvidas do Q&A do Acompanhamento e recebe o aviso no sino (só dos próprios alunos)
PERFIS_DUVIDAS_ACOMPANHAMENTO = ['Professor']
# Nome de cada papel nas telas: {tela: {nome certo: [outros nomes que a tela NÃO usa para esse papel]}}. O Agente UX
# (agentes_funcionalidades/varredura_ux.py) confere o texto da tela, do tt() e do t(); mudar aqui muda o que ele espera.
NOME_DO_PAPEL_NAS_TELAS = {'acompanhamento.html': {'Professor(a)': ['Mentor', 'Mentora', 'Mentores', 'Mentoras', 'Mentor(a)']}}


@app.context_processor
def injetar_notificacoes_qa():
    if not current_user.is_authenticated:
        return dict(novas_mensagens_count=0, notificacoes_qa=[])
    
    notificacoes_formatadas = []
    so_plataforma = current_user.tipo_usuario == 'Avaliador Banca'

    # --- 1. BUSCA NOTIFICAÇÕES DE Q&A (ACOMPANHAMENTO) ---
    if so_plataforma:
        notifs_qa = []
    elif current_user.tipo_usuario == 'Aluno':
        notifs_qa = QADuvida.query.join(Acompanhamento).filter(
            QADuvida.lida_pelo_aluno == False,
            Acompanhamento.aluno_id == current_user.id
        ).all()
    elif current_user.tipo_usuario in PERFIS_DUVIDAS_ACOMPANHAMENTO:
        # Dúvidas do Acompanhamento vão para o professor(a) do aluno (não para o mentor)
        notifs_qa = QADuvida.query.join(Acompanhamento).join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(
            QADuvida.lida_pelo_mentor == False,
            Usuario.mentores.any(id=current_user.id)
        ).all()
    elif current_user.tipo_usuario in PERFIS_VEEM_TODAS_DUVIDAS:
        notifs_qa = QADuvida.query.filter_by(lida_pelo_mentor=False).all()
    else:
        notifs_qa = []  # Mentor e demais perfis não recebem as dúvidas do Acompanhamento

    acomp_processados = set()
    for n in notifs_qa:
        if n.acompanhamento_id not in acomp_processados:
            acomp_processados.add(n.acompanhamento_id)
            acomp = db.session.get(Acompanhamento, n.acompanhamento_id)
            curso = db.session.get(Curso, acomp.curso_id) if acomp else None
            autor_nome = n.autor.nome.split()[0] if n.autor else 'Usuário'
            curso_nome = curso.nome_curso if curso else 'Curso'
            
            if current_user.tipo_usuario == 'Aluno':
                texto = f"💬 Resposta em {curso_nome[:15]}..."
            else:
                texto = f"❓ {autor_nome} enviou dúvida..."
                
            notificacoes_formatadas.append({
                'link': url_for('acompanhamento', abrir_modal=n.acompanhamento_id),
                'texto': texto,
                'data': n.data_criacao
            })

    # --- 2. BUSCA NOTIFICAÇÕES DE FEEDBACK (SESSÕES) ---
    if so_plataforma:
        notifs_fb = []
    elif current_user.tipo_usuario == 'Aluno':
        notifs_fb = FeedbackSessao.query.join(SessaoMentoria).filter(
            FeedbackSessao.lida_pelo_aluno == False,
            SessaoMentoria.aluno_id == current_user.id
        ).all()
    else:
        notifs_fb = FeedbackSessao.query.filter_by(lida_pelo_mentor=False).all()

    sessoes_processadas = set()
    for f in notifs_fb:
        if f.sessao_id not in sessoes_processadas:
            sessoes_processadas.add(f.sessao_id)
            autor_nome = f.autor.nome.split()[0] if f.autor else 'Usuário'
            
            notificacoes_formatadas.append({
                'link': url_for('sessoes', abrir_modal=f.sessao_id),
                'texto': f"⭐ Novo feedback de {autor_nome}",
                'data': f.data_envio
            })

    # 3. BUSCA ALUNOS BLOQUEADOS (SINO DE ADMINS E MENTORES)
    if current_user.tipo_usuario not in PERFIS_SEM_AVISOS_DA_EQUIPE:
        if current_user.tipo_usuario in PERFIS_VEEM_TODOS_BLOQUEADOS:
            alunos_bloqueados = Usuario.query.filter_by(status='Bloqueado').all()
        else:
            alunos_bloqueados = Usuario.query.filter(Usuario.status == 'Bloqueado', Usuario.mentores.any(id=current_user.id)).all()

        for ab in alunos_bloqueados:
            notificacoes_formatadas.append({
                'link': url_for('gerenciar_usuarios'),
                'texto': f"⚠️ BLOQUEADO (Senha): {ab.nome.split()[0]}",
                'data': datetime.now() # Data atual para forçar o aviso a ficar no topo do sino
            })

    # 5. NOTIFICAÇÕES DA PLATAFORMA (demandas, reuniões, bancas, lembretes...)
    from models import Notificacao
    for n in Notificacao.query.filter_by(usuario_id=current_user.id, lida=False).order_by(Notificacao.data_criacao.desc()).limit(10).all():
        notificacoes_formatadas.append({
            'link': url_for('abrir_notificacao', id=n.id),
            'texto': f"🔔 {n.titulo}",
            'data': n.data_criacao
        })


    # 4. TICKETS DO PORTAL DE DEMANDAS AGUARDANDO RESPOSTA (só gestão)
    if current_user.tipo_usuario in PERFIS_GESTAO_DEMANDAS:
        from models import DemandaInstitucional
        abertas = DemandaInstitucional.query.filter_by(status='Aberta').order_by(DemandaInstitucional.data_criacao.desc()).all()
        if abertas:
            notificacoes_formatadas.append({
                'link': url_for('portal_demandas'),
                'texto': f"🎫 {len(abertas)} {t('notif_tickets_abertos', current_user.idioma)}",
                'data': abertas[0].data_criacao
            })

    # Mistura tudo e ordena pela data mais recente
    notificacoes_formatadas.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)
    
    return dict(
        novas_mensagens_count=len(notificacoes_formatadas), 
        notificacoes_qa=notificacoes_formatadas[:5] # Retorna as 5 mais recentes
    )


# ===========================================================================
# CONFIGURAÇÕES DE SEGURANÇA E BANCO DE DADOS
# ===========================================================================
# SECRET_KEY (variável de ambiente ou instance/.secret_key), cookies, CSRF, cabeçalhos, limite de requisições
# e de upload: tudo em seguranca_web.py (achados dos Agentes de Segurança)
import seguranca_web
from seguranca_web import voltar
seguranca_web.configurar_seguranca(
    app, lambda texto: tt(texto, current_user.idioma if current_user.is_authenticated else session.get('idioma', 'pt')))
# Banco de dados: DATABASE_URL (arquivo .env ou variável de ambiente) escolhe o motor, sem mudar o código.
#   SQLite (padrão, desenvolvimento):  sqlite:///mentoria.db  (arquivo em instance/)
#   MySQL / MariaDB:                   mysql+pymysql://usuario:senha@localhost:3306/mentoria?charset=utf8mb4
#   PostgreSQL:                        postgresql+psycopg://usuario:senha@localhost:5432/mentoria
# Detalhes em banco_config.py e no guia de instalação (ReadME.md › Instalação em servidor Ubuntu).
import banco_config
app.config['SQLALCHEMY_DATABASE_URI'] = banco_config.endereco_do_banco()
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = banco_config.opcoes_do_motor(app.config['SQLALCHEMY_DATABASE_URI'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ===========================================================================
# INICIALIZANDO AS EXTENSÕES
# ===========================================================================
db.init_app(app)
# Versões da estrutura do banco (Flask-Migrate / Alembic): migrations/. render_as_batch deixa o SQLite alterar colunas.
from flask_migrate import Migrate
migrate = Migrate(app, db, directory=os.path.join(app.root_path, 'migrations'), render_as_batch=True)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app) 

login_manager.login_view = 'login' 
login_manager.login_message = "Por favor, faça login para acessar esta página."

# ===========================================================================
# FUNÇÃO DE CARREGAMENTO DE USUÁRIO
# ===========================================================================
@login_manager.user_loader
def load_user(user_id):
    # Formato "id:token". Sessões antigas (só o id) ou de antes de um logout deixam de valer.
    id_texto, _, token = str(user_id).partition(':')
    if not id_texto.isdigit() or not token:
        return None
    usuario = db.session.get(Usuario, int(id_texto))
    if usuario and usuario.token_sessao and secrets.compare_digest(usuario.token_sessao, token):
        return usuario
    return None

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

# ===========================================================================
# ROTAS (PÁGINAS DO SISTEMA)
# ===========================================================================

# Rota de Login (Página Inicial)
# ===========================================================================
# ESCOPO DE VISIBILIDADE DOS JOVENS POR PERFIL (usado em painéis e listas)
# ===========================================================================
def ids_jovens_visiveis(usuario):
    """None = todos os jovens (Administrador e Mentor Administrador).
    Nos demais perfis, devolve o conjunto de ids dos jovens que a pessoa acompanha."""
    if usuario.tipo_usuario in PERFIS_VEEM_TODOS_JOVENS:
        return None
    if usuario.tipo_usuario == 'Aluno':
        return {usuario.id}
    if usuario.tipo_usuario == 'Admin B2B':
        linhas = db.session.query(turma_aluno.c.aluno_id) \
            .join(Turma, Turma.id == turma_aluno.c.turma_id) \
            .join(Empresa, Empresa.id == Turma.empresa_id) \
            .filter(Empresa.gestor_id == usuario.id).all()
        return {linha[0] for linha in linhas}
    # Mentor, Professor e demais: jovens vinculados a ele + jovens dos grupos de que participa
    vinculados = {a.id for a in Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=usuario.id)).all()}
    dos_grupos = {m.id for g in (getattr(usuario, 'grupos', None) or []) for m in g.membros if m.tipo_usuario == 'Aluno'}
    return vinculados | dos_grupos


def conta_de_teste_bloqueada(email):
    """Em produção (PythonAnywhere), as contas dos agentes de teste (*_ominitest@local.com e @local.com) não fazem login.
    Para rodar os agentes num ambiente de produção seu, defina OMNITEST_PERMITIR_EM_PRODUCAO=1."""
    if not seguranca_web.EM_PRODUCAO:
        return False
    import credenciais_agentes
    credenciais_agentes.carregar(app.config['SECRET_KEY'])  # a liberação pode ter sido feita na área Agentes IA
    if os.environ.get('OMNITEST_PERMITIR_EM_PRODUCAO') == '1':
        return False
    return (email or '').lower().endswith(('_ominitest@local.com', '@local.com'))


ENDPOINTS_LIVRES_TROCA_SENHA = {'trocar_senha_obrigatoria', 'logout', 'static', 'login', 'alterar_tema', 'alterar_idioma'}


@app.before_request
def exigir_troca_de_senha():
    """Troca de senha obrigatória vale para todas as páginas (não só para a tela de login): quem tem a troca pendente —
    senha provisória criada pela gestão ou recuperação de senha aprovada — só usa a plataforma depois de trocar."""
    if current_user.is_authenticated and getattr(current_user, 'forcar_troca_senha', False) \
            and request.endpoint and request.endpoint not in ENDPOINTS_LIVRES_TROCA_SENHA:
        if request.is_json or request.method != 'GET':
            return jsonify({'erro': tt('Troque a sua senha antes de continuar.', current_user.idioma)}), 403
        return redirect(url_for('trocar_senha_obrigatoria'))


# Política de senha forte: o tamanho mínimo vem de Administração › Parâmetros de regras (senha_min_caracteres)
from regras_negocio import padrao_senha_forte, regra
PADRAO_EMAIL = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
PERFIS_GESTAO_PROJETO = ['Administrador', 'Mentor Administrador']


def gerar_senha_provisoria():
    """Senha aleatória que atende à política (tamanho mínimo parametrizado, com maiúscula, minúscula, número e especial)."""
    import string
    gerador = secrets.SystemRandom()
    restante = max(10, int(regra('senha_min_caracteres')))  # 4 obrigatórios + restante: sempre acima do mínimo
    partes = [gerador.choice(string.ascii_uppercase), gerador.choice(string.ascii_lowercase), gerador.choice(string.digits),
              gerador.choice('#@!%&*')] + [gerador.choice(string.ascii_letters + string.digits) for _ in range(restante)]
    gerador.shuffle(partes)
    return ''.join(partes)


def pode_atribuir_nivel(usuario_logado, tipo_usuario):
    """Só o Administrador cria, promove ou altera Administradores (evita escalada de privilégio pelo Mentor Administrador)."""
    return tipo_usuario != 'Administrador' or usuario_logado.tipo_usuario in PERFIS_CRIAM_ADMINISTRADOR  # regra-nomeada: ok (o perfil-alvo é dado, não poder)


def pode_mexer_no_projeto(usuario, projeto):
    """Tarefas e exclusão do projeto: membros do grupo do projeto e a gestão (nunca outro grupo)."""
    return projeto is not None and (usuario.tipo_usuario in PERFIS_GESTAO_PROJETO or usuario in membros_do_projeto(projeto))


@app.route('/', methods=['GET', 'POST'])
def login():
    # ==============================================================================
    # 1. CUIDA DE QUEM JÁ ESTAVA LOGADO (Sessão salva no navegador)
    # ==============================================================================
    if current_user.is_authenticated:
        # Força trocar a senha se estiver pendente
        if getattr(current_user, 'forcar_troca_senha', False):
            return redirect(url_for('trocar_senha_obrigatoria'))
        
        # Força cadastrar as perguntas se nunca tiver feito
        tem_perguntas = SegurancaUsuario.query.filter_by(usuario_id=current_user.id).first()
        if not tem_perguntas:
            return redirect(url_for('cadastrar_perguntas'))
            
        # Tudo certo, vai pro painel
        return redirect(url_for('dashboard'))

    # ==============================================================================
    # 2. CUIDA DE QUEM ESTÁ DIGITANDO E-MAIL E SENHA AGORA
    # ==============================================================================
    if request.method == 'POST':
        email_digitado = request.form.get('email')
        senha_digitada = request.form.get('senha')
        usuario = Usuario.query.filter_by(email=email_digitado).first()

        if usuario and conta_de_teste_bloqueada(usuario.email):
            usuario = None  # em produção, as contas dos agentes de teste não entram

        if usuario:
            # Trava o usuário se ele estiver bloqueado pelas 5 tentativas
            if usuario.status == 'Bloqueado':
                flash('Sua conta foi bloqueada por excesso de tentativas falhas. Procure a Administração.', 'danger')
                return render_template('index.html')
            if usuario.status == 'Desistente':
                flash('Sua participação no programa foi encerrada. Para voltar, procure a coordenação.', 'warning')
                return render_template('index.html')

            # Se a senha estiver correta
            if bcrypt.check_password_hash(usuario.senha, senha_digitada):
                # Zera as falhas e loga o usuário
                usuario.tentativas_login = 0
                usuario.ultimo_acesso = datetime.now()
                db.session.commit()
                login_user(usuario)
                
                # Regra A: Força troca de senha
                if getattr(usuario, 'forcar_troca_senha', False):
                    flash('Por medida de segurança, defina uma nova senha definitiva.', 'warning')
                    return redirect(url_for('trocar_senha_obrigatoria'))
                
                # Regra B: Força cadastrar as perguntas de segurança
                tem_perguntas = SegurancaUsuario.query.filter_by(usuario_id=usuario.id).first()
                if not tem_perguntas:
                    flash('Ação Necessária: Configure suas 3 perguntas de recuperação de conta.', 'info')
                    return redirect(url_for('cadastrar_perguntas'))

                # Passou por todas as regras, vai pro painel
                return redirect(url_for('dashboard'))
            
            # Se a senha estiver errada
            else:
                usuario.tentativas_login = (usuario.tentativas_login or 0) + 1
                limite_tentativas = int(regra('login_tentativas_bloqueio'))
                if usuario.tentativas_login >= limite_tentativas:
                    usuario.status = 'Bloqueado'
                    flash(f'Conta bloqueada após {limite_tentativas} tentativas incorretas.', 'danger')
                else:
                    # Mensagem idêntica à de e-mail inexistente (não revela quais e-mails existem)
                    flash('E-mail ou senha incorretos.', 'danger')
                    app.logger.info(f"Login: senha incorreta para o usuário {usuario.id} (tentativa {usuario.tentativas_login} de {limite_tentativas})")
                
                db.session.add(usuario)
                db.session.commit()
        else:
            flash('E-mail ou senha incorretos.', 'danger')

    return render_template('index.html')


# ---------------------------------------------------------
# Nova Rota: Troca de Senha Obrigatória
# ---------------------------------------------------------
@app.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha_obrigatoria():
    if not getattr(current_user, 'forcar_troca_senha', False):
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha')
        padrao_senha = padrao_senha_forte()
        
        if not re.match(padrao_senha, nova_senha):
            flash(f"Segurança: A nova senha deve ter no mínimo {regra('senha_min_caracteres')} caracteres (maiúsculas, minúsculas, números e especiais).", "danger")
            return render_template('trocar_senha.html')

        historico_senhas = HistoricoSenha.query.filter_by(usuario_id=current_user.id).order_by(HistoricoSenha.data_registro.desc()).limit(10).all()
        for historico in historico_senhas:
            if bcrypt.check_password_hash(historico.senha_hash, nova_senha):
                flash("Segurança: Você não pode reutilizar uma das suas últimas 10 senhas.", "danger")
                return render_template('trocar_senha.html')
                
        nova_senha_hash = bcrypt.generate_password_hash(nova_senha).decode('utf-8')
        current_user.senha = nova_senha_hash
        current_user.data_ultima_troca_senha = datetime.utcnow()
        current_user.forcar_troca_senha = False
        
        novo_registro = HistoricoSenha(usuario_id=current_user.id, senha_hash=nova_senha_hash)
        db.session.add(novo_registro)
        db.session.commit()
        
        # --- A MÁGICA ACONTECE AQUI ---
        # Verifica se as perguntas já foram cadastradas antes de mandar para o Dashboard
        tem_perguntas = SegurancaUsuario.query.filter_by(usuario_id=current_user.id).first()
        if not tem_perguntas:
            flash("Senha atualizada! Agora é obrigatório configurar suas 3 perguntas de recuperação.", "info")
            return redirect(url_for('cadastrar_perguntas'))
            
        flash("Senha atualizada com sucesso! Bem-vindo(a).", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('trocar_senha.html')

# ---------------------------------------------------------
# ROTA PARA DESATIVAR O TOUR DE BOAS-VINDAS
# ---------------------------------------------------------
@app.route('/desativar-tour', methods=['POST'])
@login_required
def desativar_tour():
    current_user.exibir_tour = False
    db.session.commit()
    return {"status": "sucesso"}



# ---------------------------------------------------------
# Rota do Painel Interno (Dashboard e Indicadores)
# ---------------------------------------------------------
from datetime import datetime
import re
import json

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.tipo_usuario == 'Avaliador Banca':
        return redirect(url_for('minhas_bancas'))

    nome_do_mentor = "Não atribuído"
    if current_user.tipo_usuario == 'Aluno':
        if hasattr(current_user, 'mentores'):
            mentores_aluno = current_user.mentores.all() if hasattr(current_user.mentores, 'all') else current_user.mentores
            if mentores_aluno:
                nome_do_mentor = " e ".join([m.nome for m in mentores_aluno])
        else:
            sessao = SessaoMentoria.query.filter_by(aluno_id=current_user.id).first()
            if sessao:
                mentor = Usuario.query.get(sessao.mentor_id)
                if mentor:
                    nome_do_mentor = mentor.nome

    DIAS_EXPIRACAO_SENHA = int(regra('senha_dias_expiracao'))
    if current_user.data_ultima_troca_senha:
        dias_desde_ultima_troca = (datetime.utcnow() - current_user.data_ultima_troca_senha).days
        dias_restantes_senha = max(0, DIAS_EXPIRACAO_SENHA - dias_desde_ultima_troca)
    else:
        dias_restantes_senha = DIAS_EXPIRACAO_SENHA

    total_alunos = 0
    total_matriculas = 0
    total_alunos_sistema = 0
    total_sessoes = 0
    total_finalizados = 0
    finalizados_com_certificado = 0
    finalizados_sem_certificado = 0
    matrizes_analise = []
    contador_saudavel = 0
    contador_atencao = 0
    contador_risco = 0

    evolucao_labels = []
    evolucao_horas = []
    evolucao_cursos = []
    radar_labels = []
    radar_valores = []

    if current_user.tipo_usuario == 'Aluno':
        acompanhamentos = Acompanhamento.query.filter_by(aluno_id=current_user.id).all()
        total_sessoes = SessaoMentoria.query.filter_by(aluno_id=current_user.id).count()
    elif current_user.tipo_usuario in PERFIS_VEEM_SO_SEUS_ALUNOS:
        # Filtra os acompanhamentos e totalizadores apenas para os alunos deste mentor
        acompanhamentos = Acompanhamento.query.join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(Usuario.mentores.any(id=current_user.id)).all()
        total_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).count()
        total_sessoes = SessaoMentoria.query.filter_by(mentor_id=current_user.id).count()
    elif current_user.tipo_usuario == 'Admin B2B':
        # Gestor B2B: só os jovens das turmas das empresas que ele gere (LGPD)
        ids_b2b = list(ids_jovens_visiveis(current_user)) or [-1]
        acompanhamentos = Acompanhamento.query.filter(Acompanhamento.aluno_id.in_(ids_b2b)).order_by(Acompanhamento.id.desc()).all()
        total_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.id.in_(ids_b2b)).count()
        total_sessoes = SessaoMentoria.query.filter(SessaoMentoria.aluno_id.in_(ids_b2b)).count()
    else:
        # Administrador e Mentor Administrador veem tudo
        acompanhamentos = Acompanhamento.query.order_by(Acompanhamento.id.desc()).all()
        total_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').count()
        total_sessoes = SessaoMentoria.query.count()


    total_alunos_sistema = total_alunos
    total_matriculas = len(acompanhamentos)

    dict_evolucao = {}
    dict_radar = {}
    agora_painel = datetime.now()
    # Histórico de progresso de todas as matrículas visíveis numa consulta só (não uma por matrícula)
    historico_por_acomp = {}
    ids_acomp = [a.id for a in acompanhamentos]
    for lote in range(0, len(ids_acomp), 500):
        for h in HistoricoProgresso.query.filter(HistoricoProgresso.acompanhamento_id.in_(ids_acomp[lote:lote + 500])) \
                .order_by(HistoricoProgresso.data_registro, HistoricoProgresso.id).all():
            historico_por_acomp.setdefault(h.acompanhamento_id, []).append(h)

    def mes_do(quando):
        chave = (quando or agora_painel).strftime('%m/%Y')
        return dict_evolucao.setdefault(chave, {'horas': 0, 'iniciados': 0, 'cursos_finalizados': 0})
    # Dados extras para os gráficos personalizáveis do painel
    contagem_status, carga_por_tipo, progresso_por_aluno, progresso_por_curso = {}, {}, {}, {}

    for a in acompanhamentos:
        curso = getattr(a, 'curso', None) or Curso.query.get(a.curso_id)
        aluno = getattr(a, 'aluno', None) or Usuario.query.get(a.aluno_id)

        if not curso or not aluno:
            continue

        percentual = a.percentual_conclusao or 0

        if a.status == 'Finalizado':
            total_finalizados += 1
            tem_certificado = getattr(a, 'certificado_anexado', False) or getattr(a, 'certificado', False)
            if tem_certificado:
                finalizados_com_certificado += 1
            else:
                finalizados_sem_certificado += 1

        risco = "Em Atenção"
        if a.status == 'Finalizado':
            risco = "Saudável"
            contador_saudavel += 1
        elif a.status == 'Parado':
            risco = "Risco"
            contador_risco += 1
        elif a.status == 'Iniciado':
            if percentual > 0:
                risco = "Saudável"
                contador_saudavel += 1
            else:
                risco = "Em Atenção"
                contador_atencao += 1
        else:
            risco = "Desativado"

        if a.status not in ['Finalizado', 'Desativado']:
            prazo_str = "Sem prazo definido"
            if hasattr(a, 'data_termino') and a.data_termino:
                prazo_str = a.data_termino.strftime('%d/%m/%Y')
            
            matrizes_analise.append({
                'aluno': aluno.nome,
                'curso': curso.nome_curso,
                'url': curso.url,  # <--- ADICIONE ESTA LINHA PARA O LINK FUNCIONAR!
                'carga_horaria': curso.carga_horaria or 0,
                'percentual': percentual,
                'prazo': prazo_str,
                'status': a.status,
                'risco': risco
            })

        # Linha do Tempo de Aprendizado, mês a mês:
        # - horas estudadas = carga horária × o que o progresso avançou naquele mês (histórico de progresso);
        #   o avanço sem histórico (registros antigos) entra no mês de início;
        # - cursos iniciados = matrículas pelo mês de início; cursos concluídos = pelo mês em que chegou a 100%.
        carga = curso.carga_horaria or 0
        historico = historico_por_acomp.get(a.id, [])
        inicio = a.data_inicio or (historico[0].data_registro if historico else None) or agora_painel
        mes_do(inicio)['iniciados'] += 1
        alcancado, concluido_em = 0, None
        for h in historico:
            if (h.percentual or 0) > alcancado:
                mes_do(h.data_registro or inicio)['horas'] += carga * ((h.percentual or 0) - alcancado) / 100
                alcancado = h.percentual or 0
            if (h.percentual or 0) >= 100 and concluido_em is None:
                concluido_em = h.data_registro
        if percentual > alcancado:
            mes_do(inicio)['horas'] += carga * (percentual - alcancado) / 100
        if a.status == 'Finalizado':
            mes_do(concluido_em or a.data_termino or inicio)['cursos_finalizados'] += 1

        tipo_curso = getattr(curso, 'tipo', 'Outro')
        if tipo_curso not in dict_radar:
            dict_radar[tipo_curso] = {'soma_progresso': 0, 'qtd': 0}
        
        dict_radar[tipo_curso]['soma_progresso'] += percentual
        dict_radar[tipo_curso]['qtd'] += 1

        contagem_status[a.status or 'Iniciado'] = contagem_status.get(a.status or 'Iniciado', 0) + 1
        carga_por_tipo[tipo_curso] = carga_por_tipo.get(tipo_curso, 0) + (curso.carga_horaria or 0)
        soma_aluno = progresso_por_aluno.setdefault(aluno.nome, [0, 0])
        soma_aluno[0] += percentual
        soma_aluno[1] += 1
        progresso_por_curso[curso.nome_curso] = percentual

    try:
        meses_ordenados = sorted(dict_evolucao.keys(), key=lambda x: datetime.strptime(x, '%m/%Y'))
    except (ValueError, TypeError):
        meses_ordenados = list(dict_evolucao.keys())

    evolucao_iniciados = []
    for mes in meses_ordenados:
        evolucao_labels.append(mes)
        evolucao_horas.append(round(dict_evolucao[mes]['horas'], 1))
        evolucao_iniciados.append(dict_evolucao[mes]['iniciados'])
        evolucao_cursos.append(dict_evolucao[mes]['cursos_finalizados'])

    for tipo, dados in dict_radar.items():
        radar_labels.append(tipo)
        media = round(dados['soma_progresso'] / dados['qtd'], 1) if dados['qtd'] > 0 else 0
        radar_valores.append(media)

    # ==============================================================================
    # INDICADORES DE PROJETOS PARA O DASHBOARD
    # ==============================================================================
    if current_user.tipo_usuario in PERFIS_VEEM_SO_PROJETOS_DO_GRUPO:
        meus_projetos = Projeto.query.join(Grupo).filter(Grupo.membros.any(id=current_user.id)).all()
    else:
        meus_projetos = Projeto.query.order_by(Projeto.id.desc()).all()

    total_projetos = len(meus_projetos)

    projetos_andamento = sum(1 for p in meus_projetos if p.status == 'Em Andamento')
    projetos_concluidos = sum(1 for p in meus_projetos if p.status == 'Concluído')

    # Jovens que registraram presença Online hoje (no escopo de quem está vendo)
    jovens_online_hoje = None
    jovens_online_cadastro = None
    if current_user.tipo_usuario != 'Aluno':
        inicio_hoje = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        consulta_online = Frequencia.query.join(Usuario, Usuario.id == Frequencia.usuario_id).filter(
            Usuario.tipo_usuario == 'Aluno', Frequencia.tipo_presenca == 'Online', Frequencia.data_registro >= inicio_hoje)
        consulta_cadastro = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.status == 'Ativo',
                                                 Usuario.modalidade_participacao.in_(['Online', 'Híbrido']))
        visiveis = ids_jovens_visiveis(current_user)
        if visiveis is not None:
            consulta_online = consulta_online.filter(Frequencia.usuario_id.in_(list(visiveis)))
            consulta_cadastro = consulta_cadastro.filter(Usuario.id.in_(list(visiveis)))
        jovens_online_hoje = consulta_online.count()
        jovens_online_cadastro = consulta_cadastro.count()

    # Relógio de voluntariado: opções de grupo/TCC e o histórico "Minhas horas"
    contexto_voluntariado = {}
    if current_user.tipo_usuario != 'Aluno':
        from models import CheckinVoluntariado
        minhas_horas = CheckinVoluntariado.query.filter_by(usuario_id=current_user.id) \
            .order_by(CheckinVoluntariado.data_hora_inicio.desc()).limit(30).all()
        concluidos = CheckinVoluntariado.query.filter(CheckinVoluntariado.usuario_id == current_user.id,
                                                      CheckinVoluntariado.data_hora_fim.isnot(None)).all()
        contexto_voluntariado = dict(
            tipos_voluntariado=TIPOS_ATIVIDADE_VOLUNTARIADO,
            grupos_voluntariado=grupos_do_usuario(current_user),
            projetos_voluntariado=projetos_do_usuario(current_user),
            minhas_horas=minhas_horas,
            minutos_regulares=sum((c.total_minutos or 0) for c in concluidos if (c.categoria or classificar_categoria(c.tipo_atividade)) == 'Regular'),
            minutos_extras=sum((c.total_minutos or 0) for c in concluidos if (c.categoria or classificar_categoria(c.tipo_atividade)) == 'Extra'),
        )

    # Atividade extra do grupo acontecendo agora (janela: 30 min antes até 1 h depois do fim previsto)
    agora_local = datetime.now()
    atividades_agora = [a for a in atividades_extras_visiveis(current_user)
                        if a.status in ['Agendada', 'Em andamento'] and pode_registrar_presenca(current_user, a)
                        and a.data_hora_inicio_prevista - timedelta(minutes=30) <= agora_local <= a.fim_previsto + timedelta(hours=1)]
    minhas_presencas_agora = {p.atividade_id: p for a in atividades_agora for p in a.presencas if p.usuario_id == current_user.id}

    encaminhamentos_vencidos = encaminhamentos_atrasados(current_user) if current_user.tipo_usuario != 'Aluno' else []

    from models import Banca
    ids_meus_grupos = [g.id for g in (getattr(current_user, 'grupos', None) or [])] or [-1]
    minhas_bancas_grupo = Banca.query.join(Projeto, Projeto.id == Banca.projeto_id).filter(
        Projeto.grupo_id.in_(ids_meus_grupos), Banca.status.in_(['Agendada', 'Remarcada']),
        Banca.data_hora >= datetime.now() - timedelta(hours=3)).order_by(Banca.data_hora).all()

    fontes_graficos = montar_fontes_painel(current_user, current_user.idioma, {
        'evolucao_labels': evolucao_labels, 'evolucao_horas': evolucao_horas, 'evolucao_cursos': evolucao_cursos,
        'evolucao_iniciados': evolucao_iniciados,
        'radar_labels': radar_labels, 'radar_valores': radar_valores, 'contagem_status': contagem_status,
        'saudavel': contador_saudavel, 'atencao': contador_atencao, 'risco': contador_risco,
        'com_certificado': finalizados_com_certificado, 'sem_certificado': finalizados_sem_certificado,
        'carga_por_tipo': carga_por_tipo, 'progresso_por_aluno': progresso_por_aluno, 'progresso_por_curso': progresso_por_curso,
        'projetos_andamento': projetos_andamento, 'projetos_concluidos': projetos_concluidos})

    return render_template('dashboard.html',
                           fontes_graficos=fontes_graficos,
                           graficos_painel=graficos_do_usuario(current_user, fontes_graficos),
                           graficos_padrao=graficos_padrao_painel(),
                           tipos_grafico_simples=TIPOS_GRAFICO_SIMPLES, tipos_grafico_multi=TIPOS_GRAFICO_MULTI,
                           max_graficos=MAX_GRAFICOS_PAINEL,
                           encaminhamentos_vencidos=encaminhamentos_vencidos, ocorrencias_alerta=ocorrencias_pendentes_para(current_user),
                           avaliacoes_pendentes=pendencias_avaliacao(current_user), reunioes_sem_avaliacao=reunioes_sem_avaliacao(current_user),
                           alertas_acompanhamento=alertas_acompanhamento(current_user),
                           minhas_bancas_grupo=minhas_bancas_grupo,
                           atividades_agora=atividades_agora,
                           minhas_presencas_agora=minhas_presencas_agora,
                           **contexto_voluntariado,
                           jovens_online_hoje=jovens_online_hoje,
                           jovens_online_cadastro=jovens_online_cadastro,
                           data_hoje_iso=datetime.utcnow().strftime('%Y-%m-%d'),
                           nome_mentor=nome_do_mentor,
                           dias_restantes_senha=dias_restantes_senha,
                           total_alunos=total_alunos,
                           total_matriculas=total_matriculas,
                           total_alunos_sistema=total_alunos_sistema,
                           total_sessoes=total_sessoes,
                           total_finalizados=total_finalizados,
                           finalizados_com_certificado=finalizados_com_certificado,
                           finalizados_sem_certificado=finalizados_sem_certificado,
                           contador_risco=contador_risco,
                           contador_saudavel=contador_saudavel,
                           contador_atencao=contador_atencao,
                           matrizes_analise=matrizes_analise,
                           evolucao_labels=evolucao_labels,
                           evolucao_horas=evolucao_horas,
                           evolucao_cursos=evolucao_cursos,
                           radar_labels=radar_labels,
                           radar_valores=radar_valores,
                           total_projetos=total_projetos,
                           projetos_andamento=projetos_andamento,
                           projetos_concluidos=projetos_concluidos)


# ==============================================================================
# ROTA: Gerenciamento de Grupos (Criação e Listagem)
# ==============================================================================
@app.route('/admin/grupos', methods=['GET', 'POST'])
@login_required
def gerenciar_grupos():
    # 1. Trava de Segurança: Apenas Administradores podem criar grupos
    if current_user.tipo_usuario not in PERFIS_GESTAO_CADASTROS:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))

    # 2. Quando o usuário clica no botão "Salvar Grupo" (POST)
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        # Recebe uma lista com os IDs de todos os usuários que você marcou na caixinha
        membros_ids = request.form.getlist('membros')

        novo_grupo = Grupo(nome=nome, descricao=descricao)

        # Laço de repetição: Para cada ID marcado, busca o usuário no banco e liga ao grupo
        if membros_ids:
            for membro_id in membros_ids:
                usuario = db.session.get(Usuario, int(membro_id))
                if usuario:
                    novo_grupo.membros.append(usuario)
        
        db.session.add(novo_grupo)
        db.session.commit()
        flash("Novo grupo cadastrado com sucesso!", "success")
        return redirect(url_for('gerenciar_grupos'))

    # 3. Quando a página apenas carrega (GET)
    lista_grupos = Grupo.query.order_by(Grupo.nome).all()
    # Busca usuários ativos para montar a lista de seleção
    usuarios_disponiveis = Usuario.query.filter_by(status='Ativo').all()


    return render_template('admin_grupos.html', grupos=lista_grupos, usuarios=usuarios_disponiveis)

# ==============================================================================
# ROTA: Editar Grupo
# ==============================================================================
@app.route('/admin/grupos/editar/<int:id>', methods=['POST'])
@login_required
def editar_grupo(id):
    if current_user.tipo_usuario not in PERFIS_GESTAO_CADASTROS:
        return redirect(url_for('dashboard'))

    grupo = db.session.get(Grupo, id)
    if grupo:
        grupo.nome = request.form.get('nome')
        grupo.descricao = request.form.get('descricao')

        membros_ids = request.form.getlist('membros')
        grupo.membros = [] # Limpa os membros atuais para regravar as novas seleções
        
        if membros_ids:
            for membro_id in membros_ids:
                usuario = db.session.get(Usuario, int(membro_id))
                if usuario:
                    grupo.membros.append(usuario)

        db.session.commit()
        flash('Grupo atualizado com sucesso!', 'success')
        
    return redirect(url_for('gerenciar_grupos'))

# ==============================================================================
# ROTA: Excluir Grupo
# ==============================================================================
@app.route('/admin/grupos/deletar/<int:id>', methods=['POST'])
@login_required
def deletar_grupo(id):
    if current_user.tipo_usuario not in PERFIS_GESTAO_CADASTROS:
        return redirect(url_for('dashboard'))

    grupo = db.session.get(Grupo, id)
    if grupo:
        # Trava de Segurança: Impede apagar o grupo se ele já tiver projetos rodando
        if grupo.projetos:
            flash('Erro: Não é possível excluir este grupo pois existem projetos vinculados a ele.', 'danger')
        else:
            db.session.delete(grupo)
            db.session.commit()
            flash('Grupo excluído com sucesso!', 'success')
            
    return redirect(url_for('gerenciar_grupos'))


# ==============================================================================
# MOTOR DE MATCH INTELIGENTE (ALUNO <-> MENTOR)
# ==============================================================================
def calcular_match_inteligente(aluno, mentores_disponiveis):
    """
    Analisa o objetivo do aluno e cruza com a especialidade/área de atuação dos mentores.
    Retorna uma lista de mentores sugeridos organizados por % de afinidade.
    """
    sugestoes = []
    
    # Se o aluno não tiver preenchido o objetivo, aborta a análise
    if not aluno.objetivo_principal:
        return sugestoes

    objetivo = aluno.objetivo_principal.lower()
    
    # Dicionário de sinónimos corporativos e tecnológicos
    categorias_match = {
        'Cloud & Infraestrutura': ['cloud', 'nuvem', 'azure', 'aws', 'redes', 'infraestrutura', 'servidores', 'segurança', 'cyber', 'cisco', 'juniper', 'dell'],
        'Desenvolvimento de Software': ['programação', 'código', 'python', 'java', 'web', 'backend', 'frontend', 'app', 'software', 'flask', 'github'],
        'Dados & IA': ['dados', 'análise', 'data science', 'machine learning', 'ia', 'inteligência artificial', 'sql', 'power bi', 'excel', 'pandas'],
        'Liderança & Soft Skills': ['liderança', 'gestão', 'carreira', 'rh', 'comunicação', 'projetos', 'agile', 'scrum', 'negócios', 'apresentação']
    }
    
    # Descobre os interesses do aluno
    interesses_aluno = []
    for categoria, palavras in categorias_match.items():
        if any(p in objetivo for p in palavras):
            interesses_aluno.append(categoria)
            
    # Cruza com a área de atuação de cada mentor executivo
    for mentor in mentores_disponiveis:
        score = 0
        area_mentor = ""
        
        # Puxa a área de atuação do perfil avaliador (se existir) ou das observações
        if hasattr(mentor, 'perfil_avaliador') and mentor.perfil_avaliador:
            area_mentor = (mentor.perfil_avaliador.area_atuacao or "").lower()
        else:
            area_mentor = (getattr(mentor, 'observacoes_mentor', '') or "").lower()
            
        for interesse in interesses_aluno:
            if interesse.lower() in area_mentor or any(p in area_mentor for p in categorias_match[interesse]):
                score += 50 # Ganha 50% de match por cada categoria em comum
                
        if score > 0:
            sugestoes.append({
                'mentor': mentor,
                'score': min(score, 100), # Trava o match no máximo em 100%
                'tags_comuns': ", ".join(interesses_aluno)
            })
            
    # Ordena do maior match para o menor
    sugestoes.sort(key=lambda x: x['score'], reverse=True)
    return sugestoes


# ---------------------------------------------------------
# Rota de Cadastro de Usuários (AGORA COM MÚLTIPLOS MENTORES)
# ---------------------------------------------------------
@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
def gerenciar_usuarios():
    if current_user.tipo_usuario not in PERFIS_GESTAO_CADASTROS:
        return "<h1>Acesso Negado</h1>"
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email').strip()
        tipo_usuario = request.form.get('tipo_usuario')
        nivel = perfis_acesso.resolver_nivel(tipo_usuario)
        if not nivel:
            flash(tt('Escolha um nível de acesso válido.', current_user.idioma), "danger")
            return redirect(url_for('gerenciar_usuarios'))
        tipo_usuario, perfil_personalizado_id = nivel
        if not pode_atribuir_nivel(current_user, tipo_usuario):
            flash(tt('Acesso negado: só o Administrador cadastra Administradores.', current_user.idioma), "danger")
            return redirect(url_for('gerenciar_usuarios'))
        status = request.form.get('status')
        senha_plana = request.form.get('senha')
        forcar_troca = request.form.get('forcar_troca_senha') == 'True'
        
        mentores_selecionados_ids = request.form.getlist('mentores') 
        
        padrao_email = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(padrao_email, email):
            flash("Erro: O e-mail digitado não é válido.", "danger")
            return redirect(url_for('gerenciar_usuarios'))
            
        if Usuario.query.filter_by(email=email).first():
            flash("Erro: Este e-mail já está cadastrado no sistema.", "danger")
            return redirect(url_for('gerenciar_usuarios'))
            
        padrao_senha = padrao_senha_forte()
        if not re.match(padrao_senha, senha_plana):
            flash(f"Segurança: A senha deve ter no mínimo {regra('senha_min_caracteres')} caracteres e incluir letras maiúsculas, minúsculas, números e caracteres especiais.", "danger")
            return redirect(url_for('gerenciar_usuarios'))
            
        senha_criptografada = bcrypt.generate_password_hash(senha_plana).decode('utf-8')
        
        novo_usuario = Usuario(
            nome=nome, 
            email=email, 
            tipo_usuario=tipo_usuario,
            status=status,
            senha=senha_criptografada,
            data_criacao=datetime.utcnow(),
            data_ultima_troca_senha=datetime.utcnow(),
            criado_por=current_user.nome,
            forcar_troca_senha=forcar_troca,
            modalidade_participacao=(request.form.get('modalidade_participacao') or 'Presencial') if tipo_usuario == 'Aluno' else None,
            perfil_personalizado_id=perfil_personalizado_id
        )
        
        if tipo_usuario == 'Aluno' and mentores_selecionados_ids:
            for m_id in mentores_selecionados_ids:
                mentor_obj = db.session.get(Usuario, int(m_id))
                if mentor_obj:
                    novo_usuario.mentores.append(mentor_obj) 

        db.session.add(novo_usuario)
        db.session.commit()
        
        flash("Usuário cadastrado com sucesso!", "success")
        return redirect(url_for('gerenciar_usuarios'))
    
    lista_usuarios = Usuario.query.order_by(Usuario.nome).all()
    lista_mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_ORIENTADORES)).all()

    # Busca todos os dados para montar a tela de Cadastros
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_ORIENTADORES)).all()
    solicitacoes = SolicitacaoMentoria.query.order_by(SolicitacaoMentoria.data_solicitacao.desc()).all()


    # Puxa os dados da URL caso o admin tenha clicado em "Aprovar"
    fill_nome = request.args.get('fill_nome', '')
    fill_email = request.args.get('fill_email', '')

    return render_template('admin_usuarios.html', usuarios=usuarios, mentores=mentores, solicitacoes=solicitacoes, fill_nome=fill_nome, fill_email=fill_email, calcular_match=calcular_match_inteligente)
    
# ---------------------------------------------------------
# Rota de Edição de Usuários (AGORA COM MÚLTIPLOS MENTORES)
# ---------------------------------------------------------
@app.route('/admin/usuarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_usuario(id):
    if current_user.tipo_usuario not in PERFIS_GESTAO_CADASTROS:
        return "Acesso Negado"
    
    usuario = db.session.get(Usuario, id)
    if usuario and not pode_atribuir_nivel(current_user, usuario.tipo_usuario):
        flash(tt('Acesso negado: só o Administrador altera contas de Administrador.', current_user.idioma), "danger")
        return redirect(url_for('gerenciar_usuarios'))
    if usuario:
        novo_email = request.form.get('email').strip()
        padrao_email = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        
        if not re.match(padrao_email, novo_email):
            flash("Erro: Formato de e-mail inválido na edição.", "danger")
            return redirect(url_for('gerenciar_usuarios'))
            
        usuario.nome = request.form.get('nome')
        usuario.email = novo_email
        nivel = perfis_acesso.resolver_nivel(request.form.get('tipo_usuario'))
        if not nivel:
            flash(tt('Escolha um nível de acesso válido.', current_user.idioma), "danger")
            return redirect(url_for('gerenciar_usuarios'))
        if not pode_atribuir_nivel(current_user, nivel[0]):
            flash(tt('Acesso negado: só o Administrador cadastra Administradores.', current_user.idioma), "danger")
            return redirect(url_for('gerenciar_usuarios'))
        usuario.tipo_usuario, usuario.perfil_personalizado_id = nivel
        if usuario.tipo_usuario == 'Aluno' and request.form.get('modalidade_participacao'):
            usuario.modalidade_participacao = request.form.get('modalidade_participacao')
        novo_status = request.form.get('status')
        if novo_status == 'Ativo' and usuario.status == 'Bloqueado':
            usuario.tentativas_login = 0
        usuario.status = novo_status
        usuario.forcar_troca_senha = request.form.get('forcar_troca_senha') == 'True'
        
        # NOVO: Apaga as perguntas de segurança do banco se a caixa vermelha foi marcada
        if request.form.get('resetar_perguntas') == 'True':
            SegurancaUsuario.query.filter_by(usuario_id=usuario.id).delete()
        usuario.perfil_aluno = request.form.get('perfil_aluno')
        usuario.objetivo_principal = request.form.get('objetivo_principal')
        usuario.expectativa_mentoria = request.form.get('expectativa_mentoria')
        usuario.observacoes_mentor = request.form.get('observacoes_mentor')
        
        if usuario.tipo_usuario == 'Aluno':
            mentores_selecionados_ids = request.form.getlist('mentores')
            usuario.mentores = [] 
            for m_id in mentores_selecionados_ids:
                mentor_obj = db.session.get(Usuario, int(m_id))
                if mentor_obj:
                    usuario.mentores.append(mentor_obj) 
        
        nova_senha = request.form.get('senha')
        if nova_senha:
            padrao_senha = padrao_senha_forte()
            if not re.match(padrao_senha, nova_senha):
                flash(f"Segurança: A nova senha deve ter no mínimo {regra('senha_min_caracteres')} caracteres...", "danger")
                return redirect(url_for('gerenciar_usuarios'))
                
            usuario.senha = bcrypt.generate_password_hash(nova_senha).decode('utf-8')
            usuario.data_ultima_troca_senha = datetime.utcnow()
            
        db.session.commit()
        flash(f"Usuário {usuario.nome} atualizado com sucesso!", "success")
        
    return redirect(url_for('gerenciar_usuarios'))



# ---------------------------------------------------------
# Rota para Editar/Atualizar o Curso e Auditar Desativação
# ---------------------------------------------------------
@app.route('/admin/cursos/editar/<int:id>', methods=['POST'])
@login_required
def editar_curso(id):
    if current_user.tipo_usuario == 'Aluno':
        return "Acesso Negado"
        
    curso = db.session.get(Curso, id)
    if curso:
        status_anterior = curso.status
        novo_status = request.form.get('status')
        motivo = request.form.get('motivo_desativacao')
        
        if novo_status == 'Desativado' and status_anterior != 'Desativado':
            if not motivo or motivo.strip() == '':
                flash("Operação Cancelada: É obrigatório informar o motivo ao desativar um curso.", "danger")
                return redirect(url_for('gerenciar_turmas'))
                
            curso.status = 'Desativado'
            curso.motivo_desativacao = motivo
            curso.desativado_por_id = current_user.id
            curso.data_desativacao = datetime.now(timezone.utc).replace(tzinfo=None)
            
            acompanhamentos_ativos = Acompanhamento.query.filter_by(curso_id=curso.id).all()
            for acc in acompanhamentos_ativos:
                if acc.status not in ['Finalizado', 'Desativado']:
                    acc.status = 'Desativado'
                    nota_sistema = f"\n[Auditoria - {datetime.now().strftime('%d/%m/%Y')}]: Status alterado pois o curso foi desativado. Motivo: {motivo}"
                    acc.observacao_aluno = (acc.observacao_aluno or "") + nota_sistema

        elif novo_status == 'Ativo' and status_anterior == 'Desativado':
            curso.status = 'Ativo'
            curso.motivo_desativacao = None
            curso.desativado_por_id = None
            curso.data_desativacao = None
        else:
            curso.status = novo_status

        curso.nome_curso = request.form.get('nome')
        curso.plataforma = request.form.get('plataforma')
        curso.tipo = request.form.get('tipo')
        curso.carga_horaria = int(request.form.get('carga_horaria', 20))
        curso.url = request.form.get('url')
        curso.exige_certificado = request.form.get('exige_certificado')
        
        db.session.commit()
        flash(f"Curso '{curso.nome_curso}' atualizado com sucesso!", "success")
        
    return redirect(url_for('gerenciar_turmas'))


app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ==============================================================================
# CONTEÚDO DO CURSO DENTRO DA PLATAFORMA: aulas, vídeo, teste de conhecimento e progresso automático
# (lógica em conteudo_curso.py; telas curso_conteudo.html e estudar_curso.html)
# ==============================================================================
import conteudo_curso

PASTA_AULAS = os.path.join(app.config['UPLOAD_FOLDER'], 'aulas')
EXTENSOES_VIDEO_AULA = {'mp4', 'm4v', 'webm', 'mov', 'ogv'}
EXTENSOES_MATERIAL_AULA = {'pdf', 'docx', 'pptx', 'xlsx', 'doc', 'ppt', 'xls', 'txt', 'zip', 'png', 'jpg', 'jpeg'}
PERFIS_GESTAO_CURSOS = ['Administrador', 'Mentor Administrador', 'Admin B2B']
app.jinja_env.filters['texto_aula'] = conteudo_curso.texto_em_html


def _caminho_aula(nome):
    if not nome:
        return None
    caminho = os.path.realpath(os.path.join(PASTA_AULAS, nome))
    return caminho if caminho.startswith(os.path.realpath(PASTA_AULAS) + os.sep) and os.path.isfile(caminho) else None


def _apagar_arquivo_aula(nome):
    caminho = _caminho_aula(nome)
    if caminho:
        try:
            os.remove(caminho)
        except OSError:
            app.logger.warning("Não consegui apagar o arquivo da aula %s", caminho)


def apagar_conteudo_do_curso(curso_id):
    """Apaga aulas, perguntas, progresso dos alunos e os arquivos (vídeos e materiais) de um curso."""
    from models import AulaCurso, QuestaoAula, ProgressoAula
    aulas = AulaCurso.query.filter_by(curso_id=curso_id).all()
    ids = [a.id for a in aulas]
    if ids:
        ProgressoAula.query.filter(ProgressoAula.aula_id.in_(ids)).delete(synchronize_session=False)
        QuestaoAula.query.filter(QuestaoAula.aula_id.in_(ids)).delete(synchronize_session=False)
    for aula in aulas:
        _apagar_arquivo_aula(aula.video_arquivo)
        _apagar_arquivo_aula(aula.material_arquivo)
        db.session.delete(aula)


def _salvar_arquivo_aula(arquivo, aula, prefixo, extensoes):
    """Grava o arquivo enviado em uploads/aulas. Devolve (nome_salvo, tamanho) ou levanta ValueError (formato/vazio/grande)."""
    extensao = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in (arquivo.filename or '') else ''
    if extensao not in extensoes:
        raise ValueError('formato')
    os.makedirs(PASTA_AULAS, exist_ok=True)
    nome_salvo = f"{prefixo}_{aula.curso_id}_{secrets.token_hex(8)}.{extensao}"
    caminho = os.path.join(PASTA_AULAS, nome_salvo)
    arquivo.save(caminho)
    tamanho = os.path.getsize(caminho)
    limite = int(regra('video_aula_limite_mb')) * 1024 * 1024
    if tamanho == 0 or tamanho > limite:
        os.remove(caminho)
        raise ValueError('vazio' if tamanho == 0 else 'grande')
    return nome_salvo, tamanho


def _proxima_ordem(curso_id):
    from models import AulaCurso
    maior = db.session.query(db.func.max(AulaCurso.ordem)).filter(AulaCurso.curso_id == curso_id).scalar()
    return (maior or 0) + 1


def _reordenar(curso_id):
    from models import AulaCurso
    for n, aula in enumerate(AulaCurso.query.filter_by(curso_id=curso_id).order_by(AulaCurso.ordem, AulaCurso.id).all(), 1):
        aula.ordem = n


def _gravar_questoes(aula, questoes, origem, substituir=True):
    from models import QuestaoAula
    if substituir:
        QuestaoAula.query.filter(QuestaoAula.aula_id == aula.id, QuestaoAula.origem != 'manual').delete(synchronize_session=False)
    inicio = db.session.query(db.func.max(QuestaoAula.ordem)).filter(QuestaoAula.aula_id == aula.id).scalar() or 0
    for n, q in enumerate(questoes, 1):
        db.session.add(QuestaoAula(aula_id=aula.id, ordem=inicio + n, enunciado=q['enunciado'],
                                   alternativas=json.dumps(q['alternativas'], ensure_ascii=False), correta=q['correta'],
                                   explicacao=q.get('explicacao'), origem=origem))


def _recalcular_alunos_do_curso(curso_id):
    """Mudou o conteúdo (aula ou perguntas): o percentual de quem já estudava é refeito com a nova régua."""
    for registro in Acompanhamento.query.filter_by(curso_id=curso_id).all():
        conteudo_curso.recalcular_acompanhamento(registro)


def _gerar_testes(aula_ids, usuario_id, usar_ia):
    """Gera o teste de cada aula (IA ou automático). Devolve (pela_ia, automaticas, sem_texto, aviso)."""
    from models import AulaCurso
    quantidade = int(regra('aula_teste_questoes'))
    ia = automaticas = vazias = 0
    aviso = None
    if usar_ia:
        import credenciais_agentes
        credenciais_agentes.carregar(app.config['SECRET_KEY'])
    curso_id = None
    for aula_id in aula_ids:
        aula = db.session.get(AulaCurso, aula_id)
        if not aula:
            continue
        curso_id = aula.curso_id
        if not (aula.texto or '').strip():
            vazias += 1
            continue
        questoes, origem, motivo = conteudo_curso.gerar_questoes(aula.titulo, aula.texto, quantidade,
                                                                  usuario_id=usuario_id, usar_ia=usar_ia)
        if motivo:
            aviso = aviso or motivo
            usar_ia = False  # a IA falhou (desligada, sem saldo): o resto vai pelo gerador automático, sem nova espera
        if questoes:
            _gravar_questoes(aula, questoes, origem)
            if origem == 'ia':
                ia += 1
            else:
                automaticas += 1
        else:
            vazias += 1
        db.session.commit()
    if curso_id:
        _recalcular_alunos_do_curso(curso_id)
        db.session.commit()
    return ia, automaticas, vazias, aviso


def _gerar_testes_em_segundo_plano(aula_ids, usuario_id):
    import threading

    def trabalho():
        with app.app_context():
            try:
                ia, automaticas, vazias, _ = _gerar_testes(aula_ids, usuario_id, True)
                usuario = db.session.get(Usuario, usuario_id)
                if usuario:
                    idioma = usuario.idioma or 'pt'
                    notificar([usuario], tt('Testes das aulas prontos', idioma),
                              tt('{ia} pela IA, {auto} pelo gerador automático e {vazias} sem texto para gerar perguntas.', idioma)
                              .format(ia=ia, auto=automaticas, vazias=vazias), por_email=False)
            except Exception as erro:
                app.logger.warning("Geração dos testes das aulas falhou: %s", erro)
            finally:
                db.session.remove()
    threading.Thread(target=trabalho, daemon=True).start()


def _usa_ia(usuario):
    """Contas de teste (@local.com) não consomem a IA: usam o gerador automático."""
    import provedores_ia
    return not eh_conta_de_teste(usuario) and provedores_ia.ativo('acompanhamento')


def _id_do_formulario(nome):
    valor = request.form.get(nome) or ''
    return int(valor) if valor.isdigit() else 0


@app.route('/admin/cursos/<int:id>/conteudo', methods=['GET', 'POST'])
@login_required
def conteudo_curso_admin(id):
    """Gestão monta o curso: importa o documento (dividido em aulas), envia vídeos e materiais e revisa os testes."""
    from models import AulaCurso, QuestaoAula, ProgressoAula
    import base_conhecimento
    idioma = current_user.idioma
    if current_user.tipo_usuario not in PERFIS_GESTAO_CURSOS:
        flash(tt('Acesso negado. Apenas a equipa de gestão pode aceder ao Hub Educacional.', idioma), 'danger')
        return redirect(url_for('dashboard'))
    curso = db.session.get(Curso, id)
    if not curso:
        flash(tt('Curso não encontrado.', idioma), 'danger')
        return redirect(url_for('gerenciar_turmas'))

    def voltar_tela(ancora=''):
        return redirect(url_for('conteudo_curso_admin', id=curso.id) + ancora)

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'importar_documento':
            arquivo = request.files.get('documento')
            if not arquivo or not arquivo.filename:
                flash(tt('Escolha o documento do curso.', idioma), 'warning')
                return voltar_tela()
            try:
                texto = base_conhecimento.extrair_texto(arquivo.filename, arquivo.read())
            except base_conhecimento.ErroDocumento as erro:
                flash(tt(str(erro), idioma), 'warning')
                return voltar_tela()
            capitulos, metodo = conteudo_curso.dividir_em_capitulos(texto, os.path.splitext(arquivo.filename)[0])
            if metodo == 'tamanho' and _usa_ia(current_user):
                try:
                    import credenciais_agentes
                    credenciais_agentes.carregar(app.config['SECRET_KEY'])
                    pela_ia = conteudo_curso.dividir_com_ia(texto, current_user.id)
                    if pela_ia:
                        capitulos, metodo = pela_ia, 'ia'
                except Exception as erro:
                    app.logger.info("A IA não dividiu o documento: %s", erro)
            if request.form.get('modo') == 'substituir':
                apagar_conteudo_do_curso(curso.id)
                db.session.flush()
            ordem = _proxima_ordem(curso.id)
            novas = []
            for n, (titulo, corpo) in enumerate(capitulos):
                aula = AulaCurso(curso_id=curso.id, ordem=ordem + n, titulo=(titulo or f'Aula {ordem + n}')[:200],
                                 texto=corpo or None, origem='documento')
                db.session.add(aula)
                novas.append(aula)
            db.session.flush()
            _recalcular_alunos_do_curso(curso.id)
            db.session.commit()
            como = {'titulos': 'pelos títulos do documento', 'palavras': 'pelos capítulos e aulas do texto',
                    'numeracao': 'pela numeração dos títulos', 'ia': 'pela IA',
                    'tamanho': 'em partes de tamanho parecido (o documento não tem títulos)'}[metodo]
            flash(tt('Documento importado: {n} aula(s), divididas {como}.', idioma).format(n=len(novas), como=tt(como, idioma)), 'success')
            if request.form.get('gerar_testes'):
                ids = [a.id for a in novas]
                if _usa_ia(current_user):
                    _gerar_testes_em_segundo_plano(ids, current_user.id)
                    flash(tt('A IA está escrevendo os testes das aulas: você recebe um aviso no sino quando terminar.', idioma), 'info')
                else:
                    _, automaticas, _, _ = _gerar_testes(ids, current_user.id, False)
                    flash(tt('Testes gerados automaticamente em {n} aula(s). Revise as perguntas de cada aula.', idioma).format(n=automaticas), 'info')
            return voltar_tela()

        if acao == 'salvar_aula':
            aula = db.session.get(AulaCurso, _id_do_formulario('aula_id')) if _id_do_formulario('aula_id') else None
            if aula and aula.curso_id != curso.id:
                return voltar_tela()
            titulo = (request.form.get('titulo') or '').strip()
            if not titulo:
                flash(tt('Informe o título da aula.', idioma), 'warning')
                return voltar_tela()
            if aula is None:
                aula = AulaCurso(curso_id=curso.id, ordem=_proxima_ordem(curso.id), origem='manual')
                db.session.add(aula)
            aula.titulo = titulo[:200]
            aula.texto = (request.form.get('texto') or '').strip() or None
            if request.form.get('remover_video'):
                if aula.video_tipo == 'arquivo':
                    _apagar_arquivo_aula(aula.video_arquivo)
                aula.video_tipo = aula.video_arquivo = aula.video_nome = aula.video_tamanho = aula.youtube_id = aula.video_duracao = None
            db.session.flush()
            video = request.files.get('video')
            youtube = (request.form.get('youtube') or '').strip()
            if video and video.filename:
                try:
                    nome_salvo, tamanho = _salvar_arquivo_aula(video, aula, 'video', EXTENSOES_VIDEO_AULA)
                except ValueError as erro:
                    db.session.rollback()
                    flash({'formato': tt('Formato de vídeo não aceito. Envie MP4, WEBM, MOV ou M4V.', idioma),
                           'vazio': tt('O arquivo está vazio.', idioma)}.get(str(erro)) or
                          tt('O arquivo passa do limite de {mb} MB.', idioma).format(mb=int(regra('video_aula_limite_mb'))), 'warning')
                    return voltar_tela()
                if aula.video_tipo == 'arquivo':
                    _apagar_arquivo_aula(aula.video_arquivo)
                aula.video_tipo, aula.video_arquivo, aula.video_tamanho = 'arquivo', nome_salvo, tamanho
                aula.video_nome, aula.youtube_id, aula.video_duracao = (secure_filename(video.filename) or nome_salvo)[:255], None, None
            elif youtube:
                codigo = conteudo_curso.extrair_youtube_id(youtube)
                if not codigo:
                    db.session.rollback()
                    flash(tt('Não reconheci o link do YouTube. Cole o endereço do vídeo (youtube.com/watch?v=… ou youtu.be/…).', idioma), 'warning')
                    return voltar_tela()
                if codigo != aula.youtube_id:
                    if aula.video_tipo == 'arquivo':
                        _apagar_arquivo_aula(aula.video_arquivo)
                    aula.video_tipo, aula.youtube_id, aula.video_duracao = 'youtube', codigo, None
                    aula.video_arquivo = aula.video_nome = aula.video_tamanho = None
            if request.form.get('remover_material'):
                _apagar_arquivo_aula(aula.material_arquivo)
                aula.material_arquivo = aula.material_nome = None
            material = request.files.get('material')
            if material and material.filename:
                try:
                    nome_salvo, _ = _salvar_arquivo_aula(material, aula, 'material', EXTENSOES_MATERIAL_AULA)
                except ValueError:
                    db.session.rollback()
                    flash(tt('Material não aceito: envie PDF, Word, PowerPoint, Excel, imagem, TXT ou ZIP dentro do limite.', idioma), 'warning')
                    return voltar_tela()
                _apagar_arquivo_aula(aula.material_arquivo)
                aula.material_arquivo, aula.material_nome = nome_salvo, (secure_filename(material.filename) or nome_salvo)[:255]
            db.session.flush()
            _recalcular_alunos_do_curso(curso.id)
            db.session.commit()
            flash(tt('Aula salva.', idioma), 'success')
            return voltar_tela(f'#aula{aula.id}')

        if acao == 'excluir_aula':
            aula = db.session.get(AulaCurso, _id_do_formulario('aula_id'))
            if aula and aula.curso_id == curso.id:
                ProgressoAula.query.filter_by(aula_id=aula.id).delete(synchronize_session=False)
                _apagar_arquivo_aula(aula.video_arquivo)
                _apagar_arquivo_aula(aula.material_arquivo)
                db.session.delete(aula)
                db.session.flush()
                _reordenar(curso.id)
                _recalcular_alunos_do_curso(curso.id)
                db.session.commit()
                flash(tt('Aula excluída.', idioma), 'info')
            return voltar_tela()

        if acao == 'mover_aula':
            aula = db.session.get(AulaCurso, _id_do_formulario('aula_id'))
            if aula and aula.curso_id == curso.id:
                _reordenar(curso.id)
                lista = AulaCurso.query.filter_by(curso_id=curso.id).order_by(AulaCurso.ordem).all()
                posicao = lista.index(aula)
                vizinha = posicao - 1 if request.form.get('direcao') == 'subir' else posicao + 1
                if 0 <= vizinha < len(lista):
                    aula.ordem, lista[vizinha].ordem = lista[vizinha].ordem, aula.ordem
                db.session.commit()
                return voltar_tela(f'#aula{aula.id}')
            return voltar_tela()

        if acao in ('gerar_teste', 'gerar_testes_faltando'):
            if acao == 'gerar_teste':
                aula = db.session.get(AulaCurso, _id_do_formulario('aula_id'))
                ids = [aula.id] if aula and aula.curso_id == curso.id else []
            else:
                com_teste = {q.aula_id for q in QuestaoAula.query.join(AulaCurso).filter(AulaCurso.curso_id == curso.id).all()}
                ids = [a.id for a in AulaCurso.query.filter_by(curso_id=curso.id).order_by(AulaCurso.ordem).all() if a.id not in com_teste]
            if not ids:
                flash(tt('Todas as aulas já têm teste.', idioma), 'info')
                return voltar_tela()
            if _usa_ia(current_user) and len(ids) > 3:
                _gerar_testes_em_segundo_plano(ids, current_user.id)
                flash(tt('A IA está escrevendo os testes das aulas: você recebe um aviso no sino quando terminar.', idioma), 'info')
                return voltar_tela()
            ia, automaticas, vazias, _ = _gerar_testes(ids, current_user.id, _usa_ia(current_user))
            if ia or automaticas:
                flash(tt('Teste gerado: {ia} aula(s) pela IA e {auto} pelo gerador automático. Revise as perguntas.', idioma)
                      .format(ia=ia, auto=automaticas), 'success')
            if vazias:
                flash(tt('{n} aula(s) sem texto suficiente para gerar perguntas: escreva um resumo do vídeo no texto da aula ou crie as perguntas à mão.', idioma)
                      .format(n=vazias), 'warning')
            return voltar_tela(f'#aula{ids[0]}' if len(ids) == 1 else '')

        if acao == 'salvar_questao':
            aula = db.session.get(AulaCurso, _id_do_formulario('aula_id'))
            if not aula or aula.curso_id != curso.id:
                return voltar_tela()
            alternativas = [(request.form.get(f'alternativa_{n}') or '').strip() for n in range(6)]
            preenchidas = [n for n, a in enumerate(alternativas) if a]
            correta = _id_do_formulario('correta')
            enunciado = (request.form.get('enunciado') or '').strip()
            if not enunciado or len(preenchidas) < 2 or correta not in preenchidas:
                flash(tt('A pergunta precisa de enunciado, pelo menos duas alternativas e a alternativa certa marcada.', idioma), 'warning')
                return voltar_tela(f'#aula{aula.id}')
            questao = db.session.get(QuestaoAula, _id_do_formulario('questao_id')) if _id_do_formulario('questao_id') else None
            if questao and questao.aula_id != aula.id:
                return voltar_tela()
            if questao is None:
                ordem = (db.session.query(db.func.max(QuestaoAula.ordem)).filter(QuestaoAula.aula_id == aula.id).scalar() or 0) + 1
                questao = QuestaoAula(aula_id=aula.id, ordem=ordem)
                db.session.add(questao)
            questao.enunciado = enunciado[:2000]
            questao.alternativas = json.dumps([alternativas[n][:500] for n in preenchidas], ensure_ascii=False)
            questao.correta = preenchidas.index(correta)
            questao.explicacao = (request.form.get('explicacao') or '').strip() or None
            questao.origem = 'manual'
            db.session.flush()
            _recalcular_alunos_do_curso(curso.id)
            db.session.commit()
            flash(tt('Pergunta salva.', idioma), 'success')
            return voltar_tela(f'#aula{aula.id}')

        if acao == 'excluir_questao':
            questao = db.session.get(QuestaoAula, _id_do_formulario('questao_id'))
            if questao and questao.aula.curso_id == curso.id:
                aula_id = questao.aula_id
                db.session.delete(questao)
                db.session.flush()
                _recalcular_alunos_do_curso(curso.id)
                db.session.commit()
                flash(tt('Pergunta excluída.', idioma), 'info')
                return voltar_tela(f'#aula{aula_id}')
            return voltar_tela()

        return voltar_tela()

    aulas = AulaCurso.query.filter_by(curso_id=curso.id).order_by(AulaCurso.ordem, AulaCurso.id).all()
    return render_template('curso_conteudo.html', curso=curso, aulas=aulas,
                           matriculas=Acompanhamento.query.filter_by(curso_id=curso.id).count(),
                           limite_video_mb=int(regra('video_aula_limite_mb')), usa_ia=_usa_ia(current_user),
                           questoes_por_teste=int(regra('aula_teste_questoes')))


app.config.setdefault('LIMITES_UPLOAD_ROTA', {})['conteudo_curso_admin'] = lambda: regra('video_aula_limite_mb')


def _pode_ver_aulas(usuario, curso_id):
    """Gestão e mentores veem as aulas (prévia); o aluno só as do curso em que está matriculado e ativo."""
    if usuario.tipo_usuario != 'Aluno':
        return True
    return Acompanhamento.query.filter(Acompanhamento.aluno_id == usuario.id, Acompanhamento.curso_id == curso_id,
                                       Acompanhamento.status != 'Desativado').first() is not None


def _acompanhamento_visivel(acomp_id):
    """O acompanhamento, se o usuário puder abri-lo: o próprio aluno, seus mentores ou a gestão."""
    registro = db.session.get(Acompanhamento, acomp_id)
    if not registro:
        return None
    if current_user.tipo_usuario == 'Aluno':
        return registro if registro.aluno_id == current_user.id and registro.status != 'Desativado' else None
    if current_user.tipo_usuario in PERFIS_VEEM_SO_SEUS_ALUNOS:
        aluno = db.session.get(Usuario, registro.aluno_id)
        return registro if aluno and aluno.mentores.filter_by(id=current_user.id).first() else None
    return registro


@app.route('/cursos/aula/<int:aula_id>/<tipo>')
@login_required
def midia_aula(aula_id, tipo):
    """Vídeo (tocado na página, sem link de download) e material de apoio da aula, só para quem pode ver o curso."""
    import mimetypes
    from models import AulaCurso
    aula = db.session.get(AulaCurso, aula_id)
    if not aula or tipo not in ('video', 'material') or not _pode_ver_aulas(current_user, aula.curso_id):
        return ('', 404)
    caminho = _caminho_aula(aula.video_arquivo if tipo == 'video' else aula.material_arquivo)
    if not caminho:
        return ('', 404)
    if tipo == 'material':
        if current_user.tipo_usuario == 'Aluno':
            registro = Acompanhamento.query.filter(Acompanhamento.aluno_id == current_user.id, Acompanhamento.curso_id == aula.curso_id,
                                                   Acompanhamento.status != 'Desativado').first()
            if registro:
                progresso = conteudo_curso.obter_progresso(registro.id, aula.id)
                if not progresso.material_aberto:
                    progresso.material_aberto = True
                    conteudo_curso.fechar_aula_se_concluida(aula, progresso)
                    _, concluiu = conteudo_curso.recalcular_acompanhamento(registro)
                    db.session.commit()
                    if concluiu:
                        _avisar_conclusao(registro)
        return send_file(caminho, as_attachment=True, download_name=aula.material_nome or os.path.basename(caminho))
    resposta = send_file(caminho, mimetype=mimetypes.guess_type(caminho)[0] or 'video/mp4', conditional=True)
    resposta.headers['Content-Disposition'] = 'inline'
    resposta.headers['Cache-Control'] = 'private, no-store'
    return resposta


@app.route('/meus-cursos/<int:acomp_id>')
@login_required
def estudar_curso(acomp_id):
    """Sala de estudo: lista de aulas com o andamento, o conteúdo da aula escolhida e o teste de conhecimento."""
    from models import QuestaoAula
    registro = _acompanhamento_visivel(acomp_id)
    if not registro:
        flash(tt('Acesso negado.', current_user.idioma), 'danger')
        return redirect(url_for('acompanhamento'))
    curso = db.session.get(Curso, registro.curso_id)
    itens, percentual = conteudo_curso.mapa_do_curso(registro)
    if not itens:
        flash(tt('Este curso ainda não tem aulas na plataforma.', current_user.idioma), 'info')
        return redirect(url_for('acompanhamento'))
    escolhida = request.args.get('aula', type=int)
    atual = next((i for i in itens if i['aula'].id == escolhida), None)
    if atual is None:  # continuar de onde parou: a primeira aula ainda não concluída
        atual = next((i for i in itens if i['situacao']['partes'] and not i['situacao']['concluida']), itens[0])
    posicao = itens.index(atual)
    ver = request.args.get('ver') or 'conteudo'
    if ver not in ('conteudo', 'teste') or (ver == 'teste' and not atual['questoes']):
        ver = 'conteudo'
    questoes = QuestaoAula.query.filter_by(aula_id=atual['aula'].id).order_by(QuestaoAula.ordem, QuestaoAula.id).all()
    progresso = atual['progresso']
    resultado = None
    if ver == 'teste' and request.args.get('resultado') and progresso and progresso.teste_respostas:
        try:
            respostas = {int(k): v for k, v in json.loads(progresso.teste_respostas).items()}
        except (ValueError, AttributeError):
            respostas = {}
        nota, detalhes = conteudo_curso.corrigir_teste(questoes, respostas)
        resultado = {'nota': nota, 'detalhes': detalhes}
    eh_aluno = current_user.tipo_usuario == 'Aluno' and registro.aluno_id == current_user.id
    if eh_aluno and ver == 'conteudo':
        session[f'leitura_{registro.id}_{atual["aula"].id}'] = datetime.now().timestamp()
    return render_template('estudar_curso.html', registro=registro, curso=curso, itens=itens, atual=atual, ver=ver,
                           anterior=itens[posicao - 1] if posicao > 0 else None,
                           proxima=itens[posicao + 1] if posicao + 1 < len(itens) else None,
                           questoes=questoes, resultado=resultado, percentual=percentual,
                           concluidas=sum(1 for i in itens if i['situacao']['concluida']),
                           eh_aluno=eh_aluno, aluno=db.session.get(Usuario, registro.aluno_id),
                           nota_minima=int(regra('aula_teste_nota_minima')),
                           video_minimo=int(regra('aula_video_percentual_minimo')),
                           segundos_leitura=conteudo_curso.segundos_de_leitura(atual['aula'].texto),
                           trechos=json.loads(progresso.trechos_video) if progresso and progresso.trechos_video else [])


def _juntar_trechos(trechos):
    juntos = []
    for a, b in sorted([a, b] for a, b in trechos if b > a):
        if juntos and a <= juntos[-1][1] + 1:
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b])
    return juntos


def _avisar_conclusao(registro):
    """Avisa o professor(a) do aluno quando ele termina todas as aulas e testes do curso (o Acompanhamento é do professor)."""
    aluno = db.session.get(Usuario, registro.aluno_id)
    curso = db.session.get(Curso, registro.curso_id)
    if not aluno or not curso:
        return
    for mentor in [u for u in aluno.mentores.all() if u.tipo_usuario in PERFIS_DUVIDAS_ACOMPANHAMENTO]:
        idioma = mentor.idioma or 'pt'
        notificar([mentor], tt('Curso concluído pelas aulas', idioma),
                  tt('{aluno} concluiu todas as aulas e testes do curso {curso}.', idioma).format(aluno=aluno.nome, curso=curso.nome_curso),
                  link=url_for('acompanhamento'), referencia=f'curso-concluido:{registro.id}', por_email=not eh_conta_de_teste(aluno))


def _registro_do_aluno(acomp_id, aula_id):
    from models import AulaCurso
    registro = db.session.get(Acompanhamento, acomp_id)
    aula = db.session.get(AulaCurso, aula_id)
    if not registro or not aula or registro.aluno_id != current_user.id or aula.curso_id != registro.curso_id \
            or registro.status == 'Desativado':
        return None, None
    return registro, aula


@app.route('/meus-cursos/<int:acomp_id>/aula/<int:aula_id>/progresso', methods=['POST'])
@login_required
def progresso_aula(acomp_id, aula_id):
    """O player avisa o andamento: trechos do vídeo realmente assistidos ou a leitura do texto até o fim."""
    registro, aula = _registro_do_aluno(acomp_id, aula_id)
    if not registro:
        return jsonify({'ok': False}), 403
    dados = request.get_json(silent=True) or {}
    progresso = conteudo_curso.obter_progresso(registro.id, aula.id)
    evento = dados.get('evento')
    if evento == 'video' and aula.tem_video:
        try:
            duracao = int(float(dados.get('duracao') or 0))
            posicao = int(float(dados.get('posicao') or 0))
            novos = [[int(float(a)), int(float(b))] for a, b in (dados.get('trechos') or [])[:500]]
        except (TypeError, ValueError):
            return jsonify({'ok': False}), 400
        if duracao > 0 and (not aula.video_duracao or abs(aula.video_duracao - duracao) > 2):
            aula.video_duracao = duracao
        limite = aula.video_duracao or duracao
        antigos = json.loads(progresso.trechos_video) if progresso.trechos_video else []
        juntos = _juntar_trechos(antigos + [[max(0, a), min(b, limite) if limite else b] for a, b in novos])
        progresso.trechos_video = json.dumps(juntos)
        progresso.segundos_assistidos = sum(b - a for a, b in juntos)
        progresso.posicao_video = max(0, min(posicao, limite) if limite else posicao)
        if limite and progresso.segundos_assistidos >= limite * int(regra('aula_video_percentual_minimo')) / 100:
            progresso.video_concluido = True
    elif evento == 'leitura' and (aula.texto or '').strip():
        aberta_em = session.get(f'leitura_{registro.id}_{aula.id}')
        if not aberta_em or datetime.now().timestamp() - aberta_em < conteudo_curso.segundos_de_leitura(aula.texto) - 2:
            return jsonify({'ok': False, 'motivo': 'cedo'}), 409
        progresso.leitura_concluida = True
    else:
        return jsonify({'ok': False}), 400
    situacao = conteudo_curso.fechar_aula_se_concluida(aula, progresso)
    percentual, concluiu = conteudo_curso.recalcular_acompanhamento(registro)
    db.session.commit()
    if concluiu:
        _avisar_conclusao(registro)
    return jsonify({'ok': True, 'percentual': percentual, 'concluida': situacao['concluida'],
                    'video_concluido': progresso.video_concluido, 'leitura_concluida': progresso.leitura_concluida,
                    'assistidos': progresso.segundos_assistidos, 'duracao': aula.video_duracao})


@app.route('/meus-cursos/<int:acomp_id>/aula/<int:aula_id>/teste', methods=['POST'])
@login_required
def teste_aula(acomp_id, aula_id):
    """Corrige o teste de conhecimento da aula; vale a melhor nota e o aluno pode refazer."""
    from models import QuestaoAula
    registro, aula = _registro_do_aluno(acomp_id, aula_id)
    if not registro:
        flash(tt('Acesso negado.', current_user.idioma), 'danger')
        return redirect(url_for('acompanhamento'))
    questoes = QuestaoAula.query.filter_by(aula_id=aula.id).order_by(QuestaoAula.ordem, QuestaoAula.id).all()
    respostas = {}
    for questao in questoes:
        valor = request.form.get(f'q{questao.id}') or ''
        if valor.isdigit():
            respostas[questao.id] = int(valor)
    if not questoes or len(respostas) < len(questoes):
        flash(tt('Responda todas as perguntas antes de enviar.', current_user.idioma), 'warning')
        return redirect(url_for('estudar_curso', acomp_id=registro.id, aula=aula.id, ver='teste'))
    nota, _ = conteudo_curso.corrigir_teste(questoes, respostas)
    progresso = conteudo_curso.obter_progresso(registro.id, aula.id)
    progresso.teste_tentativas = (progresso.teste_tentativas or 0) + 1
    progresso.teste_nota = max(progresso.teste_nota or 0, nota)
    progresso.teste_respostas = json.dumps({str(k): v for k, v in respostas.items()})
    if nota >= int(regra('aula_teste_nota_minima')):
        progresso.teste_aprovado = True
    conteudo_curso.fechar_aula_se_concluida(aula, progresso)
    _, concluiu = conteudo_curso.recalcular_acompanhamento(registro)
    db.session.commit()
    if concluiu:
        _avisar_conclusao(registro)
    return redirect(url_for('estudar_curso', acomp_id=registro.id, aula=aula.id, ver='teste', resultado=1))


# ---------------------------------------------------------
# Rota de Acompanhamento de Estudos
# ---------------------------------------------------------
@app.route('/acompanhamento', methods=['GET', 'POST'])
@login_required
def acompanhamento():
    from datetime import datetime, timedelta, timezone
    from werkzeug.utils import secure_filename
    import os

    if request.method == 'POST':
        # --- EXCLUIR MATERIAIS DE APOIO ---
        if request.form.get('acao') == 'excluir_materiais':
            acompanhamento_id = request.form.get('acompanhamento_id')
            materiais_para_excluir = request.form.getlist('materiais_excluir')
            
            registro = Acompanhamento.query.get(acompanhamento_id)
            if registro and registro.material_apoio:
                materiais_atuais = registro.material_apoio.split('|')
                materiais_restantes = []
                
                for mat in materiais_atuais:
                    if mat in materiais_para_excluir:
                        mat_parts = mat.split('::')
                        nome_arquivo = mat_parts[1] if len(mat_parts) > 1 else mat_parts[0]
                        try:
                            caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                            if os.path.exists(caminho_arquivo):
                                os.remove(caminho_arquivo)
                        except Exception:
                            pass
                    else:
                        materiais_restantes.append(mat)
                
                registro.material_apoio = '|'.join(materiais_restantes) if materiais_restantes else None
                db.session.commit()
                flash('Materiais excluídos permanentemente.', 'success')
            return redirect(url_for('acompanhamento'))

        # --- PARECER DO MENTOR ---
        if request.form.get('acao') == 'atualizar_parecer_livre' and current_user.tipo_usuario != 'Aluno':
            acompanhamento_id = request.form.get('acompanhamento_id')
            registro = Acompanhamento.query.get(acompanhamento_id)
            if registro:
                registro.observacao = request.form.get('observacao')
                registro.data_parecer_mentor = datetime.now()
                db.session.commit()
                flash(tt('Parecer oficial do professor(a) atualizado!', current_user.idioma), 'success')
            return redirect(url_for('acompanhamento'))

        acompanhamento_id = request.form.get('acompanhamento_id')
        if acompanhamento_id:
            if current_user.tipo_usuario == 'Aluno':
                QADuvida.query.filter_by(acompanhamento_id=acompanhamento_id, lida_pelo_aluno=False).update({'lida_pelo_aluno': True})
            else:
                QADuvida.query.filter_by(acompanhamento_id=acompanhamento_id, lida_pelo_mentor=False).update({'lida_pelo_mentor': True})
            db.session.commit()
            
        # --- ANOTAÇÃO DO ALUNO ---
        if request.form.get('acao') == 'atualizar_anotacao_livre':
            acompanhamento_id = request.form.get('acompanhamento_id')
            novo_texto = request.form.get('observacao_aluno')
            registro = Acompanhamento.query.get(acompanhamento_id)
            if registro:
                registro.observacao_aluno = novo_texto
                db.session.commit()
                flash('Anotações atualizadas com sucesso!', 'success')
            return redirect(url_for('acompanhamento'))

        # --- ATUALIZAÇÃO PRINCIPAL DO ACOMPANHAMENTO ---
        if 'acompanhamento_id' in request.form and request.form.get('acao') != 'vincular':
            acompanhamento_id = request.form.get('acompanhamento_id')
            status = request.form.get('status')
            percentual = int(request.form.get('percentual_conclusao', 0))
            observacao_aluno = request.form.get('observacao_aluno')
            observacao_mentor = request.form.get('observacao')
            
            data_inicio_str = request.form.get('data_inicio')
            data_termino_str = request.form.get('data_termino')
            
            regstro = db.session.get(Acompanhamento, acompanhamento_id)
            
            if regstro:
                # TRAVA DE SEGURANÇA: Apenas Mentores e Gestores podem alterar prazos oficiais
                if current_user.tipo_usuario != 'Aluno':
                    if data_inicio_str:
                        regstro.data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
                    else:
                        regstro.data_inicio = None

                    if data_termino_str:
                        regstro.data_termino = datetime.strptime(data_termino_str, '%Y-%m-%d')
                    else:
                        regstro.data_termino = None
                
                if current_user.tipo_usuario != 'Aluno':
                    aluno_obj = db.session.get(Usuario, regstro.aluno_id)
                
                if current_user.tipo_usuario != 'Aluno':
                    aluno_obj = db.session.get(Usuario, regstro.aluno_id)
                    if aluno_obj:
                        aluno_obj.perfil_aluno = request.form.get('perfil_aluno')
                        aluno_obj.objetivo_principal = request.form.get('objetivo_principal')
                        aluno_obj.expectativa_mentoria = request.form.get('expectativa_mentoria')

                curso = db.session.get(Curso, regstro.curso_id)
                arquivo = request.files.get('certificado')
                
                exige_certificado = (curso.exige_certificado == 'Sim')
                tem_arquivo_novo = (arquivo is not None and arquivo.filename != '')
                ja_tem_certificado_salvo = getattr(regstro, 'certificado_anexado', False) or getattr(regstro, 'certificado', False)
                
                # Curso com aulas na plataforma: o progresso é automático (aulas assistidas e testes), não vem do formulário
                progresso_automatico = conteudo_curso.curso_tem_conteudo(curso.id)
                if progresso_automatico:
                    percentual = conteudo_curso.recalcular_acompanhamento(regstro)[0]

                if ((percentual == 100 and not progresso_automatico) or status == 'Finalizado') and exige_certificado and not (ja_tem_certificado_salvo or tem_arquivo_novo):
                    flash("Atenção: Este curso exige certificado para ser finalizado. Faça o upload do arquivo para concluir.", "danger")
                    return redirect(url_for('acompanhamento'))
                
                if status == 'Finalizado' and percentual < 100:
                    flash("Atenção: Você não pode marcar o status como 'Finalizado' sem ter 100% de progresso.", "warning")
                    return redirect(url_for('acompanhamento'))
                
                if percentual == 100 and (not exige_certificado or ja_tem_certificado_salvo or tem_arquivo_novo):
                    status = 'Finalizado'
                
                if tem_arquivo_novo:
                    filename = secure_filename(arquivo.filename)
                    caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    arquivo.save(caminho_arquivo)
                    regstro.certificado_anexado = True
                    regstro.certificado = filename
                
                arq_apoio = request.files.get('material_apoio')
                if arq_apoio and arq_apoio.filename != '':
                    filename_apoio = secure_filename(arq_apoio.filename)
                    caminho_apoio = os.path.join(app.config['UPLOAD_FOLDER'], filename_apoio)
                    arq_apoio.save(caminho_apoio)
                    
                    autor_tag = 'Aluno' if current_user.tipo_usuario == 'Aluno' else 'Mentor'
                    arquivo_carimbado = f"{autor_tag}::{filename_apoio}"
                    
                    if getattr(regstro, 'material_apoio', None):
                        if arquivo_carimbado not in regstro.material_apoio.split('|'):
                            regstro.material_apoio += f"|{arquivo_carimbado}"
                    else:
                        regstro.material_apoio = arquivo_carimbado

                regstro.status = status
                regstro.observacao_aluno = observacao_aluno

                # Notas do Mentor
                if current_user.tipo_usuario != 'Aluno':
                    nota_tecnica = request.form.get('nota_tecnica')
                    nota_postura = request.form.get('nota_postura')
                    if nota_tecnica: regstro.nota_tecnica = float(nota_tecnica)
                    if nota_postura: regstro.nota_postura = float(nota_postura)

                novo_percentual_mentor = request.form.get('percentual_mentor')
                if novo_percentual_mentor is not None:
                    regstro.percentual_mentor = int(novo_percentual_mentor)
                
                if regstro.percentual_conclusao != percentual:
                    regstro.percentual_conclusao = percentual
                    novo_historico = HistoricoProgresso(
                        acompanhamento_id=regstro.id,
                        percentual=percentual,
                        data_registro=datetime.now()
                    )
                    db.session.add(novo_historico)

                if current_user.tipo_usuario != 'Aluno' and observacao_mentor:
                    regstro.observacao = observacao_mentor
                    nova_duvida_qa = QADuvida(
                        acompanhamento_id=regstro.id,
                        autor_id=current_user.id,
                        mensagem=observacao_mentor,
                        lida_pelo_aluno=False,
                        lida_pelo_mentor=True 
                    )
                    db.session.add(nova_duvida_qa)

                fuso_br = timezone(timedelta(hours=-3))
                nova_duvida_texto = request.form.get('nova_duvida_qa')
                if nova_duvida_texto and current_user.tipo_usuario == 'Aluno':
                    nova_duvida = QADuvida(
                        acompanhamento_id=acompanhamento_id,
                        autor_id=current_user.id,
                        mensagem=nova_duvida_texto,
                        lida_pelo_mentor=False,
                        lida_pelo_aluno=True, 
                        data_criacao=datetime.now(fuso_br)
                    )
                    db.session.add(nova_duvida)

                for chave, valor in request.form.items():
                    if chave.startswith('resposta_qa_') and valor.strip():
                        duvida_id = chave.split('_')[-1]
                        duvida_obj = QADuvida.query.get(duvida_id)
                        if duvida_obj:
                            duvida_obj.resposta = valor
                            duvida_obj.lida_pelo_aluno = False 
                            if hasattr(duvida_obj, 'data_resposta'):
                                duvida_obj.data_resposta = datetime.now(fuso_br)

                # =====================================================================
                # MOTOR DE AGENDA SEGURO E ALINHADO
                # =====================================================================
                slot_datas = request.form.getlist('slot_data')
                slot_inicios = request.form.getlist('slot_inicio')
                slot_fims = request.form.getlist('slot_fim')
                
                if slot_datas:
                    curso_obj = db.session.get(Curso, regstro.curso_id)
                    horarios_salvos = {}
                    
                    if regstro.planejamento_estudos:
                        for slot in regstro.planejamento_estudos.split('|'):
                            partes = slot.split('::')
                            if len(partes) == 3:
                                horarios_salvos[partes[0]] = slot
                                
                    hoje = datetime.now(fuso_br).date()
                    tentou_passado = False
                    
                    for i in range(len(slot_datas)):
                        if not slot_datas[i]: 
                            continue
                            
                        ano, mes, dia = slot_datas[i].split('-')
                        data_br = f"{dia}/{mes}/{ano}"
                        data_slot = datetime.strptime(slot_datas[i], '%Y-%m-%d').date()
                        
                        if slot_inicios[i] and slot_fims[i]:
                            if data_slot < hoje:
                                tentou_passado = True
                                continue 
                                
                            horarios_salvos[data_br] = f"{data_br}::{slot_inicios[i]}::{slot_fims[i]}"
                            
                            try:
                                sincronizar_evento_agenda(
                                    titulo=f"Estudo: {curso_obj.nome_curso}",
                                    descricao=f"Sessão focada no curso: {curso_obj.nome_curso}.",
                                    data_inicio=datetime.strptime(slot_datas[i], '%Y-%m-%d'),
                                    horario_str=slot_inicios[i],
                                    horario_fim_str=slot_fims[i]
                                )
                            except Exception:
                                pass

                    regstro.planejamento_estudos = "|".join(horarios_salvos.values()) if horarios_salvos else None
                    if tentou_passado:
                        flash("⚠️ Datas antigas protegidas. Não é possível alterar horários do passado na agenda.", "warning")

            db.session.commit()
            flash("Acompanhamento atualizado com sucesso!", "success")

            if request.form.get('acao_modal') == 'manter_aberto':
                return redirect(url_for('acompanhamento', abrir_modal=regstro.id))
                
        else:
            # --- NOVA MATRÍCULA MANUAL ---
            aluno_id = request.form.get('aluno_id')
            curso_id = request.form.get('curso_id')
            
            if not aluno_id or not curso_id:
                flash("Selecione um aluno e um curso válidos.", "danger")
                return redirect(url_for('acompanhamento'))
            
            curso_selecionado = db.session.get(Curso, int(curso_id))
            if curso_selecionado.status == 'Desativado':
                flash(f"O curso '{curso_selecionado.nome_curso}' está desativado.", "danger")
                return redirect(url_for('acompanhamento'))
            
            existe = Acompanhamento.query.filter_by(aluno_id=int(aluno_id), curso_id=int(curso_id)).first()
            if existe:
                flash("Aluno já matriculado neste curso.", "warning")
            else:
                novo = Acompanhamento(aluno_id=int(aluno_id), curso_id=int(curso_id), status='Iniciado', percentual_conclusao=0)
                db.session.add(novo)
                db.session.commit()
                flash("Matrícula realizada com sucesso!", "success")
                
        return redirect(url_for('acompanhamento'))

    # --- MÉTODO GET: CARREGAR A TELA ---
    if current_user.tipo_usuario == 'Aluno':
        registros = Acompanhamento.query.filter_by(aluno_id=current_user.id).all()
    elif current_user.tipo_usuario in PERFIS_VEEM_SO_SEUS_ALUNOS:
        registros = Acompanhamento.query.join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(Usuario.mentores.any(id=current_user.id)).all()
    else:
        registros = Acompanhamento.query.order_by(Acompanhamento.id.desc()).all()

    from models import AulaCurso
    cursos_com_aulas = {c for (c,) in db.session.query(AulaCurso.curso_id).distinct().all()}
    detalhes = []
    for r in registros:

        aluno = db.session.get(Usuario, r.aluno_id)
        curso = db.session.get(Curso, r.curso_id)
        qtd_sessoes = SessaoMentoria.query.filter_by(aluno_id=r.aluno_id).count()
        
        minutos_estudo = 0
        if r.planejamento_estudos:
            slots = r.planejamento_estudos.split('|')
            for slot in slots:
                partes = slot.split('::')
                if len(partes) == 3:
                    try:
                        from datetime import datetime
                        h_ini = datetime.strptime(partes[1], '%H:%M')
                        h_fim = datetime.strptime(partes[2], '%H:%M')
                        diff = (h_fim - h_ini).seconds // 60
                        minutos_estudo += diff
                    except (ValueError, IndexError, TypeError):
                        pass
                        
        horas_estudo = minutos_estudo // 60
        min_restantes = minutos_estudo % 60
        tempo_formatado = f"{horas_estudo}h {min_restantes}m" if horas_estudo > 0 else f"{min_restantes}m"

        detalhes.append({'reg': r, 'aluno': aluno, 'curso': curso, 'qtd_sessoes': qtd_sessoes, 'tempo_estudo': tempo_formatado,
                         'tem_aulas': r.curso_id in cursos_com_aulas})
        
    if current_user.tipo_usuario in PERFIS_VEEM_SO_SEUS_ALUNOS:
        lista_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).all()
    else:
        lista_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').all()
        
    lista_cursos = Curso.query.filter_by(status='Ativo').all()

    from datetime import datetime, time
    hoje_inicio = datetime.combine(datetime.utcnow().date(), time.min)
    hoje_fim = datetime.combine(datetime.utcnow().date(), time.max)
    
    for item in registros:
        aluno_id = None
        curso_id = None
        try:
            if isinstance(item, dict):
                aluno_id = item.get('aluno_id') or getattr(item.get('aluno'), 'id', None) or getattr(item.get('reg'), 'aluno_id', None)
                curso_id = item.get('curso_id') or getattr(item.get('curso'), 'id', None) or getattr(item.get('reg'), 'curso_id', None)
            else:
                aluno_id = getattr(item, 'aluno_id', None) or getattr(getattr(item, 'aluno', None), 'id', None) or getattr(getattr(item, 'reg', None), 'aluno_id', None)
                curso_id = getattr(item, 'curso_id', None) or getattr(getattr(item, 'curso', None), 'id', None) or getattr(getattr(item, 'reg', None), 'curso_id', None)
        except Exception:
            pass

        ja_tem = False
        if aluno_id and curso_id:
            ja_tem = CheckinAula.query.filter(
                CheckinAula.usuario_id == aluno_id,
                CheckinAula.curso_id == curso_id,
                CheckinAula.data_hora_entrada >= hoje_inicio,
                CheckinAula.data_hora_entrada <= hoje_fim
            ).first() is not None

        if isinstance(item, dict):
            item['ja_fez_checkin_hoje'] = ja_tem
        else:
            setattr(item, 'ja_fez_checkin_hoje', ja_tem)
    
    return render_template('acompanhamento.html', registros=detalhes, alunos=lista_alunos, cursos=lista_cursos)


# ==============================================================================
# ROTA: REGISTAR CHECK-IN DE AULA DO ALUNO (PONTUALIDADE)
# ==============================================================================
@app.route('/acompanhamento/checkin', methods=['POST'])
@login_required
def fazer_checkin_aula():
    from datetime import datetime
    
    curso_id = request.form.get('curso_id', type=int)
    if not curso_id:
        flash('Erro: Curso não especificado.', 'danger')
        return redirect(url_for('acompanhamento'))
    # Check-in só nos cursos em que a pessoa está matriculada (tem acompanhamento do curso)
    if not Acompanhamento.query.filter_by(aluno_id=current_user.id, curso_id=curso_id).first():
        flash(tt('Check-in recusado: você não está matriculado neste curso.', current_user.idioma), 'danger')
        return redirect(url_for('acompanhamento'))

    hoje = datetime.utcnow().date()
    
    # Verifica se já existe check-in para este curso hoje
    existente = CheckinAula.query.filter(
        CheckinAula.usuario_id == current_user.id,
        CheckinAula.curso_id == curso_id,
        db.func.date(CheckinAula.data_hora_entrada) == hoje
    ).first()
    
    if not existente:
        # Descobre se o aluno marcou presença Online ou Presencial na portaria hoje
        freq_diaria = Frequencia.query.filter(
            Frequencia.usuario_id == current_user.id,
            db.func.date(Frequencia.data_registro) == hoje
        ).first()
        
        modalidade_atual = freq_diaria.tipo_presenca if freq_diaria else 'Não Informada'
        
        novo_checkin = CheckinAula(
            usuario_id=current_user.id,
            curso_id=curso_id,
            modalidade=modalidade_atual
        )
        db.session.add(novo_checkin)
        db.session.commit()
        flash('Presença na aula registrada com sucesso! Bom estudo.', 'success')
    else:
        flash('Você já havia registado presença nesta aula hoje.', 'info')
        
    return redirect(url_for('acompanhamento'))


# ==============================================================================
# ROTA: Gestão de Projetos (Tela principal e Cadastro)
# ==============================================================================
PERFIS_SEM_CADASTRO_PROJETO = ['Aluno']  # o Aluno vê os projetos do seu grupo, mas não cadastra


@app.route('/projetos', methods=['GET', 'POST'])
@login_required
def projetos():
    # 1. Se o usuário preencheu o formulário e clicou em "Salvar" (POST)
    if request.method == 'POST':
        # Esconder o formulário não basta: a rota também recusa o cadastro feito pelo Aluno
        if current_user.tipo_usuario in PERFIS_SEM_CADASTRO_PROJETO:
            flash(tt('Acesso negado: o Aluno não pode cadastrar projetos.', current_user.idioma), 'danger')
            return redirect(url_for('projetos'))
        nome = (request.form.get('nome') or '').strip()
        descricao = request.form.get('descricao')
        grupo_id = request.form.get('grupo_id', type=int) # Recebe o ID do Grupo
        if not nome or not grupo_id or not db.session.get(Grupo, grupo_id):
            flash(tt('Informe o nome do projeto e escolha um grupo válido.', current_user.idioma), 'warning')
            return redirect(url_for('projetos'))
        
        # Garante o preenchimento de todos os dados vitais para o projeto aparecer
        novo_projeto = Projeto(
            nome=nome,
            descricao=descricao,
            grupo_id=grupo_id,
            status='Em Andamento',
            percentual_conclusao=0,
            data_criacao=datetime.now()
        )
        
        db.session.add(novo_projeto)
        db.session.commit()
        
        flash('Projeto criado com sucesso!', 'success')
        return redirect(url_for('projetos'))

    # 2. Quando a página apenas carrega (GET) - CORREÇÃO DE SEGURANÇA E LGPD
    grupo_filtro = request.args.get('grupo_filtro')
    query = Projeto.query
    
    # TRAVA: Se for Aluno, filtra rigorosamente para mostrar apenas os grupos dele
    if current_user.tipo_usuario == 'Aluno':
        meus_grupos_ids = [g.id for g in current_user.grupos]
        query = query.filter(Projeto.grupo_id.in_(meus_grupos_ids))
        grupos_disponiveis = current_user.grupos # Aluno só pode escolher os seus grupos no filtro
    else:
        # Se for Gestor ou Mentor, pode ver tudo e usar filtros livres
        if grupo_filtro:
            query = query.filter_by(grupo_id=grupo_filtro)
        grupos_disponiveis = Grupo.query.order_by(Grupo.nome).all()
        
    # Ordena para manter os mais recentes no topo
    lista_projetos = query.order_by(Projeto.id.desc()).all()

    
    # Aba Gráficos de cada projeto: Gantt das tarefas e séries para os gráficos sob demanda dos mentores
    import graficos_projeto
    graficos = {p.id: graficos_projeto.dados_do_projeto(p, traduzir=lambda texto: tt(texto, current_user.idioma)) for p in lista_projetos}
    return render_template('projetos.html', projetos=lista_projetos, grupos=grupos_disponiveis, grupo_filtro=grupo_filtro,
                           pode_cadastrar_projeto=current_user.tipo_usuario not in PERFIS_SEM_CADASTRO_PROJETO,
                           graficos=graficos, dados_graficos=graficos_projeto.DADOS)


# ==============================================================================
# FUNÇÃO MATEMÁTICA: Efeito Cascata de Progresso (Subtarefa -> Tarefa -> Projeto)
# ==============================================================================
def recalcular_progresso_projeto(projeto_id):
    projeto = db.session.get(Projeto, projeto_id)
    if not projeto: return

    # Filtra apenas as tarefas "Pai" (que não têm tarefa acima delas)
    tarefas_principais = [t for t in projeto.tarefas if t.tarefa_pai_id is None]
    
    if tarefas_principais:
        soma_projeto = 0
        for tp in tarefas_principais:
            # Se a tarefa principal tem filhas, o % dela é a média das filhas!
            if tp.subtarefas:
                soma_sub = sum(sub.percentual_conclusao for sub in tp.subtarefas)
                tp.percentual_conclusao = int(soma_sub / len(tp.subtarefas))
                # Ajusta o status automaticamente
                tp.status = 'Concluído' if tp.percentual_conclusao == 100 else 'Em Andamento' if tp.percentual_conclusao > 0 else 'Pendente'

            soma_projeto += tp.percentual_conclusao
            
        # Calcula a média do projeto baseada apenas nas Tarefas Principais
        media_proj = int(soma_projeto / len(tarefas_principais))
        projeto.percentual_conclusao = media_proj
        projeto.status = 'Concluído' if media_proj == 100 else 'Em Andamento' if media_proj > 0 else 'Em Andamento'
    else:
        projeto.percentual_conclusao = 0
        
    db.session.commit()

# ==============================================================================
# ROTA: Criar Tarefa ou Subtarefa
# ==============================================================================
@app.route('/projetos/nova_tarefa', methods=['POST'])
@login_required
def nova_tarefa():
    projeto_id = request.form.get('projeto_id')
    if not pode_mexer_no_projeto(current_user, db.session.get(Projeto, request.form.get('projeto_id', type=int) or 0)):
        flash(tt('Acesso negado: só o grupo do projeto e a gestão mexem nas tarefas.', current_user.idioma), 'danger')
        return redirect(url_for('projetos'))
    tarefa_pai_id = request.form.get('tarefa_pai_id') or None # Identifica se é subtarefa
    
    # Recebe a lista de apoio (Múltipla escolha) e transforma em texto separado por vírgula
    equipe_apoio_list = request.form.getlist('equipe_apoio')
    equipe_apoio_str = ", ".join(equipe_apoio_list) if equipe_apoio_list else ""

    from datetime import datetime
    data_inicio_str, data_fim_str = request.form.get('data_inicio'), request.form.get('data_fim')
    
    nova = Tarefa(
        projeto_id=projeto_id,
        tarefa_pai_id=tarefa_pai_id,
        descricao=request.form.get('descricao'),
        data_inicio=datetime.strptime(data_inicio_str, '%Y-%m-%d') if data_inicio_str else None,
        data_fim=datetime.strptime(data_fim_str, '%Y-%m-%d') if data_fim_str else None,
        responsavel=request.form.get('responsavel'),
        equipe_apoio=equipe_apoio_str,
        status=request.form.get('status', 'Pendente')
    )
    
    db.session.add(nova)
    db.session.commit()
    recalcular_progresso_projeto(projeto_id)
    
    flash('Adicionado com sucesso!', 'success')
    return redirect(url_for('projetos'))

# ==============================================================================
# ROTA: Atualizar Tarefa e Recalcular
# ==============================================================================
@app.route('/projetos/atualizar_tarefa', methods=['POST'])
@login_required
def atualizar_tarefa():
    tarefa_id = request.form.get('tarefa_id')
    tarefa = db.session.get(Tarefa, int(tarefa_id)) if tarefa_id else None
    if tarefa and not pode_mexer_no_projeto(current_user, tarefa.projeto):
        flash(tt('Acesso negado: só o grupo do projeto e a gestão mexem nas tarefas.', current_user.idioma), 'danger')
        return redirect(url_for('projetos'))

    if tarefa:
        try:
            percentual = int(request.form.get('percentual_conclusao', 0) or 0)
        except ValueError:
            percentual = -1
        if not 0 <= percentual <= 100:
            flash(tt('O progresso da tarefa deve ficar entre 0 e 100%.', current_user.idioma), 'warning')
            return redirect(url_for('projetos'))
        tarefa.descricao = request.form.get('descricao')
        tarefa.responsavel = request.form.get('responsavel')
        
        equipe_apoio_list = request.form.getlist('equipe_apoio')
        tarefa.equipe_apoio = ", ".join(equipe_apoio_list) if equipe_apoio_list else ""
        
        from datetime import datetime
        d_ini, d_fim = request.form.get('data_inicio'), request.form.get('data_fim')
        tarefa.data_inicio = datetime.strptime(d_ini, '%Y-%m-%d') if d_ini else None
        tarefa.data_fim = datetime.strptime(d_fim, '%Y-%m-%d') if d_fim else None

        tarefa.status = request.form.get('status')
        if not tarefa.subtarefas:
            tarefa.percentual_conclusao = percentual
        
        # --- NOVA LÓGICA MÚLTIPLOS ANEXOS (EXCLUSÃO) ---
        materiais_para_excluir = request.form.getlist('materiais_excluir')
        if materiais_para_excluir and tarefa.arquivo_anexo:
            materiais_atuais = tarefa.arquivo_anexo.split('|')
            materiais_restantes = []
            for mat in materiais_atuais:
                if mat in materiais_para_excluir:
                    mat_parts = mat.split('::')
                    nome_arquivo = mat_parts[1] if len(mat_parts) > 1 else mat_parts[0]
                    try:
                        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                        if os.path.exists(caminho_arquivo):
                            os.remove(caminho_arquivo)
                    except Exception:
                        pass
                else:
                    materiais_restantes.append(mat)
            tarefa.arquivo_anexo = '|'.join(materiais_restantes) if materiais_restantes else None

        # --- NOVA LÓGICA MÚLTIPLOS ANEXOS (UPLOAD) ---
        arquivos = request.files.getlist('arquivos_anexos')
        for arquivo in arquivos:
            if arquivo and arquivo.filename:
                import os
                from werkzeug.utils import secure_filename
                filename = secure_filename(arquivo.filename)
                arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                autor_tag = current_user.tipo_usuario
                arquivo_carimbado = f"{autor_tag}::{filename}"
                
                if getattr(tarefa, 'arquivo_anexo', None):
                    if arquivo_carimbado not in tarefa.arquivo_anexo.split('|'):
                        tarefa.arquivo_anexo += f"|{arquivo_carimbado}"
                else:
                    tarefa.arquivo_anexo = arquivo_carimbado
        # ----------------------------------------
        
        # --- LÓGICA DO PLANEAMENTO E AGENDA DO RESPONSÁVEL ---
        slot_datas = request.form.getlist('slot_data')
        slot_inicios = request.form.getlist('slot_inicio')
        slot_fims = request.form.getlist('slot_fim')
        
        if slot_datas:
            planejamento_salvo = []
            total_minutos = 0
            houve_novo_input = False
            
            for i in range(len(slot_datas)):
                if slot_inicios[i] and slot_fims[i]: 
                    houve_novo_input = True
                    try:
                        from datetime import datetime as dt_calc
                        t_inicio = dt_calc.strptime(slot_inicios[i], '%H:%M')
                        t_fim = dt_calc.strptime(slot_fims[i], '%H:%M')
                        diff_minutos = (t_fim - t_inicio).seconds // 60
                        total_minutos += diff_minutos
                    except Exception:
                        pass
                        
                    ano, mes, dia = slot_datas[i].split('-')
                    data_br = f"{dia}/{mes}/{ano}"
                    planejamento_salvo.append(f"{data_br}::{slot_inicios[i]}::{slot_fims[i]}")
                    
                    if current_user.nome == tarefa.responsavel:
                        try:
                            from datetime import datetime as dt_seguro
                            data_slot = dt_seguro.strptime(slot_datas[i], '%Y-%m-%d')
                            projeto_pai = db.session.get(Projeto, tarefa.projeto_id)
                            nome_proj = projeto_pai.nome if projeto_pai else "Projeto"
                            
                            sincronizar_evento_agenda(
                                titulo=f"Tarefa: {tarefa.descricao[:25]}",
                                descricao=f"Projeto: {nome_proj}\nAtividade: {tarefa.descricao}",
                                data_inicio=data_slot,
                                horario_str=slot_inicios[i],
                                horario_fim_str=slot_fims[i]
                            )
                        except Exception:
                            pass
                            
            if houve_novo_input:
                tarefa.planejamento_tarefa = "|".join(planejamento_salvo)
                tarefa.tempo_total_minutos = total_minutos
        # ----------------------------------------------------
        
        db.session.commit()
        recalcular_progresso_projeto(tarefa.projeto_id)
        flash('Atualizado com sucesso!', 'success')
        
        # O SEGREDO ESTÁ AQUI: Verifica qual botão foi clicado
        acao_modal = request.form.get('acao_modal')
        if acao_modal == 'manter_aberto':
            return redirect(url_for('projetos', abrir_modal=tarefa.id))
        
    return redirect(url_for('projetos'))

# ==============================================================================
# ROTA: Excluir Tarefa
# ==============================================================================
@app.route('/projetos/deletar_tarefa/<int:id>', methods=['POST'])
@login_required
def deletar_tarefa(id):
    tarefa = db.session.get(Tarefa, id)
    if tarefa and not pode_mexer_no_projeto(current_user, tarefa.projeto):
        flash(tt('Acesso negado: só o grupo do projeto e a gestão mexem nas tarefas.', current_user.idioma), 'danger')
        return redirect(url_for('projetos'))
    if tarefa:
        p_id = tarefa.projeto_id
        db.session.delete(tarefa)
        db.session.commit()
        recalcular_progresso_projeto(p_id)
        flash('Excluído com sucesso!', 'success')
    return redirect(url_for('projetos'))


# ==============================================================================
# ROTA: Excluir Projeto Inteiro
# ==============================================================================
@app.route('/projetos/deletar_projeto/<int:id>', methods=['POST'])
@login_required
def deletar_projeto(id):
    # 1. Trava de Segurança: Apenas os perfis autorizados podem deletar
    perfis_autorizados = PERFIS_EXCLUEM_PROJETO
    
    if current_user.tipo_usuario not in perfis_autorizados:
        flash('Acesso negado: Apenas mentores e administradores podem excluir projetos.', 'danger')
        return redirect(url_for('projetos'))

    projeto = db.session.get(Projeto, id)
    if projeto and not pode_mexer_no_projeto(current_user, projeto):
        flash(tt('Acesso negado: mentores e professores só excluem projetos do próprio grupo.', current_user.idioma), 'danger')
        return redirect(url_for('projetos'))
    if projeto:
        # 2. Segurança do Banco: Apaga todas as tarefas e subtarefas do projeto primeiro
        tarefas = Tarefa.query.filter_by(projeto_id=projeto.id).all()
        for t in tarefas:
            db.session.delete(t)
            
        # 3. Apaga o projeto em si
        db.session.delete(projeto)
        db.session.commit()
        flash('Projeto e todas as suas tarefas foram excluídos permanentemente!', 'success')
        
    return redirect(url_for('projetos'))


# ==============================================================================
# ROTA: AVALIAR PROJETO (TCC) - NOTAS COLETIVAS E INDIVIDUAIS
# ==============================================================================
@app.route('/projetos/avaliar/<int:id>', methods=['POST'])
@login_required
def avaliar_projeto(id):
    # Trava de Segurança: Alunos não podem dar notas
    if current_user.tipo_usuario == 'Aluno':
        return redirect(url_for('projetos'))

    projeto = db.session.get(Projeto, id)
    if projeto:
        # 0. Toda nota informada fica entre 0 e 10 (nada é gravado se alguma estiver fora)
        for campo, valor in request.form.items():
            if campo.startswith(('nota_conteudo', 'nota_apresentacao', 'nota_postura_', 'nota_dominio_')) and valor.strip():
                try:
                    nota = float(valor.replace(',', '.'))
                except ValueError:
                    nota = -1
                if not 0 <= nota <= NOTA_MAXIMA:
                    flash(tt('As notas do projeto devem ficar entre 0 e 10.', current_user.idioma), 'warning')
                    return redirect(url_for('projetos'))

        # 1. Capta as notas do Grupo (O Entregável)
        nota_conteudo = (request.form.get('nota_conteudo') or '').replace(',', '.')
        nota_apresentacao = (request.form.get('nota_apresentacao') or '').replace(',', '.')

        # Depois que a banca começa a dar notas, a nota do grupo é a consolidada da banca
        from models import AvaliacaoBanca
        banca_avaliando = AvaliacaoBanca.query.filter_by(projeto_id=projeto.id).first() is not None
        if nota_conteudo and not banca_avaliando:
            projeto.nota_conteudo = float(nota_conteudo)
        if nota_apresentacao and not banca_avaliando:
            projeto.nota_apresentacao = float(nota_apresentacao)

        # 2. Capta as notas e observações Individuais (Para cada membro do grupo)
        if projeto.grupo:
            for membro in projeto.grupo.membros:
                # Procura se o aluno já tem um boletim neste projeto. Se não, cria um.
                av_indiv = AvaliacaoProjeto.query.filter_by(projeto_id=projeto.id, aluno_id=membro.id).first()
                if not av_indiv:
                    av_indiv = AvaliacaoProjeto(projeto_id=projeto.id, aluno_id=membro.id)
                    db.session.add(av_indiv)

                # Busca os inputs gerados dinamicamente com o ID do aluno no HTML
                nota_postura = (request.form.get(f'nota_postura_{membro.id}') or '').replace(',', '.')
                nota_dominio = (request.form.get(f'nota_dominio_{membro.id}') or '').replace(',', '.')
                obs_mentor = request.form.get(f'obs_mentor_{membro.id}')

                if nota_postura: 
                    av_indiv.nota_postura = float(nota_postura)
                if nota_dominio: 
                    av_indiv.nota_dominio = float(nota_dominio)
                if obs_mentor:
                    av_indiv.observacoes_mentor = obs_mentor

        db.session.commit()
        flash('Avaliação do Projeto gravada com sucesso!', 'success')

    return redirect(url_for('projetos'))

# -------------------------------------------------------------------------
# Rota de Sessões de Mentoria e Feedback
# ---------------------------------------------------------
@app.route('/sessoes', methods=['GET', 'POST'])
@login_required
def sessoes():
    
    abrir_modal = request.args.get('abrir_modal')
    if abrir_modal:
        if current_user.tipo_usuario == 'Aluno':
            FeedbackSessao.query.filter_by(sessao_id=abrir_modal, lida_pelo_aluno=False).update({'lida_pelo_aluno': True})
        else:
            FeedbackSessao.query.filter_by(sessao_id=abrir_modal, lida_pelo_mentor=False).update({'lida_pelo_mentor': True})
        db.session.commit()

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'agendar':
            if current_user.tipo_usuario == 'Aluno':
                flash("Acesso Negado: Alunos não podem agendar sessões.", "danger")
                return redirect(url_for('sessoes'))
                
            aluno_id = request.form.get('aluno_id')
            data_str = request.form.get('data_sessao')
            hora_inicio_str = request.form.get('hora_inicio')
            hora_fim_str = request.form.get('hora_fim')
            observacoes = request.form.get('observacoes')
            
            # Junta a data com a hora de início para salvar no banco de dados da plataforma
            data_hora_completa = f"{data_str} {hora_inicio_str}"
            data_sessao = datetime.strptime(data_hora_completa, '%Y-%m-%d %H:%M')
            
            nova_sessao = SessaoMentoria(
                mentor_id=current_user.id,
                aluno_id=aluno_id,
                data_sessao=data_sessao,
                observacoes=observacoes
            )
            db.session.add(nova_sessao)
            db.session.commit()


            # --- GATILHO DO SINO: Notifica o aluno imediatamente ---
            aviso_agendamento = FeedbackSessao(
                sessao_id=nova_sessao.id,
                autor_id=current_user.id,
                papel_autor='Mentor',
                comentario=f"Sessão agendada! Pauta oficial: {observacoes}",
                visibilidade='Publico',
                lida_pelo_aluno=False, # O False acende o sino vermelho no topo da tela do aluno!
                lida_pelo_mentor=True
            )
            db.session.add(aviso_agendamento)
            db.session.commit()
            # -------------------------------------------------------

            
            # --- GATILHO DO GOOGLE AGENDA ---
            try:
                # Busca o nome do aluno para o título do evento
                aluno_obj = db.session.get(Usuario, aluno_id)
                nome_aluno = aluno_obj.nome if aluno_obj else "Aluno"
                
                titulo_evento = f"Mentoria: {nome_aluno}"
                descricao_evento = f"Pauta da Sessão: {observacoes}" if observacoes else "Sessão de mentoria."
                
                # Usa os horários exatos definidos por você na tela
                sincronizar_evento_agenda(
                    titulo=titulo_evento,
                    descricao=descricao_evento,
                    data_inicio=data_sessao,
                    horario_str=hora_inicio_str,
                    horario_fim_str=hora_fim_str
                )
            except Exception:
                pass # Se o Google falhar ou estiver desconectado, o sistema apenas ignora silenciosamente
            # --------------------------------
            
            flash("Sessão agendada com sucesso e sincronizada na agenda!", "success")
            
        elif acao == 'enviar_feedback':
            sessao_id = request.form.get('sessao_id')
            comentario = request.form.get('comentario')
            visibilidade = request.form.get('visibilidade', 'Publico')
            
            papel = 'Mentor' if current_user.tipo_usuario != 'Aluno' else 'Aluno'
            
            if papel == 'Aluno':
                visibilidade = 'Publico'
            
            lida_aluno = True if papel == 'Aluno' else False
            lida_mentor = True if papel == 'Mentor' else False
            
            novo_feedback = FeedbackSessao(
                sessao_id=sessao_id,
                autor_id=current_user.id,
                papel_autor=papel,
                comentario=comentario,
                visibilidade=visibilidade,
                lida_pelo_aluno=lida_aluno,
                lida_pelo_mentor=lida_mentor
            )
            db.session.add(novo_feedback)
            db.session.commit()
            flash("Feedback enviado com sucesso!", "success")
            
        return redirect(url_for('sessoes'))
    
    if current_user.tipo_usuario == 'Aluno':
        minhas_sessoes = SessaoMentoria.query.filter_by(aluno_id=current_user.id).order_by(SessaoMentoria.data_sessao.desc()).all()
    elif current_user.tipo_usuario in PERFIS_VEEM_TODAS_SESSOES:
        minhas_sessoes = SessaoMentoria.query.order_by(SessaoMentoria.data_sessao.desc()).all()
    else:
        minhas_sessoes = SessaoMentoria.query.filter_by(mentor_id=current_user.id).order_by(SessaoMentoria.data_sessao.desc()).all()
        
    sessoes_detalhadas = []
    for s in minhas_sessoes:
        mentor = db.session.get(Usuario, s.mentor_id)
        aluno = db.session.get(Usuario, s.aluno_id)
        
        if current_user.tipo_usuario == 'Aluno':
            feedbacks = FeedbackSessao.query.filter_by(sessao_id=s.id, visibilidade='Publico').order_by(FeedbackSessao.data_envio.asc()).all()
        else:
            feedbacks = FeedbackSessao.query.filter_by(sessao_id=s.id).order_by(FeedbackSessao.data_envio.asc()).all()
            
        feedbacks_detalhados = [{'fb': f, 'autor': db.session.get(Usuario, f.autor_id)} for f in feedbacks]
        
        sessoes_detalhadas.append({
            'sessao': s, 
            'mentor': mentor, 
            'aluno': aluno, 
            'feedbacks': feedbacks_detalhados
        })
        
    if current_user.tipo_usuario in PERFIS_VEEM_SO_SEUS_ALUNOS:
        lista_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).all()
    else:
        lista_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').all()

    return render_template('sessoes.html', sessoes=sessoes_detalhadas, alunos=lista_alunos, agora=datetime.now(),
                           pode_ata=lambda s: s.mentor_id == current_user.id or current_user.tipo_usuario in PERFIS_GESTAO_INSTITUICAO)

@app.route('/sessoes/<int:id>/ata', methods=['POST'])
@login_required
def ata_sessao(id):
    """Ata digital do encontro: resumo das deliberações, fontes recomendadas e plano de ação (próximos passos).
    O mentor da sessão (ou a gestão da instituição) registra; ao salvar com o plano de ação, o jovem recebe os próximos passos por e-mail."""
    idioma = current_user.idioma
    sessao = db.session.get(SessaoMentoria, id)
    if not sessao or not (sessao.mentor_id == current_user.id or current_user.tipo_usuario in PERFIS_GESTAO_INSTITUICAO):
        flash("Acesso negado.", "danger")
        return redirect(url_for('sessoes'))
    resumo = (request.form.get('ata_resumo') or '').strip()[:5000]
    fontes = (request.form.get('ata_fontes') or '').strip()[:3000]
    plano = '\n'.join(l.strip() for l in (request.form.get('ata_plano_acao') or '').splitlines() if l.strip())[:3000]
    try:
        proximo = datetime.strptime(request.form.get('ata_proximo_encontro'), '%Y-%m-%d').date() if request.form.get('ata_proximo_encontro') else None
    except ValueError:
        proximo = None
    if len(resumo) < MINIMO_CARACTERES_DESCRICAO or not plano:
        flash(tt('Preencha o resumo das deliberações (mínimo de 10 caracteres) e pelo menos um passo do plano de ação.', idioma), 'warning')
        return redirect(url_for('sessoes', abrir_ata=sessao.id))
    if sessao.data_sessao > datetime.now() + timedelta(hours=1):
        flash(tt('A ata é registrada depois do encontro.', idioma), 'warning')
        return redirect(url_for('sessoes'))
    sessao.ata_resumo, sessao.ata_fontes, sessao.ata_plano_acao, sessao.ata_proximo_encontro = resumo, fontes or None, plano, proximo
    sessao.ata_registrada_em, sessao.ata_registrada_por_id = datetime.now(), current_user.id
    db.session.commit()
    aluno, mentor = db.session.get(Usuario, sessao.aluno_id), db.session.get(Usuario, sessao.mentor_id)
    if request.form.get('enviar_proximos_passos') and aluno:
        passos = '; '.join(plano.splitlines())
        quando = proximo.strftime('%d/%m/%Y') if proximo else '—'
        notificar([aluno] + ([mentor] if mentor and mentor.id != current_user.id else []),
                  ('notif_proximos_passos_titulo', {'data': sessao.data_sessao.strftime('%d/%m/%Y')}),
                  ('notif_proximos_passos_msg', {'mentor': mentor.nome if mentor else '—', 'passos': passos, 'proximo': quando}),
                  link=url_for('sessoes', abrir_ata=sessao.id), tipo='sessao',
                  referencia=f"proximos-passos:{sessao.id}:{sessao.ata_registrada_em:%Y%m%d%H%M%S}", por_email=not eh_conta_de_teste(aluno))
        sessao.proximos_passos_enviados_em = datetime.now()
        db.session.commit()
        flash(tt('Ata registrada e próximos passos enviados ao jovem por e-mail.', idioma), 'success')
    else:
        flash(tt('Ata registrada.', idioma), 'success')
    return redirect(url_for('sessoes', abrir_ata=sessao.id))


# ==============================================================================
# ROTA: ALUNO SALVAR SESSÃO NA PRÓPRIA AGENDA
# ==============================================================================
@app.route('/sessoes/sincronizar_aluno/<int:id>', methods=['POST'])
@login_required
def sincronizar_sessao_aluno(id):
    if current_user.tipo_usuario != 'Aluno':
        return redirect(url_for('sessoes'))
        
    # Exige uma agenda conectada (Google ou Microsoft 365) antes de tentar salvar
    if not agenda_conectada():
        flash(tt('Conecte sua agenda (Google ou Microsoft 365) na lista Agenda, em Acompanhamento.', current_user.idioma), "warning")
        return redirect(url_for('acompanhamento'))
        
    sessao = db.session.get(SessaoMentoria, id)
    if sessao and sessao.aluno_id == current_user.id:
        mentor = db.session.get(Usuario, sessao.mentor_id)
        nome_mentor = mentor.nome if mentor else "Mentor"
        
        # Assume 1 hora de duração a partir do horário de início
        from datetime import timedelta
        data_fim = sessao.data_sessao + timedelta(hours=1)
        
        sucesso = sincronizar_evento_agenda(
            titulo=f"Mentoria com {nome_mentor}",
            descricao=f"Pauta: {sessao.observacoes}",
            data_inicio=sessao.data_sessao,
            horario_str=sessao.data_sessao.strftime('%H:%M'),
            horario_fim_str=data_fim.strftime('%H:%M')
        )
        
        if sucesso:
            flash(tt('Sessão salva na sua agenda!', current_user.idioma), "success")
        else:
            flash("Erro ao salvar. Tente desconectar e conectar o Google novamente.", "danger")
            
    return redirect(url_for('sessoes'))



# ===========================================================================
# Rota segura para exibir/baixar os certificados e materiais
# ===========================================================================
@app.route('/uploads/<nome_arquivo>')
@login_required
def acessar_upload(nome_arquivo):
    if current_user.tipo_usuario == 'Aluno':
        meus_grupos = [g.id for g in current_user.grupos] or [-1]
        tarefas = Tarefa.query.join(Projeto, Projeto.id == Tarefa.projeto_id).filter(
            Projeto.grupo_id.in_(meus_grupos), Tarefa.arquivo_anexo.like(f"%{nome_arquivo}%")).all()
        materiais = Acompanhamento.query.filter(Acompanhamento.aluno_id == current_user.id,
                                                Acompanhamento.material_apoio.like(f"%{nome_arquivo}%")).all()
        dono = any(nome_arquivo in (x.arquivo_anexo or '').split('|') for x in tarefas) or \
            any(nome_arquivo in (x.material_apoio or '').split('|') for x in materiais)
        if not dono:
            flash("Acesso negado.", "danger")
            return redirect(url_for('dashboard'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], nome_arquivo)

# ---------------------------------------------------------
# Rota de Logout (Sair do Sistema)
# ---------------------------------------------------------
@app.route('/logout')
@login_required
def logout():
    # Limpa as credenciais do Google da memória do navegador
    session.pop('google_token', None)
    session.pop('google_refresh_token', None)

    # Troca o token: qualquer cópia do cookie de sessão deixa de valer
    current_user.token_sessao = secrets.token_hex(16)
    db.session.commit()
    logout_user()
    session.pop('_csrf_token', None)
    flash("Você saiu do sistema em segurança.", "info")
    return redirect(url_for('login'))

# ---------------------------------------------------------
# Rota para Deletar um Curso
# ---------------------------------------------------------
@app.route('/admin/cursos/deletar/<int:id>')
@login_required
def deletar_curso(id):
    if current_user.tipo_usuario == 'Aluno':
        return "<h1>Acesso Negado</h1><p>Apenas mentores e administradores podem excluir cursos.</p>"
    
    curso = db.session.get(Curso, id)
    if curso:
        # Presenças apontam para o curso: o histórico não pode sumir (antes dava erro 500)
        if CheckinAula.query.filter_by(curso_id=curso.id).first():
            flash(tt('Este curso já tem presenças registradas e não pode ser excluído. Desative o curso em vez de excluir.', current_user.idioma), "warning")
            return redirect(url_for('gerenciar_turmas'))
        apagar_conteudo_do_curso(curso.id)
        db.session.delete(curso)
        db.session.commit()
        flash("Curso excluído com sucesso!", "success")
    else:
        flash("Curso não encontrado.", "danger")
        
    return redirect(url_for('gerenciar_turmas'))


# ---------------------------------------------------------
# Rota para Alternar o Tema do Sistema
# ---------------------------------------------------------
@app.route('/alterar-tema/<nome_tema>')
@login_required
def alterar_tema(nome_tema):
    temas_validos = ['claro', 'escuro', 'futurista', 'vintage']
    if nome_tema in temas_validos:
        current_user.tema = nome_tema
        db.session.commit()
        # Removido o flash daqui para não poluir a tela com alertas
    
    return voltar('dashboard')

# ---------------------------------------------------------
# Rota para Alternar o Idioma do Sistema
# ---------------------------------------------------------
@app.route('/alterar-idioma/<sigla_idioma>')
@login_required
def alterar_idioma(sigla_idioma):
    idiomas_validos = ['pt', 'en', 'es']
    if sigla_idioma in idiomas_validos:
        current_user.idioma = sigla_idioma
        db.session.commit()
    
    return voltar('dashboard')

# ==============================================================================
# MOTOR DO RELÓGIO DE VOLUNTARIADO CORPORATIVO (ESG)
# ==============================================================================

# ==============================================================================
# VOLUNTARIADO: TIPOS, CATEGORIAS E VÍNCULOS (grupo / TCC) DOS LANÇAMENTOS
# ==============================================================================
# (valor gravado no banco, chave de tradução do rótulo)
TIPOS_ATIVIDADE_VOLUNTARIADO = [
    ('Mentoria Extraordinária', 'vol_tipo_extra'),
    ('Leitura Assíncrona de TCC', 'vol_tipo_leitura'),
    ('Análise e Notas', 'vol_tipo_analise'),
    ('Avaliação de Banca Ao Vivo', 'vol_tipo_banca'),
    ('Apoio Institucional', 'vol_tipo_apoio'),
]
# Atividades fora do cronograma oficial: entram como horas EXTRAS no relatório ESG
TIPOS_EXTRA = ['Mentoria Extraordinária', 'Reunião Institucional']
PERFIS_GESTAO_VOLUNTARIADO = ['Administrador', 'Mentor Administrador', 'Admin B2B']


def classificar_categoria(tipo_atividade):
    """'Extra' para o que acontece fora do cronograma oficial; 'Regular' para o resto.
    Isolada aqui para ajustarmos quando existir o calendário oficial de encontros."""
    tipo_base = (tipo_atividade or '').replace(' (Lançamento Manual)', '')
    return 'Extra' if tipo_base in TIPOS_EXTRA else 'Regular'


def grupos_do_usuario(usuario):
    """Grupos em que a pessoa pode lançar horas: os seus (gestores veem todos)."""
    if usuario.tipo_usuario in PERFIS_GESTAO_VOLUNTARIADO:
        return Grupo.query.order_by(Grupo.nome).all()
    return sorted(getattr(usuario, 'grupos', None) or [], key=lambda g: g.nome)


def projetos_do_usuario(usuario):
    """TCCs dos grupos da pessoa e das bancas em que está escalada (gestores veem todos)."""
    if usuario.tipo_usuario in PERFIS_GESTAO_VOLUNTARIADO:
        return Projeto.query.order_by(Projeto.nome).all()
    from models import Banca
    ids_banca = {b.projeto_id for b in Banca.query.all() if usuario in b.avaliadores}
    if usuario.tipo_usuario == 'Avaliador Banca':
        return Projeto.query.filter(Projeto.id.in_(list(ids_banca) or [-1])).order_by(Projeto.nome).all()
    ids_grupos = [g.id for g in grupos_do_usuario(usuario)] or [-1]
    return Projeto.query.filter(Projeto.grupo_id.in_(ids_grupos) | Projeto.id.in_(list(ids_banca) or [-1])).order_by(Projeto.nome).all()


def validar_vinculos_voluntariado(usuario, tipo, formulario):
    """Confere os vínculos exigidos por cada tipo de atividade.
    Devolve (chave_do_erro ou None, grupo_id, projeto_id, motivo)."""
    motivo = (formulario.get('observacoes') or '').strip()
    grupo_id = formulario.get('grupo_id', type=int)
    projeto_id = formulario.get('projeto_id', type=int)
    tipo_base = (tipo or '').replace(' (Lançamento Manual)', '')

    if tipo_base == 'Mentoria Extraordinária':
        if grupo_id not in {g.id for g in grupos_do_usuario(usuario)}:
            return 'vol_erro_grupo', None, None, motivo
        if len(motivo) < MINIMO_CARACTERES_DESCRICAO:
            return 'vol_erro_motivo', None, None, motivo
    else:
        grupo_id = None
    if tipo_base in ['Leitura Assíncrona de TCC', 'Análise e Notas', 'Avaliação de Banca Ao Vivo']:
        if projeto_id not in {p.id for p in projetos_do_usuario(usuario)}:
            return 'vol_erro_projeto', None, None, motivo
    elif tipo_base != 'Mentoria Extraordinária':
        projeto_id = projeto_id if projeto_id in {p.id for p in projetos_do_usuario(usuario)} else None
    return None, grupo_id, projeto_id, motivo


def registros_esg_do_perfil(usuario):
    """Lançamentos de voluntariado que o perfil pode ver no relatório ESG."""
    from models import CheckinVoluntariado
    consulta = CheckinVoluntariado.query
    if usuario.tipo_usuario == 'Admin B2B':
        empresas = Empresa.query.filter_by(gestor_id=usuario.id).all()
        ids_mentores = [m.id for emp in empresas for m in emp.mentores] or [-1]
        consulta = consulta.filter(CheckinVoluntariado.usuario_id.in_(ids_mentores))
    return consulta.order_by(CheckinVoluntariado.data_hora_inicio.desc()).all()


def linha_relatorio_esg(vol):
    """Uma linha do relatório ESG (CSV e PDF usam o mesmo formato)."""
    usuario = db.session.get(Usuario, vol.usuario_id)
    # O relacionamento correto é empresas_vinculadas (backref de Empresa.mentores)
    empresas = getattr(usuario, 'empresas_vinculadas', None) or []
    return {
        'nome': usuario.nome if usuario else 'Desconhecido',
        'perfil': usuario.tipo_usuario if usuario else 'N/A',
        'empresa': ", ".join(e.nome for e in empresas) if empresas else "Institucional (Hub)",
        'atividade': vol.tipo_atividade,
        'categoria': vol.categoria or classificar_categoria(vol.tipo_atividade),
        'grupo': vol.grupo.nome if vol.grupo else '',
        'projeto': vol.projeto.nome if vol.projeto else '',
        'motivo': vol.observacoes or '',
        'minutos': vol.total_minutos or 0,
        'data': vol.data_hora_inicio.strftime('%d/%m/%Y %H:%M') if vol.data_hora_inicio else "",
        'status': "Concluído" if vol.data_hora_fim else "Em Andamento (Relógio Ativo)",
    }


# Sensor global que avisa o HTML (tela) se o relógio de um usuário está a contar
@app.context_processor
def verificar_relogio_voluntariado():
    relogio_aberto = False
    if current_user.is_authenticated:
        from models import CheckinVoluntariado
        try:
            ponto = CheckinVoluntariado.query.filter_by(usuario_id=current_user.id, data_hora_fim=None).first()
            if ponto:
                relogio_aberto = True
        except Exception:
            pass
    return dict(relogio_aberto=relogio_aberto)

# Rota que liga e desliga o cronômetro
@app.route('/voluntariado/ponto', methods=['POST'])
@login_required
def bater_ponto_voluntariado():
    from models import CheckinVoluntariado
    from datetime import datetime

    # Verifica se o voluntário já tem um relógio a contar
    ponto_aberto = CheckinVoluntariado.query.filter_by(
        usuario_id=current_user.id,
        data_hora_fim=None
    ).first()

    if ponto_aberto:
        # DESLIGAR O RELÓGIO (Check-out)
        ponto_aberto.data_hora_fim = datetime.utcnow()

        # Calcula os minutos exatos
        tempo_passado = ponto_aberto.data_hora_fim - ponto_aberto.data_hora_inicio
        minutos = int(tempo_passado.total_seconds() / 60)
        ponto_aberto.total_minutos = minutos

        db.session.commit()
        flash(f"⏱️ Check-out concluído! Foram contabilizados {minutos} minutos para o relatório corporativo ESG.", "success")
    else:
        # LIGAR O RELÓGIO (Check-in): extras exigem grupo e motivo; leitura exige o TCC
        tipo = request.form.get('tipo_atividade') or 'Apoio Institucional'
        erro, grupo_id, projeto_id, motivo = validar_vinculos_voluntariado(current_user, tipo, request.form)
        if erro:
            flash(t(erro, current_user.idioma), "warning")
            return voltar('dashboard')

        novo_ponto = CheckinVoluntariado(
            usuario_id=current_user.id,
            tipo_atividade=tipo,
            data_hora_inicio=datetime.utcnow(),
            grupo_id=grupo_id,
            projeto_id=projeto_id,
            categoria=classificar_categoria(tipo),
            observacoes=motivo or None
        )
        db.session.add(novo_ponto)
        db.session.commit()
        flash("⏳ O relógio de voluntariado começou a contar! Não se esqueça de desligar quando terminar a leitura ou reunião.", "info")

    return voltar('dashboard')


# ==============================================================================
# ROTA: PORTAL DE DEMANDAS INSTITUCIONAIS (TICKETS INSTITUIÇÃO & B2B)
# ==============================================================================
# ==============================================================================
# ATIVIDADES EXTRAS DO GRUPO (fora do cronograma) — check-in/out de mentores e jovens
# ==============================================================================
PERFIS_CRIAM_ATIVIDADE_EXTRA = ['Mentor', 'Professor', 'Mentor Administrador', 'Administrador']


def pode_ver_atividade_extra(usuario, atividade):
    if usuario.tipo_usuario in PERFIS_VEEM_TODAS_ATIVIDADES:
        return True
    membros = {m.id for m in atividade.grupo.membros} if atividade.grupo else set()
    if usuario.id in membros or usuario.id == atividade.criado_por_id:
        return True
    if usuario.tipo_usuario == 'Admin B2B':
        return bool(membros & (ids_jovens_visiveis(usuario) or set()))
    return False


def pode_gerir_atividade_extra(usuario, atividade):
    return usuario.id == atividade.criado_por_id or usuario.tipo_usuario in PERFIS_VEEM_TODAS_ATIVIDADES


def pode_registrar_presenca(usuario, atividade):
    """Só quem é do grupo (ou quem criou a atividade) faz check-in."""
    membros = {m.id for m in atividade.grupo.membros} if atividade.grupo else set()
    return usuario.id in membros or usuario.id == atividade.criado_por_id


def atividades_extras_visiveis(usuario):
    from models import AtividadeExtra
    todas = AtividadeExtra.query.order_by(AtividadeExtra.data_hora_inicio_prevista.desc()).limit(200).all()
    return [a for a in todas if pode_ver_atividade_extra(usuario, a)]


def fechar_presenca(presenca, horario_saida, automatico=False):
    """Calcula os minutos e, para quem não é Aluno, gera o lançamento ESG (categoria Extra) sem duplicar."""
    from models import CheckinVoluntariado
    presenca.check_out = max(horario_saida, presenca.check_in)
    presenca.total_minutos = int((presenca.check_out - presenca.check_in).total_seconds() / 60)
    presenca.checkout_automatico = automatico
    pessoa = presenca.usuario
    if pessoa and pessoa.tipo_usuario != 'Aluno' and not presenca.checkin_voluntariado_id:
        # Relógio de voluntariado aberto já está contando este tempo: não lança de novo
        relogio_aberto = CheckinVoluntariado.query.filter_by(usuario_id=pessoa.id, data_hora_fim=None).first()
        if not relogio_aberto:
            atividade = presenca.atividade
            lancamento = CheckinVoluntariado(
                usuario_id=pessoa.id, tipo_atividade='Mentoria Extraordinária', categoria='Extra',
                grupo_id=atividade.grupo_id, data_hora_inicio=presenca.check_in, data_hora_fim=presenca.check_out,
                total_minutos=presenca.total_minutos,
                observacoes=f"Atividade extra #{atividade.id}: {atividade.titulo} — {atividade.motivo}"[:1000])
            db.session.add(lancamento)
            db.session.flush()
            presenca.checkin_voluntariado_id = lancamento.id


@app.route('/atividades-extras')
@login_required
def atividades_extras():
    from models import AtividadeExtra
    lista = atividades_extras_visiveis(current_user)
    minhas = {p.atividade_id: p for a in lista for p in a.presencas if p.usuario_id == current_user.id}
    pode_criar = current_user.tipo_usuario in PERFIS_CRIAM_ATIVIDADE_EXTRA
    return render_template('atividades_extras.html', atividades=lista, minhas=minhas, pode_criar=pode_criar,
                           grupos=grupos_do_usuario(current_user) if pode_criar else [],
                           agora=datetime.now(), pode_gerir=lambda a: pode_gerir_atividade_extra(current_user, a),
                           pode_registrar=lambda a: pode_registrar_presenca(current_user, a))


@app.route('/atividades-extras/nova', methods=['POST'])
@login_required
def nova_atividade_extra():
    from models import AtividadeExtra
    if current_user.tipo_usuario not in PERFIS_CRIAM_ATIVIDADE_EXTRA:
        flash("Acesso negado.", "danger")
        return redirect(url_for('atividades_extras'))

    grupo_id = request.form.get('grupo_id', type=int)
    titulo = (request.form.get('titulo') or '').strip()
    motivo = (request.form.get('motivo') or '').strip()
    try:
        inicio = datetime.strptime(request.form.get('data_hora_inicio', ''), "%Y-%m-%dT%H:%M")
    except ValueError:
        inicio = None
    duracao = request.form.get('duracao_prevista_min', type=int) or 60

    if grupo_id not in {g.id for g in grupos_do_usuario(current_user)}:
        flash(t('vol_erro_grupo', current_user.idioma), "warning")
    elif not titulo or len(motivo) < MINIMO_CARACTERES_DESCRICAO or not inicio:
        flash(t('extra_erro_campos', current_user.idioma), "warning")
    elif not DURACAO_MINIMA_ATIVIDADE_MIN <= duracao <= DURACAO_MAXIMA_EVENTO_MIN:
        flash(t('vol_erro_duracao', current_user.idioma), "warning")
    else:
        atividade = AtividadeExtra(grupo_id=grupo_id, titulo=titulo, motivo=motivo, data_hora_inicio_prevista=inicio,
                                   duracao_prevista_min=duracao, modalidade=request.form.get('modalidade') or 'Presencial',
                                   link_sala=(request.form.get('link_sala') or '').strip() or None, criado_por_id=current_user.id)
        db.session.add(atividade)
        db.session.commit()
        notificar([m for m in atividade.grupo.membros if m.id != current_user.id],
                  ('notif_extra_titulo', {'titulo': titulo}),
                  ('notif_extra_msg', {'autor': current_user.nome, 'grupo': atividade.grupo.nome,
                                       'inicio': inicio.strftime('%d/%m/%Y %H:%M'), 'motivo': motivo}),
                  link=url_for('atividades_extras'), tipo='atividade_extra', referencia=f"extra-nova:{atividade.id}")
        flash(t('extra_criada', current_user.idioma), "success")
    return redirect(url_for('atividades_extras'))


@app.route('/atividades-extras/<int:id>/<acao>', methods=['POST'])
@login_required
def acao_atividade_extra(id, acao):
    from models import AtividadeExtra, PresencaAtividadeExtra
    atividade = db.session.get(AtividadeExtra, id)
    if not atividade or not pode_ver_atividade_extra(current_user, atividade):
        flash("Acesso negado.", "danger")
        return redirect(url_for('atividades_extras'))
    agora = datetime.now()
    aberta = atividade.status in ['Agendada', 'Em andamento']
    presenca = PresencaAtividadeExtra.query.filter_by(atividade_id=atividade.id, usuario_id=current_user.id).first()

    if acao == 'checkin':
        if not pode_registrar_presenca(current_user, atividade):
            flash(t('extra_so_membros', current_user.idioma), "danger")
        elif not aberta:
            flash(t('extra_fechada', current_user.idioma), "warning")
        elif agora < atividade.data_hora_inicio_prevista - timedelta(minutes=30):
            flash(t('extra_cedo', current_user.idioma), "warning")
        elif presenca:
            flash(t('extra_ja_registrado', current_user.idioma), "info")
        else:
            db.session.add(PresencaAtividadeExtra(atividade_id=atividade.id, usuario_id=current_user.id, check_in=agora,
                                                  modalidade=request.form.get('modalidade') or atividade.modalidade))
            if atividade.status == 'Agendada':
                atividade.status = 'Em andamento'
            db.session.commit()
            flash(t('extra_checkin_ok', current_user.idioma), "success")

    elif acao == 'checkout':
        if not presenca or presenca.check_out:
            flash(t('extra_sem_checkin', current_user.idioma), "warning")
        else:
            fechar_presenca(presenca, agora)
            db.session.commit()
            flash(t('extra_checkout_ok', current_user.idioma).format(minutos=presenca.total_minutos), "success")

    elif acao in ['encerrar', 'cancelar']:
        if not pode_gerir_atividade_extra(current_user, atividade) or not aberta:
            flash("Acesso negado.", "danger")
        elif acao == 'cancelar':
            atividade.status = 'Cancelada'
            db.session.commit()
            flash(t('extra_cancelada', current_user.idioma), "info")
        else:
            # Quem esqueceu o check-out recebe o horário de fim previsto (ou agora, se já passou do check-in)
            for p in atividade.presencas:
                if not p.check_out:
                    fechar_presenca(p, min(agora, max(atividade.fim_previsto, p.check_in)), automatico=True)
            atividade.status = 'Encerrada'
            atividade.data_encerramento = agora
            db.session.commit()
            flash(t('extra_encerrada', current_user.idioma), "success")
    return redirect(url_for('atividades_extras') + f"#extra-{atividade.id}")


@app.route('/atividades-extras/<int:id>/relatorio.csv')
@login_required
def relatorio_atividade_extra(id):
    import csv
    import io
    from flask import Response
    from models import AtividadeExtra
    atividade = db.session.get(AtividadeExtra, id)
    if not atividade or not (pode_gerir_atividade_extra(current_user, atividade) or current_user.tipo_usuario in PERFIS_VEEM_RELATORIO_ATIVIDADE
                             and pode_ver_atividade_extra(current_user, atividade)):
        flash("Acesso negado.", "danger")
        return redirect(url_for('atividades_extras'))
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(['Atividade', 'Grupo', 'Participante', 'Perfil', 'Entrada', 'Saída', 'Minutos', 'Modalidade', 'Check-out automático'])
    for p in sorted(atividade.presencas, key=lambda x: x.check_in):
        escritor.writerow([atividade.titulo, atividade.grupo.nome if atividade.grupo else '', p.usuario.nome if p.usuario else '',
                           p.usuario.tipo_usuario if p.usuario else '', p.check_in.strftime('%d/%m/%Y %H:%M'),
                           p.check_out.strftime('%d/%m/%Y %H:%M') if p.check_out else '', p.total_minutos or 0,
                           p.modalidade or '', 'Sim' if p.checkout_automatico else 'Não'])
    return Response(saida.getvalue().encode('utf-8-sig'), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=Atividade_Extra_{atividade.id}.csv"})


# ==============================================================================
# REUNIÕES INSTITUCIONAIS instituição × B2B (ata, participantes, encaminhamentos e horas)
# ==============================================================================
PERFIS_GESTAO_REUNIOES = ['Administrador', 'Mentor Administrador', 'Admin B2B']
TIPOS_REUNIAO = ['Alinhamento', 'Acompanhamento do programa', 'Planejamento', 'Institucional']
CHECKIN_REUNIAO_ANTES_MIN = 30   # o check-in abre 30 min antes do início
CHECKIN_REUNIAO_DEPOIS_MIN = 60  # e fecha 1 h depois do fim previsto
CHECKOUT_REUNIAO_AUTOMATICO_H = 2  # check-out esquecido: fecha no fim previsto 2 h depois do fim


def pode_ver_reuniao(usuario, reuniao):
    return usuario.tipo_usuario in PERFIS_GESTAO_REUNIOES or usuario in reuniao.participantes


def fechar_presenca_reuniao(presenca, saida, automatico=False):
    presenca.check_out = max(saida, presenca.check_in)
    presenca.total_minutos = int((presenca.check_out - presenca.check_in).total_seconds() // 60)
    presenca.checkout_automatico = automatico


def sincronizar_voluntariado_reuniao(reuniao):
    """Mantém um lançamento ESG (categoria Extra) por participante interno, sem duplicar ao editar.
    Com controle de presença, só conta quem fez check-in e check-out, pelo tempo real; reuniões antigas
    (sem controle de presença) continuam com a duração prevista para todos os participantes."""
    from models import CheckinVoluntariado
    existentes = {c.usuario_id: c for c in CheckinVoluntariado.query.filter_by(reuniao_id=reuniao.id).all()}
    internos = {p.id for p in reuniao.participantes if p.tipo_usuario != 'Aluno'}
    periodos = {}
    if reuniao.contar_voluntariado:
        if reuniao.controle_presenca:
            periodos = {p.usuario_id: (p.check_in, p.check_out, p.total_minutos) for p in reuniao.presencas
                        if p.usuario_id in internos and p.check_out and (p.total_minutos or 0) > 0}
        else:
            fim = reuniao.data_hora + timedelta(minutes=reuniao.duracao_minutos or 0)
            periodos = {uid: (reuniao.data_hora, fim, reuniao.duracao_minutos or 0) for uid in internos}
    for usuario_id, (inicio, fim, minutos) in periodos.items():
        lancamento = existentes.pop(usuario_id, None) or CheckinVoluntariado(usuario_id=usuario_id, reuniao_id=reuniao.id)
        lancamento.tipo_atividade = 'Reunião Institucional'
        lancamento.categoria = 'Extra'
        lancamento.data_hora_inicio = inicio
        lancamento.data_hora_fim = fim
        lancamento.total_minutos = minutos
        lancamento.observacoes = f"Reunião #{reuniao.id}: {reuniao.titulo}"[:1000]
        db.session.add(lancamento)
    # Quem saiu da lista (ou "contar como voluntariado" desligado) perde o lançamento
    for sobra in existentes.values():
        db.session.delete(sobra)


def salvar_reuniao_do_formulario(reuniao, formulario, usuario):
    """Preenche a reunião com os dados do formulário. Devolve a chave do erro ou None."""
    titulo = (formulario.get('titulo') or '').strip()
    empresa = None
    empresa_id = formulario.get('empresa_id', type=int)
    if empresa_id:
        empresa = next((e for e in empresas_da_reuniao(usuario, reuniao.empresa) if e.id == empresa_id), None)
        if empresa is None:
            return 'reuniao_erro_parceiro'
    try:
        data_hora = datetime.strptime(formulario.get('data_hora', ''), "%Y-%m-%dT%H:%M")
    except ValueError:
        data_hora = None
    duracao = formulario.get('duracao_minutos', type=int) or 0
    if not titulo or not data_hora:
        return 'reuniao_erro_campos'
    if not DURACAO_MINIMA_REUNIAO_MIN <= duracao <= DURACAO_MAXIMA_EVENTO_MIN:
        return 'vol_erro_duracao'
    gravacao = (formulario.get('link_gravacao') or '').strip()
    if gravacao:
        from urllib.parse import urlparse
        partes = urlparse(gravacao)
        if partes.scheme not in ('http', 'https') or not partes.netloc or len(gravacao) > 500:
            return 'reuniao_erro_gravacao'
    reuniao.tipo = formulario.get('tipo') if formulario.get('tipo') in TIPOS_REUNIAO else 'Alinhamento'
    reuniao.pontos_parceiro = (formulario.get('pontos_parceiro') or '').strip()[:5000] or None
    reuniao.link_gravacao = gravacao or None
    reuniao.titulo = titulo
    reuniao.data_hora = data_hora
    reuniao.duracao_minutos = duracao
    reuniao.modalidade = formulario.get('modalidade') or 'Online'
    reuniao.local_ou_link = (formulario.get('local_ou_link') or '').strip() or None
    reuniao.pauta = (formulario.get('pauta') or '').strip() or None
    reuniao.deliberacoes = (formulario.get('deliberacoes') or '').strip() or None
    reuniao.participantes_externos = (formulario.get('participantes_externos') or '').strip() or None
    reuniao.contar_voluntariado = bool(formulario.get('contar_voluntariado'))
    reuniao.demanda_id = formulario.get('demanda_id', type=int) or None
    reuniao.empresa_id = empresa.id if empresa else None
    ids = [int(i) for i in formulario.getlist('participantes') if i.isdigit()]
    if empresa:
        # Com parceiro escolhido, só entram pessoas desse parceiro (a tela já filtra; aqui garante no servidor)
        do_parceiro = ids_do_parceiro(empresa)
        ids = [i for i in ids if i in do_parceiro]
    reuniao.participantes = Usuario.query.filter(Usuario.id.in_(ids or [-1]), Usuario.tipo_usuario != 'Aluno').all()

    # Encaminhamentos novos (linhas preenchidas no formulário)
    from models import EncaminhamentoReuniao
    for descricao, responsavel, prazo in zip(formulario.getlist('enc_descricao'), formulario.getlist('enc_responsavel'),
                                             formulario.getlist('enc_prazo')):
        if descricao.strip():
            try:
                data_prazo = datetime.strptime(prazo, "%Y-%m-%d").date() if prazo else None
            except ValueError:
                data_prazo = None
            reuniao.encaminhamentos.append(EncaminhamentoReuniao(
                descricao=descricao.strip(), responsavel_id=int(responsavel) if responsavel.isdigit() else None, prazo=data_prazo))
    return None


def pessoas_internas_reuniao():
    return Usuario.query.filter(Usuario.tipo_usuario != 'Aluno', Usuario.status == 'Ativo').order_by(Usuario.nome).all()


def empresas_da_reuniao(usuario, atual=None):
    """Parceiros B2B que a pessoa pode escolher na reunião: o Gestor B2B só as empresas que ele gerencia."""
    consulta = Empresa.query.filter(db.or_(Empresa.status.is_(None), Empresa.status != 'Inativa'))
    if usuario.tipo_usuario == 'Admin B2B':
        consulta = consulta.filter(Empresa.gestor_id == usuario.id)
    empresas = consulta.order_by(Empresa.nome).all()
    if atual is not None and atual not in empresas:
        empresas.append(atual)  # reunião antiga com parceiro hoje inativo continua editável
    return empresas


def ids_do_parceiro(empresa):
    """Quem pertence ao parceiro B2B: o gestor B2B da empresa, os mentores vinculados a ela
    e os avaliadores da banca cuja empresa de origem é ela."""
    from models import PerfilAvaliador
    ids = {m.id for m in empresa.mentores}
    if empresa.gestor_id:
        ids.add(empresa.gestor_id)
    ids |= {p.usuario_id for p in PerfilAvaliador.query.filter(
        db.func.lower(db.func.trim(PerfilAvaliador.empresa_origem)) == empresa.nome.strip().lower()).all()}
    return ids


# ------------------------------------------------------------------------------ convidados externos (sem conta)
def sincronizar_convidados_reuniao(reuniao):
    """Cada linha de "Participantes externos" vira um convidado com link pessoal (presença e avaliação sem login).
    Quem sai da lista perde o link; se já tinha presença ou avaliação, fica no histórico da reunião."""
    import convites_reuniao
    from models import ConvidadoReuniao
    chave = lambda c: (c.email or '').lower() or c.nome.strip().lower()
    atuais = {chave(c): c for c in reuniao.convidados}
    for pessoa in convites_reuniao.ler_externos(reuniao.participantes_externos):
        convidado = atuais.pop(pessoa['email'] or pessoa['nome'].strip().lower(), None)
        if convidado is None:
            convidado = ConvidadoReuniao(codigo=secrets.token_urlsafe(24))
            reuniao.convidados.append(convidado)
        convidado.nome, convidado.instituicao, convidado.email, convidado.na_lista = \
            pessoa['nome'], pessoa['instituicao'], pessoa['email'], True
    for sobra in atuais.values():
        if sobra.check_in or sobra.nota:
            sobra.na_lista = False
        else:
            reuniao.convidados.remove(sobra)


def garantir_convidados(reuniao):
    """Reuniões gravadas antes dos links pessoais: cria os convidados na primeira vez que a reunião é aberta."""
    if reuniao.participantes_externos and not reuniao.convidados:
        sincronizar_convidados_reuniao(reuniao)
        db.session.commit()


def link_convidado(convidado):
    return url_for('convidado_reuniao', codigo=convidado.codigo, _external=True)


def instituicao_do_participante(usuario, reuniao, parceiro_ids, apelido):
    """De que lado a pessoa está na reunião: o parceiro B2B da reunião, a empresa dela, ou a instituição."""
    if reuniao.empresa and usuario.id in parceiro_ids:
        return reuniao.empresa.nome
    if usuario.tipo_usuario == 'Admin B2B' and usuario.empresas_gerenciadas:
        return usuario.empresas_gerenciadas[0].nome
    if usuario.tipo_usuario != 'Aluno' and usuario.empresas_vinculadas:
        return usuario.empresas_vinculadas[0].nome
    return apelido


def tempo_investido_reuniao(reuniao):
    """Tempo que cada lado dedicou à reunião (check-in → check-out), somando participantes internos e convidados externos.
    Devolve ([{'instituicao', 'pessoas', 'minutos'}], total_minutos)."""
    apelido = identidade.obter()['apelido']
    parceiro_ids = ids_do_parceiro(reuniao.empresa) if reuniao.empresa else set()
    lados = {}

    def somar(instituicao, minutos):
        lado = lados.setdefault(instituicao, {'instituicao': instituicao, 'pessoas': 0, 'minutos': 0})
        lado['pessoas'] += 1
        lado['minutos'] += minutos or 0

    for p in reuniao.presencas:
        if p.check_out and p.usuario:
            somar(instituicao_do_participante(p.usuario, reuniao, parceiro_ids, apelido), p.total_minutos)
    for c in reuniao.convidados:
        if c.check_out:
            somar(c.instituicao or tt('Convidados externos', current_user.idioma if current_user.is_authenticated else 'pt'),
                  c.total_minutos)
    lista = sorted(lados.values(), key=lambda l: -l['minutos'])
    return lista, sum(l['minutos'] for l in lista)


def janela_checkin_reuniao(reuniao, agora=None):
    agora = agora or datetime.now()
    return reuniao.data_hora - timedelta(minutes=CHECKIN_REUNIAO_ANTES_MIN) <= agora \
        <= reuniao.fim_previsto + timedelta(minutes=CHECKIN_REUNIAO_DEPOIS_MIN)


def _convidado_por_codigo(codigo):
    from models import ConvidadoReuniao
    if not codigo or len(codigo) > 64:
        return None
    convidado = ConvidadoReuniao.query.filter_by(codigo=codigo).first()
    return convidado if convidado and convidado.na_lista and convidado.reuniao else None


@app.route('/reuniao/convidado/<codigo>', methods=['GET', 'POST'])
def convidado_reuniao(codigo):
    """Página do convidado externo (sem conta), aberta pelo link pessoal do convite: check-in, check-out e avaliação."""
    idioma = session.get('idioma', 'pt')
    convidado = _convidado_por_codigo(codigo)
    if convidado is None:
        return render_template('reuniao_convidado.html', convidado=None, reuniao=None, idioma=idioma), 404
    reuniao, agora = convidado.reuniao, datetime.now()
    voltar_pagina = redirect(url_for('convidado_reuniao', codigo=codigo))
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'checkin':
            if not janela_checkin_reuniao(reuniao, agora):
                flash(tt('O check-in abre 30 minutos antes da reunião e fecha 1 hora depois do fim previsto.', idioma), 'warning')
            elif convidado.check_in:
                flash(tt('Sua presença nesta reunião já foi registrada.', idioma), 'info')
            else:
                modalidade = request.form.get('modalidade')
                convidado.check_in = agora
                convidado.modalidade = modalidade if modalidade in ('Online', 'Presencial') else \
                    ('Online' if reuniao.modalidade == 'Online' else 'Presencial')
                db.session.commit()
                flash(tt('Check-in registrado. Não esqueça o check-out ao sair.', idioma), 'success')
        elif acao == 'checkout':
            if not convidado.check_in or convidado.check_out:
                flash(tt('Faça o check-in antes do check-out.', idioma), 'warning')
            else:
                fechar_presenca_reuniao(convidado, agora)
                db.session.commit()
                flash(tt('Check-out registrado: {minutos} minutos na reunião.', idioma).format(minutos=convidado.total_minutos), 'success')
        elif acao == 'avaliar':
            nota = request.form.get('nota', type=int)
            if agora < reuniao.data_hora:
                flash(tt('A avaliação abre quando a reunião começa.', idioma), 'warning')
            elif not nota or not AVALIACAO_NOTA_MINIMA <= nota <= AVALIACAO_NOTA_MAXIMA:
                flash(tt('Dê uma nota de 1 a 5.', idioma), 'warning')
            else:
                convidado.nota = nota
                convidado.comentario = (request.form.get('comentario') or '').strip()[:2000] or None
                convidado.avaliado_em = agora
                db.session.commit()
                flash(tt('Obrigado! Sua avaliação da reunião foi registrada.', idioma), 'success')
        return voltar_pagina
    return render_template('reuniao_convidado.html', convidado=convidado, reuniao=reuniao, idioma=idioma,
                           checkin_aberto=janela_checkin_reuniao(reuniao, agora), feedback_aberto=agora >= reuniao.data_hora)


@app.route('/reuniao/convidado/<codigo>/agenda.ics')
def agenda_convidado_reuniao(codigo):
    from flask import Response
    import convites_reuniao
    convidado = _convidado_por_codigo(codigo)
    if convidado is None:
        return ('', 404)
    conteudo = convites_reuniao.gerar_ics(convidado.reuniao, link_convidado(convidado))
    return Response(conteudo.encode('utf-8'), mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename=reuniao_{convidado.reuniao_id}.ics'})


@app.route('/reuniao/convidado/<codigo>/gravacao')
def gravacao_convidado_reuniao(codigo):
    convidado = _convidado_por_codigo(codigo)
    if convidado is None or not convidado.reuniao.gravacao_arquivo:
        return ('', 404)
    return _enviar_gravacao(convidado.reuniao)


# ------------------------------------------------------------------------------ arquivo da gravação
EXTENSOES_GRAVACAO = {'mp4', 'm4v', 'mov', 'webm', 'mkv', 'mp3', 'm4a', 'wav', 'ogg'}
PASTA_GRAVACOES = os.path.join(app.config['UPLOAD_FOLDER'], 'reunioes')


def _caminho_gravacao(reuniao):
    if not reuniao.gravacao_arquivo:
        return None
    caminho = os.path.realpath(os.path.join(PASTA_GRAVACOES, reuniao.gravacao_arquivo))
    return caminho if caminho.startswith(os.path.realpath(PASTA_GRAVACOES) + os.sep) and os.path.isfile(caminho) else None


def _enviar_gravacao(reuniao):
    import mimetypes
    caminho = _caminho_gravacao(reuniao)
    if not caminho:
        return ('', 404)
    tipo = mimetypes.guess_type(caminho)[0] or 'application/octet-stream'
    # conditional=True responde a pedidos parciais (Range): o vídeo toca no navegador sem baixar inteiro antes
    return send_file(caminho, mimetype=tipo, conditional=True, download_name=reuniao.gravacao_nome or os.path.basename(caminho))


def _apagar_arquivo_gravacao(reuniao):
    caminho = _caminho_gravacao(reuniao)
    if caminho:
        try:
            os.remove(caminho)
        except OSError:
            app.logger.warning("Não consegui apagar a gravação %s", caminho)
    reuniao.gravacao_arquivo = reuniao.gravacao_nome = reuniao.gravacao_tamanho = reuniao.gravacao_enviada_em = None


@app.route('/reunioes/<int:id>/gravacao', methods=['GET', 'POST'])
@login_required
def gravacao_reuniao(id):
    """GET: participantes e gestão assistem/baixam a gravação. POST: a gestão envia (ou exclui) o arquivo da gravação."""
    from models import ReuniaoInstitucional
    from regras_negocio import regra
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao or not pode_ver_reuniao(current_user, reuniao):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    if request.method == 'GET':
        return _enviar_gravacao(reuniao)
    idioma = current_user.idioma
    voltar_reuniao = redirect(url_for('detalhe_reuniao', id=reuniao.id) + '#cardGravacao')
    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        flash("Acesso negado.", "danger")
        return voltar_reuniao
    if request.form.get('acao') == 'excluir':
        if reuniao.gravacao_arquivo:
            _apagar_arquivo_gravacao(reuniao)
            db.session.commit()
            flash(tt('Arquivo da gravação excluído.', idioma), 'info')
        return voltar_reuniao
    arquivo = request.files.get('arquivo')
    extensao = arquivo.filename.rsplit('.', 1)[-1].lower() if arquivo and '.' in (arquivo.filename or '') else ''
    if not arquivo or not arquivo.filename:
        flash(tt('Escolha o arquivo da gravação.', idioma), 'warning')
        return voltar_reuniao
    if extensao not in EXTENSOES_GRAVACAO:
        flash(tt('Formato não aceito. Envie vídeo (MP4, MOV, WEBM, MKV) ou áudio (MP3, M4A, WAV, OGG).', idioma), 'warning')
        return voltar_reuniao
    os.makedirs(PASTA_GRAVACOES, exist_ok=True)
    nome_salvo = f"reuniao_{reuniao.id}_{secrets.token_hex(8)}.{extensao}"
    caminho = os.path.join(PASTA_GRAVACOES, nome_salvo)
    arquivo.save(caminho)
    tamanho = os.path.getsize(caminho)
    limite = int(regra('gravacao_reuniao_limite_mb')) * 1024 * 1024
    if tamanho == 0 or tamanho > limite:
        os.remove(caminho)
        flash(tt('O arquivo passa do limite de {mb} MB.', idioma).format(mb=limite // (1024 * 1024)) if tamanho else
              tt('O arquivo está vazio.', idioma), 'warning')
        return voltar_reuniao
    _apagar_arquivo_gravacao(reuniao)
    reuniao.gravacao_arquivo, reuniao.gravacao_tamanho, reuniao.gravacao_enviada_em = nome_salvo, tamanho, datetime.now()
    reuniao.gravacao_nome = (secure_filename(arquivo.filename) or nome_salvo)[:255]
    db.session.commit()
    flash(tt('Gravação enviada: os participantes já podem assistir.', idioma), 'success')
    return voltar_reuniao


app.config.setdefault('LIMITES_UPLOAD_ROTA', {})['gravacao_reuniao'] = lambda: regra('gravacao_reuniao_limite_mb')


@app.errorhandler(413)
def arquivo_grande_demais(_erro):
    limite = request.max_content_length or app.config.get('MAX_CONTENT_LENGTH') or 0
    idioma = current_user.idioma if current_user.is_authenticated else session.get('idioma', 'pt')
    flash(tt('O arquivo passa do limite de {mb} MB.', idioma).format(mb=limite // (1024 * 1024)), 'warning')
    return redirect(seguranca_web.destino_interno(request.referrer, url_for('dashboard')))


@app.route('/reunioes')
@login_required
def reunioes():
    from models import ReuniaoInstitucional
    consulta = ReuniaoInstitucional.query
    inicio = request.args.get('data_inicio')
    fim = request.args.get('data_fim')
    if inicio:
        consulta = consulta.filter(db.func.date(ReuniaoInstitucional.data_hora) >= inicio)
    if fim:
        consulta = consulta.filter(db.func.date(ReuniaoInstitucional.data_hora) <= fim)
    lista = [r for r in consulta.order_by(ReuniaoInstitucional.data_hora.desc()).all() if pode_ver_reuniao(current_user, r)]
    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES and not lista:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('reunioes.html', reunioes=lista, filtro_inicio=inicio, filtro_fim=fim,
                           pode_criar=current_user.tipo_usuario in PERFIS_GESTAO_REUNIOES, hoje=datetime.now().date())


@app.route('/reunioes/nova', methods=['GET', 'POST'])
@app.route('/reunioes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_reuniao(id=None):
    from models import ReuniaoInstitucional, DemandaInstitucional
    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    reuniao = db.session.get(ReuniaoInstitucional, id) if id else None
    if id and not reuniao:
        return redirect(url_for('reunioes'))

    if request.method == 'POST':
        from models import ReuniaoAlteracao
        nova = reuniao is None
        if nova:
            reuniao = ReuniaoInstitucional(criado_por_id=current_user.id)
        antes = None if nova else {'data': reuniao.data_hora, 'duracao': reuniao.duracao_minutos,
                                   'modalidade': reuniao.modalidade, 'local': reuniao.local_ou_link}
        erro = salvar_reuniao_do_formulario(reuniao, request.form, current_user)
        if erro:
            flash(t(erro, current_user.idioma), "warning")
            return redirect(url_for('editar_reuniao', id=id))
        sincronizar_convidados_reuniao(reuniao)
        mudancas = descrever_mudancas_reuniao(antes, reuniao) if antes else []
        alteracao = None
        if mudancas:
            alteracao = ReuniaoAlteracao(autor_id=current_user.id, mudancas='\n'.join(mudancas),
                                         motivo=(request.form.get('motivo_alteracao') or '').strip()[:1000] or None)
            reuniao.alteracoes.append(alteracao)
        db.session.add(reuniao)
        db.session.flush()
        sincronizar_voluntariado_reuniao(reuniao)
        db.session.commit()
        if alteracao:
            notificar([p for p in reuniao.participantes if p.id != current_user.id],
                      ('notif_reuniao_alterada_titulo', {'titulo': reuniao.titulo}),
                      ('notif_reuniao_alterada_msg', {'autor': current_user.nome, 'mudancas': '; '.join(mudancas),
                                                      'motivo': alteracao.motivo or '—'}),
                      link=url_for('detalhe_reuniao', id=reuniao.id), tipo='reuniao',
                      referencia=f"reuniao-alterada:{reuniao.id}:{alteracao.id}")
            if reuniao.convite_enviado_em and not request.form.get('enviar_convite'):
                import convites_reuniao
                if reuniao.convite_enviado_via == 'Microsoft 365' and conta_microsoft(current_user):
                    via = 'microsoft'
                elif reuniao.convite_enviado_via == 'Gmail' and session.get('gmail_token'):
                    via = 'gmail'
                else:
                    via = 'smtp' if convites_reuniao.smtp_configurado() else None
                if via:
                    categoria, texto = enviar_convite_reuniao(reuniao, via)
                    flash(tt('Convite atualizado reenviado automaticamente.', current_user.idioma) + ' ' + texto, categoria)
                else:
                    flash(tt('A reunião mudou: reenvie o convite para atualizar a agenda dos participantes.', current_user.idioma), 'info')
        if nova:
            notificar([p for p in reuniao.participantes if p.id != current_user.id],
                      ('notif_reuniao_titulo', {'titulo': reuniao.titulo}),
                      ('notif_reuniao_msg', {'autor': current_user.nome, 'data': reuniao.data_hora.strftime('%d/%m/%Y %H:%M')}),
                      link=url_for('detalhe_reuniao', id=reuniao.id), tipo='reuniao', referencia=f"reuniao:{reuniao.id}")
        flash(t('reuniao_salva', current_user.idioma), "success")
        if request.form.get('enviar_convite'):
            categoria, texto = enviar_convite_reuniao(reuniao, request.form.get('convite_via'))
            flash(texto, categoria)
        return redirect(url_for('detalhe_reuniao', id=reuniao.id))

    demanda = db.session.get(DemandaInstitucional, request.args.get('demanda_id', type=int) or 0)
    demandas = DemandaInstitucional.query.order_by(DemandaInstitucional.data_criacao.desc()).limit(100).all()
    empresas = empresas_da_reuniao(current_user, reuniao.empresa if reuniao else None)
    membros = {e.id: ids_do_parceiro(e) for e in empresas}
    # Para cada pessoa, os parceiros B2B a que ela pertence (o filtro da tela usa isto)
    pessoas = pessoas_internas_reuniao()
    parceiros_da_pessoa = {p.id: [eid for eid, ids in membros.items() if p.id in ids] for p in pessoas}
    return render_template('reuniao_form.html', reuniao=reuniao, pessoas=pessoas,
                           demandas=demandas, demanda_inicial=demanda, empresas=empresas, parceiros_da_pessoa=parceiros_da_pessoa,
                           tipos_reuniao=TIPOS_REUNIAO, **opcoes_envio_convite())


@app.route('/reunioes/<int:id>', methods=['GET', 'POST'])
@login_required
def detalhe_reuniao(id):
    from models import ReuniaoInstitucional, EncaminhamentoReuniao
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao or not pode_ver_reuniao(current_user, reuniao):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Responsável pelo encaminhamento ou gestão marcam como concluído / reabrem
        enc = db.session.get(EncaminhamentoReuniao, request.form.get('encaminhamento_id', type=int) or 0)
        if enc and enc.reuniao_id == reuniao.id and (current_user.tipo_usuario in PERFIS_GESTAO_REUNIOES or enc.responsavel_id == current_user.id):
            concluir = enc.status != 'Concluído'
            enc.status = 'Concluído' if concluir else 'Pendente'
            enc.data_conclusao = datetime.utcnow() if concluir else None
            db.session.commit()
            flash(t('reuniao_enc_atualizado', current_user.idioma), "success")
        return redirect(url_for('detalhe_reuniao', id=reuniao.id))

    garantir_convidados(reuniao)
    notas = [f.nota for f in reuniao.feedbacks] + [c.nota for c in reuniao.convidados if c.nota]
    media_feedback = round(sum(notas) / len(notas), 1) if notas else None
    tempo_lados, tempo_total = tempo_investido_reuniao(reuniao)
    imprimir = request.args.get('imprimir') == '1'
    if imprimir:
        return render_template('reuniao_ata.html', reuniao=reuniao, hoje=datetime.now().date(),
                               pode_editar=current_user.tipo_usuario in PERFIS_GESTAO_REUNIOES,
                               media_feedback=media_feedback, total_avaliacoes=len(notas), tempo_lados=tempo_lados,
                               tempo_total=tempo_total)
    import convites_reuniao
    validos, ignorados = convites_reuniao.destinatarios(reuniao, session.get('gmail_email'))
    link = url_for('detalhe_reuniao', id=reuniao.id, _external=True)
    agora = datetime.now()
    participante = current_user in reuniao.participantes
    ultima_alteracao = reuniao.alteracoes[0].criado_em if reuniao.alteracoes else None
    return render_template('reuniao_detalhe.html', reuniao=reuniao, hoje=datetime.now().date(),
                           pode_editar=current_user.tipo_usuario in PERFIS_GESTAO_REUNIOES,
                           participante=participante, tempo_lados=tempo_lados, tempo_total=tempo_total,
                           total_avaliacoes=len(notas), link_convidado=link_convidado,
                           gravacao_limite_mb=int(regra('gravacao_reuniao_limite_mb')),
                           extensoes_gravacao=sorted(EXTENSOES_GRAVACAO),
                           minha_presenca=next((p for p in reuniao.presencas if p.usuario_id == current_user.id), None),
                           meu_feedback=next((f for f in reuniao.feedbacks if f.usuario_id == current_user.id), None),
                           checkin_aberto=janela_checkin_reuniao(reuniao, agora),
                           feedback_aberto=agora >= reuniao.data_hora,
                           media_feedback=media_feedback,
                           reenviar_convite=bool(reuniao.convite_enviado_em and ultima_alteracao
                                                 and ultima_alteracao > reuniao.convite_enviado_em + (datetime.now() - datetime.utcnow())),
                           links_agenda=convites_reuniao.links_agenda(reuniao, link, url_for('agenda_reuniao_ics', id=reuniao.id)),
                           provedores=convites_reuniao.PROVEDORES, convidados=validos, convidados_ignorados=ignorados,
                           convite_enviado_local=(reuniao.convite_enviado_em - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
                           if reuniao.convite_enviado_em else '', **opcoes_envio_convite())


def descrever_mudancas_reuniao(antes, reuniao):
    """Linhas do histórico de alterações: data/hora, duração, modalidade e local/link."""
    mudancas = []
    if antes['data'] != reuniao.data_hora:
        mudancas.append(f"Data: {antes['data']:%d/%m/%Y %H:%M} → {reuniao.data_hora:%d/%m/%Y %H:%M}")
    if antes['duracao'] != reuniao.duracao_minutos:
        mudancas.append(f"Duração: {antes['duracao']} → {reuniao.duracao_minutos} min")
    if (antes['modalidade'] or '') != (reuniao.modalidade or ''):
        mudancas.append(f"Modalidade: {antes['modalidade'] or '—'} → {reuniao.modalidade}")
    if (antes['local'] or '') != (reuniao.local_ou_link or ''):
        mudancas.append(f"Local/link: {antes['local'] or '—'} → {reuniao.local_ou_link or '—'}")
    return mudancas


@app.route('/reunioes/<int:id>/presenca', methods=['POST'])
@login_required
def presenca_reuniao(id):
    """Check-in/check-out do participante; a gestão registra ou remove a presença de quem esqueceu."""
    from models import ReuniaoInstitucional, PresencaReuniao
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao or not pode_ver_reuniao(current_user, reuniao):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    idioma, agora, acao = current_user.idioma, datetime.now(), request.form.get('acao')
    voltar = redirect(url_for('detalhe_reuniao', id=reuniao.id) + '#cardPresenca')
    modalidade = request.form.get('modalidade') if request.form.get('modalidade') in ('Online', 'Presencial') else \
        ('Online' if reuniao.modalidade == 'Online' else 'Presencial')

    if acao in ('checkin', 'checkout'):
        if current_user not in reuniao.participantes:
            flash(tt('Só os participantes da reunião registram presença.', idioma), 'warning')
            return voltar
        presenca = next((p for p in reuniao.presencas if p.usuario_id == current_user.id), None)
        if acao == 'checkin':
            if not (reuniao.data_hora - timedelta(minutes=CHECKIN_REUNIAO_ANTES_MIN) <= agora
                    <= reuniao.fim_previsto + timedelta(minutes=CHECKIN_REUNIAO_DEPOIS_MIN)):
                flash(tt('O check-in abre 30 minutos antes da reunião e fecha 1 hora depois do fim previsto.', idioma), 'warning')
            elif presenca:
                flash(tt('Sua presença nesta reunião já foi registrada.', idioma), 'info')
            else:
                reuniao.presencas.append(PresencaReuniao(usuario_id=current_user.id, check_in=agora, modalidade=modalidade))
                db.session.commit()
                flash(tt('Check-in registrado. Não esqueça o check-out ao sair.', idioma), 'success')
        elif not presenca or presenca.check_out:
            flash(tt('Faça o check-in antes do check-out.', idioma), 'warning')
        else:
            fechar_presenca_reuniao(presenca, agora)
            sincronizar_voluntariado_reuniao(reuniao)
            db.session.commit()
            flash(tt('Check-out registrado: {minutos} minutos na reunião.', idioma).format(minutos=presenca.total_minutos), 'success')
        return voltar

    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES or acao not in ('manual', 'remover'):
        flash("Acesso negado.", "danger")
        return voltar
    # A lista da tela mistura participantes internos ("u12") e convidados externos ("c5"); usuario_id/convidado_id também valem
    pessoa = request.form.get('pessoa') or ''
    usuario_id = int(pessoa[1:]) if pessoa[:1] == 'u' and pessoa[1:].isdigit() else request.form.get('usuario_id', type=int)
    convidado_id = int(pessoa[1:]) if pessoa[:1] == 'c' and pessoa[1:].isdigit() else request.form.get('convidado_id', type=int)
    convidado = next((c for c in reuniao.convidados if c.id == convidado_id), None) if convidado_id else None
    try:
        dia = reuniao.data_hora.date()
        entrada = datetime.combine(dia, datetime.strptime(request.form.get('entrada') or '', '%H:%M').time())
        saida = datetime.combine(dia, datetime.strptime(request.form.get('saida') or '', '%H:%M').time())
    except ValueError:
        entrada = saida = None
    periodo_invalido = not entrada or saida <= entrada or saida - entrada > timedelta(hours=12) or saida > agora + timedelta(minutes=5)
    if convidado_id:
        if convidado is None:
            flash(tt('Escolha um participante da reunião.', idioma), 'warning')
        elif acao == 'remover':
            convidado.check_in = convidado.check_out = None
            convidado.total_minutos, convidado.registro_manual, convidado.checkout_automatico = 0, False, False
            db.session.commit()
            flash(tt('Presença removida.', idioma), 'info')
        elif periodo_invalido:
            flash(tt('Informe a entrada e a saída (a saída depois da entrada e nada no futuro).', idioma), 'warning')
        else:
            convidado.check_in, convidado.modalidade = entrada, modalidade
            fechar_presenca_reuniao(convidado, saida)
            convidado.registro_manual, convidado.registrado_por_id = True, current_user.id
            db.session.commit()
            flash(tt('Presença de {nome} registrada pela gestão.', idioma).format(nome=convidado.nome), 'success')
        return voltar
    usuario = db.session.get(Usuario, usuario_id or 0)
    if not usuario or usuario not in reuniao.participantes:
        flash(tt('Escolha um participante interno da reunião.', idioma), 'warning')
        return voltar
    presenca = next((p for p in reuniao.presencas if p.usuario_id == usuario.id), None)
    if acao == 'remover':
        if presenca:
            reuniao.presencas.remove(presenca)
            sincronizar_voluntariado_reuniao(reuniao)
            db.session.commit()
            flash(tt('Presença removida.', idioma), 'info')
        return voltar
    if periodo_invalido:
        flash(tt('Informe a entrada e a saída (a saída depois da entrada e nada no futuro).', idioma), 'warning')
        return voltar
    if presenca is None:
        presenca = PresencaReuniao(usuario_id=usuario.id, check_in=entrada)
        reuniao.presencas.append(presenca)
    presenca.check_in, presenca.modalidade = entrada, modalidade
    fechar_presenca_reuniao(presenca, saida)
    presenca.registro_manual, presenca.registrado_por_id = True, current_user.id
    sincronizar_voluntariado_reuniao(reuniao)
    db.session.commit()
    flash(tt('Presença de {nome} registrada pela gestão.', idioma).format(nome=usuario.nome), 'success')
    return voltar


@app.route('/reunioes/<int:id>/feedback', methods=['POST'])
@login_required
def feedback_reuniao(id):
    """Cada participante avalia a reunião (nota de 1 a 5 e comentário) a partir do início; pode corrigir depois."""
    from models import ReuniaoInstitucional, FeedbackReuniao
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao or not pode_ver_reuniao(current_user, reuniao):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    idioma = current_user.idioma
    voltar = redirect(url_for('detalhe_reuniao', id=reuniao.id) + '#cardFeedback')
    nota = request.form.get('nota', type=int)
    if current_user not in reuniao.participantes:
        flash(tt('Só os participantes avaliam a reunião.', idioma), 'warning')
    elif datetime.now() < reuniao.data_hora:
        flash(tt('A avaliação abre quando a reunião começa.', idioma), 'warning')
    elif not nota or not AVALIACAO_NOTA_MINIMA <= nota <= AVALIACAO_NOTA_MAXIMA:
        flash(tt('Dê uma nota de 1 a 5.', idioma), 'warning')
    else:
        feedback = next((f for f in reuniao.feedbacks if f.usuario_id == current_user.id), None)
        if feedback is None:
            feedback = FeedbackReuniao(usuario_id=current_user.id, nota=nota)
            reuniao.feedbacks.append(feedback)
        feedback.nota = nota
        feedback.comentario = (request.form.get('comentario') or '').strip()[:2000] or None
        db.session.commit()
        flash(tt('Obrigado! Sua avaliação da reunião foi registrada.', idioma), 'success')
    return voltar


# ------------------------------------------------------------------------------ convites por e-mail e agenda
def opcoes_envio_convite():
    """Como o convite pode sair: pelo Gmail conectado nesta sessão e/ou pelo SMTP da plataforma."""
    import convites_reuniao
    import microsoft365
    import credenciais_agentes
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    conta = conta_microsoft(current_user)
    return {'gmail_email': session.get('gmail_email') if session.get('gmail_token') else None,
            'gmail_disponivel': os.path.exists(os.path.join(app.root_path, 'client_secret.json')),
            'smtp_disponivel': convites_reuniao.smtp_configurado(),
            'microsoft_email': conta.email if conta else None, 'microsoft_disponivel': microsoft365.configurado()}


def conta_microsoft(usuario):
    from models import ContaConectada
    return ContaConectada.query.filter_by(usuario_id=usuario.id, provedor='microsoft').first() if usuario and usuario.is_authenticated else None


def agenda_conectada():
    """Agenda em que a pessoa salva prazos e sessões: 'microsoft', 'google' ou None."""
    if current_user.is_authenticated and conta_microsoft(current_user):
        return 'microsoft'
    return 'google' if session.get('google_token') else None


app.jinja_env.globals.update(agenda_conectada=agenda_conectada, conta_microsoft_atual=lambda: conta_microsoft(current_user))


def token_microsoft(usuario):
    import microsoft365
    import credenciais_agentes
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    return microsoft365.token_valido(db, conta_microsoft(usuario), app.config['SECRET_KEY'])


def enviar_convite_microsoft(reuniao, emails_escolhidos=None):
    """Cria (ou atualiza) a reunião como evento na agenda do Outlook de quem organiza: o próprio Outlook envia o convite
    aos participantes, com aceitar/recusar, e as atualizações. Reunião on-line sem link ganha sala do Teams."""
    import convites_reuniao
    import microsoft365
    idioma = current_user.idioma
    conta = conta_microsoft(current_user)
    token = token_microsoft(current_user)
    if not token:
        return 'warning', tt('Conecte sua conta Microsoft 365 (lista Contas conectadas) para enviar pelo Outlook.', idioma)
    validos, ignorados = convites_reuniao.destinatarios(reuniao, conta.email if conta else None)
    if emails_escolhidos is not None:
        escolhidos = {e.strip().lower() for e in emails_escolhidos}
        validos = [c for c in validos if c[1] in escolhidos]
    if not validos:
        return 'warning', t('convite_sem_destinatarios', idioma)
    inicio, fim = convites_reuniao.inicio_fim(reuniao)
    link = url_for('detalhe_reuniao', id=reuniao.id, _external=True)
    online = reuniao.modalidade in ('Online', 'Híbrido') and not (reuniao.local_ou_link or '').startswith('http')
    evento = microsoft365.montar_evento(reuniao.titulo, convites_reuniao.descricao(reuniao, link), inicio, fim,
                                        reuniao.local_ou_link, validos, reuniao_online=online)
    try:
        if reuniao.outlook_evento_id and reuniao.outlook_organizador_id == current_user.id:
            resposta = microsoft365.atualizar_evento(token, reuniao.outlook_evento_id, evento)
        else:
            resposta = microsoft365.criar_evento(token, evento)
    except microsoft365.ErroMicrosoft as erro:
        app.logger.warning("Convite da reunião %s não enviado pelo Microsoft 365: %s (%s)", reuniao.id, erro, erro.codigo)
        return 'danger', t('convite_falha_envio', idioma)
    reuniao.outlook_evento_id = resposta.get('id') or reuniao.outlook_evento_id
    reuniao.outlook_organizador_id = current_user.id
    sala = ((resposta.get('onlineMeeting') or {}).get('joinUrl') or '').strip()
    if sala and not reuniao.local_ou_link:
        reuniao.local_ou_link = sala[:500]
    reuniao.convite_sequencia = (reuniao.convite_sequencia or 0) + (1 if reuniao.convite_enviado_em else 0)
    reuniao.convite_enviado_em = datetime.utcnow()
    reuniao.convite_enviado_via = 'Microsoft 365'
    reuniao.convite_destinatarios = '\n'.join(email for _, email in validos)
    db.session.commit()
    texto = t('convite_enviado', idioma).format(qtd=len(validos), via='Microsoft 365 (Outlook)')
    if sala:
        texto += ' ' + tt('Sala do Teams criada e gravada na reunião.', idioma)
    texto += ' ' + enviar_links_pessoais(reuniao, validos)
    if ignorados:
        texto += ' ' + t('convite_ignorados', idioma).format(qtd=len(ignorados))
    return 'success', texto


def enviar_links_pessoais(reuniao, validos):
    """O Outlook manda o mesmo texto a todos: o link pessoal dos convidados externos segue num e-mail curto à parte
    (pelo e-mail da plataforma). Sem e-mail da plataforma, a gestão copia o link de cada um na página da reunião."""
    import convites_reuniao
    idioma = current_user.idioma
    garantir_convidados(reuniao)
    escolhidos = {email for _, email in validos}
    externos = [c for c in reuniao.convidados if c.na_lista and c.email in escolhidos]
    if not externos:
        return ''
    if not convites_reuniao.smtp_configurado():
        return tt('Copie o link pessoal de cada convidado externo no quadro Presença e envie a ele.', idioma)
    remetente = (f"{current_user.nome} · {convites_reuniao.remetente_smtp()[0]}", convites_reuniao.remetente_smtp()[1])
    enviados = 0
    for convidado in externos:
        try:
            mensagem = convites_reuniao.montar_email_link_pessoal(reuniao, remetente, convidado.nome, convidado.email,
                                                                  link_convidado(convidado))
            if current_user.email:
                mensagem['Reply-To'] = current_user.email
            convites_reuniao.enviar_smtp(mensagem)
            enviados += 1
        except Exception as erro:
            app.logger.warning("Link pessoal da reunião %s não enviado a %s: %s", reuniao.id, convidado.email, erro)
    return tt('{qtd} convidado(s) externo(s) receberam o link pessoal de presença.', idioma).format(qtd=enviados)


def enviar_convite_reuniao(reuniao, via, emails_escolhidos=None):
    """Envia o convite (.ics) aos participantes. Devolve (categoria do flash, mensagem já traduzida)."""
    import convites_reuniao
    idioma = current_user.idioma
    if via == 'microsoft':
        return enviar_convite_microsoft(reuniao, emails_escolhidos)
    if via == 'gmail':
        if not session.get('gmail_token'):
            return 'warning', t('convite_gmail_nao_conectado', idioma)
        remetente = (current_user.nome, session.get('gmail_email') or current_user.email)
    elif via == 'smtp':
        if not convites_reuniao.smtp_configurado():
            return 'warning', t('convite_smtp_nao_configurado', idioma)
        remetente = (f"{current_user.nome} · {convites_reuniao.remetente_smtp()[0]}", convites_reuniao.remetente_smtp()[1])
    else:
        return 'warning', t('convite_escolha_envio', idioma)

    validos, ignorados = convites_reuniao.destinatarios(reuniao, remetente[1])
    if emails_escolhidos is not None:
        escolhidos = {e.strip().lower() for e in emails_escolhidos}
        validos = [c for c in validos if c[1] in escolhidos]
    if not validos:
        return 'warning', t('convite_sem_destinatarios', idioma)

    atualizacao = reuniao.convite_enviado_em is not None
    reuniao.convite_sequencia = (reuniao.convite_sequencia or 0) + (1 if atualizacao else 0)
    link = url_for('detalhe_reuniao', id=reuniao.id, _external=True)
    # Participantes da plataforma recebem um e-mail juntos; cada convidado externo recebe o seu, com o link pessoal
    # de presença e avaliação (o mesmo evento: as agendas não duplicam).
    garantir_convidados(reuniao)
    externos = {c.email: c for c in reuniao.convidados if c.email and c.na_lista}
    internos = [c for c in validos if c[1] not in externos]
    mensagens = []
    if internos:
        mensagens.append(convites_reuniao.montar_email(reuniao, remetente, validos, link,
                                                       url_for('agenda_reuniao_ics', id=reuniao.id, _external=True), atualizacao,
                                                       para=internos))
    for nome, email in validos:
        if email in externos:
            convidado = externos[email]
            mensagens.append(convites_reuniao.montar_email(
                reuniao, remetente, validos, None, url_for('agenda_convidado_reuniao', codigo=convidado.codigo, _external=True),
                atualizacao, para=[(nome, email)], link_pessoal=link_convidado(convidado)))
    for mensagem in mensagens:
        if via == 'smtp' and current_user.email:
            mensagem['Reply-To'] = current_user.email
    try:
        if via == 'gmail':
            credenciais = convites_reuniao.credenciais_gmail(session['gmail_token'], session.get('gmail_refresh_token'),
                                                             os.path.join(app.root_path, 'client_secret.json'))
            for mensagem in mensagens:
                convites_reuniao.enviar_gmail(mensagem, credenciais)
            if credenciais.token and credenciais.token != session['gmail_token']:
                session['gmail_token'] = credenciais.token  # o Google renovou o acesso
        else:
            for mensagem in mensagens:
                convites_reuniao.enviar_smtp(mensagem)
    except Exception as erro:
        db.session.rollback()
        app.logger.warning("Convite da reunião %s não enviado (%s): %s", reuniao.id, via, erro)
        if via == 'gmail' and any(p in str(erro).lower() for p in ('invalid_grant', 'unauthorized', '401', '403', 'insufficient')):
            for chave in ('gmail_token', 'gmail_refresh_token', 'gmail_email'):
                session.pop(chave, None)
            return 'warning', t('convite_gmail_reconectar', idioma)
        return 'danger', t('convite_falha_envio', idioma)

    reuniao.convite_enviado_em = datetime.utcnow()
    reuniao.convite_enviado_via = 'Gmail' if via == 'gmail' else 'SMTP'
    reuniao.convite_destinatarios = '\n'.join(email for _, email in validos)
    db.session.commit()
    texto = t('convite_enviado', idioma).format(qtd=len(validos), via=reuniao.convite_enviado_via)
    if ignorados:
        texto += ' ' + t('convite_ignorados', idioma).format(qtd=len(ignorados))
    return 'success', texto


@app.route('/reunioes/<int:id>/agenda.ics')
@login_required
def agenda_reuniao_ics(id):
    """Arquivo para salvar a reunião em qualquer agenda (Outlook, Apple, Thunderbird, Yahoo, Google...)."""
    from flask import Response
    from models import ReuniaoInstitucional
    import convites_reuniao
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao or not pode_ver_reuniao(current_user, reuniao):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    conteudo = convites_reuniao.gerar_ics(reuniao, url_for('detalhe_reuniao', id=reuniao.id, _external=True))
    return Response(conteudo.encode('utf-8'), mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename=reuniao_{reuniao.id}.ics'})


@app.route('/reunioes/<int:id>/convite', methods=['POST'])
@login_required
def enviar_convite(id):
    from models import ReuniaoInstitucional
    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    reuniao = db.session.get(ReuniaoInstitucional, id)
    if not reuniao:
        return redirect(url_for('reunioes'))
    categoria, texto = enviar_convite_reuniao(reuniao, request.form.get('via'), request.form.getlist('convidados'))
    flash(texto, categoria)
    return redirect(url_for('detalhe_reuniao', id=reuniao.id))


@app.route('/conectar-gmail')
@login_required
def conectar_gmail():
    """Conecta o Gmail da pessoa só para ENVIAR convites (permissão gmail.send: não lê a caixa de entrada)."""
    import convites_reuniao
    if current_user.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    caminho_secreto = os.path.join(app.root_path, 'client_secret.json')
    if not os.path.exists(caminho_secreto):
        flash(t('gmail_sem_configuracao', current_user.idioma), "warning")
        return redirect(seguranca_web.destino_interno(request.args.get('voltar'), url_for('reunioes')))
    flow = Flow.from_client_secrets_file(caminho_secreto, scopes=convites_reuniao.SCOPES_GMAIL,
                                         redirect_uri=url_for('oauth2callback', _external=True))
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='false',
                                                      prompt='consent select_account')
    session['state'] = state
    session['code_verifier'] = flow.code_verifier
    session['oauth_destino'] = 'gmail'
    session['oauth_voltar'] = seguranca_web.destino_interno(request.args.get('voltar'), url_for('reunioes'))
    return redirect(authorization_url)


@app.route('/conectar-microsoft')
@login_required
def conectar_microsoft():
    """Login oficial da Microsoft (OAuth 2.0 + PKCE). A senha fica com a Microsoft; a plataforma guarda só os tokens, cifrados."""
    import microsoft365
    import credenciais_agentes
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    voltar_para = seguranca_web.destino_interno(request.args.get('voltar'), url_for('dashboard'))
    if not microsoft365.configurado():
        flash(tt('A conexão com o Microsoft 365 ainda não foi configurada pelo Administrador.', current_user.idioma), 'warning')
        return redirect(voltar_para)
    verificador, desafio = microsoft365.novo_pkce()
    estado = secrets.token_urlsafe(24)
    session['ms_state'], session['ms_verificador'], session['ms_voltar'] = estado, verificador, voltar_para
    return redirect(microsoft365.url_login(url_for('oauth_microsoft', _external=True), estado, desafio, current_user.email))


@app.route('/oauth-microsoft/callback')
@login_required
def oauth_microsoft():
    import hmac
    import microsoft365
    import credenciais_agentes
    from models import ContaConectada
    idioma = current_user.idioma
    estado, verificador = session.pop('ms_state', None), session.pop('ms_verificador', None)
    voltar_para = seguranca_web.destino_interno(session.pop('ms_voltar', None), url_for('dashboard'))
    recebido = request.args.get('state') or ''
    if not estado or not verificador or not hmac.compare_digest(estado, recebido):
        flash(tt('Conexão com o Microsoft 365 recusada: a resposta não corresponde ao pedido. Tente de novo.', idioma), 'danger')
        return redirect(voltar_para)
    if request.args.get('error'):
        descricao = (request.args.get('error_description') or '').lower()
        if request.args.get('error') == 'consent_required' or 'admin' in descricao or 'aadsts65001' in descricao or 'aadsts90094' in descricao:
            flash(tt('A empresa precisa aprovar o aplicativo: peça ao administrador do Microsoft 365 o consentimento (veja o guia).', idioma), 'warning')
        else:
            flash(tt('Conexão com o Microsoft 365 cancelada.', idioma), 'info')
        return redirect(voltar_para)
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    try:
        tokens = microsoft365.trocar_codigo(request.args.get('code') or '', url_for('oauth_microsoft', _external=True), verificador)
        nome, email = microsoft365.quem_sou(tokens['access_token'])
    except microsoft365.ErroMicrosoft as erro:
        app.logger.warning("Conexão com o Microsoft 365 não concluída: %s (%s)", erro, erro.codigo)
        flash(tt('Não foi possível concluir a conexão com o Microsoft 365. Tente de novo.', idioma), 'warning')
        return redirect(voltar_para)
    microsoft365.salvar_conta(db, ContaConectada, current_user.id, tokens, nome, email, app.config['SECRET_KEY'])
    flash(tt('Microsoft 365 conectado: {email}.', idioma).format(email=email or nome), 'success')
    return redirect(voltar_para)


@app.route('/desconectar-microsoft', methods=['POST'])
@login_required
def desconectar_microsoft():
    from models import ContaConectada
    ContaConectada.query.filter_by(usuario_id=current_user.id, provedor='microsoft').delete()
    db.session.commit()
    flash(tt('Microsoft 365 desconectado.', current_user.idioma), 'info')
    return redirect(seguranca_web.destino_interno(request.form.get('voltar'), url_for('dashboard')))


@app.route('/desconectar-gmail', methods=['POST'])
@login_required
def desconectar_gmail():
    for chave in ('gmail_token', 'gmail_refresh_token', 'gmail_email'):
        session.pop(chave, None)
    flash(t('gmail_desconectado', current_user.idioma), "info")
    return voltar('reunioes')


def encaminhamentos_atrasados(usuario):
    """Encaminhamentos pendentes com prazo vencido que a pessoa deve acompanhar."""
    from models import EncaminhamentoReuniao
    consulta = EncaminhamentoReuniao.query.filter(EncaminhamentoReuniao.status == 'Pendente',
                                                  EncaminhamentoReuniao.prazo < datetime.now().date())
    if usuario.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        consulta = consulta.filter(EncaminhamentoReuniao.responsavel_id == usuario.id)
    return consulta.all()


# ==============================================================================
# ACOMPANHAMENTO DOS JOVENS: DESISTÊNCIAS E OCORRÊNCIAS (pedidos da reunião de alinhamento com a B2B)
# ==============================================================================
PERFIS_GESTAO_INSTITUICAO = ['Administrador', 'Mentor Administrador']
PERFIS_DECIDEM_DESISTENCIA = PERFIS_GESTAO_INSTITUICAO + ['Admin B2B']      # decidem desistências de jovens e mentores
PERFIS_VEEM_RESULTADOS_AVALIACAO = PERFIS_GESTAO_INSTITUICAO + ['Admin B2B'] # resultados e alertas das avaliações 360°
PERFIS_EQUIPE = ['Administrador', 'Mentor Administrador', 'Admin B2B', 'Mentor', 'Professor']
CATEGORIAS_DESISTENCIA = ['Pessoal', 'Estudos', 'Trabalho', 'Saúde', 'Mudança de cidade', 'Sem interesse', 'Outro']
CATEGORIAS_OCORRENCIA = ['Progresso', 'Comportamento', 'Frequência', 'Entregas', 'Comunicação', 'Outro']
CONTEXTOS_OCORRENCIA = ['Sala de aula', 'Palestra', 'Mentoria', 'Banca', 'Online', 'Outro']
GRAVIDADES_OCORRENCIA = ['Baixa', 'Média', 'Alta']


def _somente_equipe():
    if current_user.tipo_usuario not in PERFIS_EQUIPE:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return None


def pode_ver_jovem(usuario, aluno):
    visiveis = ids_jovens_visiveis(usuario)
    return aluno is not None and (visiveis is None or aluno.id in visiveis)


def jovens_da_equipe(usuario, incluir_desistentes=False):
    """Jovens que a pessoa acompanha (gestão da instituição: todos)."""
    consulta = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno')
    if not incluir_desistentes:
        consulta = consulta.filter(Usuario.status != 'Desistente')
    visiveis = ids_jovens_visiveis(usuario)
    if visiveis is not None:
        consulta = consulta.filter(Usuario.id.in_(visiveis or [-1]))
    return consulta.order_by(Usuario.nome).all()


def equipe_ativa():
    """Quem pode ser responsável por responder uma ocorrência: equipe da instituição e B2B ativa (sem jovens e sem avaliadores)."""
    return Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_EQUIPE), Usuario.status == 'Ativo').order_by(Usuario.nome).all()


def empresas_do_jovem(aluno):
    return sorted({t.empresa_id for t in (aluno.turmas_como_aluno or []) if t.empresa_id})


def gestores_b2b_das_empresas(ids_empresas):
    return [e.gestor for e in Empresa.query.filter(Empresa.id.in_(ids_empresas or [-1])).all() if e.gestor]


def gestao_itm_ativa():
    return Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_GESTAO_INSTITUICAO), Usuario.status == 'Ativo').all()


# ------------------------------------------------------------------------------ desistências
def pode_decidir_desistencia(usuario, desistencia):
    """Confirma, recusa ou reativa: gestão da instituição, ou o gestor B2B da empresa do jovem."""
    if usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO:
        return True
    if usuario.tipo_usuario == 'Admin B2B':
        geridas = {e.id for e in usuario.empresas_gerenciadas or []}
        return bool(geridas & set(json.loads(desistencia.empresas or '[]')))
    return False


def desistencias_visiveis(usuario):
    from models import Desistencia
    todas = Desistencia.query.order_by(Desistencia.solicitado_em.desc()).all()
    if usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO:
        return todas
    visiveis = ids_jovens_visiveis(usuario) or set()
    def ve(d):
        vinc = json.loads(d.vinculos or '{}')
        return (d.solicitado_por_id == usuario.id or d.usuario_id in visiveis or usuario.id in vinc.get('mentores', [])
                or d.substituto_id == usuario.id or pode_decidir_desistencia(usuario, d))
    return [d for d in todas if ve(d)]


def confirmar_desistencia(desistencia, usuario, observacao=''):
    """O jovem sai dos grupos, turmas e mentores (guardados para uma reativação), deixa de entrar na plataforma,
    de contar na frequência e nos indicadores e não recebe certificado. Avisa mentores, gestor B2B e gestão da instituição."""
    aluno = desistencia.usuario
    vinculos = {'grupos': [g.id for g in aluno.grupos], 'turmas': [t.id for t in aluno.turmas_como_aluno],
                'mentores': [m.id for m in aluno.mentores]}
    mentores = list(aluno.mentores)
    for grupo in list(aluno.grupos):
        grupo.membros.remove(aluno)
    for turma in list(aluno.turmas_como_aluno):
        turma.alunos.remove(aluno)
    aluno.mentores = []
    aluno.status = 'Desistente'
    desistencia.vinculos = json.dumps(vinculos)
    desistencia.status, desistencia.decidido_por_id, desistencia.decidido_em = 'Confirmada', usuario.id, datetime.utcnow()
    desistencia.observacao_decisao = observacao or None
    db.session.commit()
    avisados = mentores + gestores_b2b_das_empresas(json.loads(desistencia.empresas or '[]')) + gestao_itm_ativa()
    notificar([p for p in avisados if p.id != usuario.id], ('notif_desistencia_titulo', {'nome': aluno.nome}),
              ('notif_desistencia_msg', {'nome': aluno.nome, 'data': desistencia.data_saida.strftime('%d/%m/%Y'), 'categoria': desistencia.categoria}),
              link=url_for('desistencias'), tipo='desistencia', referencia=f"desistencia:{desistencia.id}",
              por_email=not eh_conta_de_teste(aluno))


def reativar_jovem(desistencia, usuario):
    """Volta o jovem aos mesmos grupos, turmas e mentores (os que ainda existem) e libera o acesso."""
    from models import Grupo as _Grupo
    aluno = desistencia.usuario
    vinculos = json.loads(desistencia.vinculos or '{}')
    for grupo in _Grupo.query.filter(_Grupo.id.in_(vinculos.get('grupos') or [-1])).all():
        if aluno not in grupo.membros:
            grupo.membros.append(aluno)
    for turma in Turma.query.filter(Turma.id.in_(vinculos.get('turmas') or [-1])).all():
        if aluno not in turma.alunos:
            turma.alunos.append(aluno)
    for mentor in Usuario.query.filter(Usuario.id.in_(vinculos.get('mentores') or [-1])).all():
        if mentor not in aluno.mentores:
            aluno.mentores.append(mentor)
    aluno.status = 'Ativo'
    desistencia.status, desistencia.revertido_por_id, desistencia.revertido_em = 'Revertida', usuario.id, datetime.utcnow()
    db.session.commit()


@app.route('/desistencias', methods=['GET', 'POST'])
@login_required
def desistencias():
    from models import Desistencia
    bloqueio = _somente_equipe()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    if request.method == 'POST':
        aluno = db.session.get(Usuario, request.form.get('aluno_id', type=int) or 0)
        categoria = request.form.get('categoria')
        motivo = (request.form.get('motivo') or '').strip()
        try:
            data_saida = datetime.strptime(request.form.get('data_saida') or '', '%Y-%m-%d').date()
        except ValueError:
            data_saida = None
        if not aluno or aluno.tipo_usuario != 'Aluno' or not pode_ver_jovem(current_user, aluno):
            flash(tt('Escolha um jovem que você acompanha.', idioma), 'warning')
        elif aluno.status == 'Desistente' or Desistencia.query.filter_by(usuario_id=aluno.id, status='Solicitada').first():
            flash(tt('Este jovem já tem uma desistência registrada.', idioma), 'warning')
        elif categoria not in CATEGORIAS_DESISTENCIA or len(motivo) < MINIMO_CARACTERES_DESCRICAO or not data_saida or data_saida > datetime.now().date():
            flash(tt('Informe a data de saída (até hoje), o motivo (mínimo de 10 caracteres) e a categoria.', idioma), 'warning')
        else:
            pedido = Desistencia(usuario_id=aluno.id, categoria=categoria, motivo=motivo[:2000], data_saida=data_saida,
                                 solicitado_por_id=current_user.id, empresas=json.dumps(empresas_do_jovem(aluno)))
            db.session.add(pedido)
            db.session.commit()
            if pode_decidir_desistencia(current_user, pedido) and request.form.get('confirmar_agora'):
                confirmar_desistencia(pedido, current_user, 'Registrada e confirmada pela gestão.')
                flash(tt('Desistência registrada e confirmada: o jovem saiu do grupo e da turma.', idioma), 'success')
            else:
                confirmadores = gestores_b2b_das_empresas(json.loads(pedido.empresas)) + gestao_itm_ativa()
                notificar([p for p in confirmadores if p.id != current_user.id], ('notif_desistencia_pedido_titulo', {'nome': aluno.nome}),
                          ('notif_desistencia_pedido_msg', {'autor': current_user.nome, 'nome': aluno.nome}),
                          link=url_for('desistencias'), tipo='desistencia', referencia=f"desistencia-pedido:{pedido.id}",
                          por_email=not eh_conta_de_teste(aluno))
                flash(tt('Pedido de desistência registrado: a gestão foi avisada para confirmar.', idioma), 'success')
        return redirect(url_for('desistencias'))
    lista = desistencias_visiveis(current_user)
    geridos = mentores_geridos(current_user)
    substitutos = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_MENTORIA), Usuario.status == 'Ativo').order_by(Usuario.nome).all() \
        if geridos else []
    return render_template('desistencias.html', desistencias=lista, jovens=[j for j in jovens_da_equipe(current_user)],
                           mentores_geridos=geridos, substitutos=substitutos,
                           categorias=CATEGORIAS_DESISTENCIA, hoje=datetime.now().date(),
                           pode_decidir=lambda d: pode_decidir_desistencia(current_user, d),
                           decide_algo=current_user.tipo_usuario in PERFIS_DECIDEM_DESISTENCIA)


PERFIS_MENTOR_SUBSTITUIVEL = ['Mentor', 'Professor']


def mentores_geridos(usuario):
    """Mentores que a pessoa pode registrar como desistentes: gestão da instituição, todos; gestor B2B, os das suas empresas."""
    consulta = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_MENTOR_SUBSTITUIVEL), Usuario.status == 'Ativo')
    if usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO:
        return consulta.order_by(Usuario.nome).all()
    if usuario.tipo_usuario == 'Admin B2B':
        ids = {m.id for e in (usuario.empresas_gerenciadas or []) for m in e.mentores}
        return consulta.filter(Usuario.id.in_(ids or [-1])).order_by(Usuario.nome).all()
    return []


def substituir_mentor(mentor, substituto):
    """Passa ao substituto os jovens, grupos, turmas, empresas e sessões futuras do mentor.
    As horas de voluntariado já lançadas continuam no nome de quem as fez. Devolve o que foi transferido."""
    vinculos = {'jovens': [], 'grupos': [], 'turmas': [], 'empresas': [], 'sessoes_futuras': []}
    for aluno in list(mentor.alunos):
        aluno.mentores.remove(mentor)
        if substituto not in aluno.mentores:
            aluno.mentores.append(substituto)
        vinculos['jovens'].append(aluno.id)
    for grupo in list(mentor.grupos or []):
        grupo.membros.remove(mentor)
        if substituto not in grupo.membros:
            grupo.membros.append(substituto)
        vinculos['grupos'].append(grupo.id)
    for turma in list(mentor.turmas_como_mentor or []):
        turma.mentores.remove(mentor)
        if substituto not in turma.mentores:
            turma.mentores.append(substituto)
        vinculos['turmas'].append(turma.id)
    for empresa in list(mentor.empresas_vinculadas or []):
        empresa.mentores.remove(mentor)
        if substituto not in empresa.mentores:
            empresa.mentores.append(substituto)
        vinculos['empresas'].append(empresa.id)
    for sessao in SessaoMentoria.query.filter(SessaoMentoria.mentor_id == mentor.id, SessaoMentoria.data_sessao > datetime.now()).all():
        sessao.mentor_id = substituto.id
        vinculos['sessoes_futuras'].append(sessao.id)
    return vinculos


@app.route('/desistencias/mentor', methods=['POST'])
@login_required
def desistencia_mentor():
    """Mentor desistente: a gestão da instituição (ou o gestor B2B da empresa) registra a saída e escolhe o substituto,
    que assume na hora os jovens, grupos, turmas e sessões futuras. O histórico e as horas ficam guardados."""
    from models import Desistencia
    idioma = current_user.idioma
    voltar = redirect(url_for('desistencias') + '#mentorDesistente')
    if current_user.tipo_usuario not in PERFIS_DECIDEM_DESISTENCIA:
        flash("Acesso negado.", "danger")
        return voltar
    geridos = {m.id: m for m in mentores_geridos(current_user)}
    mentor = geridos.get(request.form.get('mentor_id', type=int) or 0)
    substituto = db.session.get(Usuario, request.form.get('substituto_id', type=int) or 0)
    categoria, motivo = request.form.get('categoria'), (request.form.get('motivo') or '').strip()
    try:
        data_saida = datetime.strptime(request.form.get('data_saida') or '', '%Y-%m-%d').date()
    except ValueError:
        data_saida = None
    precisa_substituto = mentor is not None and (mentor.alunos.count() or mentor.grupos or mentor.turmas_como_mentor)
    if not mentor:
        flash(tt('Escolha um mentor que você gerencia.', idioma), 'warning')
    elif substituto is not None and (substituto.id == mentor.id or substituto.status != 'Ativo'
                                     or substituto.tipo_usuario not in PERFIS_MENTORIA):
        flash(tt('O substituto precisa ser outro mentor ativo.', idioma), 'warning')
    elif precisa_substituto and substituto is None:
        flash(tt('Este mentor acompanha jovens ou grupos: escolha quem vai substituí-lo.', idioma), 'warning')
    elif categoria not in CATEGORIAS_DESISTENCIA or len(motivo) < MINIMO_CARACTERES_DESCRICAO or not data_saida or data_saida > datetime.now().date():
        flash(tt('Informe a data de saída (até hoje), o motivo (mínimo de 10 caracteres) e a categoria.', idioma), 'warning')
    else:
        empresas = sorted({e.id for e in (mentor.empresas_vinculadas or [])})
        vinculos = substituir_mentor(mentor, substituto) if substituto else {}
        mentor.status = 'Desistente'
        registro = Desistencia(usuario_id=mentor.id, categoria=categoria, motivo=motivo[:2000], data_saida=data_saida, status='Confirmada',
                               solicitado_por_id=current_user.id, decidido_por_id=current_user.id, decidido_em=datetime.utcnow(),
                               substituto_id=substituto.id if substituto else None, vinculos=json.dumps(vinculos), empresas=json.dumps(empresas))
        db.session.add(registro)
        db.session.commit()
        jovens = Usuario.query.filter(Usuario.id.in_(vinculos.get('jovens') or [-1])).all()
        teste = eh_conta_de_teste(mentor)
        if substituto:
            notificar([substituto], ('notif_mentor_substituto_titulo', {'nome': mentor.nome}),
                      ('notif_mentor_substituto_msg', {'nome': mentor.nome, 'jovens': len(jovens), 'grupos': len(vinculos.get('grupos', []))}),
                      link=url_for('sessoes'), tipo='desistencia', referencia=f"mentor-substituto:{registro.id}", por_email=not teste)
            notificar(jovens, ('notif_novo_mentor_titulo', {'nome': substituto.nome}),
                      ('notif_novo_mentor_msg', {'nome': substituto.nome, 'anterior': mentor.nome}),
                      link=url_for('sessoes'), tipo='desistencia', referencia=f"novo-mentor:{registro.id}", por_email=not teste)
        avisados = [p for p in gestores_b2b_das_empresas(empresas) + gestao_itm_ativa() if p.id != current_user.id]
        notificar(avisados, ('notif_desistencia_titulo', {'nome': mentor.nome}),
                  ('notif_desistencia_msg', {'nome': mentor.nome, 'data': data_saida.strftime('%d/%m/%Y'), 'categoria': categoria}),
                  link=url_for('desistencias'), tipo='desistencia', referencia=f"desistencia:{registro.id}", por_email=not teste)
        flash(tt('Mentor desligado. {nome} assumiu {jovens} jovem(ns) e {grupos} grupo(s).', idioma).format(
            nome=substituto.nome if substituto else '—', jovens=len(jovens), grupos=len(vinculos.get('grupos', []))), 'success')
    return voltar


@app.route('/desistencias/<int:id>/decidir', methods=['POST'])
@login_required
def decidir_desistencia(id):
    from models import Desistencia
    bloqueio = _somente_equipe()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    desistencia = db.session.get(Desistencia, id)
    if not desistencia or not pode_decidir_desistencia(current_user, desistencia):
        flash("Acesso negado.", "danger")
        return redirect(url_for('desistencias'))
    acao, observacao = request.form.get('acao'), (request.form.get('observacao') or '').strip()[:1000]
    if acao == 'confirmar' and desistencia.status == 'Solicitada':
        confirmar_desistencia(desistencia, current_user, observacao)
        flash(tt('Desistência confirmada: o jovem saiu do grupo e da turma.', idioma), 'success')
    elif acao == 'recusar' and desistencia.status == 'Solicitada':
        desistencia.status, desistencia.decidido_por_id, desistencia.decidido_em = 'Recusada', current_user.id, datetime.utcnow()
        desistencia.observacao_decisao = observacao or None
        db.session.commit()
        if desistencia.solicitado_por:
            notificar([desistencia.solicitado_por], ('notif_desistencia_recusada_titulo', {'nome': desistencia.usuario.nome}),
                      ('notif_desistencia_recusada_msg', {'nome': desistencia.usuario.nome, 'obs': observacao or '—'}),
                      link=url_for('desistencias'), tipo='desistencia', referencia=f"desistencia-recusa:{desistencia.id}",
                      por_email=not eh_conta_de_teste(desistencia.usuario))
        flash(tt('Pedido de desistência recusado.', idioma), 'info')
    elif acao == 'reativar' and desistencia.status == 'Confirmada' and desistencia.usuario.tipo_usuario != 'Aluno':
        # Mentor volta a ter acesso e às empresas; os jovens continuam com o substituto (a gestão redistribui se quiser)
        mentor = desistencia.usuario
        for empresa in Empresa.query.filter(Empresa.id.in_(json.loads(desistencia.empresas or '[]') or [-1])).all():
            if mentor not in empresa.mentores:
                empresa.mentores.append(mentor)
        mentor.status = 'Ativo'
        desistencia.status, desistencia.revertido_por_id, desistencia.revertido_em = 'Revertida', current_user.id, datetime.utcnow()
        db.session.commit()
        flash(tt('Mentor reativado. Os jovens continuam com o substituto; redistribua em Cadastros, se quiser.', idioma), 'success')
    elif acao == 'reativar' and desistencia.status == 'Confirmada':
        reativar_jovem(desistencia, current_user)
        flash(tt('Jovem reativado: voltou aos grupos, turmas e mentores de antes.', idioma), 'success')
    return redirect(url_for('desistencias'))


# ------------------------------------------------------------------------------ ocorrências
def pode_ver_ocorrencia(usuario, ocorrencia):
    if usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO or usuario.id in (ocorrencia.registrado_por_id, ocorrencia.responsavel_id):
        return True
    return usuario.tipo_usuario in PERFIS_EQUIPE and pode_ver_jovem(usuario, ocorrencia.aluno)


def pode_tratar_ocorrencia(usuario, ocorrencia):
    """Mudar o status (inclusive resolver): o responsável, quem registrou e a gestão da instituição."""
    return usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO or usuario.id in (ocorrencia.registrado_por_id, ocorrencia.responsavel_id)


def sinal_ocorrencia(ocorrencia, hoje=None):
    """Sinal de pendência de retorno: vermelho (prazo vencido sem retorno do responsável), amarelo (vencendo),
    azul (responsável já respondeu, em tratativa), cinza (aguardando, no prazo), verde (resolvida)."""
    from regras_negocio import regra
    hoje = hoje or datetime.now().date()
    if ocorrencia.status == 'Resolvida':
        return {'chave': 'resolvida', 'cor': 'success', 'texto': 'Resolvida'}
    respondeu = any(r.autor_id == ocorrencia.responsavel_id and r.tipo in ('Retorno', 'Ação') for r in ocorrencia.registros)
    if respondeu:
        return {'chave': 'em_tratativa', 'cor': 'primary', 'texto': 'Em tratativa'}
    if ocorrencia.prazo_resposta < hoje:
        return {'chave': 'atrasada', 'cor': 'danger', 'texto': 'Retorno atrasado'}
    if (ocorrencia.prazo_resposta - hoje).days <= int(regra('ocorrencia_alerta_dias')):
        return {'chave': 'vence', 'cor': 'warning', 'texto': 'Retorno vence em breve'}
    return {'chave': 'aguardando', 'cor': 'secondary', 'texto': 'Aguardando retorno'}


def ocorrencias_visiveis(usuario):
    from models import Ocorrencia
    return [o for o in Ocorrencia.query.order_by(Ocorrencia.criado_em.desc()).all() if pode_ver_ocorrencia(usuario, o)]


def ocorrencias_pendentes_para(usuario):
    """Para o alerta do painel: abertas com retorno atrasado ou vencendo que a pessoa precisa olhar."""
    if usuario.tipo_usuario not in PERFIS_EQUIPE:
        return []
    saida = []
    for o in ocorrencias_visiveis(usuario):
        sinal = sinal_ocorrencia(o)
        if sinal['chave'] in ('atrasada', 'vence') and (usuario.tipo_usuario in PERFIS_GESTAO_INSTITUICAO
                                                       or usuario.id in (o.responsavel_id, o.registrado_por_id)):
            saida.append((o, sinal))
    return saida


def _avisar_ocorrencia(ocorrencia, autor, titulo, mensagem, referencia):
    pessoas = [ocorrencia.responsavel, ocorrencia.registrado_por] + list(ocorrencia.aluno.mentores) + \
        gestores_b2b_das_empresas(empresas_do_jovem(ocorrencia.aluno)) + [r.autor for r in ocorrencia.registros]
    notificar([p for p in pessoas if p and p.id != autor.id and p.status == 'Ativo'], titulo, mensagem,
              link=url_for('detalhe_ocorrencia', id=ocorrencia.id), tipo='ocorrencia', referencia=referencia,
              por_email=not eh_conta_de_teste(ocorrencia.aluno))


@app.route('/ocorrencias')
@login_required
def ocorrencias():
    bloqueio = _somente_equipe()
    if bloqueio:
        return bloqueio
    hoje = datetime.now().date()
    lista = [(o, sinal_ocorrencia(o, hoje)) for o in ocorrencias_visiveis(current_user)]
    contagem = {c: sum(1 for _, s in lista if s['chave'] == c) for c in ('atrasada', 'vence', 'aguardando', 'em_tratativa', 'resolvida')}
    filtro = request.args.get('sinal', 'abertas')
    if filtro == 'abertas':
        lista = [(o, s) for o, s in lista if s['chave'] != 'resolvida']
    elif filtro in contagem:
        lista = [(o, s) for o, s in lista if s['chave'] == filtro]
    aluno_id = request.args.get('aluno_id', type=int)
    if aluno_id:
        lista = [(o, s) for o, s in lista if o.aluno_id == aluno_id]
    ordem = {'atrasada': 0, 'vence': 1, 'aguardando': 2, 'em_tratativa': 3, 'resolvida': 4}
    lista.sort(key=lambda par: (ordem[par[1]['chave']], par[0].prazo_resposta))
    return render_template('ocorrencias.html', ocorrencias=lista, contagem=contagem, filtro=filtro, aluno_id=aluno_id,
                           jovens=jovens_da_equipe(current_user, incluir_desistentes=True))


@app.route('/ocorrencias/nova', methods=['GET', 'POST'])
@login_required
def nova_ocorrencia():
    from models import Ocorrencia
    from regras_negocio import regra
    bloqueio = _somente_equipe()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    if request.method == 'POST':
        f = request.form
        aluno = db.session.get(Usuario, f.get('aluno_id', type=int) or 0)
        responsavel = db.session.get(Usuario, f.get('responsavel_id', type=int) or 0)
        descricao = (f.get('descricao') or '').strip()
        try:
            prazo = datetime.strptime(f.get('prazo_resposta') or '', '%Y-%m-%d').date()
        except ValueError:
            prazo = None
        if not aluno or aluno.tipo_usuario != 'Aluno' or not pode_ver_jovem(current_user, aluno):
            flash(tt('Escolha um jovem que você acompanha.', idioma), 'warning')
        elif not responsavel or responsavel.tipo_usuario not in PERFIS_EQUIPE or responsavel.status != 'Ativo':
            flash(tt('Escolha quem deve dar o retorno (equipe {apelido} ou B2B).', idioma), 'warning')
        elif (f.get('categoria') not in CATEGORIAS_OCORRENCIA or f.get('contexto') not in CONTEXTOS_OCORRENCIA
              or f.get('gravidade') not in GRAVIDADES_OCORRENCIA or len(descricao) < MINIMO_CARACTERES_DESCRICAO or not prazo or prazo < datetime.now().date()):
            flash(tt('Preencha categoria, contexto, gravidade, o que foi observado (mínimo de 10 caracteres) e um prazo a partir de hoje.', idioma), 'warning')
        else:
            ocorrencia = Ocorrencia(aluno_id=aluno.id, registrado_por_id=current_user.id, categoria=f['categoria'], contexto=f['contexto'],
                                    gravidade=f['gravidade'], descricao=descricao[:4000], acoes=(f.get('acoes') or '').strip()[:4000] or None,
                                    responsavel_id=responsavel.id, prazo_resposta=prazo)
            db.session.add(ocorrencia)
            db.session.commit()
            _avisar_ocorrencia(ocorrencia, current_user, ('notif_ocorrencia_titulo', {'nome': aluno.nome, 'categoria': ocorrencia.categoria}),
                               ('notif_ocorrencia_msg', {'autor': current_user.nome, 'responsavel': responsavel.nome,
                                                         'prazo': prazo.strftime('%d/%m/%Y')}), f"ocorrencia:{ocorrencia.id}")
            flash(tt('Ocorrência registrada: o responsável e quem acompanha o jovem foram avisados.', idioma), 'success')
            return redirect(url_for('detalhe_ocorrencia', id=ocorrencia.id))
    prazo_padrao = datetime.now().date() + timedelta(days=int(regra('ocorrencia_prazo_dias')))
    return render_template('ocorrencia_form.html', jovens=jovens_da_equipe(current_user), equipe=equipe_ativa(),
                           categorias=CATEGORIAS_OCORRENCIA, contextos=CONTEXTOS_OCORRENCIA, gravidades=GRAVIDADES_OCORRENCIA,
                           prazo_padrao=prazo_padrao, aluno_inicial=request.args.get('aluno_id', type=int), hoje=datetime.now().date())


@app.route('/ocorrencias/<int:id>', methods=['GET', 'POST'])
@login_required
def detalhe_ocorrencia(id):
    from models import Ocorrencia, OcorrenciaRegistro
    bloqueio = _somente_equipe()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    ocorrencia = db.session.get(Ocorrencia, id)
    if not ocorrencia or not pode_ver_ocorrencia(current_user, ocorrencia):
        flash("Acesso negado.", "danger")
        return redirect(url_for('ocorrencias'))
    if request.method == 'POST':
        acao = request.form.get('acao')
        texto = (request.form.get('texto') or '').strip()[:4000]
        if acao == 'registrar':
            tipo = request.form.get('tipo') if request.form.get('tipo') in ('Retorno', 'Ação', 'Comentário') else 'Comentário'
            if len(texto) < MINIMO_CARACTERES_COMENTARIO or ocorrencia.status == 'Resolvida':
                flash(tt('Escreva o retorno (a ocorrência precisa estar aberta).', idioma), 'warning')
            else:
                db.session.add(OcorrenciaRegistro(ocorrencia_id=ocorrencia.id, autor_id=current_user.id, tipo=tipo, texto=texto))
                if current_user.id == ocorrencia.responsavel_id and ocorrencia.status == 'Aberta' and tipo in ('Retorno', 'Ação'):
                    ocorrencia.status = 'Em tratativa'
                db.session.commit()
                _avisar_ocorrencia(ocorrencia, current_user, ('notif_ocorrencia_registro_titulo', {'nome': ocorrencia.aluno.nome, 'tipo': tipo}),
                                   ('notif_ocorrencia_registro_msg', {'autor': current_user.nome, 'texto': texto[:200]}),
                                   f"ocorrencia-registro:{ocorrencia.id}:{len(ocorrencia.registros)}")
                flash(tt('Registro adicionado à ocorrência.', idioma), 'success')
        elif acao in ('resolver', 'reabrir') and pode_tratar_ocorrencia(current_user, ocorrencia):
            if acao == 'resolver' and len(texto) < MINIMO_CARACTERES_DESCRICAO:
                flash(tt('Para resolver, descreva o desfecho (mínimo de 10 caracteres).', idioma), 'warning')
            else:
                novo = 'Resolvida' if acao == 'resolver' else 'Em tratativa'
                ocorrencia.status = novo
                ocorrencia.resolvido_em = datetime.utcnow() if novo == 'Resolvida' else None
                db.session.add(OcorrenciaRegistro(ocorrencia_id=ocorrencia.id, autor_id=current_user.id, tipo='Status',
                                                  texto=f"{novo}: {texto}" if texto else novo))
                db.session.commit()
                _avisar_ocorrencia(ocorrencia, current_user, ('notif_ocorrencia_status_titulo', {'nome': ocorrencia.aluno.nome, 'status': novo}),
                                   ('notif_ocorrencia_status_msg', {'autor': current_user.nome, 'texto': texto[:200] or '—'}),
                                   f"ocorrencia-status:{ocorrencia.id}:{len(ocorrencia.registros)}")
                flash(tt('Ocorrência atualizada.', idioma), 'success')
        return redirect(url_for('detalhe_ocorrencia', id=ocorrencia.id))
    return render_template('ocorrencia_detalhe.html', ocorrencia=ocorrencia, sinal=sinal_ocorrencia(ocorrencia),
                           pode_tratar=pode_tratar_ocorrencia(current_user, ocorrencia))


# ==============================================================================
# AVALIAÇÕES 360° E MICROAVALIAÇÕES + ALERTAS DE RUÍDO DE COMUNICAÇÃO E DESENGAJAMENTO
# ==============================================================================
CRITERIOS_AVALIACAO = {
    'Mentor': ['Comunicação', 'Disponibilidade', 'Apoio no aprendizado', 'Pontualidade'],
    'Jovem': ['Comunicação', 'Engajamento', 'Entregas', 'Pontualidade'],
    'Gestor B2B': ['Comunicação', 'Organização', 'Apoio ao programa'],
    'Gestão {apelido}': ['Comunicação', 'Organização', 'Apoio ao programa'],  # chave gravada; a tela mostra a sigla cadastrada
    'Gestor {apelido}': ['Comunicação', 'Organização', 'Apoio ao programa', 'Disponibilidade'],  # cada pessoa da gestão do projeto
    'Programa': ['Conteúdo', 'Organização', 'Comunicação'],
}
# Microavaliação (quinzenal): rápida, só entre jovem e mentor
CRITERIOS_MICRO = {'Mentor': ['Clareza na Comunicação', 'Comprometimento', 'Postura', 'Evolução Técnica'],
                   'Jovem': ['Clareza na Comunicação', 'Comprometimento', 'Postura', 'Evolução Técnica']}
CRITERIOS_RUIDO = ('Comunicação', 'Clareza na Comunicação')
CRITERIOS_ENGAJAMENTO = ('Engajamento', 'Comprometimento')
TIPOS_CICLO = ['360', 'Micro']
PERFIS_MENTORIA = ['Mentor', 'Professor', 'Mentor Administrador']
JANELA_RESULTADOS_DIAS = 180
JANELA_ALERTAS_DIAS = 90


def criterios_do_alvo(ciclo, alvo_tipo):
    return (CRITERIOS_MICRO if ciclo.tipo == 'Micro' else CRITERIOS_AVALIACAO).get(alvo_tipo, [])


def _ativos(pessoas):
    return [p for p in pessoas if p is not None and p.status == 'Ativo']


def _na_empresa(pessoa, empresa_id):
    return empresa_id is None or any(e.id == empresa_id for e in empresas_parceiras(pessoa))


def mentores_com_jovens():
    return Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_MENTORIA), Usuario.status == 'Ativo', Usuario.alunos.any()).all()


def jovens_avaliaveis(usuario):
    """Jovens ativos e em turma que a gestão (instituição: todos; gestor B2B: os das suas empresas) avalia no 360°."""
    return sorted((j for j in jovens_da_equipe(usuario) if j.status == 'Ativo' and j.turmas_como_aluno), key=lambda j: j.nome)


def alvos_da_avaliacao(usuario, ciclo):
    """Quem (ou o quê) a pessoa avalia no ciclo: [(alvo_tipo, pessoa ou None)]. No 360° todos avaliam todos:
    jovem → mentores, gestor B2B, cada gestor da instituição, a gestão da instituição e o programa;
    mentor → jovens, gestor B2B, cada gestor da instituição, a gestão e o programa;
    gestor B2B → mentores e jovens da empresa, cada gestor da instituição, a gestão e o programa;
    gestão da instituição → mentores, jovens, gestores B2B, os outros gestores da instituição e o programa.
    Na microavaliação (quinzenal), só jovem ↔ mentor."""
    tipo, micro, empresa_id = usuario.tipo_usuario, ciclo.tipo == 'Micro', ciclo.empresa_id
    if usuario.status != 'Ativo' or tipo == 'Avaliador Banca':
        return []
    if tipo not in PERFIS_GESTAO_INSTITUICAO and not _na_empresa(usuario, empresa_id):
        return []
    alvos = []
    if tipo == 'Aluno':
        alvos += [('Mentor', m) for m in _ativos(list(usuario.mentores))]
        if not micro:
            alvos += [('Gestor B2B', g) for g in _ativos(gestores_b2b_das_empresas(empresas_do_jovem(usuario)))]
    elif tipo in PERFIS_VEEM_SO_SEUS_ALUNOS:
        alvos += [('Jovem', a) for a in _ativos(list(usuario.alunos))]
        if not micro:
            alvos += [('Gestor B2B', e.gestor) for e in (usuario.empresas_vinculadas or []) if e.gestor and e.gestor.status == 'Ativo']
    elif tipo == 'Admin B2B' and not micro:
        for empresa in Empresa.query.filter_by(gestor_id=usuario.id).all():
            alvos += [('Mentor', m) for m in _ativos(empresa.mentores)]
        alvos += [('Jovem', j) for j in jovens_avaliaveis(usuario)]
    elif tipo in PERFIS_GESTAO_INSTITUICAO and not micro:
        alvos += [('Mentor', m) for m in mentores_com_jovens()]
        alvos += [('Jovem', j) for j in jovens_avaliaveis(usuario)]
        alvos += [('Gestor B2B', e.gestor) for e in Empresa.query.filter(Empresa.gestor_id.isnot(None)).all()
                  if e.gestor and e.gestor.status == 'Ativo']
    if not micro:
        # Cada pessoa da gestão do projeto na instituição (o filtro de empresa do ciclo não vale para ela)
        # (contas dos agentes de teste só aparecem para outras contas de teste)
        alvos += [('Gestor {apelido}', g) for g in sorted(gestao_itm_ativa(), key=lambda g: g.nome)
                  if not eh_conta_de_teste(g) or eh_conta_de_teste(usuario)]
        if tipo not in PERFIS_GESTAO_INSTITUICAO:
            alvos.append(('Gestão {apelido}', None))
        alvos.append(('Programa', None))
    vistos, final = set(), []
    for alvo_tipo, pessoa in alvos:
        if pessoa is not None and (pessoa.id == usuario.id or (alvo_tipo != 'Gestor {apelido}' and not _na_empresa(pessoa, empresa_id))):
            continue
        chave = (alvo_tipo, pessoa.id if pessoa else None)
        if chave not in vistos:
            vistos.add(chave)
            final.append((alvo_tipo, pessoa))
    return final


def ciclos_abertos():
    from models import CicloAvaliacao
    hoje = datetime.now().date()
    return CicloAvaliacao.query.filter(CicloAvaliacao.encerrado_em.is_(None), CicloAvaliacao.inicio <= hoje,
                                       CicloAvaliacao.fim >= hoje).order_by(CicloAvaliacao.fim).all()


def respostas_do_avaliador(usuario, ciclo):
    from models import RespostaAvaliacao
    return {(r.alvo_tipo, r.avaliado_id): r for r in RespostaAvaliacao.query.filter_by(ciclo_id=ciclo.id, avaliador_id=usuario.id).all()}


def pendencias_avaliacao(usuario):
    """[(ciclo, alvo_tipo, pessoa)] ainda sem resposta nos ciclos abertos."""
    pendentes = []
    for ciclo in ciclos_abertos():
        feitas = respostas_do_avaliador(usuario, ciclo)
        pendentes += [(ciclo, a, p) for a, p in alvos_da_avaliacao(usuario, ciclo) if (a, p.id if p else None) not in feitas]
    return pendentes


def reunioes_sem_avaliacao(usuario, dias=14):
    """Reuniões instituição × B2B em que a pessoa esteve (check-out feito) e que ainda não avaliou."""
    from models import PresencaReuniao, FeedbackReuniao
    agora = datetime.now()
    avaliadas = {f.reuniao_id for f in FeedbackReuniao.query.filter_by(usuario_id=usuario.id).all()}
    lista = []
    for p in PresencaReuniao.query.filter(PresencaReuniao.usuario_id == usuario.id, PresencaReuniao.check_out.isnot(None)).all():
        r = p.reuniao
        if r and r.id not in avaliadas and agora - timedelta(days=dias) <= r.fim_previsto <= agora:
            lista.append(r)
    return sorted(lista, key=lambda r: r.data_hora, reverse=True)


def abrir_ciclo_avaliacao(ciclo):
    """Grava o ciclo e avisa quem tem algo a avaliar. Devolve quantas pessoas foram avisadas."""
    db.session.add(ciclo)
    db.session.commit()
    avaliadores = [u for u in Usuario.query.filter(Usuario.status == 'Ativo').all() if alvos_da_avaliacao(u, ciclo)]
    notificar(avaliadores, ('notif_avaliacao_titulo', {'titulo': ciclo.titulo}),
              ('notif_avaliacao_msg', {'fim': ciclo.fim.strftime('%d/%m/%Y')}),
              link='/avaliacoes', tipo='avaliacao', referencia=f"avaliacao-ciclo:{ciclo.id}",
              por_email=not eh_conta_de_teste(ciclo.criado_por))  # ciclo aberto pelos agentes de teste: só o sino
    return len(avaliadores)


def _agrupar_respostas(respostas, com_autor):
    grupos = {}
    for r in respostas:
        g = grupos.setdefault((r.alvo_tipo, r.avaliado_id), {'alvo_tipo': r.alvo_tipo, 'pessoa': r.avaliado, 'medias': [],
                                                             'criterios': {}, 'comentarios': []})
        g['medias'].append(r.media)
        for criterio, nota in json.loads(r.notas).items():
            g['criterios'].setdefault(criterio, []).append(nota)
        if r.comentario:
            g['comentarios'].append((r.comentario, r.avaliador.nome if com_autor and r.avaliador else None, r.ciclo.tipo))
    lista = []
    for g in grupos.values():
        g['n'] = len(g['medias'])
        g['media'] = round(sum(g['medias']) / g['n'], 1)
        g['criterios'] = {c: round(sum(v) / len(v), 1) for c, v in g['criterios'].items()}
        lista.append(g)
    return sorted(lista, key=lambda g: g['media'])


def ids_pessoas_da_empresa_gerida(usuario):
    """Gestor B2B: mentores das suas empresas, jovens das turmas delas e ele mesmo."""
    ids = set(ids_jovens_visiveis(usuario) or set()) | {usuario.id}
    for empresa in Empresa.query.filter_by(gestor_id=usuario.id).all():
        ids |= {m.id for m in empresa.mentores}
    return ids


def resultados_avaliacao(usuario):
    """Médias recebidas por pessoa/entidade nos últimos 180 dias, no escopo de quem vê (gestão da instituição e gestor B2B)."""
    from models import RespostaAvaliacao
    tipo = usuario.tipo_usuario
    if tipo not in PERFIS_VEEM_RESULTADOS_AVALIACAO:
        return []
    respostas = RespostaAvaliacao.query.filter(RespostaAvaliacao.criado_em >= datetime.now() - timedelta(days=JANELA_RESULTADOS_DIAS)).all()
    if tipo == 'Admin B2B':
        ids = ids_pessoas_da_empresa_gerida(usuario)
        respostas = [r for r in respostas if r.avaliado_id in ids or r.alvo_tipo == 'Programa']
    return _agrupar_respostas(respostas, com_autor=tipo in PERFIS_GESTAO_INSTITUICAO)


def avaliacoes_recebidas(usuario):
    """O que a própria pessoa recebeu (anônimo). Só aparece com o mínimo de respostas, para não identificar quem avaliou."""
    from models import RespostaAvaliacao
    from regras_negocio import regra
    respostas = RespostaAvaliacao.query.filter(RespostaAvaliacao.avaliado_id == usuario.id,
                                               RespostaAvaliacao.criado_em >= datetime.now() - timedelta(days=JANELA_RESULTADOS_DIAS)).all()
    minimo = int(regra('avaliacao_minimo_respostas', 2) or 1)
    if not respostas:
        return None
    if len(respostas) < minimo:
        return {'n': len(respostas), 'oculto': True, 'minimo': minimo}
    grupo = _agrupar_respostas(respostas, com_autor=False)
    return {'n': len(respostas), 'oculto': False, 'grupos': grupo}


def ultima_atividade(ids):
    """Último sinal de atividade de cada pessoa: login, frequência, aula, sessão, feedback, entrega, presença, voluntariado, avaliação."""
    from models import (Frequencia, CheckinAula, FeedbackSessao, PresencaAtividadeExtra, PresencaReuniao, SessaoMentoria,
                        CheckinVoluntariado, RespostaAvaliacao, EntregaTCC)
    ids = list(ids)
    if not ids:
        return {}
    agora = datetime.now()
    ultimo = {u.id: u.ultimo_acesso or u.data_criacao for u in Usuario.query.filter(Usuario.id.in_(ids)).all()}
    fontes = [(Frequencia.usuario_id, Frequencia.data_registro), (CheckinAula.usuario_id, CheckinAula.data_hora_entrada),
              (FeedbackSessao.autor_id, FeedbackSessao.data_envio), (PresencaAtividadeExtra.usuario_id, PresencaAtividadeExtra.check_in),
              (PresencaReuniao.usuario_id, PresencaReuniao.check_in), (SessaoMentoria.mentor_id, SessaoMentoria.data_sessao),
              (CheckinVoluntariado.usuario_id, CheckinVoluntariado.data_hora_inicio), (RespostaAvaliacao.avaliador_id, RespostaAvaliacao.criado_em),
              (EntregaTCC.enviado_por_id, EntregaTCC.data_envio)]
    for coluna_usuario, coluna_data in fontes:
        linhas = db.session.query(coluna_usuario, db.func.max(coluna_data)).filter(coluna_usuario.in_(ids), coluna_data <= agora) \
            .group_by(coluna_usuario).all()
        for usuario_id, quando in linhas:
            if quando and (ultimo.get(usuario_id) is None or quando > ultimo[usuario_id]):
                ultimo[usuario_id] = quando
    return ultimo


def alertas_acompanhamento(usuario):
    """Ruído de comunicação (média de 'Comunicação' abaixo do limite), engajamento baixo nas avaliações e
    desengajamento (dias sem nenhuma atividade). Escopo: gestão da instituição vê todos; gestor B2B, a sua empresa; mentor, os seus jovens."""
    from models import RespostaAvaliacao
    from regras_negocio import regra
    tipo = usuario.tipo_usuario
    if tipo not in PERFIS_EQUIPE:
        return []
    limite = float(regra('ruido_comunicacao_limite', 3.5))
    minimo = int(regra('avaliacao_minimo_respostas', 2) or 1)
    dias = int(regra('desengajamento_dias', 14))
    jovens = [j for j in jovens_da_equipe(usuario) if j.status == 'Ativo' and j.turmas_como_aluno]
    if tipo in PERFIS_GESTAO_INSTITUICAO:
        mentores = mentores_com_jovens()
    elif tipo == 'Admin B2B':
        mentores = [m for e in Empresa.query.filter_by(gestor_id=usuario.id).all() for m in _ativos(e.mentores)]
    else:
        mentores = []
    pessoas = {p.id: p for p in jovens + mentores if p.id != usuario.id}
    alertas = []
    respostas = RespostaAvaliacao.query.filter(RespostaAvaliacao.avaliado_id.in_(list(pessoas) or [-1]),
                                               RespostaAvaliacao.criado_em >= datetime.now() - timedelta(days=JANELA_ALERTAS_DIAS)).all()
    notas = {}
    for r in respostas:
        for criterio, nota in json.loads(r.notas).items():
            if criterio in CRITERIOS_RUIDO + CRITERIOS_ENGAJAMENTO:
                tipo_alerta = 'ruido' if criterio in CRITERIOS_RUIDO else 'engajamento'
                notas.setdefault((r.avaliado_id, tipo_alerta), []).append(nota)
    for (pessoa_id, tipo_alerta), valores in notas.items():
        media = sum(valores) / len(valores)
        if len(valores) >= minimo and media < limite:
            alertas.append({'tipo': tipo_alerta, 'pessoa': pessoas[pessoa_id],
                            'valor': round(media, 1), 'n': len(valores), 'cor': 'danger' if media < limite - 1 else 'warning'})
    agora = datetime.now()
    for pessoa_id, quando in ultima_atividade(pessoas).items():
        parado = (agora - quando).days if quando else None
        if parado is not None and parado >= dias:
            alertas.append({'tipo': 'inativo', 'pessoa': pessoas[pessoa_id], 'valor': parado, 'n': None,
                            'cor': 'danger' if parado >= 2 * dias else 'warning'})
    return sorted(alertas, key=lambda a: (a['cor'] != 'danger', a['pessoa'].nome))


@app.route('/avaliacoes')
@login_required
def avaliacoes():
    from models import CicloAvaliacao
    pendentes = []  # (ciclo, alvo_tipo, pessoa, resposta já dada ou None)
    for ciclo in ciclos_abertos():
        feitas = respostas_do_avaliador(current_user, ciclo)
        for alvo_tipo, pessoa in alvos_da_avaliacao(current_user, ciclo):
            pendentes.append((ciclo, alvo_tipo, pessoa, feitas.get((alvo_tipo, pessoa.id if pessoa else None))))
    gestao = current_user.tipo_usuario in PERFIS_GESTAO_INSTITUICAO
    ciclos = CicloAvaliacao.query.order_by(CicloAvaliacao.inicio.desc()).limit(30).all() \
        if current_user.tipo_usuario in PERFIS_VEEM_RESULTADOS_AVALIACAO else []
    return render_template('avaliacoes.html', pendentes=pendentes, criterios_do_alvo=criterios_do_alvo,
                           json_notas=lambda r: json.loads(r.notas) if r else {}, ciclos=ciclos, gestao=gestao,
                           resultados=resultados_avaliacao(current_user), recebidas=avaliacoes_recebidas(current_user),
                           alertas=alertas_acompanhamento(current_user), reunioes_pendentes=reunioes_sem_avaliacao(current_user),
                           empresas=Empresa.query.order_by(Empresa.nome).all() if gestao else [], hoje=datetime.now().date(),
                           tipos_ciclo=TIPOS_CICLO)


@app.route('/avaliacoes/responder', methods=['POST'])
@login_required
def responder_avaliacao():
    from models import CicloAvaliacao, RespostaAvaliacao
    idioma = current_user.idioma
    voltar = redirect(url_for('avaliacoes') + '#pendentes')
    ciclo = db.session.get(CicloAvaliacao, request.form.get('ciclo_id', type=int) or 0)
    if not ciclo or not ciclo.aberto():
        flash(tt('Este ciclo de avaliação não está aberto.', idioma), 'warning')
        return voltar
    alvo_tipo, avaliado_id = request.form.get('alvo_tipo'), request.form.get('avaliado_id', type=int)
    if not any(a == alvo_tipo and (p.id if p else None) == avaliado_id for a, p in alvos_da_avaliacao(current_user, ciclo)):
        flash("Acesso negado.", "danger")
        return voltar
    notas = {}
    for i, criterio in enumerate(criterios_do_alvo(ciclo, alvo_tipo)):
        nota = request.form.get(f'nota_{i}', type=int)
        if not nota or not AVALIACAO_NOTA_MINIMA <= nota <= AVALIACAO_NOTA_MAXIMA:
            flash(tt('Dê uma nota de 1 a 5 em cada critério.', idioma), 'warning')
            return voltar
        notas[criterio] = nota
    resposta = RespostaAvaliacao.query.filter_by(ciclo_id=ciclo.id, avaliador_id=current_user.id, alvo_tipo=alvo_tipo,
                                                 avaliado_id=avaliado_id).first()
    if resposta is None:
        resposta = RespostaAvaliacao(ciclo_id=ciclo.id, avaliador_id=current_user.id, alvo_tipo=alvo_tipo, avaliado_id=avaliado_id)
        db.session.add(resposta)
    resposta.notas = json.dumps(notas, ensure_ascii=False)
    resposta.media = round(sum(notas.values()) / len(notas), 2)
    resposta.comentario = (request.form.get('comentario') or '').strip()[:2000] or None
    db.session.commit()
    flash(tt('Avaliação registrada. Obrigado!', idioma), 'success')
    return voltar


@app.route('/avaliacoes/ciclos', methods=['POST'])
@login_required
def ciclos_avaliacao():
    """A gestão da instituição abre ciclos de avaliação 360° (ou micro) e encerra antes do prazo, se precisar."""
    from models import CicloAvaliacao
    idioma = current_user.idioma
    voltar = redirect(url_for('avaliacoes') + '#ciclos')
    if current_user.tipo_usuario not in PERFIS_GESTAO_INSTITUICAO:
        flash("Acesso negado.", "danger")
        return voltar
    if request.form.get('acao') == 'encerrar':
        ciclo = db.session.get(CicloAvaliacao, request.form.get('ciclo_id', type=int) or 0)
        if ciclo and ciclo.encerrado_em is None:
            ciclo.encerrado_em = datetime.now()
            db.session.commit()
            flash(tt('Ciclo de avaliação encerrado.', idioma), 'info')
        return voltar
    titulo = (request.form.get('titulo') or '').strip()[:150]
    tipo = request.form.get('tipo') if request.form.get('tipo') in TIPOS_CICLO else '360'
    try:
        inicio = datetime.strptime(request.form.get('inicio') or '', '%Y-%m-%d').date()
        fim = datetime.strptime(request.form.get('fim') or '', '%Y-%m-%d').date()
    except ValueError:
        inicio = fim = None
    empresa_id = request.form.get('empresa_id', type=int) or None
    if empresa_id and not db.session.get(Empresa, empresa_id):
        empresa_id = None
    hoje = datetime.now().date()
    if len(titulo) < MINIMO_CARACTERES_TITULO or not inicio or not fim or fim < inicio or fim < hoje or (fim - inicio).days > CICLO_AVALIACAO_MAXIMO_DIAS:
        flash(tt('Informe o título e o período (fim a partir de hoje, até 90 dias de duração).', idioma), 'warning')
        return voltar
    ciclo = CicloAvaliacao(titulo=titulo, tipo=tipo, inicio=inicio, fim=fim, empresa_id=empresa_id, criado_por_id=current_user.id)
    avisados = abrir_ciclo_avaliacao(ciclo)
    flash(tt('Ciclo de avaliação aberto: {qtd} pessoa(s) avisada(s).', idioma).format(qtd=avisados), 'success')
    return voltar


# ==============================================================================
# ROTAS: NOTIFICAÇÕES DO USUÁRIO (histórico do sino e preferência de e-mail)
# ==============================================================================
@app.route('/notificacoes', methods=['GET', 'POST'])
@login_required
def central_notificacoes():
    from models import Notificacao
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'marcar_todas':
            Notificacao.query.filter_by(usuario_id=current_user.id, lida=False).update({'lida': True})
            db.session.commit()
            flash(t('notif_todas_lidas', current_user.idioma), "success")
        elif acao == 'preferencia_email':
            current_user.receber_email = bool(request.form.get('receber_email'))
            db.session.commit()
            flash(t('notif_preferencia_salva', current_user.idioma), "success")
        return redirect(url_for('central_notificacoes'))

    notificacoes = Notificacao.query.filter_by(usuario_id=current_user.id).order_by(Notificacao.data_criacao.desc()).limit(100).all()
    return render_template('notificacoes.html', notificacoes=notificacoes)


@app.route('/notificacoes/<int:id>/abrir')
@login_required
def abrir_notificacao(id):
    from models import Notificacao
    notificacao = db.session.get(Notificacao, id)
    if not notificacao or notificacao.usuario_id != current_user.id:
        return redirect(url_for('central_notificacoes'))
    notificacao.lida = True
    db.session.commit()
    # Só segue links internos da própria plataforma
    destino = notificacao.link if (notificacao.link or '').startswith('/') else url_for('central_notificacoes')
    return redirect(destino)


@app.route('/demandas', methods=['GET', 'POST'])
@login_required
def portal_demandas():
    # Canal oficial para TODOS os perfis (inclusive o Aluno): cada um vê os próprios tickets
    # e só a gestão vê todos e responde oficialmente.
    from models import DemandaInstitucional, ComentarioDemanda
    perfis_gestao = PERFIS_GESTAO_DEMANDAS
    from datetime import datetime

    if request.method == 'POST':
        acao = request.form.get('acao')

        # --- AÇÃO 1: CRIAR NOVO TICKET ---
        if acao == 'nova_demanda':
            titulo = (request.form.get('titulo') or '').strip()
            tipo_demanda = request.form.get('tipo_demanda')
            prioridade = request.form.get('prioridade')
            descricao = (request.form.get('descricao') or '').strip()
            if not titulo or not descricao:
                flash(tt('Informe o título e a descrição do chamado.', current_user.idioma), "warning")
                return redirect(url_for('portal_demandas'))

            nova_demanda = DemandaInstitucional(
                autor_id=current_user.id,
                titulo=titulo,
                tipo_demanda=tipo_demanda,
                prioridade=prioridade,
                descricao=descricao,
                status='Aberta'
            )
            db.session.add(nova_demanda)
            db.session.commit()
            notificar(usuarios_gestao(exceto_id=current_user.id),
                      ('notif_demanda_nova_titulo', {'id': nova_demanda.id, 'titulo': titulo}),
                      ('notif_demanda_nova_msg', {'autor': current_user.nome, 'tipo': tipo_demanda, 'prioridade': prioridade}),
                      link=url_for('portal_demandas'), tipo='demanda', referencia=f"demanda-nova:{nova_demanda.id}")
            flash("Ticket aberto com sucesso! A equipe de gestão foi notificada.", "success")

        # --- AÇÃO 2: RESPONDER E ATUALIZAR TICKET ---
        elif acao == 'responder_demanda':
            # Apenas perfis de gestão (Admins) podem responder oficialmente
            if current_user.tipo_usuario not in perfis_gestao:
                flash("Apenas gestores podem responder oficialmente aos tickets.", "danger")
                return redirect(url_for('portal_demandas'))

            demanda_id = request.form.get('demanda_id')
            resposta = request.form.get('resposta_oficial')
            novo_status = request.form.get('status')

            demanda = db.session.get(DemandaInstitucional, int(demanda_id))
            if demanda:
                demanda.resposta_oficial = resposta
                demanda.status = novo_status
                demanda.data_atualizacao = datetime.utcnow()
                db.session.commit()
                if demanda.autor and demanda.autor_id != current_user.id:
                    notificar([demanda.autor], ('notif_demanda_resposta_titulo', {'id': demanda.id, 'titulo': demanda.titulo}),
                              ('notif_demanda_resposta_msg', {'status': demanda.status}),
                              link=url_for('portal_demandas'), tipo='demanda')
                flash(f"Ticket #{demanda.id} atualizado com sucesso!", "success")

        # --- AÇÃO 3: MENSAGEM NO HISTÓRICO DO TICKET (autor ou gestão) ---
        elif acao == 'comentar_demanda':
            demanda = db.session.get(DemandaInstitucional, request.form.get('demanda_id', type=int) or 0)
            texto_comentario = (request.form.get('texto') or '').strip()
            if not demanda or (current_user.tipo_usuario not in perfis_gestao and demanda.autor_id != current_user.id):
                flash(t('demanda_sem_permissao', current_user.idioma), "danger")
            elif not texto_comentario:
                flash(t('demanda_comentario_vazio', current_user.idioma), "warning")
            else:
                db.session.add(ComentarioDemanda(demanda_id=demanda.id, autor_id=current_user.id, texto=texto_comentario))
                demanda.data_atualizacao = datetime.utcnow()
                # Gestão comentando um ticket ainda 'Aberta' coloca-o em análise
                if current_user.tipo_usuario in perfis_gestao and demanda.status == 'Aberta':
                    demanda.status = 'Em Análise'
                db.session.commit()
                # Gestão escreveu: avisa o autor. Autor escreveu: avisa a gestão.
                if current_user.tipo_usuario in perfis_gestao:
                    destino = [demanda.autor] if demanda.autor_id != current_user.id else []
                else:
                    destino = usuarios_gestao(exceto_id=current_user.id)
                notificar(destino, ('notif_demanda_msg_titulo', {'id': demanda.id, 'titulo': demanda.titulo}),
                          f"{current_user.nome}: {texto_comentario[:300]}",
                          link=url_for('portal_demandas'), tipo='demanda')
                flash(t('demanda_comentario_ok', current_user.idioma), "success")

        return redirect(url_for('portal_demandas'))

    # --- MÉTODO GET: LISTAR OS TICKETS NA TELA ---
    # Gestores veem todos os tickets organizados por status. Os demais perfis veem apenas os seus.
    if current_user.tipo_usuario in perfis_gestao:
        lista_demandas = DemandaInstitucional.query.order_by(
            db.case(
                (DemandaInstitucional.status == 'Aberta', 1),
                (DemandaInstitucional.status == 'Em Análise', 2),
                else_=3
            ),
            DemandaInstitucional.data_criacao.desc()
        ).all()
    else:
        lista_demandas = DemandaInstitucional.query.filter_by(autor_id=current_user.id).order_by(DemandaInstitucional.data_criacao.desc()).all()

    return render_template('demandas.html', demandas=lista_demandas)

# ==============================================================================
# ROTA: LANÇAMENTO MANUAL DE HORAS DE VOLUNTARIADO (B2B GENÉRICO)
# ==============================================================================
@app.route('/voluntariado/manual', methods=['POST'])
@login_required
def lancamento_manual_voluntariado():
    from models import CheckinVoluntariado
    from datetime import datetime, timedelta

    tipo = request.form.get('tipo_atividade')
    data_str = request.form.get('data')
    hora_inicio_str = request.form.get('hora_inicio')
    hora_fim_str = request.form.get('hora_fim')

    if not (tipo and data_str and hora_inicio_str and hora_fim_str):
        flash("Preencha todos os campos obrigatórios para o lançamento manual.", "warning")
        return voltar('dashboard')

    erro, grupo_id, projeto_id, motivo = validar_vinculos_voluntariado(current_user, tipo, request.form)
    if erro:
        flash(t(erro, current_user.idioma), "warning")
        return voltar('dashboard')

    try:
        # Junta a data com as horas para criar o formato completo
        inicio_dt = datetime.strptime(f"{data_str} {hora_inicio_str}", "%Y-%m-%d %H:%M")
        fim_dt = datetime.strptime(f"{data_str} {hora_fim_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Erro ao processar as datas. Tente novamente.", "danger")
        return voltar('dashboard')

    # Trata o caso de virar a noite (ex: 23:00 até 01:00)
    if fim_dt < inicio_dt:
        fim_dt += timedelta(days=1)
    minutos = int((fim_dt - inicio_dt).total_seconds() / 60)

    # Regras: nada no futuro, nada com duração zero e no máximo 12 h por lançamento
    if inicio_dt > datetime.now():
        flash(t('vol_erro_futuro', current_user.idioma), "warning")
        return voltar('dashboard')
    if minutos <= 0 or minutos > 12 * 60:
        flash(t('vol_erro_duracao', current_user.idioma), "warning")
        return voltar('dashboard')

    novo_ponto = CheckinVoluntariado(
        usuario_id=current_user.id,
        tipo_atividade=f"{tipo} (Lançamento Manual)",
        data_hora_inicio=inicio_dt,
        data_hora_fim=fim_dt,
        total_minutos=minutos,
        observacoes=motivo or None,
        grupo_id=grupo_id,
        projeto_id=projeto_id,
        categoria=classificar_categoria(tipo)
    )
    db.session.add(novo_ponto)
    db.session.commit()

    # Alerta limpo e genérico para qualquer parceiro B2B
    flash(f"✅ Lançamento manual gravado! {minutos} minutos adicionados ao relatório corporativo ESG.", "success")
    return voltar('dashboard')

# ==============================================================================
# ROTA: EXPORTAÇÃO DE RELATÓRIO EXECUTIVO ESG (CSV/EXCEL)
# ==============================================================================
@app.route('/admin/exportar-relatorio-esg')
@login_required
def exportar_relatorio_esg():
    import csv
    import io
    from flask import Response

    # 1. Trava de segurança: Apenas Admins e Gestores B2B podem baixar o relatório
    if current_user.tipo_usuario not in PERFIS_EXPORTAM_ESG:
        flash('Acesso negado. Apenas gestores podem exportar o relatório ESG.', 'danger')
        return redirect(url_for('dashboard'))

    # 2. Cria o arquivo na memória
    output = io.StringIO()
    # Usamos ponto e vírgula para abrir corretamente no Excel em português
    writer = csv.writer(output, delimiter=';')

    # 3. Cabeçalho das colunas do Excel
    writer.writerow(['Nome do Colaborador', 'Perfil', 'Empresa Associada', 'Tipo de Atividade (ESG)', 'Categoria',
                     'Grupo', 'Projeto (TCC)', 'Motivo / Observações', 'Minutos de Voluntariado', 'Data do Registo', 'Status'])

    # 4. Linhas no escopo do perfil (Gestor B2B só vê os mentores das suas empresas)
    for linha in [linha_relatorio_esg(vol) for vol in registros_esg_do_perfil(current_user)]:
        writer.writerow([linha['nome'], linha['perfil'], linha['empresa'], linha['atividade'], linha['categoria'],
                         linha['grupo'], linha['projeto'], linha['motivo'], linha['minutos'], linha['data'], linha['status']])

    # Retorna para o início do arquivo
    output.seek(0)

    # 5. Devolve o arquivo pronto para download (utf-8-sig evita que os acentos fiquem desconfigurados no Windows)
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Relatorio_Executivo_ESG_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# ==============================================================================
# ROTA: EXPORTAÇÃO DE RELATÓRIO EXECUTIVO ESG (PDF / IMPRESSÃO)
# ==============================================================================
@app.route('/admin/exportar-relatorio-esg-pdf')
@login_required
def exportar_relatorio_esg_pdf():
    if current_user.tipo_usuario not in PERFIS_EXPORTAM_ESG:
        flash('Acesso negado. Apenas gestores podem exportar o relatório ESG.', 'danger')
        return redirect(url_for('dashboard'))

    dados_formatados = [linha_relatorio_esg(vol) for vol in registros_esg_do_perfil(current_user)]

    # Totais por colaborador: horas regulamentares × extraordinárias (só registros concluídos)
    totais = {}
    for d in dados_formatados:
        if d['status'] != 'Concluído':
            continue
        pessoa = totais.setdefault(d['nome'], {'nome': d['nome'], 'empresa': d['empresa'], 'Regular': 0, 'Extra': 0})
        pessoa['Extra' if d['categoria'] == 'Extra' else 'Regular'] += d['minutos']
    resumo = sorted(totais.values(), key=lambda p: -(p['Regular'] + p['Extra']))

    # HTML limpo otimizado para salvar como PDF (templates/relatorio_esg_pdf.html)
    return render_template('relatorio_esg_pdf.html', dados=dados_formatados, resumo=resumo, data_emissao=datetime.now().strftime('%d/%m/%Y %H:%M'))

# ==============================================================================
# MOTOR DO ONBOARDING B2B E TRAVA DE COMPLIANCE
# ==============================================================================

# O @app.before_request age como um segurança de porta: ele roda ANTES de qualquer página abrir
# Versão vigente do Termo de Adesão (Lei 9.608/98). Mudar a versão obriga todos a assinar de novo.
VERSAO_TERMO_ATUAL = "2.0 - Lei 9.608/98"


PARCEIRO_PADRAO = 'empresa parceira (B2B)'


def empresas_parceiras(objeto):
    """Empresas parceiras (B2B) de uma pessoa, de um projeto (as dos jovens do grupo) ou de uma turma.
    O programa atende vários parceiros: use isto (ou nome_parceiro_b2b) em vez de qualquer nome fixo."""
    empresas = set()
    if objeto is None:
        return []
    if isinstance(objeto, Empresa):
        empresas.add(objeto)
    elif isinstance(objeto, Turma):
        if objeto.empresa:
            empresas.add(objeto.empresa)
    elif isinstance(objeto, Projeto):
        for membro in (objeto.grupo.membros if objeto.grupo else []):
            if membro.tipo_usuario == 'Aluno':
                empresas.update(empresas_parceiras(membro))
    else:
        empresas.update(getattr(objeto, 'empresas_gerenciadas', None) or [])
        empresas.update(getattr(objeto, 'empresas_vinculadas', None) or [])
        for turma in (getattr(objeto, 'turmas_como_aluno', None) or []) + (getattr(objeto, 'turmas_como_mentor', None) or []):
            if turma.empresa:
                empresas.add(turma.empresa)
        perfil = getattr(objeto, 'perfil_avaliador', None)
        if perfil and perfil.empresa_origem:
            igual = Empresa.query.filter(db.func.lower(Empresa.nome) == perfil.empresa_origem.strip().lower()).first()
            if igual:
                empresas.add(igual)
    return sorted(empresas, key=lambda e: e.nome)


def nome_parceiro_b2b(objeto, padrao=PARCEIRO_PADRAO):
    """Variável do nome do parceiro B2B para telas e textos: '{{ nome_parceiro_b2b(current_user) }}',
    '{{ nome_parceiro_b2b(projeto) }}' ou nome_parceiro_b2b(turma) no Python. Vários parceiros saem separados por vírgula."""
    nomes = [e.nome for e in empresas_parceiras(objeto)]
    perfil = getattr(objeto, 'perfil_avaliador', None)
    if perfil and perfil.empresa_origem and perfil.empresa_origem.strip().lower() not in {n.lower() for n in nomes}:
        nomes.append(perfil.empresa_origem.strip())  # avaliador de empresa ainda não cadastrada como parceira
    return ', '.join(nomes) if nomes else padrao


def parceiros_do_usuario(usuario):
    nome = nome_parceiro_b2b(usuario, '')
    return [n.strip() for n in nome.split(',') if n.strip()]


def parceiros_do_projeto(projeto):
    return [e.nome for e in empresas_parceiras(projeto)]


def organizacao_do_termo(usuario):
    parceiros = parceiros_do_usuario(usuario)
    instituicao = identidade.obter()['nome']  # o termo usa a instituição desta instalação e os parceiros de cada pessoa
    return f"{instituicao} e {', '.join(parceiros)}" if parceiros else f"{instituicao} e empresas parceiras (B2B)"


# Disponível em qualquer tela: {{ nome_parceiro_b2b(current_user) }}, {{ nome_parceiro_b2b(projeto) }}, empresas_parceiras(...)
app.jinja_env.filters['fromjson'] = lambda texto: json.loads(texto) if texto else {}
app.jinja_env.globals.update(nome_parceiro_b2b=nome_parceiro_b2b, empresas_parceiras=empresas_parceiras)

# ------------------------------------------------------------------------------ logo do parceiro B2B (vai no certificado)
PASTA_LOGOS = os.path.join(app.root_path, 'uploads', 'logos')
FORMATOS_LOGO = {'png': b'\x89PNG\r\n\x1a\n', 'jpg': b'\xff\xd8\xff', 'jpeg': b'\xff\xd8\xff', 'webp': b'RIFF'}
LIMITE_LOGO_BYTES = 2 * 1024 * 1024


def _apagar_logo(caminho):
    """Apaga o arquivo antigo; se estiver em uso (Windows), fica para trás sem quebrar a tela — o banco já não aponta para ele."""
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
    except OSError as erro:
        app.logger.warning("Logo antigo não apagado (%s): %s", caminho, erro)


def pode_gerir_logo(usuario, empresa):
    return usuario.tipo_usuario in PERFIS_GESTAO_LOGOS or (
        usuario.tipo_usuario == 'Admin B2B' and empresa.gestor_id == usuario.id)


@app.route('/empresas/<int:id>/logo')
def logo_empresa(id):
    """Imagem pública do logo (aparece também na verificação pública do certificado)."""
    empresa = db.session.get(Empresa, id)
    if not empresa or not empresa.logo_arquivo:
        return ('', 404)
    caminho = os.path.join(PASTA_LOGOS, os.path.basename(empresa.logo_arquivo))
    if not os.path.exists(caminho):
        return ('', 404)
    resposta = send_file(caminho, max_age=3600)
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    return resposta


@app.route('/empresas/<int:id>/logo/enviar', methods=['POST'])
@login_required
def enviar_logo_empresa(id):
    """Envia, troca ou remove o logo. Só PNG, JPG ou WEBP (SVG não: pode carregar script), até 2 MB, conferindo o conteúdo."""
    idioma = current_user.idioma
    empresa = db.session.get(Empresa, id)
    if not empresa or not pode_gerir_logo(current_user, empresa):
        flash("Acesso negado.", "danger")
        return voltar('gerenciar_turmas')
    antigo = os.path.join(PASTA_LOGOS, os.path.basename(empresa.logo_arquivo)) if empresa.logo_arquivo else None
    if request.form.get('acao') == 'remover':
        empresa.logo_arquivo = None
        db.session.commit()
        _apagar_logo(antigo)
        flash(tt('Logo removido.', idioma), 'info')
        return voltar('gerenciar_turmas')
    arquivo = request.files.get('logo')
    extensao = (arquivo.filename.rsplit('.', 1)[-1].lower() if arquivo and '.' in arquivo.filename else '')
    conteudo = arquivo.read(LIMITE_LOGO_BYTES + 1) if arquivo else b''
    assinatura = FORMATOS_LOGO.get(extensao)
    if not assinatura or not conteudo.startswith(assinatura) or (extensao == 'webp' and conteudo[8:12] != b'WEBP'):
        flash(tt('Envie o logo em PNG, JPG ou WEBP.', idioma), 'warning')
    elif len(conteudo) > LIMITE_LOGO_BYTES:
        flash(tt('O logo deve ter no máximo 2 MB.', idioma), 'warning')
    else:
        os.makedirs(PASTA_LOGOS, exist_ok=True)
        nome = f"empresa_{empresa.id}_{secrets.token_hex(6)}.{'jpg' if extensao == 'jpeg' else extensao}"
        with open(os.path.join(PASTA_LOGOS, nome), 'wb') as f:
            f.write(conteudo)
        empresa.logo_arquivo = nome
        db.session.commit()
        _apagar_logo(antigo)
        flash(tt('Logo do parceiro atualizado: ele aparece nos certificados dos participantes desta empresa.', idioma), 'success')
    return voltar('gerenciar_turmas')


# ==============================================================================
# IDENTIDADE DA INSTITUIÇÃO (Administração › Sistema › Identidade da instituição)
# Cada cliente tem a sua instalação: nome, apelido dos botões, plataforma, logo, site, e-mail e cargo da assinatura.
# ==============================================================================
import identidade


@app.context_processor
def _marca_no_template():
    """{{ marca.nome }}, {{ marca.apelido }}, {{ marca.plataforma }}, {{ marca.logo_url }} em qualquer tela."""
    dados = dict(identidade.obter())
    dados['logo_url'] = url_for('logo_instituicao') if dados.get('logo_arquivo') else ''
    return {'marca': dados}


@app.route('/instituicao/logo')
def logo_instituicao():
    """Logo da instituição (público: aparece no login, nos certificados e na verificação pública)."""
    nome = identidade.obter().get('logo_arquivo')
    caminho = os.path.join(PASTA_LOGOS, os.path.basename(nome)) if nome else ''
    if not caminho or not os.path.exists(caminho):
        return ('', 404)
    resposta = send_file(caminho, max_age=300)
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    return resposta


def _recurso_indisponivel(chave):
    """Mensagem (traduzida) quando o recurso não funciona nesta hospedagem; '' quando funciona (ambiente.py)."""
    import ambiente
    ok, motivo = ambiente.disponivel(chave)
    return '' if ok else tt(motivo, current_user.idioma) + ' ' + tt('Detalhes em Administração › Sistema › Ambiente e compatibilidade.', current_user.idioma)


@app.route('/admin/ambiente')
@login_required
def ambiente_compatibilidade():
    """Onde a plataforma está publicada, o banco em uso, as pastas de backup e o que funciona aqui (ligado, atenção
    ou desligado, com o motivo e como ligar). Só o Administrador."""
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import ambiente
    import backup_servico
    from models import AgendamentoBackup
    return render_template('ambiente.html', a=ambiente.resumo(), agendamentos=AgendamentoBackup.query.order_by(AgendamentoBackup.id).all(),
                           tamanho_legivel=backup_servico.tamanho_legivel)


@app.route('/admin/ambiente/backups-padrao', methods=['POST'])
@login_required
def ambiente_backups_padrao():
    """Cria os agendamentos padrão (Diário 7, Semanal 4, Mensal 12) quando ainda não há nenhum."""
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import backup_servico
    criados = backup_servico.criar_agendamentos_padrao(current_user.id)
    flash(tt('Agendamentos padrão criados: Diário, Semanal e Mensal.', current_user.idioma) if criados
          else tt('Já existem agendamentos de backup: nada foi alterado.', current_user.idioma), 'success' if criados else 'info')
    return redirect(url_for('ambiente_compatibilidade'))


@app.route('/admin/identidade', methods=['GET', 'POST'])
@login_required
def identidade_instituicao():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    if request.method == 'POST':
        erros = identidade.salvar(request.form, current_user.id)
        if erros:
            for erro in erros:
                flash(tt(erro, idioma), 'warning')
        else:
            flash(tt('Identidade da instituição salva: as telas, os e-mails e os certificados já usam os novos dados.', idioma), 'success')
        return redirect(url_for('identidade_instituicao'))
    return render_template('identidade.html', dados=identidade.obter(), padrao=identidade.PADRAO)


@app.route('/admin/identidade/logo', methods=['POST'])
@login_required
def identidade_logo():
    """Mesmas regras do logo dos parceiros: PNG, JPG ou WEBP (SVG não), até 2 MB, conferindo o conteúdo."""
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    if not identidade.obter().get('configurada'):
        flash(tt('Salve primeiro o nome, o apelido e a plataforma; depois envie o logo.', idioma), 'warning')
        return redirect(url_for('identidade_instituicao'))
    if request.form.get('acao') == 'remover':
        antigo = identidade.definir_logo(None)
        _apagar_logo(os.path.join(PASTA_LOGOS, os.path.basename(antigo)) if antigo else None)
        flash(tt('Logo removido.', idioma), 'info')
        return redirect(url_for('identidade_instituicao'))
    arquivo = request.files.get('logo')
    extensao = (arquivo.filename.rsplit('.', 1)[-1].lower() if arquivo and '.' in arquivo.filename else '')
    conteudo = arquivo.read(LIMITE_LOGO_BYTES + 1) if arquivo else b''
    assinatura = FORMATOS_LOGO.get(extensao)
    if not assinatura or not conteudo.startswith(assinatura) or (extensao == 'webp' and conteudo[8:12] != b'WEBP'):
        flash(tt('Envie o logo em PNG, JPG ou WEBP.', idioma), 'warning')
    elif len(conteudo) > LIMITE_LOGO_BYTES:
        flash(tt('O logo deve ter no máximo 2 MB.', idioma), 'warning')
    else:
        os.makedirs(PASTA_LOGOS, exist_ok=True)
        nome = f"instituicao_{secrets.token_hex(6)}.{'jpg' if extensao == 'jpeg' else extensao}"
        with open(os.path.join(PASTA_LOGOS, nome), 'wb') as f:
            f.write(conteudo)
        antigo = identidade.definir_logo(nome)
        _apagar_logo(os.path.join(PASTA_LOGOS, os.path.basename(antigo)) if antigo else None)
        flash(tt('Logo da instituição atualizado: ele aparece no menu, nos certificados e na verificação pública.', idioma), 'success')
    return redirect(url_for('identidade_instituicao'))


# Perfis que precisam concluir a trilha de orientação do TCC antes de usar a plataforma
PERFIS_TRILHA_TCC = ['Mentor', 'Professor', 'Mentor Administrador']
PERFIS_VEEM_TRILHA_TCC = PERFIS_TRILHA_TCC + ['Administrador']

# Rotas que continuam livres enquanto o termo ou a trilha estão pendentes
# (registrar_frequencia estava fora desta lista e prendia Mentor/Professor no primeiro acesso)
ENDPOINTS_LIVRES_ONBOARDING = ['login', 'logout', 'static', 'onboarding', 'aceitar_termos', 'registrar_frequencia',
                               'desativar_tour', 'alterar_tema', 'alterar_idioma', 'trocar_senha_obrigatoria',
                               'cadastrar_perguntas', 'recuperar_senha', 'trilha_tcc', 'concluir_modulo_tcc']


def progresso_trilha_tcc(usuario):
    """Devolve (módulos lidos na versão atual, total de módulos ativos)."""
    from models import ModuloOnboardingTCC, ConclusaoModuloTCC
    modulos = ModuloOnboardingTCC.query.filter_by(ativo=True).all()
    lidos = {c.modulo_id: c.versao_lida for c in ConclusaoModuloTCC.query.filter_by(usuario_id=usuario.id).all()}
    feitos = sum(1 for m in modulos if (lidos.get(m.id) or 0) >= (m.versao or 1))
    return feitos, len(modulos)


@app.before_request
def verificar_onboarding():
    # Deixa passar livremente as páginas de login, logout, arquivos estáticos e o próprio onboarding
    if request.endpoint is None or request.endpoint in ENDPOINTS_LIVRES_ONBOARDING:
        return

    if current_user.is_authenticated:
        # Alunos não passam por este onboarding corporativo
        if current_user.tipo_usuario == 'Aluno':
            return

        from models import TermoAceite
        # Precisa existir a assinatura da versão VIGENTE do termo
        aceite = TermoAceite.query.filter_by(usuario_id=current_user.id, versao_termo=VERSAO_TERMO_ATUAL).first()

        # Se não tem a assinatura, "tranca" o usuário na página de Onboarding
        if not aceite:
            return redirect(url_for('onboarding'))

        # Trilha do TCC: o Painel continua aberto (mostra o progresso); o resto espera a conclusão
        if current_user.tipo_usuario in PERFIS_TRILHA_TCC and request.endpoint != 'dashboard':
            feitos, total = progresso_trilha_tcc(current_user)
            if feitos < total:
                flash(t('trilha_pendente_aviso', current_user.idioma).format(feitos=feitos, total=total), "warning")
                return redirect(url_for('trilha_tcc'))


@app.context_processor
def injetar_progresso_trilha():
    # Banner do Painel para quem ainda não terminou a trilha do TCC
    if current_user.is_authenticated and current_user.tipo_usuario in PERFIS_TRILHA_TCC:
        feitos, total = progresso_trilha_tcc(current_user)
        if feitos < total:
            return dict(trilha_tcc_pendente={'feitos': feitos, 'total': total})
    return dict(trilha_tcc_pendente=None)

# Rota visual para ler o termo
@app.route('/onboarding')
@login_required
def onboarding():
    # Se aluno cair aqui por acidente, manda de volta ao painel
    if current_user.tipo_usuario == 'Aluno':
        return redirect(url_for('dashboard'))
    return render_template('onboarding.html', versao_termo=VERSAO_TERMO_ATUAL, organizacao=organizacao_do_termo(current_user),
                           projeto=identidade.obter()['plataforma'], data_hoje=datetime.now().strftime('%d/%m/%Y'))

# Rota de gravação da assinatura
@app.route('/onboarding/aceitar', methods=['POST'])
@login_required
def aceitar_termos():
    from models import TermoAceite
    from datetime import datetime
    
    novo_aceite = TermoAceite(
        usuario_id=current_user.id,
        data_aceite=datetime.utcnow(),
        versao_termo=VERSAO_TERMO_ATUAL
    )
    db.session.add(novo_aceite)
    db.session.commit()

    flash("✅ Diretrizes corporativas aceitas com sucesso! Bem-vindo(a) ao projeto.", "success")
    # Mentores e professores seguem direto para a trilha do TCC, se ainda não concluíram
    if current_user.tipo_usuario in PERFIS_TRILHA_TCC:
        feitos, total = progresso_trilha_tcc(current_user)
        if feitos < total:
            return redirect(url_for('trilha_tcc'))
    return redirect(url_for('dashboard'))
# ==============================================================================
# TRILHA OBRIGATÓRIA DE ORIENTAÇÃO DO TCC (Mentor, Professor e Mentor Administrador)
# ==============================================================================
@app.route('/onboarding/trilha-tcc')
@login_required
def trilha_tcc():
    from models import ModuloOnboardingTCC, ConclusaoModuloTCC
    if current_user.tipo_usuario not in PERFIS_VEEM_TRILHA_TCC:
        return redirect(url_for('dashboard'))

    modulos = ModuloOnboardingTCC.query.filter_by(ativo=True).order_by(ModuloOnboardingTCC.ordem).all()
    lidos = {c.modulo_id: c for c in ConclusaoModuloTCC.query.filter_by(usuario_id=current_user.id).all()}
    feitos, total = progresso_trilha_tcc(current_user)
    return render_template('trilha_tcc.html', modulos=modulos, lidos=lidos, feitos=feitos, total=total)


@app.route('/onboarding/trilha-tcc/<int:modulo_id>/concluir', methods=['POST'])
@login_required
def concluir_modulo_tcc(modulo_id):
    from models import ModuloOnboardingTCC, ConclusaoModuloTCC
    modulo = db.session.get(ModuloOnboardingTCC, modulo_id)
    if not modulo or not modulo.ativo:
        return redirect(url_for('trilha_tcc'))

    conclusao = ConclusaoModuloTCC.query.filter_by(usuario_id=current_user.id, modulo_id=modulo.id).first()
    if conclusao:
        conclusao.versao_lida = modulo.versao
        conclusao.data_conclusao = datetime.utcnow()
    else:
        db.session.add(ConclusaoModuloTCC(usuario_id=current_user.id, modulo_id=modulo.id, versao_lida=modulo.versao))
    db.session.commit()

    feitos, total = progresso_trilha_tcc(current_user)
    if feitos >= total:
        flash(t('trilha_concluida', current_user.idioma), "success")
        return redirect(url_for('dashboard'))
    return redirect(url_for('trilha_tcc') + f"#modulo-{modulo.id}")


@app.route('/onboarding/trilha-tcc/gestao', methods=['GET', 'POST'])
@login_required
def gestao_trilha_tcc():
    from models import ModuloOnboardingTCC, ConclusaoModuloTCC, Usuario
    if current_user.tipo_usuario not in PERFIS_GESTAO_TRILHA_TCC:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        titulo = (request.form.get('titulo') or '').strip()
        conteudo = (request.form.get('conteudo_html') or '').strip()
        if not titulo or not conteudo:
            flash(t('trilha_gestao_campos', current_user.idioma), "warning")
            return redirect(url_for('gestao_trilha_tcc'))

        modulo = db.session.get(ModuloOnboardingTCC, request.form.get('modulo_id', type=int) or 0)
        if not modulo:
            modulo = ModuloOnboardingTCC(versao=1)
            db.session.add(modulo)
        elif request.form.get('exigir_releitura'):
            # Nova versão: quem leu a anterior volta a ter o módulo pendente
            modulo.versao = (modulo.versao or 1) + 1
        modulo.titulo = titulo
        modulo.conteudo_html = conteudo
        modulo.link_video = (request.form.get('link_video') or '').strip() or None
        modulo.ordem = request.form.get('ordem', type=int) or 1
        modulo.ativo = bool(request.form.get('ativo'))
        db.session.commit()
        flash(t('trilha_gestao_salvo', current_user.idioma), "success")
        return redirect(url_for('gestao_trilha_tcc'))

    modulos = ModuloOnboardingTCC.query.order_by(ModuloOnboardingTCC.ordem).all()
    pessoas = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_TRILHA_TCC), Usuario.status == 'Ativo').order_by(Usuario.nome).all()
    progresso = []
    for pessoa in pessoas:
        feitos, total = progresso_trilha_tcc(pessoa)
        ultima = ConclusaoModuloTCC.query.filter_by(usuario_id=pessoa.id).order_by(ConclusaoModuloTCC.data_conclusao.desc()).first()
        progresso.append({'pessoa': pessoa, 'feitos': feitos, 'total': total,
                          'ultima': ultima.data_conclusao if ultima else None})
    return render_template('trilha_tcc_gestao.html', modulos=modulos, progresso=progresso)

# ==============================================================================
# ROTA: BIBLIOTECA HISTÓRICA DE TCCS (VITRINE DE PROJETOS)
# ==============================================================================
@app.route('/biblioteca', methods=['GET', 'POST'])
@login_required
def biblioteca_tccs():
    # P19: acervo interno de TCCs (aprovados na plataforma e históricos) + materiais de apoio
    from models import TCCAcervo, MaterialApoio

    if request.method == 'POST':
        if not pode_gerir_bancas(current_user):
            flash("Acesso negado.", "danger")
            return redirect(url_for('biblioteca_tccs'))
        acao = request.form.get('acao')
        if acao == 'importar_historico':
            titulo = (request.form.get('titulo') or '').strip()
            pdf = salvar_arquivo_acervo(request.files.get('arquivo_pdf'), 'historico', {'pdf'})
            if not titulo or not pdf:
                flash(t('acervo_erro_importar', current_user.idioma), "warning")
                return redirect(url_for('biblioteca_tccs'))
            item = TCCAcervo(titulo=titulo, origem='Histórico', arquivo_pdf=pdf,
                             autores_exibicao=(request.form.get('autores_exibicao') or '').strip() or None)
            dados_acervo_do_formulario(item, request.form)
            db.session.add(item)
            flash(t('acervo_importado', current_user.idioma), "success")
        elif acao == 'editar_acervo':
            item = db.session.get(TCCAcervo, request.form.get('acervo_id', type=int) or 0)
            if item:
                dados_acervo_do_formulario(item, request.form)
                flash(t('acervo_atualizado', current_user.idioma), "success")
        elif acao == 'material':
            arquivo = request.files.get('arquivo')
            nome = salvar_arquivo_acervo(arquivo, 'material', {'pdf', 'docx', 'pptx', 'xlsx'})
            titulo = (request.form.get('titulo') or '').strip()
            if not titulo or not nome:
                flash(t('acervo_erro_material', current_user.idioma), "warning")
                return redirect(url_for('biblioteca_tccs'))
            db.session.add(MaterialApoio(titulo=titulo, descricao=(request.form.get('descricao') or '').strip() or None,
                                         categoria=request.form.get('categoria') or 'Metodologia', arquivo=nome,
                                         nome_original=secure_filename(arquivo.filename), enviado_por_id=current_user.id))
            flash(t('acervo_material_ok', current_user.idioma), "success")
        db.session.commit()
        return redirect(url_for('biblioteca_tccs'))

    busca = (request.args.get('q') or '').strip().lower()
    ano = request.args.get('ano', type=int)
    itens = TCCAcervo.query.order_by(TCCAcervo.ano_edicao.desc(), TCCAcervo.titulo).all()
    anos = sorted({i.ano_edicao for i in itens if i.ano_edicao}, reverse=True)
    if busca:
        itens = [i for i in itens if busca in ' '.join(filter(None, [i.titulo, i.tema, i.resumo, i.palavras_chave, i.autores_exibicao])).lower()]
    if ano:
        itens = [i for i in itens if i.ano_edicao == ano]
    materiais = MaterialApoio.query.order_by(MaterialApoio.categoria, MaterialApoio.titulo).all()
    return render_template('biblioteca.html', itens=itens, materiais=materiais, anos=anos, busca=request.args.get('q') or '',
                           ano=ano, gestor=pode_gerir_bancas(current_user), ano_atual=datetime.now().year)


# ==============================================================================
# ROTA: EMISSÃO DE CERTIFICADOS OFICIAIS (PDF)
# ==============================================================================
@app.route('/certificado/<int:projeto_id>/<int:usuario_id>')
@login_required
def emitir_certificado(projeto_id, usuario_id):
    # P17: certificado com as horas dedicadas, só para quem participou e só depois da divulgação do resultado
    import json
    projeto = db.session.get(Projeto, projeto_id)
    usuario = db.session.get(Usuario, usuario_id)

    if not projeto or not usuario:
        flash("Dados não encontrados para a emissão do certificado.", "danger")
        return redirect(url_for('dashboard'))
    if not pode_emitir_certificado_de(current_user, usuario):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    # Trava de Segurança: Certificado só sai se a banca aprovou e a coordenação divulgou o resultado
    if projeto.status != 'Concluído' or not projeto.notas_publicadas:
        flash("Este projeto ainda não foi aprovado pela Banca Avaliadora.", "warning")
        return redirect(url_for('meus_certificados'))

    tipo = tipo_certificado(usuario, projeto)
    if not tipo:
        flash(t('cert_nao_participou', current_user.idioma), "warning")
        return redirect(url_for('meus_certificados'))

    certificado = registrar_certificado(usuario, projeto, tipo)
    detalhe = json.loads(certificado.detalhe_minutos or '{}')
    # Logos dos parceiros B2B: a empresa da própria pessoa (mentor, avaliador) e as dos jovens do projeto
    logos = [e for e in dict.fromkeys(empresas_parceiras(usuario) + empresas_parceiras(projeto)) if e.logo_arquivo]
    return render_template('certificado.html', projeto=projeto, usuario=usuario, certificado=certificado, detalhe=detalhe,
                           logos_parceiros=logos, nome_parceiro=nome_parceiro_b2b(projeto),
                           data_emissao=certificado.data_emissao.strftime('%d/%m/%Y'),
                           url_verificacao=url_for('verificar_certificado', codigo=certificado.codigo, _external=True))


# ===========================================================================
# EXECUÇÃO DO APLICATIVO
# ===========================================================================
import os
from datetime import datetime

@app.route('/admin/banco', methods=['GET', 'POST'])
@login_required
def manutencao_banco():
    """Manutenção (DB): saúde dos backups, agendamentos, backup imediato, restauração, histórico e zona de perigo."""
    import backup_servico as bs
    from models import AgendamentoBackup, AlteracaoAgendamentoBackup
    # Backup, restauração e limpeza de histórico: só o Administrador (o menu também só mostra a ele)
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    idioma = current_user.idioma

    if request.method == 'POST':
        acao = request.form.get('acao')

        # 1. Backup imediato (fica no servidor, em instance/backups/<pasta>, e pode ser baixado depois)
        if acao == 'backup':
            registro = bs.fazer_backup('Imediato', request.form.get('pasta'), current_user.id)
            if registro.status == 'Concluído':
                flash(tt('Backup concluído e validado: {arquivo}', idioma).format(arquivo=registro.arquivo), "success")
            else:
                flash(tt('O backup falhou: {erro}', idioma).format(erro=registro.detalhes), "danger")

        # 2. Criar ou editar agendamento
        elif acao in ('novo_agendamento', 'editar_agendamento'):
            frequencia = request.form.get('frequencia')
            horario = (request.form.get('horario') or '').strip()
            try:
                data_inicio = datetime.strptime(request.form.get('data_inicio') or '', '%Y-%m-%d').date()
                retencao = int(request.form.get('retencao') or 7)
                valido = frequencia in bs.FREQUENCIAS and re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', horario) and 1 <= retencao <= RETENCAO_BACKUP_MAXIMA
            except ValueError:
                valido = False
            if not valido:
                flash(tt('Confira a frequência, o horário (HH:MM), a data de início e a retenção (1 a 365).', idioma), "warning")
                return redirect(url_for('manutencao_banco'))
            if acao == 'novo_agendamento':
                agendamento = AgendamentoBackup(criado_por_id=current_user.id, status='Ativo')
                db.session.add(agendamento)
                antes = None
            else:
                agendamento = db.session.get(AgendamentoBackup, request.form.get('agendamento_id', type=int))
                if not agendamento:
                    return redirect(url_for('manutencao_banco'))
                antes = bs.descrever(agendamento)
            agendamento.frequencia, agendamento.horario, agendamento.data_inicio = frequencia, horario, data_inicio
            agendamento.retencao, agendamento.pasta = retencao, bs.nome_de_pasta(request.form.get('pasta') or 'agendados')
            db.session.flush()
            agendamento.proxima_execucao = bs.calcular_proxima(agendamento, datetime.now())
            if antes is None:
                bs.registrar_alteracao(agendamento.id, 'Criado', bs.descrever(agendamento), current_user.id)
                flash(tt('Agendamento criado. Próxima execução: {data}', idioma).format(data=agendamento.proxima_execucao.strftime('%d/%m/%Y %H:%M')), "success")
            else:
                bs.registrar_alteracao(agendamento.id, 'Editado', f"De: {antes} | Para: {bs.descrever(agendamento)}", current_user.id)
                flash(tt('Agendamento atualizado.', idioma), "success")
            db.session.commit()

        # 3. Pausar, retomar, executar agora ou excluir agendamento
        elif acao in ('pausar', 'retomar', 'executar', 'excluir'):
            agendamento = db.session.get(AgendamentoBackup, request.form.get('agendamento_id', type=int))
            if agendamento:
                if acao == 'pausar':
                    agendamento.status = 'Pausado'
                    bs.registrar_alteracao(agendamento.id, 'Pausado', bs.descrever(agendamento), current_user.id)
                    flash(tt('Agendamento pausado.', idioma), "info")
                elif acao == 'retomar':
                    agendamento.status = 'Ativo'
                    agendamento.proxima_execucao = bs.calcular_proxima(agendamento, datetime.now())
                    bs.registrar_alteracao(agendamento.id, 'Retomado', bs.descrever(agendamento), current_user.id)
                    flash(tt('Agendamento retomado.', idioma), "success")
                elif acao == 'executar':
                    bs.registrar_alteracao(agendamento.id, 'Executado manualmente', bs.descrever(agendamento), current_user.id)
                    db.session.commit()
                    registro = bs.executar_agendamento(agendamento, current_user.id)
                    flash(tt('Backup concluído e validado: {arquivo}', idioma).format(arquivo=registro.arquivo) if registro.status == 'Concluído'
                          else tt('O backup falhou: {erro}', idioma).format(erro=registro.detalhes),
                          "success" if registro.status == 'Concluído' else "danger")
                else:
                    bs.registrar_alteracao(agendamento.id, 'Excluído', bs.descrever(agendamento), current_user.id)
                    db.session.delete(agendamento)
                    flash(tt('Agendamento excluído. Os arquivos já gerados continuam na pasta.', idioma), "info")
                db.session.commit()

        # 4. Restaurar (arquivo da lista ou enviado), com cópia de segurança do banco atual antes
        elif acao == 'restaurar':
            caminho = bs.caminho_seguro(request.form.get('arquivo_existente'))
            enviado = request.files.get('arquivo_db')
            if not caminho and enviado and enviado.filename:
                if not enviado.filename.lower().endswith(bs.EXTENSOES):
                    flash(tt('Envie um arquivo .db (SQLite) ou .sql.gz (MySQL) gerado pelo backup da plataforma.', idioma), "warning")
                    return redirect(url_for('manutencao_banco'))
                caminho = os.path.join(bs.pasta_de('enviados'), f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(enviado.filename)}")
                enviado.save(caminho)
            if not caminho:
                flash(tt('Escolha um backup da lista ou envie um arquivo.', idioma), "warning")
                return redirect(url_for('manutencao_banco'))
            usuario_id = current_user.id
            ok, info = bs.restaurar(caminho, usuario_id, atualizar_estrutura_banco)
            if ok:
                flash(tt('Banco restaurado. A cópia do banco anterior foi guardada em: {arquivo}', idioma).format(arquivo=info), "success")
                if not db.session.get(Usuario, usuario_id):
                    logout_user()
                    flash(tt('Sua conta não existe no backup restaurado: entre com uma conta desse backup.', idioma), "warning")
                    return redirect(url_for('login'))
            else:
                flash(tt('Restauração cancelada: {erro}', idioma).format(erro=info), "danger")

        # 5. Zona de perigo: apaga os dados (exige digitar APAGAR e faz backup de segurança antes)
        elif acao == 'limpar':
            if (request.form.get('confirmacao') or '').strip().upper() != 'APAGAR':
                flash(tt('Para apagar os dados, digite APAGAR no campo de confirmação.', idioma), "warning")
                return redirect(url_for('manutencao_banco'))
            seguranca = bs.fazer_backup('Segurança (pré-limpeza)', 'seguranca', current_user.id)
            if seguranca.status != 'Concluído':
                flash(tt('Limpeza cancelada: não foi possível fazer o backup de segurança.', idioma), "danger")
                return redirect(url_for('manutencao_banco'))
            try:
                QADuvida.query.delete()
                FeedbackSessao.query.delete()
                SessaoMentoria.query.delete()
                HistoricoProgresso.query.delete()
                from models import ProgressoAula, QuestaoAula, AulaCurso
                ProgressoAula.query.delete()
                QuestaoAula.query.delete()
                AulaCurso.query.delete()
                Acompanhamento.query.delete()
                HistoricoSenha.query.filter(HistoricoSenha.usuario_id != current_user.id).delete()
                SegurancaUsuario.query.filter(SegurancaUsuario.usuario_id != current_user.id).delete()
                Curso.query.delete()
                SolicitacaoMentoria.query.delete()
                db.session.execute(aluno_mentor.delete())
                Usuario.query.filter(Usuario.id != current_user.id).delete()
                db.session.commit()
                bs.registrar('Limpeza de dados', 'Concluído',
                             f"Dados apagados; só a conta de {current_user.nome} foi preservada. Backup de segurança: {seguranca.arquivo}.",
                             current_user.id, arquivo=seguranca.arquivo)
                flash(tt('Dados apagados. Backup de segurança guardado em: {arquivo}', idioma).format(arquivo=seguranca.arquivo), "success")
            except Exception as e:
                db.session.rollback()
                bs.registrar('Limpeza de dados', 'Falha', f"Erro: {e}", current_user.id)
                flash(tt('Erro ao apagar os dados: {erro}', idioma).format(erro=e), "danger")

        # 6. Apagar o histórico de execuções (guarda um CSV de auditoria antes e registra quem apagou)
        elif acao == 'limpar_auditoria':
            total, arquivo = bs.apagar_historico(current_user.id, current_user.nome)
            flash(tt('{total} registro(s) apagado(s). Cópia em CSV guardada em: auditoria/{arquivo}', idioma).format(total=total, arquivo=arquivo), "success")

        return redirect(url_for('manutencao_banco'))

    # ---------------- Tela
    data_inicio_filtro, data_fim_filtro = request.args.get('data_inicio'), request.args.get('data_fim')
    logs_backup = historico_backup_filtrado(data_inicio_filtro, data_fim_filtro).all()
    agendamentos = AgendamentoBackup.query.order_by(AgendamentoBackup.id.desc()).all()
    alteracoes = AlteracaoAgendamentoBackup.query.order_by(AlteracaoAgendamentoBackup.data.desc()).limit(200).all()
    return render_template('admin_banco.html', logs_backup=logs_backup, data_inicio=data_inicio_filtro, data_fim=data_fim_filtro,
                           agendamentos=agendamentos, alteracoes=alteracoes, saude=bs.saude(), backups=bs.listar_backups(),
                           subpastas=bs.subpastas(), frequencias=bs.FREQUENCIAS, tamanho_legivel=bs.tamanho_legivel,
                           hoje=datetime.now().strftime('%Y-%m-%d'))


def historico_backup_filtrado(data_inicio, data_fim):
    consulta = RegistroBackup.query
    try:
        if data_inicio:
            consulta = consulta.filter(RegistroBackup.data_registro >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            consulta = consulta.filter(RegistroBackup.data_registro <= datetime.strptime(data_fim + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    except ValueError:
        pass
    return consulta.order_by(RegistroBackup.data_registro.desc())


@app.route('/admin/banco/arquivo')
@login_required
def baixar_backup():
    """Baixa um arquivo de backup do servidor (só os que estão em instance/backups)."""
    import backup_servico as bs
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    caminho = bs.caminho_seguro(request.args.get('f'))
    if not caminho:
        flash(tt('Arquivo de backup não encontrado.', current_user.idioma), "warning")
        return redirect(url_for('manutencao_banco'))
    bs.registrar('Download', 'Concluído', f"Arquivo baixado: {request.args.get('f')}", current_user.id, arquivo=os.path.basename(caminho),
                 tamanho=os.path.getsize(caminho))
    return send_file(caminho, as_attachment=True, download_name=os.path.basename(caminho))


@app.route('/admin/banco/relatorio/<tipo>.csv')
@login_required
def relatorio_auditoria_backup(tipo):
    """Relatórios para auditoria: execuções (com o filtro de datas da tela) ou alterações dos agendamentos."""
    import io
    import csv as _csv
    import backup_servico as bs
    from flask import Response
    from models import AlteracaoAgendamentoBackup
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    saida = io.StringIO()
    escritor = _csv.writer(saida, delimiter=';')
    if tipo == 'alteracoes':
        escritor.writerow(['Data/Hora', 'Agendamento', 'Ação', 'Usuário', 'Detalhes'])
        for a in AlteracaoAgendamentoBackup.query.order_by(AlteracaoAgendamentoBackup.data.desc()).all():
            escritor.writerow([a.data.strftime('%d/%m/%Y %H:%M:%S'), a.agendamento_id, a.acao, a.usuario.nome if a.usuario else 'sistema', a.detalhes or ''])
    else:
        cabecalho, linhas = bs.exportar_historico_csv(historico_backup_filtrado(request.args.get('data_inicio'), request.args.get('data_fim')).all())
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)
    nome = f"auditoria_backup_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response('﻿' + saida.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={nome}'})


# Agendamentos vencidos também rodam quando o app está em uso (no máximo uma verificação a cada 5 minutos);
# no PythonAnywhere quem garante a execução é o tarefas_agendadas.py, de hora em hora.
_ULTIMA_VERIFICACAO_BACKUP = [datetime.min]


@app.before_request
def verificar_backups_agendados():
    if os.environ.get('MENTORIA_VALIDACAO') == '1':
        return  # instância de validação do Orquestrador (cópia do banco): nunca grava backups nas pastas reais
    agora = datetime.now()
    if agora - _ULTIMA_VERIFICACAO_BACKUP[0] < timedelta(minutes=5):
        return
    _ULTIMA_VERIFICACAO_BACKUP[0] = agora
    try:
        import backup_servico
        backup_servico.executar_vencidos(agora)
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Verificação de backups agendados falhou: {e}")


def hash_resposta_seguranca(resposta):
    """Respostas das perguntas de segurança: normalizadas (minúsculas, sem espaços nas pontas) e guardadas com bcrypt."""
    return bcrypt.generate_password_hash((resposta or '').strip().lower()).decode('utf-8')


def conferir_resposta_seguranca(digitada, guardada):
    digitada = (digitada or '').strip().lower()
    if not digitada or not guardada:
        return False
    if guardada.startswith('$2'):
        try:
            return bcrypt.check_password_hash(guardada, digitada)
        except ValueError:
            return False
    return secrets.compare_digest(digitada, guardada.strip().lower())  # resposta antiga ainda não migrada


# ==============================================================================
# ROTA DE RECUPERAÇÃO DE SENHA (Aprovação exige acertar 2 de 3 perguntas)
# ==============================================================================
@app.route('/recuperar-senha', methods=['POST'])
def recuperar_senha():
    # 1. Catálogo oficial de 20 perguntas para documentação e uso no cadastro
    perguntas_disponiveis = [
        "Qual era o nome do seu primeiro animal de estimação?",
        "Qual é o nome de solteira da sua mãe?",
        "Qual foi o modelo do seu primeiro carro?",
        "Em qual cidade seus pais se conheceram?",
        "Qual era o nome do seu melhor amigo de infância?",
        "Qual o nome da sua primeira escola?",
        "Qual é o seu prato favorito?",
        "Qual foi a primeira viagem internacional que você fez?",
        "Qual é o nome do seu professor favorito no ensino médio?",
        "Qual é a sua cor favorita?",
        "Em qual cidade você nasceu?",
        "Qual é a sua banda ou artista musical favorito?",
        "Qual o título do seu livro favorito?",
        "Qual foi o seu primeiro emprego?",
        "Qual é o nome do seu avô materno?",
        "Qual é a sua equipe esportiva favorita?",
        "Em qual rua você morava quando era criança?",
        "Qual foi o primeiro filme que você viu no cinema?",
        "Qual é o seu apelido de infância?",
        "Qual o nome do seu herói ou personagem favorito?"
    ]

    # 2. Recebe o e-mail digitado no modal de "Esqueci a Senha"
    email = request.form.get('email_recuperacao')
    usuario = Usuario.query.filter_by(email=email).first()
    
    # 3 e 4. E-mail inexistente, conta de teste em produção ou conta sem perguntas recebem 3 perguntas "de fachada"
    # (sempre as mesmas para o mesmo e-mail) e nunca são aprovadas: a tela não revela quais e-mails existem.
    seguranca = None
    if usuario and not conta_de_teste_bloqueada(usuario.email):
        seguranca = SegurancaUsuario.query.filter_by(usuario_id=usuario.id).first()
    if not seguranca:
        if 'resposta_1' in request.form:
            flash('Você não atingiu o mínimo de 2 acertos. Tente novamente.', 'danger')
            return redirect(url_for('login'))
        import hashlib
        semente = int(hashlib.sha256((email or '').strip().lower().encode('utf-8')).hexdigest(), 16)
        fachada = [perguntas_disponiveis[(semente >> (8 * i)) % len(perguntas_disponiveis)] for i in range(12)]
        fachada = list(dict.fromkeys(fachada))[:3] + perguntas_disponiveis[:3]
        fachada = list(dict.fromkeys(fachada))[:3]
        return render_template('perguntas_seguranca.html', email=email, p1=fachada[0], p2=fachada[1], p3=fachada[2])

    # 5. Verifica se o usuário já preencheu a tela de respostas
    if 'resposta_1' in request.form:
        acertos = 0
        
        # Converte tudo para letras minúsculas e remove espaços vazios para evitar erros de digitação boba
        r1_digitada = request.form.get('resposta_1', '').strip().lower()
        r2_digitada = request.form.get('resposta_2', '').strip().lower()
        r3_digitada = request.form.get('resposta_3', '').strip().lower()

        # Compara com o hash guardado no banco (as respostas nunca ficam legíveis)
        if conferir_resposta_seguranca(r1_digitada, seguranca.resposta_1): acertos += 1
        if conferir_resposta_seguranca(r2_digitada, seguranca.resposta_2): acertos += 1
        if conferir_resposta_seguranca(r3_digitada, seguranca.resposta_3): acertos += 1

        # 6. Regra de Negócio: Se acertou 2 ou mais, libera o acesso para troca
        if acertos >= 2:
            login_user(usuario)
            usuario.forcar_troca_senha = True # Trava o usuário na tela de criar nova senha
            db.session.commit()
            flash('Identidade confirmada! Crie uma nova senha de acesso.', 'success')
            return redirect(url_for('trocar_senha_obrigatoria'))
        else:
            flash('Você não atingiu o mínimo de 2 acertos. Tente novamente.', 'danger')
            return redirect(url_for('login'))

    # 7. Se ainda não respondeu, exibe a tela HTML com as 3 perguntas dele
    return render_template('perguntas_seguranca.html', email=email, p1=seguranca.pergunta_1, p2=seguranca.pergunta_2, p3=seguranca.pergunta_3)


# ==============================================================================
# ROTA: CADASTRAR PERGUNTAS DE SEGURANÇA (Obrigatório após o primeiro login)
# ==============================================================================
@app.route('/cadastrar-perguntas', methods=['GET', 'POST'])
@login_required
def cadastrar_perguntas():
    # 1. Verifica se o usuário já tem perguntas cadastradas. Se sim, manda pro Dashboard (para não repetir)
    ja_cadastrou = SegurancaUsuario.query.filter_by(usuario_id=current_user.id).first()
    if ja_cadastrou:
        return redirect(url_for('dashboard'))

    # 2. Nossa lista oficial de 20 perguntas
    perguntas_disponiveis = [
        "Qual era o nome do seu primeiro animal de estimação?", "Qual é o nome de solteira da sua mãe?",
        "Qual foi o modelo do seu primeiro carro?", "Em qual cidade seus pais se conheceram?",
        "Qual era o nome do seu melhor amigo de infância?", "Qual o nome da sua primeira escola?",
        "Qual é o seu prato favorito?", "Qual foi a primeira viagem internacional que você fez?",
        "Qual é o nome do seu professor favorito no ensino médio?", "Qual é a sua cor favorita?",
        "Em qual cidade você nasceu?", "Qual é a sua banda ou artista musical favorito?",
        "Qual o título do seu livro favorito?", "Qual foi o seu primeiro emprego?",
        "Qual é o nome do seu avô materno?", "Qual é a sua equipe esportiva favorita?",
        "Em qual rua você morava quando era criança?", "Qual foi o primeiro filme que você viu no cinema?",
        "Qual é o seu apelido de infância?", "Qual o nome do seu herói ou personagem favorito?"
    ]

    # 3. Se o usuário preencheu o formulário e clicou em salvar
    if request.method == 'POST':
        p1 = request.form.get('pergunta_1')
        r1 = request.form.get('resposta_1')
        p2 = request.form.get('pergunta_2')
        r2 = request.form.get('resposta_2')
        p3 = request.form.get('pergunta_3')
        r3 = request.form.get('resposta_3')

        # Trava: Impede o usuário de escolher a mesma pergunta duas vezes
        if p1 == p2 or p1 == p3 or p2 == p3:
            flash("Por favor, escolha 3 perguntas diferentes.", "danger")
            return render_template('cadastrar_perguntas.html', perguntas=perguntas_disponiveis)

        if not all((r or '').strip() for r in (r1, r2, r3)):
            flash("Responda as 3 perguntas.", "danger")
            return render_template('cadastrar_perguntas.html', perguntas=perguntas_disponiveis)

        # Salva no banco só o hash das respostas (normalizadas em minúsculas)
        nova_seguranca = SegurancaUsuario(
            usuario_id=current_user.id,
            pergunta_1=p1, resposta_1=hash_resposta_seguranca(r1),
            pergunta_2=p2, resposta_2=hash_resposta_seguranca(r2),
            pergunta_3=p3, resposta_3=hash_resposta_seguranca(r3)
        )
        db.session.add(nova_seguranca)
        db.session.commit()
        
        flash("Perguntas de segurança configuradas com sucesso!", "success")
        return redirect(url_for('dashboard'))

    # Se for a primeira vez acessando a página, mostra o formulário
    return render_template('cadastrar_perguntas.html', perguntas=perguntas_disponiveis)


# ==============================================================================
# ROTA: RECEBER SOLICITAÇÃO (Tela de Login)
# ==============================================================================
@app.route('/solicitar-mentoria', methods=['POST'])
def solicitar_mentoria():
    nome = (request.form.get('nome') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    motivo = (request.form.get('motivo') or '').strip()
    idioma = session.get('idioma', 'pt')
    if not nome or not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
        flash(tt('Informe seu nome e um e-mail válido para pedir a mentoria.', idioma), 'warning')
        return redirect(url_for('login'))

    # Trava: Impede de pedir mentoria se o e-mail já for de um aluno matriculado
    ja_existe = Usuario.query.filter_by(email=email).first()
    if ja_existe:
        flash('Este e-mail já possui um cadastro ativo no sistema.', 'warning')
        return redirect(url_for('login'))

    nova_solicitacao = SolicitacaoMentoria(nome=nome, email=email, motivo=motivo)
    db.session.add(nova_solicitacao)
    db.session.commit()

    flash('Solicitação enviada com sucesso! Aguarde o contato da administração.', 'success')
    return redirect(url_for('login'))

# ==============================================================================
# ROTA: TELA EXCLUSIVA DE SOLICITAÇÕES E FILTRO DE DATAS
# ==============================================================================
# ROTA: TELA EXCLUSIVA DE SOLICITAÇÕES E FILTRO DE DATAS
@app.route('/admin/solicitacoes', methods=['GET'])
@login_required
def gerenciar_solicitacoes():
    # TRAVA DE SEGURANÇA: Apenas 'Mentor Administrador' passa daqui
    if current_user.tipo_usuario not in PERFIS_DECIDEM_SOLICITACOES:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    # Pega as datas digitadas no filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    # Prepara a busca no banco
    query = SolicitacaoMentoria.query

    # Filtra a partir da Data Inicial
    if data_inicio:
        data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(SolicitacaoMentoria.data_solicitacao >= data_inicio_dt)

    # Filtra até o final do dia da Data Final (23:59)
    if data_fim:
        data_fim_dt = datetime.strptime(data_fim + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        query = query.filter(SolicitacaoMentoria.data_solicitacao <= data_fim_dt)

    # Ordena da solicitação mais recente para a mais antiga
    solicitacoes = query.order_by(SolicitacaoMentoria.data_solicitacao.desc()).all()

    return render_template('admin_solicitacoes.html',
                            solicitacoes=solicitacoes,
                            data_inicio=data_inicio, data_fim=data_fim)

# ==============================================================================
# ROTA: APROVAR OU NEGAR SOLICITAÇÃO
# ==============================================================================
# ROTA: APROVAR OU NEGAR SOLICITAÇÃO
@app.route('/admin/solicitacao/<int:id>/<acao>')
@login_required
def acao_solicitacao(id, acao):
    # TRAVA DE SEGURANÇA: Apenas 'Mentor Administrador' pode aprovar ou negar
    if current_user.tipo_usuario not in PERFIS_DECIDEM_SOLICITACOES:
        return redirect(url_for('dashboard'))

    solicitacao = SolicitacaoMentoria.query.get_or_404(id)

    if acao == 'negar':
        solicitacao.status = 'Negado'
        db.session.commit()
        flash(f'Solicitação de {solicitacao.nome} foi negada.', 'info')
        return redirect(url_for('gerenciar_solicitacoes'))

    elif acao == 'aprovar':
        solicitacao.status = 'Aprovado'
        db.session.commit()
        flash('Solicitação aprovada! Finalize o cadastro escolhendo a senha e o mentor abaixo.', 'success')
        return redirect(url_for('gerenciar_usuarios', fill_nome=solicitacao.nome, fill_email=solicitacao.email))

# ==============================================================================
# INTEGRAÇÃO COM GOOGLE CALENDAR
# ==============================================================================
@app.route('/conectar-agenda')
@login_required
def conectar_agenda():
    caminho_secreto = os.path.join(app.root_path, 'client_secret.json')
    
    flow = Flow.from_client_secrets_file(
        caminho_secreto,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # Adicionamos o comando "prompt='select_account'" para forçar o Google a perguntar quem está logando
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account'
    )
    
    # SALVAMOS O STATE E O "CÓDIGO VERIFICADOR"
    session['state'] = state
    session['code_verifier'] = flow.code_verifier 
    
    return redirect(authorization_url)

@app.route('/oauth2callback')
@login_required
def oauth2callback():
    import convites_reuniao
    state = session.get('state')
    caminho_secreto = os.path.join(app.root_path, 'client_secret.json')
    # O mesmo endereço de retorno serve à Agenda e ao Gmail (só um endereço cadastrado no Google Cloud)
    destino = session.pop('oauth_destino', 'agenda')

    flow = Flow.from_client_secrets_file(
        caminho_secreto,
        scopes=convites_reuniao.SCOPES_GMAIL if destino == 'gmail' else SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )

    # 2. RECUPERAMOS O "CÓDIGO VERIFICADOR" PARA DEVOLVER AO GOOGLE
    flow.code_verifier = session.get('code_verifier')

    authorization_response = request.url
    try:
        flow.fetch_token(authorization_response=authorization_response)
    except Exception as erro:
        app.logger.warning("Conexão com o Google não concluída (%s): %s", destino, erro)
        flash(t('gmail_erro_conectar', current_user.idioma), "warning")
        return redirect(url_for('reunioes') if destino == 'gmail' else url_for('acompanhamento'))

    credenciais = flow.credentials

    if destino == 'gmail':
        session['gmail_token'] = credenciais.token
        session['gmail_refresh_token'] = credenciais.refresh_token
        session['gmail_email'] = convites_reuniao.email_do_id_token(getattr(credenciais, 'id_token', None) or '') or ''
        flash(t('gmail_conectado', current_user.idioma).format(email=session['gmail_email'] or 'Gmail'), "success")
        return redirect(seguranca_web.destino_interno(session.pop('oauth_voltar', None), url_for('reunioes')))

    # Salvamos o acesso na sessão!
    session['google_token'] = credenciais.token
    session['google_refresh_token'] = credenciais.refresh_token
    
    flash("Sua Conta do Google Agenda foi conectada com sucesso!", "success")
    # Redireciona de volta para a tela de acompanhamento
    return redirect(url_for('acompanhamento'))

# ==============================================================================
# INTEGRAÇÃO COM GOOGLE CALENDAR (MOTOR INTELIGENTE)
# ==============================================================================
@app.route('/desconectar-agenda')
@login_required
def desconectar_agenda():
    session.pop('google_token', None)
    session.pop('google_refresh_token', None)
    flash("Sua conta do Google Agenda foi desconectada do sistema.", "info")
    return voltar('acompanhamento')

def sincronizar_evento_agenda(titulo, descricao, data_inicio, horario_str="09:00", horario_fim_str="10:00"):
    """Grava o evento na agenda conectada pela pessoa: Microsoft 365 (Outlook) ou Google Agenda."""
    if conta_microsoft(current_user):
        import microsoft365
        token = token_microsoft(current_user)
        if not token:
            return False
        try:
            hora_i, min_i = map(int, horario_str.split(':'))
            hora_f, min_f = map(int, horario_fim_str.split(':'))
            inicio = data_inicio.replace(hour=hora_i, minute=min_i, second=0, microsecond=0)
            fim = data_inicio.replace(hour=hora_f, minute=min_f, second=0, microsecond=0)
            if fim <= inicio:
                fim = inicio + timedelta(hours=1)
            microsoft365.criar_evento(token, microsoft365.montar_evento(titulo, descricao, inicio, fim))
            return True
        except (microsoft365.ErroMicrosoft, ValueError) as erro:
            app.logger.warning("Agenda do Microsoft 365 não sincronizada: %s", erro)
            return False
    return sincronizar_evento_google(titulo, descricao, data_inicio, horario_str, horario_fim_str)


def sincronizar_evento_google(titulo, descricao, data_inicio, horario_str="09:00", horario_fim_str="10:00"):
    # Regra 1: Se o usuário não conectou a agenda, aborta silenciosamente
    if 'google_token' not in session:
        return False 
        
    try:
        import json
        from datetime import timedelta
        
        caminho_secreto = os.path.join(app.root_path, 'client_secret.json')
        with open(caminho_secreto, 'r') as f:
            dados_cliente = json.load(f)['web']
            
        creds = google.oauth2.credentials.Credentials(
            token=session['google_token'],
            refresh_token=session.get('google_refresh_token'),
            token_uri=dados_cliente['token_uri'],
            client_id=dados_cliente['client_id'],
            client_secret=dados_cliente['client_secret'],
            scopes=SCOPES
        )

        proxy = httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, 'proxy.server', 3128)
        http_base = httplib2.Http(proxy_info=proxy)
        http_autorizado = google_auth_httplib2.AuthorizedHttp(creds, http=http_base)
        service = build('calendar', 'v3', http=http_autorizado, cache_discovery=False)
        
        # Monta a data/hora exata de INÍCIO do Slot
        hora_i, min_i = map(int, horario_str.split(':'))
        inicio_dt = data_inicio.replace(hour=hora_i, minute=min_i, second=0)
        
        # Monta a data/hora exata de FIM do Slot
        hora_f, min_f = map(int, horario_fim_str.split(':'))
        fim_dt = data_inicio.replace(hour=hora_f, minute=min_f, second=0)
        
        # Trava de segurança: Se a hora de fim for antes da de início, corrige para +1h
        if fim_dt <= inicio_dt:
            fim_dt = inicio_dt + timedelta(hours=1)
        
        # Força o fuso horário de Brasília (GMT-3)
        inicio = inicio_dt.isoformat() + '-03:00'
        fim = fim_dt.isoformat() + '-03:00'
        
        evento = {
            'summary': titulo,
            'description': descricao,
            'start': {'dateTime': inicio, 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': fim, 'timeZone': 'America/Sao_Paulo'},
            'reminders': {'useDefault': True},
        }
        
        service.events().insert(calendarId='primary', body=evento).execute()
        return True
    except Exception as e:
        print(f"Erro silencioso ao sincronizar agenda: {e}")
        return False

from flask import jsonify

# ==============================================================================
# INTEGRAÇÃO COM IA - ESTILO NOTEBOOKLM
# ==============================================================================
@app.route('/chat-ia', methods=['POST'])
@login_required
def chat_ia():
    dados = request.get_json()
    mensagem_usuario = dados.get('mensagem', '')

    try:

        # 1. Coleta o contexto real do usuário no Banco de Dados
        contexto_estudos = ""
        if current_user.tipo_usuario == 'Aluno':
            acompanhamentos = Acompanhamento.query.filter_by(aluno_id=current_user.id, status='Iniciado').all()
            if acompanhamentos:
                for a in acompanhamentos:
                    curso = db.session.get(Curso, a.curso_id)
                    contexto_estudos += f"- Curso: {curso.nome_curso} (Progresso: {a.percentual_conclusao}%)\n"
                    contexto_estudos += f"  Anotações do aluno: {a.observacao_aluno or 'Nenhuma'}\n"
                    contexto_estudos += f"  Diretriz do mentor: {a.observacao or 'Nenhuma'}\n"
            else:
                contexto_estudos = "O aluno não possui cursos em andamento no momento."
        else:
            contexto_estudos = f"O usuário logado é um {current_user.tipo_usuario}. Responda como um assistente de produtividade para mentores."

        # 2. Constrói o System Prompt com as barreiras de segurança (Guardrails)
        instrucoes_tutor = f"""Você é o Assistente Gemini Notebook da plataforma de mentoria.
        Usuário atual: {current_user.nome}

        [CONTEXTO ACADÊMICO DO ALUNO]
        {contexto_estudos}

        [REGRAS DE CONDUTA]
        1. Atue como um mentor avançado: revise conceitos, arquitetura de soluções e políticas de segurança.
        2. Baseie-se nas 'Anotações do aluno' e na 'Diretriz do mentor' para personalizar a explicação.
        3. Se o usuário pedir um quiz, gere questões de múltipla escolha com a resposta correta detalhada logo abaixo.
        4. Nunca forneça respostas diretas de provas; guie o raciocínio.
        5. Formate a resposta usando HTML leve (use <br> para quebras de linha e <strong> para negrito).
        """


        import provedores_ia
        if not provedores_ia.ativo('acompanhamento'):
            return jsonify({'resposta': tt('O assistente de estudos está desligado pelo Administrador.', current_user.idioma)}), 503

        # Contas de teste (@local.com) não consomem a IA: os agentes recebem uma resposta fixa
        if eh_conta_de_teste(current_user):
            return jsonify({'resposta': tt('Modo de teste: contas de teste não consomem a IA. Sua mensagem chegou ao assistente.', current_user.idioma)})

        # A ordem de modelos (e a reserva) vem da tela Provedores de IA, com o teto de gasto do mês
        import credenciais_agentes
        import provedores_ia
        credenciais_agentes.carregar(app.config['SECRET_KEY'])
        resposta = provedores_ia.gerar('acompanhamento', instrucoes_tutor, [{'role': 'user', 'content': mensagem_usuario[:4000]}],
                                       max_tokens=2500, esforco='low', usuario_id=current_user.id)
        return jsonify({'resposta': resposta.texto})

    except Exception as e:
        # O detalhe técnico vai só para o log (não expõe chaves, cotas nem caminhos ao usuário)
        app.logger.warning(f"Chat IA falhou: {e}")
        return jsonify({'resposta': tt('Desculpe, o assistente está indisponível agora. Tente de novo em alguns minutos.', current_user.idioma)}), 503

# ==============================================================================
# ROTA: FORÇAR SINCRONIZAÇÃO DE HORÁRIOS SALVOS (BOTÃO AMIGÁVEL)
# ==============================================================================
@app.route('/acompanhamento/sincronizar_agenda/<int:acomp_id>', methods=['POST'])
@login_required
def sincronizar_agenda_acompanhamento(acomp_id):
    regstro = db.session.get(Acompanhamento, acomp_id)
    
    if not regstro:
        flash("Acompanhamento não encontrado.", "danger")
        return redirect(url_for('acompanhamento'))

    # Exige uma agenda conectada (Google ou Microsoft 365)
    if not agenda_conectada():
        flash(tt('Conecte sua agenda (Google ou Microsoft 365) na lista Agenda, em Acompanhamento.', current_user.idioma), "warning")
        return redirect(url_for('acompanhamento'))

    if regstro.planejamento_estudos:
        curso_obj = db.session.get(Curso, regstro.curso_id)
        
        # Quebra a string de horários que já está guardada no banco
        slots = regstro.planejamento_estudos.split('|')
        sucesso_count = 0
        
        from datetime import datetime, timezone, timedelta
        fuso_br = timezone(timedelta(hours=-3))
        hoje = datetime.now(fuso_br).date()
        
        for slot in slots:
            partes = slot.split('::')
            if len(partes) == 3:
                data_br, hora_ini, hora_fim = partes
                try:
                    # Converte a data para verificar se não é do passado
                    data_obj = datetime.strptime(data_br, '%d/%m/%Y').date()
                    
                    if data_obj >= hoje:
                        sucesso = sincronizar_evento_agenda(
                            titulo=f"Estudo: {curso_obj.nome_curso}",
                            descricao=f"Sessão focada no curso: {curso_obj.nome_curso}.",
                            data_inicio=datetime.strptime(data_br, '%d/%m/%Y'),
                            horario_str=hora_ini,
                            horario_fim_str=hora_fim
                        )
                        if sucesso:
                            sucesso_count += 1
                except Exception:
                    pass
        
        if sucesso_count > 0:
            flash(f"{sucesso_count} horário(s) futuro(s) sincronizado(s) com sucesso na sua Google Agenda!", "success")
        else:
            flash("Nenhum horário futuro encontrado para sincronizar ou erro de comunicação com o Google.", "warning")

    return redirect(url_for('acompanhamento', abrir_modal=regstro.id))


# =========================================================================
# MOTOR DE BACKUP EM SEGUNDO PLANO (WATCHER)
# =========================================================================
def rotina_de_backups(app_context):
    """Com 'python app.py' no computador: confere os agendamentos de backup a cada minuto."""
    import backup_servico
    with app_context:
        while True:
            try:
                backup_servico.executar_vencidos()
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao processar backup agendado: {e}")
            time.sleep(60)

def iniciar_agendador(app):
    # Inicia a tarefa invisível junto com o servidor Flask
    thread = threading.Thread(target=rotina_de_backups, args=(app.app_context(),))
    thread.daemon = True # Permite que a thread seja encerrada ao fechar o terminal
    thread.start()

# ==============================================================================
# ROTA: PAINEL DE GESTÃO E VALIDAÇÃO DE FREQUÊNCIA (COM FILTROS E RANKING)
# ==============================================================================
def situacao_frequencia(aluno, turma, hoje=None):
    """Regra do MEC parametrizada: frequência mínima, alerta de risco e dias letivos por semana vêm da tela
    Parâmetros de regras. Devolve None se a turma ainda não começou; senão a situação do aluno na frequência."""
    from regras_negocio import regra
    hoje = hoje or datetime.utcnow().date()
    if not turma or turma.data_inicio > hoje:
        return None
    data_fim_calculo = hoje if hoje < turma.data_termino else turma.data_termino
    dias_corridos = (data_fim_calculo - turma.data_inicio).days + 1
    dias_semana = int(regra('freq_dias_letivos_semana'))
    semanas, dias_extras = divmod(dias_corridos, 7)
    dias_letivos = semanas * dias_semana + min(dias_extras, dias_semana)  # aulas esperadas até agora
    if dias_letivos <= 0:
        return None
    limite_faltas = int(dias_letivos * (100 - int(regra('freq_minima_pct'))) / 100)  # cota de faltas permitida
    presencas = Frequencia.query.filter(Frequencia.usuario_id == aluno.id, Frequencia.tipo_presenca.in_(['Online', 'Presencial'])).count()
    faltas = Frequencia.query.filter(Frequencia.usuario_id == aluno.id, Frequencia.tipo_presenca.in_(['Falta', 'Falta Automática'])).count()
    taxa = min(100, presencas / dias_letivos * 100)  # não passa de 100% se o aluno registrou fim de semana
    if faltas > limite_faltas:
        situacao = 'Reprovado por faltas'
    elif faltas and faltas >= limite_faltas * int(regra('freq_alerta_cota_pct')) / 100:
        situacao = 'Em risco'  # sem nenhuma falta não há risco (antes, turma recém-começada com cota 0 marcava todos)
    else:
        situacao = 'Regular'
    return {'situacao': situacao, 'faltas': faltas, 'limite_faltas': limite_faltas, 'dias_letivos': dias_letivos,
            'presencas': presencas, 'taxa_presenca': taxa}


def situacao_no_diario(acompanhamento, frequencia):
    """Situação da disciplina no diário: faltas primeiro (regra do MEC), depois a média técnica + postura."""
    from regras_negocio import regra
    notas = [n for n in (acompanhamento.nota_tecnica, acompanhamento.nota_postura) if n is not None]
    media = round(sum(notas) / len(notas), 2) if notas else None
    if frequencia and frequencia['situacao'] == 'Reprovado por faltas':
        return 'Reprovado por faltas', media
    if media is None:
        return 'Sem nota', None
    if media < float(regra('nota_minima_diario')):
        return 'Reprovado por nota', media
    return ('Aprovado (em risco por faltas)' if frequencia and frequencia['situacao'] == 'Em risco' else 'Aprovado'), media


# Situações que a gestão pode atribuir a um registro de frequência (as opções da tela de validação)
SITUACOES_FREQUENCIA = ['Presencial', 'Online', 'Falta', 'Falta Justificada']


@app.route('/admin/frequencia', methods=['GET', 'POST'])
@login_required
def gerenciar_frequencia():
    # Trava: Alunos não podem aceder a este painel
    if current_user.tipo_usuario == 'Aluno':
        flash('Acesso Negado: Apenas a equipa de gestão pode aceder às frequências.', 'danger')
        return redirect(url_for('dashboard'))

    # Se o formulário de validação for submetido (POST)
    if request.method == 'POST':
        freq_id = request.form.get('frequencia_id')
        obs_admin = request.form.get('observacoes_admin')
        alterar_status = request.form.get('alterar_status') # Novo campo de ação do modal
        
        registro = db.session.get(Frequencia, freq_id)
        # Só as situações da tela e só os jovens que a pessoa acompanha
        if alterar_status and alterar_status not in SITUACOES_FREQUENCIA:
            flash(tt('Situação de frequência inválida.', current_user.idioma), 'warning')
            return redirect(url_for('gerenciar_frequencia'))
        visiveis = ids_jovens_visiveis(current_user)
        if registro and visiveis is not None and registro.usuario_id not in visiveis:
            flash(tt('Acesso negado: você só valida a frequência dos jovens que acompanha.', current_user.idioma), 'danger')
            return redirect(url_for('gerenciar_frequencia'))
        if registro:
            registro.validado_admin = True
            registro.admin_id = current_user.id
            
            # Se o mentor preencheu observações, junta com o que já existia ou cria novo
            if obs_admin:
                if registro.observacoes_admin:
                    registro.observacoes_admin += f" | {obs_admin}"
                else:
                    registro.observacoes_admin = obs_admin
            
            # Se o mentor escolheu alterar o status da falta/presença
            if alterar_status:
                registro.tipo_presenca = alterar_status
                
            db.session.commit()
            flash('Registo de presença validado/atualizado com sucesso!', 'success')
            
        return redirect(url_for('gerenciar_frequencia'))

    # ==========================================
    # LÓGICA DE FILTROS (MÉTODO GET)
    # ==========================================
    filtro_aluno = request.args.get('aluno_id')
    filtro_tipo = request.args.get('tipo_presenca')
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')

    query = Frequencia.query

    visiveis = ids_jovens_visiveis(current_user)
    if visiveis is not None:
        query = query.filter(Frequencia.usuario_id.in_(list(visiveis | {current_user.id})))

    if filtro_aluno:
        query = query.filter(Frequencia.usuario_id == filtro_aluno)
    
    if filtro_tipo:
        if filtro_tipo == 'Faltas':
            query = query.filter(Frequencia.tipo_presenca.in_(['Falta', 'Falta Automática']))
        elif filtro_tipo == 'Presencas':
            query = query.filter(Frequencia.tipo_presenca.in_(['Online', 'Presencial']))
        else:
            query = query.filter(Frequencia.tipo_presenca == filtro_tipo)

    if filtro_data_inicio:
        query = query.filter(db.func.date(Frequencia.data_registro) >= filtro_data_inicio)
    
    if filtro_data_fim:
        query = query.filter(db.func.date(Frequencia.data_registro) <= filtro_data_fim)

    # Registos finais filtrados
    registros = query.order_by(Frequencia.data_registro.desc()).all()

    # ==========================================
    # LÓGICA DO RANKING DE FALTAS (DETALHAMENTO)
    # ==========================================
    from sqlalchemy import func
    # Agrupa por aluno, conta as faltas reais (ignorando justificadas)
    ranking_faltas = db.session.query(
        Usuario.nome,
        func.count(Frequencia.id).label('total_faltas')
    ).join(Frequencia, Usuario.id == Frequencia.usuario_id) \
     .filter(Frequencia.tipo_presenca.in_(['Falta', 'Falta Automática'])) \
     .group_by(Usuario.id, Usuario.nome) \
     .order_by(func.count(Frequencia.id).desc()) \
     .limit(10).all()

    # Trazemos a lista de alunos para preencher o select do filtro
    alunos = Usuario.query.filter_by(tipo_usuario='Aluno').all()
    if visiveis is not None:
        alunos = [a for a in alunos if a.id in visiveis]


    # ==========================================
    # CÁLCULOS DOS KPIs DE FREQUÊNCIA (REGRA MEC 75%)
    # ==========================================
    # 1. Total de Faltas Justificadas no sistema (Abonadas)
    kpi_faltas_justificadas = Frequencia.query.filter(Frequencia.tipo_presenca == 'Falta Justificada').count()

    # Preparação para calcular taxas por aluno
    from datetime import datetime
    hoje = datetime.utcnow().date()
    
    # Busca todas as turmas ativas que tenham alunos
    turmas_ativas = Turma.query.filter(Turma.data_termino >= hoje).all()
    
    kpi_taxa_presenca_geral = 0
    kpi_alunos_risco = 0
    kpi_alunos_reprovados = 0
    total_alunos_avaliados = 0
    soma_taxas_presenca = 0

    for turma in turmas_ativas:
        # Regra parametrizada (Administração › Parâmetros de regras): mesma conta usada no diário de classe
        for aluno in turma.alunos:
            situacao = situacao_frequencia(aluno, turma, hoje)
            if situacao is None:
                continue
            total_alunos_avaliados += 1
            soma_taxas_presenca += situacao['taxa_presenca']
            if situacao['situacao'] == 'Reprovado por faltas':
                kpi_alunos_reprovados += 1
            elif situacao['situacao'] == 'Em risco':
                kpi_alunos_risco += 1

    if total_alunos_avaliados > 0:
        kpi_taxa_presenca_geral = round(soma_taxas_presenca / total_alunos_avaliados)
    else:
        kpi_taxa_presenca_geral = 100 # Sem alunos, assumimos perfeição

    # Formatando para a view
    str_taxa_presenca = f"{kpi_taxa_presenca_geral}%"

    return render_template('admin_frequencia.html', 
                           registros=registros, 
                           alunos=alunos,
                           ranking_faltas=ranking_faltas,
                           filtro_aluno=filtro_aluno,
                           filtro_tipo=filtro_tipo,
                           filtro_data_inicio=filtro_data_inicio,
                           filtro_data_fim=filtro_data_fim,
                           kpi_taxa_presenca=str_taxa_presenca,
                           kpi_alunos_risco=kpi_alunos_risco,
                           kpi_alunos_reprovados=kpi_alunos_reprovados,
                           kpi_faltas_justificadas=kpi_faltas_justificadas)


# ==============================================================================
# PROCESSADOR DE CONTEXTO GLOBAL: TRAVA DE FREQUÊNCIA DIÁRIA
# ==============================================================================
@app.context_processor
def verificar_frequencia_diaria():
    precisa_registrar = False
    
    # Só dispara se estiver logado E for Aluno, Mentor ou Professor
    if current_user.is_authenticated and current_user.tipo_usuario in PERFIS_REGISTRAM_FREQUENCIA \
            and request.endpoint not in ['onboarding', 'trilha_tcc']:
        from datetime import datetime, time
        
        hoje_inicio = datetime.combine(datetime.utcnow().date(), time.min)
        hoje_fim = datetime.combine(datetime.utcnow().date(), time.max)
        
        # Verificação blindada com intervalo exato de tempo
        ja_registrou = Frequencia.query.filter(
            Frequencia.usuario_id == current_user.id,
            Frequencia.data_registro >= hoje_inicio,
            Frequencia.data_registro <= hoje_fim
        ).first()
        
        if not ja_registrou:
            precisa_registrar = True
            
    return dict(precisa_registrar_frequencia=precisa_registrar)

# ==============================================================================
# ROTA: GRAVAR A FREQUÊNCIA (Online, Presencial ou Falta Automática)
# ==============================================================================
@app.route('/registrar_frequencia', methods=['POST'])
@login_required
def registrar_frequencia():
    from datetime import datetime
    
    tipo = request.form.get('tipo_presenca')
    observacoes = request.form.get('observacoes', '')
    
    hoje = datetime.utcnow().date()
    ja_registrou = Frequencia.query.filter(
        Frequencia.usuario_id == current_user.id,
        db.func.date(Frequencia.data_registro) == hoje
    ).first()
    
    if not ja_registrou:
        nova_freq = Frequencia(
            usuario_id=current_user.id,
            tipo_presenca=tipo,
            observacoes=observacoes
        )
        db.session.add(nova_freq)
        db.session.commit()
        
        if tipo == 'Falta' or tipo == 'Falta Automática':
            flash('Ausência registrada automaticamente. Caso seja um erro, contate o seu mentor.', 'danger')
        else:
            flash('Presença registrada com sucesso! Bom trabalho.', 'success')
            
    # Devolve o usuário para a página em que ele estava
    return voltar('dashboard')

# ==============================================================================
# ROTA: HUB EDUCACIONAL (CATÁLOGO, PARCEIROS E TURMAS)
# ==============================================================================
@app.route('/admin/turmas', methods=['GET', 'POST'])
@login_required
def gerenciar_turmas():
    from datetime import datetime  # <--- ADICIONE ESTA LINHA AQUI
    if current_user.tipo_usuario not in PERFIS_GESTAO_CURSOS:
        flash('Acesso negado. Apenas a equipa de gestão pode aceder ao Hub Educacional.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        acao = request.form.get('acao')

        # ---------------------------------------------------------
        # 1. Módulo: Catálogo de Cursos (Nova aba 01)
        # ---------------------------------------------------------
        if acao == 'novo_curso':
            nome = request.form.get('nome')
            plataforma = request.form.get('plataforma')
            tipo = request.form.get('tipo')
            carga_horaria = request.form.get('carga_horaria')
            link = request.form.get('link')
            exige_certificado = request.form.get('exige_certificado') == 'Sim'
            status = request.form.get('status', 'Ativo')

            novo_curso = Curso(
                nome_curso=nome,
                plataforma=plataforma,
                tipo=tipo,
                carga_horaria=carga_horaria,
                url=link,  # <--- Tem de estar escrito "url=" do lado esquerdo
                exige_certificado=exige_certificado,
                status=status,
            )
            db.session.add(novo_curso)
            db.session.commit()
            flash(f'Curso "{nome}" adicionado ao catálogo com sucesso!', 'success')

        # ---------------------------------------------------------
        # 2. Módulo: Parceiros B2B (Empresas)
        # ---------------------------------------------------------
        elif acao == 'nova_empresa':
            nome = request.form.get('nome')
            c1_nome = request.form.get('contato_nome')
            c1_email = request.form.get('contato_email')
            c2_nome = request.form.get('contato_sec_nome')
            c2_email = request.form.get('contato_sec_email')
            
            gestor_id = request.form.get('gestor_id')
            mentores_selecionados = request.form.getlist('mentores_ids')
            
            nova_emp = Empresa(
                nome=nome, 
                contato_nome=c1_nome, 
                contato_email=c1_email,
                contato_sec_nome=c2_nome,       # NOVO: Salva direto na coluna certa
                contato_sec_email=c2_email,     # NOVO: Salva direto na coluna certa
                gestor_id=int(gestor_id) if gestor_id else None
            )
            db.session.add(nova_emp)
            
            if mentores_selecionados:
                for mid in mentores_selecionados:
                    mentor_obj = db.session.get(Usuario, int(mid))
                    if mentor_obj:
                        nova_emp.mentores.append(mentor_obj)
                        
            db.session.commit()
            flash(f'Parceiro "{nome}" cadastrado com sucesso!', 'success')

        # ---------------------------------------------------------
        # 2.5 Módulo: Editar Empresa
        # ---------------------------------------------------------
        elif acao == 'editar_empresa':
            emp_id = request.form.get('empresa_id')
            empresa = db.session.get(Empresa, int(emp_id))
            
            if empresa:
                # O 'nome' agora é obrigatório e vem preenchido do HTML correto
                novo_nome = request.form.get('nome')
                if novo_nome: 
                    empresa.nome = novo_nome
                
                empresa.contato_nome = request.form.get('contatos')
                empresa.contato_email = request.form.get('emails')
                empresa.contato_sec_nome = request.form.get('contato_sec_nome')
                empresa.contato_sec_email = request.form.get('contato_sec_email')
                
                gestor_id = request.form.get('gestor_id')
                empresa.gestor_id = int(gestor_id) if gestor_id else None
                
                mentores_selecionados = request.form.getlist('mentores_ids')
                empresa.mentores = [] 
                
                if mentores_selecionados:
                    for mid in mentores_selecionados:
                        mentor_obj = db.session.get(Usuario, int(mid))
                        if mentor_obj:
                            empresa.mentores.append(mentor_obj)
                
                db.session.commit()
                flash(f'Dados da empresa "{empresa.nome}" atualizados com sucesso!', 'success')

        # ---------------------------------------------------------
        # 3. Módulo: Turmas e Trilhas (O Motor de Matrícula)
        # ---------------------------------------------------------
        elif acao == 'nova_turma':
            nome = request.form.get('nome')
            empresa_id = request.form.get('empresa_id')
            grupo_id = request.form.get('grupo_id') 
            cursos_selecionados = request.form.getlist('cursos_ids')
            data_inicio_str = request.form.get('data_inicio')
            data_termino_str = request.form.get('data_termino')

            if data_inicio_str and data_termino_str and cursos_selecionados:
                from datetime import datetime
                try:
                    try:
                        dt_ini = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                        dt_fim = datetime.strptime(data_termino_str, '%Y-%m-%d').date()
                    except ValueError:
                        dt_ini = datetime.strptime(data_inicio_str, '%d/%m/%Y').date()
                        dt_fim = datetime.strptime(data_termino_str, '%d/%m/%Y').date()
                    
                    nova_turma = Turma(
                        nome=nome,
                        empresa_id=empresa_id if empresa_id else None,
                        data_inicio=dt_ini,
                        data_termino=dt_fim
                    )
                    db.session.add(nova_turma)
                    
                    for cid in cursos_selecionados:
                        curso_obj = db.session.get(Curso, int(cid))
                        if curso_obj:
                            nova_turma.cursos.append(curso_obj)
                            
                    if grupo_id:
                        grupo_obj = db.session.get(Grupo, int(grupo_id))
                        if grupo_obj:
                            alunos_do_grupo = getattr(grupo_obj, 'membros', getattr(grupo_obj, 'usuarios', []))
                            for aluno in alunos_do_grupo:
                                if aluno not in nova_turma.alunos:
                                    nova_turma.alunos.append(aluno)
                                    for curso_obj in nova_turma.cursos:
                                        existe = Acompanhamento.query.filter_by(aluno_id=aluno.id, curso_id=curso_obj.id).first()
                                        if not existe:
                                            novo_acomp = Acompanhamento(
                                                aluno_id=aluno.id,
                                                curso_id=curso_obj.id,
                                                status='Iniciado',
                                                data_inicio=nova_turma.data_inicio,
                                                data_termino=nova_turma.data_termino
                                            )
                                            db.session.add(novo_acomp)
                                            
                    db.session.commit()
                    flash(f'Turma "{nome}" criada e alunos matriculados!', 'success')
                    
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro no Banco de Dados: {str(e)}', 'danger')
            else:
                flash('Preencha todos os campos e selecione pelo menos um curso.', 'warning')

        # ---------------------------------------------------------
        # 4. Módulo: Matricular Alunos na Turma (A Mágica)
        # ---------------------------------------------------------
        elif acao == 'matricular_alunos':
            turma_id = request.form.get('turma_id')
            alunos_ids = request.form.getlist('alunos_ids')
            
            turma = db.session.get(Turma, int(turma_id))
            if turma and alunos_ids:
                cadastrados = 0
                for a_id in alunos_ids:
                    aluno = db.session.get(Usuario, int(a_id))
                    if aluno and aluno not in turma.alunos:
                        turma.alunos.append(aluno)
                        cadastrados += 1
                        
                        for curso in turma.cursos:
                            existe = Acompanhamento.query.filter_by(aluno_id=aluno.id, curso_id=curso.id).first()
                            if not existe:
                                novo_acomp = Acompanhamento(
                                    aluno_id=aluno.id,
                                    curso_id=curso.id,
                                    status='Iniciado',
                                    data_inicio=turma.data_inicio,
                                    data_termino=turma.data_termino
                                )
                                db.session.add(novo_acomp)
                db.session.commit()
                flash(f'{cadastrados} aluno(s) matriculado(s) com sucesso na turma {turma.nome}!', 'success')

        # ---------------------------------------------------------
        # 5. Módulo: Criação Rápida de Grupo (Atalho do Hub)
        # ---------------------------------------------------------
        elif acao == 'novo_grupo_rapido':
            nome_grupo = request.form.get('nome_grupo')
            alunos_selecionados = request.form.getlist('alunos_ids')
                
            if nome_grupo:
                novo_grupo = Grupo(nome=nome_grupo)
                db.session.add(novo_grupo)
                    
                for aluno_id in alunos_selecionados:
                    aluno = db.session.get(Usuario, int(aluno_id))
                    if aluno:
                        novo_grupo.membros.append(aluno)
                    
                db.session.commit()
                flash(f'Grupo "{nome_grupo}" criado com sucesso! Agora já pode selecioná-lo na turma.', 'success')

        # ---------------------------------------------------------
        # 6. Módulo: Criação Rápida de Usuário (Atalho do Hub)
        # ---------------------------------------------------------
        elif acao == 'novo_usuario_rapido':
            from datetime import datetime # NOVO: Importando a biblioteca de data/hora

            nome = request.form.get('nome_usuario')
            email = request.form.get('email_usuario').strip()
            nivel_rapido = perfis_acesso.resolver_nivel(request.form.get('tipo_usuario_rapido'))
            tipo_usuario = nivel_rapido[0] if nivel_rapido else None
            senha_plana = request.form.get('senha_usuario')

            if not nivel_rapido or not pode_atribuir_nivel(current_user, tipo_usuario):
                flash(tt('Escolha um nível de acesso válido.', current_user.idioma), "danger")
            elif not re.match(PADRAO_EMAIL, email or ''):
                flash("Erro: O e-mail digitado não é válido.", "danger")
            elif not re.match(padrao_senha_forte(), senha_plana or ''):
                flash(f"Segurança: A senha deve ter no mínimo {regra('senha_min_caracteres')} caracteres e incluir letras maiúsculas, minúsculas, números e caracteres especiais.", "danger")
            elif Usuario.query.filter_by(email=email).first():
                flash(f"Erro: O e-mail '{email}' já está cadastrado no sistema.", "danger")
            else:
                senha_criptografada = bcrypt.generate_password_hash(senha_plana).decode('utf-8')
                novo_usuario = Usuario(
                    nome=nome, 
                    email=email, 
                    tipo_usuario=tipo_usuario,
                    status='Ativo',
                    senha=senha_criptografada,
                    data_criacao=datetime.now(),
                    data_ultima_troca_senha=datetime.now(),
                    criado_por=current_user.nome,
                    forcar_troca_senha=True,
                    perfil_personalizado_id=nivel_rapido[1]
                )
                db.session.add(novo_usuario)
                db.session.commit()
                flash(f"{tipo_usuario} '{nome}' cadastrado com sucesso! Já o pode selecionar na lista.", "success")

        # ---------------------------------------------------------
        # 7. Módulo: Importação em Massa (Planilha CSV)
        # ---------------------------------------------------------
        elif acao == 'importar_csv':
            import csv
            import io
            
            arquivo = request.files.get('arquivo_csv')
            
            if arquivo and arquivo.filename.endswith('.csv'):
                try:
                    # Lê o arquivo que o usuário enviou
                    stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
                    leitor_csv = csv.DictReader(stream)
                    
                    sucessos = 0
                    ignorados = 0
                    credenciais = []

                    for linha in leitor_csv:
                        # Procura pelas colunas 'nome' e 'email' (ignorando maiúsculas/minúsculas)
                        nome_csv = linha.get('nome') or linha.get('Nome') or linha.get('NOME')
                        email_csv = linha.get('email') or linha.get('Email') or linha.get('EMAIL')

                        if nome_csv and email_csv:
                            email_limpo = email_csv.strip().lower()

                            # Só cria o aluno se o e-mail for válido e ainda não existir no sistema
                            if re.match(PADRAO_EMAIL, email_limpo) and not Usuario.query.filter_by(email=email_limpo).first():
                                # Senha provisória aleatória e forte para cada aluno (nada de senha fixa no código)
                                senha_provisoria = gerar_senha_provisoria()
                                novo_aluno = Usuario(
                                    nome=nome_csv.strip(),
                                    email=email_limpo,
                                    tipo_usuario='Aluno',
                                    status='Ativo',
                                    senha=bcrypt.generate_password_hash(senha_provisoria).decode('utf-8'),
                                    forcar_troca_senha=True
                                )
                                db.session.add(novo_aluno)
                                credenciais.append((nome_csv.strip(), email_limpo, senha_provisoria))
                                sucessos += 1
                            else:
                                ignorados += 1

                    db.session.commit()

                    mensagem = f'{sucessos} novos alunos importados com sucesso!'
                    if ignorados > 0:
                        mensagem += f' ({ignorados} linha(s) com e-mail inválido ou já cadastrado foram ignoradas).'
                    flash(mensagem, 'success')
                    if credenciais:
                        # Entrega as senhas provisórias numa planilha (uma única vez); a troca é obrigatória no primeiro acesso
                        saida = io.StringIO()
                        escritor = csv.writer(saida, delimiter=';')
                        escritor.writerow(['nome', 'email', 'senha_provisoria'])
                        escritor.writerows(credenciais)
                        return send_file(io.BytesIO(('﻿' + saida.getvalue()).encode('utf-8')), mimetype='text/csv', as_attachment=True,
                                         download_name=f"senhas_provisorias_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
                    
                except Exception as e:
                    flash(f'Erro ao ler o arquivo. Certifique-se de que é um CSV válido. Detalhe: {str(e)}', 'danger')
            else:
                flash('Formato inválido. Por favor, envie um arquivo .csv', 'danger')

        # ---------------------------------------------------------
        # 8. Módulo: Editar e Excluir Turma
        # ---------------------------------------------------------
        elif acao == 'editar_turma':
            turma_id = request.form.get('turma_id')
            turma = db.session.get(Turma, int(turma_id))
            
            if turma:
                turma.nome = request.form.get('nome')
                data_inicio_str = request.form.get('data_inicio')
                data_termino_str = request.form.get('data_termino')
                
                if data_inicio_str and data_termino_str:
                    from datetime import datetime
                    turma.data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                    turma.data_termino = datetime.strptime(data_termino_str, '%Y-%m-%d').date()
                            
                db.session.commit()
                flash(f'Turma "{turma.nome}" atualizada com sucesso!', 'success')

        # ---------------------------------------------------------
        # 9. Módulo: Excluir Turma
        # ---------------------------------------------------------
        elif acao == 'excluir_turma':
            turma_id = request.form.get('turma_id')
            turma = db.session.get(Turma, int(turma_id))
            
            if turma:
                nome_turma = turma.nome
                db.session.delete(turma)
                db.session.commit()
                flash(f'Turma "{nome_turma}" excluída com sucesso!', 'success')

    # =========================================================
    # CARREGAMENTO DE DADOS PARA PREENCHER AS 3 ABAS DA TELA (MÉTODO GET)
    # =========================================================
    if current_user.tipo_usuario == 'Admin B2B':
        empresas = Empresa.query.filter_by(gestor_id=current_user.id).order_by(Empresa.nome).all()
        turmas = Turma.query.join(Empresa).filter(Empresa.gestor_id == current_user.id).order_by(Turma.data_inicio.desc()).all()
    else:
        empresas = Empresa.query.order_by(Empresa.nome).all()
        turmas = Turma.query.order_by(Turma.data_inicio.desc()).all()
        
    cursos = Curso.query.order_by(Curso.nome_curso).all() 
    alunos = Usuario.query.filter_by(tipo_usuario='Aluno', status='Ativo').order_by(Usuario.nome).all() 
    grupos = Grupo.query.order_by(Grupo.nome).all() 
    
    # Traz apenas quem é puramente Mentor (ignora os gestores Admin B2B para não dar erro)
    mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_ORIENTADORES), Usuario.status=='Ativo').order_by(Usuario.nome).all()
    gestores = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_GESTORES_DE_TURMA), Usuario.status=='Ativo').order_by(Usuario.nome).all()

    # --- LÓGICA BLINDADA: MENTORES DISPONÍVEIS (POR ID) ---
    mentores_em_uso_ids = []
    for emp in empresas:
        for m in emp.mentores:
            mentores_em_uso_ids.append(m.id)
            
    # Filtra mantendo APENAS os mentores cujo ID NÃO está na lista de uso
    mentores_disponiveis = [m for m in mentores if m.id not in mentores_em_uso_ids]
    # ------------------------------------------------------

    # 2. Enviar tudo para o HTML
    from models import AulaCurso
    aulas_por_curso = dict(db.session.query(AulaCurso.curso_id, db.func.count(AulaCurso.id)).group_by(AulaCurso.curso_id).all())
    return render_template('admin_turmas.html', 
                           aulas_por_curso=aulas_por_curso,
                           cursos=cursos, 
                           empresas=empresas,
                           grupos=grupos,
                           turmas=turmas,
                           mentores=mentores,
                           gestores=gestores,
                           alunos=alunos,
                           mentores_disponiveis=mentores_disponiveis)
    
# ==============================================================================
# ROTA: DIÁRIO DE CLASSE (LANÇAMENTO DE NOTAS)
# ==============================================================================
@app.route('/admin/notas', methods=['GET', 'POST'])
@login_required
def gerenciar_notas():
    if current_user.tipo_usuario == 'Aluno':
        flash('Acesso negado. Apenas mentores e gestores podem lançar notas.', 'danger')
        return redirect(url_for('dashboard'))

    turmas = Turma.query.filter_by(status='Ativa').order_by(Turma.nome).all()
    turma_selecionada_id = request.args.get('turma_id')
    turma_selecionada = None
    dados_tabela = []

    if turma_selecionada_id:
        turma_selecionada = db.session.get(Turma, int(turma_selecionada_id))
        if turma_selecionada:
            cursos_ids = [c.id for c in turma_selecionada.cursos]
            
            # Puxa os alunos da turma e os seus respetivos acompanhamentos
            for aluno in turma_selecionada.alunos:
                if cursos_ids:
                    acompanhamentos = Acompanhamento.query.filter(
                        Acompanhamento.aluno_id == aluno.id,
                        Acompanhamento.curso_id.in_(cursos_ids)
                    ).all()
                else:
                    acompanhamentos = []
                
                frequencia = situacao_frequencia(aluno, turma_selecionada)
                dados_tabela.append({
                    'aluno': aluno,
                    'acompanhamentos': acompanhamentos,
                    'frequencia': frequencia,
                    # Situação de cada disciplina pelas regras parametrizadas (faltas do MEC + média mínima)
                    'situacoes': {a.id: situacao_no_diario(a, frequencia) for a in acompanhamentos},
                })

    if request.method == 'POST':
        # Valida antes de gravar: notas de 0 a 10 (vírgula ou ponto); com qualquer nota inválida, nada é gravado
        invalidas = []
        for chave, valor in request.form.items():
            if chave.startswith(('nota_tecnica_', 'nota_postura_')) and valor.strip():
                try:
                    numero = float(valor.replace(',', '.'))
                except ValueError:
                    numero = None
                if numero is None or not 0 <= numero <= NOTA_MAXIMA:
                    invalidas.append(valor)
        if invalidas:
            flash(tt('Notas devem estar entre 0 e 10. Nada foi gravado; confira: {valores}', current_user.idioma)
                  .format(valores=', '.join(invalidas[:5])), 'danger')
            return redirect(url_for('gerenciar_notas', turma_id=turma_selecionada_id))
        # Varre todos os campos enviados pelo formulário e salva as notas
        for chave, valor in request.form.items():
            if chave.startswith('nota_tecnica_'):
                acomp_id = int(chave.split('_')[-1])
                nota_tec_str = valor.replace(',', '.') if valor else None
                
                nota_postura_str = request.form.get(f'nota_postura_{acomp_id}')
                nota_postura_str = nota_postura_str.replace(',', '.') if nota_postura_str else None
                
                acomp = db.session.get(Acompanhamento, acomp_id)
                if acomp:
                    acomp.nota_tecnica = float(nota_tec_str) if nota_tec_str else None
                    acomp.nota_postura = float(nota_postura_str) if nota_postura_str else None
        
        db.session.commit()
        flash('Diário de Classe atualizado com sucesso!', 'success')
        return redirect(url_for('gerenciar_notas', turma_id=turma_selecionada_id))

    return render_template('admin_notas.html', turmas=turmas, turma_selecionada=turma_selecionada, dados=dados_tabela)

# =========================================================
# ROTA INVISÍVEL PARA BUSCAR MENTORES DA EMPRESA (VIA AJAX)
# =========================================================
@app.route('/api/mentores_empresa/<int:empresa_id>')
@login_required
def api_mentores_empresa(empresa_id):
    from flask import jsonify
    from models import Empresa
    
    empresa = db.session.get(Empresa, empresa_id)
    
    if empresa:
        # Pega apenas os mentores desta empresa específica.
        # CRÍTICO: Transforma o ID num texto (str) para evitar bugs no TomSelect
        mentores_data = [{"id": str(m.id), "nome": m.nome} for m in empresa.mentores]
        return jsonify(mentores_data)
    
    return jsonify([]) # Se não tiver empresa, devolve vazio

# ==============================================================================
# BANCA DE AVALIAÇÃO DO TCC — avaliadores, agenda, entregas e check-in/out
# ==============================================================================
PERFIS_GESTAO_BANCA = ['Administrador', 'Mentor Administrador', 'Admin B2B']
TIPO_AVALIADOR = 'Avaliador Banca'
# Quem pode ser escalado numa banca: executivos convidados e a equipe de mentoria
PERFIS_ESCALAVEIS_BANCA = [TIPO_AVALIADOR, 'Mentor', 'Professor', 'Mentor Administrador']
PASTA_TCC = os.path.join(app.config['UPLOAD_FOLDER'], 'tcc')
os.makedirs(PASTA_TCC, exist_ok=True)
TIPOS_ENTREGA_TCC = {'Escrito final': {'pdf'}, 'Slides da apresentação': {'pdf', 'pptx', 'ppt'}}
LIMITE_ENTREGA_MB = 20

# O Avaliador Banca (executivo convidado) só enxerga o que é da banca dele
ENDPOINTS_AVALIADOR = {'login', 'logout', 'static', 'dashboard', 'onboarding', 'aceitar_termos', 'trocar_senha_obrigatoria',
                       'cadastrar_perguntas', 'recuperar_senha', 'alterar_tema', 'alterar_idioma', 'desativar_tour',
                       'central_notificacoes', 'abrir_notificacao', 'portal_demandas', 'biblioteca_tccs',
                       'bater_ponto_voluntariado', 'lancamento_manual_voluntariado', 'minhas_bancas', 'relogio_banca',
                       'painel_banca', 'perguntas_banca', 'cronometro_banca', 'estado_cronometro_banca', 'telao_banca',
                       'baixar_entrega_tcc', 'curriculo_avaliador', 'ficha_banca', 'emitir_certificado', 'meus_certificados',
                       'baixar_acervo', 'verificar_certificado', 'repositorio_publico', 'baixar_repositorio_publico'}


@app.before_request
def restringir_avaliador_banca():
    if current_user.is_authenticated and current_user.tipo_usuario == TIPO_AVALIADOR \
            and request.endpoint and request.endpoint not in ENDPOINTS_AVALIADOR:
        flash("Acesso negado.", "danger")
        return redirect(url_for('minhas_bancas'))


def eh_avaliador_da_banca(usuario, banca):
    return banca is not None and usuario in banca.avaliadores


def pode_gerir_bancas(usuario):
    return usuario.tipo_usuario in PERFIS_GESTAO_BANCA


def bancas_visiveis_gestao(usuario):
    """Agenda da gestão. O Gestor B2B vê as bancas com jovens das suas empresas ou avaliadores da sua empresa."""
    from models import Banca
    todas = Banca.query.order_by(Banca.data_hora).all()
    if usuario.tipo_usuario != 'Admin B2B':
        return todas
    jovens = ids_jovens_visiveis(usuario) or set()
    empresas = {e.nome for e in Empresa.query.filter_by(gestor_id=usuario.id).all()}
    def da_empresa(b):
        membros = {m.id for m in b.projeto.grupo.membros} if b.projeto and b.projeto.grupo else set()
        avaliadores = {a.perfil_avaliador.empresa_origem for a in b.avaliadores if getattr(a, 'perfil_avaliador', None)}
        return bool(membros & jovens) or bool(avaliadores & empresas)
    return [b for b in todas if da_empresa(b)]


def bancas_do_avaliador(usuario):
    from models import Banca
    return [b for b in Banca.query.order_by(Banca.data_hora).all() if usuario in b.avaliadores and b.status != 'Cancelada']


def membros_do_projeto(projeto):
    return list(projeto.grupo.membros) if projeto and projeto.grupo else []


def pode_enviar_entrega(usuario, projeto):
    return usuario in membros_do_projeto(projeto) or usuario.tipo_usuario in PERFIS_GESTAO_ENTREGAS_TCC


def pode_baixar_entrega(usuario, projeto):
    banca = getattr(projeto, 'banca', None)
    return (usuario in membros_do_projeto(projeto) or pode_gerir_bancas(usuario)
            or eh_avaliador_da_banca(usuario, banca))


def situacao_entrega(projeto, tipo='Escrito final'):
    """'sem' (nada enviado), 'no_prazo' ou 'atrasada' — para o painel da gestão."""
    entregas = [e for e in projeto.entregas if e.tipo == tipo]
    if not entregas:
        return 'sem'
    return 'no_prazo' if entregas[0].entregue_no_prazo else 'atrasada'


def pessoas_escalaveis_banca():
    return Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_ESCALAVEIS_BANCA), Usuario.status == 'Ativo').order_by(Usuario.nome).all()


def ler_datahora(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M") if valor else None
    except ValueError:
        return None


# ------------------------------------------------------------------------------
# P08 — Avaliadores da banca (executivos convidados)
# ------------------------------------------------------------------------------
@app.route('/bancas/avaliadores', methods=['GET', 'POST'])
@login_required
def avaliadores_banca():
    from models import PerfilAvaliador
    if not pode_gerir_bancas(current_user):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    empresas_b2b = [e.nome for e in Empresa.query.filter_by(gestor_id=current_user.id).order_by(Empresa.nome).all()] \
        if current_user.tipo_usuario == 'Admin B2B' else None

    if request.method == 'POST':
        acao = request.form.get('acao')
        empresa = (request.form.get('empresa_origem') or '').strip()
        if empresas_b2b is not None and empresa not in empresas_b2b:
            flash(t('aval_erro_empresa', current_user.idioma), "warning")
            return redirect(url_for('avaliadores_banca'))

        if acao == 'criar':
            nome = (request.form.get('nome_completo') or '').strip()
            email = (request.form.get('email') or '').strip().lower()
            senha = request.form.get('senha') or ''
            if not nome or not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                flash(t('aval_erro_campos', current_user.idioma), "warning")
                return redirect(url_for('avaliadores_banca'))
            if Usuario.query.filter_by(email=email).first():
                flash(t('aval_erro_email', current_user.idioma), "warning")
                return redirect(url_for('avaliadores_banca'))
            if not re.match(padrao_senha_forte(), senha):
                flash(f"Segurança: A senha inicial deve ter no mínimo {regra('senha_min_caracteres')} caracteres (maiúsculas, minúsculas, números e especiais).", "danger")
                return redirect(url_for('avaliadores_banca'))
            usuario = Usuario(nome=nome, email=email, tipo_usuario=TIPO_AVALIADOR, status='Ativo',
                              senha=bcrypt.generate_password_hash(senha).decode('utf-8'), criado_por=current_user.nome,
                              forcar_troca_senha=True, data_criacao=datetime.utcnow(), data_ultima_troca_senha=datetime.utcnow())
            db.session.add(usuario)
            db.session.flush()
            perfil = PerfilAvaliador(usuario_id=usuario.id)
            db.session.add(perfil)
        else:
            perfil = db.session.get(PerfilAvaliador, request.form.get('perfil_id', type=int) or 0)
            if not perfil or (empresas_b2b is not None and perfil.empresa_origem not in empresas_b2b):
                flash("Acesso negado.", "danger")
                return redirect(url_for('avaliadores_banca'))
            perfil.usuario.nome = (request.form.get('nome_completo') or perfil.usuario.nome).strip()

        perfil.nome_completo = (request.form.get('nome_completo') or '').strip() or perfil.usuario.nome
        perfil.empresa_origem = empresa or None
        perfil.area_atuacao = (request.form.get('area_atuacao') or '').strip() or None
        perfil.curriculo_minibio = (request.form.get('curriculo_minibio') or '').strip() or None
        perfil.telefone = (request.form.get('telefone') or '').strip() or None
        perfil.linkedin = (request.form.get('linkedin') or '').strip() or None

        arquivo = request.files.get('curriculo_arquivo')
        if arquivo and arquivo.filename:
            if not arquivo.filename.lower().endswith('.pdf'):
                db.session.rollback()
                flash(t('aval_erro_pdf', current_user.idioma), "warning")
                return redirect(url_for('avaliadores_banca'))
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            arquivo.seek(0)
            if tamanho > 5 * 1024 * 1024:
                db.session.rollback()
                flash(t('aval_erro_tamanho', current_user.idioma), "warning")
                return redirect(url_for('avaliadores_banca'))
            nome_arquivo = f"curriculo_{perfil.usuario_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            arquivo.save(os.path.join(PASTA_TCC, nome_arquivo))
            perfil.curriculo_arquivo = nome_arquivo
        db.session.commit()
        flash(t('aval_salvo', current_user.idioma), "success")
        return redirect(url_for('avaliadores_banca'))

    consulta = PerfilAvaliador.query.join(Usuario).order_by(Usuario.nome)
    perfis = [p for p in consulta.all() if empresas_b2b is None or p.empresa_origem in empresas_b2b]
    return render_template('avaliadores_banca.html', perfis=perfis, empresas_b2b=empresas_b2b)


@app.route('/bancas/avaliadores/<int:usuario_id>/curriculo')
@login_required
def curriculo_avaliador(usuario_id):
    from models import PerfilAvaliador
    perfil = PerfilAvaliador.query.filter_by(usuario_id=usuario_id).first()
    colega = any(perfil and perfil.usuario in b.avaliadores for b in bancas_do_avaliador(current_user))
    if not perfil or not perfil.curriculo_arquivo or not (pode_gerir_bancas(current_user) or colega or current_user.id == usuario_id):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return send_from_directory(PASTA_TCC, perfil.curriculo_arquivo, as_attachment=False)


@app.route('/bancas/<int:id>/ficha')
@login_required
def ficha_banca(id):
    from models import Banca
    banca = db.session.get(Banca, id)
    if not banca or not (pode_gerir_bancas(current_user) or eh_avaliador_da_banca(current_user, banca)):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('banca_ficha.html', banca=banca)


# ------------------------------------------------------------------------------
# P12 — Agenda de bancas (com histórico de remarcações) e "Minhas bancas"
# ------------------------------------------------------------------------------
def notificar_banca(banca, titulo, mensagem, incluir_grupo=True, referencia=None):
    destinatarios = list(banca.avaliadores)
    if incluir_grupo:
        destinatarios += membros_do_projeto(banca.projeto)
    notificar([p for p in destinatarios if p.id != current_user.id], titulo, mensagem,
              link=url_for('minhas_bancas'), tipo='banca', referencia=referencia)


@app.route('/bancas', methods=['GET', 'POST'])
@login_required
def agenda_bancas():
    from models import Banca, HistoricoDataBanca, EnvioFormularioBanca
    if not pode_gerir_bancas(current_user):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        acao = request.form.get('acao')
        banca = db.session.get(Banca, request.form.get('banca_id', type=int) or 0)

        if acao == 'salvar':
            data_hora = ler_datahora(request.form.get('data_hora'))
            projeto = db.session.get(Projeto, request.form.get('projeto_id', type=int) or 0)
            if not data_hora or (not banca and not projeto):
                flash(t('banca_erro_campos', current_user.idioma), "warning")
                return redirect(url_for('agenda_bancas'))
            nova = banca is None
            if nova:
                if Banca.query.filter_by(projeto_id=projeto.id).first():
                    flash(t('banca_erro_duplicada', current_user.idioma), "warning")
                    return redirect(url_for('agenda_bancas'))
                banca = Banca(projeto_id=projeto.id, data_hora=data_hora, criado_por_id=current_user.id)
                db.session.add(banca)
            elif data_hora != banca.data_hora:
                motivo = (request.form.get('motivo_alteracao') or '').strip()
                if len(motivo) < MINIMO_CARACTERES_MOTIVO_REMARCACAO:
                    flash(t('banca_erro_motivo', current_user.idioma), "warning")
                    return redirect(url_for('agenda_bancas'))
                db.session.add(HistoricoDataBanca(banca_id=banca.id, data_anterior=banca.data_hora, data_nova=data_hora,
                                                  motivo=motivo, alterado_por_id=current_user.id))
                data_antiga = banca.data_hora
                banca.data_hora = data_hora
                banca.status = 'Remarcada'
                # O formulário da banca volta a ser enviado na nova janela
                EnvioFormularioBanca.query.filter_by(banca_id=banca.id).delete()
                db.session.flush()
                notificar_banca(banca, ('notif_banca_remarcada_titulo', {'projeto': banca.projeto.nome}),
                                ('notif_banca_remarcada_msg', {'antiga': data_antiga.strftime('%d/%m/%Y %H:%M'),
                                                               'nova': data_hora.strftime('%d/%m/%Y %H:%M'), 'motivo': motivo}))

            banca.local = (request.form.get('local') or '').strip() or None
            banca.link_sala = (request.form.get('link_sala') or '').strip() or None
            banca.duracao_apresentacao_min = request.form.get('duracao_apresentacao_min', type=int) or 15
            banca.duracao_perguntas_min = request.form.get('duracao_perguntas_min', type=int) or 10
            banca.prazo_entrega_escrito = ler_datahora(request.form.get('prazo_entrega_escrito'))
            banca.prazo_entrega_slides = ler_datahora(request.form.get('prazo_entrega_slides'))
            banca.prazo_leitura_avaliadores = ler_datahora(request.form.get('prazo_leitura_avaliadores'))
            banca.horas_antes_formulario = request.form.get('horas_antes_formulario', type=int) or 24
            banca.anonimizar_feedback = bool(request.form.get('anonimizar_feedback'))
            ids = [int(i) for i in request.form.getlist('avaliadores') if i.isdigit()]
            banca.avaliadores = Usuario.query.filter(Usuario.id.in_(ids or [-1]), Usuario.tipo_usuario.in_(PERFIS_ESCALAVEIS_BANCA)).all()
            db.session.commit()
            if nova:
                notificar_banca(banca, ('notif_banca_nova_titulo', {'projeto': banca.projeto.nome}),
                                ('notif_banca_nova_msg', {'data': banca.data_hora.strftime('%d/%m/%Y %H:%M'),
                                                          'local': banca.local or banca.link_sala or '—'}),
                                referencia=f"banca-nova:{banca.id}")
            flash(t('banca_salva', current_user.idioma), "success")

        elif acao == 'cancelar' and banca and banca.status in ['Agendada', 'Remarcada']:
            banca.status = 'Cancelada'
            db.session.commit()
            flash(t('banca_cancelada', current_user.idioma), "info")

        elif acao in ['publicar', 'publicar_todas'] and current_user.tipo_usuario in PERFIS_PUBLICAM_BANCAS:
            alvo = [banca] if acao == 'publicar' and banca else [b for b in bancas_visiveis_gestao(current_user)]
            publicadas = sum(1 for b in alvo if publicar_resultado_banca(b))
            flash(t('banca_publicadas', current_user.idioma).format(n=publicadas), "success" if publicadas else "info")
        return redirect(url_for('agenda_bancas'))

    bancas = bancas_visiveis_gestao(current_user)
    com_banca = {b.projeto_id for b in Banca.query.all()}
    projetos_sem_banca = [p for p in Projeto.query.order_by(Projeto.nome).all() if p.id not in com_banca]
    envios = {(e.banca_id, e.avaliador_id): e.enviado_em for e in EnvioFormularioBanca.query.filter_by(tipo='formulario').all()}
    return render_template('agenda_bancas.html', bancas=bancas, projetos_sem_banca=projetos_sem_banca,
                           pessoas=pessoas_escalaveis_banca(), envios=envios, situacao_entrega=situacao_entrega,
                           pode_publicar=current_user.tipo_usuario in PERFIS_PUBLICAM_BANCAS)


@app.route('/minhas-bancas')
@login_required
def minhas_bancas():
    from models import CheckinVoluntariado, AvaliacaoBanca
    bancas = bancas_do_avaliador(current_user)
    if not bancas and not pode_gerir_bancas(current_user) and current_user.tipo_usuario != TIPO_AVALIADOR:
        flash(t('banca_nenhuma', current_user.idioma), "info")
        return redirect(url_for('dashboard'))
    minutos = {}
    for c in CheckinVoluntariado.query.filter(CheckinVoluntariado.usuario_id == current_user.id,
                                             CheckinVoluntariado.projeto_id.isnot(None)).all():
        chave = (c.projeto_id, c.tipo_atividade.replace(' (Lançamento Manual)', ''))
        minutos[chave] = minutos.get(chave, 0) + (c.total_minutos or 0)
    aberto = CheckinVoluntariado.query.filter_by(usuario_id=current_user.id, data_hora_fim=None).first()
    avaliacoes = {a.projeto_id: a for a in AvaliacaoBanca.query.filter_by(avaliador_id=current_user.id).all()}
    return render_template('minhas_bancas.html', bancas=bancas, minutos=minutos, aberto=aberto, avaliacoes=avaliacoes,
                           agora=datetime.now())


# ------------------------------------------------------------------------------
# P10 — Entrega do TCC (escrito final e slides) com prazos e versões
# ------------------------------------------------------------------------------
@app.route('/projetos/<int:id>/entregas', methods=['POST'])
@login_required
def enviar_entrega_tcc(id):
    from models import EntregaTCC
    projeto = db.session.get(Projeto, id)
    if not projeto or not pode_enviar_entrega(current_user, projeto):
        flash("Acesso negado.", "danger")
        return redirect(url_for('projetos'))
    tipo = request.form.get('tipo')
    arquivo = request.files.get('arquivo')
    extensao = arquivo.filename.rsplit('.', 1)[-1].lower() if arquivo and '.' in (arquivo.filename or '') else ''
    if tipo not in TIPOS_ENTREGA_TCC or extensao not in TIPOS_ENTREGA_TCC[tipo]:
        flash(t('entrega_erro_tipo', current_user.idioma), "warning")
        return redirect(url_for('projetos'))
    arquivo.seek(0, os.SEEK_END)
    tamanho = arquivo.tell()
    arquivo.seek(0)
    if tamanho > LIMITE_ENTREGA_MB * 1024 * 1024:
        flash(t('entrega_erro_tamanho', current_user.idioma), "warning")
        return redirect(url_for('projetos'))

    versao = 1 + max([e.versao for e in projeto.entregas if e.tipo == tipo] or [0])
    nome_salvo = f"tcc_{projeto.id}_{'escrito' if tipo == 'Escrito final' else 'slides'}_v{versao}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extensao}"
    arquivo.save(os.path.join(PASTA_TCC, nome_salvo))
    banca = getattr(projeto, 'banca', None)
    prazo = (banca.prazo_entrega_escrito if tipo == 'Escrito final' else banca.prazo_entrega_slides) if banca else None
    entrega = EntregaTCC(projeto_id=projeto.id, tipo=tipo, arquivo=nome_salvo, nome_original=secure_filename(arquivo.filename),
                         versao=versao, enviado_por_id=current_user.id, observacao=(request.form.get('observacao') or '').strip() or None,
                         entregue_no_prazo=(prazo is None or datetime.now() <= prazo))
    db.session.add(entrega)
    db.session.commit()
    if tipo == 'Escrito final' and banca and banca.avaliadores:
        prazo_leitura = banca.prazo_leitura_avaliadores.strftime('%d/%m/%Y %H:%M') if banca.prazo_leitura_avaliadores else '—'
        notificar(banca.avaliadores, ('notif_entrega_titulo', {'projeto': projeto.nome}),
                  ('notif_entrega_msg', {'versao': versao, 'prazo': prazo_leitura}),
                  link=url_for('minhas_bancas'), tipo='banca', referencia=f"entrega:{entrega.id}")
    flash(t('entrega_ok', current_user.idioma).format(versao=versao) + ('' if entrega.entregue_no_prazo else ' ' + t('entrega_fora_prazo', current_user.idioma)),
          "success" if entrega.entregue_no_prazo else "warning")
    return redirect(url_for('projetos') + f"#projeto-{projeto.id}")


@app.route('/entregas/<int:id>/arquivo')
@login_required
def baixar_entrega_tcc(id):
    from models import EntregaTCC
    entrega = db.session.get(EntregaTCC, id)
    if not entrega or not pode_baixar_entrega(current_user, entrega.projeto):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return send_from_directory(PASTA_TCC, entrega.arquivo, as_attachment=True,
                               download_name=entrega.nome_original or entrega.arquivo)


# ------------------------------------------------------------------------------
# P09 — Check-in/out do avaliador ligado ao TCC (leitura, análise e banca ao vivo)
# ------------------------------------------------------------------------------
ACOES_RELOGIO_BANCA = {'iniciar_leitura': 'Leitura Assíncrona de TCC', 'iniciar_analise': 'Análise e Notas',
                       'checkin_banca': 'Avaliação de Banca Ao Vivo'}


@app.route('/bancas/<int:id>/relogio/<acao>', methods=['POST'])
@login_required
def relogio_banca(id, acao):
    from models import Banca, CheckinVoluntariado
    banca = db.session.get(Banca, id)
    if not banca or not (eh_avaliador_da_banca(current_user, banca) or pode_gerir_bancas(current_user)):
        flash("Acesso negado.", "danger")
        return redirect(url_for('minhas_bancas'))
    aberto = CheckinVoluntariado.query.filter_by(usuario_id=current_user.id, data_hora_fim=None).first()
    agora_utc = datetime.utcnow()

    if acao == 'encerrar':
        if aberto:
            aberto.data_hora_fim = agora_utc
            aberto.total_minutos = int((aberto.data_hora_fim - aberto.data_hora_inicio).total_seconds() / 60)
            db.session.commit()
            flash(t('banca_relogio_encerrado', current_user.idioma).format(minutos=aberto.total_minutos), "success")
        return redirect(url_for('minhas_bancas'))

    tipo = ACOES_RELOGIO_BANCA.get(acao)
    if not tipo:
        return redirect(url_for('minhas_bancas'))
    if aberto:
        flash(t('banca_relogio_ja_aberto', current_user.idioma), "warning")
        return redirect(url_for('minhas_bancas'))
    if acao == 'checkin_banca' and not (banca.data_hora - timedelta(hours=2) <= datetime.now() <= banca.fim_previsto + timedelta(hours=2)):
        flash(t('banca_checkin_fora_janela', current_user.idioma), "warning")
        return redirect(url_for('minhas_bancas'))
    db.session.add(CheckinVoluntariado(usuario_id=current_user.id, tipo_atividade=tipo, projeto_id=banca.projeto_id,
                                       categoria='Regular', data_hora_inicio=agora_utc,
                                       observacoes=f"Banca #{banca.id}: {banca.projeto.nome}"))
    db.session.commit()
    flash(t('banca_relogio_iniciado', current_user.idioma), "info")
    return redirect(url_for('minhas_bancas'))


# ------------------------------------------------------------------------------
# P11 / P16 — Sala da Banca: notas por avaliador, consolidação e divulgação
# ------------------------------------------------------------------------------
@app.route('/projetos/banca/<int:id>', methods=['GET', 'POST'])
@login_required
def painel_banca(id):
    # Sala da Banca: só os avaliadores escalados nesta banca e a gestão entram (Alunos nunca)
    from models import AvaliacaoBanca, QABanca
    projeto = db.session.get(Projeto, id)
    if not projeto:
        return redirect(url_for('projetos'))
    banca = getattr(projeto, 'banca', None)
    gestor = pode_gerir_bancas(current_user)
    avaliador = eh_avaliador_da_banca(current_user, banca)
    if not (gestor or avaliador):
        flash("Acesso restrito à Banca Avaliadora.", "danger")
        return redirect(url_for('projetos'))
    if not banca:
        flash(t('banca_nao_agendada', current_user.idioma), "warning")
        return redirect(url_for('agenda_bancas'))

    minha = AvaliacaoBanca.query.filter_by(projeto_id=projeto.id, avaliador_id=current_user.id).first()
    encerrada = banca.status == 'Realizada'

    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao in ['etapa_escrita', 'etapa_oral']:
            if not avaliador or encerrada:
                flash("Acesso negado.", "danger")
                return redirect(url_for('painel_banca', id=projeto.id))
            if not minha:
                minha = AvaliacaoBanca(projeto_id=projeto.id, banca_id=banca.id, avaliador_id=current_user.id)
                db.session.add(minha)
            erro = registrar_etapa_avaliacao(minha, acao, request.form)
            if erro:
                db.session.rollback()
                mensagem = t(erro, current_user.idioma)
                if erro == 'banca_erro_justificativa':
                    mensagem = mensagem.format(nota=regra('banca_nota_exige_justificativa'), minimo=regra('banca_justificativa_min'))
                flash(mensagem, "warning")
                return redirect(url_for('painel_banca', id=projeto.id))
            db.session.commit()
            fechou = consolidar_banca(banca)
            flash(t('banca_etapa_salva', current_user.idioma) + (' ' + t('banca_encerrada_auto', current_user.idioma) if fechou else ''), "success")
        elif acao == 'encerrar' and gestor and not encerrada:
            if consolidar_banca(banca, encerrar=True):
                flash(t('banca_encerrada_ok', current_user.idioma).format(nota=f"{projeto.nota_final:.1f}", status=projeto.status), "success")
            else:
                flash(t('banca_encerrar_sem_notas', current_user.idioma), "warning")
        return redirect(url_for('painel_banca', id=projeto.id))

    avaliacoes = AvaliacaoBanca.query.filter_by(projeto_id=projeto.id).all() if gestor else []
    entregas = [e for e in projeto.entregas]
    historico_qa = QABanca.query.filter_by(projeto_id=projeto.id).order_by(QABanca.data_registro).all()
    return render_template('banca_avaliacao.html', projeto=projeto, banca=banca, minha=minha, avaliador=avaliador,
                           gestor=gestor, encerrada=encerrada, avaliacoes=avaliacoes, entregas=entregas, historico_qa=historico_qa)


def ler_nota(formulario, campo):
    try:
        valor = round(float((formulario.get(campo) or '').replace(',', '.')), 1)
    except ValueError:
        return None
    return valor if 0 <= valor <= NOTA_MAXIMA else None


def registrar_etapa_avaliacao(avaliacao, etapa, formulario):
    """Grava uma etapa da avaliação. Devolve a chave do erro ou None."""
    if etapa == 'etapa_escrita':
        nota = ler_nota(formulario, 'nota_escrita')
        justificativa = (formulario.get('justificativa_escrita') or '').strip()
        if nota is None:
            return 'banca_erro_nota'
        if nota < float(regra('banca_nota_exige_justificativa')) and len(justificativa) < int(regra('banca_justificativa_min')):
            return 'banca_erro_justificativa'
        avaliacao.nota_escrita, avaliacao.justificativa_escrita = nota, justificativa or None
        avaliacao.etapa_escrita_concluida_em = datetime.utcnow()
    else:
        apresentacao, visual = ler_nota(formulario, 'nota_apresentacao'), ler_nota(formulario, 'nota_visual')
        justificativa = (formulario.get('justificativa_oral') or '').strip()
        if apresentacao is None or visual is None:
            return 'banca_erro_nota'
        if min(apresentacao, visual) < float(regra('banca_nota_exige_justificativa')) and len(justificativa) < int(regra('banca_justificativa_min')):
            return 'banca_erro_justificativa'
        avaliacao.nota_apresentacao, avaliacao.nota_visual = apresentacao, visual
        avaliacao.justificativa_oral = justificativa or None
        avaliacao.feedback_jovens = (formulario.get('feedback_jovens') or '').strip() or None
        avaliacao.etapa_oral_concluida_em = datetime.utcnow()
    return None


def consolidar_banca(banca, encerrar=False):
    """Médias por critério entre os avaliadores e fórmula oficial (pesos em Parâmetros de regras; padrão 40/40/20).
    O status do projeto só muda quando todos os escalados concluírem ou a gestão encerrar.
    Devolve True quando a banca foi encerrada agora."""
    from models import AvaliacaoBanca
    projeto = banca.projeto
    avaliacoes = AvaliacaoBanca.query.filter_by(projeto_id=projeto.id).all()

    def media(campo):
        valores = [getattr(a, campo) for a in avaliacoes if getattr(a, campo) is not None]
        return round(sum(valores) / len(valores), 2) if valores else None

    projeto.nota_conteudo, projeto.nota_apresentacao, projeto.nota_visual = media('nota_escrita'), media('nota_apresentacao'), media('nota_visual')
    if None not in (projeto.nota_conteudo, projeto.nota_apresentacao, projeto.nota_visual):
        pesos = [int(regra(c)) / 100 for c in ('banca_peso_escrito', 'banca_peso_apresentacao', 'banca_peso_visual')]
        projeto.nota_final = round(projeto.nota_conteudo * pesos[0] + projeto.nota_apresentacao * pesos[1] + projeto.nota_visual * pesos[2], 2)
    else:
        projeto.nota_final = None

    concluidas = {a.avaliador_id for a in avaliacoes if a.etapa_escrita_concluida_em and a.etapa_oral_concluida_em}
    todos = bool(banca.avaliadores) and {p.id for p in banca.avaliadores} <= concluidas
    fechou = False
    if (encerrar or todos) and projeto.nota_final is not None and banca.status != 'Realizada':
        projeto.status = 'Concluído' if projeto.nota_final >= float(regra('banca_nota_aprovacao')) else 'Em Recuperação'
        projeto.data_avaliacao = datetime.utcnow()
        banca.status = 'Realizada'
        banca.encerrada_em = datetime.utcnow()
        fechou = True
    db.session.commit()
    return fechou


def publicar_resultado_banca(banca):
    """Divulga as notas aos jovens e mentores do grupo (P16). Só bancas encerradas e ainda não publicadas."""
    projeto = banca.projeto
    if banca.status != 'Realizada' or projeto.notas_publicadas:
        return False
    projeto.notas_publicadas = True
    projeto.data_publicacao_notas = datetime.utcnow()
    db.session.commit()
    notificar(membros_do_projeto(projeto), ('notif_resultado_titulo', {'projeto': projeto.nome}),
              ('notif_resultado_msg', {'status': projeto.status}),
              link=url_for('projetos') + f"#projeto-{projeto.id}", tipo='banca', referencia=f"resultado:{projeto.id}")
    return True


def pode_ver_resultado(usuario, projeto):
    """Antes da publicação, só a gestão e os avaliadores escalados enxergam notas e status final."""
    return projeto.notas_publicadas or pode_gerir_bancas(usuario) or eh_avaliador_da_banca(usuario, getattr(projeto, 'banca', None))


def perguntas_do_projeto(projeto):
    from models import QABanca
    return QABanca.query.filter_by(projeto_id=projeto.id).order_by(QABanca.ordem, QABanca.data_registro).all()


@app.context_processor
def injetar_bancas_menu():
    if current_user.is_authenticated and current_user.tipo_usuario not in ['Aluno', TIPO_AVALIADOR]:
        return dict(tem_minhas_bancas=bool(bancas_do_avaliador(current_user)))
    return dict(tem_minhas_bancas=False)


# Funções de permissão da banca disponíveis nos templates
app.jinja_env.globals.update(pode_ver_resultado=pode_ver_resultado, pode_enviar_entrega=pode_enviar_entrega,
                             pode_baixar_entrega=pode_baixar_entrega, eh_avaliador_da_banca=eh_avaliador_da_banca,
                             pode_gerir_bancas=pode_gerir_bancas, situacao_entrega=situacao_entrega,
                             perguntas_do_projeto=perguntas_do_projeto)


@app.context_processor
def injetar_certificados_menu():
    # Item "Certificados" no menu só para quem já tem algum disponível
    if current_user.is_authenticated:
        return dict(tem_certificados=bool(certificados_disponiveis(current_user)))
    return dict(tem_certificados=False)


# ------------------------------------------------------------------------------
# P14 — Perguntas da banca e respostas dos jovens (a qualquer momento, sem enviar notas)
# ------------------------------------------------------------------------------
@app.route('/bancas/<int:id>/perguntas', methods=['GET', 'POST'])
@login_required
def perguntas_banca(id):
    from models import Banca, QABanca
    banca = db.session.get(Banca, id)
    if not banca or not (eh_avaliador_da_banca(current_user, banca) or pode_gerir_bancas(current_user)):
        return jsonify({'erro': 'acesso negado'}), 403

    if request.method == 'POST':
        dados = request.get_json(silent=True) or request.form
        acao = dados.get('acao', 'adicionar')
        registro = db.session.get(QABanca, int(dados.get('id') or 0)) if dados.get('id') else None
        if banca.status == 'Realizada':
            return jsonify({'erro': t('banca_qa_encerrada', current_user.idioma)}), 400
        if acao == 'adicionar':
            pergunta = (dados.get('pergunta') or '').strip()
            if not pergunta:
                return jsonify({'erro': t('banca_qa_vazia', current_user.idioma)}), 400
            ordem = 1 + (db.session.query(db.func.max(QABanca.ordem)).filter(QABanca.projeto_id == banca.projeto_id).scalar() or 0)
            db.session.add(QABanca(projeto_id=banca.projeto_id, banca_id=banca.id, avaliador_id=current_user.id, ordem=ordem,
                                   pergunta_feita=pergunta, resposta_jovens=(dados.get('resposta') or '').strip() or None))
        elif registro and registro.avaliador_id == current_user.id and registro.projeto_id == banca.projeto_id:
            if acao == 'editar':
                registro.pergunta_feita = (dados.get('pergunta') or registro.pergunta_feita).strip()
                registro.resposta_jovens = (dados.get('resposta') or '').strip() or None
            elif acao == 'apagar':
                db.session.delete(registro)
        db.session.commit()

    registros = QABanca.query.filter_by(projeto_id=banca.projeto_id).order_by(QABanca.ordem, QABanca.data_registro).all()
    return jsonify({'perguntas': [{'id': r.id, 'pergunta': r.pergunta_feita, 'resposta': r.resposta_jovens or '',
                                   'autor': r.avaliador.nome if getattr(r, 'avaliador', None) else '',
                                   'minha': r.avaliador_id == current_user.id,
                                   'hora': r.data_registro.strftime('%H:%M') if r.data_registro else ''} for r in registros]})


# ------------------------------------------------------------------------------
# P15 — Cronômetro em duas fases, sincronizado entre a sala e o telão
# ------------------------------------------------------------------------------
def estado_cronometro(banca):
    decorrido = banca.cron_acumulado_seg or 0
    if banca.cron_fase and not banca.cron_pausado and banca.cron_inicio:
        decorrido += int((datetime.utcnow() - banca.cron_inicio).total_seconds())
    limite = 60 * ((banca.duracao_apresentacao_min or 15) if banca.cron_fase != 'perguntas' else (banca.duracao_perguntas_min or 10))
    return {'fase': banca.cron_fase, 'decorrido': decorrido, 'limite': limite, 'pausado': bool(banca.cron_pausado),
            'tempo_real_apresentacao': banca.tempo_real_apresentacao_seg, 'tempo_real_perguntas': banca.tempo_real_perguntas_seg,
            'duracao_apresentacao': (banca.duracao_apresentacao_min or 15) * 60, 'duracao_perguntas': (banca.duracao_perguntas_min or 10) * 60}


def pode_ver_cronometro(usuario, banca):
    return eh_avaliador_da_banca(usuario, banca) or pode_gerir_bancas(usuario) or usuario in membros_do_projeto(banca.projeto)


@app.route('/bancas/<int:id>/cronometro', methods=['POST'])
@login_required
def cronometro_banca(id):
    from models import Banca
    banca = db.session.get(Banca, id)
    if not banca or not (eh_avaliador_da_banca(current_user, banca) or pode_gerir_bancas(current_user)):
        return jsonify({'erro': 'acesso negado'}), 403
    acao = (request.get_json(silent=True) or request.form).get('acao')
    agora = datetime.utcnow()
    if acao in ['iniciar_apresentacao', 'iniciar_perguntas']:
        banca.cron_fase = 'apresentacao' if acao == 'iniciar_apresentacao' else 'perguntas'
        banca.cron_inicio, banca.cron_acumulado_seg, banca.cron_pausado = agora, 0, False
    elif acao == 'pausar' and banca.cron_fase and not banca.cron_pausado:
        banca.cron_acumulado_seg = estado_cronometro(banca)['decorrido']
        banca.cron_pausado = True
    elif acao == 'retomar' and banca.cron_fase and banca.cron_pausado:
        banca.cron_inicio, banca.cron_pausado = agora, False
    elif acao == 'encerrar_fase' and banca.cron_fase:
        decorrido = estado_cronometro(banca)['decorrido']
        if banca.cron_fase == 'apresentacao':
            banca.tempo_real_apresentacao_seg = decorrido
        else:
            banca.tempo_real_perguntas_seg = decorrido
        banca.cron_fase, banca.cron_inicio, banca.cron_acumulado_seg, banca.cron_pausado = None, None, 0, True
    db.session.commit()
    return jsonify(estado_cronometro(banca))


@app.route('/bancas/<int:id>/cronometro/estado')
@login_required
def estado_cronometro_banca(id):
    from models import Banca
    banca = db.session.get(Banca, id)
    if not banca or not pode_ver_cronometro(current_user, banca):
        return jsonify({'erro': 'acesso negado'}), 403
    return jsonify(estado_cronometro(banca))


@app.route('/bancas/<int:id>/telao')
@login_required
def telao_banca(id):
    from models import Banca
    banca = db.session.get(Banca, id)
    if not banca or not pode_ver_cronometro(current_user, banca):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('banca_telao.html', banca=banca)


# ==============================================================================
# FASE 4 — CERTIFICADOS COM HORAS, INDICADORES DE VOLUNTARIADO E REPOSITÓRIO DE TCCs
# ==============================================================================
PASTA_ACERVO = os.path.join(app.config['UPLOAD_FOLDER'], 'acervo')
os.makedirs(PASTA_ACERVO, exist_ok=True)
ROTULOS_ATIVIDADE = {'Leitura Assíncrona de TCC': 'Leitura do TCC', 'Análise e Notas': 'Análise e notas',
                     'Avaliação de Banca Ao Vivo': 'Banca ao vivo', 'Mentoria Extraordinária': 'Mentoria extra',
                     'Reunião Institucional': 'Reuniões institucionais', 'Apoio Institucional': 'Apoio institucional'}


# ------------------------------------------------------------------------------
# P17 — Certificados
# ------------------------------------------------------------------------------
def pode_emitir_certificado_de(quem, usuario):
    """O próprio usuário, a coordenação ou o Gestor B2B para pessoas das suas empresas."""
    if quem.id == usuario.id or quem.tipo_usuario in PERFIS_EMITEM_CERTIFICADOS:
        return True
    if quem.tipo_usuario == 'Admin B2B':
        empresas = {e.nome for e in Empresa.query.filter_by(gestor_id=quem.id).all()}
        da_empresa = {e.nome for e in (getattr(usuario, 'empresas_vinculadas', None) or [])}
        perfil = getattr(usuario, 'perfil_avaliador', None)
        if perfil and perfil.empresa_origem:
            da_empresa.add(perfil.empresa_origem)
        return bool(empresas & da_empresa) or usuario.id in (ids_jovens_visiveis(quem) or set())
    return False


def tipo_certificado(usuario, projeto):
    banca = getattr(projeto, 'banca', None)
    if banca and usuario in banca.avaliadores:
        return 'Avaliador da Banca'
    if usuario in membros_do_projeto(projeto):
        return 'Jovem participante' if usuario.tipo_usuario == 'Aluno' else 'Mentor'
    return None


def minutos_certificado(usuario, projeto, tipo):
    """Soma as horas registradas (só lançamentos concluídos) e devolve (total, {atividade: minutos})."""
    from models import CheckinVoluntariado, AtividadeExtra, PresencaAtividadeExtra
    detalhe = {}
    if tipo == 'Jovem participante':
        presencas = PresencaAtividadeExtra.query.join(AtividadeExtra).filter(
            PresencaAtividadeExtra.usuario_id == usuario.id, AtividadeExtra.grupo_id == projeto.grupo_id,
            PresencaAtividadeExtra.check_out.isnot(None)).all()
        if presencas:
            detalhe['Atividades extras do grupo'] = sum(p.total_minutos or 0 for p in presencas)
    else:
        consulta = CheckinVoluntariado.query.filter(CheckinVoluntariado.usuario_id == usuario.id,
                                                    CheckinVoluntariado.data_hora_fim.isnot(None))
        if tipo == 'Avaliador da Banca':
            consulta = consulta.filter(CheckinVoluntariado.projeto_id == projeto.id)
        else:
            consulta = consulta.filter((CheckinVoluntariado.projeto_id == projeto.id) | (CheckinVoluntariado.grupo_id == projeto.grupo_id))
        for registro in consulta.all():
            base = registro.tipo_atividade.replace(' (Lançamento Manual)', '')
            rotulo = ROTULOS_ATIVIDADE.get(base, base)
            detalhe[rotulo] = detalhe.get(rotulo, 0) + (registro.total_minutos or 0)
    return sum(detalhe.values()), detalhe


def registrar_certificado(usuario, projeto, tipo):
    """Cria (ou atualiza as horas de) o certificado com um código curto e único para verificação pública."""
    import json
    import secrets
    from models import CertificadoEmitido
    certificado = CertificadoEmitido.query.filter_by(usuario_id=usuario.id, projeto_id=projeto.id, tipo=tipo).first()
    if not certificado:
        codigo = secrets.token_hex(5).upper()
        while CertificadoEmitido.query.filter_by(codigo=codigo).first():
            codigo = secrets.token_hex(5).upper()
        certificado = CertificadoEmitido(usuario_id=usuario.id, projeto_id=projeto.id, tipo=tipo, codigo=codigo)
        db.session.add(certificado)
    total, detalhe = minutos_certificado(usuario, projeto, tipo)
    certificado.minutos_total = total
    certificado.detalhe_minutos = json.dumps(detalhe, ensure_ascii=False)
    db.session.commit()
    return certificado


def certificados_disponiveis(usuario):
    """Projetos aprovados e divulgados em que a pessoa participou: (projeto, tipo)."""
    publicados = Projeto.query.filter_by(status='Concluído', notas_publicadas=True).order_by(Projeto.data_publicacao_notas.desc()).all()
    return [(p, tipo_certificado(usuario, p)) for p in publicados if tipo_certificado(usuario, p)]


@app.route('/certificados')
@login_required
def meus_certificados():
    from models import CertificadoEmitido
    emitidos = {(c.projeto_id, c.tipo): c for c in CertificadoEmitido.query.filter_by(usuario_id=current_user.id).all()}
    return render_template('meus_certificados.html', disponiveis=certificados_disponiveis(current_user), emitidos=emitidos)


@app.route('/certificado/verificar/<codigo>')
def verificar_certificado(codigo):
    """Página pública: confirma a autenticidade sem expor e-mail nem dados sensíveis."""
    from models import CertificadoEmitido
    certificado = CertificadoEmitido.query.filter_by(codigo=(codigo or '').upper()).first()
    parceiros = parceiros_do_projeto(certificado.projeto) if certificado and certificado.projeto else []
    return render_template('certificado_verificar.html', certificado=certificado, codigo=codigo,
                           parceiros=', '.join(parceiros) or 'empresas parceiras (B2B)')


# ------------------------------------------------------------------------------
# P18 — Indicadores de voluntariado
# ------------------------------------------------------------------------------
def registros_indicadores(usuario, filtros):
    """Lançamentos do escopo do perfil com os filtros da tela aplicados."""
    registros = registros_esg_do_perfil(usuario)
    inicio, fim = filtros.get('data_inicio'), filtros.get('data_fim')
    if inicio:
        registros = [r for r in registros if r.data_hora_inicio and r.data_hora_inicio.strftime('%Y-%m-%d') >= inicio]
    if fim:
        registros = [r for r in registros if r.data_hora_inicio and r.data_hora_inicio.strftime('%Y-%m-%d') <= fim]
    if filtros.get('tipo'):
        registros = [r for r in registros if r.tipo_atividade.replace(' (Lançamento Manual)', '') == filtros['tipo']]
    if filtros.get('grupo_id'):
        registros = [r for r in registros if r.grupo_id == filtros['grupo_id'] or (r.projeto and r.projeto.grupo_id == filtros['grupo_id'])]
    if filtros.get('empresa'):
        registros = [r for r in registros if filtros['empresa'] in linha_relatorio_esg(r)['empresa']]
    return registros


def calcular_indicadores(usuario, filtros):
    registros = registros_indicadores(usuario, filtros)
    concluidos = [r for r in registros if r.data_hora_fim]
    linhas = [linha_relatorio_esg(r) for r in concluidos]
    total = sum(l['minutos'] for l in linhas)
    por_pessoa, por_tipo, por_empresa, por_mes = {}, {}, {}, {}
    regular = extra = 0
    for r, l in zip(concluidos, linhas):
        por_pessoa[l['nome']] = por_pessoa.get(l['nome'], 0) + l['minutos']
        rotulo = ROTULOS_ATIVIDADE.get(r.tipo_atividade.replace(' (Lançamento Manual)', ''), r.tipo_atividade)
        por_tipo[rotulo] = por_tipo.get(rotulo, 0) + l['minutos']
        por_empresa[l['empresa']] = por_empresa.get(l['empresa'], 0) + l['minutos']
        mes = r.data_hora_inicio.strftime('%Y-%m')
        por_mes[mes] = por_mes.get(mes, 0) + l['minutos']
        if l['categoria'] == 'Extra':
            extra += l['minutos']
        else:
            regular += l['minutos']

    visiveis = ids_jovens_visiveis(usuario)
    consulta_jovens = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.status == 'Ativo')
    if visiveis is not None:
        consulta_jovens = consulta_jovens.filter(Usuario.id.in_(list(visiveis) or [-1]))
    jovens = consulta_jovens.count()
    aprovados = Projeto.query.filter_by(status='Concluído', notas_publicadas=True).count()
    return {
        'total_min': total, 'voluntarios': len(por_pessoa), 'regular_min': regular, 'extra_min': extra,
        'por_tipo': sorted(por_tipo.items(), key=lambda x: -x[1]),
        'ranking': sorted(por_pessoa.items(), key=lambda x: -x[1])[:10],
        'por_empresa': sorted(por_empresa.items(), key=lambda x: -x[1]),
        'por_mes': sorted(por_mes.items()),
        'jovens': jovens, 'horas_por_jovem': round(total / 60 / jovens, 1) if jovens else 0,
        'tccs_aprovados': aprovados,
        'abertos': [r for r in registros if not r.data_hora_fim],
        'linhas': linhas,
    }


def filtros_indicadores():
    return {'data_inicio': request.args.get('data_inicio') or '', 'data_fim': request.args.get('data_fim') or '',
            'tipo': request.args.get('tipo') or '', 'empresa': request.args.get('empresa') or '',
            'grupo_id': request.args.get('grupo_id', type=int)}


@app.route('/indicadores-voluntariado')
@login_required
def indicadores_voluntariado():
    if current_user.tipo_usuario not in PERFIS_GESTAO_BANCA:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    filtros = filtros_indicadores()
    dados = calcular_indicadores(current_user, filtros)
    empresas = [e.nome for e in (Empresa.query.filter_by(gestor_id=current_user.id) if current_user.tipo_usuario == 'Admin B2B'
                                 else Empresa.query).order_by(Empresa.nome).all()]
    return render_template('indicadores_voluntariado.html', dados=dados, filtros=filtros, empresas=empresas,
                           grupos=Grupo.query.order_by(Grupo.nome).all(), tipos=list(ROTULOS_ATIVIDADE.items()))


@app.route('/indicadores-voluntariado.csv')
@login_required
def indicadores_voluntariado_csv():
    import csv
    import io
    from flask import Response
    if current_user.tipo_usuario not in PERFIS_GESTAO_BANCA:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    dados = calcular_indicadores(current_user, filtros_indicadores())
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(['Indicador', 'Valor'])
    for nome, valor in [('Horas totais', round(dados['total_min'] / 60, 1)), ('Voluntários ativos', dados['voluntarios']),
                        ('Horas regulares', round(dados['regular_min'] / 60, 1)), ('Horas extras', round(dados['extra_min'] / 60, 1)),
                        ('Jovens capacitados', dados['jovens']), ('Horas por jovem', dados['horas_por_jovem']),
                        ('TCCs aprovados', dados['tccs_aprovados'])]:
        escritor.writerow([nome, valor])
    escritor.writerow([])
    escritor.writerow(['Atividade', 'Horas'])
    for nome, minutos in dados['por_tipo']:
        escritor.writerow([nome, round(minutos / 60, 1)])
    escritor.writerow([])
    escritor.writerow(['Voluntário', 'Horas'])
    for nome, minutos in dados['ranking']:
        escritor.writerow([nome, round(minutos / 60, 1)])
    return Response(saida.getvalue().encode('utf-8-sig'), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=Indicadores_Voluntariado_{datetime.now().strftime('%Y%m%d')}.csv"})


# ------------------------------------------------------------------------------
# P19 — Repositório de TCCs e materiais de apoio
# ------------------------------------------------------------------------------
def eh_orientador(usuario, projeto):
    return usuario.tipo_usuario != 'Aluno' and usuario in membros_do_projeto(projeto)


app.jinja_env.globals.update(eh_orientador=eh_orientador, regra=regra)


def salvar_arquivo_acervo(arquivo, prefixo, extensoes):
    if not arquivo or not arquivo.filename or '.' not in arquivo.filename:
        return None
    extensao = arquivo.filename.rsplit('.', 1)[-1].lower()
    if extensao not in extensoes:
        return None
    nome = f"{prefixo}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{extensao}"
    arquivo.save(os.path.join(PASTA_ACERVO, nome))
    return nome


def dados_acervo_do_formulario(item, formulario):
    item.tema = (formulario.get('tema') or '').strip() or None
    item.resumo = (formulario.get('resumo') or '').strip() or None
    item.palavras_chave = (formulario.get('palavras_chave') or '').strip() or None
    item.ano_edicao = formulario.get('ano_edicao', type=int) or datetime.now().year
    item.edicao = (formulario.get('edicao') or '').strip() or None
    item.exibir_nota = bool(formulario.get('exibir_nota'))
    item.autorizacao_publicacao = bool(formulario.get('autorizacao_publicacao'))
    # Sem a autorização dos jovens/responsáveis registrada, o TCC nunca fica público
    item.visibilidade = 'Pública' if (formulario.get('visibilidade') == 'Pública' and item.autorizacao_publicacao) else 'Interna'
    if item.autorizacao_publicacao:
        item.autorizado_por_id = current_user.id


@app.route('/projetos/<int:id>/aprovar-versao-final', methods=['POST'])
@login_required
def aprovar_versao_final(id):
    """Orientador do grupo ou gestão leva a versão final aprovada para o acervo."""
    import shutil
    from models import TCCAcervo
    projeto = db.session.get(Projeto, id)
    if not projeto or not (eh_orientador(current_user, projeto) or pode_gerir_bancas(current_user)):
        flash("Acesso negado.", "danger")
        return redirect(url_for('projetos'))
    escrito = next((e for e in projeto.entregas if e.tipo == 'Escrito final'), None)
    if projeto.status != 'Concluído' or not projeto.notas_publicadas or not escrito:
        flash(t('acervo_erro_requisitos', current_user.idioma), "warning")
        return redirect(url_for('projetos') + f"#projeto-{projeto.id}")

    item = projeto.acervo or TCCAcervo(projeto_id=projeto.id, origem='Plataforma')
    item.titulo = projeto.nome
    item.nota_final = projeto.nota_final
    jovens = [m for m in membros_do_projeto(projeto) if m.tipo_usuario == 'Aluno']
    item.autores_exibicao = ", ".join(sorted(m.nome.split()[0] for m in jovens)) or (projeto.grupo.nome if projeto.grupo else '')
    dados_acervo_do_formulario(item, request.form)
    for entrega, campo in [(escrito, 'arquivo_pdf'), (next((e for e in projeto.entregas if e.tipo == 'Slides da apresentação'), None), 'arquivo_slides')]:
        if entrega:
            destino = f"acervo_{projeto.id}_{entrega.arquivo}"
            shutil.copyfile(os.path.join(PASTA_TCC, entrega.arquivo), os.path.join(PASTA_ACERVO, destino))
            setattr(item, campo, destino)
    db.session.add(item)
    db.session.commit()
    flash(t('acervo_aprovado', current_user.idioma), "success")
    return redirect(url_for('biblioteca_tccs'))


@app.route('/acervo/<int:id>/<tipo>')
@login_required
def baixar_acervo(id, tipo):
    from models import TCCAcervo, MaterialApoio
    if tipo == 'material':
        item = db.session.get(MaterialApoio, id)
        arquivo = item.arquivo if item else None
    else:
        item = db.session.get(TCCAcervo, id)
        arquivo = (item.arquivo_slides if tipo == 'slides' else item.arquivo_pdf) if item else None
    if not item or not arquivo:
        flash("Arquivo não encontrado.", "warning")
        return redirect(url_for('biblioteca_tccs'))
    item.downloads = (item.downloads or 0) + 1
    db.session.commit()
    return send_from_directory(PASTA_ACERVO, arquivo, as_attachment=True)


@app.route('/repositorio')
def repositorio_publico():
    """Acervo aberto (sem login) para a instituição, as empresas parceiras (B2B) e o mercado: só TCCs públicos e autorizados."""
    from models import TCCAcervo
    busca = (request.args.get('q') or '').strip().lower()
    itens = TCCAcervo.query.filter_by(visibilidade='Pública', autorizacao_publicacao=True).order_by(TCCAcervo.ano_edicao.desc(), TCCAcervo.titulo).all()
    if busca:
        itens = [i for i in itens if busca in ' '.join(filter(None, [i.titulo, i.tema, i.resumo, i.palavras_chave])).lower()]
    return render_template('repositorio_publico.html', itens=itens, busca=request.args.get('q') or '')


@app.route('/repositorio/<int:id>/pdf')
def baixar_repositorio_publico(id):
    from models import TCCAcervo
    item = db.session.get(TCCAcervo, id)
    if not item or item.visibilidade != 'Pública' or not item.autorizacao_publicacao or not item.arquivo_pdf:
        return redirect(url_for('repositorio_publico'))
    item.downloads = (item.downloads or 0) + 1
    db.session.commit()
    return send_from_directory(PASTA_ACERVO, item.arquivo_pdf, as_attachment=True)


# ==============================================================================
# ADMINISTRAÇÃO › AGENTES IA: hub dos agentes de teste (Agente Gestor + agentes por perfil)
# ==============================================================================
PASTA_AGENTES_IA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Agent Reports', 'Agentes IA')
PASTA_AO_VIVO_IA = os.path.join(PASTA_AGENTES_IA, '.ao_vivo')
ORDEM_AGENTES_IA = [('administrador', 'Administrador'), ('aluno', 'Aluno'), ('professor', 'Professor'), ('mentor', 'Mentor'),
                    ('mentor_administrador', 'Mentor Administrador'), ('gestor_b2b', 'Gestor B2B'), ('avaliador', 'Avaliador Banca'),
                    ('perfis_personalizados', 'Perfis personalizados')]
# Uma subpasta por agente em cada pasta da área (mesmos nomes que o agentes_omnitest/agente_gestor.py usa)
PASTAS_PERFIS_IA = ['Perfil administrador', 'Perfil aluno', 'Perfil professor', 'Perfil mentor',
                    'Perfil mentor administrador', 'Perfil gestor B2B', 'Perfil avaliador banca', 'Perfis personalizados']
# Agentes de Segurança: uma subpasta por agente especialista (mesmos nomes que o agentes_seguranca/gestor_seguranca.py usa)
PASTAS_SEGURANCA_IA = ['Agente Configuração e Segredos', 'Agente Inconsistências de Dados', 'Agente Análise de Código',
                       'Agente Dependências e Tecnologias', 'Agente Pentest', 'Consolidado']
# Agentes de Banco de Dados (mesmos nomes que o agentes_banco/gestor_banco.py usa)
PASTAS_BANCO_IA = ['Agente Consultas e Desempenho', 'Agente Esquema e Índices', 'Agente Backup e Recuperação',
                   'Agente DBA Manutenção e Logs', 'Agente Multi-banco', 'Consolidado']
# Agentes de Funcionalidades (mesmos nomes que o agentes_funcionalidades/gestor_funcionalidades.py usa), na ordem do fluxo
PASTAS_FUNC_IA = ['Agente Dev', 'Agente UX', 'Agente Administrador', 'Agente Mentor Administrador', 'Agente Gestor Parceiro', 'Agente Professor', 'Agente Mentor',
                  'Agente Aluno', 'Agente Avaliador da Banca', 'Agente Encerramento do Ciclo', 'Consolidado']


def _ler_json_ia(nome):
    try:
        with open(os.path.join(PASTA_AO_VIVO_IA, nome), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def estado_agentes_ia():
    """Estado do Agente Gestor. Sem batimento há mais de 30 s, a execução é dada como interrompida."""
    estado = _ler_json_ia('estado.json')
    if estado and estado.get('status') == 'executando' and time.time() - estado.get('batimento', 0) > 30:
        estado['status'] = 'interrompido'
    return estado


def arvore_agentes_ia():
    """Pastas e arquivos da área (Relatórios e Prompts de cada tipo de agente), do mais novo para o mais antigo."""
    def arquivos(pasta):
        if not os.path.isdir(pasta):
            return []
        itens = [os.path.join(pasta, n) for n in os.listdir(pasta) if n.lower().endswith(('.pdf', '.md'))]
        return [{'nome': os.path.basename(a), 'relativo': os.path.relpath(a, PASTA_AGENTES_IA).replace('\\', '/'),
                 'data': datetime.fromtimestamp(os.path.getmtime(a))} for a in sorted(itens, key=os.path.getmtime, reverse=True)]

    def subpastas(pasta, nomes=PASTAS_PERFIS_IA):
        # Sempre uma subpasta por agente, na ordem dos agentes, mesmo antes da primeira execução
        for nome in nomes:
            os.makedirs(os.path.join(pasta, nome), exist_ok=True)
        return [{'nome': n, 'arquivos': arquivos(os.path.join(pasta, n))} for n in nomes]

    e2e = os.path.join(PASTA_AGENTES_IA, 'Agentes Teste Fim a Fim')
    seg = os.path.join(PASTA_AGENTES_IA, 'Agentes Teste de Segurança')
    bd = os.path.join(PASTA_AGENTES_IA, 'Agentes Banco de Dados')
    fn = os.path.join(PASTA_AGENTES_IA, 'Agentes Funcionalidades')
    return [
        {'nome': 'Agentes Teste Fim a Fim', 'pastas': [
            {'nome': 'Relatórios de Testes Fim a Fim e Evidencias', 'subpastas': subpastas(os.path.join(e2e, 'Relatórios de Testes Fim a Fim e Evidencias'))},
            {'nome': 'Prompt de correção LLM', 'subpastas': subpastas(os.path.join(e2e, 'Prompt de correção LLM'))}]},
        {'nome': 'Agentes Teste de Segurança', 'pagina': 'agentes_seguranca', 'pastas': [
            {'nome': 'Relatórios de Testes de Segurança', 'subpastas': subpastas(os.path.join(seg, 'Relatórios de Testes de Segurança'), PASTAS_SEGURANCA_IA)},
            {'nome': 'Prompt de correção LLM', 'subpastas': subpastas(os.path.join(seg, 'Prompt de correção LLM'), PASTAS_SEGURANCA_IA)}]},
        {'nome': 'Agentes Banco de Dados', 'pagina': 'agentes_banco', 'pastas': [
            {'nome': 'Relatórios de Banco de Dados', 'subpastas': subpastas(os.path.join(bd, 'Relatórios de Banco de Dados'), PASTAS_BANCO_IA)},
            {'nome': 'Prompt de melhoria LLM', 'subpastas': subpastas(os.path.join(bd, 'Prompt de melhoria LLM'), PASTAS_BANCO_IA)}]},
        {'nome': 'Agentes Funcionalidades', 'pagina': 'agentes_funcionalidades', 'pastas': [
            {'nome': 'Relatórios de Funcionalidades e Evidências',
             'subpastas': subpastas(os.path.join(fn, 'Relatórios de Funcionalidades e Evidências'), PASTAS_FUNC_IA)},
            {'nome': 'Prompt de correção LLM', 'subpastas': subpastas(os.path.join(fn, 'Prompt de correção LLM'), PASTAS_FUNC_IA)}]},
    ]


def _somente_administrador():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    return None


def ambiente_dos_agentes():
    """Ambiente para iniciar uma equipe de agentes: inclui as credenciais cadastradas na área Agentes IA."""
    import credenciais_agentes
    credenciais_agentes.carregar(app.config['SECRET_KEY'], forcar=True)
    return {**os.environ, 'PYTHONIOENCODING': 'utf-8'}


@app.route('/admin/agentes-ia/credenciais', methods=['POST'])
@login_required
def credenciais_agentes_ia():
    """Administrador cadastra, troca ou remove as credenciais dos agentes. O valor fica cifrado e nunca é mostrado."""
    import credenciais_agentes
    from models import CredencialAgente
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    voltar = redirect(url_for('provedores_ia_view') + '#cardCredenciaisIa')
    segredo = app.config['SECRET_KEY']
    alteradas, erros = [], []
    for chave, (nome, tipo) in credenciais_agentes.CAMPOS.items():
        registro = CredencialAgente.query.filter_by(chave=chave).first()
        if request.form.get(f'remover_{chave}'):
            if registro:
                db.session.delete(registro)
                alteradas.append(nome)
            continue
        valor = (request.form.get(chave) or '').strip()
        if not valor:
            continue
        erro = credenciais_agentes.validar(chave, valor)
        if erro:
            erros.append(f"{tt(nome, idioma)}: {tt(erro, idioma)}")
            continue
        if tipo == 'sim_nao' and registro and credenciais_agentes.decifrar(registro.valor_cifrado, segredo) == valor:
            continue
        if registro is None:
            registro = CredencialAgente(chave=chave)
            db.session.add(registro)
        registro.valor_cifrado = credenciais_agentes.cifrar(valor, segredo)
        registro.atualizado_por_id = current_user.id
        registro.atualizado_em = datetime.now()
        alteradas.append(nome)
    db.session.commit()
    credenciais_agentes.carregar(segredo, forcar=True)
    if alteradas:
        app.logger.info("Credenciais dos agentes alteradas por %s: %s", current_user.email, ', '.join(alteradas))
        flash(tt('Credenciais dos agentes atualizadas: {lista}.', idioma).format(lista=', '.join(tt(a, idioma) for a in alteradas)), 'success')
    for erro in erros:
        flash(erro, 'warning')
    if not alteradas and not erros:
        flash(tt('Nada foi alterado.', idioma), 'info')
    return voltar


# ==============================================================================
# PROVEDORES DE IA — ordem de modelos por uso, liga/desliga, preços e gasto do mês (só o Administrador)
# ==============================================================================
@app.context_processor
def _ia_ligada_no_template():
    def ia_ligada(uso):
        try:
            import provedores_ia
            return provedores_ia.ativo(uso)
        except Exception:
            return True
    return {'ia_ligada': ia_ligada}


@app.route('/admin/provedores-ia')
@login_required
def provedores_ia_view():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import credenciais_agentes
    import provedores_ia
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    return render_template('provedores_ia.html', r=provedores_ia.resumo_para_tela(), usos=provedores_ia.USOS,
                           provedores=provedores_ia.PROVEDORES, maximo=provedores_ia.MAXIMO_NA_ORDEM,
                           credenciais=credenciais_agentes.situacao(app.config['SECRET_KEY']))


@app.route('/admin/provedores-ia/uso/<uso>', methods=['POST'])
@login_required
def provedores_ia_uso(uso):
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import provedores_ia
    idioma = current_user.idioma
    voltar = request.form.get('voltar') or ''
    destino = redirect(voltar if voltar.startswith('/') and not voltar.startswith('//') else url_for('provedores_ia_view'))
    if uso not in provedores_ia.USOS:
        flash(tt('Uso desconhecido.', idioma), 'danger')
        return destino
    try:
        if 'ligado' in request.form:
            ligado = request.form.get('ligado') == '1'
            provedores_ia.definir_ativo(uso, ligado, current_user.id)
            flash(f"{tt(provedores_ia.USOS[uso][0], idioma)}: {tt('IA ligada.', idioma) if ligado else tt('IA desligada.', idioma)}", 'success')
        else:
            provedores_ia.salvar_ordem(uso, request.form.getlist('modelos'), current_user.id)
            flash(f"{tt(provedores_ia.USOS[uso][0], idioma)}: {tt('ordem de modelos salva.', idioma)}", 'success')
    except ValueError as e:
        flash(tt(str(e), idioma), 'danger')
    return destino


@app.route('/admin/provedores-ia/precos', methods=['POST'])
@login_required
def provedores_ia_precos():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import provedores_ia
    valores = {mid: (request.form.get(f'entrada_{mid}', ''), request.form.get(f'saida_{mid}', '')) for mid in provedores_ia.modelos()}
    try:
        provedores_ia.salvar_precos(valores, current_user.id)
        flash(tt('Preços salvos.', current_user.idioma), 'success')
    except ValueError as e:
        flash(tt(str(e), current_user.idioma), 'danger')
    return redirect(url_for('provedores_ia_view'))


@app.route('/admin/provedores-ia/modelos', methods=['POST'])
@login_required
def provedores_ia_modelos():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    import provedores_ia
    try:
        if request.form.get('acao') == 'remover':
            provedores_ia.remover_modelo(request.form.get('modelo', ''), current_user.id)
            flash(tt('Modelo removido.', current_user.idioma), 'success')
        else:
            provedores_ia.adicionar_modelo(request.form.get('provedor'), request.form.get('modelo'), request.form.get('nome'), current_user.id)
            flash(tt('Modelo adicionado. Preencha os preços para ele entrar no controle do teto.', current_user.idioma), 'success')
    except ValueError as e:
        flash(tt(str(e), current_user.idioma), 'danger')
    return redirect(url_for('provedores_ia_view'))


# ==============================================================================
# ASSISTENTE DA PLATAFORMA (chat) — só o Administrador
# Base: conhecimento dos Agentes gerentes + documentos PRD, PTD e DTD enviados na tela (base_conhecimento.py)
# ==============================================================================
def _bloqueio_assistente(como_json=False):
    if current_user.tipo_usuario in PERFIS_USAM_ASSISTENTE:
        return None
    if como_json:
        return jsonify({'erro': tt('Acesso restrito ao Administrador.', current_user.idioma)}), 403
    return _somente_administrador()


@app.route('/admin/assistente')
@login_required
def assistente():
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    import chat_assistente
    try:
        base_conhecimento.sincronizar_gerentes(current_user.id)
    except Exception as e:
        db.session.rollback()
        app.logger.warning('Assistente: não foi possível sincronizar o conhecimento dos gerentes: %s', e)
    conversa = chat_assistente.conversa_do_usuario(current_user, request.args.get('conversa', type=int))
    return render_template('assistente.html', resumo=base_conhecimento.resumo(), tipos=base_conhecimento.TIPOS,
                           tipos_upload=base_conhecimento.TIPOS_UPLOAD, extensoes=sorted(base_conhecimento.EXTENSOES),
                           limite_mb=base_conhecimento.LIMITE_ARQUIVO_MB, conversa=conversa,
                           mensagens=chat_assistente.mensagens_para_tela(conversa), conversas=chat_assistente.conversas(current_user),
                           aba=request.args.get('aba', 'conversar'), modelo=chat_assistente.modelo_principal())


@app.route('/admin/assistente/perguntar', methods=['POST'])
@login_required
def assistente_perguntar():
    bloqueio = _bloqueio_assistente(como_json=True)
    if bloqueio:
        return bloqueio
    import credenciais_agentes
    import chat_assistente
    import provedores_ia
    if not provedores_ia.ativo('assistente'):
        return jsonify({'erro': tt('O Assistente está desligado. Ligue em Administração › Provedores de IA.', current_user.idioma)}), 409
    dados = request.get_json(silent=True) or request.form
    credenciais_agentes.carregar(app.config['SECRET_KEY'])
    try:
        conversa, resposta = chat_assistente.perguntar(current_user, dados.get('pergunta', ''), _inteiro(dados.get('conversa_id')),
                                                       idioma=current_user.idioma or 'pt', usar_ia=not eh_conta_de_teste(current_user))
    except ValueError:
        return jsonify({'erro': tt('Escreva a sua pergunta.', current_user.idioma)}), 400
    except chat_assistente.LimiteExcedido:
        return jsonify({'erro': tt('Você atingiu o limite de perguntas desta hora. Tente de novo mais tarde.', current_user.idioma)}), 429
    mensagens = chat_assistente.mensagens_para_tela(conversa)
    return jsonify({'conversa_id': conversa.id, 'titulo': conversa.titulo, 'resposta': mensagens[-1],
                    'pergunta': mensagens[-2] if len(mensagens) > 1 else None})


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@app.route('/admin/assistente/conversa/<int:id>')
@login_required
def assistente_conversa(id):
    bloqueio = _bloqueio_assistente(como_json=True)
    if bloqueio:
        return bloqueio
    import chat_assistente
    conversa = chat_assistente.conversa_do_usuario(current_user, id)
    if conversa is None:
        return jsonify({'erro': tt('Conversa não encontrada.', current_user.idioma)}), 404
    return jsonify({'conversa_id': conversa.id, 'titulo': conversa.titulo, 'mensagens': chat_assistente.mensagens_para_tela(conversa)})


@app.route('/admin/assistente/conversa/ultima')
@login_required
def assistente_ultima_conversa():
    bloqueio = _bloqueio_assistente(como_json=True)
    if bloqueio:
        return bloqueio
    import chat_assistente
    conversa = chat_assistente.conversa_do_usuario(current_user)
    return jsonify({'conversa_id': conversa.id if conversa else None, 'titulo': conversa.titulo if conversa else '',
                    'mensagens': chat_assistente.mensagens_para_tela(conversa)})


@app.route('/admin/assistente/conversa/<int:id>/excluir', methods=['POST'])
@login_required
def assistente_excluir_conversa(id):
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import chat_assistente
    conversa = chat_assistente.conversa_do_usuario(current_user, id)
    if conversa:
        chat_assistente.excluir_conversa(conversa)
        flash(tt('Conversa excluída.', current_user.idioma), 'success')
    return redirect(url_for('assistente'))


@app.route('/admin/assistente/documentos', methods=['POST'])
@login_required
def assistente_documentos():
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    idioma = current_user.idioma
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        flash(tt('Escolha o arquivo do documento.', idioma), 'warning')
        return redirect(url_for('assistente', aba='base'))
    try:
        fonte = base_conhecimento.adicionar_documento(request.form.get('tipo'), request.form.get('titulo'), arquivo.filename,
                                                      arquivo.read(), app.config['UPLOAD_FOLDER'], current_user.id,
                                                      request.form.get('descricao', ''))
    except base_conhecimento.ErroDocumento as e:
        db.session.rollback()
        flash(tt(str(e), idioma), 'danger')
        return redirect(url_for('assistente', aba='base'))
    flash(f"{tt('Documento adicionado à base', idioma)}: {fonte.titulo} (v{fonte.versao}) · {fonte.total_trechos} {tt('trechos', idioma)}.", 'success')
    return redirect(url_for('assistente', aba='base'))


@app.route('/admin/assistente/documentos/<int:id>/situacao', methods=['POST'])
@login_required
def assistente_situacao_documento(id):
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    from models import FonteConhecimento
    fonte = db.get_or_404(FonteConhecimento, id)
    base_conhecimento.alternar(fonte, request.form.get('ativo') == '1')
    flash(tt('Fonte ativada: o Assistente passa a usá-la.' if fonte.ativo else 'Fonte desativada: o Assistente deixa de usá-la.',
             current_user.idioma), 'success')
    return redirect(url_for('assistente', aba='base'))


@app.route('/admin/assistente/documentos/<int:id>/excluir', methods=['POST'])
@login_required
def assistente_excluir_documento(id):
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    from models import FonteConhecimento
    fonte = db.get_or_404(FonteConhecimento, id)
    try:
        base_conhecimento.excluir(fonte)
        flash(tt('Documento excluído da base.', current_user.idioma), 'success')
    except base_conhecimento.ErroDocumento as e:
        flash(tt(str(e), current_user.idioma), 'warning')
    return redirect(url_for('assistente', aba='base'))


@app.route('/admin/assistente/documentos/<int:id>/arquivo')
@login_required
def assistente_arquivo_documento(id):
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    from models import FonteConhecimento
    fonte = db.get_or_404(FonteConhecimento, id)
    pasta = os.path.realpath(base_conhecimento.pasta_documentos(app.config['UPLOAD_FOLDER']))
    caminho = os.path.realpath(fonte.arquivo_caminho or '')
    if not fonte.arquivo_caminho or not caminho.startswith(pasta + os.sep) or not os.path.isfile(caminho):
        flash(tt('Arquivo não encontrado.', current_user.idioma), 'warning')
        return redirect(url_for('assistente', aba='base'))
    return send_file(caminho, as_attachment=True, download_name=fonte.arquivo_nome or os.path.basename(caminho))


@app.route('/admin/assistente/documentos/<int:id>/trechos')
@login_required
def assistente_trechos_documento(id):
    bloqueio = _bloqueio_assistente(como_json=True)
    if bloqueio:
        return bloqueio
    from models import FonteConhecimento, TrechoConhecimento
    fonte = db.get_or_404(FonteConhecimento, id)
    trechos = TrechoConhecimento.query.filter_by(fonte_id=fonte.id).order_by(TrechoConhecimento.ordem).limit(300).all()
    return jsonify({'titulo': fonte.titulo, 'versao': fonte.versao, 'total': fonte.total_trechos,
                    'trechos': [{'secao': t.secao or '', 'texto': t.texto} for t in trechos]})


@app.route('/admin/assistente/sincronizar', methods=['POST'])
@login_required
def assistente_sincronizar():
    bloqueio = _bloqueio_assistente()
    if bloqueio:
        return bloqueio
    import base_conhecimento
    fonte, mudou = base_conhecimento.sincronizar_gerentes(current_user.id, forcar=True)
    flash((tt('Conhecimento dos Agentes gerentes atualizado', current_user.idioma) if mudou
           else tt('O conhecimento dos Agentes gerentes já estava em dia', current_user.idioma))
          + f": {fonte.total_trechos} {tt('trechos', current_user.idioma)}.", 'success')
    return redirect(url_for('assistente', aba='base'))


@app.route('/admin/agentes-ia')
@login_required
def agentes_ia():
    import importlib.util
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    return render_template('agentes_ia.html', ordem=ORDEM_AGENTES_IA, estado=estado_agentes_ia(), arvore=arvore_agentes_ia(),
                           playwright_ok=importlib.util.find_spec('playwright') is not None)


@app.route('/admin/agentes-ia/iniciar', methods=['POST'])
@login_required
def iniciar_agentes_ia():
    """O Agente Gestor roda em segundo plano e dispara os agentes um a um, começando pelo Administrador."""
    import importlib.util
    import subprocess
    import sys as _sys
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = estado_agentes_ia()
    if estado and estado.get('status') == 'executando':
        flash(tt('Já existe uma execução em andamento.', current_user.idioma), "warning")
        return redirect(url_for('agentes_ia'))
    indisponivel = _recurso_indisponivel('omnitest')
    if indisponivel:
        flash(indisponivel, 'danger')
        return redirect(url_for('agentes_ia'))
    if importlib.util.find_spec('playwright') is None:
        flash(tt('Este servidor não tem o Playwright instalado: rode os agentes num computador com o Playwright.', current_user.idioma), "danger")
        return redirect(url_for('agentes_ia'))
    validos = [c for c, _ in ORDEM_AGENTES_IA]
    perfis = [p for p in request.form.getlist('perfis') if p in validos] or validos
    raiz = os.path.dirname(os.path.abspath(__file__))
    cmd = [_sys.executable, os.path.join(raiz, 'agentes_omnitest', 'agente_gestor.py'), '--perfis', *perfis,
           '--url', request.host_url.rstrip('/'), '--lento', '150']
    if request.form.get('escrita'):
        cmd.append('--escrita')
    os.makedirs(PASTA_AO_VIVO_IA, exist_ok=True)
    for nome in ('estado.json', 'agente.json', 'frame.jpg'):
        try:
            os.remove(os.path.join(PASTA_AO_VIVO_IA, nome))
        except OSError:
            pass
    opcoes = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    log = open(os.path.join(PASTA_AO_VIVO_IA, 'gestor.log'), 'w', encoding='utf-8')
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente_dos_agentes(), **opcoes)
    flash(tt('Agente Gestor iniciado: os testes começam pelo Administrador.', current_user.idioma), "success")
    return redirect(url_for('agentes_ia'))


@app.route('/admin/agentes-ia/parar', methods=['POST'])
@login_required
def parar_agentes_ia():
    import subprocess
    import signal
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = _ler_json_ia('estado.json')
    if estado and estado.get('pid'):
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(estado['pid']), '/T', '/F'], capture_output=True, timeout=20)
            else:
                os.killpg(os.getpgid(estado['pid']), signal.SIGTERM)
        except Exception:
            pass
        estado.update(status='parado', fim=datetime.now().isoformat(timespec='seconds'))
        estado['log'] = (estado.get('log') or []) + [f"{datetime.now().strftime('%H:%M:%S')}  ■ {current_user.nome} parou a execução"]
        with open(os.path.join(PASTA_AO_VIVO_IA, 'estado.json'), 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False)
        flash(tt('Execução interrompida.', current_user.idioma), "info")
    return redirect(url_for('agentes_ia'))


@app.route('/admin/agentes-ia/estado')
@login_required
def estado_agentes_ia_json():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return jsonify({'erro': 'acesso negado'}), 403
    quadro = os.path.join(PASTA_AO_VIVO_IA, 'frame.jpg')
    return jsonify({'estado': estado_agentes_ia(), 'agente': _ler_json_ia('agente.json'), 'agora': datetime.now().isoformat(timespec='seconds'),
                    'quadro': os.path.getmtime(quadro) if os.path.exists(quadro) else None})


@app.route('/admin/agentes-ia/quadro')
@login_required
def quadro_agentes_ia():
    """Último quadro do navegador do agente em execução (o monitor central da página)."""
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return '', 403
    quadro = os.path.join(PASTA_AO_VIVO_IA, 'frame.jpg')
    if not os.path.exists(quadro):
        return '', 204
    try:
        with open(quadro, 'rb') as f:
            dados = f.read()
    except OSError:
        return '', 204
    resposta = app.response_class(dados, mimetype='image/jpeg')
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta


@app.route('/admin/agentes-ia/arquivo')
@login_required
def arquivo_agentes_ia():
    """Abre (PDF) ou baixa (prompt .md) um arquivo das pastas da área. Só dentro de Agent Reports/Agentes IA."""
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    base = os.path.realpath(PASTA_AGENTES_IA)
    alvo = os.path.realpath(os.path.join(base, request.args.get('f', '')))
    if not alvo.startswith(base + os.sep) or not os.path.isfile(alvo) or not alvo.lower().endswith(('.pdf', '.md')):
        flash(tt('Arquivo não encontrado.', current_user.idioma), "warning")
        return redirect(url_for('agentes_ia'))
    return send_file(alvo, as_attachment=alvo.lower().endswith('.md'), download_name=os.path.basename(alvo))


# ==============================================================================
# ADMINISTRAÇÃO › AGENTES DE SEGURANÇA: Gerente de Segurança + 5 especialistas (dados, configuração, SAST, SCA e pentest)
# ==============================================================================
PASTA_AO_VIVO_SEG = os.path.join(PASTA_AGENTES_IA, '.ao_vivo_seguranca')
# (chave, nome, ícone, o que verifica)
ORDEM_AGENTES_SEG = [
    ('configuracao', 'Configuração e Segredos', 'bi-key-fill',
     'Chaves secretas, modo debug, cookies, CSRF, cabeçalhos de segurança e segredos esquecidos no código.'),
    ('dados', 'Inconsistências de Dados', 'bi-database-fill-exclamation',
     'Senhas e respostas de segurança mal guardadas, contas de teste, perfis e vínculos inconsistentes, integridade do banco.'),
    ('codigo', 'Análise de Código (SAST)', 'bi-code-slash',
     'Funções perigosas, SQL montado com texto, rotas sem login, XSS nos templates e código mal escrito.'),
    ('dependencias', 'Dependências e Tecnologias (SCA)', 'bi-boxes',
     'Vulnerabilidades conhecidas (OSV.dev) do Python, Flask, bibliotecas e CDNs; pacotes descontinuados e SRI.'),
    ('pentest', 'Pentest (DAST)', 'bi-bug-fill',
     'Ataques controlados na plataforma em execução: XSS, SQL injection, IDOR, CSRF, força bruta, sessão e redirecionamento.'),
]


def _ler_json_seg(nome):
    try:
        with open(os.path.join(PASTA_AO_VIVO_SEG, nome), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def estado_agentes_seguranca():
    estado = _ler_json_seg('estado.json')
    if estado and estado.get('status') == 'executando' and time.time() - estado.get('batimento', 0) > 30:
        estado['status'] = 'interrompido'
    return estado


@app.route('/admin/agentes-seguranca')
@login_required
def agentes_seguranca():
    import importlib.util
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    grupo = next(g for g in arvore_agentes_ia() if g['nome'] == 'Agentes Teste de Segurança')
    from urllib.parse import urlparse
    alvo = urlparse(request.host_url).hostname or ''
    import conhecimento_seguranca
    try:
        aprendizado = conhecimento_seguranca.resumo_para_tela()
    except Exception:
        db.session.rollback()
        aprendizado = None
    return render_template('agentes_seguranca.html', ordem=ORDEM_AGENTES_SEG, estado=estado_agentes_seguranca(), grupo=grupo, aprendizado=aprendizado,
                           playwright_ok=importlib.util.find_spec('playwright') is not None,
                           pentest_local=alvo in ('localhost', '127.0.0.1', '::1') or alvo.endswith(('.localhost', '.test')))


@app.route('/admin/agentes-seguranca/iniciar', methods=['POST'])
@login_required
def iniciar_agentes_seguranca():
    """O Gerente de Segurança roda em segundo plano e chama os especialistas um a um."""
    import subprocess
    import sys as _sys
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = estado_agentes_seguranca()
    if estado and estado.get('status') == 'executando':
        flash(tt('Já existe uma execução em andamento.', current_user.idioma), "warning")
        return redirect(url_for('agentes_seguranca'))
    indisponivel = _recurso_indisponivel('agentes')
    if indisponivel:
        flash(indisponivel, 'danger')
        return redirect(url_for('agentes_seguranca'))
    validos = [c for c, *_ in ORDEM_AGENTES_SEG]
    agentes = [a for a in request.form.getlist('agentes') if a in validos] or validos
    raiz = os.path.dirname(os.path.abspath(__file__))
    cmd = [_sys.executable, os.path.join(raiz, 'agentes_seguranca', 'gestor_seguranca.py'), '--agentes', *agentes,
           '--url', request.host_url.rstrip('/')]
    os.makedirs(PASTA_AO_VIVO_SEG, exist_ok=True)
    for nome in ('estado.json', 'agente.json'):
        try:
            os.remove(os.path.join(PASTA_AO_VIVO_SEG, nome))
        except OSError:
            pass
    opcoes = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    log = open(os.path.join(PASTA_AO_VIVO_SEG, 'gestor.log'), 'w', encoding='utf-8')
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente_dos_agentes(), **opcoes)
    flash(tt('Gerente de Segurança iniciado: a auditoria começa pela configuração.', current_user.idioma), "success")
    return redirect(url_for('agentes_seguranca'))


@app.route('/admin/agentes-seguranca/aprender', methods=['POST'])
@login_required
def aprender_agentes_seguranca():
    """Botão "Aprender agora": o Gerente de Segurança aprende as mudanças e pesquisa a OSV.dev (fonte oficial)."""
    import conhecimento_seguranca
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    try:
        novos = conhecimento_seguranca.detectar_mudancas(f"Solicitado por {current_user.nome}")
        flash(tt('Gerente de Segurança: {n} aprendizado(s) novo(s) aplicado(s) aos agentes.', idioma).format(n=len(novos)), 'success')
    except Exception as e:
        db.session.rollback()
        flash(tt('Detecção falhou: {erro}', idioma).format(erro=e), 'danger')
    try:
        pendentes = conhecimento_seguranca.pesquisar_vulnerabilidades(f"Solicitado por {current_user.nome}", forcar=True)
        flash(tt('Pesquisa na OSV.dev: {n} aviso(s) novo(s) aguardando aprovação na Governança.', idioma).format(n=len(pendentes)), 'info')
    except Exception as e:
        db.session.rollback()
        flash(tt('Pesquisa na OSV.dev não realizada: {erro}', idioma).format(erro=e), 'warning')
    return redirect(url_for('agentes_seguranca'))


@app.route('/admin/agentes-seguranca/parar', methods=['POST'])
@login_required
def parar_agentes_seguranca():
    import subprocess
    import signal
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = _ler_json_seg('estado.json')
    if estado and estado.get('pid'):
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(estado['pid']), '/T', '/F'], capture_output=True, timeout=20)
            else:
                os.killpg(os.getpgid(estado['pid']), signal.SIGTERM)
        except Exception:
            pass
        estado.update(status='parado', fim=datetime.now().isoformat(timespec='seconds'))
        estado['log'] = (estado.get('log') or []) + [f"{datetime.now().strftime('%H:%M:%S')}  ■ {current_user.nome} parou a execução"]
        with open(os.path.join(PASTA_AO_VIVO_SEG, 'estado.json'), 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False)
        flash(tt('Execução interrompida.', current_user.idioma), "info")
    return redirect(url_for('agentes_seguranca'))


@app.route('/admin/agentes-seguranca/estado')
@login_required
def estado_agentes_seguranca_json():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return jsonify({'erro': 'acesso negado'}), 403
    return jsonify({'estado': estado_agentes_seguranca(), 'agente': _ler_json_seg('agente.json'), 'agora': datetime.now().isoformat(timespec='seconds')})


# ==============================================================================
# ADMINISTRAÇÃO › AGENTES DE BANCO DE DADOS: Gerente de Banco de Dados + 5 especialistas e as ações do DBA
# ==============================================================================
PASTA_AO_VIVO_BANCO = os.path.join(PASTA_AGENTES_IA, '.ao_vivo_banco')
PASTA_AO_VIVO_FUNC = os.path.join(PASTA_AGENTES_IA, '.ao_vivo_funcionalidades')
# (chave, nome, ícone, o que testa) — na ordem do fluxo: cada um cria os usuários e os dados do próximo
ORDEM_AGENTES_FUNC = [
    ('dev', 'Dev (código)', 'bi-code-slash', 'Varre 100% do código: toda regra de negócio numa regra nomeada, que o Gerente aprende sozinho.'),
    ('ux', 'UX/UI (telas)', 'bi-universal-access', 'Varre 100% das telas: textos traduzidos (pt/en/es), imagens, botões e campos acessíveis e cada papel com o mesmo nome.'),
    ('administrador', 'Administrador', 'bi-shield-fill-check', 'Matriz de acesso, validações do cadastro e cria o Mentor Administrador.'),
    ('mentor_administrador', 'Mentor Administrador', 'bi-person-gear',
     'Primeiro acesso; cria cursos, perfis, empresa, grupo e turma; matricula, cria projeto e tarefa e agenda a banca.'),
    ('gestor_parceiro', 'Gestor Parceiro', 'bi-building', 'Vê só os dados da sua empresa, cadastra avaliadores dela e exporta o ESG.'),
    ('professor', 'Professor', 'bi-journal-check', 'Lança as notas no diário de classe e valida as regras de notas e de grupos.'),
    ('mentor', 'Mentor', 'bi-people', 'Agenda sessão com o aluno, registra parecer e lança horas de voluntariado.'),
    ('aluno', 'Aluno', 'bi-mortarboard', 'Frequência, anotações, retorno da sessão e entregas do TCC; valida o que o aluno não pode fazer.'),
    ('avaliador', 'Avaliador da Banca', 'bi-award', 'Troca a senha, avalia as etapas escrita e oral e confere a fórmula da nota final.'),
    ('encerramento', 'Encerramento do Ciclo', 'bi-patch-check', 'Publica o resultado, leva o TCC ao acervo e emite e verifica o certificado.'),
]


def _ler_json_func(nome):
    try:
        with open(os.path.join(PASTA_AO_VIVO_FUNC, nome), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def estado_agentes_funcionalidades():
    estado = _ler_json_func('estado.json')
    if estado and estado.get('status') == 'executando' and time.time() - estado.get('batimento', 0) > 30:
        estado['status'] = 'interrompido'
    return estado
# (chave, nome, ícone, o que verifica)
ORDEM_AGENTES_BANCO = [
    ('consultas', 'Consultas e Desempenho', 'bi-speedometer',
     'Mede as páginas de verdade (consultas, tempo, repetições), lê o plano de execução e acha consultas lentas e padrões N+1 no código.'),
    ('esquema', 'Esquema e Índices', 'bi-diagram-3',
     'Compara o modelo com o banco, prioriza índices pelas consultas reais, acha registros órfãos e tipos inadequados.'),
    ('backup', 'Backup e Recuperação', 'bi-cloud-check',
     'Confere agendamentos, execuções, integridade dos arquivos e faz um teste de restauração numa cópia temporária.'),
    ('dba', 'DBA (Manutenção e Logs)', 'bi-tools',
     'Integridade, estatísticas (ANALYZE), espaço livre (VACUUM), configuração, crescimento e retenção dos logs.'),
    ('portabilidade', 'Multi-banco', 'bi-database-gear',
     'Especialista em SQLite, PostgreSQL, MySQL, SQL Server e MongoDB: mede a prontidão e o roteiro de migração.'),
]


def _ler_json_banco(nome):
    try:
        with open(os.path.join(PASTA_AO_VIVO_BANCO, nome), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def estado_agentes_banco():
    estado = _ler_json_banco('estado.json')
    if estado and estado.get('status') == 'executando' and time.time() - estado.get('batimento', 0) > 30:
        estado['status'] = 'interrompido'
    return estado


@app.route('/admin/agentes-banco')
@login_required
def agentes_banco():
    import importlib.util
    import backup_servico
    import banco_manutencao
    import conhecimento_banco
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    grupo = next(g for g in arvore_agentes_ia() if g['nome'] == 'Agentes Banco de Dados')
    try:
        aprendizado = conhecimento_banco.resumo_para_tela()
        indices = banco_manutencao.indices_sugeridos() if banco_manutencao.suportado() else []
        saude_backup = backup_servico.saude()
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Agentes de Banco de Dados: {e}")
        aprendizado, indices, saude_backup = None, [], None
    return render_template('agentes_banco.html', ordem=ORDEM_AGENTES_BANCO, estado=estado_agentes_banco(), grupo=grupo, aprendizado=aprendizado,
                           indices=indices, manutencoes=banco_manutencao.historico(15), acoes=banco_manutencao.ACOES, saude_backup=saude_backup,
                           motores=conhecimento_banco.MOTORES, playwright_ok=importlib.util.find_spec('playwright') is not None)


@app.route('/admin/agentes-banco/iniciar', methods=['POST'])
@login_required
def iniciar_agentes_banco():
    """O Gerente de Banco de Dados roda em segundo plano e chama os especialistas um a um."""
    import subprocess
    import sys as _sys
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = estado_agentes_banco()
    if estado and estado.get('status') == 'executando':
        flash(tt('Já existe uma execução em andamento.', current_user.idioma), "warning")
        return redirect(url_for('agentes_banco'))
    indisponivel = _recurso_indisponivel('agentes')
    if indisponivel:
        flash(indisponivel, 'danger')
        return redirect(url_for('agentes_banco'))
    validos = [c for c, *_ in ORDEM_AGENTES_BANCO]
    agentes = [a for a in request.form.getlist('agentes') if a in validos] or validos
    raiz = os.path.dirname(os.path.abspath(__file__))
    cmd = [_sys.executable, os.path.join(raiz, 'agentes_banco', 'gestor_banco.py'), '--agentes', *agentes]
    os.makedirs(PASTA_AO_VIVO_BANCO, exist_ok=True)
    for nome in ('estado.json', 'agente.json'):
        try:
            os.remove(os.path.join(PASTA_AO_VIVO_BANCO, nome))
        except OSError:
            pass
    opcoes = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    log = open(os.path.join(PASTA_AO_VIVO_BANCO, 'gestor.log'), 'w', encoding='utf-8')
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente_dos_agentes(), **opcoes)
    flash(tt('Gerente de Banco de Dados iniciado: a análise começa pelas consultas.', current_user.idioma), "success")
    return redirect(url_for('agentes_banco'))


@app.route('/admin/agentes-banco/parar', methods=['POST'])
@login_required
def parar_agentes_banco():
    import subprocess
    import signal
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = _ler_json_banco('estado.json')
    if estado and estado.get('pid'):
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(estado['pid']), '/T', '/F'], capture_output=True, timeout=20)
            else:
                os.killpg(os.getpgid(estado['pid']), signal.SIGTERM)
        except Exception:
            pass
        estado.update(status='parado', fim=datetime.now().isoformat(timespec='seconds'))
        estado['log'] = (estado.get('log') or []) + [f"{datetime.now().strftime('%H:%M:%S')}  ■ {current_user.nome} parou a execução"]
        with open(os.path.join(PASTA_AO_VIVO_BANCO, 'estado.json'), 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False)
        flash(tt('Execução interrompida.', current_user.idioma), "info")
    return redirect(url_for('agentes_banco'))


@app.route('/admin/agentes-banco/estado')
@login_required
def estado_agentes_banco_json():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return jsonify({'erro': 'acesso negado'}), 403
    return jsonify({'estado': estado_agentes_banco(), 'agente': _ler_json_banco('agente.json'), 'agora': datetime.now().isoformat(timespec='seconds')})


@app.route('/admin/agentes-banco/aprender', methods=['POST'])
@login_required
def aprender_agentes_banco():
    """'Aprender agora' (mudanças do banco) ou 'Aprender sobre outro banco' (documentação oficial, pendente de aprovação)."""
    import conhecimento_banco
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    motor = request.form.get('motor')
    try:
        if motor:
            if motor not in conhecimento_banco.MOTORES:
                raise ValueError(tt('banco desconhecido', idioma))
            novos = conhecimento_banco.aprender_sobre_banco(motor, current_user.id, f"Solicitado por {current_user.nome}")
            flash(tt('{banco}: {n} página(s) oficial(is) lida(s) e enviada(s) para aprovação na Governança.', idioma)
                  .format(banco=conhecimento_banco.MOTORES[motor], n=len(novos)), 'success' if novos else 'info')
        else:
            novos = conhecimento_banco.detectar_mudancas(f"Solicitado por {current_user.nome}")
            flash(tt('Gerente de Banco de Dados: {n} aprendizado(s) novo(s) aplicado(s) aos agentes.', idioma).format(n=len(novos)), 'success')
    except Exception as e:
        db.session.rollback()
        flash(tt('Detecção falhou: {erro}', idioma).format(erro=e), 'danger')
    return redirect(url_for('agentes_banco'))


@app.route('/admin/agentes-funcionalidades')
@login_required
def agentes_funcionalidades():
    import importlib.util
    import conhecimento_funcional
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    grupo = next(g for g in arvore_agentes_ia() if g['nome'] == 'Agentes Funcionalidades')
    try:
        aprendizado = conhecimento_funcional.resumo_para_tela()
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Agentes de Funcionalidades: {e}")
        aprendizado = None
    return render_template('agentes_funcionalidades.html', ordem=ORDEM_AGENTES_FUNC, estado=estado_agentes_funcionalidades(), grupo=grupo,
                           aprendizado=aprendizado, playwright_ok=importlib.util.find_spec('playwright') is not None)


@app.route('/admin/agentes-funcionalidades/iniciar', methods=['POST'])
@login_required
def iniciar_agentes_funcionalidades():
    """O Gerente de Funcionalidades roda em segundo plano e passa a vez de agente em agente, pelo fluxo da plataforma."""
    import subprocess
    import sys as _sys
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = estado_agentes_funcionalidades()
    if estado and estado.get('status') == 'executando':
        flash(tt('Já existe uma execução em andamento.', current_user.idioma), "warning")
        return redirect(url_for('agentes_funcionalidades'))
    indisponivel = _recurso_indisponivel('agentes')
    if indisponivel:
        flash(indisponivel, 'danger')
        return redirect(url_for('agentes_funcionalidades'))
    raiz = os.path.dirname(os.path.abspath(__file__))
    cmd = [_sys.executable, os.path.join(raiz, 'agentes_funcionalidades', 'gestor_funcionalidades.py'), '--url', request.host_url.rstrip('/')]
    if request.form.get('manter_dados'):
        cmd.append('--manter-dados')
    os.makedirs(PASTA_AO_VIVO_FUNC, exist_ok=True)
    for nome in ('estado.json', 'agente.json', 'frame.png', 'frame.json'):
        try:
            os.remove(os.path.join(PASTA_AO_VIVO_FUNC, nome))
        except OSError:
            pass
    opcoes = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    log = open(os.path.join(PASTA_AO_VIVO_FUNC, 'gestor.log'), 'w', encoding='utf-8')
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente_dos_agentes(), **opcoes)
    flash(tt('Gerente de Funcionalidades iniciado: o Administrador começa o fluxo e passa a vez para o Mentor Administrador.', current_user.idioma), "success")
    return redirect(url_for('agentes_funcionalidades'))


# ==============================================================================
# AGENTE ORQUESTRADOR EXECUTOR: lê os prompts de correção das 4 equipes, corrige numa cópia, valida e só então commita
# ==============================================================================
def _orquestrador():
    import sys as _sys
    pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agentes_orquestrador')
    if pasta not in _sys.path:
        _sys.path.insert(0, pasta)
    import executor as orquestrador_executor
    import coletor as orquestrador_coletor
    import ambiente_orquestrador as orquestrador_ambiente  # não confundir com o ambiente.py da raiz
    import ia_correcao as orquestrador_ia
    return orquestrador_executor, orquestrador_coletor, orquestrador_ambiente, orquestrador_ia


def _orquestrador_em_execucao(estado):
    """Em execução de verdade: status 'executando' e o processo deu sinal de vida há pouco."""
    import time as _time
    return bool(estado) and estado.get('status') == 'executando' and _time.time() - (estado.get('batimento') or 0) < 15 * 60


@app.route('/admin/agentes-orquestrador')
@login_required
def agentes_orquestrador():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, coletor, ambiente_orq, ia = _orquestrador()
    ignorados = executor.ignorados()
    correcoes = coletor.coletar()
    estado = executor.ler_estado()
    if estado:
        estado['diff'] = None  # o diff é baixado à parte
    return render_template('agentes_orquestrador.html', correcoes=[c for c in correcoes if c['id'] not in ignorados],
                           ignorados=[{**ignorados[c['id']], **c} for c in correcoes if c['id'] in ignorados],
                           ambiente=ambiente_orq.capacidades(), provedores=ia.provedores_disponiveis(), estado=estado,
                           em_execucao=_orquestrador_em_execucao(estado), historico=executor.historico(),
                           equipes=executor.EQUIPES_VALIDACAO)


@app.route('/admin/agentes-orquestrador/iniciar', methods=['POST'])
@login_required
def iniciar_orquestrador():
    import subprocess
    import sys as _sys
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, coletor, ambiente_orq, ia = _orquestrador()
    idioma = current_user.idioma
    estado = executor.ler_estado()
    if _orquestrador_em_execucao(estado) or (estado and estado.get('status') == 'aguardando_confirmacao'):
        flash(tt('Termine a correção em andamento (confirme ou faça o rollback) antes de começar outra.', idioma), 'warning')
        return redirect(url_for('agentes_orquestrador'))
    capacidade = ambiente_orq.capacidades()
    if not capacidade['pode_corrigir']:
        flash(tt('Este ambiente não permite corrigir o código. Veja os itens em vermelho no quadro do ambiente.', idioma), 'danger')
        return redirect(url_for('agentes_orquestrador'))
    provedor = request.form.get('provedor', 'gemini')
    if provedor not in ia.provedores_disponiveis():
        flash(tt('A IA escolhida não tem chave configurada no .env.', idioma), 'warning')
        return redirect(url_for('agentes_orquestrador'))
    import provedores_ia
    if not provedores_ia.ativo('orquestrador'):
        flash(tt('A IA do Agente Orquestrador está desligada. Ligue em Administração › Provedores de IA.', idioma), 'warning')
        return redirect(url_for('agentes_orquestrador'))
    try:
        provedores_ia.conferir_orcamento()
    except provedores_ia.OrcamentoEsgotado as e:
        flash(f"{tt('O Orquestrador não pode usar a IA agora', idioma)}: {e}.", 'warning')
        return redirect(url_for('agentes_orquestrador'))
    ignorados = executor.ignorados()
    disponiveis = [c['id'] for c in coletor.coletar() if c['id'] not in ignorados]
    ids = disponiveis if request.form.get('tudo') else [i for i in request.form.getlist('ids') if i in disponiveis]
    if not ids:
        flash(tt('Nenhuma correção escolhida.', idioma), 'warning')
        return redirect(url_for('agentes_orquestrador'))
    equipes = [e for e in request.form.getlist('equipes') if e in {c for c, *_ in executor.EQUIPES_VALIDACAO}] or \
        [c for c, *_ in executor.EQUIPES_VALIDACAO]
    raiz = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(executor.PASTA_AO_VIVO, exist_ok=True)
    cmd = [_sys.executable, os.path.join(raiz, 'agentes_orquestrador', 'executor.py'), '--provedor', provedor,
           '--usuario', current_user.nome, '--ids', *ids, '--equipes', *equipes]
    opcoes = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    log = open(os.path.join(executor.PASTA_AO_VIVO, 'executor.log'), 'w', encoding='utf-8')
    ambiente = ambiente_dos_agentes()
    for nome_provedor, variavel in (('claude', 'ORQUESTRADOR_MODELO_CLAUDE'), ('gemini', 'ORQUESTRADOR_MODELO_GEMINI'),
                                    ('openai', 'ORQUESTRADOR_MODELO_OPENAI')):
        modelo_escolhido = provedores_ia.modelo_de_provedor('orquestrador', nome_provedor)  # tela Provedores de IA
        if modelo_escolhido:
            ambiente[variavel] = modelo_escolhido
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente, **opcoes)
    flash(tt('Orquestrador iniciado: as correções são feitas numa cópia do código e validadas pelas equipes antes de qualquer commit.', idioma), 'success')
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-orquestrador/ignorar', methods=['POST'])
@login_required
def ignorar_correcao():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    ignorados = executor.ignorados()
    correcao_id = (request.form.get('id') or '')[:20]
    if request.form.get('acao') == 'restaurar':
        ignorados.pop(correcao_id, None)
        flash(tt('Correção de volta à lista.', current_user.idioma), 'info')
    elif correcao_id:
        ignorados[correcao_id] = {'por': current_user.nome, 'em': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                  'motivo': (request.form.get('motivo') or '').strip()[:300], 'titulo': (request.form.get('titulo') or '')[:200]}
        flash(tt('Correção ignorada. Ela pode voltar à lista quando você quiser.', current_user.idioma), 'info')
    executor._gravar_json(executor.ARQUIVO_IGNORADOS, ignorados)
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-orquestrador/estado.json')
@login_required
def estado_orquestrador_json():
    bloqueio = _somente_administrador()
    if bloqueio:
        return jsonify({'erro': 'acesso negado'}), 403
    executor, *_ = _orquestrador()
    estado = executor.ler_estado() or {}
    estado.pop('diff', None)
    estado['em_execucao'] = _orquestrador_em_execucao(estado)
    return jsonify(estado)


@app.route('/admin/agentes-orquestrador/diff')
@login_required
def diff_orquestrador():
    from flask import Response
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    estado = executor.ler_estado() or {}
    return Response(estado.get('diff') or 'Sem alterações pendentes.', mimetype='text/plain; charset=utf-8')


@app.route('/admin/agentes-orquestrador/confirmar', methods=['POST'])
@login_required
def confirmar_orquestrador():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    ok, mensagem = executor.confirmar(current_user.nome)
    flash(mensagem, 'success' if ok else 'danger')
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-orquestrador/rollback', methods=['POST'])
@login_required
def rollback_orquestrador():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    ok, mensagem = executor.rollback(current_user.nome)
    flash(mensagem, 'success' if ok else 'warning')
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-orquestrador/desfazer', methods=['POST'])
@login_required
def desfazer_orquestrador():
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    commit = (request.form.get('commit') or '').strip()
    if not re.fullmatch(r'[0-9a-f]{7,40}', commit):
        return redirect(url_for('agentes_orquestrador'))
    ok, mensagem = executor.desfazer_commit(commit, current_user.nome)
    flash(mensagem, 'success' if ok else 'danger')
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-orquestrador/parar', methods=['POST'])
@login_required
def parar_orquestrador():
    import signal
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    executor, *_ = _orquestrador()
    estado = executor.ler_estado()
    if estado and estado.get('status') == 'executando' and estado.get('pid'):
        import subprocess
        try:
            pid = int(estado['pid'])
            if os.name == 'nt':  # encerra também a instância de validação e as equipes que o executor abriu
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True, timeout=30)
            else:
                os.killpg(pid, signal.SIGTERM)  # o executor nasce num grupo de processos próprio
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        estado['status'] = 'parado'
        executor._gravar_json(executor.ARQUIVO_ESTADO, estado)
        executor.rollback(current_user.nome)
        flash(tt('Orquestrador parado e cópia descartada: nada foi alterado no código em uso.', current_user.idioma), 'info')
    return redirect(url_for('agentes_orquestrador'))


@app.route('/admin/agentes-funcionalidades/parar', methods=['POST'])
@login_required
def parar_agentes_funcionalidades():
    import subprocess
    import signal
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    estado = _ler_json_func('estado.json')
    if estado and estado.get('pid'):
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(estado['pid']), '/T', '/F'], capture_output=True, timeout=20)
            else:
                os.killpg(os.getpgid(estado['pid']), signal.SIGTERM)
        except Exception:
            pass
        estado.update(status='parado', fim=datetime.now().isoformat(timespec='seconds'))
        estado['log'] = (estado.get('log') or []) + [f"{datetime.now().strftime('%H:%M:%S')}  ■ {current_user.nome} parou a execução "
                                                     "(os dados [Funcional] serão removidos no início da próxima execução)"]
        with open(os.path.join(PASTA_AO_VIVO_FUNC, 'estado.json'), 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False)
        flash(tt('Execução interrompida.', current_user.idioma), "info")
    return redirect(url_for('agentes_funcionalidades'))


@app.route('/admin/agentes-funcionalidades/estado')
@login_required
def estado_agentes_funcionalidades_json():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return jsonify({'erro': 'acesso negado'}), 403
    quadro = os.path.join(PASTA_AO_VIVO_FUNC, 'frame.png')
    return jsonify({'estado': estado_agentes_funcionalidades(), 'agente': _ler_json_func('agente.json'), 'frame': _ler_json_func('frame.json'),
                    'quadro': os.path.getmtime(quadro) if os.path.exists(quadro) else None, 'agora': datetime.now().isoformat(timespec='seconds')})


@app.route('/admin/agentes-funcionalidades/quadro')
@login_required
def quadro_agentes_funcionalidades():
    """Último print capturado pelo agente em execução."""
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return '', 403
    quadro = os.path.join(PASTA_AO_VIVO_FUNC, 'frame.png')
    if not os.path.exists(quadro):
        return '', 204
    try:
        with open(quadro, 'rb') as f:
            dados = f.read()
    except OSError:
        return '', 204
    resposta = app.response_class(dados, mimetype='image/png')
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta


@app.route('/admin/agentes-funcionalidades/aprender', methods=['POST'])
@login_required
def aprender_agentes_funcionalidades():
    import conhecimento_funcional
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    try:
        novos = conhecimento_funcional.detectar_mudancas(f"Solicitado por {current_user.nome}")
        flash(tt('Gerente de Funcionalidades: {n} aprendizado(s) novo(s) aplicado(s) aos agentes.', current_user.idioma).format(n=len(novos)), 'success')
    except Exception as e:
        db.session.rollback()
        flash(tt('Detecção falhou: {erro}', current_user.idioma).format(erro=e), 'danger')
    return redirect(url_for('agentes_funcionalidades'))


@app.route('/admin/agentes-banco/manutencao', methods=['POST'])
@login_required
def manutencao_agentes_banco():
    """Ações do DBA: sempre com backup validado antes de alterar o banco (banco_manutencao.py)."""
    import banco_manutencao
    bloqueio = _somente_administrador()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    acao = request.form.get('acao')
    if acao not in banco_manutencao.ACOES:
        flash(tt('Ação desconhecida.', idioma), 'warning')
        return redirect(url_for('agentes_banco'))
    if acao in ('vacuum', 'indices') and (request.form.get('confirmacao') or '').strip().upper() != 'CONFIRMAR':
        flash(tt('Para alterar o banco, digite CONFIRMAR no campo de confirmação.', idioma), 'warning')
        return redirect(url_for('agentes_banco'))
    registro = banco_manutencao.executar(acao, current_user.id, request.form.getlist('indices'))
    nome = tt(banco_manutencao.ACOES[acao], idioma)
    if registro.status == 'Concluída':
        flash(tt('{acao}: concluída. {detalhes}', idioma).format(acao=nome, detalhes=registro.detalhes or ''), 'success')
    else:
        flash(tt('{acao}: falhou. {detalhes}', idioma).format(acao=nome, detalhes=registro.detalhes or ''), 'danger')
    return redirect(url_for('agentes_banco'))


# ==============================================================================
# PAINEL GERAL: GRÁFICOS PERSONALIZÁVEIS POR UTILIZADOR
# Cada perfil vê um catálogo de dados; cada utilizador escolhe até 4 gráficos (dado, tipo e cor).
# ==============================================================================
TIPOS_GRAFICO_SIMPLES = ['barras', 'barras_h', 'linhas', 'area', 'pizza', 'rosca', 'polar', 'radar']
TIPOS_GRAFICO_MULTI = ['misto', 'barras', 'barras_empilhadas', 'linhas', 'area']
MAX_GRAFICOS_PAINEL = 4
CORES_PADRAO_PAINEL = ['#0d6efd', '#6f42c1', '#198754', '#fd7e14']


def montar_fontes_painel(usuario, idioma, dados):
    """Catálogo de dados para os gráficos do Painel Geral, conforme o perfil.
    'dados' traz o que a rota dashboard() já agregou dos acompanhamentos visíveis ao perfil."""
    def serie(rotulo, valores):
        return {'rotulo': rotulo, 'dados': valores}

    def simples(titulo, pares, rotulo, traduzir_rotulos=False):
        pares = list(pares)
        return {'titulo': titulo, 'multi': False,
                'labels': [tt(str(k), idioma) if traduzir_rotulos else k for k, _ in pares],
                'series': [serie(rotulo, [v for _, v in pares])]}

    fontes = {
        'evolucao': {'titulo': t('titulo_grafico_evolucao', idioma), 'multi': True, 'labels': dados['evolucao_labels'],
                     'series': [serie(t('label_volume_horas', idioma), dados['evolucao_horas']),
                                serie(tt('Cursos iniciados', idioma), dados.get('evolucao_iniciados', [])),
                                serie(t('label_cursos_concluidos', idioma), dados['evolucao_cursos'])]},
        'habilidades': {'titulo': t('titulo_grafico_skills', idioma), 'multi': False, 'labels': dados['radar_labels'],
                        'series': [serie(t('label_progresso_curso', idioma), dados['radar_valores'])], 'max': 100},
        'status_cursos': simples(tt('Cursos por status', idioma), sorted(dados['contagem_status'].items()), tt('Cursos', idioma), True),
        'saude_cursos': simples(tt('Saúde dos cursos', idioma),
                                [(tt('Saudáveis', idioma), dados['saudavel']), (tt('Em atenção', idioma), dados['atencao']), (tt('Em risco', idioma), dados['risco'])],
                                tt('Cursos', idioma)),
        'certificacao': simples(tt('Certificação dos cursos finalizados', idioma),
                                [(t('com_certificado', idioma), dados['com_certificado']), (t('sem_certificado', idioma), dados['sem_certificado'])],
                                tt('Cursos', idioma)),
        'carga_por_tipo': simples(tt('Carga horária por tipo de curso', idioma), sorted(dados['carga_por_tipo'].items()), tt('Horas', idioma), True),
        'projetos': simples(tt('Projetos (TCC) por status', idioma),
                            [(tt('Em Andamento', idioma), dados['projetos_andamento']), (tt('Concluído', idioma), dados['projetos_concluidos'])],
                            tt('Projetos', idioma)),
    }
    if usuario.tipo_usuario == 'Aluno':
        fontes['progresso_por_curso'] = simples(tt('Progresso por curso', idioma),
                                                sorted(dados['progresso_por_curso'].items(), key=lambda x: -x[1])[:12], '%')
        fontes['progresso_por_curso']['max'] = 100
    else:
        medias = sorted(((nome, round(s / q, 1)) for nome, (s, q) in dados['progresso_por_aluno'].items() if q), key=lambda x: -x[1])[:12]
        fontes['progresso_por_aluno'] = simples(tt('Progresso médio por aluno', idioma), medias, '%')
        fontes['progresso_por_aluno']['max'] = 100
        from models import CheckinVoluntariado
        por_mes = {}
        for c in CheckinVoluntariado.query.filter(CheckinVoluntariado.usuario_id == usuario.id,
                                                  CheckinVoluntariado.data_hora_fim.isnot(None)).all():
            mes = c.data_hora_inicio.strftime('%Y-%m')
            por_mes[mes] = por_mes.get(mes, 0) + (c.total_minutos or 0)
        fontes['voluntariado_mes'] = simples(tt('Minhas horas de voluntariado por mês', idioma),
                                             [(f"{m[5:]}/{m[:4]}", round(v / 60, 1)) for m, v in sorted(por_mes.items())], tt('Horas', idioma))
    return fontes


def graficos_padrao_painel():
    """Os dois gráficos originais do painel (é o que os agentes de teste conferem)."""
    return [{'fonte': 'evolucao', 'tipo': 'misto', 'cor': CORES_PADRAO_PAINEL[0]},
            {'fonte': 'habilidades', 'tipo': 'radar', 'cor': CORES_PADRAO_PAINEL[1]}]


def validar_graficos_painel(lista, fontes):
    """Mantém só configurações válidas para o perfil (fonte disponível, tipo permitido e cor #RRGGBB)."""
    validos = []
    for item in (lista or [])[:MAX_GRAFICOS_PAINEL]:
        if not isinstance(item, dict) or item.get('fonte') not in fontes:
            continue
        tipos = TIPOS_GRAFICO_MULTI if fontes[item['fonte']]['multi'] else TIPOS_GRAFICO_SIMPLES
        tipo = item.get('tipo') if item.get('tipo') in tipos else tipos[0]
        cor = item.get('cor') if re.fullmatch(r'#[0-9a-fA-F]{6}', str(item.get('cor') or '')) else CORES_PADRAO_PAINEL[len(validos) % 4]
        validos.append({'fonte': item['fonte'], 'tipo': tipo, 'cor': cor})
    return validos


def graficos_do_usuario(usuario, fontes):
    try:
        salvos = json.loads(usuario.preferencias_painel or 'null')
    except ValueError:
        salvos = None
    return validar_graficos_painel(salvos, fontes) or graficos_padrao_painel()


@app.route('/painel/graficos', methods=['POST'])
@login_required
def salvar_graficos_painel():
    """Grava (ou restaura) os gráficos escolhidos pelo utilizador no Painel Geral."""
    corpo = request.get_json(silent=True) or {}
    if corpo.get('restaurar'):
        current_user.preferencias_painel = None
        db.session.commit()
        return jsonify({'ok': True, 'graficos': graficos_padrao_painel()})
    fontes = {chave: {'multi': chave == 'evolucao'} for chave in
              ['evolucao', 'habilidades', 'status_cursos', 'saude_cursos', 'certificacao', 'carga_por_tipo', 'projetos',
               'progresso_por_curso' if current_user.tipo_usuario == 'Aluno' else 'progresso_por_aluno']}
    if current_user.tipo_usuario != 'Aluno':
        fontes['voluntariado_mes'] = {'multi': False}
    graficos = validar_graficos_painel(corpo.get('graficos'), fontes)
    if not graficos:
        return jsonify({'ok': False, 'erro': tt('Escolha pelo menos um gráfico válido.', current_user.idioma)}), 400
    current_user.preferencias_painel = json.dumps(graficos)
    db.session.commit()
    return jsonify({'ok': True, 'graficos': graficos})


# ==============================================================================
# ADMINISTRAÇÃO › PERFIS DE ACESSO (perfis personalizados) e GOVERNANÇA DE APRENDIZADOS
# ==============================================================================
@app.before_request
def restringir_perfil_personalizado():
    """Perfil personalizado: o módulo desligado some do menu e a rota também é barrada."""
    if current_user.is_authenticated and getattr(current_user, 'perfil_personalizado_id', None) and request.endpoint:
        if perfis_acesso.endpoint_bloqueado(current_user, request.endpoint):
            flash(tt('Acesso negado: o seu perfil não inclui este módulo.', current_user.idioma), 'danger')
            return redirect(url_for('dashboard'))


@app.context_processor
def injetar_perfis_acesso():
    if current_user.is_authenticated:
        return {'pode_modulo': lambda chave: perfis_acesso.modulo_liberado(current_user, chave),
                'nome_perfil_usuario': perfis_acesso.nome_do_perfil(current_user)}
    return {'pode_modulo': lambda chave: True, 'nome_perfil_usuario': ''}


def perfis_personalizados_ativos():
    from models import PerfilPersonalizado
    return PerfilPersonalizado.query.filter_by(ativo=True).order_by(PerfilPersonalizado.nome).all()


app.jinja_env.globals.update(perfis_personalizados_ativos=perfis_personalizados_ativos)


def aprender_mudancas(origem):
    """O Agente Gerente Técnico e o Gerente de Segurança percebem a mudança na hora e distribuem os aprendizados."""
    criados = []
    try:
        import conhecimento
        criados += conhecimento.detectar_mudancas(origem)
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Detecção de aprendizados falhou: {e}")
    try:
        import conhecimento_seguranca
        criados += conhecimento_seguranca.detectar_mudancas(origem)
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Detecção de aprendizados de segurança falhou: {e}")
    try:
        import conhecimento_banco
        criados += conhecimento_banco.detectar_mudancas(origem)
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Detecção de aprendizados de banco de dados falhou: {e}")
    try:
        import conhecimento_funcional
        criados += conhecimento_funcional.detectar_mudancas(origem)
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Detecção de aprendizados funcionais falhou: {e}")
    return criados


def _somente_admin_perfis():
    if current_user.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    return None


# ==============================================================================
# PARÂMETROS DAS REGRAS DE NEGÓCIO (frequência do MEC, notas, banca, senhas e regras novas)
# ==============================================================================
@app.route('/admin/parametros-regras', methods=['GET', 'POST'])
@login_required
def parametros_regras():
    import regras_negocio as rn
    bloqueio = _somente_admin_perfis()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    if request.method == 'POST':
        motivo = (request.form.get('motivo') or '').strip()
        if request.form.get('restaurar'):
            chave = request.form['restaurar']
            if rn.restaurar(chave, current_user.id, motivo or 'Voltou ao padrão'):
                flash(tt('Regra "{nome}" voltou ao valor padrão.', idioma).format(nome=tt(rn.nome_da_regra(chave), idioma)), 'success')
        elif request.form.get('excluir'):
            chave = request.form['excluir']
            nome = rn.nome_da_regra(chave)
            if rn.excluir(chave, current_user.id, motivo):
                flash(tt('Regra "{nome}" excluída.', idioma).format(nome=nome), 'success')
        elif request.form.get('acao') == 'criar':
            erro = rn.criar(request.form.get('nova_chave'), request.form.get('nova_nome'), request.form.get('nova_tipo'),
                            request.form.get('nova_valor'), request.form.get('nova_descricao'), current_user.id)
            if erro:
                flash(tt(erro, idioma), 'warning')
            else:
                flash(tt('Regra nova criada. O sistema já pode usá-la em novas funcionalidades.', idioma), 'success')
        else:
            valores = {k[6:]: v for k, v in request.form.items() if k.startswith('valor_')}
            alteradas, erros = rn.salvar_varios(valores, current_user.id, motivo)
            if erros:
                for chave, erro in erros.items():
                    flash(f"{tt(rn.nome_da_regra(chave), idioma)}: {tt(erro, idioma)}", 'warning')
                flash(tt('Nada foi gravado. Corrija os valores indicados.', idioma), 'danger')
            elif alteradas:
                flash(tt('{n} regra(s) atualizada(s). Passam a valer a partir de agora.', idioma).format(n=len(alteradas)), 'success')
            else:
                flash(tt('Nenhum valor foi alterado.', idioma), 'info')
        return redirect(url_for('parametros_regras'))

    from models import HistoricoParametro
    return render_template('parametros_regras.html', itens=rn.listar(), grupos=rn.GRUPOS, tipos=rn.TIPOS, historico=rn.historico(),
                           nome_da_regra=rn.nome_da_regra, total_historico=HistoricoParametro.query.count())


@app.route('/admin/perfis', methods=['GET', 'POST'])
@login_required
def perfis_acesso_view():
    """Tela de parâmetros: criar, editar, desativar e excluir perfis personalizados."""
    from models import PerfilPersonalizado, HistoricoPerfilAcesso
    bloqueio = _somente_admin_perfis()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma

    def registrar_historico(perfil_id, acao, detalhes):
        db.session.add(HistoricoPerfilAcesso(perfil_id=perfil_id, acao=acao, detalhes=detalhes, usuario_id=current_user.id, data=datetime.now()))

    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'salvar':
            perfil_id = request.form.get('perfil_id', type=int)
            nome = ' '.join((request.form.get('nome') or '').split())[:80]
            base = request.form.get('perfil_base')
            if not nome or base not in perfis_acesso.PERFIS_BASE:
                flash(tt('Informe o nome do perfil e escolha um perfil-base.', idioma), 'warning')
                return redirect(url_for('perfis_acesso_view'))
            if nome in perfis_acesso.PERFIS_BASE:
                flash(tt('Este nome já é de um perfil do sistema. Escolha outro nome.', idioma), 'warning')
                return redirect(url_for('perfis_acesso_view'))
            existente = PerfilPersonalizado.query.filter(db.func.lower(PerfilPersonalizado.nome) == nome.lower()).first()
            if existente and existente.id != perfil_id:
                flash(tt('Já existe um perfil com este nome.', idioma), 'warning')
                return redirect(url_for('perfis_acesso_view'))
            perfil = db.session.get(PerfilPersonalizado, perfil_id) if perfil_id else None
            antes = perfis_acesso.descrever(perfil) if perfil else None
            if not perfil:
                perfil = PerfilPersonalizado(criado_por_id=current_user.id, data_criacao=datetime.now())
                db.session.add(perfil)
            base_mudou = perfil.perfil_base and perfil.perfil_base != base
            modulos = perfis_acesso.modulos_validos(base, request.form.getlist('modulos'))
            if base == 'Avaliador Banca' and 'bancas' not in modulos:
                modulos.append('bancas')   # a página inicial do avaliador é Minhas bancas
            perfil.nome, perfil.perfil_base = nome, base
            perfil.descricao = (request.form.get('descricao') or '').strip()[:500]
            perfil.modulos = json.dumps(modulos)
            perfil.ativo = bool(request.form.get('ativo'))
            perfil.atualizado_em = datetime.now()
            db.session.flush()
            if base_mudou:
                # Quem já usa o perfil passa a ter o novo perfil-base (é ele que as telas conferem)
                Usuario.query.filter_by(perfil_personalizado_id=perfil.id).update({'tipo_usuario': base})
            registrar_historico(perfil.id, 'Editado' if antes else 'Criado', f"De: {antes} | Para: {perfis_acesso.descrever(perfil)}" if antes else perfis_acesso.descrever(perfil))
            db.session.commit()
            aprendidos = aprender_mudancas('Perfis de acesso')
            flash(tt('Perfil salvo.', idioma) + (' ' + tt('O Agente Gerente Técnico aprendeu a mudança: {codigos}', idioma).format(
                codigos=', '.join(a.codigo for a in aprendidos)) if aprendidos else ''), 'success')
        elif acao == 'excluir':
            perfil = db.session.get(PerfilPersonalizado, request.form.get('perfil_id', type=int))
            if perfil:
                usuarios = Usuario.query.filter_by(perfil_personalizado_id=perfil.id).all()
                for u in usuarios:
                    u.perfil_personalizado_id = None   # voltam ao perfil-base
                registrar_historico(perfil.id, 'Excluído', f"{perfis_acesso.descrever(perfil)}; {len(usuarios)} usuário(s) voltaram ao perfil {perfil.perfil_base}")
                db.session.delete(perfil)
                db.session.commit()
                aprender_mudancas('Perfis de acesso')
                flash(tt('Perfil excluído. Os usuários dele voltaram ao perfil-base.', idioma), 'info')
        return redirect(url_for('perfis_acesso_view'))

    perfis = PerfilPersonalizado.query.order_by(PerfilPersonalizado.nome).all()
    contagem = {p.id: Usuario.query.filter_by(perfil_personalizado_id=p.id).count() for p in perfis}
    usuarios_base = {b: Usuario.query.filter(Usuario.tipo_usuario == b, Usuario.perfil_personalizado_id.is_(None)).count() for b in perfis_acesso.PERFIS_BASE}
    historico = HistoricoPerfilAcesso.query.order_by(HistoricoPerfilAcesso.data.desc()).limit(100).all()
    return render_template('perfis_acesso.html', perfis=perfis, contagem=contagem, usuarios_base=usuarios_base, historico=historico,
                           modulos=perfis_acesso.MODULOS, modulos_por_base=perfis_acesso.MODULOS_POR_BASE, perfis_base=perfis_acesso.PERFIS_BASE)


@app.route('/admin/agentes-ia/aprendizados', methods=['GET', 'POST'])
@login_required
def governanca_aprendizados():
    """Governança dos aprendizados dos agentes: revisão, revogação, fontes confiáveis e limpeza para compliance."""
    import conhecimento
    from models import AprendizadoAgente, EventoAprendizado, FonteConfiavel, EstadoConhecimento
    bloqueio = _somente_admin_perfis()
    if bloqueio:
        return bloqueio
    idioma = current_user.idioma
    conhecimento.garantir_fontes_padrao()

    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao in ('aprovar', 'rejeitar', 'revogar', 'reaplicar'):
            item = AprendizadoAgente.query.filter_by(codigo=request.form.get('codigo')).first()
            if item and conhecimento.revisar(item, acao, current_user.id, (request.form.get('motivo') or '').strip()[:500]):
                flash(tt('Aprendizado atualizado: {codigo}', idioma).format(codigo=item.codigo), 'success')
        elif acao == 'detectar':
            novos = aprender_mudancas(f"Solicitado por {current_user.nome}")
            flash(tt('Detecção concluída: {n} aprendizado(s) novo(s).', idioma).format(n=len(novos)), 'info')
        elif acao == 'buscar':
            try:
                item = conhecimento.buscar_fonte_oficial((request.form.get('url') or '').strip(), (request.form.get('tema') or '').strip()[:120], current_user.id)
                flash(tt('Referência lida e enviada para aprovação: {codigo}', idioma).format(codigo=item.codigo), 'success')
            except Exception as e:
                db.session.rollback()
                flash(tt('Busca recusada: {erro}', idioma).format(erro=e), 'danger')
        elif acao == 'fonte_incluir':
            dominio = (request.form.get('dominio') or '').strip().lower().removeprefix('https://').removeprefix('http://').split('/')[0]
            if re.fullmatch(r'([a-z0-9-]+\.)+[a-z]{2,}', dominio) and not FonteConfiavel.query.filter_by(dominio=dominio).first():
                db.session.add(FonteConfiavel(dominio=dominio, descricao=(request.form.get('descricao') or '').strip()[:200], ativa=True,
                                              criado_por_id=current_user.id))
                conhecimento.evento('Fonte incluída', dominio, usuario_id=current_user.id)
                db.session.commit()
                flash(tt('Fonte confiável incluída.', idioma), 'success')
            else:
                flash(tt('Informe um domínio válido que ainda não esteja na lista (ex.: docs.python.org).', idioma), 'warning')
        elif acao in ('fonte_ativar', 'fonte_desativar', 'fonte_remover'):
            fonte = db.session.get(FonteConfiavel, request.form.get('fonte_id', type=int))
            if fonte:
                if acao == 'fonte_remover':
                    db.session.delete(fonte)
                else:
                    fonte.ativa = acao == 'fonte_ativar'
                conhecimento.evento({'fonte_ativar': 'Fonte ativada', 'fonte_desativar': 'Fonte desativada', 'fonte_remover': 'Fonte removida'}[acao],
                                    fonte.dominio, usuario_id=current_user.id)
                db.session.commit()
        elif acao == 'limpar':
            if (request.form.get('confirmacao') or '').strip().upper() != 'LIMPAR':
                flash(tt('Para limpar, digite LIMPAR no campo de confirmação.', idioma), 'warning')
                return redirect(url_for('governanca_aprendizados'))
            escopo = request.form.get('escopo', 'revogados')
            consulta = AprendizadoAgente.query
            if escopo == 'revogados':
                consulta = consulta.filter(AprendizadoAgente.status.in_(['Revogado', 'Rejeitado']))
            elif escopo.startswith('agente:'):
                agente = escopo[7:]
                consulta = consulta.filter(AprendizadoAgente.agentes_destino.like(f'%"{agente}"%'))
            elif escopo == 'antigos':
                limite = request.form.get('ate')
                try:
                    consulta = consulta.filter(AprendizadoAgente.criado_em <= datetime.strptime(limite + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
                except (TypeError, ValueError):
                    flash(tt('Informe a data limite da limpeza.', idioma), 'warning')
                    return redirect(url_for('governanca_aprendizados'))
            elif escopo != 'todos':
                return redirect(url_for('governanca_aprendizados'))
            total, arquivo = conhecimento.limpar(consulta.all(), current_user.id, current_user.nome, escopo)
            if escopo == 'todos':
                # Recomeça do zero: o próximo retrato vira a nova linha de base (dos dois gerentes)
                EstadoConhecimento.query.filter(EstadoConhecimento.chave.in_(['retrato', 'retrato_seguranca', 'retrato_banco', 'retrato_funcional'])).delete(synchronize_session=False)
                db.session.commit()
            flash(tt('{n} aprendizado(s) removido(s). Cópia de auditoria: {arquivo}', idioma).format(n=total, arquivo=arquivo or '—'), 'success')
        return redirect(url_for('governanca_aprendizados'))

    filtro_status, filtro_tipo, filtro_agente = request.args.get('status', ''), request.args.get('tipo', ''), request.args.get('agente', '')
    consulta = AprendizadoAgente.query
    if filtro_status:
        consulta = consulta.filter_by(status=filtro_status)
    if filtro_tipo:
        consulta = consulta.filter_by(tipo=filtro_tipo)
    if filtro_agente == 'seguranca':
        # Grupo de segurança: aprendizados do grupo e de cada um dos 5 agentes de segurança (seg_*)
        consulta = consulta.filter(AprendizadoAgente.agentes_destino.like('%"seg%') | AprendizadoAgente.agentes_destino.like('%"todos"%'))
    elif filtro_agente == 'funcionalidades':
        # Grupo funcional: aprendizados do grupo e de cada agente de perfil do fluxo (fn_*)
        consulta = consulta.filter(AprendizadoAgente.agentes_destino.like('%"fn_%') | AprendizadoAgente.agentes_destino.like('%"funcionalidades"%')
                                   | AprendizadoAgente.agentes_destino.like('%"todos"%'))
    elif filtro_agente == 'banco':
        # Grupo de banco de dados: aprendizados do grupo e de cada um dos 5 agentes de banco (db_*)
        consulta = consulta.filter(AprendizadoAgente.agentes_destino.like('%"db_%') | AprendizadoAgente.agentes_destino.like('%"banco"%')
                                   | AprendizadoAgente.agentes_destino.like('%"todos"%'))
    elif filtro_agente:
        consulta = consulta.filter(AprendizadoAgente.agentes_destino.like(f'%"{filtro_agente}"%') | AprendizadoAgente.agentes_destino.like('%"todos"%'))
    itens = consulta.order_by(AprendizadoAgente.id.desc()).all()
    todos = AprendizadoAgente.query.all()
    resumo = {s: sum(1 for a in todos if a.status == s) for s in ('Aplicado', 'Pendente', 'Revogado', 'Rejeitado')}
    eventos = EventoAprendizado.query.order_by(EventoAprendizado.data.desc()).limit(200).all()
    # Última detecção de CADA gerente (antes só aparecia a do Gerente Técnico), da mais recente para a mais antiga
    deteccoes = []
    for chave, gerente in (('ultima_deteccao', 'Gerente Técnico'), ('ultima_deteccao_seguranca', 'Gerente de Segurança'),
                           ('ultima_deteccao_banco', 'Gerente de Banco de Dados'), ('ultima_deteccao_funcional', 'Gerente de Funcionalidades')):
        registro = db.session.get(EstadoConhecimento, chave)
        try:
            valor = json.loads(registro.valor) if registro and registro.valor else None
        except ValueError:
            valor = None
        if valor and valor.get('em'):
            deteccoes.append({**valor, 'gerente': tt(gerente, idioma)})
    deteccoes.sort(key=lambda d: d['em'], reverse=True)
    return render_template('aprendizados.html', itens=itens, resumo=resumo, eventos=eventos, fontes=FonteConfiavel.query.order_by(FonteConfiavel.dominio).all(),
                           agentes=conhecimento.AGENTES, deteccoes=deteccoes,
                           filtros={'status': filtro_status, 'tipo': filtro_tipo, 'agente': filtro_agente},
                           tipos=sorted({a.tipo for a in todos}), carregar_json=json.loads)


@app.route('/admin/agentes-ia/aprendizados/<tipo>.<formato>')
@login_required
def governanca_aprendizados_csv(tipo, formato):
    """Exportação para auditoria: aprendizados ou eventos, em CSV ou JSON."""
    import io
    import csv as _csv
    import conhecimento
    from flask import Response
    from models import AprendizadoAgente, EventoAprendizado
    bloqueio = _somente_admin_perfis()
    if bloqueio:
        return bloqueio
    carimbo = datetime.now().strftime('%Y%m%d_%H%M')
    if tipo == 'eventos':
        eventos = EventoAprendizado.query.order_by(EventoAprendizado.data).all()
        cabecalho = ['Data/Hora', 'Aprendizado', 'Ação', 'Agente', 'Usuário', 'Detalhes']
        linhas = [[e.data.strftime('%d/%m/%Y %H:%M:%S'), e.aprendizado_codigo or '', e.acao, e.agente or '',
                   e.usuario.nome if e.usuario else '', e.detalhes or ''] for e in eventos]
    else:
        itens = AprendizadoAgente.query.order_by(AprendizadoAgente.id).all()
        if formato == 'json':
            corpo = json.dumps([{'codigo': a.codigo, 'titulo': a.titulo, 'tipo': a.tipo, 'status': a.status,
                                 'destino': json.loads(a.agentes_destino), 'origem': a.origem, 'fonte_url': a.fonte_url,
                                 'conteudo': json.loads(a.conteudo), 'assinatura': a.assinatura,
                                 'criado_em': a.criado_em.isoformat() if a.criado_em else None} for a in itens], ensure_ascii=False, indent=1)
            return Response(corpo, mimetype='application/json',
                            headers={'Content-Disposition': f'attachment; filename=aprendizados_agentes_{carimbo}.json'})
        cabecalho, linhas = conhecimento.linhas_csv(itens)
    saida = io.StringIO()
    escritor = _csv.writer(saida, delimiter=';')
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return Response('﻿' + saida.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={tipo}_agentes_{carimbo}.csv'})


# ==============================================================================
# CONTEÚDO INICIAL DA TRILHA DO TCC (editável depois em Onboarding › Gestão da trilha)
# ==============================================================================
MODULOS_TRILHA_PADRAO = [
    ("O cronograma do TCC: 6 encontros e os marcos de entrega", """
<p>Os encontros são fixos e o tempo dos jovens é curto. A plataforma é o fio condutor entre um encontro e outro: a cada encontro, abre-se o prazo da entrega seguinte.</p>
<table class="table table-sm table-bordered align-middle">
<thead><tr><th>Encontro</th><th>Foco com os mentores</th><th>Entrega na plataforma</th></tr></thead>
<tbody>
<tr><td>1</td><td>Alinhamento inicial e chuva de ideias</td><td>Tema do TCC, justificativa e objetivo geral</td></tr>
<tr><td>2</td><td>Estruturação do esqueleto</td><td>Sumário inicial e primeiras fontes de pesquisa</td></tr>
<tr><td>3</td><td>Revisão do conteúdo inicial</td><td>Introdução e primeiro capítulo de fundamentação</td></tr>
<tr><td>4</td><td>Desenvolvimento e solução</td><td>Rascunho completo da solução / projeto prático</td></tr>
<tr><td>5</td><td>Conclusão e lapidação</td><td>Versão escrita final (PDF) para avaliação prévia</td></tr>
<tr><td>6</td><td>Ensaio geral da apresentação</td><td>Slides da apresentação</td></tr>
<tr><td>Banca</td><td>Apresentação oficial</td><td>Arquivo histórico na biblioteca de TCCs</td></tr>
</tbody></table>"""),
    ("O papel do mentor e a ata de cada encontro", """
<p>Cada grupo conta com 2 a 4 mentores. Para que todos falem a mesma língua, ao final de cada encontro um mentor (ou um jovem relator) registra a ata com:</p>
<ul>
<li><strong>Resumo das deliberações:</strong> o que foi discutido e o denominador comum alcançado;</li>
<li><strong>Fontes recomendadas:</strong> links, livros e artigos sugeridos;</li>
<li><strong>Próximos passos:</strong> tarefas claras, com prazo até o encontro seguinte.</li>
</ul>
<p>Use linguagem simples: muitos termos corporativos não fazem parte do dia a dia dos jovens. Na dúvida, pergunte se ficou claro.</p>"""),
    ("Check-in, check-out e horas extras", """
<p>Todo tempo dedicado ao projeto precisa de <strong>check-in e check-out</strong> na plataforma: encontros oficiais, leitura de TCCs, banca e, principalmente, as <strong>orientações extras</strong> fora do cronograma.</p>
<ul>
<li>Nas atividades extras com o grupo, os <strong>jovens também</strong> fazem check-in e check-out.</li>
<li>Informe sempre o grupo e o motivo do encontro extra.</li>
<li>Esses registros alimentam os indicadores de voluntariado (ESG) e o seu certificado de participação.</li>
</ul>"""),
    ("A banca de avaliação", """
<p>A nota final do TCC segue a fórmula oficial:</p>
<p class="fw-bold">Nota final = média ponderada de Escrito, Apresentação e Visual — pesos e nota de aprovação em Administração › Parâmetros de regras (padrão 40% / 40% / 20%, aprovado a partir de 7,0).</p>
<ul>
<li>Cada avaliador registra suas notas com comentários e justificativas.</li>
<li>As perguntas feitas aos jovens e as respostas deles ficam registradas para feedback.</li>
<li>As notas são divulgadas apenas no final, pela coordenação.</li>
</ul>"""),
    ("LGPD, sigilo e comunicação pela plataforma", """
<p>O voluntário mantém total sigilo sobre dados pessoais, informações escolares, histórico familiar e registros dos jovens, e não os compartilha fora dos canais oficiais (Lei Geral de Proteção de Dados).</p>
<p>É vedado usar ideias, projetos de TCC ou propriedade intelectual dos jovens para fins comerciais próprios ou da empresa sem autorização por escrito da coordenação.</p>
<p><strong>Tudo é registrado na plataforma:</strong> demandas, mudanças e sugestões entram pelo Portal de Demandas, não por WhatsApp ou e-mail.</p>"""),
]


def garantir_modulos_trilha_tcc():
    """Cria os módulos iniciais da trilha só se a tabela estiver vazia."""
    from models import ModuloOnboardingTCC
    if ModuloOnboardingTCC.query.count() == 0:
        for ordem, (titulo, conteudo) in enumerate(MODULOS_TRILHA_PADRAO, 1):
            db.session.add(ModuloOnboardingTCC(ordem=ordem, titulo=titulo, conteudo_html=conteudo.strip(), versao=1, ativo=True))
        db.session.commit()


def migrar_respostas_seguranca():
    """Troca as respostas de segurança gravadas em texto puro pelo hash bcrypt (idempotente)."""
    try:
        alteradas = 0
        for registro in SegurancaUsuario.query.all():
            for campo in ('resposta_1', 'resposta_2', 'resposta_3'):
                valor = getattr(registro, campo) or ''
                if valor and not valor.startswith('$2'):
                    setattr(registro, campo, hash_resposta_seguranca(valor))
                    alteradas += 1
        if alteradas:
            db.session.commit()
            app.logger.info(f"{alteradas} resposta(s) de segurança migrada(s) para hash")
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Migração das respostas de segurança falhou: {e}")


# ===========================================================================
# ATUALIZAÇÃO DO BANCO DE DADOS (Garante que roda no PythonAnywhere)
# ===========================================================================
def atualizar_estrutura_banco():
    """Cria tabelas e colunas novas. Roda ao iniciar e depois de restaurar um backup antigo.

    Versões da estrutura (migrations/, Flask-Migrate):
    - banco já versionado (tem a tabela alembic_version): aplica as migrações pendentes (flask db upgrade) antes de tudo;
    - banco novo ou instalação antiga sem versão: create_all cria o que falta e o banco é marcado na versão atual.
    Os ALTER TABLE abaixo são das instalações SQLite anteriores às migrações e só rodam no SQLite.
    Com vários processos (gunicorn), inicie com --preload para esta rotina rodar uma vez só."""
    from sqlalchemy import text, inspect as inspecionar
    from flask_migrate import upgrade as migrar_para_ultima, stamp as marcar_versao
    versionado = 'alembic_version' in inspecionar(db.engine).get_table_names()
    if versionado and os.environ.get('MIGRAR_AO_INICIAR', '1') == '1':
        migrar_para_ultima()
    db.create_all()
    if not banco_config.eh_sqlite(app.config['SQLALCHEMY_DATABASE_URI']):
        if not versionado:
            marcar_versao()
        _rotinas_de_dados_ao_iniciar()
        return
    colunas_novas = [
        # Perfis personalizados (Administração › Perfis de acesso)
        "ALTER TABLE usuario ADD COLUMN perfil_personalizado_id INTEGER REFERENCES perfil_personalizado(id)",
        # Painel Geral: gráficos personalizados por utilizador
        "ALTER TABLE usuario ADD COLUMN preferencias_painel TEXT",
        "ALTER TABLE mensagem_chat ADD COLUMN custo_usd FLOAT",
        "ALTER TABLE mensagem_chat ADD COLUMN chave_cache VARCHAR(64)",
        # Manutenção (DB): histórico de execuções com arquivo, tamanho, duração e agendamento de origem
        "ALTER TABLE registro_backup ADD COLUMN arquivo VARCHAR(255)",
        "ALTER TABLE registro_backup ADD COLUMN tamanho_bytes INTEGER",
        "ALTER TABLE registro_backup ADD COLUMN duracao_seg FLOAT",
        "ALTER TABLE registro_backup ADD COLUMN agendamento_id INTEGER",
        "ALTER TABLE acompanhamento ADD COLUMN planejamento_estudos TEXT",
        "ALTER TABLE tarefa ADD COLUMN planejamento_tarefa TEXT",
        "ALTER TABLE tarefa ADD COLUMN tempo_total_minutos INTEGER DEFAULT 0",
        "ALTER TABLE acompanhamento ADD COLUMN nota_tecnica FLOAT",
        "ALTER TABLE acompanhamento ADD COLUMN nota_postura FLOAT",
        "ALTER TABLE projeto ADD COLUMN nota_conteudo FLOAT",
        "ALTER TABLE projeto ADD COLUMN nota_apresentacao FLOAT",
        "ALTER TABLE empresa ADD COLUMN contato_sec_nome VARCHAR(150)",
        "ALTER TABLE empresa ADD COLUMN contato_sec_email VARCHAR(150)",
        # Adequações instituição/B2B
        "ALTER TABLE usuario ADD COLUMN modalidade_participacao VARCHAR(20) DEFAULT 'Presencial'",
        "ALTER TABLE usuario ADD COLUMN receber_email BOOLEAN DEFAULT 1",
        "ALTER TABLE checkin_voluntariado ADD COLUMN grupo_id INTEGER REFERENCES grupo(id)",
        "ALTER TABLE checkin_voluntariado ADD COLUMN categoria VARCHAR(20) DEFAULT 'Regular'",
        # Correção idempotente: lançamentos antigos de mentoria extraordinária são horas EXTRAS
        "UPDATE checkin_voluntariado SET categoria = 'Extra' WHERE tipo_atividade LIKE 'Mentoria Extraordin%' AND (categoria IS NULL OR categoria = 'Regular')",
        "ALTER TABLE checkin_voluntariado ADD COLUMN reuniao_id INTEGER REFERENCES reuniao_institucional(id)",
        "ALTER TABLE perfil_avaliador ADD COLUMN nome_completo VARCHAR(200)",
        "ALTER TABLE perfil_avaliador ADD COLUMN telefone VARCHAR(40)",
        "ALTER TABLE perfil_avaliador ADD COLUMN linkedin VARCHAR(300)",
        "ALTER TABLE perfil_avaliador ADD COLUMN curriculo_arquivo VARCHAR(255)",
        "ALTER TABLE projeto ADD COLUMN nota_visual FLOAT",
        "ALTER TABLE projeto ADD COLUMN nota_final FLOAT",
        "ALTER TABLE projeto ADD COLUMN data_avaliacao DATETIME",
        "ALTER TABLE projeto ADD COLUMN notas_publicadas BOOLEAN DEFAULT 0",
        "ALTER TABLE projeto ADD COLUMN data_publicacao_notas DATETIME",
        "ALTER TABLE qa_banca ADD COLUMN banca_id INTEGER REFERENCES banca(id)",
        "ALTER TABLE qa_banca ADD COLUMN ordem INTEGER DEFAULT 0",
        # Segurança: token que invalida a sessão no logout
        "ALTER TABLE usuario ADD COLUMN token_sessao VARCHAR(64)",
        # Reuniões instituição × B2B: convite por e-mail
        "ALTER TABLE reuniao_institucional ADD COLUMN convite_sequencia INTEGER DEFAULT 0",
        "ALTER TABLE reuniao_institucional ADD COLUMN convite_enviado_em DATETIME",
        "ALTER TABLE reuniao_institucional ADD COLUMN convite_enviado_via VARCHAR(20)",
        "ALTER TABLE reuniao_institucional ADD COLUMN convite_destinatarios TEXT",
        "ALTER TABLE reuniao_institucional ADD COLUMN empresa_id INTEGER REFERENCES empresa(id)",
        "ALTER TABLE empresa ADD COLUMN logo_arquivo VARCHAR(255)",
        "ALTER TABLE reuniao_institucional ADD COLUMN tipo VARCHAR(30)",
        "ALTER TABLE reuniao_institucional ADD COLUMN pontos_parceiro TEXT",
        "ALTER TABLE reuniao_institucional ADD COLUMN link_gravacao VARCHAR(500)",
        "ALTER TABLE reuniao_institucional ADD COLUMN controle_presenca BOOLEAN",
        "ALTER TABLE usuario ADD COLUMN ultimo_acesso DATETIME",
        "ALTER TABLE desistencia ADD COLUMN substituto_id INTEGER REFERENCES usuario(id)",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_resumo TEXT",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_fontes TEXT",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_plano_acao TEXT",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_proximo_encontro DATE",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_registrada_em DATETIME",
        "ALTER TABLE sessao_mentoria ADD COLUMN ata_registrada_por_id INTEGER REFERENCES usuario(id)",
        "ALTER TABLE sessao_mentoria ADD COLUMN proximos_passos_enviados_em DATETIME",
        "ALTER TABLE reuniao_institucional ADD COLUMN outlook_evento_id VARCHAR(300)",
        "ALTER TABLE reuniao_institucional ADD COLUMN outlook_organizador_id INTEGER REFERENCES usuario(id)",
        # Reunião: arquivo da gravação enviado à plataforma
        "ALTER TABLE reuniao_institucional ADD COLUMN gravacao_arquivo VARCHAR(255)",
        "ALTER TABLE reuniao_institucional ADD COLUMN gravacao_nome VARCHAR(255)",
        "ALTER TABLE reuniao_institucional ADD COLUMN gravacao_tamanho BIGINT",
        "ALTER TABLE reuniao_institucional ADD COLUMN gravacao_enviada_em DATETIME"
    ]
    
    for comando in colunas_novas:
        try:
            db.session.execute(text(comando))
            db.session.commit()
        except Exception:
            db.session.rollback()
    if not versionado:
        marcar_versao()
    _rotinas_de_dados_ao_iniciar()


def _rotinas_de_dados_ao_iniciar():
    """Ajustes de dados idempotentes que valem para qualquer banco."""
    from sqlalchemy import text
    try:  # avaliação 360°: a chave antiga com o nome do cliente vira a chave neutra
        db.session.execute(text("UPDATE resposta_avaliacao SET alvo_tipo = 'Gestão {apelido}' WHERE alvo_tipo = 'Gestão ITM'"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    migrar_respostas_seguranca()
    garantir_modulos_trilha_tcc()
    import backup_servico
    backup_servico.migrar_agendamentos_antigos()
    try:
        import conhecimento
        conhecimento.garantir_fontes_padrao()
    except Exception:
        db.session.rollback()


if os.environ.get('PULAR_ATUALIZACAO_BANCO') != '1':  # 1 = só para gerar migrações (flask db migrate) num banco vazio
    with app.app_context():
        atualizar_estrutura_banco()

# ===========================================================================
# EXECUÇÃO DO APLICATIVO
# ===========================================================================
# As regras nomeadas de perfis chegam a todas as telas pelo mesmo nome (ex.: current_user.tipo_usuario in PERFIS_GESTAO_DEMANDAS)
app.jinja_env.globals.update({_nome: _valor for _nome, _valor in list(globals().items()) if _nome.startswith('PERFIS_')})


def _versao_tema():
    """Muda quando o tema muda (data dos arquivos): o navegador baixa o CSS novo em vez de usar o guardado."""
    pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'css')
    try:
        return int(max(os.path.getmtime(os.path.join(pasta, nome)) for nome in ('tokens.css', 'tema.css')))
    except OSError:
        return 0


app.jinja_env.globals['versao_tema'] = _versao_tema()


if __name__ == '__main__':
    # Liga a tarefa de backup automático em segundo plano
    iniciar_agendador(app)
    # O servidor de desenvolvimento não anuncia versões do Werkzeug/Python no cabeçalho Server
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.server_version, WSGIRequestHandler.sys_version = 'Mentoria', ''
    # Depurador interativo só se pedido (FLASK_DEBUG=1) e nunca exposto fora do computador
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
