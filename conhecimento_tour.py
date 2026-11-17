# -*- coding: utf-8 -*-
"""
CONHECIMENTO DO TOUR — o que o Agente Gerente Técnico aprende com os testes do tour e ensina aos agentes OmniTest
================================================================================================================
Mesmas regras de governança dos outros gerentes (conhecimento.py): assinatura SHA-256, trilha de eventos,
revogação e limpeza para compliance na tela Governança de aprendizados.

1. Mapa do tour (tour_mapa, aplicado na hora): para cada perfil, as páginas do menu e, em cada página, as abas, os botões
   principais e as seções que existem. Na execução seguinte o agente do perfil cobra o mapa: página que sumiu do tour,
   aba ou botão que desapareceu viram falha ou alerta, mesmo que hoje a tela esteja diferente.
2. Erros do tour (tour_falha, aplicado na hora): as páginas em que o tour ficou incompleto (aba não aberta, botão ou seção
   sem explicação, balão solto ou cortado) e o que faltou. O agente verifica primeiro esses pontos; quando o erro some,
   o Gerente revoga o aprendizado com o motivo "corrigido" (fica no histórico).
3. Fontes oficiais (PENDENTE até um Administrador aprovar): a documentação do Intro.js e o padrão de abas da W3C (WAI-ARIA),
   para orientar a correção do tour.

Todas as funções rodam dentro de um app_context.
"""
import json
from datetime import datetime

import conhecimento
from conhecimento import criar_aprendizado, assinar, evento
from models import db, AprendizadoAgente

GERENTE = conhecimento.AGENTE_GERENTE
TIPO_MAPA = 'tour_mapa'
TIPO_FALHA = 'tour_falha'
REFERENCIAS = [
    ('https://introjs.com/docs', 'Intro.js: passos, posicionamento do balão e rolagem do tour'),
    ('https://www.w3.org/WAI/ARIA/apg/patterns/tabs/', 'W3C WAI-ARIA: padrão de abas (tabs) acessíveis'),
    ('https://www.w3.org/WAI/WCAG22/quickref/', 'W3C WCAG 2.2: referência rápida de acessibilidade'),
]


def _vigente(tipo, agente):
    """Último aprendizado aplicado deste tipo para o agente."""
    for item in AprendizadoAgente.query.filter_by(status='Aplicado', tipo=tipo).order_by(AprendizadoAgente.id.desc()).all():
        if agente in json.loads(item.agentes_destino or '[]'):
            return item
    return None


def _substituir(item, motivo):
    item.status = 'Revogado'
    item.revisado_em = datetime.now()
    item.motivo = motivo
    evento('Revogado', motivo, item.codigo, GERENTE)


def _propor_referencias():
    """Uma vez: as fontes oficiais do tour ficam PENDENTES na Governança até um Administrador aprovar."""
    for url, tema in REFERENCIAS:
        if AprendizadoAgente.query.filter_by(tipo='referencia_externa', fonte_url=url).first():
            continue
        criar_aprendizado(f'Referência oficial: {tema}', 'referencia_externa', {'url': url, 'tema': tema, 'assunto': 'tour'},
                          [conhecimento.TODOS], descricao='Proposta pelo Gerente Técnico depois de erros no tour.',
                          origem='Fonte oficial (tour)', fonte_url=url, status='Pendente', gerente=GERENTE)


def aprender_com_tour(agente, perfil, paginas_do_menu, mapa, problemas):
    """agente = chave do agente OmniTest; mapa = {caminho: {abas, botoes, secoes}} desta execução;
    problemas = {caminho: [textos]} desta execução. Devolve o resumo do que o Gerente aprendeu e ensinou."""
    resumo = {'mapa': 'igual', 'novos': [], 'persistentes': [], 'corrigidos': [], 'codigos': []}

    # 1. Mapa: páginas do menu atual (as que saíram do menu deixam de ser cobradas)
    atual = _vigente(TIPO_MAPA, agente)
    paginas = dict(json.loads(atual.conteudo).get('paginas', {})) if atual else {}
    paginas.update({p: v for p, v in mapa.items() if v})
    if paginas_do_menu:
        paginas = {p: v for p, v in paginas.items() if p in paginas_do_menu}
    conteudo = {'perfil': perfil, 'paginas': paginas, 'menu': list(paginas_do_menu or [])}
    if paginas and (atual is None or assinar(conteudo) != atual.assinatura):
        if atual:
            _substituir(atual, 'Mapa do tour atualizado pelo Gerente Técnico')
        item = criar_aprendizado(f'Mapa do tour: {perfil} ({len(paginas)} páginas)', TIPO_MAPA, conteudo, [agente],
                                 descricao='Páginas do menu e, em cada uma, as abas, os botões principais e as seções que o tour precisa explicar.',
                                 origem='Gerente Técnico (teste do tour)', gerente=GERENTE)
        resumo['mapa'] = 'novo' if atual is None else 'atualizado'
        resumo['codigos'].append(item.codigo)

    # 2. Erros do tour: novos, que continuam e corrigidos
    anterior = _vigente(TIPO_FALHA, agente)
    antes = json.loads(anterior.conteudo).get('paginas', {}) if anterior else {}
    # problemas traz TODAS as páginas visitadas ([] = sem erro); página não visitada nesta execução mantém o erro anterior
    agora = {p: lista for p, lista in problemas.items() if lista}
    agora.update({p: lista for p, lista in antes.items() if p not in problemas})
    resumo['corrigidos'] = sorted(p for p in antes if p not in agora)
    resumo['persistentes'] = sorted(p for p in agora if p in antes)
    resumo['novos'] = sorted(p for p in agora if p not in antes)
    conteudo_falha = {'perfil': perfil, 'paginas': agora}
    if anterior and (not agora or assinar(conteudo_falha) != anterior.assinatura):
        _substituir(anterior, 'Erros do tour corrigidos' if not agora else 'Erros do tour atualizados (ver o aprendizado novo)')
    if agora and (anterior is None or assinar(conteudo_falha) != anterior.assinatura):
        item = criar_aprendizado(f'Tour incompleto: {perfil} ({len(agora)} página(s))', TIPO_FALHA, conteudo_falha, [agente],
                                 descricao='Páginas em que o tour não abriu abas, deixou botões ou seções sem explicação ou mostrou o balão '
                                           'fora do lugar. O agente confere estes pontos primeiro na próxima execução.',
                                 origem='Gerente Técnico (teste do tour)', gerente=GERENTE)
        resumo['codigos'].append(item.codigo)
        _propor_referencias()
    db.session.commit()
    return resumo


def ensinado_para(agente):
    """O que o agente recebe antes do teste: (mapa {caminho: {...}}, erros {caminho: [...]}, códigos)."""
    mapa = _vigente(TIPO_MAPA, agente)
    falha = _vigente(TIPO_FALHA, agente)
    return ((json.loads(mapa.conteudo).get('paginas', {}) if mapa else {}),
            (json.loads(falha.conteudo).get('paginas', {}) if falha else {}),
            {'mapa': mapa.codigo if mapa else None, 'falha': falha.codigo if falha else None})
