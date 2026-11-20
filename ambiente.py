# -*- coding: utf-8 -*-
"""
AMBIENTE E COMPATIBILIDADE — onde a plataforma está publicada e o que funciona aqui
=====================================================================================
Cada cliente tem a própria instalação e escolhe, no instalador (instalar.py), a hospedagem e o banco:

  Hospedagem (HOSPEDAGEM no .env)              Tipo
  servidor          Servidor próprio (Linux)     máquina virtual: tudo funciona
  aws_vm / gcp_vm / azure_vm                     máquina virtual na nuvem: tudo funciona
  aws_conteiner / gcp_conteiner / azure_conteiner  contêiner: disco apagado a cada reinício, salvo com volume montado
  pythonanywhere    PythonAnywhere               hospedagem gerenciada: sem SQL Server e sem navegador para os agentes
  computador        Desenvolvimento

  Banco (DATABASE_URL): SQLite, MySQL/MariaDB, PostgreSQL ou SQL Server (banco_config.py).

Cada recurso confere o que precisa (driver do banco, ferramenta de backup, disco que não se apaga, navegador
Chromium, Git, processos em segundo plano, tarefas agendadas, e-mail, Google, Microsoft 365, chaves de IA).
O que falta DESLIGA o recurso com o motivo e como ligar: nada quebra em silêncio. A tela fica em
Administração › Sistema › Ambiente e compatibilidade; as rotas que dependem de um recurso consultam disponivel().

Pastas de backup: BACKUP_DIR (padrão por hospedagem, gravado pelo instalador; sem ele, instance/backups) e, opcional,
BACKUP_DIR_EXTERNO, uma segunda pasta fora do servidor (disco de rede, volume da nuvem ou pasta sincronizada com o
rclone) que recebe uma cópia de cada backup.
"""
import importlib.util
import os
import shutil
import sys
import time
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))

HOSPEDAGENS = {
    'servidor': ('Servidor próprio (Linux)', 'vm'),
    'aws_vm': ('AWS · máquina virtual (EC2 / Lightsail / Elastic Beanstalk)', 'vm'),
    'gcp_vm': ('GCP · máquina virtual (Compute Engine)', 'vm'),
    'azure_vm': ('Azure · máquina virtual', 'vm'),
    'aws_conteiner': ('AWS · contêiner (App Runner / ECS / Lambda)', 'conteiner'),
    'gcp_conteiner': ('GCP · contêiner (Cloud Run)', 'conteiner'),
    'azure_conteiner': ('Azure · contêiner (App Service / Container Apps)', 'conteiner'),
    'pythonanywhere': ('PythonAnywhere', 'gerenciada'),
    'computador': ('Computador de desenvolvimento', 'computador'),
}

BANCOS = {
    'sqlite': {'nome': 'SQLite', 'driver': None, 'pip': None, 'backup': 'interno', 'extensao': '.db',
               'nota': 'Arquivo único: bom para um servidor pequeno e para testes.'},
    'mysql': {'nome': 'MySQL / MariaDB', 'driver': 'pymysql', 'pip': 'PyMySQL', 'backup': 'mysqldump', 'extensao': '.sql.gz',
              'apt': 'mysql-client', 'nota': 'Recomendado para produção num servidor Linux.'},
    'postgresql': {'nome': 'PostgreSQL', 'driver': 'psycopg', 'pip': 'psycopg[binary]', 'backup': 'pg_dump', 'extensao': '.dump',
                   'apt': 'postgresql-client', 'nota': 'Alternativa ao MySQL; muito usada como banco gerenciado nas nuvens.'},
    'mssql': {'nome': 'SQL Server', 'driver': 'pyodbc', 'pip': 'pyodbc', 'backup': None, 'extensao': None,
              'apt': 'msodbcsql18', 'nota': 'Precisa do ODBC Driver 18 da Microsoft. O backup fica a cargo do próprio '
                                            'SQL Server (ele grava no disco do servidor do banco) ou do Azure.'},
}

# Bancos possíveis em cada tipo de hospedagem (o instalador só oferece estes)
BANCOS_POR_TIPO = {
    'vm': ['mysql', 'postgresql', 'mssql', 'sqlite'],
    'conteiner': ['mysql', 'postgresql', 'mssql'],          # banco gerenciado da nuvem; SQLite se perderia com o disco
    'gerenciada': ['mysql', 'postgresql', 'sqlite'],        # PythonAnywhere: MySQL incluso, PostgreSQL pago, sem SQL Server
    'computador': ['sqlite', 'mysql', 'postgresql', 'mssql'],
}

