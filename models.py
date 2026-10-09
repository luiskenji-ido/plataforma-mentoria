# Importando as ferramentas necessárias para criar o banco de dados e gerenciar o login
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

# Criando a "ponte" entre o nosso código Python e o arquivo do banco de dados (SQLite)
db = SQLAlchemy()

# ===========================================================================
# NOVA TABELA PONTE: RELAÇÃO MUITOS-PARA-MUITOS (ALUNOS <-> MENTORES)
# ===========================================================================
aluno_mentor = db.Table('aluno_mentor',
    db.Column('aluno_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True),
    db.Column('mentor_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)

# ---------------------------------------------------------------------------
# 1. TABELA DE USUÁRIOS (CADASTROS E PRONTUÁRIO)
# ---------------------------------------------------------------------------
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo_usuario = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Ativo')
    tentativas_login = db.Column(db.Integer, default=0)
    tema = db.Column(db.String(20), default='claro')
    idioma = db.Column(db.String(10), default='pt')
    data_ultima_troca_senha = db.Column(db.DateTime, default=datetime.utcnow)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    criado_por = db.Column(db.String(100), default='Sistema')
    forcar_troca_senha = db.Column(db.Boolean, default=True)
    exibir_tour = db.Column(db.Boolean, default=True)
    perfil_aluno = db.Column(db.Text, nullable=True)
    objetivo_principal = db.Column(db.Text, nullable=True)
    expectativa_mentoria = db.Column(db.Text, nullable=True)
    
    # -------------------------------------------------------------
    # A LIGAÇÃO OFICIAL: Isso diz ao banco que um Aluno tem uma lista
    # de mentores, baseada naquela tabela ponte que criamos lá em cima!
    # -------------------------------------------------------------
    mentores = db.relationship('Usuario', 
                               secondary=aluno_mentor,
                               primaryjoin=(aluno_mentor.c.aluno_id == id),
                               secondaryjoin=(aluno_mentor.c.mentor_id == id),
                               backref=db.backref('alunos', lazy='dynamic'),
                               lazy='dynamic')

# ---------------------------------------------------------------------------
# 2. TABELA DE CURSOS
# ---------------------------------------------------------------------------
class Curso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_curso = db.Column(db.String(200), nullable=False)
    exige_certificado = db.Column(db.String(3), default='Não')
    url = db.Column(db.String(500), nullable=True)
    plataforma = db.Column(db.String(100), default='Plataforma Externa')
    carga_horaria = db.Column(db.Integer, default=20)
    tipo = db.Column(db.String(50), default='Hard Skill')
    status = db.Column(db.String(20), default='Ativo')
    data_inclusao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    desativado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    motivo_desativacao = db.Column(db.Text, nullable=True)
    data_desativacao = db.Column(db.DateTime, nullable=True)
    # Relacionamento para puxar o nome de quem cadastrou o curso
    criador = db.relationship('Usuario', foreign_keys=[criado_por_id])

# ---------------------------------------------------------------------------
# 3. TABELA DE ACOMPANHAMENTO (PROGRESSO DO ALUNO)
# ---------------------------------------------------------------------------
class Acompanhamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    status = db.Column(db.String(50), default='Iniciado') 
    percentual_conclusao = db.Column(db.Integer, default=0)
    percentual_mentor = db.Column(db.Integer, default=0)
    certificado_anexado = db.Column(db.Boolean, default=False) 
    observacao = db.Column(db.Text, nullable=True)
    data_parecer_mentor = db.Column(db.DateTime, nullable=True)
    observacao_aluno = db.Column(db.Text, nullable=True)
    material_apoio = db.Column(db.String(200), nullable=True)
    data_limite = db.Column(db.DateTime, nullable=True)
    data_inicio = db.Column(db.DateTime, nullable=True)
    data_termino = db.Column(db.DateTime, nullable=True)
    planejamento_estudos = db.Column(db.String(2000), nullable=True)
    # Notas da Avaliação Final do Curso
    nota_tecnica = db.Column(db.Float, nullable=True)
    nota_postura = db.Column(db.Float, nullable=True)

# ---------------------------------------------------------------------------
# 4. TABELA DE SESSÕES DE MENTORIA
# ---------------------------------------------------------------------------
class SessaoMentoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_sessao = db.Column(db.DateTime, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)

# ---------------------------------------------------------------------------
# 5. TABELA DE FEEDBACK DAS SESSÕES
# ---------------------------------------------------------------------------
class FeedbackSessao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sessao_id = db.Column(db.Integer, db.ForeignKey('sessao_mentoria.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    papel_autor = db.Column(db.String(20), nullable=False)
    comentario = db.Column(db.Text, nullable=False)
    visibilidade = db.Column(db.String(20), default='Publico')
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOVAS COLUNAS PARA O SINO DE NOTIFICAÇÕES
    lida_pelo_aluno = db.Column(db.Boolean, default=True)
    lida_pelo_mentor = db.Column(db.Boolean, default=True)
    autor = db.relationship('Usuario', foreign_keys=[autor_id])

# ---------------------------------------------------------------------------
# 6. TABELA: Q&A (DÚVIDAS E RESPOSTAS)
# ---------------------------------------------------------------------------
class QADuvida(db.Model):
    __tablename__ = 'qa_duvida'
    
    id = db.Column(db.Integer, primary_key=True)
    acompanhamento_id = db.Column(db.Integer, db.ForeignKey('acompanhamento.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    mensagem = db.Column(db.Text, nullable=False)
    resposta = db.Column(db.Text, nullable=True)
    
    lida_pelo_aluno = db.Column(db.Boolean, default=False)
    lida_pelo_mentor = db.Column(db.Boolean, default=True)
    
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_resposta = db.Column(db.DateTime, nullable=True)

    autor = db.relationship('Usuario', foreign_keys=[autor_id])
    acompanhamento = db.relationship('Acompanhamento', backref=db.backref('duvidas_qa', lazy=True))

# ---------------------------------------------------------------------------
# 7. TABELA DE HISTÓRICO DE PROGRESSO (MEMÓRIA)
# ---------------------------------------------------------------------------
class HistoricoProgresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acompanhamento_id = db.Column(db.Integer, db.ForeignKey('acompanhamento.id'), nullable=False)
    percentual = db.Column(db.Integer, nullable=False)
    data_registro = db.Column(db.DateTime, default=datetime.now)

    acompanhamento = db.relationship('Acompanhamento', backref=db.backref('historico_progresso', lazy=True, cascade="all, delete-orphan"))

# ---------------------------------------------------------------------------
# 8. TABELA DE HISTÓRICO DE Senha (MEMÓRIA)
# ---------------------------------------------------------------------------
class HistoricoSenha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)


# ==================================================================================
# 9. TABELA DE SEGURANÇA: Armazena as 3 perguntas escolhidas para recuperar a senha
# ==================================================================================
class SegurancaUsuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Vincula esta configuração ao ID do usuário dono da conta
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Textos das 3 perguntas escolhidas e suas respectivas respostas
    pergunta_1 = db.Column(db.String(200), nullable=False)
    resposta_1 = db.Column(db.String(200), nullable=False)
    
    pergunta_2 = db.Column(db.String(200), nullable=False)
    resposta_2 = db.Column(db.String(200), nullable=False)
    
    pergunta_3 = db.Column(db.String(200), nullable=False)
    resposta_3 = db.Column(db.String(200), nullable=False)


# ==============================================================================
# 10. TABELA: Histórico de Solicitações de Mentoria (Fila de Aprovação)
# ==============================================================================
class SolicitacaoMentoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pendente') # Pendente, Aprovado, Negado
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)


# ==============================================================================
# 11. TABELA: Registro de Backup
# ==============================================================================
class RegistroBackup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50)) # 'Agendado' ou 'Imediato'
    status = db.Column(db.String(50)) # 'Pendente', 'Sucesso' ou 'Falha'
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    data_agendada = db.Column(db.String(50), nullable=True) 
    destino = db.Column(db.String(255))
    detalhes = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    autor = db.relationship('Usuario', backref='backups_registrados')


# ==============================================================================
# 12. TABELA: Projeto
# ==============================================================================
class Projeto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    
    # NOVA LIGAÇÃO: Substituímos o aluno_id e mentor_id pelo grupo_id
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=False)
    
    status = db.Column(db.String(50), default='Em Andamento')
    percentual_conclusao = db.Column(db.Integer, default=0)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relações para facilitar as buscas no sistema
    tarefas = db.relationship('Tarefa', backref='projeto', lazy=True, cascade="all, delete-orphan")
    grupo = db.relationship('Grupo', backref='projetos', lazy=True)
    # Notas da Avaliação Coletiva (Entregável do Grupo)
    nota_conteudo = db.Column(db.Float, nullable=True)
    nota_apresentacao = db.Column(db.Float, nullable=True)

# ==============================================================================
# 13. TABELA: Tarefa (Agora suporta Subtarefas e Equipe de Apoio)
# ==============================================================================
class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    
    # NOVA LIGAÇÃO: Permite que uma tarefa seja "filha" de outra tarefa
    tarefa_pai_id = db.Column(db.Integer, db.ForeignKey('tarefa.id'), nullable=True)
    
    descricao = db.Column(db.String(255), nullable=False)
    data_inicio = db.Column(db.DateTime, nullable=True)
    data_fim = db.Column(db.DateTime, nullable=True)
    
    responsavel = db.Column(db.String(150), nullable=True)
    # NOVA COLUNA: Equipe de apoio
    equipe_apoio = db.Column(db.String(255), nullable=True) 
    
    status = db.Column(db.String(50), default='Pendente')
    percentual_conclusao = db.Column(db.Integer, default=0)
    arquivo_anexo = db.Column(db.String(255), nullable=True)
    tag_autor_anexo = db.Column(db.String(50), nullable=True)

    planejamento_tarefa = db.Column(db.String(2000), nullable=True)
    tempo_total_minutos = db.Column(db.Integer, default=0)


    # Relação para o Python puxar as subtarefas facilmente
    subtarefas = db.relationship('Tarefa', backref=db.backref('tarefa_pai', remote_side=[id]), cascade="all, delete-orphan")

# ==============================================================================
# TABELA DE ASSOCIAÇÃO INVISÍVEL: grupo_usuario (N para N)
# Funciona como uma "ponte" para ligar vários usuários a vários grupos
# ==============================================================================
grupo_usuario = db.Table('grupo_usuario',
    db.Column('grupo_id', db.Integer, db.ForeignKey('grupo.id'), primary_key=True),
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)

# Tabela associativa: Quais alunos pertencem a quais turmas
turma_aluno = db.Table('turma_aluno',
    db.Column('turma_id', db.Integer, db.ForeignKey('turma.id'), primary_key=True),
    db.Column('aluno_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)

# Tabela associativa: Quais mentores gerem quais turmas
turma_mentor = db.Table('turma_mentor',
    db.Column('turma_id', db.Integer, db.ForeignKey('turma.id'), primary_key=True),
    db.Column('mentor_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)

# Tabela associativa: Quais cursos (trilhas) compõem uma turma
turma_curso = db.Table('turma_curso',
    db.Column('turma_id', db.Integer, db.ForeignKey('turma.id'), primary_key=True),
    db.Column('curso_id', db.Integer, db.ForeignKey('curso.id'), primary_key=True)
)

# ==============================================================================
# 14. TABELA: Grupo
# ==============================================================================
class Grupo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    descricao = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relação N para N: A mágica que conecta o Grupo à tabela de Usuários usando a ponte acima
    membros = db.relationship('Usuario', secondary=grupo_usuario, lazy='subquery',
                              backref=db.backref('grupos', lazy=True))

# ==============================================================================
# 15. TABELA: Frequência (Controle de Presença Diária)
# ==============================================================================
class Frequencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Guarda o momento exato em que a pessoa clicou no botão
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Opções: 'Online', 'Presencial' ou 'Falta'
    tipo_presenca = db.Column(db.String(20), nullable=False)
    
    observacoes = db.Column(db.Text, nullable=True)
    
    # Campos exclusivos para a equipe de gestão validar depois
    validado_admin = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    observacoes_admin = db.Column(db.Text, nullable=True)
    
    # Facilita buscar os dados do usuário e do admin que validou
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref=db.backref('frequencias', lazy=True))
    admin_validador = db.relationship('Usuario', foreign_keys=[admin_id])

# ==============================================================================
# 16. TABELA: Avaliação Individual de Projetos (TCC)
# ==============================================================================
class AvaliacaoProjeto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Notas do Comportamento Individual na Equipe e na Banca
    nota_postura = db.Column(db.Float, nullable=True)
    nota_dominio = db.Column(db.Float, nullable=True)
    observacoes_mentor = db.Column(db.Text, nullable=True)
    
    # Relações para facilitar as buscas no painel
    projeto = db.relationship('Projeto', backref=db.backref('avaliacoes_individuais', lazy=True, cascade="all, delete-orphan"))
    aluno = db.relationship('Usuario', backref=db.backref('avaliacoes_projetos', lazy=True))

# ==============================================================================
# 17. TABELA: Empresa (Parceiros B2B)
# ==============================================================================
# Tabela ponte para a relação muitos-para-muitos entre Empresa e Mentores
empresa_mentor = db.Table('empresa_mentor',
    db.Column('empresa_id', db.Integer, db.ForeignKey('empresa.id'), primary_key=True),
    db.Column('mentor_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)

class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    contato_nome = db.Column(db.String(100), nullable=True)
    contato_email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default='Ativa') # Ativa / Inativa
    
    # NOVA LIGAÇÃO 1: O Gestor Parceiro (Admin B2B)
    gestor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    gestor = db.relationship('Usuario', foreign_keys=[gestor_id], backref='empresas_gerenciadas')
    
    # NOVA LIGAÇÃO 2: Os Mentores vinculados a esta empresa
    mentores = db.relationship('Usuario', secondary=empresa_mentor, lazy='subquery',
        backref=db.backref('empresas_vinculadas', lazy=True))
    
    # Uma empresa pode ter várias turmas
    turmas = db.relationship('Turma', backref='empresa', lazy=True)

# ==============================================================================
# 18. TABELA: Turma (O Motor do KPI e Frequência)
# ==============================================================================
class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False) # Ex: Semestre 2 - 2026
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True)
    
    # O Motor do KPI (As datas cravadas)
    data_inicio = db.Column(db.Date, nullable=False)
    data_termino = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), default='Ativa') # Ativa / Concluída
    
    # Relações: Trilhas, Alunos e Mentores
    cursos = db.relationship('Curso', secondary=turma_curso, lazy='subquery',
        backref=db.backref('turmas_vinculadas', lazy=True))
    alunos = db.relationship('Usuario', secondary=turma_aluno, lazy='subquery',
        backref=db.backref('turmas_como_aluno', lazy=True))
    mentores = db.relationship('Usuario', secondary=turma_mentor, lazy='subquery',
        backref=db.backref('turmas_como_mentor', lazy=True))