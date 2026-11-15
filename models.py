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
    # Como o jovem participa do programa: 'Presencial', 'Online' ou 'Híbrido'
    modalidade_participacao = db.Column(db.String(20), default='Presencial')
    # Aceita receber por e-mail os avisos da plataforma (o sino continua mostrando tudo)
    receber_email = db.Column(db.Boolean, default=True)
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

    # Usado no Diário de Classe (admin_notas.html mostra o nome do curso de cada matrícula)
    curso = db.relationship('Curso', lazy='joined')

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
    # Execução: arquivo gerado, tamanho, duração e o agendamento que a disparou (vazio = manual)
    arquivo = db.Column(db.String(255), nullable=True)
    tamanho_bytes = db.Column(db.Integer, nullable=True)
    duracao_seg = db.Column(db.Float, nullable=True)
    agendamento_id = db.Column(db.Integer, nullable=True)
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
    # Banca: médias consolidadas e divulgação controlada pela coordenação
    nota_visual = db.Column(db.Float, nullable=True)
    nota_final = db.Column(db.Float, nullable=True)
    data_avaliacao = db.Column(db.DateTime, nullable=True)
    notas_publicadas = db.Column(db.Boolean, default=False)
    data_publicacao_notas = db.Column(db.DateTime, nullable=True)

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
    # Adicione estas duas linhas abaixo dos contatos principais:
    contato_sec_nome = db.Column(db.String(150), nullable=True)
    contato_sec_email = db.Column(db.String(150), nullable=True)
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

# ==============================================================================
# 19. NOVO MODELO: CHECK-IN POR AULA / CURSO (Pontualidade e Tempo de Estudo)
# ==============================================================================
class CheckinAula(db.Model):
    __tablename__ = 'checkin_aula'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    
    # Grava o momento exato do clique
    data_hora_entrada = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Herda a modalidade do dia (Online ou Presencial)
    modalidade = db.Column(db.String(20), nullable=True) 
    
    # Relacionamentos para facilitar a busca nos relatórios dos professores
    usuario = db.relationship('Usuario', backref=db.backref('checkins_aulas', lazy=True))
    curso = db.relationship('Curso', backref=db.backref('checkins_aulas', lazy=True))

    def __repr__(self):
        return f"<CheckinAula {self.usuario.nome} - {self.curso.nome_curso}>"


# ==============================================================================
# 20. MÓDULO 4: BANCA AVALIADORA (AON / ITM) E VOLUNTARIADO DE LEITURA
# ==============================================================================

class PerfilAvaliador(db.Model):
    __tablename__ = 'perfil_avaliador'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Dados Corporativos do Executivo
    empresa_origem = db.Column(db.String(150), default="Parceiro B2B")
    area_atuacao = db.Column(db.String(150))
    curriculo_minibio = db.Column(db.Text)
    # Adequações Aon/ITM: ficha do executivo para a apresentação final
    nome_completo = db.Column(db.String(200), nullable=True)
    telefone = db.Column(db.String(40), nullable=True)
    linkedin = db.Column(db.String(300), nullable=True)
    curriculo_arquivo = db.Column(db.String(255), nullable=True)  # PDF em uploads/tcc/
    
    # Relação com a tabela principal de Usuários
    usuario = db.relationship('Usuario', backref=db.backref('perfil_avaliador', uselist=False))

class CheckinVoluntariado(db.Model):
    __tablename__ = 'checkin_voluntariado'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=True) # Pode ser leitura de um TCC específico
    
    # Ex: 'Leitura de TCC', 'Banca Ao Vivo', 'Mentoria Extraordinária'
    tipo_atividade = db.Column(db.String(100), nullable=False) 
    
    data_hora_inicio = db.Column(db.DateTime, nullable=False)
    data_hora_fim = db.Column(db.DateTime, nullable=True) # Fica vazio até o executivo fazer o Check-out
    total_minutos = db.Column(db.Integer, default=0)
    
    observacoes = db.Column(db.Text)
    # Adequações Aon/ITM: com qual grupo foi o extra e se a hora é Regular ou Extra (fora do cronograma)
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=True)
    categoria = db.Column(db.String(20), default='Regular')
    # Lançamento gerado por uma reunião institucional (atualizado quando a reunião é editada)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=True)

    usuario = db.relationship('Usuario', backref=db.backref('lancamentos_voluntariado', lazy='dynamic'))
    grupo = db.relationship('Grupo')
    projeto = db.relationship('Projeto')

