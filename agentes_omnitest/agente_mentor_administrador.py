"""
AGENTE OMNITEST — PERFIL MENTOR ADMINISTRADOR
Uso: python agentes_omnitest/agente_mentor_administrador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Mentor Administrador. Para rodar todos os perfis use executar_todos.py.
"""
from nucleo import AgenteOmniTest, executar_cli, ROTAS, APROVADO, FALHA


class AgenteMentorAdministrador(AgenteOmniTest):
    chave_perfil = "mentor_administrador"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "todos"

    ROTEIRO = [
        "Cadastros & Usuários: tabela carregada e busca pelo e-mail do próprio utilizador de teste",
        "Manutenção (DB): oculta no menu, mas confere se a rota abre por URL direta",
        "Painel Geral: KPIs recalculados com todos os alunos da plataforma",
        "Relatório ESG (CSV): uma linha por lançamento, com a empresa de cada colaborador",
        "Relógio de Voluntariado visível e Portal de Demandas como gestor",
        "[--escrita] Ciclo completo de ticket e 1h de voluntariado (apagados no fim)",
    ]

    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "usuarios", "grupos", "demandas", "banca",
                        "esg_csv", "esg_pdf", "atividades_extras", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "certificados", "repositorio"]
    # Manutenção (DB) é exclusiva do Administrador (backup, restauração e limpeza)
    ROTAS_BLOQUEADAS = ["banco", "agentes_ia"]
    MENU_VISIVEL = ["indicadores", "agenda_bancas", "avaliadores_banca", "atividades_extras", "reunioes", "dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "usuarios", "demandas", "biblioteca"]
    MENU_OCULTO = ["banco"]

    def testes_especificos(self):
        self.etapa("Cadastros & Usuários", "Tabela e busca", self.verificar_cadastros)
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

    def verificar_banco_por_url(self):
        """O menu esconde a Manutenção (DB) deste perfil; a rota também tem de negar (esconder não é proteger)."""
        _, bloqueado = self.visitar(ROTAS["banco"]["caminho"])
        if bloqueado:
            self.registrar("Manutenção (DB)", "Coerência menu × rota", APROVADO, "Rota bloqueada, coerente com o menu.", evidencia=False)
        else:
            self.registrar("Manutenção (DB)", "Coerência menu × rota", FALHA,
                           "🔓 A rota abre por URL direta, mas a Manutenção é exclusiva do Administrador.",
                           arquivos="rotas_backup.py (manutencao_banco)")


if __name__ == "__main__":
    executar_cli(AgenteMentorAdministrador)
