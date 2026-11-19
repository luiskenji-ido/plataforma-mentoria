# design:design-system (modo "audit") — saída da skill

## Como a skill funciona

É um roteiro de auditoria: tokens, componentes, nomes e o que está fixo no código.

- **Como apliquei:** contagem no código (grep, só leitura) em `prototipo_ux/paletas.py`, `prototipo_ux/static/tema.css`
  e `templates/*.html`, comparando com a R3 da `SKILL_UX_UI.md`.
- **Nota da skill:** a nota "/100" que o modelo da skill pede **não foi dada**. Uma nota única esconde qual eixo falhou;
  vai por eixo.

---

## Design System Audit — tema do protótipo v2 sobre as telas atuais

### Resumo

**O que foi revisado:**

- 30 tokens de cor por tema, nos 4 temas;
- 10 componentes do Bootstrap que o tema reescreve (botão, campo, janela, cartão, tabela, etiqueta, menu, lista,
  alerta, progresso);
- 50 templates.

**Problemas:** 5.

### Nomes

| Problema | Onde | Padrão a adotar |
|---|---|---|
| O tema usa nomes por papel (`--p-fg`, `--p-accent-text`, `--p-ok-soft`), e as telas usam nomes por cor (`text-dark`, `bg-white`, `text-success`); o tema "traduz" um para o outro com `!important` | `tema.css` linhas 40–60 | Nas telas novas, usar só o papel (`text-body`, `text-body-secondary`, ou uma classe utilitária do tema). É o que a R3 já pede |
| Tokens de raio misturados: existe `--p-r-lg`, mas convive com `8px`, `10px`, `12px` e `999px` escritos à mão | `tema.css` | `--p-r-sm` (8) · `--p-r-lg` (12) · `--p-r-pill` (999) |

### Cobertura de tokens

| Categoria | Definidos | Valores fixos encontrados |
|---|---|---|
| Cores | 30 por tema (`paletas.py`, 144 pares conferidos) | `tema.css`: 0 cores soltas ✅. **Templates: 458 classes de cor fixa** (`text-dark`, `text-white`, `bg-white`, `bg-light`, `bg-dark`, `text-light`, `text-black`) em 50 arquivos, e 24 `style="color/background:#…"` em 9 arquivos. As que mais têm: admin_turmas 39, acompanhamento 37, projetos 31, dashboard 27, base 22. Além disso, ~650 cores hex dentro de `<style>` de templates (base 177, acompanhamento 101, agentes_* ~45 cada) |
| Tipografia | 2 famílias (`--p-body` Inter, `--p-display` Space Grotesk); **nenhum token de tamanho** | `tema.css`: 10 tamanhos escritos à mão (.7, .72, .75, .8, .85, .88, 1, 1.15rem, 15px). Templates: **185 `font-size` inline**. É daí que vêm os 12 tamanhos por tela e os 9,84 px medidos pelo ux-ui-audit |
| Espaçamento | nenhum token (usa o do Bootstrap) | 15–18 valores distintos por tela (ux-ui-audit); aceitável enquanto vier do Bootstrap |
| Bordas e raios | 1 token (`--p-r-lg`) | 6 valores à mão no tema; 7 a 10 raios distintos por tela |
| Sombras | 1 token (`--p-sombra`) | ok |

### Componentes e estados

| Componente | Estados | Variantes | Foco (R8) | Nota |
|---|---|---|---|---|
| Botão `.btn` | ✅ hover, ativo, desativado | ✅ primário, contorno, perigo | ✅ 3 px na cor de ação | — |
| Campo `.form-control` / `.form-select` | ✅ | ✅ | ⚠️ só borda + halo de 35% (1,7:1) | ver accessibility-review |
| Link do menu `.nav-link` | ✅ hover, ativo | — | ❌ anel do Bootstrap (1,41:1) | o tema não cobre |
| Fechar `.btn-close` | — | — | ❌ anel do Bootstrap (1,41:1) | o tema não cobre |
| Escolha rápida `.proto-seg` | ⚠️ escolhido só pela cor | — | ⚠️ contorno de 1 px do navegador | falta `aria-pressed` |
| Etiqueta do avaliador `.proto-chip` | ✅ | — | ⚠️ | some ao remover (perde o foco) |

### O que o Agente UX cobre hoje (para comparar)

- **A R3 não tem verificação nenhuma.**
  - `varredura_ux.py` não procura `text-dark`, `bg-white`, `bg-light` nem `style="color:#…"`.
  - A regra existe só no papel, e as 458 ocorrências passam em silêncio.
  - Hoje é o tema do protótipo que "conserta" essas classes por cima, com `!important`.
- **Não há verificação de tamanho de letra** (o mínimo e a escala).

### Ações por prioridade

1. **Fazer a R3 virar varredura.**
   - Contar as classes de cor fixa e os `style` com cor por template, como alerta.
   - Com o `{# ux: ok - motivo #}` para o que for de propósito (ex.: o PDF do relatório ESG, que é sempre claro).
2. **Criar tokens de tamanho de letra e de raio** no `paletas.py` (`--p-fs-xs/sm/md/lg/xl/2xl`, `--p-r-sm/lg/pill`) e
   trocar os 10 tamanhos e os 6 raios do `tema.css` por eles. A escala de 12 tamanhos por tela cai para 6.
3. **Estender o foco da R8** a `.nav-link`, `.btn-close`, `.dropdown-item`, `.form-check-input` e aos botões de escolha
   rápida.