class QABanca(db.Model):
    __tablename__ = 'qa_banca'
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    avaliador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    pergunta_feita = db.Column(db.Text, nullable=False)
    resposta_jovens = db.Column(db.Text) # Resumo de como os jovens se saíram na resposta

    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    banca_id = db.Column(db.Integer, db.ForeignKey('banca.id'), nullable=True)
    ordem = db.Column(db.Integer, default=0)
    avaliador = db.relationship('Usuario')


# ==============================================================================
# 21. MÓDULO 5: PORTAL DE DEMANDAS INSTITUCIONAIS (TICKETS ITM & AON)
# ==============================================================================

class DemandaInstitucional(db.Model):
    __tablename__ = 'demanda_institucional'
    id = db.Column(db.Integer, primary_key=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Classificação do Ticket
    tipo_demanda = db.Column(db.String(50), nullable=False) # Mudança de Data, Melhoria, Alinhamento, etc.
    prioridade = db.Column(db.String(20), default='Normal') # Baixa, Normal, Alta, Urgente
    status = db.Column(db.String(20), default='Aberta')     # Aberta, Em Análise, Concluída, Cancelada
    
    # Conteúdo
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    
    # Resolução (Preenchido pelos Gestores/Admins)
    resposta_oficial = db.Column(db.Text, nullable=True) 
    
    # Datas de rastreio
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Conexão com quem abriu o chamado
    autor = db.relationship('Usuario', backref='demandas_criadas')

# ==============================================================================
# 22. MÓDULO 6: COMPLIANCE E ONBOARDING (TERMOS DE USO B2B)
# ==============================================================================

class TermoAceite(db.Model):
    __tablename__ = 'termo_aceite'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    data_aceite = db.Column(db.DateTime, default=datetime.utcnow)
    versao_termo = db.Column(db.String(50), default="1.0 - B2B Genérico")
    
    usuario = db.relationship('Usuario', backref='termos_assinados')


# ==============================================================================
# TABELA: Conversa dos tickets do Portal de Demandas (autor <-> gestão)
# ==============================================================================
class ComentarioDemanda(db.Model):
    __tablename__ = 'comentario_demanda'
    id = db.Column(db.Integer, primary_key=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey('demanda_institucional.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    demanda = db.relationship('DemandaInstitucional', backref=db.backref(
        'comentarios', lazy=True, order_by='ComentarioDemanda.data_criacao', cascade="all, delete-orphan"))
    autor = db.relationship('Usuario')



# ==============================================================================
# TABELAS: Trilha obrigatória de orientação do TCC para mentores e professores
# Cada módulo tem uma versão; ao exigir releitura, a versão sobe e o módulo volta
# a ficar pendente para quem leu uma versão anterior.
# ==============================================================================
class ModuloOnboardingTCC(db.Model):
    __tablename__ = 'modulo_onboarding_tcc'
    id = db.Column(db.Integer, primary_key=True)
    ordem = db.Column(db.Integer, default=1)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo_html = db.Column(db.Text, nullable=False)
    link_video = db.Column(db.String(500), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    versao = db.Column(db.Integer, default=1)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConclusaoModuloTCC(db.Model):
    __tablename__ = 'conclusao_modulo_tcc'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulo_onboarding_tcc.id'), nullable=False)
    versao_lida = db.Column(db.Integer, default=1)
    data_conclusao = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('modulos_tcc_concluidos', lazy=True))
    modulo = db.relationship('ModuloOnboardingTCC', backref=db.backref('conclusoes', lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint('usuario_id', 'modulo_id', name='uq_conclusao_modulo_usuario'),)


# ==============================================================================
# TABELA: Notificações da plataforma (sino e e-mail)
# 'referencia' identifica o evento (ex.: 'checkout:15') para não avisar duas vezes.
# ==============================================================================
class Notificacao(db.Model):
    __tablename__ = 'notificacao'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False)
    mensagem = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(500), nullable=True)
    tipo = db.Column(db.String(50), default='geral')
    referencia = db.Column(db.String(100), nullable=True, index=True)
    lida = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('notificacoes', lazy='dynamic'))


