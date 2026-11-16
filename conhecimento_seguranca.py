# -*- coding: utf-8 -*-
"""
CONHECIMENTO DE SEGURANÇA — o que o Gerente de Segurança aprende e ensina aos 5 agentes de segurança
===================================================================================================
Mesmas regras de governança do Agente Gerente Técnico (conhecimento.py): assinatura SHA-256, trilha de eventos,
revogação e limpeza para compliance na tela Governança de aprendizados.

1. Detecção interna (autônoma, aplicada na hora): o Gerente de Segurança compara a plataforma com o último
   retrato de segurança e ensina cada diferença ao agente certo:
     - rotas novas/removidas (com métodos, parâmetros e se exigem login) → Pentest e Análise de Código;
     - perfis personalizados (módulos que cada um NÃO pode abrir)        → Pentest (testa escalada de privilégio);
     - tabelas/colunas com dados sensíveis (senha, token, CPF, e-mail…)  → Inconsistências de Dados;
     - pacotes Python e bibliotecas de CDN novos/atualizados/removidos   → Dependências e Tecnologias.
   Roda ao iniciar a auditoria, no botão "Aprender agora" e de hora em hora (tarefas_agendadas.py).
2. Fontes oficiais (só domínios da lista de Fontes confiáveis, HTTPS): o que vem da internet fica PENDENTE até
   um administrador aprovar:
     - avisos de vulnerabilidade da base OSV.dev para os componentes instalados (no máximo 1 vez por dia);
     - a página oficial do CWE de cada fraqueza nova que os agentes encontrarem (cwe.mitre.org).

Todas as funções rodam dentro de um app_context.
"""
import os
import re
import json
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from flask import current_app

import conhecimento
from conhecimento import criar_aprendizado, aprendizados_para, registrar_consumo, dominio_confiavel, evento, _estado, _gravar_estado
from models import db, AprendizadoAgente

GERENTE_SEGURANCA = 'Gerente de Segurança'
GRUPO = 'seguranca'  # destino: todos os agentes de segurança
AGENTES_SEGURANCA = ['seg_configuracao', 'seg_dados', 'seg_codigo', 'seg_dependencias', 'seg_pentest']
NOMES = {'seguranca': 'Todos os agentes de segurança', 'seg_configuracao': 'Segurança · Configuração e Segredos',
         'seg_dados': 'Segurança · Inconsistências de Dados', 'seg_codigo': 'Segurança · Análise de Código',
         'seg_dependencias': 'Segurança · Dependências e Tecnologias', 'seg_pentest': 'Segurança · Pentest'}
TIPOS = {'seg_linha_base': 'Linha de base de segurança', 'seg_rota_nova': 'Rota nova (segurança)', 'seg_rota_removida': 'Rota removida (segurança)',
         'seg_perfil': 'Perfil de acesso (segurança)', 'seg_perfil_removido': 'Perfil removido (segurança)',
         'seg_dado_sensivel': 'Dado sensível novo', 'seg_dependencia': 'Componente novo/atualizado', 'seg_vulnerabilidade': 'Vulnerabilidade conhecida'}
# Segredos: precisam estar com hash. Dados pessoais: entram no inventário LGPD.
COLUNA_SEGREDO = re.compile(r"^(senha|senha_hash|password|password_hash|secret|segredo|api_key|chave_api|resposta_\d)$", re.I)
COLUNA_PESSOAL = re.compile(r"(^|_)(e?mail|telefone|celular|cpf|rg|nascimento|endereco|linkedin)($|_)", re.I)
IGNORAR_COLUNA = re.compile(r"^(data_|receber_|forcar_)", re.I)
# Rotas GET que mudam estado não entram nos testes de acesso automáticos (mesmo sendo só leitura para o atacante)
ACOES = re.compile(r"excluir|apagar|deletar|remover|logout|sair|executar|restaurar|limpar|desconectar|parar|iniciar|encerrar|aprovar|"
                   r"rejeitar|reabrir|cancelar|toggle|alternar|marcar|sincronizar|forcar|resetar|reset", re.I)
OSV_LOTE = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
LIMITE_CWE_POR_AUDITORIA = 5


# ------------------------------------------------------------------------------ retrato de segurança
def _exige_login(view):
    camada = view
    for _ in range(8):
        if camada is None:
            return False
        codigo = getattr(camada, '__code__', None)
        if codigo and 'flask_login' in codigo.co_filename.replace('\\', '/'):
            return True
        camada = getattr(camada, '__wrapped__', None)
    return False


