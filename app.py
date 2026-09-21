# Importações para Upload de Arquivos e Datas
import os
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename


# Importações do Flask
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, session

# Importações do Google Calendar
from google_auth_oauthlib.flow import Flow
import os
import httplib2
import socks
import google_auth_httplib2

import google.oauth2.credentials
from googleapiclient.discovery import build
import datetime

import google.generativeai as genai

# Configuração da Inteligência Artificial
# Substitua o texto abaixo pela chave enorme que você copiou no Passo 1
import os

from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'), transport='rest')

# Isso permite testarmos o login do Google no nosso computador (localhost) sem HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Dizemos ao Google que só queremos criar/ver eventos na agenda
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Thread (Tarefa em Segundo Plano)
import threading
import shutil
import time

# Importações de Segurança e Login (Aqui está o LoginManager que faltava!)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# Importações do Banco de Dados
from models import db, Usuario, Curso, Acompanhamento, SessaoMentoria, FeedbackSessao, QADuvida, HistoricoProgresso, aluno_mentor, HistoricoSenha, SegurancaUsuario, SolicitacaoMentoria, RegistroBackup, Projeto, Tarefa, Grupo, grupo_usuario
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

# ---------------------------------------------------------
# INJETOR DE TRADUÇÃO PARA OS TEMPLATES (HTML)
# Torna a função 't' disponível globalmente em todas as páginas
# ---------------------------------------------------------
@app.context_processor
def utility_processor():
    def inject_traducao():
        # Verifica se o usuário está logado e pega o idioma dele, senão usa português ('pt')
        idioma_atual = current_user.idioma if current_user.is_authenticated else 'pt'
        return {'t': lambda chave: t(chave, idioma_atual)}
    return inject_traducao()

