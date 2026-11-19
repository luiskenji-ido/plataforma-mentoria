# -*- coding: utf-8 -*-
"""
PALETAS DO PROTÓTIPO — uma por tema da plataforma (claro, escuro, futurista, vintage), com contraste conferido
==============================================================================================================
Regra da skill de UX/UI: nenhuma cor de texto entra no tema sem passar pelo contraste mínimo da WCAG 2.2 contra cada
fundo em que ela é usada (4,5:1 para texto, 3:1 para bordas de campos e peças de interface). Este arquivo é a fonte:
  python prototipo_ux/paletas.py   → confere todos os pares e grava prototipo_ux/static/tokens.css
Se um par ficar abaixo do mínimo, nada é gravado e a lista dos pares ruins aparece na tela.
"""
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))

# Papéis das cores (os nomes viram variáveis --p-<papel> no CSS):
#   bg fundo da página · surface cartões e janelas · surface2 faixas internas, cabeçalho de tabela, rodapé de janela
#   line bordas discretas · field borda de campo (precisa de 3:1) · fg texto · muted texto secundário
#   accent cor de ação · on-accent texto sobre a cor de ação · accent-soft fundo suave de seleção · accent-text link e texto de ação
#   ok/warn/bad/info: <estado>-text (texto e ícone) sobre <estado>-soft (fundo da etiqueta e do aviso); <estado> é o
#   preenchimento forte (barra de progresso, botão de perigo), com on-<estado> por cima
PALETAS = {
    'claro': {
        'bg': '#f4f6f9', 'surface': '#ffffff', 'surface2': '#eef1f5', 'line': '#dde2e9', 'field': '#778191',
        'fg': '#152030', 'muted': '#4f5b6b',
        'accent': '#1f5fd6', 'on-accent': '#ffffff', 'accent-soft': '#e7eefc', 'accent-text': '#1a52b8',
        'ok': '#18794e', 'on-ok': '#ffffff', 'ok-soft': '#e3f4ea', 'ok-text': '#136840',
        'warn': '#b25e00', 'on-warn': '#ffffff', 'warn-soft': '#fdf0db', 'warn-text': '#8a4600',
        'bad': '#c0281d', 'on-bad': '#ffffff', 'bad-soft': '#fdebe9', 'bad-text': '#a3211a',
        'info': '#0a6f8f', 'on-info': '#ffffff', 'info-soft': '#e0f2f8', 'info-text': '#0a5c77',
        'sombra': '15 25 40', 'escuro': '0',
    },
    'escuro': {  # mantém o âmbar do tema escuro atual como cor de ação, com texto escuro por cima (branco no âmbar não passa)
        'bg': '#111214', 'surface': '#1a1b1f', 'surface2': '#232529', 'line': '#2e3137', 'field': '#6b717c',
        'fg': '#ededef', 'muted': '#a4a8b1',
        'accent': '#f59e0b', 'on-accent': '#1a1206', 'accent-soft': '#2e2412', 'accent-text': '#fbbf24',
        'ok': '#22c55e', 'on-ok': '#06210f', 'ok-soft': '#14281c', 'ok-text': '#4ade80',
        'warn': '#f59e0b', 'on-warn': '#1a1206', 'warn-soft': '#2e2412', 'warn-text': '#fbbf24',
        'bad': '#ef4444', 'on-bad': '#1f0505', 'bad-soft': '#311716', 'bad-text': '#fca5a5',
        'info': '#38bdf8', 'on-info': '#04151f', 'info-soft': '#0f2633', 'info-text': '#7dd3fc',
        'sombra': '0 0 0', 'escuro': '1',
    },
    'futurista': {  # azul-ardósia com ciano, como o futurista atual
        'bg': '#0b1220', 'surface': '#121b2d', 'surface2': '#1a2539', 'line': '#26344b', 'field': '#5f708b',
        'fg': '#e7eef8', 'muted': '#9eacc0',
        'accent': '#22b8f0', 'on-accent': '#03131d', 'accent-soft': '#0f2a3f', 'accent-text': '#7dd3fc',
        'ok': '#2dd4a0', 'on-ok': '#04201a', 'ok-soft': '#0f2a2a', 'ok-text': '#5eead4',
        'warn': '#f5b83d', 'on-warn': '#1d1404', 'warn-soft': '#2a2413', 'warn-text': '#fcd34d',
        'bad': '#f05d6c', 'on-bad': '#22060a', 'bad-soft': '#2c1724', 'bad-text': '#fda4af',
        'info': '#818cf8', 'on-info': '#0b0c26', 'info-soft': '#1c1f45', 'info-text': '#a5b4fc',
        'sombra': '0 0 0', 'escuro': '1',
    },
    'vintage': {  # papel e sépia, com o verde-garrafa do vintage atual
        'bg': '#f3efe6', 'surface': '#fbf8f2', 'surface2': '#ede6d8', 'line': '#dcd1bf', 'field': '#85745e',
        'fg': '#3a2e25', 'muted': '#66574a',
        'accent': '#2a5a46', 'on-accent': '#ffffff', 'accent-soft': '#e2ebe4', 'accent-text': '#24503e',
        'ok': '#2f6f3c', 'on-ok': '#ffffff', 'ok-soft': '#e4eee0', 'ok-text': '#2a6235',
        'warn': '#9a5410', 'on-warn': '#ffffff', 'warn-soft': '#f5e8d2', 'warn-text': '#80450a',
        'bad': '#a8342a', 'on-bad': '#ffffff', 'bad-soft': '#f6e2dc', 'bad-text': '#922c23',
        'info': '#2d6477', 'on-info': '#ffffff', 'info-soft': '#e1ecee', 'info-text': '#285a6b',
        'sombra': '60 45 30', 'escuro': '0',
    },
}

