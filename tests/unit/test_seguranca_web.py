"""seguranca_web: limitador de requisições, HTML seguro, redirecionamento interno e IP do cliente."""

import pytest
from flask import Flask

import seguranca_web as sw


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


@pytest.fixture
def relogio(monkeypatch):
    r = Relogio()
    monkeypatch.setattr(sw.time, "monotonic", r)
    return r


# ------------------------------------------------------------------ limitador
def test_limitador_permite_ate_o_maximo_e_depois_recusa_com_espera(relogio):
    lim = sw.LimitadorRequisicoes()
    assert [lim.permitir("k", 3, 60)[0] for _ in range(3)] == [True, True, True]
    permitido, espera = lim.permitir("k", 3, 60)
    assert permitido is False
    assert espera == 61


def test_limitador_libera_quando_a_janela_passa(relogio):
    lim = sw.LimitadorRequisicoes()
    for _ in range(2):
        lim.permitir("k", 2, 60)
    relogio.agora += 61
    assert lim.permitir("k", 2, 60) == (True, 0)


def test_limitador_conta_cada_chave_separada(relogio):
    lim = sw.LimitadorRequisicoes()
    lim.permitir(("login", "1.1.1.1"), 1, 60)
    assert lim.permitir(("login", "1.1.1.1"), 1, 60)[0] is False
    assert lim.permitir(("login", "2.2.2.2"), 1, 60)[0] is True


# ------------------------------------------------------------------ HTML seguro
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("<b>oi</b>", "<b>oi</b>"),
        ("<script>alert(1)</script>texto", "texto"),
        ('<a href="javascript:alert(1)">x</a>', "<a>x</a>"),
        ('<img src="x" onerror="alert(1)">', '<img src="x">'),
        ('<a href="https://ex.org" target="_blank">x</a>', '<a href="https://ex.org" target="_blank" rel="noopener noreferrer">x</a>'),
        ("1 < 2 & 3", "1 &lt; 2 &amp; 3"),
        ("<iframe src='https://mal.org'></iframe><p>ok</p>", "<p>ok</p>"),
        ("", ""),
        (None, ""),
    ],
)
def test_html_seguro_deixa_so_formatacao(entrada, esperado):
    assert str(sw.html_seguro(entrada)) == esperado


# ------------------------------------------------------------------ redirecionamento e IP
@pytest.fixture
def app():
    return Flask(__name__)


@pytest.mark.parametrize(
    "url, esperado",
    [
        ("/dashboard", "/dashboard"),
        ("http://localhost/perfil", "http://localhost/perfil"),
        ("https://mal.org/roubo", "/padrao"),
        ("//mal.org/roubo", "/padrao"),
        ("javascript:alert(1)", "/padrao"),
        ("", "/padrao"),
        (None, "/padrao"),
    ],
)
def test_destino_interno_so_aceita_o_proprio_site(app, url, esperado):
    with app.test_request_context("/", base_url="http://localhost"):
        assert sw.destino_interno(url, "/padrao") == esperado


def test_ip_do_cliente_ignora_cabecalho_fora_de_proxy(app):
    with app.test_request_context("/", headers={"X-Real-IP": "6.6.6.6"}, environ_base={"REMOTE_ADDR": "10.0.0.1"}):
        assert sw.ip_do_cliente() == "10.0.0.1"


def test_ip_do_cliente_confia_no_proxy_quando_configurado(app, monkeypatch):
    monkeypatch.setenv("ATRAS_DE_PROXY", "1")
    with app.test_request_context("/", headers={"X-Real-IP": "8.8.8.8"}, environ_base={"REMOTE_ADDR": "10.0.0.1"}):
        assert sw.ip_do_cliente() == "8.8.8.8"


# ------------------------------------------------------------------ limitador no Redis
class PipeFalso:
    def __init__(self, cliente):
        self.cliente, self.ops = cliente, []

    def incr(self, nome):
        self.ops.append(("incr", nome))

    def expire(self, nome, segundos):
        self.ops.append(("expire", nome, segundos))

    def execute(self):
        if self.cliente.fora_do_ar:
            raise ConnectionError("redis fora")
        resultado = []
        for op in self.ops:
            if op[0] == "incr":
                self.cliente.valores[op[1]] = self.cliente.valores.get(op[1], 0) + 1
                resultado.append(self.cliente.valores[op[1]])
            else:
                self.cliente.expiracoes[op[1]] = op[2]
                resultado.append(True)
        return resultado


class RedisFalso:
    def __init__(self):
        self.valores, self.expiracoes, self.fora_do_ar = {}, {}, False

    def pipeline(self):
        return PipeFalso(self)


def test_redis_conta_por_janela_e_chave_e_expira():
    redis = RedisFalso()
    lim = sw.LimitadorRedis(redis, relogio=lambda: 1200.0)
    assert [lim.permitir(("login", "1.1.1.1"), 2, 60)[0] for _ in range(2)] == [True, True]
    assert lim.permitir(("login", "1.1.1.1"), 2, 60) == (False, 61)
    assert lim.permitir(("login", "2.2.2.2"), 2, 60)[0] is True
    assert all(segundos == 61 for segundos in redis.expiracoes.values())


def test_redis_janela_nova_libera():
    agora = [1200.0]
    lim = sw.LimitadorRedis(RedisFalso(), relogio=lambda: agora[0])
    lim.permitir("k", 1, 60)
    assert lim.permitir("k", 1, 60)[0] is False
    agora[0] += 60
    assert lim.permitir("k", 1, 60)[0] is True


def test_redis_fora_do_ar_usa_o_limite_local(relogio):
    redis = RedisFalso()
    redis.fora_do_ar = True
    lim = sw.LimitadorRedis(redis)
    assert lim.permitir("k", 1, 60) == (True, 0)
    assert lim.permitir("k", 1, 60)[0] is False  # o limite local continua valendo


def test_chave_do_redis_nao_aceita_caracteres_de_controle():
    redis = RedisFalso()
    sw.LimitadorRedis(redis, relogio=lambda: 0.0).permitir(("login", "1.1.1.1\r\nFLUSHALL"), 5, 60)
    (nome,) = redis.valores
    assert "\r" not in nome and "\n" not in nome and " " not in nome


def test_sem_redis_url_o_limitador_e_em_memoria(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert isinstance(sw.criar_limitador(), sw.LimitadorRequisicoes)
