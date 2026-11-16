# -*- coding: utf-8 -*-
"""
CONHECIMENTO DE BANCO DE DADOS — o que o Gerente de Banco de Dados aprende e ensina aos 5 agentes de banco
=======================================================================================================
Mesmas regras de governança dos outros gerentes (conhecimento.py): assinatura SHA-256, trilha de eventos,
revogação e limpeza para compliance na tela Governança de aprendizados.

1. Detecção interna (autônoma, aplicada na hora): o Gerente compara o banco com o último retrato e ensina:
     - motor do banco (SQLite hoje; PostgreSQL, MySQL, SQL Server…) → todos os agentes de banco;
     - tabelas, colunas e índices novos/removidos                    → Esquema e Índices + Consultas e Desempenho;
     - agendamentos de backup criados/alterados/pausados             → Backup e Recuperação.
   Também guarda o histórico de tamanho do banco e de linhas por tabela (o DBA usa para prever o crescimento).
   Roda ao iniciar a análise, no botão "Aprender agora" e de hora em hora (tarefas_agendadas.py).
2. Fontes oficiais (só domínios da lista de Fontes confiáveis, HTTPS) — ficam PENDENTES até a aprovação:
     - a documentação oficial do motor em uso e de cada banco pedido na tela (SQLite, PostgreSQL, MySQL, SQL Server, MongoDB);
     - a página oficial ligada a cada tipo de problema que os agentes encontrarem (planejador de consultas, VACUUM…).
"""
import json
import sqlite3
from datetime import datetime

from sqlalchemy import inspect

import conhecimento
from conhecimento import criar_aprendizado, aprendizados_para, registrar_consumo, evento, _estado, _gravar_estado
from models import db, AprendizadoAgente

GERENTE_BANCO = 'Gerente de Banco de Dados'
GRUPO = 'banco'
AGENTES_BANCO = ['db_consultas', 'db_esquema', 'db_backup', 'db_dba', 'db_portabilidade']
TIPOS = {'db_linha_base': 'Linha de base do banco', 'db_esquema': 'Esquema mudou', 'db_backup': 'Agendamento de backup mudou',
         'db_motor': 'Motor do banco mudou'}
MOTORES = {'sqlite': 'SQLite', 'postgresql': 'PostgreSQL', 'mysql': 'MySQL', 'mssql': 'SQL Server', 'mongodb': 'MongoDB'}
# Documentação oficial de cada banco (os domínios precisam estar nas Fontes confiáveis)
DOCS = {
    'sqlite': [('https://www.sqlite.org/queryplanner.html', 'SQLite: como o planejador de consultas usa índices'),
               ('https://www.sqlite.org/lang_analyze.html', 'SQLite: ANALYZE e estatísticas'),
               ('https://www.sqlite.org/lang_vacuum.html', 'SQLite: VACUUM'),
               ('https://www.sqlite.org/wal.html', 'SQLite: Write-Ahead Logging (WAL)'),
               ('https://www.sqlite.org/backup.html', 'SQLite: API de backup online')],
    'postgresql': [('https://www.postgresql.org/docs/current/performance-tips.html', 'PostgreSQL: dicas de desempenho'),
                   ('https://www.postgresql.org/docs/current/routine-vacuuming.html', 'PostgreSQL: VACUUM de rotina'),
                   ('https://www.postgresql.org/docs/current/backup.html', 'PostgreSQL: backup e restauração')],
    'mysql': [('https://dev.mysql.com/doc/refman/8.4/en/optimization.html', 'MySQL: otimização'),
              ('https://dev.mysql.com/doc/refman/8.4/en/backup-and-recovery.html', 'MySQL: backup e recuperação')],
    'mssql': [('https://learn.microsoft.com/en-us/sql/relational-databases/performance/performance-monitoring-and-tuning-tools',
               'SQL Server: ferramentas de monitoramento e ajuste de desempenho'),
              ('https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/back-up-and-restore-of-sql-server-databases',
               'SQL Server: backup e restauração')],
    'mongodb': [('https://www.mongodb.com/docs/manual/core/query-optimization/', 'MongoDB: otimização de consultas'),
                ('https://www.mongodb.com/docs/manual/core/backups/', 'MongoDB: backups')],
}
# Categoria do achado → página oficial do SQLite que ensina o assunto
DOC_POR_CATEGORIA = {'Desempenho de consultas': DOCS['sqlite'][0], 'Índices': DOCS['sqlite'][0], 'Manutenção': DOCS['sqlite'][1],
                     'Configuração do banco': DOCS['sqlite'][3], 'Backup e recuperação': DOCS['sqlite'][4]}
