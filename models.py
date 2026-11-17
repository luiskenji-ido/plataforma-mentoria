# Importando as ferramentas necessárias para criar o banco de dados e gerenciar o login
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone, timedelta

from sqlalchemy.dialects.mysql import LONGTEXT

# A "ponte" entre o código Python e o banco de dados (SQLite, MySQL, PostgreSQL... conforme DATABASE_URL)
db = SQLAlchemy()

# Texto sem limite prático em qualquer banco: no MySQL o TEXT guarda só 64 KB, então lá ele vira LONGTEXT (4 GB).
TextoLongo = db.Text().with_variant(LONGTEXT(), 'mysql', 'mariadb')

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
    # Muda a cada logout: invalida cópias antigas do cookie de sessão (ver get_id e load_user no app.py)
    token_sessao = db.Column(db.String(64))
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo_usuario = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Ativo')
    tentativas_login = db.Column(db.Integer, default=0)
    tema = db.Column(db.String(20), default='claro')
    idioma = db.Column(db.String(10), default='pt')
    # Gráficos escolhidos no Painel Geral (JSON: [{fonte, tipo, cor}]); vazio = padrão do perfil
    preferencias_painel = db.Column(TextoLongo, nullable=True)
    # Perfil personalizado (herda de tipo_usuario e só restringe módulos); vazio = perfil padrão
    perfil_personalizado_id = db.Column(db.Integer, db.ForeignKey('perfil_personalizado.id'), nullable=True)
    perfil_personalizado = db.relationship('PerfilPersonalizado', foreign_keys=[perfil_personalizado_id])
    data_ultima_troca_senha = db.Column(db.DateTime, default=datetime.utcnow)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    criado_por = db.Column(db.String(100), default='Sistema')
    forcar_troca_senha = db.Column(db.Boolean, default=True)
    exibir_tour = db.Column(db.Boolean, default=True)
    # Como o jovem participa do programa: 'Presencial', 'Online' ou 'Híbrido'
    modalidade_participacao = db.Column(db.String(20), default='Presencial')
    # Aceita receber por e-mail os avisos da plataforma (o sino continua mostrando tudo)
    receber_email = db.Column(db.Boolean, default=True)
    # Último login (sinal de engajamento para o alerta de desengajamento)
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    perfil_aluno = db.Column(TextoLongo, nullable=True)
    objetivo_principal = db.Column(TextoLongo, nullable=True)
    expectativa_mentoria = db.Column(TextoLongo, nullable=True)
    
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
    motivo_desativacao = db.Column(TextoLongo, nullable=True)
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
    observacao = db.Column(TextoLongo, nullable=True)
    data_parecer_mentor = db.Column(db.DateTime, nullable=True)
    observacao_aluno = db.Column(TextoLongo, nullable=True)
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
    observacoes = db.Column(TextoLongo, nullable=True)
    # Ata digital estruturada do encontro (resumo das deliberações, fontes recomendadas e plano de ação)
    ata_resumo = db.Column(TextoLongo, nullable=True)
    ata_fontes = db.Column(TextoLongo, nullable=True)
    ata_plano_acao = db.Column(TextoLongo, nullable=True)  # um passo por linha
    ata_proximo_encontro = db.Column(db.Date, nullable=True)
    ata_registrada_em = db.Column(db.DateTime, nullable=True)
    ata_registrada_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    proximos_passos_enviados_em = db.Column(db.DateTime, nullable=True)

