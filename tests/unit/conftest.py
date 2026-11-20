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
    ):
        monkeypatch.delenv(nome, raising=False)


def pytest_collection_modifyitems(items):
    for item in items:
        if "unit" in item.path.parts:
            item.add_marker(pytest.mark.unit)
