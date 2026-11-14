"""
ORQUESTRADOR OMNITEST
=====================
Prepara os utilizadores de teste uma única vez, dispara um agente por perfil
(em paralelo por padrão, cada um no seu próprio processo e navegador) e junta
tudo num relatório consolidado.

Uso:
    python agentes_omnitest/executar_todos.py                 # 6 agentes em paralelo, sem janela
    python agentes_omnitest/executar_todos.py --sequencial --visual
    python agentes_omnitest/executar_todos.py --perfis aluno mentor --escrita
    python agentes_omnitest/executar_todos.py --primeiro-acesso       # refaz onboarding e presença do zero
"""
import os
import sys
import json
import glob
import argparse
import subprocess
from datetime import datetime

from nucleo import (PERFIS, PASTA_RELATORIOS, RAIZ_PROJETO, BASE_URL, preparar_usuario, cabecalho_prompt_gemini,
                    APROVADO, FALHA, ALERTA, PULADO)

PASTA_AGENTES = os.path.dirname(os.path.abspath(__file__))


def gerar_prompt_consolidado(relatorios, inicio):
    """Junta os ❌/⚠️ de todos os perfis num só prompt; o mesmo problema em vários perfis aparece uma vez."""
    grupos = {}
    for dados in relatorios.values():
        for r in dados["resultados"]:
            if r["status"] not in (FALHA, ALERTA) or r["modulo"] == "Preparação":
                continue
            chave = (r["modulo"], r["acao"], r["detalhe"])
            grupo = grupos.setdefault(chave, {"r": r, "perfis": []})
            grupo["perfis"].append(dados["perfil"])
    if not grupos:
        return None

    itens = sorted(grupos.values(), key=lambda g: (g["r"]["status"] != FALHA, -len(g["perfis"])))
    linhas = cabecalho_prompt_gemini("Todos os perfis", "os 6 perfis da plataforma",
                                     [g["r"] for g in itens], "python agentes_omnitest/executar_todos.py")
    for i, g in enumerate(itens, 1):
        r = g["r"]
        tipo = "FALHA" if r["status"] == FALHA else "ALERTA (melhoria)"
        linhas.append(f"### {i}. {tipo} — {r['modulo']} › {r['acao']}")
        linhas.append(f"- **Perfis afetados:** {', '.join(g['perfis'])}")
        linhas += [f"- {linha}" for linha in r.get("detalhes", [f"**Observado:** {r['detalhe']}"])]
        linhas.append("")

    caminho = os.path.join(PASTA_RELATORIOS, f"Prompt_Gemini_TODOS_{inicio.strftime('%Y%m%d_%H%M%S')}.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    return caminho


def main():
    parser = argparse.ArgumentParser(description="OmniTest — executa um agente por perfil e consolida os relatórios.")
    parser.add_argument("--perfis", nargs="+", choices=list(PERFIS), default=list(PERFIS), help="Perfis a testar (padrão: todos).")
    parser.add_argument("--sequencial", action="store_true", help="Um agente de cada vez em vez de todos em paralelo.")
    parser.add_argument("--visual", action="store_true", help="Abre as janelas do navegador (por padrão roda headless).")
    parser.add_argument("--escrita", action="store_true", help="Liga os testes que gravam dados (tickets, horas de voluntariado).")
    parser.add_argument("--primeiro-acesso", action="store_true", help="Reinicia termo, frequência de hoje e tour para testar a primeira entrada.")
    args = parser.parse_args()

    inicio = datetime.now()
    print("\n==================================================")
    print("  🤖 [OMNITEST] ORQUESTRADOR — UM AGENTE POR PERFIL")
    print(f"     Perfis: {', '.join(args.perfis)}  →  {BASE_URL}")
    print("==================================================\n")

    # 1. Fixture uma única vez, para os agentes paralelos não disputarem o SQLite
    notas_preparo = {}
    for chave in args.perfis:
        try:
            notas_preparo[chave] = preparar_usuario(chave, args.primeiro_acesso)
        except Exception as e:
            notas_preparo[chave] = [f"Falha ao preparar: {e}"]
        print(f"   🛠️ {PERFIS[chave]['tipo']}: " + ("; ".join(notas_preparo[chave]) or "pronto"))

    # 2. Dispara os agentes
    comandos = {}
    for chave in args.perfis:
        cmd = [sys.executable, os.path.join(PASTA_AGENTES, f"agente_{chave}.py"), "--sem-preparo"]
        if not args.visual:
            cmd += ["--headless", "--lento", "0"]
        if args.escrita:
            cmd.append("--escrita")
        comandos[chave] = cmd

    codigos = {}
    if args.sequencial:
        for chave, cmd in comandos.items():
            codigos[chave] = subprocess.run(cmd, cwd=RAIZ_PROJETO).returncode
    else:
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        processos = {}
        for chave, cmd in comandos.items():
            log = open(os.path.join(PASTA_RELATORIOS, f"log_{chave}.txt"), "w", encoding="utf-8")
            processos[chave] = (subprocess.Popen(cmd, cwd=RAIZ_PROJETO, stdout=log, stderr=subprocess.STDOUT,
                                                 env={**os.environ, "PYTHONIOENCODING": "utf-8"}), log)
            print(f"   🚀 Agente {PERFIS[chave]['tipo']} iniciado.")
        for chave, (proc, log) in processos.items():
            codigos[chave] = proc.wait()
            log.close()
            print(f"   {'✅' if codigos[chave] == 0 else '❌'} Agente {PERFIS[chave]['tipo']} terminou.")

    # 3. Consolida os JSON gerados nesta execução
    linhas = [
        "# 📊 Relatório Consolidado — OmniTest por Perfil\n",
        f"**Data da Execução:** {inicio.strftime('%d/%m/%Y às %H:%M:%S')}  ",
        f"**Ambiente:** {BASE_URL}  ",
        f"**Modo escrita:** {'Ligado' if args.escrita else 'Desligado (somente leitura)'}\n",
        "| Perfil | ✅ Aprovados | ❌ Falhas | ⚠️ Alertas | ⏭️ Pulados | Relatório |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]
    # Lê pelo campo "chave" do JSON: o glob "mentor_*" também apanharia "mentor_administrador_*"
    relatorios = {}
    for arquivo in sorted(glob.glob(os.path.join(PASTA_RELATORIOS, "Relatorio_OmniTest_*.json")), key=os.path.getmtime):
        if os.path.getmtime(arquivo) >= inicio.timestamp():
            with open(arquivo, encoding="utf-8") as f:
                dados = json.load(f)
            relatorios[dados["chave"]] = dados

    falhas_gerais = []
    for chave in args.perfis:
        dados = relatorios.get(chave)
        if not dados:
            linhas.append(f"| {PERFIS[chave]['tipo']} | – | – | – | – | ❌ Agente não gerou relatório (ver log_{chave}.txt) |")
            continue
        c = dados["contagem"]
        rel = os.path.basename(dados["relatorio"])
        linhas.append(f"| {dados['perfil']} | {c[APROVADO]} | {c[FALHA]} | {c[ALERTA]} | {c[PULADO]} | [{rel}]({rel}) |")
        falhas_gerais += [f"- **{dados['perfil']}** › {r['modulo']} › {r['acao']}: {r['detalhe']}"
                          for r in dados["resultados"] if r["status"] == FALHA]

    linhas.append("\n## 🔴 Todas as falhas encontradas\n")
    linhas += falhas_gerais or ["- Nenhuma falha. 🎉"]

    consolidado = gerar_prompt_consolidado(relatorios, inicio)
    prompts = [d["prompt_gemini"] for d in relatorios.values() if d.get("prompt_gemini")]
    if consolidado:
        linhas.append("\n## 🤖 Prompt de correção para o Gemini\n")
        linhas.append(f"- **Todos os perfis, sem repetição (recomendado):** [{os.path.basename(consolidado)}]({os.path.basename(consolidado)})")
        linhas += [f"- {os.path.basename(p)}: [{os.path.basename(p)}]({os.path.basename(p)})" for p in prompts]

    caminho = os.path.join(PASTA_RELATORIOS, f"Relatorio_OmniTest_Consolidado_{inicio.strftime('%Y%m%d_%H%M%S')}.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    print("\n==================================================")
    print(f"✅ OMNITEST CONCLUÍDO em {(datetime.now() - inicio).seconds}s — {len(falhas_gerais)} falha(s) no total")
    print(f"   Consolidado: {caminho}")
    if consolidado:
        print(f"   Prompt único para o Gemini: {consolidado}")
    print("==================================================\n")
    sys.exit(0 if all(c == 0 for c in codigos.values()) else 1)


if __name__ == "__main__":
    main()