def _rotas():
    rotas = []
    for r in current_app.url_map.iter_rules():
        if r.endpoint == 'static':
            continue
        rotas.append({'endpoint': r.endpoint, 'regra': r.rule, 'metodos': sorted(m for m in r.methods if m not in ('HEAD', 'OPTIONS')),
                      'parametros': bool(r.arguments), 'login': _exige_login(current_app.view_functions.get(r.endpoint))})
    return sorted(rotas, key=lambda x: (x['regra'], x['endpoint']))


def _colunas_sensiveis():
    """{tabela: {'segredos': [...], 'pessoais': [...]}} pelas colunas do modelo."""
    sensiveis = {}
    for nome, tabela in sorted(db.metadata.tables.items()):
        nomes = [c.name for c in tabela.columns if not IGNORAR_COLUNA.search(c.name)]
        grupo = {'segredos': sorted(c for c in nomes if COLUNA_SEGREDO.search(c)),
                 'pessoais': sorted(c for c in nomes if COLUNA_PESSOAL.search(c))}
        if grupo['segredos'] or grupo['pessoais']:
            sensiveis[nome] = grupo
    return sensiveis


def _componentes():
    from importlib import metadata
    pacotes = {d.metadata['Name'].lower(): d.version for d in metadata.distributions() if d.metadata['Name']}
    cdn = {}
    pasta = os.path.join(current_app.root_path, 'templates')
    padrao = re.compile(r"(?:cdn\.jsdelivr\.net/npm/(@?[\w.\-]+(?:/[\w.\-]+)?)@([\d.]+)|cdnjs\.cloudflare\.com/ajax/libs/([\w.\-]+)/([\d.]+)/)")
    for arquivo in sorted(os.listdir(pasta)):
        if arquivo.endswith('.html'):
            for m in padrao.finditer(open(os.path.join(pasta, arquivo), encoding='utf-8', errors='ignore').read()):
                cdn[m.group(1) or m.group(3)] = m.group(2) or m.group(4)
    return {'python': pacotes, 'cdn': cdn}


def _perfis():
    from models import PerfilPersonalizado
    from perfis_acesso import MODULOS, MODULOS_POR_BASE
    sem_parametros = {r['endpoint'] for r in _rotas() if not r['parametros'] and 'GET' in r['metodos'] and not ACOES.search(r['endpoint'])}
    perfis = {}
    for p in PerfilPersonalizado.query.all():
        modulos = sorted(p.lista_modulos())
        negados = [m for m in MODULOS_POR_BASE.get(p.perfil_base, []) if m not in modulos and not MODULOS[m][3]]
        bloqueados = sorted({e for m in negados for e in MODULOS[m][2] if e in sem_parametros})
        perfis[str(p.id)] = {'perfil_id': p.id, 'nome': p.nome, 'base': p.perfil_base, 'ativo': bool(p.ativo), 'modulos': modulos,
                             'modulos_negados': negados, 'endpoints_bloqueados': bloqueados}
    return perfis


def retrato_seguranca():
    return {'rotas': _rotas(), 'sensiveis': _colunas_sensiveis(), 'componentes': _componentes(), 'perfis': _perfis()}


def _criar(titulo, tipo, conteudo, destino, descricao, origem, **extra):
    return criar_aprendizado(titulo, tipo, conteudo, destino, descricao, origem, gerente=GERENTE_SEGURANCA, **extra)


