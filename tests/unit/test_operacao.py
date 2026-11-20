"""Operação: logs JSON mascarados, novas tentativas com espera, SMTP com TLS verificado e sondas de saúde."""

import json
import logging
import smtplib
import ssl
from email.message import EmailMessage

import pytest
from flask import Flask

import email_smtp
import logs_estruturados as le
import resiliencia
import saude


# ------------------------------------------------------------------ mascaramento
@pytest.mark.parametrize(
    "entrada, nao_pode, deve",
    [
        ("senha=Segredo123 ok", "Segredo123", "senha=***"),
        ('{"password": "abc123xyz"}', "abc123xyz", '"password": "***'),
        ("Authorization: Bearer eyJhbGciOi.xyz", "eyJhbGciOi", "Bearer ***"),
        ("chave " + "sk-" + "ant-api03-" + "abcdefghijkl" + " vazou", "abcdefghijkl", "***"),  # montada: não é um segredo real
        ("google " + "AIza" + "SyA1234567890abcdefghijklmn", "AIzaSyA1234567890", "***"),
        ("mysql+pymysql://mentoria:S3nh4@db:3306/x", "S3nh4", "mentoria:***@db"),
        ("Falha ao enviar e-mail para maria.silva@empresa.com.br", "maria.silva", "m***@empresa.com.br"),
    ],
)
def test_mascarar_tira_segredos_e_dados_pessoais(entrada, nao_pode, deve):
    saida = le.mascarar(entrada)
    assert nao_pode not in saida and deve in saida


def test_texto_comum_nao_muda():
    assert le.mascarar("Backup agendado concluído em 3 s") == "Backup agendado concluído em 3 s"


def _registro(msg, *args, exc_info=None, **extra):
    r = logging.LogRecord("teste", logging.ERROR, __file__, 10, msg, args, exc_info)
    for k, v in extra.items():
        setattr(r, k, v)
    return r


def test_formato_json_uma_linha_com_campos_e_sem_pilha():
    try:
        raise ValueError("token=abc123 deu erro")
    except ValueError:
        import sys

        registro = _registro("falhou para %s", "ana@x.org", exc_info=sys.exc_info(), status=500)
    linha = le.FormatoJson().format(registro)
    assert "\n" not in linha
    evento = json.loads(linha)
    assert evento["nivel"] == "ERROR" and evento["logger"] == "teste" and evento["status"] == 500
    assert evento["mensagem"] == "falhou para a***@x.org"
    assert evento["erro_tipo"] == "ValueError" and evento["erro"] == "token=*** deu erro"
    assert evento["erro_onde"].startswith("test_operacao.py:")
    assert "pilha" not in evento


def test_pilha_so_quando_pedida():
    try:
        raise RuntimeError("x")
    except RuntimeError:
        import sys

        registro = _registro("erro", exc_info=sys.exc_info())
    assert "Traceback" in json.loads(le.FormatoJson(com_pilha=True).format(registro))["pilha"]


def test_formatador_texto_tambem_mascara(monkeypatch):
    monkeypatch.setenv("LOG_FORMATO", "texto")
    assert "s3cr3t" not in le.criar_formatador().format(_registro("senha=s3cr3t"))


def test_id_da_requisicao_recebido_ou_gerado():
    app = Flask(__name__)
    le.ligar_no_app(app)
    app.add_url_rule("/x", "x", lambda: "ok")
    c = app.test_client()
    assert c.get("/x", headers={"X-Request-ID": "abc12345-proxy"}).headers["X-Request-ID"] == "abc12345-proxy"
    gerado = c.get("/x", headers={"X-Request-ID": "<script>"}).headers["X-Request-ID"]
    assert len(gerado) == 32 and gerado.isalnum()


# ------------------------------------------------------------------ novas tentativas
def test_espera_cresce_e_respeita_o_teto():
    assert resiliencia.espera(1, sortear=lambda: 1.0) == 0.5
    assert resiliencia.espera(3, sortear=lambda: 1.0) == 2.0
    assert resiliencia.espera(10, sortear=lambda: 1.0) == resiliencia.ESPERA_MAXIMA
    assert resiliencia.espera(1, sortear=lambda: 0.0) == 0.25


def test_repete_erros_passageiros_e_devolve_o_resultado():
    chamadas, pausas = [], []

    def instavel():
        chamadas.append(1)
        if len(chamadas) < 3:
            raise ConnectionError("caiu")
        return "ok"

    assert resiliencia.com_retentativas(instavel, repetir_se=lambda e: isinstance(e, ConnectionError), dormir=pausas.append) == "ok"
    assert len(chamadas) == 3 and len(pausas) == 2 and pausas[0] < pausas[1] + 1


def test_nao_repete_erro_definitivo():
    chamadas = []

    def recusa():
        chamadas.append(1)
        raise PermissionError("senha errada")

    with pytest.raises(PermissionError):
        resiliencia.com_retentativas(recusa, repetir_se=lambda e: isinstance(e, ConnectionError), dormir=lambda _s: None)
    assert len(chamadas) == 1


