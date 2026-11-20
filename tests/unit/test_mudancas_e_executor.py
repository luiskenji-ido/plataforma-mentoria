"""Requisição de mudança (números, prazos) e o fim da execução disparada por uma CR no Orquestrador executor."""

import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import mudancas

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "agentes_orquestrador"))
import executor  # noqa: E402


# ------------------------------------------------------------------ números e prazos
def test_numero_usa_o_prefixo_do_idioma():
    r = SimpleNamespace(codigo="2026-0007")
    assert mudancas.numero(r, "pt") == "RDM-2026-0007"
    assert mudancas.numero(r, "en") == "CR-2026-0007"
    assert mudancas.numero(r, "es") == "SC-2026-0007"
    assert mudancas.numero(r, "fr") == "RDM-2026-0007"
    assert mudancas.numero(None) == ""


@pytest.mark.parametrize(
    "texto, ano, seq",
    [
        ("RDM-2026-0001", "2026", "0001"),
        ("cr-2026-1", "2026", "1"),
        ("SC 2026-0012", "2026", "0012"),
        ("2026-0003", "2026", "0003"),
    ],
)
def test_codigo_aceita_os_formatos_de_numero(texto, ano, seq):
    m = mudancas.CODIGO.match(texto)
    assert m and m.groups() == (ano, seq)


@pytest.mark.parametrize("texto", ["", "RDM-26-1", "RDM-2026-00001", "2026-0001; drop table", "XYZ-2026-0001"])
def test_codigo_recusa_o_resto(texto):
    assert mudancas.CODIGO.match(texto) is None


def test_no_prazo():
    agora = datetime(2026, 11, 20, 12, 0)
    assert mudancas.no_prazo(SimpleNamespace(data_agendada=None), agora)
    assert mudancas.no_prazo(SimpleNamespace(data_agendada=agora - timedelta(minutes=1)), agora)
    assert not mudancas.no_prazo(SimpleNamespace(data_agendada=agora + timedelta(minutes=1)), agora)


def test_executavel_so_com_lista_de_correcoes(monkeypatch):
    assert mudancas.executavel(SimpleNamespace(tipo="codigo", conteudo='{"correcoes": [{"id": "a"}]}'))
    assert not mudancas.executavel(SimpleNamespace(tipo="codigo", conteudo='{"correcoes": []}'))
    assert not mudancas.executavel(SimpleNamespace(tipo="parametros", conteudo='{"correcoes": [{"id": "a"}]}'))
    assert not mudancas.executavel(SimpleNamespace(tipo="codigo", conteudo="não é json"))
    assert not mudancas.executavel(None)


# ------------------------------------------------------------------ executor: fim da execução pela CR
@pytest.fixture
def estado(monkeypatch):
    """Estado do executor em memória, com confirmar/rollback falsos (sem git, push nem disco)."""
    caixa = {"dados": None, "chamadas": []}
    monkeypatch.setattr(executor, "ler_estado", lambda: dict(caixa["dados"]) if caixa["dados"] else None)
    monkeypatch.setattr(executor, "_gravar_json", lambda _caminho, dados: caixa.update(dados=dict(dados)))

    def confirmar(usuario, rdm):
        caixa["chamadas"].append(("confirmar", usuario))
        caixa["dados"] = {**caixa["dados"], "status": "confirmado", "commit": "abc1234567"}
        return True, "Commit abc12345 criado."

    def rollback(usuario):
        caixa["chamadas"].append(("rollback", usuario))
        caixa["dados"] = {**caixa["dados"], "status": "revertido"}
        return True, ""

    monkeypatch.setattr(executor, "confirmar", confirmar)
    monkeypatch.setattr(executor, "rollback", rollback)
    return caixa


RDM = {"id": 3, "numero": "RDM-2026-0003", "titulo": "x", "aprovador": "Comitê"}


def test_equipes_aprovaram_commit_sai_sozinho(estado):
    estado["dados"] = {"status": "aguardando_confirmacao"}
    res = executor.finalizar_pela_rdm(RDM)
    assert res["status"] == "aplicada" and res["commit"] == "abc1234567"
    assert estado["chamadas"] == [("confirmar", "Agente executor (RDM-2026-0003)")]
    assert estado["dados"]["resultado_rdm"]["status"] == "aplicada"


@pytest.mark.parametrize("situacao", ["reprovado", "erro", "sem_alteracoes", "parado"])
def test_qualquer_falha_faz_rollback_sozinho(estado, situacao):
    estado["dados"] = {"status": situacao, "erro": "Boom"}
    res = executor.finalizar_pela_rdm(RDM)
    assert res["status"] == "nao_aplicada" and res["motivo"]
    assert estado["chamadas"] == [("rollback", "Agente executor (RDM-2026-0003)")]
    assert estado["dados"]["resultado_rdm"]["status"] == "nao_aplicada"


def test_commit_recusado_vira_rollback(estado, monkeypatch):
    estado["dados"] = {"status": "aguardando_confirmacao"}
    monkeypatch.setattr(executor, "confirmar", lambda u, r: (False, "O código em uso mudou depois da cópia."))
    res = executor.finalizar_pela_rdm(RDM)
    assert res["status"] == "nao_aplicada" and "mudou" in res["motivo"]
    assert estado["chamadas"][-1][0] == "rollback"
