# -*- coding: utf-8 -*-
"""
PROVEDORES DE IA — um só lugar para escolher modelos, controlar o custo e trocar de provedor
==========================================================================================
Cada USO da plataforma (Assistente da Plataforma, Assistente do Acompanhamento, Agente Orquestrador) tem uma ordem de
modelos: o primeiro responde; se falhar ou estiver sem chave, tenta o próximo (reserva). A ordem e os preços são
escolhidos pelo Administrador na tela Administração › Sistema › Provedores de IA.

Custo: cada chamada fica registrada (UsoIA) com tokens e custo em US$, pelos preços da tela. O gasto do mês é comparado
ao teto (Parâmetros de regras › ia_teto_mensal_usd): ao atingir o teto as IAs param até o mês seguinte e os
Administradores são avisados (também quando passa do aviso, ia_aviso_teto_pct). Teto zero desliga as IAs.

Provedores: Claude (ANTHROPIC_API_KEY), Gemini (GEMINI_API_KEY ou GOOGLE_API_KEY) e ChatGPT/OpenAI (OPENAI_API_KEY),
todas cadastradas em Provedores de IA e custos › Credenciais. O Orquestrador roda em outro processo: ele grava o consumo em
instance/uso_ia_externo.jsonl, que é importado aqui (importar_uso_externo).

Todas as funções rodam dentro de um app_context.
"""
import os
import re
import json
from datetime import datetime, timedelta

