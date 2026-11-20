# -*- coding: utf-8 -*-
"""
INSTALADOR DA PLATAFORMA — uma instalação por cliente
=====================================================
    python3 instalar.py                      perguntas passo a passo (Enter aceita o padrão entre colchetes)
    python3 instalar.py --respostas r.json   sem perguntas (automação); as chaves são as mesmas das perguntas
    python3 instalar.py --env /outro/.env    grava em outro arquivo (padrão: .env na pasta da plataforma)

O que ele faz:
 1. Pergunta a hospedagem (servidor próprio, máquina virtual ou contêiner na AWS/GCP/Azure, PythonAnywhere) e
    mostra o que funciona nela (ambiente.MATRIZ).
 2. Pergunta o banco (só os possíveis na hospedagem: ambiente.BANCOS_POR_TIPO), onde ele fica e a conexão.
 3. Pergunta as pastas de backup (padrão por hospedagem: ambiente.PASTA_BACKUP_PADRAO) e a cópia fora do servidor.
 4. Grava o .env (permissão só do dono; o anterior vira .env.bak-<data>), mantendo as chaves que já existiam
    (SECRET_KEY, e-mail, chaves de IA...).
 5. Banco no mesmo servidor: gera o SQL que cria o banco e o usuário (instance/criar_banco_<banco>.sql) e mostra o
    comando para rodá-lo.
 6. Instala o driver do banco (requirements-postgresql.txt / requirements-sqlserver.txt), testa a conexão, copia os
    dados de um SQLite antigo (opcional, copiar_banco.py), cria a estrutura e marca a versão das migrações.
 7. Cria os backups agendados padrão (Diário 7, Semanal 4, Mensal 12) e as pastas.
 8. Banco sem nenhum Administrador (instalação nova): cria o primeiro, com senha provisória mostrada uma única vez
    e troca obrigatória no primeiro acesso.
 9. Mostra os próximos passos da hospedagem (deploy/<hospedagem>/LEIAME.md).

Pode ser rodado de novo: as respostas anteriores viram o padrão e nada é apagado sem perguntar.
"""
import argparse
import getpass
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
import ambiente  # noqa: E402  (só biblioteca padrão; não carrega o app)

PORTAS = {'mysql': 3306, 'postgresql': 5432, 'mssql': 1433}
REQUISITOS = {'postgresql': 'requirements-postgresql.txt', 'mssql': 'requirements-sqlserver.txt'}
PERFIL_DEPLOY = {'vm': 'ubuntu', 'conteiner': None, 'gerenciada': 'pythonanywhere', 'computador': None}
NOME_VALIDO = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,62}$')


# ------------------------------------------------------------------------------
# Perguntas
# ------------------------------------------------------------------------------
class Perguntas:
    def __init__(self, respostas=None):
        self.respostas = respostas          # dict: modo automático
        self.dadas = {}

    def texto(self, chave, pergunta, padrao='', segredo=False, validar=None):
        if self.respostas is not None:
            valor = str(self.respostas.get(chave, padrao) or '')
        else:
            while True:
                rotulo = f"{pergunta}" + (f" [{'*****' if segredo and padrao else padrao}]" if padrao else '') + ': '
                valor = (getpass.getpass(rotulo) if segredo else input(rotulo)).strip() or padrao
                erro = validar(valor) if validar else None
                if not erro:
                    break
                print(f"  ! {erro}")
        erro = validar(valor) if validar else None
        if erro:
            raise SystemExit(f"Resposta inválida para {chave}: {erro}")
        self.dadas[chave] = '*****' if segredo else valor
        return valor

    def escolha(self, chave, pergunta, opcoes, padrao):
        """opcoes = [(chave, rótulo)]."""
        chaves = [c for c, _ in opcoes]
        if self.respostas is not None:
            valor = self.respostas.get(chave, padrao)
            if valor not in chaves:
                raise SystemExit(f"Resposta inválida para {chave}: use {', '.join(chaves)}")
        else:
            print(f"\n{pergunta}")
            for n, (c, rotulo) in enumerate(opcoes, 1):
                print(f"  {n}) {rotulo}" + ('  (padrão)' if c == padrao else ''))
            while True:
                entrada = input(f"Escolha 1-{len(opcoes)} [{chaves.index(padrao) + 1 if padrao in chaves else 1}]: ").strip()
                if not entrada:
                    valor = padrao if padrao in chaves else chaves[0]
                    break
                if entrada.isdigit() and 1 <= int(entrada) <= len(opcoes):
                    valor = chaves[int(entrada) - 1]
                    break
                print('  ! Número fora da lista.')
        self.dadas[chave] = valor
        return valor

    def sim(self, chave, pergunta, padrao=True):
        if self.respostas is not None:
            valor = self.respostas.get(chave, padrao)
            valor = valor if isinstance(valor, bool) else str(valor).lower() in ('1', 's', 'sim', 'y', 'yes', 'true')
        else:
            entrada = input(f"{pergunta} [{'S/n' if padrao else 's/N'}]: ").strip().lower()
            valor = padrao if not entrada else entrada in ('s', 'sim', 'y', 'yes')
        self.dadas[chave] = valor
        return valor


