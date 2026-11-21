# AGENTS.md — Mentoria (Flask + SQLAlchemy)

Responda em português do Brasil.

## Comandos (Windows: `.venv\Scripts\python`)
- Instalar: `pip install -r requirements-dev.txt`
- Rodar: `python app.py` → http://127.0.0.1:5000 (aplica migrações ao iniciar)
- Testes: `pytest tests/unit -q` (um: `pytest tests/unit/test_x.py::test_y -q`); integração/e2e precisam do Docker
- Lint: `ruff check .` · formato só nos arquivos listados no `ruff format --check` de `.github/workflows/ci.yml`
- Migração após mudar `models.py`: `PULAR_ATUALIZACAO_BANCO=1 flask --app app db migrate -m "..."`
- Tema: `python tema_plataforma.py` (confere contraste e gera `static/css/tokens.css`)
- Regras escritas direto: `python agentes_funcionalidades/varredura_regras.py`
- Agentes: `python agentes_funcionalidades/gestor_funcionalidades.py` · `python agentes_omnitest/executar_todos.py`

## Convenções
- Poder de perfil → regra nomeada `PERFIS_*` em MAIÚSCULAS (`tipo_usuario in PERFIS_X`), nunca lista literal; exceção: `# regra-nomeada: ok (motivo)`.
- Texto de tela → chave em `traducoes*.py` via `t()`/`tt()`; nome da instituição só por `{apelido}`/`{instituicao}`/`{plataforma}` ou `marca.*` (nada fixo no código).
- Cor → papel do tema (`static/css/tema.css`, paleta em `tema_plataforma.py`); sem `text-dark`/`bg-white`/`style="color:"` fixos.
- Escreva "B2B", nunca "Aon".
- Texto longo no MySQL: `LONGTEXT`.

## Limites
- Nunca: senha de teste no código (só `.env` `OMNITEST_SENHA` ou tela criptografada); incluir `Agent Reports/*` em commit; deixar dados ou notificações de teste para usuários reais.
- Nunca: agentes ou contas `@local.com` usam IA real ou contatam Microsoft/Google de verdade; pentest só contra host local ou de teste.
- Contas `@local.com` bloqueadas em produção (exceto `OMNITEST_PERMITIR_EM_PRODUCAO=1`).
- Pergunte antes: commit e push (main recebe `git push origin <branch>:main`); criar conta ou digitar cartão em nuvem (o usuário faz).
- Outras sessões podem estar editando esta pasta: não reverta nem inclua em commit arquivos que você não mexeu.

## Pronto significa
- Mudança pequena: `ruff check` + teste de unidade relacionado.
- Tela ou regra: abrir no navegador (desktop e 375 px) nos 4 temas; rodar o agente da área.
- Mudança em `models.py`: migração gerada e aplicada.

## Como trabalhar
- Resposta direta, sem introdução nem resumo.
- Busque (grep/glob) antes de abrir; `app.py` tem ~10 mil linhas: leia por trecho.
- Não releia arquivo que acabou de editar; filtre saídas longas.
- Exploração ampla só de leitura → subagente, que devolve só a conclusão.

## Ler quando precisar
- `ReadME.md` — Assistente, Provedores de IA, Tour, Identidade, banco, instalador, Ubuntu.
- `deploy/<nuvem>/` — publicar (AWS: `deploy/aws/Roteiro_deploy_AWS.docx`).
- `prototipo_ux/SKILL_UX_UI.md` — régua de UX/UI.
- `regras_testes_b2b.md` — testes do perfil B2B.

<!-- Higiene de sessão (pessoas):
- /clear entre tarefas sem relação; /compact "preserve X, Y" no meio de uma tarefa.
- /context e /usage mostram o que consome tokens; /memory mostra os arquivos de instrução carregados.
- MCP e skills desligados quando não usados — cada um soma definições ao contexto.
- Não edite este arquivo no meio da sessão: arquivo estável mantém o cache do prompt.
-->