PROVEDORES = {
    'claude': ('Claude (Anthropic)', ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN')),
    'gemini': ('Gemini (Google)', ('GEMINI_API_KEY', 'GOOGLE_API_KEY')),
    'openai': ('ChatGPT (OpenAI)', ('OPENAI_API_KEY',)),
}

# Modelos conhecidos: id → (provedor, nome, preço de entrada, preço de saída) em US$ por milhão de tokens, preço padrão
# (Standard / camada paga) de texto. Conferidos nas páginas oficiais em PRECOS_CONFERIDOS_EM:
#   platform.claude.com/docs/en/about-claude/pricing · aistudio.google.com/docs/pricing · developers.openai.com/api/docs/pricing
# O Administrador pode corrigir qualquer preço na tela (o da tela vale mais que o daqui).
PRECOS_CONFERIDOS_EM = '19/11/2026'
MODELOS_PADRAO = {
    'claude-haiku-5-5': ('claude', 'Claude Haiku 5.5 (mais barato)', 0.10, 0.50),
    'claude-sonnet-5-5': ('claude', 'Claude Sonnet 5.5 (equilibrado)', 2.00, 10.00),
    'claude-opus-5-5': ('claude', 'Claude Opus 5.5 (mais capaz)', 4.00, 20.00),
    'gemini-3.5-flash-lite': ('gemini', 'Gemini 3.5 Flash-Lite (mais barato)', 0.30, 2.50),
    'gemini-3.6-flash': ('gemini', 'Gemini 3.6 Flash', 0.75, 3.75),
    'gemini-3.8-flash': ('gemini', 'Gemini 3.8 Flash (Flash mais novo)', 0.75, 3.75),
    'gemini-4-hydrogen': ('gemini', 'Gemini 4 Hydrogen (equilibrado)', 1.50, 7.50),
    'gpt-6-luna': ('openai', 'GPT-6 Luna (mais barato)', 0.10, 0.50),
    'gpt-6.1-terra': ('openai', 'GPT-6.1 Terra', 1.00, 5.00),
    'gpt-6.2-sol': ('openai', 'GPT-6.2 Sol (equilibrado)', 2.00, 10.00),
    'gpt-6.2-astra': ('openai', 'GPT-6.2 Astra (mais capaz)', 8.00, 40.00),
}
# Reajustes já anunciados pelo provedor: a partir da data, o preço padrão passa a ser este (o da tela continua valendo
# se o Administrador tiver preenchido outro). A tela mostra o aviso antes da data.
REAJUSTES = {
    'gemini-3.6-flash': ('2027-01-01', 1.50, 7.50),
    'gemini-3.8-flash': ('2027-01-01', 1.50, 7.50),
}
# Modelos que saíram do catálogo: quem tinha o antigo na ordem passa a usar o substituto (sem a ordem ficar vazia)
SUBSTITUIDOS = {
    'gemini-flash-lite-latest': 'gemini-3.5-flash-lite',  # o Google pede id estável em produção; o "latest" muda sozinho
    'gemini-2.5-flash': 'gemini-3.5-flash-lite',           # descontinuado: o Google redireciona em 01/12/2026
    'gemini-2.5-pro': 'gemini-3.8-flash',                  # descontinuado: o Google redireciona em 01/12/2026
}

USOS = {
    'assistente': ('Assistente da Plataforma', 'Responde o Administrador com base na base de conhecimento.',
                   ['claude-haiku-5-5', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']),
    'acompanhamento': ('Assistente do Acompanhamento', 'Tira dúvidas de jovens e mentores sobre os estudos.',
                       ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'claude-haiku-5-5']),
    'orquestrador': ('Agente Orquestrador', 'Corrige o código a partir dos achados dos agentes (precisa de modelo forte).',
                     ['claude-sonnet-5-5', 'gemini-3.6-flash', 'gpt-6.2-sol']),
}
MAXIMO_NA_ORDEM = 3
PRECO_MAXIMO_POR_MILHAO = 1000  # US$ por milhão de tokens: acima disso o preço digitado na tela é recusado (erro de digitação)
ID_MODELO = re.compile(r'^[a-z0-9][a-z0-9.\-]{2,79}$')


class IAIndisponivel(Exception):
    """Nenhum modelo da ordem respondeu (motivos juntos na mensagem)."""


class OrcamentoEsgotado(IAIndisponivel):
    """O gasto do mês chegou ao teto (ou o teto é zero)."""


class IADesligada(IAIndisponivel):
    """O Administrador desligou a IA deste uso na tela Provedores de IA."""


class FalhaProvedor(Exception):
    pass


class Resposta:
    def __init__(self, texto, provedor, modelo, tokens_entrada, tokens_saida, custo_usd, bruto=None):
        self.texto, self.provedor, self.modelo = texto, provedor, modelo
        self.tokens_entrada, self.tokens_saida, self.custo_usd, self.bruto = tokens_entrada, tokens_saida, custo_usd, bruto


# ------------------------------------------------------------------------------
# Configuração (banco)
# ------------------------------------------------------------------------------
def _ler(chave, padrao):
    from models import ConfiguracaoIA
    item = ConfiguracaoIA.query.filter_by(chave=chave).first()
    if not item:
        return padrao
    try:
        return json.loads(item.valor)
    except ValueError:
        return padrao


def _gravar(chave, valor, usuario_id=None):
    from models import db, ConfiguracaoIA
    item = ConfiguracaoIA.query.filter_by(chave=chave).first() or ConfiguracaoIA(chave=chave)
    item.valor = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    item.atualizado_por_id = usuario_id
    db.session.add(item)
    db.session.commit()


def modelos(hoje=None, precos_da_tela=True):
    """Todos os modelos (padrão + cadastrados), com os preços da tela: {id: {provedor, nome, entrada, saida, extra,
    reajuste}}. Preço em branco na tela não apaga o preço padrão (só um número preenchido o substitui); reajuste
    anunciado passa a valer sozinho na data."""
    hoje = (hoje or datetime.now()).strftime('%Y-%m-%d')
    precos = _ler('precos', {}) if precos_da_tela else {}
    lista = {}
    for mid, (prov, nome, ent, sai) in MODELOS_PADRAO.items():
        reajuste = None
        if mid in REAJUSTES:
            data, novo_ent, novo_sai = REAJUSTES[mid]
            if hoje >= data:
                ent, sai = novo_ent, novo_sai
            else:
                reajuste = {'data': datetime.strptime(data, '%Y-%m-%d').strftime('%d/%m/%Y'), 'entrada': novo_ent, 'saida': novo_sai}
        lista[mid] = {'provedor': prov, 'nome': nome, 'entrada': ent, 'saida': sai, 'extra': False, 'reajuste': reajuste}
    for mid, dados in _ler('modelos_extras', {}).items():
        if dados.get('provedor') in PROVEDORES and mid not in lista:
            lista[mid] = {'provedor': dados['provedor'], 'nome': dados.get('nome') or mid, 'entrada': None, 'saida': None,
                          'extra': True, 'reajuste': None}
    for mid, valores in precos.items():
        if mid in lista and isinstance(valores, list) and len(valores) == 2:
            if valores[0] is not None:
                lista[mid]['entrada'] = valores[0]
            if valores[1] is not None:
                lista[mid]['saida'] = valores[1]
    return lista


def ordem(uso):
    """Modelos do uso, na ordem de tentativa (só os que existem no catálogo; os que saíram viram o substituto)."""
    catalogo = modelos()
    escolhidos = []
    for m in _ler(f'uso:{uso}', None) or USOS[uso][2]:
        m = SUBSTITUIDOS.get(m, m)
        if m in catalogo and m not in escolhidos:
            escolhidos.append(m)
    return escolhidos[:MAXIMO_NA_ORDEM] or [m for m in USOS[uso][2] if m in catalogo]


def salvar_ordem(uso, lista, usuario_id=None):
    if uso not in USOS:
        raise ValueError('Uso desconhecido.')
    catalogo = modelos()
    limpa = []
    for m in lista:
        m = (m or '').strip()
        if not m:
            continue
        if m not in catalogo:
            raise ValueError(f'Modelo desconhecido: {m}.')
        if m in limpa:
            raise ValueError('O mesmo modelo aparece duas vezes na ordem.')
        limpa.append(m)
    if not limpa:
        raise ValueError('Escolha pelo menos um modelo.')
    _gravar(f'uso:{uso}', limpa[:MAXIMO_NA_ORDEM], usuario_id)
    return limpa


def _preco(texto):
    texto = (str(texto or '')).strip().replace(',', '.')
    if not texto:
        return None
    valor = float(texto)
    if not 0 <= valor <= PRECO_MAXIMO_POR_MILHAO:
        raise ValueError
    return round(valor, 4)


def salvar_precos(valores, usuario_id=None):
    """valores = {modelo: (entrada, saida)} em texto. Só fica gravado o que o Administrador mudou em relação ao preço
    padrão (vazio ou igual ao padrão = segue o padrão), para os preços conferidos e os reajustes do código continuarem
    valendo depois de salvar a tela."""
    padrao = modelos(precos_da_tela=False)
    precos = {}
    for mid, (ent, sai) in valores.items():
        if mid not in padrao:
            continue
        try:
            novo = [_preco(ent), _preco(sai)]
        except ValueError:
            raise ValueError(f'Preço inválido para {mid}: use números de 0 a 1000 (US$ por milhão de tokens).') from None
        novo = [None if v == padrao[mid][campo] else v for v, campo in zip(novo, ('entrada', 'saida'), strict=False)]
        if novo != [None, None]:
            precos[mid] = novo
    _gravar('precos', precos, usuario_id)


def adicionar_modelo(provedor, mid, nome, usuario_id=None):
    mid = (mid or '').strip().lower()
    if provedor not in PROVEDORES:
        raise ValueError('Provedor inválido.')
    if not ID_MODELO.match(mid):
        raise ValueError('Identificador de modelo inválido (use letras minúsculas, números, ponto e hífen, como no site do provedor).')
    if mid in modelos():
        raise ValueError('Esse modelo já está na lista.')
    extras = _ler('modelos_extras', {})
    extras[mid] = {'provedor': provedor, 'nome': (nome or mid).strip()[:80]}
    _gravar('modelos_extras', extras, usuario_id)


def remover_modelo(mid, usuario_id=None):
    extras = _ler('modelos_extras', {})
    if mid not in extras:
        raise ValueError('Só modelos cadastrados na tela podem ser removidos.')
    for uso in USOS:
        if mid in (_ler(f'uso:{uso}', None) or []):
            raise ValueError(f'Tire o modelo da ordem de "{USOS[uso][0]}" antes de removê-lo.')
    extras.pop(mid)
    _gravar('modelos_extras', extras, usuario_id)


def ativo(uso):
    """Cada uso pode ser ligado ou desligado na tela (padrão: ligado)."""
    return bool(_ler('ativos', {}).get(uso, True))


def definir_ativo(uso, ligado, usuario_id=None):
    if uso not in USOS:
        raise ValueError('Uso desconhecido.')
    ativos = _ler('ativos', {})
    ativos[uso] = bool(ligado)
    _gravar('ativos', ativos, usuario_id)


def chave_configurada(provedor):
    return any(os.environ.get(v) for v in PROVEDORES[provedor][1])


def modelo_de_provedor(uso, provedor):
    """Primeiro modelo do provedor na ordem do uso (o Orquestrador escolhe o provedor na tela dele)."""
    catalogo = modelos()
    # ordem salva na tela → ordem padrão do uso (ex.: gpt-6.2-sol para o Orquestrador) → qualquer modelo do provedor
    for m in ordem(uso) + USOS[uso][2] + list(catalogo):
        if catalogo.get(m, {}).get('provedor') == provedor:
            return m
    return None


# ------------------------------------------------------------------------------
# Custo e teto
# ------------------------------------------------------------------------------
def custo(modelo, tokens_entrada, tokens_saida):
    info = modelos().get(modelo) or {}
    ent, sai = info.get('entrada'), info.get('saida')
    if ent is None or sai is None:
        return 0.0
    return round((tokens_entrada or 0) / 1_000_000 * ent + (tokens_saida or 0) / 1_000_000 * sai, 6)


def _inicio_do_mes(agora=None):
    agora = agora or datetime.now()
    return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def gasto_do_mes(agora=None):
    from models import db, UsoIA
    total = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0.0)).filter(UsoIA.quando >= _inicio_do_mes(agora)).scalar()
    return round(float(total or 0), 4)


