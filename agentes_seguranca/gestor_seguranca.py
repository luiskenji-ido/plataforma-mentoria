# -*- coding: utf-8 -*-
"""
GERENTE DE SEGURANÇA — HUB DOS AGENTES DE SEGURANÇA (Administração › Agentes de Segurança)
=====================================================================================
Roda os especialistas em sequência, transmite o andamento ao vivo, gera um PDF por agente e um consolidado,
e guarda os prompts de correção para LLM:

  Agent Reports/Agentes IA/Agentes Teste de Segurança/
    Relatórios de Testes de Segurança/<Agente>/Relatorio_Seguranca_<agente>_<data>.pdf
    Relatórios de Testes de Segurança/Consolidado/Relatorio_Seguranca_consolidado_<data>.pdf
    Prompt de correção LLM/<Agente>/Prompt_seguranca_<agente>_<data>.md

Uso: python agentes_seguranca/gestor_seguranca.py [--agentes configuracao dados codigo dependencias pentest] [--url http://127.0.0.1:5000]
"""
import os
import sys
import json
import glob
import time
import shutil
import argparse
import threading
import subprocess
from html import escape
from datetime import datetime

from base import RAIZ_PROJETO, PASTA_RELATORIOS, SEVERIDADES, PESO

PASTA = os.path.dirname(os.path.abspath(__file__))
ORDEM = ["configuracao", "dados", "codigo", "dependencias", "pentest"]
NOMES = {"configuracao": "Agente Configuração e Segredos", "dados": "Agente Inconsistências de Dados", "codigo": "Agente Análise de Código (SAST)",
         "dependencias": "Agente Dependências e Tecnologias (SCA)", "pentest": "Agente Pentest (DAST)"}
PASTAS = {"configuracao": "Agente Configuração e Segredos", "dados": "Agente Inconsistências de Dados", "codigo": "Agente Análise de Código",
          "dependencias": "Agente Dependências e Tecnologias", "pentest": "Agente Pentest", "consolidado": "Consolidado"}
ESTIMATIVA = {"configuracao": 8, "dados": 12, "codigo": 10, "dependencias": 25, "pentest": 20}

BASE_IA = os.path.join(RAIZ_PROJETO, "Agent Reports", "Agentes IA")
PASTA_SEG = os.path.join(BASE_IA, "Agentes Teste de Segurança")
PASTA_REL = os.path.join(PASTA_SEG, "Relatórios de Testes de Segurança")
PASTA_PROMPT = os.path.join(PASTA_SEG, "Prompt de correção LLM")
PASTA_AO_VIVO = os.path.join(BASE_IA, ".ao_vivo_seguranca")
ARQUIVO_ESTADO = os.path.join(PASTA_AO_VIVO, "estado.json")
ARQUIVO_HISTORICO = os.path.join(BASE_IA, ".historico_seguranca.json")
COR = {"Crítica": "#7f1d1d", "Alta": "#dc2626", "Média": "#d97706", "Baixa": "#2563eb", "Informativa": "#64748b"}


def criar_estrutura():
    for pasta in (PASTA_REL, PASTA_PROMPT):
        for nome in PASTAS.values():
            os.makedirs(os.path.join(pasta, nome), exist_ok=True)
        # Subpastas antigas por perfil (vazias) dão lugar às pastas por agente de segurança
        for antiga in glob.glob(os.path.join(pasta, "Perfil *")):
            try:
                os.rmdir(antiga)
            except OSError:
                pass
    os.makedirs(PASTA_AO_VIVO, exist_ok=True)


def ler_historico():
    try:
        with open(ARQUIVO_HISTORICO, encoding="utf-8") as f:
            return {**ESTIMATIVA, **json.load(f)}
    except (OSError, ValueError):
        return dict(ESTIMATIVA)


class Estado:
    def __init__(self, agentes):
        self.trava = threading.Lock()
        historico = ler_historico()
        self.dados = {"status": "executando", "pid": os.getpid(), "inicio": datetime.now().isoformat(timespec="seconds"), "fim": None,
                      "atual": None, "batimento": time.time(), "log": [], "consolidado": None,
                      "estimativas": {c: historico.get(c, 15) for c in agentes},
                      "agentes": {c: {"nome": NOMES[c], "status": "aguardando", "verificacoes": 0, "contagem": {s: 0 for s in SEVERIDADES},
                                      "risco": 0, "pdf": None, "prompt": None, "duracao": None} for c in agentes}}
        self.gravar()

    def gravar(self):
        with self.trava:
            self.dados["batimento"] = time.time()
            temporario = ARQUIVO_ESTADO + ".tmp"
            with open(temporario, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, ensure_ascii=False)
            for _ in range(5):
                try:
                    os.replace(temporario, ARQUIVO_ESTADO)
                    break
                except PermissionError:
                    time.sleep(0.1)

    def log(self, texto):
        with self.trava:
            self.dados["log"] = (self.dados["log"] + [f"{datetime.now().strftime('%H:%M:%S')}  {texto}"])[-60:]
        self.gravar()

    def agente(self, chave, **campos):
        with self.trava:
            self.dados["agentes"][chave].update(campos)
        self.gravar()


