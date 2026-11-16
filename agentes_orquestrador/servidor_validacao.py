# -*- coding: utf-8 -*-
"""Instância temporária da plataforma para a validação: python servidor_validacao.py <pasta da cópia> <porta>.
Roda o código CORRIGIDO da cópia com a CÓPIA do banco (instance/mentoria.db da cópia), só em 127.0.0.1."""
import os
import sys

raiz, porta = os.path.abspath(sys.argv[1]), int(sys.argv[2])
os.chdir(raiz)
sys.path.insert(0, raiz)
import app as modulo  # noqa: E402  (o próprio app.py da cópia)

modulo.app.run(host='127.0.0.1', port=porta, debug=False, use_reloader=False, threaded=True)
