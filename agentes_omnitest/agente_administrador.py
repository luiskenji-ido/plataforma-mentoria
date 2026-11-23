"""
AGENTE OMNITEST — PERFIL ADMINISTRADOR
Uso: python agentes_omnitest/agente_administrador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Administrador. Para rodar todos os perfis use executar_todos.py.
Atenção: na Manutenção (DB) o agente nunca clica em restaurar nem em apagar dados.
Com --escrita ele cria um agendamento de teste, pausa, retoma e exclui (o registro de alterações fica, como auditoria).
"""
from nucleo import AgenteOmniTest, executar_cli, consultar_banco, BASE_URL, APROVADO, FALHA


class AgenteAdministrador(AgenteOmniTest):
    chave_perfil = "administrador"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "todos"

    # Regra 2: o Administrador acede ao Portal de Demandas, à Biblioteca e gere utilizadores
    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "usuarios", "grupos", "demandas", "banco", "banca", "esg_csv", "esg_pdf", "atividades_extras", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "certificados", "repositorio", "agentes_ia"]
    ROTAS_BLOQUEADAS = []
    MENU_VISIVEL = ["agentes_ia", "indicadores", "agenda_bancas", "avaliadores_banca", "atividades_extras", "reunioes", "dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "usuarios", "demandas", "biblioteca", "banco"]
    MENU_OCULTO = []

    ROTEIRO = [
        "Cadastros & Usuários: tabela carregada e busca pelo e-mail do próprio utilizador de teste (Regra 2)",
        "Painel Geral: KPIs recalculados com todos os alunos da plataforma",
        "Relógio de Voluntariado visível e modal de lançamento manual",
        "Portal de Demandas: abrir ticket e responder oficialmente como gestor",
        "Relatório ESG (CSV): uma linha por lançamento, com a empresa de cada colaborador; página de impressão aberta",
        "Manutenção (DB): saúde dos backups, agendamentos, histórico e relatório CSV para auditoria; nunca restaura nem apaga dados",
        "[--escrita] Manutenção (DB): criar, pausar, retomar e excluir um agendamento de backup de teste",
        "[--escrita] Ciclo completo de ticket (abrir e responder) e 1h de voluntariado (apagados no fim)",
    ]

    def testes_especificos(self):
        self.etapa("Cadastros & Usuários", "Tabela e busca", self.verificar_cadastros)
        self.etapa("Painel Geral", "KPIs no escopo do perfil", self.verificar_kpis_equipe)
        self.etapa("Voluntariado ESG", "Relógio visível", lambda: self.verificar_relogio_voluntariado(deve_existir=True))
        self.etapa("Exportar ESG (CSV)", "Conteúdo do relatório", self.verificar_relatorio_esg)
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=True))
        if self.escrita:
            def ciclo_ticket():
                titulo = self.abrir_ticket_demanda()
                self.responder_ticket_demanda(titulo)
            self.etapa("Portal de Demandas", "Ciclo completo de ticket (escrita)", ciclo_ticket)
        self.etapa("Manutenção (DB)", "Painel de backups", self.verificar_painel_backups)
        if self.escrita:
            self.etapa("Manutenção (DB)", "Ciclo de agendamento (escrita)", self.ciclo_agendamento_backup)

    def verificar_painel_backups(self):
        self.visitar("/admin/banco")
        faltando = [nome for nome, sel in (("Saúde dos Backups", "#cardSaude"), ("Agendamentos", "#cardAgendamentos"),
                                           ("Backup imediato", "#cardBackupImediato"), ("Restaurar", "#cardRestaurar"),
                                           ("Histórico", "#cardHistorico"), ("Zona de perigo", "#cardPerigo")) if not self.visivel(sel)]
        if faltando:
            self.registrar("Manutenção (DB)", "Painel de backups", FALHA, "Seções ausentes: " + ", ".join(faltando),
                           arquivos="templates/admin_banco.html")
        else:
            self.registrar("Manutenção (DB)", "Painel de backups", APROVADO, "Saúde, agendamentos, backup, restauração, histórico e zona de perigo.", evidencia=False)
        if self.page.locator("#btnApagarDados").is_disabled():
            self.registrar("Manutenção (DB)", "Zona de perigo travada", APROVADO, "O botão só libera ao digitar APAGAR.", evidencia=False)
        else:
            self.registrar("Manutenção (DB)", "Zona de perigo travada", FALHA, "O botão de apagar os dados já vem liberado.",
                           arquivos="templates/admin_banco.html")
        resposta = self.context.request.get(BASE_URL + "/admin/banco/relatorio/execucoes.csv")
        if resposta.status == 200 and "Data/Hora;Tipo;Status" in resposta.text():
            self.registrar("Manutenção (DB)", "Relatório para auditoria (CSV)", APROVADO, f"{len(resposta.text().splitlines()) - 1} linha(s).", evidencia=False)
        else:
            self.registrar("Manutenção (DB)", "Relatório para auditoria (CSV)", FALHA, f"HTTP {resposta.status}.",
                           arquivos="rotas_backup.py (relatorio_auditoria_backup), backup_servico.py (exportar_historico_csv)")

    def ciclo_agendamento_backup(self):
        """Cria um agendamento de teste pela tela, pausa, retoma e exclui. Confere cada passo no banco."""
        from models import AgendamentoBackup, AlteracaoAgendamentoBackup
        pasta = f"omnitest_{self.carimbo}"[:60]

        def agendamento():
            a = AgendamentoBackup.query.filter_by(pasta=pasta).first()
            return (a.id, a.status) if a else (None, None)

        self.visitar("/admin/banco")
        self.page.locator("#btnNovoAgendamento").click()
        modal = self.page.locator("#modalNovoAgendamento")
        modal.wait_for(state="visible")
        modal.locator('select[name="frequencia"]').select_option("Semanal")
        modal.locator('input[name="retencao"]').fill("3")
        modal.locator('input[name="pasta"]').fill(pasta)
        modal.locator('button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        aid, status = consultar_banco(agendamento)
        if not aid:
            self.registrar("Manutenção (DB)", "Ciclo de agendamento", FALHA, "O agendamento não foi criado.",
                           arquivos="rotas_backup.py (manutencao_banco: novo_agendamento), backup_regras.py (validar_agendamento), templates/admin_banco.html")
            return
        passos = []
        for acao, esperado in (("pausar", "Pausado"), ("retomar", "Ativo")):
            self.visitar("/admin/banco")
            self.page.locator(f'tr[data-bs-target="#modalAgendamento{aid}"]').click()
            self.page.locator(f'#modalAgendamento{aid}').wait_for(state="visible")
            self.page.locator(f'#modalAgendamento{aid} button[form="acao{aid}{acao}"]').click()
            self.page.wait_for_load_state("domcontentloaded")
            passos.append(consultar_banco(agendamento)[1] == esperado)
        self.visitar("/admin/banco")
        self.page.locator(f'tr[data-bs-target="#modalAgendamento{aid}"]').click()
        self.page.locator(f'#modalAgendamento{aid}').wait_for(state="visible")
        self.page.once("dialog", lambda d: d.accept())
        self.page.locator(f'#modalAgendamento{aid} button[form="acao{aid}excluir"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        passos.append(consultar_banco(agendamento)[0] is None)
        acoes = consultar_banco(lambda: {m.acao for m in AlteracaoAgendamentoBackup.query.filter_by(agendamento_id=aid).all()})
        passos.append({"Criado", "Pausado", "Retomado", "Excluído"} <= acoes)
        if all(passos):
            self.registrar("Manutenção (DB)", "Ciclo de agendamento", APROVADO, "Criado, pausado, retomado e excluído, com registro de alterações.", evidencia=False)
        else:
            self.registrar("Manutenção (DB)", "Ciclo de agendamento", FALHA,
                           f"Pausar/retomar/excluir/registro: {passos}; ações registradas: {sorted(acoes)}.",
                           arquivos="rotas_backup.py (manutencao_banco), backup_servico.py (registrar_alteracao), templates/admin_banco.html")


if __name__ == "__main__":
    executar_cli(AgenteAdministrador)