def teto():
    from regras_negocio import regra
    return float(regra('ia_teto_mensal_usd') or 0)


def situacao_do_orcamento():
    gasto, limite = gasto_do_mes(), teto()
    pct = (gasto / limite * 100) if limite > 0 else 100.0
    return {'gasto': gasto, 'teto': limite, 'pct': round(min(pct, 999), 1), 'esgotado': limite <= 0 or gasto >= limite,
            'desligada': limite <= 0}


def conferir_orcamento():
    """Levanta OrcamentoEsgotado quando não há mais saldo no mês."""
    importar_uso_externo()
    s = situacao_do_orcamento()
    if s['desligada']:
        raise OrcamentoEsgotado('as IAs estão desligadas (teto mensal zero em Parâmetros de regras)')
    if s['esgotado']:
        raise OrcamentoEsgotado(f"o teto mensal de US$ {s['teto']:.2f} foi atingido (gasto US$ {s['gasto']:.2f})")
    return s


def _avisar_teto():
    """Sino (e e-mail) para os Administradores ao passar do aviso e ao atingir o teto — uma vez por mês cada."""
    try:
        from regras_negocio import regra
        from models import Usuario
        from notificacoes import notificar, eh_conta_de_teste
        s = situacao_do_orcamento()
        if s['teto'] <= 0:
            return
        mes = datetime.now().strftime('%Y-%m')
        aviso = float(regra('ia_aviso_teto_pct') or 80)
        nivel = 'teto' if s['esgotado'] else ('aviso' if s['pct'] >= aviso else None)
        if not nivel:
            return
        admins = [u for u in Usuario.query.filter_by(tipo_usuario='Administrador', status='Ativo').all() if not eh_conta_de_teste(u)]
        if not admins:
            return
        titulo = 'Teto de gasto com IA atingido' if nivel == 'teto' else 'Gasto com IA perto do teto'
        mensagem = (f"Gasto do mês com IA: US$ {s['gasto']:.2f} de US$ {s['teto']:.2f} ({s['pct']:.0f}%). "
                    + ('As IAs pararam até o mês que vem; o Assistente mostra só os trechos encontrados.' if nivel == 'teto'
                       else 'Ao atingir o teto, as IAs param até o mês que vem.'))
        notificar(admins, titulo, mensagem, link='/admin/provedores-ia', tipo='sistema', referencia=f'ia-{nivel}-{mes}')
    except Exception:
        pass  # o aviso nunca impede a resposta


