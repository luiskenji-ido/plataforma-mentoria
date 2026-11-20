# -*- coding: utf-8 -*-
"""
SERVIÇO DE BACKUP DA PLATAFORMA (Manutenção › DB)
=================================================
- Cópia consistente conforme o banco em uso (DATABASE_URL) e verificação de integridade:
    SQLite: API de backup do SQLite (funciona com o app em uso), arquivo .db;
    MySQL / MariaDB: mysqldump --single-transaction compactado, arquivo .sql.gz. As credenciais vão num arquivo
    temporário só do dono (--defaults-extra-file), nunca na linha de comando. Precisa do pacote mysql-client
    (mysqldump e mysql); outro caminho pode ser indicado em MYSQLDUMP_BIN e MYSQL_BIN.
    PostgreSQL: pg_dump no formato próprio (compactado), arquivo .dump. A senha vai num arquivo .pgpass temporário
    só do dono (PGPASSFILE), nunca na linha de comando. Precisa do pacote postgresql-client (pg_dump e pg_restore);
    outro caminho pode ser indicado em PG_DUMP_BIN e PG_RESTORE_BIN.
    SQL Server: o backup fica a cargo do próprio servidor do banco (ou do Azure); a plataforma não gera o arquivo.
- Restauração: .db no SQLite; .sql.gz no MySQL; .dump no PostgreSQL; um .db também restaura em MySQL ou PostgreSQL
  (copiado por copiar_banco.py).
- Agendamentos Diário / Semanal / Mensal com pausa, retenção por agendamento e próxima execução calculada.
- Restauração com cópia de segurança do banco atual antes e com a auditoria preservada
  (os agendamentos e o histórico de execuções não voltam no tempo junto com os dados).
- Todos os arquivos ficam dentro da pasta de backups (BACKUP_DIR; padrão instance/backups), em <subpasta>:
  nada é gravado fora dela. Com BACKUP_DIR_EXTERNO, cada backup ganha uma segunda cópia fora do servidor,
  com a mesma retenção (ambiente.py).
- Instalação nova: criar_agendamentos_padrao() cria Diário (7 cópias), Semanal (4) e Mensal (12).

As funções rodam dentro de um app_context (rotas do Flask ou tarefas_agendadas.py).
"""
import os
import re
import csv
import logging
import gzip
import shutil
import sqlite3
import calendar
import tempfile
import subprocess
from datetime import datetime, timedelta, time as hora_do_dia

from flask import current_app
from werkzeug.utils import secure_filename

from models import db, RegistroBackup, AgendamentoBackup, AlteracaoAgendamentoBackup

FREQUENCIAS = ['Diário', 'Semanal', 'Mensal']
STATUS_OK = ('Concluído', 'Sucesso')          # 'Sucesso' = registros antigos
TIPOS_BACKUP = ('Imediato', 'Agendado', 'Agendado (manual)')
DIAS_SEM_BACKUP_ATENCAO = 8                   # sem backup bem-sucedido há mais tempo que isto: "Atenção"
TABELAS_PRESERVADAS = ('agendamento_backup', 'alteracao_agendamento_backup', 'registro_backup')
EXTENSOES = ('.db', '.sql.gz', '.dump')       # SQLite, MySQL e PostgreSQL


def motor():
    """Banco em uso: 'sqlite', 'mysql', 'postgresql'..."""
    return db.engine.dialect.name


def eh_mysql():
    return motor() in ('mysql', 'mariadb')


def eh_postgresql():
    return motor() == 'postgresql'


# ------------------------------------------------------------------------------
# Caminhos
# ------------------------------------------------------------------------------
def caminho_banco():
    return db.engine.url.database if os.path.isabs(db.engine.url.database or '') else os.path.join(current_app.instance_path, 'mentoria.db')


def pasta_base():
    import ambiente
    pasta = ambiente.pasta_backups(current_app.instance_path)
    os.makedirs(pasta, exist_ok=True)
    return pasta


def nome_de_pasta(nome):
    """Subpasta segura (só letras, números, - e _). Vazio vira 'manuais'."""
    return secure_filename((nome or '').strip()) or 'manuais'


