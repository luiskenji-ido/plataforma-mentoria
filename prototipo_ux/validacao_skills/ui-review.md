# ui-design-review:ui-review — saída da skill

## Como a skill funciona

É um roteiro de revisão por área: propósito, hierarquia, espaço, consistência, textos, "cara de IA", acessibilidade,
toque, estados e convenções.

A skill pede para **ver a tela de verdade**, por isso as telas foram abertas no navegador:

- em **1440, 768 e 390 px**;
- nos temas claro e escuro;
- só com o teclado;
- forçando um estado vazio (busca sem resultado).

O conector UXKIN e qualquer serviço externo **não foram usados** (pedido do usuário): os julgamentos se apoiam em
convenções conhecidas da web, sem exemplos de produtos reais.

Capturas: `sondas/*_768_*.png` e as demais em `sondas/`.

## 1. Para que serve

- **Janela Agendar banca.**
  - **Quem usa:** gestor ou professor.
  - **O que precisa conseguir:** marcar a banca de um TCC com data, local, tempos, prazos e avaliadores, sem errar.
- **Painel.**
  - **Quem usa:** o gestor.
  - **O que precisa conseguir:** ver em 5 segundos se há aluno em risco e o que fazer.
- **Acompanhamento.**
  - **Quem usa:** o professor.
  - **O que precisa conseguir:** ver o progresso de cada aluno e registrar o parecer.
- **Sala de estudo.**
  - **Quem usa:** o aluno.
  - **O que precisa conseguir:** saber qual é a próxima aula e fazê-la.

Regras do produto usadas como régua: `prototipo_ux/SKILL_UX_UI.md` (R1–R12) e os tokens de `paletas.py`.

## 2. Achados, do que mais atrapalha para o que menos atrapalha

### Corrigir antes de usar

1. **Busca de avaliador sem resultado não diz nada.** (Janela Agendar banca, protótipo.)
   - Ao digitar "zzzz" na busca, a lista some (fica com 2 px de altura, 0 itens) e não aparece mensagem nenhuma.
   - A pessoa não sabe se a busca falhou, se a lista ainda está carregando ou se não existe ninguém com aquele nome.
   - **Correção:** dentro de `desenhar()`, se nenhum item passar pelo filtro, mostrar "Nenhum avaliador encontrado para
     «zzzz»" e um link "Cadastrar avaliador" (a tela `/bancas/avaliadores` já existe).
2. **Prazos cortados no celular.** (Janela, 390 px.)
   - Em 768 px os três prazos cabem.
   - Em 390 px aparece só `dd/mm/yyyy`, sem a hora.
   - **Correção:** usar `col-12 col-sm-4`.
3. **O foco sai da janela ao marcar ou remover um avaliador.** Depois disso, o Esc para de funcionar.
   - **Correção:** devolver o foco ao item recriado. (Detalhes em accessibility-review.md, item 6.)
4. **Os botões de escolha rápida mostram o escolhido só pela cor.** São os botões 10/15/20, 5/10/15 e 12/24/48 h.
   - **Correção:** acrescentar `aria-pressed` e um nome com a unidade ("20 minutos").
5. **Anel de foco fraco no menu e no "Fechar":** 1,31–1,41:1.
   - **Correção:** estender o `outline` de 3 px do tema a `.nav-link` e `.btn-close`.

### Corrigir para não parecer inacabado ou inconsistente

6. **Acompanhamento: botões principais em excesso.**
   - Cada cartão de aluno tem **dois** botões azuis cheios, um embaixo do outro ("Ver aulas e andamento" e
     "Atualizar Progresso & Anotações").
   - O topo tem um terceiro ("+ Vincular Aluno a Curso").
   - Com 10 alunos são 21 botões principais na tela, e nenhum se destaca.
   - **Correção:** um botão cheio por cartão ("Atualizar progresso"). "Ver aulas" vira botão de contorno ou link.