def registrar(uso, provedor, modelo, tokens_entrada=0, tokens_saida=0, sucesso=True, motivo=None, usuario_id=None, quando=None):
    from models import db, UsoIA
    valor = custo(modelo, tokens_entrada, tokens_saida) if sucesso else 0.0
    db.session.add(UsoIA(quando=quando or datetime.now(), uso=uso, provedor=provedor, modelo=modelo,
                         tokens_entrada=tokens_entrada or 0, tokens_saida=tokens_saida or 0, custo_usd=valor,
                         sucesso=sucesso, motivo=(motivo or '')[:300] or None, usuario_id=usuario_id))
    db.session.commit()
    if sucesso and valor:
        _avisar_teto()
    return valor


def arquivo_uso_externo():
    raiz = os.path.dirname(os.path.abspath(__file__))
    pasta = os.path.join(raiz, 'instance')
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, 'uso_ia_externo.jsonl')


def anotar_uso_externo(uso, provedor, modelo, tokens_entrada, tokens_saida, sucesso=True, motivo=None):
    """Para processos sem acesso ao banco (Orquestrador): grava uma linha que a plataforma importa depois."""
    linha = {'quando': datetime.now().isoformat(timespec='seconds'), 'uso': uso, 'provedor': provedor, 'modelo': modelo,
             'tokens_entrada': int(tokens_entrada or 0), 'tokens_saida': int(tokens_saida or 0), 'sucesso': bool(sucesso),
             'motivo': (motivo or '')[:300]}
    with open(arquivo_uso_externo(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(linha, ensure_ascii=False) + '\n')


def importar_uso_externo():
    caminho = arquivo_uso_externo()
    if not os.path.isfile(caminho) or os.path.getsize(caminho) == 0:
        return 0
    temporario = caminho + '.importando'
    try:
        os.replace(caminho, temporario)
    except OSError:
        return 0
    total = 0
    with open(temporario, encoding='utf-8') as f:
        for linha in f:
            try:
                d = json.loads(linha)
                registrar(d['uso'], d['provedor'], d['modelo'], d.get('tokens_entrada'), d.get('tokens_saida'), d.get('sucesso', True),
                          d.get('motivo'), quando=datetime.fromisoformat(d['quando']))
                total += 1
            except (ValueError, KeyError):
                continue
    os.remove(temporario)
    return total


# ------------------------------------------------------------------------------
# Chamadas
# ------------------------------------------------------------------------------
def _sem_segredos(texto):
    try:
        from base_conhecimento import sem_segredos
        return sem_segredos(str(texto))
    except Exception:
        return str(texto)


def _claude(modelo, sistema, mensagens, max_tokens, esforco):
    try:
        import anthropic
    except ImportError:
        raise FalhaProvedor('biblioteca anthropic não instalada') from None
    cliente = anthropic.Anthropic(timeout=120.0, max_retries=1)
    try:
        with cliente.messages.stream(model=modelo, max_tokens=max_tokens,
                                     system=[{'type': 'text', 'text': sistema, 'cache_control': {'type': 'ephemeral'}}],
                                     messages=mensagens, output_config={'effort': esforco}) as fluxo:
            r = fluxo.get_final_message()
    except anthropic.AuthenticationError:
        raise FalhaProvedor('chave recusada pela Anthropic') from None
    except anthropic.RateLimitError:
        raise FalhaProvedor('limite de uso da Anthropic atingido') from None
    except anthropic.NotFoundError:
        raise FalhaProvedor(f'modelo {modelo} não encontrado na Anthropic') from None
    except anthropic.APIConnectionError:
        raise FalhaProvedor('sem conexão com a Anthropic') from None
    except anthropic.APIStatusError as e:
        raise FalhaProvedor(f'erro da Anthropic ({e.status_code})') from e
    if r.stop_reason == 'refusal':
        raise FalhaProvedor('a IA recusou o pedido')
    texto = ''.join(b.text for b in r.content if b.type == 'text').strip()
    if r.stop_reason == 'max_tokens':
        texto += '\n\n(…resposta cortada por ser longa demais.)'
    u = r.usage
    entrada = (u.input_tokens or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0)
    return texto, entrada, u.output_tokens or 0


def _gemini(modelo, sistema, mensagens, max_tokens, esforco):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise FalhaProvedor('biblioteca google-genai não instalada') from None
    chave = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    cliente = genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=30_000))
    conteudos = [types.Content(role='model' if m['role'] == 'assistant' else 'user', parts=[types.Part(text=m['content'])])
                 for m in mensagens]
    # Raciocínio curto (como o esforço "low" do Claude): responde mais rápido e evita o 504 DEADLINE_EXCEEDED
    nivel = {'low': 'LOW', 'medium': 'MEDIUM', 'high': 'HIGH'}.get(esforco, 'LOW')
    config = types.GenerateContentConfig(system_instruction=sistema, max_output_tokens=max_tokens,
                                         thinking_config=types.ThinkingConfig(thinking_level=nivel))
    try:
        r = cliente.models.generate_content(model=modelo, contents=conteudos, config=config)
    except Exception as e:
        # Sobrecarga ou prazo estourado: sem nova tentativa, vai logo para o próximo modelo da ordem (resposta mais rápida)
        if any(c in str(e) for c in ('503', '504', 'DEADLINE_EXCEEDED', 'UNAVAILABLE', 'overloaded', 'timed out')):
            raise FalhaProvedor(f'{modelo} demorou demais ou está sobrecarregado no Google') from e
        raise FalhaProvedor(f'erro do Gemini: {_sem_segredos(e)[:160]}') from e
    texto = (getattr(r, 'text', None) or '').strip()
    u = getattr(r, 'usage_metadata', None)
    entrada = getattr(u, 'prompt_token_count', 0) or 0
    saida = (getattr(u, 'candidates_token_count', 0) or 0) + (getattr(u, 'thoughts_token_count', 0) or 0)
    return texto, entrada, saida


