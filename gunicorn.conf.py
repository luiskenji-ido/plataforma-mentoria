# -*- coding: utf-8 -*-
"""
Configuração do gunicorn (servidor do contêiner). Tudo vem do ambiente; os padrões servem para 1 vCPU / 1 GB.
- PORT (8080): porta em que o contêiner escuta.
- WEB_CONCURRENCY (2) processos × GUNICORN_THREADS (4) threads.
- GUNICORN_TIMEOUT (120 s): pedido mais longo aceito (respostas das IAs podem demorar).
- GUNICORN_GRACEFUL_TIMEOUT (30 s): no SIGTERM, o gunicorn para de aceitar conexões, /readyz passa a responder 503
  e os pedidos em andamento têm este tempo para terminar; depois os processos fecham as conexões do banco e saem. O
  processo principal ainda espera até GUNICORN_PRAZO_ENTREGA (8 s) os clientes terminarem de receber as respostas
  (encerramento.py).
- FORWARDED_ALLOW_IPS: IPs do proxy/balanceador em que se confia para X-Forwarded-* (padrão: só local).
"""

import os

import gunicorn.http.wsgi as _wsgi_gunicorn

# Cabeçalho Server: o gunicorn escreve o dele ("gunicorn") antes dos cabeçalhos do app, e o navegador lê o primeiro.
# Com o nome da plataforma aqui, a resposta sai com um único "Server: Mentoria", inclusive nas páginas de erro do
# próprio gunicorn; seguranca_web.py não repete o cabeçalho quando roda sob o gunicorn.
_wsgi_gunicorn.SERVER = "Mentoria"

bind = f"0.0.0.0:{int(os.environ.get('PORT', '8080'))}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
# Depois dos workers, tempo máximo para os clientes terminarem de receber as respostas já escritas. graceful_timeout + este prazo
# precisa caber no tempo que o orquestrador espera antes do SIGKILL (stop_grace_period: 40 s no docker-compose.yml).
prazo_entrega = int(os.environ.get("GUNICORN_PRAZO_ENTREGA", "8"))
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


def on_exit(server):
    """Processo principal saindo: espera os clientes terminarem de receber as respostas já escritas (encerramento.py)."""
    import encerramento

    encerramento.esperar_conexoes(int(os.environ.get("PORT", "8080")), prazo_entrega)


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
