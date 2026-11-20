"""Testes de integração: o app de verdade contra um banco de verdade.

Banco usado, nesta ordem:
1. TEST_DATABASE_URL, se definida (ex.: o MySQL do docker-compose: mysql+pymysql://mentoria:mentoria@127.0.0.1:3306/mentoria_teste);
2. senão, um MySQL 8.4 novo em contêiner (Testcontainers), que some no fim da sessão.
O banco precisa estar vazio: as migrações rodam ao importar o app. Cada teste cria os próprios dados com e-mails
únicos e apaga o que criou no fim, sem depender da ordem dos testes.
"""

import os
import uuid

import pytest

IMAGEM_MYSQL = "mysql:8.4.3"


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def url_do_banco():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    from testcontainers.mysql import MySqlContainer

    with MySqlContainer(IMAGEM_MYSQL, dialect="pymysql", username="mentoria", password="mentoria", dbname="mentoria") as mysql:
        yield mysql.get_connection_url() + "?charset=utf8mb4"


@pytest.fixture(scope="session")
def app_real(url_do_banco, tmp_path_factory):
    """Importa o app uma vez por sessão, apontado para o banco de teste (migrações aplicadas na importação)."""
    os.environ["DATABASE_URL"] = url_do_banco
    os.environ["SECRET_KEY"] = "x" * 64
    os.environ["MENTORIA_SEM_EXECUCAO_AUTOMATICA"] = "1"
    os.environ.pop("MENTORIA_PRODUCAO", None)
    import app as modulo_app

    modulo_app.app.config.update(TESTING=False)  # CSRF ligado, como em produção
    return modulo_app


def apagar_em_cascata(db, tabela, ids, visitados=None):
    """Apaga as linhas e, antes, tudo o que aponta para elas (chaves estrangeiras declaradas nos modelos)."""
    ids = list(ids)
    if not ids:
        return
    visitados = visitados or set()
    for filha in db.metadata.sorted_tables:
        for fk in filha.foreign_keys:
            if fk.column.table is not tabela or (filha.name, fk.parent.name) in visitados:
                continue
            visitados.add((filha.name, fk.parent.name))
            pk = list(filha.primary_key.columns)
            linhas = db.session.execute(db.select(*pk).where(fk.parent.in_(ids))).all()
            if len(pk) == 1:
                apagar_em_cascata(db, filha, [linha[0] for linha in linhas], visitados)
            db.session.execute(filha.delete().where(fk.parent.in_(ids)))
            visitados.discard((filha.name, fk.parent.name))
    db.session.execute(tabela.delete().where(list(tabela.primary_key.columns)[0].in_(ids)))


@pytest.fixture
def criados(app_real):
    """Lista de (modelo, id) criados pelo teste; no fim, apaga cada um com tudo o que aponta para ele."""
    lista = []
    yield lista
    db = app_real.db
    with app_real.app.app_context():
        for modelo, ident in reversed(lista):
            apagar_em_cascata(db, modelo.__table__, [ident])
        db.session.commit()


@pytest.fixture
def novo_usuario(app_real, criados):
    """Cria um usuário pronto para entrar (termo aceito e perguntas de segurança feitas). Devolve (id, email, senha)."""
    from models import SegurancaUsuario, TermoAceite, Usuario

    def criar(tipo="Aluno"):
        email = f"it_{uuid.uuid4().hex[:10]}@local.com"
        senha = "Teste@" + uuid.uuid4().hex[:10] + "A1"
        with app_real.app.app_context():
            db, bcrypt = app_real.db, app_real.bcrypt
            u = Usuario(nome=f"IT {tipo}", email=email, tipo_usuario=tipo, status="Ativo")
            u.senha = bcrypt.generate_password_hash(senha).decode()
            u.forcar_troca_senha = False
            db.session.add(u)
            db.session.commit()
            resposta = bcrypt.generate_password_hash(uuid.uuid4().hex).decode()  # resposta aleatória por conta
            filhos = [
                TermoAceite(usuario_id=u.id, versao_termo=app_real.VERSAO_TERMO_ATUAL),
                SegurancaUsuario(
                    usuario_id=u.id,
                    pergunta_1="a",
                    resposta_1=resposta,
                    pergunta_2="b",
                    resposta_2=resposta,
                    pergunta_3="c",
                    resposta_3=resposta,
                ),
            ]
            db.session.add_all(filhos)
            db.session.commit()
            criados.append((Usuario, u.id))
            return u.id, email, senha

    return criar


class Navegador:
    """Cliente HTTP do Flask com o token CSRF da sessão, como o navegador manda."""

    def __init__(self, app):
        self.c = app.test_client()
        self.token = None

    def _token(self):
        if not self.token:
            self.c.get("/")
            with self.c.session_transaction() as s:
                self.token = s.get("_csrf_token")
        return self.token

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, data=None, com_csrf=True, **kw):
        data = dict(data or {})
        if com_csrf:
            data["csrf_token"] = self._token()
        return self.c.post(url, data=data, **kw)

    def entrar(self, email, senha):
        r = self.post("/", {"email": email, "senha": senha})
        assert r.status_code == 302, r.status_code
        return r


@pytest.fixture
def navegador(app_real):
    return Navegador(app_real.app)


@pytest.fixture
def novo_navegador(app_real):
    """Outro navegador (outra sessão), para testar o acesso de uma segunda pessoa."""
    return lambda: Navegador(app_real.app)