def batimento(estado, parar):
    while not parar.is_set():
        estado.gravar()
        parar.wait(5)


# ------------------------------------------------------------------------------ PDF
def _cards(contagem, risco):
    cards = "".join(f"<div class='card' style='border-top:4px solid {COR[s]}'><b style='color:{COR[s]}'>{contagem.get(s, 0)}</b>{s}</div>" for s in SEVERIDADES)
    cor_risco = "#16a34a" if risco < 25 else "#d97706" if risco < 60 else "#dc2626"
    return f"<div class='cards'><div class='card risco' style='border-top:4px solid {cor_risco}'><b style='color:{cor_risco}'>{risco}/100</b>Risco</div>{cards}</div>"


def _achados_html(achados, agente_col=False):
    linhas = "".join(
        f"<tr><td><span class='sev' style='background:{COR[a['severidade']]}'>{escape(a['severidade'])}</span></td><td>{escape(a['id'])}</td>"
        + (f"<td>{escape(a.get('agente', ''))}</td>" if agente_col else "") +
        f"<td>{escape(a['titulo'])}</td><td>{escape(a['categoria'].split(' ')[0])} · {escape(a['cwe'] or '—')}</td></tr>" for a in achados)
    detalhes = "".join(
        f"<section class='achado'><h3><span class='sev' style='background:{COR[a['severidade']]}'>{escape(a['severidade'])}</span> {escape(a['id'])} — {escape(a['titulo'])}</h3>"
        f"<p><b>Categoria:</b> {escape(a['categoria'])} · <b>{escape(a['cwe'] or 'sem CWE')}</b></p>"
        f"<p><b>Onde:</b> <code>{escape(a['local'])}</code></p><p><b>Evidência:</b> {escape(a['evidencia'])}</p>"
        f"<p><b>Recomendação:</b> {escape(a['recomendacao'])}</p>"
        f"<p class='ref'><b>Referências:</b> {' · '.join(escape(r) for r in a.get('referencias', [])) or '—'}</p></section>"
        for a in achados if a["severidade"] != "Informativa") or "<p>Nenhuma vulnerabilidade relevante.</p>"
    cab = "<tr><th>Severidade</th><th>ID</th>" + ("<th>Agente</th>" if agente_col else "") + "<th>Achado</th><th>OWASP · CWE</th></tr>"
    return f"<table>{cab}{linhas}</table><h2>Detalhes e correções</h2>{detalhes}"


ESTILO = """<style>
  @page { size: A4; margin: 14mm 12mm; }
  body { font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; font-size: 10pt; }
  h1 { font-size: 19pt; margin: 0 0 4px; color: #7f1d1d; } h2 { font-size: 13pt; color: #7f1d1d; border-bottom: 2px solid #fecaca; padding-bottom: 3px; margin-top: 20px; }
  h3 { font-size: 10.5pt; margin: 0 0 4px; } .meta { color: #475569; margin-bottom: 10px; }
  .cards { display: flex; gap: 6px; margin: 10px 0; } .card { flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 7px; text-align: center; font-size: 8.5pt; }
  .card b { display: block; font-size: 16pt; } table { width: 100%; border-collapse: collapse; font-size: 8.6pt; }
  th, td { border-bottom: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; } th { background: #1f2937; color: #fff; }
  .sev { color: #fff; border-radius: 4px; padding: 1px 6px; font-size: 8pt; font-weight: 700; white-space: nowrap; }
  .achado { page-break-inside: avoid; border: 1px solid #e2e8f0; border-left: 4px solid #7f1d1d; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; }
  .achado p { margin: 3px 0; } code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 8.5pt; word-break: break-all; }
  .ref { color: #475569; font-size: 8.5pt; word-break: break-all; } ul { margin: 4px 0 4px 16px; padding: 0; }
</style>"""


