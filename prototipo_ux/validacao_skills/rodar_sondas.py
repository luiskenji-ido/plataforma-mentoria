# -*- coding: utf-8 -*-
"""
Roda as sondas (probes) do plugin ux-ui-audit nas mesmas telas do protótipo (5070) e do visual atual (5071),
nos temas claro e escuro, em 1440 px; a janela Agendar banca também em 390 px. Só leitura: abre páginas e mede.
Saída: prototipo_ux/validacao_skills/sondas/<versao>_<tema>_<largura>_<tela>.json (+ capturas .png)
Uso: python prototipo_ux/validacao_skills/rodar_sondas.py <pasta_dos_scripts_do_plugin>
"""
import json
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(PASTA)
sys.path.insert(0, os.path.dirname(PROTO))
sys.path.insert(0, PROTO)
from rodar_prototipo import CONTAS, SENHA_DEMO  # noqa: E402
from capturar_telas import LIMPAR  # noqa: E402

SAIDA = os.path.join(PASTA, 'sondas')
VERSOES = {'prototipo': 'http://127.0.0.1:5070', 'atual': 'http://127.0.0.1:5071'}
TEMAS = ['claro', 'escuro']
TELAS_ADMIN = [('bancas_modal', '/bancas'), ('acompanhamento', '/acompanhamento'),
               ('seguranca', '/admin/agentes-seguranca'), ('trilha_gestao', '/onboarding/trilha-tcc/gestao'),
               ('dashboard', '/dashboard')]
SONDAS = ['probe-core.js', 'probe-heuristics.js', 'probe-perception.js', 'probe-ltr.js']


def entrar(pagina, base, email):
    pagina.goto(base + '/logout')
    pagina.goto(base + '/')
    pagina.fill('#f_email', email)
    pagina.fill('#f_senha', SENHA_DEMO)
    pagina.click('button[type=submit]')
    pagina.wait_for_load_state('networkidle')


def preparar(pagina, base, caminho, tela):
    pagina.goto(base + caminho)
    pagina.wait_for_load_state('networkidle')
    pagina.evaluate(LIMPAR)
    if tela == 'bancas_modal':
        pagina.evaluate("() => bootstrap.Modal.getOrCreateInstance(document.getElementById('modalBanca0')).show()")
        pagina.wait_for_selector('#modalBanca0.show')
    pagina.wait_for_timeout(500)


def focos(pagina, n=12):
    """Aperta Tab de verdade n vezes e mede o anel de foco de cada controle (probe-focus exige tecla real)."""
    codigo = open(os.path.join(SCRIPTS, 'probe-focus.js'), encoding='utf-8').read()
    saida = []
    for _ in range(n):
        pagina.keyboard.press('Tab')
        pagina.wait_for_timeout(120)
        try:
            saida.append(json.loads(pagina.evaluate(codigo)))
        except Exception as e:  # noqa: BLE001
            saida.append({'erro': str(e)})
    return saida


def medir(pagina, nome, com_foco=True):
    resultado = {}
    for s in SONDAS:
        codigo = open(os.path.join(SCRIPTS, s), encoding='utf-8').read()
        try:
            resultado[s] = json.loads(pagina.evaluate(codigo))
        except Exception as e:  # noqa: BLE001
            resultado[s] = {'erro': str(e)}
    pagina.screenshot(path=os.path.join(SAIDA, nome + '.png'))
    if com_foco:
        resultado['probe-focus.js'] = focos(pagina)
    with open(os.path.join(SAIDA, nome + '.json'), 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
    print('  ok', nome, flush=True)


def rodar():
    from playwright.sync_api import sync_playwright
    from navegador import abrir_chromium
    os.makedirs(SAIDA, exist_ok=True)
    with sync_playwright() as p:
        nav = abrir_chromium(p)
        for versao, base in VERSOES.items():
            ctx = nav.new_context(viewport={'width': 1440, 'height': 900}, locale='pt-BR')
            pg = ctx.new_page()
            entrar(pg, base, CONTAS[0][0])
            for tema in TEMAS:
                pg.goto(f'{base}/alterar-tema/{tema}')
                for tela, caminho in TELAS_ADMIN:
                    preparar(pg, base, caminho, tela)
                    medir(pg, f'{versao}_{tema}_1440_{tela}')
            pg.goto(f'{base}/alterar-tema/claro')
            entrar(pg, base, CONTAS[1][0])
            for tema in TEMAS:
                pg.goto(f'{base}/alterar-tema/{tema}')
                preparar(pg, base, '/meus-cursos/7', 'sala')
                medir(pg, f'{versao}_{tema}_1440_sala_estudo')
            pg.goto(f'{base}/alterar-tema/claro')
            ctx.close()
            ctx = nav.new_context(viewport={'width': 390, 'height': 844}, locale='pt-BR', device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
            pg = ctx.new_page()
            entrar(pg, base, CONTAS[0][0])
            for tema in TEMAS:
                pg.goto(f'{base}/alterar-tema/{tema}')
                preparar(pg, base, '/bancas', 'bancas_modal')
                medir(pg, f'{versao}_{tema}_390_bancas_modal')
            pg.goto(f'{base}/alterar-tema/claro')
            ctx.close()
        nav.close()


if __name__ == '__main__':
    SCRIPTS = sys.argv[1]
    rodar()