def pasta_de(subpasta):
    pasta = os.path.join(pasta_base(), nome_de_pasta(subpasta))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def caminho_seguro(relativo):
    """Caminho dentro da pasta de backups ou None (bloqueia ../ e caminhos absolutos)."""
    base = os.path.realpath(pasta_base())
    alvo = os.path.realpath(os.path.join(base, relativo or ''))
    return alvo if alvo.startswith(base + os.sep) and os.path.isfile(alvo) else None


def subpastas():
    return sorted(d for d in os.listdir(pasta_base()) if os.path.isdir(os.path.join(pasta_base(), d)) and d != 'auditoria')


def listar_backups():
    """Arquivos .db disponíveis para restaurar ou baixar, do mais novo para o mais antigo."""
    itens = []
    base = pasta_base()
    for raiz, _, arquivos in os.walk(base):
        for nome in arquivos:
            if nome.endswith(EXTENSOES):
                completo = os.path.join(raiz, nome)
                itens.append({'relativo': os.path.relpath(completo, base).replace('\\', '/'), 'nome': nome,
                              'tamanho': os.path.getsize(completo), 'data': datetime.fromtimestamp(os.path.getmtime(completo))})
    return sorted(itens, key=lambda i: i['data'], reverse=True)


def tamanho_legivel(n):
    if n is None:
        return '—'
    for unidade in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unidade == 'GB':
            return f"{n:.0f} {unidade}" if unidade == 'B' else f"{n:.1f} {unidade}".replace('.0 ', ' ')
        n /= 1024


# ------------------------------------------------------------------------------
# Cópia, verificação e registro
# ------------------------------------------------------------------------------
def verificar_integridade(caminho):
    """(ok, mensagem): arquivo íntegro (SQLite .db ou dump do MySQL .sql.gz) e com as tabelas da plataforma."""
    if caminho.endswith('.sql.gz'):
        return _verificar_dump(caminho)
    if caminho.endswith('.dump'):
        return _verificar_dump_postgresql(caminho)
    try:
        with open(caminho, 'rb') as f:
            if f.read(16) != b'SQLite format 3\x00':
                return False, 'o arquivo não é um banco SQLite'
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        try:
            resultado = con.execute('PRAGMA integrity_check').fetchone()[0]
            tem_usuarios = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='usuario'").fetchone()
        finally:
            con.close()
        if resultado != 'ok':
            return False, f'integridade: {resultado}'
        if not tem_usuarios:
            return False, 'o banco não tem as tabelas da plataforma'
        return True, 'íntegro'
    except Exception as e:
        return False, str(e)


def registrar(tipo, status, detalhes, usuario_id=None, arquivo=None, tamanho=None, duracao=None, destino=None, agendamento_id=None):
    registro = RegistroBackup(tipo=tipo, status=status, detalhes=detalhes, usuario_id=usuario_id, arquivo=arquivo,
                              tamanho_bytes=tamanho, duracao_seg=duracao, destino=destino, agendamento_id=agendamento_id,
                              data_registro=datetime.now())
    db.session.add(registro)
    db.session.commit()
    return registro


def copiar_banco(subpasta, prefixo):
    """Gera a cópia e confere a integridade. Devolve (caminho, tamanho, duração); levanta erro se falhar."""
    import ambiente
    inicio = datetime.now()
    pode, motivo = ambiente.disponivel('backup')
    if not pode:
        raise RuntimeError(motivo)
    extensao = '.sql.gz' if eh_mysql() else '.dump' if eh_postgresql() else '.db'
    nome = f"{prefixo}_{inicio.strftime('%Y%m%d_%H%M%S_%f')}" + extensao
    destino = os.path.join(pasta_de(subpasta), nome)
    db.session.commit()  # nada pendente na sessão antes da cópia
    if eh_mysql() or eh_postgresql():
        try:
            (_dump_mysql if eh_mysql() else _dump_postgresql)(destino)
        except Exception:
            if os.path.exists(destino):
                os.remove(destino)
            raise
    else:
        origem = sqlite3.connect(caminho_banco())
        copia = sqlite3.connect(destino)
        try:
            origem.backup(copia)
        finally:
            copia.close()
            origem.close()
    ok, mensagem = verificar_integridade(destino)
    if not ok:
        os.remove(destino)
        raise RuntimeError(f"cópia descartada, {mensagem}")
    return destino, os.path.getsize(destino), round((datetime.now() - inicio).total_seconds(), 2)


