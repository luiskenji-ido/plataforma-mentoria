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
from notificacoes import notificar, usuarios_gestao

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
    if current_user.tipo_usuario not in ['Aluno', 'Avaliador Banca']:
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

    # 5. NOTIFICAÇÕES DA PLATAFORMA (demandas, reuniões, bancas, lembretes...)
    from models import Notificacao
    for n in Notificacao.query.filter_by(usuario_id=current_user.id, lida=False).order_by(Notificacao.data_criacao.desc()).limit(10).all():
        notificacoes_formatadas.append({
            'link': url_for('abrir_notificacao', id=n.id),
            'texto': f"🔔 {n.titulo}",
            'data': n.data_criacao
        })


    # 4. TICKETS DO PORTAL DE DEMANDAS AGUARDANDO RESPOSTA (só gestão)
    if current_user.tipo_usuario in ['Administrador', 'Mentor Administrador', 'Admin B2B']:
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
# ===========================================================================
# ESCOPO DE VISIBILIDADE DOS JOVENS POR PERFIL (usado em painéis e listas)
# ===========================================================================
def ids_jovens_visiveis(usuario):
    """None = todos os jovens (Administrador e Mentor Administrador).
    Nos demais perfis, devolve o conjunto de ids dos jovens que a pessoa acompanha."""
    if usuario.tipo_usuario in ['Administrador', 'Mentor Administrador']:
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
    elif current_user.tipo_usuario in ['Mentor', 'Professor']:
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

    return render_template('dashboard.html',
                           encaminhamentos_vencidos=encaminhamentos_vencidos,
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
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
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
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
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
            forcar_troca_senha=forcar_troca,
            modalidade_participacao=(request.form.get('modalidade_participacao') or 'Presencial') if tipo_usuario == 'Aluno' else None
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
    lista_mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Mentor', 'Mentor Administrador', 'Professor'])).all()

    # Busca todos os dados para montar a tela de Cadastros
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Mentor', 'Mentor Administrador', 'Professor'])).all()
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
                flash('Parecer oficial do mentor atualizado!', 'success')
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
                                sincronizar_evento_google(
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
    elif current_user.tipo_usuario in ['Mentor', 'Professor']:
        registros = Acompanhamento.query.join(Usuario, Acompanhamento.aluno_id == Usuario.id).filter(Usuario.mentores.any(id=current_user.id)).all()
    else:
        registros = Acompanhamento.query.order_by(Acompanhamento.id.desc()).all()

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
                    except:
                        pass
                        
        horas_estudo = minutos_estudo // 60
        min_restantes = minutos_estudo % 60
        tempo_formatado = f"{horas_estudo}h {min_restantes}m" if horas_estudo > 0 else f"{min_restantes}m"

        detalhes.append({'reg': r, 'aluno': aluno, 'curso': curso, 'qtd_sessoes': qtd_sessoes, 'tempo_estudo': tempo_formatado})
        
    if current_user.tipo_usuario in ['Mentor', 'Professor']:
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
    
    curso_id = request.form.get('curso_id')
    if not curso_id:
        flash('Erro: Curso não especificado.', 'danger')
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
                            
                            sincronizar_evento_google(
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
    perfis_autorizados = ['Mentor', 'Mentor Administrador', 'Professor', 'Administrador']
    
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
        # 1. Capta as notas do Grupo (O Entregável)
        nota_conteudo = request.form.get('nota_conteudo')
        nota_apresentacao = request.form.get('nota_apresentacao')
        
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
                nota_postura = request.form.get(f'nota_postura_{membro.id}')
                nota_dominio = request.form.get(f'nota_dominio_{membro.id}')
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
        
    if current_user.tipo_usuario in ['Mentor', 'Professor']:
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
        if len(motivo) < 10:
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
        except:
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
            return redirect(request.referrer or url_for('dashboard'))

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

    return redirect(request.referrer or url_for('dashboard'))


# ==============================================================================
# ROTA: PORTAL DE DEMANDAS INSTITUCIONAIS (TICKETS ITM & AON)
# ==============================================================================
# ==============================================================================
# ATIVIDADES EXTRAS DO GRUPO (fora do cronograma) — check-in/out de mentores e jovens
# ==============================================================================
PERFIS_CRIAM_ATIVIDADE_EXTRA = ['Mentor', 'Professor', 'Mentor Administrador', 'Administrador']


def pode_ver_atividade_extra(usuario, atividade):
    if usuario.tipo_usuario in ['Administrador', 'Mentor Administrador']:
        return True
    membros = {m.id for m in atividade.grupo.membros} if atividade.grupo else set()
    if usuario.id in membros or usuario.id == atividade.criado_por_id:
        return True
    if usuario.tipo_usuario == 'Admin B2B':
        return bool(membros & (ids_jovens_visiveis(usuario) or set()))
    return False


def pode_gerir_atividade_extra(usuario, atividade):
    return usuario.id == atividade.criado_por_id or usuario.tipo_usuario in ['Administrador', 'Mentor Administrador']


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
    elif not titulo or len(motivo) < 10 or not inicio:
        flash(t('extra_erro_campos', current_user.idioma), "warning")
    elif not 10 <= duracao <= 12 * 60:
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
    if not atividade or not (pode_gerir_atividade_extra(current_user, atividade) or current_user.tipo_usuario == 'Admin B2B'
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
# REUNIÕES INSTITUCIONAIS ITM × AON (ata, participantes, encaminhamentos e horas)
# ==============================================================================
PERFIS_GESTAO_REUNIOES = ['Administrador', 'Mentor Administrador', 'Admin B2B']


def pode_ver_reuniao(usuario, reuniao):
    return usuario.tipo_usuario in PERFIS_GESTAO_REUNIOES or usuario in reuniao.participantes


def sincronizar_voluntariado_reuniao(reuniao):
    """Mantém um lançamento ESG (categoria Extra) por participante interno, sem duplicar ao editar."""
    from models import CheckinVoluntariado
    existentes = {c.usuario_id: c for c in CheckinVoluntariado.query.filter_by(reuniao_id=reuniao.id).all()}
    contar = {p.id for p in reuniao.participantes if p.tipo_usuario != 'Aluno'} if reuniao.contar_voluntariado else set()
    fim = reuniao.data_hora + timedelta(minutes=reuniao.duracao_minutos or 0)
    for usuario_id in contar:
        lancamento = existentes.pop(usuario_id, None) or CheckinVoluntariado(usuario_id=usuario_id, reuniao_id=reuniao.id)
        lancamento.tipo_atividade = 'Reunião Institucional'
        lancamento.categoria = 'Extra'
        lancamento.data_hora_inicio = reuniao.data_hora
        lancamento.data_hora_fim = fim
        lancamento.total_minutos = reuniao.duracao_minutos or 0
        lancamento.observacoes = f"Reunião #{reuniao.id}: {reuniao.titulo}"[:1000]
        db.session.add(lancamento)
    # Quem saiu da lista (ou "contar como voluntariado" desligado) perde o lançamento
    for sobra in existentes.values():
        db.session.delete(sobra)


def salvar_reuniao_do_formulario(reuniao, formulario):
    """Preenche a reunião com os dados do formulário. Devolve a chave do erro ou None."""
    titulo = (formulario.get('titulo') or '').strip()
    try:
        data_hora = datetime.strptime(formulario.get('data_hora', ''), "%Y-%m-%dT%H:%M")
    except ValueError:
        data_hora = None
    duracao = formulario.get('duracao_minutos', type=int) or 0
    if not titulo or not data_hora:
        return 'reuniao_erro_campos'
    if not 5 <= duracao <= 12 * 60:
        return 'vol_erro_duracao'
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
    ids = [int(i) for i in formulario.getlist('participantes') if i.isdigit()]
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
        nova = reuniao is None
        if nova:
            reuniao = ReuniaoInstitucional(criado_por_id=current_user.id)
        erro = salvar_reuniao_do_formulario(reuniao, request.form)
        if erro:
            flash(t(erro, current_user.idioma), "warning")
            return redirect(request.url)
        db.session.add(reuniao)
        db.session.flush()
        sincronizar_voluntariado_reuniao(reuniao)
        db.session.commit()
        if nova:
            notificar([p for p in reuniao.participantes if p.id != current_user.id],
                      ('notif_reuniao_titulo', {'titulo': reuniao.titulo}),
                      ('notif_reuniao_msg', {'autor': current_user.nome, 'data': reuniao.data_hora.strftime('%d/%m/%Y %H:%M')}),
                      link=url_for('detalhe_reuniao', id=reuniao.id), tipo='reuniao', referencia=f"reuniao:{reuniao.id}")
        flash(t('reuniao_salva', current_user.idioma), "success")
        return redirect(url_for('detalhe_reuniao', id=reuniao.id))

    demanda = db.session.get(DemandaInstitucional, request.args.get('demanda_id', type=int) or 0)
    demandas = DemandaInstitucional.query.order_by(DemandaInstitucional.data_criacao.desc()).limit(100).all()
    return render_template('reuniao_form.html', reuniao=reuniao, pessoas=pessoas_internas_reuniao(),
                           demandas=demandas, demanda_inicial=demanda)


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

    imprimir = request.args.get('imprimir') == '1'
    return render_template('reuniao_ata.html' if imprimir else 'reuniao_detalhe.html', reuniao=reuniao, hoje=datetime.now().date(),
                           pode_editar=current_user.tipo_usuario in PERFIS_GESTAO_REUNIOES)


def encaminhamentos_atrasados(usuario):
    """Encaminhamentos pendentes com prazo vencido que a pessoa deve acompanhar."""
    from models import EncaminhamentoReuniao
    consulta = EncaminhamentoReuniao.query.filter(EncaminhamentoReuniao.status == 'Pendente',
                                                  EncaminhamentoReuniao.prazo < datetime.now().date())
    if usuario.tipo_usuario not in PERFIS_GESTAO_REUNIOES:
        consulta = consulta.filter(EncaminhamentoReuniao.responsavel_id == usuario.id)
    return consulta.all()


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
    perfis_gestao = ['Administrador', 'Mentor Administrador', 'Admin B2B']
    from datetime import datetime

    if request.method == 'POST':
        acao = request.form.get('acao')

        # --- AÇÃO 1: CRIAR NOVO TICKET ---
        if acao == 'nova_demanda':
            titulo = request.form.get('titulo')
            tipo_demanda = request.form.get('tipo_demanda')
            prioridade = request.form.get('prioridade')
            descricao = request.form.get('descricao')

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
        return redirect(request.referrer or url_for('dashboard'))

    erro, grupo_id, projeto_id, motivo = validar_vinculos_voluntariado(current_user, tipo, request.form)
    if erro:
        flash(t(erro, current_user.idioma), "warning")
        return redirect(request.referrer or url_for('dashboard'))

    try:
        # Junta a data com as horas para criar o formato completo
        inicio_dt = datetime.strptime(f"{data_str} {hora_inicio_str}", "%Y-%m-%d %H:%M")
        fim_dt = datetime.strptime(f"{data_str} {hora_fim_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Erro ao processar as datas. Tente novamente.", "danger")
        return redirect(request.referrer or url_for('dashboard'))

    # Trata o caso de virar a noite (ex: 23:00 até 01:00)
    if fim_dt < inicio_dt:
        fim_dt += timedelta(days=1)
    minutos = int((fim_dt - inicio_dt).total_seconds() / 60)

    # Regras: nada no futuro, nada com duração zero e no máximo 12 h por lançamento
    if inicio_dt > datetime.now():
        flash(t('vol_erro_futuro', current_user.idioma), "warning")
        return redirect(request.referrer or url_for('dashboard'))
    if minutos <= 0 or minutos > 12 * 60:
        flash(t('vol_erro_duracao', current_user.idioma), "warning")
        return redirect(request.referrer or url_for('dashboard'))

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
    return redirect(request.referrer or url_for('dashboard'))

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
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador', 'Admin B2B']:
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
    from flask import render_template_string

    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador', 'Admin B2B']:
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

    # Gera um HTML limpo otimizado para salvar como PDF
    html_pdf = """
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <title>Relatório ESG - PDF</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; padding: 20px; }
            .header { text-align: center; border-bottom: 2px solid #198754; padding-bottom: 10px; margin-bottom: 20px; }
            .header h1 { color: #198754; margin: 0; }
            .header p { color: #666; font-size: 0.9em; }
            h2 { color: #198754; font-size: 1.1em; margin-top: 28px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85em; }
            th, td { border: 1px solid #ddd; padding: 8px 10px; text-align: left; }
            th { background-color: #f8f9fa; color: #198754; }
            td.num { text-align: right; font-variant-numeric: tabular-nums; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .badge { background-color: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
            .extra { background-color: #fff3cd; }
            @media print {
                .no-print { display: none; }
                body { padding: 0; }
            }
        </style>
    </head>
    <body onload="window.print()">
        <div class="no-print" style="margin-bottom: 20px; text-align: right;">
            <button onclick="window.print()" style="background: #198754; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Salvar como PDF</button>
            <a href="{{ url_for('dashboard') }}" style="margin-left: 15px; color: #666; text-decoration: none;">Voltar ao Sistema</a>
        </div>
        <div class="header">
            <h1>Relatório Executivo ESG</h1>
            <p>Horas de Voluntariado Corporativo e Impacto Social | Emitido em: {{ data_emissao }}</p>
        </div>

        <h2>Horas por colaborador (regulamentares × extraordinárias)</h2>
        <table>
            <thead><tr><th>Colaborador</th><th>Empresa</th><th>Regulares</th><th>Extras</th><th>Total</th></tr></thead>
            <tbody>
                {% for p in resumo %}
                <tr>
                    <td><strong>{{ p.nome }}</strong></td>
                    <td>{{ p.empresa }}</td>
                    <td class="num">{{ '%.1f'|format(p.Regular / 60) }} h</td>
                    <td class="num">{{ '%.1f'|format(p.Extra / 60) }} h</td>
                    <td class="num"><strong>{{ '%.1f'|format((p.Regular + p.Extra) / 60) }} h</strong></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <h2>Lançamentos</h2>
        <table>
            <thead>
                <tr>
                    <th>Colaborador</th>
                    <th>Empresa</th>
                    <th>Atividade Executada</th>
                    <th>Categoria</th>
                    <th>Grupo / Projeto</th>
                    <th>Motivo</th>
                    <th>Minutos</th>
                    <th>Data</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for d in dados %}
                <tr class="{{ 'extra' if d.categoria == 'Extra' else '' }}">
                    <td><strong>{{ d.nome }}</strong><br><span class="badge">{{ d.perfil }}</span></td>
                    <td>{{ d.empresa }}</td>
                    <td>{{ d.atividade }}</td>
                    <td>{{ d.categoria }}</td>
                    <td>{{ d.grupo }}{% if d.projeto %}<br><small>{{ d.projeto }}</small>{% endif %}</td>
                    <td>{{ d.motivo }}</td>
                    <td class="num"><strong>{{ d.minutos }} min</strong></td>
                    <td>{{ d.data }}</td>
                    <td>{{ d.status }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """
    return render_template_string(html_pdf, dados=dados_formatados, resumo=resumo, data_emissao=datetime.now().strftime('%d/%m/%Y %H:%M'))

# ==============================================================================
# MOTOR DO ONBOARDING B2B E TRAVA DE COMPLIANCE
# ==============================================================================

# O @app.before_request age como um segurança de porta: ele roda ANTES de qualquer página abrir
# Versão vigente do Termo de Adesão (Lei 9.608/98). Mudar a versão obriga todos a assinar de novo.
VERSAO_TERMO_ATUAL = "2.0 - Lei 9.608/98"
TERMO_ORGANIZACAO = "Aon / Instituto ITM"
TERMO_PROJETO = "Jovem Seguro 2026"

# Perfis que precisam concluir a trilha de orientação do TCC antes de usar a plataforma
PERFIS_TRILHA_TCC = ['Mentor', 'Professor', 'Mentor Administrador']

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
    return render_template('onboarding.html', versao_termo=VERSAO_TERMO_ATUAL, organizacao=TERMO_ORGANIZACAO,
                           projeto=TERMO_PROJETO, data_hoje=datetime.now().strftime('%d/%m/%Y'))

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
    if current_user.tipo_usuario not in PERFIS_TRILHA_TCC + ['Administrador']:
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
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador']:
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
    return render_template('certificado.html', projeto=projeto, usuario=usuario, certificado=certificado, detalhe=detalhe,
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
    if current_user.tipo_usuario != 'Administrador':
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
                valido = frequencia in bs.FREQUENCIAS and re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', horario) and 1 <= retencao <= 365
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
                if not enviado.filename.lower().endswith('.db'):
                    flash(tt('Envie um arquivo .db gerado pelo backup da plataforma.', idioma), "warning")
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
    if current_user.tipo_usuario != 'Administrador':
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
    if current_user.tipo_usuario != 'Administrador':
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

    # Exige que a conta do Google esteja conectada
    if 'google_token' not in session:
        flash("Você precisa conectar sua conta do Google Agenda primeiro!", "warning")
        return redirect(url_for('conectar_agenda'))

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
                        sucesso = sincronizar_evento_google(
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
        # Calcular os dias letivos teóricos da turma até a data de hoje (para saber o progresso atual)
        # Por simplificação, se o aluno entrou na turma, conta desde o início da turma
        # Se a turma ainda não começou, pula
        if turma.data_inicio > hoje:
            continue
            
        # Calcula dias úteis (simplificado) desde o início da turma até hoje (ou término, o que for menor)
        data_fim_calculo = hoje if hoje < turma.data_termino else turma.data_termino
        dias_corridos = (data_fim_calculo - turma.data_inicio).days + 1
        
        # Desconta estimativa de finais de semana (5 dias úteis a cada 7)
        semanas = dias_corridos // 7
        dias_extras = dias_corridos % 7
        dias_letivos_estimados = (semanas * 5) + min(dias_extras, 5) # Estimativa de total de aulas dadas

        if dias_letivos_estimados <= 0:
            continue
            
        limite_faltas = int(dias_letivos_estimados * 0.25) # 25% de faltas

        for aluno in turma.alunos:
            total_alunos_avaliados += 1
            
            # Conta presenças (Online + Presencial)
            qtd_presencas = Frequencia.query.filter(
                Frequencia.usuario_id == aluno.id,
                Frequencia.tipo_presenca.in_(['Online', 'Presencial'])
            ).count()
            
            # Conta faltas não justificadas
            qtd_faltas = Frequencia.query.filter(
                Frequencia.usuario_id == aluno.id,
                Frequencia.tipo_presenca.in_(['Falta', 'Falta Automática'])
            ).count()
            
            # Taxa de presença do aluno em relação ao esperado até hoje
            # Para evitar 100% mágico se o aluno não bateu ponto, calculamos sobre o total letivo esperado
            taxa_aluno = (qtd_presencas / dias_letivos_estimados) * 100 if dias_letivos_estimados > 0 else 100
            # Trava para não passar de 100% se o aluno preencheu sábado/domingo
            if taxa_aluno > 100: taxa_aluno = 100
            
            soma_taxas_presenca += taxa_aluno
            
            # Análise de Risco (MEC)
            if qtd_faltas > limite_faltas:
                # Já estourou os 25%
                kpi_alunos_reprovados += 1
            elif qtd_faltas >= (limite_faltas * 0.75):
                # Usou 75% da sua "cota" de faltas - Está em risco!
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
    if current_user.is_authenticated and current_user.tipo_usuario in ['Aluno', 'Mentor', 'Professor'] \
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
    return redirect(request.referrer or url_for('dashboard'))

# ==============================================================================
# ROTA: HUB EDUCACIONAL (CATÁLOGO, PARCEIROS E TURMAS)
# ==============================================================================
@app.route('/admin/turmas', methods=['GET', 'POST'])
@login_required
def gerenciar_turmas():
    from datetime import datetime  # <--- ADICIONE ESTA LINHA AQUI
    if current_user.tipo_usuario not in ['Administrador', 'Mentor Administrador', 'Admin B2B']:
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
            tipo_usuario = request.form.get('tipo_usuario_rapido')
            senha_plana = request.form.get('senha_usuario')
            
            if Usuario.query.filter_by(email=email).first():
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
                    forcar_troca_senha=True
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
                    
                    for linha in leitor_csv:
                        # Procura pelas colunas 'nome' e 'email' (ignorando maiúsculas/minúsculas)
                        nome_csv = linha.get('nome') or linha.get('Nome') or linha.get('NOME')
                        email_csv = linha.get('email') or linha.get('Email') or linha.get('EMAIL')
                        
                        if nome_csv and email_csv:
                            email_limpo = email_csv.strip().lower()
                            
                            # Só cria o aluno se o e-mail não existir no sistema
                            if not Usuario.query.filter_by(email=email_limpo).first():
                                senha_padrao = bcrypt.generate_password_hash("Mudar@123").decode('utf-8')
                                novo_aluno = Usuario(
                                    nome=nome_csv.strip(),
                                    email=email_limpo,
                                    tipo_usuario='Aluno',
                                    status='Ativo',
                                    senha=senha_padrao,
                                    forcar_troca_senha=True
                                )
                                db.session.add(novo_aluno)
                                sucessos += 1
                            else:
                                ignorados += 1
                                
                    db.session.commit()
                    
                    mensagem = f'{sucessos} novos alunos importados com sucesso!'
                    if ignorados > 0:
                        mensagem += f' ({ignorados} e-mails já existiam e foram ignorados).'
                    flash(mensagem, 'success')
                    
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
    mentores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Mentor', 'Mentor Administrador', 'Professor']), Usuario.status=='Ativo').order_by(Usuario.nome).all()
    gestores = Usuario.query.filter(Usuario.tipo_usuario.in_(['Administrador', 'Admin B2B']), Usuario.status=='Ativo').order_by(Usuario.nome).all()

    # --- LÓGICA BLINDADA: MENTORES DISPONÍVEIS (POR ID) ---
    mentores_em_uso_ids = []
    for emp in empresas:
        for m in emp.mentores:
            mentores_em_uso_ids.append(m.id)
            
    # Filtra mantendo APENAS os mentores cujo ID NÃO está na lista de uso
    mentores_disponiveis = [m for m in mentores if m.id not in mentores_em_uso_ids]
    # ------------------------------------------------------

    # 2. Enviar tudo para o HTML
    return render_template('admin_turmas.html', 
                           cursos=cursos, 
                           empresas=empresas,
                           grupos=grupos,
                           turmas=turmas,
                           mentores=mentores,
                           gestores=gestores,
                           alunos=alunos,
                           mentores_disponiveis=mentores_disponiveis)



    return render_template('admin_turmas.html', empresas=empresas, turmas=turmas, cursos=cursos, alunos=alunos, grupos=grupos, mentores=lista_mentores, gestores=lista_gestores)
    
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
                
                dados_tabela.append({
                    'aluno': aluno,
                    'acompanhamentos': acompanhamentos
                })

    if request.method == 'POST':
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
    return usuario in membros_do_projeto(projeto) or usuario.tipo_usuario in ['Administrador', 'Mentor Administrador']


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
            if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{10,}$', senha):
                flash("Segurança: A senha inicial deve ter no mínimo 10 caracteres (maiúsculas, minúsculas, números e especiais).", "danger")
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
                if len(motivo) < 5:
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

        elif acao in ['publicar', 'publicar_todas'] and current_user.tipo_usuario in ['Administrador', 'Mentor Administrador']:
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
                           pode_publicar=current_user.tipo_usuario in ['Administrador', 'Mentor Administrador'])


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
                flash(t(erro, current_user.idioma), "warning")
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
    return valor if 0 <= valor <= 10 else None


def registrar_etapa_avaliacao(avaliacao, etapa, formulario):
    """Grava uma etapa da avaliação. Devolve a chave do erro ou None."""
    if etapa == 'etapa_escrita':
        nota = ler_nota(formulario, 'nota_escrita')
        justificativa = (formulario.get('justificativa_escrita') or '').strip()
        if nota is None:
            return 'banca_erro_nota'
        if nota < 7 and len(justificativa) < 10:
            return 'banca_erro_justificativa'
        avaliacao.nota_escrita, avaliacao.justificativa_escrita = nota, justificativa or None
        avaliacao.etapa_escrita_concluida_em = datetime.utcnow()
    else:
        apresentacao, visual = ler_nota(formulario, 'nota_apresentacao'), ler_nota(formulario, 'nota_visual')
        justificativa = (formulario.get('justificativa_oral') or '').strip()
        if apresentacao is None or visual is None:
            return 'banca_erro_nota'
        if min(apresentacao, visual) < 7 and len(justificativa) < 10:
            return 'banca_erro_justificativa'
        avaliacao.nota_apresentacao, avaliacao.nota_visual = apresentacao, visual
        avaliacao.justificativa_oral = justificativa or None
        avaliacao.feedback_jovens = (formulario.get('feedback_jovens') or '').strip() or None
        avaliacao.etapa_oral_concluida_em = datetime.utcnow()
    return None


def consolidar_banca(banca, encerrar=False):
    """Médias por critério entre os avaliadores e fórmula oficial (40/40/20).
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
        projeto.nota_final = round(projeto.nota_conteudo * 0.4 + projeto.nota_apresentacao * 0.4 + projeto.nota_visual * 0.2, 2)
    else:
        projeto.nota_final = None

    concluidas = {a.avaliador_id for a in avaliacoes if a.etapa_escrita_concluida_em and a.etapa_oral_concluida_em}
    todos = bool(banca.avaliadores) and {p.id for p in banca.avaliadores} <= concluidas
    fechou = False
    if (encerrar or todos) and projeto.nota_final is not None and banca.status != 'Realizada':
        projeto.status = 'Concluído' if projeto.nota_final >= 7.0 else 'Em Recuperação'
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
    if quem.id == usuario.id or quem.tipo_usuario in ['Administrador', 'Mentor Administrador']:
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
    return render_template('certificado_verificar.html', certificado=certificado, codigo=codigo)


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


app.jinja_env.globals.update(eh_orientador=eh_orientador)


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
    """Acervo aberto (sem login) para o Instituto Aon, o ITM e o mercado: só TCCs públicos e autorizados."""
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
                    ('mentor_administrador', 'Mentor Administrador'), ('gestor_b2b', 'Gestor B2B'), ('avaliador', 'Avaliador Banca')]
# Uma subpasta por agente em cada pasta da área (mesmos nomes que o agentes_omnitest/agente_gestor.py usa)
PASTAS_PERFIS_IA = ['Perfil administrador', 'Perfil aluno', 'Perfil professor', 'Perfil mentor',
                    'Perfil mentor administrador', 'Perfil gestor B2B', 'Perfil avaliador banca']


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

    def subpastas(pasta):
        # Sempre as 7 subpastas, na ordem dos agentes, mesmo antes da primeira execução
        for nome in PASTAS_PERFIS_IA:
            os.makedirs(os.path.join(pasta, nome), exist_ok=True)
        return [{'nome': n, 'arquivos': arquivos(os.path.join(pasta, n))} for n in PASTAS_PERFIS_IA]

    e2e = os.path.join(PASTA_AGENTES_IA, 'Agentes Teste Fim a Fim')
    seg = os.path.join(PASTA_AGENTES_IA, 'Agentes Teste de Segurança')
    return [
        {'nome': 'Agentes Teste Fim a Fim', 'pastas': [
            {'nome': 'Relatórios de Testes Fim a Fim e Evidencias', 'subpastas': subpastas(os.path.join(e2e, 'Relatórios de Testes Fim a Fim e Evidencias'))},
            {'nome': 'Prompt de correção LLM', 'subpastas': subpastas(os.path.join(e2e, 'Prompt de correção LLM'))}]},
        {'nome': 'Agentes Teste de Segurança', 'em_breve': True, 'pastas': [
            {'nome': 'Relatórios de Testes de Segurança', 'subpastas': subpastas(os.path.join(seg, 'Relatórios de Testes de Segurança'))},
            {'nome': 'Prompt de correção LLM', 'subpastas': subpastas(os.path.join(seg, 'Prompt de correção LLM'))}]},
    ]


def _somente_administrador():
    if current_user.tipo_usuario != 'Administrador':
        flash("Acesso Negado.", "danger")
        return redirect(url_for('dashboard'))
    return None


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
    subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, **opcoes)
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
    if current_user.tipo_usuario != 'Administrador':
        return jsonify({'erro': 'acesso negado'}), 403
    quadro = os.path.join(PASTA_AO_VIVO_IA, 'frame.jpg')
    return jsonify({'estado': estado_agentes_ia(), 'agente': _ler_json_ia('agente.json'), 'agora': datetime.now().isoformat(timespec='seconds'),
                    'quadro': os.path.getmtime(quadro) if os.path.exists(quadro) else None})


@app.route('/admin/agentes-ia/quadro')
@login_required
def quadro_agentes_ia():
    """Último quadro do navegador do agente em execução (o monitor central da página)."""
    if current_user.tipo_usuario != 'Administrador':
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
<p class="fw-bold">Nota final = Escrito × 0,4 + Apresentação × 0,4 + Visual × 0,2 — aprovado a partir de 7,0.</p>
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


# ===========================================================================
# ATUALIZAÇÃO DO BANCO DE DADOS (Garante que roda no PythonAnywhere)
# ===========================================================================
def atualizar_estrutura_banco():
    """Cria tabelas e colunas novas. Roda ao iniciar e depois de restaurar um backup antigo."""
    from sqlalchemy import text
    db.create_all()
    colunas_novas = [
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
        # Adequações Aon/ITM
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
        "ALTER TABLE qa_banca ADD COLUMN ordem INTEGER DEFAULT 0"
    ]
    
    for comando in colunas_novas:
        try:
            db.session.execute(text(comando))
            db.session.commit()
        except Exception:
            db.session.rollback()

    garantir_modulos_trilha_tcc()
    import backup_servico
    backup_servico.migrar_agendamentos_antigos()


with app.app_context():
    atualizar_estrutura_banco()

# ===========================================================================
# EXECUÇÃO DO APLICATIVO
# ===========================================================================
if __name__ == '__main__':
    # Liga a tarefa de backup automático em segundo plano
    iniciar_agendador(app)
    # Roda o servidor web no modo 'debug'
    app.run(debug=True)
