# -*- coding: utf-8 -*-
"""
ONDE O ORQUESTRADOR ESTÁ RODANDO E O QUE ELE CONSEGUE FAZER AQUI
================================================================
Computador, PythonAnywhere, Azure (App Service) ou GCP (App Engine / Cloud Run / Compute Engine). Cada ambiente tem
limites diferentes: precisa ser um repositório Git gravável para corrigir e fazer commit, ter o Chromium para os agentes
Fim a Fim e permitir processos em segundo plano para a validação. A tela mostra tudo isso antes de começar.
"""
import glob
import os
import shutil
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def nome():
    if os.environ.get('PYTHONANYWHERE_DOMAIN') or os.environ.get('PYTHONANYWHERE_SITE'):
        return 'PythonAnywhere'
    if os.environ.get('WEBSITE_SITE_NAME') or os.environ.get('WEBSITE_INSTANCE_ID'):
        return 'Azure'
    if os.environ.get('K_SERVICE') or os.environ.get('GAE_SERVICE') or os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCE_METADATA_HOST'):
        return 'GCP'
    return 'Computador'


def _git(*args, cwd=RAIZ, tempo=20):
    try:
        r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, timeout=tempo,
                           encoding='utf-8', errors='replace')
        return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, '', str(e)


def _chromium():
    try:
        import importlib.util
        if importlib.util.find_spec('playwright') is None:
            return False
        import sys
        if RAIZ not in sys.path:
            sys.path.insert(0, RAIZ)
        from navegador import chromium_do_sistema
        if chromium_do_sistema():
            return True
        pastas = [os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or '', os.path.expanduser('~/.cache/ms-playwright'),
                  os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')]
        return any(glob.glob(os.path.join(p, 'chromium*')) for p in pastas if p)
    except Exception:
        return False


def capacidades():
    """O que dá para fazer aqui: cada item tem ok (bool) e uma explicação curta."""
    onde = nome()
    tem_git = shutil.which('git') is not None
    codigo, _, _ = _git('rev-parse', '--is-inside-work-tree') if tem_git else (1, '', '')
    repositorio = tem_git and codigo == 0
    gravavel = repositorio and os.access(os.path.join(RAIZ, '.git'), os.W_OK)
    _, remoto, _ = _git('remote', 'get-url', 'origin') if repositorio else (1, '', '')
    _, ramo, _ = _git('rev-parse', '--abbrev-ref', 'HEAD') if repositorio else (1, '', '')
    efemero = onde == 'GCP' and bool(os.environ.get('K_SERVICE') or os.environ.get('GAE_SERVICE'))
    chromium = _chromium()
    itens = {
        'git': {'ok': repositorio and gravavel, 'texto': f"Repositório Git gravável (ramo {ramo})" if repositorio and gravavel
                else 'Sem repositório Git gravável: o código daqui não pode ser corrigido nem ir para commit.'},
        'push': {'ok': bool(remoto), 'texto': f"Push para {remoto}" if remoto else 'Sem remoto "origin": o push não é possível.'},
        'segundo_plano': {'ok': not efemero, 'texto': 'Processos em segundo plano permitidos' if not efemero
                          else 'Cloud Run / App Engine encerram processos fora da requisição: a validação não roda aqui.'},
        'persistente': {'ok': not efemero, 'texto': 'Disco persistente' if not efemero
                        else 'Disco temporário: alterações somem a cada nova instância.'},
        'fim_a_fim': {'ok': chromium, 'texto': 'Chromium disponível para os agentes Fim a Fim' if chromium
                      else 'Sem Chromium/Playwright: os agentes Fim a Fim não rodam aqui (no PythonAnywhere exige conta paga).'},
    }
    pode_corrigir = itens['git']['ok'] and itens['segundo_plano']['ok'] and itens['persistente']['ok']
    return {'nome': onde, 'ramo': ramo, 'remoto': remoto, 'itens': itens, 'pode_corrigir': pode_corrigir,
            'pode_validar_tudo': pode_corrigir and chromium, 'pode_push': pode_corrigir and bool(remoto)}


def recarregar_aplicacao():
    """Depois do commit, faz o site usar o código novo. Devolve (ok, mensagem)."""
    comando = os.environ.get('ORQUESTRADOR_COMANDO_RECARREGAR', '').strip()
    if comando:
        r = subprocess.run(comando, shell=True, cwd=RAIZ, capture_output=True, text=True, timeout=120)  # nosec: comando definido pelo administrador no .env
        return r.returncode == 0, f"Comando de recarga executado ({r.returncode})."
    onde = nome()
    if onde == 'PythonAnywhere':
        usuario = (os.environ.get('USER') or os.path.basename(os.path.expanduser('~'))).lower()
        candidatos = glob.glob('/var/www/*_wsgi.py')  # ex.: /var/www/usuario_pythonanywhere_com_wsgi.py
        alvo = next((c for c in candidatos if usuario and os.path.basename(c).lower().startswith(usuario)), candidatos[0] if candidatos else None)
        if alvo:
            os.utime(alvo, None)  # o PythonAnywhere recarrega o site quando o arquivo WSGI muda
            return True, 'Site recarregado no PythonAnywhere (arquivo WSGI atualizado).'
        return False, 'Arquivo WSGI não encontrado: clique em Reload na aba Web do PythonAnywhere.'
    if onde in ('Azure', 'GCP'):
        return False, f'No {onde}, reinicie o serviço (ou defina ORQUESTRADOR_COMANDO_RECARREGAR no .env).'
    return False, 'No computador, reinicie o servidor (python app.py) para usar o código novo.'
