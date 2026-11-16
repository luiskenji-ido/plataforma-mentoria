# -*- coding: utf-8 -*-
"""
CREDENCIAIS DOS AGENTES
=======================
A senha das contas de teste, a liberação dos agentes num servidor de produção e as chaves de IA do Orquestrador
são cadastradas pelo Administrador na área Agentes IA (só ele vê essa área). Ficam cifradas no banco (Fernet,
com chave derivada da SECRET_KEY do servidor) e nunca voltam para a tela: só aparece se estão configuradas.

Os agentes continuam lendo variáveis de ambiente: antes de iniciar qualquer equipe, a plataforma coloca as
credenciais cadastradas no ambiente do processo. O que estiver no .env vale enquanto nada for cadastrado na tela.
Se a SECRET_KEY mudar, as credenciais ficam ilegíveis e a tela pede para cadastrá-las de novo.
"""
import base64
import hashlib
import os
import time

# chave -> (nome na tela, tipo)
CAMPOS = {
    'OMNITEST_SENHA': ('Senha das contas de teste dos agentes', 'senha'),
    'OMNITEST_PERMITIR_EM_PRODUCAO': ('Permitir que os agentes entrem neste servidor de produção', 'sim_nao'),
    'ANTHROPIC_API_KEY': ('Chave da API do Claude (Agente Orquestrador)', 'chave'),
    'GEMINI_API_KEY': ('Chave da API do Gemini (Agente Orquestrador)', 'chave'),
}
TEMPO_CACHE = 60  # segundos: cada processo do servidor relê o banco no máximo uma vez por minuto
_cache = {'quando': 0.0}
_do_ambiente = {}  # o que veio do .env/ambiente antes da tela (origem e volta ao remover)


def _fernet(segredo):
    from cryptography.fernet import Fernet
    chave = hashlib.sha256(('credenciais-agentes:' + str(segredo)).encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(valor, segredo):
    return _fernet(segredo).encrypt(valor.encode('utf-8')).decode('ascii')


def decifrar(token, segredo):
    from cryptography.fernet import InvalidToken
    try:
        return _fernet(segredo).decrypt(token.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError):
        return None


def validar(chave, valor):
    """Devolve a mensagem de erro (texto em português, traduzido na rota) ou None."""
    tipo = CAMPOS[chave][1]
    if tipo == 'senha':
        if len(valor) < 10 or len(valor) > 128 or any(c.isspace() for c in valor):
            return 'A senha das contas de teste precisa de 10 a 128 caracteres, sem espaços.'
    elif tipo == 'chave':
        if not 20 <= len(valor) <= 400 or any(c.isspace() for c in valor):
            return 'A chave da API parece incompleta: confira e cole de novo (sem espaços).'
    elif valor not in ('0', '1'):
        return 'Valor inválido.'
    return None


def _guardar_origem():
    for chave in CAMPOS:
        if chave not in _do_ambiente:
            _do_ambiente[chave] = os.environ.get(chave)


def carregar(segredo, forcar=False):
    """Coloca no os.environ as credenciais cadastradas na tela (as do .env valem quando não há cadastro)."""
    if not forcar and time.time() - _cache['quando'] < TEMPO_CACHE:
        return
    _cache['quando'] = time.time()
    _guardar_origem()
    from models import CredencialAgente
    try:
        gravadas = {c.chave: c.valor_cifrado for c in CredencialAgente.query.all()}
    except Exception:
        return  # banco ainda sem a tabela (primeira subida)
    for chave in CAMPOS:
        valor = decifrar(gravadas[chave], segredo) if chave in gravadas else None
        if valor:
            os.environ[chave] = valor
        elif _do_ambiente.get(chave) is not None:
            os.environ[chave] = _do_ambiente[chave]
        else:
            os.environ.pop(chave, None)


def situacao(segredo):
    """Para a tela: de onde vem cada credencial — nunca o valor."""
    from models import CredencialAgente
    _guardar_origem()
    gravadas = {c.chave: c for c in CredencialAgente.query.all()}
    linhas = []
    for chave, (nome, tipo) in CAMPOS.items():
        c = gravadas.get(chave)
        legivel = c is not None and decifrar(c.valor_cifrado, segredo) is not None
        linhas.append({'chave': chave, 'nome': nome, 'tipo': tipo,
                       'origem': 'tela' if legivel else ('env' if _do_ambiente.get(chave) else None),
                       'ilegivel': c is not None and not legivel,
                       'ligado': (decifrar(c.valor_cifrado, segredo) if legivel else _do_ambiente.get(chave)) == '1',
                       'atualizado_em': c.atualizado_em if c else None, 'por': c.atualizado_por.nome if c and c.atualizado_por else None})
    return linhas
