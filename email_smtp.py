# -*- coding: utf-8 -*-
"""
ENVIO DE E-MAIL POR SMTP (um só lugar para os avisos e para os convites de reunião)
==================================================================================
- STARTTLS com certificado VERIFICADO (contexto padrão do sistema). Antes, smtp.starttls() sem contexto cifrava
  a conexão mas aceitava qualquer certificado.
- Tempo-limite em cada conexão e novas tentativas com espera crescente só nas falhas de conexão (o servidor
  não chegou a aceitar a mensagem). Recusa de senha ou de destinatário não se repete.
Variáveis: MAIL_SERVER, MAIL_PORT (587), MAIL_USE_TLS (1), MAIL_USERNAME, MAIL_PASSWORD.
"""

import os
import smtplib
import socket
import ssl

import resiliencia

TEMPO_LIMITE = 20  # segundos por conexão
ERROS_PASSAGEIROS = (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, ConnectionError)


def configurado():
    return bool(os.environ.get("MAIL_SERVER") and os.environ.get("MAIL_REMETENTE"))


def _uma_tentativa(mensagem, tempo_limite, fabrica_smtp):
    with fabrica_smtp(os.environ["MAIL_SERVER"], int(os.environ.get("MAIL_PORT", 587)), timeout=tempo_limite) as smtp:
        if os.environ.get("MAIL_USE_TLS", "1") != "0":
            smtp.starttls(context=ssl.create_default_context())
        if os.environ.get("MAIL_USERNAME"):
            smtp.login(os.environ["MAIL_USERNAME"], os.environ.get("MAIL_PASSWORD", ""))
        smtp.send_message(mensagem)


def enviar(mensagem, tempo_limite=TEMPO_LIMITE, fabrica_smtp=smtplib.SMTP, dormir=None):
    """Envia a mensagem (email.message.EmailMessage). Levanta a exceção se todas as tentativas falharem."""
    extra = {"dormir": dormir} if dormir else {}
    resiliencia.com_retentativas(lambda: _uma_tentativa(mensagem, tempo_limite, fabrica_smtp),
                                 repetir_se=lambda erro: isinstance(erro, ERROS_PASSAGEIROS), nome="envio de e-mail (SMTP)", **extra)
