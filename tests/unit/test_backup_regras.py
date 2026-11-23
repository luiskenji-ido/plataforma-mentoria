"""Regras dos backups (backup_regras.py): validação do agendamento, próxima execução, retenção e saúde."""

import random
from datetime import date, datetime, timedelta

import pytest

import backup_regras as r


# ------------------------------------------------------------------ validação
def test_agendamento_valido_vira_dados():
    dados = r.validar_agendamento("Semanal", " 03:15 ", "2026-01-31", "4")
    assert dados == r.DadosAgendamento("Semanal", "03:15", date(2026, 1, 31), 4)


def test_retencao_vazia_vale_o_padrao():
    assert r.validar_agendamento("Diário", "00:00", "2026-01-01", "").retencao == r.RETENCAO_PADRAO


@pytest.mark.parametrize(
    "frequencia, horario, inicio, retencao",
    [
        ("Anual", "03:00", "2026-01-01", "7"),  # frequência fora da lista
        ("Diário", "24:00", "2026-01-01", "7"),  # hora inexistente
        ("Diário", "3:00", "2026-01-01", "7"),  # sem zero à esquerda
        ("Diário", "03:60", "2026-01-01", "7"),
        ("Diário", "03:00", "01/01/2026", "7"),  # data fora do formato
        ("Diário", "03:00", "", "7"),
        ("Diário", "03:00", "2026-01-01", "0"),  # retenção abaixo de 1
        ("Diário", "03:00", "2026-01-01", str(r.RETENCAO_MAXIMA + 1)),
        ("Diário", "03:00", "2026-01-01", "sete"),
        (None, None, None, None),
    ],
)
def test_agendamento_invalido_e_recusado(frequencia, horario, inicio, retencao):
    assert r.validar_agendamento(frequencia, horario, inicio, retencao) is None


# ------------------------------------------------------------------ próxima execução
def _referencia(frequencia, horario, inicio, depois_de):
    """Força bruta: anda de execução em execução a partir do início até passar de 'depois_de'."""
    h, m = (int(x) for x in horario.split(":"))
    base = datetime(inicio.year, inicio.month, inicio.day, h, m)
    n = 0
    while True:
        if frequencia == "Mensal":
            candidato = r.somar_meses(base, n)
        else:
            candidato = base + n * timedelta(days=7 if frequencia == "Semanal" else 1)
        if candidato > depois_de:
            return candidato
        n += 1


def test_proxima_igual_a_forca_bruta_em_datas_aleatorias():
    sorteio = random.Random(20261122)
    for _ in range(400):
        frequencia = sorteio.choice(r.FREQUENCIAS)
        horario = f"{sorteio.randrange(24):02d}:{sorteio.randrange(60):02d}"
        inicio = date(2024, 1, 1) + timedelta(days=sorteio.randrange(900))
        depois_de = datetime(2024, 1, 1) + timedelta(minutes=sorteio.randrange(1_500_000))
        esperado = _referencia(frequencia, horario, inicio, depois_de)
        assert r.proxima_execucao(frequencia, horario, inicio, depois_de) == esperado, (frequencia, horario, inicio, depois_de)


def test_inicio_no_futuro_e_a_primeira_execucao():
    assert r.proxima_execucao("Diário", "03:00", date(2030, 5, 1), datetime(2026, 1, 1)) == datetime(2030, 5, 1, 3, 0)


def test_estritamente_depois_no_horario_exato():
    assert r.proxima_execucao("Diário", "03:00", date(2026, 1, 1), datetime(2026, 1, 5, 3, 0)) == datetime(2026, 1, 6, 3, 0)


def test_mensal_no_dia_31_cai_no_ultimo_dia_do_mes_curto():
    assert r.proxima_execucao("Mensal", "03:00", date(2026, 1, 31), datetime(2026, 2, 1)) == datetime(2026, 2, 28, 3, 0)
    assert r.proxima_execucao("Mensal", "03:00", date(2026, 1, 31), datetime(2026, 3, 1)) == datetime(2026, 3, 31, 3, 0)


def test_horario_vazio_usa_o_padrao():
    assert r.proxima_execucao("Diário", None, date(2030, 1, 1), datetime(2026, 1, 1)).strftime("%H:%M") == r.HORARIO_PADRAO


# ------------------------------------------------------------------ nomes e retenção
def test_prefixo_do_arquivo():
    assert r.prefixo_do_arquivo() == "mentoria_backup"
    assert r.prefixo_do_arquivo(3, "Diário") == "mentoria_backup_ag3_diario"
    assert r.prefixo_do_arquivo(3, "Quinzenal!") == "mentoria_backup_ag3_quinzenal"


def test_retencao_apaga_so_os_mais_antigos_do_proprio_agendamento():
    nomes = [
        "mentoria_backup_ag1_diario_20260101_030000_000000.sql.gz",
        "mentoria_backup_ag1_diario_20260102_030000_000000.sql.gz",
        "mentoria_backup_ag1_diario_20260103_030000_000000.sql.gz",
        "mentoria_backup_ag12_diario_20250101_030000_000000.sql.gz",  # outro agendamento (ag12 ≠ ag1)
        "mentoria_backup_20250101_030000_000000.db",  # manual
        "mentoria_backup_ag1_diario_20250101_030000_000000.sql.gz.parcial",  # extensão desconhecida
        "leia-me.txt",
    ]
    assert r.arquivos_excedentes(nomes, 1, 2) == ["mentoria_backup_ag1_diario_20260101_030000_000000.sql.gz"]


@pytest.mark.parametrize("retencao", [0, None, -5])
def test_retencao_nunca_apaga_a_ultima_copia(retencao):
    nomes = [f"mentoria_backup_ag1_diario_2026010{d}_030000_000000.db" for d in (1, 2)]
    assert r.arquivos_excedentes(nomes, 1, retencao) == [nomes[0]]


# ------------------------------------------------------------------ saúde
AGORA = datetime(2026, 11, 22, 12, 0)


def test_saude_ultimo_backup_falhou_e_critica_mesmo_com_sucesso_recente():
    assert r.classificar_saude(AGORA, 3, "Falha", AGORA - timedelta(hours=1))[0] == "Crítica"


def test_saude_sem_agendamento_ativo_pede_atencao():
    assert r.classificar_saude(AGORA, 0, "Concluído", AGORA) == ("Atenção", "Nenhum agendamento ativo.")


def test_saude_sem_sucesso_recente_pede_atencao():
    situacao, motivo = r.classificar_saude(AGORA, 1, "Concluído", AGORA - timedelta(days=r.DIAS_SEM_BACKUP_ATENCAO, seconds=1))
    assert situacao == "Atenção" and motivo == "Nenhum backup bem-sucedido nos últimos 8 dias."
    assert r.classificar_saude(AGORA, 1, None, None)[0] == "Atenção"


def test_saude_em_dia_e_saudavel():
    assert r.classificar_saude(AGORA, 1, "Concluído", AGORA - timedelta(days=1)) == ("Saudável", "")