# Pasta padrão dos backups em cada tipo de hospedagem (subpastas diario, semanal, mensal e manuais)
PASTA_BACKUP_PADRAO = {
    'vm': '/var/backups/mentoria',
    'conteiner': '/dados/backups',                          # volume montado (EFS, Filestore / Cloud Storage, Azure Files)
    'gerenciada': '~/backups/mentoria',
    'computador': '',                                       # vazio = instance/backups
}
# Agendamentos criados na instalação: (frequência, horário, subpasta, retenção)
AGENDAMENTOS_PADRAO = [('Diário', '02:30', 'diario', 7), ('Semanal', '03:00', 'semanal', 4), ('Mensal', '03:30', 'mensal', 12)]

# O que funciona em cada tipo de hospedagem (texto da tela e do instalador): ligado / limitado / desligado
MATRIZ = [
    # recurso,                                  vm,          conteiner,                                   gerenciada (PythonAnywhere)
    ('Telas, cadastros, relatórios e certificados', ('ligado', ''), ('ligado', ''), ('ligado', '')),
    ('Arquivos enviados, logos e documentos',   ('ligado', ''), ('limitado', 'só com volume montado em /app/uploads e /app/instance'), ('ligado', '')),
    ('Backups agendados',                       ('ligado', ''), ('limitado', 'use o backup do banco gerenciado; com volume, também o da plataforma'), ('ligado', 'tarefa agendada na aba Tasks')),
    ('Lembretes e avisos automáticos',          ('ligado', 'timer do systemd'), ('limitado', 'agendador da nuvem chamando tarefas_agendadas.py'), ('ligado', 'aba Tasks')),
    ('E-mail, Google e Microsoft 365',          ('ligado', ''), ('ligado', ''), ('ligado', 'Google e Microsoft exigem conta paga (lista de sites liberados)')),
    ('Assistente e IAs (Claude / Gemini)',      ('ligado', ''), ('ligado', ''), ('ligado', 'conta paga para acessar as APIs')),
    ('Agentes de Segurança, Banco e Funcionalidades', ('ligado', ''), ('desligado', 'processos em segundo plano são encerrados'), ('limitado', 'rodam mais devagar')),
    ('Agentes OmniTest (navegador)',            ('ligado', 'precisa do Chromium'), ('desligado', 'sem navegador no contêiner'), ('desligado', 'sem Chromium')),
    ('Agente Orquestrador (corrige o código)',  ('ligado', 'precisa do Git'), ('desligado', 'código só de leitura'), ('limitado', 'Git e processos limitados')),
]
COLUNAS_MATRIZ = {'vm': 1, 'conteiner': 2, 'gerenciada': 3, 'computador': 1}

_CACHE = {}


def _cache(chave, segundos, funcao):
    agora = time.time()
    if chave in _CACHE and agora - _CACHE[chave][0] < segundos:
        return _CACHE[chave][1]
    valor = funcao()
    _CACHE[chave] = (agora, valor)
    return valor


# ------------------------------------------------------------------------------
# Hospedagem e banco
# ------------------------------------------------------------------------------
def hospedagem():
    """Chave de HOSPEDAGENS: a do .env (gravada pelo instalador) ou detectada pelas variáveis da nuvem."""
    escolhida = (os.environ.get('HOSPEDAGEM') or '').strip().lower()
    if escolhida in HOSPEDAGENS:
        return escolhida
    if os.environ.get('PYTHONANYWHERE_DOMAIN') or os.environ.get('PYTHONANYWHERE_SITE'):
        return 'pythonanywhere'
    if os.environ.get('K_SERVICE') or os.environ.get('GAE_SERVICE'):
        return 'gcp_conteiner'
    if os.environ.get('WEBSITE_SITE_NAME') or os.environ.get('CONTAINER_APP_NAME'):
        return 'azure_conteiner'
    aws = aws_servico()
    if aws in ('ecs', 'app_runner', 'lambda'):
        return 'aws_conteiner'
    if aws in ('elastic_beanstalk', 'ec2'):
        return 'aws_vm'
    if sys.platform.startswith('linux'):
        return 'servidor'
    return 'computador'


