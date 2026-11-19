# design:accessibility-review — saída da skill

## Como a skill funciona

A skill **não traz ferramenta nenhuma**: é um roteiro (lista de critérios WCAG 2.1 AA, problemas comuns e um modelo de
relatório).

Para seguir o roteiro fiz três coisas:

- usei as medidas do ux-ui-audit (contraste, foco, alvos);
- rodei no navegador (Playwright) os testes que o roteiro pede e que ninguém mais faz aqui:
  - teclado na janela;
  - tecla Esc;
  - foco preso na janela;
  - zoom de 200% e 400% (reflow);
  - marcos da página (landmarks);
  - mensagens de erro;
  - o que o leitor de tela ouve;
- li o código da janela redesenhada.

Os dados brutos estão em `sondas/a11y_teclado_reflow.json`.

**Erro da própria skill.** Ela lista "2.5.5 alvo ≥ 44×44" como AA. Na WCAG 2.1, a 2.5.5 é **AAA**. O critério AA de
tamanho de alvo só existe na WCAG 2.2: é a 2.5.8, de 24×24. Segui o certo.

---

## Accessibility Audit: Agendar banca + 5 telas (protótipo v2 × visual atual)

**Padrão:** WCAG 2.1 AA (+ 2.2 onde indicado) · **Data:** 19/11/2026

### Resumo

**Problemas no protótipo:** 9 · **Críticos:** 1 · **Maiores:** 4 · **Menores:** 4

Destes, 4 já existiam no visual atual. Destes 9, **o protótipo criou 3**: os itens 1, 4 e 6 abaixo.

### Perceptível

| # | Problema | Critério | Sev. | Versão | Recomendação |
|---|---|---|---|---|---|
| 1 | Seções da janela ("Quando e onde", "Tempo da apresentação", "Prazos de entrega", "Avaliadores") são `<span class="proto-rotulo">`: visualmente são títulos, mas o leitor de tela não os vê como grupo | 1.3.1 | 🟢 Menor | protótipo | `<fieldset><legend>` por seção (ou `role="group" aria-labelledby`) |
| 2 | Nenhuma tela tem `<main>` nem `<h1>`: o título da página é h2/h3; leitor de tela não pula direto para o conteúdo | 1.3.1 | 🟡 Maior | as duas | `<main id="conteudo">` em `base.html` e o título da página como `<h1>` |
| 3 | Contraste do texto | 1.4.3 | 🔴 no atual / ✅ no protótipo | atual | já resolvido no protótipo (0 falhas; ver ux-ui-audit.md) |
| 4 | Anel de foco do menu do topo e do "Fechar" = 1,31–1,41:1 | 1.4.11 | 🟡 Maior | as duas | ver ux-ui-audit.md, achado 01 |
| 5 | Reflow a 320 px (zoom 400%): `/dashboard` com rolagem lateral (345 px no protótipo; **608 px no atual**); `/admin/agentes-seguranca` 338 px ("fora desta execução") | 1.4.10 | 🟡 Maior | as duas | O agente mede 375 px; medir também 320 px (é o número da WCAG) |

### Operável

| # | Problema | Critério | Sev. | Versão | Recomendação |
|---|---|---|---|---|---|
| 6 | **Na lista de avaliadores, marcar uma pessoa com a barra de espaço (ou remover uma etiqueta com Enter) joga o foco para fora da janela (`BODY`).** A lista é redesenhada inteira (`desenhar()` apaga e recria os itens). Depois disso **Esc não fecha mais a janela** e o leitor de tela fica "perdido" | 2.4.3 / 2.1.1 | 🔴 Crítico | **protótipo** | Em `desenhar()`, guardar o `value` do item com foco e devolver o foco ao item recriado (ou só alternar `checked` sem recriar a lista) |
| 7 | Em 60 tabs seguidos, o foco sai da janela uma única vez: cai no `BODY` ao dar a volta (no 52º tab no protótipo e no 35º no atual) e logo volta para dentro | 2.4.3 | 🟢 Menor | as duas | comportamento do Bootstrap; aceitável |
| 8 | Não há link "Pular para o conteúdo"; o menu do topo tem 51 itens antes do conteúdo | 2.4.1 | 🟡 Maior | as duas | link `visually-hidden-focusable` para `#conteudo` em `base.html` |
| 9 | Botões "🔍 Expandir" com 20 px de altura em `/acompanhamento` | 2.5.8 (2.2) | 🟢 Menor | as duas | `btn-sm` com `min-height: 32px` |

### Compreensível

