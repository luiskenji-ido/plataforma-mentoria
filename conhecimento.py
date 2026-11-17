# -*- coding: utf-8 -*-
"""
CONHECIMENTO DOS AGENTES — o que o Agente Gerente Técnico aprende e distribui
==========================================================================
1. Detecção interna (autônoma): o Gerente compara a plataforma com o último retrato guardado
   (perfis personalizados e rotas). Cada diferença vira um aprendizado APLICADO na hora aos agentes de destino.
   Roda ao salvar um perfil, ao iniciar os testes (Agente Gestor) e de hora em hora (tarefas_agendadas.py).
2. Fontes oficiais: o Gerente só consulta domínios da lista de fontes confiáveis (HTTPS). O que vem da internet
   fica PENDENTE até um administrador aprovar na Governança de aprendizados.
3. Governança: todo aprendizado tem assinatura SHA-256 do conteúdo; revogar tira o aprendizado dos agentes;
   a limpeza para compliance exporta (JSON + CSV) antes de apagar e deixa um evento com o retrato do que saiu.

Todas as funções rodam dentro de um app_context.
"""
import os
import re
import csv
import json
import hashlib
import ipaddress
from html import unescape
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import current_app

from models import (db, AprendizadoAgente, EventoAprendizado, FonteConfiavel, EstadoConhecimento, PerfilPersonalizado)

AGENTE_GERENTE = 'Agente Gerente Técnico'
TODOS = 'todos'
AGENTES = ['administrador', 'aluno', 'professor', 'mentor', 'mentor_administrador', 'gestor_b2b', 'avaliador', 'perfis_personalizados',
           # Agentes de Segurança (ensinados pelo Gerente de Segurança, conhecimento_seguranca.py)
           'seguranca', 'seg_configuracao', 'seg_dados', 'seg_codigo', 'seg_dependencias', 'seg_pentest',
           # Agentes de Banco de Dados (ensinados pelo Gerente de Banco de Dados, conhecimento_banco.py)
           'banco', 'db_consultas', 'db_esquema', 'db_backup', 'db_dba', 'db_portabilidade',
           # Agentes de Funcionalidades (ensinados pelo Gerente de Funcionalidades, conhecimento_funcional.py)
           'funcionalidades', 'fn_administrador', 'fn_mentor_administrador', 'fn_gestor_parceiro', 'fn_professor', 'fn_mentor', 'fn_aluno',
           'fn_avaliador', 'fn_encerramento']
