"""
AGENTE OMNITEST — PERFIS PERSONALIZADOS (aprendidos do Agente Gerente Técnico)
Uso: python agentes_omnitest/agente_perfis_personalizados.py [--headless] [--lento 0] [--sem-preparo]

Este agente não tem uma lista fixa de perfis: ele lê os aprendizados APLICADOS do tipo perfil_novo/perfil_alterado/
perfil_removido (conhecimento.perfis_aprendidos) e, para cada perfil personalizado ativo:
  1. cria/ajusta um utilizador de teste com aquele perfil (perfil<ID>_ominitest@local.com);
  2. monta o agente a partir do agente do perfil-base, recalculando rotas e menu conforme os módulos ligados;
  3. roda o teste fim a fim (menu, matriz de acesso, temas, idiomas, logout) e junta tudo num relatório só.
Se um aprendizado de perfil for revogado na Governança de aprendizados, o perfil sai deste teste.
"""
import os
import sys
import json
import argparse
from datetime import datetime

from nucleo import (PERFIS, PASTA_RELATORIOS, consultar_banco, preparar_usuario, cabecalho_prompt_llm,
                    APROVADO, FALHA, ALERTA, PULADO)
from agente_administrador import AgenteAdministrador
from agente_aluno import AgenteAluno
from agente_professor import AgenteProfessor
from agente_mentor import AgenteMentor
from agente_mentor_administrador import AgenteMentorAdministrador
from agente_gestor_b2b import AgenteGestorB2B
from agente_avaliador import AgenteAvaliador

CHAVE = "perfis_personalizados"
CLASSE_DA_BASE = {"Administrador": AgenteAdministrador, "Aluno": AgenteAluno, "Professor": AgenteProfessor, "Mentor": AgenteMentor,
                  "Mentor Administrador": AgenteMentorAdministrador, "Admin B2B": AgenteGestorB2B, "Avaliador Banca": AgenteAvaliador}
# Rotas do catálogo do OmniTest (nucleo.ROTAS) que pertencem a cada módulo de perfis_acesso.MODULOS
ROTAS_DO_MODULO = {"painel": ["dashboard"], "sessoes": ["sessoes"], "acompanhamento": ["acompanhamento"], "atividades_extras": ["atividades_extras"],
                   "hub": ["hub_educacional"], "diario": ["frequencia", "notas"], "projetos": ["projetos"], "bancas": ["minhas_bancas", "banca"],
                   "biblioteca": ["biblioteca"], "certificados": ["certificados"], "demandas": ["demandas"], "voluntariado": ["esg_csv", "esg_pdf"],
                   "cadastros": ["usuarios", "grupos"], "reunioes": ["reunioes"],
                   "agenda_bancas": ["agenda_bancas", "avaliadores_banca"], "indicadores": ["indicadores"], "agentes_ia": ["agentes_ia"],
                   "manutencao": ["banco"]}
MODULO_DA_ROTA = {rota: modulo for modulo, rotas in ROTAS_DO_MODULO.items() for rota in rotas}


def classe_para(perfil):
    """Agente do perfil personalizado: herda do agente do perfil-base e só muda o que os módulos mudam."""
    base = CLASSE_DA_BASE[perfil["base"]]
    liberados = set(perfil["modulos"]) | {"painel"}

    def liberada(rota):
        modulo = MODULO_DA_ROTA.get(rota)
        return modulo is None or modulo in liberados

    permitidas = [r for r in base.ROTAS_PERMITIDAS if liberada(r)]
    bloqueadas = list(dict.fromkeys(base.ROTAS_BLOQUEADAS + [r for r in base.ROTAS_PERMITIDAS if not liberada(r)]))
    if perfil["base"] == "Avaliador Banca":
        # A Sala da Banca depende de o utilizador estar escalado numa banca: fica fora da matriz deste perfil
        permitidas = [r for r in permitidas if r != "banca"]
        bloqueadas = [r for r in bloqueadas if r != "banca"]
    menu_visivel = [r for r in base.MENU_VISIVEL if liberada(r)]
    menu_oculto = list(dict.fromkeys(base.MENU_OCULTO + [r for r in base.MENU_VISIVEL if not liberada(r)]))

    def testes_especificos(self):
        self.etapa("Perfil personalizado", "Módulos do perfil", lambda: self.verificar_perfil(perfil))

    def verificar_perfil(self, dados):
        """O painel mostra o nome do perfil e o menu respeita os módulos (a matriz de acesso confere as rotas)."""
        self.visitar(self.PAGINA_INICIAL)
        texto = self.texto_pagina()
        if dados["base"] != "Avaliador Banca" and dados["nome"] not in texto:
            self.registrar("Perfil personalizado", "Nome do perfil no painel", FALHA, f"'{dados['nome']}' não aparece no Painel Geral.",
                           arquivos="templates/dashboard.html (Nível de Acesso)")
        else:
            self.registrar("Perfil personalizado", "Nome do perfil no painel", APROVADO, evidencia=False)
        self.registrar("Perfil personalizado", "Módulos aprendidos", APROVADO,
                       f"Herda de {dados['base']}; liberados: {', '.join(sorted(liberados))} (aprendizado {dados['aprendizado']}).", evidencia=False)

    def teste_tour(self):
        # O tour encadeado do perfil-base pode passar por módulos desligados: aqui só o botão de tour de cada página
        self.tratar_tour = False
        try:
            self.etapa("Tour", "Botão de tour em cada página", self.tour_botao_manual)
        finally:
            self.tratar_tour = True

    return type(f"AgentePerfil{perfil['perfil_id']}", (base,), {
        "chave_perfil": f"perfil_{perfil['perfil_id']}", "ROTAS_PERMITIDAS": permitidas, "ROTAS_BLOQUEADAS": bloqueadas,
        "MENU_VISIVEL": menu_visivel, "MENU_OCULTO": menu_oculto, "TESTAR_RECUPERACAO": False, "TOUR_ESPERADO": None,
        "CHAVES_MENU_IDIOMA": ("painel_geral",), "ROTEIRO": [
            f"Perfil personalizado '{perfil['nome']}' (herda de {perfil['base']}), aprendido em {perfil['aprendizado']}",
            "Menu: só os módulos ligados aparecem; matriz de acesso: módulos desligados são barrados na rota",
            "Temas, idiomas, botão de tour e logout em todas as páginas liberadas"],
        "testes_especificos": testes_especificos, "verificar_perfil": verificar_perfil, "teste_tour": teste_tour,
    })


