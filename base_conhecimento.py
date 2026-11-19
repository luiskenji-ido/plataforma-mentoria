# -*- coding: utf-8 -*-
"""
BASE DE CONHECIMENTO DO ASSISTENTE DA PLATAFORMA
================================================
Fontes (FonteConhecimento) divididas em trechos (TrechoConhecimento) para a busca:

1. Agentes gerentes (tipo GERENTES, sincronizada sozinha): os aprendizados APLICADOS dos quatro gerentes
   (Técnico, Segurança, Banco de Dados e Funcionalidades), como cada gerente trabalha, os parâmetros de regras de negócio
   e os módulos de cada perfil. Aprendizado pendente, revogado ou rejeitado não entra.
2. Documentos do projeto enviados na tela: PRD (Product Requirements Document), PTD (Product Technical Document),
   DTD (Detail Technical Document) ou outro. Formatos: .md, .txt, .html, .docx e .pdf (o PDF precisa do pacote pypdf).
   Enviar de novo um documento com o mesmo tipo e título cria a versão seguinte e desativa a anterior.

A busca é local (BM25 sobre os trechos, sem acento e com radical simples) e só considera fontes ativas.
Segredos que porventura apareçam no texto (chaves de API, tokens) são trocados por [omitido] antes de gravar.

Todas as funções rodam dentro de um app_context.
"""
import os
import re
import io
import json
import math
import time
import uuid
import zipfile
import hashlib
import unicodedata
from html.parser import HTMLParser
from collections import Counter
from xml.etree import ElementTree

from models import db, FonteConhecimento, TrechoConhecimento

TIPOS = {
    'GERENTES': 'Agentes gerentes',
    'PRD': 'PRD · Product Requirements Document',
    'PTD': 'PTD · Product Technical Document',
    'DTD': 'DTD · Detail Technical Document',
    'OUTRO': 'Outro documento',
}
TIPOS_UPLOAD = ['PRD', 'PTD', 'DTD', 'OUTRO']
EXTENSOES = {'.md', '.markdown', '.txt', '.html', '.htm', '.docx', '.pdf'}
LIMITE_ARQUIVO_MB = 20
MINIMO_CARACTERES_DOCUMENTO = 20   # menos que isso: documento sem texto (PDF escaneado)
PASTA = 'base_conhecimento'          # dentro de uploads/
TAMANHO_TRECHO = 1400                # caracteres por trecho (alvo)
MAXIMO_TRECHO = 2200
TITULO_GERENTES = 'Conhecimento dos Agentes gerentes'
INTERVALO_SINCRONIA = 60             # segundos entre duas conferências automáticas da fonte dos gerentes


class ErroDocumento(Exception):
    """Arquivo que não dá para ler (formato, tamanho, texto vazio)."""


# ------------------------------------------------------------------------------
# Segredos: nunca entram na base
# ------------------------------------------------------------------------------
_SEGREDOS = re.compile(
    r"(sk-ant-[A-Za-z0-9_\-]{10,}|AIza[0-9A-Za-z_\-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9\-]{10,}"
    r"|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    r"|(?i:(?:senha|password|secret|segredo|api[_-]?key|token)\s*[:=]\s*)\S{6,})")


def sem_segredos(texto):
    return _SEGREDOS.sub('[omitido]', texto or '')