def test_desiste_depois_do_limite():
    chamadas = []

    def sempre_cai():
        chamadas.append(1)
        raise TimeoutError()

    with pytest.raises(TimeoutError):
        resiliencia.com_retentativas(sempre_cai, repetir_se=lambda e: True, tentativas=4, dormir=lambda _s: None)
    assert len(chamadas) == 4


def test_sessao_http_tem_pool_e_retentativas_seguras():
    sessao = resiliencia.sessao_http()
    adaptador = sessao.get_adapter("https://graph.microsoft.com")
    regra = adaptador.max_retries
    assert regra.total == resiliencia.TENTATIVAS and 503 in regra.status_forcelist and 429 in regra.status_forcelist
    assert "POST" not in regra.allowed_methods  # POST não se repete sozinho (poderia duplicar um envio)
    assert sessao is resiliencia.sessao_http()


# ------------------------------------------------------------------ SMTP
class SmtpFalso:
    instancias = []
    falhas_de_conexao = 0

    def __init__(self, servidor, porta, timeout):
        SmtpFalso.instancias.append(self)
        if SmtpFalso.falhas_de_conexao:
            SmtpFalso.falhas_de_conexao -= 1
            raise smtplib.SMTPConnectError(421, "ocupado")
        self.servidor, self.porta, self.timeout, self.contexto, self.login_feito, self.enviadas = servidor, porta, timeout, None, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.contexto = context

    def login(self, usuario, senha):
        if senha == "errada":
            raise smtplib.SMTPAuthenticationError(535, "recusada")
        self.login_feito = usuario

    def send_message(self, msg):
        self.enviadas.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    SmtpFalso.instancias, SmtpFalso.falhas_de_conexao = [], 0
    monkeypatch.setenv("MAIL_SERVER", "smtp.exemplo.org")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_USERNAME", "avisos")
    monkeypatch.setenv("MAIL_PASSWORD", "boa")
    monkeypatch.delenv("MAIL_USE_TLS", raising=False)
    return SmtpFalso


def _mensagem():
    m = EmailMessage()
    m["To"], m["Subject"] = "a@b.org", "oi"
    m.set_content("texto")
    return m


def test_smtp_usa_tls_com_certificado_verificado(smtp):
    email_smtp.enviar(_mensagem(), fabrica_smtp=smtp, dormir=lambda _s: None)
    conexao = smtp.instancias[-1]
    assert conexao.contexto.verify_mode == ssl.CERT_REQUIRED and conexao.contexto.check_hostname
    assert conexao.login_feito == "avisos" and len(conexao.enviadas) == 1 and conexao.timeout == email_smtp.TEMPO_LIMITE


def test_smtp_tenta_de_novo_quando_a_conexao_falha(smtp):
    smtp.falhas_de_conexao = 2
    email_smtp.enviar(_mensagem(), fabrica_smtp=smtp, dormir=lambda _s: None)
    assert len(smtp.instancias) == 3 and len(smtp.instancias[-1].enviadas) == 1


def test_smtp_nao_repete_senha_recusada(smtp, monkeypatch):
    monkeypatch.setenv("MAIL_PASSWORD", "errada")
    with pytest.raises(smtplib.SMTPAuthenticationError):
        email_smtp.enviar(_mensagem(), fabrica_smtp=smtp, dormir=lambda _s: None)
    assert len(smtp.instancias) == 1


# ------------------------------------------------------------------ saúde
@pytest.fixture
def app_saude(monkeypatch):
    monkeypatch.setattr(saude, "_VERIFICACOES", {})
    monkeypatch.setattr(saude, "_ESTADO", {"desligando": False})
    app = Flask(__name__)
    app.register_blueprint(saude.bp)
    return app.test_client()


def test_healthz_nao_depende_de_nada(app_saude):
    saude.registrar("banco", lambda: (_ for _ in ()).throw(ConnectionError("fora")))
    r = app_saude.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_readyz_ok_com_tudo_respondendo(app_saude):
    saude.registrar("banco", lambda: None)
    r = app_saude.get("/readyz")
    assert r.status_code == 200 and r.get_json() == {"status": "ok", "verificacoes": {"banco": "ok"}}


def test_readyz_503_sem_vazar_o_erro(app_saude):
    saude.registrar("banco", lambda: (_ for _ in ()).throw(ConnectionError("mysql://u:senha@db recusou")))
    r = app_saude.get("/readyz")
    assert r.status_code == 503 and r.get_json()["verificacoes"] == {"banco": "falhou"}
    assert b"senha" not in r.data


def test_readyz_503_desligando(app_saude):
    saude.registrar("banco", lambda: None)
    saude.marcar_desligando()
    r = app_saude.get("/readyz")
    assert r.status_code == 503 and r.get_json()["status"] == "desligando"
