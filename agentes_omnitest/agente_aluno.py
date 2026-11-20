"""
AGENTE OMNITEST — PERFIL ALUNO
Uso: python agentes_omnitest/agente_aluno.py [--headless] [--lento 0]

O que este agente cobre:
  1. Login e recuperação de senha pelas perguntas de segurança (resposta de teste: "teste")
  2. Painel Geral: KPIs conferidos com o banco, gráficos, filtro e todas as ordenações
  3. Sessões: lista as sessões do aluno e quantas estão agendadas
  4. Acompanhamento: cursos do aluno, Conectar Agenda (OAuth Google) e Gemini Notebook
  5. Projetos: o projeto do grupo do aluno aparece e nenhum outro
  6. Regra 1 (sem relógio, demandas e banca) e privacidade entre alunos
  7. Tour: convite, Lembrar Depois, tour encadeado por todas as páginas do menu,
     Não mostrar novamente e botão de tour em cada página (no núcleo)
  8. Tema e idioma em todas as páginas (no núcleo)

Este agente testa SOMENTE o perfil Aluno. Para rodar todos os perfis use executar_todos.py.
Com --pausar o navegador fica aberto no fim até você pressionar Enter.
Tudo o que falhar entra no prompt de correção para LLM (Agent Reports/OmniTest/Prompt_LLM_aluno_*.md).
"""
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from nucleo import AgenteOmniTest, executar_cli, consultar_banco, BASE_URL, APROVADO, FALHA, ALERTA, PULADO


