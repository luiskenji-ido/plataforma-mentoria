# -*- coding: utf-8 -*-
"""
AGENTE DE SEGURANÇA — CONFIGURAÇÃO E SEGREDOS
Uso: python agentes_seguranca/agente_configuracao.py
Lê a configuração do Flask, o .gitignore, os arquivos versionados no Git e procura segredos expostos no código.
Os valores encontrados aparecem MASCARADOS no relatório.
"""
import os
import re
import subprocess

from base import AgenteSeguranca, RAIZ_PROJETO

PADROES_SEGREDO = [
    ("Chave de API do Google", r"AIza[0-9A-Za-z\-_]{35}"),
    ("Segredo de cliente OAuth do Google", r"GOCSPX-[0-9A-Za-z\-_]{20,}"),
    ("Chave secreta estilo OpenAI/Anthropic", r"\bsk-(?:ant-)?[A-Za-z0-9\-_]{20,}"),
    ("Chave de acesso AWS", r"AKIA[0-9A-Z]{16}"),
    ("Chave privada", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("Token do GitHub", r"gh[pousr]_[A-Za-z0-9]{36}"),
]
ARQUIVOS_SENSIVEIS = [r"(^|/)\.env$", r"\.db$", r"client_secret.*\.json$", r"credentials.*\.json$", r"token.*\.(json|pickle)$", r"\.pem$", r"\.key$"]


def mascarar(valor):
    return valor[:4] + "…" + valor[-3:] if len(valor) > 10 else "…"


class AgenteConfiguracao(AgenteSeguranca):
    chave = "configuracao"
    nome = "Agente Configuração e Segredos"
    especialidade = "configuração do Flask, sessão, cabeçalhos, segredos e higiene do repositório"
    ROTEIRO = ["SECRET_KEY, modo debug, cookies de sessão e limite de upload",
               "Proteções ausentes: CSRF, cabeçalhos de segurança e limite de tentativas",
               "Arquivos sensíveis versionados no Git e cobertura do .gitignore",
               "Varredura de segredos (chaves de API, tokens, chaves privadas) nos arquivos versionados",
               "Arquivo de dependências legível para o pip"]

    def rodar(self):
        self.app_py = open(os.path.join(RAIZ_PROJETO, "app.py"), encoding="utf-8").read()
        # As proteções web (cookies, CSRF, cabeçalhos, limites) podem morar no módulo seguranca_web.py
        caminho_web = os.path.join(RAIZ_PROJETO, "seguranca_web.py")
        self.config_py = self.app_py + (open(caminho_web, encoding="utf-8").read() if os.path.exists(caminho_web) else "")
        self.configuracao_flask()
        self.protecoes_ausentes()
        self.repositorio()
        self.segredos()
        self.dependencias_legiveis()

    def linha_de(self, trecho):
        i = self.app_py.find(trecho)
        return self.app_py.count("\n", 0, i) + 1 if i >= 0 else "?"

    def configuracao_flask(self):
        self.etapa("Configuração do Flask")
        m = re.search(r"app\.config\[['\"]SECRET_KEY['\"]\]\s*=\s*(['\"])(.*?)\1", self.app_py)
        if m:
            self.achado("SECRET_KEY fixa no código-fonte", "Crítica", "A02", "CWE-798", f"app.py:{self.linha_de(m.group(0))}",
                        f"SECRET_KEY = '{mascarar(m.group(2))}' versionada no Git ({len(m.group(2))} caracteres).",
                        "Ler a chave de uma variável de ambiente (os.environ['SECRET_KEY'] / .env) com valor aleatório de 32+ bytes "
                        "(secrets.token_hex(32)) e trocar a chave atual: quem tem o código pode forjar sessões de qualquer usuário.",
                        ["https://flask.palletsprojects.com/en/stable/config/#SECRET_KEY"])
        else:
            self.ok("SECRET_KEY não está fixa no código")
        if re.search(r"app\.run\([^)]*debug\s*=\s*True", self.app_py):
            self.achado("Modo debug ligado em app.run()", "Média", "A05", "CWE-489", f"app.py:{self.linha_de('app.run(')}",
                        "app.run(debug=True) liga o depurador interativo do Werkzeug quando o app roda com 'python app.py'.",
                        "Usar debug=os.environ.get('FLASK_DEBUG') == '1'. No PythonAnywhere o WSGI não chama app.run(), mas confirme que o debug está desligado lá.",
                        ["https://flask.palletsprojects.com/en/stable/debugging/"])
        else:
            self.ok("app.run sem debug fixo")
        for opcao, sev, cwe, texto in (("SESSION_COOKIE_SECURE", "Média", "CWE-614", "o cookie de sessão pode trafegar sem HTTPS"),
                                       ("SESSION_COOKIE_SAMESITE", "Média", "CWE-1275", "sem SameSite o cookie vai em requisições de outros sites (CSRF)"),
                                       ("REMEMBER_COOKIE_SECURE", "Baixa", "CWE-614", "o cookie 'lembrar-me' do Flask-Login pode trafegar sem HTTPS")):
            if opcao not in self.config_py:
                valor = '"Lax"' if 'SAMESITE' in opcao else 'True'
                self.achado(f"{opcao} não configurado", sev, "A05", cwe, "app.py (configuração)", f"Opção ausente: {texto}.",
                            f"Definir app.config['{opcao}'] = {valor} em produção (HTTPS).",
                            ["https://flask.palletsprojects.com/en/stable/security/#set-cookie-options"])
            else:
                self.ok(f"{opcao} configurado")
        if "MAX_CONTENT_LENGTH" not in self.config_py:
            self.achado("Sem limite global de tamanho de requisição/upload", "Média", "A05", "CWE-400", "app.py (configuração)",
                        "MAX_CONTENT_LENGTH não está definido: uploads gigantes podem esgotar disco e memória.",
                        "Definir app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024 (ou o maior limite real da plataforma).",
                        ["https://flask.palletsprojects.com/en/stable/patterns/fileuploads/#improving-uploads"])
        else:
            self.ok("MAX_CONTENT_LENGTH definido")

    def protecoes_ausentes(self):
        self.etapa("Proteções da aplicação")
        if not re.search(r"CSRFProtect|csrf_token|flask_wtf", self.config_py):
            self.achado("Formulários sem proteção CSRF", "Alta", "A01", "CWE-352", "app.py (todas as rotas POST)",
                        "Nenhum token CSRF nos formulários: um site malicioso pode enviar POST em nome do usuário logado "
                        "(trocar senha, excluir projeto, restaurar backup...).",
                        "Adicionar Flask-WTF CSRFProtect(app) e {{ csrf_token() }} nos formulários; nas chamadas fetch, enviar o cabeçalho X-CSRFToken.",
                        ["https://flask-wtf.readthedocs.io/en/stable/csrf/", "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html"])
        else:
            self.ok("Proteção CSRF presente")
        if not re.search(r"Content-Security-Policy|Talisman|X-Frame-Options", self.config_py):
            self.achado("Cabeçalhos de segurança HTTP ausentes", "Média", "A05", "CWE-693", "app.py (respostas)",
                        "Não há Content-Security-Policy, X-Frame-Options, X-Content-Type-Options nem Referrer-Policy.",
                        "Usar Flask-Talisman ou um @app.after_request que defina CSP (com os CDNs usados), X-Frame-Options: DENY, "
                        "X-Content-Type-Options: nosniff e Referrer-Policy: strict-origin-when-cross-origin.",
                        ["https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html"])
        else:
            self.ok("Cabeçalhos de segurança configurados")
        if not re.search(r"Limiter|flask_limiter|LimitadorRequisicoes", self.config_py):
            self.achado("Sem limite de requisições (rate limiting)", "Baixa", "A07", "CWE-307", "app.py (login, recuperação de senha, chat IA)",
                        "O login bloqueia após 5 tentativas por conta, mas não há limite por IP: dá para testar senhas em muitas contas "
                        "e abusar da recuperação de senha e do chat com IA.",
                        "Adicionar Flask-Limiter nas rotas de login, recuperação de senha e /chat-ia (ex.: 10/minuto por IP).",
                        ["https://flask-limiter.readthedocs.io/"])
        else:
            self.ok("Rate limiting presente")

    def repositorio(self):
        self.etapa("Higiene do repositório Git")
        try:
            versionados = subprocess.run(["git", "ls-files"], cwd=RAIZ_PROJETO, capture_output=True, text=True, timeout=30).stdout.splitlines()
        except Exception as e:
            self.log(f"git indisponível: {e}")
            versionados = []
        self.versionados = versionados
        sensiveis = [a for a in versionados if any(re.search(p, a, re.I) for p in ARQUIVOS_SENSIVEIS)]
        if sensiveis:
            self.achado("Arquivos sensíveis versionados no Git", "Crítica", "A05", "CWE-538", ", ".join(sensiveis[:8]),
                        f"{len(sensiveis)} arquivo(s) com segredos ou dados podem estar no histórico do repositório.",
                        "Remover do Git (git rm --cached), incluir no .gitignore e trocar os segredos expostos (eles continuam no histórico).")
        else:
            self.ok(f"Nenhum arquivo sensível entre {len(versionados)} versionados")
        try:
            gitignore = open(os.path.join(RAIZ_PROJETO, ".gitignore"), encoding="utf-8").read()
        except OSError:
            gitignore = ""
        faltando = [e for e in (".env", "instance/", "client_secret.json", "uploads/", "*.db") if e not in gitignore]
        if faltando:
            self.achado("Itens sensíveis fora do .gitignore", "Média", "A05", "CWE-538", ".gitignore", "Faltam: " + ", ".join(faltando),
                        "Incluir as entradas no .gitignore.")
        else:
            self.ok(".gitignore cobre .env, instance/, uploads/, banco e client_secret")
        nao_ignorados = [n for n in ("Agent Reports", "agentes_conhecimento") if n not in gitignore]
        if "Agent Reports" in nao_ignorados:
            self.achado("Relatórios de teste com evidências fora do .gitignore", "Baixa", "A05", "CWE-538", ".gitignore",
                        "A pasta 'Agent Reports' (prints de tela, e-mails de teste e relatórios de segurança) não está no .gitignore.",
                        "Incluir 'Agent Reports/' no .gitignore para não publicar evidências por engano.")

    def segredos(self):
        self.etapa("Varredura de segredos nos arquivos versionados")
        encontrados = []
        for rel in self.versionados:
            caminho = os.path.join(RAIZ_PROJETO, rel)
            if not os.path.isfile(caminho) or os.path.getsize(caminho) > 1_000_000 or rel.endswith((".png", ".jpg", ".pdf", ".ico", ".db")):
                continue
            try:
                texto = open(caminho, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for nome, padrao in PADROES_SEGREDO:
                for m in re.finditer(padrao, texto):
                    linha = texto.count("\n", 0, m.start()) + 1
                    encontrados.append((nome, f"{rel}:{linha}", mascarar(m.group(0))))
        for nome, local, valor in encontrados[:15]:
            self.achado(f"{nome} exposta no código", "Crítica", "A02", "CWE-798", local, f"Valor mascarado: {valor}",
                        "Revogar/trocar o segredo no provedor, mover para variável de ambiente (.env fora do Git) e limpar o histórico do Git.")
        if not encontrados:
            self.ok(f"Nenhum segredo conhecido nos {len(self.versionados)} arquivos versionados")
        senha_teste = os.environ.get("OMNITEST_SENHA", "")
        if not senha_teste:
            try:
                from dotenv import dotenv_values
                senha_teste = dotenv_values(os.path.join(RAIZ_PROJETO, ".env")).get("OMNITEST_SENHA") or ""
            except ImportError:
                pass
        teste = [rel for rel in self.versionados if senha_teste and rel.endswith(".py") and os.path.isfile(os.path.join(RAIZ_PROJETO, rel))
                 and senha_teste in open(os.path.join(RAIZ_PROJETO, rel), encoding="utf-8", errors="ignore").read()]
        if teste:
            self.achado("Senha das contas de teste escrita no código", "Média", "A07", "CWE-259", ", ".join(teste[:4]),
                        "A senha padrão das contas *_ominitest está nos agentes de teste; quem lê o repositório entra nessas contas.",
                        "Ler a senha de teste de variável de ambiente (OMNITEST_SENHA) e garantir que as contas de teste não existam em produção.")

    def dependencias_legiveis(self):
        self.etapa("Arquivo de dependências")
        caminho = os.path.join(RAIZ_PROJETO, "requirements.txt")
        if not os.path.exists(caminho):
            self.achado("requirements.txt ausente", "Baixa", "A06", "CWE-1104", "requirements.txt", "Sem lista de dependências fixadas.",
                        "Gerar com pip freeze > requirements.txt (UTF-8).")
            return
        bruto = open(caminho, "rb").read(4)
        if bruto.startswith((b"\xff\xfe", b"\xfe\xff")):
            self.achado("requirements.txt em UTF-16", "Baixa", "QUAL", "CWE-1104", "requirements.txt",
                        "O arquivo foi gerado pelo PowerShell em UTF-16; o pip do PythonAnywhere pode falhar ao instalar.",
                        "Regerar em UTF-8: pip freeze | Out-File -Encoding utf8 requirements.txt (ou rodar pelo Git Bash).")
        else:
            self.ok("requirements.txt em UTF-8")


if __name__ == "__main__":
    AgenteConfiguracao().executar()
