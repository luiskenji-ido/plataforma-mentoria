# ux-ui-audit — saída da skill no protótipo v2 (5070) e no visual atual (5071)

- **Como rodou:** as 4 sondas de página (`probe-core`, `probe-heuristics`, `probe-perception`, `probe-ltr`) e a sonda de
  foco (`probe-focus`, depois de 12 toques reais em Tab) foram executadas pelo Playwright em cada tela.
  - Script: `prototipo_ux/validacao_skills/rodar_sondas.py`.
  - JSON bruto e captura de cada medição: `prototipo_ux/validacao_skills/sondas/`.
  - `probe-rtl` e `probe-parity` não rodaram: a plataforma não tem árabe, e a paridade pt/en/es já é coberta pelo Agente UX.
  - `probe-routes` não rodou: faz GET em todos os links, inclusive `/logout` e `/alterar-tema`.
- **Telas:**
  - `/bancas` com a janela `#modalBanca0` aberta;
  - `/acompanhamento`;
  - `/admin/agentes-seguranca`;
  - `/onboarding/trilha-tcc/gestao`;
  - `/dashboard`;
  - `/meus-cursos/7`, como aluno.
- **Temas e larguras:** temas claro e escuro, em 1440 px; a janela também em 390 px (celular). São 28 medições.
- **Contas:** demo_admin e demo_aluno, na cópia do banco. O tema voltou para `claro` no fim.
- **Data:** 19/11/2026.

## Resumo

| Severidade | Protótipo v2 | Visual atual |
|---|---|---|
| Acessibilidade (WCAG) | 2 | 4 |
| Maior (usabilidade) | 2 | 2 |
| Nota | 4 | 3 |

O protótipo resolve o principal: o **contraste do texto deu 0 falhas** em todas as telas e nos dois temas, nas duas
ferramentas.

O que sobra no protótipo:

- o **anel de foco** do menu do topo e do botão Fechar;
- **letras pequenas demais**, abaixo de 12 px;
- datas cortadas na janela, no celular.

## Achados

### 01 · [Acessibilidade 1.4.11 / 2.4.7] · protótipo, todas as telas · menu do topo e botão "Fechar" das janelas

O anel de foco é o padrão do Bootstrap, quase invisível. Quem navega pelo teclado não vê onde está.

```
a.nav-link "Painel Geral" / "Aprendizagem" / … (Tab real, medido após 450 ms):
  box-shadow: rgba(13,110,253,0.25) 0 0 0 4px  sobre rgb(255,255,255) → 1,41:1 (claro)
                                               sobre rgb(26,27,31)    → 1,31:1 (escuro)
button.btn-close (janela Agendar banca): mesmo anel → 1,41:1 (claro) / 1,30:1 (escuro)
mínimo SC 1.4.11: 3:1 — e a nossa regra R8 pede 3 px na cor de ação com 3:1
```

- **Correção:** em `tema.css`, a regra `.btn:focus-visible` só pega `.btn`. Estender para
  `:is(.nav-link, .btn-close, .dropdown-item, .form-check-input, button, a):focus-visible`, com o mesmo
  `outline: 3px solid var(--p-accent)`.
- **Visual atual:** está pior. Em todos os controles medidos o anel fica entre 1,00:1 e 2,06:1, e no tema escuro até o
  link da marca cai para 1,07:1.

### 02 · [Acessibilidade 1.4.11, R8] · protótipo · campos da janela Agendar banca

O halo de foco dos campos tem só 35% de cor.

```
.form-control:focus  box-shadow: color(srgb … / 0.35) 0 0 0 3px → 1,70:1 (claro) / 2,08:1 (escuro)
                     border-color: accent → 5,73:1 (claro) / 8,01:1 (escuro)
```

- **WCAG AA:** passa, porque a borda muda para a cor de ação com mais de 3:1.
- **Nossa R8:** **não** cumpre, porque ela pede um anel de 3 px com 3:1.
- **Decisão a tomar:** aceitar "a borda na cor de ação" como foco de campo, ou trocar o halo por `outline` 2 px.

