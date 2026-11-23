# -*- coding: utf-8 -*-
"""
REGRAS DE NEGÓCIO DOS BACKUPS (sem Flask, sem banco, sem disco)
==============================================================
Decisões puras usadas pelo backup_servico.py e pela tela Manutenção (DB):
- validar um agendamento digitado na tela;
- calcular a próxima execução de um agendamento Diário / Semanal / Mensal;
- classificar a saúde dos backups (Saudável / Atenção / Crítica);
- escolher quais arquivos de um agendamento saem pela retenção.

Nada aqui lê o relógio, o banco ou o disco: quem chama passa os dados. Assim as regras são testadas sem o app
(tests/unit/test_backup_regras.py) e vão inteiras para o serviço de backup quando ele for separado.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

FREQUENCIAS = ["Diário", "Semanal", "Mensal"]
STATUS_OK = ("Concluído", "Sucesso")  # 'Sucesso' = registros antigos
TIPOS_BACKUP = ("Imediato", "Agendado", "Agendado (manual)")
EXTENSOES = (".db", ".sql.gz", ".dump")  # SQLite, MySQL e PostgreSQL
DIAS_SEM_BACKUP_ATENCAO = 8  # sem backup bem-sucedido há mais tempo que isto: "Atenção"
RETENCAO_MAXIMA = 365  # cópias guardadas por agendamento de backup
RETENCAO_PADRAO = 7
HORARIO_PADRAO = "03:00"

_HORARIO = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_SEM_ACENTO = {"Diário": "diario", "Semanal": "semanal", "Mensal": "mensal"}


# ------------------------------------------------------------------------------
# Validação do formulário de agendamento
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class DadosAgendamento:
    frequencia: str
    horario: str
    data_inicio: date
    retencao: int


def validar_agendamento(frequencia, horario, data_inicio, retencao):
    """Textos vindos da tela → DadosAgendamento, ou None se algum campo for inválido.
    data_inicio no formato AAAA-MM-DD; retencao vazia vale RETENCAO_PADRAO; horario HH:MM (00:00 a 23:59)."""
    horario = (horario or "").strip()
    try:
        inicio = datetime.strptime(data_inicio or "", "%Y-%m-%d").date()
        copias = int(retencao or RETENCAO_PADRAO)
    except ValueError:
        return None
    if frequencia not in FREQUENCIAS or not _HORARIO.fullmatch(horario) or not 1 <= copias <= RETENCAO_MAXIMA:
        return None
    return DadosAgendamento(frequencia, horario, inicio, copias)


# ------------------------------------------------------------------------------
# Próxima execução
# ------------------------------------------------------------------------------
def somar_meses(data, meses):
    """Mesmo dia N meses depois; no mês mais curto, o último dia (31/01 + 1 mês = 28 ou 29/02)."""
    mes = data.month - 1 + meses
    ano, mes = data.year + mes // 12, mes % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


def proxima_execucao(frequencia, horario, data_inicio, depois_de):
    """Primeira data/hora do agendamento estritamente depois de 'depois_de'."""
    horas, minutos = (int(x) for x in (horario or HORARIO_PADRAO).split(":"))
    base = datetime.combine(data_inicio, time(horas, minutos))
    if base > depois_de:
        return base
    if frequencia == "Mensal":
        n = (depois_de.year - base.year) * 12 + depois_de.month - base.month
        candidato = somar_meses(base, max(n, 0))
        while candidato <= depois_de:
            n += 1
            candidato = somar_meses(base, n)
        return candidato
    passo = timedelta(days=7 if frequencia == "Semanal" else 1)
    saltos = int((depois_de - base) / passo) + 1
    return base + saltos * passo


# ------------------------------------------------------------------------------
# Nomes e retenção dos arquivos
# ------------------------------------------------------------------------------
def frequencia_sem_acento(frequencia):
    return _SEM_ACENTO.get(frequencia, re.sub(r"\W", "", (frequencia or "").lower()))


def prefixo_do_arquivo(agendamento_id=None, frequencia=None):
    """Prefixo do nome do arquivo: os de um agendamento levam o id (é por ele que a retenção os encontra)."""
    if agendamento_id is None:
        return "mentoria_backup"
    return f"mentoria_backup_ag{agendamento_id}_{frequencia_sem_acento(frequencia)}"


def arquivos_excedentes(nomes, agendamento_id, retencao):
    """Arquivos do agendamento além das 'retencao' cópias mais novas (o nome tem a data: ordem alfabética = cronológica).
    Arquivos de outros agendamentos, manuais ou com outra extensão nunca entram."""
    marca = f"mentoria_backup_ag{agendamento_id}_"
    proprios = sorted((n for n in nomes if n.startswith(marca) and n.endswith(EXTENSOES)), reverse=True)
    return proprios[max(retencao or 1, 1) :]


# ------------------------------------------------------------------------------
# Saúde (KPI da tela Manutenção (DB) e do Agente Backup e Recuperação)
# ------------------------------------------------------------------------------
def classificar_saude(agora, ativos, ultimo, ultimo_ok_em):
    """(situação, motivo).
    ativos: quantos agendamentos ativos; ultimo: status da execução mais recente (ou None);
    ultimo_ok_em: data/hora do último backup bem-sucedido (ou None)."""
    if ultimo == "Falha":
        return "Crítica", "O último backup falhou."
    if not ativos:
        return "Atenção", "Nenhum agendamento ativo."
    if not ultimo_ok_em or ultimo_ok_em < agora - timedelta(days=DIAS_SEM_BACKUP_ATENCAO):
        return "Atenção", f"Nenhum backup bem-sucedido nos últimos {DIAS_SEM_BACKUP_ATENCAO} dias."
    return "Saudável", ""
