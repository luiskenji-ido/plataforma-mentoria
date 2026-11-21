# -*- coding: utf-8 -*-
"""
AGENTE DE PREÇOS E MODELOS DE IA — confere uma vez por dia e mantém o catálogo da tela Provedores de IA atualizado
==================================================================================================================
1. Preços: lê a tabela pública de preços por modelo (FONTE_PRECOS, mantida pela comunidade a partir das páginas
   oficiais do Claude, do Google e da OpenAI; outra fonte pode ser indicada em PRECOS_IA_FONTE_URL). Preço que mudou é
   aplicado sozinho; mudança grande demais (mais que VARIACAO_MAXIMA vezes) fica para o Administrador conferir.
   Preço digitado na tela continua valendo mais (o log avisa quando ele ficou diferente do oficial).
2. Modelos: com a chave do provedor cadastrada, pergunta ao próprio provedor a lista de modelos (não gasta tokens).
   Modelo da plataforma que sumiu do provedor = "fora do ar" (a reserva da ordem assume); modelo novo da mesma geração
   ou mais nova entra na lista da tela (com o preço da fonte, quando houver).
Tudo vira linha no log (LogCatalogoIA), mostrado em Provedores de IA › Atualizações automáticas.

Roda na tarefa de hora em hora (tarefas_agendadas.py), de fato só a cada HORAS_ENTRE_CONFERENCIAS; o botão
"Conferir agora" da tela força a conferência. Não usa IA (nenhuma chamada gera custo).
"""
import os
import re
from datetime import datetime, timedelta

FONTE_PRECOS = 'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json'
HORAS_ENTRE_CONFERENCIAS = 24
VARIACAO_MAXIMA = 3.0
TEMPO_LIMITE = 20
PREFIXO_FONTE = {'claude': ['anthropic/', ''], 'gemini': ['gemini/', ''], 'openai': ['openai/', '']}
CHAVE_ULTIMA = 'catalogo:ultima_conferencia'
NOME = 'Agente de Preços e Modelos de IA'


# ------------------------------------------------------------------------------
# Fontes (cada uma pode ser trocada nos testes)
# ------------------------------------------------------------------------------
def baixar_precos(url=None):
    import requests
    resposta = requests.get(url or os.environ.get('PRECOS_IA_FONTE_URL') or FONTE_PRECOS, timeout=TEMPO_LIMITE,
                            headers={'User-Agent': 'plataforma-mentoria/catalogo-ia'})
    resposta.raise_for_status()
    dados = resposta.json()
    if not isinstance(dados, dict):
        raise ValueError('a fonte de preços não devolveu uma tabela')
    return dados