def _ler_arquivo(caminho):
    try:
        with open(caminho, encoding='utf-8', errors='ignore') as f:
            return f.read(200).strip()
    except OSError:
        return ''


def arquivo_client_secret_google():
    """Credencial OAuth do Google (Agenda e Gmail). Em contêiner ela é montada como segredo (nunca vai na imagem) e o
    caminho vem de GOOGLE_CLIENT_SECRETS_FILE; sem a variável, o client_secret.json da pasta da plataforma."""
    return (os.environ.get('GOOGLE_CLIENT_SECRETS_FILE') or '').strip() or os.path.join(RAIZ, 'client_secret.json')


def aws_servico():
    """Qual serviço da AWS está rodando a plataforma, pelas marcas que a própria AWS deixa (sem chamar a rede):
    Lambda e ECS/Fargate pelas variáveis de ambiente, App Runner pela variável dele, Elastic Beanstalk pela pasta
    /opt/elasticbeanstalk e EC2 pelo fabricante da máquina (Amazon EC2) ou pelo identificador do hipervisor.
    Devolve 'lambda', 'ecs', 'app_runner', 'elastic_beanstalk', 'ec2' ou None (não é AWS)."""
    execucao = os.environ.get('AWS_EXECUTION_ENV') or ''
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or execucao.startswith('AWS_Lambda'):
        return 'lambda'
    if os.environ.get('ECS_CONTAINER_METADATA_URI_V4') or os.environ.get('ECS_CONTAINER_METADATA_URI') or execucao.startswith('AWS_ECS'):
        return 'ecs'
    if os.environ.get('AWS_APP_RUNNER_SERVICE_ID'):
        return 'app_runner'
    if not sys.platform.startswith('linux'):
        return None
    if os.path.isdir('/opt/elasticbeanstalk') or execucao.startswith('AWS_ElasticBeanstalk'):
        return 'elastic_beanstalk'
    fabricante = ' '.join(_ler_arquivo(f'/sys/devices/virtual/dmi/id/{c}') for c in ('sys_vendor', 'board_vendor', 'bios_vendor'))
    if 'Amazon EC2' in fabricante or _ler_arquivo('/sys/hypervisor/uuid').lower().startswith('ec2'):
        return 'ec2'
    return None


def tipo_hospedagem(chave=None):
    return HOSPEDAGENS[chave or hospedagem()][1]


def nome_hospedagem(chave=None):
    return HOSPEDAGENS[chave or hospedagem()][0]


def disco_persistente():
    """Contêiner só guarda arquivos com volume montado (DISCO_PERSISTENTE=1, gravado pelo instalador)."""
    return tipo_hospedagem() != 'conteiner' or os.environ.get('DISCO_PERSISTENTE') == '1'


def dialeto_do_banco():
    import banco_config
    d = banco_config.dialeto()
    return 'mysql' if d in ('mysql', 'mariadb') else d


# ------------------------------------------------------------------------------
# Pastas de backup
# ------------------------------------------------------------------------------
def pasta_backups_padrao(chave=None):
    """Sugestão do instalador para a hospedagem (vazio = instance/backups)."""
    pasta = PASTA_BACKUP_PADRAO[tipo_hospedagem(chave)]
    return os.path.expanduser(pasta) if pasta else ''


def pasta_backups(instance_path=None):
    """Pasta base dos backups: BACKUP_DIR (caminho absoluto) ou instance/backups."""
    configurada = os.path.expanduser((os.environ.get('BACKUP_DIR') or '').strip())
    if configurada and os.path.isabs(configurada):
        return configurada
    if instance_path is None:
        try:
            from flask import current_app
            instance_path = current_app.instance_path
        except Exception:
            instance_path = os.path.join(RAIZ, 'instance')
    return os.path.join(instance_path, 'backups')


def pasta_backups_externa():
    """Segunda cópia dos backups fora do servidor (BACKUP_DIR_EXTERNO, caminho absoluto) ou ''."""
    pasta = os.path.expanduser((os.environ.get('BACKUP_DIR_EXTERNO') or '').strip())
    return pasta if pasta and os.path.isabs(pasta) else ''


