# -*- coding: utf-8 -*-
"""
CHAMADAS A SERVIÇOS EXTERNOS: tempo-limite, novas tentativas com espera crescente e reaproveitamento de conexões
==============================================================================================================
- com_retentativas(): tenta de novo só os erros passageiros (conexão caiu, tempo esgotado, servidor ocupado),
  esperando 0,5 s, 1 s, 2 s... (com sorteio, para várias réplicas não baterem juntas), até um teto.
- sessao_http(): requests com pool de conexões, TLS verificado e novas tentativas automáticas só nos métodos que
  podem repetir sem efeito duplicado (GET, PUT, DELETE...) e nas respostas 429/502/503/504, respeitando Retry-After.
"""

import logging
import random
import time

log = logging.getLogger("resiliencia")

TENTATIVAS = 3
ESPERA_INICIAL = 0.5  # segundos
ESPERA_MAXIMA = 8.0  # segundos
STATUS_PASSAGEIROS = (429, 502, 503, 504)


def espera(tentativa, inicial=ESPERA_INICIAL, maxima=ESPERA_MAXIMA, sortear=random.random):
    """Espera antes da tentativa seguinte (1 = depois da primeira falha): exponencial com sorteio ("full jitter")."""
    teto = min(maxima, inicial * (2 ** (tentativa - 1)))
    return teto * (0.5 + sortear() / 2)


def com_retentativas(funcao, *, repetir_se, tentativas=TENTATIVAS, nome="chamada externa", dormir=time.sleep, sortear=random.random):
    """Chama funcao(); se ela levantar um erro para o qual repetir_se(erro) é verdadeiro, tenta de novo até
    'tentativas' vezes. Outros erros (ou o último) sobem para quem chamou."""
    for tentativa in range(1, tentativas + 1):
        try:
            return funcao()
        except Exception as erro:
            if tentativa >= tentativas or not repetir_se(erro):
                raise
            pausa = espera(tentativa, sortear=sortear)
            log.warning("%s falhou (%s); nova tentativa %d de %d em %.1f s", nome, type(erro).__name__, tentativa + 1, tentativas, pausa)
            dormir(pausa)
    raise AssertionError("inalcançável")  # pragma: no cover


_SESSAO = None


def sessao_http():
    """Sessão HTTP compartilhada pelo processo (pool de conexões + novas tentativas seguras)."""
    global _SESSAO
    if _SESSAO is None:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        regra = Retry(total=TENTATIVAS, connect=TENTATIVAS, read=TENTATIVAS, backoff_factor=ESPERA_INICIAL,
                      status_forcelist=STATUS_PASSAGEIROS, respect_retry_after_header=True, raise_on_status=False)
        sessao = requests.Session()
        adaptador = HTTPAdapter(max_retries=regra, pool_connections=10, pool_maxsize=20)
        sessao.mount("https://", adaptador)
        sessao.mount("http://", adaptador)
        _SESSAO = sessao
    return _SESSAO
