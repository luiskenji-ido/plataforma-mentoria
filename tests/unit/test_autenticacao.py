"""MFA (TOTP RFC 6238), códigos de recuperação e cifra do segredo — sem banco e sem rede."""

import json
import types

import autenticacao as a


def test_totp_vetor_oficial_rfc6238():
    # RFC 6238, apêndice B: segredo ASCII "12345678901234567890", SHA1, T=59s -> 94287082 (8 dígitos) / 287082 (6)
    segredo = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert a.codigo_atual(segredo, agora=59) == "287082"
    assert a.codigo_atual(segredo, agora=1111111109) == "081804"


def test_conferir_aceita_janela_e_recusa_reuso():
    segredo = a.gerar_segredo()
    agora = 1_800_000_000
    codigo = a.codigo_atual(segredo, agora=agora)
    passo = a.conferir_totp(segredo, codigo, agora=agora)
    assert passo == a.passo_atual(agora)
    # o mesmo código não vale de novo (ultimo_passo gravado)
    assert a.conferir_totp(segredo, codigo, ultimo_passo=passo, agora=agora) is None
    # código do passo anterior ainda vale (relógio do celular um pouco atrasado)
    anterior = a.codigo_atual(segredo, agora=agora - 30)
    assert a.conferir_totp(segredo, anterior, agora=agora) == passo - 1
    # fora da janela, formato errado ou vazio: recusado
    assert a.conferir_totp(segredo, a.codigo_atual(segredo, agora=agora - 120), agora=agora) is None
    assert a.conferir_totp(segredo, "12a456", agora=agora) is None
    assert a.conferir_totp(None, codigo, agora=agora) is None


def test_codigo_com_espaco_e_aceito():
    segredo = a.gerar_segredo()
    codigo = a.codigo_atual(segredo, agora=1_800_000_000)
    assert a.conferir_totp(segredo, f"{codigo[:3]} {codigo[3:]}", agora=1_800_000_000) is not None


def test_segredo_cifrado_so_abre_com_a_mesma_chave():
    segredo = a.gerar_segredo()
    cifrado = a.cifrar_segredo(segredo, "chave-1")
    assert segredo not in cifrado
    assert a.decifrar_segredo(cifrado, "chave-1") == segredo
    assert a.decifrar_segredo(cifrado, "outra-chave") is None
    assert a.decifrar_segredo(None, "chave-1") is None


def test_codigos_de_recuperacao_valem_uma_vez():
    codigos, hashes = a.gerar_codigos_recuperacao()
    assert len(codigos) == a.CODIGOS_RECUPERACAO and len(set(codigos)) == len(codigos)
    assert all(c not in hashes for c in codigos)  # só o hash fica gravado
    usuario = types.SimpleNamespace(mfa_codigos_recuperacao=hashes)
    assert a.usar_codigo_recuperacao(usuario, codigos[0].lower().replace("-", ""))  # sem hífen e minúsculo também vale
    assert not a.usar_codigo_recuperacao(usuario, codigos[0])
    assert a.codigos_restantes(usuario) == a.CODIGOS_RECUPERACAO - 1
    assert not a.usar_codigo_recuperacao(usuario, "XXXXX-XXXXX")


def test_ativar_e_redefinir():
    usuario = types.SimpleNamespace()
    segredo = a.gerar_segredo()
    codigos = a.ativar(usuario, segredo, "chave", passo=10)
    assert usuario.mfa_ativo and usuario.mfa_ultimo_passo == 10 and len(codigos) == a.CODIGOS_RECUPERACAO
    assert a.decifrar_segredo(usuario.mfa_segredo, "chave") == segredo
    assert len(json.loads(usuario.mfa_codigos_recuperacao)) == a.CODIGOS_RECUPERACAO
    a.redefinir(usuario)
    assert not usuario.mfa_ativo and usuario.mfa_segredo is None and usuario.mfa_codigos_recuperacao is None


def test_uri_otpauth_e_qr():
    uri = a.uri_otpauth("ABCDEF", "pessoa@instituicao.org", "Plataforma: Teste")
    assert uri.startswith("otpauth://totp/Plataforma%20Teste:pessoa%40instituicao.org?secret=ABCDEF")
    assert "period=30" in uri and "digits=6" in uri
    assert a.qr_svg(uri).startswith("<svg")


def test_login_pela_metade_expira():
    assert a.segredo_da_sessao_valido({"desde": 1000}, agora=1000 + a.MINUTOS_PENDENTE * 60)
    assert not a.segredo_da_sessao_valido({"desde": 1000}, agora=1001 + a.MINUTOS_PENDENTE * 60)
    assert not a.segredo_da_sessao_valido(None)


def test_contas_de_teste_nao_usam_mfa(monkeypatch):
    import regras_negocio

    monkeypatch.setattr(regras_negocio, "regra", lambda chave, padrao=None: True)
    teste = types.SimpleNamespace(email="aluno_ominitest@local.com", mfa_ativo=False)
    real = types.SimpleNamespace(email="pessoa@instituicao.org", mfa_ativo=False)
    assert not a.exige_mfa(teste)
    assert a.exige_mfa(real)
    monkeypatch.setattr(regras_negocio, "regra", lambda chave, padrao=None: chave != "mfa_no_login_google")
    assert not a.exige_mfa(real, "google")