def _gravavel(pasta):
    try:
        os.makedirs(pasta, exist_ok=True)
        teste = os.path.join(pasta, '.teste_gravacao')
        with open(teste, 'w') as f:
            f.write('ok')
        os.remove(teste)
        return True
    except OSError:
        return False


def espaco_livre(pasta):
    """Bytes livres no disco da pasta (ou None)."""
    alvo = pasta
    while alvo and not os.path.exists(alvo):
        alvo = os.path.dirname(alvo)
    try:
        return shutil.disk_usage(alvo or RAIZ).free
    except OSError:
        return None


# ------------------------------------------------------------------------------
# Ferramentas
# ------------------------------------------------------------------------------
def ferramenta_backup(dialeto=None):
    """Caminho do programa de backup do banco (mysqldump / pg_dump), 'interno' (SQLite) ou None."""
    dialeto = dialeto or dialeto_do_banco()
    if dialeto == 'sqlite':
        return 'interno'
    if dialeto == 'mysql':
        nomes = [os.environ.get('MYSQLDUMP_BIN'), 'mysqldump', 'mariadb-dump']
    elif dialeto == 'postgresql':
        nomes = [os.environ.get('PG_DUMP_BIN'), 'pg_dump']
    else:
        return None
    for nome in nomes:
        if nome and (shutil.which(nome) or os.path.isfile(nome)):
            return shutil.which(nome) or nome
    return None


def driver_instalado(dialeto=None):
    info = BANCOS.get(dialeto or dialeto_do_banco())
    return bool(info) and (info['driver'] is None or importlib.util.find_spec(info['driver']) is not None)


def chromium_disponivel():
    def procurar():
        try:
            if RAIZ not in sys.path:
                sys.path.insert(0, RAIZ)
            from agentes_orquestrador import ambiente_orquestrador as ambiente_orq
            return ambiente_orq._chromium()
        except Exception:
            return False
    return _cache('chromium', 600, procurar)


def capacidades_orquestrador():
    def ler():
        try:
            from agentes_orquestrador import ambiente_orquestrador as ambiente_orq
            return ambiente_orq.capacidades()
        except Exception as e:
            return {'pode_corrigir': False, 'itens': {}, 'erro': str(e)}
    return _cache('orquestrador', 120, ler)


# ------------------------------------------------------------------------------
# Tarefas agendadas: o próprio tarefas_agendadas.py anota quando rodou
# ------------------------------------------------------------------------------
def _arquivo_batimento():
    return os.path.join(RAIZ, 'instance', 'ultima_execucao_tarefas.txt')


CHAVE_BATIMENTO_REDIS = 'mentoria:tarefas:ultima_execucao'


def _redis_do_batimento():
    """Com REDIS_URL (contêiner), o batimento fica no Redis: o worker grava e as réplicas web leem."""
    url = (os.environ.get('REDIS_URL') or '').strip()
    if not url:
        return None
    import redis
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def anotar_execucao_das_tarefas(agora=None):
    momento = (agora or datetime.now()).isoformat(timespec='seconds')
    try:
        cliente = _redis_do_batimento()
        if cliente is not None:
            cliente.set(CHAVE_BATIMENTO_REDIS, momento)
            return
        os.makedirs(os.path.dirname(_arquivo_batimento()), exist_ok=True)
        with open(_arquivo_batimento(), 'w', encoding='utf-8') as f:
            f.write(momento)
    except Exception as erro:  # o batimento é só um indicador da tela Ambiente; nunca derruba as tarefas
        import logging
        logging.getLogger('ambiente').warning('Não foi possível anotar a execução das tarefas: %s', erro)


def ultima_execucao_das_tarefas():
    try:
        cliente = _redis_do_batimento()
        if cliente is not None:
            valor = cliente.get(CHAVE_BATIMENTO_REDIS)
            return datetime.fromisoformat(valor.decode()) if valor else None
        with open(_arquivo_batimento(), encoding='utf-8') as f:
            return datetime.fromisoformat(f.read().strip())
    except (OSError, ValueError):
        return None
    except Exception as erro:
        import logging
        logging.getLogger('ambiente').warning('Não foi possível ler a execução das tarefas: %s', erro)
        return None


# ------------------------------------------------------------------------------
# Recursos: ligado / atenção / desligado, com motivo e como ligar
# ------------------------------------------------------------------------------
def _item(chave, nome, estado, motivo, como_ligar='', grupo='Plataforma'):
    return {'chave': chave, 'nome': nome, 'estado': estado, 'motivo': motivo, 'como_ligar': como_ligar, 'grupo': grupo}