def _nome(valor):
    return None if NOME_VALIDO.match(valor or '') else 'use letras, números e _ (começando por letra)'


def _caminho_absoluto(valor):
    return None if not valor or os.path.isabs(os.path.expanduser(valor)) else 'informe um caminho absoluto (ex.: /var/backups/mentoria)'


# ------------------------------------------------------------------------------
# .env
# ------------------------------------------------------------------------------
def ler_env(caminho):
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(caminho).items() if v is not None} if os.path.exists(caminho) else {}
    except ImportError:
        raise SystemExit('Falta o python-dotenv: rode antes  pip install -r requirements.txt') from None


def gravar_env(caminho, valores, anteriores):
    """Mantém as chaves anteriores que o instalador não trata; o arquivo antigo vira .env.bak-<data>."""
    if os.path.exists(caminho):
        copia = f"{caminho}.bak-{datetime.now():%Y%m%d%H%M%S}"
        os.replace(caminho, copia)
        os.chmod(copia, 0o600)
        print(f"  .env anterior guardado em {copia}")
    finais = dict(anteriores)
    finais.update({k: v for k, v in valores.items() if v is not None})
    for chave in [k for k, v in valores.items() if v is None]:
        finais.pop(chave, None)

    def aspas(v):
        v = str(v)
        return v if re.match(r'^[A-Za-z0-9_./:@+%?=&,-]*$', v) else '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    linhas = [f"# Gerado por instalar.py em {datetime.now():%d/%m/%Y %H:%M}. Nunca coloque este arquivo no Git.", '']
    linhas += [f"{k}={aspas(v)}" for k, v in finais.items()]
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas) + '\n')


# ------------------------------------------------------------------------------
# Banco
# ------------------------------------------------------------------------------
def montar_url(banco, dados):
    from sqlalchemy.engine import URL
    if banco == 'sqlite':
        caminho = os.path.abspath(os.path.expanduser(dados['arquivo'])).replace('\\', '/')
        return 'sqlite:///' + caminho
    driver = {'mysql': 'mysql+pymysql', 'postgresql': 'postgresql+psycopg', 'mssql': 'mssql+pyodbc'}[banco]
    consulta = {'charset': 'utf8mb4'} if banco == 'mysql' else {}
    if banco == 'mssql':
        consulta = {'driver': 'ODBC Driver 18 for SQL Server', 'TrustServerCertificate': 'yes' if dados['local'] else 'no'}
    url = URL.create(driver, username=dados['usuario'], password=dados['senha'], host=dados['servidor'],
                     port=int(dados['porta']), database=dados['nome'], query=consulta)
    return url.render_as_string(hide_password=False)


