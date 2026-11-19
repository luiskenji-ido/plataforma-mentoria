# Protótipo de UX/UI

A plataforma real com o visual proposto, para experimentar antes de decidir. **Nada de produção é alterado**: o protótipo
roda o mesmo `app.py` numa cópia do banco (`dados/prototipo.db`) e numa porta própria, e coloca por cima:

- `paletas.py`: uma paleta por tema da plataforma (claro, escuro, futurista, vintage). Confere o contraste WCAG de cada
  par de cores antes de usar (`python prototipo_ux/paletas.py`); com um par reprovado, o protótipo nem sobe;
- `static/tema.css`: o tema proposto (cores por papel, fonte, botões, janelas, cartões, tabelas e etiquetas), que segue o
  tema escolhido por cada pessoa. Paleta e tema são relidos a cada página: mudou, é só dar F5;
- `templates/`: as telas redesenhadas (hoje, a janela **Agendar banca**); as outras continuam as atuais, só com o tema novo.

Apagar a pasta `prototipo_ux` desfaz tudo.

## Como abrir

Na raiz do projeto, em dois terminais:

```
python prototipo_ux/rodar_prototipo.py              # protótipo:      http://127.0.0.1:5070
python prototipo_ux/rodar_prototipo.py --sem-tema   # visual atual:   http://127.0.0.1:5071  (mesma cópia, para comparar)
```

`--novo-banco` recopia `instance/mentoria.db` para a cópia do protótipo. As portas 5060 e 5061 não servem: os navegadores
as bloqueiam.

Contas de demonstração (só existem na cópia do protótipo):

| Perfil        | E-mail                 | Senha            |
|---------------|------------------------|------------------|
| Administrador | demo_admin@local.com   | Demo@Aulas2026x  |
| Aluno         | demo_aluno@local.com   | Demo@Aulas2026x  |

Tudo o que for salvo no protótipo (bancas agendadas, notas…) fica só na cópia.

## Régua e medida

- `SKILL_UX_UI.md`: a skill de UX/UI (versão 2) que o Agente UX e as propostas seguem.
- `python prototipo_ux/comparar_contraste.py --rotulo prototipo_v2`: mede o contraste de cada texto nas mesmas telas, nos
  4 temas, no visual atual e no protótipo (grava `capturas/contraste.json`). Usa o mesmo medidor do Agente UX
  (`agentes_funcionalidades/contraste.py`).

## Capturas para o documento

Com os dois servidores no ar: `python prototipo_ux/capturar_telas.py` grava `capturas/<tela>_<tema>_antes.png` e
`_depois.png` nos 4 temas (computador 1440 px; a janela Agendar banca também no celular, 390 px). Depois,
`python prototipo_ux/gerar_documento.py` monta `Proposta_UX_UI_v2.docx` (precisa de `python-docx` e `pillow`).
`Proposta_UX_UI.docx` é a versão 1, guardada para comparação.
