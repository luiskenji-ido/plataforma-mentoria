# -*- coding: utf-8 -*-
"""
LOGS ESTRUTURADOS (JSON, uma linha por evento, só na saída padrão)
=================================================================
- Cada linha é um JSON: momento (UTC), nível, logger, mensagem e, numa requisição, id da requisição, método,
  caminho, status e duração. Nada vai para arquivo: quem roda o contêiner coleta a saída (CloudWatch, Loki...).
- Segredos e dados pessoais são mascarados antes de sair: senhas, tokens, chaves de API, cabeçalho Authorization,
  endereço do banco com senha e e-mails.
- Exceções saem com tipo, mensagem (mascarada) e onde aconteceram (arquivo:linha). A pilha completa (stack trace)
  só sai com LOG_TRACEBACK=1, para depuração.
Variáveis: LOG_FORMATO=json (padrão) ou texto; LOG_LEVEL=INFO (padrão).
"""

import json
import logging
import os
import re
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

MASCARA = "***"
_PADROES = [
    # chave=valor ou "chave": "valor" de campos sensíveis
    (
        re.compile(r"(?i)\b(senha|password|passwd|pwd|secret|segredo|token|api[_-]?key|chave)(\"?\s*[:=]\s*\"?)([^\s\"',;&]+)"),
        lambda m: f"{m.group(1)}{m.group(2)}{MASCARA}",
    ),
    (re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+"), lambda m: f"{m.group(1)} {MASCARA}"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})\b"), lambda m: MASCARA),
    # usuário:senha@ em endereços (banco, SMTP)
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://[^:/@\s]+:)([^@\s]+)(@)"), lambda m: f"{m.group(1)}{MASCARA}{m.group(3)}"),
    # e-mails: fica a primeira letra e o domínio
    (re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), lambda m: f"{m.group(1)}***@{m.group(2)}"),
]


def mascarar(texto):
    """Tira segredos e dados pessoais de um texto de log."""
    texto = str(texto)
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return texto


def _contexto_da_requisicao():
    try:
        from flask import g, has_request_context, request
    except ImportError:  # pragma: no cover - o Flask sempre existe na plataforma
        return {}
    if not has_request_context():
        return {}
    return {"request_id": getattr(g, "request_id", None), "metodo": request.method, "caminho": request.path}


class FormatoJson(logging.Formatter):
    def __init__(self, com_pilha=False):
        super().__init__()
        self.com_pilha = com_pilha

    def format(self, registro):
        evento = {
            "momento": datetime.fromtimestamp(registro.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensagem": mascarar(registro.getMessage()),
        }
        evento.update({k: v for k, v in _contexto_da_requisicao().items() if v is not None})
        for campo in ("status", "duracao_ms", "request_id", "metodo", "caminho", "evento"):
            valor = getattr(registro, campo, None)
            if valor is not None:
                evento[campo] = valor
        if registro.exc_info and registro.exc_info[0]:
            tipo, erro, tb = registro.exc_info
            evento["erro_tipo"] = tipo.__name__
            evento["erro"] = mascarar(erro)[:500]
            ultimo = traceback.extract_tb(tb)[-1] if tb else None
            if ultimo:
                evento["erro_onde"] = f"{os.path.basename(ultimo.filename)}:{ultimo.lineno}"
            if self.com_pilha:
                evento["pilha"] = mascarar("".join(traceback.format_exception(tipo, erro, tb)))
        return json.dumps(evento, ensure_ascii=False, default=str)


class FormatoTexto(logging.Formatter):
    """Para desenvolvimento (LOG_FORMATO=texto): legível, mas com o mesmo mascaramento."""

    def format(self, registro):
        return mascarar(super().format(registro))


def criar_formatador():
    if (os.environ.get("LOG_FORMATO") or "json").lower() == "texto":
        return FormatoTexto("%(asctime)s %(levelname)s %(name)s: %(message)s")
    return FormatoJson(com_pilha=os.environ.get("LOG_TRACEBACK") == "1")


def configurar_logs():
    """Um único destino para todos os loggers (app, werkzeug, gunicorn, sqlalchemy): a saída padrão."""
    raiz = logging.getLogger()
    for h in list(raiz.handlers):
        raiz.removeHandler(h)
    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(criar_formatador())
    raiz.addHandler(saida)
    raiz.setLevel((os.environ.get("LOG_LEVEL") or "INFO").upper())
    for nome in ("werkzeug", "gunicorn.error", "gunicorn.access"):
        lg = logging.getLogger(nome)
        lg.handlers = []
        lg.propagate = True
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # o acesso sai pelo log de requisições abaixo


# Caminhos que não geram log de acesso (sondas de saúde chamadas a cada poucos segundos)
SEM_LOG_DE_ACESSO = {"/healthz", "/readyz"}


def ligar_no_app(app):
    """id da requisição (X-Request-ID recebido do proxy ou gerado) e uma linha de log por requisição."""
    from flask import g, request

    log = logging.getLogger("acesso")

    @app.before_request
    def _inicio_da_requisicao():
        recebido = request.headers.get("X-Request-ID", "")
        g.request_id = recebido if re.fullmatch(r"[A-Za-z0-9._-]{8,64}", recebido) else uuid.uuid4().hex
        g.inicio_requisicao = time.perf_counter()

    @app.after_request
    def _fim_da_requisicao(resposta):
        resposta.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if request.path not in SEM_LOG_DE_ACESSO:
            duracao = (time.perf_counter() - getattr(g, "inicio_requisicao", time.perf_counter())) * 1000
            log.info(
                "%s %s %s",
                request.method,
                request.path,
                resposta.status_code,
                extra={
                    "status": resposta.status_code,
                    "duracao_ms": round(duracao, 1),
                    "metodo": request.method,
                    "caminho": request.path,
                    "request_id": getattr(g, "request_id", None),
                },
            )
        return resposta

    return app
