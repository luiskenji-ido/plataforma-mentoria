# -*- coding: utf-8 -*-
"""
IA DO ORQUESTRADOR EXECUTOR (Gemini, Claude ou ChatGPT/OpenAI)
==============================================================
Recebe uma correção + o prompt do agente + os arquivos citados e devolve, em JSON validado, se dá para corrigir e as
trocas exatas de trecho, com plano de rollback, como testar e riscos. As instruções fixas ficam na Skill
(skill_correcao.md). Chaves (.env ou Agentes IA › Credenciais): GEMINI_API_KEY (ou GOOGLE_API_KEY), ANTHROPIC_API_KEY
e/ou OPENAI_API_KEY.
"""
import json
import os

PASTA = os.path.dirname(os.path.abspath(__file__))
# Os modelos vêm da tela Provedores de IA (a plataforma passa estas variáveis ao iniciar o executor)
MODELO_GEMINI = os.environ.get('ORQUESTRADOR_MODELO_GEMINI', 'gemini-3.6-flash')
MODELO_CLAUDE = os.environ.get('ORQUESTRADOR_MODELO_CLAUDE', 'claude-sonnet-5-5')
MODELO_OPENAI = os.environ.get('ORQUESTRADOR_MODELO_OPENAI', 'gpt-6.2-sol')
LIMITE_ARQUIVO = 60_000      # arquivos maiores vão em janelas ao redor das linhas citadas
JANELA = 90                  # linhas antes/depois de cada linha citada

ESQUEMA = {
    'type': 'object',
    'properties': {
        'pode_corrigir': {'type': 'boolean'},
        'motivo': {'type': 'string'},
        'resumo': {'type': 'string'},
        'alteracoes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'arquivo': {'type': 'string'}, 'trecho_atual': {'type': 'string'},
                           'trecho_novo': {'type': 'string'}, 'explicacao': {'type': 'string'}},
            'required': ['arquivo', 'trecho_atual', 'trecho_novo', 'explicacao'], 'additionalProperties': False}},
        'rollback': {'type': 'string'},
        'como_testar': {'type': 'string'},
        'riscos': {'type': 'string'},
    },
    'required': ['pode_corrigir', 'motivo', 'resumo', 'alteracoes', 'rollback', 'como_testar', 'riscos'],
    'additionalProperties': False,
}


class IAIndisponivel(Exception):
    pass


def skill():
    with open(os.path.join(PASTA, 'skill_correcao.md'), encoding='utf-8') as f:
        return f.read()


def provedores_disponiveis():
    """Quais IAs têm chave configurada (a tela só oferece essas)."""
    disponiveis = []
    if os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY'):
        disponiveis.append('gemini')
    if os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        disponiveis.append('claude')
    if os.environ.get('OPENAI_API_KEY'):
        disponiveis.append('openai')
    return disponiveis


# ------------------------------------------------------------------------------ montagem do pedido
def conteudo_dos_arquivos(raiz, arquivos):
    """Arquivos citados com número de linha. Pequenos vão inteiros; grandes (ex.: app.py) em janelas ao redor das linhas citadas."""
    partes = []
    for caminho, linhas in arquivos:
        completo = os.path.join(raiz, caminho)
        try:
            with open(completo, encoding='utf-8') as f:
                texto = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        todas = texto.split('\n')
        if len(texto) <= LIMITE_ARQUIVO or not linhas:
            faixas = [(1, len(todas))] if len(texto) <= LIMITE_ARQUIVO else [(1, min(len(todas), 2 * JANELA))]
        else:
            faixas = []
            for n in linhas:
                ini, fim = max(1, n - JANELA), min(len(todas), n + JANELA)
                if faixas and ini <= faixas[-1][1] + 1:
                    faixas[-1] = (faixas[-1][0], max(fim, faixas[-1][1]))
                else:
                    faixas.append((ini, fim))
        blocos = []
        for ini, fim in faixas:
            blocos.append('\n'.join(f'{i:>5}| {todas[i - 1]}' for i in range(ini, fim + 1)))
        aviso = '' if len(texto) <= LIMITE_ARQUIVO else f' (arquivo grande: só as linhas {", ".join(f"{a}-{b}" for a, b in faixas)} de {len(todas)})'
        partes.append(f'### Arquivo `{caminho}`{aviso}\n(Os números à esquerda e o "| " NÃO fazem parte do arquivo.)\n```\n'
                      + '\n...\n'.join(blocos) + '\n```')
    return '\n\n'.join(partes) or '(nenhum arquivo do projeto foi citado no achado)'