def _openai(modelo, sistema, mensagens, max_tokens, esforco):
    try:
        import openai
    except ImportError:
        raise FalhaProvedor('biblioteca openai não instalada') from None
    cliente = openai.OpenAI(timeout=120.0, max_retries=1)
    try:
        # API Responses; store=False: a conversa não fica guardada na OpenAI (dados de jovens e mentores)
        r = cliente.responses.create(model=modelo, instructions=sistema, max_output_tokens=max_tokens, store=False,
                                     input=[{'role': m['role'], 'content': m['content']} for m in mensagens],
                                     reasoning={'effort': esforco if esforco in ('low', 'medium', 'high') else 'low'})
    except openai.AuthenticationError:
        raise FalhaProvedor('chave recusada pela OpenAI') from None
    except openai.RateLimitError as e:
        # 429 com insufficient_quota = conta sem créditos (não adianta esperar); o resto é limite por minuto
        if (e.body or {}).get('type') == 'insufficient_quota' if isinstance(e.body, dict) else False:
            raise FalhaProvedor('a conta da OpenAI está sem créditos (adicione em platform.openai.com › Billing)') from e
        raise FalhaProvedor('limite de uso da OpenAI atingido') from e
    except openai.NotFoundError:
        raise FalhaProvedor(f'modelo {modelo} não encontrado na OpenAI') from None
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise FalhaProvedor('sem conexão com a OpenAI') from None
    except openai.APIStatusError as e:
        raise FalhaProvedor(f'erro da OpenAI ({e.status_code})') from e
    texto = (r.output_text or '').strip()
    if r.status == 'incomplete' and getattr(r.incomplete_details, 'reason', '') == 'content_filter':
        raise FalhaProvedor('a IA recusou o pedido')
    if r.status == 'incomplete' and texto:
        texto += '\n\n(…resposta cortada por ser longa demais.)'
    u = r.usage
    # output_tokens já inclui o raciocínio (cobrado como saída)
    return texto, (u.input_tokens or 0) if u else 0, (u.output_tokens or 0) if u else 0