def _estado_do_banco():
    from models import db
    from sqlalchemy import text
    d = dialeto_do_banco()
    info = BANCOS.get(d, {'nome': d, 'pip': None})
    if not driver_instalado(d):
        return _item('banco', f"Banco: {info['nome']}", 'desligado', 'O driver do banco não está instalado.',
                     f"pip install {info['pip']}", 'Banco de dados'), None
    try:
        with db.engine.connect() as conexao:
            conexao.execute(text('SELECT 1'))
            versao = '.'.join(str(x) for x in (db.engine.dialect.server_version_info or ()) if isinstance(x, int))
        return _item('banco', f"Banco: {info['nome']}" + (f" {versao}" if versao else ''), 'ligado',
                     'Conectado.', '', 'Banco de dados'), versao
    except Exception as e:
        from base_conhecimento import sem_segredos
        return _item('banco', f"Banco: {info['nome']}", 'desligado', 'Sem conexão: ' + sem_segredos(str(e))[:160],
                     'Confira DATABASE_URL no .env e se o servidor do banco está ligado.', 'Banco de dados'), None


def _estado_das_migracoes():
    from models import db
    from sqlalchemy import text
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config()
        config.set_main_option('script_location', os.path.join(RAIZ, 'migrations'))
        cabecas = set(ScriptDirectory.from_config(config).get_heads())
        atuais = set(db.session.execute(text('SELECT version_num FROM alembic_version')).scalars().all())
    except Exception:
        db.session.rollback()
        return _item('migracoes', 'Estrutura do banco (migrações)', 'atencao', 'Não foi possível ler a versão da estrutura.',
                     'flask db upgrade', 'Banco de dados')
    if atuais == cabecas:
        return _item('migracoes', 'Estrutura do banco (migrações)', 'ligado', 'Na versão mais recente.', '', 'Banco de dados')
    return _item('migracoes', 'Estrutura do banco (migrações)', 'atencao', 'Há mudanças de estrutura por aplicar.',
                 'flask db upgrade', 'Banco de dados')