DESTINO_POR_CATEGORIA = {'Desempenho de consultas': 'db_consultas', 'Índices': 'db_esquema', 'Manutenção': 'db_dba',
                         'Configuração do banco': 'db_dba', 'Backup e recuperação': 'db_backup'}


# ------------------------------------------------------------------------------ retrato
def motor_atual():
    dialeto = db.engine.dialect.name
    versao = sqlite3.sqlite_version if dialeto == 'sqlite' else '.'.join(str(p) for p in (db.engine.dialect.server_version_info or ()))
    return {'dialeto': dialeto, 'nome': MOTORES.get(dialeto, dialeto), 'versao': versao}


def _tabelas():
    insp = inspect(db.engine)
    tabelas = {}
    for nome in sorted(insp.get_table_names()):
        tabelas[nome] = {'colunas': sorted(c['name'] for c in insp.get_columns(nome)),
                         'indices': sorted(f"{i['name']}({','.join(c for c in i['column_names'] if c)})" for i in insp.get_indexes(nome)),
                         'fks': sorted(f"{','.join(fk['constrained_columns'])}->{fk['referred_table']}" for fk in insp.get_foreign_keys(nome))}
    return tabelas


def _agendamentos():
    from models import AgendamentoBackup
    return {str(a.id): {'frequencia': a.frequencia, 'horario': a.horario, 'status': a.status, 'retencao': a.retencao, 'pasta': a.pasta}
            for a in AgendamentoBackup.query.all()}


DRIVERS = {'postgresql': ('psycopg', 'psycopg2', 'psycopg2-binary'), 'mysql': ('pymysql', 'mysqlclient', 'mysql-connector-python'),
           'mssql': ('pyodbc', 'pymssql'), 'mongodb': ('pymongo', 'mongoengine')}


def _drivers():
    """Bancos cujos drivers estão instalados: sinal de que a equipe vai precisar desse conhecimento."""
    from importlib import metadata
    instalados = {d.metadata['Name'].lower() for d in metadata.distributions() if d.metadata['Name']}
    return sorted(motor for motor, pacotes in DRIVERS.items() if instalados & set(pacotes))


def retrato_banco():
    return {'motor': motor_atual(), 'tabelas': _tabelas(), 'agendamentos': _agendamentos(), 'drivers': _drivers()}


def _criar(titulo, tipo, conteudo, destino, descricao, origem, **extra):
    return criar_aprendizado(titulo, tipo, conteudo, destino, descricao, origem, gerente=GERENTE_BANCO, **extra)


def _registrar_historico():
    """Uma foto por dia do tamanho do banco e das linhas por tabela (base da previsão de crescimento)."""
    import os
    import backup_servico
    historico = _estado('historico_banco', [])
    hoje = datetime.now().strftime('%Y-%m-%d')
    if historico and historico[-1]['dia'] == hoje:
        return
    linhas = {}
    with db.engine.connect() as con:
        for tabela in inspect(db.engine).get_table_names():
            linhas[tabela] = con.exec_driver_sql('SELECT COUNT(*) FROM "' + tabela.replace('"', '') + '"').scalar()
    caminho = backup_servico.caminho_banco() if db.engine.dialect.name == 'sqlite' else None
    historico.append({'dia': hoje, 'bytes': os.path.getsize(caminho) if caminho and os.path.exists(caminho) else None, 'linhas': linhas})
    _gravar_estado('historico_banco', historico[-180:])


