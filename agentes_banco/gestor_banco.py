# -*- coding: utf-8 -*-
"""
GERENTE DE BANCO DE DADOS — HUB DOS AGENTES DE BANCO (Administração › Agentes de Banco de Dados)
==============================================================================================
Aprende as mudanças do banco (autônomo), roda os especialistas em sequência transmitindo o andamento ao vivo, gera um
PDF por agente e um consolidado, guarda os prompts de melhoria para LLM e propõe a documentação oficial dos problemas:

  Agent Reports/Agentes IA/Agentes Banco de Dados/
    Relatórios de Banco de Dados/<Agente>/Relatorio_Banco_<agente>_<data>.pdf
    Relatórios de Banco de Dados/Consolidado/Relatorio_Banco_consolidado_<data>.pdf
    Prompt de melhoria LLM/<Agente>/Prompt_banco_<agente>_<data>.md

Uso: python agentes_banco/gestor_banco.py [--agentes consultas esquema backup dba portabilidade]
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
ORDEM = ["consultas", "esquema", "backup", "dba", "portabilidade"]
NOMES = {"consultas": "Agente Consultas e Desempenho", "esquema": "Agente Esquema e Índices", "backup": "Agente Backup e Recuperação",
         "dba": "Agente DBA (Manutenção e Logs)", "portabilidade": "Agente Multi-banco"}
PASTAS = {"consultas": "Agente Consultas e Desempenho", "esquema": "Agente Esquema e Índices", "backup": "Agente Backup e Recuperação",
          "dba": "Agente DBA Manutenção e Logs", "portabilidade": "Agente Multi-banco", "consolidado": "Consolidado"}
ESTIMATIVA = {"consultas": 15, "esquema": 8, "backup": 6, "dba": 8, "portabilidade": 6}

BASE_IA = os.path.join(RAIZ_PROJETO, "Agent Reports", "Agentes IA")
PASTA_BANCO = os.path.join(BASE_IA, "Agentes Banco de Dados")
PASTA_REL = os.path.join(PASTA_BANCO, "Relatórios de Banco de Dados")
PASTA_PROMPT = os.path.join(PASTA_BANCO, "Prompt de melhoria LLM")
PASTA_AO_VIVO = os.path.join(BASE_IA, ".ao_vivo_banco")
ARQUIVO_ESTADO = os.path.join(PASTA_AO_VIVO, "estado.json")
ARQUIVO_HISTORICO = os.path.join(BASE_IA, ".historico_banco.json")
COR = {"Crítica": "#7f1d1d", "Alta": "#dc2626", "Média": "#d97706", "Baixa": "#2563eb", "Informativa": "#64748b"}


def criar_estrutura():
    for pasta in (PASTA_REL, PASTA_PROMPT):
        for nome in PASTAS.values():
            os.makedirs(os.path.join(pasta, nome), exist_ok=True)
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


def aprender(estado, relatorios=None):
    """Autonomia do Gerente de Banco de Dados. Antes: aprende motor, esquema, índices, agendamentos de backup e drivers
    (aplicados na hora) e guarda a foto diária de crescimento. Depois: propõe a documentação oficial de cada tipo de
    problema encontrado (pendente até a aprovação na Governança)."""
    try:
        if RAIZ_PROJETO not in sys.path:
            sys.path.insert(0, RAIZ_PROJETO)
        from app import app
        import conhecimento_banco as cb
        with app.app_context():
            if relatorios is None:
                novos = cb.detectar_mudancas("Gerente de Banco de Dados (início da análise)")
                estado.log(f"🧠 Gerente de Banco de Dados aprendeu {len(novos)} mudança(s) do banco"
                           + (": " + "; ".join(a.titulo for a in novos[:4]) if novos else ""))
                with estado.trava:
                    estado.dados["aprendizado"] = {"novos": len(novos), "codigos": [a.codigo for a in novos][:10]}
            else:
                refs = cb.aprender_com_achados(relatorios, "Gerente de Banco de Dados (fim da análise)")
                if refs:
                    estado.log(f"📖 {len(refs)} página(s) oficial(is) propostas para os agentes (aguardando aprovação)")
                with estado.trava:
                    estado.dados.setdefault("aprendizado", {})["referencias"] = len(refs)
        estado.gravar()
    except Exception as e:
        estado.log(f"🧠 Aprendizado indisponível: {e}")


def batimento(estado, parar):
    while not parar.is_set():
        estado.gravar()
        parar.wait(5)


# ------------------------------------------------------------------------------ PDF
def _cards(contagem, risco):
    saude = 100 - risco
    cards = "".join(f"<div class='card' style='border-top:4px solid {COR[s]}'><b style='color:{COR[s]}'>{contagem.get(s, 0)}</b>{s}</div>" for s in SEVERIDADES)
    cor = "#16a34a" if saude >= 75 else "#d97706" if saude >= 40 else "#dc2626"
    return f"<div class='cards'><div class='card' style='border-top:4px solid {cor}'><b style='color:{cor}'>{saude}/100</b>Saúde</div>{cards}</div>"


def _achados_html(achados, agente_col=False):
    linhas = "".join(
        f"<tr><td><span class='sev' style='background:{COR[a['severidade']]}'>{escape(a['severidade'])}</span></td><td>{escape(a['id'])}</td>"
        + (f"<td>{escape(a.get('agente', ''))}</td>" if agente_col else "") +
        f"<td>{escape(a['titulo'])}</td><td>{escape(a['categoria'])}</td></tr>" for a in achados)
    detalhes = "".join(
        f"<section class='achado'><h3><span class='sev' style='background:{COR[a['severidade']]}'>{escape(a['severidade'])}</span> {escape(a['id'])} — {escape(a['titulo'])}</h3>"
        f"<p><b>Categoria:</b> {escape(a['categoria'])}</p>"
        f"<p><b>Onde:</b> <code>{escape(a['local'])}</code></p><p><b>Evidência:</b> {escape(a['evidencia'])}</p>"
        f"<p><b>Recomendação:</b> {escape(a['recomendacao'])}</p>"
        + (f"<pre>{escape(a['script'])}</pre>" if a.get("script") else "") +
        f"<p class='ref'><b>Referências:</b> {' · '.join(escape(r) for r in a.get('referencias', [])) or '—'}</p></section>"
        for a in achados if a["severidade"] != "Informativa") or "<p>Nenhum problema relevante.</p>"
    informativos = "".join(f"<li><b>{escape(a['titulo'])}</b>: {escape(a['evidencia'][:400])}</li>" for a in achados if a["severidade"] == "Informativa")
    cab = "<tr><th>Severidade</th><th>ID</th>" + ("<th>Agente</th>" if agente_col else "") + "<th>Ponto</th><th>Categoria</th></tr>"
    return (f"<table>{cab}{linhas}</table><h2>Detalhes e melhorias</h2>{detalhes}"
            + (f"<h2>Informações para acompanhamento</h2><ul>{informativos}</ul>" if informativos else ""))


ESTILO = """<style>
  @page { size: A4; margin: 14mm 12mm; }
  body { font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; font-size: 10pt; }
  h1 { font-size: 19pt; margin: 0 0 4px; color: #0e7490; } h2 { font-size: 13pt; color: #0e7490; border-bottom: 2px solid #a5f3fc; padding-bottom: 3px; margin-top: 20px; }
  h3 { font-size: 10.5pt; margin: 0 0 4px; } .meta { color: #475569; margin-bottom: 10px; }
  .cards { display: flex; gap: 6px; margin: 10px 0; } .card { flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 7px; text-align: center; font-size: 8.5pt; }
  .card b { display: block; font-size: 16pt; } table { width: 100%; border-collapse: collapse; font-size: 8.6pt; }
  th, td { border-bottom: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; } th { background: #164e63; color: #fff; }
  .sev { color: #fff; border-radius: 4px; padding: 1px 6px; font-size: 8pt; font-weight: 700; white-space: nowrap; }
  .achado { page-break-inside: avoid; border: 1px solid #e2e8f0; border-left: 4px solid #0e7490; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; }
  .achado p { margin: 3px 0; } code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 8.5pt; word-break: break-all; }
  pre { background: #0f172a; color: #e2e8f0; padding: 6px 8px; border-radius: 4px; font-size: 7.8pt; white-space: pre-wrap; word-break: break-all; }
  .ref { color: #475569; font-size: 8.5pt; word-break: break-all; } ul { margin: 4px 0 4px 16px; padding: 0; } li { margin-bottom: 3px; }
</style>"""


def html_agente(dados):
    roteiro = "".join(f"<li>{escape(p)}</li>" for p in dados.get("roteiro", []))
    aprendidos = dados.get("aprendizados", [])
    aprendizado = ("<ul>" + "".join(f"<li><b>{escape(a['codigo'])}</b> · {escape(a['tipo'])} — {escape(a['titulo'])}</li>" for a in aprendidos[-15:])
                   + "</ul>") if aprendidos else "<p>Nenhum aprendizado recebido nesta análise.</p>"
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Relatório de Banco de Dados — {escape(dados['nome'])}</h1>
      <div class="meta">{escape(dados['especialidade'])} · {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
        {dados['verificacoes']} verificações em {dados.get('duracao_seg', 0)} s</div>
      {_cards(dados['contagem'], dados['nota_risco'])}
      <h2>Roteiro</h2><ol>{roteiro}</ol>
      <h2>Aprendizados aplicados ({len(aprendidos)}, ensinados pelo Gerente de Banco de Dados)</h2>{aprendizado}
      <h2>Pontos encontrados</h2>{_achados_html(dados['achados'])}
    </body></html>"""


def html_consolidado(relatorios):
    todos = [{**a, "agente": r["nome"]} for r in relatorios for a in r["achados"]]
    todos.sort(key=lambda a: SEVERIDADES.index(a["severidade"]))
    contagem = {s: sum(1 for a in todos if a["severidade"] == s) for s in SEVERIDADES}
    risco = min(100, sum(PESO[a["severidade"]] for a in todos))
    por_categoria = {}
    for a in todos:
        if a["severidade"] != "Informativa":
            por_categoria[a["categoria"]] = por_categoria.get(a["categoria"], 0) + 1
    categorias = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in sorted(por_categoria.items(), key=lambda x: -x[1]))
    agentes = "".join(f"<tr><td>{escape(r['nome'])}</td><td>{r['verificacoes']}</td>" +
                      "".join(f"<td>{r['contagem'][s]}</td>" for s in SEVERIDADES) + f"<td>{100 - r['nota_risco']}/100</td></tr>" for r in relatorios)
    prioridades = "".join(f"<li><b>[{escape(a['severidade'])}]</b> {escape(a['titulo'])} — <i>{escape(a['agente'])}</i></li>"
                          for a in todos if a["severidade"] in ("Crítica", "Alta", "Média")) or "<li>Nenhum item crítico, alto ou médio.</li>"
    html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Relatório Consolidado do Banco de Dados</h1>
      <div class="meta">Plataforma Mentoria · {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(relatorios)} agente(s) especialista(s)</div>
      {_cards(contagem, risco)}
      <h2>Prioridades</h2><ul>{prioridades}</ul>
      <h2>Resultado por agente</h2><table><tr><th>Agente</th><th>Verificações</th>{''.join(f'<th>{s}</th>' for s in SEVERIDADES)}<th>Saúde</th></tr>{agentes}</table>
      <h2>Por categoria</h2><table><tr><th>Categoria</th><th>Pontos</th></tr>{categorias}</table>
      <h2>Todos os pontos</h2>{_achados_html(todos, agente_col=True)}
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
                   footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#64748b'>Mentoria · Agentes de Banco de Dados · "
                                   "página <span class='pageNumber'></span> de <span class='totalPages'></span> · CONFIDENCIAL</div>",
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        navegador.close()
    os.remove(temporario)


def prompt_consolidado(todos, destino):
    relevantes = [a for a in todos if a["severidade"] != "Informativa"]
    linhas = ["# 🗄️ Prompt de Melhoria do Banco de Dados para LLM — Consolidado\n",
              f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo Gerente de Banco de Dados. Cole no assistente de IA da sua preferência.\n",
              "---\n",
              "Você é um DBA sênior especialista em SQLite, PostgreSQL, MySQL, SQL Server e MongoDB e em Flask-SQLAlchemy (PythonAnywhere).",
              f"A análise completa (5 agentes especialistas) encontrou {len(relevantes)} pontos. Trate na ordem de severidade; para cada um, "
              "explique o impacto, entregue o código ANTES → DEPOIS e/ou o script SQL (com backup antes e plano de volta) e diga como medir o ganho.\n"]
    for i, a in enumerate(relevantes, 1):
        linhas += [f"### {i}. [{a['severidade']}] {a['titulo']} ({a['agente']})", f"- {a['categoria']} · `{a['local']}`",
                   f"- Evidência: {a['evidencia']}", f"- Recomendação: {a['recomendacao']}"]
        if a.get("script"):
            linhas += ["```sql", a["script"], "```"]
        linhas.append("")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# ------------------------------------------------------------------------------ execução
def rodar_agente(chave, estado):
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
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "BANCO_AO_VIVO": PASTA_AO_VIVO}
    proc = subprocess.Popen([sys.executable, os.path.join(PASTA, f"agente_{chave}.py")], cwd=RAIZ_PROJETO, env=ambiente,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for linha in proc.stdout:
        if "⚠ [" in linha or "▶" in linha:
            estado.log(f"[{NOMES[chave].replace('Agente ', '')}] {linha.strip()[10:] if linha[:2].isdigit() else linha.strip()}")
    proc.wait()
    segundos = int(time.time() - inicio)
    arquivos = [j for j in glob.glob(os.path.join(PASTA_RELATORIOS, f"Banco_{chave}_*.json")) if os.path.getmtime(j) >= marco]
    if not arquivos:
        estado.agente(chave, status="erro", duracao=f"{segundos} s")
        estado.log(f"✖ {NOMES[chave]} terminou sem relatório (código {proc.returncode})")
        return None
    with open(max(arquivos, key=os.path.getmtime), encoding="utf-8") as f:
        dados = json.load(f)
    data = datetime.now().strftime("%Y%m%d_%H%M")
    destino_pdf = os.path.join(PASTA_REL, PASTAS[chave], f"Relatorio_Banco_{chave}_{data}.pdf")
    destino_prompt = os.path.join(PASTA_PROMPT, PASTAS[chave], f"Prompt_banco_{chave}_{data}.md")
    try:
        gerar_pdf(html_agente(dados), destino_pdf)
        pdf = os.path.relpath(destino_pdf, BASE_IA)
    except Exception as e:
        pdf = None
        estado.log(f"✖ PDF não gerado: {e}")
    shutil.copyfile(dados["prompt"], destino_prompt)
    c = dados["contagem"]
    graves = c["Crítica"] + c["Alta"]
    estado.agente(chave, status="atencao" if graves else "concluido", verificacoes=dados["verificacoes"], contagem=c,
                  risco=dados["nota_risco"], pdf=pdf, prompt=os.path.relpath(destino_prompt, BASE_IA), duracao=f"{segundos} s", segundos=segundos,
                  fim=datetime.now().isoformat(timespec="seconds"))
    estado.log(f"{'✖' if graves else '✔'} {NOMES[chave]}: {dados['verificacoes']} verificações · Crítica {c['Crítica']} · Alta {c['Alta']} · "
               f"Média {c['Média']} · Baixa {c['Baixa']} · saúde {100 - dados['nota_risco']}/100")
    historico = ler_historico()
    historico[chave] = round((historico.get(chave, segundos) + segundos) / 2)
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(historico, f)
    return dados


def main():
    parser = argparse.ArgumentParser(description="Gerente de Banco de Dados: roda os agentes de banco e gera os relatórios.")
    parser.add_argument("--agentes", nargs="+", choices=ORDEM, default=ORDEM)
    args = parser.parse_args()
    agentes = [c for c in ORDEM if c in args.agentes]
    criar_estrutura()
    estado = Estado(agentes)
    parar = threading.Event()
    threading.Thread(target=batimento, args=(estado, parar), daemon=True).start()
    try:
        estado.log("🗄️ Gerente de Banco de Dados: iniciando a análise")
        aprender(estado)
        relatorios = [r for r in (rodar_agente(c, estado) for c in agentes) if r]
        if relatorios:
            aprender(estado, relatorios)
            estado.log("📄 Gerando o relatório consolidado…")
            html, contagem, risco, todos = html_consolidado(relatorios)
            data = datetime.now().strftime("%Y%m%d_%H%M")
            destino = os.path.join(PASTA_REL, PASTAS["consolidado"], f"Relatorio_Banco_consolidado_{data}.pdf")
            destino_prompt = os.path.join(PASTA_PROMPT, PASTAS["consolidado"], f"Prompt_banco_consolidado_{data}.md")
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
                                                              for a in todos if a["severidade"] in ("Crítica", "Alta", "Média")][:12]}
        with estado.trava:
            estado.dados.update(status="concluido", atual=None, fim=datetime.now().isoformat(timespec="seconds"))
        estado.log("✔ Análise do banco de dados concluída")
    except Exception as e:
        with estado.trava:
            estado.dados.update(status="erro", fim=datetime.now().isoformat(timespec="seconds"))
        estado.log(f"✖ Gerente de Banco de Dados interrompido: {e}")
    finally:
        parar.set()
        estado.gravar()


if __name__ == "__main__":
    main()
