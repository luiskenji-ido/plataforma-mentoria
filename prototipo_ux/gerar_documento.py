"""Gera prototipo_ux/Proposta_UX_UI_v2.docx: a versão 2 da proposta, com cada tela nos 4 temas (antes e depois), o contraste
medido (visual atual, protótipo v1 e protótipo v2) e as regras da skill de UX/UI.
Precisa de python-docx e Pillow (pip install python-docx pillow), que não fazem parte do requirements da plataforma.
Rode depois de prototipo_ux/capturar_telas.py e prototipo_ux/comparar_contraste.py: python prototipo_ux/gerar_documento.py"""
import os
import json
import sys
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image

PASTA = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(PASTA, 'capturas')
LEVES = os.path.join(CAP, 'doc')  # cópias em JPEG reduzidas, para o documento não passar de poucos MB
sys.path.insert(0, PASTA)
from paletas import PALETAS, PARES, razao  # noqa: E402

AZUL, CINZA, ESCURO = RGBColor(0x1A, 0x52, 0xB8), RGBColor(0x4F, 0x5B, 0x6B), RGBColor(0x15, 0x20, 0x30)
TEMAS = ['claro', 'escuro', 'futurista', 'vintage']
NOME_TEMA = {'claro': 'Claro', 'escuro': 'Escuro', 'futurista': 'Futurista', 'vintage': 'Vintage'}

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for lado in ('left_margin', 'right_margin'):
    setattr(sec, lado, Cm(1.8))
sec.top_margin = sec.bottom_margin = Cm(1.8)
LARGURA = Cm(17.4)

estilos = doc.styles
estilos['Normal'].font.name = 'Calibri'
estilos['Normal'].font.size = Pt(10.5)
estilos['Normal'].element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')
estilos['Normal'].paragraph_format.space_after = Pt(4)
for nome, tam, antes, depois in (('Title', 24, 0, 6), ('Heading 1', 16, 16, 6), ('Heading 2', 12.5, 10, 4)):
    e = estilos[nome]
    e.font.name, e.font.size, e.font.bold, e.font.color.rgb = 'Calibri', Pt(tam), True, ESCURO if nome != 'Heading 1' else AZUL
    e.paragraph_format.space_before, e.paragraph_format.space_after, e.paragraph_format.keep_with_next = Pt(antes), Pt(depois), True


def leve(arquivo, largura_px=1100):
    """Cópia JPEG reduzida da captura (as PNG de 1440 px deixariam o documento com dezenas de MB)."""
    os.makedirs(LEVES, exist_ok=True)
    destino = os.path.join(LEVES, os.path.splitext(arquivo)[0] + '.jpg')
    origem = os.path.join(CAP, arquivo)
    if not os.path.exists(destino) or os.path.getmtime(destino) < os.path.getmtime(origem):
        img = Image.open(origem).convert('RGB')
        if img.width > largura_px:
            img = img.resize((largura_px, round(img.height * largura_px / img.width)), Image.LANCZOS)
        img.save(destino, 'JPEG', quality=82, optimize=True)
    return destino


def rodape_com_pagina():
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Proposta de UX/UI · versão 2 · página ')
    r.font.size, r.font.color.rgb = Pt(8.5), CINZA
    for tipo, texto in (('begin', None), (None, 'PAGE'), ('end', None)):
        run = p.add_run()
        run.font.size, run.font.color.rgb = Pt(8.5), CINZA
        if tipo:
            f = OxmlElement('w:fldChar'); f.set(qn('w:fldCharType'), tipo); run._r.append(f)
        else:
            t = OxmlElement('w:instrText'); t.set(qn('xml:space'), 'preserve'); t.text = texto; run._r.append(t)


def par(texto, cor=None, tam=None, negrito=False, italico=False, depois=None):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold, r.italic = negrito, italico
    if cor:
        r.font.color.rgb = cor
    if tam:
        r.font.size = Pt(tam)
    if depois is not None:
        p.paragraph_format.space_after = Pt(depois)
    return p


def lista(itens):
    for item in itens:
        p = doc.add_paragraph(style='List Bullet')
        if isinstance(item, tuple):
            r = p.add_run(item[0]); r.bold = True
            p.add_run(' ' + item[1])
        else:
            p.add_run(item)
        p.paragraph_format.space_after = Pt(2)