FONTES_PADRAO = [
    ('docs.python.org', 'Documentação oficial do Python'), ('flask.palletsprojects.com', 'Documentação oficial do Flask'),
    ('jinja.palletsprojects.com', 'Documentação oficial do Jinja'), ('docs.sqlalchemy.org', 'Documentação oficial do SQLAlchemy'),
    ('playwright.dev', 'Documentação oficial do Playwright'), ('developer.mozilla.org', 'MDN Web Docs (Mozilla)'),
    ('www.w3.org', 'W3C (padrões web e WCAG)'), ('owasp.org', 'OWASP (segurança de aplicações)'),
    ('cheatsheetseries.owasp.org', 'OWASP Cheat Sheet Series'), ('getbootstrap.com', 'Documentação oficial do Bootstrap'),
    ('www.chartjs.org', 'Documentação oficial do Chart.js'), ('www.gov.br', 'Governo Federal (LGPD e ANPD)'),
    ('help.pythonanywhere.com', 'Ajuda oficial do PythonAnywhere'),
    # Bases oficiais de vulnerabilidades (usadas pelos Agentes de Segurança)
    ('osv.dev', 'OSV — base oficial de vulnerabilidades open source (Google/OpenSSF)'), ('pypi.org', 'PyPI — índice oficial de pacotes Python'),
    ('nvd.nist.gov', 'NVD — National Vulnerability Database (NIST)'), ('cwe.mitre.org', 'CWE — catálogo de fraquezas (MITRE)'),
    # Documentação oficial dos bancos de dados (usada pelo Gerente de Banco de Dados)
    ('sqlite.org', 'SQLite — documentação oficial'), ('postgresql.org', 'PostgreSQL — documentação oficial'),
    ('dev.mysql.com', 'MySQL — documentação oficial (Oracle)'), ('learn.microsoft.com', 'Microsoft Learn — SQL Server'),
    ('mongodb.com', 'MongoDB — documentação oficial'),
    # Tour, telas e acessibilidade (agentes OmniTest)
    ('introjs.com', '[Tour e telas] Intro.js — documentação oficial da biblioteca do tour'),
    ('web.dev', '[Tour e telas] web.dev (Google) — desempenho, acessibilidade e boas práticas web'),
    ('whatwg.org', '[Tour e telas] WHATWG — especificação oficial do HTML'),
    # Funcionalidades, Python e publicação (agentes de Funcionalidades e Orquestrador)
    ('python.org', '[Funcionalidades] Python.org — documentação, PEPs e avisos de segurança do Python'),
    ('palletsprojects.com', '[Funcionalidades] Pallets — Flask, Werkzeug, Jinja e ItsDangerous'),
    ('sqlalchemy.org', '[Banco de dados] SQLAlchemy e Alembic — documentação oficial'),
    ('git-scm.com', '[Orquestrador] Git — documentação oficial'),
    ('docs.github.com', '[Orquestrador] GitHub Docs — repositórios, push e Actions'),
    ('www.planalto.gov.br', '[Funcionalidades] Planalto — legislação federal (LGPD, Lei 13.709/2018, e ECA)'),
    # Segurança (agentes de Segurança)
    ('csrc.nist.gov', '[Segurança] NIST CSRC — normas de segurança (ex.: SP 800-63, senhas e autenticação)'),
    ('www.cisa.gov', '[Segurança] CISA — catálogo de vulnerabilidades exploradas (KEV) e alertas'),
    ('www.cve.org', '[Segurança] Programa CVE — identificadores oficiais de vulnerabilidades'),
    ('www.first.org', '[Segurança] FIRST — especificação do CVSS (nota de gravidade)'),
    ('www.cert.br', '[Segurança] CERT.br — boas práticas e incidentes de segurança no Brasil'),
    ('www.rfc-editor.org', '[Segurança] RFC Editor — padrões oficiais da internet (HTTP, cookies, OAuth)'),
    ('oauth.net', '[Segurança] OAuth.net — especificações OAuth 2.0 e PKCE (login Google e Microsoft)'),
    ('www.iso.org', '[Segurança] ISO — normas de gestão de segurança da informação (ISO/IEC 27001)'),
    # Integrações e IA (Assistente, Provedores de IA, agendas)
    ('developers.google.com', '[Integrações] Google Developers — APIs do Gmail e do Google Agenda'),
    ('ai.google.dev', '[IA] Google AI for Developers — API do Gemini, modelos e preços'),
    ('claude.com', '[IA] Claude (Anthropic) — documentação da API, modelos e preços'),
    ('anthropic.com', '[IA] Anthropic — documentação e políticas oficiais'),
]
LIMITE_DOWNLOAD = 2 * 1024 * 1024


