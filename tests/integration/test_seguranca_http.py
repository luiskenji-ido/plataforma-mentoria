"""Segurança pelos endpoints HTTP: autenticação, autorização, CSRF, cabeçalhos e rotas públicas."""

import os
from urllib.parse import urlparse

import pytest


def test_tela_protegida_sem_login_vai_para_o_login(navegador):
    r = navegador.get("/dashboard")
    assert r.status_code == 302 and urlparse(r.headers["Location"]).path == "/"


def test_login_com_senha_errada_nao_entra(navegador, novo_usuario):
    _, email, _ = novo_usuario()
    navegador.post("/", {"email": email, "senha": "errada"})
    assert navegador.get("/dashboard").status_code == 302


def test_login_certo_entra(navegador, novo_usuario):
    _, email, senha = novo_usuario()
    navegador.entrar(email, senha)
    assert navegador.get("/dashboard").status_code == 200


def test_post_sem_token_csrf_e_recusado(navegador, novo_usuario):
    _, email, senha = novo_usuario()
    r = navegador.post("/", {"email": email, "senha": senha}, com_csrf=False)
    assert r.status_code == 302
    assert navegador.get("/dashboard").status_code == 302  # não entrou


def test_post_de_script_sem_token_recebe_400_em_json(navegador):
    r = navegador.post("/admin/mudancas/1/cancelar", com_csrf=False, headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_cabecalhos_de_seguranca(navegador):
    r = navegador.get("/")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Server"] == "Mentoria"


@pytest.mark.parametrize("acao", ["decidir", "cancelar"])
def test_aluno_nao_decide_nem_cancela_requisicao_de_mudanca(navegador, novo_usuario, acao):
    _, email, senha = novo_usuario("Aluno")
    navegador.entrar(email, senha)
    r = navegador.post(f"/admin/mudancas/999999/{acao}", {"decisao": "aprovar"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/dashboard")


def test_administrador_chega_na_regra_de_negocio(navegador, novo_usuario):
    _, email, senha = novo_usuario("Administrador")
    navegador.entrar(email, senha)
    r = navegador.post("/admin/mudancas/999999/cancelar", follow_redirects=True)
    assert "Só dá para cancelar".encode() in r.data  # passou da checagem de perfil e chegou em mudancas.cancelar


@pytest.mark.parametrize("rota", ["/reuniao/convidado/{c}", "/reuniao/convidado/{c}/agenda.ics", "/reuniao/convidado/{c}/gravacao"])
def test_rotas_de_convidado_sem_codigo_valido_dao_404(navegador, rota):
    assert navegador.get(rota.format(c="codigo-inventado")).status_code == 404
    assert navegador.get(rota.format(c="x" * 65)).status_code == 404


def test_oauth_sem_https_so_fora_de_producao(app_real):
    assert os.environ.get("MENTORIA_PRODUCAO") != "1"
    assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") == "1"