# ---------------------------------------------------------------------------
# 5. TABELA DE FEEDBACK DAS SESSÕES
# ---------------------------------------------------------------------------
class FeedbackSessao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sessao_id = db.Column(db.Integer, db.ForeignKey('sessao_mentoria.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    papel_autor = db.Column(db.String(20), nullable=False)
    comentario = db.Column(TextoLongo, nullable=False)
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
    
    mensagem = db.Column(TextoLongo, nullable=False)
    resposta = db.Column(TextoLongo, nullable=True)
    
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
def _gerar_token_sessao():
    import secrets
    return secrets.token_hex(16)


def _get_id_com_token(self):
    if not self.token_sessao:
        self.token_sessao = _gerar_token_sessao()
        db.session.commit()
    return f"{self.id}:{self.token_sessao}"


Usuario.get_id = _get_id_com_token


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
    motivo = db.Column(TextoLongo, nullable=False)
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
    detalhes = db.Column(TextoLongo)
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
    descricao = db.Column(TextoLongo, nullable=True)
    
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
    descricao = db.Column(TextoLongo, nullable=True)
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
    
    observacoes = db.Column(TextoLongo, nullable=True)
    
    # Campos exclusivos para a equipe de gestão validar depois
    validado_admin = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    observacoes_admin = db.Column(TextoLongo, nullable=True)
    
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
    observacoes_mentor = db.Column(TextoLongo, nullable=True)
    
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
    logo_arquivo = db.Column(db.String(255), nullable=True)  # logo do parceiro B2B (uploads/logos), usado no certificado
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
# 20. MÓDULO 4: BANCA AVALIADORA (B2B / instituição) E VOLUNTARIADO DE LEITURA
# ==============================================================================

class PerfilAvaliador(db.Model):
    __tablename__ = 'perfil_avaliador'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Dados Corporativos do Executivo
    empresa_origem = db.Column(db.String(150), default="Parceiro B2B")
    area_atuacao = db.Column(db.String(150))
    curriculo_minibio = db.Column(TextoLongo)
    # Adequações instituição/B2B: ficha do executivo para a apresentação final
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
    
    observacoes = db.Column(TextoLongo)
    # Adequações instituição/B2B: com qual grupo foi o extra e se a hora é Regular ou Extra (fora do cronograma)
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
    
    pergunta_feita = db.Column(TextoLongo, nullable=False)
    resposta_jovens = db.Column(TextoLongo) # Resumo de como os jovens se saíram na resposta

    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    banca_id = db.Column(db.Integer, db.ForeignKey('banca.id'), nullable=True)
    ordem = db.Column(db.Integer, default=0)
    avaliador = db.relationship('Usuario')


# ==============================================================================
# 21. MÓDULO 5: PORTAL DE DEMANDAS INSTITUCIONAIS (TICKETS INSTITUIÇÃO & B2B)
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
    descricao = db.Column(TextoLongo, nullable=False)
    
    # Resolução (Preenchido pelos Gestores/Admins)
    resposta_oficial = db.Column(TextoLongo, nullable=True) 
    
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
    texto = db.Column(TextoLongo, nullable=False)
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
    conteudo_html = db.Column(TextoLongo, nullable=False)
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
    mensagem = db.Column(TextoLongo, nullable=True)
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
    motivo = db.Column(TextoLongo, nullable=False)
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
# TABELAS: Reuniões institucionais instituição × B2B (ata, participantes e encaminhamentos)
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
    pauta = db.Column(TextoLongo, nullable=True)
    deliberacoes = db.Column(TextoLongo, nullable=True)
    participantes_externos = db.Column(TextoLongo, nullable=True)  # "Nome – Instituição", um por linha
    contar_voluntariado = db.Column(db.Boolean, default=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey('demanda_institucional.id'), nullable=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True)  # parceiro B2B da reunião
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Convite por e-mail (.ics): a sequência sobe a cada reenvio para as agendas trocarem o evento em vez de duplicar
    convite_sequencia = db.Column(db.Integer, default=0)
    convite_enviado_em = db.Column(db.DateTime, nullable=True)
    convite_enviado_via = db.Column(db.String(20), nullable=True)  # Gmail / SMTP
    convite_destinatarios = db.Column(TextoLongo, nullable=True)  # e-mails convidados no último envio, um por linha
    # Convite como evento do Outlook (Microsoft 365): o evento fica na agenda de quem organizou e é atualizado ao remarcar
    outlook_evento_id = db.Column(db.String(300), nullable=True)
    outlook_organizador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    # Reunião de Alinhamento: tipo, pontos levantados pelo parceiro B2B, gravação e presença real
    tipo = db.Column(db.String(30), default='Alinhamento')  # reuniões antigas ficam sem tipo (= Institucional)
    pontos_parceiro = db.Column(TextoLongo, nullable=True)  # falhas/pontos que o parceiro B2B trouxe para o programa
    link_gravacao = db.Column(db.String(500), nullable=True)
    # Horas ESG pelo check-in/out real; reuniões antigas (NULL) continuam com a duração prevista para todos
    controle_presenca = db.Column(db.Boolean, default=True)

    participantes = db.relationship('Usuario', secondary=reuniao_participante, lazy='subquery')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id])
    demanda = db.relationship('DemandaInstitucional')
    empresa = db.relationship('Empresa')
    encaminhamentos = db.relationship('EncaminhamentoReuniao', backref='reuniao', lazy=True,
                                      cascade="all, delete-orphan", order_by='EncaminhamentoReuniao.prazo')
    alteracoes = db.relationship('ReuniaoAlteracao', backref='reuniao', lazy=True, cascade="all, delete-orphan",
                                 order_by='ReuniaoAlteracao.criado_em.desc()')
    presencas = db.relationship('PresencaReuniao', backref='reuniao', lazy=True, cascade="all, delete-orphan",
                                order_by='PresencaReuniao.check_in')
    feedbacks = db.relationship('FeedbackReuniao', backref='reuniao', lazy=True, cascade="all, delete-orphan",
                                order_by='FeedbackReuniao.criado_em')

    @property
    def fim_previsto(self):
        return self.data_hora + timedelta(minutes=self.duracao_minutos or 0)


