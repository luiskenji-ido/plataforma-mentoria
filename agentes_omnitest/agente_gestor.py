"""
AGENTE GESTOR — HUB CENTRAL DOS AGENTES DE IA (área Administração › Agentes IA)
==============================================================================
Coordena os agentes de teste fim a fim, um de cada vez, começando pelo Administrador:
  1. prepara os utilizadores de teste e a massa de dados [OmniTest];
  2. dispara cada agente com a transmissão ao vivo ligada (a página Agentes IA mostra o navegador no centro);
  3. ao fim de cada agente, gera o PDF com as evidências e guarda o prompt de correção:

  Agent Reports/Agentes IA/
    Agentes Teste Fim a Fim/
      Relatórios de Testes Fim a Fim e Evidencias/Perfil <nome>/Relatorio_E2E_<perfil>_<data>.pdf
      Prompt de correção LLM/Perfil <nome>/Prompt_correcao_LLM_<perfil>_<data>.md   (serve para qualquer LLM)
    Agentes Teste de Segurança/
      (criadas e mantidas pelo agentes_seguranca/gestor_seguranca.py, uma subpasta por agente de segurança)
As pastas dos testes fim a fim já nascem com uma subpasta para cada agente de perfil.

Uso (normalmente a própria página dispara):
    python agentes_omnitest/agente_gestor.py [--perfis administrador aluno ...] [--escrita] [--lento 150]
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

from nucleo import PERFIS, PASTA_RELATORIOS, RAIZ_PROJETO, preparar_usuario, APROVADO, FALHA, ALERTA, PULADO

PASTA_AGENTES = os.path.dirname(os.path.abspath(__file__))
ORDEM = ["administrador", "aluno", "professor", "mentor", "mentor_administrador", "gestor_b2b", "avaliador", "perfis_personalizados"]
NOMES_PASTA = {"administrador": "Perfil administrador", "aluno": "Perfil aluno", "professor": "Perfil professor", "mentor": "Perfil mentor",
               "mentor_administrador": "Perfil mentor administrador", "gestor_b2b": "Perfil gestor B2B", "avaliador": "Perfil avaliador banca",
               "perfis_personalizados": "Perfis personalizados"}
# Nome exibido de cada agente (os perfis personalizados não estão em nucleo.PERFIS)
NOMES_AGENTE = {**{c: d["tipo"] for c, d in PERFIS.items()}, "perfis_personalizados": "Perfis personalizados"}

BASE_IA = os.path.join(RAIZ_PROJETO, "Agent Reports", "Agentes IA")
PASTA_E2E = os.path.join(BASE_IA, "Agentes Teste Fim a Fim")
PASTA_REL_E2E = os.path.join(PASTA_E2E, "Relatórios de Testes Fim a Fim e Evidencias")
PASTA_PROMPT_E2E = os.path.join(PASTA_E2E, "Prompt de correção LLM")
PASTA_SEGURANCA = os.path.join(BASE_IA, "Agentes Teste de Segurança")
PASTA_AO_VIVO = os.path.join(BASE_IA, ".ao_vivo")
ARQUIVO_ESTADO = os.path.join(PASTA_AO_VIVO, "estado.json")
ARQUIVO_HISTORICO = os.path.join(BASE_IA, ".historico_duracoes.json")
# Estimativa inicial (duração em segundos e número de verificações), medida numa execução completa;
# a cada execução o Gestor ajusta com a média entre o valor anterior e o novo.
ESTIMATIVA_PADRAO = {"administrador": (303, 64), "aluno": (172, 74), "professor": (178, 62), "mentor": (182, 62),
                     "mentor_administrador": (275, 63), "gestor_b2b": (236, 59), "avaliador": (131, 57),
                     "perfis_personalizados": (240, 60)}


def criar_estrutura():
    """Pastas da área com uma subpasta por agente de perfil (as de Segurança são do gestor_seguranca.py)."""
    for pasta in (PASTA_REL_E2E, PASTA_PROMPT_E2E):
        for nome in NOMES_PASTA.values():
            os.makedirs(os.path.join(pasta, nome), exist_ok=True)
    os.makedirs(PASTA_AO_VIVO, exist_ok=True)


def ler_historico():
    historico = {c: {"duracao": d, "verificacoes": v} for c, (d, v) in ESTIMATIVA_PADRAO.items()}
    try:
        with open(ARQUIVO_HISTORICO, encoding="utf-8") as f:
            historico.update(json.load(f))
    except (OSError, ValueError):
        pass
    return historico


def atualizar_historico(chave, duracao, verificacoes):
    historico = ler_historico()
    anterior = historico.get(chave, {"duracao": duracao, "verificacoes": verificacoes})
    historico[chave] = {"duracao": round((anterior["duracao"] + duracao) / 2), "verificacoes": round((anterior["verificacoes"] + verificacoes) / 2)}
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=1)


class Estado:
    """estado.json lido pela página (fila, perfil atual, resultados, log e batimento do gestor)."""

    def __init__(self, perfis, escrita):
        self.trava = threading.Lock()
        historico = ler_historico()
        self.dados = {"status": "executando", "pid": os.getpid(), "inicio": datetime.now().isoformat(timespec="seconds"),
                      "fim": None, "escrita": escrita, "perfil_atual": None, "batimento": time.time(), "log": [],
                      "estimativas": {c: historico[c] for c in perfis if c in historico},
                      "perfis": {c: {"nome": NOMES_AGENTE[c], "status": "aguardando", "aprovados": 0, "falhas": 0,
                                     "alertas": 0, "pulados": 0, "pdf": None, "prompt": None, "duracao": None} for c in perfis}}
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
            self.dados["log"] = (self.dados["log"] + [f"{datetime.now().strftime('%H:%M:%S')}  {texto}"])[-40:]
        self.gravar()

    def perfil(self, chave, **campos):
        with self.trava:
            self.dados["perfis"][chave].update(campos)
        self.gravar()


def batimento(estado, parar):
    """Mostra à página que o gestor continua vivo (mesmo quando um agente fica muito tempo numa etapa)."""
    while not parar.is_set():
        estado.gravar()
        parar.wait(5)


# ------------------------------------------------------------------------------
# PDF com as evidências
# ------------------------------------------------------------------------------
def _uri(caminho):
    return "file:///" + os.path.abspath(caminho).replace("\\", "/") if caminho and os.path.exists(caminho) else ""


def html_relatorio(dados, duracao):
    c = dados["contagem"]
    cor = {APROVADO: "#15803d", FALHA: "#b91c1c", ALERTA: "#b45309", PULADO: "#475569"}
    linhas = "".join(
        f"<tr><td style='color:{cor.get(r['status'], '#334155')};font-weight:700;white-space:nowrap'>{escape(r['status'])}</td>"
        f"<td>{escape(r['modulo'])}</td><td>{escape(r['acao'])}</td><td>{escape(str(r.get('detalhe') or ''))[:300]}</td></tr>"
        for r in dados["resultados"])
    problemas = ""
    for i, r in enumerate([r for r in dados["resultados"] if r["status"] in (FALHA, ALERTA)], 1):
        detalhes = "".join(f"<li>{escape(d.replace('**', ''))}</li>" for d in r.get("detalhes", [])[:6])
        imagem = f"<img src='{_uri(r.get('evidencia'))}'>" if _uri(r.get("evidencia")) else ""
        problemas += (f"<section class='evidencia'><h3 style='color:{cor[r['status']]}'>{i}. {escape(r['status'])} — "
                      f"{escape(r['modulo'])} › {escape(r['acao'])}</h3><ul>{detalhes}</ul>{imagem}</section>")
    capturas = "".join(
        f"<figure class='evidencia'><img src='{_uri(cap['arquivo'])}'><figcaption>{n}. {escape(cap['modulo'])} › {escape(cap['acao'])}</figcaption></figure>"
        for n, cap in enumerate(dados.get("capturas", []), 1) if _uri(cap["arquivo"]))
    roteiro = "".join(f"<li>{escape(p)}</li>" for p in dados.get("roteiro", []))
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 14mm 12mm; }}
      body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; font-size: 10.5pt; }}
      h1 {{ font-size: 19pt; margin: 0 0 4px; color: #0b3d91; }} h2 {{ font-size: 13pt; color: #0b3d91; border-bottom: 2px solid #dbeafe; padding-bottom: 3px; margin-top: 22px; }}
      h3 {{ font-size: 11pt; margin: 0 0 6px; }}
      .meta {{ color: #475569; margin-bottom: 12px; }} .cards {{ display: flex; gap: 8px; margin: 10px 0 4px; }}
      .card {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; text-align: center; }}
      .card b {{ display: block; font-size: 18pt; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 8.8pt; }} th, td {{ border-bottom: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; }}
      th {{ background: #0f172a; color: #fff; }} .evidencia {{ page-break-inside: avoid; margin: 0 0 14px; }}
      .evidencia img {{ width: 100%; border: 1px solid #cbd5e1; border-radius: 4px; }} figcaption {{ color: #475569; font-size: 9pt; margin-top: 3px; }}
      ul {{ margin: 0 0 6px 16px; padding: 0; }}
    </style></head><body>
      <h1>Relatório de Teste Fim a Fim — {escape(dados['perfil'])}</h1>
      <div class="meta">Agente {escape(dados['chave'])} · {escape(dados.get('email', ''))} · Ambiente {escape(dados.get('ambiente', ''))}<br>
        Executado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} · Duração {duracao} · Modo escrita: {'ligado' if dados.get('escrita') else 'desligado'}</div>
      <div class="cards">
        <div class="card" style="color:{cor[APROVADO]}"><b>{c[APROVADO]}</b>Aprovados</div>
        <div class="card" style="color:{cor[FALHA]}"><b>{c[FALHA]}</b>Falhas</div>
        <div class="card" style="color:{cor[ALERTA]}"><b>{c[ALERTA]}</b>Alertas</div>
        <div class="card" style="color:{cor[PULADO]}"><b>{c[PULADO]}</b>Pulados</div>
      </div>
      <h2>Roteiro do agente</h2><ol>{roteiro}</ol>
      <h2>Checklist de homologação</h2><table><tr><th>Status</th><th>Módulo</th><th>Ação</th><th>Observação</th></tr>{linhas}</table>
      <h2>Falhas e alertas com evidência</h2>{problemas or '<p>Nenhuma falha ou alerta nesta execução.</p>'}
      <h2>Evidências de cada etapa</h2>{capturas or '<p>Sem capturas de etapa.</p>'}
    </body></html>"""


