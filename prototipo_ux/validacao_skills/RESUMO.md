# Validação das skills de UX/UI instaladas — resumo

19/11/2026. Testadas no protótipo v2 (porta 5070) e no visual atual (porta 5071), com a cópia do banco.

## Veredito

| Skill | Veredito | Por quê |
|---|---|---|
| **ux-ui-audit** | ✅ **Manter para o dia a dia** | Mede o que o nosso agente não mede: foco, tamanho de alvo, escala de letras. Mas o contraste dela é pior que o nosso |
| **ui-design-review: ui-review** | ✅ **Manter para o dia a dia** (sem UXKIN) | Foi a que mais achou problemas "de uso": busca sem resposta, botões principais demais, emoji como ícone, "Plataforma: Plataforma" |
| **design: accessibility-review** | 🟡 **Manter só como roteiro**, antes de levar uma tela para produção | Não tem ferramenta, mas o roteiro dela (teclado, tecla Esc, zoom) levou ao achado mais grave. Tem um erro: chama de AA um critério que é AAA |
| **design: design-critique** | ⚪ **Redundante** | Faz o mesmo que a ui-review, de forma mais genérica |
| **design: design-system** | ⚪ **Útil uma vez; depois, redundante** | Mostrou que a regra R3 não é conferida por ninguém e que faltam tamanhos de letra fixos. Uma vez transformados em regra, não precisa rodar de novo |

**Em uma frase:** nenhuma skill substitui o nosso Agente UX, mas duas completam o que ele não vê. Ele continua melhor em
três pontos:

- contraste nos 4 temas e com as janelas abertas;
- tradução;
- rótulos.

As skills enxergam o que ele não enxerga:

- foco;
- teclado;
- estados vazios;
- tamanho de letra e de alvo;
- excesso de botões principais.

## Skills encontradas e faltando

- **Encontradas e usadas:** `ux-ui-audit:ux-ui-audit`, `design:accessibility-review`, `design:design-critique`,
  `design:design-system`, `ui-design-review:ui-review`. **Nenhuma faltou.**
- **Também instaladas, mas não usadas:**
  - `ui-design-review:ui-polish`: altera arquivos, e a tarefa era só de leitura;
  - `ui-design-review:ui-compare`: só faz sentido com o UXKIN.
- **O conector UXKIN aparece "pedindo login"** e não foi usado, como combinado. Todo o resto rodou na máquina, sem
  serviço externo.

## Como foi feito

- **ux-ui-audit:** as sondas da skill (scripts de medição) rodaram no navegador:
  - 6 telas;
  - temas claro e escuro;
  - 1440 px, e 390 px na janela Agendar banca;
  - 28 medições, mais 12 toques de Tab em cada uma.
- **Outras skills:** são roteiros, sem ferramenta. Segui o roteiro de cada uma com:
  - testes no navegador: teclado, Esc, zoom de 200% e 400%, busca sem resultado, 768 px;
  - leitura das capturas e do código.
- **Conferência:** cada número suspeito foi conferido de novo, à mão.
- **Saídas:**
  - relatórios, um por skill: `ux-ui-audit.md`, `accessibility-review.md`, `design-critique.md`, `design-system.md`,
    `ui-review.md`;
  - medições brutas e capturas: `sondas/`;
  - script que roda as sondas: `rodar_sondas.py`.
- **Projeto:** nenhum arquivo do projeto foi alterado fora desta pasta. O tema das contas demo voltou para claro.

## 1. O que as skills acharam e nós não

"Novo" quer dizer que nem o nosso medidor de contraste nem o Agente UX pegam isso hoje.