def sql_de_criacao(banco, dados):
    """SQL para criar o banco e o usuário no servidor local, e o comando que o roda."""
    nome, usuario, senha = dados['nome'], dados['usuario'], dados['senha'].replace("'", "''")
    if banco == 'mysql':
        sql = (f"CREATE DATABASE IF NOT EXISTS `{nome}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
               f"CREATE USER IF NOT EXISTS '{usuario}'@'localhost' IDENTIFIED BY '{senha}';\n"
               f"ALTER USER '{usuario}'@'localhost' IDENTIFIED BY '{senha}';\n"
               f"GRANT ALL PRIVILEGES ON `{nome}`.* TO '{usuario}'@'localhost';\nFLUSH PRIVILEGES;\n")
        return sql, 'sudo mysql -e "source {arquivo}"'
    if banco == 'postgresql':
        sql = (f"DO $$ BEGIN\n  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{usuario}') THEN\n"
               f"    CREATE ROLE {usuario} LOGIN PASSWORD '{senha}';\n  ELSE\n    ALTER ROLE {usuario} LOGIN PASSWORD '{senha}';\n"
               f"  END IF;\nEND $$;\n"
               f"SELECT 'CREATE DATABASE {nome} OWNER {usuario} ENCODING ''UTF8'' TEMPLATE template0'\n"
               f"WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{nome}')\\gexec\n")
        return sql, 'sudo cat {arquivo} | sudo -u postgres psql'
    sql = (f"IF DB_ID('{nome}') IS NULL CREATE DATABASE [{nome}] COLLATE Latin1_General_100_CI_AI_SC_UTF8;\nGO\n"
           f"IF SUSER_ID('{usuario}') IS NULL CREATE LOGIN [{usuario}] WITH PASSWORD = '{senha}';\nGO\n"
           f"USE [{nome}];\nGO\nIF USER_ID('{usuario}') IS NULL CREATE USER [{usuario}] FOR LOGIN [{usuario}];\n"
           f"ALTER ROLE db_owner ADD MEMBER [{usuario}];\nGO\n")
    return sql, 'sudo /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -i {arquivo}'


def testar_conexao(url):
    from sqlalchemy import create_engine, text
    try:
        motor = create_engine(url)
        with motor.connect() as conexao:
            conexao.execute(text('SELECT 1'))
        motor.dispose()
        return True, ''
    except Exception as e:
        try:
            from base_conhecimento import sem_segredos
            return False, sem_segredos(str(e))[:300]
        except Exception:
            return False, str(e).split('\n')[0][:300]


def instalar_driver(banco, perguntas):
    if ambiente.driver_instalado(banco):
        return True
    arquivo = REQUISITOS.get(banco) or 'requirements.txt'
    print(f"\nO driver do {ambiente.BANCOS[banco]['nome']} não está instalado.")
    if not perguntas.sim('instalar_driver', f"Instalar agora com  pip install -r {arquivo}?", True):
        return False
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', os.path.join(RAIZ, arquivo)])
    import importlib
    importlib.invalidate_caches()
    return r.returncode == 0 and ambiente.driver_instalado(banco)