def gerar_pdf(dados, destino, duracao):
    from playwright.sync_api import sync_playwright
    pasta = os.path.dirname(dados["capturas"][0]["arquivo"]) if dados.get("capturas") else PASTA_AO_VIVO
    os.makedirs(pasta, exist_ok=True)
    html = os.path.join(pasta, "relatorio_pdf.html")
    with open(html, "w", encoding="utf-8") as f:
        f.write(html_relatorio(dados, duracao))
    with sync_playwright() as p:
        from navegador import abrir_chromium
        navegador = abrir_chromium(p)
        pagina = navegador.new_page()
        pagina.goto("file:///" + os.path.abspath(html).replace("\\", "/"), wait_until="load")
        pagina.pdf(path=destino, format="A4", print_background=True,
                   display_header_footer=True, header_template="<span></span>",
                   footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#64748b'>"
                                   "Mentoria · Agentes IA · página <span class='pageNumber'></span> de <span class='totalPages'></span></div>",
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        navegador.close()


# ------------------------------------------------------------------------------
# Execução
# ------------------------------------------------------------------------------
def rodar_agente(chave, estado, escrita, lento, url):
    inicio = time.time()
    estado.perfil(chave, status="executando", inicio=datetime.now().isoformat(timespec="seconds"))
    with estado.trava:
        estado.dados["perfil_atual"] = chave
    estado.log(f"▶ Agente {NOMES_AGENTE[chave]} iniciado")
    for arquivo in ("frame.jpg", "agente.json"):
        try:
            os.remove(os.path.join(PASTA_AO_VIVO, arquivo))
        except OSError:
            pass
    cmd = [sys.executable, os.path.join(PASTA_AGENTES, f"agente_{chave}.py"), "--sem-preparo", "--headless", "--lento", str(lento)]
    if escrita:
        cmd.append("--escrita")
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "OMNITEST_AO_VIVO": PASTA_AO_VIVO, "OMNITEST_URL": url}
    marco = time.time()
    proc = subprocess.Popen(cmd, cwd=RAIZ_PROJETO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ambiente,
                            text=True, encoding="utf-8", errors="replace")
    for linha in proc.stdout:
        linha = linha.rstrip()
        if linha.startswith(("🔎", "   ✅", "   ❌", "   ⚠️", "   ⏭️")):
            estado.log(f"[{NOMES_AGENTE[chave]}] {linha.strip()}")
    proc.wait()

    duracao = f"{int(time.time() - inicio) // 60} min {int(time.time() - inicio) % 60:02d} s"
    relatorios = [j for j in glob.glob(os.path.join(PASTA_RELATORIOS, f"Relatorio_OmniTest_{chave}_*.json")) if os.path.getmtime(j) >= marco]
    if not relatorios:
        estado.perfil(chave, status="erro", duracao=duracao, segundos=int(time.time() - inicio), fim=datetime.now().isoformat(timespec="seconds"))
        estado.log(f"✖ Agente {NOMES_AGENTE[chave]} terminou sem relatório (código {proc.returncode})")
        return
    with open(max(relatorios, key=os.path.getmtime), encoding="utf-8") as f:
        dados = json.load(f)
    c = dados["contagem"]
    data = datetime.now().strftime("%Y%m%d_%H%M")
    pasta_pdf = os.path.join(PASTA_REL_E2E, NOMES_PASTA[chave])
    pasta_prompt = os.path.join(PASTA_PROMPT_E2E, NOMES_PASTA[chave])
    os.makedirs(pasta_pdf, exist_ok=True)
    os.makedirs(pasta_prompt, exist_ok=True)
    destino_pdf = os.path.join(pasta_pdf, f"Relatorio_E2E_{chave}_{data}.pdf")
    estado.log(f"📄 Gerando o PDF de {NOMES_AGENTE[chave]}…")
    try:
        gerar_pdf(dados, destino_pdf, duracao)
        pdf_relativo = os.path.relpath(destino_pdf, BASE_IA)
    except Exception as e:
        pdf_relativo = None
        estado.log(f"✖ PDF não gerado: {e}")
    prompt_relativo = None
    origem_prompt = dados.get("prompt_llm") or dados.get("prompt_gemini")
    if origem_prompt and os.path.exists(origem_prompt):
        destino_prompt = os.path.join(pasta_prompt, f"Prompt_correcao_LLM_{chave}_{data}.md")
        shutil.copyfile(origem_prompt, destino_prompt)
        prompt_relativo = os.path.relpath(destino_prompt, BASE_IA)
    segundos = int(time.time() - inicio)
    atualizar_historico(chave, segundos, sum(c.values()))
    estado.perfil(chave, status="falhas" if c[FALHA] else "concluido", aprovados=c[APROVADO], falhas=c[FALHA],
                  alertas=c[ALERTA], pulados=c[PULADO], pdf=pdf_relativo, prompt=prompt_relativo, duracao=duracao,
                  segundos=segundos, fim=datetime.now().isoformat(timespec="seconds"))
    estado.log(f"{'✔' if not c[FALHA] else '✖'} {NOMES_AGENTE[chave]}: {c[APROVADO]} aprovados, {c[FALHA]} falhas, {c[ALERTA]} alertas")


