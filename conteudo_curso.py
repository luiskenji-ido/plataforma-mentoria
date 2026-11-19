# -*- coding: utf-8 -*-
"""
CONTEÚDO DOS CURSOS DENTRO DA PLATAFORMA
========================================
O Hub Educacional recebe o material do curso e o aluno estuda dentro da plataforma:

  - documento (.pdf, .docx, .md, .txt, .html): o texto é dividido em capítulos sozinho (títulos do Word, "Capítulo 1",
    "Aula 2", "Módulo 3", "1. Introdução"…); sem estrutura reconhecível, a IA aponta os capítulos; sem IA, o texto é
    dividido em partes de tamanho parecido. Cada capítulo vira uma aula.
  - vídeo: arquivo enviado (servido só a quem está matriculado, sem link de download) ou YouTube (tocado dentro da
    página; o aluno não recebe o endereço).
  - teste de conhecimento por aula: a IA escreve as perguntas a partir do conteúdo da aula; sem IA (ou para contas de
    teste), um gerador automático monta perguntas de completar a frase com o próprio texto. A gestão revisa e edita.
  - progresso automático: cada aula vale o mesmo peso, dividido entre o conteúdo (vídeo assistido até o mínimo,
    leitura até o fim ou material aberto) e o teste (nota mínima). O percentual do acompanhamento é recalculado a cada
    passo e entra no histórico de progresso.

As funções que tocam o banco rodam dentro de um app_context.
"""
import json
import math
import random
import re
import unicodedata
from datetime import datetime

from markupsafe import Markup, escape


# ------------------------------------------------------------------------------
# YouTube
# ------------------------------------------------------------------------------
_YOUTUBE = re.compile(r'(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})')


def extrair_youtube_id(endereco):
    """Aceita o link do YouTube em qualquer formato (watch, youtu.be, shorts, embed) ou só o código de 11 caracteres."""
    endereco = (endereco or '').strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', endereco):
        return endereco
    achado = _YOUTUBE.search(endereco)
    return achado.group(1) if achado else None


# ------------------------------------------------------------------------------
# Divisão do documento em capítulos
# ------------------------------------------------------------------------------
_PAGINA_PDF = re.compile(r'^# Página \d+\s*$', re.M)
_TITULO_MD = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$')
_PALAVRA_CAPITULO = re.compile(
    r'^\s*(cap[ií]tulo|aula|m[oó]dulo|unidade|li[cç][aã]o|parte|se[cç][aã]o|t[oó]pico|chapter|lesson|unit|module|lecci[oó]n)'
    r'\s+([0-9]{1,3}|[ivxlc]{1,6}|[a-z])\b[^\n]{0,110}$', re.I)
_NUMERADO = re.compile(r'^\s*(\d{1,2})\s*[\.\)\-–]?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{2,90})$')
PALAVRAS_POR_PARTE = 1500


def _limpar(texto):
    texto = re.sub(r'[ \t]+\n', '\n', texto or '')
    return re.sub(r'\n{3,}', '\n\n', texto).strip()


def _cortar(linhas, inicios, titulos):
    """Separa as linhas nos índices de início; o que vem antes do primeiro vira 'Introdução' se tiver corpo."""
    capitulos = []
    preambulo = _limpar('\n'.join(linhas[:inicios[0]]))
    if len(preambulo) >= 200:
        capitulos.append(('Introdução', preambulo))
    for n, inicio in enumerate(inicios):
        fim = inicios[n + 1] if n + 1 < len(inicios) else len(linhas)
        corpo = _limpar('\n'.join(linhas[inicio + 1:fim]))
        capitulos.append((titulos[n][:200], corpo))
    return [(t, c) for t, c in capitulos if c]  # título sem corpo (ex.: o título da apostila) não vira aula


def _por_titulos_markdown(linhas):
    por_nivel = {}
    for i, linha in enumerate(linhas):
        achado = _TITULO_MD.match(linha.strip())
        if achado:
            por_nivel.setdefault(len(achado.group(1)), []).append((i, achado.group(2).strip()))
    for nivel in sorted(por_nivel):
        marcas = por_nivel[nivel]
        if 2 <= len(marcas) <= 80:
            return _cortar(linhas, [i for i, _ in marcas], [t for _, t in marcas])
    return None


