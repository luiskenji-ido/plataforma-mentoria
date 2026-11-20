# -*- coding: utf-8 -*-
"""
SAÚDE DO PROCESSO (sondas do orquestrador de contêineres e do balanceador)
=========================================================================
- GET /healthz (liveness): o processo responde. Não toca em nada externo: se o banco cair, o contêiner NÃO deve
  ser reiniciado por isso.
- GET /readyz (readiness): o processo pode receber tráfego. Confere cada serviço de apoio registrado (banco e,
  quando configurados, Redis e armazenamento de arquivos), cada um com tempo-limite. Qualquer falha → 503, e o
  balanceador tira a réplica do ar até ela voltar. A resposta diz só o nome e o estado de cada verificação, nunca
  endereços, senhas ou detalhes do erro (esses vão para o log).
- Desligando (SIGTERM recebido pelo gunicorn): /readyz passa a responder 503 para o balanceador parar de mandar
  pedidos enquanto os que estão em andamento terminam.
"""

import logging
import time

from flask import Blueprint, jsonify

log = logging.getLogger("saude")
bp = Blueprint("saude", __name__)

_VERIFICACOES = {}
_ESTADO = {"desligando": False}


def registrar(nome, funcao):
    """funcao() levanta exceção se o serviço não está pronto."""
    _VERIFICACOES[nome] = funcao


def marcar_desligando():
    _ESTADO["desligando"] = True


def verificar_tudo():
    """{nome: 'ok' | 'falhou'} e se está tudo pronto."""
    resultado = {}
    for nome, funcao in _VERIFICACOES.items():
        inicio = time.perf_counter()
        try:
            funcao()
            resultado[nome] = "ok"
        except Exception as erro:
            resultado[nome] = "falhou"
            log.warning("verificação de prontidão '%s' falhou: %s: %s", nome, type(erro).__name__, erro,
                        extra={"duracao_ms": round((time.perf_counter() - inicio) * 1000, 1)})
    pronto = all(v == "ok" for v in resultado.values()) and not _ESTADO["desligando"]
    return resultado, pronto


@bp.route("/healthz")
def vivo():
    return jsonify(status="ok")


@bp.route("/readyz")
def pronto():
    verificacoes, ok = verificar_tudo()
    corpo = {"status": "ok" if ok else ("desligando" if _ESTADO["desligando"] else "indisponivel"), "verificacoes": verificacoes}
    return jsonify(corpo), (200 if ok else 503)


def verificar_banco(db, tempo_limite=3):
    """SELECT 1 no banco (o pool já testa a conexão antes de usar)."""
    from sqlalchemy import text

    def verificar():
        with db.engine.connect() as conexao:
            if db.engine.dialect.name == "mysql":
                conexao.execute(text(f"SET SESSION MAX_EXECUTION_TIME={int(tempo_limite * 1000)}"))
            conexao.execute(text("SELECT 1"))

    return verificar