# ------------------------------------------------------------------------------
# Extração de texto dos arquivos
# ------------------------------------------------------------------------------
class _LeitorHtml(HTMLParser):
    BLOCOS = {'p', 'div', 'li', 'tr', 'br', 'section', 'article', 'table', 'ul', 'ol', 'pre'}

    def __init__(self):
        super().__init__()
        self.partes, self._titulo, self._ignorar = [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._ignorar += 1
        elif re.fullmatch(r'h[1-6]', tag):
            self._titulo = int(tag[1])
            self.partes.append('\n' + '#' * self._titulo + ' ')
        elif tag in self.BLOCOS:
            self.partes.append('\n')
        elif tag in ('td', 'th'):
            self.partes.append(' | ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._ignorar = max(0, self._ignorar - 1)
        elif re.fullmatch(r'h[1-6]', tag):
            self.partes.append('\n')

    def handle_data(self, dados):
        if not self._ignorar:
            self.partes.append(dados)


def _texto_html(conteudo):
    leitor = _LeitorHtml()
    leitor.feed(conteudo)
    return ''.join(leitor.partes)


_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def _texto_docx(dados):
    """Lê o document.xml do .docx: parágrafos, títulos (estilos Heading/Título) e tabelas."""
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            raiz = ElementTree.fromstring(z.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        raise ErroDocumento('Arquivo .docx inválido ou corrompido.')
    linhas = []
    corpo = raiz.find(f'{_W}body')
    for bloco in (corpo if corpo is not None else []):
        if bloco.tag == f'{_W}p':
            linhas.append(_paragrafo_docx(bloco))
        elif bloco.tag == f'{_W}tbl':
            for linha in bloco.iter(f'{_W}tr'):
                celulas = [' '.join(_paragrafo_docx(p) for p in c.iter(f'{_W}p')).strip() for c in linha.iter(f'{_W}tc')]
                linhas.append(' | '.join(celulas))
    return '\n'.join(linhas)


def _paragrafo_docx(p):
    texto = ''.join(t.text or '' for t in p.iter(f'{_W}t'))
    estilo = p.find(f'{_W}pPr/{_W}pStyle')
    nome = (estilo.get(f'{_W}val') if estilo is not None else '') or ''
    nivel = re.search(r'(?:heading|t[ií]tulo|ttulo)\s*([1-6])', nome, re.I)
    if nivel and texto.strip():
        return '#' * int(nivel.group(1)) + ' ' + texto
    if re.fullmatch(r'(?i)title|t[ií]tulo', nome) and texto.strip():
        return '# ' + texto
    return texto


def _texto_pdf(dados):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ErroDocumento('Para ler PDF, instale o pacote pypdf no servidor (pip install pypdf) ou envie o documento em .docx ou .md.')
    try:
        leitor = PdfReader(io.BytesIO(dados))
        return '\n'.join(f'# Página {i}\n{(pagina.extract_text() or "").strip()}' for i, pagina in enumerate(leitor.pages, 1))
    except Exception as e:
        raise ErroDocumento(f'Não foi possível ler o PDF: {e}')


def _decodificar(dados):
    for codificacao in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode('utf-8', errors='replace')


def extrair_texto(nome_arquivo, dados):
    extensao = os.path.splitext(nome_arquivo or '')[1].lower()
    if extensao not in EXTENSOES:
        raise ErroDocumento('Formato não aceito. Use .md, .txt, .html, .docx ou .pdf.')
    if len(dados) > LIMITE_ARQUIVO_MB * 1024 * 1024:
        raise ErroDocumento(f'Arquivo maior que {LIMITE_ARQUIVO_MB} MB.')
    if extensao == '.docx':
        texto = _texto_docx(dados)
    elif extensao == '.pdf':
        texto = _texto_pdf(dados)
    elif extensao in ('.html', '.htm'):
        texto = _texto_html(_decodificar(dados))
    else:
        texto = _decodificar(dados)
    texto = re.sub(r'[ \t\r\f\v]+\n', '\n', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto).strip()
    if len(texto) < MINIMO_CARACTERES_DOCUMENTO:
        raise ErroDocumento('Não encontrei texto no arquivo (se for PDF escaneado, envie uma versão com texto).')
    return texto


# ------------------------------------------------------------------------------
# Divisão em trechos (por seção; seções grandes viram vários trechos)
# ------------------------------------------------------------------------------
_TITULO_MD = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$')


def dividir(texto, titulo_documento=''):
    """Devolve [(seção, texto)]. A seção é o caminho de títulos (ex.: '2. Requisitos › 2.1 Login')."""
    secoes, caminho, atual = [], [], []

    def fechar():
        corpo = '\n'.join(atual).strip()
        if corpo:
            secoes.append((' › '.join(t for _, t in caminho) or titulo_documento, corpo))

    for linha in texto.split('\n'):
        m = _TITULO_MD.match(linha.strip())
        if m:
            fechar()
            atual = []
            nivel = len(m.group(1))
            caminho = [(n, t) for n, t in caminho if n < nivel] + [(nivel, m.group(2).strip()[:120])]
        else:
            atual.append(linha)
    fechar()

    trechos = []
    for secao, corpo in secoes:
        for parte in _quebrar(corpo):
            trechos.append((secao[:300], parte))
    return trechos


def _quebrar(corpo):
    if len(corpo) <= MAXIMO_TRECHO:
        return [corpo]
    partes, atual = [], ''
    for paragrafo in re.split(r'\n\s*\n', corpo):
        if len(paragrafo) > MAXIMO_TRECHO:  # parágrafo enorme: corta por frases
            for frase in re.split(r'(?<=[.!?;])\s+', paragrafo):
                if len(atual) + len(frase) > TAMANHO_TRECHO and atual:
                    partes.append(atual.strip())
                    atual = ''
                atual += frase[:MAXIMO_TRECHO] + ' '
            continue
        if len(atual) + len(paragrafo) > TAMANHO_TRECHO and atual:
            partes.append(atual.strip())
            atual = ''
        atual += paragrafo + '\n\n'
    if atual.strip():
        partes.append(atual.strip())
    return partes


def _gravar_trechos(fonte, trechos):
    TrechoConhecimento.query.filter_by(fonte_id=fonte.id).delete(synchronize_session=False)
    total = 0
    for ordem, (secao, texto) in enumerate(trechos):
        texto = sem_segredos(texto)
        total += len(texto)
        db.session.add(TrechoConhecimento(fonte_id=fonte.id, ordem=ordem, secao=sem_segredos(secao), texto=texto))
    fonte.total_trechos = len(trechos)
    fonte.total_caracteres = total
    _INDICE.clear()


def _hash(texto):
    return hashlib.sha256((texto or '').encode('utf-8')).hexdigest()


# ------------------------------------------------------------------------------
# Documentos do projeto (PRD, PTD, DTD...)
# ------------------------------------------------------------------------------
def pasta_documentos(raiz_uploads):
    caminho = os.path.join(raiz_uploads, PASTA)
    os.makedirs(caminho, exist_ok=True)
    return caminho


def adicionar_documento(tipo, titulo, nome_arquivo, dados, raiz_uploads, usuario_id=None, descricao=''):
    """Grava o arquivo, extrai o texto e cria a fonte (nova versão se já houver uma com o mesmo tipo e título)."""
    from werkzeug.utils import secure_filename
    tipo = (tipo or '').upper()
    if tipo not in TIPOS_UPLOAD:
        raise ErroDocumento('Tipo de documento inválido.')
    texto = extrair_texto(nome_arquivo, dados)
    titulo = (titulo or os.path.splitext(nome_arquivo)[0]).strip()[:200] or 'Documento'
    anteriores = FonteConhecimento.query.filter(FonteConhecimento.tipo == tipo,
                                                db.func.lower(FonteConhecimento.titulo) == titulo.lower()).all()
    versao = max([f.versao for f in anteriores] or [0]) + 1
    nome_seguro = secure_filename(nome_arquivo) or 'documento'
    caminho = os.path.join(pasta_documentos(raiz_uploads), f'{uuid.uuid4().hex[:12]}_{nome_seguro}')
    with open(caminho, 'wb') as f:
        f.write(dados)
    fonte = FonteConhecimento(tipo=tipo, titulo=titulo, versao=versao, descricao=(descricao or '').strip()[:1000] or None,
                              arquivo_nome=nome_arquivo[:255], arquivo_caminho=caminho, hash_conteudo=_hash(texto),
                              ativo=True, criado_por_id=usuario_id)
    db.session.add(fonte)
    db.session.flush()
    _gravar_trechos(fonte, dividir(texto, titulo))
    for antiga in anteriores:      # a versão nova substitui as anteriores (que ficam no histórico, desativadas)
        antiga.ativo = False
    db.session.commit()
    return fonte


def alternar(fonte, ativo):
    fonte.ativo = bool(ativo)
    db.session.commit()
    _INDICE.clear()


def excluir(fonte):
    """Apaga a fonte, os trechos e o arquivo enviado (a fonte dos gerentes não é apagada, só desativada)."""
    if fonte.tipo == 'GERENTES':
        raise ErroDocumento('A fonte dos Agentes gerentes não pode ser excluída; desative-a se não quiser usá-la.')
    caminho = fonte.arquivo_caminho
    db.session.delete(fonte)
    db.session.commit()
    _INDICE.clear()
    if caminho and os.path.isfile(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass


# ------------------------------------------------------------------------------
# Conhecimento dos Agentes gerentes
# ------------------------------------------------------------------------------
def _gerente(item):
    tipo = item.tipo or ''
    destinos = item.agentes_destino or ''
    origem = item.origem or ''
    if tipo.startswith('seg_') or '"seguranca"' in destinos or '"seg_' in destinos or 'Segurança' in origem:
        return 'Gerente de Segurança'
    if tipo.startswith('db_') or '"banco"' in destinos or '"db_' in destinos or 'Banco de Dados' in origem:
        return 'Gerente de Banco de Dados'
    if tipo.startswith('fn_') or tipo == 'regra_verificada' or 'funcionalidades' in destinos or '"fn_' in destinos or 'Funcionalidades' in origem:
        return 'Gerente de Funcionalidades'
    return 'Agente Gerente Técnico'


def json_legivel(valor, prefixo='', nivel=0):
    """JSON → linhas 'chave: valor' (lê melhor na busca e na resposta da IA do que o JSON cru)."""
    linhas = []
    recuo = '  ' * nivel
    if isinstance(valor, dict):
        for chave in sorted(valor, key=str):
            v = valor[chave]
            if isinstance(v, (dict, list)) and v and not _lista_simples(v):
                linhas.append(f'{recuo}{chave}:')
                linhas += json_legivel(v, '', nivel + 1)
            else:
                linhas.append(f'{recuo}{chave}: {_simples(v)}')
    elif isinstance(valor, list):
        if _lista_simples(valor):
            linhas.append(f'{recuo}{prefixo}{_simples(valor)}')
        else:
            for item in valor:
                linhas += json_legivel(item, '- ', nivel)
    else:
        linhas.append(f'{recuo}{prefixo}{_simples(valor)}')
    return linhas


def _lista_simples(v):
    return isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v)


def _simples(v):
    if isinstance(v, list):
        return ', '.join(str(x) for x in v) if v else '(vazio)'
    if isinstance(v, dict):
        return '(vazio)'
    if v is None or v == '':
        return '—'
    return str(v)


def _secoes_dos_gerentes():
    """[(seção, texto)] com tudo o que os quatro gerentes sabem hoje."""
    import conhecimento
    import conhecimento_seguranca
    import conhecimento_banco
    import conhecimento_funcional
    import regras_negocio
    import perfis_acesso
    from models import AprendizadoAgente

    secoes = []
    # Como cada gerente trabalha (a documentação de cada módulo de conhecimento)
    for modulo, nome in ((conhecimento, 'Agente Gerente Técnico'), (conhecimento_seguranca, 'Gerente de Segurança'),
                         (conhecimento_banco, 'Gerente de Banco de Dados'), (conhecimento_funcional, 'Gerente de Funcionalidades')):
        linhas_doc = (modulo.__doc__ or '').strip().splitlines()
        doc = '\n'.join(l for l in linhas_doc if not re.fullmatch(r'\s*[=\-~]{3,}\s*', l))  # sem as linhas de sublinhado
        if doc:
            secoes.append((f'{nome} › Como trabalha', doc))

    # Aprendizados aplicados (pendentes, revogados e rejeitados ficam fora). O mapa e os erros do tour são dados de
    # teste dos agentes OmniTest (listas de seletores e páginas): o Guia das telas, abaixo, já explica cada tela.
    internos = ('tour_mapa', 'tour_falha')
    for item in AprendizadoAgente.query.filter_by(status='Aplicado').filter(AprendizadoAgente.tipo.notin_(internos)) \
            .order_by(AprendizadoAgente.id).all():
        try:
            conteudo = json.loads(item.conteudo or '{}')
        except ValueError:
            conteudo = item.conteudo
        try:
            destinos = ', '.join(json.loads(item.agentes_destino or '[]'))
        except ValueError:
            destinos = item.agentes_destino
        partes = [f'{item.codigo} · {item.titulo}', f'Gerente: {_gerente(item)}', f'Tipo: {item.tipo}', f'Origem: {item.origem}',
                  f'Agentes de destino: {destinos}']
        if item.aplicado_em:
            partes.append(f'Aplicado em: {item.aplicado_em:%d/%m/%Y %H:%M}')
        if item.descricao:
            partes.append(f'Descrição: {item.descricao}')
        if item.fonte_url:
            partes.append(f'Fonte oficial: {item.fonte_url}')
        detalhes = '\n'.join(json_legivel(conteudo)) if conteudo not in ({}, [], '', None) else ''
        if detalhes:
            partes.append('Conteúdo:\n' + detalhes)
        secoes.append((f'{_gerente(item)} › {item.codigo} {item.titulo}'[:300], '\n'.join(partes)))

    # Parâmetros das regras de negócio (o que o Gerente de Funcionalidades lê para montar os testes)
    grupos = {}
    for p in regras_negocio.listar():
        unidade = f" {p['unidade']}" if p.get('unidade') else ''
        linha = f"- {p['nome']} ({p['chave']}): {p['valor']}{unidade}" + (f" (padrão {p['padrao']}{unidade})" if p.get('alterado') else '')
        if p.get('descricao'):
            linha += f" — {p['descricao']}"
        grupos.setdefault(p.get('grupo') or 'geral', []).append(linha)
    for grupo, linhas in grupos.items():
        secoes.append((f'Gerente de Funcionalidades › Parâmetros de regras › {grupo}', '\n'.join(linhas)))

    # Módulos de cada perfil (matriz de acesso que os gerentes ensinam aos agentes)
    nomes = {chave: dados[0] for chave, dados in perfis_acesso.MODULOS.items()}
    linhas = [f"- {perfil}: {', '.join(nomes.get(m, m) for m in modulos)}" for perfil, modulos in perfis_acesso.MODULOS_POR_BASE.items()]
    secoes.append(('Gerente de Funcionalidades › Módulos de cada perfil', '\n'.join(linhas)))

    # Guia das telas: onde fica cada tela no menu e o passo a passo do Tour (o "como fazer" para quem usa a plataforma)
    try:
        import guia_telas
        secoes += guia_telas.secoes()
    except Exception:
        pass
    return secoes


_ULTIMA_CONFERENCIA = {'quando': 0.0}


def sincronizar_gerentes(usuario_id=None, forcar=False):
    """Cria/atualiza a fonte dos Agentes gerentes. Devolve (fonte, mudou)."""
    if not forcar and time.time() - _ULTIMA_CONFERENCIA['quando'] < INTERVALO_SINCRONIA:
        fonte = FonteConhecimento.query.filter_by(tipo='GERENTES').first()
        if fonte:
            return fonte, False
    _ULTIMA_CONFERENCIA['quando'] = time.time()
    secoes = _secoes_dos_gerentes()
    trechos = [(secao, parte) for secao, texto in secoes for parte in _quebrar(texto)]
    assinatura = _hash(json.dumps(trechos, ensure_ascii=False))
    fonte = FonteConhecimento.query.filter_by(tipo='GERENTES').first()
    if fonte is None:
        fonte = FonteConhecimento(tipo='GERENTES', titulo=TITULO_GERENTES, versao=1, ativo=True, criado_por_id=None,  # fonte do sistema
                                  descricao='Sincronizada sozinha com os aprendizados aplicados dos Agentes gerentes.')
        db.session.add(fonte)
        db.session.flush()
    elif fonte.hash_conteudo == assinatura and fonte.trechos.count() == fonte.total_trechos == len(trechos):
        return fonte, False
    else:
        fonte.versao = (fonte.versao or 1) + 1
    fonte.hash_conteudo = assinatura
    _gravar_trechos(fonte, trechos)
    db.session.commit()
    return fonte, True


# ------------------------------------------------------------------------------
# Busca (BM25 local)
# ------------------------------------------------------------------------------
_PARADAS = set("""
a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se ao aos à às ou como mais menos
eu voce você me faco faço fazer faz posso pode consigo preciso quero gostaria ajuda ajude favor oi ola olá bom dia tarde noite
qual quais quando onde quem sobre entre isso isto esse essa este esta ser são foi está estão tem têm há meu minha
the of and or to in on for is are be by with what which how when who an it this that
el la los las y del al un una con por para que es son como cual cuales donde quien
""".split())


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', (texto or '').lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def termos(texto):
    """Palavras sem acento, sem palavras vazias e com radical simples (6 letras): desistência ≈ desistente."""
    saida = []
    for palavra in re.findall(r'[a-z0-9_]+', _normalizar(texto)):
        if len(palavra) < 2 or palavra in _PARADAS:
            continue
        saida.append(palavra[:6] if len(palavra) > 6 and not palavra.isdigit() else palavra)
    return saida


# Sinônimos (já no radical de termos()): quem pergunta "criar" ou "apagar" usa outras palavras que a tela
_GRUPOS_SINONIMOS = [
    ('criar', 'cadast', 'novo', 'nova', 'adicio', 'inclui', 'regist'),
    ('excluir', 'exclui', 'apagar', 'remove', 'deleta'),
    ('editar', 'altera', 'mudar', 'trocar', 'corrig'),
    ('ver', 'consul', 'visual', 'abrir', 'acessa'),
    ('enviar', 'mandar', 'convid', 'convite'),
    ('aluno', 'alunos', 'jovem', 'jovens', 'discen'),
    ('projet', 'tcc'),
]
_SINONIMOS = {}
for _grupo in _GRUPOS_SINONIMOS:
    for _termo in _grupo:
        _SINONIMOS.setdefault(_termo, set()).update(t for t in _grupo if t != _termo)

_INDICE = {}


def _indice():
    """Índice em memória das fontes ativas; refeito quando alguma fonte ou trecho muda."""
    marca = db.session.query(db.func.count(TrechoConhecimento.id), db.func.max(TrechoConhecimento.id),
                             db.func.max(FonteConhecimento.atualizado_em)).select_from(FonteConhecimento) \
        .outerjoin(TrechoConhecimento, TrechoConhecimento.fonte_id == FonteConhecimento.id) \
        .filter(FonteConhecimento.ativo.is_(True)).first()
    chave = tuple(str(x) for x in marca)
    if _INDICE.get('chave') == chave:
        return _INDICE
    linhas = db.session.query(TrechoConhecimento, FonteConhecimento).join(FonteConhecimento) \
        .filter(FonteConhecimento.ativo.is_(True)).all()
    documentos, df = [], Counter()
    for trecho, fonte in linhas:
        contagem = Counter(termos(f'{trecho.secao or ""} {fonte.titulo} {trecho.texto}'))
        nome = set(termos((trecho.secao or '').split(' › ')[-1]))  # nome da tela/seção: vale mais na busca
        documentos.append((trecho.id, contagem, sum(contagem.values()), nome))
        df.update(contagem.keys())
    _INDICE.clear()
    _INDICE.update(chave=chave, documentos=documentos, df=df, n=len(documentos),
                   media=(sum(d[2] for d in documentos) / len(documentos)) if documentos else 1)
    return _INDICE


def buscar(pergunta, limite=8, tipos=None):
    """Trechos mais relevantes das fontes ativas: [(pontuação, trecho, fonte)]."""
    indice = _indice()
    consulta = termos(pergunta)
    if not consulta or not indice['n']:
        return []
    k1, b = 1.4, 0.75
    pesos = {termo: 1.0 for termo in consulta}
    for termo in consulta:                       # sinônimos com meio peso: "criar" também acha "cadastre"
        for sinonimo in _SINONIMOS.get(termo, ()):
            pesos.setdefault(sinonimo, 0.5)
    pontos = []
    for trecho_id, contagem, tamanho, nome in indice['documentos']:
        nota = 0.0
        for termo, peso in pesos.items():
            tf = contagem.get(termo)
            if not tf:
                continue
            idf = math.log(1 + (indice['n'] - indice['df'][termo] + 0.5) / (indice['df'][termo] + 0.5))
            nota += peso * idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * tamanho / indice['media']))
        if nota > 0 and nome & set(pesos):   # a pergunta cita o nome da tela ("projeto" → tela Projetos)
            nota *= 1.6
        if nota > 0:
            pontos.append((nota, trecho_id))
    pontos.sort(reverse=True)
    ids = [i for _, i in pontos[:limite * 3]]
    if not ids:
        return []
    trechos = {t.id: t for t in TrechoConhecimento.query.filter(TrechoConhecimento.id.in_(ids)).all()}
    resultado = []
    for nota, trecho_id in pontos[:limite * 3]:
        trecho = trechos.get(trecho_id)
        if trecho is None or (tipos and trecho.fonte.tipo not in tipos):
            continue
        resultado.append((round(nota, 3), trecho, trecho.fonte))
        if len(resultado) >= limite:
            break
    return resultado


def resumo():
    """Para a tela: fontes ativas e inativas, com contagens."""
    fontes = FonteConhecimento.query.all()
    fontes.sort(key=lambda f: (f.tipo != 'GERENTES', f.tipo, f.titulo.lower(), -f.versao))
    ativas = [f for f in fontes if f.ativo]
    return {'fontes': fontes, 'ativas': len(ativas), 'trechos': sum(f.total_trechos for f in ativas),
            'por_tipo': Counter(f.tipo for f in ativas)}