FUNDOS_DE_TEXTO = ('bg', 'surface', 'surface2')
# (texto, fundo, mínimo): todos os pares que as telas usam
PARES = ([(t, f, 4.5) for t in ('fg', 'muted', 'accent-text') for f in FUNDOS_DE_TEXTO + ('accent-soft',)]
         + [(t, f, 4.5) for e in ('ok', 'warn', 'bad', 'info') for t, f in ((f'{e}-text', f'{e}-soft'), (f'{e}-text', 'surface'),
                                                                               (f'{e}-text', 'bg'), (f'on-{e}', e))]
         + [('on-accent', 'accent', 4.5), ('fg', 'surface2', 4.5)]
         + [('field', f, 3.0) for f in FUNDOS_DE_TEXTO] + [('accent', f, 3.0) for f in FUNDOS_DE_TEXTO])


def _lum(h):
    h = h.lstrip('#')
    def canal(v):
        v = int(v, 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razao(a, b):
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def conferir():
    ruins = []
    for tema, p in PALETAS.items():
        for t, f, minimo in PARES:
            q = razao(p[t], p[f])
            if q < minimo:
                ruins.append(f'{tema}: {t} {p[t]} sobre {f} {p[f]} = {q:.2f}:1 (mínimo {minimo})')
    return ruins


def css():
    linhas = ['/* GERADO por prototipo_ux/paletas.py — não editar à mão: mude a paleta lá e rode de novo (o contraste é conferido) */']
    for tema, p in PALETAS.items():
        seletor = 'html[data-proto]' + ('' if tema == 'claro' else f'[data-theme="{tema}"]')
        corpo = ' '.join(f'--p-{k}: {v};' for k, v in p.items() if k not in ('sombra', 'escuro'))
        rgb = ', '.join(str(int(p['accent'].lstrip('#')[i:i + 2], 16)) for i in (0, 2, 4))
        linhas.append(f'{seletor} {{ {corpo} --p-sombra: {p["sombra"]}; --p-escuro: {p["escuro"]}; '
                      f'--bs-primary: {p["accent"]}; --bs-primary-rgb: {rgb}; --bs-link-color: {p["accent-text"]}; '
                      f'--bs-body-color: {p["fg"]}; --bs-body-bg: {p["bg"]}; --bs-border-color: {p["line"]}; '
                      f'--bs-secondary-color: {p["muted"]}; --bs-emphasis-color: {p["fg"]}; '
                      f'color-scheme: {"dark" if p["escuro"] == "1" else "light"}; }}')
    return '\n'.join(linhas) + '\n'


if __name__ == '__main__':
    ruins = conferir()
    for tema, p in PALETAS.items():
        piores = sorted((razao(p[t], p[f]), t, f) for t, f, m in PARES if m == 4.5)[:3]
        print(f'{tema:10s} pior texto: ' + ' · '.join(f'{t}/{f} {q:.2f}' for q, t, f in piores))
    if ruins:
        print('\nPares abaixo do mínimo (nada foi gravado):\n  ' + '\n  '.join(ruins))
        sys.exit(1)
    with open(os.path.join(PASTA, 'static', 'tokens.css'), 'w', encoding='utf-8') as f:
        f.write(css())
    print(f'\n{len(PARES) * len(PALETAS)} pares conferidos; static/tokens.css gravado.')