def fazer_backup(tipo, subpasta, usuario_id=None, agendamento=None):
    """Backup + registro no histórico. Devolve o RegistroBackup (status Concluído ou Falha)."""
    prefixo = f"mentoria_backup_ag{agendamento.id}_{_sem_acento(agendamento.frequencia)}" if agendamento else "mentoria_backup"
    try:
        caminho, tamanho, duracao = copiar_banco(subpasta, prefixo)
        nome = os.path.basename(caminho)
        detalhes = f"Backup criado e validado: {nome} ({tamanho_legivel(tamanho)})"
        externa = copiar_para_fora(caminho, subpasta)
        if externa:
            detalhes += f"; cópia fora do servidor: {externa}"
        if agendamento:
            removidos = aplicar_retencao(agendamento)
            if removidos:
                detalhes += f"; {removidos} arquivo(s) antigo(s) removido(s) pela retenção"
        return registrar(tipo, 'Concluído', detalhes, usuario_id, nome, tamanho, duracao, nome_de_pasta(subpasta),
                         agendamento.id if agendamento else None)
    except Exception as e:
        db.session.rollback()
        return registrar(tipo, 'Falha', f"Erro no backup: {e}", usuario_id, destino=nome_de_pasta(subpasta),
                         agendamento_id=agendamento.id if agendamento else None)


def _sem_acento(texto):
    return {'Diário': 'diario', 'Semanal': 'semanal', 'Mensal': 'mensal'}.get(texto, re.sub(r'\W', '', texto.lower()))


def aplicar_retencao(agendamento):
    """Mantém só os N arquivos mais novos deste agendamento. Devolve quantos foram apagados."""
    pasta = pasta_de(agendamento.pasta)
    proprios = sorted((n for n in os.listdir(pasta) if n.startswith(f"mentoria_backup_ag{agendamento.id}_") and n.endswith(EXTENSOES)),
                      reverse=True)  # o nome tem a data: ordem alfabética = cronológica
    apagados = 0
    for nome in proprios[max(agendamento.retencao or 1, 1):]:
        os.remove(os.path.join(pasta, nome))
        apagados += 1
    # A cópia fora do servidor segue a mesma retenção
    import ambiente
    externa = ambiente.pasta_backups_externa()
    pasta_fora = os.path.join(externa, nome_de_pasta(agendamento.pasta)) if externa else ''
    if pasta_fora and os.path.isdir(pasta_fora):
        fora = sorted((n for n in os.listdir(pasta_fora) if n.startswith(f"mentoria_backup_ag{agendamento.id}_") and n.endswith(EXTENSOES)),
                      reverse=True)
        for nome in fora[max(agendamento.retencao or 1, 1):]:
            try:
                os.remove(os.path.join(pasta_fora, nome))
            except OSError:
                pass
    return apagados


def copiar_para_fora(caminho, subpasta):
    """Segunda cópia em BACKUP_DIR_EXTERNO/<subpasta> (disco de rede, volume da nuvem, pasta do rclone).
    Devolve o caminho da cópia ou '' (sem pasta externa ou falha: o backup principal continua valendo)."""
    import ambiente
    externa = ambiente.pasta_backups_externa()
    if not externa:
        return ''
    try:
        destino = os.path.join(externa, nome_de_pasta(subpasta))
        os.makedirs(destino, exist_ok=True)
        alvo = os.path.join(destino, os.path.basename(caminho))
        shutil.copy2(caminho, alvo + '.parcial')
        os.replace(alvo + '.parcial', alvo)   # nunca deixa uma cópia pela metade com o nome final
        return alvo
    except OSError as e:
        logging.getLogger("backup").warning("Cópia externa do backup falhou: %s", e)
        return ''