def imagem(arquivo, legenda, largura=LARGURA):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(leve(arquivo), width=largura)
    c = par(legenda, cor=CINZA, tam=9, italico=True, depois=8)
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER


def sombrear(cel, cor):
    pr = cel._tc.get_or_add_tcPr()
    s = OxmlElement('w:shd'); s.set(qn('w:val'), 'clear'); s.set(qn('w:color'), 'auto'); s.set(qn('w:fill'), cor.lstrip('#'))
    pr.append(s)


def sem_quebra(linha):
    pr = linha._tr.get_or_add_trPr()
    c = OxmlElement('w:cantSplit'); c.set(qn('w:val'), 'true'); pr.append(c)


def tabela(cabecalho, linhas, larguras, tam=9.5):
    t = doc.add_table(rows=1, cols=len(cabecalho))
    t.style = 'Light Grid Accent 1'
    for i, texto in enumerate(cabecalho):
        cel = t.rows[0].cells[i]
        cel.text = ''
        r = cel.paragraphs[0].add_run(texto); r.bold = True; r.font.size = Pt(tam)
    for linha in linhas:
        cels = t.add_row().cells
        for i, texto in enumerate(linha):
            cels[i].text = ''
            r = cels[i].paragraphs[0].add_run(str(texto)); r.font.size = Pt(tam)
    for linha in t.rows:
        sem_quebra(linha)
        for i, w in enumerate(larguras):
            linha.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def grade_de_temas(nome, temas=TEMAS, largura=Cm(8.3)):
    """Uma linha por tema: antes (visual atual) à esquerda e depois (protótipo v2) à direita."""
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for col, texto in enumerate(('Antes: visual de hoje', 'Depois: protótipo v2')):
        p = t.cell(0, col).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(texto); r.bold = True; r.font.size = Pt(9.5)
    for tema in temas:
        rotulo = t.add_row()
        sem_quebra(rotulo)
        c = rotulo.cells[0].merge(rotulo.cells[1])
        r = c.paragraphs[0].add_run(f'Tema {NOME_TEMA[tema]}'); r.bold = True; r.font.size = Pt(9); r.font.color.rgb = AZUL
        c.paragraphs[0].paragraph_format.keep_with_next = True
        linha = t.add_row()
        sem_quebra(linha)
        for col, versao in enumerate(('antes', 'depois')):
            arq = f'{nome}_{tema}_{versao}.png'
            p = linha.cells[col].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if os.path.exists(os.path.join(CAP, arq)):
                p.add_run().add_picture(leve(arq, 900), width=largura)
    doc.add_paragraph()


def tela(numero, titulo, nome, mudancas, nota=None):
    doc.add_page_break()
    doc.add_heading(f'{numero}. {titulo}', level=1)
    lista(mudancas)
    if nota:
        par(nota, cor=CINZA, tam=9.5)
    grade_de_temas(nome)


# ---------------------------------------------------------------- números do contraste
with open(os.path.join(CAP, 'contraste.json'), encoding='utf-8') as f:
    MEDIDAS = json.load(f)


def resumo(versao):
    saida = {}
    for tema, pags in MEDIDAS.get(versao, {}).items():
        medidos = sum(r['medidos'] for r in pags.values())
        ruins = sum(x['vezes'] for r in pags.values() for x in r['falhas'])
        saida[tema] = (medidos, ruins)
    return saida


def piores_paginas(versao, tema, n=5):
    pags = MEDIDAS.get(versao, {}).get(tema, {})
    return sorted(((sum(x['vezes'] for x in r['falhas']), c.split(':', 1)[1]) for c, r in pags.items()), reverse=True)[:n]


def pct(v):
    m, r = v
    return f'{100 * r / max(m, 1):.1f}% ({r} de {m})'


rodape_com_pagina()
ATUAL, V1, V2 = resumo('atual'), resumo('prototipo_v1'), resumo('prototipo_v2')
TELAS_MEDIDAS = len(next(iter(MEDIDAS['atual'].values())))

