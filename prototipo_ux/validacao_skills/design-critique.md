# design:design-critique — saída da skill

## Como a skill funciona

A skill também é **só um roteiro**: primeira impressão, usabilidade, hierarquia, consistência, acessibilidade, o que
funciona e prioridades. Não mede nada.

- **Como apliquei:** olhando as capturas de 1440 px e 390 px nos temas claro e escuro (`sondas/*.png`), com os números do
  ux-ui-audit como apoio.
- **Conectores:** o Figma e as fontes de feedback não estão conectados, e não seriam usados de qualquer forma (tudo local).
- **Fase do trabalho:** é um protótipo (proposta), então a crítica foca em decisões de desenho, não em acabamento.

---

## Design Critique: protótipo v2 — janela "Agendar banca" e telas com o tema novo

### Impressão geral

- **A janela nova é claramente melhor que a atual.** Ela tem seções com nome, um subtítulo que diz o que fazer, o
  rodapé fixo com o resumo do que vai acontecer, e não tem mais a faixa azul no cabeçalho.
- **A maior oportunidade está fora da janela.** O tema pinta os **títulos das páginas na cor de ação** (azul no claro,
  âmbar no escuro), e no painel o único botão cheio da tela pertence a uma função secundária. Por isso a hierarquia das
  telas ainda não diz "o que é clicável" nem "o que é o principal aqui".

### Usabilidade

| Achado | Sev. | Recomendação |
|---|---|---|
| A duração aparece **duas vezes**: botões 10/15/20 **e** um campo com "15 min" ao lado. São dois controles para o mesmo valor, que competem e somam 6 alvos a mais | 🟡 | Manter só os botões, com uma opção "Outro…" que mostra o campo; ou só o campo com − / + |
| No celular (390 px), os três prazos ficam lado a lado e a hora some (só aparece `dd/mm/yyyy`). "Leitura dos avaliadores" quebra em duas linhas e desalinha o terceiro campo | 🔴 | Abaixo de 576 px, um prazo por linha |
| A lista de avaliadores tem rolagem própria **dentro** da janela, que também rola: no celular são duas rolagens uma dentro da outra | 🟡 | Mostrar 3 avaliadores e um "ver todos", ou deixar só a busca mais as etiquetas, e a lista aparecer ao digitar |
| Marcar um avaliador pelo teclado tira o foco da janela (ver accessibility-review, item 6) | 🔴 | Devolver o foco ao item depois de redesenhar |
| Sala de estudo: "1 concluída(s)" e a barra em **37%** contam coisas diferentes (1 de 4 aulas daria 25%; 37% inclui a leitura da aula 2). A pessoa não entende de onde veio o número | 🟢 | Uma frase só: "37% · 1 de 4 aulas concluída · leitura da aula 2 feita" |
| "Em andamento", no alto da aula, é uma pílula cinza que parece botão | 🟢 | Etiqueta com o estilo de estado (`info-soft`), sem cara de botão |

### Hierarquia visual

- **O que chama o olho primeiro:**
  - **Janela:** o título "Agendar banca", e depois o botão azul do rodapé. Está certo.
  - **Painel (`/dashboard`):** a caixa vermelha de alertas, e logo depois o botão azul cheio "Iniciar Contagem" do
    Relógio de Voluntariado. O título da página, "Painel de Indicadores & Gestão de Riscos", fica em **terceiro**,
    abaixo de duas caixas. Para um painel de gestão, a ordem está trocada.
  - **Segurança (escuro):** título em vermelho e botão vermelho "Iniciar auditoria". Ali o vermelho é a cor de ação,
    o que contradiz a R5 (vermelho só para estado).
- **Fluxo de leitura:** a janela lê de cima para baixo, em blocos (Quando e onde → Tempo → Prazos → Avaliadores →
  rodapé). É o melhor ponto do protótipo.