def criar_agendamentos_padrao(usuario_id=None):
    """Instalação nova: Diário, Semanal e Mensal (ambiente.AGENDAMENTOS_PADRAO) nas subpastas diario, semanal e mensal.
    Não faz nada se já existe algum agendamento. Devolve quantos criou."""
    import ambiente
    if AgendamentoBackup.query.count():
        return 0
    agora = datetime.now()
    for frequencia, horario, pasta, retencao in ambiente.AGENDAMENTOS_PADRAO:
        agendamento = AgendamentoBackup(frequencia=frequencia, horario=horario, data_inicio=agora.date(), status='Ativo',
                                        retencao=retencao, pasta=pasta, criado_por_id=usuario_id)
        agendamento.proxima_execucao = calcular_proxima(agendamento, agora)
        db.session.add(agendamento)
        db.session.flush()
        registrar_alteracao(agendamento.id, 'Criado', 'Agendamento padrão da instalação: ' + descrever(agendamento), usuario_id)
        try:
            pasta_de(pasta)
        except OSError:
            pass   # sem permissão agora: a tela Ambiente e compatibilidade mostra como resolver
    db.session.commit()
    return len(ambiente.AGENDAMENTOS_PADRAO)


# ------------------------------------------------------------------------------
# Agendamentos
# ------------------------------------------------------------------------------
def _somar_meses(data, meses):
    mes = data.month - 1 + meses
    ano, mes = data.year + mes // 12, mes % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


def calcular_proxima(agendamento, depois_de):
    """Primeira data/hora do agendamento estritamente depois de 'depois_de'."""
    horas, minutos = (int(x) for x in (agendamento.horario or '03:00').split(':'))
    base = datetime.combine(agendamento.data_inicio, hora_do_dia(horas, minutos))
    if base > depois_de:
        return base
    if agendamento.frequencia == 'Mensal':
        n = (depois_de.year - base.year) * 12 + depois_de.month - base.month
        candidato = _somar_meses(base, max(n, 0))
        while candidato <= depois_de:
            n += 1
            candidato = _somar_meses(base, n)
        return candidato
    passo = timedelta(days=7 if agendamento.frequencia == 'Semanal' else 1)
    saltos = int((depois_de - base) / passo) + 1
    return base + saltos * passo


def registrar_alteracao(agendamento_id, acao, detalhes, usuario_id):
    db.session.add(AlteracaoAgendamentoBackup(agendamento_id=agendamento_id, acao=acao, detalhes=detalhes,
                                              usuario_id=usuario_id, data=datetime.now()))


def descrever(agendamento):
    return (f"{agendamento.frequencia} às {agendamento.horario}, início {agendamento.data_inicio.strftime('%d/%m/%Y')}, "
            f"retenção {agendamento.retencao}, pasta {agendamento.pasta}")


def executar_agendamento(agendamento, usuario_id=None):
    """Roda um agendamento agora (pelo relógio ou pelo botão 'Executar agora')."""
    tipo = 'Agendado (manual)' if usuario_id else 'Agendado'
    registro = fazer_backup(tipo, agendamento.pasta, usuario_id=usuario_id, agendamento=agendamento)
    agendamento.ultima_execucao = registro.data_registro
    db.session.commit()
    return registro


def executar_vencidos(agora=None):
    """Roda os agendamentos ativos com a próxima execução vencida. Devolve quantos rodaram."""
    agora = agora or datetime.now()
    vencidos = AgendamentoBackup.query.filter(AgendamentoBackup.status == 'Ativo',
                                              AgendamentoBackup.proxima_execucao <= agora).all()
    for agendamento in vencidos:
        # "Reserva" a execução antes de copiar: outro processo que olhar agora já vê a próxima data
        agendamento.proxima_execucao = calcular_proxima(agendamento, agora)
        db.session.commit()
        executar_agendamento(agendamento)
    return len(vencidos)


