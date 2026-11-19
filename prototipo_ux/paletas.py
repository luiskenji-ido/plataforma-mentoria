# -*- coding: utf-8 -*-
"""As paletas foram aprovadas e foram para produção: tema_plataforma.py (na raiz do projeto). Este arquivo só repassa,
com o seletor do protótipo (html[data-proto]), para o rodar_prototipo.py continuar funcionando com uma fonte só."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tema_plataforma as _tema  # noqa: E402

PALETAS, PARES, razao, conferir = _tema.PALETAS, _tema.PARES, _tema.razao, _tema.conferir


def css():
    return _tema.css('html[data-proto]')
