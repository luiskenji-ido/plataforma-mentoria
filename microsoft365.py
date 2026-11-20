# -*- coding: utf-8 -*-
"""
CONEXÃO COM O MICROSOFT 365 (Outlook / Agenda) PELO MICROSOFT GRAPH
==================================================================
Cada pessoa conecta a própria conta corporativa (login oficial da Microsoft, OAuth 2.0 com PKCE).
A plataforma nunca vê a senha: guarda só os tokens, cifrados no banco (chave derivada da SECRET_KEY).

Permissões pedidas (delegadas, em nome da pessoa):
  - User.Read            → nome e e-mail da conta conectada;
  - Calendars.ReadWrite  → criar e atualizar eventos na agenda dela (o Outlook envia os convites aos participantes);
  - offline_access       → renovar o acesso sem pedir login de novo.

Aplicativo registrado no Microsoft Entra ID (o antigo Azure AD). Configuração, nesta ordem de prioridade:
tela Provedores de IA e custos › Credenciais (Administrador) ou o .env:
  MS365_CLIENT_ID, MS365_CLIENT_SECRET e MS365_TENANT (padrão 'organizations' = contas de qualquer empresa).
"""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

AUTORIDADE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0'
GRAPH = 'https://graph.microsoft.com/v1.0'
ESCOPOS = ['openid', 'profile', 'email', 'offline_access', 'User.Read', 'Calendars.ReadWrite']
FUSO_WINDOWS = 'E. South America Standard Time'  # horário de Brasília no Outlook
TIMEOUT = 20


class ErroMicrosoft(Exception):
    """Falha ao falar com a Microsoft; 'codigo' traz o erro devolvido (ex.: consent_required)."""
    def __init__(self, mensagem, codigo=''):
        super().__init__(mensagem)
        self.codigo = codigo or ''


# ------------------------------------------------------------------ configuração
def configuracao():
    client_id = (os.environ.get('MS365_CLIENT_ID') or '').strip()
    segredo = (os.environ.get('MS365_CLIENT_SECRET') or '').strip()
    tenant = (os.environ.get('MS365_TENANT') or 'organizations').strip() or 'organizations'
    return client_id, segredo, tenant


def configurado():
    client_id, segredo, _ = configuracao()
    return bool(client_id and segredo)


def _requisicao(metodo, url, **kwargs):
    """Ponto único de saída para a internet (os testes trocam esta função por uma simulação). Conexões reaproveitadas
    e novas tentativas só nos métodos que podem repetir e nas respostas 429/502/503/504 (resiliencia.py)."""
    import resiliencia
    return resiliencia.sessao_http().request(metodo, url, timeout=TIMEOUT, **kwargs)


def _json(resposta):
    try:
        return resposta.json()
    except ValueError:
        return {}


# ------------------------------------------------------------------ login (OAuth 2.0 + PKCE)
def novo_pkce():
    verificador = secrets.token_urlsafe(64)[:96]
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verificador, desafio


def url_login(redirect_uri, state, desafio, email_sugerido=None):
    client_id, _, tenant = configuracao()
    parametros = {'client_id': client_id, 'response_type': 'code', 'redirect_uri': redirect_uri, 'response_mode': 'query',
                  'scope': ' '.join(ESCOPOS), 'state': state, 'code_challenge': desafio, 'code_challenge_method': 'S256',
                  'prompt': 'select_account'}
    if email_sugerido:
        parametros['login_hint'] = email_sugerido
    return AUTORIDADE.format(tenant=tenant) + '/authorize?' + urlencode(parametros)


def _token(dados):
    client_id, segredo, tenant = configuracao()
    dados = dict(dados, client_id=client_id, client_secret=segredo, scope=' '.join(ESCOPOS))
    resposta = _requisicao('POST', AUTORIDADE.format(tenant=tenant) + '/token', data=dados)
    corpo = _json(resposta)
    if resposta.status_code != 200 or 'access_token' not in corpo:
        raise ErroMicrosoft(corpo.get('error_description') or f'HTTP {resposta.status_code}', corpo.get('error', ''))
    return corpo


def trocar_codigo(codigo, redirect_uri, verificador):
    return _token({'grant_type': 'authorization_code', 'code': codigo, 'redirect_uri': redirect_uri, 'code_verifier': verificador})


def renovar(refresh_token):
    return _token({'grant_type': 'refresh_token', 'refresh_token': refresh_token})