7. **Acompanhamento: "Plataforma: Plataforma".**
   - O rótulo "Plataforma:" é seguido de uma etiqueta que também diz "Plataforma" (no cartão do Demo Aluno). Parece um
     texto de exemplo esquecido.
   - O valor vem do cadastro do curso (`curso.plataforma = "Plataforma"`).
   - No mesmo trecho, o texto reserva está fixo e fora da tradução, com gênero trocado entre as duas linhas:
     - `templates/acompanhamento.html:301`: `item.curso.plataforma or 'Externa'`;
     - linha 918: `or 'Externo'`.
   - **Correção:**
     - quando o curso é da própria plataforma, mostrar o nome dela (Identidade);
     - passar os textos reservas por `tt()`, com um só gênero.
8. **Acompanhamento: caixas de texto vazias parecem campos.**
   - "Nenhuma anotação registrada." e "Nenhum parecer do professor(a) registrado." ficam em caixas com borda de campo de
     formulário. Parecem editáveis, mas não são: para escrever é preciso clicar em "Atualizar Progresso & Anotações".
   - **Correção:** estado vazio em texto secundário, sem borda, com o link "Escrever parecer" ali mesmo.
9. **Ícones de dois sistemas.**
   - O produto usa Bootstrap Icons (60 a 290 por tela), mas alguns botões usam emoji como ícone: "🚀 Jovem Seguro 2026",
     "🧭 Tour", "🔍 Expandir / Tela Cheia", "🔍 Expandir Parecer", "🧠 Conectar Gemini Notebook", "⏳ Lembrar Depois",
     "❌ Não mostrar novamente".
   - O emoji muda de cara em cada sistema (Windows, Android, iPhone) e não segue a cor do tema. É um dos sinais de
     "visual genérico".
   - **Correção:** trocar por `bi-rocket-takeoff`, `bi-compass`, `bi-arrows-fullscreen`, `bi-lightbulb`, `bi-clock`,
     `bi-x-circle`.
10. **Títulos de página na cor de ação.** "Acompanhamento de Estudos", "Painel de Indicadores", "Word 2016 - …" e
    "Português" estão em azul, a mesma cor dos links e botões. O título parece clicável. **Correção:** usar `--p-fg`.
11. **Menu do topo em duas linhas** no Administrador, de 1200 a 1599 px. A segunda linha (sino, idioma, tema, Tour, Sair)
    fica solta embaixo do menu.
    - **Correção:** juntar idioma, tema e Tour num menu "Preferências" (ícone de engrenagem). Assim cabe numa linha até
      1200 px.
12. **Duas formas de escolher o mesmo valor na janela.** Botões 10/15/20 mais o campo "15 min", e o mesmo para as
    perguntas e para as horas.
    - **Correção:** os botões e um "Outro…" que mostra o campo.
13. **Mistura de Title Case e sentence case:**
    - Title Case: "Atualizar Progresso & Anotações", "Conectar Gemini Notebook", "Vincular Aluno a Curso",
      "Iniciar Contagem", "Inserir Manual";
    - sentence case: "Ver aulas e andamento", "Personalizar gráficos", "Agendar banca".
    - **Correção:** sentence case em tudo, que é o normal em português.

### Polimento

14. **Textos com "(s)":** "2 alerta(s) de acompanhamento", "4 aula(s) no total", "1 concluída(s)",
    "0 escolhido(s)". Trocar pela forma certa conforme o número.
15. **Painel em 768 px:** o cartão "Projetos (TCC)" fica sozinho na última linha, e "PROJETOS (TCC)" é o único rótulo em
    maiúsculas.
16. **Sala de estudo:** a barra em 37% convive com "1 concluída(s)". Escrever de onde vem o número.

## 3. O que já funciona

- **Janela nova:** é bem melhor que a atual.
  - Tem seções nomeadas e um subtítulo que diz o que fazer.
  - O rodapé fixo resume o que acontece ao salvar.
  - A escolha de avaliadores tem busca e etiquetas (antes era uma lista "segure Ctrl").
  - Em 768 px a janela cabe inteira e sem cortes.
- **Contraste e tema escuro:** o contraste passa em tudo nos dois temas. O escuro tem três tons de superfície e o âmbar
  leva texto escuro, e os cabeçalhos coloridos que deixavam texto ilegível sumiram.

---

Para corrigir, a skill complementar é a `ui-polish`, que não foi rodada: a tarefa é só de leitura.
