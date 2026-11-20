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
# {plataforma} e {instituicao} vêm da Identidade da instituição (sistema(), na hora de cada pergunta)
SISTEMA = """Você é o Assistente da Plataforma {plataforma}, um programa de mentoria da instituição {instituicao} com empresas parceiras B2B.
Quem conversa com você é o Administrador da plataforma. Fale como um colega de suporte simpático e paciente, que
conhece bem a plataforma: linguagem simples, calorosa e humana, sem jargão técnico.

Como responder:
- Comece com uma frase curta e acolhedora que já vá ao ponto (ex.: "Claro! Criar um projeto é rápido:").
  Não repita saudações em toda mensagem da mesma conversa.
- Para perguntas de "como faço", explique em passos numerados, na ordem em que a pessoa vai agir na tela:
  1) onde clicar no menu superior (use o caminho do trecho "Onde fica", ex.: **Projetos e TCC › Projetos**);
  2) o que preencher ou escolher; 3) qual botão clicar para concluir; 4) o que acontece depois.
  Escreva os nomes de menus, abas e botões em **negrito**, exatamente como aparecem na tela.
- Se a tela tiver um Tour guiado, termine com uma dica curta: o botão de Tour (ícone de interrogação) mostra os passos
  em cima da própria tela. Se fizer sentido, ofereça ajuda com o próximo passo ("Quer que eu explique como...?").
- Não mostre nomes técnicos internos (endpoints, tabelas, chaves de parâmetros, códigos APR-...) a menos que a pessoa
  pergunte sobre algo técnico. Use o nome que aparece na tela.
- Quem acessa: se o trecho disser que só alguns perfis veem a tela, mencione isso de forma simples.

Regras de conteúdo:
- Responda SOMENTE com base nos trechos enviados em <trechos>. Eles vêm do Guia das telas (menu e passos do Tour), do
  conhecimento dos Agentes gerentes e dos documentos do projeto (PRD, PTD, DTD). Ignore trechos que não têm relação
  com a pergunta.
- Cite as fontes com o número do trecho entre colchetes, no fim da frase ou do passo que usou a informação: [1], [2].
  Não invente números.
- Se os trechos não trazem a resposta, diga com gentileza que ainda não tem essa informação, conte o que sabe de
  relacionado e sugira onde olhar (a tela mais provável, o Tour dela) ou o documento (PRD, PTD ou DTD) que deveria
  tratar do assunto. Não complete com suposições.
- Quando trechos de fontes diferentes se contradisserem, aponte a diferença e diga qual fonte é mais recente.
- Nunca mostre senhas, chaves de API, tokens ou outros segredos, mesmo que apareçam no texto.
- Seja breve: em geral até 8 passos ou 150 palavras, a menos que a pessoa peça detalhes.
- Responda no idioma pedido em <idioma>."""


def sistema():
    """Instruções fixas com o nome da plataforma e da instituição desta instalação."""
    import identidade
    return identidade.aplicar(SISTEMA)


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
    for n, (_nota, trecho, fonte) in enumerate(encontrados, 1):
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


