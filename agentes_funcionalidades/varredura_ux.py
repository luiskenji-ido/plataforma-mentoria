# -*- coding: utf-8 -*-
"""
VARREDURA DE UX/UI — o olho do Agente UX sobre 100% das telas
==============================================================
Um cliente novo só usa a plataforma sozinho se toda tela falar a língua dele, puder ser usada por leitor de tela e
chamar cada papel sempre do mesmo jeito. Esta varredura lê todos os templates (templates/*.html) e aponta:
  - TEXTO VISÍVEL FORA DO t()/tt(): texto da tela, placeholder, title, alt ou aria-label escrito direto em português
    (nunca vira inglês nem espanhol);
  - tt() SEM TRADUÇÃO: texto passado ao tt() que não está em traducoes_literais.py (ou está sem en/es);
  - t() SEM TRADUÇÃO: chave do t() que não existe em traducoes.py, ou existe só em português;
  - FUNÇÃO DE TRADUÇÃO ESCONDIDA: t()/tt() chamado dentro de {% for t in ... %} ou depois de {% set t = ... %} (erro 500);
  - IMAGEM SEM alt, e BOTÃO OU LINK SEM NOME (sem texto e sem title/aria-label: o leitor de tela diz só "botão");
  - CAMPO SEM RÓTULO: input/select/textarea sem <label>, aria-label ou title (o placeholder some ao digitar);
  - LAYOUT ESTOURADO: a grade 'row' na própria parte do modal/card (modal-body row): o miolo fica mais largo que o
    topo e o rodapé (a varredura no navegador, nos agentes de perfil, mede o estouro de verdade);
  - PAPEL COM NOME TROCADO: nas telas listadas na regra nomeada NOME_DO_PAPEL_NAS_TELAS (app.py), o papel aparece
    com outro nome (ex.: "Mentor" onde a regra diz "Professor(a)"). Mudar a regra muda o que o agente espera.
Uma exceção consciente leva o comentário {# ux: ok - motivo #} na linha apontada; um trecho inteiro (ex.: um texto
jurídico) fica entre {# ux: ok-inicio - motivo #} e {# ux: ok-fim #}.

Uso: python agentes_funcionalidades/varredura_ux.py  (lista os achados)
"""
import os
import re
import sys
from html.parser import HTMLParser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TELAS = os.path.join(RAIZ, 'templates')
MARCA_EXCECAO = 'ux: ok'
LETRAS = re.compile(r'[A-Za-zÀ-ÿ]{2,}')
# Siglas, marcas e unidades iguais em pt/en/es: sozinhas não precisam de tradução
NAO_TRADUZ = {'TCC', 'TCCs', 'PDF', 'ESG', 'Q&A', 'LGPD', 'CSV', 'URL', 'ID', 'YouTube', 'Markdown', 'HTML', 'TXT', 'MySQL',
              'SQLite', 'IA', 'AI', 'KPI', 'KPIs', 'B2B', 'MB', 'KB', 'GB', 'min', 'h', 'OK', 'JSON', 'SQL', 'PNG', 'JPG', 'SVG',
              'DOCX', 'XLSX', 'PPTX', 'Word', 'Excel', 'Teams', 'Zoom', 'Meet', 'Google', 'Microsoft', 'API', 'QR', 'Code', 'Email',
              'Omnitest', 'OmniTest', 'PRD', 'TI', 'RH', 'UX', 'UI', 'Dev', 'SSL', 'HTTPS', 'HTTP', 'Gemini', 'Claude',
              'OpenAI', 'GPT', 'Anthropic', 'AWS', 'Azure', 'GCP', 'Nginx', 'Flask', 'Python', 'IP', 'UTC', 'CPF', 'CNPJ',
              'vs', 'px', 'e.g', 'Gmail', 'Outlook', 'LinkedIn', 'Check-in', 'Check-out', 'Commit', 'US$', 'tokens',
              'Total', 'Ticket', 'US', 'Min', 'auto', 'PTD', 'DTD', 'Microsoft 365'}
