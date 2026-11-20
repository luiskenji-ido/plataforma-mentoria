"""Regras de negócio (conversão dos valores digitados) e credenciais (cifra e formato)."""

import pytest

import credenciais_agentes as cred
import regras_negocio as rn


@pytest.mark.parametrize(
    "tipo, texto, esperado",
    [
        ("inteiro", " 42 ", 42),
        ("inteiro", "-3", -3),
        ("decimal", "6,5", 6.5),
        ("decimal", "7", 7.0),
        ("decimal", "1.23456", 1.23),
        ("sim_nao", "Sim", True),
        ("sim_nao", "não", False),
        ("sim_nao", "1", True),
        ("texto", "  algo  ", "algo"),
    ],
)
def test_converter_aceita_os_formatos_validos(tipo, texto, esperado):
    assert rn.converter(tipo, texto) == esperado


@pytest.mark.parametrize(
    "tipo, texto, mensagem",
    [
        ("inteiro", "4.5", "inteiro"),
        ("inteiro", "", "inteiro"),
        ("decimal", "abc", "número"),
        ("sim_nao", "talvez", "sim ou não"),
        ("texto", "   ", "Informe um valor"),
        ("texto", None, "Informe um valor"),
    ],
)
def test_converter_recusa_com_explicacao(tipo, texto, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        rn.converter(tipo, texto)


def test_texto_longo_e_cortado_em_500():
    assert len(rn.converter("texto", "x" * 900)) == 500


def test_para_texto():
    assert rn.para_texto(True) == "sim"
    assert rn.para_texto(False) == "nao"
    assert rn.para_texto(85) == "85"


def test_chave_de_regra_valida():
    assert rn.CHAVE_VALIDA.match("freq_minima_pct")
    assert not rn.CHAVE_VALIDA.match("1abc")
    assert not rn.CHAVE_VALIDA.match("Freq")


# ------------------------------------------------------------------ credenciais
def test_cifra_e_decifra_com_o_mesmo_segredo():
    token = cred.cifrar("sk-123", "segredo-a")
    assert token != "sk-123"
    assert cred.decifrar(token, "segredo-a") == "sk-123"


def test_segredo_diferente_nao_decifra():
    assert cred.decifrar(cred.cifrar("sk-123", "segredo-a"), "segredo-b") is None


def test_token_corrompido_nao_decifra():
    assert cred.decifrar("nao-e-um-token", "s") is None


def test_validar_chave_de_api():
    assert cred.validar("OPENAI_API_KEY", "sk-" + "a" * 30) is None
    assert cred.validar("OPENAI_API_KEY", "curta") is not None
    assert cred.validar("OPENAI_API_KEY", "sk-" + "a" * 20 + " " + "b" * 5) is not None


def test_validar_apelido_do_grupo():
    assert cred.validar("COMITE_APROVACAO_APELIDO", "B2B-Comite-Aprovacao") is None
    assert cred.validar("COMITE_APROVACAO_APELIDO", "grupo; DROP TABLE") is not None