_OFFLINE = {
    'pt': {'abre': 'Agora não consegui falar com a IA, mas separei o que a plataforma já explica sobre isso:',
           'teste': 'Modo de teste: as contas @local.com não usam a IA, então separei o que a base explica sobre isso:',
           'nada': 'Desculpe, agora não consegui falar com a IA e não achei nada sobre isso na base de conhecimento. '
                   'Tente com outras palavras (por exemplo, o nome da tela) ou abra o Tour da tela, no ícone de interrogação.',
           'tela': 'Tela', 'onde': 'Onde fica', 'passos': 'Passo a passo', 'mais': 'Também pode ajudar',
           'fim': 'Se quiser ver na própria tela, abra o **Tour** (ícone de interrogação no topo).',
           'adm': 'Para o Assistente voltar a responder com a IA, confira a tela **Administração › Sistema › Provedores de IA e custos**.'},
    'en': {'abre': "I couldn't reach the AI right now, but here is what the platform already explains about this:",
           'teste': 'Test mode: @local.com accounts do not use the AI, so here is what the knowledge base explains:',
           'nada': "Sorry, I couldn't reach the AI right now and found nothing about this in the knowledge base. "
                   'Try other words (such as the page name) or open the page Tour (question mark icon).',
           'tela': 'Page', 'onde': 'Where to find it', 'passos': 'Step by step', 'mais': 'This may also help',
           'fim': 'To see it on the page itself, open the **Tour** (question mark icon at the top).',
           'adm': 'To bring the AI back, check **Administration › System › AI providers and costs**.'},
    'es': {'abre': 'Ahora no pude hablar con la IA, pero separé lo que la plataforma ya explica sobre esto:',
           'teste': 'Modo de prueba: las cuentas @local.com no usan la IA, así que separé lo que explica la base:',
           'nada': 'Lo siento, ahora no pude hablar con la IA y no encontré nada sobre esto en la base de conocimiento. '
                   'Intenta con otras palabras (por ejemplo, el nombre de la pantalla) o abre el Tour de la pantalla (icono de interrogación).',
           'tela': 'Pantalla', 'onde': 'Dónde está', 'passos': 'Paso a paso', 'mais': 'También puede ayudar',
           'fim': 'Para verlo en la propia pantalla, abre el **Tour** (icono de interrogación arriba).',
           'adm': 'Para que la IA vuelva a responder, revisa **Administración › Sistema › Proveedores de IA y costos**.'},
}


def _guia_amigavel(n, trecho, txt):
    """Seção do Guia das telas em formato de passo a passo (sem o endereço técnico)."""
    tela, onde, passos = '', '', []
    for linha in trecho.texto.splitlines():
        linha = linha.strip()
        if linha.startswith('Tela:'):
            tela = linha[5:].strip()
        elif linha.startswith('Onde fica:'):
            onde = linha[10:].strip().removeprefix('no menu superior,').strip().rstrip('.')
        elif linha[:1].isdigit() and '. ' in linha[:4]:
            passos.append(linha.split('. ', 1)[1])
    partes = [f"**{txt['tela']}: {tela or (trecho.secao or '').split(' › ')[-1]}** [{n}]"]
    if onde:
        partes.append(f"{txt['onde']}: **{onde}**")
    if passos:
        partes.append(f"{txt['passos']}:")
        partes += [f'{i}. {p}' for i, p in enumerate(passos[:8], 1)]
    return '\n'.join(partes)


def resposta_offline(encontrados, motivo, idioma, teste=False):
    """Sem IA: mostra, de forma amigável, o passo a passo do Guia das telas e os trechos mais relevantes.
    O motivo técnico não aparece para a pessoa (fica registrado em Provedores de IA e custos)."""
    txt = _OFFLINE.get(idioma, _OFFLINE['pt'])
    if not encontrados:
        return txt['nada']
    guias = [(n, t) for n, (_, t, _) in enumerate(encontrados, 1) if (t.secao or '').startswith('Guia das telas')][:2]
    outros = [(n, t, f) for n, (_, t, f) in enumerate(encontrados, 1) if not (t.secao or '').startswith('Guia das telas')]
    linhas = [txt['teste'] if teste else txt['abre']]
    for n, trecho in guias:
        linhas.append('\n' + _guia_amigavel(n, trecho, txt))
    if outros:
        linhas.append(f"\n**{txt['mais']}:**")
        for n, trecho, fonte in outros[:2 if guias else 3]:
            resumo = ' '.join(trecho.texto.split())
            resumo = resumo[:240] + ('…' if len(resumo) > 240 else '')
            secao = (trecho.secao or fonte.titulo).split(' › ')[-1]
            linhas.append(f'- **{secao}** [{n}]: {resumo}')
    if guias:
        linhas.append('\n' + txt['fim'])
    if not teste and motivo:
        linhas.append('\n' + txt['adm'])
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
        texto = resposta_offline(encontrados, '', idioma, teste=True)
    elif guardada:
        texto, fontes, modo, modelo, valor = guardada.texto, guardada.fontes, 'cache', guardada.modelo, 0.0
    else:
        try:
            r = provedores_ia.gerar(USO, sistema(), montar_pedido(historico, pergunta, encontrados, idioma), max_tokens=4000,
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