| Skill | O que achou (tela · elemento · prova) | Novo ou já coberto? |
|---|---|---|
| ux-ui-audit | **Foco quase invisível** no menu do topo e no "Fechar" das janelas: o anel do Bootstrap tem **1,41:1** (claro) e **1,31:1** (escuro). O mínimo é 3:1. Está no protótipo e no atual | **Novo.** A R8 existe, mas ninguém mede |
| ux-ui-audit | **Letras pequenas demais.** O protótipo criou textos de **9,84 px** ("Avaliação escrita", "Sem atividade") e passou de 6 para **12 tamanhos** de letra na tela de bancas | **Novo** |
| ux-ui-audit | **Botões "🔍 Expandir"** em /acompanhamento com **20 px** de altura (o mínimo da WCAG é 24). São 14 botões, nas duas versões | **Novo.** A R9 existe, mas ninguém mede |
| ux-ui-audit | Botões da janela nova com 38–39 px; "Fechar" com 31 px. Abaixo dos 40 px da nossa R9 | **Novo** (R9 sem medida) |
| ux-ui-audit / ui-review | Textos com "(s)": "0 escolhido(s)", "2 alerta(s)", "1 concluída(s)" | **Novo** |
| ux-ui-audit | 61% a 90% do texto em negrito: o negrito não destaca mais nada | **Novo** (julgamento) |
| accessibility-review | **Na janela nova, marcar um avaliador pelo teclado joga o foco para fora da janela, e o Esc para de funcionar.** Teste: Espaço na caixa → foco no `BODY` → Esc não fecha | **Novo — o mais grave.** Foi criado pelo protótipo |
| accessibility-review | Os botões 10/15/20 min e 12/24/48 h mostram o escolhido **só pela cor**, sem `aria-pressed`. O leitor de tela não sabe qual está marcado | **Novo.** Criado pelo protótipo |
| accessibility-review | Nenhuma tela tem `<main>`, `<h1>` nem link "pular para o conteúdo". São 51 itens de menu antes do conteúdo | **Novo** |
| accessibility-review | Zoom de 400% (320 px): o painel tem rolagem lateral (**345 px** no protótipo, **608 px** no atual) | **Em parte.** O agente mede 375 px, não 320 |
| accessibility-review | No visual atual, a janela Agendar banca não tem nome para o leitor de tela. O protótipo **já corrigiu** | Novo (e já resolvido no protótipo) |
| design-critique / ui-review | **Prazos cortados no celular:** na janela, em 390 px, os três prazos lado a lado mostram só `dd/mm/yyyy` e a hora some | **Novo.** O agente vê "estouro de caixa", não "texto cortado dentro do campo" |
| design-critique / ui-review | **Títulos de página na cor de ação** (azul no claro, âmbar no escuro): parecem links. Na Segurança, a ação é vermelha (contra a R5). No painel, o único botão cheio é de uma função secundária | **Novo** (R5 sem medida) |
| ui-review | **Busca de avaliador sem resultado fica em branco**: 0 itens e nenhuma mensagem | **Novo** |
| ui-review | **Acompanhamento:** 2 botões azuis cheios por aluno, mais 1 no topo (com 10 alunos, 21 botões "principais") | **Novo** |
| ui-review | **"Plataforma: Plataforma"** no Acompanhamento; texto reserva fixo `'Externa'`/`'Externo'` fora da tradução (acompanhamento.html:301 e 918) | **Novo.** A varredura de tradução não olha textos dentro de `{{ }}` |
| ui-review | **Emoji usado como ícone** em botões: 🚀 🧭 🔍 🧠 ⏳ ❌. Muda de cara em cada aparelho e não segue o tema | **Novo** |
| design-system | **A regra R3 (sem cor fixa) não é conferida:** há **458** `text-dark`/`bg-white`/`bg-light`/… e 24 `style="color:#…"` nas telas | **Novo.** A regra existe só no papel |
| design-system | Não há tamanhos de letra nem raios fixos no tema: são 10 tamanhos e 6 raios escritos à mão no `tema.css` | **Novo** |
| todas | Contraste do texto no protótipo: **0 falhas** | **Já coberto.** Confirma o nosso número |

## 2. Alguma skill contradisse os nossos números?

**No contraste do texto, não.** Nenhuma skill acusou falha no protótipo, e onde a sonda e o nosso medidor mediram o
mesmo texto, a razão bateu na segunda casa decimal: 3,61 · 4,11 · 4,13 · 3,66 · 3,68 · 3,19.

As contagens do visual atual diferem (por exemplo, /acompanhamento escuro: 1 na sonda, 12 no nosso). Conferi, e **o
nosso medidor está certo**, por três motivos:

1. **A sonda ignora a transparência dos elementos de fora.**
   - Em /admin/agentes-seguranca (escuro), "Agente Configuração e Segredos" é branco, mas está dentro de um quadro com
     30% de opacidade.
   - Na tela, isso dá **2,91:1**, e o nosso medidor reprova. A sonda calcula como se fosse branco puro e **deixa
     passar**.
2. **A sonda não abre janelas.** As piores falhas do visual atual (1,00 a 1,48:1) estão dentro das janelas "Editar" e
   "Expandir" do Acompanhamento. O nosso medidor abre as janelas; a sonda nem as vê.
3. **A sonda tem limite.** Ela mede só os primeiros 400 textos e lista no máximo 25 falhas.

**Onde as skills contradizem o que dissemos do protótipo:**

- **R8 (foco).** O documento diz que o anel de foco tem 3 px na cor de ação. Isso vale para os botões (5,73:1 e 8,01:1),
  mas não para o menu, o "Fechar" e as caixas de seleção, que ficaram com o anel do Bootstrap (1,3–1,4:1). Nesse ponto,
  **a skill está certa**.
- **R9 (40 px).** Os botões da janela nova têm 38–39 px. **A skill está certa**, por pouco.