def recursos():
    """Lista de recursos com estado ('ligado', 'atencao', 'desligado'), motivo e como ligar."""
    itens = []
    d = dialeto_do_banco()
    tipo = tipo_hospedagem()
    banco, _ = _estado_do_banco()
    itens.append(banco)
    itens.append(_estado_das_migracoes())
    if tipo == 'conteiner' and d == 'sqlite':
        itens.append(_item('banco_local', 'Banco num contêiner', 'desligado', 'O SQLite fica no disco do contêiner e se perde a cada reinício.',
                           'Use um banco gerenciado (RDS, Cloud SQL ou Azure Database) no DATABASE_URL.', 'Banco de dados'))

    # Backup
    pasta = pasta_backups()
    ferramenta = ferramenta_backup(d)
    if d == 'mssql':
        itens.append(_item('backup', 'Backup pela plataforma', 'desligado',
                           'No SQL Server o backup é feito pelo próprio servidor do banco (ou pelo Azure), não pela plataforma.',
                           'Configure o plano de manutenção do SQL Server ou o backup automático do Azure SQL.', 'Backup'))
    elif not ferramenta:
        apt = BANCOS[d].get('apt', '')
        itens.append(_item('backup', 'Backup pela plataforma', 'desligado', f"Falta o programa {BANCOS[d]['backup']} neste servidor.",
                           f"sudo apt install {apt}" if apt else '', 'Backup'))
    elif not disco_persistente():
        itens.append(_item('backup', 'Backup pela plataforma', 'desligado', 'O disco do contêiner é apagado a cada reinício.',
                           'Monte um volume e defina DISCO_PERSISTENTE=1 e BACKUP_DIR; ou use o backup do banco gerenciado.', 'Backup'))
    elif not _gravavel(pasta):
        itens.append(_item('backup', 'Backup pela plataforma', 'desligado', f'Sem permissão para gravar em {pasta}.',
                           f'sudo mkdir -p {pasta} && sudo chown <usuário do site> {pasta}', 'Backup'))
    else:
        livre = espaco_livre(pasta)
        pouco = livre is not None and livre < 1024 ** 3
        itens.append(_item('backup', 'Backup pela plataforma', 'atencao' if pouco else 'ligado',
                           f'Pasta {pasta}' + (' · menos de 1 GB livre' if pouco else ''), 'Libere espaço no disco.' if pouco else '', 'Backup'))
    externa = pasta_backups_externa()
    if externa and _gravavel(externa):
        itens.append(_item('backup_externo', 'Cópia dos backups fora do servidor', 'ligado', f'Pasta {externa}', '', 'Backup'))
    else:
        itens.append(_item('backup_externo', 'Cópia dos backups fora do servidor', 'atencao',
                           'Sem segunda cópia: se o disco do servidor falhar, o banco e os backups se perdem juntos.' if not externa
                           else f'Sem permissão para gravar em {externa}.',
                           'Defina BACKUP_DIR_EXTERNO com um disco de rede, um volume da nuvem ou uma pasta sincronizada pelo rclone.', 'Backup'))

    # Arquivos e tarefas
    itens.append(_item('arquivos', 'Arquivos enviados, logos e documentos', 'ligado' if disco_persistente() else 'desligado',
                       'Gravados no disco do servidor.' if disco_persistente() else 'O disco do contêiner é apagado a cada reinício.',
                       '' if disco_persistente() else 'Monte volumes em /app/uploads e /app/instance e defina DISCO_PERSISTENTE=1.'))
    ultima = ultima_execucao_das_tarefas()
    if ultima and (datetime.now() - ultima).total_seconds() < 3 * 3600:
        itens.append(_item('tarefas', 'Lembretes, avisos e backups agendados', 'ligado', f"Última execução: {ultima:%d/%m/%Y %H:%M}."))
    else:
        como = {'vm': 'sudo systemctl enable --now mentoria-tarefas.timer',
                'gerenciada': 'PythonAnywhere › Tasks: tarefa de hora em hora com python tarefas_agendadas.py',
                'conteiner': 'Agendador da nuvem (EventBridge, Cloud Scheduler ou Azure Logic Apps) chamando tarefas_agendadas.py',
                'computador': 'Rode python tarefas_agendadas.py (o python app.py faz só os backups).'}[tipo]
        itens.append(_item('tarefas', 'Lembretes, avisos e backups agendados', 'atencao',
                           f"Sem execução nas últimas 3 horas (última: {ultima:%d/%m/%Y %H:%M})." if ultima else 'As tarefas agendadas ainda não rodaram neste servidor.',
                           como))

    # Integrações
    itens.append(_item('email', 'E-mail (SMTP)', 'ligado' if os.environ.get('MAIL_SERVER') else 'atencao',
                       'Configurado.' if os.environ.get('MAIL_SERVER') else 'Sem servidor de e-mail: avisos só aparecem na plataforma.',
                       'Preencha MAIL_SERVER, MAIL_USERNAME e MAIL_PASSWORD no .env.', 'Integrações'))
    google = os.path.exists(arquivo_client_secret_google())
    itens.append(_item('google', 'Google (Agenda e Gmail)', 'ligado' if google else 'atencao',
                       'Configurado.' if google else 'Sem client_secret.json: Conectar Google fica indisponível.',
                       'Coloque o client_secret.json do Google Cloud na pasta da plataforma (ou informe o caminho em '
                       'GOOGLE_CLIENT_SECRETS_FILE).', 'Integrações'))
    try:
        import microsoft365
        m365 = microsoft365.configurado()
    except Exception:
        m365 = False
    itens.append(_item('microsoft', 'Microsoft 365 (Outlook e Agenda)', 'ligado' if m365 else 'atencao',
                       'Configurado.' if m365 else 'Sem MS365_CLIENT_ID: Conectar Microsoft 365 fica indisponível.',
                       'Preencha MS365_CLIENT_ID e MS365_CLIENT_SECRET (GUIA_MICROSOFT365.md).', 'Integrações'))
    try:
        import provedores_ia
        chaves = [p for p in provedores_ia.PROVEDORES if provedores_ia.chave_configurada(p)]
    except Exception:
        chaves = []
    itens.append(_item('ia', 'IAs (Claude / Gemini)', 'ligado' if chaves else 'atencao',
                       ('Chaves: ' + ', '.join(chaves)) if chaves else 'Sem chave: o Assistente responde só com a base, sem IA.',
                       'Cadastre as chaves em Provedores de IA e custos › Credenciais.', 'Integrações'))

    # Agentes
    segundo_plano = tipo != 'conteiner'
    itens.append(_item('agentes', 'Agentes de Segurança, Banco e Funcionalidades', 'ligado' if segundo_plano else 'desligado',
                       'Rodam em segundo plano neste servidor.' if segundo_plano else 'O contêiner encerra processos em segundo plano.',
                       '' if segundo_plano else 'Rode os agentes numa máquina virtual ou no computador de desenvolvimento.', 'Agentes'))
    chromium = chromium_disponivel()
    fim_a_fim = segundo_plano and chromium
    itens.append(_item('omnitest', 'Agentes OmniTest (testes no navegador)', 'ligado' if fim_a_fim else 'desligado',
                       'Chromium disponível.' if fim_a_fim else ('Sem o navegador Chromium.' if segundo_plano else 'O contêiner encerra processos em segundo plano.'),
                       '' if fim_a_fim else 'pip install playwright && python -m playwright install --with-deps chromium', 'Agentes'))
    orq = capacidades_orquestrador()
    motivos = [v['texto'] for v in (orq.get('itens') or {}).values() if not v.get('ok')][:2]
    itens.append(_item('orquestrador', 'Agente Orquestrador (corrige o código)', 'ligado' if orq.get('pode_corrigir') else 'desligado',
                       'Repositório Git gravável e processos em segundo plano.' if orq.get('pode_corrigir') else ' '.join(motivos) or 'Indisponível.',
                       '' if orq.get('pode_corrigir') else 'Precisa de máquina virtual com o código num repositório Git (git clone).', 'Agentes'))
    return itens