def preparar_utilizador(perfil):
    chave = f"perfil_{perfil['perfil_id']}"
    PERFIS[chave] = {"nome": f"{perfil['nome']} OmniTest"[:100], "email": f"perfil{perfil['perfil_id']}_ominitest@local.com", "tipo": perfil["base"]}
    preparar_usuario(chave)

    def vincular():
        from models import Usuario, db
        u = Usuario.query.filter_by(email=PERFIS[chave]["email"]).first()
        u.perfil_personalizado_id = perfil["perfil_id"]
        db.session.commit()
    consultar_banco(vincular)
    return chave


def main():
    parser = argparse.ArgumentParser(description="OmniTest — perfis personalizados aprendidos do Agente Gerente Técnico")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--lento", type=int, default=400)
    parser.add_argument("--escrita", action="store_true", help="Sem efeito aqui: este agente só lê.")
    parser.add_argument("--sem-preparo", action="store_true")
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()

    import conhecimento
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    perfis = consultar_banco(conhecimento.perfis_aprendidos)
    resultados, capturas, roteiro = [], [], []
    print(f"🧠 Perfis personalizados aprendidos: {len(perfis)}")
    for perfil in perfis:
        if perfil["base"] not in CLASSE_DA_BASE:
            continue
        preparar_utilizador(perfil)
        agente = classe_para(perfil)(headless=args.headless, lento=args.lento, escrita=False, preparar=False)
        agente.executar()
        for r in agente.resultados:
            r = dict(r)
            r["modulo"] = f"[{perfil['nome']}] {r['modulo']}"
            if r["status"] in (FALHA, ALERTA):
                r["detalhes"] = agente.detalhes_do_problema(r)
            resultados.append(r)
        capturas += [{**c, "modulo": f"[{perfil['nome']}] {c['modulo']}"} for c in agente.capturas]
        roteiro += [f"[{perfil['nome']}] {p}" for p in agente.roteiro()]
    if not perfis:
        resultados.append({"modulo": "Perfis personalizados", "acao": "Perfis aprendidos", "status": PULADO,
                           "detalhe": "Nenhum perfil personalizado ativo foi aprendido ainda (Administração › Perfis de acesso).",
                           "evidencia": "", "esperado": "", "dica": "", "arquivos": "", "url": "", "hora": datetime.now().strftime("%H:%M:%S")})

    # Relatório consolidado deste agente (o Agente Gestor gera o PDF a partir deste JSON)
    contagem = {s: sum(1 for r in resultados if r["status"] == s) for s in (APROVADO, FALHA, ALERTA, PULADO)}
    problemas = [r for r in resultados if r["status"] in (FALHA, ALERTA)]
    caminho_prompt = os.path.join(PASTA_RELATORIOS, f"Prompt_LLM_{CHAVE}_{carimbo}.md")
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    with open(caminho_prompt, "w", encoding="utf-8") as f:
        if problemas:
            linhas = cabecalho_prompt_llm("Perfis personalizados", "os perfis personalizados", problemas,
                                          "python agentes_omnitest/agente_perfis_personalizados.py")
            for i, r in enumerate(problemas, 1):
                linhas.append(f"### {i}. {'FALHA' if r['status'] == FALHA else 'ALERTA'} — {r['modulo']} › {r['acao']}")
                linhas += [f"- {d}" for d in r.get("detalhes", [])]
                linhas.append("")
        else:
            linhas = ["# 🤖 Prompt de Correção para LLM — Perfis personalizados\n",
                      f"✅ Nenhuma falha ou alerta nos {len(perfis)} perfil(is) personalizado(s) testado(s). Não há correções para pedir ao LLM."]
        f.write("\n".join(linhas) + "\n")
    with open(os.path.join(PASTA_RELATORIOS, f"Relatorio_OmniTest_{CHAVE}_{carimbo}.json"), "w", encoding="utf-8") as f:
        json.dump({"perfil": "Perfis personalizados", "chave": CHAVE, "contagem": contagem, "resultados": resultados, "capturas": capturas,
                   "prompt_llm": caminho_prompt, "email": ", ".join(f"perfil{p['perfil_id']}_ominitest@local.com" for p in perfis),
                   "ambiente": os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000"), "escrita": False,
                   "roteiro": roteiro or ["Nenhum perfil personalizado aprendido"], "carimbo": carimbo}, f, ensure_ascii=False, indent=2)
    print(f"✅ Perfis personalizados: {contagem[APROVADO]} ✅  {contagem[FALHA]} ❌  {contagem[ALERTA]} ⚠️")
    sys.exit(0 if contagem[FALHA] == 0 else 1)


if __name__ == "__main__":
    main()