# ------------------------------------------------------------------------------ 1. detecção interna (autônoma)
def detectar_mudancas(origem=GERENTE_SEGURANCA):
    """Compara com o último retrato de segurança e cria aprendizados APLICADOS para cada diferença."""
    atual = retrato_seguranca()
    anterior = _estado('retrato_seguranca', None)
    criados = []
    if anterior is None:
        criados.append(_criar('Linha de base de segurança registrada', 'seg_linha_base',
                              {'rotas': atual['rotas'], 'sensiveis': atual['sensiveis']}, [GRUPO],
                              f"{len(atual['rotas'])} rotas, {sum(len(g['segredos']) + len(g['pessoais']) for g in atual['sensiveis'].values())} coluna(s) sensível(is), "
                              f"{len(atual['componentes']['python'])} pacote(s) Python e {len(atual['componentes']['cdn'])} biblioteca(s) de CDN.", origem))
        anterior = {'rotas': atual['rotas'], 'sensiveis': atual['sensiveis'], 'componentes': atual['componentes'], 'perfis': {}}

    # Rotas
    chave = lambda r: (r['endpoint'], r['regra'])
    antes = {chave(r): r for r in anterior.get('rotas', [])}
    agora = {chave(r): r for r in atual['rotas']}
    novas = [r for k, r in agora.items() if k not in antes or antes[k] != r]
    removidas = [r for k, r in antes.items() if k not in agora]
    if novas:
        sem_login = [r['regra'] for r in novas if not r['login']]
        criados.append(_criar(f"{len(novas)} rota(s) nova(s) ou alterada(s) para testar", 'seg_rota_nova', {'rotas': novas},
                              ['seg_pentest', 'seg_codigo'],
                              "O Pentest testa o acesso anônimo e o do Aluno; a Análise de Código revisa as funções."
                              + (f" Sem @login_required: {', '.join(sem_login[:6])}." if sem_login else ''), origem))
    if removidas:
        criados.append(_criar(f"{len(removidas)} rota(s) removida(s)", 'seg_rota_removida', {'rotas': removidas}, ['seg_pentest'],
                              'O Pentest deixa de testar estas rotas.', origem))

    # Dados sensíveis
    novas_colunas = {}
    for t, grupo in atual['sensiveis'].items():
        antes_t = anterior.get('sensiveis', {}).get(t, {})
        antes_t = antes_t if isinstance(antes_t, dict) else {}
        novo = {g: [c for c in cols if c not in antes_t.get(g, [])] for g, cols in grupo.items()}
        if novo['segredos'] or novo['pessoais']:
            novas_colunas[t] = novo
    if novas_colunas:
        total = sum(len(g['segredos']) + len(g['pessoais']) for g in novas_colunas.values())
        criados.append(_criar(f"{total} coluna(s) com dado sensível nova(s)", 'seg_dado_sensivel', {'colunas': novas_colunas}, ['seg_dados'],
                              'O agente de dados confere se os segredos estão com hash e inclui os dados pessoais no inventário LGPD: '
                              + '; '.join(f"{t}: {', '.join(g['segredos'] + g['pessoais'])}" for t, g in novas_colunas.items())[:400], origem))

    # Componentes (dependências)
    mudancas = {}
    for tipo in ('python', 'cdn'):
        a, d = anterior.get('componentes', {}).get(tipo, {}), atual['componentes'][tipo]
        novos = {p: v for p, v in d.items() if p not in a}
        atualizados = {p: [a[p], v] for p, v in d.items() if p in a and a[p] != v}
        fora = sorted(p for p in a if p not in d)
        if novos or atualizados or fora:
            mudancas[tipo] = {'novos': novos, 'atualizados': atualizados, 'removidos': fora}
    if mudancas:
        resumo = '; '.join(f"{t}: +{len(m['novos'])} ~{len(m['atualizados'])} -{len(m['removidos'])}" for t, m in mudancas.items())
        criados.append(_criar('Componentes da plataforma mudaram', 'seg_dependencia', mudancas, ['seg_dependencias'],
                              f"O agente de dependências destaca estes componentes na próxima auditoria ({resumo}).", origem))

    # Perfis personalizados
    for pid, perfil in atual['perfis'].items():
        if anterior.get('perfis', {}).get(pid) != perfil:
            criados.append(_criar(f"Perfil de acesso para testar escalada de privilégio: {perfil['nome']}", 'seg_perfil', perfil, ['seg_pentest'],
                                  f"Herda de {perfil['base']}; {len(perfil['endpoints_bloqueados'])} rota(s) devem ser barradas.", origem))
    for pid, perfil in anterior.get('perfis', {}).items():
        if pid not in atual['perfis']:
            criados.append(_criar(f"Perfil de acesso removido: {perfil['nome']}", 'seg_perfil_removido', {'perfil_id': int(pid)},
                                  ['seg_pentest'], 'O Pentest deixa de testar este perfil.', origem))

    _gravar_estado('retrato_seguranca', atual)
    _gravar_estado('ultima_deteccao_seguranca', {'em': datetime.now().isoformat(timespec='seconds'), 'origem': origem, 'novos': len(criados)})
    db.session.commit()
    return criados


