# -*- coding: utf-8 -*-
"""
CONTRASTE DO TEXTO (WCAG 2.2, critério 1.4.3) — medido no navegador, em cada tema da plataforma
================================================================================================
Para cada texto visível da página, calcula a cor real da letra e a cor real do fundo atrás dela (somando as camadas
semitransparentes e a opacidade dos pais) e a razão de contraste. Texto comum precisa de 4,5:1; texto grande (24 px, ou
18,66 px em negrito) precisa de 3:1. Texto de botão desativado e texto escondido para leitor de tela ficam de fora (a
WCAG isenta). Fundo com imagem não é medido (sem como saber a cor atrás da letra): conta como "não medido"; degradê por
cima de uma cor sólida (pauta de caderno, brilho) é medido pela cor sólida.

Usado pelo Agente UX (agentes por perfil, em todos os temas) e pelo protótipo de UX/UI (antes x depois).
Uso avulso: python agentes_funcionalidades/contraste.py http://127.0.0.1:5000 email senha [/caminho ...]
"""
import sys

TEMAS = ['claro', 'escuro', 'futurista', 'vintage']  # os mesmos de app.alterar_tema
CONTRASTE_MINIMO_TEXTO = 4.5        # WCAG 1.4.3 (AA), texto comum
CONTRASTE_MINIMO_TEXTO_GRANDE = 3.0  # WCAG 1.4.3 (AA), texto grande
TEXTO_GRANDE_PX, TEXTO_GRANDE_NEGRITO_PX = 24, 18.66
MODAIS_POR_PAGINA = 4  # abre até 4 janelas de tipos diferentes por página e mede o texto delas também

JS_CONTRASTE = """(args) => {
  const [MIN, MIN_G, G_PX, GN_PX, escopo] = args;
  const raiz = escopo ? document.querySelector(escopo) : document.body;
  if (!raiz) return {medidos: 0, falhas: [], sem_medida: 0};
  const cor = s => {
    if (!s || s === 'transparent') return [0, 0, 0, 0];
    let m = s.match(/^rgba?\\(([^)]+)\\)/);
    if (m) { const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(parseFloat); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    m = s.match(/^color\\(srgb\\s+([^)]+)\\)/);
    if (m) { const p = m[1].split(/[\\s\\/]+/).filter(Boolean).map(parseFloat); return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1]; }
    return null;
  };
  const sobre = (a, b) => { const k = a[3]; return [a[0] * k + b[0] * (1 - k), a[1] * k + b[1] * (1 - k), a[2] * k + b[2] * (1 - k), 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const razao = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = c => '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  const fundo = el => {
    const pilha = []; let opac = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e);
      opac *= parseFloat(s.opacity || '1');
      const b = cor(s.backgroundColor);
      // imagem de fundo: sem como saber a cor atrás da letra. Degradê (pauta, brilho) sobre uma cor sólida: vale a cor sólida
      if (s.backgroundImage && s.backgroundImage !== 'none' && (/url\\(/.test(s.backgroundImage) || !(b && b[3] >= 1))) return {imagem: true};
      if (b && b[3] > 0) pilha.push(b);
      if (b && b[3] >= 1) break;
    }
    let f = [255, 255, 255, 1];
    for (let i = pilha.length - 1; i >= 0; i--) f = sobre(pilha[i], f);
    return {cor: f, opac};
  };
  const nome = el => { const c = el.closest('[id]'); const cls = [...el.classList].slice(0, 2).join('.');
    return (c && c !== el ? '#' + c.id.replace(/\\d+/g, 'N') + ' ' : '') + el.tagName.toLowerCase() + (el.id ? '#' + el.id.replace(/\\d+/g, 'N') : '') + (cls ? '.' + cls : ''); };
  const falhas = new Map(); let medidos = 0, sem_medida = 0;
  const andar = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  const vistos = new Set();
  for (let n = andar.nextNode(); n; n = andar.nextNode()) {
    const texto = n.nodeValue.replace(/\\s+/g, ' ').trim();
    if (texto.length < 2 || !/[\\p{L}\\p{N}]/u.test(texto)) continue;
    const el = n.parentElement; if (!el || vistos.has(el)) continue; vistos.add(el);
    if (el.closest('script,style,noscript,template,option,.visually-hidden,.sr-only,[aria-hidden="true"],.proto-selo')) continue;
    if (el.closest('button:disabled,.btn.disabled,[disabled],fieldset:disabled')) continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    const s = getComputedStyle(el); if (s.visibility !== 'visible' || s.display === 'none') continue;
    const f = fundo(el); if (f.imagem) { sem_medida++; continue; }
    const c = cor(s.color); if (!c) { sem_medida++; continue; }
    const letra = sobre([c[0], c[1], c[2], c[3] * f.opac], f.cor);
    const px = parseFloat(s.fontSize), negrito = parseInt(s.fontWeight, 10) >= 700;
    const minimo = (px >= G_PX || (px >= GN_PX && negrito)) ? MIN_G : MIN;
    const q = razao(letra, f.cor); medidos++;
    if (q + 0.005 < minimo) {
      const chave = nome(el) + '|' + hex(letra) + '|' + hex(f.cor);
      const atual = falhas.get(chave);
      if (atual) { atual.vezes++; continue; }
      falhas.set(chave, {texto: texto.slice(0, 60), razao: Math.round(q * 100) / 100, minimo, letra: hex(letra), fundo: hex(f.cor),
                         onde: nome(el), vezes: 1});
    }
  }
  return {medidos, sem_medida, falhas: [...falhas.values()].sort((a, b) => a.razao - b.razao)};
}"""

