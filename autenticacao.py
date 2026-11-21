# -*- coding: utf-8 -*-
"""
AUTENTICAÇÃO — MFA (app autenticador), primeiro acesso e acesso de emergência
=============================================================================
MFA: código de 6 dígitos de um app autenticador (Google Authenticator, Microsoft Authenticator, Authy, 1Password…),
padrão TOTP (RFC 6238, 30 segundos). O segredo fica cifrado com a SECRET_KEY; os 10 códigos de recuperação ficam só
como hash e cada um vale uma vez. Quem é obrigado a usar: Parâmetros de regras › Senhas e acesso (mfa_obrigatorio).
Contas de teste dos agentes (@local.com) não usam MFA (em produção elas nem entram, salvo OMNITEST_PERMITIR_EM_PRODUCAO).

Primeiro acesso: enquanto o banco não tiver nenhum Administrador ativo (instalação nova, banco novo depois de mudar de
servidor), a tela de login oferece "Configurar o primeiro acesso". Ela pede um código de uso único que só quem tem
acesso ao servidor vê (log do servidor ou o comando `flask --app app primeiro-acesso`). Assim ninguém fica trancado
fora e ninguém de fora cria o Administrador.

Emergência: `flask --app app admin-emergencia --email voce@instituicao.org` (no servidor ou no contêiner) cria um
Administrador ou devolve o acesso de um existente: senha provisória nova, desbloqueio e MFA refeito no próximo login.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from datetime import datetime, timedelta

PASSO_SEGUNDOS = 30
DIGITOS = 6
JANELA = 1                      # aceita o código anterior e o seguinte (relógio do celular um pouco fora)
JANELA_ATIVACAO = 10            # na ativação aceita até 5 min de diferença entre os relógios e guarda essa diferença
CODIGOS_RECUPERACAO = 10
MINUTOS_PENDENTE = 10           # tempo para digitar o código depois da senha
TENTATIVAS_MFA = 5              # códigos errados antes de voltar para a senha
HORAS_CODIGO_PRIMEIRO_ACESSO = 24
CHAVE_PRIMEIRO_ACESSO = 'primeiro_acesso'


# ------------------------------------------------------------------------------
# TOTP (RFC 6238) e cifra do segredo
# ------------------------------------------------------------------------------
def gerar_segredo():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _codigo_no_passo(segredo, passo):
    chave = base64.b32decode(segredo + '=' * (-len(segredo) % 8), casefold=True)
    resumo = hmac.new(chave, struct.pack('>Q', passo), hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    numero = struct.unpack('>I', resumo[deslocamento:deslocamento + 4])[0] & 0x7FFFFFFF
    return str(numero % (10 ** DIGITOS)).zfill(DIGITOS)


def passo_atual(agora=None):
    return int((agora if agora is not None else time.time()) // PASSO_SEGUNDOS)


def codigo_atual(segredo, agora=None):
    return _codigo_no_passo(segredo, passo_atual(agora))


def conferir_totp(segredo, codigo, ultimo_passo=None, agora=None, desvio=0, janela=JANELA):
    """Passo aceito (int) ou None. Recusa o código de um passo já usado (não vale reaproveitar o mesmo código).
    desvio = diferença conhecida entre o relógio do celular e o do servidor (em passos de 30 s, medida na ativação):
    confere em volta da hora do servidor e em volta da hora do celular, assim funciona com ou sem o relógio acertado."""
    codigo = ''.join(c for c in str(codigo or '') if c.isdigit())
    if len(codigo) != DIGITOS or not segredo:
        return None
    atual = passo_atual(agora)
    desvio = int(desvio or 0)
    candidatos = set(range(atual - janela, atual + janela + 1)) | set(range(atual + desvio - JANELA, atual + desvio + JANELA + 1))
    for passo in sorted(candidatos, key=lambda p: abs(p - atual)):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(_codigo_no_passo(segredo, passo), codigo):
            return passo
    return None


def uri_otpauth(segredo, conta, emissor):
    from urllib.parse import quote
    emissor = (emissor or 'Mentoria').replace(':', '')
    return (f"otpauth://totp/{quote(emissor)}:{quote(conta)}?secret={segredo}&issuer={quote(emissor)}"
            f"&algorithm=SHA1&digits={DIGITOS}&period={PASSO_SEGUNDOS}")


def qr_svg(texto):
    """QR code em SVG (texto pronto para pôr na página) ou '' se o pacote qrcode não estiver instalado."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ''
    imagem = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    svg = imagem.to_string(encoding='unicode')
    return svg[svg.index('<svg'):] if '<svg' in svg else svg