# ------------------------------------------------------------------------------
# Instalação
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Instala a plataforma: hospedagem, banco, pastas de backup e .env.')
    parser.add_argument('--respostas', help='arquivo JSON com as respostas (sem perguntas)')
    parser.add_argument('--env', default=os.path.join(RAIZ, '.env'), help='arquivo .env de saída')
    args = parser.parse_args()
    respostas = None
    if args.respostas:
        with open(args.respostas, encoding='utf-8') as f:
            respostas = json.load(f)
    p = Perguntas(respostas)
    anterior = ler_env(args.env)

    print('=' * 72 + '\n INSTALAÇÃO DA PLATAFORMA DE MENTORIA\n' + '=' * 72)

    # 1. Hospedagem
    padrao_hosp = anterior.get('HOSPEDAGEM') or ambiente.hospedagem()
    hosp = p.escolha('hospedagem', 'Onde a plataforma vai rodar?', [(c, n) for c, (n, _) in ambiente.HOSPEDAGENS.items()], padrao_hosp)
    tipo = ambiente.tipo_hospedagem(hosp)
    coluna = ambiente.COLUNAS_MATRIZ[tipo]
    print(f"\nO que funciona em {ambiente.nome_hospedagem(hosp)}:")
    simbolos = {'ligado': 'OK  ', 'limitado': 'LIM ', 'desligado': 'NÃO '}
    for linha in ambiente.MATRIZ:
        estado, nota = linha[coluna]
        print(f"  {simbolos[estado]} {linha[0]}" + (f" — {nota}" if nota else ''))

    # 2. Banco
    opcoes = [(b, ambiente.BANCOS[b]['nome'] + ' — ' + ambiente.BANCOS[b]['nota']) for b in ambiente.BANCOS_POR_TIPO[tipo]]
    padrao_banco = ambiente.BANCOS_POR_TIPO[tipo][0]
    if anterior.get('DATABASE_URL'):
        import banco_config
        d = banco_config.dialeto(banco_config.normalizar(anterior['DATABASE_URL']))
        d = 'mysql' if d in ('mysql', 'mariadb') else d
        padrao_banco = d if d in dict(opcoes) else padrao_banco
    banco = p.escolha('banco', 'Qual banco de dados?', opcoes, padrao_banco)
    dados = {'local': False}
    if banco == 'sqlite':
        padrao_arq = {'vm': '/srv/mentoria/dados/mentoria.db', 'gerenciada': os.path.join(RAIZ, 'instance', 'mentoria.db'),
                      'computador': os.path.join(RAIZ, 'instance', 'mentoria.db')}.get(tipo, os.path.join(RAIZ, 'instance', 'mentoria.db'))
        dados['arquivo'] = p.texto('arquivo_sqlite', 'Arquivo do banco SQLite', padrao_arq, validar=_caminho_absoluto)
        pasta_arquivo = os.path.dirname(os.path.expanduser(dados['arquivo']))
        try:
            os.makedirs(pasta_arquivo, exist_ok=True)
        except OSError:
            raise SystemExit(f"Sem permissão para criar {pasta_arquivo}: sudo mkdir -p {pasta_arquivo} && sudo chown {getpass.getuser()} {pasta_arquivo}") from None
    else:
        if tipo == 'conteiner':
            print('\nNum contêiner o banco precisa ser gerenciado pela nuvem (RDS, Cloud SQL ou Azure Database).')
        elif tipo in ('vm', 'computador'):
            dados['local'] = p.sim('banco_local', 'O banco fica neste mesmo servidor?', True)
        padrao_servidor = 'localhost' if dados['local'] else ''
        if tipo == 'gerenciada' and banco == 'mysql':
            padrao_servidor = f"{getpass.getuser()}.mysql.pythonanywhere-services.com"
        dados['servidor'] = p.texto('servidor', 'Servidor do banco (endereço)', padrao_servidor,
                                    validar=lambda v: None if v else 'informe o endereço do servidor')
        dados['porta'] = p.texto('porta', 'Porta', str(PORTAS[banco]), validar=lambda v: None if v.isdigit() else 'use só números')
        dados['nome'] = p.texto('nome_banco', 'Nome do banco', 'mentoria', validar=_nome)
        dados['usuario'] = p.texto('usuario_banco', 'Usuário do banco', 'mentoria', validar=_nome)
        sugestao = secrets.token_urlsafe(18) if dados['local'] else ''
        if dados['local'] and p.respostas is None:
            print('  (Enter gera uma senha forte automaticamente)')
        dados['senha'] = p.texto('senha_banco', 'Senha do banco', sugestao, segredo=True,
                                 validar=lambda v: None if len(v) >= 8 else 'use pelo menos 8 caracteres')
    url = montar_url(banco, dados)

    # 3. Endereço do site e pastas
    site = p.texto('endereco_site', 'Endereço público do site (para links nos e-mails)',
                   anterior.get('APP_BASE_URL', 'http://localhost:5000' if tipo == 'computador' else 'https://'))
    persistente = True
    if tipo == 'conteiner':
        persistente = p.sim('disco_persistente', 'Há volume montado em /app/uploads e /app/instance (EFS, Cloud Storage/Filestore, Azure Files)?', False)
    padrao_backup = anterior.get('BACKUP_DIR') or ambiente.pasta_backups_padrao(hosp)
    pasta_backup = p.texto('pasta_backups', 'Pasta dos backups (vazio = instance/backups)', padrao_backup, validar=_caminho_absoluto)
    pasta_externa = p.texto('pasta_backups_externa', 'Pasta para a cópia dos backups FORA do servidor (disco de rede, volume, rclone; vazio = sem cópia)',
                            anterior.get('BACKUP_DIR_EXTERNO', ''), validar=_caminho_absoluto)

    # 4. .env
    valores = {
        'HOSPEDAGEM': hosp,
        'DATABASE_URL': url,
        'SECRET_KEY': anterior.get('SECRET_KEY') or secrets.token_hex(32),
        'APP_BASE_URL': site,
        'BACKUP_DIR': os.path.expanduser(pasta_backup) if pasta_backup else None,
        'BACKUP_DIR_EXTERNO': os.path.expanduser(pasta_externa) if pasta_externa else None,
        'DISCO_PERSISTENTE': '1' if (tipo == 'conteiner' and persistente) else None,
        'MENTORIA_PRODUCAO': None if tipo == 'computador' else '1',
        'ATRAS_DE_PROXY': '1' if tipo in ('vm', 'conteiner') else anterior.get('ATRAS_DE_PROXY'),
    }
    gravar_env(args.env, valores, anterior)
    print(f"\n.env gravado em {args.env} (só o dono lê).")
    for chave, valor in valores.items():
        if valor is not None:
            os.environ[chave] = valor
        else:
            os.environ.pop(chave, None)

    # 5. SQL de criação no servidor local
    if banco != 'sqlite' and dados['local']:
        sql, comando = sql_de_criacao(banco, dados)
        os.makedirs(os.path.join(RAIZ, 'instance'), exist_ok=True)
        arquivo_sql = os.path.join(RAIZ, 'instance', f'criar_banco_{banco}.sql')
        descritor = os.open(arquivo_sql, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descritor, 'w', encoding='utf-8') as f:
            f.write(sql)
        print(f"\nPara criar o banco e o usuário neste servidor, rode (uma vez):\n    {comando.format(arquivo=arquivo_sql)}\n"
              f"Depois apague o arquivo (ele tem a senha):  sudo rm {arquivo_sql}")

    # 6. Driver, conexão, cópia e estrutura
    if not instalar_driver(banco, p):
        return _fim(hosp, False, "Instale o driver do banco e rode o instalador de novo.")
    ok, erro = testar_conexao(url)
    if not ok:
        return _fim(hosp, False, f"Não conectou ao banco: {erro}\nCrie o banco (passo acima) e rode o instalador de novo.")
    print('\nConexão com o banco: OK')
    origem = p.texto('copiar_de', 'Copiar os dados de um banco SQLite antigo? Caminho do arquivo .db (vazio = não copiar)', '',
                     validar=lambda v: None if not v or os.path.isfile(os.path.expanduser(v)) else 'arquivo não encontrado')
    if origem and os.path.abspath(os.path.expanduser(origem)) != os.path.abspath(os.path.expanduser(dados.get('arquivo', ''))):
        import copiar_banco
        origem_url = 'sqlite:///' + os.path.abspath(os.path.expanduser(origem)).replace('\\', '/')
        try:
            copiar_banco.copiar(origem_url, url)
        except ValueError as e:
            print(f"  ! {e}")
            if p.sim('substituir', 'Apagar os dados do banco de destino e copiar mesmo assim?', False):
                copiar_banco.copiar(origem_url, url, substituir=True)
    os.environ.pop('PULAR_ATUALIZACAO_BANCO', None)
    print('\nCriando ou atualizando a estrutura do banco...')
    from app import app                          # noqa: E402  (atualizar_estrutura_banco roda na importação)
    import backup_servico
    with app.app_context():
        criados = backup_servico.criar_agendamentos_padrao()
        pastas = []
        for _, _, pasta, _ in ambiente.AGENDAMENTOS_PADRAO + [('', '', 'manuais', 0)]:
            try:
                pastas.append(backup_servico.pasta_de(pasta))
            except OSError as e:
                print(f"  ! Sem permissão para criar {e.filename}: sudo mkdir -p {e.filename} && sudo chown {getpass.getuser()} {e.filename}")
        print(f"Backups agendados padrão: {'criados (Diário 7, Semanal 4, Mensal 12)' if criados else 'já existiam, mantidos'}.")
        if pastas:
            print('Pastas de backup: ' + ', '.join(pastas))
        criar_primeiro_administrador(p)
        situacao = ambiente.recursos()
    print('\nSituação dos recursos neste servidor:')
    marcas = {'ligado': 'OK  ', 'atencao': 'ATEN', 'desligado': 'NÃO '}
    for item in situacao:
        print(f"  {marcas[item['estado']]} {item['nome']}" + (f" — {item['motivo']}" if item['estado'] != 'ligado' else ''))
    return _fim(hosp, True)