ARGS = [CONTRASTE_MINIMO_TEXTO, CONTRASTE_MINIMO_TEXTO_GRANDE, TEXTO_GRANDE_PX, TEXTO_GRANDE_NEGRITO_PX]

# Lista os tipos de janela (modal) da página, um de cada (os repetidos por linha, como #modalBanca3, contam como um)
JS_MODAIS = """(limite) => { const vistos = new Set(), ids = [];
  document.querySelectorAll('.modal[id]').forEach(m => { const tipo = m.id.replace(/\\d+/g, 'N');
    if (!vistos.has(tipo) && ids.length < limite) { vistos.add(tipo); ids.push(m.id); } });
  return ids; }"""
JS_LIMPAR = """() => { document.querySelectorAll('.tour-balao, .tour-fundo, [class*="tour-"]').forEach(e => e.remove()); }"""


def medir_pagina(pagina, modais=MODAIS_POR_PAGINA):
    """Mede a página aberta e, depois, cada tipo de janela dela (aberta e fechada de novo). Devolve
    {'medidos', 'sem_medida', 'falhas': [{texto, razao, minimo, letra, fundo, onde, vezes, janela?}]}."""
    pagina.evaluate(JS_LIMPAR)
    total = pagina.evaluate(JS_CONTRASTE, ARGS + [None])
    for mid in (pagina.evaluate(JS_MODAIS, modais) if modais else []):
        try:
            pagina.evaluate("id => bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).show()", mid)
            pagina.wait_for_selector(f'#{mid}.show', timeout=3000)
            pagina.wait_for_timeout(250)
            r = pagina.evaluate(JS_CONTRASTE, ARGS + [f'#{mid}'])
            pagina.evaluate("id => bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide()", mid)
            pagina.wait_for_timeout(250)
        except Exception:
            continue
        total['medidos'] += r['medidos']
        total['sem_medida'] += r['sem_medida']
        total['falhas'] += [dict(f, janela='#' + mid) for f in r['falhas']]
    return total


def entrar(pagina, base, email, senha):
    pagina.goto(base + '/logout')
    pagina.goto(base + '/')
    pagina.fill('#f_email', email)
    pagina.fill('#f_senha', senha)
    pagina.click('button[type=submit]')
    pagina.wait_for_load_state('networkidle')


def auditar(pagina, base, caminhos, temas=TEMAS, ao_medir=None):
    """Mede os caminhos em cada tema (troca o tema da conta logada e volta ao tema que ela tinha). Devolve
    {tema: {caminho: resultado}}."""
    original = pagina.evaluate("() => document.documentElement.dataset.theme") or 'claro'
    saida = {}
    try:
        for tema in temas:
            pagina.goto(f'{base}/alterar-tema/{tema}')
            saida[tema] = {}
            for caminho in caminhos:
                try:
                    pagina.goto(base + caminho, wait_until='domcontentloaded', timeout=30000)
                    pagina.wait_for_timeout(200)
                    saida[tema][caminho] = medir_pagina(pagina)
                except Exception as e:
                    saida[tema][caminho] = {'medidos': 0, 'sem_medida': 0, 'falhas': [], 'erro': e.__class__.__name__}
                if ao_medir:
                    ao_medir(tema, caminho, saida[tema][caminho])
    finally:
        pagina.goto(f'{base}/alterar-tema/{original}')
    return saida


def resumo(saida):
    """{tema: (textos medidos, textos abaixo do mínimo)} — 'vezes' conta cada repetição do mesmo texto."""
    return {tema: (sum(r['medidos'] for r in pags.values()), sum(f['vezes'] for r in pags.values() for f in r['falhas']))
            for tema, pags in saida.items()}


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from playwright.sync_api import sync_playwright
    from navegador import abrir_chromium
    base, email, senha, caminhos = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:] or ['/dashboard']
    with sync_playwright() as p:
        nav = abrir_chromium(p)
        pg = nav.new_context(viewport={'width': 1366, 'height': 860}).new_page()
        entrar(pg, base, email, senha)
        res = auditar(pg, base, caminhos)
        for tema, (medidos, ruins) in resumo(res).items():
            print(f'{tema:10s} {medidos:6d} textos medidos, {ruins:5d} abaixo do mínimo')
            for caminho, r in res[tema].items():
                for f in r['falhas'][:8]:
                    print(f"   {caminho} {f.get('janela', '')} {f['razao']}:1 (mín {f['minimo']}) {f['letra']} em {f['fundo']} "
                          f"x{f['vezes']} · {f['onde']} · {f['texto']!r}")
        nav.close()