# ------------------------------------------------------------------------------
# Registro
# ------------------------------------------------------------------------------
def assinar(conteudo):
    return hashlib.sha256(json.dumps(conteudo, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def evento(acao, detalhes='', codigo=None, agente=None, usuario_id=None):
    db.session.add(EventoAprendizado(aprendizado_codigo=codigo, acao=acao, detalhes=detalhes, agente=agente,
                                     usuario_id=usuario_id, data=datetime.now()))


def _numero(codigo):
    m = re.fullmatch(r'APR-(\d+)', codigo or '')
    return int(m.group(1)) if m else 0


def _proximo_codigo():
    """Códigos nunca se repetem, nem depois de uma limpeza para compliance (a trilha de eventos guarda os antigos)."""
    usados = [_numero(c) for (c,) in db.session.query(AprendizadoAgente.codigo).all()]
    usados += [_numero(c) for (c,) in db.session.query(EventoAprendizado.aprendizado_codigo).filter(EventoAprendizado.aprendizado_codigo.isnot(None)).all()]
    for texto in (d for (d,) in db.session.query(EventoAprendizado.detalhes).filter(EventoAprendizado.acao == 'Limpeza para compliance').all()):
        usados += [int(n) for n in re.findall(r'APR-(\d+)', texto or '')]
    ultimo = max([_estado('ultimo_codigo', 0)] + usados)
    _gravar_estado('ultimo_codigo', ultimo + 1)
    return f"APR-{ultimo + 1:04d}"


def criar_aprendizado(titulo, tipo, conteudo, destino, descricao='', origem='Detecção interna', fonte_url=None, status='Aplicado',
                      gerente=AGENTE_GERENTE):
    item = AprendizadoAgente(codigo=_proximo_codigo(), titulo=titulo[:200], tipo=tipo, descricao=descricao,
                             conteudo=json.dumps(conteudo, ensure_ascii=False), agentes_destino=json.dumps(destino),
                             origem=origem, fonte_url=fonte_url, status=status, assinatura=assinar(conteudo),
                             criado_em=datetime.now(), aplicado_em=datetime.now() if status == 'Aplicado' else None)
    db.session.add(item)
    db.session.flush()
    evento('Criado' if status == 'Pendente' else 'Criado e aplicado', f"{tipo}: {titulo} → {', '.join(destino)}", item.codigo, gerente)
    return item


def _estado(chave, padrao):
    registro = db.session.get(EstadoConhecimento, chave)
    try:
        return json.loads(registro.valor) if registro and registro.valor else padrao
    except ValueError:
        return padrao


def _gravar_estado(chave, valor):
    registro = db.session.get(EstadoConhecimento, chave) or EstadoConhecimento(chave=chave)
    registro.valor = json.dumps(valor, ensure_ascii=False)
    registro.atualizado_em = datetime.now()
    db.session.add(registro)


# ------------------------------------------------------------------------------
# 1. Detecção interna (autônoma)
# ------------------------------------------------------------------------------
def retrato_da_plataforma():
    perfis = {str(p.id): {'nome': p.nome, 'base': p.perfil_base, 'modulos': sorted(p.lista_modulos()), 'ativo': bool(p.ativo)}
              for p in PerfilPersonalizado.query.all()}
    rotas = sorted({f"{r.endpoint} {r.rule}" for r in current_app.url_map.iter_rules() if r.endpoint != 'static'})
    return {'perfis': perfis, 'rotas': rotas}


def detectar_mudancas(origem=AGENTE_GERENTE):
    """Compara com o último retrato e cria aprendizados aplicados para cada diferença. Devolve a lista criada."""
    from perfis_acesso import MODULOS
    atual = retrato_da_plataforma()
    anterior = _estado('retrato', None)
    criados = []
    if anterior is None:
        criados.append(criar_aprendizado(
            'Linha de base da plataforma registrada', 'linha_base',
            {'rotas': len(atual['rotas']), 'perfis_personalizados': len(atual['perfis'])}, [TODOS],
            f"Primeiro retrato: {len(atual['rotas'])} rotas e {len(atual['perfis'])} perfil(is) personalizado(s).", origem))
        anterior = {'perfis': {}, 'rotas': atual['rotas']}

    for pid, perfil in atual['perfis'].items():
        antes = anterior['perfis'].get(pid)
        conteudo = {'perfil_id': int(pid), **perfil, 'rotulos_modulos': [MODULOS[m][0] for m in perfil['modulos'] if m in MODULOS]}
        if antes is None:
            criados.append(criar_aprendizado(f"Novo perfil de acesso: {perfil['nome']}", 'perfil_novo', conteudo,
                                             ['perfis_personalizados', 'administrador'],
                                             f"Herda de {perfil['base']}; módulos: {', '.join(conteudo['rotulos_modulos'])}.", origem))
        elif antes != perfil:
            mudou = [c for c in ('nome', 'base', 'modulos', 'ativo') if antes.get(c) != perfil.get(c)]
            criados.append(criar_aprendizado(f"Perfil de acesso alterado: {perfil['nome']}", 'perfil_alterado',
                                             {**conteudo, 'antes': antes, 'campos_alterados': mudou},
                                             ['perfis_personalizados', 'administrador'], f"Mudou: {', '.join(mudou)}.", origem))
    for pid, antes in anterior['perfis'].items():
        if pid not in atual['perfis']:
            criados.append(criar_aprendizado(f"Perfil de acesso removido: {antes['nome']}", 'perfil_removido',
                                             {'perfil_id': int(pid), **antes}, ['perfis_personalizados', 'administrador'],
                                             'Os agentes deixam de testar este perfil.', origem))

    novas = sorted(set(atual['rotas']) - set(anterior['rotas']))
    removidas = sorted(set(anterior['rotas']) - set(atual['rotas']))
    if novas:
        criados.append(criar_aprendizado(f"{len(novas)} rota(s) nova(s) na plataforma", 'rota_nova',
                                         {'rotas': [{'endpoint': r.split(' ', 1)[0], 'regra': r.split(' ', 1)[1]} for r in novas]},
                                         ['administrador'], 'O agente Administrador confere se as rotas novas sem parâmetros abrem sem erro.', origem))
    if removidas:
        criados.append(criar_aprendizado(f"{len(removidas)} rota(s) removida(s) da plataforma", 'rota_removida',
                                         {'rotas': removidas}, [TODOS], 'Registro para análise de impacto nos testes.', origem))
    _gravar_estado('retrato', atual)
    _gravar_estado('ultima_deteccao', {'em': datetime.now().isoformat(timespec='seconds'), 'origem': origem, 'novos': len(criados)})
    db.session.commit()
    return criados


# ------------------------------------------------------------------------------
# Consumo pelos agentes
# ------------------------------------------------------------------------------
def aprendizados_para(agente, tipos=None):
    """Aprendizados APLICADOS para este agente (ou para todos), do mais antigo para o mais novo."""
    consulta = AprendizadoAgente.query.filter_by(status='Aplicado')
    if tipos:
        consulta = consulta.filter(AprendizadoAgente.tipo.in_(tipos))
    itens = []
    for a in consulta.order_by(AprendizadoAgente.id).all():
        destino = json.loads(a.agentes_destino or '[]')
        if (TODOS in destino or agente in destino) and assinar(json.loads(a.conteudo)) == a.assinatura:
            itens.append(a)
    return itens


def registrar_consumo(agente, itens):
    if not itens:
        return
    for a in itens:
        a.vezes_consumido = (a.vezes_consumido or 0) + 1
    evento('Consumido pelo agente', ', '.join(a.codigo for a in itens), None, agente)
    db.session.commit()


def perfis_aprendidos():
    """Perfis personalizados ativos conforme os aprendizados aplicados (o agente de perfis testa estes)."""
    perfis = {}
    for a in aprendizados_para('perfis_personalizados', ['perfil_novo', 'perfil_alterado', 'perfil_removido']):
        dados = json.loads(a.conteudo)
        if a.tipo == 'perfil_removido':
            perfis.pop(dados['perfil_id'], None)
        else:
            perfis[dados['perfil_id']] = {**{k: dados[k] for k in ('perfil_id', 'nome', 'base', 'modulos', 'ativo')}, 'aprendizado': a.codigo}
    return [p for p in perfis.values() if p['ativo']]


def referencias_aprovadas(limite=8):
    """Referências oficiais aprovadas: entram no prompt de correção para o LLM."""
    return AprendizadoAgente.query.filter_by(status='Aplicado', tipo='referencia_externa').order_by(AprendizadoAgente.id.desc()).limit(limite).all()


# ------------------------------------------------------------------------------
# 2. Fontes oficiais
# ------------------------------------------------------------------------------
def garantir_fontes_padrao():
    """Inclui cada fonte padrão uma única vez (se o administrador remover uma, ela não volta sozinha)."""
    oferecidas = set(_estado('fontes_oferecidas', [] if FonteConfiavel.query.count() == 0 else [d for d, _ in FONTES_PADRAO[:13]]))
    novas = [(d, desc) for d, desc in FONTES_PADRAO if d not in oferecidas]
    for dominio, descricao in novas:
        if not FonteConfiavel.query.filter_by(dominio=dominio).first():
            db.session.add(FonteConfiavel(dominio=dominio, descricao=descricao, ativa=True))
    if novas:
        _gravar_estado('fontes_oferecidas', sorted(oferecidas | {d for d, _ in novas}))
        db.session.commit()


def dominio_confiavel(url):
    """Só HTTPS e só domínios (ou subdomínios) da lista ativa; nada de IPs nem endereços internos."""
    partes = urlparse(url or '')
    host = (partes.hostname or '').lower()
    if partes.scheme != 'https' or not host:
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    for fonte in FonteConfiavel.query.filter_by(ativa=True).all():
        dominio = fonte.dominio.lower().strip()
        if host == dominio or host.endswith('.' + dominio):
            return fonte
    return None


def _texto_da_pagina(html):
    titulo = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    corpo = re.sub(r'<(script|style|nav|header|footer|noscript)\b.*?</\1>', ' ', html, flags=re.S | re.I)
    # Começa pelo conteúdo principal quando a página o marca (ex.: CWE/MITRE "Description", <main>, <article>)
    inicio = re.search(r'id="Description"|<main\b|<article\b|role="main"', corpo, re.I)
    if inicio:
        corpo = corpo[inicio.start():]
        texto_corrido = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', corpo[:20000])).split())
    paragrafos = [unescape(re.sub(r'<[^>]+>', ' ', p)) for p in re.findall(r'<(?:p|li|h[1-3])\b[^>]*>(.*?)</(?:p|li|h[1-3])>', corpo, re.S | re.I)]
    texto = ' '.join(' '.join(p.split()) for p in paragrafos if len(p.split()) > 3)
    # Prefere os parágrafos de texto (<p>) a listas de navegação/sumário quando houver conteúdo suficiente
    so_paragrafos = ' '.join(' '.join(unescape(re.sub(r'<[^>]+>', ' ', p)).split()) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', corpo, re.S | re.I)
                             if len(p.split()) > 5)
    if len(so_paragrafos) >= 300:
        texto = so_paragrafos
    if inicio and (len(texto) < 200 or inicio.group(0) == 'id="Description"'):
        texto = texto_corrido.removeprefix('id="Description"> ').strip()
    return (unescape(' '.join(titulo.group(1).split())) if titulo else ''), texto


def buscar_fonte_oficial(url, tema, usuario_id=None, gerente=AGENTE_GERENTE, destino=None):
    """Lê uma página de fonte oficial e cria um aprendizado PENDENTE (só vale depois da aprovação)."""
    fonte = dominio_confiavel(url)
    if not fonte:
        evento('Busca recusada', f"Domínio fora da lista de fontes confiáveis: {url}", agente=gerente, usuario_id=usuario_id)
        db.session.commit()
        raise ValueError('domínio fora da lista de fontes confiáveis (ou endereço sem HTTPS)')
    pedido = Request(url, headers={'User-Agent': 'MentoriaAgenteGerenteTecnico/1.0' if gerente == AGENTE_GERENTE else 'MentoriaGerenteSeguranca/1.0'})
    with urlopen(pedido, timeout=15) as resposta:
        if not dominio_confiavel(resposta.geturl()):
            raise ValueError('a página redirecionou para fora das fontes confiáveis')
        tipo = resposta.headers.get('Content-Type', '')
        if 'html' not in tipo and 'text' not in tipo:
            raise ValueError('a página não é texto/HTML')
        html = resposta.read(LIMITE_DOWNLOAD).decode(resposta.headers.get_content_charset() or 'utf-8', errors='replace')
    titulo, texto = _texto_da_pagina(html)
    resumo = texto[:2500]
    conteudo = {'tema': tema, 'titulo_pagina': titulo, 'url': url, 'dominio': fonte.dominio, 'resumo': resumo,
                'lido_em': datetime.now().isoformat(timespec='seconds')}
    item = criar_aprendizado(f"Referência oficial: {tema or titulo}"[:200], 'referencia_externa', conteudo, destino or [TODOS],
                             f"{fonte.descricao or fonte.dominio} — {titulo}", f"Fonte oficial ({fonte.dominio})", url, status='Pendente',
                             gerente=gerente)
    db.session.commit()
    return item


# ------------------------------------------------------------------------------
# 3. Governança
# ------------------------------------------------------------------------------
def revisar(item, acao, usuario_id, motivo=''):
    """aprovar (Pendente → Aplicado), rejeitar (Pendente → Rejeitado), revogar (Aplicado → Revogado), reaplicar."""
    transicoes = {'aprovar': ('Pendente', 'Aplicado', 'Aprovado'), 'rejeitar': ('Pendente', 'Rejeitado', 'Rejeitado'),
                  'revogar': ('Aplicado', 'Revogado', 'Revogado'), 'reaplicar': ('Revogado', 'Aplicado', 'Reaplicado')}
    if acao not in transicoes or item.status != transicoes[acao][0]:
        return False
    item.status = transicoes[acao][1]
    item.revisado_por_id, item.revisado_em, item.motivo = usuario_id, datetime.now(), motivo or item.motivo
    if item.status == 'Aplicado':
        item.aplicado_em = datetime.now()
    evento(transicoes[acao][2], motivo, item.codigo, usuario_id=usuario_id)
    db.session.commit()
    return True


def pasta_auditoria():
    pasta = os.path.join(current_app.instance_path, 'agentes_conhecimento', 'auditoria')
    os.makedirs(pasta, exist_ok=True)
    return pasta


def linhas_csv(itens):
    cabecalho = ['Código', 'Título', 'Tipo', 'Status', 'Agentes', 'Origem', 'Fonte', 'Criado em', 'Aplicado em',
                 'Revisado por', 'Revisado em', 'Motivo', 'Vezes consumido', 'Assinatura SHA-256']
    linhas = [[a.codigo, a.titulo, a.tipo, a.status, ', '.join(json.loads(a.agentes_destino or '[]')), a.origem, a.fonte_url or '',
               a.criado_em.strftime('%d/%m/%Y %H:%M') if a.criado_em else '', a.aplicado_em.strftime('%d/%m/%Y %H:%M') if a.aplicado_em else '',
               a.revisado_por.nome if a.revisado_por else '', a.revisado_em.strftime('%d/%m/%Y %H:%M') if a.revisado_em else '',
               a.motivo or '', a.vezes_consumido or 0, a.assinatura] for a in itens]
    return cabecalho, linhas


def limpar(itens, usuario_id, usuario_nome, escopo):
    """Limpeza para compliance: exporta JSON e CSV, apaga e deixa o evento com o retrato do que saiu."""
    if not itens:
        return 0, None
    carimbo = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = os.path.join(pasta_auditoria(), f"limpeza_aprendizados_{carimbo}")
    with open(base + '.json', 'w', encoding='utf-8') as f:
        json.dump([{'codigo': a.codigo, 'titulo': a.titulo, 'tipo': a.tipo, 'status': a.status, 'destino': json.loads(a.agentes_destino),
                    'origem': a.origem, 'fonte_url': a.fonte_url, 'conteudo': json.loads(a.conteudo), 'assinatura': a.assinatura,
                    'criado_em': a.criado_em.isoformat() if a.criado_em else None} for a in itens], f, ensure_ascii=False, indent=1)
    cabecalho, linhas = linhas_csv(itens)
    with open(base + '.csv', 'w', newline='', encoding='utf-8-sig') as f:
        escritor = csv.writer(f, delimiter=';')
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)
    codigos = [a.codigo for a in itens]
    for a in itens:
        db.session.delete(a)
    evento('Limpeza para compliance', f"{len(codigos)} aprendizado(s) apagado(s) por {usuario_nome} ({escopo}): {', '.join(codigos)}. "
                                      f"Cópia: {os.path.basename(base)}.json/.csv", usuario_id=usuario_id)
    db.session.commit()
    return len(codigos), os.path.basename(base)