| # | Problema | Critério | Sev. | Versão | Recomendação |
|---|---|---|---|---|---|
| 10 | Campos obrigatórios (TCC, Data e hora) usam a validação do navegador | 3.3.1 / 3.3.2 | ✅ | as duas | Passa: o navegador mostra a mensagem no idioma dele. Não há aviso "obrigatório" no rótulo, mas a mensagem nativa identifica o campo |
| 11 | O botão "20" (minutos) não diz "minutos": o leitor ouve "20, botão"; a unidade "min" está num `<span>` solto | 3.3.2 | 🟢 Menor | protótipo | `aria-label="20 minutos"`, ou o grupo com `aria-label="Minutos de apresentação"` |

### Robusto

| # | Problema | Critério | Sev. | Versão | Recomendação |
|---|---|---|---|---|---|
| 12 | Os botões de escolha rápida (10/15/20 min, 5/10/15, 12/24/48 h) mostram o escolhido só pela cor (classe `ativo`); sem `aria-pressed`, o leitor de tela não sabe qual está marcado | 4.1.2 | 🟡 Maior | **protótipo** | `b.setAttribute('aria-pressed', b.value === campo.value)` em `marcar()`; o grupo com `role="group"` + `aria-label` |
| 13 | A janela Agendar banca do visual atual não tem nome acessível (`aria-labelledby` ausente) | 4.1.2 | 🟡 Maior | **atual** | ✅ o protótipo corrigiu: `aria-labelledby="tituloBanca0"` → "Agendar banca, Escolha o TCC, a data e quem avalia." |

### Contraste das cores (do ux-ui-audit, conferido)

| Elemento | Letra | Fundo | Razão | Mínimo | Passa? |
|---|---|---|---|---|---|
| Texto da janela (protótipo, claro) | #152030 | #ffffff | 16,39:1 | 4,5:1 | ✅ |
| Texto secundário (protótipo, claro) | #4f5b6b | #ffffff | 6,91:1 | 4,5:1 | ✅ |
| Botão principal (protótipo, escuro) | texto escuro | âmbar #f59e0b | ≥ 4,5:1 (paletas.py) | 4,5:1 | ✅ |
| Foco do menu (protótipo, claro) | rgba(13,110,253,.25) | #ffffff | 1,41:1 | 3:1 | ❌ |
| Foco dos botões `.btn` (protótipo, claro) | #1f5fd6 | #ffffff | 5,73:1 | 3:1 | ✅ |
| "Administração" no menu (atual, claro) | #0d6efd | #dae8f9 | 3,61:1 | 4,5:1 | ❌ |

### Navegação pelo teclado (janela Agendar banca, protótipo)

| Elemento | Ordem do Tab | Enter/Espaço | Esc | Setas |
|---|---|---|---|---|
| Abrir pelo botão "Agendar banca" | foco vai para a janela ✅ | — | fecha e devolve o foco ao botão ✅ | — |
| TCC, Data, Local, Link | na ordem visual ✅ | — | fecha ✅ | — |
| Botões 10/15/20 | um por um ✅ | preenche o campo ✅ | fecha ✅ | não movem (aceitável) |
| Caixa de avaliador | ✅ | **marca, mas o foco vai para o BODY** ❌ | **não fecha mais** ❌ | — |
| Etiqueta (×) do avaliador | ✅ | **remove, e o foco vai para o BODY** ❌ | **não fecha mais** ❌ | — |
| Cancelar | ✅ | fecha e devolve o foco ao botão ✅ | — | — |

### Leitor de tela (o que é anunciado, pelos atributos)

| Elemento | Anunciado como | Problema |
|---|---|---|
| Janela | "diálogo, Agendar banca, Escolha o TCC, a data e quem avalia." | ✅ (no atual: "diálogo", sem nome) |
| Botão "15" | "15, botão" | sem unidade e sem estado "pressionado" |
| Campo de busca | "Buscar avaliadores, campo de pesquisa" | ✅ |
| Etiqueta do avaliador | "Remover Avaliador OmniTest da Silva, botão" | ✅ |
| Contagem "0 escolhido(s)" | não é anunciada quando muda | a região viva (`aria-live`) está nas etiquetas, não na contagem; OK |

### Correções por prioridade

1. **Foco perdido na lista de avaliadores** (item 6). Afeta quem usa teclado ou leitor de tela, e trava a janela
   (o Esc para de funcionar). Foi criado pelo protótipo e precisa ser corrigido antes de levar o desenho para produção.
2. **Estado dos botões de escolha rápida** (item 12). Hoje quem não enxerga a cor não sabe qual opção está marcada.
3. **Anel de foco do menu e do Fechar** (item 4) e **`<main>` + `<h1>` + link para pular o menu** (itens 2 e 8):
   uma mudança em `base.html` resolve em todas as telas.
4. **Reflow a 320 px** no painel (item 5).
5. Os menores: fieldset, unidade nos botões, botões "Expandir".