### 03 · [Maior] · protótipo · janela Agendar banca em 390 px — datas cortadas

- No celular, os três prazos ficam lado a lado (Trabalho escrito, Slides, Leitura dos avaliadores).
- Em cada um aparece só `dd/mm/yyyy`: a hora some, e a pessoa não vê a hora que escolheu.
- O rótulo "Leitura dos avaliadores" quebra em duas linhas e empurra o terceiro campo para baixo, que fica desalinhado.

```
captura sondas/prototipo_escuro_390_bancas_modal.png — campos 3 por linha em 374 px de janela
```

- **Correção:** abaixo de 576 px, empilhar os prazos com `col-12 col-sm-4`.

### 04 · [Maior] · protótipo · escala de letras — o protótipo criou tamanhos pequenos e soltos

O tema multiplica os tamanhos em `em` pela base de 15 px. O resultado são 12 tamanhos diferentes (eram 6), três deles
abaixo de 12 px.

```
/bancas + janela:  9,84 px "Avaliação escrita", "Apresentação oral e visual" (era 10,5 px)
                   11,25 px "Realizada", "Resultado publicado", "Entregue no prazo"
                   11,52 px "QUANDO E ONDE", "TEMPO DA APRESENTAÇÃO", "PRAZOS DE ENTREGA"
/dashboard:        9,84 px "Sem atividade" (era 10,5 px)
tamanhos distintos: protótipo 12 · atual 6 (probe-heuristics designSystem.distinctFontSizes)
```

- **Correção:** definir uma escala fixa, por exemplo 12 · 13 · 15 · 18 · 24 · 32, e um mínimo de 12 px para etiquetas.

### 05 · [Acessibilidade 2.5.8 / R9] · as duas versões · `/acompanhamento` — botões "🔍 Expandir"

Os botões "🔍 Expandir / Tela Cheia" e "🔍 Expandir Parecer" têm **20 px de altura**, abaixo do mínimo de 24 px da WCAG
2.2 (e dos 40 px da nossa R9). São 14 botões na tela, nas duas versões.

```
button.btn  "🔍 Expandir / Tela Cheia"  160 x 20
button.btn  "🔍 Expandir Parecer"       137 x 20
```

### 06 · [Nota / R9] · protótipo · janela Agendar banca — alvos entre 31 e 39 px

- Botões "Cancelar" e "Agendar banca": 38 px. Chips de minutos e de horas: 39 px. "Fechar": 31×31.
- Passa na WCAG AA (24 px), mas fica abaixo dos 40 px da nossa R9.

### 07 · [Nota] · as duas versões · textos com "(s)"

O texto contorna o plural em vez de resolvê-lo:

- "AVALIADORES · 0 ESCOLHIDO(S)", texto novo do protótipo;
- "1 concluída(s)" e "aula(s)", na sala de estudo;
- "alerta(s)", no painel.

**Correção:** escolher a frase pelo número ("Nenhum escolhido", "1 escolhido", "2 escolhidos").

### 08 · [Nota] · as duas versões · peso da letra não marca mais hierarquia

De 61% a 90% dos textos da primeira tela estão em negrito ou seminegrito. No painel, são 90% no protótipo e 79% no atual.
Quando quase tudo é negrito, nada se destaca.

### 09 · [Nota 2.4.4] · as duas versões · `/admin/agentes-seguranca` — links só com data

- "16/11 19:11" aparece 4 vezes, cada uma levando a um PDF diferente. Na mesma tela, "Sala da banca" e
  "Ficha dos avaliadores" aparecem 3 vezes cada, com destinos diferentes.
- O contexto (a pasta aberta) explica, então não é falha de nível A.
- Para quem usa leitor de tela, um `aria-label` como "Relatório de 16/11 19:11 — Agente Configuração" ajuda.

### 10 · [Acessibilidade 1.4.3] · visual atual · contraste do texto

