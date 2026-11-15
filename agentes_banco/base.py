# -*- coding: utf-8 -*-
"""
BASE DOS AGENTES DE BANCO DE DADOS
==================================
Cada agente é um especialista (consultas e desempenho, esquema e índices, backup e recuperação, DBA de manutenção
e logs, multi-banco). Todos:
  - registram ACHADOS com severidade (Crítica → Informativa), categoria de banco de dados, local exato, evidência,
    recomendação (com o script SQL quando couber) e referências oficiais;
  - publicam o andamento ao vivo (agente.json, mostrado no console central da tela Agentes de Banco de Dados);
  - recebem os aprendizados do Gerente de Banco de Dados (conhecimento_banco.py);
  - geram um relatório JSON e um prompt de melhoria para qualquer LLM.
Só LEEM o banco. Alterações (índices, VACUUM, ANALYZE) são feitas pelo administrador na tela, com backup antes.
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

PASTA_RELATORIOS = os.path.join(RAIZ_PROJETO, "Agent Reports", "BancoDados")
PASTA_AO_VIVO = os.environ.get("BANCO_AO_VIVO", "")
SEVERIDADES = ["Crítica", "Alta", "Média", "Baixa", "Informativa"]
PESO = {"Crítica": 10, "Alta": 6, "Média": 3, "Baixa": 1, "Informativa": 0}
CATEGORIAS = {
    "DES": "Desempenho de consultas", "IDX": "Índices", "ESQ": "Esquema e modelagem", "INT": "Integridade dos dados",
    "BKP": "Backup e recuperação", "MAN": "Manutenção", "LOG": "Logs e auditoria", "CAP": "Capacidade e crescimento",
    "RET": "Retenção de dados (LGPD)", "POR": "Portabilidade entre bancos", "CFG": "Configuração do banco",
}
REF_SQLITE = "https://www.sqlite.org/docs.html"


def _gravar_atomico(caminho, conteudo):
    temporario = caminho + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as f:
            f.write(conteudo)
        os.replace(temporario, caminho)
    except OSError:
        pass


def tamanho_legivel(n):
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024


class AgenteBanco:
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
        self.aprendizados = []
        self.extras = {}  # dados estruturados do relatório (ex.: índices sugeridos)
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

    def achado(self, titulo, severidade, categoria, local, evidencia, recomendacao, referencias=None, script=None):
        """Registra um problema ou melhoria. 'script' = SQL sugerido (nunca é executado pelo agente)."""
        self.verificacoes += 1
        item = {"id": f"{self.chave.upper()[:3]}-{len(self.achados) + 1:03d}", "titulo": titulo, "severidade": severidade,
                "categoria": CATEGORIAS.get(categoria, categoria), "local": local, "evidencia": str(evidencia)[:1500],
                "recomendacao": recomendacao, "script": script or "", "referencias": list(referencias or []),
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
        print(f"\n🗄️ {self.nome} — {self.especialidade}")
        for i, passo in enumerate(self.ROTEIRO, 1):
            print(f"   {i:>2}. {passo}")
        self.carregar_aprendizados()
        try:
            self.rodar()
        except Exception as e:
            self.achado(f"O agente parou por erro interno: {e.__class__.__name__}", "Informativa", "LOG", self.etapa_atual or "-",
                        str(e), "Conferir o log do agente e rodar de novo.")
        return self.gerar_relatorio()

    def nota_de_risco(self):
        """0 (banco saudável) a 100 (risco máximo). A tela mostra a SAÚDE = 100 − risco."""
        return min(100, sum(PESO[a["severidade"]] for a in self.achados) * 2)

    # ------------------------------------------------------------------ aprendizados
    def carregar_aprendizados(self):
        """Recebe do Gerente de Banco de Dados os aprendizados APLICADOS para este agente e registra o consumo."""
        from types import SimpleNamespace
        try:
            from app import app
            import conhecimento_banco as cb
            with app.app_context():
                itens = cb.para_agente(self.chave)
                cb.consumir(self.chave, itens)
                self.aprendizados = [SimpleNamespace(codigo=a.codigo, tipo=a.tipo, titulo=a.titulo, conteudo=a.conteudo,
                                                     fonte_url=a.fonte_url) for a in itens]
        except Exception as e:
            self.log(f"Aprendizados indisponíveis: {e}")
            self.aprendizados = []
        if self.aprendizados:
            tipos = {}
            for a in self.aprendizados:
                tipos[a.tipo] = tipos.get(a.tipo, 0) + 1
            self.log(f"📚 {len(self.aprendizados)} aprendizado(s) do Gerente de Banco de Dados: "
                     + ", ".join(f"{t} ×{n}" for t, n in sorted(tipos.items())))
        else:
            self.log("📚 Nenhum aprendizado recebido do Gerente de Banco de Dados")

    def aprendizados_do_tipo(self, *tipos):
        return [a for a in self.aprendizados if a.tipo in tipos]

    def referencias_aprovadas(self):
        refs = []
        for a in self.aprendizados_do_tipo("referencia_externa"):
            dados = json.loads(a.conteudo)
            refs.append({"titulo": dados.get("tema") or a.titulo, "url": a.fonte_url, "resumo": dados.get("resumo", "")[:280]})
        return refs[-8:]

    # ------------------------------------------------------------------ saída
    def gerar_prompt(self, caminho):
        ordenados = sorted(self.achados, key=lambda a: SEVERIDADES.index(a["severidade"]))
        relevantes = [a for a in ordenados if a["severidade"] != "Informativa"]
        linhas = [f"# 🗄️ Prompt de Melhoria do Banco de Dados para LLM — {self.nome}\n",
                  f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelos Agentes de Banco de Dados. Cole no assistente de IA da sua "
                  "preferência (ChatGPT, Claude, Gemini, Copilot ou outro), anexando os arquivos citados.\n", "---\n"]
        if not relevantes:
            linhas.append(f"✅ O {self.nome} não encontrou problemas relevantes ({self.verificacoes} verificações).")
        else:
            linhas += [
                "Você é um DBA e engenheiro de dados sênior, especialista em SQLite, PostgreSQL, MySQL, SQL Server e MongoDB, "
                "e em Python com Flask-SQLAlchemy (SQLAlchemy 2.x), implantado no PythonAnywhere.",
                f"Uma análise automática ({self.especialidade}) desta plataforma de mentoria encontrou os {len(relevantes)} pontos abaixo.\n",
                "Para CADA item:",
                "1. Explique o impacto (desempenho, integridade ou risco de perda de dados) em até 3 frases.",
                "2. Entregue a melhoria pronta: código Python ANTES → DEPOIS e/ou o script SQL, idempotente e seguro para produção.",
                "3. Para mudanças de esquema, inclua a migração (ALTER/CREATE INDEX) e o plano de volta (rollback); faça backup antes.",
                "4. Meça o ganho: diga como comparar antes/depois (EXPLAIN QUERY PLAN, tempo da página, número de consultas).",
                "5. Textos novos de interface vão para traducoes_literais.py (pt, en, es) e são usados com tt('texto').\n",
            ]
            refs = self.referencias_aprovadas()
            if refs:
                linhas.append("**Referências oficiais aprovadas na Governança de aprendizados (ensinadas pelo Gerente de Banco de Dados):**\n")
                linhas += [f"- [{r['titulo']}]({r['url']}) — {r['resumo']}" for r in refs]
                linhas.append("")
            linhas.append("## Pontos de melhoria (do mais grave para o menos grave)\n")
            for i, a in enumerate(relevantes, 1):
                linhas += [f"### {i}. [{a['severidade']}] {a['titulo']}",
                           f"- **Categoria:** {a['categoria']}", f"- **Onde:** `{a['local']}`",
                           f"- **Evidência:** {a['evidencia']}", f"- **Recomendação:** {a['recomendacao']}"]
                if a["script"]:
                    linhas += ["- **Script sugerido:**", "```sql", a["script"], "```"]
                linhas += [f"- **Referências:** {', '.join(a['referencias']) or REF_SQLITE}", ""]
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    def gerar_relatorio(self):
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        base = os.path.join(PASTA_RELATORIOS, f"Banco_{self.chave}_{self.carimbo}")
        self.gerar_prompt(base + "_prompt.md")
        dados = {"chave": self.chave, "nome": self.nome, "especialidade": self.especialidade, "roteiro": self.ROTEIRO,
                 "verificacoes": self.verificacoes, "contagem": self.contagem(), "nota_risco": self.nota_de_risco(),
                 "aprendizados": [{"codigo": a.codigo, "tipo": a.tipo, "titulo": a.titulo} for a in self.aprendizados],
                 "achados": sorted(self.achados, key=lambda a: SEVERIDADES.index(a["severidade"])), "extras": self.extras,
                 "duracao_seg": int(time.time() - self.inicio), "carimbo": self.carimbo, "prompt": base + "_prompt.md"}
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        c = self.contagem()
        print(f"\n✅ {self.nome}: {self.verificacoes} verificações · Crítica {c['Crítica']} · Alta {c['Alta']} · Média {c['Média']} "
              f"· Baixa {c['Baixa']} · Info {c['Informativa']} · saúde {100 - self.nota_de_risco()}/100")
        return dados