# Endereços, e-mails, caminhos e nomes técnicos (https://..., contato@empresa.com, backups/, horas_minimas) não se traduzem
TECNICO = re.compile(r"\S*(?://|@|_)\S*|\b[a-z0-9.-]+/[\w./…-]*|\b[\w-]+(?:\.[a-z]{2,})+\b")
ATRIBUTOS_VISIVEIS = ('placeholder', 'title', 'alt', 'aria-label')
CAMPOS_SEM_ROTULO = {'hidden', 'submit', 'button', 'reset', 'image'}
# Partes de modal/card que não podem ser a própria grade: a classe 'row' (margens negativas) estoura as bordas da caixa
PARTES_DE_CAIXA = {'modal-body', 'modal-header', 'modal-footer', 'card-body', 'card-header', 'card-footer'}
CHAMADA_TT = re.compile(r"(?<![\w.])tt\(\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*\)")
CHAMADA_T = re.compile(r"(?<![\w.])t\(\s*('[^'\\]*'|\"[^\"\\]*\")\s*\)")
EXPRESSAO = re.compile(r'\{\{.*?\}\}', re.S)
BLOCO = re.compile(r'\{%.*?%\}', re.S)
COMENTARIO_JINJA = re.compile(r'\{#.*?#\}', re.S)
COMENTARIO_HTML = re.compile(r'<!--.*?-->', re.S)
MARCA_EXPRESSAO = '\x01'  # lugar de um {{ ... }} (conta como conteúdo dinâmico, não como texto escrito)


def _telas():
    for nome in sorted(os.listdir(PASTA_TELAS)):
        if nome.endswith('.html'):
            yield os.path.join(PASTA_TELAS, nome)


def _legivel(texto):
    """Devolve o {{ }} no lugar das marcas internas (para o trecho do relatório)."""
    return re.sub(MARCA_EXPRESSAO + r'\d+' + MARCA_EXPRESSAO, '{{…}}', ' '.join(str(texto).split()))


def _achado(arquivo, linha, tipo, trecho, sugestao):
    return {'arquivo': os.path.relpath(arquivo, RAIZ).replace(os.sep, '/'), 'linha': linha, 'tipo': tipo,
            'trecho': _legivel(trecho)[:160], 'sugestao': _legivel(sugestao)}


def _apagar(regex, texto, troca=''):
    """Troca o trecho casado por `troca`, mantendo as quebras de linha (os números de linha continuam valendo)."""
    return regex.sub(lambda m: troca + '\n' * m.group(0).count('\n'), texto)


def _texto_escrito(valor):
    """O que sobra de texto escrito à mão (sem expressões, siglas e números); '' quando não há o que traduzir."""
    sobra = TECNICO.sub(' ', re.sub(MARCA_EXPRESSAO + r'\d+' + MARCA_EXPRESSAO, ' ', valor))
    palavras = [p for p in re.findall(r"[A-Za-zÀ-ÿ&]+(?:[.'’-][A-Za-zÀ-ÿ]+)*", sobra) if p not in NAO_TRADUZ]
    return ' '.join(valor.split()) if any(LETRAS.search(p) for p in palavras) else ''


def _linhas_isentas(linhas):
    """Linhas com {# ux: ok #} e as de um bloco {# ux: ok-inicio ... #} ... {# ux: ok-fim #} (exceções conscientes)."""
    isentas, bloco = set(), False
    for n, linha in enumerate(linhas, 1):
        if MARCA_EXCECAO + '-inicio' in linha:
            bloco = True
        if bloco or MARCA_EXCECAO in linha:
            isentas.add(n)
        if MARCA_EXCECAO + '-fim' in linha:
            bloco = False
    return isentas