def listar_modelos_do_provedor(provedor):
    """[(id, nome)] direto do provedor (lista de modelos da API: não gasta tokens)."""
    if provedor == 'claude':
        import anthropic
        cliente = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY') or None,
                                      auth_token=os.environ.get('ANTHROPIC_AUTH_TOKEN') or None, timeout=TEMPO_LIMITE)
        return [(m.id, getattr(m, 'display_name', None) or m.id) for m in cliente.models.list(limit=1000)]
    if provedor == 'openai':
        import openai
        cliente = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'), timeout=TEMPO_LIMITE)
        return [(m.id, m.id) for m in cliente.models.list()]
    if provedor == 'gemini':
        from google import genai
        cliente = genai.Client(api_key=os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY'))
        lista = []
        for m in cliente.models.list():
            acoes = getattr(m, 'supported_actions', None) or []
            if acoes and 'generateContent' not in acoes:
                continue
            lista.append(((m.name or '').split('/')[-1], getattr(m, 'display_name', None) or m.name))
        return lista
    return []


# ------------------------------------------------------------------------------
# Regras
# ------------------------------------------------------------------------------
def versao(mid):
    """Geração do modelo pelo identificador: claude-sonnet-5-5 → 5.5, gemini-3.6-flash → 3.6, gpt-6.2-sol → 6.2."""
    achado = re.search(r'(\d+)(?:[.-](\d+))?', mid)
    if not achado:
        return 0.0
    menor = achado.group(2) if achado.group(2) and len(achado.group(2)) <= 2 else '0'
    return float(f'{achado.group(1)}.{menor}')


def modelo_de_texto(provedor, mid):
    """Só modelos de conversa/texto, sem versões datadas, prévias ou variantes de áudio, imagem e embeddings."""
    if re.search(r'-\d{8}$|-\d{4}-\d{2}-\d{2}$|-\d{3}$|latest|preview|exp|tts|audio|realtime|transcribe|image|embedding|search|live|instruct|vision|codex',
                 mid):
        return False
    return {'claude': mid.startswith('claude-'), 'gemini': mid.startswith('gemini-'),
            'openai': bool(re.match(r'^gpt-\d', mid))}.get(provedor, False)


def preco_da_fonte(tabela, provedor, mid):
    """(entrada, saída) em US$ por milhão de tokens, ou None."""
    for prefixo in PREFIXO_FONTE.get(provedor, ['']):
        item = tabela.get(prefixo + mid)
        if isinstance(item, dict) and item.get('input_cost_per_token') is not None and item.get('output_cost_per_token') is not None:
            try:
                return round(float(item['input_cost_per_token']) * 1_000_000, 4), round(float(item['output_cost_per_token']) * 1_000_000, 4)
            except (TypeError, ValueError):
                return None
    return None


def _formatar(par):
    return '—' if not par or par[0] is None else f'US$ {par[0]:g} / {par[1]:g}'


def _variacao_aceitavel(antes, depois):
    for a, d in zip(antes, depois, strict=False):
        if a in (None, 0) or d in (None, 0):
            continue
        razao = d / a
        if razao > VARIACAO_MAXIMA or razao < 1 / VARIACAO_MAXIMA:
            return False
    return True


# ------------------------------------------------------------------------------
# Conferência
# ------------------------------------------------------------------------------
def _log(tipo, provedor=None, modelo=None, antes=None, depois=None, aplicado=False, detalhe=None, fonte=None):
    from models import db, LogCatalogoIA
    db.session.add(LogCatalogoIA(data=datetime.now(), tipo=tipo, provedor=provedor, modelo=modelo, antes=antes, depois=depois,
                                 aplicado=aplicado, detalhe=detalhe, fonte=(fonte or '')[:255] or None))


def ultima_conferencia():
    import provedores_ia
    return provedores_ia._ler(CHAVE_ULTIMA, None)


def precisa_conferir(agora=None):
    ultima = ultima_conferencia() or {}
    try:
        quando = datetime.fromisoformat(ultima.get('data', ''))
    except ValueError:
        return True
    return (agora or datetime.now()) - quando >= timedelta(hours=HORAS_ENTRE_CONFERENCIAS)


def conferir(forcar=False, quem=None, baixar=baixar_precos, listar=listar_modelos_do_provedor, agora=None):
    """Confere preços e modelos. Devolve o resumo (dict) ou None quando ainda não é hora (sem forcar)."""
    import provedores_ia
    from models import db
    agora = agora or datetime.now()
    if not forcar and not precisa_conferir(agora):
        return None
    quem = quem or f'{NOME} (tarefa diária)'
    fonte_url = os.environ.get('PRECOS_IA_FONTE_URL') or FONTE_PRECOS
    resumo = {'precos_atualizados': 0, 'precos_para_revisar': 0, 'modelos_novos': 0, 'modelos_fora_do_ar': 0,
              'provedores_conferidos': [], 'provedores_sem_chave': [], 'erros': []}

    # 1. Preços
    automaticos = provedores_ia._ler('precos_automaticos', {})
    da_tela = provedores_ia._ler('precos', {})
    tabela = None
    try:
        tabela = baixar(fonte_url)
    except Exception as erro:
        resumo['erros'].append(f'Fonte de preços indisponível: {type(erro).__name__}')
        _log('erro', detalhe=f'Fonte de preços indisponível ({type(erro).__name__}: {str(erro)[:200]}). Os preços atuais continuam valendo.',
             fonte=fonte_url)

    def aplicar_preco(mid, provedor, atual):
        novo = preco_da_fonte(tabela, provedor, mid)
        if not novo:
            return
        if atual[0] is not None and abs(novo[0] - atual[0]) < 0.00005 and abs(novo[1] - atual[1]) < 0.00005:
            return
        if atual[0] is not None and not _variacao_aceitavel(atual, novo):
            resumo['precos_para_revisar'] += 1
            _log('preco_revisar', provedor, mid, _formatar(atual), _formatar(novo), False,
                 f'Mudança maior que {VARIACAO_MAXIMA:g}x: não aplicada. Confira no site do provedor e, se estiver certa, digite na tela.',
                 fonte_url)
            return
        automaticos[mid] = {'entrada': novo[0], 'saida': novo[1], 'data': agora.isoformat(timespec='minutes')}
        resumo['precos_atualizados'] += 1
        detalhe = 'Preço atualizado pela fonte.'
        if isinstance(da_tela.get(mid), list) and any(v is not None for v in da_tela[mid]):
            detalhe += ' Atenção: o preço digitado na tela continua valendo; apague-o para seguir o oficial.'
        _log('preco', provedor, mid, _formatar(atual), _formatar(novo), True, detalhe, fonte_url)

    # 2. Modelos (com chave), antes dos preços para os novos já entrarem com preço
    catalogo = provedores_ia.modelos(hoje=agora, precos_da_tela=False)
    extras = provedores_ia._ler('modelos_extras', {})
    ausentes = []
    for provedor in provedores_ia.PROVEDORES:
        if not provedores_ia.chave_configurada(provedor):
            resumo['provedores_sem_chave'].append(provedor)
            continue
        try:
            lista = listar(provedor)
        except Exception as erro:
            resumo['erros'].append(f'{provedor}: {type(erro).__name__}')
            _log('erro', provedor, detalhe=f'Lista de modelos indisponível ({type(erro).__name__}: {str(erro)[:200]}).')
            continue
        ids = {mid for mid, _ in lista}
        if not ids:
            continue
        resumo['provedores_conferidos'].append(provedor)
        do_provedor = {m: d for m, d in catalogo.items() if d['provedor'] == provedor}
        for mid in do_provedor:
            if mid not in ids:
                ausentes.append(mid)
                usos = [provedores_ia.USOS[u][0] for u in provedores_ia.USOS if mid in provedores_ia.ordem(u)]
                resumo['modelos_fora_do_ar'] += 1
                _log('modelo_ausente', provedor, mid, None, None, False,
                     'O provedor não lista mais este modelo.' + (f" Está na ordem de: {', '.join(usos)} — a reserva assume; "
                                                                  'troque o modelo na tela.' if usos else ''))
        geracao = min((versao(m) for m in do_provedor), default=0)
        for mid, nome in lista:
            if mid in catalogo or not modelo_de_texto(provedor, mid) or versao(mid) < geracao:
                continue
            extras[mid] = {'provedor': provedor, 'nome': (nome or mid)[:80]}
            catalogo[mid] = {'provedor': provedor, 'entrada': None, 'saida': None}
            resumo['modelos_novos'] += 1
            preco = preco_da_fonte(tabela, provedor, mid) if tabela else None
            _log('modelo_novo', provedor, mid, None, _formatar(preco) if preco else 'sem preço na fonte', True,
                 'Modelo novo do provedor incluído na lista da tela' + ('' if preco else ': preencha o preço.'))

    if tabela:
        for mid, dados in catalogo.items():
            atual = (dados.get('entrada'), dados.get('saida'))
            aplicar_preco(mid, dados['provedor'], atual)

    provedores_ia._gravar('modelos_extras', extras)
    provedores_ia._gravar('precos_automaticos', automaticos)
    provedores_ia._gravar('modelos_ausentes', sorted(ausentes))
    partes = [f"{resumo['precos_atualizados']} preço(s) atualizado(s)", f"{resumo['modelos_novos']} modelo(s) novo(s)",
              f"{resumo['modelos_fora_do_ar']} fora do ar", f"{resumo['precos_para_revisar']} para revisar"]
    if resumo['provedores_sem_chave']:
        partes.append('sem chave (modelos não conferidos): ' + ', '.join(resumo['provedores_sem_chave']))
    _log('conferencia', detalhe=f'{quem}: ' + '; '.join(partes) + '.', aplicado=True, fonte=fonte_url if tabela else None)
    provedores_ia._gravar(CHAVE_ULTIMA, {'data': agora.isoformat(timespec='minutes'), 'resumo': resumo})
    db.session.commit()
    return resumo


def log_recente(limite=40):
    from models import LogCatalogoIA
    return LogCatalogoIA.query.order_by(LogCatalogoIA.id.desc()).limit(limite).all()
