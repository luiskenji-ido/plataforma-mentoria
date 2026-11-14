"""
AGENTE OMNITEST — PERFIL GESTOR PARCEIRO B2B (tipo_usuario 'Admin B2B')
Uso: python agentes_omnitest/agente_gestor_b2b.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Gestor B2B. Para rodar todos os perfis use executar_todos.py.
O foco de especialista é o isolamento entre empresas (LGPD): o gestor só vê os dados das suas empresas.
"""
from nucleo import AgenteOmniTest, executar_cli, consultar_banco, APROVADO, FALHA, PULADO


class AgenteGestorB2B(AgenteOmniTest):
    chave_perfil = "gestor_b2b"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "empresas"

    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "demandas", "banca", "esg_csv", "esg_pdf"]
    ROTAS_BLOQUEADAS = ["usuarios", "grupos", "solicitacoes", "banco"]
    MENU_VISIVEL = ["dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "demandas", "biblioteca"]
    # 'Cadastros & Usuários' aparece no menu do B2B, mas /admin/usuarios nega o acesso
    MENU_OCULTO = ["usuarios", "solicitacoes", "banco"]

    ROTEIRO = [
        "Hub Educacional: nenhuma empresa de outro gestor aparece (isolamento entre empresas)",
        "Painel Geral: KPIs comparados com os alunos das turmas das empresas deste gestor",
        "Relatório ESG (CSV): só os lançamentos dos mentores das suas empresas, com a empresa de cada um",
        "Relógio de Voluntariado visível e modal de lançamento manual",
        "Portal de Demandas: abrir ticket e responder oficialmente como gestor",
        "[--escrita] Ciclo completo de ticket e 1h de voluntariado (apagados no fim)",
    ]

    def testes_especificos(self):
        self.etapa("Hub Educacional", "Isolamento entre empresas", self.verificar_isolamento_empresas)
        self.etapa("Painel Geral", "KPIs no escopo do perfil", self.verificar_kpis_equipe)
        self.etapa("Voluntariado ESG", "Relógio visível", lambda: self.verificar_relogio_voluntariado(deve_existir=True))
        self.etapa("Exportar ESG (CSV)", "Conteúdo do relatório", self.verificar_relatorio_esg)
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=True))
        if self.escrita:
            def ciclo_ticket():
                titulo = self.abrir_ticket_demanda()
                self.responder_ticket_demanda(titulo)
            self.etapa("Portal de Demandas", "Ciclo completo de ticket (escrita)", ciclo_ticket)

    def verificar_isolamento_empresas(self):
        """O Gestor B2B só pode ver as empresas e turmas em que ele é o gestor."""
        from models import Usuario, Empresa

        def empresas_alheias():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            return [e.nome for e in Empresa.query.filter((Empresa.gestor_id != eu.id) | (Empresa.gestor_id.is_(None))).all()]

        alheias = consultar_banco(empresas_alheias)
        if not alheias:
            self.registrar("Hub Educacional", "Isolamento entre empresas", PULADO, "Não há empresas de outros gestores no banco.", evidencia=False)
            return
        self.visitar("/admin/turmas")
        texto = self.texto_pagina()
        vazadas = [nome for nome in alheias if nome and nome in texto]
        if vazadas:
            self.registrar("Hub Educacional", "Isolamento entre empresas", FALHA,
                           f"{len(vazadas)} empresa(s) de outros gestores visíveis (ex.: {vazadas[0]}).",
                           esperado="Somente as empresas em que este utilizador é o gestor (LGPD)")
        else:
            self.registrar("Hub Educacional", "Isolamento entre empresas", APROVADO,
                           f"Nenhuma das {len(alheias)} empresas de outros gestores aparece.", evidencia=False)


if __name__ == "__main__":
    executar_cli(AgenteGestorB2B)