class _LeitorDeTela(HTMLParser):
    """Lê uma tela já sem o Jinja e junta os achados de texto, nomes acessíveis e rótulos."""

    def __init__(self, caminho, linhas):
        super().__init__(convert_charrefs=True)
        self.caminho, self.linhas, self.achados = caminho, linhas, []
        self.ignorar = 0            # dentro de <script>/<style>
        self.abertos = []           # <a>/<button> abertos: [tag, linha, attrs, tem_nome]
        self.rotulos = 0            # dentro de <label>
        self.rotulos_para = set()   # ids citados em <label for="...">
        self.campos = []            # (linha, tag, id, trecho)
        self.titulo = 0
        self.isentas = _linhas_isentas(linhas)

    def _linha_ok(self, n):
        return n in self.isentas

    def _registrar(self, linha, tipo, trecho, sugestao):
        if not self._linha_ok(linha):
            self.achados.append(_achado(self.caminho, linha, tipo, trecho, sugestao))

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignorar += 1
            return
        if self.ignorar:
            return
        linha = self.getpos()[0]
        a = {k: (v or '') for k, v in attrs}
        tipo = a.get('type', 'text').lower()
        for nome in ATRIBUTOS_VISIVEIS + (('value',) if tag == 'input' and tipo in ('submit', 'button', 'reset') else ()):
            if nome in a and _texto_escrito(a[nome]):
                self._registrar(linha, 'Texto visível fora do t()/tt()', f'{nome}="{a[nome]}"',
                                f"Trocar por {nome}=\"{{{{ tt('{a[nome].strip()}') }}}}\" e pôr a tradução em traducoes_literais.py.")
        classes = set(re.sub(MARCA_EXPRESSAO + r'\d+' + MARCA_EXPRESSAO, ' ', a.get('class', '')).split())
        partes = classes & PARTES_DE_CAIXA
        if 'row' in classes and partes:
            self._registrar(linha, 'Layout estourado', self.linhas[linha - 1],
                            f"A grade 'row' (margens negativas) está no próprio {sorted(partes)[0]}: o miolo fica mais largo que o topo e o "
                            f"rodapé. Embrulhar: <{tag} class=\"{sorted(partes)[0]}\"><div class=\"row ...\">...</div></{tag}>.")
        if tag == 'img':
            if 'alt' not in a:
                self._registrar(linha, 'Imagem sem alt', self.linhas[linha - 1],
                                'Pôr alt="{{ tt(\'o que a imagem mostra\') }}" (ou alt="" se for só enfeite).')
            for aberto in self.abertos:
                aberto[3] = aberto[3] or bool(a.get('alt', '').strip())
        if tag in ('a', 'button'):
            nome_acessivel = any(a.get(k, '').strip() for k in ('title', 'aria-label', 'aria-labelledby'))
            clicavel = tag == 'button' or 'href' in a or 'onclick' in a or 'data-bs-toggle' in a
            self.abertos.append([tag, linha, a, nome_acessivel or not clicavel])
        if tag == 'label':
            self.rotulos += 1
            if a.get('for'):
                self.rotulos_para.add(a['for'])
        if tag == 'title':
            self.titulo += 1
        if tag in ('input', 'select', 'textarea') and tipo not in CAMPOS_SEM_ROTULO:
            if not (self.rotulos or any(a.get(k, '').strip() for k in ('aria-label', 'aria-labelledby', 'title'))):
                self.campos.append((linha, tag, a.get('id', ''), self.linhas[linha - 1]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignorar = max(0, self.ignorar - 1)
            return
        if self.ignorar:
            return
        if tag in ('a', 'button'):
            for i in range(len(self.abertos) - 1, -1, -1):
                if self.abertos[i][0] == tag:
                    self._fechar(self.abertos.pop(i))
                    break
        if tag == 'label':
            self.rotulos = max(0, self.rotulos - 1)
        if tag == 'title':
            self.titulo = max(0, self.titulo - 1)

    def _fechar(self, aberto):
        tag, linha, a, tem_nome = aberto
        if not tem_nome:
            self._registrar(linha, 'Botão ou link sem nome' if tag == 'button' else 'Link sem nome', self.linhas[linha - 1],
                            'Só tem ícone: pôr title="{{ tt(\'o que faz\') }}" (ou aria-label) para o leitor de tela e a dica do mouse.')

    def handle_data(self, dados):
        if self.ignorar or not dados.strip():
            return
        for aberto in self.abertos:
            aberto[3] = True
        escrito = _texto_escrito(dados)
        if escrito:
            linha = self.getpos()[0] + dados[:len(dados) - len(dados.lstrip())].count('\n')
            self._registrar(linha, 'Texto visível fora do t()/tt()', escrito,
                            f"Trocar por {{{{ tt('{escrito.strip()}') }}}} e pôr a tradução em traducoes_literais.py.")

    def terminar(self):
        self.close()
        for aberto in self.abertos:
            self._fechar(aberto)
        for linha, tag, ident, trecho in self.campos:
            if not (ident and ident in self.rotulos_para):
                self._registrar(linha, 'Campo sem rótulo', trecho,
                                'Ligar a um <label for="id"> ou pôr aria-label="{{ tt(\'o que preencher\') }}" (o placeholder some ao digitar).')
        return self.achados


def _sem_jinja(texto):
    """A tela sem Jinja: comentários e {% %} somem, cada {{ }} vira uma marca de conteúdo dinâmico (as linhas não mudam)."""
    texto = _apagar(COMENTARIO_JINJA, texto)
    texto = _apagar(BLOCO, texto)
    # {{ }} entre aspas de atributo continua dentro das aspas; cada expressão diferente ganha a própria marca (ids de label)
    vistas = {}
    return EXPRESSAO.sub(lambda m: MARCA_EXPRESSAO + str(vistas.setdefault(' '.join(m.group(0).split()), len(vistas)))
                         + MARCA_EXPRESSAO + '\n' * m.group(0).count('\n'), texto)


def varrer_marcacao(caminho):
    """Texto fora do t()/tt(), imagens sem alt, botões/links sem nome e campos sem rótulo."""
    original = open(caminho, encoding='utf-8').read()
    leitor = _LeitorDeTela(caminho, original.splitlines())
    leitor.feed(_sem_jinja(original))
    return leitor.terminar()


# ------------------------------------------------------------------------------ traduções do t() e do tt()
def _traducoes():
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)
    import traducoes
    import traducoes_literais
    return traducoes.TEXTOS, traducoes_literais.LITERAIS


def _literal(texto):
    import ast
    try:
        return ast.literal_eval(texto)
    except (ValueError, SyntaxError):
        return None


def varrer_traducoes(caminho):
    """tt() com texto fora de traducoes_literais.py e t() com chave inexistente ou só em português."""
    textos, literais = _traducoes()
    achados = []
    original = open(caminho, encoding='utf-8').read()
    isentas = _linhas_isentas(original.splitlines())
    sem_comentarios = _apagar(COMENTARIO_HTML, _apagar(COMENTARIO_JINJA, original))
    for n, linha in enumerate(sem_comentarios.splitlines(), 1):
        if n in isentas:
            continue
        for bruto in CHAMADA_TT.findall(linha):
            texto = _literal(bruto)
            if not isinstance(texto, str) or not texto.strip():
                continue
            traducao = literais.get(texto) or literais.get(texto.strip())
            if not traducao:
                achados.append(_achado(caminho, n, 'tt() sem tradução', texto,
                                       f"Pôr '{texto}': ('english', 'español') em traducoes_literais.py."))
            elif not all(str(x).strip() for x in traducao[:2]):
                achados.append(_achado(caminho, n, 'tt() sem tradução', texto, 'Completar o inglês e o espanhol em traducoes_literais.py.'))
        for bruto in CHAMADA_T.findall(linha):
            chave = _literal(bruto)
            if not isinstance(chave, str):
                continue
            if chave not in textos.get('pt', {}):
                achados.append(_achado(caminho, n, 't() com chave inexistente', chave,
                                       f"Criar a chave '{chave}' em traducoes.py (pt, en e es): hoje a tela mostra o nome da chave."))
            else:
                faltam = [i for i in ('en', 'es') if chave not in textos.get(i, {})]
                if faltam:
                    achados.append(_achado(caminho, n, 't() sem tradução', chave,
                                           f"A chave '{chave}' não tem {' nem '.join(faltam)} em traducoes.py (a tela fica em português)."))
    return achados + varrer_funcoes_escondidas(caminho, sem_comentarios, isentas)


LACO_OU_SET = re.compile(r'\{%-?\s*(for\s+([\w\s,]+?)\s+in\b|endfor\b|set\s+(\w+)\s*=)')
CHAMADA_FUNCAO = re.compile(r'(?<![\w.])(tt|t)\(')


def varrer_funcoes_escondidas(caminho, texto, isentas):
    """t()/tt() chamados onde um laço ({% for t in ... %}) ou um {% set t = ... %} trocou a função por um dado: a tela
    quebra com erro 500 ('Turma' object is not callable)."""
    eventos = sorted([(m.start(), 'bloco', m) for m in LACO_OU_SET.finditer(texto)] +
                     [(m.start(), 'chamada', m) for m in CHAMADA_FUNCAO.finditer(texto)], key=lambda e: e[0])
    lacos, globais, achados = [], set(), []
    for pos, tipo, m in eventos:
        if tipo == 'bloco':
            if m.group(2):
                lacos.append({v.strip() for v in m.group(2).split(',')})
            elif m.group(0).rstrip().endswith('endfor') and lacos:
                lacos.pop()
            elif m.group(3):
                (lacos[-1] if lacos else globais).add(m.group(3))
            continue
        nome = m.group(1)
        n = texto.count('\n', 0, pos) + 1
        if n not in isentas and (nome in globais or any(nome in vs for vs in lacos)):
            achados.append(_achado(caminho, n, 'Função de tradução escondida', texto.splitlines()[n - 1].strip(),
                                   f"A variável '{nome}' do laço ou do set esconde a função {nome}(): renomear a variável "
                                   f"(ex.: {{% for turma in ... %}}) ou usar a outra função de tradução."))
    return achados


# ------------------------------------------------------------------------------ o mesmo papel com o mesmo nome
def _regra_dos_papeis():
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)
    try:
        import app as modulo_app
        return getattr(modulo_app, 'NOME_DO_PAPEL_NAS_TELAS', {}) or {}
    except Exception:
        return {}


