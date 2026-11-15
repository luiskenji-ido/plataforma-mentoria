# -*- coding: utf-8 -*-
"""
BASE DOS AGENTES DE SEGURANÇA
=============================
Cada agente é um especialista (dados, configuração, código, dependências, pentest). Todos:
  - registram ACHADOS com severidade (Crítica → Informativa), categoria OWASP Top 10 (2021), CWE, local exato,
    evidência, recomendação e referências oficiais;
  - publicam o andamento ao vivo (agente.json com o "feed" que a tela Agentes de Segurança mostra no console central);
  - geram um relatório JSON e um prompt de correção para qualquer LLM.
Só analisam a PRÓPRIA plataforma. O pentest só roda contra hosts locais/de teste (ver pentest.HOSTS_PERMITIDOS).
"""
import os
import sys
import json
import time
from datetime import datetime

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)
for _fluxo in (sys.stdout, sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")

PASTA_RELATORIOS = os.path.join(RAIZ_PROJETO, "Agent Reports", "Seguranca")
PASTA_AO_VIVO = os.environ.get("SEGURANCA_AO_VIVO", "")
SEVERIDADES = ["Crítica", "Alta", "Média", "Baixa", "Informativa"]
PESO = {"Crítica": 10, "Alta": 6, "Média": 3, "Baixa": 1, "Informativa": 0}
OWASP = {
    "A01": "A01:2021 Quebra de controle de acesso", "A02": "A02:2021 Falhas criptográficas", "A03": "A03:2021 Injeção",
    "A04": "A04:2021 Design inseguro", "A05": "A05:2021 Configuração incorreta de segurança",
    "A06": "A06:2021 Componentes vulneráveis e desatualizados", "A07": "A07:2021 Falhas de identificação e autenticação",
    "A08": "A08:2021 Falhas de integridade de software e dados", "A09": "A09:2021 Falhas de log e monitoramento",
    "A10": "A10:2021 Server-Side Request Forgery", "QUAL": "Qualidade de código (pode virar vulnerabilidade)",
}
REF_OWASP = "https://owasp.org/Top10/"


def _gravar_atomico(caminho, conteudo):
    temporario = caminho + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as f:
            f.write(conteudo)
        os.replace(temporario, caminho)
    except OSError:
        pass


class AgenteSeguranca:
    chave = ""
    nome = ""
    especialidade = ""
    ROTEIRO = []

    def __init__(self):
        self.achados = []
        self.verificacoes = 0
        self.feed = []
        self.etapa_atual = ""
        self.carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.inicio = time.time()

    # ------------------------------------------------------------------ registro
    def etapa(self, texto):
        self.etapa_atual = texto
        self.log(f"▶ {texto}")

    def log(self, texto):
        linha = f"{datetime.now().strftime('%H:%M:%S')}  {texto}"
        print(linha)
        self.feed = (self.feed + [linha])[-40:]
        self.publicar()

    def ok(self, texto):
        self.verificacoes += 1
        self.log(f"✓ {texto}")

    def achado(self, titulo, severidade, categoria, cwe, local, evidencia, recomendacao, referencias=None):
        """Registra uma vulnerabilidade ou fraqueza. 'local' = arquivo:linha ou método + URL."""
        self.verificacoes += 1
        item = {"id": f"{self.chave.upper()[:3]}-{len(self.achados) + 1:03d}", "titulo": titulo, "severidade": severidade,
                "categoria": OWASP.get(categoria, categoria), "cwe": cwe, "local": local, "evidencia": str(evidencia)[:1200],
                "recomendacao": recomendacao, "referencias": list(referencias or []) + ([f"https://cwe.mitre.org/data/definitions/{cwe.split('-')[1]}.html"] if cwe and cwe.startswith("CWE-") else []),
                "hora": datetime.now().strftime("%H:%M:%S")}
        self.achados.append(item)
        self.log(f"⚠ [{severidade}] {titulo} — {local}")
        return item

    def contagem(self):
        return {s: sum(1 for a in self.achados if a["severidade"] == s) for s in SEVERIDADES}

    def publicar(self):
        if not PASTA_AO_VIVO:
            return
        os.makedirs(PASTA_AO_VIVO, exist_ok=True)
        dados = {"chave": self.chave, "nome": self.nome, "etapa": self.etapa_atual, "verificacoes": self.verificacoes,
                 "contagem": self.contagem(), "feed": self.feed[-30:], "atualizado": datetime.now().isoformat(timespec="seconds")}
        _gravar_atomico(os.path.join(PASTA_AO_VIVO, "agente.json"), json.dumps(dados, ensure_ascii=False))

    # ------------------------------------------------------------------ execução
    def rodar(self):
        raise NotImplementedError

    def executar(self):
        print(f"\n🛡️ {self.nome} — {self.especialidade}")
        for i, passo in enumerate(self.ROTEIRO, 1):
            print(f"   {i:>2}. {passo}")
        try:
            self.rodar()
        except Exception as e:
            self.achado(f"O agente parou por erro interno: {e.__class__.__name__}", "Informativa", "A09", "", self.etapa_atual or "-",
                        str(e), "Conferir o log do agente e rodar de novo.")
        return self.gerar_relatorio()

    # ------------------------------------------------------------------ saída
    def nota_de_risco(self):
        """0 (nenhum risco) a 100 (risco máximo), ponderando as severidades."""
        pontos = sum(PESO[a["severidade"]] for a in self.achados)
        return min(100, pontos * 2)

    def referencias_aprovadas(self):
        """Referências oficiais aprovadas na Governança de aprendizados (entram no prompt)."""
        try:
            from app import app
            import conhecimento
            with app.app_context():
                itens = conhecimento.referencias_aprovadas()
                conhecimento.registrar_consumo(f"seguranca_{self.chave}", itens)
                return [{"titulo": json.loads(a.conteudo).get("tema") or a.titulo, "url": a.fonte_url,
                         "resumo": json.loads(a.conteudo).get("resumo", "")[:280]} for a in itens]
        except Exception:
            return []

    def gerar_prompt(self, caminho):
        ordenados = sorted(self.achados, key=lambda a: SEVERIDADES.index(a["severidade"]))
        relevantes = [a for a in ordenados if a["severidade"] != "Informativa"]
        linhas = [f"# 🛡️ Prompt de Correção de Segurança para LLM — {self.nome}\n",
                  f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelos Agentes de Segurança. Cole no assistente de IA da sua "
                  "preferência (ChatGPT, Claude, Gemini, Copilot ou outro), anexando os arquivos citados.\n", "---\n"]
        if not relevantes:
            linhas.append(f"✅ O {self.nome} não encontrou vulnerabilidades relevantes ({self.verificacoes} verificações). Não há correções para pedir.")
        else:
            linhas += [
                "Você é um engenheiro de segurança de aplicações sênior (AppSec), especialista em Python, Flask, Flask-Login, "
                "Flask-SQLAlchemy, Jinja2, Bootstrap 5, Chart.js, SQLite e implantação no PythonAnywhere.",
                f"Uma auditoria automática ({self.especialidade}) desta plataforma de mentoria encontrou os {len(relevantes)} problemas abaixo.\n",
                "Para CADA item:",
                "1. Confirme se é explorável e explique o impacto em até 3 frases (cite OWASP/CWE).",
                "2. Entregue a correção como trechos ANTES → DEPOIS prontos para colar, sem quebrar as permissões dos perfis.",
                "3. Prefira as bibliotecas oficiais do ecossistema (ex.: Flask-WTF para CSRF, Flask-Talisman para cabeçalhos, Flask-Limiter para limites).",
                "4. Textos novos de interface vão para traducoes_literais.py (pt, en, es) e são usados com tt('texto').",
                "5. Diga como testar a correção (manual e com o agente de segurança).\n",
            ]
            refs = self.referencias_aprovadas()
            if refs:
                linhas.append("**Referências oficiais aprovadas pelo Agente Gerente Técnico:**\n")
                linhas += [f"- [{r['titulo']}]({r['url']}) — {r['resumo']}" for r in refs]
                linhas.append("")
            linhas.append("## Achados (do mais grave para o menos grave)\n")
            for i, a in enumerate(relevantes, 1):
                linhas += [f"### {i}. [{a['severidade']}] {a['titulo']}",
                           f"- **Categoria:** {a['categoria']} · **{a['cwe'] or 'sem CWE'}**",
                           f"- **Onde:** `{a['local']}`",
                           f"- **Evidência:** {a['evidencia']}",
                           f"- **Recomendação:** {a['recomendacao']}",
                           f"- **Referências:** {', '.join(a['referencias']) or REF_OWASP}", ""]
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    def gerar_relatorio(self):
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        base = os.path.join(PASTA_RELATORIOS, f"Seguranca_{self.chave}_{self.carimbo}")
        self.gerar_prompt(base + "_prompt.md")
        dados = {"chave": self.chave, "nome": self.nome, "especialidade": self.especialidade, "roteiro": self.ROTEIRO,
                 "verificacoes": self.verificacoes, "contagem": self.contagem(), "nota_risco": self.nota_de_risco(),
                 "achados": sorted(self.achados, key=lambda a: SEVERIDADES.index(a["severidade"])),
                 "duracao_seg": int(time.time() - self.inicio), "carimbo": self.carimbo, "prompt": base + "_prompt.md"}
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        c = self.contagem()
        print(f"\n✅ {self.nome}: {self.verificacoes} verificações · Crítica {c['Crítica']} · Alta {c['Alta']} · Média {c['Média']} "
              f"· Baixa {c['Baixa']} · Info {c['Informativa']} · risco {self.nota_de_risco()}/100")
        return dados