def _senha_provisoria():
    """Senha provisória forte (maiúscula, minúscula, número e símbolo); a troca é obrigatória no primeiro acesso."""
    return 'Prov-' + secrets.token_urlsafe(12) + '-7a'


def criar_primeiro_administrador(p):
    """Instalação nova (nenhum Administrador no banco): cria o primeiro com senha provisória mostrada uma única vez."""
    from app import db, bcrypt
    from models import Usuario
    if Usuario.query.filter_by(tipo_usuario='Administrador').first():
        print('Administrador: já existe, mantido.')
        return
    if p.respostas is not None and not p.respostas.get('admin_email'):
        print('Administrador: nenhum no banco. Rode o instalador sem --respostas (ou informe admin_nome e admin_email).')
        return
    print('\nNenhum Administrador no banco: vamos criar o primeiro acesso.')
    nome = p.texto('admin_nome', 'Nome do Administrador', 'Administrador', validar=lambda v: None if v.strip() else 'informe o nome')
    email = p.texto('admin_email', 'E-mail do Administrador (será o login)', '',
                    validar=lambda v: None if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', v.strip()) else 'e-mail inválido')
    email = email.strip().lower()
    if Usuario.query.filter_by(email=email).first():
        print(f'  ! Já existe uma conta com {email}: nada foi criado.')
        return
    senha = _senha_provisoria()
    db.session.add(Usuario(nome=nome.strip(), email=email, senha=bcrypt.generate_password_hash(senha).decode('utf-8'),
                           tipo_usuario='Administrador', status='Ativo', forcar_troca_senha=True,
                           data_ultima_troca_senha=datetime.utcnow()))
    db.session.commit()
    print('\n' + '-' * 72)
    print(f' Primeiro acesso do Administrador\n   Login: {email}\n   Senha provisória: {senha}')
    print(' Anote agora: ela não fica gravada em nenhum arquivo. No primeiro login o sistema pede uma senha nova.')
    print('-' * 72)


def _fim(hosp, ok, mensagem=''):
    tipo = ambiente.tipo_hospedagem(hosp)
    perfil = PERFIL_DEPLOY[tipo] or (hosp.split('_')[0] if tipo == 'conteiner' else None)
    if mensagem:
        print('\n' + mensagem)
    if perfil:
        print(f"\nPróximos passos para {ambiente.nome_hospedagem(hosp)}: deploy/{perfil}/LEIAME.md")
    elif tipo == 'computador':
        print('\nPróximo passo: python app.py')
    print('Depois, entre como Administrador e confira Administração › Sistema › Ambiente e compatibilidade.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