# ------------------------------------------------------------------ Graph
def _graph(metodo, caminho, token, **kwargs):
    cabecalhos = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    resposta = _requisicao(metodo, GRAPH + caminho, headers=cabecalhos, **kwargs)
    corpo = _json(resposta)
    if resposta.status_code >= 400:
        erro = corpo.get('error') or {}
        raise ErroMicrosoft(erro.get('message') or f'HTTP {resposta.status_code}', erro.get('code', ''))
    return corpo


def quem_sou(token):
    dados = _graph('GET', '/me?$select=displayName,mail,userPrincipalName', token)
    return dados.get('displayName') or '', (dados.get('mail') or dados.get('userPrincipalName') or '').lower()


def _quando(dt):
    return {'dateTime': dt.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': FUSO_WINDOWS}


def montar_evento(titulo, descricao, inicio, fim, local=None, participantes=(), reuniao_online=False):
    """Evento do Outlook. Com participantes, o próprio Outlook envia o convite (aceitar/recusar) e as atualizações."""
    evento = {'subject': titulo[:255], 'body': {'contentType': 'text', 'content': descricao or ''},
              'start': _quando(inicio), 'end': _quando(fim),
              'attendees': [{'emailAddress': {'address': email, 'name': nome or email}, 'type': 'required'}
                            for nome, email in participantes]}
    if local:
        evento['location'] = {'displayName': local[:255]}
    if reuniao_online:
        evento['isOnlineMeeting'] = True
        evento['onlineMeetingProvider'] = 'teamsForBusiness'
    return evento


def criar_evento(token, evento):
    try:
        return _graph('POST', '/me/events', token, json=evento)
    except ErroMicrosoft:
        if evento.get('isOnlineMeeting'):  # conta sem Teams: cria o evento sem a sala on-line
            evento = {k: v for k, v in evento.items() if k not in ('isOnlineMeeting', 'onlineMeetingProvider')}
            return _graph('POST', '/me/events', token, json=evento)
        raise


def atualizar_evento(token, evento_id, evento):
    evento = {k: v for k, v in evento.items() if k not in ('isOnlineMeeting', 'onlineMeetingProvider')}
    return _graph('PATCH', f'/me/events/{evento_id}', token, json=evento)


# ------------------------------------------------------------------ tokens guardados (cifrados) por pessoa
def _fernet(segredo):
    from cryptography.fernet import Fernet
    chave = hashlib.sha256(('contas-conectadas:' + str(segredo)).encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(valor, segredo):
    return _fernet(segredo).encrypt((valor or '').encode('utf-8')).decode('ascii')


def decifrar(valor, segredo):
    from cryptography.fernet import InvalidToken
    try:
        return _fernet(segredo).decrypt(valor.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError, AttributeError):
        return None


def salvar_conta(db, ContaConectada, usuario_id, tokens, nome, email, segredo):
    conta = ContaConectada.query.filter_by(usuario_id=usuario_id, provedor='microsoft').first() or \
        ContaConectada(usuario_id=usuario_id, provedor='microsoft')
    conta.email, conta.nome = email[:200], (nome or '')[:150]
    conta.acesso_cifrado = cifrar(tokens['access_token'], segredo)
    if tokens.get('refresh_token'):
        conta.renovacao_cifrada = cifrar(tokens['refresh_token'], segredo)
    conta.expira_em = datetime.utcnow() + timedelta(seconds=int(tokens.get('expires_in') or 3600) - 60)
    conta.conectado_em = conta.conectado_em or datetime.utcnow()
    db.session.add(conta)
    db.session.commit()
    return conta


def token_valido(db, conta, segredo):
    """Token de acesso pronto para usar (renova sozinho quando venceu). None se a conexão caiu."""
    if conta is None:
        return None
    if conta.expira_em and conta.expira_em > datetime.utcnow():
        token = decifrar(conta.acesso_cifrado, segredo)
        if token:
            return token
    renovacao = decifrar(conta.renovacao_cifrada or '', segredo)
    if not renovacao or not configurado():
        return None
    try:
        tokens = renovar(renovacao)
    except ErroMicrosoft:
        return None
    conta.acesso_cifrado = cifrar(tokens['access_token'], segredo)
    if tokens.get('refresh_token'):
        conta.renovacao_cifrada = cifrar(tokens['refresh_token'], segredo)
    conta.expira_em = datetime.utcnow() + timedelta(seconds=int(tokens.get('expires_in') or 3600) - 60)
    db.session.commit()
    return tokens['access_token']