def montar_pedido(correcao, prompt_do_agente, arquivos_texto, tentativa_anterior=None):
    pedido = [
        f"## Correção pedida pela equipe {correcao['equipe_nome']} (agente {correcao['agente']})",
        f"- Título: {correcao['titulo']}",
        f"- Severidade: {correcao['severidade']} · Categoria: {correcao.get('categoria', '')}",
        f"- Onde: {correcao.get('onde', '')}",
        f"- O que o agente viu: {correcao.get('detalhe', '')}",
        f"- O que se esperava: {correcao.get('esperado', '')}",
        f"- Recomendação do agente: {correcao.get('recomendacao', '')}",
        '', '## Prompt de correção gerado pelo agente (contexto)', prompt_do_agente or '(sem prompt)',
        '', '## Arquivos atuais', arquivos_texto,
    ]
    if tentativa_anterior:
        pedido += ['', '## A tentativa anterior não pôde ser aplicada', tentativa_anterior,
                   'Corrija copiando o trecho_atual exatamente como está no arquivo (sem os números de linha).']
    pedido += ['', 'Responda somente com o JSON pedido.']
    return '\n'.join(pedido)


# ------------------------------------------------------------------------------ provedores
def _anotar_uso(provedor, modelo, entrada, saida):
    """Consumo desta chamada para o gasto do mês (a plataforma importa o arquivo; o executor não usa o banco)."""
    try:
        import sys
        raiz = os.path.dirname(PASTA)
        if raiz not in sys.path:
            sys.path.insert(0, raiz)
        import provedores_ia
        provedores_ia.anotar_uso_externo('orquestrador', provedor, modelo, entrada, saida)
    except Exception:
        pass  # anotar nunca impede a correção


