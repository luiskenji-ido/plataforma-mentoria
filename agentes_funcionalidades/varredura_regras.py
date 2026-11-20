# -*- coding: utf-8 -*-
"""
VARREDURA DE REGRAS — o olho do Agente Dev sobre 100% do código
================================================================
O Gerente de Funcionalidades só aprende o que está numa REGRA NOMEADA (constante em MAIÚSCULAS, como
PERFIS_GESTAO_CURSOS ou MINIMO_CARACTERES_JUSTIFICATIVA): é ela que entra no retrato das regras de negócio,
vira aprendizado quando muda e é ensinada aos agentes. Regra escrita direto no meio do código fica invisível.

Esta varredura lê todos os .py (pela árvore sintática) e todos os templates e aponta:
  - LISTA DE PERFIS solta no código (['Administrador', 'Mentor Administrador'] dentro de uma função ou tela);
  - PODER DADO A UM PERFIL por comparação direta (tipo_usuario == 'Administrador', != 'Mentor Administrador'...);
  - NÚMERO DE REGRA solto: tamanho mínimo de texto (len(x) < 10), faixa de nota (0 <= nota <= 10), prazo em dias.
Fica de fora o que é IDENTIDADE do perfil, não regra: Aluno, Gestor B2B (Admin B2B) e Avaliador da banca veem só o
que é deles (ex.: tipo_usuario == 'Aluno'). Uma exceção consciente leva o comentário "# regra-nomeada: ok" na linha.

Uso: python agentes_funcionalidades/varredura_regras.py  (lista os achados)
"""
import os
import re
import ast
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERFIS = {'Aluno', 'Professor', 'Mentor', 'Mentor Administrador', 'Administrador', 'Admin B2B', 'Avaliador Banca'}
PERFIS_DE_IDENTIDADE = {'Aluno', 'Admin B2B', 'Avaliador Banca'}  # escopo dos próprios dados, não um poder
MARCA_EXCECAO = 'regra-nomeada: ok'
# Fora da varredura: bibliotecas, migrações, dados, os próprios agentes de teste (usam os perfis para testar) e traduções
PASTAS_FORA = {'.venv', 'venv', '__pycache__', 'migrations', 'Agent Reports', 'node_modules', '.git', 'instance', 'uploads', 'static',
               'agentes_funcionalidades', 'agentes_omnitest', 'agentes_seguranca', 'agentes_banco', 'agentes_ia', 'deploy', '.claude'}
ARQUIVOS_FORA = re.compile(r'^(traducoes.*|conhecimento_tour|guia_telas|criar_admin|reset_admin|criar_tabela_.*|atualizar_.*)\.py$')
ESQUERDA_PERFIL = re.compile(r'(^|\.)tipo_usuario$|^tipo$|^base$')
TEMPLATE_PERFIL = re.compile(r"current_user\.tipo_usuario\s*(==|!=|not in|in)\s*(\[[^\]]*\]|\([^)]*\)|'[^']*'|\"[^\"]*\")")


def _arquivos(extensao):
    for raiz, pastas, nomes in os.walk(RAIZ):
        pastas[:] = sorted(p for p in pastas if p not in PASTAS_FORA and not p.startswith(('.', 'venv')) and p != 'site-packages')
        for nome in sorted(nomes):
            if nome.endswith(extensao) and not ARQUIVOS_FORA.match(nome):
                yield os.path.join(raiz, nome)


def _achado(arquivo, linha, tipo, trecho, sugestao):
    return {'arquivo': os.path.relpath(arquivo, RAIZ).replace(os.sep, '/'), 'linha': linha, 'tipo': tipo,
            'trecho': trecho.strip()[:160], 'sugestao': sugestao}


def _numero(no):
    return isinstance(no, ast.Constant) and isinstance(no.value, (int, float)) and not isinstance(no.value, bool)