# ==============================================================================
# TABELAS: Atividades extras do grupo (fora do cronograma) com check-in/out
# de mentores E jovens. Horários em hora local, como o lançamento manual.
# ==============================================================================
class AtividadeExtra(db.Model):
    __tablename__ = 'atividade_extra'
    id = db.Column(db.Integer, primary_key=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    data_hora_inicio_prevista = db.Column(db.DateTime, nullable=False)
    duracao_prevista_min = db.Column(db.Integer, default=60)
    modalidade = db.Column(db.String(20), default='Presencial')  # Presencial / Online
    link_sala = db.Column(db.String(500), nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    status = db.Column(db.String(20), default='Agendada')  # Agendada / Em andamento / Encerrada / Cancelada
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_encerramento = db.Column(db.DateTime, nullable=True)

    grupo = db.relationship('Grupo')
    criado_por = db.relationship('Usuario')
    presencas = db.relationship('PresencaAtividadeExtra', backref='atividade', lazy=True, cascade="all, delete-orphan")

    @property
    def fim_previsto(self):
        from datetime import timedelta
        return self.data_hora_inicio_prevista + timedelta(minutes=self.duracao_prevista_min or 60)


class PresencaAtividadeExtra(db.Model):
    __tablename__ = 'presenca_atividade_extra'
    id = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.Integer, db.ForeignKey('atividade_extra.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)
    total_minutos = db.Column(db.Integer, default=0)
    modalidade = db.Column(db.String(20), nullable=True)
    checkout_automatico = db.Column(db.Boolean, default=False)
    # Lançamento ESG gerado para quem não é Aluno (evita contar duas vezes)
    checkin_voluntariado_id = db.Column(db.Integer, db.ForeignKey('checkin_voluntariado.id'), nullable=True)

    usuario = db.relationship('Usuario')
    __table_args__ = (db.UniqueConstraint('atividade_id', 'usuario_id', name='uq_presenca_atividade_usuario'),)


# ==============================================================================
# TABELAS: Reuniões institucionais ITM × Aon (ata, participantes e encaminhamentos)
# Objetivo: nada corre por fora; todo alinhamento fica registrado na plataforma.
# ==============================================================================
reuniao_participante = db.Table('reuniao_participante',
    db.Column('reuniao_id', db.Integer, db.ForeignKey('reuniao_institucional.id'), primary_key=True),
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)


class ReuniaoInstitucional(db.Model):
    __tablename__ = 'reuniao_institucional'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)  # hora local
    duracao_minutos = db.Column(db.Integer, default=60)
    modalidade = db.Column(db.String(20), default='Online')
    local_ou_link = db.Column(db.String(500), nullable=True)
    pauta = db.Column(db.Text, nullable=True)
    deliberacoes = db.Column(db.Text, nullable=True)
    participantes_externos = db.Column(db.Text, nullable=True)  # "Nome – Instituição", um por linha
    contar_voluntariado = db.Column(db.Boolean, default=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey('demanda_institucional.id'), nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    participantes = db.relationship('Usuario', secondary=reuniao_participante, lazy='subquery')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id])
    demanda = db.relationship('DemandaInstitucional')
    encaminhamentos = db.relationship('EncaminhamentoReuniao', backref='reuniao', lazy=True,
                                      cascade="all, delete-orphan", order_by='EncaminhamentoReuniao.prazo')


class EncaminhamentoReuniao(db.Model):
    __tablename__ = 'encaminhamento_reuniao'
    id = db.Column(db.Integer, primary_key=True)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    prazo = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='Pendente')  # Pendente / Concluído
    data_conclusao = db.Column(db.DateTime, nullable=True)

    responsavel = db.relationship('Usuario')


# ==============================================================================
# BANCA DE AVALIAÇÃO DO TCC (agenda, avaliadores, entregas, notas por avaliador)
# Datas e horas da banca em hora local, como digitadas pela coordenação.
# ==============================================================================
banca_avaliador = db.Table('banca_avaliador',
    db.Column('banca_id', db.Integer, db.ForeignKey('banca.id'), primary_key=True),
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuario.id'), primary_key=True)
)


