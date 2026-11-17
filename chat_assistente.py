# -*- coding: utf-8 -*-
"""
ASSISTENTE DA PLATAFORMA (chat)
===============================
Responde perguntas com base na Base de conhecimento (base_conhecimento.py), citando as fontes como [1], [2]...

Fluxo de cada pergunta:
1. Confere a fonte dos Agentes gerentes (sincroniza se algum aprendizado mudou).
2. Busca os trechos mais relevantes (BM25 local) nas fontes ativas.
3. A mesma primeira pergunta, no mesmo idioma e com a base sem mudança, reaproveita a resposta já dada (sem custo),
   por até assistente_cache_dias dias (Parâmetros de regras).
4. Pede a resposta à IA pela ordem de modelos do uso "assistente" (provedores_ia.py: Claude Haiku por padrão, com o
   Gemini de reserva), com as últimas mensagens da conversa e os trechos encontrados (assistente_trechos).
5. Sem IA (conta de teste @local.com, teto do mês atingido, sem chave ou erro de todos os modelos): responde no modo
   offline, mostrando os trechos encontrados. Assim os agentes de teste nunca consomem a IA.
"""
import json
import hashlib
from datetime import datetime, timedelta

from models import db, ConversaChat, MensagemChat, FonteConhecimento
import base_conhecimento
import provedores_ia

USO = 'assistente'
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


def modelo_principal():
    """Primeiro modelo da ordem do Assistente (mostrado na tela)."""
    ordem = provedores_ia.ordem(USO)
    return ordem[0] if ordem else ''


def chave_de_cache(pergunta, idioma):
    """Pergunta normalizada + idioma + versão das fontes ativas: muda quando qualquer fonte muda."""
    fontes = FonteConhecimento.query.filter_by(ativo=True).order_by(FonteConhecimento.id).all()
    marca = '|'.join(f'{f.id}:{f.versao}:{f.hash_conteudo}' for f in fontes)
    normalizada = ' '.join(base_conhecimento.termos(pergunta))
    return hashlib.sha256(f'{normalizada}#{idioma}#{marca}'.encode('utf-8')).hexdigest()


def resposta_guardada(chave):
    from regras_negocio import regra
    dias = int(regra('assistente_cache_dias') or 0)
    if dias <= 0:
        return None
    return MensagemChat.query.filter(MensagemChat.chave_cache == chave, MensagemChat.papel == 'assistente',
                                     MensagemChat.modo == 'ia', MensagemChat.criada_em >= datetime.now() - timedelta(days=dias)) \
        .order_by(MensagemChat.id.desc()).first()


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
    from regras_negocio import regra
    encontrados = base_conhecimento.buscar(pergunta, limite=int(regra('assistente_trechos') or 5))

    db.session.add(MensagemChat(conversa_id=conversa.id, papel='usuario', texto=pergunta))
    modo, modelo, entrada, saida, valor, chave = 'offline', None, None, None, None, None
    fontes = json.dumps(_fontes_citaveis(encontrados), ensure_ascii=False)
    guardada = None
    if usar_ia and not historico:
        chave = chave_de_cache(pergunta, idioma)
        guardada = resposta_guardada(chave)
    if not usar_ia:
        texto = resposta_offline(encontrados, {'pt': 'modo de teste: contas @local.com não consomem a IA',
                                                'en': 'test mode: @local.com accounts do not use the AI',
                                                'es': 'modo de prueba: las cuentas @local.com no usan la IA'}.get(idioma), idioma)
    elif guardada:
        texto, fontes, modo, modelo, valor = guardada.texto, guardada.fontes, 'cache', guardada.modelo, 0.0
    else:
        try:
            r = provedores_ia.gerar(USO, SISTEMA, montar_pedido(historico, pergunta, encontrados, idioma), max_tokens=4000,
                                    esforco='low', usuario_id=usuario.id)
            texto, entrada, saida, valor, modo, modelo = r.texto, r.tokens_entrada, r.tokens_saida, r.custo_usd, 'ia', r.modelo
            texto = base_conhecimento.sem_segredos(texto)   # nenhuma chave ou senha sai na resposta
        except provedores_ia.IAIndisponivel as e:
            texto = resposta_offline(encontrados, str(e), idioma)

    resposta = MensagemChat(conversa_id=conversa.id, papel='assistente', texto=texto, modo=modo, modelo=modelo,
                            tokens_entrada=entrada, tokens_saida=saida, custo_usd=valor,
                            chave_cache=chave if modo == 'ia' else None, fontes=fontes)
    db.session.add(resposta)
    conversa.atualizada_em = datetime.now()
    db.session.commit()
    return conversa, resposta