# ------------------------------------------------------------------------------
# Saúde
# ------------------------------------------------------------------------------
def saude():
    ativos = AgendamentoBackup.query.filter_by(status='Ativo').all()
    pausados = AgendamentoBackup.query.filter_by(status='Pausado').count()
    backups = RegistroBackup.query.filter(RegistroBackup.tipo.in_(TIPOS_BACKUP))
    ultimo_ok = backups.filter(RegistroBackup.status.in_(STATUS_OK)).order_by(RegistroBackup.data_registro.desc()).first()
    ultimo = backups.order_by(RegistroBackup.data_registro.desc()).first()
    falhas = RegistroBackup.query.filter_by(status='Falha').count()
    proximas = [a.proxima_execucao for a in ativos if a.proxima_execucao]
    if ultimo and ultimo.status == 'Falha':
        situacao, motivo = 'Crítica', 'O último backup falhou.'
    elif not ativos:
        situacao, motivo = 'Atenção', 'Nenhum agendamento ativo.'
    elif not ultimo_ok or ultimo_ok.data_registro < datetime.now() - timedelta(days=DIAS_SEM_BACKUP_ATENCAO):
        situacao, motivo = 'Atenção', 'Nenhum backup bem-sucedido nos últimos 8 dias.'
    else:
        situacao, motivo = 'Saudável', ''
    return {'ativos': len(ativos), 'pausados': pausados, 'ultimo': ultimo_ok.data_registro if ultimo_ok else None,
            'proximo': min(proximas) if proximas else None, 'falhas': falhas, 'situacao': situacao, 'motivo': motivo}


# ------------------------------------------------------------------------------
# Restauração e limpeza
# ------------------------------------------------------------------------------
def _identificador(nome, permitidos):
    """Nome de tabela/coluna para SQL dinâmico: só da lista fixa (ou do próprio esquema), só [a-z0-9_] e entre aspas."""
    if nome not in permitidos or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', nome):
        raise ValueError(f"Identificador SQL não permitido: {nome!r}")
    return '"' + nome + '"'


def _tabela(nome):
    _identificador(nome, TABELAS_PRESERVADAS)
    return db.metadata.tables[nome]


def _ler_tabelas_preservadas():
    """Agendamentos e histórico de backups (pelo SQLAlchemy: vale para qualquer banco)."""
    from sqlalchemy import select
    with db.engine.connect() as con:
        return {t: [dict(r._mapping) for r in con.execute(select(_tabela(t)))] for t in TABELAS_PRESERVADAS}


def _gravar_tabelas_preservadas(dados):
    from sqlalchemy import inspect
    with db.engine.begin() as con:
        for nome, linhas in dados.items():
            tabela = _tabela(nome)
            colunas_atuais = {c['name'] for c in inspect(con).get_columns(nome)}
            con.execute(tabela.delete())
            linhas = [{k: v for k, v in linha.items() if k in colunas_atuais} for linha in linhas]
            if linhas:
                con.execute(tabela.insert(), linhas)


def restaurar(caminho_arquivo, usuario_id, atualizar_estrutura):
    """Restaura o banco a partir de um arquivo validado. Devolve (ok, mensagem)."""
    ok, mensagem = verificar_integridade(caminho_arquivo)
    nome = os.path.basename(caminho_arquivo)
    if ok and caminho_arquivo.endswith('.sql.gz') and not eh_mysql():
        ok, mensagem = False, 'backup do MySQL (.sql.gz) só restaura num banco MySQL'
    if ok and caminho_arquivo.endswith('.dump') and not eh_postgresql():
        ok, mensagem = False, 'backup do PostgreSQL (.dump) só restaura num banco PostgreSQL'
    if not ok:
        registrar('Restauração', 'Falha', f"Arquivo recusado ({nome}): {mensagem}", usuario_id, arquivo=nome)
        return False, mensagem
    seguranca = fazer_backup('Segurança (pré-restauração)', 'seguranca', usuario_id)
    if seguranca.status != 'Concluído':
        return False, 'não foi possível guardar a cópia de segurança do banco atual'

    preservadas = _ler_tabelas_preservadas()
    inicio = datetime.now()
    db.session.remove()
    db.engine.dispose()
    if caminho_arquivo.endswith('.sql.gz'):
        _restaurar_mysql(caminho_arquivo)
    elif caminho_arquivo.endswith('.dump'):
        _restaurar_postgresql(caminho_arquivo)
    elif motor() == 'sqlite':
        origem = sqlite3.connect(f"file:{caminho_arquivo}?mode=ro", uri=True)
        destino = sqlite3.connect(caminho_banco())
        try:
            origem.backup(destino)
        finally:
            destino.close()
            origem.close()
    else:  # backup .db (SQLite) restaurado num MySQL/PostgreSQL: cópia tabela a tabela
        import copiar_banco
        copiar_banco.copiar('sqlite:///' + os.path.abspath(caminho_arquivo).replace('\\', '/'),
                            db.engine.url.render_as_string(hide_password=False), substituir=True, avisar=lambda *_: None)
        db.engine.dispose()
    atualizar_estrutura()          # backup antigo pode não ter as tabelas/colunas novas
    _gravar_tabelas_preservadas(preservadas)
    registrar('Restauração', 'Concluído',
              f"Banco restaurado a partir de {nome}. Cópia do banco anterior: {seguranca.arquivo}. "
              f"Agendamentos e histórico de backups preservados.",
              usuario_id, arquivo=nome, tamanho=os.path.getsize(caminho_arquivo),
              duracao=round((datetime.now() - inicio).total_seconds(), 2))
    return True, seguranca.arquivo


