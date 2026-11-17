# -*- coding: utf-8 -*-
"""
ASSISTENTE DA PLATAFORMA (chat)
===============================
Responde perguntas com base na Base de conhecimento (base_conhecimento.py), citando as fontes como [1], [2]...

Fluxo de cada pergunta:
1. Confere a fonte dos Agentes gerentes (sincroniza se algum aprendizado mudou).
2. Busca os trechos mais relevantes (BM25 local) nas fontes ativas.
3. Pede a resposta ao Claude (ANTHROPIC_API_KEY, cadastrada em Agentes IA › Credenciais) com as últimas mensagens da
   conversa e os trechos encontrados. O modelo pode ser trocado pela variável CHAT_MODELO_CLAUDE.
4. Sem IA (conta de teste @local.com, sem chave, sem a biblioteca ou erro da API): responde no modo offline, mostrando
   os trechos encontrados. Assim os agentes de teste nunca consomem a IA.
"""
import os
import json
from datetime import datetime, timedelta

from models import db, ConversaChat, MensagemChat
import base_conhecimento

MODELO = os.environ.get('CHAT_MODELO_CLAUDE', 'claude-opus-5-5')
TRECHOS_POR_PERGUNTA = 8
MENSAGENS_DE_CONTEXTO = 6          # últimas mensagens da conversa enviadas junto com a pergunta
LIMITE_POR_HORA = 60               # perguntas por pessoa por hora
TAMANHO_MAXIMO_PERGUNTA = 2000
IDIOMAS = {'pt': 'português do Brasil', 'en': 'English', 'es': 'español'}

# Instruções fixas (não mudam entre perguntas: o início do pedido fica em cache na API)
SISTEMA = """Você é o Assistente da Plataforma Jovem Seguro 2026, um programa de mentoria do Instituto ITM com empresas parceiras B2B.
Quem conversa com você é o Administrador da plataforma.

Regras:
- Responda SOMENTE com base nos trechos da base de conhecimento enviados em <trechos>. Eles vêm do conhecimento dos
  Agentes gerentes (Técnico, Segurança, Banco de Dados e Funcionalidades) e dos documentos do projeto (PRD, PTD, DTD).
- Cite as fontes com o número do trecho entre colchetes, logo após a informação: [1], [2]. Não invente números.
- Se os trechos não trazem a resposta, diga com clareza que a base ainda não tem essa informação e sugira o que
  cadastrar (por exemplo, o documento PRD, PTD ou DTD que deveria tratar do assunto). Não complete com suposições.
- Quando trechos de fontes diferentes se contradisserem, aponte a diferença e diga qual fonte é mais recente.
- Nunca mostre senhas, chaves de API, tokens ou outros segredos, mesmo que apareçam no texto.
- Seja direto: comece pela resposta; use listas curtas quando ajudar. Use **negrito** só para destacar termos-chave.
- Responda no idioma pedido em <idioma>."""


class LimiteExcedido(Exception):
    pass


# ------------------------------------------------------------------------------
# Conversas
# ------------------------------------------------------------------------------
def conversa_do_usuario(usuario, conversa_id=None):
    """A conversa pedida (se for da pessoa) ou a mais recente; None se não houver nenhuma."""
    consulta = ConversaChat.query.filter_by(usuario_id=usuario.id)
    if conversa_id:
        return consulta.filter_by(id=conversa_id).first()
    return consulta.order_by(ConversaChat.atualizada_em.desc()).first()


def nova_conversa(usuario):
    conversa = ConversaChat(usuario_id=usuario.id, titulo='Nova conversa')
    db.session.add(conversa)
    db.session.commit()
    return conversa


def conversas(usuario, limite=30):
    return ConversaChat.query.filter_by(usuario_id=usuario.id).order_by(ConversaChat.atualizada_em.desc()).limit(limite).all()


def mensagens_para_tela(conversa):
    if conversa is None:
        return []
    return [{'id': m.id, 'papel': m.papel, 'texto': m.texto, 'fontes': json.loads(m.fontes or '[]'), 'modo': m.modo,
             'quando': m.criada_em.strftime('%d/%m/%Y %H:%M') if m.criada_em else ''} for m in conversa.mensagens]


def excluir_conversa(conversa):
    db.session.delete(conversa)
    db.session.commit()