def varrer_papeis(regra=None):
    """Nas telas da regra NOME_DO_PAPEL_NAS_TELAS, o papel aparece sempre com o nome da regra (texto da tela, tt() e t())."""
    regra = _regra_dos_papeis() if regra is None else regra
    textos, _ = _traducoes()
    achados = []
    for tela, papeis in regra.items():
        caminho = os.path.join(PASTA_TELAS, tela)
        if not os.path.exists(caminho):
            achados.append(_achado(caminho, 0, 'Papel com nome trocado', tela, 'A regra NOME_DO_PAPEL_NAS_TELAS cita uma tela que não existe.'))
            continue
        original = open(caminho, encoding='utf-8').read()
        linhas = original.splitlines()
        isentas = _linhas_isentas(linhas)
        visivel = _apagar(BLOCO, _apagar(COMENTARIO_JINJA, original))
        visivel = _apagar(COMENTARIO_HTML, visivel)
        for nome_certo, outros_nomes in papeis.items():
            errado = re.compile(r'\b(' + '|'.join(re.escape(o) for o in sorted(outros_nomes, key=len, reverse=True))
                                + r')(?![\w(])(?!\s+Administrador)')
            for n, linha in enumerate(visivel.splitlines(), 1):
                if n in isentas:
                    continue
                # texto da tela e do tt() (o que está fora de {{ }} e os textos literais do tt()); da t(), o português da chave
                pedacos = [EXPRESSAO.sub(' ', linha)] + [_literal(b) or '' for b in CHAMADA_TT.findall(linha)]
                pedacos += [str(textos.get('pt', {}).get(_literal(b), '')) for b in CHAMADA_T.findall(linha)]
                pedacos = [re.sub(r'\w+="[^"]*_\w*"|[\w-]+_[\w-]+', ' ', p) for p in pedacos]  # nomes de campo/variável não contam
                for pedaco in pedacos:
                    m = errado.search(re.sub(r'<[^>]*\b(name|id|class|for|href|value)="[^"]*"', ' ', pedaco))
                    if m:
                        achados.append(_achado(caminho, n, 'Papel com nome trocado', linhas[n - 1].strip(),
                                               f"A regra NOME_DO_PAPEL_NAS_TELAS diz '{nome_certo}' nesta tela: trocar '{m.group(1)}'."))
                        break
    return achados


def varrer():
    """Todos os achados das telas, em ordem de arquivo e linha."""
    achados = []
    for caminho in _telas():
        achados += varrer_marcacao(caminho) + varrer_traducoes(caminho)
    achados += varrer_papeis()
    vistos, unicos = set(), []
    for a in achados:
        chave = (a['arquivo'], a['linha'], a['tipo'], a['trecho'])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)
    return sorted(unicos, key=lambda a: (a['arquivo'], a['linha']))


if __name__ == '__main__':
    lista = varrer()
    for a in lista:
        print(f"{a['arquivo']}:{a['linha']}  [{a['tipo']}]  {a['trecho']}")
    print(f"\n{len(lista)} problema(s) de UX/UI nas telas.")