def varrer_python(caminho):
    texto = open(caminho, encoding='utf-8').read()
    linhas = texto.splitlines()
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return []
    nomeados = set()  # o que está dentro de uma constante do módulo já é regra nomeada
    for no in arvore.body:
        if isinstance(no, (ast.Assign, ast.AnnAssign)):
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            if all(isinstance(a, ast.Name) and a.id.isupper() for a in alvos):
                nomeados.update(id(s) for s in ast.walk(no))
    achados = []

    def linha_ok(n):
        return MARCA_EXCECAO in (linhas[n - 1] if 0 < n <= len(linhas) else '')

    for no in ast.walk(arvore):
        if id(no) in nomeados or not hasattr(no, 'lineno') or linha_ok(no.lineno):
            continue
        trecho = linhas[no.lineno - 1]
        if isinstance(no, (ast.List, ast.Tuple, ast.Set)):
            valores = [e.value for e in no.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if valores and len(valores) == len(no.elts) and set(valores) <= PERFIS:
                achados.append(_achado(caminho, no.lineno, 'Lista de perfis solta', trecho,
                                       f"Criar uma regra nomeada PERFIS_<O_QUE_PODEM> = {sorted(set(valores))} e usar o nome."))
        elif isinstance(no, ast.Compare):
            esquerda = ast.unparse(no.left)
            for comparado in no.comparators:
                if (isinstance(comparado, ast.Constant) and comparado.value in PERFIS - PERFIS_DE_IDENTIDADE
                        and ESQUERDA_PERFIL.search(esquerda)):
                    achados.append(_achado(caminho, no.lineno, 'Poder dado a um perfil por comparação direta', trecho,
                                           f"Trocar por 'in PERFIS_<O_QUE_PODEM>' com a regra nomeada [{comparado.value!r}]."))
            # número de regra: tamanho mínimo de texto e faixas de valor
            partes = [no.left] + list(no.comparators)
            if (isinstance(no.left, ast.Call) and ast.unparse(no.left.func) == 'len' and len(no.ops) == 1
                    and isinstance(no.ops[0], (ast.Lt, ast.LtE)) and _numero(no.comparators[0]) and no.comparators[0].value >= 3):
                achados.append(_achado(caminho, no.lineno, 'Tamanho mínimo de texto solto', trecho,
                                       f"Criar MINIMO_CARACTERES_<CAMPO> = {no.comparators[0].value} e usar o nome."))
            elif len(no.ops) == 2 and _numero(partes[0]) and (_numero(partes[2]) or isinstance(partes[2], ast.BinOp)) \
                    and not (_numero(partes[2]) and partes[2].value in (1, 100)):
                achados.append(_achado(caminho, no.lineno, 'Faixa de valores solta', trecho,
                                       'Criar as regras nomeadas do mínimo e do máximo (ex.: NOTA_MAXIMA) e usar os nomes.'))
            elif (len(no.ops) == 1 and isinstance(no.left, ast.Attribute) and no.left.attr == 'days'
                  and _numero(no.comparators[0]) and no.comparators[0].value > 1):
                achados.append(_achado(caminho, no.lineno, 'Prazo em dias solto', trecho,
                                       f"Criar <PRAZO>_DIAS = {no.comparators[0].value} e usar o nome."))
    return achados


def varrer_template(caminho):
    achados = []
    for n, linha in enumerate(open(caminho, encoding='utf-8').read().splitlines(), 1):
        if MARCA_EXCECAO in linha:
            continue
        for _operador, valor in TEMPLATE_PERFIL.findall(linha):
            if valor[0] in '[(':
                achados.append(_achado(caminho, n, 'Lista de perfis solta na tela', linha,
                                       'Usar a regra nomeada PERFIS_* (as regras PERFIS_* do app.py já chegam a todas as telas).'))
            elif valor.strip('\'"') in PERFIS - PERFIS_DE_IDENTIDADE:
                achados.append(_achado(caminho, n, 'Poder dado a um perfil na tela', linha,
                                       "Trocar por 'current_user.tipo_usuario in PERFIS_<O_QUE_PODEM>'."))
    return achados


def varrer():
    """Todos os achados do código (Python e telas), em ordem de arquivo e linha."""
    achados = []
    for caminho in _arquivos('.py'):
        achados += varrer_python(caminho)
    for caminho in _arquivos('.html'):
        achados += varrer_template(caminho)
    vistos, unicos = set(), []
    for a in achados:
        chave = (a['arquivo'], a['linha'], a['tipo'])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)
    return sorted(unicos, key=lambda a: (a['arquivo'], a['linha']))


# ------------------------------------------------------------------------------ regras nomeadas (o que o Gerente aprende)
PREFIXOS_TECNICOS = ('PASTA', 'ORDEM_AGENTES', 'SCOPES', 'CORES_', 'ROTULOS_', '_')


def regras_nomeadas(modulo):
    """{nome: valor} de toda regra nomeada do módulo (constante em MAIÚSCULAS com valor de dado), menos as técnicas."""
    import json
    regras = {}
    for nome, valor in vars(modulo).items():
        if not nome.isupper() or nome.startswith(PREFIXOS_TECNICOS) or callable(valor) or isinstance(valor, type(sys)):
            continue
        if isinstance(valor, (set, frozenset, tuple)):
            valor = sorted(valor) if isinstance(valor, (set, frozenset)) else list(valor)
        elif isinstance(valor, dict):
            valor = {str(k): (sorted(v) if isinstance(v, (set, frozenset)) else v) for k, v in valor.items()}
        try:
            json.dumps(valor, ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        regras[nome] = valor
    return regras


if __name__ == '__main__':
    lista = varrer()
    for a in lista:
        print(f"{a['arquivo']}:{a['linha']}  [{a['tipo']}]  {a['trecho']}")
    print(f"\n{len(lista)} regra(s) escrita(s) direto no código.")
