# Skill de UX/UI dos agentes (versão 2)

Esta é a régua que o Agente UX e quem propõe um layout novo seguem. A versão 1 olhava só a tela no tema claro e
propôs um visual "padrão de IA" sem conferir a cor das letras. Resultado: no tema escuro, as letras escuras ficaram em
cima de fundo escuro, e as letras claras em cima de fundo claro. A versão 2 parte de quatro princípios:

1. **O tema escolhido manda.** Os 4 temas da plataforma (claro, escuro, futurista, vintage) são propostos juntos.
2. **Contraste medido em todos os temas.** O contraste é medido no navegador, e não estimado a olho.
3. **Cada cor tem um papel.** Uma tela nunca usa uma cor solta.
4. **Uma proposta só vale com números de antes e depois.**

Baseada na WCAG 2.2 (nível AA) e nas skills de mercado de auditoria de UX/UI e acessibilidade, para uso no dia a dia:
- ux-ui-audit: contraste medido no navegador, alvos de toque e anel de foco;
- Design (Anthropic): accessibility-review e design-system;
- UI Design Review: revisão no celular e no computador, pela ordem de importância.

## 1. Cores por papel, nunca cor solta

| Papel | Uso | Regra |
|---|---|---|
| `bg` | fundo da página | — |
| `surface` | cartões e janelas | — |
| `surface2` | faixas internas, cabeçalho de tabela, rodapé de janela | — |
| `line` | bordas discretas | só decoração |
| `field` | borda de campo de formulário | **3:1** contra `bg`, `surface` e `surface2` |
| `fg` | texto | **4,5:1** contra `bg`, `surface`, `surface2` e `accent-soft` |
| `muted` | texto secundário | **4,5:1** contra os mesmos fundos (secundário não quer dizer ilegível) |
| `accent` / `on-accent` | botão principal e o texto dele | **4,5:1** entre os dois |
| `accent-text` | link e texto de ação | **4,5:1** |
| `ok`, `warn`, `bad`, `info` | estados | `<estado>-text` sobre `<estado>-soft`, sobre `surface` e sobre `bg`: **4,5:1** |

- As paletas ficam em `prototipo_ux/paletas.py`, uma por tema.
- `python prototipo_ux/paletas.py` confere os 144 pares (36 por tema) e só grava `tokens.css` se todos passarem.
- O protótipo nem sobe com um par reprovado.

## 2. Regras de tela

- **R1 — Respeitar o tema.** Toda proposta vem nos 4 temas. Mostrar só o tema claro não vale.
- **R2 — Contraste no navegador.** Texto comum precisa de **4,5:1**. Texto grande (24 px, ou 18,66 px em negrito) precisa
  de **3:1**.
  - A medida soma as camadas semitransparentes e a opacidade dos pais.
  - As janelas abertas entram na medida.
  - Ferramenta: `agentes_funcionalidades/contraste.py`.
- **R3 — Sem classe de cor fixa.** Classes como `text-dark`, `text-white`, `bg-white`, `bg-light`, `bg-dark` e
  `style="color:#…"` só ficam certas num tema.
  - Na tela, use o papel (`text-body`, `text-body-secondary`) ou a variável do tema.
- **R4 — Fundo forte só em etiqueta, botão e barra.** Cabeçalho de cartão ou de janela usa fundo suave. O texto fica na
  cor do mesmo estado (o contraste vem garantido da paleta).
- **R5 — Uma cor de ação.** Verde, âmbar e vermelho ficam só para estado.
  - No tema escuro, o âmbar leva texto escuro, porque branco no âmbar fica abaixo de 4,5:1.
- **R6 — Grade dentro da caixa.** A grade `row` não fica no próprio `modal-body`/`card-body` (isso estoura a borda). Já
  coberta pelo Agente UX.
- **R7 — Sem rolagem lateral.** Nada pode gerar rolagem lateral a 1366 px nem a 375 px. Já coberta.
- **R8 — Foco visível.** O anel de foco tem 3 px na cor de ação, com 3:1 contra o fundo, em **todo** controle que recebe
  Tab: menu, "Fechar", caixas de seleção, links e abas, não só botões. A medida está na R13.
- **R9 — Alvo de toque.** Abaixo de 24 px é **falha** (mínimo da WCAG 2.2, critério 2.5.8). Entre 24 e 40 px é
  **alerta**.
  - Botões comuns e campos têm 40 px; botões pequenos, 32 px; o "Fechar" da janela, 40 px.
  - Uma caixa de seleção dentro de um `<label>` conta pelo tamanho do label inteiro.
