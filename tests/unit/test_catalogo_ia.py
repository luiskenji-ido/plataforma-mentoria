"""Regras do Agente de Preços e Modelos de IA (sem banco e sem rede)."""

import agente_catalogo_ia as ag


def test_versao_pelo_identificador():
    assert ag.versao("claude-sonnet-5-5") == 5.5
    assert ag.versao("gemini-3.6-flash") == 3.6
    assert ag.versao("gpt-6.2-sol") == 6.2
    assert ag.versao("gpt-6-luna") == 6.0
    assert ag.versao("sem-numero") == 0.0


def test_so_modelos_de_texto_estaveis():
    assert ag.modelo_de_texto("gemini", "gemini-3.9-flash")
    assert ag.modelo_de_texto("claude", "claude-opus-5-5")
    assert ag.modelo_de_texto("openai", "gpt-6.2-sol")
    for provedor, mid in [
        ("gemini", "gemini-3.9-flash-preview"),
        ("gemini", "gemini-3.9-flash-tts"),
        ("gemini", "gemini-2.0-flash-001"),
        ("claude", "claude-haiku-5-5-20261001"),
        ("openai", "gpt-6.2-realtime"),
        ("openai", "gpt-6.2-sol-2026-10-01"),
        ("openai", "text-embedding-4"),
        ("openai", "dall-e-4"),
    ]:
        assert not ag.modelo_de_texto(provedor, mid), mid


def test_preco_da_fonte_por_milhao_e_prefixo():
    tabela = {
        "anthropic/claude-haiku-5-5": {"input_cost_per_token": 1e-07, "output_cost_per_token": 5e-07},
        "gpt-6.2-sol": {"input_cost_per_token": 2e-06, "output_cost_per_token": 1e-05},
        "gemini/gemini-x": {"input_cost_per_token": "abc", "output_cost_per_token": 1},
    }
    assert ag.preco_da_fonte(tabela, "claude", "claude-haiku-5-5") == (0.1, 0.5)
    assert ag.preco_da_fonte(tabela, "openai", "gpt-6.2-sol") == (2.0, 10.0)
    assert ag.preco_da_fonte(tabela, "gemini", "gemini-x") is None
    assert ag.preco_da_fonte(tabela, "gemini", "nao-existe") is None


def test_variacao_grande_fica_para_revisao():
    assert ag._variacao_aceitavel((1.0, 5.0), (2.0, 10.0))
    assert not ag._variacao_aceitavel((1.0, 5.0), (4.0, 5.0))
    assert not ag._variacao_aceitavel((1.0, 5.0), (0.2, 5.0))
    assert ag._variacao_aceitavel((None, None), (9.0, 9.0))
