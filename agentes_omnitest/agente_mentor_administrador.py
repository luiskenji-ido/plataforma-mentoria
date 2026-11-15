"""
AGENTE OMNITEST — PERFIL MENTOR ADMINISTRADOR
Uso: python agentes_omnitest/agente_mentor_administrador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Mentor Administrador. Para rodar todos os perfis use executar_todos.py.
"""
from nucleo import AgenteOmniTest, executar_cli, ROTAS, APROVADO, FALHA, ALERTA


class AgenteMentorAdministrador(AgenteOmniTest):
    chave_perfil = "mentor_administrador"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "todos"

    ROTEIRO = [
        "Cadastros & Usuários: tabela carregada e busca pelo e-mail do próprio utilizador de teste",
        "Solicitações de Mentoria (exclusivo deste perfil): página e filtro por período",
        "Manutenção (DB): oculta no menu, mas confere se a rota abre por URL direta",
        "Painel Geral: KPIs recalculados com todos os alunos da plataforma",
        "Relatório ESG (CSV): uma linha por lançamento, com a empresa de cada colaborador",
        "Relógio de Voluntariado visível e Portal de Demandas como gestor",
        "[--escrita] Ciclo completo de ticket e 1h de voluntariado (apagados no fim)",
    ]

    # Único perfil com acesso às Solicitações de Mentoria
    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "usuarios", "grupos", "demandas", "solicitacoes", "banca",
                        "esg_csv", "esg_pdf", "atividades_extras", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "certificados", "repositorio"]
    # Manutenção (DB) é exclusiva do Administrador (backup, restauração e limpeza)
    ROTAS_BLOQUEADAS = ["banco", "agentes_ia"]
    MENU_VISIVEL = ["indicadores", "agenda_bancas", "avaliadores_banca", "atividades_extras", "reunioes", "dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "usuarios", "demandas", "biblioteca", "solicitacoes"]
    MENU_OCULTO = ["banco"]

    def testes_especificos(self):
        self.etapa("Cadastros & Usuários", "Tabela e busca", self.verificar_cadastros)
        self.etapa("Solicitações de Mentoria", "Filtro por período", self.verificar_filtro_solicitacoes)
        self.etapa("Manutenção (DB)", "Coerência menu × rota", self.verificar_banco_por_url)
        self.etapa("Painel Geral", "KPIs no escopo do perfil", self.verificar_kpis_equipe)
        self.etapa("Exportar ESG (CSV)", "Conteúdo do relatório", self.verificar_relatorio_esg)
        self.etapa("Voluntariado ESG", "Relógio visível", lambda: self.verificar_relogio_voluntariado(deve_existir=True))
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=True))
        if self.escrita:
            def ciclo_ticket():
                titulo = self.abrir_ticket_demanda()
                self.responder_ticket_demanda(titulo)
            self.etapa("Portal de Demandas", "Ciclo completo de ticket (escrita)", ciclo_ticket)

    def verificar_filtro_solicitacoes(self):
        self.visitar("/admin/solicitacoes?data_inicio=2020-01-01&data_fim=2099-12-31")
        if self.caminho_atual() != "/admin/solicitacoes":
            self.registrar("Solicitações de Mentoria", "Filtro por período", FALHA, f"Redirecionado para {self.caminho_atual()}.")
            return
        campos = [c for c in ("data_inicio", "data_fim") if self.page.locator(f'[name="{c}"]').count()]
        if len(campos) == 2:
            self.registrar("Solicitações de Mentoria", "Filtro por período", APROVADO, "Página aceita o filtro de datas.", evidencia=False)
        else:
            self.registrar("Solicitações de Mentoria", "Filtro por período", ALERTA, "Campos de data do filtro não encontrados na página.")
        self.checar_saude("Solicitações de Mentoria", None)

    def verificar_banco_por_url(self):
        """O menu esconde a Manutenção (DB) deste perfil; a rota também tem de negar (esconder não é proteger)."""
        _, bloqueado = self.visitar(ROTAS["banco"]["caminho"])
        if bloqueado:
            self.registrar("Manutenção (DB)", "Coerência menu × rota", APROVADO, "Rota bloqueada, coerente com o menu.", evidencia=False)
        else:
            self.registrar("Manutenção (DB)", "Coerência menu × rota", FALHA,
                           "🔓 A rota abre por URL direta, mas a Manutenção é exclusiva do Administrador.",
                           arquivos="app.py (manutencao_banco)")


if __name__ == "__main__":
    executar_cli(AgenteMentorAdministrador)