def exportar_historico_csv(registros, destino_arquivo=None):
    """Linhas do histórico em CSV (para o relatório de auditoria ou o arquivo guardado antes de apagar)."""
    cabecalho = ['Data/Hora', 'Tipo', 'Status', 'Arquivo', 'Tamanho', 'Duração (s)', 'Usuário', 'Pasta', 'Agendamento', 'Detalhes']
    linhas = [[r.data_registro.strftime('%d/%m/%Y %H:%M:%S') if r.data_registro else '', r.tipo, r.status, r.arquivo or '',
               tamanho_legivel(r.tamanho_bytes), r.duracao_seg if r.duracao_seg is not None else '',
               r.autor.nome if r.autor else 'sistema', r.destino or '', r.agendamento_id or '', r.detalhes or '']
              for r in registros]
    if destino_arquivo:
        with open(destino_arquivo, 'w', newline='', encoding='utf-8-sig') as f:
            escritor = csv.writer(f, delimiter=';')
            escritor.writerow(cabecalho)
            escritor.writerows(linhas)
    return cabecalho, linhas


def apagar_historico(usuario_id, usuario_nome):
    """Guarda o histórico em CSV (instance/backups/auditoria) antes de apagar e registra quem apagou."""
    registros = RegistroBackup.query.order_by(RegistroBackup.data_registro).all()
    pasta = os.path.join(pasta_base(), 'auditoria')
    os.makedirs(pasta, exist_ok=True)
    arquivo = os.path.join(pasta, f"historico_backups_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    exportar_historico_csv(registros, arquivo)
    total = len(registros)
    RegistroBackup.query.delete()
    db.session.commit()
    registrar('Limpeza do histórico', 'Concluído',
              f"{total} registro(s) apagado(s) por {usuario_nome}. Cópia guardada em auditoria/{os.path.basename(arquivo)}.",
              usuario_id, arquivo=os.path.basename(arquivo))
    return total, os.path.basename(arquivo)


# ------------------------------------------------------------------------------
# Migração do formato antigo (agendamento gravado como linha "Pendente" no histórico)
# ------------------------------------------------------------------------------
def migrar_agendamentos_antigos():
    """Converte uma única vez os agendamentos antigos em AgendamentoBackup (a linha antiga vira 'Migrado')."""
    antigos = RegistroBackup.query.filter_by(tipo='Agendado', status='Pendente').all()
    for registro in antigos:
        try:
            alvo = datetime.strptime((registro.data_agendada or '').replace(' às ', ' '), '%Y-%m-%d %H:%M')
        except ValueError:
            alvo = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
        texto = (registro.detalhes or '').lower()
        frequencia = 'Semanal' if 'semanal' in texto else 'Mensal' if 'mensal' in texto else 'Diário'
        agendamento = AgendamentoBackup(frequencia=frequencia, horario=alvo.strftime('%H:%M'), data_inicio=alvo.date(),
                                        status='Ativo', retencao=7, pasta='agendados', criado_por_id=registro.usuario_id)
        db.session.add(agendamento)
        db.session.flush()
        agendamento.proxima_execucao = calcular_proxima(agendamento, datetime.now())
        registrar_alteracao(agendamento.id, 'Migrado',
                            f"Convertido do formato antigo ({registro.data_agendada}, {registro.detalhes}; pasta antiga {registro.destino})",
                            registro.usuario_id)
        registro.status = 'Migrado'
    if antigos:
        db.session.commit()


# ------------------------------------------------------------------------------
# MySQL / MariaDB: mysqldump e mysql com credenciais num arquivo temporário (nunca na linha de comando)
# ------------------------------------------------------------------------------
def _programa(variavel, nomes):
    for nome in [os.environ.get(variavel)] + list(nomes):
        if nome and (shutil.which(nome) or os.path.isfile(nome)):
            return shutil.which(nome) or nome
    raise RuntimeError(f"{nomes[0]} não encontrado: instale o pacote mysql-client (Ubuntu: sudo apt install mysql-client) "
                       f"ou indique o caminho em {variavel}")


def _arquivo_de_credenciais():
    """Arquivo [client] só do dono (0600) com usuário, senha, servidor e porta do DATABASE_URL. Apague depois de usar."""
    url = db.engine.url
    def valor(v):
        return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'
    linhas = ['[client]', f'user={valor(url.username or "")}', f'password={valor(url.password or "")}',
              f'host={valor(url.host or "localhost")}', 'default-character-set=utf8mb4']
    if url.port:
        linhas.append(f'port={int(url.port)}')
    if url.query.get('unix_socket'):
        linhas.append(f'socket={valor(url.query["unix_socket"])}')
    descritor, caminho = tempfile.mkstemp(prefix='mentoria_', suffix='.cnf')
    with os.fdopen(descritor, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas) + '\n')
    os.chmod(caminho, 0o600)
    return caminho