def main():
    parser = argparse.ArgumentParser(description="Agente Gestor: hub central dos agentes de teste fim a fim.")
    parser.add_argument("--perfis", nargs="+", choices=ORDEM, default=ORDEM)
    parser.add_argument("--escrita", action="store_true")
    parser.add_argument("--lento", type=int, default=150, help="Pausa entre ações (ms), para dar para acompanhar ao vivo.")
    parser.add_argument("--url", default=os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000"))
    args = parser.parse_args()
    perfis = [c for c in ORDEM if c in args.perfis]   # sempre na ordem oficial, começando pelo Administrador

    criar_estrutura()
    estado = Estado(perfis, args.escrita)
    parar = threading.Event()
    threading.Thread(target=batimento, args=(estado, parar), daemon=True).start()
    try:
        # Agente Gerente Técnico: antes de testar, aprende o que mudou na plataforma (perfis, rotas)
        try:
            from app import app as aplicacao
            import conhecimento
            with aplicacao.app_context():
                novos = conhecimento.detectar_mudancas('Agente Gerente Técnico (início dos testes)')
                estado.log(f"🧠 Gerente Técnico: {len(novos)} aprendizado(s) novo(s)" + (f" ({', '.join(a.codigo for a in novos)})" if novos else ""))
        except Exception as e:
            estado.log(f"⚠ Aprendizado não executado: {e}")
        estado.log("🧭 Agente Gestor: preparando utilizadores de teste e massa de dados")
        for chave in perfis:
            if chave in PERFIS:
                preparar_usuario(chave)
        try:
            from massa_dados import garantir_massa
            estado.log(f"🌱 Massa de dados: {garantir_massa()}")
        except Exception as e:
            estado.log(f"⚠ Massa de dados não preparada: {e}")
        for chave in perfis:
            rodar_agente(chave, estado, args.escrita, args.lento, args.url.rstrip("/"))
        with estado.trava:
            estado.dados.update(status="concluido", perfil_atual=None, fim=datetime.now().isoformat(timespec="seconds"))
        estado.log("🏁 Testes fim a fim concluídos")
    except Exception as e:
        with estado.trava:
            estado.dados.update(status="erro", fim=datetime.now().isoformat(timespec="seconds"))
        estado.log(f"✖ Agente Gestor interrompido: {e}")
    finally:
        parar.set()
        estado.gravar()


if __name__ == "__main__":
    main()