# ---------------------------------------------------------------- capa
doc.add_paragraph('Proposta de UX/UI · versão 2', style='Title')
par('Os 4 temas da plataforma, com o contraste de cada texto medido no navegador', cor=CINZA, tam=12, depois=12)
par('A versão 1 propôs um visual “padrão” só no tema claro e, por cima dos temas escuros, deixou letras escuras em fundo escuro e '
    'letras claras em fundo claro. Esta versão parte de outra régua: respeitar o tema que cada pessoa escolheu e medir, texto por texto, '
    'se dá para ler. Nada de produção foi alterado; tudo roda no protótipo, numa cópia do banco.')
doc.add_heading('O resultado em uma tabela', level=2)
par(f'Percentual de textos abaixo do contraste mínimo da WCAG 2.2 (4,5:1; 3:1 no texto grande), nas mesmas {TELAS_MEDIDAS} telas '
    '(administrador e aluno), com as janelas abertas também. Quanto menor, melhor.')
tabela(['Tema', 'Visual de hoje', 'Protótipo v1', 'Protótipo v2'],
       [[NOME_TEMA[t], pct(ATUAL[t]), pct(V1[t]) if t in V1 else '—', pct(V2[t]) if t in V2 else '—'] for t in TEMAS],
       [2.6, 4.9, 4.9, 4.9])
par('O protótipo v1 já foi medido com a régua nova: ele melhorava o tema claro, mas no escuro e no futurista ficava tão ruim quanto '
    'o visual de hoje, que é o que você viu nas telas. (O v1 foi medido com a primeira versão do medidor, que ainda não media o '
    'texto sobre degradê; por isso mediu um pouco menos de textos.)', cor=CINZA, tam=9.5)
doc.add_heading('Como experimentar', level=2)
lista([('Protótipo:', 'python prototipo_ux/rodar_prototipo.py → http://127.0.0.1:5070. Troque o tema no menu (Claro, Escuro, Futurista, Vintage).'),
       ('Visual de hoje, com os mesmos dados:', 'python prototipo_ux/rodar_prototipo.py --sem-tema → http://127.0.0.1:5071'),
       ('Contas de demonstração:', 'Administrador e Aluno, em prototipo_ux/LEIAME.md. Só existem na cópia do protótipo.'),
       ('Medir de novo:', 'python prototipo_ux/comparar_contraste.py (os dois servidores no ar).'),
       ('Para desfazer:', 'apagar a pasta prototipo_ux.')])

# ---------------------------------------------------------------- o que deu errado na v1
doc.add_page_break()
doc.add_heading('1. O que deu errado na versão 1', level=1)
par('As telas que você enviou mostram o problema: a versão 1 trocava as cores só de algumas peças (cartões, botões, tabelas) e '
    'deixava o resto com as cores do tema escolhido.')
lista([('Acompanhamento no tema Escuro:', 'a página ficou clara, mas o bloco “Perfil da Entrevista” continuou preto com letra cinza escura, e os títulos em âmbar ficaram sobre fundo branco.'),
       ('Agentes de Segurança no tema Escuro:', 'a árvore de pastas ficou com letra quase branca sobre cartão branco: não dava para ler.'),
       ('Gestão da trilha no tema Futurista:', 'a tabela continuou azul-marinho, o cartão ficou branco e o cabeçalho claro: três fundos que não conversam.'),
       ('Causa:', 'o tema v1 tinha uma paleta só (a clara) e não olhava o tema da pessoa. Não havia nenhuma medida de contraste, só o “olhar” da imagem.')])
imagem('v1_acompanhamento_escuro.png', 'Versão 1, tema Escuro: o Acompanhamento ficou claro com blocos ainda escuros', largura=Cm(15))
imagem('v1_seguranca_escuro.png', 'Versão 1, tema Escuro: a árvore de pastas some no cartão branco', largura=Cm(15))

# ---------------------------------------------------------------- a skill nova
doc.add_page_break()
doc.add_heading('2. A skill de UX/UI nova', level=1)
par('A régua completa está em prototipo_ux/SKILL_UX_UI.md. Ela foi montada com a WCAG 2.2 (nível AA) e com o que as skills de '
    'auditoria de UX/UI do diretório de plugins fazem: contraste medido no navegador (ux-ui-audit), revisão de acessibilidade e de '
    'sistema de design (Design, da Anthropic) e revisão no celular e no computador por ordem de importância (UI Design Review). '
    'Esses plugins podem ser instalados para o dia a dia; o que eles fazem de mais importante já entrou no Agente UX.')