def _fernet(segredo_app):
    from cryptography.fernet import Fernet
    chave = hashlib.sha256(('mfa-totp:' + str(segredo_app)).encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar_segredo(segredo, segredo_app):
    return _fernet(segredo_app).encrypt(segredo.encode('ascii')).decode('ascii')


def decifrar_segredo(cifrado, segredo_app):
    """Segredo TOTP ou None (SECRET_KEY trocada: a pessoa usa um código de recuperação ou o Administrador redefine)."""
    from cryptography.fernet import InvalidToken
    if not cifrado:
        return None
    try:
        return _fernet(segredo_app).decrypt(cifrado.encode('ascii')).decode('ascii')
    except (InvalidToken, ValueError):
        return None


# ------------------------------------------------------------------------------
# Códigos de recuperação
# ------------------------------------------------------------------------------
def _hash_codigo(codigo):
    return hashlib.sha256(''.join(c for c in codigo.upper() if c.isalnum()).encode('ascii')).hexdigest()


def gerar_codigos_recuperacao():
    """(códigos para mostrar uma única vez, JSON com os hashes para gravar)."""
    alfabeto = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # sem 0/O e 1/I, que se confundem
    codigos = []
    for _ in range(CODIGOS_RECUPERACAO):
        bruto = ''.join(secrets.choice(alfabeto) for _ in range(10))
        codigos.append(f'{bruto[:5]}-{bruto[5:]}')
    return codigos, json.dumps([_hash_codigo(c) for c in codigos])


def usar_codigo_recuperacao(usuario, codigo):
    """Confere e gasta o código (True/False). Quem chama faz o commit."""
    try:
        hashes = json.loads(usuario.mfa_codigos_recuperacao or '[]')
    except ValueError:
        return False
    alvo = _hash_codigo(codigo or '')
    for h in hashes:
        if hmac.compare_digest(h, alvo):
            hashes.remove(h)
            usuario.mfa_codigos_recuperacao = json.dumps(hashes)
            return True
    return False


def codigos_restantes(usuario):
    try:
        return len(json.loads(usuario.mfa_codigos_recuperacao or '[]'))
    except ValueError:
        return 0


def segredo_em_configuracao(usuario, segredo_app):
    """Segredo da configuração em andamento: o mesmo QR code vale até a ativação, mesmo saindo e entrando de novo
    (antes, cada login gerava outro QR e o app ficava com uma conta antiga que nunca conferia). Quem chama faz o commit."""
    segredo = None if usuario.mfa_ativo else decifrar_segredo(usuario.mfa_segredo, segredo_app)
    if not segredo:
        segredo = gerar_segredo()
        usuario.mfa_segredo = cifrar_segredo(segredo, segredo_app)
    return segredo


def ativar(usuario, segredo, segredo_app, passo, agora=None):
    """Grava o MFA do usuário e devolve os códigos de recuperação (mostrar uma única vez). Quem chama faz o commit.
    Guarda a diferença entre o relógio do celular e o do servidor (mfa_desvio) medida neste código."""
    codigos, hashes = gerar_codigos_recuperacao()
    usuario.mfa_desvio = passo - passo_atual(agora)
    usuario.mfa_segredo = cifrar_segredo(segredo, segredo_app)
    usuario.mfa_codigos_recuperacao = hashes
    usuario.mfa_ultimo_passo = passo
    usuario.mfa_ativo = True
    usuario.mfa_ativado_em = datetime.utcnow()
    return codigos


def redefinir(usuario):
    """Apaga o MFA: no próximo login a pessoa configura de novo (se for obrigatório para ela)."""
    usuario.mfa_ativo = False
    usuario.mfa_segredo = None
    usuario.mfa_codigos_recuperacao = None
    usuario.mfa_ultimo_passo = None
    usuario.mfa_ativado_em = None
    usuario.mfa_desvio = None


def conta_de_teste(email):
    return (email or '').lower().endswith('@local.com')


def exige_mfa(usuario, origem='senha'):
    """Este login precisa do segundo fator? MFA já ativado vale sempre no login por senha; no Google, só se o
    parâmetro mfa_no_login_google estiver ligado (o Google já tem a verificação em duas etapas dele)."""
    from regras_negocio import regra
    if conta_de_teste(usuario.email):
        return False
    if origem == 'google' and not regra('mfa_no_login_google'):
        return False
    return bool(usuario.mfa_ativo) or bool(regra('mfa_obrigatorio'))


# ------------------------------------------------------------------------------
# Primeiro acesso (banco sem nenhum Administrador)
# ------------------------------------------------------------------------------
def _ler_config(chave):
    from models import ConfiguracaoSistema
    item = ConfiguracaoSistema.query.filter_by(chave=chave).first()
    if not item:
        return None
    try:
        return json.loads(item.valor)
    except ValueError:
        return None


def _gravar_config(chave, valor):
    from models import db, ConfiguracaoSistema
    item = ConfiguracaoSistema.query.filter_by(chave=chave).first() or ConfiguracaoSistema(chave=chave)
    item.valor = json.dumps(valor)
    db.session.add(item)
    db.session.commit()


def _apagar_config(chave):
    from models import db, ConfiguracaoSistema
    ConfiguracaoSistema.query.filter_by(chave=chave).delete()
    db.session.commit()


def ha_administrador():
    """Existe Administrador ativo de verdade? As contas dos agentes de teste (@local.com) não contam."""
    from models import Usuario
    return Usuario.query.filter(Usuario.tipo_usuario == 'Administrador', Usuario.status == 'Ativo',  # regra-nomeada: ok (perfil-alvo é dado)
                                ~Usuario.email.ilike('%@local.com')).first() is not None


def primeiro_acesso_pendente():
    try:
        return not ha_administrador()
    except Exception:
        return False   # banco ainda sem estrutura: o instalador ou as migrações resolvem antes


def novo_codigo_primeiro_acesso(log=None):
    """Gera (e devolve) um código novo de uso único; o anterior deixa de valer. Só o hash fica no banco."""
    codigo = '-'.join(secrets.token_hex(3).upper() for _ in range(3))
    _gravar_config(CHAVE_PRIMEIRO_ACESSO, {'hash': _hash_codigo(codigo),
                                           'expira': (datetime.utcnow() + timedelta(hours=HORAS_CODIGO_PRIMEIRO_ACESSO)).isoformat()})
    if log is not None:
        log.warning("PRIMEIRO ACESSO: nenhum Administrador no banco. Código de uso único (vale %sh): %s  "
                    "-> abra a tela de login e clique em 'Configurar o primeiro acesso'.", HORAS_CODIGO_PRIMEIRO_ACESSO, codigo)
    return codigo


def garantir_codigo_primeiro_acesso(log=None):
    """Sem Administrador e sem código válido: gera um e escreve no log do servidor. Devolve True se está pendente."""
    if not primeiro_acesso_pendente():
        return False
    atual = _ler_config(CHAVE_PRIMEIRO_ACESSO) or {}
    try:
        valido = datetime.fromisoformat(atual.get('expira', '')) > datetime.utcnow()
    except ValueError:
        valido = False
    if not valido:
        novo_codigo_primeiro_acesso(log)
    return True


def conferir_codigo_primeiro_acesso(codigo):
    atual = _ler_config(CHAVE_PRIMEIRO_ACESSO) or {}
    try:
        if datetime.fromisoformat(atual.get('expira', '')) <= datetime.utcnow():
            return False
    except ValueError:
        return False
    return bool(atual.get('hash')) and hmac.compare_digest(atual['hash'], _hash_codigo(codigo or ''))


def encerrar_primeiro_acesso():
    _apagar_config(CHAVE_PRIMEIRO_ACESSO)


def segredo_da_sessao_valido(pendente, agora=None):
    """O login pela metade (senha certa, falta o código) vale MINUTOS_PENDENTE minutos."""
    agora = agora or time.time()
    return bool(pendente) and agora - float(pendente.get('desde', 0)) <= MINUTOS_PENDENTE * 60


def nome_emissor():
    """Nome que aparece no app autenticador (o da plataforma cadastrado em Identidade, senão 'Mentoria')."""
    try:
        import identidade
        return identidade.obter().get('plataforma') or 'Mentoria'
    except Exception:
        return os.environ.get('MFA_EMISSOR') or 'Mentoria'
