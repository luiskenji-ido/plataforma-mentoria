# -*- coding: utf-8 -*-
"""
AÇÕES DO DBA (Administração › Agentes de Banco de Dados)
=======================================================
Os agentes só LEEM o banco. As ações que alteram o banco são disparadas pelo administrador na tela e seguem sempre:
  1. backup imediato validado (backup_servico, pasta "pre_manutencao"); se o backup falhar, nada é alterado;
  2. a ação (ANALYZE + PRAGMA optimize, VACUUM, criação de índices sugeridos, verificação de integridade);
  3. registro no histórico de manutenção (tabela manutencao_banco_dados), com duração e o arquivo de backup.
"""
import re
import json
import time
import sqlite3
from datetime import datetime

from sqlalchemy import inspect

from models import db, ManutencaoBanco

ACOES = {'otimizar': 'Atualizar estatísticas (ANALYZE + optimize)', 'vacuum': 'Compactar o banco (VACUUM)',
         'indices': 'Criar índices sugeridos', 'integridade': 'Verificar integridade'}
_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def suportado():
    return db.engine.dialect.name == 'sqlite'


def _nome_indice(tabela, colunas):
    return f"ix_{tabela}_{'_'.join(colunas)}"[:60]


_CACHE = {'em': 0.0, 'valor': None}
CACHE_SEGUNDOS = 600


def indices_sugeridos(usar_cache=True):
    """Lista do cache (10 min) — inspecionar as ~60 tabelas custa centenas de consultas ao catálogo.
    O cache é limpo a cada ação do DBA e quando os agentes gravam novas sugestões."""
    from conhecimento import _estado
    marca = json.dumps(_estado('db_indices_sugeridos', []), sort_keys=True)
    if usar_cache and _CACHE['valor'] is not None and time.time() - _CACHE['em'] < CACHE_SEGUNDOS and _CACHE.get('marca') == marca:
        return _CACHE['valor']
    _CACHE.update(em=time.time(), valor=_calcular_indices_sugeridos(), marca=marca)
    return _CACHE['valor']


def _calcular_indices_sugeridos():
    """Chaves estrangeiras sem índice + colunas que as consultas varrem inteiras (do Agente Consultas e Desempenho)."""
    from conhecimento import _estado
    insp = inspect(db.engine)
    tabelas = set(insp.get_table_names())
    sugestoes = {}
    for tabela in tabelas:
        indexadas = {tuple(i['column_names'][:1]) for i in insp.get_indexes(tabela) if i['column_names']}
        pk = insp.get_pk_constraint(tabela).get('constrained_columns') or []
        if pk:
            indexadas.add((pk[0],))
        for fk in insp.get_foreign_keys(tabela):
            col = fk['constrained_columns'][0]
            if (col,) not in indexadas:
                sugestoes[(tabela, (col,))] = f"chave estrangeira para {fk['referred_table']} sem índice"
        for unico in insp.get_unique_constraints(tabela):
            indexadas.add(tuple(unico['column_names'][:1]))
    for item in _estado('db_indices_sugeridos', []):
        tabela, colunas = item.get('tabela'), tuple(item.get('colunas') or [])
        if tabela in tabelas and colunas:
            existentes = {c['name'] for c in insp.get_columns(tabela)}
            indexadas = {tuple(i['column_names'][:len(colunas)]) for i in insp.get_indexes(tabela)}
            pk = tuple((insp.get_pk_constraint(tabela).get('constrained_columns') or [])[:len(colunas)])
            if set(colunas) <= existentes and colunas not in indexadas and colunas != pk:
                sugestoes.setdefault((tabela, colunas), item.get('motivo', 'consulta varre a tabela inteira'))
    # Prioridade alta: colunas que os agentes viram em uso nas consultas (filtros, junções, varreduras)
    prioritarias = {(i.get('tabela'), tuple(i.get('colunas') or [])) for i in _estado('db_indices_sugeridos', [])}
    lista = []
    for (tabela, colunas), motivo in sorted(sugestoes.items(), key=lambda x: ((x[0][0], x[0][1]) not in prioritarias, x[0])):
        if all(_IDENT.match(x) for x in (tabela, *colunas)):
            nome = _nome_indice(tabela, colunas)
            lista.append({'tabela': tabela, 'colunas': list(colunas), 'motivo': motivo, 'nome': nome,
                          'prioridade': 'alta' if (tabela, colunas) in prioritarias else 'baixa',
                          'sql': f'CREATE INDEX IF NOT EXISTS "{nome}" ON "{tabela}" ({", ".join(chr(34) + c + chr(34) for c in colunas)});'})
    return lista


