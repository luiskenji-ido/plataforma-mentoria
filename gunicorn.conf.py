# -*- coding: utf-8 -*-
"""
Configuração do gunicorn (servidor do contêiner). Tudo vem do ambiente; os padrões servem para 1 vCPU / 1 GB.
- PORT (8080): porta em que o contêiner escuta.
- WEB_CONCURRENCY (2) processos × GUNICORN_THREADS (4) threads.
- GUNICORN_TIMEOUT (120 s): pedido mais longo aceito (respostas das IAs podem demorar).
- GUNICORN_GRACEFUL_TIMEOUT (30 s): no SIGTERM, o gunicorn para de aceitar conexões, /readyz passa a responder 503
  e os pedidos em andamento têm este tempo para terminar; depois os processos fecham as conexões do banco e saem.
- FORWARDED_ALLOW_IPS: IPs do proxy/balanceador em que se confia para X-Forwarded-* (padrão: só local).
"""

import os

bind = f"0.0.0.0:{int(os.environ.get('PORT', '8080'))}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = 5
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
# Sistema de arquivos só de leitura: o batimento dos processos fica em memória
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None
# Limites do pedido HTTP (cabeçalhos); o tamanho do corpo é limitado pelo app (MAX_CONTENT_LENGTH)
limit_request_line = 8190
limit_request_fields = 100
# Logs: o app escreve JSON na saída padrão (logs_estruturados.py); o gunicorn não escreve arquivos
accesslog = None
errorlog = "-"
capture_output = False


def on_starting(server):
    import logs_estruturados

    logs_estruturados.configurar_logs()


def worker_int(worker):
    """SIGINT/SIGQUIT no processo: marca o desligamento para o balanceador parar de mandar pedidos."""
    _marcar_desligando()


def worker_abort(worker):
    _marcar_desligando()


def worker_exit(server, worker):
    """Processo saindo (fim do desligamento gracioso): devolve as conexões do banco."""
    try:
        from app import db, app

        with app.app_context():
            db.engine.dispose()
    except Exception as erro:  # o processo está saindo; só registra
        server.log.warning("Não foi possível fechar as conexões do banco: %s", erro)


def pre_request(worker, req):
    if getattr(worker, "alive", True) is False:
        _marcar_desligando()


def _marcar_desligando():
    try:
        import saude

        saude.marcar_desligando()
    except Exception:  # noqa: BLE001 - sem o app carregado não há o que marcar
        return