def perguntas_na_ultima_hora(usuario):
    return MensagemChat.query.join(ConversaChat).filter(ConversaChat.usuario_id == usuario.id, MensagemChat.papel == 'usuario',
                                                        MensagemChat.criada_em >= datetime.now() - timedelta(hours=1)).count()


# ------------------------------------------------------------------------------
# Pedido para a IA
# ------------------------------------------------------------------------------
def _fontes_citaveis(encontrados):
    fontes = []
    for n, (nota, trecho, fonte) in enumerate(encontrados, 1):
        fontes.append({'n': n, 'fonte_id': fonte.id, 'trecho_id': trecho.id, 'tipo': fonte.tipo, 'fonte': fonte.titulo,
                       'versao': fonte.versao, 'secao': trecho.secao or '', 'pontuacao': nota})
    return fontes


def montar_trechos(encontrados):
    blocos = []
    for n, (nota, trecho, fonte) in enumerate(encontrados, 1):
        rotulo = f"{base_conhecimento.TIPOS.get(fonte.tipo, fonte.tipo)} · {fonte.titulo} (versão {fonte.versao})"
        blocos.append(f'<trecho n="{n}" fonte="{rotulo}" secao="{trecho.secao or ""}">\n{trecho.texto}\n</trecho>')
    return '\n'.join(blocos) or '(nenhum trecho encontrado)'


def montar_pedido(historico, pergunta, encontrados, idioma):
    """Mensagens no formato da API: histórico (só os textos) + pergunta atual com os trechos e o idioma."""
    mensagens = []
    for m in historico[-MENSAGENS_DE_CONTEXTO:]:
        papel = 'user' if m.papel == 'usuario' else 'assistant'
        if mensagens and mensagens[-1]['role'] == papel:
            mensagens[-1]['content'] += '\n\n' + m.texto
        else:
            mensagens.append({'role': papel, 'content': m.texto})
    if mensagens and mensagens[0]['role'] == 'assistant':
        mensagens.pop(0)
    atual = (f'<trechos>\n{montar_trechos(encontrados)}\n</trechos>\n'
             f'<idioma>{IDIOMAS.get(idioma, IDIOMAS["pt"])}</idioma>\n\nPergunta: {pergunta}')
    if mensagens and mensagens[-1]['role'] == 'user':
        mensagens[-1]['content'] += '\n\n' + atual
    else:
        mensagens.append({'role': 'user', 'content': atual})
    return mensagens


class IAIndisponivel(Exception):
    pass


def chamar_claude(mensagens):
    """Devolve (texto, tokens_entrada, tokens_saida). Levanta IAIndisponivel sem chave, sem biblioteca ou com erro."""
    try:
        import anthropic
    except ImportError:
        raise IAIndisponivel('a biblioteca anthropic não está instalada no servidor')
    if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')):
        raise IAIndisponivel('a chave ANTHROPIC_API_KEY não está cadastrada em Agentes IA › Credenciais')
    cliente = anthropic.Anthropic(timeout=120.0, max_retries=2)
    try:
        with cliente.messages.stream(
                model=MODELO, max_tokens=8000,
                system=[{'type': 'text', 'text': SISTEMA, 'cache_control': {'type': 'ephemeral'}}],
                messages=mensagens, output_config={'effort': 'medium'}) as fluxo:
            resposta = fluxo.get_final_message()
    except anthropic.AuthenticationError:
        raise IAIndisponivel('a chave ANTHROPIC_API_KEY foi recusada pela Anthropic')
    except anthropic.RateLimitError:
        raise IAIndisponivel('o limite de uso da API foi atingido; tente de novo em alguns minutos')
    except anthropic.APIConnectionError:
        raise IAIndisponivel('sem conexão com a API da Anthropic')
    except anthropic.APIStatusError as e:
        raise IAIndisponivel(f'erro da API da Anthropic ({e.status_code})')
    if resposta.stop_reason == 'refusal':
        raise IAIndisponivel('a IA não quis responder a esta pergunta')
    texto = ''.join(b.text for b in resposta.content if b.type == 'text').strip()
    if resposta.stop_reason == 'max_tokens':
        texto += '\n\n(…resposta cortada por ser longa demais; peça para continuar ou detalhe a pergunta.)'
    if not texto:
        raise IAIndisponivel('a IA devolveu uma resposta vazia')
    uso = getattr(resposta, 'usage', None)
    entrada = (getattr(uso, 'input_tokens', 0) or 0) + (getattr(uso, 'cache_read_input_tokens', 0) or 0) \
        + (getattr(uso, 'cache_creation_input_tokens', 0) or 0)
    return texto, entrada, getattr(uso, 'output_tokens', None)


