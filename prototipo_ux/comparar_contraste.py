# -*- coding: utf-8 -*-
"""
Mede o contraste do texto (WCAG 2.2, 4,5:1 e 3:1) nos 4 temas, nas mesmas telas, no visual ATUAL (porta 5071) e no
PROTÓTIPO (porta 5070). Os dois servidores do rodar_prototipo.py precisam estar no ar.
Uso: python prototipo_ux/comparar_contraste.py [--so-prototipo] [--rotulo prototipo_v2]  → prototipo_ux/capturas/contraste.json e o resumo na tela
"""
import os
import sys
import json

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA)
sys.path.insert(0, PASTA)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'agentes_funcionalidades'))
from rodar_prototipo import CONTAS, SENHA_DEMO  # noqa: E402
import contraste  # noqa: E402

VERSOES = {'atual': 'http://127.0.0.1:5071', 'prototipo': 'http://127.0.0.1:5070'}
TELAS = ['/dashboard', '/admin/turmas', '/bancas', '/bancas/avaliadores', '/acompanhamento', '/projetos', '/sessoes',
         '/reunioes', '/avaliacoes', '/demandas', '/admin/usuarios', '/admin/grupos', '/admin/notas', '/admin/frequencia',
         '/admin/solicitacoes', '/biblioteca', '/onboarding/trilha-tcc/gestao', '/admin/cursos/3/conteudo',
         '/admin/agentes-seguranca', '/admin/agentes-funcionalidades', '/admin/parametros-regras', '/admin/identidade',
         '/certificados', '/indicadores-voluntariado', '/atividades-extras', '/ocorrencias', '/desistencias']
TELAS_ALUNO = ['/dashboard', '/meus-cursos/7', '/acompanhamento', '/projetos']
SAIDA = os.path.join(PASTA, 'capturas', 'contraste.json')


def medir(versoes):
    from playwright.sync_api import sync_playwright
    from navegador import abrir_chromium
    resultado = {}
    with sync_playwright() as p:
        nav = abrir_chromium(p)
        for versao in versoes:
            base = VERSOES[versao]
            pg = nav.new_context(viewport={'width': 1366, 'height': 860}, locale='pt-BR').new_page()
            resultado[versao] = {}
            for (email, _, perfil), telas in ((CONTAS[0], TELAS), (CONTAS[1], TELAS_ALUNO)):
                contraste.entrar(pg, base, email, SENHA_DEMO)
                r = contraste.auditar(pg, base, telas, ao_medir=lambda t, c, x: print(
                    f"  {versao:9s} {perfil:13s} {t:9s} {c:34s} {sum(f['vezes'] for f in x['falhas']):4d} abaixo de {x['medidos']}", flush=True))
                for tema, pags in r.items():
                    for caminho, medida in pags.items():
                        resultado[versao].setdefault(tema, {})[f'{perfil}:{caminho}'] = medida
            pg.context.close()
        nav.close()
    return resultado


if __name__ == '__main__':
    versoes = ['prototipo'] if '--so-prototipo' in sys.argv else list(VERSOES)
    rotulo = sys.argv[sys.argv.index('--rotulo') + 1] if '--rotulo' in sys.argv else 'prototipo'
    res = medir(versoes)
    if 'prototipo' in res:
        res[rotulo] = res.pop('prototipo')
    anterior = {}
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding='utf-8') as f:
            anterior = json.load(f)
    anterior.update(res)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(anterior, f, ensure_ascii=False, indent=1)
    for versao in anterior:
        print(versao)
        for tema, (medidos, ruins) in contraste.resumo(anterior[versao]).items():
            print(f'   {tema:10s} {medidos:6d} textos medidos · {ruins:5d} abaixo do mínimo ({100 * ruins / max(medidos, 1):.1f}%)')
