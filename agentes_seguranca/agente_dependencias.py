# -*- coding: utf-8 -*-
"""
AGENTE DE SEGURANÇA — DEPENDÊNCIAS E TECNOLOGIAS (SCA)
Uso: python agentes_seguranca/agente_dependencias.py
Inventário das tecnologias da plataforma (pacotes Python instalados, bibliotecas de navegador via CDN, versão do Python)
e consulta de vulnerabilidades conhecidas na base oficial OSV.dev (https://osv.dev, mantida pelo Google/OpenSSF).
Só consulta a OSV se o domínio estiver na lista de Fontes confiáveis (Administração › Governança de aprendizados).
"""
import os
import re
import sys
import json
from urllib.request import Request, urlopen
from importlib import metadata

from base import AgenteSeguranca, RAIZ_PROJETO

OSV_LOTE = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
# Fim do suporte de segurança das versões do Python (python.org/downloads, "Status of Python versions")
EOL_PYTHON = {(3, 8): "2024-10", (3, 9): "2025-10", (3, 10): "2026-10", (3, 11): "2027-10", (3, 12): "2028-10", (3, 13): "2029-10", (3, 14): "2030-10"}
DESCONTINUADOS = {"google-generativeai": ("O SDK google-generativeai foi descontinuado pelo Google (sem correções, nem de segurança).",
                                          "Migrar o chat do Acompanhamento para o SDK oficial atual google-genai.",
                                          "https://github.com/google-gemini/deprecated-generative-ai-python")}
CDN = [(r"cdn\.jsdelivr\.net/npm/(@?[\w.\-]+(?:/[\w.\-]+)?)@([\d.]+)", "npm"), (r"cdnjs\.cloudflare\.com/ajax/libs/([\w.\-]+)/([\d.]+)/", "npm"),
       (r"unpkg\.com/(@?[\w.\-]+)@([\d.]+)", "npm")]
NOME_NPM = {"intro.js": "intro.js"}


def _versao(texto):
    try:
        from packaging.version import Version
        return Version(texto)
    except Exception:
        return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-+]", str(texto)))


def afeta(vuln, pacote, versao):
    """Confere se a versão instalada está mesmo numa faixa afetada (evita falso positivo de entradas sem 'fixed')."""
    atual = _versao(versao)
    for afetado in vuln.get("affected", []):
        if (afetado.get("package") or {}).get("name", "").lower() != pacote.lower():
            continue
        if versao in afetado.get("versions", []):
            return True
        for faixa in afetado.get("ranges", []):
            if faixa.get("type") not in ("ECOSYSTEM", "SEMVER"):
                continue
            inicio, fim = None, None
            for evento in faixa.get("events", []):
                if "introduced" in evento:
                    inicio, fim = evento["introduced"], None
                elif "fixed" in evento or "last_affected" in evento:
                    fim = evento.get("fixed") or evento.get("last_affected")
                    inclusivo = "last_affected" in evento
                    if (inicio in (None, "0") or atual >= _versao(inicio)) and (atual <= _versao(fim) if inclusivo else atual < _versao(fim)):
                        return True
                    inicio = None
            if inicio is not None and (inicio == "0" or atual >= _versao(inicio)) and fim is None:
                # faixa aberta sem correção publicada: só conta se a base também listar versões afetadas explícitas
                if not afetado.get("versions"):
                    return True
    return False


