"""Operação com o app e o banco reais: sondas de saúde, id da requisição, logs JSON e o worker das tarefas."""

import json
import logging
import threading

import pytest


def test_healthz(navegador):
    r = navegador.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_readyz_confere_o_banco_de_verdade(navegador):
    r = navegador.get("/readyz")
    assert r.status_code == 200
    assert r.get_json()["verificacoes"]["banco"] == "ok"


def test_readyz_com_banco_fora_do_ar_da_503(app_real, monkeypatch):
    import saude
    from sqlalchemy import create_engine

    morto = create_engine("mysql+pymysql://ninguem:x@127.0.0.1:1/nada", connect_args={"connect_timeout": 1})
    falso_db = type("DB", (), {"engine": morto})()
    monkeypatch.setitem(saude._VERIFICACOES, "banco", saude.verificar_banco(falso_db))
    r = app_real.app.test_client().get("/readyz")
    assert r.status_code == 503 and r.get_json()["verificacoes"]["banco"] == "falhou"
    assert b"ninguem" not in r.data


def test_sondas_nao_exigem_login_nem_disparam_tarefas(app_real, monkeypatch):
    chamadas = []
    monkeypatch.setattr(app_real, "_ULTIMA_VERIFICACAO_TAREFAS", [__import__("datetime").datetime.min])
    monkeypatch.setattr(app_real, "_executar_mudancas_com_seguranca", lambda: chamadas.append(1))
    app_real.app.test_client().get("/readyz")
    assert chamadas == []


def test_cada_resposta_tem_id_da_requisicao(navegador):
    assert len(navegador.get("/").headers["X-Request-ID"]) == 32


def test_log_de_acesso_em_json_sem_dados_pessoais(app_real, caplog):
    import logs_estruturados

    with caplog.at_level(logging.INFO, logger="acesso"):
        app_real.app.test_client().get("/?email=ana.souza@empresa.org")
    linhas = [logs_estruturados.FormatoJson().format(r) for r in caplog.records if r.name == "acesso"]
    evento = json.loads(linhas[-1])
    assert evento["caminho"] == "/" and evento["status"] == 200 and "duracao_ms" in evento and evento["request_id"]
    assert "ana.souza" not in linhas[-1]


# ------------------------------------------------------------------ worker das tarefas
@pytest.fixture
def tarefas(app_real):
    import tarefas_agendadas

    return tarefas_agendadas


def test_worker_para_entre_as_tarefas_quando_recebe_sigterm(tarefas):
    parar = threading.Event()
    parar.set()
    assert tarefas.executar_tarefas(parar) == {}


def test_worker_roda_e_sai_no_desligamento(tarefas):
    parar = threading.Event()
    rodadas = []

    def rodada(evento):
        rodadas.append(1)
        evento.set()  # o SIGTERM chega durante a rodada

    assert tarefas.rodar_continuo(parar, intervalo=3600, rodada=rodada) == 1
    assert rodadas == [1]


def test_tarefas_nao_rodam_no_processo_web_do_conteiner(app_real, monkeypatch):
    monkeypatch.setenv("MENTORIA_TAREFAS_NO_WEB", "0")
    assert app_real.tarefas_no_processo_web() is False
    monkeypatch.delenv("MENTORIA_TAREFAS_NO_WEB")
    assert app_real.tarefas_no_processo_web() is True
