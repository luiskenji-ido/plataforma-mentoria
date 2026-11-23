# -*- coding: utf-8 -*-
"""
GERENTE DE FUNCIONALIDADES — HUB DOS AGENTES DE FUNCIONALIDADES (Administração › Agentes de Funcionalidades)
=========================================================================================================
Conduz a "corrida de revezamento" pelo fluxo da plataforma:
  1. backup do banco (pasta pre_funcionalidades) e limpeza de sobras de execuções anteriores;
  2. aprende as regras de negócio da plataforma (autônomo) — os agentes testam contra elas;
  3. chama os agentes em ordem (Administrador → Mentor Administrador → Gestor Parceiro → Professor → Mentor → Aluno →
     Avaliador → Encerramento), passando a cada um o que o anterior criou (contexto.json);
  4. gera um PDF por agente com os prints de cada etapa e um consolidado com a cobertura das funções da plataforma;
  5. propõe referências oficiais para as falhas (pendentes na Governança) e guarda os prompts de correção;
  6. remove todos os dados [Funcional] e confere que nada sobrou.

  Agent Reports/Agentes IA/Agentes Funcionalidades/
    Relatórios de Funcionalidades e Evidências/<Agente>/Relatorio_Funcional_<agente>_<data>.pdf
    Prompt de correção LLM/<Agente>/Prompt_funcional_<agente>_<data>.md

Uso: python agentes_funcionalidades/gestor_funcionalidades.py [--manter-dados] [--url http://127.0.0.1:5000]
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

from base import RAIZ_PROJETO, PASTA_RELATORIOS, APROVADO, FALHA, ALERTA, SEVERIDADES

PASTA = os.path.dirname(os.path.abspath(__file__))
ORDEM = ["dev", "ux", "administrador", "mentor_administrador", "gestor_parceiro", "professor", "mentor", "aluno", "avaliador", "encerramento"]
NOMES = {"dev": "Agente Dev", "ux": "Agente UX", "administrador": "Agente Administrador", "mentor_administrador": "Agente Mentor Administrador", "gestor_parceiro": "Agente Gestor Parceiro",
         "professor": "Agente Professor", "mentor": "Agente Mentor", "aluno": "Agente Aluno", "avaliador": "Agente Avaliador da Banca",
         "encerramento": "Agente Encerramento do Ciclo"}
PASTAS = {c: NOMES[c] for c in ORDEM} | {"consolidado": "Consolidado"}
ESTIMATIVA = {"dev": 10, "ux": 10, "administrador": 15, "mentor_administrador": 30, "gestor_parceiro": 15, "professor": 15, "mentor": 15, "aluno": 20,
              "avaliador": 15, "encerramento": 10}

BASE_IA = os.path.join(RAIZ_PROJETO, "Agent Reports", "Agentes IA")
PASTA_FUNC = os.path.join(BASE_IA, "Agentes Funcionalidades")
PASTA_REL = os.path.join(PASTA_FUNC, "Relatórios de Funcionalidades e Evidências")
PASTA_PROMPT = os.path.join(PASTA_FUNC, "Prompt de correção LLM")
PASTA_AO_VIVO = os.path.join(BASE_IA, ".ao_vivo_funcionalidades")
ARQUIVO_ESTADO = os.path.join(PASTA_AO_VIVO, "estado.json")
ARQUIVO_CONTEXTO = os.path.join(PASTA_AO_VIVO, "contexto.json")
ARQUIVO_HISTORICO = os.path.join(BASE_IA, ".historico_funcionalidades.json")
COR = {APROVADO: "#16a34a", FALHA: "#dc2626", ALERTA: "#d97706"}


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
                      "agentes": {c: {"nome": NOMES[c], "status": "aguardando", "verificacoes": 0,
                                      "contagem": {APROVADO: 0, FALHA: 0, ALERTA: 0}, "saude": None, "pdf": None, "prompt": None, "duracao": None}
                                  for c in agentes}}
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


def com_app(funcao):
    if RAIZ_PROJETO not in sys.path:
        sys.path.insert(0, RAIZ_PROJETO)
    from app import app
    with app.app_context():
        return funcao()


def preparar(estado):
    """Backup antes de tudo, limpeza de sobras e aprendizado das regras de negócio."""
    import limpeza

    def backup():
        import cliente_backup
        if cliente_backup.configurado():  # serviço privado de backup
            try:
                execucao = cliente_backup.pedir_backup("pre_funcionalidades: agentes de funcionalidades", pasta="pre_funcionalidades")
                return execucao["status"], execucao.get("arquivo"), execucao.get("detalhes")
            except cliente_backup.ErroServicoBackup as erro:
                return "Falha", None, str(erro)
        import backup_servico
        registro = backup_servico.fazer_backup("Imediato", "pre_funcionalidades")
        return registro.status, registro.arquivo, registro.detalhes
    situacao, arquivo, detalhes = com_app(backup)
    if situacao not in ("Concluído", "Sucesso"):
        raise RuntimeError(f"backup antes do teste falhou: {detalhes}")
    estado.log(f"💾 Backup antes do teste: {arquivo}")
    sobras = limpeza.limpar(lambda texto: None)
    if sobras["linhas"]:
        estado.log(f"🧹 Sobras de uma execução anterior removidas: {sobras['linhas']} linha(s)")

    def aprender():
        import conhecimento_funcional as cf
        return [a.titulo for a in cf.detectar_mudancas("Gerente de Funcionalidades (início do teste)")]
    try:
        novos = com_app(aprender)
        estado.log(f"🧠 Gerente de Funcionalidades aprendeu {len(novos)} mudança(s) nas regras de negócio"
                   + (": " + "; ".join(novos[:3]) if novos else ""))
        with estado.trava:
            estado.dados["aprendizado"] = {"novos": len(novos)}
    except Exception as e:
        estado.log(f"🧠 Aprendizado indisponível: {e}")


# ------------------------------------------------------------------------------ PDF
ESTILO = """<style>
  @page { size: A4; margin: 14mm 12mm; }
  body { font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; font-size: 10pt; }
  h1 { font-size: 19pt; margin: 0 0 4px; color: #6d28d9; } h2 { font-size: 13pt; color: #6d28d9; border-bottom: 2px solid #ddd6fe; padding-bottom: 3px; margin-top: 18px; }
  .meta { color: #475569; margin-bottom: 10px; } .cards { display: flex; gap: 6px; margin: 10px 0; }
  .card { flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 7px; text-align: center; font-size: 8.5pt; } .card b { display: block; font-size: 16pt; }
  table { width: 100%; border-collapse: collapse; font-size: 8.4pt; } th, td { border-bottom: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; }
  th { background: #4c1d95; color: #fff; } .res { color: #fff; border-radius: 4px; padding: 1px 6px; font-size: 8pt; font-weight: 700; white-space: nowrap; }
  .passo { page-break-inside: avoid; border: 1px solid #e2e8f0; border-left: 4px solid #6d28d9; border-radius: 6px; padding: 7px 9px; margin-bottom: 9px; }
  .passo p { margin: 2px 0; } .passo img { width: 100%; border: 1px solid #cbd5e1; border-radius: 4px; margin-top: 5px; }
  ul { margin: 4px 0 4px 16px; padding: 0; } code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 8.4pt; }
</style>"""


def _cards(contagem, saude):
    cor = "#16a34a" if saude >= 90 else "#d97706" if saude >= 70 else "#dc2626"
    return ("<div class='cards'>" + f"<div class='card' style='border-top:4px solid {cor}'><b style='color:{cor}'>{saude}/100</b>Saúde</div>"
            + "".join(f"<div class='card' style='border-top:4px solid {COR[r]}'><b style='color:{COR[r]}'>{contagem.get(r, 0)}</b>{r}</div>"
                      for r in (APROVADO, FALHA, ALERTA)) + "</div>")


def _img(relativo):
    if not relativo:
        return ""
    caminho = os.path.join(PASTA_RELATORIOS, relativo)
    return f"<img src='file:///{os.path.abspath(caminho).replace(os.sep, '/')}'>" if os.path.exists(caminho) else ""


def html_agente(dados):
    linhas = "".join(f"<tr><td><span class='res' style='background:{COR[t['resultado']]}'>{t['resultado']}</span></td><td>{escape(t['id'])}</td>"
                     f"<td>{escape(t['etapa'])}</td><td>{escape(t['titulo'])}</td><td>{escape(t['categoria'])}</td></tr>" for t in dados["testes"])
    passos = "".join(
        f"<section class='passo'><p><span class='res' style='background:{COR[t['resultado']]}'>{t['resultado']}</span> <b>{escape(t['id'])} — {escape(t['titulo'])}</b>"
        + (f" <i>({escape(t['severidade'])})</i>" if t["severidade"] else "") + "</p>"
        f"<p><b>Regra / esperado:</b> {escape(t['esperado'])}</p><p><b>Resultado:</b> {escape(t['detalhe'])}</p>"
        + (f"<p><b>Sugestão:</b> {escape(t['recomendacao'])}</p>" if t["resultado"] != APROVADO and t["recomendacao"] else "")
        + _img(t.get("evidencia")) + "</section>" for t in dados["testes"])
    roteiro = "".join(f"<li>{escape(p)}</li>" for p in dados.get("roteiro", []))
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Teste Funcional — {escape(dados['nome'])}</h1>
      <div class="meta">Perfil {escape(dados['perfil'])} · {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(dados['testes'])} testes em {dados.get('duracao_seg', 0)} s ·
        funções exercitadas: {escape(', '.join(dados.get('cobertura', [])) or '—')}</div>
      {_cards(dados['contagem'], dados['saude'])}
      <h2>Roteiro</h2><ol>{roteiro}</ol>
      <h2>Resultados</h2><table><tr><th>Resultado</th><th>ID</th><th>Etapa</th><th>Teste</th><th>Categoria</th></tr>{linhas}</table>
      <h2>Passo a passo com evidências</h2>{passos}
    </body></html>"""


def cobertura(relatorios):
    cobertas = set().union(*[set(r.get("cobertura", [])) for r in relatorios]) if relatorios else set()
    disponiveis = set().union(*[set(r.get("funcoes_do_perfil", [])) for r in relatorios]) if relatorios else set()
    return sorted(cobertas & disponiveis), sorted(disponiveis - cobertas)


def html_consolidado(relatorios, limpeza_resumo):
    todos = [{**t, "agente": r["nome"]} for r in relatorios for t in r["testes"]]
    contagem = {k: sum(1 for t in todos if t["resultado"] == k) for k in (APROVADO, FALHA, ALERTA)}
    total = sum(contagem.values())
    saude = round(100 * (contagem[APROVADO] + 0.5 * contagem[ALERTA]) / total) if total else 100
    cobertas, faltando = cobertura(relatorios)
    problemas = sorted([t for t in todos if t["resultado"] != APROVADO], key=lambda t: SEVERIDADES.index(t["severidade"]) if t["severidade"] in SEVERIDADES else 9)
    lista = "".join(f"<li><b>[{escape(t['resultado'])} · {escape(t['severidade'])}]</b> {escape(t['titulo'])} — <i>{escape(t['agente'])}</i><br>"
                    f"<small>{escape(t['detalhe'][:300])}</small></li>" for t in problemas) or "<li>Nenhuma falha nem alerta.</li>"
    agentes = "".join(f"<tr><td>{escape(r['nome'])}</td><td>{escape(r['perfil'])}</td><td>{len(r['testes'])}</td>"
                      + "".join(f"<td>{r['contagem'][k]}</td>" for k in (APROVADO, FALHA, ALERTA)) + f"<td>{r['saude']}/100</td></tr>" for r in relatorios)
    html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">{ESTILO}</head><body>
      <h1>Relatório Consolidado de Funcionalidades</h1>
      <div class="meta">Plataforma Mentoria · {datetime.now().strftime('%d/%m/%Y %H:%M')} · fluxo completo com {len(relatorios)} agente(s)</div>
      {_cards(contagem, saude)}
      <h2>Falhas e alertas (corrigir primeiro)</h2><ul>{lista}</ul>
      <h2>Resultado por agente (ordem do fluxo)</h2><table><tr><th>Agente</th><th>Perfil</th><th>Testes</th><th>Aprovados</th><th>Falhas</th><th>Alertas</th><th>Saúde</th></tr>{agentes}</table>
      <h2>Cobertura das funções da plataforma</h2>
      <p>{len(cobertas)} de {len(cobertas) + len(faltando)} funções que gravam dados foram exercitadas pelo fluxo.</p>
      <p><b>Exercitadas:</b> {escape(', '.join(cobertas))}</p><p><b>Ainda sem passo de teste:</b> {escape(', '.join(faltando)) or '—'}</p>
      <h2>Limpeza dos dados do teste</h2><p>{escape(limpeza_resumo)}</p>
    </body></html>"""
    return html, contagem, saude, problemas, (cobertas, faltando)


def gerar_pdf(html, destino):
    from playwright.sync_api import sync_playwright
    temporario = os.path.join(PASTA_AO_VIVO, f"pdf_{os.getpid()}.html")
    with open(temporario, "w", encoding="utf-8") as f:
        f.write(html)
    with sync_playwright() as p:
        from navegador import abrir_chromium
        navegador = abrir_chromium(p)
        pagina = navegador.new_page()
        pagina.goto("file:///" + os.path.abspath(temporario).replace("\\", "/"), wait_until="load")
        pagina.pdf(path=destino, format="A4", print_background=True, display_header_footer=True, header_template="<span></span>",
                   footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#64748b'>Mentoria · Agentes de Funcionalidades · "
                                   "página <span class='pageNumber'></span> de <span class='totalPages'></span></div>",
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        navegador.close()
    os.remove(temporario)


def prompt_consolidado(problemas, faltando, destino):
    linhas = ["# 🧩 Prompt de Correção de Funcionalidades para LLM — Consolidado\n",
              f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo Gerente de Funcionalidades. Cole no assistente de IA da sua preferência.\n",
              "---\n", "Você é um desenvolvedor sênior de Python/Flask desta plataforma de mentoria (Flask-Login, Flask-SQLAlchemy, Jinja2).",
              f"O teste funcional do fluxo completo (8 perfis) encontrou {len(problemas)} ponto(s). Corrija na ordem; para cada um explique a causa, "
              "entregue o código ANTES → DEPOIS sem quebrar as regras dos outros perfis e diga como confirmar com os Agentes de Funcionalidades.\n"]
    for i, t in enumerate(problemas, 1):
        linhas += [f"### {i}. [{t['resultado']} · {t['severidade']}] {t['titulo']} ({t['agente']})", f"- Esperado: {t['esperado']}",
                   f"- Obtido: {t['detalhe']}"] + ([f"- Sugestão: {t['recomendacao']}"] if t["recomendacao"] else []) + [""]
    if faltando:
        linhas += ["## Funções ainda sem passo no fluxo de teste\n", ", ".join(faltando), ""]
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# ------------------------------------------------------------------------------ execução
def rodar_agente(chave, estado, url):
    inicio = time.time()
    estado.agente(chave, status="executando", inicio=datetime.now().isoformat(timespec="seconds"))
    with estado.trava:
        estado.dados["atual"] = chave
    estado.log(f"▶ {NOMES[chave]} recebeu a vez")
    try:
        os.remove(os.path.join(PASTA_AO_VIVO, "agente.json"))
    except OSError:
        pass
    marco = time.time()
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "FUNC_AO_VIVO": PASTA_AO_VIVO, "FUNC_CONTEXTO": ARQUIVO_CONTEXTO, "OMNITEST_URL": url}
    proc = subprocess.Popen([sys.executable, os.path.join(PASTA, "agente_fluxo.py"), chave], cwd=RAIZ_PROJETO, env=ambiente,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for linha in proc.stdout:
        if "✗ [" in linha or "⚠ [" in linha or "▶" in linha:
            estado.log(f"[{NOMES[chave].replace('Agente ', '')}] {linha.strip()[10:] if linha[:2].isdigit() else linha.strip()}")
    proc.wait()
    segundos = int(time.time() - inicio)
    arquivos = [j for j in glob.glob(os.path.join(PASTA_RELATORIOS, f"Funcional_{chave}_*.json")) if os.path.getmtime(j) >= marco]
    if not arquivos:
        estado.agente(chave, status="erro", duracao=f"{segundos} s")
        estado.log(f"✖ {NOMES[chave]} terminou sem relatório (código {proc.returncode})")
        return None
    with open(max(arquivos, key=os.path.getmtime), encoding="utf-8") as f:
        dados = json.load(f)
    data = datetime.now().strftime("%Y%m%d_%H%M")
    destino_pdf = os.path.join(PASTA_REL, PASTAS[chave], f"Relatorio_Funcional_{chave}_{data}.pdf")
    destino_prompt = os.path.join(PASTA_PROMPT, PASTAS[chave], f"Prompt_funcional_{chave}_{data}.md")
    try:
        gerar_pdf(html_agente(dados), destino_pdf)
        pdf = os.path.relpath(destino_pdf, BASE_IA)
    except Exception as e:
        pdf = None
        estado.log(f"✖ PDF não gerado: {e}")
    shutil.copyfile(dados["prompt"], destino_prompt)
    c = dados["contagem"]
    estado.agente(chave, status="falhas" if c[FALHA] else "concluido", verificacoes=len(dados["testes"]), contagem=c, saude=dados["saude"],
                  pdf=pdf, prompt=os.path.relpath(destino_prompt, BASE_IA), duracao=f"{segundos} s", segundos=segundos,
                  fim=datetime.now().isoformat(timespec="seconds"))
    estado.log(f"{'✖' if c[FALHA] else '✔'} {NOMES[chave]}: {len(dados['testes'])} testes · {c[APROVADO]} aprovados · {c[FALHA]} falhas · "
               f"{c[ALERTA]} alertas · passa a vez")
    historico = ler_historico()
    historico[chave] = round((historico.get(chave, segundos) + segundos) / 2)
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(historico, f)
    return dados


def main():
    parser = argparse.ArgumentParser(description="Gerente de Funcionalidades: fluxo completo da plataforma, perfil a perfil.")
    parser.add_argument("--url", default=os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--manter-dados", action="store_true", help="Não remove os dados [Funcional] ao final (para inspeção).")
    args = parser.parse_args()
    criar_estrutura()
    estado = Estado(ORDEM)
    parar = threading.Event()
    threading.Thread(target=batimento, args=(estado, parar), daemon=True).start()
    try:
        estado.log("🧩 Gerente de Funcionalidades: iniciando o fluxo completo da plataforma")
        try:
            os.remove(ARQUIVO_CONTEXTO)
        except OSError:
            pass
        preparar(estado)
        relatorios = []
        for chave in ORDEM:
            dados = rodar_agente(chave, estado, args.url.rstrip("/"))
            if dados:
                relatorios.append(dados)
        resumo_limpeza = "Dados mantidos para inspeção (--manter-dados)."
        if not args.manter_dados:
            import limpeza
            resultado = limpeza.limpar(estado.log)
            resumo_limpeza = (f"{resultado['linhas']} linha(s) em {len(resultado['tabelas'])} tabela(s) e {resultado['arquivos']} arquivo(s) removidos; "
                              f"usuários do teste restantes: {resultado['sobras_usuarios']}.")
            try:
                os.remove(ARQUIVO_CONTEXTO)  # tinha as senhas geradas para os usuários do teste
            except OSError:
                pass
        if relatorios:
            def aprender_falhas():
                import conhecimento_funcional as cf
                return cf.aprender_com_falhas(relatorios)
            try:
                refs = com_app(aprender_falhas)
                if refs:
                    estado.log(f"📖 {len(refs)} referência(s) oficial(is) propostas para os agentes (aguardando aprovação)")
            except Exception as e:
                estado.log(f"📖 Referências não propostas: {e}")

            def ensinar():
                import conhecimento_funcional as cf
                return [a.titulo for a in cf.ensinar_outros_agentes(relatorios)]
            try:
                ensinadas = com_app(ensinar)
                if ensinadas:
                    estado.log(f"🎓 {len(ensinadas)} regra(s) de negócio ensinada(s) às equipes de Segurança, Banco de Dados e testes fim a fim")
            except Exception as e:
                estado.log(f"🎓 Regras não ensinadas: {e}")
            estado.log("📄 Gerando o relatório consolidado…")
            html, contagem, saude, problemas, (cobertas, faltando) = html_consolidado(relatorios, resumo_limpeza)
            data = datetime.now().strftime("%Y%m%d_%H%M")
            destino = os.path.join(PASTA_REL, PASTAS["consolidado"], f"Relatorio_Funcional_consolidado_{data}.pdf")
            destino_prompt = os.path.join(PASTA_PROMPT, PASTAS["consolidado"], f"Prompt_funcional_consolidado_{data}.md")
            try:
                gerar_pdf(html, destino)
            except Exception as e:
                destino = None
                estado.log(f"✖ PDF consolidado não gerado: {e}")
            prompt_consolidado(problemas, faltando, destino_prompt)
            with estado.trava:
                estado.dados["consolidado"] = {"pdf": destino and os.path.relpath(destino, BASE_IA), "prompt": os.path.relpath(destino_prompt, BASE_IA),
                                               "contagem": contagem, "saude": saude, "cobertura": [len(cobertas), len(cobertas) + len(faltando)],
                                               "limpeza": resumo_limpeza,
                                               "principais": [{"resultado": t["resultado"], "severidade": t["severidade"], "titulo": t["titulo"],
                                                               "agente": t["agente"]} for t in problemas][:12]}
        with estado.trava:
            estado.dados.update(status="concluido", atual=None, fim=datetime.now().isoformat(timespec="seconds"))
        estado.log("✔ Fluxo funcional concluído")
    except Exception as e:
        with estado.trava:
            estado.dados.update(status="erro", fim=datetime.now().isoformat(timespec="seconds"))
        estado.log(f"✖ Gerente de Funcionalidades interrompido: {e}")
    finally:
        parar.set()
        estado.gravar()


if __name__ == "__main__":
    main()