- **Ênfase:**
  - O tema pinta **títulos de página e de cartão na cor de ação**: "Gestão da trilha do TCC" em âmbar, "Painel de
    Indicadores" em azul, os títulos das aulas em âmbar. O título fica parecendo link, e a cor de ação perde a força nos
    botões de verdade.
  - De 61% a 90% do texto está em negrito (ux-ui-audit, achado 08).
- **Menu do topo:** no Administrador, em 1440 px, o menu ocupa **duas linhas**. A segunda (sino, PT, tema, Tour, Sair)
  fica embaixo do menu e não alinhada à direita. No Aluno, que tem menos itens, cabe numa linha, e a altura do topo muda
  de perfil para perfil.

### Consistência

| Elemento | Problema | Recomendação |
|---|---|---|
| Tipografia | 12 tamanhos na tela de bancas (eram 6), alguns de 9,84 e 11,25 px vindos de `em` sobre a base de 15 px | Escala fixa (12 · 13 · 15 · 18 · 24 · 32) e mínimo de 12 px |
| Letra maiúscula | "PROJETOS (TCC)" em maiúsculas entre "Total de Alunos", "Finalizados"…; rótulos de seção da janela também em maiúsculas | Rótulo de cartão sempre no mesmo caso; maiúsculas só nos rótulos de seção |
| Cor dos títulos | Títulos na cor de ação no claro (azul) e no escuro (âmbar); a Segurança usa vermelho | Títulos em `fg`; cor de ação só no que se clica |
| Botão principal | Janela: azul (claro) e âmbar (escuro), certo. Segurança: vermelho. Painel: "Iniciar Contagem" azul cheio numa função secundária | Um botão cheio por tela, no objetivo principal da tela |
| Bordas arredondadas | 7 a 10 raios diferentes por tela (8, 14, 12, 10, 6, 3,75, pílula…) | 3 raios: campo/botão 8, cartão 12, etiqueta pílula |

### Acessibilidade

- **Contraste do texto:** ✅ passa em tudo, nos dois temas (0 falhas, medido).
- **Alvos de toque:** os botões da janela têm 38–39 px, um pouco abaixo da R9 (40 px). O "Fechar" tem 31 px.
  "🔍 Expandir", em `/acompanhamento`, tem 20 px (abaixo dos 24 px da WCAG).
- **Legibilidade:** o corpo de 15 px com Inter está bom. Os textos de 9,84–11,25 px (etiquetas "Sem atividade",
  "Avaliação escrita", "1 concluída(s)") ficam pequenos demais, ainda mais no celular.

### O que funciona bem

- **Janela em seções, com subtítulo e rodapé fixo:**
  - "Os avaliadores recebem o formulário 24 h antes da banca." diz, antes de salvar, o que vai acontecer;
  - no celular o botão principal fica sempre visível (no visual atual é preciso rolar 1.295 px).
- **Busca, etiquetas e caixas de seleção no lugar do "segure Ctrl" para escolher avaliadores.** É bem mais fácil de usar,
  inclusive no celular.
- **Cabeçalho de janela sem faixa colorida.** Era o maior foco de ilegibilidade no tema escuro.
- **O tema escuro parece desenhado, não invertido.** As superfícies têm três tons de cinza, o âmbar leva texto escuro,
  e a tabela da trilha tem cabeçalho discreto e o progresso em etiquetas (0/5 em âmbar, 5/5 em verde).

### Recomendações por prioridade

1. **Prazos empilhados no celular e foco que não escapa da lista de avaliadores.** São os dois pontos em que a janela
   nova fica pior que a atual. Corrigir antes de qualquer decisão de levar para produção.
2. **Títulos em `fg`, cor de ação só no que se clica, um botão cheio por tela.** Isso devolve a hierarquia às telas
   (painel, segurança, sala de estudo) e cumpre a R5 de verdade.
3. **Escala de letras fechada e um só controle por valor na janela.** Isso reduz o ruído visual (12 → 6 tamanhos;
   6 alvos a menos).
