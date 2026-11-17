# Publicar no PythonAnywhere

| Recurso | Situação |
|---|---|
| Telas, cadastros, backups, lembretes, Assistente | funcionam |
| Banco | **MySQL** (incluso em todos os planos), PostgreSQL (plano pago) ou SQLite. SQL Server não existe lá. |
| Google, Microsoft 365 e IAs | exigem conta paga (acesso livre à internet) |
| Agentes OmniTest (navegador) | desligados (sem Chromium) |
| Agente Orquestrador | limitado (Git e processos em segundo plano restritos) |

Passos:
1. **Databases**: crie o banco MySQL (o nome fica `<usuário>$mentoria`) e anote a senha.
2. Console Bash:
   ```bash
   git clone <repositório> ~/Mentoria && cd ~/Mentoria
   python3.10 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   python instalar.py
   ```
   Escolha **PythonAnywhere** e **MySQL**; o servidor sugerido já é `<usuário>.mysql.pythonanywhere-services.com`.
   Pasta de backups padrão: `~/backups/mentoria`.
3. **Web** › Add a new web app › Manual configuration (Python 3.10):
   - *Virtualenv*: `/home/<usuário>/Mentoria/.venv`
   - *WSGI configuration file*:
     ```python
     import sys
     sys.path.insert(0, '/home/<usuário>/Mentoria')
     from app import app as application
     ```
   - *Static files*: URL `/static/` → `/home/<usuário>/Mentoria/static`
4. **Tasks**: tarefa de hora em hora com
   `cd ~/Mentoria && .venv/bin/python tarefas_agendadas.py` (lembretes, avisos e backups agendados).
5. **Reload** na aba Web.

Atualizações: `cd ~/Mentoria && git pull && .venv/bin/pip install -r requirements.txt`, depois **Reload**.
Depois de publicar, confira **Administração › Sistema › Ambiente e compatibilidade**.