class Banca(db.Model):
    __tablename__ = 'banca'
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False, unique=True)
    data_hora = db.Column(db.DateTime, nullable=False)
    local = db.Column(db.String(200), nullable=True)
    link_sala = db.Column(db.String(500), nullable=True)
    duracao_apresentacao_min = db.Column(db.Integer, default=15)
    duracao_perguntas_min = db.Column(db.Integer, default=10)
    status = db.Column(db.String(20), default='Agendada')  # Agendada / Remarcada / Realizada / Cancelada
    prazo_entrega_escrito = db.Column(db.DateTime, nullable=True)
    prazo_entrega_slides = db.Column(db.DateTime, nullable=True)
    prazo_leitura_avaliadores = db.Column(db.DateTime, nullable=True)
    horas_antes_formulario = db.Column(db.Integer, default=24)
    anonimizar_feedback = db.Column(db.Boolean, default=True)
    encerrada_em = db.Column(db.DateTime, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    # Cronômetro compartilhado (sala do avaliador e telão dos jovens)
    cron_fase = db.Column(db.String(20), nullable=True)  # apresentacao / perguntas
    cron_inicio = db.Column(db.DateTime, nullable=True)  # UTC do último "iniciar/retomar"
    cron_acumulado_seg = db.Column(db.Integer, default=0)
    cron_pausado = db.Column(db.Boolean, default=True)
    tempo_real_apresentacao_seg = db.Column(db.Integer, nullable=True)
    tempo_real_perguntas_seg = db.Column(db.Integer, nullable=True)

    projeto = db.relationship('Projeto', backref=db.backref('banca', uselist=False))
    avaliadores = db.relationship('Usuario', secondary=banca_avaliador, lazy='subquery')
    historico_datas = db.relationship('HistoricoDataBanca', backref='banca', lazy=True,
                                      cascade="all, delete-orphan", order_by='HistoricoDataBanca.data_alteracao.desc()')

    @property
    def fim_previsto(self):
        from datetime import timedelta
        return self.data_hora + timedelta(minutes=(self.duracao_apresentacao_min or 15) + (self.duracao_perguntas_min or 10))


class HistoricoDataBanca(db.Model):
    __tablename__ = 'historico_data_banca'
    id = db.Column(db.Integer, primary_key=True)
    banca_id = db.Column(db.Integer, db.ForeignKey('banca.id'), nullable=False)
    data_anterior = db.Column(db.DateTime, nullable=False)
    data_nova = db.Column(db.DateTime, nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    alterado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_alteracao = db.Column(db.DateTime, default=datetime.utcnow)

    alterado_por = db.relationship('Usuario')


class EntregaTCC(db.Model):
    __tablename__ = 'entrega_tcc'
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    tipo = db.Column(db.String(40), nullable=False)  # 'Escrito final' / 'Slides da apresentação'
    arquivo = db.Column(db.String(255), nullable=False)  # nome salvo em uploads/tcc/
    nome_original = db.Column(db.String(255), nullable=True)
    versao = db.Column(db.Integer, default=1)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.now)
    observacao = db.Column(db.Text, nullable=True)
    entregue_no_prazo = db.Column(db.Boolean, default=True)

    projeto = db.relationship('Projeto', backref=db.backref('entregas', lazy=True, order_by='EntregaTCC.data_envio.desc()'))
    enviado_por = db.relationship('Usuario')


class AvaliacaoBanca(db.Model):
    __tablename__ = 'avaliacao_banca'
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    banca_id = db.Column(db.Integer, db.ForeignKey('banca.id'), nullable=True)
    avaliador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nota_escrita = db.Column(db.Float, nullable=True)
    justificativa_escrita = db.Column(db.Text, nullable=True)
    nota_apresentacao = db.Column(db.Float, nullable=True)
    nota_visual = db.Column(db.Float, nullable=True)
    justificativa_oral = db.Column(db.Text, nullable=True)
    feedback_jovens = db.Column(db.Text, nullable=True)
    etapa_escrita_concluida_em = db.Column(db.DateTime, nullable=True)
    etapa_oral_concluida_em = db.Column(db.DateTime, nullable=True)

    avaliador = db.relationship('Usuario')
    projeto = db.relationship('Projeto', backref=db.backref('avaliacoes_banca', lazy=True))
    __table_args__ = (db.UniqueConstraint('projeto_id', 'avaliador_id', name='uq_avaliacao_banca_projeto_avaliador'),)


class EnvioFormularioBanca(db.Model):
    __tablename__ = 'envio_formulario_banca'
    id = db.Column(db.Integer, primary_key=True)
    banca_id = db.Column(db.Integer, db.ForeignKey('banca.id'), nullable=False)
    avaliador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tipo = db.Column(db.String(20), default='formulario')  # formulario / lembrete_2h
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('banca_id', 'avaliador_id', 'tipo', name='uq_envio_formulario_banca'),)