tabela(['Regra', 'O que exige', 'Quem confere'],
       [['R1 Respeitar o tema', 'toda proposta vem nos 4 temas; nada de mostrar só o claro', 'este documento e o protótipo'],
        ['R2 Contraste medido', 'texto 4,5:1, texto grande 3:1, com camadas e opacidade somadas e janelas abertas', 'Agente UX, nos 4 temas (novo)'],
        ['R3 Sem cor solta', 'nada de text-dark, text-white, bg-white, bg-dark ou style="color:…" que só servem a um tema', 'Agente UX (pelo contraste)'],
        ['R4 Fundo forte só em etiqueta, botão e barra', 'cabeçalhos com fundo suave e texto do mesmo estado', 'paleta'],
        ['R5 Uma cor de ação', 'verde, âmbar e vermelho só para estado; no escuro, texto escuro sobre o âmbar', 'paleta'],
        ['R6 Grade dentro da caixa', 'row nunca no próprio modal-body/card-body', 'Agente UX (já fazia)'],
        ['R7 Sem rolagem lateral', '1366 px e 375 px', 'Agente UX (já fazia)'],
        ['R8 Foco visível', 'anel de 3 px na cor de ação', 'tema'],
        ['R9 Alvo de toque', 'botões e campos com 40 px de altura', 'tema'],
        ['R10 Nomes e rótulos', 'campo com rótulo; botão de ícone com nome; texto traduzido', 'Agente UX (já fazia)'],
        ['R11 Hierarquia', 'um título por tela; seções com rótulo curto; ação principal à direita no rodapé', 'revisão'],
        ['R12 Antes e depois com números', 'toda proposta traz a medida do visual de hoje e da proposta, por tema', 'comparar_contraste.py']],
       [4.3, 8.4, 4.7], tam=9)
doc.add_heading('Paletas por tema, conferidas antes de usar', level=2)
par(f'Cada tema tem a sua paleta em prototipo_ux/paletas.py. Os {len(PARES)} pares de cor de cada tema (texto, texto secundário, '
    'links, estados, bordas de campo) são conferidos antes de gravar o tema; se um par ficar abaixo do mínimo, o protótipo nem sobe.')
papeis = [('bg', 'Fundo'), ('surface', 'Cartão'), ('fg', 'Texto'), ('muted', 'Secundário'), ('accent', 'Ação'),
          ('ok-text', 'Ok'), ('warn-text', 'Atenção'), ('bad-text', 'Erro')]
t = doc.add_table(rows=1, cols=len(papeis) + 2)
t.style = 'Table Grid'
for i, texto in enumerate(['Tema'] + [p[1] for p in papeis] + ['Pior par de texto']):
    r = t.rows[0].cells[i].paragraphs[0].add_run(texto); r.bold = True; r.font.size = Pt(8)
for tema in TEMAS:
    p = PALETAS[tema]
    cels = t.add_row().cells
    r = cels[0].paragraphs[0].add_run(NOME_TEMA[tema]); r.bold = True; r.font.size = Pt(8.5)
    for i, (papel, _) in enumerate(papeis, 1):
        sombrear(cels[i], p[papel])
        fundo = p['surface'] if papel not in ('bg', 'surface') else p['fg']
        r = cels[i].paragraphs[0].add_run(p[papel]); r.font.size = Pt(7)
        r.font.color.rgb = RGBColor.from_string((p['fg'] if papel in ('bg', 'surface') else ('ffffff' if razao(p[papel], '#ffffff') > razao(p[papel], '#000000') else '000000')).lstrip('#'))
    pior = min((razao(p[a], p[b]), a, b) for a, b, m in PARES if m == 4.5)
    r = cels[-1].paragraphs[0].add_run(f'{pior[0]:.1f}:1 ({pior[1]} em {pior[2]})'); r.font.size = Pt(7.5)
