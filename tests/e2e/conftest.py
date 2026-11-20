"""Testes ponta a ponta: a imagem de PRODUÇÃO (Dockerfile) rodando com MySQL, Redis e MinIO pelo docker-compose.

Sobe tudo uma vez por sessão (projeto compose próprio, 'mentoria_e2e'), espera o /readyz e derruba tudo no fim,
apagando os volumes. Precisa do Docker. Nada aqui acessa a internet além do download das imagens base.
"""

import os
import re
import secrets
import socket
import subprocess
import time

import pytest
import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJETO = "mentoria_e2e"
ARQUIVOS_COMPOSE = ["-f", os.path.join(RAIZ, "docker-compose.yml"), "-f", os.path.join(RAIZ, "tests", "e2e", "docker-compose.e2e.yml")]


def pytest_collection_modifyitems(items):
    for item in items:
        if "e2e" in item.path.parts:
            item.add_marker(pytest.mark.e2e)


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Pilha:
    def __init__(self):
        self.porta_web = _porta_livre()
        self.porta_minio = _porta_livre()
        self.porta_redis = _porta_livre()
        self.ambiente = dict(
            os.environ,
            SECRET_KEY=secrets.token_hex(32),
            PORTA_WEB=str(self.porta_web),
            PORTA_MINIO_E2E=str(self.porta_minio),
            PORTA_REDIS_E2E=str(self.porta_redis),
            MYSQL_PASSWORD="e2e_" + secrets.token_hex(8),
            MINIO_SENHA="e2e_" + secrets.token_hex(12),
        )
        self.url = f"http://127.0.0.1:{self.porta_web}"

    def compose(self, *args, verificar=True, tempo=900):
        cmd = ["docker", "compose", "-p", PROJETO, *ARQUIVOS_COMPOSE, *args]
        r = subprocess.run(cmd, cwd=RAIZ, env=self.ambiente, capture_output=True, text=True, timeout=tempo)
        if verificar and r.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} falhou ({r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
        return r

    def python_no_web(self, codigo):
        """Roda Python dentro do contêiner web (mesma imagem, mesmo ambiente). Devolve a saída padrão."""
        return self.compose("exec", "-T", "web", "python", "-c", codigo).stdout

    def esperar(self, caminho="/readyz", status=200, prazo=180):
        fim = time.time() + prazo
        ultimo = None
        while time.time() < fim:
            try:
                ultimo = requests.get(self.url + caminho, timeout=5)
                if ultimo.status_code == status:
                    return ultimo
            except requests.RequestException as erro:
                ultimo = erro
            time.sleep(2)
        raise TimeoutError(f"{caminho} não chegou a {status}: {ultimo!r}")

    def id_do_conteiner(self, servico):
        return self.compose("ps", "-q", servico).stdout.strip()

    def logs(self, servico):
        return self.compose("logs", "--no-color", servico, verificar=False).stdout


@pytest.fixture(scope="session")
def pilha():
    p = Pilha()
    try:
        p.compose("build", tempo=1800)
        p.compose("up", "-d")
        p.esperar()
        yield p
    finally:
        p.compose("down", "-v", "--remove-orphans", verificar=False)


SENHA_E2E = "E2e@" + secrets.token_hex(6) + "A1"


@pytest.fixture(scope="session")
def admin(pilha):
    """Conta de administrador criada direto no banco do ambiente E2E. Devolve o e-mail."""
    email = f"e2e_admin_{secrets.token_hex(4)}@local.com"
    pilha.python_no_web(
        "from app import app, db, bcrypt, VERSAO_TERMO_ATUAL\n"
        "from models import Usuario, TermoAceite, SegurancaUsuario\n"
        "with app.app_context():\n"
        f"    u = Usuario(nome='Admin E2E', email='{email}', tipo_usuario='Administrador', status='Ativo')\n"
        f"    u.senha = bcrypt.generate_password_hash('{SENHA_E2E}').decode(); u.forcar_troca_senha = False\n"
        "    db.session.add(u); db.session.commit()\n"
        "    r = bcrypt.generate_password_hash('x').decode()\n"
        "    db.session.add_all([TermoAceite(usuario_id=u.id, versao_termo=VERSAO_TERMO_ATUAL),\n"
        "        SegurancaUsuario(usuario_id=u.id, pergunta_1='a', resposta_1=r, pergunta_2='b', resposta_2=r, pergunta_3='c', resposta_3=r)])\n"
        "    db.session.commit()\n"
    )
    return email


class Sessao(requests.Session):
    """Navegador simples: guarda o cookie e manda o token CSRF da página nos POSTs."""

    def __init__(self, url):
        super().__init__()
        self.base = url
        self.token = None

    def abrir(self, caminho="/"):
        r = self.get(self.base + caminho, timeout=15)
        m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
        if m:
            self.token = m.group(1)
        return r

    def enviar(self, caminho, dados=None, arquivos=None, **kw):
        if not self.token:
            self.abrir()
        dados = dict(dados or {}, csrf_token=self.token)
        return self.post(self.base + caminho, data=dados, files=arquivos, timeout=30, **kw)

    def entrar(self, email, senha):
        self.abrir("/")
        r = self.enviar("/", {"email": email, "senha": senha}, allow_redirects=False)
        assert r.status_code == 302, r.status_code
        self.abrir("/dashboard")
        return r


@pytest.fixture(scope="session")
def senha_admin():
    return SENHA_E2E


@pytest.fixture
def navegador(pilha):
    return Sessao(pilha.url)
