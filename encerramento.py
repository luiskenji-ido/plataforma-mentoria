# -*- coding: utf-8 -*-
"""
ENCERRAMENTO SEM PERDER RESPOSTAS (gunicorn.conf.py › on_exit)
=============================================================
O gunicorn pode terminar de escrever uma resposta grande (vídeo, gravação, backup) bem antes de o cliente lê-la: os
bytes ficam nos buffers do kernel, do lado do servidor e do lado do cliente. No SIGTERM, os workers saem e, quando o
último processo do contêiner termina, a rede do contêiner é destruída e as conexões ainda abertas recebem um reset
(RST). Ao receber o RST, o kernel do cliente descarta até o que já tinha chegado e ainda não foi lido: o download
termina cortado, mesmo com a resposta inteira já enviada pelo app.

esperar_conexoes() segura o processo principal até não sobrar conexão aberta na porta do app, isto é, até cada cliente
ler a resposta e fechar a conexão (do lado do servidor ela passa a TIME_WAIT ou some), ou até o prazo. Lê
/proc/net/tcp e /proc/net/tcp6 (Linux); fora do Linux não espera nada.
"""

import logging
import time

log = logging.getLogger("gunicorn.error")

ARQUIVOS = ("/proc/net/tcp", "/proc/net/tcp6")
# Estados do TCP no /proc/net/tcp em que o cliente ainda não terminou de receber: ESTABLISHED, FIN_WAIT1, FIN_WAIT2,
# CLOSE_WAIT, LAST_ACK e CLOSING. LISTEN (0A), TIME_WAIT (06) e CLOSE (07) não seguram o encerramento.
ESTADOS_ABERTOS = {"01", "04", "05", "08", "09", "0B"}


def conexoes_abertas(linhas, porta):
    """(conexões ainda abertas na porta local 'porta', bytes ainda não confirmados pelo cliente).
    'linhas' são as linhas de /proc/net/tcp(6), com ou sem o cabeçalho."""
    conexoes = pendentes = 0
    for linha in linhas:
        campos = linha.split()
        if len(campos) < 5 or ":" not in campos[1] or ":" not in campos[4]:
            continue
        try:
            porta_local = int(campos[1].rsplit(":", 1)[1], 16)
            fila_envio = int(campos[4].split(":", 1)[0], 16)
        except ValueError:
            continue  # cabeçalho
        if porta_local == porta and campos[3] in ESTADOS_ABERTOS:
            conexoes += 1
            pendentes += fila_envio
    return conexoes, pendentes


def _ler_conexoes():
    linhas = []
    for caminho in ARQUIVOS:
        try:
            with open(caminho, encoding="ascii") as arquivo:
                linhas.extend(arquivo.readlines())
        except OSError:
            pass
    return linhas


def esperar_conexoes(porta, prazo, ler=_ler_conexoes, relogio=time.monotonic, dormir=time.sleep, intervalo=0.1):
    """Espera até não haver conexão aberta na porta, por no máximo 'prazo' segundos.
    Devolve quantas conexões ainda estavam abertas ao desistir (0 = todos os clientes terminaram)."""
    fim = relogio() + max(prazo, 0)
    conexoes, pendentes = conexoes_abertas(ler(), porta)
    if conexoes:
        log.info("aguardando %d conexão(ões) terminar(em) de receber a resposta antes de sair (%d byte(s) no envio)", conexoes, pendentes)
    while conexoes and relogio() < fim:
        dormir(intervalo)
        conexoes, pendentes = conexoes_abertas(ler(), porta)
    if conexoes:
        log.warning("prazo de encerramento esgotado com %d conexão(ões) ainda abertas", conexoes)
    return conexoes
