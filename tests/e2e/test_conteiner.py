"""Fluxos principais contra o contêiner de produção, da interface pública até o banco, o Redis e o MinIO."""

import json
import secrets
import subprocess
import threading
import time

import boto3
import pytest
import redis
import requests

PNG = b"\x89PNG\r\n\x1a\n" + secrets.token_bytes(256)


# ------------------------------------------------------------------ imagem e sondas
def _inspecionar(conteiner):
    return json.loads(subprocess.run(["docker", "inspect", conteiner], capture_output=True, text=True).stdout)[0]


def test_conteiner_roda_sem_root_e_com_disco_so_de_leitura(pilha):
    info = _inspecionar(pilha.id_do_conteiner("web"))
    assert info["Config"]["User"] == "10001:10001"
    assert info["HostConfig"]["ReadonlyRootfs"] is True
    # O HEALTHCHECK da imagem roda à parte do /readyz que a pilha espera: aguarda a primeira sondagem (--start-interval)
    prazo = time.time() + 60
    while info["State"]["Health"]["Status"] == "starting" and time.time() < prazo:
        time.sleep(1)
        info = _inspecionar(pilha.id_do_conteiner("web"))
    assert info["State"]["Health"]["Status"] == "healthy"


def test_healthz_e_readyz_com_todos_os_servicos(pilha):
    assert requests.get(pilha.url + "/healthz", timeout=5).json() == {"status": "ok"}
    r = requests.get(pilha.url + "/readyz", timeout=10)
    assert r.status_code == 200 and r.json()["verificacoes"] == {"banco": "ok", "redis": "ok", "arquivos": "ok"}


def test_cabecalhos_de_seguranca_e_id_da_requisicao(pilha):
    r = requests.get(pilha.url + "/", timeout=10)
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers["Content-Security-Policy"] and r.headers["Server"] == "Mentoria"
    assert len(r.headers["X-Request-ID"]) == 32


def test_logs_saem_em_json_sem_segredos(pilha):
    requests.get(pilha.url + "/?senha=nao-pode-aparecer", timeout=10)
    linhas = [linha.split("|", 1)[-1].strip() for linha in pilha.logs("web").splitlines() if "{" in linha]
    eventos = [json.loads(linha[linha.index("{") :]) for linha in linhas if linha.rstrip().endswith("}")]
    assert any(e.get("logger") == "acesso" for e in eventos)
    assert "nao-pode-aparecer" not in pilha.logs("web")
    assert pilha.ambiente["SECRET_KEY"] not in pilha.logs("web")


# ------------------------------------------------------------------ autenticação e autorização
def test_login_e_tela_protegida(pilha, admin, navegador, senha_admin):
    assert requests.get(pilha.url + "/dashboard", allow_redirects=False, timeout=10).status_code == 302
    navegador.entrar(admin, senha_admin)
    assert navegador.get(pilha.url + "/dashboard", timeout=15).status_code == 200


def test_post_sem_csrf_e_recusado(pilha, admin, senha_admin):
    r = requests.post(pilha.url + "/", data={"email": admin, "senha": senha_admin}, allow_redirects=False, timeout=10)
    assert r.status_code == 302
    sessao = requests.Session()
    sessao.cookies.update(r.cookies)
    assert sessao.get(pilha.url + "/dashboard", allow_redirects=False, timeout=10).status_code == 302


def test_limite_de_tentativas_de_login_e_compartilhado_no_redis(pilha):
    cliente = redis.Redis(host="127.0.0.1", port=pilha.porta_redis)
    s = requests.Session()
    s.get(pilha.url + "/", timeout=10)
    try:
        respostas = [
            s.post(pilha.url + "/", data={"email": f"x{i}@local.com", "senha": "errada"}, allow_redirects=False, timeout=10)
            for i in range(32)
        ]
        assert 429 in [r.status_code for r in respostas]
        assert cliente.keys("mentoria:limite:login:*")
    finally:
        # O limite é por IP e os testes saem todos do mesmo IP: sem isto, os logins dos testes seguintes recebem 429
        for chave in cliente.scan_iter("mentoria:limite:login:*"):
            cliente.delete(chave)


# ------------------------------------------------------------------ arquivos no MinIO (S3)
def _minio(pilha):
    return boto3.client(
        "s3",
        endpoint_url=f"http://127.0.0.1:{pilha.porta_minio}",
        aws_access_key_id="mentoria",
        aws_secret_access_key=pilha.ambiente["MINIO_SENHA"],
        region_name="us-east-1",
    )