# ------------------------------------------------------------------------------ 1. detecção interna (autônoma)
def detectar_mudancas(origem=GERENTE_BANCO):
    atual = retrato_banco()
    anterior = _estado('retrato_banco', None)
    criados = []
    if anterior is None:
        criados.append(_criar('Linha de base do banco de dados registrada', 'db_linha_base',
                              {'motor': atual['motor'], 'tabelas': {t: {'indices': d['indices'], 'fks': d['fks']} for t, d in atual['tabelas'].items()}},
                              [GRUPO], f"{atual['motor']['nome']} {atual['motor']['versao']}: {len(atual['tabelas'])} tabela(s), "
                              f"{sum(len(d['indices']) for d in atual['tabelas'].values())} índice(s), {len(atual['agendamentos'])} agendamento(s) de backup.",
                              origem))
        anterior = {'motor': atual['motor'], 'tabelas': atual['tabelas'], 'agendamentos': atual['agendamentos']}

    if anterior['motor']['dialeto'] != atual['motor']['dialeto']:
        criados.append(_criar(f"Motor do banco mudou: {anterior['motor']['nome']} → {atual['motor']['nome']}", 'db_motor',
                              {'antes': anterior['motor'], 'depois': atual['motor']}, [GRUPO],
                              'Os agentes passam a aplicar as regras do novo motor; o Gerente propõe a documentação oficial dele.', origem))

    ta, tb = anterior['tabelas'], atual['tabelas']
    mudancas = {'tabelas_novas': sorted(set(tb) - set(ta)), 'tabelas_removidas': sorted(set(ta) - set(tb)),
                'colunas_novas': {t: sorted(set(tb[t]['colunas']) - set(ta[t]['colunas'])) for t in tb if t in ta},
                'indices_novos': {t: sorted(set(tb[t]['indices']) - set(ta[t]['indices'])) for t in tb if t in ta},
                'indices_removidos': {t: sorted(set(ta[t]['indices']) - set(tb[t]['indices'])) for t in tb if t in ta}}
    for chave in ('colunas_novas', 'indices_novos', 'indices_removidos'):
        mudancas[chave] = {t: v for t, v in mudancas[chave].items() if v}
    if any(mudancas.values()):
        # Tabelas são listas; colunas e índices vêm agrupados por tabela: conta os itens, não as tabelas
        partes = [f"{sum(map(len, v.values())) if isinstance(v, dict) else len(v)} {k.replace('_', ' ')}"
                  + (f" em {len(v)} tabela(s)" if isinstance(v, dict) else '') for k, v in mudancas.items() if v]
        criados.append(_criar('Esquema do banco mudou', 'db_esquema', mudancas, ['db_esquema', 'db_consultas', 'db_dba'],
                              'Para revisar índices e consultas: ' + ', '.join(partes) + '.', origem))

    if anterior.get('agendamentos', {}) != atual['agendamentos']:
        criados.append(_criar('Agendamentos de backup mudaram', 'db_backup', {'antes': anterior.get('agendamentos', {}), 'depois': atual['agendamentos']},
                              ['db_backup', 'db_dba'], f"{sum(1 for a in atual['agendamentos'].values() if a['status'] == 'Ativo')} ativo(s) agora.", origem))

    novos_drivers = sorted(set(atual['drivers']) - set(anterior.get('drivers', [])))
    if novos_drivers:
        criados.append(_criar(f"Driver de outro banco instalado: {', '.join(MOTORES[m] for m in novos_drivers)}", 'db_motor',
                              {'antes': anterior['motor'], 'depois': atual['motor'], 'drivers_novos': novos_drivers}, ['db_portabilidade'],
                              'O Gerente busca a documentação oficial desses bancos (pendente de aprovação) para o Agente Multi-banco.', origem))

    _registrar_historico()
    _gravar_estado('retrato_banco', atual)
    _gravar_estado('ultima_deteccao_banco', {'em': datetime.now().isoformat(timespec='seconds'), 'origem': origem, 'novos': len(criados)})
    db.session.commit()
    # Conhecimento sob demanda: o motor em uso (na linha de base ou quando muda) e os bancos com driver novo
    precisa = ([atual['motor']['dialeto']] if any(a.tipo == 'db_linha_base' or (a.tipo == 'db_motor' and 'drivers_novos' not in json.loads(a.conteudo))
                                                  for a in criados) else []) + novos_drivers
    for motor in precisa:
        try:
            aprender_sobre_banco(motor, origem=origem)
        except Exception as e:
            db.session.rollback()
            evento('Busca recusada', f"Documentação de {MOTORES.get(motor, motor)}: {e}", agente=GERENTE_BANCO)
            db.session.commit()
    return criados


