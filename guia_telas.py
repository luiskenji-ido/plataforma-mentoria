# -*- coding: utf-8 -*-
"""
GUIA DAS TELAS — o "como fazer" de cada página, para o Assistente da Plataforma explicar passo a passo
=====================================================================================================
Montado sozinho a partir do que já existe no código (nada para manter em dobro):
- o menu (templates/base.html): onde cada tela fica, por exemplo "Projetos e TCC › Projetos (TCC)";
- os passos do Tour guiado (templates/_tours.html e o rodarTour() de cada página), em português;
- os perfis que acessam cada tela (perfis_acesso.MODULOS e MODULOS_POR_BASE);
- o endereço da tela (url_map do Flask).

Entra na fonte "Conhecimento dos Agentes gerentes" (base_conhecimento.sincronizar_gerentes), como seções
"Guia das telas › <tela>". Quando o Tour ou o menu mudam, o guia muda junto na próxima sincronização.
Roda dentro de um app_context.
"""
import ast
import os
import re

PASTA = os.path.dirname(os.path.abspath(__file__))
_TEXTO = re.compile(r"""\b(tt?)\(\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*\)""")


def _ler(nome):
    with open(os.path.join(PASTA, nome), encoding='utf-8') as f:
        return f.read()


def _traduzir(funcao, literal):
    """t('chave') ou tt('texto') em português, como a tela mostra."""
    try:
        valor = ast.literal_eval(literal)
    except (ValueError, SyntaxError):
        return ''
    if funcao == 'tt':
        return valor
    from traducoes import t
    return t(valor, 'pt')


def _textos(trecho):
    return [_traduzir(f, s) for f, s in _TEXTO.findall(trecho)]


def _limpar(texto):
    return re.sub(r'<[^>]+>', '', texto or '').replace('&amp;', '&').strip()


def menu():
    """{endpoint: 'Grupo › Seção › Nome'} na ordem do menu principal."""
    linhas = _ler('templates/base.html').splitlines()
    caminhos, grupo, secao, dentro, rotulo_pendente = {}, None, None, False, False
    inicio = next(i for i, linha in enumerate(linhas) if 'navbar-nav me-auto' in linha)
    for linha in linhas[inicio:]:
        if 'navbar-nav ms-auto' in linha or 'central_notificacoes' in linha:
            break
        if 'dropdown-toggle' in linha and 'id="menu' in linha or 'id="adminDropdown"' in linha:
            rotulo_pendente, grupo, secao = True, None, None
            continue
        if rotulo_pendente:
            nomes = _textos(linha)
            if nomes:
                grupo, rotulo_pendente = _limpar(nomes[0]), False
            continue
        if 'dropdown-menu' in linha:
            dentro = True
        if 'dropdown-header' in linha:
            nomes = _textos(linha)
            secao = _limpar(nomes[0]) if nomes else None
            continue
        if '</ul>' in linha and dentro:
            dentro, grupo, secao = False, None, None
            continue
        achado = re.search(r"url_for\('(\w+)'\)", linha)
        if not achado:
            continue
        nomes = _textos(linha)
        if not nomes:  # link de topo: o nome vem na linha seguinte
            pos = linhas.index(linha, inicio)
            nomes = _textos(linhas[pos + 1]) if pos + 1 < len(linhas) else []
        if not nomes:
            continue
        partes = [p for p in ((grupo if dentro else None), (secao if dentro else None), _limpar(nomes[0])) if p]
        caminhos.setdefault(achado.group(1), ' › '.join(partes))
    return caminhos


def _passos_de_tours():
    """{endpoint: [texto dos passos]} de _tours.html."""
    texto = _ler('templates/_tours.html')
    passos = {}
    blocos = list(re.finditer(r"^\s{8}'(\w+)':\s*\[", texto, re.M))
    for n, bloco in enumerate(blocos):
        fim = blocos[n + 1].start() if n + 1 < len(blocos) else len(texto)
        corpo = texto[bloco.end():fim]
        corpo = corpo[:corpo.find('\n        ]')] if '\n        ]' in corpo else corpo
        passos[bloco.group(1)] = [p for p in _textos(corpo) if p]
    return passos