# ------------------------------------------------------------------------------ consumo pelos agentes
def para_agente(chave_agente, tipos=None):
    """Aprendizados aplicados para um agente de segurança (dele, do grupo 'seguranca' ou de todos)."""
    alvo = f"seg_{chave_agente}"
    itens = [a for a in aprendizados_para(alvo, tipos) if a.tipo.startswith('seg_') or a.tipo in ('referencia_externa', 'linha_base')
             or (a.tipo == 'regra_verificada' and alvo in json.loads(a.agentes_destino or '[]'))]
    grupo = [a for a in aprendizados_para(GRUPO, tipos) if a not in itens and GRUPO in json.loads(a.agentes_destino or '[]')]
    return sorted(itens + grupo, key=lambda a: a.id)


def consumir(chave_agente, itens):
    registrar_consumo(f"Agente de segurança {chave_agente}", itens)


def rotas_aprendidas(itens):
    """Rotas conhecidas pelo agente = linha de base + rotas novas − removidas."""
    rotas = {}
    for a in itens:
        dados = json.loads(a.conteudo)
        if a.tipo in ('seg_linha_base', 'seg_rota_nova'):
            for r in dados.get('rotas', []):
                rotas[(r['endpoint'], r['regra'])] = {**r, 'aprendizado': a.codigo, 'nova': a.tipo == 'seg_rota_nova'}
        elif a.tipo == 'seg_rota_removida':
            for r in dados.get('rotas', []):
                rotas.pop((r['endpoint'], r['regra']), None)
    return list(rotas.values())


def perfis_aprendidos(itens):
    perfis = {}
    for a in itens:
        dados = json.loads(a.conteudo)
        if a.tipo == 'seg_perfil':
            perfis[dados['perfil_id']] = {**dados, 'aprendizado': a.codigo}
        elif a.tipo == 'seg_perfil_removido':
            perfis.pop(dados['perfil_id'], None)
    return [p for p in perfis.values() if p.get('ativo')]


def colunas_aprendidas(itens):
    colunas = {}
    for a in itens:
        dados = json.loads(a.conteudo)
        fonte = dados.get('colunas') if a.tipo == 'seg_dado_sensivel' else dados.get('sensiveis') if a.tipo == 'seg_linha_base' else None
        for tabela, grupo in (fonte or {}).items():
            destino = colunas.setdefault(tabela, {'segredos': set(), 'pessoais': set()})
            for g in ('segredos', 'pessoais'):
                destino[g].update(grupo.get(g, []))
    return {t: {g: sorted(c) for g, c in grupos.items()} for t, grupos in colunas.items()}


# ------------------------------------------------------------------------------ 2. fontes oficiais (pendentes até aprovação)
def _json(url, corpo=None):
    if not dominio_confiavel(url):
        raise ValueError(f"domínio fora da lista de fontes confiáveis: {url}")
    dados = json.dumps(corpo).encode('utf-8') if corpo is not None else None
    pedido = Request(url, data=dados, headers={'Content-Type': 'application/json', 'User-Agent': 'MentoriaGerenteSeguranca/1.0'})
    with urlopen(pedido, timeout=30) as resposta:
        if not dominio_confiavel(resposta.geturl()):
            raise ValueError('a resposta veio de fora das fontes confiáveis')
        return json.loads(resposta.read(5_000_000))


def _ja_conhecido(tipo, marcador):
    return AprendizadoAgente.query.filter(AprendizadoAgente.tipo == tipo, AprendizadoAgente.conteudo.like(f'%{marcador}%')).first() is not None


