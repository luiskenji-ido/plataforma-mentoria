# -*- coding: utf-8 -*-
"""
CLIENTE DO SERVIÇO PRIVADO DE BACKUP (LK-Plataforma-Mentoria/mentoria-backup)
=============================================================================
Ligado por BACKUP_SERVICO_URL (ex.: https://backup.mentoria.interno:8443, pelo enlace privado entre os hosts).
Sem a variável, a plataforma continua usando o backup local (backup_servico.py), como antes.

- pedir_backup(): backup prévio antes de uma ação do DBA ou dos agentes. POST /api/v1/backups com Idempotency-Key
  (repetido até 2 vezes só em erro de conexão) e depois GET /api/v1/backups/<id> a cada 5 s até Concluído/Verificado
  ou Falha, por até BACKUP_SERVICO_PRAZO segundos. Fora do ar, ocupado (409), falha ou prazo → ErroServicoBackup:
  quem chama NÃO faz a ação (mesma regra de sempre: sem backup validado, nada é alterado).
- saude(): indicadores para as telas (GET /api/v1/saude), com tempo-limite de 2 s e cache de 60 s; None se não responder.

Variáveis: BACKUP_SERVICO_URL, BACKUP_SERVICO_TOKEN (gerado no serviço: flask --app servico tokens gerar),
BACKUP_SERVICO_CA (certificado da CA interna, para conferir o TLS), BACKUP_SERVICO_PRAZO (1800).
Agendamento: BACKUP_AGENDADOR=monolito (padrão) ou servico. Com 'servico' a plataforma não roda backups agendados
em nenhum dos três lugares (requisições, thread do 'python app.py' e worker das tarefas).
"""

import logging
import os
import time
import uuid
from datetime import datetime

log = logging.getLogger("cliente_backup")

TEMPO_CONEXAO = 3
TEMPO_LEITURA = 10
TEMPO_SAUDE = 2
CACHE_SAUDE = 60
INTERVALO_CONSULTA = 5
TENTATIVAS_POST = 3  # 1 + 2 novas tentativas, só em erro de conexão
STATUS_OK = ("Concluído", "Verificado", "Sucesso")

_cache = {"quando": 0.0, "valor": None}


class ErroServicoBackup(RuntimeError):
    pass


def url_base():
    return (os.environ.get("BACKUP_SERVICO_URL") or "").rstrip("/")


def configurado():
    return bool(url_base())


def agendador_no_monolito():
    """False quando os backups agendados passaram para o serviço (BACKUP_AGENDADOR=servico)."""
    return (os.environ.get("BACKUP_AGENDADOR") or "monolito").strip().lower() != "servico"


def _sessao():
    import requests

    sessao = requests.Session()
    sessao.headers["Authorization"] = f"Bearer {os.environ.get('BACKUP_SERVICO_TOKEN', '')}"
    sessao.verify = os.environ.get("BACKUP_SERVICO_CA") or True
    return sessao


def pedir_backup(motivo, solicitante=None, pasta="pre_manutencao", sessao=None, dormir=time.sleep, relogio=time.monotonic):
    """Pede o backup e espera terminar. Devolve o JSON da execução (status Concluído/Verificado)."""
    import requests

    sessao = sessao or _sessao()
    prazo = int(os.environ.get("BACKUP_SERVICO_PRAZO") or 1800)
    chave = f"mentoria-{uuid.uuid4().hex}"
    corpo = {"motivo": motivo, "pasta": pasta}
    if solicitante is not None:
        corpo["solicitante"] = {"id": getattr(solicitante, "id", None), "nome": getattr(solicitante, "nome", str(solicitante))}
    resposta = None
    for tentativa in range(1, TENTATIVAS_POST + 1):
        try:
            resposta = sessao.post(
                f"{url_base()}/api/v1/backups", json=corpo, headers={"Idempotency-Key": chave}, timeout=(TEMPO_CONEXAO, TEMPO_LEITURA)
            )
            break
        except requests.ConnectionError as erro:
            if tentativa == TENTATIVAS_POST:
                raise ErroServicoBackup(f"serviço de backup inacessível: {type(erro).__name__}") from erro
            dormir(2 * tentativa)
        except requests.RequestException as erro:
            raise ErroServicoBackup(f"serviço de backup não respondeu: {type(erro).__name__}") from erro
    if resposta.status_code == 409:
        raise ErroServicoBackup("o serviço de backup está ocupado com outro backup ou restauração; tente de novo depois")
    if resposta.status_code not in (200, 202):
        raise ErroServicoBackup(f"o serviço de backup recusou o pedido (HTTP {resposta.status_code})")
    execucao = resposta.json()
    fim = relogio() + prazo
    while execucao.get("status") == "Em andamento":
        if relogio() >= fim:
            raise ErroServicoBackup(f"o backup {execucao.get('id')} não terminou em {prazo} s")
        dormir(INTERVALO_CONSULTA)
        try:
            consulta = sessao.get(f"{url_base()}/api/v1/backups/{execucao['id']}", timeout=(TEMPO_CONEXAO, TEMPO_LEITURA))
            if consulta.status_code == 200:
                execucao = consulta.json()
        except requests.RequestException as erro:  # consulta é idempotente: segue tentando até o prazo
            log.warning("consulta do backup %s falhou (%s); tentando de novo", execucao.get("id"), type(erro).__name__)
    if execucao.get("status") not in STATUS_OK:
        raise ErroServicoBackup(execucao.get("detalhes") or f"backup terminou com status {execucao.get('status')}")
    return execucao


def _data(valor):
    try:
        return datetime.fromisoformat(valor) if valor else None
    except (TypeError, ValueError):
        return None


def saude(sessao=None, relogio=time.monotonic):
    """Indicadores do serviço no mesmo formato de backup_servico.saude() (mais 'ultimo_verificado'), ou None."""
    if not configurado():
        return None
    if _cache["valor"] is not None and relogio() - _cache["quando"] < CACHE_SAUDE:
        return _cache["valor"]
    try:
        resposta = (sessao or _sessao()).get(f"{url_base()}/api/v1/saude", timeout=(TEMPO_SAUDE, TEMPO_SAUDE))
        if resposta.status_code != 200:
            log.warning("serviço de backup respondeu HTTP %s em /api/v1/saude", resposta.status_code)
            return None
        dados = resposta.json()
    except Exception as erro:
        log.warning("serviço de backup inacessível para os indicadores: %s", type(erro).__name__)
        return None
    for chave in ("ultimo", "ultimo_verificado", "proximo"):
        dados[chave] = _data(dados.get(chave))
    _cache.update(quando=relogio(), valor=dados)
    return dados


def esquecer_cache():
    _cache.update(quando=0.0, valor=None)
