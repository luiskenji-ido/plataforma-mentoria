# -*- coding: utf-8 -*-
"""
ABERTURA DO NAVEGADOR DOS AGENTES (Playwright)
==============================================
Um único lugar decide qual Chromium os agentes e a geração de PDFs usam:
  - no computador: o Chromium que o próprio Playwright instala (`playwright install chromium`);
  - no PythonAnywhere (conta paga): o Chromium do sistema em /usr/bin/chromium, com as opções que eles exigem —
    lá o `playwright install` não funciona (https://help.pythonanywhere.com/pages/Playwright/);
  - em qualquer outro servidor: defina PLAYWRIGHT_CHROMIUM com o caminho do navegador.
"""
import os

CHROMIUM_PYTHONANYWHERE = "/usr/bin/chromium"
ARGS_SERVIDOR = ["--disable-gpu", "--no-sandbox", "--headless"]


def chromium_do_sistema():
    """Caminho do Chromium do servidor, ou None para usar o do Playwright."""
    caminho = os.environ.get("PLAYWRIGHT_CHROMIUM", "").strip()
    if caminho:
        return caminho
    no_pythonanywhere = bool(os.environ.get("PYTHONANYWHERE_DOMAIN") or os.environ.get("PYTHONANYWHERE_SITE"))
    if no_pythonanywhere and os.path.exists(CHROMIUM_PYTHONANYWHERE):
        return CHROMIUM_PYTHONANYWHERE
    return None


def abrir_chromium(playwright, **opcoes):
    """Equivale a playwright.chromium.launch(**opcoes), trocando para o Chromium do servidor quando houver."""
    caminho = chromium_do_sistema()
    if caminho:
        opcoes["executable_path"] = caminho
        opcoes["headless"] = True  # servidor não tem tela
        opcoes["args"] = list(dict.fromkeys(list(opcoes.get("args") or []) + ARGS_SERVIDOR))
    return playwright.chromium.launch(**opcoes)