def disponivel(chave):
    """(ok, motivo) de um recurso, para as rotas desligarem o que não funciona aqui. Recurso desconhecido = disponível."""
    rapidos = {
        'agentes': lambda: (tipo_hospedagem() != 'conteiner', 'O contêiner encerra processos em segundo plano: rode os agentes numa máquina virtual.'),
        'omnitest': lambda: (tipo_hospedagem() != 'conteiner' and chromium_disponivel(),
                             'Sem o navegador Chromium neste servidor: os agentes OmniTest não rodam aqui.'),
        'backup': lambda: _backup_disponivel(),
    }
    if chave not in rapidos:
        return True, ''
    ok, motivo = rapidos[chave]()
    return bool(ok), ('' if ok else motivo)


def _backup_disponivel():
    d = dialeto_do_banco()
    if d == 'mssql':
        return False, 'No SQL Server o backup é feito pelo próprio servidor do banco (ou pelo Azure), não pela plataforma.'
    if not ferramenta_backup(d):
        return False, f"Falta o programa {BANCOS.get(d, {}).get('backup')} neste servidor (veja Ambiente e compatibilidade)."
    if not disco_persistente():
        return False, 'O disco do contêiner é apagado a cada reinício: monte um volume ou use o backup do banco gerenciado.'
    return True, ''


def resumo():
    """Tudo o que a tela mostra."""
    import banco_config
    itens = recursos()
    chave = hospedagem()
    coluna = COLUNAS_MATRIZ[tipo_hospedagem(chave)]
    return {
        'hospedagem': chave, 'hospedagem_nome': nome_hospedagem(chave), 'tipo': tipo_hospedagem(chave),
        'definida': (os.environ.get('HOSPEDAGEM') or '').strip().lower() in HOSPEDAGENS,
        'banco': dialeto_do_banco(), 'banco_nome': BANCOS.get(dialeto_do_banco(), {}).get('nome', dialeto_do_banco()),
        'endereco': banco_config.endereco_sem_senha(),
        'pasta_backups': pasta_backups(), 'pasta_externa': pasta_backups_externa(),
        'pasta_padrao': pasta_backups_padrao(chave), 'livre': espaco_livre(pasta_backups()),
        'agendamentos_padrao': AGENDAMENTOS_PADRAO,
        'itens': itens, 'contagem': {e: sum(1 for i in itens if i['estado'] == e) for e in ('ligado', 'atencao', 'desligado')},
        'matriz': MATRIZ, 'coluna': coluna, 'hospedagens': HOSPEDAGENS, 'bancos': BANCOS, 'bancos_por_tipo': BANCOS_POR_TIPO,
        'python': sys.version.split()[0],
    }