- **R10 — Texto e rótulo.** Todo campo tem rótulo, e todo botão só de ícone tem nome. Já coberta.
- **R11 — Hierarquia.** Um título por tela. Seções com rótulo curto. Ações principais à direita, no rodapé da janela.
- **R12 — Medir antes e depois.** Toda proposta traz a contagem de textos abaixo do mínimo, por tema, no visual atual e no
  proposto (`python prototipo_ux/comparar_contraste.py`).

### Regras novas (R13–R23), da validação das skills de mercado

Vieram da validação com ux-ui-audit, ui-review e accessibility-review (`prototipo_ux/validacao_skills/RESUMO.md`). Cada
uma diz o que medir e onde. O protótipo já cumpre todas as que valem para a janela Agendar banca. No Agente UX, por
enquanto, elas são só régua: ainda não estão medidas automaticamente.

- **R13 — Foco medido de verdade.**
  - **O que medir:** depois de um Tab real, o anel de foco tem ≥ 3:1 contra o fundo.
  - **Como somar:** a transparência do `box-shadow` entra na conta, não só o `outline`.
  - **No agente:** no navegador, até 30 Tabs por página, nos 4 temas.
- **R14 — Escala de letras.**
  - **O que medir:** nenhum texto visível abaixo de **12 px**, e no máximo 7 tamanhos de letra por tela.
  - **Como:** os tamanhos viram tokens, como as cores.
- **R15 — Teclado na janela.**
  - **O que testar:** abrir a janela pelo botão e conferir que:
    - o Tab nunca sai dela;
    - o Esc fecha;
    - o foco volta ao botão que abriu.
  - **E também:** depois de marcar, remover ou filtrar algo numa lista da janela, o foco continua dentro dela (o elemento
    com foco nunca é o `BODY`).
- **R16 — Escolha não é só cor.**
  - **O que exigir:** botões que funcionam como opções (10/15/20 min, 12/24/48 h) têm `aria-pressed` (ou são `radio`).
  - O nome do botão leva a unidade ("15 minutos").
- **R17 — Estado vazio com saída.**
  - **O que exigir:** toda busca ou lista filtrada sem resultado diz o que aconteceu e oferece o próximo passo
    ("Nenhum avaliador encontrado para…" + "Cadastrar avaliador").
- **R18 — Estrutura da página.**
  - **O que exigir:**
    - um `<main>`;
    - um `<h1>` por tela;
    - um link "Pular para o conteúdo" no `base.html` (hoje são 51 itens de menu antes do conteúdo).
- **R19 — Zoom de 400%.**
  - Além de 375 px, medir a rolagem lateral também em **320 px** (WCAG 1.4.10).
- **R20 — A R3 vira varredura.**
  - **O que contar:** em cada tela, `text-dark`, `text-white`, `bg-white`, `bg-light`, `bg-dark` e
    `style="color/background:#…"`, como alerta (hoje são 458 + 24).
  - **Exceções conscientes:** marcar com `{# ux: ok - motivo #}`.
  - **Na mesma varredura:** texto entre aspas dentro de `{{ }}` (como `or 'Externa'`) também precisa de `tt()`.
- **R21 — Um botão principal por área.**
  - **O que exigir:** no máximo um botão cheio (`btn-primary`) por cartão ou janela.
  - Títulos de página na cor do texto, nunca na cor de ação (para não parecerem links).
- **R22 — Ícones de um sistema só.**
  - **O que proibir:** emoji como ícone em botões, links e títulos (🚀 🧭 🔍 🧠 ⏳ ❌); usar Bootstrap Icons.
- **R23 — Plural certo.**
  - **O que proibir:** "(s)" no texto ("2 alerta(s)").
  - **Como fazer:** a frase muda com o número ("nenhum escolhido", "1 escolhido", "3 escolhidos").

### Skills de mercado no dia a dia

- **ux-ui-audit:** foco, alvo de toque e escala de letras.
- **ui-design-review (ui-review), sem o UXKIN:** problemas de uso.
- **design › accessibility-review:** roteiro de teclado e zoom antes de levar uma tela para produção.

Nenhuma substitui o Agente UX. O contraste delas não abre janelas nem soma a transparência dos elementos de fora, e o
nosso medidor está certo onde os números diferem.

## 3. O que o Agente UX passa a fazer

- **Varredura do código (já fazia):**
  - tradução;
  - `alt`;
  - rótulos;
  - nomes dos papéis;
  - grade `row` estourada.
- **Medida no navegador, em cada perfil:**
  - layout estourado e rolagem lateral (já fazia);
  - **novo:** contraste do texto nos 4 temas, com as janelas abertas.
    - Um alerta por tema, com as piores ocorrências: página, texto, razão, cor da letra e cor do fundo.