for linha in t.rows:
    sem_quebra(linha)
    for i, w in enumerate([1.9] + [1.6] * len(papeis) + [2.7]):
        linha.cells[i].width = Cm(w)
doc.add_paragraph()
par('O escuro mantém o âmbar de hoje como cor de ação, e o futurista mantém o ciano. O vintage mantém o verde-garrafa. A diferença é que '
    'cada texto agora tem a cor certa para o fundo daquele tema, inclusive as etiquetas de estado.', cor=CINZA, tam=9.5)

# ---------------------------------------------------------------- telas
tela(3, 'Janela “Agendar banca”', 'banca_modal',
     [('Seções com título:', '“Quando e onde”, “Tempo da apresentação”, “Prazos de entrega” e “Avaliadores”.'),
      ('Avaliadores com busca e etiquetas:', 'no lugar da lista “segure Ctrl”, que não funciona no celular.'),
      ('Escolhas rápidas:', '10 · 15 · 20 min, 5 · 10 · 15 min e 12 · 24 · 48 h, com o número ainda editável.'),
      ('Cabeçalho e rodapé no tema:', 'no escuro e no futurista, a janela inteira fica escura; “Cancelar” ao lado de “Agendar banca”.')])
doc.add_heading('No celular (390 px)', level=2)
t = doc.add_table(rows=2, cols=4)
t.alignment = WD_TABLE_ALIGNMENT.CENTER
for col, (tema, versao) in enumerate((('claro', 'antes'), ('claro', 'depois'), ('escuro', 'antes'), ('escuro', 'depois'))):
    arq = f'banca_celular_{tema}_{versao}.png'
    p = t.cell(0, col).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists(os.path.join(CAP, arq)):
        p.add_run().add_picture(leve(arq, 600), width=Cm(4))
    p = t.cell(1, col).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{NOME_TEMA[tema]} · {versao}'); r.italic = True; r.font.size = Pt(8.5); r.font.color.rgb = CINZA

tela(4, 'Acompanhamento', 'acompanhamento',
     [('Blocos seguem o tema:', 'o “Perfil da Entrevista” deixa de ser preto fixo; no claro fica cinza-claro, no escuro cinza-grafite, sempre com o texto legível.'),
      ('Caderno de anotações no tema:', 'o papel pautado era branco também no escuro; agora papel e pauta acompanham o tema.'),
      ('Botões de integração:', '“Conectar Agenda” e “Conectar Gemini Notebook” usam a cor de ação do tema (o azul fixo ficava em 4,2:1 no claro).')])
tela(5, 'Agentes de Segurança', 'seguranca',
     [('Árvore de pastas legível:', 'no v1, letra quase branca em cartão branco; agora a letra é a do tema.'),
      ('Severidades com cor própria:', 'no futurista de hoje, uma regra pinta todas as etiquetas de azul (Crítica, Alta e Baixa ficam iguais). No protótipo, cada severidade volta à sua cor.'),
      ('Agentes fora da execução:', 'apagados a 30% ficavam em 2,5:1; agora a 85%, ainda “em segundo plano”, mas legíveis.'),
      ('O painel escuro com radar continua:', 'é a identidade da tela; só os horários do console ganharam um cinza mais claro.')])
tela(6, 'Gestão da trilha do TCC', 'trilha_gestao',
     [('Uma superfície só:', 'tabela, cartão e cabeçalho com o mesmo fundo do tema; no futurista de hoje eram três fundos diferentes.'),
      ('Cabeçalho da tabela discreto:', 'letra pequena e secundária, sem faixa preta.'),
      ('Etiquetas de progresso:', '0/5 e 5/5 com fundo suave e texto do estado, legíveis nos 4 temas.')])
tela(7, 'Painel Geral', 'painel',
     [('Menu superior no tema:', 'fundo da superfície, item atual com fundo suave da cor de ação.'),
      ('Cartões de indicadores uniformes:', 'mesma borda, canto e sombra; o número é o destaque.'),
      ('Uma cor de ação:', 'o botão principal na cor de ação do tema; os secundários neutros.')])
tela(8, 'Agenda de bancas', 'bancas',
     [('Etiquetas de estado suaves:', 'Realizada, Agendada e Entregue no prazo com fundo suave e texto do estado.'),
      ('Ações iguais:', 'Sala da banca, Ficha, Editar e Cancelar com o mesmo formato; só Cancelar em vermelho.')])