CHAMADAS = {'claude': _claude, 'gemini': _gemini, 'openai': _openai}


def gerar(uso, sistema, mensagens, max_tokens=4000, esforco='low', usuario_id=None):
    """Pede a resposta ao primeiro modelo da ordem do uso; cai para a reserva se falhar. Devolve Resposta.
    mensagens = [{'role': 'user'|'assistant', 'content': texto}], começando e terminando com 'user'.
    Levanta OrcamentoEsgotado (sem saldo) ou IAIndisponivel (nenhum modelo respondeu)."""
    if not ativo(uso):
        raise IADesligada(f'a IA do {USOS[uso][0]} está desligada na tela Provedores de IA')
    conferir_orcamento()
    catalogo = modelos()
    motivos = []
    for modelo in ordem(uso):
        provedor = catalogo[modelo]['provedor']
        nome = catalogo[modelo]['nome']
        if not chave_configurada(provedor):
            motivos.append(f'{nome}: sem chave cadastrada')
            continue
        try:
            texto, entrada, saida = CHAMADAS[provedor](modelo, sistema, mensagens, max_tokens, esforco)
            if not texto:
                raise FalhaProvedor('resposta vazia')
        except FalhaProvedor as e:
            motivos.append(f'{nome}: {e}')
            registrar(uso, provedor, modelo, sucesso=False, motivo=str(e), usuario_id=usuario_id)
            continue
        valor = registrar(uso, provedor, modelo, entrada, saida, usuario_id=usuario_id)
        return Resposta(_sem_segredos(texto), provedor, modelo, entrada, saida, valor)
    raise IAIndisponivel('; '.join(motivos) or 'nenhum modelo configurado')