```
claro:  /dashboard 7 · /bancas+janela 8 · /acompanhamento 15 · /trilha 6 · /segurança 9 · sala 7
escuro: /dashboard 9 · /bancas+janela 4 · /acompanhamento 1 · /trilha 1 · /segurança 25(teto da sonda) · sala 6
exemplos: "Administração" #0d6efd sobre #dae8f9 = 3,61:1 · "Avaliadores da banca" 4,11:1 · "Sair / Logout" 4,13:1
protótipo v2: 0 falhas em todas (claro e escuro, 1440 e 390)
```

## Falsos positivos da sonda (conferidos e descartados)

- **"Alvo pequeno" nas caixas de seleção de avaliadores (15×15).**
  - Cada caixa está dentro de um `<label>` de 756×61 px (330×62 no celular), e a linha inteira é clicável.
  - Não é falha.
- **"Datas ambíguas" (08/11/2026).** Para pt-BR, o formato dd/mm/aaaa é o certo. A sonda foi feita para inglês.
- **"Faixa do topo só com marca".** O topo tem o menu e as ações, como em qualquer tela de sistema.
- **196 "alvos pequenos" em `/admin/agentes-seguranca`.**
  - São links de data de 16 px de altura, em listas com 24 px entre uma linha e outra.
  - Pela exceção de espaçamento da 2.5.8, passa por pouco.

## Onde a sonda erra contra o nosso medidor (conferido)

- **Opacidade dos pais.** O `probe-core.js` não multiplica a opacidade dos elementos-pai.
  - Na tela `/admin/agentes-seguranca` (visual atual, escuro), "Agente Configuração e Segredos" tem cor
    `rgb(248,250,252)`, mas está dentro de `.seg-agente.aguardando` com `opacity: 0.3`.
  - Na tela, a razão real é **2,91:1**, e o nosso `contraste.py` acusa a falha corretamente.
  - A sonda calcula como se a letra estivesse a 100% e **deixa passar**.
  - Mesmo caso: "fora desta execução", dentro de `.linha-progresso` com `opacity: 0.5`, onde o nosso medidor dá 3,03:1.
- **Janelas fechadas.** A sonda não abre janelas.
  - No visual atual, escuro, em `/acompanhamento`: a sonda achou 1 falha.
  - O nosso medidor achou 12, quase todas dentro das janelas "Editar" e "Expandir", com razões de 1,00 a 1,48:1, as piores
    da tela.
- **Teto.** A sonda mede só os primeiros 400 textos e lista no máximo 25 falhas: "25" quer dizer "25 ou mais".
- **Onde as duas medem o mesmo texto, a razão bate na segunda casa decimal:**
  3,61 · 4,11 · 4,13 · 3,66 · 3,68 · 3,19.

## O que funciona (medido)

- **Contraste do texto no protótipo: 0 falhas** em 2.072 textos medidos pela sonda (claro e escuro, 1440 e 390).
  Confirma o `contraste.json` (prototipo_v2: 0 nos 4 temas).
- **Anel de foco dos botões `.btn` no protótipo** (PT, tema, Tour, Sair, Voltar, Anterior): 3 px, de 5,29 a 5,73:1 no
  claro e de 8,01 a 8,73:1 no escuro.
- **Celular, 390 px.** No protótipo, a janela tem 828 px e o rodapé com "Agendar banca" fica fixo e visível (topo 726, fim
  835, de 844). No visual atual, a janela tem 1.295 px e o botão fica abaixo da dobra: é preciso rolar até o fim.
- **Nenhuma rolagem lateral** e nenhum controle sem nome (`naming.unnamed` = 0) em nenhuma das 28 medições.
- **Cores de texto:** 7 cores no protótipo, contra 11 no atual (painel). O "cada cor tem um papel" aparece na medida.

## Por onde começar (impacto ÷ esforço)

1. **01**: uma linha de CSS corrige o foco em todas as telas.
2. **03**: um `col-12 col-sm-4` corrige os prazos no celular.
3. **04**: a escala de letras e o mínimo de 12 px.
4. **05**: o tamanho dos botões "Expandir".
5. **07**: plural sem "(s)".
6. **02**: decidir o foco dos campos.