def _erro_limpo(texto):
    from base_conhecimento import sem_segredos
    return sem_segredos((texto or b'').decode('utf-8', 'replace').strip())[:300] or 'erro desconhecido'


def _dump_mysql(destino):
    """mysqldump --single-transaction (cópia consistente sem travar o site), compactado em .sql.gz."""
    programa = _programa('MYSQLDUMP_BIN', ('mysqldump', 'mariadb-dump'))
    credenciais = _arquivo_de_credenciais()
    try:
        processo = subprocess.Popen([programa, f'--defaults-extra-file={credenciais}', '--single-transaction', '--quick',
                                     '--routines', '--triggers', '--no-tablespaces', '--default-character-set=utf8mb4',
                                     db.engine.url.database], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.open(destino, 'wb') as saida:
            shutil.copyfileobj(processo.stdout, saida)
        erros = processo.stderr.read()
        if processo.wait() != 0:
            raise RuntimeError(f'mysqldump falhou: {_erro_limpo(erros)}')
    finally:
        os.remove(credenciais)


def _verificar_dump(caminho):
    """(ok, mensagem): .sql.gz legível, do mysqldump, completo e com as tabelas da plataforma."""
    try:
        inicio, tem_usuario, ultima = '', False, ''
        with gzip.open(caminho, 'rt', encoding='utf-8', errors='replace') as f:
            for n, linha in enumerate(f):
                if n < 5:
                    inicio += linha
                if not tem_usuario and linha.startswith('CREATE TABLE `usuario`'):
                    tem_usuario = True
                if linha.strip():
                    ultima = linha.strip()
        if 'dump' not in inicio.lower():
            return False, 'o arquivo não é um backup do mysqldump'
        if not ultima.startswith('-- Dump completed'):
            return False, 'o backup está incompleto (o mysqldump não terminou)'
        if not tem_usuario:
            return False, 'o backup não tem as tabelas da plataforma'
        return True, 'íntegro'
    except (OSError, EOFError, gzip.BadGzipFile) as e:
        return False, f'arquivo compactado inválido: {e}'


def _restaurar_mysql(caminho_arquivo):
    """Envia o .sql.gz ao cliente mysql (o dump apaga e recria cada tabela)."""
    programa = _programa('MYSQL_BIN', ('mysql', 'mariadb'))
    credenciais = _arquivo_de_credenciais()
    try:
        processo = subprocess.Popen([programa, f'--defaults-extra-file={credenciais}', '--default-character-set=utf8mb4',
                                     db.engine.url.database], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with gzip.open(caminho_arquivo, 'rb') as entrada:
            shutil.copyfileobj(entrada, processo.stdin)
        processo.stdin.close()
        erros = processo.stderr.read()
        if processo.wait() != 0:
            raise RuntimeError(f'mysql falhou ao restaurar: {_erro_limpo(erros)}')
    finally:
        os.remove(credenciais)


# ------------------------------------------------------------------------------
# PostgreSQL: pg_dump e pg_restore com a senha num .pgpass temporário (nunca na linha de comando)
# ------------------------------------------------------------------------------
def _programa_pg(variavel, nome):
    for opcao in (os.environ.get(variavel), nome):
        if opcao and (shutil.which(opcao) or os.path.isfile(opcao)):
            return shutil.which(opcao) or opcao
    raise RuntimeError(f"{nome} não encontrado: instale o pacote postgresql-client (Ubuntu: sudo apt install postgresql-client) "
                       f"ou indique o caminho em {variavel}")


def _conexao_pg():
    """(argumentos de conexão sem senha, ambiente com PGPASSFILE, caminho do .pgpass para apagar depois)."""
    url = db.engine.url
    host, porta = url.host or 'localhost', str(url.port or 5432)
    usuario, banco = url.username or '', url.database or ''

    def escapar(v):
        return str(v).replace(chr(92), chr(92) * 2).replace(':', chr(92) + ':')   # .pgpass escapa \ e : com \
    descritor, caminho = tempfile.mkstemp(prefix='mentoria_', suffix='.pgpass')
    with os.fdopen(descritor, 'w', encoding='utf-8') as f:
        f.write(':'.join(escapar(v) for v in (host, porta, banco, usuario, url.password or '')) + '\n')
    os.chmod(caminho, 0o600)
    ambiente_pg = dict(os.environ, PGPASSFILE=caminho)
    ambiente_pg.pop('PGPASSWORD', None)
    return ['--host', host, '--port', porta, '--username', usuario, '--no-password'], banco, ambiente_pg, caminho


def _dump_postgresql(destino):
    """pg_dump no formato próprio (-Fc): compactado, consistente com o site no ar e restaurável tabela a tabela."""
    programa = _programa_pg('PG_DUMP_BIN', 'pg_dump')
    argumentos, banco, ambiente_pg, credenciais = _conexao_pg()
    try:
        r = subprocess.run([programa, *argumentos, '--format=custom', '--no-owner', '--file', destino, banco],
                           env=ambiente_pg, capture_output=True, timeout=3600)
        if r.returncode != 0:
            raise RuntimeError(f'pg_dump falhou: {_erro_limpo(r.stderr)}')
    finally:
        os.remove(credenciais)


def _verificar_dump_postgresql(caminho):
    """(ok, mensagem): o pg_restore lê o índice do arquivo e ele tem a tabela usuario."""
    try:
        with open(caminho, 'rb') as f:
            if f.read(5) != b'PGDMP':
                return False, 'o arquivo não é um backup do pg_dump'
        programa = _programa_pg('PG_RESTORE_BIN', 'pg_restore')
        r = subprocess.run([programa, '--list', caminho], capture_output=True, timeout=300)
        if r.returncode != 0:
            return False, f'arquivo ilegível: {_erro_limpo(r.stderr)}'
        if not re.search(r'TABLE \S+ usuario ', r.stdout.decode('utf-8', 'replace')):
            return False, 'o backup não tem as tabelas da plataforma'
        return True, 'íntegro'
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def _restaurar_postgresql(caminho_arquivo):
    """pg_restore --clean: apaga e recria cada objeto do backup, numa única transação."""
    programa = _programa_pg('PG_RESTORE_BIN', 'pg_restore')
    argumentos, banco, ambiente_pg, credenciais = _conexao_pg()
    try:
        r = subprocess.run([programa, *argumentos, '--clean', '--if-exists', '--no-owner', '--single-transaction',
                            '--dbname', banco, caminho_arquivo], env=ambiente_pg, capture_output=True, timeout=3600)
        if r.returncode != 0:
            raise RuntimeError(f'pg_restore falhou: {_erro_limpo(r.stderr)}')
    finally:
        os.remove(credenciais)