def _por_palavra_capitulo(linhas):
    marcas = [(i, linha.strip()) for i, linha in enumerate(linhas) if _PALAVRA_CAPITULO.match(linha)]
    if 2 <= len(marcas) <= 80:
        return _cortar(linhas, [i for i, _ in marcas], [t for _, t in marcas])
    return None


def _por_numeracao(linhas):
    marcas, esperado = [], None
    for i, linha in enumerate(linhas):
        achado = _NUMERADO.match(linha)
        if not achado or linha.rstrip().endswith(('.', ',', ';', ':')):
            continue
        numero = int(achado.group(1))
        if esperado is None and numero in (0, 1):
            esperado = numero
        if numero == esperado:
            marcas.append((i, linha.strip()))
            esperado += 1
    if len(marcas) >= 2:
        return _cortar(linhas, [i for i, _ in marcas], [t for _, t in marcas])
    return None


def _por_tamanho(texto, titulo):
    paragrafos = [p for p in re.split(r'\n\s*\n', texto) if p.strip()]
    total = len(texto.split())
    if total <= PALAVRAS_POR_PARTE * 1.5:
        return [(titulo or 'Conteúdo', _limpar(texto))]
    partes = max(2, round(total / PALAVRAS_POR_PARTE))
    alvo = math.ceil(total / partes)
    capitulos, atual, contagem = [], [], 0
    for paragrafo in paragrafos:
        atual.append(paragrafo)
        contagem += len(paragrafo.split())
        if contagem >= alvo:
            capitulos.append(atual)
            atual, contagem = [], 0
    if atual:
        capitulos.append(atual)
    return [(f'Parte {n}', _limpar('\n\n'.join(c))) for n, c in enumerate(capitulos, 1)]


def dividir_em_capitulos(texto, titulo=''):
    """[(título, texto)] na ordem do documento, e o método usado: titulos / palavras / numeracao / tamanho."""
    texto = _limpar(_PAGINA_PDF.sub('', texto or ''))
    linhas = texto.split('\n')
    for metodo, funcao in (('titulos', _por_titulos_markdown), ('palavras', _por_palavra_capitulo), ('numeracao', _por_numeracao)):
        capitulos = funcao(linhas)
        if capitulos and sum(1 for _, c in capitulos if c) >= 2:
            return capitulos, metodo
    return _por_tamanho(texto, titulo), 'tamanho'


def dividir_com_ia(texto, usuario_id=None):
    """Pede à IA as linhas onde começa cada capítulo. Devolve [(título, texto)] ou None se a IA não ajudar."""
    import provedores_ia
    texto = _limpar(_PAGINA_PDF.sub('', texto or ''))
    linhas = texto.split('\n')
    numeradas = [f'{i}: {linha[:160]}' for i, linha in enumerate(linhas) if linha.strip()][:1800]
    sistema = ('Você organiza apostilas em capítulos (aulas). Recebe as linhas numeradas de um documento e devolve SÓ um JSON '
               '{"capitulos": [{"linha": <número da linha onde o capítulo começa>, "titulo": "<título curto>"}]} '
               'em ordem, com 2 a 40 capítulos, sem texto fora do JSON. Use os títulos que já existem no documento.')
    resposta = provedores_ia.gerar('acompanhamento', sistema, [{'role': 'user', 'content': '\n'.join(numeradas)[:60000]}],
                                   max_tokens=2000, esforco='low', usuario_id=usuario_id)
    dados = _json_da_resposta(resposta.texto) or {}
    marcas = []
    for item in dados.get('capitulos') or []:
        try:
            linha = int(item.get('linha'))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= linha < len(linhas) and (not marcas or linha > marcas[-1][0]):
            marcas.append((linha, str(item.get('titulo') or linhas[linha]).strip()[:200]))
    if len(marcas) < 2:
        return None
    return _cortar(linhas, [i for i, _ in marcas], [t for _, t in marcas])