class AgenteDependencias(AgenteSeguranca):
    chave = "dependencias"
    nome = "Agente Dependências e Tecnologias (SCA)"
    especialidade = "vulnerabilidades conhecidas das tecnologias usadas (Python, Flask e bibliotecas do navegador)"
    ROTEIRO = ["Inventário: versão do Python, pacotes instalados e bibliotecas carregadas por CDN",
               "Fim do suporte do Python e pacotes descontinuados",
               "Integridade das bibliotecas de CDN (SRI)",
               "Vulnerabilidades conhecidas na base oficial OSV.dev (só se o domínio for fonte confiável)"]

    def rodar(self):
        self.reportados = set()
        self.inventario()
        self.python_e_descontinuados()
        self.integridade_cdn()
        self.osv()
        self.conhecimento_aprendido()

    def conhecimento_aprendido(self):
        """Aprendizado do Gerente de Segurança: componentes que mudaram e vulnerabilidades oficiais APROVADAS na Governança.
        As aprovadas valem mesmo sem acesso à internet (ex.: PythonAnywhere sem liberação para a OSV.dev)."""
        self.etapa("Conhecimento aprendido: componentes e vulnerabilidades aprovadas")
        for a in self.aprendizados_do_tipo("seg_dependencia"):
            mudancas = json.loads(a.conteudo)
            partes = []
            for tipo, m in mudancas.items():
                partes += [f"novo {p} {v}" for p, v in list(m.get("novos", {}).items())[:6]]
                partes += [f"{p} {v[0]}→{v[1]}" for p, v in list(m.get("atualizados", {}).items())[:6]]
                partes += [f"removido {p}" for p in m.get("removidos", [])[:4]]
            self.achado(f"Componentes que mudaram desde a auditoria anterior ({a.codigo})", "Informativa", "A06", "", "requirements.txt / templates",
                        "; ".join(partes)[:600] or a.titulo, "Conferir as notas de versão e as vulnerabilidades destes componentes (já incluídos na consulta).")
        aprovadas = self.aprendizados_do_tipo("seg_vulnerabilidade")
        afetadas = 0
        for a in aprovadas:
            v = json.loads(a.conteudo)
            chave = v["pacote"].lower()
            instalada = self.pacotes.get(chave) if v.get("ecossistema", "PyPI") == "PyPI" else dict((p.lower(), ver) for p, ver in self.cdn).get(chave)
            if not instalada or chave in self.reportados:
                continue
            corrigidas = [c for c in v.get("corrigida_em", []) if c]
            ainda = instalada == v["versao_afetada"] or (corrigidas and _versao(instalada) < min(_versao(c) for c in corrigidas))
            if ainda:
                afetadas += 1
                self.achado(f"{v['pacote']} {instalada}: {v['id']} (aprendida em {a.codigo})", v.get("severidade", "Média"), "A06", "CWE-1395",
                            f"requirements.txt: {v['pacote']}=={instalada}", f"{v['resumo']} {' '.join(v.get('aliases', []))}".strip(),
                            f"Atualizar {v['pacote']} para {', '.join(corrigidas) or 'uma versão corrigida'} e testar.", [v["url"]])
        if aprovadas and not afetadas:
            self.ok(f"{len(aprovadas)} vulnerabilidade(s) aprendida(s): nenhuma afeta as versões instaladas")
        elif not aprovadas:
            self.log("Nenhuma vulnerabilidade aprovada na Governança ainda")

    def inventario(self):
        self.etapa("Inventário de tecnologias")
        self.pacotes = {d.metadata["Name"].lower(): d.version for d in metadata.distributions() if d.metadata["Name"]}
        self.ok(f"Python {sys.version.split()[0]} · {len(self.pacotes)} pacote(s) Python instalado(s)")
        principais = ", ".join(f"{n} {self.pacotes[n]}" for n in ("flask", "werkzeug", "jinja2", "flask-login", "flask-sqlalchemy", "sqlalchemy",
                                                               "flask-bcrypt", "playwright", "google-generativeai") if n in self.pacotes)
        self.log(f"Principais: {principais}")
        self.cdn = {}
        self.sem_sri = []
        pasta = os.path.join(RAIZ_PROJETO, "templates")
        for nome in sorted(os.listdir(pasta)):
            if not nome.endswith(".html"):
                continue
            texto = open(os.path.join(pasta, nome), encoding="utf-8", errors="ignore").read()
            for tag in re.finditer(r"<(script|link)\b[^>]*(?:src|href)=\"(https://[^\"]+)\"[^>]*>", texto):
                url = tag.group(2)
                for padrao, ecossistema in CDN:
                    m = re.search(padrao, url)
                    if m:
                        pacote = NOME_NPM.get(m.group(1), m.group(1))
                        self.cdn[(pacote, m.group(2))] = ecossistema
                        if "integrity=" not in tag.group(0):
                            self.sem_sri.append(f"templates/{nome}: {pacote}@{m.group(2)}")
        self.ok("Bibliotecas de navegador: " + ", ".join(f"{p}@{v}" for p, v in sorted(self.cdn)))

    def python_e_descontinuados(self):
        self.etapa("Suporte do Python e pacotes descontinuados")
        versao = sys.version_info[:2]
        fim = EOL_PYTHON.get(versao)
        if fim and fim <= __import__("datetime").date.today().strftime("%Y-%m"):
            self.achado(f"Python {versao[0]}.{versao[1]} sem suporte de segurança desde {fim}", "Alta", "A06", "CWE-1104", "ambiente (.venv)",
                        f"Versão em uso: {sys.version.split()[0]}", "Atualizar o Python do ambiente e do PythonAnywhere para uma versão com suporte.",
                        ["https://devguide.python.org/versions/"])
        else:
            self.ok(f"Python {versao[0]}.{versao[1]} com suporte de segurança" + (f" até {fim}" if fim else ""))
        for pacote, (texto, recomendacao, ref) in DESCONTINUADOS.items():
            if pacote in self.pacotes:
                self.achado(f"Pacote descontinuado: {pacote} {self.pacotes[pacote]}", "Média", "A06", "CWE-1104", "requirements.txt / app.py",
                            texto, recomendacao, [ref])

    def integridade_cdn(self):
        self.etapa("Integridade das bibliotecas de CDN")
        if self.sem_sri:
            self.achado(f"{len(self.sem_sri)} biblioteca(s) de CDN sem verificação de integridade (SRI)", "Média", "A08", "CWE-829",
                        "; ".join(sorted(set(self.sem_sri))[:8]),
                        "Se o CDN for comprometido, o navegador executa o código alterado em todas as páginas da plataforma.",
                        "Adicionar integrity=\"sha384-…\" e crossorigin=\"anonymous\" nas tags <script>/<link> (valores publicados pelo jsDelivr/cdnjs).",
                        ["https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity"])
        else:
            self.ok("Todas as bibliotecas de CDN com SRI")

    def _fonte_confiavel(self):
        try:
            from app import app
            import conhecimento
            with app.app_context():
                return conhecimento.dominio_confiavel("https://api.osv.dev/v1/querybatch") is not None
        except Exception:
            return False

    def _post(self, url, corpo):
        pedido = Request(url, data=json.dumps(corpo).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "MentoriaAgenteSeguranca/1.0"})
        with urlopen(pedido, timeout=30) as resposta:
            return json.loads(resposta.read(5_000_000))

    def _get(self, url):
        with urlopen(Request(url, headers={"User-Agent": "MentoriaAgenteSeguranca/1.0"}), timeout=20) as resposta:
            return json.loads(resposta.read(2_000_000))

    def osv(self):
        self.etapa("Consulta de vulnerabilidades na base oficial OSV.dev")
        if not self._fonte_confiavel():
            self.achado("Consulta de vulnerabilidades não realizada", "Informativa", "A06", "", "Governança de aprendizados › Fontes confiáveis",
                        "O domínio osv.dev não está na lista de fontes confiáveis ativas.",
                        "Incluir 'osv.dev' nas Fontes confiáveis para o agente consultar a base oficial de vulnerabilidades.")
            return
        consultas = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in sorted(self.pacotes.items())]
        consultas += [{"package": {"name": p, "ecosystem": e}, "version": v} for (p, v), e in sorted(self.cdn.items())]
        try:
            respostas = []
            for i in range(0, len(consultas), 500):
                respostas += self._post(OSV_LOTE, {"queries": consultas[i:i + 500]}).get("results", [])
        except Exception as e:
            self.achado("Base OSV.dev indisponível", "Informativa", "A06", "", OSV_LOTE, str(e), "Rodar de novo com acesso à internet.")
            return
        self.ok(f"{len(consultas)} componente(s) consultado(s) na OSV.dev")
        vulneraveis = 0
        for consulta, resposta in zip(consultas, respostas):
            ids = [v["id"] for v in resposta.get("vulns", [])]
            if not ids:
                continue
            pacote, versao = consulta["package"]["name"], consulta["version"]
            detalhes = []
            pior = "Baixa"
            corrigida = set()
            confirmadas = []
            for vid in ids[:10]:
                try:
                    vuln = self._get(OSV_VULN + vid)
                except Exception:
                    continue
                if not afeta(vuln, pacote, versao):
                    self.log(f"{pacote} {versao}: {vid} descartada (versão fora da faixa afetada)")
                    continue
                confirmadas.append(vid)
                sev = str((vuln.get("database_specific") or {}).get("severity", "")).upper()
                nivel = {"CRITICAL": "Crítica", "HIGH": "Alta", "MODERATE": "Média", "MEDIUM": "Média", "LOW": "Baixa"}.get(sev, "Média")
                if ["Crítica", "Alta", "Média", "Baixa"].index(nivel) < ["Crítica", "Alta", "Média", "Baixa"].index(pior):
                    pior = nivel
                for afetado in vuln.get("affected", []):
                    for faixa in afetado.get("ranges", []):
                        corrigida.update(ev["fixed"] for ev in faixa.get("events", []) if "fixed" in ev)
                apelidos = [a for a in vuln.get("aliases", []) if a.startswith("CVE-")]
                detalhes.append(f"{vid}{' (' + apelidos[0] + ')' if apelidos else ''}: {vuln.get('summary', '')[:120]}")
            if not confirmadas:
                continue
            vulneraveis += 1
            self.reportados.add(pacote.lower())
            ids = confirmadas
            self.achado(f"{pacote} {versao} com {len(ids)} vulnerabilidade(s) conhecida(s)", pior, "A06", "CWE-1395",
                        f"{'requirements.txt' if consulta['package']['ecosystem'] == 'PyPI' else 'templates (CDN)'}: {pacote}=={versao}",
                        " | ".join(detalhes), f"Atualizar {pacote} para uma versão corrigida" + (f" (ex.: {', '.join(sorted(corrigida)[-3:])})" if corrigida else "") + " e testar.",
                        [f"https://osv.dev/vulnerability/{ids[0]}"])
        if not vulneraveis:
            self.ok("Nenhuma vulnerabilidade conhecida nos componentes consultados")


if __name__ == "__main__":
    AgenteDependencias().executar()