tela(9, 'Conteúdo do curso', 'conteudo_curso',
     [('Cartões de aula mais limpos:', 'cabeçalho na superfície do tema, etiquetas suaves (vídeo, palavras, perguntas).'),
      ('Formulários:', 'campos com borda de 3:1 e foco visível na cor de ação, em todos os temas.')])
tela(10, 'Sala de estudo (aluno)', 'sala_estudo',
     [('Lista de aulas:', 'aula atual marcada com a cor de ação do tema.'),
      ('Botão principal:', '“Teste seus conhecimentos” como a única ação em destaque da aula.')])
tela(11, 'Hub Educacional', 'hub',
     [('Tabela sem faixa preta:', 'títulos das colunas em letra pequena e secundária.'),
      ('Abas sublinhadas:', 'a aba atual com uma linha na cor de ação.')])

# ---------------------------------------------------------------- produção
doc.add_page_break()
doc.add_heading('12. O que a medição achou no visual de hoje', level=1)
par('A régua nova também mede a produção. Estas são as telas com mais textos abaixo do mínimo hoje; são correções de produção '
    'independentes do novo visual (não foram feitas: ficam para decidir).')
linhas = []
for tema in TEMAS:
    pior = ', '.join(f'{c} ({n})' for n, c in piores_paginas('atual', tema, 4) if n)
    linhas.append([NOME_TEMA[tema], pct(ATUAL[tema]), pior])
tabela(['Tema', 'Abaixo do mínimo', 'Telas com mais textos ruins (quantidade)'], linhas, [2.3, 3.8, 11.3], tam=9)
lista([('Agentes de Funcionalidades e de Segurança:', 'concentram a maior parte: as listas, contagens e consoles usam cores fixas pensadas para fundo escuro.'),
       ('Tema Futurista:', 'a regra “span com style=background” pinta todas as etiquetas de severidade do mesmo azul (perde o significado da cor).'),
       ('Botões de integração do Acompanhamento:', 'azul fixo do Bootstrap (#0D6EFD) em 4,2:1 no tema claro.'),
       ('Caderno de anotações:', 'papel branco fixo, também nos temas escuros.')])

# ---------------------------------------------------------------- agente e decisão
doc.add_heading('13. O que o Agente UX passou a fazer', level=1)
lista([('Contraste nos 4 temas:', 'cada agente de perfil abre as páginas dele em cada tema (até 15 por perfil, sem repetir as que outro perfil já mediu), abre as janelas, mede cada texto e dá um alerta por tema com os piores casos: página, texto, razão, cor da letra e cor do fundo.'),
       ('Mesma medida do protótipo:', 'o agente e o comparar_contraste.py usam o mesmo medidor (agentes_funcionalidades/contraste.py); o número do documento é o número do agente.'),
       ('Paleta conferida:', 'prototipo_ux/paletas.py recusa uma paleta com par abaixo do mínimo; a próxima proposta de cores já nasce conferida.')])
doc.add_heading('14. Para decidir', level=1)
tabela(['Etapa', 'O que entra', 'Risco'],
       [['1. Paletas e tema', 'tokens.css + tema.css do protótipo viram o visual dos 4 temas', 'baixo: se desfaz tirando os dois arquivos'],
        ['2. Correções de contraste da produção', 'as cores fixas da seção 12, mesmo mantendo o visual atual', 'baixo: só cor de texto e fundo'],
        ['3. Formulários longos', 'Agendar banca (pronto no protótipo), reunião, ocorrência e cadastro em seções', 'médio: os agentes de teste acompanham os campos'],
        ['4. Acompanhamento', 'cartão em três partes com o resumo no topo', 'médio: é a tela mais usada pelos alunos']],
       [4.2, 8.4, 4.8])
par('A etapa 2 pode vir antes da 1: ela corrige o que está ilegível hoje sem trocar o visual.', cor=CINZA)

saida = os.path.join(PASTA, 'Proposta_UX_UI_v2.docx')
doc.save(saida)
print('ok', saida, f'{os.path.getsize(saida) / 1e6:.1f} MB')