def _json_da_resposta(texto):
    texto = (texto or '').strip()
    texto = re.sub(r'^```(?:json)?|```$', '', texto, flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio < 0 or fim <= inicio:
        return None
    try:
        return json.loads(texto[inicio:fim + 1])
    except ValueError:
        return None


# ------------------------------------------------------------------------------
# Teste de conhecimento da aula
# ------------------------------------------------------------------------------
_PALAVRAS_VAZIAS = set('''
a o as os um uma uns umas de do da dos das no na nos nas em por para com sem sob sobre entre até após ante e ou mas que se
como quando onde porque pois também mais menos muito muita muitos muitas pouco já não sim seu sua seus suas meu minha
este esta estes estas esse essa esses essas aquele aquela isso isto aquilo ele ela eles elas você vocês nós ser estar ter
haver fazer pode podem deve devem é são foi foram será serão está estão tem têm cada todo toda todos todas outro outra
outros outras mesmo mesma qual quais the and for with from that this which there their about into your have will
'''.split())


def _sem_acento(palavra):
    return ''.join(c for c in unicodedata.normalize('NFD', palavra.lower()) if unicodedata.category(c) != 'Mn')


def _frases(texto):
    texto = re.sub(r'^#+\s*', '', texto or '', flags=re.M)
    texto = re.sub(r'\s+', ' ', texto)
    return [f.strip() for f in re.split(r'(?<=[\.\!\?])\s+', texto) if 8 <= len(f.split()) <= 40]


def _palavras_chave(texto):
    contagem = {}
    for palavra in re.findall(r'[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{5,}', texto or ''):
        chave = _sem_acento(palavra)
        if chave in _PALAVRAS_VAZIAS:
            continue
        contagem.setdefault(chave, [palavra, 0])[1] += 1
    return {k: v[0] for k, v in contagem.items()}


def gerar_questoes_automaticas(texto, quantidade=3, semente=None):
    """Perguntas de completar a frase, montadas com o próprio texto da aula (funciona sem IA)."""
    sorteio = random.Random(semente)
    frases = _frases(texto)
    vocabulario = _palavras_chave(texto)
    if len(vocabulario) < 4 or not frases:
        return []
    candidatas = []
    for frase in frases:
        termos = [p for p in re.findall(r'[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{5,}', frase) if _sem_acento(p) in vocabulario]
        if termos:
            candidatas.append((frase, max(termos, key=len)))
    sorteio.shuffle(candidatas)
    questoes, usadas = [], set()
    for frase, termo in candidatas:
        if len(questoes) >= quantidade:
            break
        chave = _sem_acento(termo)
        if chave in usadas:
            continue
        distratores = [p for k, p in vocabulario.items() if k != chave and _sem_acento(p) not in _sem_acento(frase)]
        distratores.sort(key=lambda p: abs(len(p) - len(termo)))
        distratores = distratores[:8]
        if len(distratores) < 3:
            continue
        alternativas = sorteio.sample(distratores, 3) + [termo]
        sorteio.shuffle(alternativas)
        lacuna = re.sub(r'\b' + re.escape(termo) + r'\b', '______', frase, count=1)
        questoes.append({
            'enunciado': f'Complete a frase da aula: "{lacuna}"',
            'alternativas': alternativas,
            'correta': alternativas.index(termo),
            'explicacao': f'No conteúdo da aula: "{frase}"',
        })
        usadas.add(chave)
    return questoes


def _validar_questao(item):
    if not isinstance(item, dict):
        return None
    alternativas = [str(a).strip() for a in (item.get('alternativas') or []) if str(a).strip()]
    try:
        correta = int(item.get('correta'))
    except (TypeError, ValueError):
        return None
    enunciado = str(item.get('enunciado') or '').strip()
    if not enunciado or not 2 <= len(alternativas) <= 6 or not 0 <= correta < len(alternativas):
        return None
    certa = alternativas[correta]
    random.shuffle(alternativas)  # a IA tende a pôr a certa sempre na mesma letra
    return {'enunciado': enunciado[:2000], 'alternativas': [a[:500] for a in alternativas],
            'correta': alternativas.index(certa), 'explicacao': str(item.get('explicacao') or '').strip()[:2000]}


def gerar_questoes_ia(titulo, texto, quantidade=3, usuario_id=None):
    import provedores_ia
    sistema = ('Você é professor e escreve testes de conhecimento curtos para jovens aprendizes. Responda SÓ com um JSON '
               '{"questoes": [{"enunciado": "...", "alternativas": ["...", "...", "...", "..."], "correta": <índice 0-3>, '
               '"explicacao": "..."}]}, sem texto fora do JSON. As perguntas medem a compreensão do conteúdo da aula '
               '(não decoreba de detalhes), têm uma única alternativa certa, distratores plausíveis e são escritas no '
               'mesmo idioma do conteúdo.')
    pedido = f'Aula: {titulo}\nQuantidade de perguntas: {quantidade}\n\nConteúdo da aula:\n{(texto or "")[:30000]}'
    resposta = provedores_ia.gerar('acompanhamento', sistema, [{'role': 'user', 'content': pedido}],
                                   max_tokens=3000, esforco='low', usuario_id=usuario_id)
    dados = _json_da_resposta(resposta.texto) or {}
    questoes = [q for q in (_validar_questao(i) for i in dados.get('questoes') or []) if q]
    return questoes[:quantidade]


def gerar_questoes(titulo, texto, quantidade=3, usuario_id=None, usar_ia=True):
    """(questões, origem, aviso). Tenta a IA; se ela estiver desligada, sem saldo ou falhar, usa o gerador automático."""
    aviso = None
    if usar_ia:
        try:
            questoes = gerar_questoes_ia(titulo, texto, quantidade, usuario_id)
            if questoes:
                return questoes, 'ia', None
            aviso = 'a IA não devolveu perguntas válidas'
        except Exception as erro:  # IA desligada, sem chave, sem saldo ou fora do ar
            aviso = str(erro)[:200]
    return gerar_questoes_automaticas(texto, quantidade), 'automatica', aviso


# ------------------------------------------------------------------------------
# Texto da aula em HTML simples (títulos, listas e parágrafos; tudo escapado)
# ------------------------------------------------------------------------------
def texto_em_html(texto):
    blocos, lista = [], []

    def fechar_lista():
        if lista:
            blocos.append('<ul>' + ''.join(f'<li>{escape(i)}</li>' for i in lista) + '</ul>')
            lista.clear()

    for paragrafo in re.split(r'\n\s*\n', texto or ''):
        for linha in paragrafo.split('\n'):
            linha = linha.strip()
            if not linha:
                continue
            titulo = _TITULO_MD.match(linha)
            item = re.match(r'^[\-\*•·▪●]\s+(.+)$', linha)
            if titulo:
                fechar_lista()
                nivel = min(6, len(titulo.group(1)) + 3)
                blocos.append(f'<h{nivel} class="mt-3">{escape(titulo.group(2))}</h{nivel}>')
            elif item:
                lista.append(item.group(1))
            else:
                fechar_lista()
                blocos.append(f'<p>{escape(linha)}</p>')
        fechar_lista()
    return Markup('\n'.join(blocos))


def segundos_de_leitura(texto, palavras_por_minuto=200):
    """Tempo mínimo na página antes de a leitura contar (um terço do tempo de leitura, entre 15 s e 4 min)."""
    palavras = len((texto or '').split())
    return int(min(240, max(15, palavras / palavras_por_minuto * 60 / 3)))


# ------------------------------------------------------------------------------
# Progresso automático
# ------------------------------------------------------------------------------
def partes_da_aula(aula, total_questoes):
    """O que conta na aula: o conteúdo principal (vídeo › texto › material) e o teste, se houver perguntas."""
    partes = []
    if aula.tem_video:
        partes.append('video')
    elif (aula.texto or '').strip():
        partes.append('leitura')
    elif aula.material_arquivo:
        partes.append('material')
    if total_questoes:
        partes.append('teste')
    return partes


def situacao_da_aula(aula, progresso, total_questoes):
    """{'partes': {parte: feito}, 'fracao': 0-1, 'concluida': bool}."""
    feitos = {}
    for parte in partes_da_aula(aula, total_questoes):
        if progresso is None:
            feitos[parte] = False
        elif parte == 'video':
            feitos[parte] = bool(progresso.video_concluido)
        elif parte == 'leitura':
            feitos[parte] = bool(progresso.leitura_concluida)
        elif parte == 'material':
            feitos[parte] = bool(progresso.material_aberto)
        else:
            feitos[parte] = bool(progresso.teste_aprovado)
    fracao = (sum(feitos.values()) / len(feitos)) if feitos else 0.0
    return {'partes': feitos, 'fracao': fracao, 'concluida': bool(feitos) and all(feitos.values())}


def mapa_do_curso(acompanhamento):
    """Aulas do curso com a situação do aluno: [{'aula', 'progresso', 'questoes', 'situacao'}] e o percentual."""
    from models import AulaCurso, ProgressoAula, QuestaoAula
    from models import db
    aulas = AulaCurso.query.filter_by(curso_id=acompanhamento.curso_id).order_by(AulaCurso.ordem, AulaCurso.id).all()
    progresso = {p.aula_id: p for p in ProgressoAula.query.filter_by(acompanhamento_id=acompanhamento.id)}
    contagem = dict(db.session.query(QuestaoAula.aula_id, db.func.count(QuestaoAula.id))
                    .filter(QuestaoAula.aula_id.in_([a.id for a in aulas] or [0])).group_by(QuestaoAula.aula_id).all())
    itens, soma, validas = [], 0.0, 0
    for aula in aulas:
        situacao = situacao_da_aula(aula, progresso.get(aula.id), contagem.get(aula.id, 0))
        if situacao['partes']:
            validas += 1
            soma += situacao['fracao']
        itens.append({'aula': aula, 'progresso': progresso.get(aula.id), 'questoes': contagem.get(aula.id, 0), 'situacao': situacao})
    percentual = int(math.floor(soma / validas * 100 + 1e-9)) if validas else 0
    return itens, percentual


def curso_tem_conteudo(curso_id):
    from models import AulaCurso
    return AulaCurso.query.filter_by(curso_id=curso_id).first() is not None


def recalcular_acompanhamento(acompanhamento):
    """Atualiza o percentual do aluno pelas aulas; grava no histórico quando muda. Devolve (percentual, concluiu_agora).
    Ao chegar a 100% o curso é finalizado, a não ser que exija certificado e ele ainda não tenha sido enviado."""
    from models import db, HistoricoProgresso, Curso
    _, percentual = mapa_do_curso(acompanhamento)
    concluiu_agora = False
    if acompanhamento.percentual_conclusao != percentual:
        concluiu_agora = percentual == 100
        acompanhamento.percentual_conclusao = percentual
        db.session.add(HistoricoProgresso(acompanhamento_id=acompanhamento.id, percentual=percentual, data_registro=datetime.now()))
    if acompanhamento.status not in ('Desativado',):
        curso = db.session.get(Curso, acompanhamento.curso_id)
        exige = curso is not None and curso.exige_certificado == 'Sim'
        if percentual == 100 and (not exige or acompanhamento.certificado_anexado):
            acompanhamento.status = 'Finalizado'
        elif percentual < 100 and acompanhamento.status == 'Finalizado':
            acompanhamento.status = 'Iniciado'
    return percentual, concluiu_agora


def obter_progresso(acompanhamento_id, aula_id):
    from models import db, ProgressoAula
    progresso = ProgressoAula.query.filter_by(acompanhamento_id=acompanhamento_id, aula_id=aula_id).first()
    if progresso is None:
        progresso = ProgressoAula(acompanhamento_id=acompanhamento_id, aula_id=aula_id)
        db.session.add(progresso)
        db.session.flush()
    return progresso


def fechar_aula_se_concluida(aula, progresso):
    from models import QuestaoAula
    situacao = situacao_da_aula(aula, progresso, QuestaoAula.query.filter_by(aula_id=aula.id).count())
    if situacao['concluida'] and not progresso.concluida_em:
        progresso.concluida_em = datetime.now()
    elif not situacao['concluida']:
        progresso.concluida_em = None
    return situacao


def corrigir_teste(questoes, respostas):
    """respostas = {questao_id: índice}. Devolve (nota 0-100, [{'questao', 'escolhida', 'certa'}])."""
    detalhes, acertos = [], 0
    for questao in questoes:
        escolhida = respostas.get(questao.id)
        certa = escolhida is not None and escolhida == questao.correta
        acertos += 1 if certa else 0
        detalhes.append({'questao': questao, 'escolhida': escolhida, 'certa': certa})
    nota = round(acertos / len(questoes) * 100) if questoes else 0
    return nota, detalhes
