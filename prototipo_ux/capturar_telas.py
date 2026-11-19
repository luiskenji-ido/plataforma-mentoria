# -*- coding: utf-8 -*-
"""
Tira as capturas de ANTES (visual atual, porta 5071) e DEPOIS (protótipo, porta 5070) das mesmas telas, com os mesmos
dados, EM CADA TEMA (claro, escuro, futurista, vintage), para o documento de proposta de UX/UI.
Os dois servidores do rodar_prototipo.py precisam estar no ar.
Uso: python prototipo_ux/capturar_telas.py   → prototipo_ux/capturas/<tela>_<tema>_antes.png e _depois.png
"""
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(PASTA))
sys.path.insert(0, PASTA)
from rodar_prototipo import CONTAS, SENHA_DEMO  # noqa: E402

SAIDA = os.path.join(PASTA, 'capturas')
VERSOES = {'antes': 'http://127.0.0.1:5071', 'depois': 'http://127.0.0.1:5070'}
TEMAS = ['claro', 'escuro', 'futurista', 'vintage']
# (nome, caminho) das telas do administrador; a janela de agendar banca e a sala de estudo do aluno vêm à parte
TELAS = [('painel', '/dashboard'), ('bancas', '/bancas'), ('acompanhamento', '/acompanhamento'),
         ('seguranca', '/admin/agentes-seguranca'), ('trilha_gestao', '/onboarding/trilha-tcc/gestao'),
         ('conteudo_curso', '/admin/cursos/3/conteudo'), ('hub', '/admin/turmas')]
LIMPAR = """() => {
  document.querySelectorAll('.modal.show').forEach(m => { try { bootstrap.Modal.getOrCreateInstance(m).hide(); } catch (e) {} m.classList.remove('show'); m.style.display = 'none'; });
  document.querySelectorAll('.modal-backdrop, .tour-balao, .tour-fundo, [class*="tour-"]').forEach(e => e.remove());
  document.body.classList.remove('modal-open'); document.body.style.overflow = ''; document.body.style.paddingRight = '';
}"""


def entrar(pagina, base, email):
    pagina.goto(base + '/logout')
    pagina.goto(base + '/')
    pagina.fill('#f_email', email)
    pagina.fill('#f_senha', SENHA_DEMO)
    pagina.click('button[type=submit]')
    pagina.wait_for_load_state('networkidle')


def foto(pagina, nome, versao):
    pagina.wait_for_timeout(600)
    pagina.screenshot(path=os.path.join(SAIDA, f'{nome}_{versao}.png'))


def abrir(pagina, base, caminho, nome, versao):
    pagina.goto(base + caminho)
    pagina.wait_for_load_state('networkidle')
    pagina.evaluate(LIMPAR)
    foto(pagina, nome, versao)


def abrir_banca(pagina, base):
    pagina.goto(base + '/bancas')
    pagina.wait_for_load_state('networkidle')
    pagina.evaluate(LIMPAR)
    pagina.evaluate("() => bootstrap.Modal.getOrCreateInstance(document.getElementById('modalBanca0')).show()")
    pagina.wait_for_selector('#modalBanca0.show')
    # um avaliador escolhido, para mostrar o campo preenchido nas duas versões
    pagina.evaluate("() => { const s = document.getElementById('bAval0'); if (s && s.options.length) { s.options[0].selected = true; s.dispatchEvent(new Event('change')); "
                    "const b = document.querySelector('[data-proto-busca]'); if (b) b.dispatchEvent(new Event('input')); } }")


def capturar():
    from playwright.sync_api import sync_playwright
    from navegador import abrir_chromium
    os.makedirs(SAIDA, exist_ok=True)
    with sync_playwright() as p:
        navegador = abrir_chromium(p)
        for versao, base in VERSOES.items():
            contexto = navegador.new_context(viewport={'width': 1440, 'height': 900}, locale='pt-BR')
            pagina = contexto.new_page()
            entrar(pagina, base, CONTAS[0][0])
            for tema in TEMAS:
                pagina.goto(f'{base}/alterar-tema/{tema}')
                for nome, caminho in TELAS:
                    abrir(pagina, base, caminho, f'{nome}_{tema}', versao)
                abrir_banca(pagina, base)
                foto(pagina, f'banca_modal_{tema}', versao)
                print(f'  {versao} {tema}: ok', flush=True)
            pagina.goto(f'{base}/alterar-tema/claro')
            entrar(pagina, base, CONTAS[1][0])
            for tema in TEMAS:
                pagina.goto(f'{base}/alterar-tema/{tema}')
                abrir(pagina, base, '/meus-cursos/7', f'sala_estudo_{tema}', versao)
            pagina.goto(f'{base}/alterar-tema/claro')
            contexto.close()
            # celular: a janela de agendar banca em 390 px, no tema claro e no escuro
            contexto = navegador.new_context(viewport={'width': 390, 'height': 844}, locale='pt-BR', device_scale_factor=2)
            pagina = contexto.new_page()
            entrar(pagina, base, CONTAS[0][0])
            for tema in ('claro', 'escuro'):
                pagina.goto(f'{base}/alterar-tema/{tema}')
                abrir_banca(pagina, base)
                foto(pagina, f'banca_celular_{tema}', versao)
            pagina.goto(f'{base}/alterar-tema/claro')
            contexto.close()
        navegador.close()
    print('Capturas em', SAIDA)


if __name__ == '__main__':
    capturar()