def pesquisar_vulnerabilidades(origem=GERENTE_SEGURANCA, forcar=False, limite=15):
    """Consulta a OSV.dev (fonte oficial) para os componentes instalados e propõe cada aviso novo (PENDENTE)."""
    ultima = _estado('ultima_pesquisa_osv', None)
    if not forcar and ultima and datetime.now() - datetime.fromisoformat(ultima['em']) < timedelta(hours=24):
        return []
    if not dominio_confiavel(OSV_LOTE):
        evento('Busca recusada', 'osv.dev fora da lista de fontes confiáveis', agente=GERENTE_SEGURANCA)
        db.session.commit()
        return []
    componentes = _componentes()
    consultas = [{'package': {'name': n, 'ecosystem': 'PyPI'}, 'version': v} for n, v in sorted(componentes['python'].items())]
    consultas += [{'package': {'name': n, 'ecosystem': 'npm'}, 'version': v} for n, v in sorted(componentes['cdn'].items())]
    respostas = []
    for i in range(0, len(consultas), 500):
        respostas += _json(OSV_LOTE, {'queries': consultas[i:i + 500]}).get('results', [])
    criados = []
    import sys
    sys.path.insert(0, os.path.join(current_app.root_path, 'agentes_seguranca'))
    from agente_dependencias import afeta
    for consulta, resposta in zip(consultas, respostas):
        pacote, versao = consulta['package']['name'], consulta['version']
        for vid in [v['id'] for v in resposta.get('vulns', [])][:10]:
            if len(criados) >= limite or _ja_conhecido('seg_vulnerabilidade', f'"id": "{vid}"'):
                continue
            vuln = _json(OSV_VULN + vid)
            if not afeta(vuln, pacote, versao):
                continue
            sev = str((vuln.get('database_specific') or {}).get('severity', '')).upper()
            corrigidas = sorted({ev['fixed'] for af in vuln.get('affected', []) for fx in af.get('ranges', []) for ev in fx.get('events', []) if 'fixed' in ev})
            conteudo = {'id': vid, 'pacote': pacote, 'ecossistema': consulta['package']['ecosystem'], 'versao_afetada': versao,
                        'aliases': [a for a in vuln.get('aliases', []) if a.startswith(('CVE-', 'GHSA-'))][:4], 'resumo': (vuln.get('summary') or '')[:300],
                        'severidade': {'CRITICAL': 'Crítica', 'HIGH': 'Alta', 'MODERATE': 'Média', 'MEDIUM': 'Média', 'LOW': 'Baixa'}.get(sev, 'Média'),
                        'corrigida_em': corrigidas[-3:], 'url': f"https://osv.dev/vulnerability/{vid}", 'lido_em': datetime.now().isoformat(timespec='seconds')}
            criados.append(_criar(f"Vulnerabilidade {vid} em {pacote} {versao}", 'seg_vulnerabilidade', conteudo, ['seg_dependencias'],
                                  f"[{conteudo['severidade']}] {conteudo['resumo'][:180]}", 'Fonte oficial (osv.dev)',
                                  fonte_url=conteudo['url'], status='Pendente'))
    _gravar_estado('ultima_pesquisa_osv', {'em': datetime.now().isoformat(timespec='seconds'), 'origem': origem, 'novos': len(criados)})
    db.session.commit()
    return criados


def aprender_com_achados(relatorios, origem=GERENTE_SEGURANCA):
    """Para cada fraqueza (CWE) nova encontrada, lê a página oficial do CWE e propõe a referência ao agente que a encontrou."""
    criados = []
    vistos = set()
    for rel in relatorios:
        for achado in rel.get('achados', []):
            cwe = achado.get('cwe') or ''
            m = re.fullmatch(r'CWE-(\d+)', cwe)
            if not m or achado.get('severidade') == 'Informativa' or cwe in vistos or len(criados) >= LIMITE_CWE_POR_AUDITORIA:
                continue
            vistos.add(cwe)
            if _ja_conhecido('referencia_externa', f'"tema": "{cwe}'):
                continue
            url = f"https://cwe.mitre.org/data/definitions/{m.group(1)}.html"
            try:
                item = conhecimento.buscar_fonte_oficial(url, f"{cwe} — {achado['titulo'][:80]}", gerente=GERENTE_SEGURANCA,
                                                         destino=[f"seg_{rel['chave']}"])
                criados.append(item)
            except Exception as e:
                db.session.rollback()
                evento('Busca recusada', f"{url}: {e}", agente=GERENTE_SEGURANCA)
                db.session.commit()
    return criados


def resumo_para_tela():
    """Contagem de aprendizados por agente de segurança (para o hub)."""
    contagem = {a: {'Aplicado': 0, 'Pendente': 0} for a in [GRUPO] + AGENTES_SEGURANCA}
    for a in AprendizadoAgente.query.filter(AprendizadoAgente.status.in_(['Aplicado', 'Pendente'])).all():
        for destino in json.loads(a.agentes_destino or '[]'):
            if destino in contagem:
                contagem[destino][a.status] += 1
    return {'contagem': contagem, 'ultima': _estado('ultima_deteccao_seguranca', None), 'ultima_osv': _estado('ultima_pesquisa_osv', None)}