def _passos_das_paginas():
    """{endpoint: [texto dos passos]} dos templates que chamam rodarTour() direto."""
    app_py = _ler('app.py')
    template_para_endpoint, funcao = {}, None
    for linha in app_py.splitlines():
        definicao = re.match(r'def (\w+)\(', linha)
        if definicao:
            funcao = definicao.group(1)
        modelo = re.search(r"render_template\(\s*['\"]([\w/]+\.html)['\"]", linha)
        if modelo and funcao:
            template_para_endpoint.setdefault(modelo.group(1), funcao)
    passos = {}
    for nome in sorted(os.listdir(os.path.join(PASTA, 'templates'))):
        if nome.startswith('_') or not nome.endswith('.html'):
            continue
        texto = _ler(f'templates/{nome}')
        pos = texto.find('rodarTour([')
        if pos < 0 or nome not in template_para_endpoint:
            continue
        fim = texto.find(']', texto.rfind('texto:', pos, texto.find('</script>', pos)))
        passos[template_para_endpoint[nome]] = [p for p in _textos(texto[pos:fim + 1]) if p]
    return passos


def _perfis_por_endpoint():
    import perfis_acesso
    modulo_de = {}
    for chave, dados in perfis_acesso.MODULOS.items():
        for endpoint in dados[2]:
            modulo_de.setdefault(endpoint, chave)
    perfis = {}
    for endpoint, chave in modulo_de.items():
        perfis[endpoint] = [p for p, modulos in perfis_acesso.MODULOS_POR_BASE.items() if chave in modulos]
    return perfis


def _endereco(endpoint):
    try:
        from flask import current_app
        for regra in current_app.url_map.iter_rules(endpoint):
            if not regra.arguments:
                return regra.rule
    except Exception:
        pass
    return ''


def secoes():
    """[(seção, texto)] para a base de conhecimento: uma seção por tela do menu, com os passos do Tour."""
    caminhos = menu()
    passos = _passos_de_tours()
    passos.update(_passos_das_paginas())
    perfis = _perfis_por_endpoint()
    saida = []
    for endpoint, caminho in caminhos.items():
        nome = caminho.split(' › ')[-1]
        linhas = [f'Tela: {nome}', f'Onde fica: no menu superior, {caminho}.']
        endereco = _endereco(endpoint)
        if endereco:
            linhas.append(f'Endereço: {endereco}')
        if perfis.get(endpoint):
            linhas.append('Quem acessa: ' + ', '.join(perfis[endpoint]) + '.')
        lista = passos.get(endpoint) or []
        if lista:
            linhas.append('Como usar (os mesmos passos do Tour guiado da tela):')
            linhas += [f'{n}. {_limpar(p)}' for n, p in enumerate(lista, 1)]
            linhas.append('Dica: o botão Tour (ícone de interrogação, no topo da tela) mostra estes passos em cima da própria tela.')
        saida.append((f'Guia das telas › {nome}', '\n'.join(linhas)))
    # Telas com Tour que não estão no menu (abertas por dentro de outra tela, como a Sala da Banca)
    for endpoint, lista in passos.items():
        if endpoint in caminhos or not lista:
            continue
        nome = _limpar(lista[0]).split(':')[0][:60]
        linhas = [f'Tela: {nome}', 'Onde fica: é aberta a partir de outra tela (não aparece direto no menu).']
        if perfis.get(endpoint):
            linhas.append('Quem acessa: ' + ', '.join(perfis[endpoint]) + '.')
        linhas.append('Como usar (os mesmos passos do Tour guiado da tela):')
        linhas += [f'{n}. {_limpar(p)}' for n, p in enumerate(lista, 1)]
        saida.append((f'Guia das telas › {nome}', '\n'.join(linhas)))
    return saida