**Falsos alarmes das skills (descartados):**

- **Caixas de seleção "pequenas demais" (15×15):** a linha inteira é clicável (756×61 px).
- **"Datas ambíguas":** dd/mm/aaaa é o certo para pt-BR.
- **"Alvos pequenos" na Segurança:** são links de data em listas espaçadas, e passam pela exceção da WCAG.

## 3. Regras novas propostas para a `SKILL_UX_UI.md` e o Agente UX

São só propostas: **nada foi implementado no agente**. Cada regra diz o que medir e onde.

- **R13 — Foco medido de verdade.**
  - **O que medir:** depois de um Tab real, o anel de foco tem ≥ 3:1 contra o fundo.
  - **Como medir:** somar a transparência do `box-shadow`, e não só o `outline`.
  - **Onde:** em todos os controles, incluindo menu, "Fechar", caixas de seleção e botões feitos à mão.
  - **No agente:** no navegador (base.py), 30 Tabs por página, nos 4 temas.
  - Mede a R8, que hoje não tem medida.
- **R14 — Escala de letras.**
  - **O que medir:** nenhum texto visível abaixo de 12 px, e no máximo 7 tamanhos por tela.
  - **Como:** os tamanhos viram tokens no `paletas.py` (`--p-fs-…`), como as cores.
  - **No agente:** no navegador, junto com o contraste.
- **R15 — Teclado na janela.**
  - **O que testar:** abrir a janela pelo botão e conferir que:
    - Tab nunca sai dela;
    - Esc fecha;
    - o foco volta ao botão.
  - **E também:** depois de marcar, remover ou filtrar algo numa lista da janela, o foco continua dentro dela
    (o elemento com foco nunca é o `BODY`).
- **R16 — Escolha não é só cor.**
  - **O que exigir:** botões que funcionam como opções (10/15/20, 12/24/48 h) têm `aria-pressed` ou são `radio`.
  - Botão com número tem a unidade no nome ("20 minutos").
- **R17 — Estado vazio com saída.**
  - **O que exigir:** toda busca ou lista filtrada mostra uma mensagem quando não há resultado, e a próxima ação
    ("Cadastrar avaliador").
  - **Como testar:** no navegador, digitando um termo impossível em cada campo de busca.
- **R18 — Estrutura da página.**
  - **O que exigir:**
    - um `<main>`;
    - um `<h1>` por tela;
    - um link "Pular para o conteúdo" no `base.html`.
  - **Como verificar:** varredura do código.
- **R19 — Zoom de 400%.**
  - Além dos 375 px de hoje, medir a rolagem lateral também em **320 px**, que é o número da WCAG (1.4.10).
- **R20 — A R3 vira varredura.**
  - **O que contar:** em cada tela, `text-dark`, `text-white`, `bg-white`, `bg-light`, `bg-dark` e `style="color/background:#…"`,
    como alerta.
  - **Exceções conscientes:** marcar com `{# ux: ok - motivo #}`, por exemplo o PDF do relatório ESG.
  - **Na mesma varredura:** textos entre aspas dentro de `{{ }}` (como `or 'Externa'`) também precisam de `tt()`.
- **R21 — Um botão principal por área.**
  - **O que exigir:**
    - no máximo um botão cheio (`btn-primary`) por cartão ou janela;
    - títulos em `fg`, nunca na cor de ação.
  - **Como medir:** no navegador, comparando a cor do título com `--p-accent`.
- **R22 — Ícones de um sistema só.**
  - **O que proibir:** emoji como ícone em botões, links e títulos; usar Bootstrap Icons.
  - **Como verificar:** varredura do código.
- **R23 — Plural certo.**
  - **O que proibir:** "(s)" no texto.
  - **Como fazer:** a frase muda conforme o número ("Nenhum escolhido", "1 escolhido", "2 escolhidos").
  - **Como verificar:** varredura do código e das traduções.
- **Ajuste na R9.**
  - **Falha:** abaixo de 24 px, que é o mínimo da WCAG 2.2.
  - **Alerta:** entre 24 e 40 px.
  - **Exceção:** uma caixa de seleção dentro de um `<label>` conta pelo tamanho do label.

## O que corrigir no protótipo antes de mostrar como proposta final

Em ordem de importância:

1. Foco que escapa da janela ao marcar um avaliador (R15).
2. Prazos empilhados no celular.
3. Anel de foco em `.nav-link` e `.btn-close` (uma regra no `tema.css`).
4. `aria-pressed` nos botões de escolha rápida.
5. Mensagem de "nenhum avaliador encontrado".
6. Mínimo de 12 px nos textos.

Todos são ajustes pequenos dentro de `prototipo_ux/`. Nenhum mexe em produção.