# =========================================================================
# PROCESSADOR DE CONTEXTO GLOBAL PARA AS NOTIFICAÇÕES DO SINO (Q&A + FEEDBACK)
# =========================================================================
@app.context_processor
def injetar_notificacoes_qa():
    if not current_user.is_authenticated:
        return dict(novas_mensagens_count=0, notificacoes_qa=[])
    
    notificacoes_formatadas = []
    
    # --- 1. BUSCA NOTIFICAÇÕES DE Q&A (ACOMPANHAMENTO) ---
    if current_user.tipo_usuario == 'Aluno':
        notifs_qa = QADuvida.query.join(Acompanhamento).filter(
            QADuvida.lida_pelo_aluno == False,
            Acompanhamento.aluno_id == current_user.id
        ).all()
    else:
        notifs_qa = QADuvida.query.filter_by(lida_pelo_mentor=False).all()
        
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
    if current_user.tipo_usuario == 'Aluno':
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
        if current_user.tipo_usuario != 'Aluno':
            if current_user.tipo_usuario in ['Administrador', 'Mentor Administrador']:
                alunos_bloqueados = Usuario.query.filter_by(status='Bloqueado').all()
            else:
                alunos_bloqueados = Usuario.query.filter(Usuario.status == 'Bloqueado', Usuario.mentores.any(id=current_user.id)).all()
            
            for ab in alunos_bloqueados:
                notificacoes_formatadas.append({
                    'link': url_for('gerenciar_usuarios'),
                    'texto': f"⚠️ BLOQUEADO (Senha): {ab.nome.split()[0]}",
                    'data': datetime.now() # Data atual para forçar o aviso a ficar no topo do sino
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
app.config['SECRET_KEY'] = 'chave_super_secreta_projeto_mentoria_2026' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mentoria.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ===========================================================================
# INICIALIZANDO AS EXTENSÕES
# ===========================================================================
db.init_app(app)          
bcrypt = Bcrypt(app)      
login_manager = LoginManager(app) 

login_manager.login_view = 'login' 
login_manager.login_message = "Por favor, faça login para acessar esta página."

# ===========================================================================
# FUNÇÃO DE CARREGAMENTO DE USUÁRIO
# ===========================================================================
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

# ===========================================================================
# ROTAS (PÁGINAS DO SISTEMA)
# ===========================================================================

# Rota de Login (Página Inicial)
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

        if usuario:
            # Trava o usuário se ele estiver bloqueado pelas 5 tentativas
            if usuario.status == 'Bloqueado':
                flash('Sua conta foi bloqueada por excesso de tentativas falhas. Procure a Administração.', 'danger')
                return render_template('index.html')

            # Se a senha estiver correta
            if bcrypt.check_password_hash(usuario.senha, senha_digitada):
                # Zera as falhas e loga o usuário
                usuario.tentativas_login = 0
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
                if usuario.tentativas_login >= 5:
                    usuario.status = 'Bloqueado'
                    flash('Conta bloqueada após 5 tentativas incorretas.', 'danger')
                else:
                    flash(f'E-mail ou senha incorretos. Tentativa {usuario.tentativas_login} de 5.', 'warning')
                
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
        padrao_senha = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{10,}$'
        
        if not re.match(padrao_senha, nova_senha):
            flash("Segurança: A nova senha deve ter no mínimo 10 caracteres (maiúsculas, minúsculas, números e especiais).", "danger")
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

@app.route('/dashboard')
@login_required
def dashboard():
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

    DIAS_EXPIRACAO_SENHA = 90
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
    elif current_user.tipo_usuario == 'Mentor':
        # Filtra os acompanhamentos e totalizadores apenas para os alunos deste mentor
        acompanhamentos = Acompanhamento.query.join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(Usuario.mentores.any(id=current_user.id)).all()
        total_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).count()
        total_sessoes = SessaoMentoria.query.filter_by(mentor_id=current_user.id).count()
    else:
        # Administrador e Mentor Administrador veem tudo
        acompanhamentos = Acompanhamento.query.all()
        total_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').count()
        total_sessoes = SessaoMentoria.query.count()

    total_alunos_sistema = total_alunos
    total_matriculas = len(acompanhamentos)

    dict_evolucao = {}
    dict_radar = {}

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

        data_base = getattr(a, 'data_inicio', None) or getattr(a, 'data_criacao', None) or datetime.utcnow()
        mes_ano = data_base.strftime('%m/%Y')
        if mes_ano not in dict_evolucao:
            dict_evolucao[mes_ano] = {'horas': 0, 'cursos_finalizados': 0}
        
        dict_evolucao[mes_ano]['horas'] += (curso.carga_horaria or 0)
        if a.status == 'Finalizado':
            dict_evolucao[mes_ano]['cursos_finalizados'] += 1

        tipo_curso = getattr(curso, 'tipo', 'Outro')
        if tipo_curso not in dict_radar:
            dict_radar[tipo_curso] = {'soma_progresso': 0, 'qtd': 0}
        
        dict_radar[tipo_curso]['soma_progresso'] += percentual
        dict_radar[tipo_curso]['qtd'] += 1

    try:
        meses_ordenados = sorted(dict_evolucao.keys(), key=lambda x: datetime.strptime(x, '%m/%Y'))
    except:
        meses_ordenados = list(dict_evolucao.keys())

    for mes in meses_ordenados:
        evolucao_labels.append(mes)
        evolucao_horas.append(dict_evolucao[mes]['horas'])
        evolucao_cursos.append(dict_evolucao[mes]['cursos_finalizados'])

    for tipo, dados in dict_radar.items():
        radar_labels.append(tipo)
        media = round(dados['soma_progresso'] / dados['qtd'], 1) if dados['qtd'] > 0 else 0
        radar_valores.append(media)

    # ==============================================================================
    # INDICADORES DE PROJETOS PARA O DASHBOARD
    # ==============================================================================
    if current_user.tipo_usuario in ['Aluno', 'Mentor']:
        meus_projetos = Projeto.query.join(Grupo).filter(Grupo.membros.any(id=current_user.id)).all()
    else:
        meus_projetos = Projeto.query.all()

    total_projetos = len(meus_projetos)
    projetos_andamento = sum(1 for p in meus_projetos if p.status == 'Em Andamento')
    projetos_concluidos = sum(1 for p in meus_projetos if p.status == 'Concluído')

    return render_template('dashboard.html', 
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
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
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
    lista_grupos = Grupo.query.all()
    # Busca usuários ativos para montar a lista de seleção
    usuarios_disponiveis = Usuario.query.filter_by(status='Ativo').all()

    return render_template('admin_grupos.html', grupos=lista_grupos, usuarios=usuarios_disponiveis)


# ---------------------------------------------------------
# Rota de Cadastro de Usuários (AGORA COM MÚLTIPLOS MENTORES)
# ---------------------------------------------------------
@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
def gerenciar_usuarios():
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
        return "<h1>Acesso Negado</h1>"
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email').strip()
        tipo_usuario = request.form.get('tipo_usuario')
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
            
        padrao_senha = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{10,}$'
        if not re.match(padrao_senha, senha_plana):
            flash("Segurança: A senha deve ter no mínimo 10 caracteres e incluir letras maiúsculas, minúsculas, números e caracteres especiais.", "danger")
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
            forcar_troca_senha=forcar_troca
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
    
    lista_usuarios = Usuario.query.all()
    lista_mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Mentor', 'Mentor Administrador'])).all()

    # Busca todos os dados para montar a tela de Cadastros
    usuarios = Usuario.query.all()
    mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Mentor', 'Mentor Administrador'])).all()
    solicitacoes = SolicitacaoMentoria.query.order_by(SolicitacaoMentoria.data_solicitacao.desc()).all()

    # Puxa os dados da URL caso o admin tenha clicado em "Aprovar"
    fill_nome = request.args.get('fill_nome', '')
    fill_email = request.args.get('fill_email', '')

    return render_template('admin_usuarios.html', usuarios=usuarios, mentores=mentores, solicitacoes=solicitacoes, fill_nome=fill_nome, fill_email=fill_email)
    
# ---------------------------------------------------------
# Rota de Edição de Usuários (AGORA COM MÚLTIPLOS MENTORES)
# ---------------------------------------------------------
@app.route('/admin/usuarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_usuario(id):
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
        return "Acesso Negado"
    
    usuario = db.session.get(Usuario, id)
    if usuario:
        novo_email = request.form.get('email').strip()
        padrao_email = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        
        if not re.match(padrao_email, novo_email):
            flash("Erro: Formato de e-mail inválido na edição.", "danger")
            return redirect(url_for('gerenciar_usuarios'))
            
        usuario.nome = request.form.get('nome')
        usuario.email = novo_email
        usuario.tipo_usuario = request.form.get('tipo_usuario')
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
            padrao_senha = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{10,}$'
            if not re.match(padrao_senha, nova_senha):
                flash("Segurança: A nova senha deve ter no mínimo 10 caracteres...", "danger")
                return redirect(url_for('gerenciar_usuarios'))
                
            usuario.senha = bcrypt.generate_password_hash(nova_senha).decode('utf-8')
            usuario.data_ultima_troca_senha = datetime.utcnow()
            
        db.session.commit()
        flash(f"Usuário {usuario.nome} atualizado com sucesso!", "success")
        
    return redirect(url_for('gerenciar_usuarios'))

# ---------------------------------------------------------
# Rota de Gerenciamento de Cursos (Cadastro e Listagem)
# ---------------------------------------------------------
@app.route('/admin/cursos', methods=['GET', 'POST'])
@login_required
def gerenciar_cursos():
    if current_user.tipo_usuario == 'Aluno':
        return "<h1>Acesso Negado</h1><p>Apenas mentores e administradores podem gerenciar cursos.</p>"
    
    if request.method == 'POST':
        nome_curso = request.form.get('nome')
        exige_certificado = request.form.get('exige_certificado')
        url_curso = request.form.get('url')
        plataforma_curso = request.form.get('plataforma')
        carga_horaria = request.form.get('carga_horaria', 20)
        tipo = request.form.get('tipo', 'Hard Skill')
        status = request.form.get('status', 'Ativo')
        
        novo_curso = Curso(
            nome_curso=nome_curso, 
            exige_certificado=exige_certificado,
            url=url_curso,
            plataforma=plataforma_curso,
            carga_horaria=int(carga_horaria),
            tipo=tipo,
            status=status,
            data_inclusao=datetime.now(timezone.utc).replace(tzinfo=None),
            criado_por_id=current_user.id
        )
        db.session.add(novo_curso)
        db.session.commit()
        flash("Curso adicionado com sucesso!", "success")
        return redirect(url_for('gerenciar_cursos'))
        
    cursos_db = Curso.query.all()
    
    lista_cursos = []
    for c in cursos_db:
        criador = db.session.get(Usuario, c.criado_por_id) if c.criado_por_id else None
        nome_criador = criador.nome if criador else 'Sistema / Anônimo'
        lista_cursos.append({'curso': c, 'criado_por': nome_criador})

    return render_template('admin_cursos.html', cursos=lista_cursos)

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
                return redirect(url_for('gerenciar_cursos'))
                
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
        
    return redirect(url_for('gerenciar_cursos'))


app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------------------------------------------
# Rota de Acompanhamento de Estudos
# ---------------------------------------------------------
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
import os

@app.route('/acompanhamento', methods=['GET', 'POST'])
@login_required
def acompanhamento():
    if request.method == 'POST':
        # --- NOVA FUNÇÃO: EXCLUIR MATERIAIS DE APOIO ---
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
                        except Exception as e:
                            pass
                    else:
                        materiais_restantes.append(mat)
                
                registro.material_apoio = '|'.join(materiais_restantes) if materiais_restantes else None
                db.session.commit()
                flash('Os materiais selecionados foram excluídos permanentemente.', 'success')
            return redirect(url_for('acompanhamento'))
        # -----------------------------------------------

        if request.form.get('acao') == 'atualizar_parecer_livre' and current_user.tipo_usuario != 'Aluno':
            acompanhamento_id = request.form.get('acompanhamento_id')
            registro = Acompanhamento.query.get(acompanhamento_id)
            if registro:
                registro.observacao = request.form.get('observacao')
                registro.data_parecer_mentor = datetime.now()
                db.session.commit()
                flash('Parecer oficial do mentor atualizado com sucesso!', 'success')
            return redirect(url_for('acompanhamento'))

        acompanhamento_id = request.form.get('acompanhamento_id')
        if acompanhamento_id:
            if current_user.tipo_usuario == 'Aluno':
                QADuvida.query.filter_by(acompanhamento_id=acompanhamento_id, lida_pelo_aluno=False).update({'lida_pelo_aluno': True})
            else:
                QADuvida.query.filter_by(acompanhamento_id=acompanhamento_id, lida_pelo_mentor=False).update({'lida_pelo_mentor': True})
            db.session.commit()
            
        if request.form.get('acao') == 'atualizar_anotacao_livre':
            acompanhamento_id = request.form.get('acompanhamento_id')
            novo_texto = request.form.get('observacao_aluno')
            registro = Acompanhamento.query.get(acompanhamento_id)
            if registro:
                registro.observacao_aluno = novo_texto
                db.session.commit()
                flash('Anotações atualizadas com sucesso!', 'success')
            return redirect(url_for('acompanhamento'))

        if 'acompanhamento_id' in request.form and request.form.get('acao') != 'vincular':
            acompanhamento_id = request.form.get('acompanhamento_id')
            status = request.form.get('status')
            percentual = int(request.form.get('percentual_conclusao'))
            observacao_aluno = request.form.get('observacao_aluno')
            observacao_mentor = request.form.get('observacao')
            
            data_inicio_str = request.form.get('data_inicio')
            data_termino_str = request.form.get('data_termino')
            
            regstro = db.session.get(Acompanhamento, acompanhamento_id)
            
            if regstro:
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
                    if aluno_obj:
                        aluno_obj.perfil_aluno = request.form.get('perfil_aluno')
                        aluno_obj.objetivo_principal = request.form.get('objetivo_principal')
                        aluno_obj.expectativa_mentoria = request.form.get('expectativa_mentoria')

                curso = db.session.get(Curso, regstro.curso_id)
                arquivo = request.files.get('certificado')
                
                exige_certificado = (curso.exige_certificado == 'Sim')
                tem_arquivo_novo = (arquivo is not None and arquivo.filename != '')
                ja_tem_certificado_salvo = getattr(regstro, 'certificado_anexado', False) or getattr(regstro, 'certificado', False)
                
                if (percentual == 100 or status == 'Finalizado') and exige_certificado and not (ja_tem_certificado_salvo or tem_arquivo_novo):
                    flash("Atenção: Este curso exige certificado para ser finalizado. Faça o upload do arquivo para concluir.", "danger")
                    return redirect(url_for('acompanhamento'))
                
                if status == 'Finalizado' and percentual < 100:
                    flash("Atenção: Você não pode marcar o status como 'Finalizado' sem ter 100% de progresso.", "warning")
                    return redirect(url_for('acompanhamento'))
                
                if percentual == 100:
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
                
                # --- CAPTURAR PROGRESSO DO MENTOR ---
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

                # GATILHO DA AGENDA: Lê a grade dinâmica gerada pelo ecrã e cria slots individuais
                slot_datas = request.form.getlist('slot_data')
                slot_inicios = request.form.getlist('slot_inicio')
                slot_fims = request.form.getlist('slot_fim')
                
                if slot_datas:
                    curso_obj = db.session.get(Curso, regstro.curso_id)
                    planejamento_salvo = [] 
                    
                    for i in range(len(slot_datas)):
                        # Só guarda se o utilizador preencheu as horas (ignorando os campos --:--)
                        if slot_inicios[i] and slot_fims[i]: 
                            # 1. Salva o cartão visual de forma segura (sem depender do módulo datetime)
                            ano, mes, dia = slot_datas[i].split('-')
                            data_br = f"{dia}/{mes}/{ano}"
                            planejamento_salvo.append(f"{data_br}::{slot_inicios[i]}::{slot_fims[i]}")
                            
                            # 2. Tenta enviar para a Google Agenda num processo isolado
                            try:
                                from datetime import datetime as dt_seguro
                                data_slot = dt_seguro.strptime(slot_datas[i], '%Y-%m-%d')
                                
                                sincronizar_evento_google(
                                    titulo=f"Estudo: {curso_obj.nome_curso}",
                                    descricao=f"Sessão focada no curso: {curso_obj.nome_curso}.",
                                    data_inicio=data_slot,
                                    horario_str=slot_inicios[i],
                                    horario_fim_str=slot_fims[i]
                                )
                            except Exception:
                                pass
                                
                    # Grava todos os horários agrupados na coluna da base de dados
                    regstro.planejamento_estudos = "|".join(planejamento_salvo) if planejamento_salvo else None

                db.session.commit()
                flash("Acompanhamento atualizado com sucesso!", "success")

                # Mantém o modal aberto se o botão de planeamento for clicado
                if request.form.get('acao_modal') == 'manter_aberto':
                    return redirect(url_for('acompanhamento', abrir_modal=regstro.id))
                
        else:
            aluno_id = request.form.get('aluno_id')
            curso_id = request.form.get('curso_id')
            
            if not aluno_id or not curso_id:
                flash("Por favor, selecione um aluno e um curso válidos para realizar a matrícula.", "danger")
                return redirect(url_for('acompanhamento'))
            
            curso_selecionado = db.session.get(Curso, int(curso_id))
            if curso_selecionado.status == 'Desativado':
                flash(f"Ação bloqueada: O curso '{curso_selecionado.nome_curso}' está desativado.", "danger")
                return redirect(url_for('acompanhamento'))
            
            existe = Acompanhamento.query.filter_by(aluno_id=int(aluno_id), curso_id=int(curso_id)).first()
            if existe:
                flash("Este aluno já está matriculado neste curso.", "warning")
            else:
                novo = Acompanhamento(
                    aluno_id=int(aluno_id), 
                    curso_id=int(curso_id), 
                    status='Iniciado', 
                    percentual_conclusao=0
                )
                db.session.add(novo)
                db.session.commit()
                flash("Matrícula realizada com sucesso!", "success")
                
        return redirect(url_for('acompanhamento'))

    if current_user.tipo_usuario == 'Aluno':
        registros = Acompanhamento.query.filter_by(aluno_id=current_user.id).all()
    elif current_user.tipo_usuario == 'Mentor':
        registros = Acompanhamento.query.join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(Usuario.mentores.any(id=current_user.id)).all()
    else:
        registros = Acompanhamento.query.all()

    detalhes = []
    for r in registros:
        aluno = db.session.get(Usuario, r.aluno_id)
        curso = db.session.get(Curso, r.curso_id)
        detalhes.append({'reg': r, 'aluno': aluno, 'curso': curso})
        
    if current_user.tipo_usuario == 'Mentor':
        lista_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).all()
    else:
        lista_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').all()
        
    lista_cursos = Curso.query.filter_by(status='Ativo').all()
    
    return render_template('acompanhamento.html', registros=detalhes, alunos=lista_alunos, cursos=lista_cursos)


# ==============================================================================
# ROTA: Gestão de Projetos (Tela principal e Cadastro)
# ==============================================================================
@app.route('/projetos', methods=['GET', 'POST'])
@login_required
def projetos():
    # 1. Se o usuário preencheu o formulário e clicou em "Salvar" (POST)
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        grupo_id = request.form.get('grupo_id') # Recebe o ID do Grupo
        
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

    # 2. Quando a página apenas carrega (GET)
    grupo_filtro = request.args.get('grupo_filtro')
    
    query = Projeto.query
    if grupo_filtro:
        # Se um grupo foi escolhido, filtra apenas os projetos dele
        query = query.filter_by(grupo_id=grupo_filtro)
        
    # Ordena para manter os mais recentes no topo
    lista_projetos = query.order_by(Projeto.id.desc()).all()
    grupos_disponiveis = Grupo.query.all()
    
    return render_template('projetos.html', projetos=lista_projetos, grupos=grupos_disponiveis, grupo_filtro=grupo_filtro)


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
    
    if tarefa:
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
            tarefa.percentual_conclusao = int(request.form.get('percentual_conclusao', 0))
        
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
    perfis_autorizados = ['Mentor', 'Mentor Administrador', 'Administrador']
    
    if current_user.tipo_usuario not in perfis_autorizados:
        flash('Acesso negado: Apenas mentores e administradores podem excluir projetos.', 'danger')
        return redirect(url_for('projetos'))

    projeto = db.session.get(Projeto, id)
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
                sincronizar_evento_google(
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
    elif current_user.tipo_usuario in ['Administrador', 'Mentor Administrador']:
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
        
    if current_user.tipo_usuario == 'Mentor':
        lista_alunos = Usuario.query.filter(Usuario.tipo_usuario == 'Aluno', Usuario.mentores.any(id=current_user.id)).all()
    else:
        lista_alunos = Usuario.query.filter_by(tipo_usuario='Aluno').all()

    return render_template('sessoes.html', sessoes=sessoes_detalhadas, alunos=lista_alunos)

# ==============================================================================
# ROTA: ALUNO SALVAR SESSÃO NA PRÓPRIA AGENDA
# ==============================================================================
@app.route('/sessoes/sincronizar_aluno/<int:id>', methods=['POST'])
@login_required
def sincronizar_sessao_aluno(id):
    if current_user.tipo_usuario != 'Aluno':
        return redirect(url_for('sessoes'))
        
    # Exige que o aluno conecte o Google antes de tentar salvar
    if 'google_token' not in session:
        flash("Você precisa conectar sua conta do Google Agenda primeiro!", "warning")
        return redirect(url_for('conectar_agenda'))
        
    sessao = db.session.get(SessaoMentoria, id)
    if sessao and sessao.aluno_id == current_user.id:
        mentor = db.session.get(Usuario, sessao.mentor_id)
        nome_mentor = mentor.nome if mentor else "Mentor"
        
        # Assume 1 hora de duração a partir do horário de início
        from datetime import timedelta
        data_fim = sessao.data_sessao + timedelta(hours=1)
        
        sucesso = sincronizar_evento_google(
            titulo=f"Mentoria com {nome_mentor}",
            descricao=f"Pauta: {sessao.observacoes}",
            data_inicio=sessao.data_sessao,
            horario_str=sessao.data_sessao.strftime('%H:%M'),
            horario_fim_str=data_fim.strftime('%H:%M')
        )
        
        if sucesso:
            flash("Sessão salva com sucesso na sua Google Agenda!", "success")
        else:
            flash("Erro ao salvar. Tente desconectar e conectar o Google novamente.", "danger")
            
    return redirect(url_for('sessoes'))



# ===========================================================================
# Rota segura para exibir/baixar os certificados e materiais
# ===========================================================================
@app.route('/uploads/<nome_arquivo>')
@login_required
def acessar_upload(nome_arquivo):
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
    
    logout_user()
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
        db.session.delete(curso)
        db.session.commit()
        flash("Curso excluído com sucesso!", "success")
    else:
        flash("Curso não encontrado.", "danger")
        
    return redirect(url_for('gerenciar_cursos'))


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
    
    return redirect(request.referrer or url_for('dashboard'))

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
    
    return redirect(request.referrer or url_for('dashboard'))

# ===========================================================================
# EXECUÇÃO DO APLICATIVO
# ===========================================================================
import os
from datetime import datetime

@app.route('/admin/banco', methods=['GET', 'POST'])
@login_required
def manutencao_banco():
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))

    caminho_banco = os.path.join(app.instance_path, 'mentoria.db')

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        # 1. BACKUP IMEDIATO (Registra a intervenção manual)
        if acao == 'backup':
            if os.path.exists(caminho_banco):
                data_atual = datetime.now().strftime('%m-%d-%Y_%Hh%M')
                nome_arquivo = f"mentory_{data_atual}.db"
                
                # Registra no banco a intervenção manual
                log = RegistroBackup(tipo='Imediato', status='Sucesso', destino='Download Local', 
                                     detalhes='Backup manual gerado pelo admin.', 
                                     usuario_id=current_user.id, data_registro=datetime.now())
                db.session.add(log)
                db.session.commit()
                
                return send_file(caminho_banco, as_attachment=True, download_name=nome_arquivo)
            else:
                flash("Arquivo não encontrado.", "danger")

        # 2. SALVAR AGENDAMENTO
        elif acao == 'agendar':
            frequencia = request.form.get('frequencia', 'Não definida')
            hora = request.form.get('horario', '00:00')
            data_inicio = request.form.get('data_inicio', 'Não definida')
            destino = request.form.get('destino_interno', '').strip() or 'Backup_repository'

            os.makedirs(destino, exist_ok=True)
            
            # Registra no banco o agendamento
            detalhes = f"Frequência: {frequencia}"
            log = RegistroBackup(tipo='Agendado', status='Pendente', destino=destino, 
                                 data_agendada=f"{data_inicio} às {hora}", detalhes=detalhes, 
                                 usuario_id=current_user.id, data_registro=datetime.now())
            db.session.add(log)
            db.session.commit()
            
            flash(f"Configuração salva! Backups a partir de {data_inicio} na pasta: {destino}", "info")

        # 3. RESTAURAR BANCO DE DADOS
        elif acao == 'restaurar':
            arquivo = request.files.get('arquivo_db')
            if arquivo and arquivo.filename != '':
                try:
                    # 1. Fecha as conexões do banco para não dar erro de arquivo em uso
                    db.session.remove()
                    db.engine.dispose()
                    time.sleep(1)
                    
                    # 2. Mira na pasta correta do Flask (instance)
                    caminho_real = os.path.join(app.instance_path, 'mentoria.db')
                    
                    # 3. Salva o arquivo enviado por cima do banco vazio
                    arquivo.save(caminho_real)
                    
                    # 4. EXTREMAMENTE IMPORTANTE: Destruir a "memória fantasma" do apagão
                    caminho_wal = caminho_real + '-wal'
                    caminho_shm = caminho_real + '-shm'
                    if os.path.exists(caminho_wal): os.remove(caminho_wal)
                    if os.path.exists(caminho_shm): os.remove(caminho_shm)
                    
                    # 5. Reconecta ao banco restaurado e salva a auditoria
                    novo_log = RegistroBackup(
                        tipo='Imediato',
                        status='Sucesso',
                        destino='Restaurado (Upload)',
                        detalhes=f"Banco restaurado com sucesso a partir de: {arquivo.filename}.",
                        usuario_id=current_user.id,
                        data_registro=datetime.now()
                    )
                    db.session.add(novo_log)
                    db.session.commit()
                    
                    flash("Backup restaurado com sucesso! Seus dados voltaram.", "success")
                except Exception as e:
                    flash(f"Erro ao restaurar: {str(e)}", "danger")
            else:
                flash("Por favor, selecione um arquivo válido.", "warning")

        # 4. LIMPAR BANCO DE DADOS (ZONA DE PERIGO)
        elif acao == 'limpar':
            try:
                # Exclui as tabelas dependentes primeiro
                QADuvida.query.delete()
                FeedbackSessao.query.delete()
                SessaoMentoria.query.delete()
                HistoricoProgresso.query.delete()
                Acompanhamento.query.delete()
                
                # Exclui histórico e perguntas de segurança (EXCETO do Admin logado)
                HistoricoSenha.query.filter(HistoricoSenha.usuario_id != current_user.id).delete()
                SegurancaUsuario.query.filter(SegurancaUsuario.usuario_id != current_user.id).delete()
                
                # Exclui cursos e solicitações
                Curso.query.delete()
                SolicitacaoMentoria.query.delete()
                
                # Limpa a tabela invisível que liga o Aluno ao Mentor
                db.session.execute(aluno_mentor.delete())
                
                # Exclui todos os usuários (EXCETO o Admin logado)
                Usuario.query.filter(Usuario.id != current_user.id).delete()
                
                # Salva a auditoria obrigatória do apagão
                log_limpeza = RegistroBackup(
                    tipo='Imediato', 
                    status='Sucesso', 
                    destino='Destruição (Wipe)',
                    detalhes='ZONA DE PERIGO: O banco de dados foi completamente limpo. Apenas o administrador logado foi preservado.',
                    usuario_id=current_user.id,
                    data_registro=datetime.now()
                )
                db.session.add(log_limpeza)
                db.session.commit()
                
                flash("Banco de dados destruído com sucesso! Apenas a sua conta sobreviveu.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Erro crítico ao tentar limpar o banco: {str(e)}", "danger")

        # 4. LIMPAR HISTÓRICO DE AUDITORIA (Exclusivo Admin)
        elif acao == 'limpar_auditoria':
            if current_user.tipo_usuario == 'Administrador':
                try:
                    # 1. Apaga todos os registros da tabela no banco de dados
                    db.session.query(RegistroBackup).delete()
                    db.session.commit()
                    
                    # 2. Localiza a pasta Log_auditoria_backup e garante que ela exista
                    pasta_logs = os.path.join(os.getcwd(), 'Log_auditoria_backup')
                    os.makedirs(pasta_logs, exist_ok=True)
                    
                    # 3. Cria o arquivo de log físico com a data e hora
                    nome_arquivo = f"limpeza_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    caminho_arquivo = os.path.join(pasta_logs, nome_arquivo)
                    
                    with open(caminho_arquivo, 'w', encoding='utf-8') as arquivo_log:
                        arquivo_log.write("=== LOG DE SEGURANÇA: LIMPEZA DE AUDITORIA ===\n")
                        arquivo_log.write(f"Data e Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                        arquivo_log.write(f"Autor da Ação: {current_user.nome} (E-mail: {current_user.email})\n")
                        arquivo_log.write("Detalhes: Todo o histórico de auditoria e backups do banco de dados foi permanentemente apagado.\n")
                        arquivo_log.write("=================================================\n")
                        
                    flash("Histórico de auditoria limpo com sucesso! Log físico gerado na pasta Log_auditoria_backup.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Erro ao limpar histórico: {str(e)}", "danger")
            else:
                flash("Acesso Negado: Apenas administradores podem apagar a auditoria.", "danger")



    # ==========================================
    # LÓGICA DE FILTRAGEM PARA EXIBIÇÃO EM TELA
    # ==========================================
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    query = RegistroBackup.query
    
    if data_inicio_filtro:
        dt_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d')
        query = query.filter(RegistroBackup.data_registro >= dt_inicio)
        
    if data_fim_filtro:
        dt_fim = datetime.strptime(data_fim_filtro + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        query = query.filter(RegistroBackup.data_registro <= dt_fim)
        
    logs_backup = query.order_by(RegistroBackup.data_registro.desc()).all()

    return render_template('admin_banco.html', logs_backup=logs_backup, 
                           data_inicio=data_inicio_filtro, data_fim=data_fim_filtro)


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
    
    # 3. Verifica se o e-mail existe no sistema
    if not usuario:
        flash('E-mail não encontrado no sistema.', 'danger')
        return redirect(url_for('login'))

    # 4. Busca as perguntas salvas por este usuário no banco
    seguranca = SegurancaUsuario.query.filter_by(usuario_id=usuario.id).first()
    if not seguranca:
        flash('Este usuário não cadastrou as perguntas. Contate o administrador.', 'warning')
        return redirect(url_for('login'))

    # 5. Verifica se o usuário já preencheu a tela de respostas
    if 'resposta_1' in request.form:
        acertos = 0
        
        # Converte tudo para letras minúsculas e remove espaços vazios para evitar erros de digitação boba
        r1_digitada = request.form.get('resposta_1', '').strip().lower()
        r2_digitada = request.form.get('resposta_2', '').strip().lower()
        r3_digitada = request.form.get('resposta_3', '').strip().lower()

        # Compara com o que está no banco (também minúsculo e sem espaços)
        if r1_digitada == seguranca.resposta_1.strip().lower(): acertos += 1
        if r2_digitada == seguranca.resposta_2.strip().lower(): acertos += 1
        if r3_digitada == seguranca.resposta_3.strip().lower(): acertos += 1

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

        # Salva no banco de dados (convertendo as respostas para minúsculas para não dar erro depois)
        nova_seguranca = SegurancaUsuario(
            usuario_id=current_user.id,
            pergunta_1=p1, resposta_1=r1.strip().lower(),
            pergunta_2=p2, resposta_2=r2.strip().lower(),
            pergunta_3=p3, resposta_3=r3.strip().lower()
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
    nome = request.form.get('nome')
    email = request.form.get('email')
    motivo = request.form.get('motivo')

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
    if current_user.tipo_usuario != 'Mentor Administrador':
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
    if current_user.tipo_usuario != 'Mentor Administrador':
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
    state = session.get('state')
    caminho_secreto = os.path.join(app.root_path, 'client_secret.json')
    
    flow = Flow.from_client_secrets_file(
        caminho_secreto,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # 2. RECUPERAMOS O "CÓDIGO VERIFICADOR" PARA DEVOLVER AO GOOGLE
    flow.code_verifier = session.get('code_verifier')
    
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    credenciais = flow.credentials
    
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
    return redirect(request.referrer or url_for('acompanhamento'))

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
        # Mantendo a versão que estabilizou no seu ambiente
        modelo = genai.GenerativeModel('gemini-3.6-flash')

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

        prompt_final = f"{instrucoes_tutor}\n\nMensagem do usuário: {mensagem_usuario}\nSua resposta:"

        resposta = modelo.generate_content(prompt_final)
        return jsonify({'resposta': resposta.text})

    except Exception as e:
        return jsonify({'resposta': f"Desculpe, encontrei um erro: {str(e)}"}), 500

# =========================================================================
# MOTOR DE BACKUP EM SEGUNDO PLANO (WATCHER)
# =========================================================================
def rotina_de_backups(app_context):
    with app_context:
        while True:
            agora = datetime.now()
            
            # Busca todos os backups pendentes (criados pelo administrador)
            pendentes = RegistroBackup.query.filter_by(status='Pendente', tipo='Agendado').all()
            
            for log in pendentes:
                try:
                    # Lê a data agendada que está em texto no banco (Ex: "2026-08-30 às 14:15")
                    data_hora_str = log.data_agendada.replace(' às ', ' ')
                    data_alvo = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M')
                    
                    # Se a hora atual for igual ou maior que a hora agendada, DISPARA O BACKUP!
                    if agora >= data_alvo:
                        caminho_origem = os.path.join(app.instance_path, 'mentoria.db')
                        
                        data_formatada = agora.strftime('%m-%d-%Y_%Hh%M')
                        nome_arquivo = f"mentory_{data_formatada}.db"
                        caminho_destino = os.path.join(log.destino, nome_arquivo)
                        
                        if os.path.exists(caminho_origem):
                            # Faz a cópia física do arquivo
                            shutil.copy2(caminho_origem, caminho_destino)
                            log.status = 'Sucesso'
                            log.detalhes += f" | Salvo em: {caminho_destino}"
                        else:
                            log.status = 'Falha'
                            log.detalhes += " | Erro: Banco original não encontrado."
                        
                        # VERIFICA A FREQUÊNCIA E JÁ AGENDA O PRÓXIMO!
                        proxima_data = None
                        detalhes_lower = log.detalhes.lower()
                        
                        if "diario" in detalhes_lower or "diário" in detalhes_lower:
                            proxima_data = data_alvo + timedelta(days=1)
                        elif "semanal" in detalhes_lower:
                            proxima_data = data_alvo + timedelta(weeks=1)
                        elif "mensal" in detalhes_lower:
                            proxima_data = data_alvo + timedelta(days=30)
                            
                        # Se tiver repetição e deu sucesso, cria o agendamento da próxima data
                        if proxima_data and log.status == 'Sucesso':
                            novo_agendamento = RegistroBackup(
                                tipo='Agendado',
                                status='Pendente',
                                data_agendada=proxima_data.strftime('%Y-%m-%d às %H:%M'),
                                destino=log.destino,
                                detalhes=f"Frequência: {log.detalhes.split('Frequência: ')[-1].split(' |')[0]}",
                                usuario_id=log.usuario_id,
                                data_registro=agora
                            )
                            db.session.add(novo_agendamento)
                        
                        db.session.commit()
                except Exception as e:
                    print(f"Erro ao processar backup agendado: {e}")
            
            # A rotina dorme por 60 segundos e checa o relógio novamente
            time.sleep(60)

def iniciar_agendador(app):
    # Inicia a tarefa invisível junto com o servidor Flask
    thread = threading.Thread(target=rotina_de_backups, args=(app.app_context(),))
    thread.daemon = True # Permite que a thread seja encerrada ao fechar o terminal
    thread.start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Injeção segura da nova coluna no banco existente
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE acompanhamento ADD COLUMN planejamento_estudos TEXT"))
            db.session.commit()
        except:
            db.session.rollback() # Ignora silenciosamente se a coluna já existir nas próximas vezes
        
    # --- LIGA O MOTOR DE BACKUP AUTOMÁTICO AQUI ---
    iniciar_agendador(app)
    
    # Roda o servidor web no modo 'debug' (facilita ver erros enquanto estamos programando)
    app.run(debug=True)