def html_agente(dados, url):
    roteiro = "".join(f"<li>{escape(p)}</li>" for p in dados.get("roteiro", []))
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Relatório de Segurança — {escape(dados['nome'])}</h1>
      <div class="meta">{escape(dados['especialidade'])} · Alvo {escape(url)} · {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
        {dados['verificacoes']} verificações em {dados.get('duracao_seg', 0)} s</div>
      {_cards(dados['contagem'], dados['nota_risco'])}
      <h2>Roteiro</h2><ol>{roteiro}</ol>
      <h2>Achados</h2>{_achados_html(dados['achados'])}
    </body></html>"""


def html_consolidado(relatorios, url):
    todos = [{**a, "agente": r["nome"]} for r in relatorios for a in r["achados"]]
    todos.sort(key=lambda a: SEVERIDADES.index(a["severidade"]))
    contagem = {s: sum(1 for a in todos if a["severidade"] == s) for s in SEVERIDADES}
    risco = min(100, sum(PESO[a["severidade"]] for a in todos))
    por_owasp = {}
    for a in todos:
        if a["severidade"] != "Informativa":
            por_owasp[a["categoria"]] = por_owasp.get(a["categoria"], 0) + 1
    owasp = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in sorted(por_owasp.items(), key=lambda x: -x[1]))
    agentes = "".join(f"<tr><td>{escape(r['nome'])}</td><td>{r['verificacoes']}</td>" +
                      "".join(f"<td>{r['contagem'][s]}</td>" for s in SEVERIDADES) + f"<td>{r['nota_risco']}/100</td></tr>" for r in relatorios)
    prioridades = "".join(f"<li><b>[{escape(a['severidade'])}]</b> {escape(a['titulo'])} — <i>{escape(a['agente'])}</i></li>"
                          for a in todos if a["severidade"] in ("Crítica", "Alta"))[:6000] or "<li>Nenhum item crítico ou alto.</li>"
    html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Relatório Consolidado de Segurança</h1>
      <div class="meta">Plataforma Mentoria · Alvo {escape(url)} · {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(relatorios)} agente(s) especialista(s)</div>
      {_cards(contagem, risco)}
      <h2>Prioridades (corrigir primeiro)</h2><ul>{prioridades}</ul>
      <h2>Resultado por agente</h2><table><tr><th>Agente</th><th>Verificações</th>{''.join(f'<th>{s}</th>' for s in SEVERIDADES)}<th>Risco</th></tr>{agentes}</table>
      <h2>Por categoria OWASP Top 10 (2021)</h2><table><tr><th>Categoria</th><th>Achados</th></tr>{owasp}</table>
      <h2>Todos os achados</h2>{_achados_html(todos, agente_col=True)}
    </body></html>"""
    return html, contagem, risco, todos


def gerar_pdf(html, destino):
    from playwright.sync_api import sync_playwright
    temporario = os.path.join(PASTA_AO_VIVO, f"pdf_{os.getpid()}.html")
    with open(temporario, "w", encoding="utf-8") as f:
        f.write(html)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto("file:///" + os.path.abspath(temporario).replace("\\", "/"), wait_until="load")
        pagina.pdf(path=destino, format="A4", print_background=True, display_header_footer=True, header_template="<span></span>",
                   footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#64748b'>Mentoria · Agentes de Segurança · "
                                   "página <span class='pageNumber'></span> de <span class='totalPages'></span> · CONFIDENCIAL</div>",
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        navegador.close()
    os.remove(temporario)


def prompt_consolidado(todos, destino):
    relevantes = [a for a in todos if a["severidade"] != "Informativa"]
    linhas = ["# 🛡️ Prompt de Correção de Segurança para LLM — Consolidado\n",
              f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo Gerente de Segurança. Cole no assistente de IA da sua preferência.\n",
              "---\n",
              "Você é um engenheiro de segurança de aplicações sênior (AppSec) especialista em Python/Flask/Jinja2/SQLite/PythonAnywhere.",
              f"A auditoria completa (5 agentes especialistas) encontrou {len(relevantes)} problemas. Corrija na ordem de severidade; para cada um, "
              "explique o impacto, entregue o código ANTES → DEPOIS e diga como testar. Não quebre as permissões dos perfis.\n"]
    for i, a in enumerate(relevantes, 1):
        linhas += [f"### {i}. [{a['severidade']}] {a['titulo']} ({a['agente']})", f"- {a['categoria']} · {a['cwe'] or 'sem CWE'} · `{a['local']}`",
                   f"- Evidência: {a['evidencia']}", f"- Recomendação: {a['recomendacao']}", ""]
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# ------------------------------------------------------------------------------ execução
def rodar_agente(chave, estado, url):
    inicio = time.time()
    estado.agente(chave, status="executando", inicio=datetime.now().isoformat(timespec="seconds"))
    with estado.trava:
        estado.dados["atual"] = chave
    estado.log(f"▶ {NOMES[chave]} iniciado")
    try:
        os.remove(os.path.join(PASTA_AO_VIVO, "agente.json"))
    except OSError:
        pass
    marco = time.time()
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "SEGURANCA_AO_VIVO": PASTA_AO_VIVO, "OMNITEST_URL": url}
    proc = subprocess.Popen([sys.executable, os.path.join(PASTA, f"agente_{chave}.py")], cwd=RAIZ_PROJETO, env=ambiente,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for linha in proc.stdout:
        if "⚠ [" in linha or "▶" in linha:
            estado.log(f"[{NOMES[chave].replace('Agente ', '')}] {linha.strip()[10:] if linha[:2].isdigit() else linha.strip()}")
    proc.wait()
    segundos = int(time.time() - inicio)
    arquivos = [j for j in glob.glob(os.path.join(PASTA_RELATORIOS, f"Seguranca_{chave}_*.json")) if os.path.getmtime(j) >= marco]
    if not arquivos:
        estado.agente(chave, status="erro", duracao=f"{segundos} s")
        estado.log(f"✖ {NOMES[chave]} terminou sem relatório (código {proc.returncode})")
        return None
    with open(max(arquivos, key=os.path.getmtime), encoding="utf-8") as f:
        dados = json.load(f)
    data = datetime.now().strftime("%Y%m%d_%H%M")
    destino_pdf = os.path.join(PASTA_REL, PASTAS[chave], f"Relatorio_Seguranca_{chave}_{data}.pdf")
    destino_prompt = os.path.join(PASTA_PROMPT, PASTAS[chave], f"Prompt_seguranca_{chave}_{data}.md")
    try:
        gerar_pdf(html_agente(dados, url), destino_pdf)
        pdf = os.path.relpath(destino_pdf, BASE_IA)
    except Exception as e:
        pdf = None
        estado.log(f"✖ PDF não gerado: {e}")
    shutil.copyfile(dados["prompt"], destino_prompt)
    c = dados["contagem"]
    graves = c["Crítica"] + c["Alta"]
    estado.agente(chave, status="vulneravel" if graves else "concluido", verificacoes=dados["verificacoes"], contagem=c,
                  risco=dados["nota_risco"], pdf=pdf, prompt=os.path.relpath(destino_prompt, BASE_IA), duracao=f"{segundos} s", segundos=segundos,
                  fim=datetime.now().isoformat(timespec="seconds"))
    estado.log(f"{'✖' if graves else '✔'} {NOMES[chave]}: {dados['verificacoes']} verificações · Crítica {c['Crítica']} · Alta {c['Alta']} · "
               f"Média {c['Média']} · Baixa {c['Baixa']}")
    historico = ler_historico()
    historico[chave] = round((historico.get(chave, segundos) + segundos) / 2)
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(historico, f)
    return dados


def main():
    parser = argparse.ArgumentParser(description="Gerente de Segurança: roda os agentes de segurança e gera os relatórios.")
    parser.add_argument("--agentes", nargs="+", choices=ORDEM, default=ORDEM)
    parser.add_argument("--url", default=os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000"))
    args = parser.parse_args()
    agentes = [c for c in ORDEM if c in args.agentes]
    criar_estrutura()
    estado = Estado(agentes)
    parar = threading.Event()
    threading.Thread(target=batimento, args=(estado, parar), daemon=True).start()
    try:
        estado.log("🛡️ Gerente de Segurança: iniciando a auditoria")
        relatorios = [r for r in (rodar_agente(c, estado, args.url.rstrip("/")) for c in agentes) if r]
        if relatorios:
            estado.log("📄 Gerando o relatório consolidado…")
            html, contagem, risco, todos = html_consolidado(relatorios, args.url)
            data = datetime.now().strftime("%Y%m%d_%H%M")
            destino = os.path.join(PASTA_REL, PASTAS["consolidado"], f"Relatorio_Seguranca_consolidado_{data}.pdf")
            destino_prompt = os.path.join(PASTA_PROMPT, PASTAS["consolidado"], f"Prompt_seguranca_consolidado_{data}.md")
            try:
                gerar_pdf(html, destino)
            except Exception as e:
                destino = None
                estado.log(f"✖ PDF consolidado não gerado: {e}")
            prompt_consolidado(todos, destino_prompt)
            with estado.trava:
                estado.dados["consolidado"] = {"pdf": destino and os.path.relpath(destino, BASE_IA), "prompt": os.path.relpath(destino_prompt, BASE_IA),
                                               "contagem": contagem, "risco": risco,
                                               "principais": [{"severidade": a["severidade"], "titulo": a["titulo"], "agente": a["agente"]}
                                                              for a in todos if a["severidade"] in ("Crítica", "Alta")][:10]}
        with estado.trava:
            estado.dados.update(status="concluido", atual=None, fim=datetime.now().isoformat(timespec="seconds"))
        estado.log("✔ Auditoria de segurança concluída")
    except Exception as e:
        with estado.trava:
            estado.dados.update(status="erro", fim=datetime.now().isoformat(timespec="seconds"))
        estado.log(f"✖ Gerente de Segurança interrompido: {e}")
    finally:
        parar.set()
        estado.gravar()


if __name__ == "__main__":
    main()