def _gemini(pedido):
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise IAIndisponivel(f'google-genai não instalado: {e}')
    if not (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')):
        raise IAIndisponivel('Configure GEMINI_API_KEY no .env')
    cliente = genai.Client()
    resposta = cliente.models.generate_content(
        model=MODELO_GEMINI, contents=pedido,
        config=types.GenerateContentConfig(system_instruction=skill(), response_mime_type='application/json',
                                           response_json_schema=ESQUEMA))
    uso = getattr(resposta, 'usage_metadata', None)
    _anotar_uso('gemini', MODELO_GEMINI, getattr(uso, 'prompt_token_count', 0) or 0,
                (getattr(uso, 'candidates_token_count', 0) or 0) + (getattr(uso, 'thoughts_token_count', 0) or 0))
    return json.loads(resposta.text)


def _claude(pedido):
    try:
        import anthropic
    except ImportError as e:
        raise IAIndisponivel(f'anthropic não instalado: {e}')
    if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')):
        raise IAIndisponivel('Configure ANTHROPIC_API_KEY no .env')
    cliente = anthropic.Anthropic()
    comum = dict(model=MODELO_CLAUDE, max_tokens=64000,
                 system=[{'type': 'text', 'text': skill(), 'cache_control': {'type': 'ephemeral'}}],
                 messages=[{'role': 'user', 'content': pedido}],
                 output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': ESQUEMA}})
    try:
        # Recusa por segurança é refeita pelo próprio servidor em outro modelo (fallbacks), sem trocar de código
        with cliente.beta.messages.stream(betas=['server-side-fallback-2026-07-01'], fallbacks='default', **comum) as fluxo:
            mensagem = fluxo.get_final_message()
    except anthropic.BadRequestError:
        with cliente.messages.stream(**comum) as fluxo:  # conta/plataforma sem o recurso de fallback
            mensagem = fluxo.get_final_message()
    uso = getattr(mensagem, 'usage', None)
    _anotar_uso('claude', MODELO_CLAUDE, (getattr(uso, 'input_tokens', 0) or 0) + (getattr(uso, 'cache_read_input_tokens', 0) or 0)
                + (getattr(uso, 'cache_creation_input_tokens', 0) or 0), getattr(uso, 'output_tokens', 0) or 0)
    if mensagem.stop_reason == 'refusal':
        categoria = getattr(getattr(mensagem, 'stop_details', None), 'category', None)
        raise IAIndisponivel(f'A IA recusou a correção (categoria: {categoria}).')
    if mensagem.stop_reason == 'max_tokens':
        raise IAIndisponivel('A resposta da IA ficou grande demais e foi cortada.')
    texto = next((b.text for b in mensagem.content if b.type == 'text'), '')
    return json.loads(texto)


def _openai(pedido):
    try:
        import openai
    except ImportError as e:
        raise IAIndisponivel(f'openai não instalado: {e}')
    if not os.environ.get('OPENAI_API_KEY'):
        raise IAIndisponivel('Configure OPENAI_API_KEY no .env ou em Agentes IA › Credenciais')
    cliente = openai.OpenAI(timeout=900.0, max_retries=1)
    try:
        # Saída estruturada (json_schema estrito) no mesmo formato do Claude e do Gemini; store=False: o código do
        # projeto não fica guardado na OpenAI
        r = cliente.responses.create(model=MODELO_OPENAI, instructions=skill(), input=pedido, store=False,
                                     max_output_tokens=64000, reasoning={'effort': 'high'},
                                     text={'format': {'type': 'json_schema', 'name': 'correcao', 'schema': ESQUEMA, 'strict': True}})
    except openai.APIStatusError as e:
        if isinstance(e.body, dict) and e.body.get('type') == 'insufficient_quota':
            raise IAIndisponivel('A conta da OpenAI está sem créditos (adicione em platform.openai.com › Billing).')
        raise IAIndisponivel(f'Erro da OpenAI ({e.status_code}).')
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise IAIndisponivel('Sem conexão com a OpenAI.')
    uso = getattr(r, 'usage', None)
    _anotar_uso('openai', MODELO_OPENAI, getattr(uso, 'input_tokens', 0) or 0, getattr(uso, 'output_tokens', 0) or 0)
    recusa = next((c.refusal for item in (r.output or []) for c in (getattr(item, 'content', None) or [])
                   if getattr(c, 'type', '') == 'refusal'), None)
    if recusa:
        raise IAIndisponivel(f'A IA recusou a correção: {recusa[:200]}')
    if r.status == 'incomplete':
        raise IAIndisponivel('A resposta da IA ficou grande demais e foi cortada.')
    return json.loads(r.output_text)


CHAMADAS = {'claude': _claude, 'gemini': _gemini, 'openai': _openai}


def pedir_correcao(provedor, correcao, prompt_do_agente, arquivos_texto, tentativa_anterior=None):
    """Devolve o dicionário no formato ESQUEMA. Levanta IAIndisponivel quando não há chave/biblioteca ou a IA recusa."""
    pedido = montar_pedido(correcao, prompt_do_agente, arquivos_texto, tentativa_anterior)
    resposta = CHAMADAS.get(provedor, _gemini)(pedido)
    for campo in ESQUEMA['required']:
        resposta.setdefault(campo, [] if campo == 'alteracoes' else '')
    return resposta