class ReuniaoAlteracao(db.Model):
    """Histórico de remarcações e mudanças de modalidade/local (com o motivo), avisado aos participantes."""
    __tablename__ = 'reuniao_alteracao'
    id = db.Column(db.Integer, primary_key=True)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    mudancas = db.Column(TextoLongo, nullable=False)  # "Data: 03/12 14:30 → 05/12 10:00", uma por linha
    motivo = db.Column(TextoLongo, nullable=True)

    autor = db.relationship('Usuario')


class PresencaReuniao(db.Model):
    """Check-in/check-out real de cada participante interno (base das horas ESG da reunião)."""
    __tablename__ = 'presenca_reuniao'
    id = db.Column(db.Integer, primary_key=True)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)
    total_minutos = db.Column(db.Integer, default=0)
    modalidade = db.Column(db.String(20), nullable=True)
    checkout_automatico = db.Column(db.Boolean, default=False)
    registro_manual = db.Column(db.Boolean, default=False)  # lançado pela gestão (ex.: esqueceu o check-in)
    registrado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    registrado_por = db.relationship('Usuario', foreign_keys=[registrado_por_id])
    __table_args__ = (db.UniqueConstraint('reuniao_id', 'usuario_id', name='uq_presenca_reuniao_usuario'),)


class FeedbackReuniao(db.Model):
    """Avaliação da reunião por participante (nota 1 a 5 e comentário), uma por pessoa."""
    __tablename__ = 'feedback_reuniao'
    id = db.Column(db.Integer, primary_key=True)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(TextoLongo, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    usuario = db.relationship('Usuario')
    __table_args__ = (db.UniqueConstraint('reuniao_id', 'usuario_id', name='uq_feedback_reuniao_usuario'),)


class EncaminhamentoReuniao(db.Model):
    __tablename__ = 'encaminhamento_reuniao'
    id = db.Column(db.Integer, primary_key=True)
    reuniao_id = db.Column(db.Integer, db.ForeignKey('reuniao_institucional.id'), nullable=False)
    descricao = db.Column(TextoLongo, nullable=False)
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
    motivo = db.Column(TextoLongo, nullable=False)
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
    observacao = db.Column(TextoLongo, nullable=True)
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
    justificativa_escrita = db.Column(TextoLongo, nullable=True)
    nota_apresentacao = db.Column(db.Float, nullable=True)
    nota_visual = db.Column(db.Float, nullable=True)
    justificativa_oral = db.Column(TextoLongo, nullable=True)
    feedback_jovens = db.Column(TextoLongo, nullable=True)
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
    detalhe_minutos = db.Column(TextoLongo, nullable=True)  # JSON: {"Leitura": 40, ...}
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
    resumo = db.Column(TextoLongo, nullable=True)
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
    descricao = db.Column(TextoLongo, nullable=True)
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
    detalhes = db.Column(TextoLongo, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario')


class ManutencaoBanco(db.Model):
    """Histórico das ações do DBA (ANALYZE, VACUUM, índices, integridade), sempre com backup antes das alterações."""
    __tablename__ = 'manutencao_banco_dados'
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(30), nullable=False)          # otimizar / vacuum / indices / integridade
    status = db.Column(db.String(20), nullable=False)        # Concluída / Falha
    detalhes = db.Column(TextoLongo, nullable=True)
    duracao_seg = db.Column(db.Float, nullable=True)
    backup_arquivo = db.Column(db.String(255), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario')


# ==============================================================================
# PERFIS PERSONALIZADOS (Administração › Perfis de acesso)
# ==============================================================================
class PerfilPersonalizado(db.Model):
    """Perfil criado pela gestão. Herda as permissões de um perfil-base e liga/desliga módulos."""
    __tablename__ = 'perfil_personalizado'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    descricao = db.Column(TextoLongo, nullable=True)
    perfil_base = db.Column(db.String(30), nullable=False)        # um dos perfis do sistema (tipo_usuario)
    modulos = db.Column(TextoLongo, nullable=False, default='[]')     # JSON: chaves de perfis_acesso.MODULOS
    ativo = db.Column(db.Boolean, default=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now)

    def lista_modulos(self):
        import json
        try:
            return list(json.loads(self.modulos or '[]'))
        except ValueError:
            return []


class HistoricoPerfilAcesso(db.Model):
    """Quem criou, alterou, desativou ou excluiu cada perfil personalizado (fica após a exclusão)."""
    __tablename__ = 'historico_perfil_acesso'
    id = db.Column(db.Integer, primary_key=True)
    perfil_id = db.Column(db.Integer, nullable=False)
    acao = db.Column(db.String(30), nullable=False)
    detalhes = db.Column(TextoLongo, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


# ==============================================================================
# APRENDIZADOS DOS AGENTES (governança e compliance)
# ==============================================================================
class AprendizadoAgente(db.Model):
    """Conhecimento que o Agente Gerente Técnico distribui aos agentes de teste."""
    __tablename__ = 'aprendizado_agente'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)      # APR-0001
    titulo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)                     # perfil_novo, perfil_alterado, perfil_removido, rota_nova, rota_removida, linha_base, referencia_externa
    descricao = db.Column(TextoLongo, nullable=True)
    conteudo = db.Column(TextoLongo, nullable=False, default='{}')         # JSON usado pelos agentes
    agentes_destino = db.Column(TextoLongo, nullable=False, default='["todos"]')
    origem = db.Column(db.String(60), nullable=False)                   # Detecção interna / Fonte oficial
    fonte_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Aplicado')  # Aplicado / Pendente / Revogado / Rejeitado
    assinatura = db.Column(db.String(64), nullable=False)               # SHA-256 do conteúdo (integridade)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    aplicado_em = db.Column(db.DateTime, nullable=True)
    revisado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    revisado_em = db.Column(db.DateTime, nullable=True)
    motivo = db.Column(TextoLongo, nullable=True)
    vezes_consumido = db.Column(db.Integer, default=0)

    revisado_por = db.relationship('Usuario', foreign_keys=[revisado_por_id])


class EventoAprendizado(db.Model):
    """Trilha de auditoria dos aprendizados (não é apagada pela limpeza: guarda o retrato do que foi removido)."""
    __tablename__ = 'evento_aprendizado'
    id = db.Column(db.Integer, primary_key=True)
    aprendizado_codigo = db.Column(db.String(20), nullable=True)
    acao = db.Column(db.String(40), nullable=False)
    detalhes = db.Column(TextoLongo, nullable=True)
    agente = db.Column(db.String(60), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


class FonteConfiavel(db.Model):
    """Domínios oficiais que o Agente Gerente Técnico pode consultar para novos aprendizados."""
    __tablename__ = 'fonte_confiavel'
    id = db.Column(db.Integer, primary_key=True)
    dominio = db.Column(db.String(120), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    ativa = db.Column(db.Boolean, default=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)


class EstadoConhecimento(db.Model):
    """Retrato da plataforma que o Gerente Técnico usa para perceber mudanças (chave → JSON)."""
    __tablename__ = 'estado_conhecimento'
    chave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(TextoLongo, nullable=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now)


# ==============================================================================
# JOVENS DESISTENTES: pedido (mentor/gestão) → confirmação da gestão → saída do grupo e da turma, com histórico
# Os vínculos de antes ficam guardados (JSON) para a reativação devolver o jovem aos mesmos grupos, turmas e mentores.
# ==============================================================================
class Desistencia(db.Model):
    __tablename__ = 'desistencia'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    categoria = db.Column(db.String(40), nullable=False)           # Pessoal, Estudos, Trabalho, Saúde, Mudança, Sem interesse, Outro
    motivo = db.Column(TextoLongo, nullable=False)
    data_saida = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Solicitada')         # Solicitada / Confirmada / Recusada / Revertida
    solicitado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    solicitado_em = db.Column(db.DateTime, default=datetime.utcnow)
    decidido_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    decidido_em = db.Column(db.DateTime, nullable=True)
    observacao_decisao = db.Column(TextoLongo, nullable=True)
    vinculos = db.Column(TextoLongo, nullable=True)                   # JSON {"grupos": [...], "turmas": [...], "mentores": [...]}
    empresas = db.Column(TextoLongo, nullable=True)                   # JSON [ids] das empresas parceiras do jovem na saída
    revertido_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    revertido_em = db.Column(db.DateTime, nullable=True)
    # Mentor desistente: quem assumiu os jovens, os grupos e as turmas dele
    substituto_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    substituto = db.relationship('Usuario', foreign_keys=[substituto_id])
    solicitado_por = db.relationship('Usuario', foreign_keys=[solicitado_por_id])
    decidido_por = db.relationship('Usuario', foreign_keys=[decidido_por_id])
    revertido_por = db.relationship('Usuario', foreign_keys=[revertido_por_id])


# ==============================================================================
# OCORRÊNCIAS: o mentor (B2B ou da instituição) relata o que observou sobre o jovem, as ações tomadas e quem deve dar retorno.
# Cada ocorrência tem prazo de resposta; os sinais (amarelo/vermelho) mostram retornos pendentes para todos que acompanham.
# ==============================================================================
class Ocorrencia(db.Model):
    __tablename__ = 'ocorrencia'
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    registrado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    categoria = db.Column(db.String(40), nullable=False)           # Progresso, Comportamento, Frequência, Entregas, Comunicação, Outro
    contexto = db.Column(db.String(40), nullable=False)            # Sala de aula, Palestra, Mentoria, Banca, Online, Outro
    gravidade = db.Column(db.String(10), default='Média')          # Baixa / Média / Alta
    descricao = db.Column(TextoLongo, nullable=False)
    acoes = db.Column(TextoLongo, nullable=True)                      # ações já tomadas por quem registrou
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    prazo_resposta = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Aberta')            # Aberta / Em tratativa / Resolvida
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolvido_em = db.Column(db.DateTime, nullable=True)
    aviso_atraso_enviado = db.Column(db.Boolean, default=False)

    aluno = db.relationship('Usuario', foreign_keys=[aluno_id])
    registrado_por = db.relationship('Usuario', foreign_keys=[registrado_por_id])
    responsavel = db.relationship('Usuario', foreign_keys=[responsavel_id])
    registros = db.relationship('OcorrenciaRegistro', backref='ocorrencia', lazy=True, cascade='all, delete-orphan',
                                order_by='OcorrenciaRegistro.criado_em')


class OcorrenciaRegistro(db.Model):
    """Linha do tempo da ocorrência: retornos (feedback), ações tomadas, comentários e mudanças de status."""
    __tablename__ = 'ocorrencia_registro'
    id = db.Column(db.Integer, primary_key=True)
    ocorrencia_id = db.Column(db.Integer, db.ForeignKey('ocorrencia.id'), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tipo = db.Column(db.String(20), default='Comentário')          # Retorno / Ação / Comentário / Status
    texto = db.Column(TextoLongo, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    autor = db.relationship('Usuario')


# ==============================================================================
# PARÂMETROS DAS REGRAS DE NEGÓCIO (frequência MEC, notas, banca, senhas...)
# O catálogo e os valores-padrão ficam em regras_negocio.py; aqui só o valor escolhido pela gestão
# e as regras novas criadas por ela. Toda mudança fica no histórico (quem, quando, de → para, motivo).
# ==============================================================================
class ParametroRegra(db.Model):
    __tablename__ = 'parametro_regra'
    chave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(TextoLongo, nullable=False)                      # guardado como texto; o tipo vem do catálogo
    personalizado = db.Column(db.Boolean, default=False)            # regra nova criada pela gestão
    nome = db.Column(db.String(150), nullable=True)                 # só para as personalizadas
    descricao = db.Column(TextoLongo, nullable=True)
    tipo = db.Column(db.String(20), nullable=True)                  # inteiro / decimal / texto / sim_nao
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    atualizado_por = db.relationship('Usuario')


class HistoricoParametro(db.Model):
    __tablename__ = 'historico_parametro'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(60), nullable=False, index=True)
    acao = db.Column(db.String(30), nullable=False)                 # Alterado / Restaurado / Criado / Excluído
    valor_anterior = db.Column(TextoLongo, nullable=True)
    valor_novo = db.Column(TextoLongo, nullable=True)
    motivo = db.Column(TextoLongo, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')


# ==============================================================================
# CONTA NOVA NASCE LIMPA
# O SQLite reaproveita o id do último usuário apagado. Se alguma rotina apagou um usuário sem apagar os dados ligados
# a ele (perguntas de segurança, termo, histórico de senhas…), a conta nova herdaria esses dados — e quem conhecesse
# as respostas antigas recuperaria a conta nova. Logo após inserir um usuário, apagamos qualquer linha órfã que já
# aponte para o id recém-criado (nenhuma linha legítima pode existir antes do próprio usuário).
# ==============================================================================
from sqlalchemy import event as _evento


@_evento.listens_for(Usuario, 'after_insert')
def _conta_nova_sem_heranca(mapper, conexao, usuario):
    for tabela in list(db.metadata.tables.values()):
        for fk in tabela.foreign_keys:
            if fk.column.table.name == 'usuario' and tabela.name != 'usuario':
                conexao.execute(tabela.delete().where(fk.parent == usuario.id))


# ==============================================================================
# AVALIAÇÕES 360° E MICROAVALIAÇÕES (jovem ↔ mentor, gestores da instituição/B2B e o programa)
# ==============================================================================
class CicloAvaliacao(db.Model):
    """Período de avaliação: '360' (todos avaliam todos, com mais critérios) ou 'Micro' (quinzenal, jovem ↔ mentor)."""
    __tablename__ = 'ciclo_avaliacao'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default='360')
    inicio = db.Column(db.Date, nullable=False)
    fim = db.Column(db.Date, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True)  # vazio = todos os parceiros
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # vazio = criado pela rotina automática
    criado_em = db.Column(db.DateTime, default=datetime.now)
    encerrado_em = db.Column(db.DateTime, nullable=True)

    empresa = db.relationship('Empresa')
    criado_por = db.relationship('Usuario')
    respostas = db.relationship('RespostaAvaliacao', backref='ciclo', lazy=True, cascade="all, delete-orphan")

    def aberto(self, hoje=None):
        hoje = hoje or datetime.now().date()
        return self.encerrado_em is None and self.inicio <= hoje <= self.fim


class RespostaAvaliacao(db.Model):
    """Uma avaliação de uma pessoa (ou do programa / da gestão da instituição) num ciclo, com nota de 1 a 5 por critério."""
    __tablename__ = 'resposta_avaliacao'
    id = db.Column(db.Integer, primary_key=True)
    ciclo_id = db.Column(db.Integer, db.ForeignKey('ciclo_avaliacao.id'), nullable=False)
    avaliador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    alvo_tipo = db.Column(db.String(20), nullable=False)  # Mentor / Jovem / Gestor B2B / Gestão {apelido} / Programa
    avaliado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # vazio para Programa e Gestão {apelido}
    notas = db.Column(TextoLongo, nullable=False)  # JSON {critério: nota}
    media = db.Column(db.Float, nullable=False)
    comentario = db.Column(TextoLongo, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    avaliador = db.relationship('Usuario', foreign_keys=[avaliador_id])
    avaliado = db.relationship('Usuario', foreign_keys=[avaliado_id])


class CredencialAgente(db.Model):
    """Credenciais dos agentes de teste e das IAs (cifradas; só o Administrador cadastra; o valor nunca volta para a tela)."""
    __tablename__ = 'credencial_agente'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(60), unique=True, nullable=False)
    valor_cifrado = db.Column(TextoLongo, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    atualizado_por = db.relationship('Usuario')


class ContaConectada(db.Model):
    """Conta externa conectada pela própria pessoa (hoje: Microsoft 365). Tokens cifrados; a senha nunca passa pela plataforma."""
    __tablename__ = 'conta_conectada'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    provedor = db.Column(db.String(20), nullable=False, default='microsoft')
    email = db.Column(db.String(200), nullable=True)
    nome = db.Column(db.String(150), nullable=True)
    acesso_cifrado = db.Column(TextoLongo, nullable=True)
    renovacao_cifrada = db.Column(TextoLongo, nullable=True)
    expira_em = db.Column(db.DateTime, nullable=True)
    conectado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario')
    __table_args__ = (db.UniqueConstraint('usuario_id', 'provedor', name='uq_conta_conectada_usuario_provedor'),)


# ==============================================================================
# ASSISTENTE DA PLATAFORMA (chat): base de conhecimento e conversas
# ==============================================================================
class FonteConhecimento(db.Model):
    """Uma fonte da base do Assistente: o conhecimento dos Agentes gerentes (sincronizado sozinho) ou um documento
    enviado na tela (PRD, PTD, DTD ou outro). Cada nova versão de um documento desativa a anterior, que fica no histórico."""
    __tablename__ = 'fonte_conhecimento'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)               # GERENTES / PRD / PTD / DTD / OUTRO
    titulo = db.Column(db.String(200), nullable=False)
    versao = db.Column(db.Integer, nullable=False, default=1)
    descricao = db.Column(TextoLongo, nullable=True)
    arquivo_nome = db.Column(db.String(255), nullable=True)       # nome original do arquivo enviado
    arquivo_caminho = db.Column(db.String(500), nullable=True)    # caminho dentro de uploads/base_conhecimento
    hash_conteudo = db.Column(db.String(64), nullable=True)       # SHA-256 do texto extraído (detecta mudança)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    total_trechos = db.Column(db.Integer, nullable=False, default=0)
    total_caracteres = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    criado_por = db.relationship('Usuario')
    trechos = db.relationship('TrechoConhecimento', backref='fonte', lazy='dynamic', cascade='all, delete-orphan')


class TrechoConhecimento(db.Model):
    """Pedaço de uma fonte (seção ou parte de seção) usado na busca e citado nas respostas."""
    __tablename__ = 'trecho_conhecimento'
    id = db.Column(db.Integer, primary_key=True)
    fonte_id = db.Column(db.Integer, db.ForeignKey('fonte_conhecimento.id'), nullable=False, index=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    secao = db.Column(db.String(300), nullable=True)
    texto = db.Column(TextoLongo, nullable=False)


class ConversaChat(db.Model):
    __tablename__ = 'conversa_chat'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False, default='Nova conversa')
    criada_em = db.Column(db.DateTime, default=datetime.now)
    atualizada_em = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario')
    mensagens = db.relationship('MensagemChat', backref='conversa', lazy='dynamic', cascade='all, delete-orphan',
                                order_by='MensagemChat.id')


class MensagemChat(db.Model):
    __tablename__ = 'mensagem_chat'
    id = db.Column(db.Integer, primary_key=True)
    conversa_id = db.Column(db.Integer, db.ForeignKey('conversa_chat.id'), nullable=False, index=True)
    papel = db.Column(db.String(12), nullable=False)              # usuario / assistente
    texto = db.Column(TextoLongo, nullable=False)
    fontes = db.Column(TextoLongo, nullable=True)                    # JSON: trechos citados [{n, fonte, tipo, versao, secao}]
    modo = db.Column(db.String(12), nullable=True)                # ia / offline
    modelo = db.Column(db.String(60), nullable=True)
    tokens_entrada = db.Column(db.Integer, nullable=True)
    tokens_saida = db.Column(db.Integer, nullable=True)
    custo_usd = db.Column(db.Float, nullable=True)
    chave_cache = db.Column(db.String(64), nullable=True, index=True)  # pergunta + idioma + versão da base (reaproveita a resposta)
    criada_em = db.Column(db.DateTime, default=datetime.now, index=True)


# ==============================================================================
# PROVEDORES DE IA: escolha de modelos por uso, preços e consumo (teto mensal)
# ==============================================================================
class ConfiguracaoIA(db.Model):
    """Configuração dos provedores de IA (JSON por chave): 'uso:<uso>' = ordem dos modelos; 'precos'; 'modelos_extras'."""
    __tablename__ = 'configuracao_ia'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(60), unique=True, nullable=False)
    valor = db.Column(TextoLongo, nullable=False, default='{}')
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    atualizado_por = db.relationship('Usuario')


class UsoIA(db.Model):
    """Cada chamada a uma IA (com sucesso ou não): base do gasto do mês e do teto."""
    __tablename__ = 'uso_ia'
    id = db.Column(db.Integer, primary_key=True)
    quando = db.Column(db.DateTime, default=datetime.now, index=True)
    uso = db.Column(db.String(30), nullable=False)            # assistente / acompanhamento / orquestrador
    provedor = db.Column(db.String(20), nullable=False)       # claude / gemini
    modelo = db.Column(db.String(80), nullable=False)
    tokens_entrada = db.Column(db.Integer, nullable=False, default=0)
    tokens_saida = db.Column(db.Integer, nullable=False, default=0)
    custo_usd = db.Column(db.Float, nullable=False, default=0.0)
    sucesso = db.Column(db.Boolean, nullable=False, default=True)
    motivo = db.Column(db.String(300), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)


# ==============================================================================
# IDENTIDADE DA INSTITUIÇÃO (uma linha só): nome, apelido dos botões, plataforma, logo e assinatura
# ==============================================================================
class IdentidadeInstituicao(db.Model):
    """Quem opera esta instalação. Cada cliente tem a sua instalação e preenche aqui a própria identidade
    (Administração › Sistema › Identidade da instituição). As telas leem estes campos em vez de nomes fixos."""
    __tablename__ = 'identidade_instituicao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)                   # nome completo da instituição
    apelido = db.Column(db.String(30), nullable=False)                 # sigla ou nome curto, usado em botões e rótulos
    plataforma = db.Column(db.String(120), nullable=False)             # nome do programa ou da plataforma
    logo_arquivo = db.Column(db.String(255), nullable=True)
    site = db.Column(db.String(300), nullable=True)
    email_contato = db.Column(db.String(150), nullable=True)
    cargo_assinatura = db.Column(db.String(120), nullable=True)        # quem assina o certificado pela instituição
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    atualizado_por = db.relationship('Usuario')
