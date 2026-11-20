"""SECRET_KEY: no contêiner precisa vir do ambiente (sem arquivo); fora dele, o comportamento antigo continua."""

import builtins
import os

import pytest

import ambiente
import seguranca_web as sw

CHAVE_BOA = "a" * 64


@pytest.fixture
def sem_disco(monkeypatch):
    """Qualquer leitura ou escrita de arquivo falha: prova que o caminho do contêiner não usa o disco."""

    def recusar(*_a, **_k):
        raise AssertionError("tentou usar o disco")

    monkeypatch.setattr(builtins, "open", recusar)
    monkeypatch.setattr(os, "makedirs", recusar)


@pytest.mark.parametrize("variavel", ["MENTORIA_CONTEINER", "MENTORIA_EXIGIR_SECRET_KEY"])
def test_conteiner_sem_chave_nao_sobe(monkeypatch, sem_disco, variavel):
    monkeypatch.setenv(variavel, "1")
    with pytest.raises(sw.ChaveSecretaAusente, match="SECRET_KEY"):
        sw.carregar_chave_secreta("/qualquer")


def test_conteiner_com_chave_curta_nao_sobe(monkeypatch, sem_disco):
    monkeypatch.setenv("MENTORIA_CONTEINER", "1")
    monkeypatch.setenv("SECRET_KEY", "curta")
    with pytest.raises(sw.ChaveSecretaAusente):
        sw.carregar_chave_secreta("/qualquer")


def test_conteiner_com_chave_boa_usa_o_ambiente_sem_disco(monkeypatch, sem_disco):
    monkeypatch.setenv("MENTORIA_CONTEINER", "1")
    monkeypatch.setenv("SECRET_KEY", f"  {CHAVE_BOA}  ")
    assert sw.carregar_chave_secreta("/qualquer") == CHAVE_BOA


def test_fora_do_conteiner_a_chave_do_ambiente_vale(monkeypatch, sem_disco):
    monkeypatch.delenv("MENTORIA_CONTEINER", raising=False)
    monkeypatch.setenv("SECRET_KEY", "qualquer-chave")
    assert sw.carregar_chave_secreta("/qualquer") == "qualquer-chave"


def test_exige_secret_key_so_quando_ligado(monkeypatch):
    monkeypatch.delenv("MENTORIA_CONTEINER", raising=False)
    monkeypatch.delenv("MENTORIA_EXIGIR_SECRET_KEY", raising=False)
    assert sw.exige_secret_key_no_ambiente() is False
    monkeypatch.setenv("MENTORIA_CONTEINER", "1")
    assert sw.exige_secret_key_no_ambiente() is True


# ------------------------------------------------------------------ credencial do Google
def test_client_secret_do_google_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS_FILE", "/run/secrets/google.json")
    assert ambiente.arquivo_client_secret_google() == "/run/secrets/google.json"


def test_client_secret_do_google_padrao_na_pasta_da_plataforma(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_SECRETS_FILE", raising=False)
    assert ambiente.arquivo_client_secret_google() == os.path.join(ambiente.RAIZ, "client_secret.json")