def test_logo_vai_para_o_bucket_e_volta_pelo_app(pilha, admin, navegador, senha_admin):
    navegador.entrar(admin, senha_admin)
    empresa_id = (
        pilha.python_no_web(
            "from app import app, db\nfrom models import Empresa\n"
            "with app.app_context():\n"
            f"    e = Empresa(nome='Parceira E2E {secrets.token_hex(3)}'); db.session.add(e); db.session.commit(); print(e.id)\n"
        )
        .strip()
        .splitlines()[-1]
    )
    navegador.enviar(f"/empresas/{empresa_id}/logo/enviar", arquivos={"logo": ("logo.png", PNG, "image/png")})
    chaves = [o["Key"] for o in _minio(pilha).list_objects_v2(Bucket="mentoria-arquivos", Prefix="logos/").get("Contents", [])]
    assert any(k.startswith(f"logos/empresa_{empresa_id}_") for k in chaves)
    r = requests.get(f"{pilha.url}/empresas/{empresa_id}/logo", timeout=10)
    assert r.status_code == 200 and r.content == PNG


# ------------------------------------------------------------------ dependência fora do ar
def test_redis_fora_do_ar_tira_a_replica_do_balanceador_sem_matar_o_processo(pilha):
    pilha.compose("stop", "redis")
    try:
        r = pilha.esperar("/readyz", status=503, prazo=60)
        assert r.json()["verificacoes"]["redis"] == "falhou"
        assert requests.get(pilha.url + "/healthz", timeout=5).status_code == 200
        assert requests.get(pilha.url + "/", timeout=10).status_code == 200  # login continua (limite local)
    finally:
        pilha.compose("start", "redis")
    pilha.esperar("/readyz", status=200, prazo=90)


# ------------------------------------------------------------------ worker e desligamento gracioso
def test_worker_roda_as_tarefas(pilha):
    prazo = time.time() + 120
    while time.time() < prazo:
        if '"evento": "tarefa"' in pilha.logs("worker"):
            return
        time.sleep(3)
    pytest.fail("o worker não registrou nenhuma tarefa:\n" + pilha.logs("worker")[-2000:])


def test_sigterm_termina_o_pedido_em_andamento_e_sai_limpo(pilha, admin, senha_admin, navegador):
    """Download lento de um arquivo grande: o SIGTERM chega no meio e o arquivo ainda chega inteiro."""
    tamanho = 24 * 1024 * 1024
    reuniao_id = (
        pilha.python_no_web(
            "import os, secrets\nfrom datetime import datetime, timedelta\n"
            "from app import app, db, guarda_arquivos\nfrom models import ReuniaoInstitucional, Usuario\n"
            "with app.app_context():\n"
            "    autor = Usuario.query.filter_by(tipo_usuario='Administrador').first()\n"
            "    r = ReuniaoInstitucional(titulo='E2E SIGTERM', data_hora=datetime.now() - timedelta(hours=1), criado_por_id=autor.id)\n"
            "    db.session.add(r); db.session.commit()\n"
            f"    nome = f'reuniao_{{r.id}}_{secrets.token_hex(4)}.mp4'\n"
            f"    guarda_arquivos().salvar('reunioes/' + nome, os.urandom({tamanho}))\n"
            "    r.gravacao_arquivo, r.gravacao_nome, r.gravacao_tamanho = nome, 'e2e.mp4', " + str(tamanho) + "\n"
            "    db.session.commit(); print(r.id)\n"
        )
        .strip()
        .splitlines()[-1]
    )
    navegador.entrar(admin, senha_admin)
    s = navegador

    recebido = {"bytes": 0, "erro": None}

    def baixar_devagar():
        try:
            with s.get(f"{pilha.url}/reunioes/{reuniao_id}/gravacao", stream=True, timeout=60) as r:
                assert r.status_code == 200
                for bloco in r.iter_content(256 * 1024):
                    recebido["bytes"] += len(bloco)
                    time.sleep(0.05)
        except Exception as erro:  # registrado e conferido abaixo
            recebido["erro"] = erro

    t = threading.Thread(target=baixar_devagar)
    t.start()
    time.sleep(1.0)
    web = pilha.id_do_conteiner("web")
    subprocess.run(["docker", "kill", "--signal", "SIGTERM", web], check=True, capture_output=True)
    t.join(90)
    # Depois dos workers, o processo principal ainda espera os clientes fecharem as conexões (encerramento.py), no
    # máximo GUNICORN_PRAZO_ENTREGA segundos: a sessão do teste guarda a conexão aberta no pool, então pode levar esse tempo.
    prazo = time.time() + 45
    estado = _inspecionar(web)["State"]
    while estado["Running"] and time.time() < prazo:
        time.sleep(1)
        estado = _inspecionar(web)["State"]
    try:
        assert recebido["erro"] is None and recebido["bytes"] == tamanho
        assert estado["Running"] is False and estado["ExitCode"] == 0
    finally:
        pilha.compose("up", "-d", "web")
        pilha.esperar()