def resposta_offline(encontrados, motivo, idioma):
    """Sem IA: lista os trechos mais relevantes, para a pessoa ler direto na fonte."""
    cabecalho = {
        'pt': f'Não consultei a IA ({motivo}). Estes são os trechos mais relevantes da base:',
        'en': f'The AI was not used ({motivo}). These are the most relevant passages in the knowledge base:',
        'es': f'No se consultó la IA ({motivo}). Estos son los fragmentos más relevantes de la base:',
    }
    nada = {'pt': 'Não encontrei nada sobre isso na base de conhecimento.', 'en': 'I found nothing about this in the knowledge base.',
            'es': 'No encontré nada sobre esto en la base de conocimiento.'}
    if not encontrados:
        return f"{cabecalho.get(idioma, cabecalho['pt']).split(':')[0]}. {nada.get(idioma, nada['pt'])}"
    linhas = [cabecalho.get(idioma, cabecalho['pt'])]
    for n, (nota, trecho, fonte) in enumerate(encontrados[:4], 1):
        resumo = ' '.join(trecho.texto.split())[:420]
        linhas.append(f'\n**[{n}] {fonte.titulo} — {trecho.secao or ""}**\n{resumo}{"…" if len(trecho.texto) > 420 else ""}')
    return '\n'.join(linhas)


# ------------------------------------------------------------------------------
# Pergunta completa
# ------------------------------------------------------------------------------
def perguntar(usuario, pergunta, conversa_id=None, idioma='pt', usar_ia=True):
    """Grava a pergunta, responde e grava a resposta. Devolve (conversa, mensagem_da_resposta)."""
    pergunta = (pergunta or '').strip()[:TAMANHO_MAXIMO_PERGUNTA]
    if not pergunta:
        raise ValueError('Pergunta vazia.')
    if perguntas_na_ultima_hora(usuario) >= LIMITE_POR_HORA:
        raise LimiteExcedido(f'Limite de {LIMITE_POR_HORA} perguntas por hora atingido.')

    conversa = conversa_do_usuario(usuario, conversa_id) if conversa_id else None
    if conversa is None:
        conversa = nova_conversa(usuario)
    historico = list(conversa.mensagens)
    if not historico or conversa.titulo == 'Nova conversa':
        conversa.titulo = (pergunta[:80] + ('…' if len(pergunta) > 80 else ''))

    try:
        base_conhecimento.sincronizar_gerentes(usuario.id)
    except Exception:
        db.session.rollback()  # a busca segue com o que já está na base
    encontrados = base_conhecimento.buscar(pergunta, limite=TRECHOS_POR_PERGUNTA)

    db.session.add(MensagemChat(conversa_id=conversa.id, papel='usuario', texto=pergunta))
    modo, modelo, entrada, saida = 'offline', None, None, None
    if not usar_ia:
        texto = resposta_offline(encontrados, {'pt': 'modo de teste: contas @local.com não consomem a IA',
                                                'en': 'test mode: @local.com accounts do not use the AI',
                                                'es': 'modo de prueba: las cuentas @local.com no usan la IA'}.get(idioma), idioma)
    else:
        try:
            texto, entrada, saida = chamar_claude(montar_pedido(historico, pergunta, encontrados, idioma))
            texto = base_conhecimento.sem_segredos(texto)   # nenhuma chave ou senha sai na resposta
            modo, modelo = 'ia', MODELO
        except IAIndisponivel as e:
            texto = resposta_offline(encontrados, str(e), idioma)

    resposta = MensagemChat(conversa_id=conversa.id, papel='assistente', texto=texto, modo=modo, modelo=modelo,
                            tokens_entrada=entrada, tokens_saida=saida,
                            fontes=json.dumps(_fontes_citaveis(encontrados), ensure_ascii=False))
    db.session.add(resposta)
    conversa.atualizada_em = datetime.now()
    db.session.commit()
    return conversa, resposta