# ------------------------------------------------------------------------------
# Tela
# ------------------------------------------------------------------------------
# Separa o gasto do chat (quem conversa com as pessoas) do gasto dos agentes (que trabalham sozinhos)
CATEGORIA_USO = {'assistente': 'chatbot', 'acompanhamento': 'chatbot', 'orquestrador': 'agente'}
CATEGORIAS = {'chatbot': ('Chatbots', 'bi-chat-dots', 'Conversas com as pessoas: Assistente da Plataforma e Assistente do Acompanhamento.'),
              'agente': ('Agentes', 'bi-robot', 'Trabalho automático dos agentes: hoje só o Agente Orquestrador usa IA paga.')}
# Agentes que rodam na própria plataforma, sem chamar IA paga (custo zero; ficam na tela para a comparação)
AGENTES_SEM_IA = ['Agentes OmniTest (testes por perfil)', 'Agentes de Segurança', 'Agentes de Banco de Dados',
                  'Agentes de Funcionalidades', 'Agentes gerentes (Técnico, Segurança, Banco e Funcionalidades)']


def kpis_por_uso(inicio=None):
    """KPI de cada uso no mês: chamadas, falhas, tokens, custo, custo médio, participação no gasto, modelo mais usado,
    última chamada e comparação com o mês anterior."""
    from models import db, UsoIA
    inicio = inicio or _inicio_do_mes()
    anterior = _inicio_do_mes(inicio - timedelta(days=1))
    catalogo = modelos()

    def somar(desde, ate=None):
        consulta = db.session.query(UsoIA.uso, UsoIA.sucesso, db.func.count(UsoIA.id), db.func.sum(UsoIA.tokens_entrada),
                                    db.func.sum(UsoIA.tokens_saida), db.func.sum(UsoIA.custo_usd)).filter(UsoIA.quando >= desde)
        if ate:
            consulta = consulta.filter(UsoIA.quando < ate)
        return consulta.group_by(UsoIA.uso, UsoIA.sucesso).all()

    dados = {uso: {'uso': uso, 'nome': USOS[uso][0], 'categoria': CATEGORIA_USO.get(uso, 'agente'), 'chamadas': 0, 'falhas': 0,
                   'entrada': 0, 'saida': 0, 'custo': 0.0, 'custo_anterior': 0.0, 'modelo': None, 'ultima': None, 'ligado': ativo(uso)}
             for uso in USOS}
    for uso, sucesso, n, e, s, c in somar(inicio):
        d = dados.get(uso)
        if d is None:
            continue
        if sucesso:
            d['chamadas'] += n
            d['entrada'] += e or 0
            d['saida'] += s or 0
            d['custo'] += c or 0
        else:
            d['falhas'] += n
    for uso, sucesso, _n, _e, _s, c in somar(anterior, inicio):
        if uso in dados and sucesso:
            dados[uso]['custo_anterior'] += c or 0
    mais_usado = db.session.query(UsoIA.uso, UsoIA.modelo, db.func.count(UsoIA.id)) \
        .filter(UsoIA.quando >= inicio, UsoIA.sucesso.is_(True)).group_by(UsoIA.uso, UsoIA.modelo).all()
    for uso, modelo, _n in sorted(mais_usado, key=lambda x: x[2]):
        if uso in dados:
            dados[uso]['modelo'] = catalogo.get(modelo, {}).get('nome', modelo)
    for uso, quando in db.session.query(UsoIA.uso, db.func.max(UsoIA.quando)).group_by(UsoIA.uso).all():
        if uso in dados:
            dados[uso]['ultima'] = quando

    total = sum(d['custo'] for d in dados.values())
    for d in dados.values():
        d['custo'] = round(d['custo'], 4)
        d['custo_anterior'] = round(d['custo_anterior'], 4)
        d['medio'] = round(d['custo'] / d['chamadas'], 5) if d['chamadas'] else 0.0
        d['pct'] = round(100 * d['custo'] / total, 1) if total else 0.0
        tentativas = d['chamadas'] + d['falhas']
        d['taxa_sucesso'] = round(100 * d['chamadas'] / tentativas) if tentativas else None
    return list(dados.values())