# ------------------------------------------------------------------------------ consumo pelos agentes
def para_agente(chave_agente, tipos=None):
    alvo = f"db_{chave_agente}"
    # Referências oficiais: só as enviadas a este agente ou ao grupo de banco (não as genéricas para "todos")
    itens = [a for a in aprendizados_para(alvo, tipos) if a.tipo.startswith('db_')
             or (a.tipo in ('referencia_externa', 'regra_verificada') and alvo in json.loads(a.agentes_destino or '[]'))]
    grupo = [a for a in aprendizados_para(GRUPO, tipos) if a not in itens and GRUPO in json.loads(a.agentes_destino or '[]')]
    return sorted(itens + grupo, key=lambda a: a.id)


def consumir(chave_agente, itens):
    registrar_consumo(f"Agente de banco {chave_agente}", itens)


def historico():
    return _estado('historico_banco', [])


# ------------------------------------------------------------------------------ 2. fontes oficiais (pendentes até aprovação)
def _ja_proposto(url):
    return AprendizadoAgente.query.filter(AprendizadoAgente.tipo == 'referencia_externa', AprendizadoAgente.fonte_url == url).first() is not None


def aprender_sobre_banco(motor, usuario_id=None, origem=GERENTE_BANCO):
    """Lê a documentação oficial de um banco (o em uso ou outro pedido na tela) e propõe os aprendizados (PENDENTES)."""
    if motor not in DOCS:
        raise ValueError(f"banco desconhecido: {motor}")
    destino = AGENTES_BANCO if motor == motor_atual()['dialeto'] else ['db_portabilidade']
    criados = []
    for url, tema in DOCS[motor]:
        if _ja_proposto(url):
            continue
        try:
            criados.append(conhecimento.buscar_fonte_oficial(url, tema, usuario_id, gerente=GERENTE_BANCO, destino=destino))
        except Exception as e:
            db.session.rollback()
            evento('Busca recusada', f"{url}: {e}", agente=GERENTE_BANCO, usuario_id=usuario_id)
            db.session.commit()
    return criados


def aprender_com_achados(relatorios, origem=GERENTE_BANCO):
    """Para cada tipo de problema encontrado, propõe a página oficial que ensina o assunto ao agente certo."""
    criados = []
    categorias = {a['categoria'] for r in relatorios for a in r.get('achados', []) if a['severidade'] != 'Informativa'}
    for categoria in sorted(categorias):
        if categoria not in DOC_POR_CATEGORIA:
            continue
        url, tema = DOC_POR_CATEGORIA[categoria]
        if _ja_proposto(url):
            continue
        try:
            criados.append(conhecimento.buscar_fonte_oficial(url, tema, gerente=GERENTE_BANCO, destino=[DESTINO_POR_CATEGORIA[categoria]]))
        except Exception as e:
            db.session.rollback()
            evento('Busca recusada', f"{url}: {e}", agente=GERENTE_BANCO)
            db.session.commit()
    return criados


def resumo_para_tela():
    contagem = {a: {'Aplicado': 0, 'Pendente': 0} for a in [GRUPO] + AGENTES_BANCO}
    for a in AprendizadoAgente.query.filter(AprendizadoAgente.status.in_(['Aplicado', 'Pendente'])).all():
        for destino in json.loads(a.agentes_destino or '[]'):
            if destino in contagem:
                contagem[destino][a.status] += 1
    return {'contagem': contagem, 'ultima': _estado('ultima_deteccao_banco', None), 'motor': motor_atual()}