class AgenteAluno(AgenteOmniTest):
    chave_perfil = "aluno"
    exige_frequencia = True
    exige_onboarding = False
    # O tour do Aluno segue as páginas do menu dele, na ordem do menu (conferido pelo núcleo a partir do próprio menu)
    TOUR_ESPERADO = None

    ROTEIRO = [
        "Regra 1: Relógio de Voluntariado oculto e Sala da Banca bloqueada; Portal de Demandas liberado (só os próprios tickets)",
        "Painel Geral: KPIs e mentor responsável conferidos com o banco; 'Total de Alunos' oculto",
        "Painel Geral: gráficos de evolução e de skills com os dados do banco e desenhados no ecrã",
        "Painel Geral: filtro por texto, filtro sem resultado, as 6 opções de 'Ordenar por' e a volta para 'Padrão'",
        "Sessões: todas as sessões do aluno listadas, quantas estão agendadas e a próxima",
        "Acompanhamento: cursos do aluno, Conectar Agenda (OAuth Google, sem fazer login) e Gemini Notebook (resposta real e XSS)",
        "Projetos: projeto do grupo do aluno com nome, grupo e progresso; nenhum projeto de outro grupo; sem link da banca",
        "Privacidade: nenhum e-mail de outro aluno em Sessões e Acompanhamento",
    ]

    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "demandas", "atividades_extras", "certificados", "repositorio"]
    # Regra 1 (revista com a coordenação instituição/B2B): o Aluno não acede ao Relógio de Voluntariado nem à Sala da Banca,
    # mas usa o Portal de Demandas para registar pedidos (nada por WhatsApp ou e-mail)
    ROTAS_BLOQUEADAS = ["hub_educacional", "frequencia", "notas", "usuarios", "grupos",
                        "solicitacoes", "banco", "banca", "esg_csv", "esg_pdf", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "agentes_ia"]
    MENU_VISIVEL = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "demandas", "atividades_extras"]
    MENU_OCULTO = ["hub_educacional", "frequencia", "notas", "usuarios", "solicitacoes", "banco", "reunioes"]

    # ==========================================================================
    # TESTES APÓS O LOGIN
    # ==========================================================================
    def testes_especificos(self):
        self.etapa("Voluntariado ESG", "Relógio oculto para Aluno", lambda: self.verificar_relogio_voluntariado(deve_existir=False))
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=False))
        if self.escrita:
            self.etapa("Portal de Demandas", "Abrir ticket (escrita)", self.abrir_ticket_demanda)
        self.etapa("Painel Geral", "KPIs", self.painel_kpis)
        self.etapa("Painel Geral", "Gráficos", self.painel_graficos)
        self.etapa("Painel Geral", "Filtro e ordenação", self.painel_filtro_e_ordenacao)
        self.etapa("Sessões", "Sessões agendadas", self.sessoes_agendadas)
        self.etapa("Acompanhamento", "Cursos do aluno", self.acompanhamento_cursos)
        self.etapa("Acompanhamento", "Conectar Agenda", self.acompanhamento_conectar_agenda)
        self.etapa("Acompanhamento", "Gemini Notebook", self.acompanhamento_gemini_notebook)
        self.etapa("Projetos", "Projeto do aluno", self.projetos_do_aluno)
        self.etapa("Projetos", "Aluno não cadastra projetos", self.aluno_nao_cadastra_projeto)
        self.etapa("Sessões", "Privacidade entre alunos", lambda: self.verificar_privacidade("/sessoes", "Sessões"))
        self.etapa("Acompanhamento", "Privacidade entre alunos", lambda: self.verificar_privacidade("/acompanhamento", "Acompanhamento"))

    # --------------------------------------------------------------------------
    # Dados esperados, calculados direto do banco (independente do app.py)
    # --------------------------------------------------------------------------
    def dados_esperados(self):
        from models import Usuario, Acompanhamento, Curso, Projeto, SessaoMentoria

        def calcular():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            matriculas = []
            for a in Acompanhamento.query.filter_by(aluno_id=eu.id).all():
                curso = Curso.query.get(a.curso_id)
                if curso:
                    matriculas.append({"curso": curso.nome_curso, "tipo": curso.tipo or "Outro", "carga": curso.carga_horaria or 0,
                                       "percentual": a.percentual_conclusao or 0, "status": a.status,
                                       "certificado": bool(a.certificado_anexado),
                                       "mes": (a.data_inicio or datetime.utcnow()).strftime("%m/%Y")})
            grupos = {g.id: g.nome for g in eu.grupos}
            projetos = Projeto.query.filter(Projeto.grupo_id.in_(list(grupos) or [-1])).all()
            outros = Projeto.query.filter(~Projeto.grupo_id.in_(list(grupos) or [-1])).all()
            return {
                "matriculas": matriculas,
                "mentores": [m.nome for m in eu.mentores.all()],
                "projetos": [{"nome": p.nome, "grupo": grupos[p.grupo_id], "status": p.status,
                              "percentual": p.percentual_conclusao or 0} for p in projetos],
                "outros_projetos": [p.nome for p in outros],
                "sessoes": [s.data_sessao for s in SessaoMentoria.query.filter_by(aluno_id=eu.id).all()],
            }
        return consultar_banco(calcular)

    # --------------------------------------------------------------------------
    # 2. PAINEL GERAL
    # --------------------------------------------------------------------------
    def painel_kpis(self):
        from traducoes import TEXTOS

        dados = self.dados_esperados()
        mat = dados["matriculas"]
        finalizados = [m for m in mat if m["status"] == "Finalizado"]
        esperado = {
            "finalizados": len(finalizados),
            "com_certificado": sum(1 for m in finalizados if m["certificado"]),
            "sem_certificado": sum(1 for m in finalizados if not m["certificado"]),
            "cursos_risco": sum(1 for m in mat if m["status"] == "Parado"),
        }
        idioma = self.preferencias_atuais()[1]
        textos = TEXTOS.get(idioma, TEXTOS["pt"])
        self.visitar("/dashboard")

        divergencias, conferidos = [], []
        for chave, valor in esperado.items():
            lido = self.ler_card(textos[chave])
            if lido is None:
                divergencias.append(f"card '{textos[chave]}' não encontrado")
            elif lido != str(valor):
                divergencias.append(f"{textos[chave]}: tela {lido} × banco {valor}")
            else:
                conferidos.append(f"{textos[chave]}={valor}")

        projetos = dados["projetos"]
        rotulo_proj = self.page.locator('small:text-is("PROJETOS (TCC)")').first
        card_proj = rotulo_proj.locator("xpath=..")
        if rotulo_proj.count():
            tela = (card_proj.locator("h3").inner_text().strip(), card_proj.locator("span.text-info").inner_text().strip(),
                    card_proj.locator("span.text-success").inner_text().strip())
            banco = (str(len(projetos)), str(sum(1 for p in projetos if p["status"] == "Em Andamento")),
                     str(sum(1 for p in projetos if p["status"] == "Concluído")))
            if tela != banco:
                divergencias.append(f"Projetos (total/andamento/concluídos): tela {'/'.join(tela)} × banco {'/'.join(banco)}")
            else:
                conferidos.append(f"Projetos={'/'.join(banco)}")
        else:
            divergencias.append("card 'PROJETOS (TCC)' não encontrado")

        if self.ler_card(textos["total_alunos"]) is not None:
            divergencias.append("card 'Total de Alunos' visível para o Aluno")

        if divergencias:
            self.registrar("Painel Geral", "KPIs conferidos com o banco", FALHA, "; ".join(divergencias),
                           esperado="Cada card igual ao cálculo feito direto no banco para este aluno",
                           dica="Conferir os contadores na rota dashboard() de app.py (bloco do Aluno) e os cards de dashboard.html.")
        else:
            self.registrar("Painel Geral", "KPIs conferidos com o banco", APROVADO, ", ".join(conferidos), evidencia=False)

        esperado_mentor = " e ".join(dados["mentores"]) or "Não atribuído"
        bloco = self.page.locator("p.text-muted span.ms-3 strong.text-primary").first
        lido = bloco.inner_text().strip() if bloco.count() else ""
        if lido == esperado_mentor:
            self.registrar("Painel Geral", "Mentor responsável", APROVADO, lido, evidencia=False)
        else:
            self.registrar("Painel Geral", "Mentor responsável", FALHA, f"Tela '{lido}' × banco '{esperado_mentor}'.",
                           esperado="Nome dos mentores vinculados ao aluno (ou 'Não atribuído')")

    JS_GRAFICOS = r"""(ids) => ids.map(id => {
        const c = document.getElementById(id);
        if (!c) return { id, existe: false };
        const ch = (window.Chart && Chart.getChart) ? Chart.getChart(c) : null;
        let pintado = false;
        try {
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            for (let i = 3; i < d.length; i += 16) { if (d[i] > 0) { pintado = true; break; } }
        } catch (e) {}
        return { id, existe: true, biblioteca: !!window.Chart, instancia: !!ch, tipo: ch ? ch.config.type : null,
                 labels: ch ? ch.data.labels : [], datasets: ch ? ch.data.datasets.map(d => d.data) : [],
                 pintado, largura: c.clientWidth, altura: c.clientHeight };
    })"""

    def painel_graficos(self):
        mat = self.dados_esperados()["matriculas"]
        meses = sorted({m["mes"] for m in mat}, key=lambda x: datetime.strptime(x, "%m/%Y"))
        horas = [sum(m["carga"] for m in mat if m["mes"] == mes) for mes in meses]
        concluidos = [sum(1 for m in mat if m["mes"] == mes and m["status"] == "Finalizado") for mes in meses]
        tipos = {}
        for m in mat:
            tipos.setdefault(m["tipo"], []).append(m["percentual"])
        radar = {t: round(sum(v) / len(v), 1) for t, v in tipos.items()}

        self.visitar("/dashboard")
        self.page.wait_for_timeout(1500)  # animação do Chart.js
        graficos = {g["id"]: g for g in self.page.evaluate(self.JS_GRAFICOS, ["graficoEvolucao", "graficoSkills"])}

        for id_canvas, nome in (("graficoEvolucao", "Gráfico de evolução"), ("graficoSkills", "Gráfico de skills (radar)")):
            g = graficos[id_canvas]
            if not g["existe"]:
                self.registrar("Painel Geral", nome, FALHA, f"<canvas id='{id_canvas}'> não existe.", esperado="Gráfico renderizado no Painel Geral")
                continue
            if not g["biblioteca"] or not g["instancia"]:
                self.registrar("Painel Geral", nome, FALHA, "Chart.js não carregou ou não criou o gráfico.",
                               dica="dashboard.html carrega https://cdn.jsdelivr.net/npm/chart.js sem versão fixa; fixar a versão (ex.: chart.js@4.4.1).")
                continue
            if not mat:
                if self.visivel(f'.grafico-vazio[data-grafico="{id_canvas}"]'):
                    self.registrar("Painel Geral", nome, APROVADO, "Aluno sem matrículas: mensagem de 'sem dados' exibida.", evidencia=False)
                else:
                    self.registrar("Painel Geral", nome, ALERTA, "Aluno sem matrículas: o gráfico aparece vazio, sem mensagem de 'sem dados'.",
                                   esperado="Mensagem amigável quando não há dados para o gráfico")
                continue

            if id_canvas == "graficoEvolucao":
                lido = (g["labels"], g["datasets"][0] if g["datasets"] else [], g["datasets"][1] if len(g["datasets"]) > 1 else [])
                esperado = (meses, horas, concluidos)
                descricao = f"meses {meses}, horas {horas}, concluídos {concluidos}"
            else:
                lido = dict(zip(g["labels"], g["datasets"][0] if g["datasets"] else [], strict=False))
                esperado = radar
                descricao = f"progresso médio por tipo {radar}"

            if lido != esperado:
                self.registrar("Painel Geral", nome, FALHA, f"Dados do gráfico {lido} × banco {esperado}.",
                               esperado=f"Gráfico com {descricao}",
                               dica="Conferir a montagem de evolucao_labels/evolucao_horas/evolucao_cursos e radar_labels/radar_valores em dashboard().")
            elif not g["pintado"] or g["altura"] == 0:
                self.registrar("Painel Geral", nome, FALHA, "Dados corretos, mas o canvas está em branco ou sem altura.")
            else:
                self.registrar("Painel Geral", nome, APROVADO, f"{g['tipo']}: {descricao}.", evidencia=False)

    JS_LINHAS_VISIVEIS = r"""() => Array.from(document.querySelectorAll('#corpoTabelaMatriz tr.linha-matriz'))
        .filter(r => r.style.display !== 'none')
        .map(r => ({ aluno: r.dataset.aluno, curso: r.dataset.curso, carga: Number(r.dataset.carga), progresso: Number(r.dataset.progresso) }))"""

    JS_ORDEM_OK = r"""(ordem) => {
        const l = Array.from(document.querySelectorAll('#corpoTabelaMatriz tr.linha-matriz')).filter(r => r.style.display !== 'none');
        const cmp = {
            curso_az: (a, b) => a.dataset.curso.localeCompare(b.dataset.curso),
            curso_za: (a, b) => b.dataset.curso.localeCompare(a.dataset.curso),
            carga_maior: (a, b) => Number(b.dataset.carga) - Number(a.dataset.carga),
            carga_menor: (a, b) => Number(a.dataset.carga) - Number(b.dataset.carga),
            progresso_maior: (a, b) => Number(b.dataset.progresso) - Number(a.dataset.progresso),
            progresso_menor: (a, b) => Number(a.dataset.progresso) - Number(b.dataset.progresso),
        }[ordem];
        if (!cmp) return true;
        for (let i = 1; i < l.length; i++) { if (cmp(l[i - 1], l[i]) > 0) return false; }
        return true;
    }"""

    def painel_filtro_e_ordenacao(self):
        mat = self.dados_esperados()["matriculas"]
        em_aberto = [m for m in mat if m["status"] not in ("Finalizado", "Desativado")]
        self.visitar("/dashboard")
        linhas = self.page.evaluate(self.JS_LINHAS_VISIVEIS)

        if len(linhas) != len(em_aberto):
            self.registrar("Painel Geral", "Tabela de cursos em andamento", FALHA,
                           f"{len(linhas)} linha(s) na tela × {len(em_aberto)} matrícula(s) em aberto no banco.",
                           esperado="Uma linha por matrícula que não está Finalizada nem Desativada")
        elif not linhas:
            vazio = self.page.locator("#corpoTabelaMatriz td[colspan]").count() > 0
            self.registrar("Painel Geral", "Tabela de cursos em andamento", APROVADO if vazio else ALERTA,
                           "Sem cursos em andamento" + ("; mensagem de tabela vazia exibida." if vazio else " e sem mensagem de tabela vazia."),
                           evidencia=not vazio)
            self.registrar("Painel Geral", "Filtro e ordenação", PULADO,
                           "Sem linhas para filtrar: cadastre ao menos 2 acompanhamentos em andamento para o aluno de teste.", evidencia=False)
            return
        else:
            self.registrar("Painel Geral", "Tabela de cursos em andamento", APROVADO, f"{len(linhas)} linha(s), igual ao banco.", evidencia=False)

        # --- Filtro ---
        busca = self.page.locator("#filtroBusca")
        termo = linhas[0]["curso"][:6]
        busca.fill(termo)
        visiveis = self.page.evaluate(self.JS_LINHAS_VISIVEIS)
        esperado = [linha for linha in linhas if termo in linha["curso"] or termo in linha["aluno"]]
        if len(visiveis) == len(esperado) and all(termo in v["curso"] or termo in v["aluno"] for v in visiveis):
            self.registrar("Painel Geral", "Filtro por texto", APROVADO, f"'{termo}' → {len(visiveis)} linha(s).", evidencia=False)
        else:
            self.registrar("Painel Geral", "Filtro por texto", FALHA, f"'{termo}' devolveu {len(visiveis)} linha(s); esperado {len(esperado)}.",
                           esperado="Mostrar só as linhas cujo aluno ou curso contém o termo")

        busca.fill("zzz-omnitest-sem-resultado")
        if self.page.evaluate(self.JS_LINHAS_VISIVEIS):
            self.registrar("Painel Geral", "Filtro sem resultados", FALHA, "Linhas continuaram visíveis para um termo inexistente.")
        else:
            aviso = self.page.locator("#corpoTabelaMatriz td[colspan]:visible").count() > 0
            self.registrar("Painel Geral", "Filtro sem resultados", APROVADO if aviso else ALERTA,
                           "Tabela esvaziada" + ("" if aviso else ", mas sem mensagem 'nenhum resultado' para o utilizador."),
                           esperado="Mensagem 'Nenhum curso encontrado para o filtro' quando nada corresponde",
                           evidencia=not aviso)
        busca.fill("")
        if len(self.page.evaluate(self.JS_LINHAS_VISIVEIS)) != len(linhas):
            self.registrar("Painel Geral", "Limpar filtro", FALHA, "Ao apagar o texto, nem todas as linhas voltaram.")

        # --- Ordenação ---
        if len(linhas) < 2:
            self.registrar("Painel Geral", "Ordenar por...", PULADO, "Só 1 linha na tabela: cadastre mais acompanhamentos para testar a ordenação.", evidencia=False)
            return
        ordem_original = [linha["curso"] for linha in linhas]
        seletor = self.page.locator("#ordenacaoTabela")
        opcoes = [o for o in seletor.locator("option").evaluate_all("os => os.map(o => [o.value, o.textContent.trim()])") if o[0] != "padrao"]
        erradas = []
        for valor, rotulo in opcoes:
            seletor.select_option(valor)
            if not self.page.evaluate(self.JS_ORDEM_OK, valor):
                erradas.append(rotulo)
        if erradas:
            self.registrar("Painel Geral", "Ordenar por...", FALHA, "Ordem incorreta em: " + ", ".join(erradas),
                           esperado="Cada opção do 'Ordenar por' reordena a tabela pelo critério indicado")
        else:
            self.registrar("Painel Geral", "Ordenar por...", APROVADO, f"{len(opcoes)} opções conferidas.", evidencia=False)

        seletor.select_option("padrao")
        if [linha["curso"] for linha in self.page.evaluate(self.JS_LINHAS_VISIVEIS)] != ordem_original:
            self.registrar("Painel Geral", "Voltar para 'Padrão'", ALERTA, "Escolher 'Padrão' não restaura a ordem original da tabela.",
                           esperado="A opção 'Padrão' devolve a ordem inicial",
                           dica="No script de ordenação de dashboard.html, guardar a ordem inicial das linhas e reaplicá-la quando ordem === 'padrao'.")
        else:
            self.registrar("Painel Geral", "Voltar para 'Padrão'", APROVADO, evidencia=False)

    # --------------------------------------------------------------------------
    # 3. SESSÕES
    # --------------------------------------------------------------------------
    def sessoes_agendadas(self):
        from traducoes import TEXTOS

        sessoes = sorted(self.dados_esperados()["sessoes"])
        agora = datetime.now()
        futuras = [s for s in sessoes if s >= agora]
        self.visitar("/sessoes")
        texto_tabela = " ".join(self.page.locator("table tbody").all_inner_texts())
        datas_tela = re.findall(r"\d{2}/\d{2}/\d{4} às \d{2}:\d{2}", texto_tabela)

        if not sessoes:
            idioma = self.preferencias_atuais()[1]
            aviso = TEXTOS.get(idioma, TEXTOS["pt"]).get("nenhuma_sessao_encontrada", "")
            if aviso and aviso in texto_tabela:
                self.registrar("Sessões", "Sessões agendadas", APROVADO, "O aluno não tem sessões; a mensagem de lista vazia aparece.", evidencia=False)
            else:
                self.registrar("Sessões", "Sessões agendadas", FALHA, "Sem sessões no banco e sem mensagem de lista vazia na tela.")
            return

        faltando = [s.strftime("%d/%m/%Y às %H:%M") for s in sessoes if s.strftime("%d/%m/%Y às %H:%M") not in datas_tela]
        if faltando:
            self.registrar("Sessões", "Sessões agendadas", FALHA, "Sessões do banco ausentes na tela: " + ", ".join(faltando[:5]),
                           esperado="Todas as sessões do aluno listadas")
        elif len(datas_tela) > len(sessoes):
            self.registrar("Sessões", "Sessões agendadas", FALHA, f"{len(datas_tela)} sessões na tela × {len(sessoes)} do aluno no banco (possível vazamento).",
                           esperado="Somente as sessões do próprio aluno")
        else:
            proxima = f"; próxima em {futuras[0].strftime('%d/%m/%Y às %H:%M')}" if futuras else "; nenhuma futura"
            self.registrar("Sessões", "Sessões agendadas", APROVADO, f"{len(sessoes)} sessão(ões), {len(futuras)} agendada(s){proxima}.", evidencia=False)

    # --------------------------------------------------------------------------
    # 4. ACOMPANHAMENTO
    # --------------------------------------------------------------------------
    def acompanhamento_cursos(self):
        cursos = {m["curso"] for m in self.dados_esperados()["matriculas"]}
        self.visitar("/acompanhamento")
        if not cursos:
            self.registrar("Acompanhamento", "Cursos do aluno", PULADO, "O aluno de teste não tem matrículas.", evidencia=False)
            return
        texto = self.texto_pagina()
        faltando = [c for c in cursos if c not in texto]
        if faltando:
            self.registrar("Acompanhamento", "Cursos do aluno", FALHA, "Cursos ausentes: " + ", ".join(faltando),
                           esperado="Um card por curso em que o aluno está matriculado")
        else:
            self.registrar("Acompanhamento", "Cursos do aluno", APROVADO, f"{len(cursos)} curso(s) exibidos.", evidencia=False)

    def acompanhamento_conectar_agenda(self):
        self.visitar("/acompanhamento")
        # A agenda é uma lista (menu) com Google Agenda e Microsoft 365: abre a lista antes de procurar as opções
        lista = self.page.locator('#menuAgenda')
        if lista.count() == 0 or not lista.first.is_visible():
            self.registrar("Acompanhamento", "Lista Agenda (Google / Microsoft 365)", FALHA, "A lista 'Agenda' não está visível.",
                           esperado="Lista Agenda no topo do Acompanhamento")
            return
        lista.first.click()
        botao = self.page.locator('a[href="/conectar-agenda"]')
        microsoft = self.page.locator('#opcaoAgendaMicrosoft')
        if botao.count() == 0 or not botao.first.is_visible() or microsoft.count() == 0 or not microsoft.first.is_visible():
            self.registrar("Acompanhamento", "Lista Agenda (Google / Microsoft 365)", FALHA,
                           "A lista não mostra as duas opções (Google Agenda e Microsoft 365).",
                           esperado="Google Agenda e Microsoft 365 (Outlook) na lista enquanto nenhuma está conectada")
            return
        self.registrar("Acompanhamento", "Lista Agenda (Google / Microsoft 365)", APROVADO, evidencia=False)
        self.page.keyboard.press("Escape")
        # Um só ícone na lista: o ícone do Bootstrap; o texto traduzido não pode repetir o 📅
        texto = lista.first.inner_text()
        icones = lista.first.locator("i.bi").count()
        if "📅" in texto or icones != 1:
            self.registrar("Acompanhamento", "Ícone único no botão Conectar Agenda", FALHA,
                           f"O botão mostra {icones} ícone(s) do Bootstrap e o texto '{texto.strip()}'.",
                           esperado="Um único ícone de calendário antes do texto")
        else:
            self.registrar("Acompanhamento", "Ícone único no botão Conectar Agenda", APROVADO, evidencia=False)

        # 1) O servidor deve redirecionar para o OAuth do Google com o escopo do Calendar
        resposta = self.context.request.get(BASE_URL + "/conectar-agenda", max_redirects=0)
        destino = resposta.headers.get("location", "")
        if resposta.status >= 500 or "accounts.google.com" not in destino:
            self.registrar("Acompanhamento", "Conectar Agenda → OAuth Google", FALHA,
                           f"HTTP {resposta.status}; destino '{destino or 'nenhum'}'.",
                           esperado="Redirecionamento 302 para accounts.google.com",
                           dica="Verificar client_secret.json na raiz do projeto e a rota conectar_agenda em app.py.")
            return
        params = parse_qs(urlparse(destino).query)
        escopo = " ".join(params.get("scope", []))
        redirect_uri = " ".join(params.get("redirect_uri", []))
        problemas = []
        if "calendar" not in escopo:
            problemas.append(f"escopo sem Google Calendar ({escopo or 'vazio'})")
        if not redirect_uri.endswith("/oauth2callback"):
            problemas.append(f"redirect_uri inesperado ({redirect_uri})")
        if not params.get("client_id"):
            problemas.append("client_id ausente")
        if problemas:
            self.registrar("Acompanhamento", "Conectar Agenda → OAuth Google", FALHA, "; ".join(problemas))
            return

        # 2) O Google aceita a configuração? (o agente só lê a página; nunca faz login)
        self.page.goto(destino, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)
        texto = self.texto_pagina()
        erros = [e for e in ("redirect_uri_mismatch", "invalid_client", "invalid_request", "deleted_client", "Erro 400", "Error 400", "Erro 401", "Error 401")
                 if e in texto]
        if erros:
            self.registrar("Acompanhamento", "Conectar Agenda → OAuth Google", FALHA,
                           f"O Google recusou a configuração OAuth: {', '.join(erros)}. redirect_uri={redirect_uri}",
                           esperado="Tela de escolha de conta do Google",
                           dica="Cadastrar exatamente este redirect_uri nas credenciais OAuth do Google Cloud Console (tipo Aplicativo da Web).")
        else:
            self.registrar("Acompanhamento", "Conectar Agenda → OAuth Google", APROVADO,
                           "Google exibiu a tela de login/escolha de conta (o agente não faz login).", evidencia=False)
        self.page.goto(BASE_URL + "/acompanhamento", wait_until="domcontentloaded")

    def acompanhamento_gemini_notebook(self):
        self.visitar("/acompanhamento")
        botao = self.page.locator('button[data-bs-target="#modalNotebookLM"]')
        if botao.count() == 0:
            self.registrar("Acompanhamento", "Gemini Notebook", FALHA, "Botão 'Conectar Gemini Notebook' não encontrado.")
            return
        botao.first.click()
        modal = self.page.locator("#modalNotebookLM")
        try:
            modal.wait_for(state="visible", timeout=5000)
        except Exception:
            self.registrar("Acompanhamento", "Gemini Notebook › abrir", FALHA, "O modal do Gemini Notebook não abriu.")
            return
        self.registrar("Acompanhamento", "Gemini Notebook › abrir", APROVADO, evidencia=False)

        mensagem = 'Olá <b id="omnitest-xss">OmniTest</b>! Responda apenas com a palavra OK.'
        modal.locator("#chat-input").fill(mensagem)
        inicio = datetime.now()
        try:
            with self.page.expect_response(lambda r: r.url.endswith("/chat-ia"), timeout=90000) as info:
                modal.locator("#btn-enviar-chat").click()
            resposta = info.value
            corpo = resposta.json()
        except Exception as e:
            self.registrar("Acompanhamento", "Gemini Notebook › resposta da IA", FALHA,
                           f"Sem resposta de /chat-ia em 90s: {e}",
                           esperado="Resposta do Gemini em poucos segundos",
                           dica="chat_ia() chama o Gemini sem timeout; definir um limite (ex.: request_options={'timeout': 30}) e devolver mensagem amigável ao estourar.")
            return
        segundos = (datetime.now() - inicio).total_seconds()

        texto_ia = str(corpo.get("resposta", ""))
        if resposta.status != 200 or texto_ia.startswith("Desculpe, encontrei um erro"):
            self.registrar("Acompanhamento", "Gemini Notebook › resposta da IA", FALHA, f"HTTP {resposta.status}: {texto_ia[:180]}",
                           esperado="HTTP 200 com a resposta do Gemini no chat",
                           dica="Ver em chat_ia() o nome do modelo passado a genai.GenerativeModel(...) e a chave de API carregada do .env.")
        elif segundos > 20:
            self.registrar("Acompanhamento", "Gemini Notebook › resposta da IA", ALERTA,
                           f"Respondeu, mas demorou {segundos:.0f}s: {texto_ia[:60]}",
                           esperado="Resposta em até 20s, com indicador de 'pensando' visível",
                           dica="Avaliar um modelo mais rápido em chat_ia() ou resposta em streaming.")
        else:
            self.page.wait_for_timeout(500)
            self.registrar("Acompanhamento", "Gemini Notebook › resposta da IA", APROVADO,
                           f"{segundos:.1f}s — resposta: {texto_ia[:70]}", evidencia=False)

        if self.page.locator("#chat-box #omnitest-xss").count():
            self.registrar("Acompanhamento", "Gemini Notebook › segurança do chat", ALERTA,
                           "A mensagem do utilizador é inserida no chat como HTML (a tag <b> de teste foi renderizada): risco de XSS.",
                           esperado="Mensagem do utilizador exibida como texto puro",
                           dica="No script do chat em acompanhamento.html, criar o balão com textContent em vez de innerHTML com ${mensagem}.")
        else:
            self.registrar("Acompanhamento", "Gemini Notebook › segurança do chat", APROVADO, "Mensagem exibida como texto.", evidencia=False)
        self.page.keyboard.press("Escape")

    # --------------------------------------------------------------------------
    # 5. PROJETOS
    # --------------------------------------------------------------------------
    def projetos_do_aluno(self):
        dados = self.dados_esperados()
        self.visitar("/projetos")
        texto = self.texto_pagina()

        if not dados["projetos"]:
            self.registrar("Projetos", "Projeto do aluno", PULADO,
                           "O aluno de teste não pertence a nenhum grupo com projeto: associe-o a um grupo em Administração › Grupos.",
                           evidencia=False)
        else:
            erros = []
            for p in dados["projetos"]:
                if f"Projeto: {p['nome']}" not in texto:
                    erros.append(f"'{p['nome']}' não aparece")
                elif f"Grupo: {p['grupo']}" not in texto:
                    erros.append(f"grupo '{p['grupo']}' não aparece")
                elif f"{p['percentual']}%" not in texto:
                    erros.append(f"progresso {p['percentual']}% de '{p['nome']}' não aparece")
            if erros:
                self.registrar("Projetos", "Projeto do aluno", FALHA, "; ".join(erros),
                               esperado="Card de cada projeto do grupo do aluno com nome, grupo e progresso")
            else:
                nomes = ", ".join(f"{p['nome']} ({p['grupo']}, {p['percentual']}%)" for p in dados["projetos"])
                self.registrar("Projetos", "Projeto do aluno", APROVADO, nomes, evidencia=False)

        alheios = [n for n in dados["outros_projetos"] if f"Projeto: {n}" in texto]
        if alheios:
            self.registrar("Projetos", "Somente projetos do próprio grupo", FALHA, "Projetos de outros grupos visíveis: " + ", ".join(alheios[:5]),
                           esperado="O aluno vê apenas os projetos dos seus grupos (LGPD)")
        else:
            self.registrar("Projetos", "Somente projetos do próprio grupo", APROVADO, evidencia=False)

        if self.page.locator('a[href^="/projetos/banca/"]').count():
            self.registrar("Projetos", "Sem link para a Sala da Banca", FALHA, "O Aluno vê o botão da Sala da Banca (Regra 1).",
                           esperado="Botão da banca oculto para o Aluno")
        else:
            self.registrar("Projetos", "Sem link para a Sala da Banca", APROVADO, evidencia=False)

    def aluno_nao_cadastra_projeto(self):
        """Regra de negócio: o Aluno vê o projeto do seu grupo, mas não cadastra projetos (nem pela tela, nem pela rota)."""
        from models import Projeto
        self.visitar("/projetos")
        if self.page.locator('#cardCadastroProjeto, form[action="/projetos"] input[name="nome"]').count():
            self.registrar("Projetos", "Formulário de cadastro oculto", FALHA, "O Aluno vê o formulário 'Cadastrar Novo Projeto'.",
                           esperado="Formulário de cadastro oculto para o Aluno", arquivos="templates/projetos.html")
        else:
            self.registrar("Projetos", "Formulário de cadastro oculto", APROVADO, evidencia=False)
        nome = f"[OmniTest] Projeto proibido {self.carimbo}"
        grupo = consultar_banco(lambda: (Projeto.query.with_entities(Projeto.grupo_id).filter(Projeto.grupo_id.isnot(None)).first() or [None])[0])
        self.context.request.post(BASE_URL + "/projetos", form={"nome": nome, "descricao": "teste de permissão", "grupo_id": str(grupo or 1)},
                                  max_redirects=0)
        criado = consultar_banco(lambda: Projeto.query.filter_by(nome=nome).first() is not None)
        if criado:
            consultar_banco(lambda: (Projeto.query.filter_by(nome=nome).delete(), __import__("models").db.session.commit()))
            self.registrar("Projetos", "Cadastro bloqueado na rota", FALHA, "🔓 FALHA DE SEGURANÇA: o POST /projetos do Aluno criou um projeto.",
                           esperado="A rota /projetos recusa o cadastro feito pelo Aluno", arquivos="app.py (rota projetos)")
        else:
            self.registrar("Projetos", "Cadastro bloqueado na rota", APROVADO, "POST /projetos recusado.", evidencia=False)

    # --------------------------------------------------------------------------
    # Privacidade
    # --------------------------------------------------------------------------
    def verificar_privacidade(self, caminho, nome_pagina):
        """O Aluno não pode ver o e-mail de outros alunos em nenhuma parte da página."""
        from models import Usuario

        outros = consultar_banco(lambda: [u.email for u in Usuario.query.filter(
            Usuario.tipo_usuario == "Aluno", Usuario.email != self.perfil["email"]).all()])
        if not outros:
            self.registrar(nome_pagina, "Privacidade entre alunos", PULADO, "Não há outros alunos no banco.", evidencia=False)
            return
        self.visitar(caminho)
        html = self.page.content()
        expostos = [e for e in outros if e in html]
        if expostos:
            self.registrar(nome_pagina, "Privacidade entre alunos", FALHA,
                           f"{len(expostos)} e-mail(s) de outros alunos presentes no HTML (ex.: {expostos[0]}).")
        else:
            self.registrar(nome_pagina, "Privacidade entre alunos", APROVADO, "Nenhum dado de outro aluno exposto.", evidencia=False)


if __name__ == "__main__":
    executar_cli(AgenteAluno)
