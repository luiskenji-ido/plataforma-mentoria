# -*- coding: utf-8 -*-
"""
LEITOR DOS PROMPTS DE CORREÇÃO
==============================
Junta, numa lista única, tudo o que as quatro equipes de agentes pediram para corrigir na última execução de cada agente:
Fim a Fim (OmniTest), Segurança, Banco de Dados e Funcionalidades. Cada item traz o que foi encontrado, onde, o que se
esperava, a recomendação do agente e o prompt de correção completo (que vai junto para a IA como contexto).
"""
import glob
import hashlib
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELATORIOS = os.path.join(RAIZ, 'Agent Reports')

SEVERIDADES = ['Crítica', 'Alta', 'Média', 'Baixa']
EQUIPES = [  # (chave, nome, padrão dos relatórios, agentes)
    ('e2e', 'Testes Fim a Fim', os.path.join('OmniTest', '**', 'Relatorio_OmniTest_{agente}_2*.json'),
     ['administrador', 'aluno', 'professor', 'mentor', 'mentor_administrador', 'gestor_b2b', 'avaliador', 'perfis_personalizados']),
    ('seguranca', 'Segurança', os.path.join('Seguranca', 'Seguranca_{agente}_2*.json'),
     ['configuracao', 'dados', 'codigo', 'dependencias', 'pentest']),
    ('banco', 'Banco de Dados', os.path.join('BancoDados', 'Banco_{agente}_2*.json'),
     ['consultas', 'esquema', 'backup', 'dba', 'portabilidade']),
    ('funcionalidades', 'Funcionalidades', os.path.join('Funcionalidades', '**', 'Funcional_{agente}_2*.json'),
     ['administrador', 'mentor_administrador', 'gestor_parceiro', 'professor', 'mentor', 'aluno', 'avaliador', 'encerramento']),
]
ARQUIVO_CITADO = re.compile(r'([\w./\\-]+\.(?:py|html|js|css|txt|md|json|ini|toml))(?::(\d+))?')


def _ultimo(raiz, padrao):
    arquivos = glob.glob(os.path.join(raiz, padrao), recursive=True)
    return max(arquivos, key=os.path.getmtime) if arquivos else None


def _ler(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return f.read()
    except (OSError, TypeError):
        return ''


def arquivos_citados(*textos):
    """Arquivos do projeto citados no achado (com as linhas, quando houver): [(caminho relativo, [linhas])]."""
    vistos = {}
    for texto in textos:
        for caminho, linha in ARQUIVO_CITADO.findall(texto or ''):
            caminho = caminho.replace('\\', '/').lstrip('./')
            if caminho.startswith(('http', 'www.')) or '..' in caminho:
                continue
            if os.path.isfile(os.path.join(RAIZ, caminho)):
                vistos.setdefault(caminho, set())
                if linha:
                    vistos[caminho].add(int(linha))
            else:
                # nome solto (ex.: "reuniao_form.html" dentro de "templates/...") — procura no projeto
                achado = next(iter(glob.glob(os.path.join(RAIZ, '**', os.path.basename(caminho)), recursive=True)), None)
                if achado and '.venv' not in achado and 'Agent Reports' not in achado:
                    rel = os.path.relpath(achado, RAIZ).replace('\\', '/')
                    vistos.setdefault(rel, set())
    return [(c, sorted(l)) for c, l in vistos.items()]


def _identificador(equipe, agente, titulo, onde):
    titulo_sem_numeros = re.sub(r'\d+', '#', titulo)  # fora da f-string: Python 3.10 (PythonAnywhere) não aceita \ dentro de {}
    base = f"{equipe}|{agente}|{titulo_sem_numeros}|{onde[:120]}"
    return hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]


def _itens_do_relatorio(equipe, agente, dados):
    itens = []
    if equipe in ('seguranca', 'banco'):
        for a in dados.get('achados', []):
            if a.get('severidade') not in SEVERIDADES:
                continue  # informativos não são correções
            itens.append({'titulo': a.get('titulo', ''), 'severidade': a['severidade'], 'categoria': a.get('categoria') or a.get('cwe') or '',
                          'onde': a.get('local', ''), 'detalhe': a.get('evidencia', ''), 'esperado': '',
                          'recomendacao': a.get('recomendacao', '') + (f"\nScript sugerido:\n{a['script']}" if a.get('script') else ''),
                          'codigo_agente': a.get('id', '')})
    elif equipe == 'funcionalidades':
        for t in dados.get('testes', []):
            if t.get('resultado') not in ('Falha', 'Alerta'):
                continue
            itens.append({'titulo': t.get('titulo', ''), 'severidade': t.get('severidade') if t.get('severidade') in SEVERIDADES else 'Média',
                          'categoria': t.get('categoria', ''), 'onde': t.get('etapa', ''), 'detalhe': t.get('detalhe', ''),
                          'esperado': t.get('esperado', ''), 'recomendacao': t.get('recomendacao', ''), 'codigo_agente': t.get('id', '')})
    else:
        for r in dados.get('resultados', []):
            status = r.get('status', '')
            if 'Falha' not in status and 'Alerta' not in status:
                continue
            itens.append({'titulo': f"{r.get('modulo', '')}: {r.get('acao', '')}", 'severidade': 'Alta' if 'Falha' in status else 'Baixa',
                          'categoria': r.get('modulo', ''), 'onde': f"{r.get('url', '')} · {r.get('arquivos', '')}", 'detalhe': r.get('detalhe', ''),
                          'esperado': r.get('esperado', ''), 'recomendacao': r.get('dica', ''), 'codigo_agente': ''})
    return itens


def coletar(raiz_relatorios=RELATORIOS):
    """Lista de correções pedidas pela última execução de cada agente das quatro equipes, da mais grave para a menos grave."""
    correcoes = []
    for equipe, nome_equipe, padrao, agentes in EQUIPES:
        for agente in agentes:
            arquivo = _ultimo(raiz_relatorios, padrao.format(agente=agente))
            if not arquivo:
                continue
            try:
                dados = json.loads(_ler(arquivo))
            except ValueError:
                continue
            prompt = dados.get('prompt') or dados.get('prompt_llm') or ''
            for item in _itens_do_relatorio(equipe, agente, dados):
                citados = arquivos_citados(item['onde'], item['detalhe'], item['recomendacao'])
                correcoes.append({**item, 'id': _identificador(equipe, agente, item['titulo'], item['onde']), 'equipe': equipe,
                                  'equipe_nome': nome_equipe, 'agente': agente, 'relatorio': arquivo, 'prompt': prompt,
                                  'carimbo': dados.get('carimbo', ''), 'arquivos': citados})
    ordem = {s: i for i, s in enumerate(SEVERIDADES)}
    return sorted(correcoes, key=lambda c: (ordem.get(c['severidade'], 9), c['equipe'], c['agente']))


def trecho_do_prompt(correcao):
    """O prompt de correção do agente (lido do arquivo .md que o agente gerou) — vai inteiro para a IA como contexto."""
    return _ler(correcao.get('prompt'))