# ==============================================================================
# CERTIFICADOS EMITIDOS (com horas e código público de verificação)
# ==============================================================================
class CertificadoEmitido(db.Model):
    __tablename__ = 'certificado_emitido'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(16), unique=True, nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    tipo = db.Column(db.String(40), nullable=False)  # Avaliador da Banca / Mentor / Jovem participante
    minutos_total = db.Column(db.Integer, default=0)
    detalhe_minutos = db.Column(db.Text, nullable=True)  # JSON: {"Leitura": 40, ...}
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = db.relationship('Usuario')
    projeto = db.relationship('Projeto')
    __table_args__ = (db.UniqueConstraint('usuario_id', 'projeto_id', 'tipo', name='uq_certificado_usuario_projeto_tipo'),)


# ==============================================================================
# REPOSITÓRIO DE TCCs (acervo interno e público) E MATERIAIS DE APOIO
# ==============================================================================
class TCCAcervo(db.Model):
    __tablename__ = 'tcc_acervo'
    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=True)  # vazio nos TCCs históricos importados
    titulo = db.Column(db.String(250), nullable=False)
    tema = db.Column(db.String(200), nullable=True)
    resumo = db.Column(db.Text, nullable=True)
    palavras_chave = db.Column(db.String(300), nullable=True)
    ano_edicao = db.Column(db.Integer, nullable=True)
    edicao = db.Column(db.String(120), nullable=True)
    arquivo_pdf = db.Column(db.String(255), nullable=True)  # em uploads/acervo/
    arquivo_slides = db.Column(db.String(255), nullable=True)
    nota_final = db.Column(db.Float, nullable=True)
    exibir_nota = db.Column(db.Boolean, default=False)
    autores_exibicao = db.Column(db.String(300), nullable=True)  # só primeiros nomes ou o nome do grupo (LGPD)
    visibilidade = db.Column(db.String(20), default='Interna')  # Interna / Pública
    autorizacao_publicacao = db.Column(db.Boolean, default=False)
    autorizado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    origem = db.Column(db.String(20), default='Plataforma')  # Plataforma / Histórico
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)
    downloads = db.Column(db.Integer, default=0)

    projeto = db.relationship('Projeto', backref=db.backref('acervo', uselist=False))
    autorizado_por = db.relationship('Usuario')


class MaterialApoio(db.Model):
    __tablename__ = 'material_apoio'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(80), default='Metodologia')
    arquivo = db.Column(db.String(255), nullable=False)  # em uploads/acervo/
    nome_original = db.Column(db.String(255), nullable=True)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    downloads = db.Column(db.Integer, default=0)

    enviado_por = db.relationship('Usuario')


# ==============================================================================
# MANUTENÇÃO (DB): agendamentos de backup e trilha de auditoria das alterações
# ==============================================================================
class AgendamentoBackup(db.Model):
    """Backup automático. Roda pelo tarefas_agendadas.py (de hora em hora) e também quando o app está em uso."""
    __tablename__ = 'agendamento_backup'
    id = db.Column(db.Integer, primary_key=True)
    frequencia = db.Column(db.String(20), nullable=False, default='Diário')  # Diário / Semanal / Mensal
    horario = db.Column(db.String(5), nullable=False, default='03:00')       # HH:MM (hora local do servidor)
    data_inicio = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Ativo')       # Ativo / Pausado
    retencao = db.Column(db.Integer, nullable=False, default=7)              # quantos arquivos deste agendamento manter
    pasta = db.Column(db.String(80), nullable=False, default='agendados')    # subpasta dentro de instance/backups
    ultima_execucao = db.Column(db.DateTime, nullable=True)
    proxima_execucao = db.Column(db.DateTime, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)

    criado_por = db.relationship('Usuario')


class AlteracaoAgendamentoBackup(db.Model):
    """Quem criou, editou, pausou, retomou, executou ou excluiu cada agendamento (fica mesmo após a exclusão)."""
    __tablename__ = 'alteracao_agendamento_backup'
    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(db.Integer, nullable=False)  # sem FK: o registro sobrevive à exclusão do agendamento
    acao = db.Column(db.String(30), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario')