def _backup_antes(usuario_id):
    import backup_servico
    registro = backup_servico.fazer_backup('Imediato', 'pre_manutencao', usuario_id)
    if registro.status not in backup_servico.STATUS_OK:
        raise RuntimeError(f"backup de segurança falhou, nada foi alterado: {registro.detalhes}")
    return registro.arquivo


def executar(acao, usuario_id, indices=None):
    """Executa uma ação do DBA. Devolve o registro ManutencaoBanco (status Concluída ou Falha)."""
    import backup_servico
    if acao not in ACOES:
        raise ValueError('ação desconhecida')
    inicio = time.time()
    registro = ManutencaoBanco(acao=acao, status='Em andamento', usuario_id=usuario_id, data=datetime.now())
    try:
        if not suportado():
            raise RuntimeError('as ações automáticas do DBA estão disponíveis para SQLite; use as ferramentas do seu banco')
        caminho = backup_servico.caminho_banco()
        if acao == 'integridade':
            con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
            try:
                resultado = [r[0] for r in con.execute('PRAGMA integrity_check').fetchall()]
                chaves = con.execute('PRAGMA foreign_key_check').fetchall()
            finally:
                con.close()
            registro.detalhes = f"integrity_check: {'; '.join(resultado[:5])} · foreign_key_check: {len(chaves)} registro(s) órfão(s)"
            registro.status = 'Concluída' if resultado == ['ok'] else 'Falha'
        else:
            registro.backup_arquivo = _backup_antes(usuario_id)
            db.session.commit()
            db.session.remove()
            db.engine.dispose()  # libera as conexões antes de mexer no arquivo
            con = sqlite3.connect(caminho, timeout=30, isolation_level=None)
            try:
                if acao == 'otimizar':
                    con.execute('ANALYZE')
                    con.execute('PRAGMA optimize')
                    tabelas = con.execute("SELECT COUNT(DISTINCT tbl) FROM sqlite_stat1").fetchone()[0]
                    registro.detalhes = f"Estatísticas atualizadas para {tabelas} tabela(s)."
                elif acao == 'vacuum':
                    antes = con.execute('PRAGMA page_count').fetchone()[0] * con.execute('PRAGMA page_size').fetchone()[0]
                    con.execute('VACUUM')
                    depois = con.execute('PRAGMA page_count').fetchone()[0] * con.execute('PRAGMA page_size').fetchone()[0]
                    registro.detalhes = f"Banco compactado: {antes // 1024} KB → {depois // 1024} KB."
                else:
                    validas = {i['nome']: i for i in indices_sugeridos(usar_cache=False)}
                    escolhidos = [validas[n] for n in (indices or []) if n in validas]
                    if not escolhidos:
                        raise RuntimeError('nenhum índice sugerido foi selecionado')
                    for item in escolhidos:
                        con.execute(item['sql'])
                    con.execute('ANALYZE')
                    registro.detalhes = 'Índices criados: ' + ', '.join(i['nome'] for i in escolhidos) + '.'
            finally:
                con.close()
            registro.status = 'Concluída'
    except Exception as e:
        db.session.rollback()
        registro.status, registro.detalhes = 'Falha', f"{e}"
    registro.duracao_seg = round(time.time() - inicio, 2)
    _CACHE['valor'] = None  # índices/estatísticas mudaram: recalcula as sugestões
    db.session.add(registro)
    db.session.commit()
    return registro


def historico(limite=30):
    return ManutencaoBanco.query.order_by(ManutencaoBanco.data.desc()).limit(limite).all()


def ultima(acao):
    return ManutencaoBanco.query.filter_by(acao=acao, status='Concluída').order_by(ManutencaoBanco.data.desc()).first()


def resumo_json():
    return json.dumps([{'acao': m.acao, 'status': m.status, 'data': m.data.isoformat(timespec='seconds')} for m in historico(10)])
