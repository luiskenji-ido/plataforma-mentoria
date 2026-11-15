# -*- coding: utf-8 -*-
"""
SERVIÇO DE BACKUP DA PLATAFORMA (Manutenção › DB)
=================================================
- Cópia consistente do SQLite com a API de backup (funciona com o app em uso) e verificação de integridade.
- Agendamentos Diário / Semanal / Mensal com pausa, retenção por agendamento e próxima execução calculada.
- Restauração com cópia de segurança do banco atual antes e com a auditoria preservada
  (os agendamentos e o histórico de execuções não voltam no tempo junto com os dados).
- Todos os arquivos ficam dentro de instance/backups/<subpasta>: nada é gravado fora dessa pasta.

As funções rodam dentro de um app_context (rotas do Flask ou tarefas_agendadas.py).
"""
import os
import re
import csv
import sqlite3
import calendar
from datetime import datetime, timedelta, time as hora_do_dia

from flask import current_app
from werkzeug.utils import secure_filename

from models import db, RegistroBackup, AgendamentoBackup, AlteracaoAgendamentoBackup

FREQUENCIAS = ['Diário', 'Semanal', 'Mensal']
STATUS_OK = ('Concluído', 'Sucesso')          # 'Sucesso' = registros antigos
TIPOS_BACKUP = ('Imediato', 'Agendado', 'Agendado (manual)')
DIAS_SEM_BACKUP_ATENCAO = 8                   # sem backup bem-sucedido há mais tempo que isto: "Atenção"
TABELAS_PRESERVADAS = ('agendamento_backup', 'alteracao_agendamento_backup', 'registro_backup')


# ------------------------------------------------------------------------------
# Caminhos
# ------------------------------------------------------------------------------
def caminho_banco():
    return db.engine.url.database if os.path.isabs(db.engine.url.database or '') else os.path.join(current_app.instance_path, 'mentoria.db')


def pasta_base():
    pasta = os.path.join(current_app.instance_path, 'backups')
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
    """Caminho dentro de instance/backups ou None (bloqueia ../ e caminhos absolutos)."""
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
            if nome.endswith('.db'):
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
    """(ok, mensagem): arquivo SQLite íntegro e com as tabelas da plataforma."""
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
    inicio = datetime.now()
    nome = f"{prefixo}_{inicio.strftime('%Y%m%d_%H%M%S_%f')}.db"
    destino = os.path.join(pasta_de(subpasta), nome)
    db.session.commit()  # nada pendente na sessão antes da cópia
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
    proprios = sorted((n for n in os.listdir(pasta) if n.startswith(f"mentoria_backup_ag{agendamento.id}_") and n.endswith('.db')),
                      reverse=True)  # o nome tem a data: ordem alfabética = cronológica
    apagados = 0
    for nome in proprios[max(agendamento.retencao or 1, 1):]:
        os.remove(os.path.join(pasta, nome))
        apagados += 1
    return apagados


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


def _ler_tabelas_preservadas():
    con = sqlite3.connect(caminho_banco())
    con.row_factory = sqlite3.Row
    try:
        return {t: [dict(r) for r in con.execute('SELECT * FROM ' + _identificador(t, TABELAS_PRESERVADAS))] for t in TABELAS_PRESERVADAS}
    finally:
        con.close()


def _gravar_tabelas_preservadas(dados):
    con = sqlite3.connect(caminho_banco())
    try:
        for tabela, linhas in dados.items():
            nome_tabela = _identificador(tabela, TABELAS_PRESERVADAS)
            colunas_atuais = {c[1] for c in con.execute('PRAGMA table_info(' + nome_tabela + ')')}
            con.execute('DELETE FROM ' + nome_tabela)
            for linha in linhas:
                linha = {k: v for k, v in linha.items() if k in colunas_atuais}
                campos = ', '.join(_identificador(c, colunas_atuais) for c in linha)
                marcadores = ', '.join('?' for _ in linha)
                con.execute('INSERT INTO ' + nome_tabela + ' (' + campos + ') VALUES (' + marcadores + ')', list(linha.values()))
        con.commit()
    finally:
        con.close()


def restaurar(caminho_arquivo, usuario_id, atualizar_estrutura):
    """Restaura o banco a partir de um arquivo validado. Devolve (ok, mensagem)."""
    ok, mensagem = verificar_integridade(caminho_arquivo)
    nome = os.path.basename(caminho_arquivo)
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
    origem = sqlite3.connect(f"file:{caminho_arquivo}?mode=ro", uri=True)
    destino = sqlite3.connect(caminho_banco())
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()
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
