"""
AGENTE OMNITEST — PERFIL PROFESSOR
Uso: python agentes_omnitest/agente_professor.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Professor. Para rodar todos os perfis use executar_todos.py.
O roteiro completo (passos comuns + específicos) sai no início da execução e no relatório.
"""
from nucleo import AgenteOmniTest, executar_cli, ROTAS, APROVADO, ALERTA


class AgenteProfessor(AgenteOmniTest):
    chave_perfil = "professor"
    exige_frequencia = True
    exige_onboarding = True
    ESCOPO_ALUNOS = "vinculados"

    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca",
                        "frequencia", "notas", "demandas", "atividades_extras", "certificados", "repositorio"]
    # Reuniões instituição × B2B: só quem participou vê a ata (o perfil de teste não participa de nenhuma)
    ROTAS_BLOQUEADAS = ["hub_educacional", "usuarios", "grupos", "solicitacoes", "banco", "esg_csv", "esg_pdf", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "agentes_ia",
                        # Sala da Banca: só quem está escalado na banca daquele TCC
                        "banca"]
    MENU_VISIVEL = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "demandas", "atividades_extras", "frequencia", "notas"]
    # O Hub Educacional nega o acesso ao Professor, por isso não deveria estar no menu
    MENU_OCULTO = ["hub_educacional", "usuarios", "solicitacoes", "banco"]

    ROTEIRO = [
        "Relógio de Voluntariado visível e modal de lançamento manual com os campos obrigatórios (Regra 4)",
        "Painel Geral: KPIs recalculados só com os alunos vinculados a este perfil",
        "Sessões e Acompanhamento: apenas alunos vinculados nos seletores (isolamento de dados)",
        "Portal de Demandas: pode abrir ticket, não vê a resposta oficial de gestor e encontra o portal pelo menu",
        "[--escrita] Lançar 1h de voluntariado e abrir um ticket (apagados no fim)",
    ]

    def testes_especificos(self):
        self.etapa("Voluntariado ESG", "Relógio visível", lambda: self.verificar_relogio_voluntariado(deve_existir=True))
        self.etapa("Painel Geral", "KPIs no escopo do perfil", self.verificar_kpis_equipe)
        self.etapa("Sessões", "Isolamento de alunos", lambda: self.verificar_isolamento_alunos("/sessoes", "Sessões"))
        self.etapa("Acompanhamento", "Isolamento de alunos", lambda: self.verificar_isolamento_alunos("/acompanhamento", "Acompanhamento"))
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=False))
        self.etapa("Portal de Demandas", "Acesso pelo menu", self.verificar_demandas_no_menu)
        if self.escrita:
            self.etapa("Portal de Demandas", "Abrir ticket (escrita)", self.abrir_ticket_demanda)

    def verificar_demandas_no_menu(self):
        self.visitar("/dashboard")
        if ROTAS["demandas"]["caminho"] in self.links_do_menu():
            self.registrar("Portal de Demandas", "Acesso pelo menu", APROVADO, evidencia=False)
        else:
            self.registrar("Portal de Demandas", "Acesso pelo menu", ALERTA,
                           "O perfil pode abrir tickets, mas o link só existe no menu Administração.",
                           esperado="Link do Portal de Demandas no menu de quem pode usá-lo",
                           arquivos="templates/base.html (navbar #menuPrincipal)", evidencia=False)


if __name__ == "__main__":
    executar_cli(AgenteProfessor)