def _totais_por_categoria(kpis):
    totais = {}
    for chave, (nome, icone, descricao) in CATEGORIAS.items():
        itens = [k for k in kpis if k['categoria'] == chave]
        custo = round(sum(k['custo'] for k in itens), 4)
        totais[chave] = {'nome': nome, 'icone': icone, 'descricao': descricao, 'custo': custo,
                         'chamadas': sum(k['chamadas'] for k in itens), 'falhas': sum(k['falhas'] for k in itens),
                         'custo_anterior': round(sum(k['custo_anterior'] for k in itens), 4)}
    geral = sum(t['custo'] for t in totais.values())
    for t in totais.values():
        t['pct'] = round(100 * t['custo'] / geral, 1) if geral else 0.0
    return totais


def resumo_para_tela():
    from models import db, UsoIA
    importar_uso_externo()
    inicio = _inicio_do_mes()
    por_uso = db.session.query(UsoIA.uso, db.func.count(UsoIA.id), db.func.sum(UsoIA.custo_usd)) \
        .filter(UsoIA.quando >= inicio, UsoIA.sucesso.is_(True)).group_by(UsoIA.uso).all()
    por_modelo = db.session.query(UsoIA.modelo, db.func.count(UsoIA.id), db.func.sum(UsoIA.tokens_entrada),
                                  db.func.sum(UsoIA.tokens_saida), db.func.sum(UsoIA.custo_usd)) \
        .filter(UsoIA.quando >= inicio, UsoIA.sucesso.is_(True)).group_by(UsoIA.modelo).all()
    falhas = UsoIA.query.filter(UsoIA.quando >= inicio, UsoIA.sucesso.is_(False)).count()
    recentes = UsoIA.query.order_by(UsoIA.id.desc()).limit(30).all()
    catalogo = modelos()
    kpis = kpis_por_uso(inicio)
    return {'orcamento': situacao_do_orcamento(), 'modelos': catalogo, 'kpis': kpis, 'categorias': _totais_por_categoria(kpis),
            'agentes_sem_ia': AGENTES_SEM_IA,
            'ordens': {uso: ordem(uso) for uso in USOS}, 'ativos': {uso: ativo(uso) for uso in USOS},
            'por_uso': [{'uso': u, 'nome': USOS.get(u, (u,))[0], 'chamadas': n, 'custo': round(c or 0, 4)} for u, n, c in por_uso],
            'por_modelo': [{'modelo': m, 'nome': catalogo.get(m, {}).get('nome', m), 'chamadas': n, 'entrada': e or 0, 'saida': s or 0,
                            'custo': round(c or 0, 4)} for m, n, e, s, c in por_modelo],
            'falhas': falhas, 'recentes': recentes,
            'chaves': {p: chave_configurada(p) for p in PROVEDORES}, 'precos_conferidos_em': PRECOS_CONFERIDOS_EM,
            'sem_preco': [m for m, d in catalogo.items() if d['entrada'] is None or d['saida'] is None]}
