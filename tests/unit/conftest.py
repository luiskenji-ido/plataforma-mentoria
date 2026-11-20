"""Testes de unidade: rápidos e isolados. Nenhum teste desta camada abre conexão de rede nem importa o app
(importar o app abre o banco e roda as migrações)."""

import socket

import pytest


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def recusar(*_args, **_kwargs):
        raise AssertionError("teste de unidade tentou acessar a rede")

    monkeypatch.setattr(socket.socket, "connect", recusar)
    monkeypatch.setattr(socket, "create_connection", recusar)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    """Variáveis que mudam o comportamento da plataforma não vazam do computador de quem roda os testes."""
    for nome in (
        "SECRET_KEY",
        "DATABASE_URL",
        "MENTORIA_PRODUCAO",
        "PYTHONANYWHERE_DOMAIN",
        "ATRAS_DE_PROXY",
        "AWS_EXECUTION_ENV",
        "AWS_LAMBDA_FUNCTION_NAME",
        "ECS_CONTAINER_METADATA_URI_V4",
        "ECS_CONTAINER_METADATA_URI",
        "AWS_APP_RUNNER_SERVICE_ID",
        "DB_POOL_SIZE",
        "DB_POOL_RECYCLE",
        "DB_MAX_OVERFLOW",
        "MENTORIA_CONTEINER",
        "MENTORIA_EXIGIR_SECRET_KEY",
        "GOOGLE_CLIENT_SECRETS_FILE",
        "DB_POOL_TIMEOUT",
        "DB_CONNECT_TIMEOUT",
        "DB_READ_TIMEOUT",
        "DB_WRITE_TIMEOUT",
        "LOG_FORMATO",
        "LOG_TRACEBACK",
        "MAIL_SERVER",
        "MAIL_USERNAME",
        "MAIL_PASSWORD",
        "MAIL_USE_TLS",
        "MAIL_PORT",
    ):
        monkeypatch.delenv(nome, raising=False)


def pytest_collection_modifyitems(items):
    for item in items:
        if "unit" in item.path.parts:
            item.add_marker(pytest.mark.unit)
