# -*- coding: utf-8 -*-
"""
ETAPAS DE COBERTURA — as funções da plataforma que ainda não tinham teste de fim a fim
=====================================================================================
Cada etapa roda dentro do agente do perfil que usa a função de verdade e cobra a regra de negócio dela:
  Administrador ........ perfis de acesso, manutenção do banco, backups padrão, notificações, gráficos do painel,
                         tour, edição de usuário e o pedido público de mentoria
  Mentor Administrador . edição de curso, edição/exclusão de grupo, trilha do TCC, acervo histórico, projeto excluído,
                         Mentor Administrador não altera Administrador
  Professor ............ não mexe em tarefa nem em encaminhamento de reunião de que não participa
  Mentor ............... tarefa (atualizar e excluir), avaliação do projeto, atividade extra, relógio de voluntariado,
                         conclui o encaminhamento da reunião
  Aluno ................ check-in de aula, chat de estudos (sem IA), agenda não conectada, Microsoft 365 e redirecionamento,
                         demandas, recuperação de senha
  Avaliador ............ relógio, perguntas e cronômetro da banca (antes de lançar as notas)
  Encerramento ......... responde a demanda, abona a frequência e reabre o encaminhamento
Tudo o que é criado leva a marca [Funcional] (ou pertence a um usuário *_funcional@local.com) e sai na limpeza;
o que é preferência de uma conta de teste compartilhada volta ao valor de antes.
"""
import json
from datetime import datetime, timedelta, date

from base import MARCA, DOMINIO, FALHA, senha_forte, mensagens

PDF_MINIMO = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
              b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def _m():
    import models
    return models


def _json(texto):
    try:
        return json.loads(texto)
    except (TypeError, ValueError):
        return {}


class EtapasCobertura:
    """Mistura para AgenteDoFluxo: usa self.post, self.cliente, self.banco, self.confere, self.etapa e self.contexto."""

    def post_json(self, caminho, corpo):
        try:
            import app as modulo_app
            self.cobertura.add(modulo_app.app.url_map.bind("localhost").match(caminho.split("?")[0], method="POST")[0])
        except Exception:
            pass
        return self.cliente.pedir("POST", caminho, json_corpo=corpo)

    def _eu(self):
        m = _m()
        return self.banco(lambda: m.Usuario.query.filter_by(email=self.email_logado).first())

    # ==========================================================================================================
    # ADMINISTRADOR
    # ==========================================================================================================
    def cobertura_administrador(self):
        self.perfis_de_acesso_invalidos()
        self.manutencao_do_banco_protegida()
        self.backups_padrao()
        self.notificacoes_e_preferencia()
        self.graficos_do_painel()
        self.tour_desativado()
        self.solicitacao_publica_de_mentoria()
        self.logo_publico_da_instituicao()

    def logo_publico_da_instituicao(self):
        from base import Cliente
        import identidade
        self.etapa("Logo público da instituição")
        tem_logo = bool(self.banco(lambda: identidade._ler_do_banco().get("logo_arquivo")))
        status, _, _ = Cliente().pedir("GET", "/instituicao/logo")
        esperado = 200 if tem_logo else 404
        self.confere(status == esperado, "Logo da instituição responde conforme o cadastro (sem login)", "FLX",
                     f"HTTP {status}: {'logo cadastrado' if tem_logo else 'sem logo cadastrado'}.", f"HTTP {status}; esperado {esperado}.",
                     "Logo da Identidade aparece nas páginas públicas (certificado e acervo)", "Baixa")

    def perfis_de_acesso_invalidos(self):
        m = _m()
        self.etapa("Perfis de acesso: validações do cadastro")
        antes = self.banco(lambda: m.PerfilPersonalizado.query.count())
        self.post("/admin/perfis", {"acao": "salvar", "nome": "", "perfil_base": "Aluno", "ativo": "1"})
        self.post("/admin/perfis", {"acao": "salvar", "nome": "Mentor", "perfil_base": "Mentor", "ativo": "1"})
        self.post("/admin/perfis", {"acao": "salvar", "nome": f"{MARCA} Perfil", "perfil_base": "Perfil inexistente", "ativo": "1"})
        depois = self.banco(lambda: m.PerfilPersonalizado.query.count())
        self.confere(depois == antes, "Perfil sem nome, com nome de perfil do sistema ou base inválida é recusado", "VAL",
                     "Os três cadastros inválidos foram recusados; nenhum perfil criado.", f"Perfis antes {antes}, depois {depois}.",
                     "Perfil personalizado exige nome único e um perfil-base do sistema", "Alta", print_de="/admin/perfis")

    def manutencao_do_banco_protegida(self):
        m = _m()
        self.etapa("Manutenção do banco: ações perigosas protegidas")
        usuarios = self.banco(lambda: m.Usuario.query.count())
        backups = self.banco(lambda: m.RegistroBackup.query.count())
        self.post("/admin/banco", {"acao": "limpar", "confirmacao": "apagar tudo"})
        self.confere(self.banco(lambda: m.Usuario.query.count()) == usuarios and self.banco(lambda: m.RegistroBackup.query.count()) == backups,
                     "Apagar os dados exige digitar APAGAR", "SEG", "Limpeza recusada sem a confirmação; nenhum dado nem backup mexido.",
                     "A limpeza andou sem a confirmação exata.", "Zona de perigo só com a palavra de confirmação", "Crítica",
                     print_de="/admin/banco")
        agendamentos = self.banco(lambda: m.AgendamentoBackup.query.count())
        self.post("/admin/banco", {"acao": "novo_agendamento", "frequencia": "Diário", "horario": "25:00",
                                   "data_inicio": date.today().isoformat(), "retencao": "7", "pasta": "funcional"})
        self.post("/admin/banco", {"acao": "novo_agendamento", "frequencia": "Diário", "horario": "03:00",
                                   "data_inicio": date.today().isoformat(), "retencao": "999", "pasta": "funcional"})
        self.confere(self.banco(lambda: m.AgendamentoBackup.query.count()) == agendamentos, "Agendamento de backup inválido é recusado", "VAL",
                     "Horário 25:00 e retenção 999 recusados.", "Criou agendamento com horário ou retenção inválidos.",
                     "Agendamento com horário HH:MM válido e retenção de 1 a 365", "Média")

    def backups_padrao(self):
        m = _m()
        self.etapa("Backups padrão (Ambiente e compatibilidade)")
        antes = self.banco(lambda: sorted(a.id for a in m.AgendamentoBackup.query.all()))
        self.post("/admin/ambiente/backups-padrao", {})
        depois = self.banco(lambda: sorted((a.id, a.frequencia, a.retencao) for a in m.AgendamentoBackup.query.all()))
        if antes:
            self.confere([d[0] for d in depois] == antes, "Backups padrão não mexem em agendamentos existentes", "REG",
                         f"{len(antes)} agendamento(s) existente(s) mantido(s) sem alteração.", "Os agendamentos existentes mudaram.",
                         "Os padrões só são criados quando não há nenhum agendamento", "Alta", print_de="/admin/ambiente")
            return
        novos = [d for d in depois if d[0] not in antes]
        self.confere(sorted((f, r) for _, f, r in novos) == [("Diário", 7), ("Mensal", 12), ("Semanal", 4)],
                     "Cria os backups padrão Diário (7), Semanal (4) e Mensal (12)", "REG", "Três agendamentos padrão criados.",
                     f"Criados: {novos}.", "Instalação nova ganha os backups padrão", "Alta", print_de="/admin/ambiente")

        def desfazer():  # a instalação de teste volta a não ter agendamentos
            ids = [d[0] for d in novos]
            m.AlteracaoAgendamentoBackup.query.filter(m.AlteracaoAgendamentoBackup.agendamento_id.in_(ids)).delete(synchronize_session=False)
            m.AgendamentoBackup.query.filter(m.AgendamentoBackup.id.in_(ids)).delete(synchronize_session=False)
            m.db.session.commit()
        self.banco(desfazer)

    def notificacoes_e_preferencia(self):
        m = _m()
        self.etapa("Central de notificações e preferência de e-mail")
        eu = self._eu()
        original = bool(eu.receber_email) if eu.receber_email is not None else True
        self.post("/notificacoes", {"acao": "preferencia_email"})
        desligado = self.banco(lambda: m.Usuario.query.get(eu.id).receber_email)
        self.post("/notificacoes", {"acao": "preferencia_email", "receber_email": "1"})
        ligado = self.banco(lambda: m.Usuario.query.get(eu.id).receber_email)
        if not original:
            self.post("/notificacoes", {"acao": "preferencia_email"})
        self.confere(desligado is False and ligado is True, "Pessoa liga e desliga os avisos por e-mail", "FLX",
                     "Preferência gravada nos dois sentidos (e devolvida ao valor de antes).", f"Desligar → {desligado}; ligar → {ligado}.",
                     "Cada pessoa escolhe receber ou não os avisos por e-mail", "Média", print_de="/notificacoes")
        self.post("/notificacoes", {"acao": "marcar_todas"})
        nao_lidas = self.banco(lambda: m.Notificacao.query.filter_by(usuario_id=eu.id, lida=False).count())
        self.confere(nao_lidas == 0, "Marcar todas as notificações como lidas", "FLX", "Nenhuma notificação pendente no sino.",
                     f"{nao_lidas} notificação(ões) continuam não lidas.", "Sino zera ao marcar todas como lidas", "Baixa")

    def graficos_do_painel(self):
        m = _m()
        self.etapa("Gráficos personalizados do Painel Geral")
        eu = self._eu()
        original = eu.preferencias_painel
        status, _, corpo = self.post_json("/painel/graficos", {"graficos": [{"fonte": "inexistente", "tipo": "pizza"}]})
        recusado = status == 400 and self.banco(lambda: m.Usuario.query.get(eu.id).preferencias_painel) == original
        escolha = [{"fonte": "projetos", "tipo": "doughnut", "cor": "#123abc"}]
        status2, _, corpo2 = self.post_json("/painel/graficos", {"graficos": escolha})
        salvo = _json(self.banco(lambda: m.Usuario.query.get(eu.id).preferencias_painel) or "null") or []
        self.confere(recusado and status2 == 200 and salvo and salvo[0]["fonte"] == "projetos" and salvo[0]["cor"] == "#123abc",
                     "Painel guarda só gráficos válidos para o perfil", "VAL",
                     "Fonte inexistente recusada (400); gráfico de projetos com a cor escolhida gravado.",
                     f"Inválido: HTTP {status}; válido: HTTP {status2}, gravado {salvo}.",
                     "Cada pessoa monta o próprio painel com fontes e cores válidas", "Média")
        self.post_json("/painel/graficos", {"restaurar": True})
        restaurado = self.banco(lambda: m.Usuario.query.get(eu.id).preferencias_painel)
        self.confere(restaurado is None, "Restaurar volta ao painel padrão", "FLX", "Preferências apagadas: painel padrão.",
                     f"Ficou: {restaurado}.", "Botão restaurar devolve os gráficos padrão", "Baixa")
        if original:
            def voltar_original():
                m.Usuario.query.get(eu.id).preferencias_painel = original
                m.db.session.commit()
            self.banco(voltar_original)

    def tour_desativado(self):
        m = _m()
        self.etapa("Tour: não mostrar de novo")
        eu = self._eu()
        original = eu.exibir_tour
        status, _, corpo = self.post("/desativar-tour", {}, seguir=False)
        desligado = self.banco(lambda: m.Usuario.query.get(eu.id).exibir_tour)
        self.confere(status == 200 and desligado is False, "Pessoa desliga o convite do tour", "FLX", "O tour não abre mais sozinho.",
                     f"HTTP {status}; exibir_tour = {desligado}.", "Tour pode ser desligado pela própria pessoa", "Baixa")

        def voltar_original():
            m.Usuario.query.get(eu.id).exibir_tour = original
            m.db.session.commit()
        self.banco(voltar_original)

    def edicao_de_usuario(self, papel):
        """Administrador edita um usuário do fluxo: e-mail inválido recusado, nome alterado mantém e-mail e senha."""
        m = _m()
        alvo = self.usuario(papel)
        if not alvo:
            return
        self.etapa("Edição de usuário")
        u = self.banco(lambda: m.Usuario.query.get(alvo["id"]))
        base = {"nome": u.nome, "email": u.email, "tipo_usuario": u.tipo_usuario, "status": "Ativo", "forcar_troca_senha": "False"}
        self.post(f"/admin/usuarios/editar/{u.id}", dict(base, email="sem-arroba"))
        depois = self.banco(lambda: m.Usuario.query.get(u.id).email)
        self.confere(depois == u.email, "Edição recusa e-mail inválido", "VAL", "E-mail mantido.", f"E-mail virou '{depois}'.",
                     "Edição de usuário valida o e-mail", "Alta")
        self.post(f"/admin/usuarios/editar/{u.id}", dict(base, nome=f"{u.nome} (editado)", senha="fraca123"))
        fraca = self.banco(lambda: m.Usuario.query.get(u.id).nome)
        self.post(f"/admin/usuarios/editar/{u.id}", dict(base, nome=f"{u.nome} (editado)"))
        nome = self.banco(lambda: m.Usuario.query.get(u.id).nome)
        self.confere(fraca == u.nome and nome == f"{u.nome} (editado)", "Edição de usuário: senha fraca recusada, nome alterado", "VAL",
                     "Troca para senha fraca recusada; nome atualizado sem mexer no e-mail nem na senha.",
                     f"Com senha fraca: '{fraca}'; depois: '{nome}'.", "Edição aplica a política de senha", "Alta", print_de="/admin/usuarios")

    def solicitacao_publica_de_mentoria(self):
        """Formulário público da tela de login: quem já tem cadastro não pede de novo; e-mail é obrigatório."""
        m = _m()
        from base import Cliente
        self.etapa("Pedido público de mentoria (tela de login)")
        self.cobertura.add("solicitar_mentoria")
        publico = Cliente()
        publico.pedir("GET", "/")
        email_novo = f"interessado_{DOMINIO}"
        publico.pedir("POST", "/solicitar-mentoria", {"nome": f"{MARCA} Interessado", "email": email_novo, "motivo": "Quero participar"})
        criada = self.banco(lambda: m.SolicitacaoMentoria.query.filter_by(email=email_novo).count())
        publico.pedir("POST", "/solicitar-mentoria", {"nome": f"{MARCA} Já cadastrado", "email": self.email_logado, "motivo": "x"})
        duplicada = self.banco(lambda: m.SolicitacaoMentoria.query.filter_by(email=self.email_logado).count())
        publico.pedir("POST", "/solicitar-mentoria", {"nome": f"{MARCA} Sem e-mail", "email": "", "motivo": "x"})
        sem_email = self.banco(lambda: m.SolicitacaoMentoria.query.filter(m.SolicitacaoMentoria.nome == f"{MARCA} Sem e-mail").count())
        self.confere(criada == 1 and duplicada == 0 and sem_email == 0, "Pedido público de mentoria com validação", "VAL",
                     "Pedido novo gravado; e-mail já cadastrado e pedido sem e-mail recusados.",
                     f"Novo: {criada}; e-mail já cadastrado: {duplicada}; sem e-mail: {sem_email}.",
                     "Pedido de mentoria exige e-mail válido e não duplica quem já tem conta", "Média",
                     "Em solicitar_mentoria, exigir nome e e-mail válido antes de gravar.")

    # ==========================================================================================================
    # MENTOR ADMINISTRADOR
    # ==========================================================================================================
    def cobertura_mentor_administrador(self):
        self.edicao_de_curso()
        self.grupos_editar_e_excluir()
        self.nao_altera_administrador()
        self.trilha_do_tcc_gestao()
        self.acervo_historico()
        self.projeto_temporario_excluido()

    def edicao_de_curso(self):
        m = _m()
        cursos = self.contexto["ids"].get("cursos") or []
        if not cursos:
            return
        self.etapa("Edição de curso do catálogo")
        c = self.banco(lambda: m.Curso.query.get(cursos[0]))
        base = {"nome": c.nome_curso, "plataforma": c.plataforma, "tipo": c.tipo, "carga_horaria": str(c.carga_horaria or 20),
                "url": c.url or "https://exemplo.org/curso", "exige_certificado": c.exige_certificado or "Sim", "status": "Ativo"}
        self.post(f"/admin/cursos/editar/{c.id}", dict(base, status="Desativado", motivo_desativacao=""))
        status = self.banco(lambda: m.Curso.query.get(c.id).status)
        self.confere(status == "Ativo", "Desativar curso exige o motivo", "VAL", "Desativação sem motivo recusada.",
                     f"O curso ficou '{status}' sem motivo.", "Desativação de curso registra o motivo (auditoria)", "Média")
        self.post(f"/admin/cursos/editar/{c.id}", dict(base, carga_horaria="24"))
        carga = self.banco(lambda: m.Curso.query.get(c.id).carga_horaria)
        self.confere(carga == 24, "Edita a carga horária do curso", "FLX", "Carga horária 24 h gravada.", f"Carga gravada: {carga}.",
                     "Gestão mantém o catálogo de cursos", "Média", print_de="/admin/turmas")

    def grupos_editar_e_excluir(self):
        m = _m()
        grupo_id = self.contexto["ids"].get("grupo")
        if not grupo_id:
            return
        self.etapa("Grupos: edição e exclusão")
        g = self.banco(lambda: m.Grupo.query.get(grupo_id))
        membros = self.banco(lambda: sorted(x.id for x in m.Grupo.query.get(grupo_id).membros))
        self.post(f"/admin/grupos/editar/{grupo_id}", {"nome": g.nome, "descricao": f"{MARCA} Descrição atualizada", "membros": membros})
        depois = self.banco(lambda: (m.Grupo.query.get(grupo_id).descricao, sorted(x.id for x in m.Grupo.query.get(grupo_id).membros)))
        self.confere(depois == (f"{MARCA} Descrição atualizada", membros), "Edita o grupo mantendo os membros", "FLX",
                     "Descrição atualizada; membros preservados.", f"Gravado: {depois}.", "Gestão edita os grupos de TCC", "Média",
                     print_de="/admin/grupos")
        self.post(f"/admin/grupos/deletar/{grupo_id}", {})
        ainda = self.banco(lambda: m.Grupo.query.get(grupo_id) is not None)
        self.confere(ainda, "Grupo com projeto não pode ser excluído", "REG", "Exclusão recusada: o grupo tem projeto.",
                     "Excluiu um grupo com projeto em andamento.", "Grupo com projeto não é apagado", "Alta")
        self.post("/admin/grupos", {"nome": f"{MARCA} Grupo temporário", "descricao": "Será excluído"})
        temp = self.banco(lambda: m.Grupo.query.filter_by(nome=f"{MARCA} Grupo temporário").first())
        if temp:
            self.post(f"/admin/grupos/deletar/{temp.id}", {})
        sobrou = self.banco(lambda: m.Grupo.query.filter_by(nome=f"{MARCA} Grupo temporário").count())
        self.confere(temp is not None and sobrou == 0, "Exclui um grupo sem projeto", "FLX", "Grupo temporário criado e excluído.",
                     f"Criado: {temp is not None}; restantes: {sobrou}.", "Gestão exclui grupos sem projeto", "Média")

    def nao_altera_administrador(self):
        m = _m()
        self.etapa("Regra: Mentor Administrador não altera contas de Administrador")
        admin = self.banco(lambda: m.Usuario.query.filter_by(email="administrador_ominitest@local.com").first())
        if not admin:
            return
        self.post(f"/admin/usuarios/editar/{admin.id}", {"nome": f"{MARCA} Alterado", "email": admin.email, "tipo_usuario": "Administrador",
                                                         "status": "Bloqueado", "forcar_troca_senha": "False"})
        depois = self.banco(lambda: m.Usuario.query.get(admin.id))
        self.confere(depois.nome == admin.nome and depois.status == admin.status, "Mentor Administrador não altera Administrador", "PER",
                     "Edição da conta de Administrador recusada.", f"A conta do Administrador mudou para '{depois.nome}' / {depois.status}.",
                     "Só o Administrador altera contas de Administrador", "Crítica")

    def trilha_do_tcc_gestao(self):
        m = _m()
        self.etapa("Gestão da trilha do TCC")
        antes = self.banco(lambda: m.ModuloOnboardingTCC.query.count())
        self.post("/onboarding/trilha-tcc/gestao", {"titulo": "", "conteudo_html": "<p>x</p>"})
        vazio = self.banco(lambda: m.ModuloOnboardingTCC.query.count())
        # Módulo criado INATIVO: não vira pendência para os mentores reais
        self.post("/onboarding/trilha-tcc/gestao", {"titulo": f"{MARCA} Módulo de teste", "conteudo_html": "<p>Conteúdo do teste</p>", "ordem": "99"})
        modulo = self.banco(lambda: m.ModuloOnboardingTCC.query.filter_by(titulo=f"{MARCA} Módulo de teste").first())
        self.confere(vazio == antes and modulo is not None and not modulo.ativo, "Gestão cria módulo da trilha (título obrigatório)", "VAL",
                     "Módulo sem título recusado; módulo novo criado inativo.", f"Sem título: {vazio - antes} criado(s); módulo: {bool(modulo)}.",
                     "Trilha do TCC editável pela gestão", "Média", print_de="/onboarding/trilha-tcc/gestao")

    def acervo_historico(self):
        m = _m()
        self.etapa("Acervo: importação de TCC histórico")
        antes = self.banco(lambda: m.TCCAcervo.query.count())
        self.post("/biblioteca", {"acao": "importar_historico", "titulo": ""}, {"arquivo_pdf": ("historico.pdf", PDF_MINIMO)})
        self.post("/biblioteca", {"acao": "importar_historico", "titulo": f"{MARCA} TCC sem PDF"}, {"arquivo_pdf": ("historico.txt", b"texto")})
        recusados = self.banco(lambda: m.TCCAcervo.query.count()) == antes
        self.post("/biblioteca", {"acao": "importar_historico", "titulo": f"{MARCA} TCC histórico", "ano_edicao": "2024",
                                  "autores_exibicao": "Turma 2024"}, {"arquivo_pdf": ("historico.pdf", PDF_MINIMO)})
        item = self.banco(lambda: m.TCCAcervo.query.filter_by(titulo=f"{MARCA} TCC histórico").first())
        self.confere(recusados and item is not None and item.origem == "Histórico", "Importa TCC histórico para o acervo", "VAL",
                     "Sem título ou sem PDF recusados; histórico com PDF importado.",
                     f"Recusas ok: {recusados}; importado: {bool(item)}.", "Acervo recebe TCCs de edições anteriores", "Média",
                     print_de="/biblioteca")

    def projeto_temporario_excluido(self):
        m = _m()
        grupo_id = self.contexto["ids"].get("grupo")
        if not grupo_id:
            return
        self.etapa("Exclusão de projeto com tarefas")
        self.post("/projetos", {"nome": f"{MARCA} Projeto temporário", "descricao": "Será excluído", "grupo_id": grupo_id})
        projeto = self.banco(lambda: m.Projeto.query.filter_by(nome=f"{MARCA} Projeto temporário").first())
        if not projeto:
            self.registrar("Projeto temporário não criado", FALHA, "FLX", "Sem projeto para excluir.", "Projeto criado", "Média")
            return
        self.post("/projetos/nova_tarefa", {"projeto_id": projeto.id, "descricao": f"{MARCA} Tarefa temporária", "status": "Pendente"})
        self.post(f"/projetos/deletar_projeto/{projeto.id}", {})
        restos = self.banco(lambda: (m.Projeto.query.get(projeto.id) is not None, m.Tarefa.query.filter_by(projeto_id=projeto.id).count()))
        self.confere(restos == (False, 0), "Exclui o projeto e as tarefas dele", "FLX", "Projeto e tarefas apagados.",
                     f"Projeto ainda existe: {restos[0]}; tarefas restantes: {restos[1]}.", "Exclusão de projeto não deixa tarefas órfãs", "Média")

    # ==========================================================================================================
    # PROFESSOR (fora do grupo e da reunião)
    # ==========================================================================================================
    def cobertura_professor(self):
        m = _m()
        tarefa_id = self.contexto["ids"].get("tarefa")
        if tarefa_id:
            self.etapa("Regra: Professor fora do grupo não mexe nas tarefas")
            self.post(f"/projetos/deletar_tarefa/{tarefa_id}", {})
            self.post("/projetos/atualizar_tarefa", {"tarefa_id": tarefa_id, "descricao": f"{MARCA} Alterada pelo professor", "status": "Concluída"})
            t = self.banco(lambda: m.Tarefa.query.get(tarefa_id))
            self.confere(t is not None and "Alterada pelo professor" not in (t.descricao or ""), "Professor fora do grupo não altera nem exclui tarefa",
                         "PER", "Exclusão e alteração recusadas.", "O Professor fora do grupo alterou ou excluiu a tarefa.",
                         "Só o grupo do projeto e a gestão mexem nas tarefas", "Alta")
        enc_id = self.contexto["ids"].get("encaminhamento")
        reuniao_id = self.contexto["ids"].get("reuniao")
        if enc_id and reuniao_id:
            self.post(f"/reunioes/{reuniao_id}", {"encaminhamento_id": enc_id})
            status = self.banco(lambda: m.EncaminhamentoReuniao.query.get(enc_id).status)
            self.confere(status == "Pendente", "Quem não participou não conclui encaminhamento da reunião", "PER", "Alteração recusada.",
                         f"O encaminhamento ficou '{status}'.", "Só o responsável e a gestão concluem encaminhamentos", "Alta")

    # ==========================================================================================================
    # MENTOR
    # ==========================================================================================================
    def cobertura_mentor(self):
        self.tarefa_atualizar_e_excluir()
        self.avaliacao_do_projeto()
        self.atividade_extra()
        self.relogio_de_voluntariado()
        self.encaminhamento_concluido()
        self.trilha_sem_modulo_inativo()

    def trilha_sem_modulo_inativo(self):
        self.etapa("Trilha do TCC: módulo inativo não aparece")
        status, _, pagina = self.cliente.pedir("GET", "/onboarding/trilha-tcc")
        self.confere(status == 200 and f"{MARCA} Módulo de teste" not in pagina, "Trilha mostra só módulos ativos", "REG",
                     "Trilha aberta; o módulo inativo criado pela gestão não aparece.",
                     f"HTTP {status}; módulo inativo visível: {f'{MARCA} Módulo de teste' in pagina}.",
                     "Só módulos ativos entram na trilha dos mentores", "Média", print_de="/onboarding/trilha-tcc")

    def tarefa_atualizar_e_excluir(self):
        m = _m()
        tarefa_id, projeto_id = self.contexto["ids"].get("tarefa"), self.contexto["ids"].get("projeto")
        if not (tarefa_id and projeto_id):
            return
        self.etapa("Tarefas do projeto: atualização e exclusão")
        t = self.banco(lambda: m.Tarefa.query.get(tarefa_id))
        hoje = date.today()
        base = {"tarefa_id": tarefa_id, "descricao": t.descricao, "responsavel": t.responsavel or "Aluno Um",
                "data_inicio": hoje.isoformat(), "data_fim": (hoje + timedelta(days=7)).isoformat()}
        self.post("/projetos/atualizar_tarefa", dict(base, status="Em Andamento", percentual_conclusao="50"))
        gravada = self.banco(lambda: m.Tarefa.query.get(tarefa_id))
        self.confere(gravada.status == "Em Andamento" and gravada.percentual_conclusao == 50, "Atualiza status e progresso da tarefa", "FLX",
                     "Tarefa em andamento com 50%.", f"Gravado: {gravada.status} / {gravada.percentual_conclusao}%.",
                     "Mentor acompanha o andamento das tarefas", "Média", print_de="/projetos")
        self.post("/projetos/atualizar_tarefa", dict(base, status="Em Andamento", percentual_conclusao="150"))
        fora = self.banco(lambda: m.Tarefa.query.get(tarefa_id).percentual_conclusao)
        self.confere(fora == 50, "Progresso da tarefa fora de 0 a 100% é recusado", "VAL", "150% recusado; 50% mantido.",
                     f"Aceitou {fora}%.", "Progresso entre 0 e 100%", "Média",
                     "Em atualizar_tarefa, validar 0 <= percentual_conclusao <= 100.")
        self.post("/projetos/nova_tarefa", {"projeto_id": projeto_id, "descricao": f"{MARCA} Tarefa a excluir", "status": "Pendente"})
        extra = self.banco(lambda: m.Tarefa.query.filter_by(descricao=f"{MARCA} Tarefa a excluir").first())
        if extra:
            self.post(f"/projetos/deletar_tarefa/{extra.id}", {})
        self.confere(extra is not None and self.banco(lambda: m.Tarefa.query.get(extra.id)) is None, "Exclui uma tarefa do projeto", "FLX",
                     "Tarefa criada e excluída.", "Tarefa não criada ou não excluída.", "Grupo e gestão excluem tarefas", "Média")

    def avaliacao_do_projeto(self):
        m = _m()
        projeto_id, aluno1 = self.contexto["ids"].get("projeto"), self.usuario("aluno1")
        if not (projeto_id and aluno1):
            return
        self.etapa("Avaliação do projeto pelo mentor")
        self.post(f"/projetos/avaliar/{projeto_id}", {"nota_conteudo": "8", "nota_apresentacao": "9",
                                                      f"nota_postura_{aluno1['id']}": "8", f"nota_dominio_{aluno1['id']}": "9",
                                                      f"obs_mentor_{aluno1['id']}": f"{MARCA} Boa evolução"})
        p = self.banco(lambda: m.Projeto.query.get(projeto_id))
        ind = self.banco(lambda: m.AvaliacaoProjeto.query.filter_by(projeto_id=projeto_id, aluno_id=aluno1["id"]).first())
        self.confere(p.nota_conteudo == 8 and p.nota_apresentacao == 9 and ind is not None and ind.nota_dominio == 9,
                     "Mentor avalia o projeto (notas do grupo e individuais)", "FLX", "Notas do grupo e do aluno gravadas.",
                     f"Grupo {p.nota_conteudo}/{p.nota_apresentacao}; aluno {ind.nota_dominio if ind else None}.",
                     "Mentor registra notas do grupo e de cada jovem", "Alta", print_de="/projetos")
        self.post(f"/projetos/avaliar/{projeto_id}", {"nota_conteudo": "15", f"nota_dominio_{aluno1['id']}": "-3"})
        p2 = self.banco(lambda: m.Projeto.query.get(projeto_id))
        ind2 = self.banco(lambda: m.AvaliacaoProjeto.query.filter_by(projeto_id=projeto_id, aluno_id=aluno1["id"]).first())
        self.confere(p2.nota_conteudo == 8 and ind2.nota_dominio == 9, "Notas do projeto fora de 0 a 10 são recusadas", "VAL",
                     "Nota 15 e nota -3 recusadas; notas anteriores mantidas.",
                     f"Gravado: conteúdo {p2.nota_conteudo}, domínio {ind2.nota_dominio}.", "Notas entre 0 e 10", "Alta",
                     "Em avaliar_projeto, validar 0 <= nota <= 10 antes de gravar.")

    def atividade_extra(self):
        m = _m()
        grupo_id = self.contexto["ids"].get("grupo")
        if not grupo_id:
            return
        self.etapa("Atividade extra do grupo (check-in, check-out, encerrar e cancelar)")
        agora = datetime.now()
        base = {"grupo_id": grupo_id, "titulo": f"{MARCA} Reforço de metodologia", "data_hora_inicio": agora.strftime("%Y-%m-%dT%H:%M"),
                "duracao_prevista_min": "60", "modalidade": "Online"}
        self.post("/atividades-extras/nova", dict(base, motivo="curto"))
        curta = self.banco(lambda: m.AtividadeExtra.query.filter_by(titulo=base["titulo"]).count())
        self.post("/atividades-extras/nova", dict(base, motivo="Reforço da metodologia antes da banca do TCC"))
        a = self.banco(lambda: m.AtividadeExtra.query.filter_by(titulo=base["titulo"]).first())
        self.confere(curta == 0 and a is not None and a.status == "Agendada", "Cria atividade extra com motivo", "VAL",
                     "Motivo curto recusado; atividade agendada e o grupo avisado.", f"Com motivo curto: {curta}; criada: {bool(a)}.",
                     "Atividade fora do cronograma exige motivo (10+ caracteres)", "Média", print_de="/atividades-extras")
        if not a:
            return
        self.contexto["ids"]["atividade_extra"] = a.id
        eu = self._eu()
        self.post(f"/atividades-extras/{a.id}/checkin", {"modalidade": "Online"})
        self.post(f"/atividades-extras/{a.id}/checkout", {})
        presenca = self.banco(lambda: m.PresencaAtividadeExtra.query.filter_by(atividade_id=a.id, usuario_id=eu.id).first())
        self.confere(presenca is not None and presenca.check_out is not None, "Check-in e check-out na atividade extra", "FLX",
                     f"Presença registrada ({presenca.total_minutos if presenca else 0} min).", "Presença não registrada.",
                     "Presença real nas atividades extras (horas ESG)", "Alta")
        self.post(f"/atividades-extras/{a.id}/encerrar", {})
        self.confere(self.banco(lambda: m.AtividadeExtra.query.get(a.id).status) == "Encerrada", "Encerra a atividade extra", "FLX",
                     "Atividade encerrada.", "Atividade não encerrada.", "Quem criou encerra a atividade", "Média")
        self.post("/atividades-extras/nova", dict(base, titulo=f"{MARCA} Atividade cancelada", motivo="Encontro extra que será cancelado",
                                                  data_hora_inicio=(agora + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")))
        c = self.banco(lambda: m.AtividadeExtra.query.filter_by(titulo=f"{MARCA} Atividade cancelada").first())
        if c:
            self.post(f"/atividades-extras/{c.id}/checkin", {})
            cedo = self.banco(lambda: m.PresencaAtividadeExtra.query.filter_by(atividade_id=c.id).count())
            self.post(f"/atividades-extras/{c.id}/cancelar", {})
            self.confere(cedo == 0 and self.banco(lambda: m.AtividadeExtra.query.get(c.id).status) == "Cancelada",
                         "Check-in antecipado recusado e atividade cancelada", "REG",
                         "Check-in 2 dias antes recusado (abre 30 min antes); atividade cancelada.",
                         f"Check-ins antecipados: {cedo}.", "Check-in só a partir de 30 min antes do início", "Média")

    def relogio_de_voluntariado(self):
        m = _m()
        grupo_id = self.contexto["ids"].get("grupo")
        eu = self._eu()
        if self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).count()):
            self.log("Já existe relógio aberto: etapa do relógio pulada")
            return
        self.etapa("Relógio de voluntariado (check-in e check-out)")
        self.post("/voluntariado/ponto", {"tipo_atividade": "Mentoria Extraordinária"})
        sem_grupo = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).count())
        self.post("/voluntariado/ponto", {"tipo_atividade": "Mentoria Extraordinária", "grupo_id": grupo_id,
                                          "observacoes": "Reforço extra com o grupo do TCC"})
        aberto = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).first())
        self.post("/voluntariado/ponto", {})
        fechado = self.banco(lambda: m.CheckinVoluntariado.query.get(aberto.id) if aberto else None)
        self.confere(sem_grupo == 0 and aberto is not None and fechado.data_hora_fim is not None and aberto.categoria == "Extra",
                     "Relógio de voluntariado: mentoria extra exige grupo e motivo", "REG",
                     "Sem grupo recusado; relógio ligado e desligado; hora classificada como Extra.",
                     f"Sem grupo: {sem_grupo}; aberto: {bool(aberto)}; categoria: {aberto.categoria if aberto else None}.",
                     "Mentoria extraordinária exige grupo e motivo e conta como hora Extra", "Alta", print_de="/dashboard")

    def encaminhamento_concluido(self):
        m = _m()
        enc_id, reuniao_id = self.contexto["ids"].get("encaminhamento"), self.contexto["ids"].get("reuniao")
        if not (enc_id and reuniao_id):
            return
        self.etapa("Encaminhamento da reunião: o responsável conclui")
        self.post(f"/reunioes/{reuniao_id}", {"encaminhamento_id": enc_id})
        status = self.banco(lambda: m.EncaminhamentoReuniao.query.get(enc_id).status)
        self.confere(status == "Concluído", "Responsável conclui o encaminhamento da reunião", "FLX", "Encaminhamento concluído.",
                     f"Status: {status}.", "Responsável marca o encaminhamento como concluído", "Média", print_de=f"/reunioes/{reuniao_id}")

    # ==========================================================================================================
    # ALUNO
    # ==========================================================================================================
    def cobertura_aluno(self):
        self.checkin_de_aula()
        self.chat_de_estudos()
        self.agenda_nao_conectada()
        self.redirecionamento_seguro()
        self.demanda_do_aluno()
        self.atividade_extra_encerrada()

    def checkin_de_aula(self):
        m = _m()
        cursos = self.contexto["ids"].get("cursos") or []
        eu = self._eu()
        if not cursos:
            return
        self.etapa("Check-in de aula")
        self.post("/acompanhamento/checkin", {"curso_id": cursos[0]})
        self.post("/acompanhamento/checkin", {"curso_id": cursos[0]})
        meus = self.banco(lambda: m.CheckinAula.query.filter_by(usuario_id=eu.id, curso_id=cursos[0]).count())
        alheio = self.banco(lambda: m.Curso.query.filter(~m.Curso.id.in_(cursos)).first())
        indevido = 0
        if alheio:
            self.post("/acompanhamento/checkin", {"curso_id": alheio.id})
            indevido = self.banco(lambda: m.CheckinAula.query.filter_by(usuario_id=eu.id, curso_id=alheio.id).count())
        self.confere(meus == 1 and indevido == 0, "Check-in de aula: um por dia e só nos cursos do aluno", "REG",
                     "Check-in registrado uma vez; curso em que não está matriculado recusado.",
                     f"Check-ins no curso: {meus}; em curso alheio: {indevido}.", "Check-in só nos cursos matriculados, um por dia", "Alta",
                     "Em fazer_checkin_aula, conferir se o aluno tem acompanhamento do curso.")

    def chat_de_estudos(self):
        m = _m()
        self.etapa("Assistente de estudos (sem consumir a IA)")
        usos = self.banco(lambda: m.UsoIA.query.count())
        status, _, corpo = self.post_json("/chat-ia", {"mensagem": "Me ajude a revisar o capítulo 1"})
        resposta = _json(corpo).get("resposta", "")
        self.confere(status in (200, 503) and resposta and self.banco(lambda: m.UsoIA.query.count()) == usos,
                     "Chat de estudos responde sem gastar IA com conta de teste", "REG",
                     f"Resposta: '{resposta[:80]}' (nenhuma chamada registrada).", f"HTTP {status}; resposta '{resposta[:80]}'.",
                     "Contas de teste nunca consomem a IA", "Alta")

    def agenda_nao_conectada(self):
        m = _m()
        eu = self._eu()
        self.etapa("Agenda não conectada: nada é enviado ao Google ou à Microsoft")
        acomp = self.banco(lambda: m.Acompanhamento.query.filter_by(aluno_id=eu.id).first())
        sessao_id = self.contexto["ids"].get("sessao")
        avisos = []
        if acomp:
            _, _, html = self.post(f"/acompanhamento/sincronizar_agenda/{acomp.id}", {})
            avisos.append(any("Conecte sua agenda" in x for x in mensagens(html)))
        if sessao_id:
            _, _, html = self.post(f"/sessoes/sincronizar_aluno/{sessao_id}", {})
            avisos.append(any("Conecte sua agenda" in x for x in mensagens(html)))
        self.confere(avisos and all(avisos), "Sincronizar sem agenda conectada orienta a conectar", "REG",
                     f"{len(avisos)} tentativa(s) recusada(s) com a orientação, sem contato externo.",
                     f"Orientação exibida: {avisos}.", "Agenda só sincroniza com Google ou Microsoft 365 conectado", "Média")

    def redirecionamento_seguro(self):
        self.etapa("Microsoft 365: desconectar e redirecionamento seguro")
        _, destino, _ = self.post("/desconectar-microsoft", {"voltar": "https://exemplo-malicioso.test/roubo"}, seguir=False)
        self.confere(destino and destino != "/roubo", "Desconectar não redireciona para site externo", "SEG",
                     f"Voltou para {destino} (endereço externo ignorado).", f"Redirecionou para {destino}.",
                     "Nenhum 'voltar' leva para fora da plataforma (open redirect)", "Alta")

    def demanda_do_aluno(self):
        m = _m()
        eu = self._eu()
        self.etapa("Portal de demandas: o aluno abre e acompanha o chamado")
        self.post("/demandas", {"acao": "nova_demanda", "titulo": "", "tipo_demanda": "Dúvida", "prioridade": "Média",
                                "descricao": f"{MARCA} Sem título"})
        sem_titulo = self.banco(lambda: m.DemandaInstitucional.query.filter_by(descricao=f"{MARCA} Sem título").count())
        titulo = f"{MARCA} Dúvida sobre a banca"
        self.post("/demandas", {"acao": "nova_demanda", "titulo": titulo, "tipo_demanda": "Dúvida", "prioridade": "Média",
                                "descricao": "Qual o tempo da apresentação?"})
        d = self.banco(lambda: m.DemandaInstitucional.query.filter_by(titulo=titulo).first())
        self.confere(sem_titulo == 0 and d is not None and d.status == "Aberta" and d.autor_id == eu.id, "Aluno abre chamado (título obrigatório)",
                     "VAL", "Chamado sem título recusado; chamado aberto e a gestão avisada.",
                     f"Sem título gravado: {sem_titulo}; chamado: {bool(d)}.", "Canal oficial de demandas para todos os perfis", "Média",
                     "Em portal_demandas (nova_demanda), exigir título e descrição.", print_de="/demandas")
        if not d:
            return
        self.contexto["ids"]["demanda"] = d.id
        self.post("/demandas", {"acao": "comentar_demanda", "demanda_id": d.id, "texto": f"{MARCA} Complemento da dúvida"})
        self.post("/demandas", {"acao": "responder_demanda", "demanda_id": d.id, "resposta_oficial": "Respondida pelo aluno", "status": "Resolvida"})
        d2 = self.banco(lambda: m.DemandaInstitucional.query.get(d.id))
        comentarios = self.banco(lambda: m.ComentarioDemanda.query.filter_by(demanda_id=d.id).count())
        self.confere(comentarios == 1 and d2.status == "Aberta" and not d2.resposta_oficial, "Aluno comenta, mas não responde oficialmente", "PER",
                     "Comentário gravado; resposta oficial recusada.", f"Comentários {comentarios}; status {d2.status}.",
                     "Só a gestão responde oficialmente os chamados", "Alta")

    def atividade_extra_encerrada(self):
        m = _m()
        a_id = self.contexto["ids"].get("atividade_extra")
        if not a_id:
            return
        eu = self._eu()
        self.post(f"/atividades-extras/{a_id}/checkin", {})
        self.confere(self.banco(lambda: m.PresencaAtividadeExtra.query.filter_by(atividade_id=a_id, usuario_id=eu.id).count()) == 0,
                     "Atividade extra encerrada não aceita check-in", "REG", "Check-in recusado.", "Registrou presença numa atividade encerrada.",
                     "Presença só em atividade agendada ou em andamento", "Média")

    def recuperacao_de_senha(self, papel):
        """No fim do agente: recupera a senha pelas perguntas de segurança (2 de 3) e entra com a nova."""
        m = _m()
        from base import Cliente
        eu = self.usuario(papel)
        self.etapa("Recuperação de senha pelas perguntas de segurança")
        self.cobertura.add("recuperar_senha")
        c = Cliente()
        c.pedir("GET", "/")
        _, _, pagina = c.pedir("POST", "/recuperar-senha", {"email_recuperacao": eu["email"]})
        _, errado, _ = c.pedir("POST", "/recuperar-senha", {"email_recuperacao": eu["email"], "resposta_1": "verde",
                                                             "resposta_2": "recife", "resposta_3": "feijoada"})
        _, certo, _ = c.pedir("POST", "/recuperar-senha", {"email_recuperacao": eu["email"], "resposta_1": "Azul ",
                                                            "resposta_2": "santos", "resposta_3": "pizza"})
        nova = senha_forte()
        c.pedir("POST", "/trocar-senha", {"nova_senha": nova})
        d = Cliente()
        d.pedir("GET", "/")
        _, entrou, _ = d.pedir("POST", "/", {"email": eu["email"], "senha": nova})
        self.confere("Qual é a sua cor favorita?" in pagina and errado == "/" and certo == "/trocar-senha" and entrou not in (None, "/"),
                     "Recupera a senha acertando 2 de 3 perguntas", "REG",
                     "1 acerto recusado; 2 acertos levam à troca de senha; a nova senha entra.",
                     f"Perguntas na tela: {'Qual é a sua cor favorita?' in pagina}; 1 acerto → {errado}; 2 acertos → {certo}; login novo → {entrou}.",
                     "Recuperação exige 2 de 3 respostas e obriga a criar senha nova", "Alta")
        if entrou not in (None, "/"):
            eu["senha"] = nova

    # ==========================================================================================================
    # AVALIADOR (antes de lançar as notas: depois a banca fecha)
    # ==========================================================================================================
    def cobertura_avaliador(self):
        m = _m()
        banca_id = self.contexto["ids"].get("banca")
        if not banca_id:
            return
        eu = self._eu()
        self.etapa("Relógio do avaliador ligado ao TCC")
        self.post(f"/bancas/{banca_id}/relogio/iniciar_leitura", {})
        aberto = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).first())
        self.post(f"/bancas/{banca_id}/relogio/iniciar_analise", {})
        abertos = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).count())
        self.post(f"/bancas/{banca_id}/relogio/encerrar", {})
        fechado = self.banco(lambda: m.CheckinVoluntariado.query.get(aberto.id) if aberto else None)
        self.post(f"/bancas/{banca_id}/relogio/checkin_banca", {})
        fora = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu.id, data_hora_fim=None).count())
        self.confere(aberto is not None and aberto.tipo_atividade == "Leitura Assíncrona de TCC" and abertos == 1
                     and fechado.data_hora_fim is not None and fora == 0,
                     "Relógio da banca: um por vez e check-in só na janela da banca", "REG",
                     "Leitura iniciada e encerrada; segunda contagem recusada; check-in ao vivo fora da janela recusado.",
                     f"Aberto: {bool(aberto)}; simultâneos: {abertos}; fora da janela abertos: {fora}.",
                     "Horas do avaliador ligadas ao TCC, um relógio por vez", "Alta", print_de="/minhas-bancas")

        self.etapa("Perguntas da banca")
        status_vazio, _, _ = self.post(f"/bancas/{banca_id}/perguntas", {"acao": "adicionar", "pergunta": ""})
        pergunta = f"{MARCA} Por que escolheram esse tema?"
        _, _, corpo = self.post(f"/bancas/{banca_id}/perguntas", {"acao": "adicionar", "pergunta": pergunta, "resposta": "Relevância social"})
        lista = _json(corpo).get("perguntas", [])
        minha = next((p for p in lista if p["pergunta"] == pergunta), None)
        if minha:
            self.post(f"/bancas/{banca_id}/perguntas", {"acao": "editar", "id": minha["id"], "pergunta": pergunta,
                                                        "resposta": "Relevância social e dados públicos"})
        resposta = self.banco(lambda: m.QABanca.query.get(minha["id"]).resposta_jovens if minha else None)
        self.confere(status_vazio == 400 and minha is not None and resposta == "Relevância social e dados públicos",
                     "Registra e edita as perguntas da banca", "FLX", "Pergunta vazia recusada (400); pergunta gravada e resposta editada.",
                     f"Vazia: HTTP {status_vazio}; gravada: {bool(minha)}; resposta: {resposta}.", "Perguntas da banca e respostas dos jovens", "Média")

        self.etapa("Cronômetro da apresentação")
        for acao in ("iniciar_apresentacao", "pausar", "retomar", "encerrar_fase"):
            self.post(f"/bancas/{banca_id}/cronometro", {"acao": acao})
        b = self.banco(lambda: m.Banca.query.get(banca_id))
        self.confere(b.tempo_real_apresentacao_seg is not None and b.cron_fase is None, "Cronômetro: inicia, pausa, retoma e encerra a fase", "FLX",
                     f"Tempo real da apresentação registrado ({b.tempo_real_apresentacao_seg} s).", "Tempo real não registrado.",
                     "Cronômetro em duas fases sincronizado entre sala e telão", "Média")

    # ==========================================================================================================
    # ENCERRAMENTO (Mentor Administrador)
    # ==========================================================================================================
    def cobertura_encerramento(self):
        m = _m()
        demanda_id = self.contexto["ids"].get("demanda")
        aluno1 = self.usuario("aluno1")
        from base import Cliente
        self.etapa("Repositório público de TCCs")
        status, _, pagina = Cliente().pedir("GET", "/repositorio")
        self.confere(status == 200 and f"{MARCA} Projeto TCC" not in pagina, "Repositório público não mostra TCC interno", "SEG",
                     "Repositório aberto sem login; o TCC sem autorização (Interna) não aparece.",
                     f"HTTP {status}; TCC interno visível: {f'{MARCA} Projeto TCC' in pagina}.",
                     "Só TCCs públicos e autorizados vão para o repositório aberto (LGPD)", "Crítica")
        if demanda_id:
            self.etapa("Resposta oficial à demanda")
            self.post("/demandas", {"acao": "responder_demanda", "demanda_id": demanda_id,
                                    "resposta_oficial": f"{MARCA} São 15 minutos de apresentação.", "status": "Resolvida"})
            d = self.banco(lambda: m.DemandaInstitucional.query.get(demanda_id))
            aviso = self.banco(lambda: m.Notificacao.query.filter(m.Notificacao.usuario_id == aluno1["id"], m.Notificacao.tipo == "demanda").count())
            self.confere(d.status == "Resolvida" and d.resposta_oficial and aviso >= 1, "Gestão responde a demanda e avisa o autor", "FLX",
                         "Resposta oficial gravada; o aluno foi avisado.", f"Status {d.status}; avisos ao aluno: {aviso}.",
                         "Gestão responde oficialmente os chamados", "Alta", print_de="/demandas")

        freq = self.banco(lambda: m.Frequencia.query.filter_by(usuario_id=aluno1["id"]).first()) if aluno1 else None
        if freq:
            self.etapa("Diário de frequência: abono pela gestão")
            original = freq.tipo_presenca
            self.post("/admin/frequencia", {"frequencia_id": freq.id, "alterar_status": "Status inventado", "observacoes_admin": ""})
            invalido = self.banco(lambda: m.Frequencia.query.get(freq.id).tipo_presenca)
            self.post("/admin/frequencia", {"frequencia_id": freq.id, "alterar_status": "Falta Justificada",
                                            "observacoes_admin": f"{MARCA} Atestado apresentado"})
            f2 = self.banco(lambda: m.Frequencia.query.get(freq.id))
            self.confere(invalido == original and f2.tipo_presenca == "Falta Justificada" and f2.validado_admin,
                         "Gestão abona a frequência (só situações válidas)", "VAL",
                         "Situação inventada recusada; abono gravado e validado pela gestão.",
                         f"Com situação inventada: {invalido}; depois: {f2.tipo_presenca}.",
                         "Frequência só muda para Presencial, Online, Falta ou Falta Justificada", "Alta",
                         "Em gerenciar_frequencia, aceitar só as situações da lista.", print_de="/admin/frequencia")

        enc_id, reuniao_id = self.contexto["ids"].get("encaminhamento"), self.contexto["ids"].get("reuniao")
        if enc_id and reuniao_id:
            self.etapa("Encaminhamento da reunião: a gestão reabre")
            self.post(f"/reunioes/{reuniao_id}", {"encaminhamento_id": enc_id})
            status = self.banco(lambda: m.EncaminhamentoReuniao.query.get(enc_id).status)
            self.confere(status == "Pendente", "Gestão reabre o encaminhamento concluído", "FLX", "Encaminhamento reaberto.",
                         f"Status: {status}.", "Gestão reabre encaminhamentos", "Baixa")
        self.gravacao_excluida()

    # ------------------------------------------------------------------ Reunião: convidados externos (sem conta) e gravação
    def convidados_externos(self, reuniao_id):
        """Mentor Administrador, com a reunião acontecendo agora: o convidado externo (sem conta) usa o link pessoal para
        check-in, check-out e avaliação; a gestão vê o link, lança a presença dele e vê o tempo por instituição."""
        m = _m()
        from base import Cliente
        self.etapa("Reunião: convidado externo (sem conta) registra presença e avalia pelo link pessoal")
        convidado = self.banco(lambda: (lambda c: (c.id, c.codigo, c.nome, c.instituicao) if c else None)(
            m.ConvidadoReuniao.query.filter_by(reuniao_id=reuniao_id, email="parceiro@empresa-funcional.test").first()))
        self.confere(convidado is not None, "Cada participante externo ganha um link pessoal", "FLX",
                     "A linha da lista de externos virou um convidado com código próprio.", "Nenhum convidado criado para o participante externo.",
                     "Participantes externos sem conta também registram presença", "Alta")
        if not convidado:
            return None
        cid, codigo, nome, instituicao = convidado
        self.contexto["ids"]["convidado"] = cid
        _, _, pagina = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}")
        self.confere(f'id="linkConvidado{cid}"' in pagina and f"/reuniao/convidado/{codigo}" in pagina, "Gestão vê e copia o link pessoal do convidado",
                     "FLX", "O link pessoal aparece com o botão de copiar.", "Link pessoal ausente na página da reunião.",
                     "Gestão envia o link a quem não tem e-mail", "Média", print_de=f"/reunioes/{reuniao_id}")

        anonimo = Cliente()
        self.cobertura.add("convidado_reuniao")
        status, _, html = anonimo.pedir("GET", f"/reuniao/convidado/{codigo}")
        self.confere(status == 200 and nome in html and "cardPresencaConvidado" in html, "Convidado abre a página pessoal sem login", "FLX",
                     f"Página do convidado {nome} aberta sem conta na plataforma.", f"HTTP {status}.",
                     "Link pessoal funciona sem login", "Alta", print_de=f"/reuniao/convidado/{codigo}")
        anonimo.pedir("POST", f"/reuniao/convidado/{codigo}", {"acao": "checkout"})
        antes = self.banco(lambda: m.ConvidadoReuniao.query.get(cid).check_out)
        anonimo.pedir("POST", f"/reuniao/convidado/{codigo}", {"acao": "checkin"})
        anonimo.pedir("POST", f"/reuniao/convidado/{codigo}", {"acao": "checkout"})
        c = self.banco(lambda: (lambda x: (x.check_in, x.check_out))(m.ConvidadoReuniao.query.get(cid)))
        self.confere(antes is None and c[0] is not None and c[1] is not None, "Convidado externo faz check-in e check-out", "FLX",
                     "Check-out antes do check-in recusado; entrada e saída registradas.", f"Check-in {c[0]}; check-out {c[1]}.",
                     "Tempo dos participantes do parceiro registrado", "Alta", print_de=f"/reuniao/convidado/{codigo}")
        anonimo.pedir("POST", f"/reuniao/convidado/{codigo}", {"acao": "avaliar", "nota": "9"})
        nota_invalida = self.banco(lambda: m.ConvidadoReuniao.query.get(cid).nota)
        anonimo.pedir("POST", f"/reuniao/convidado/{codigo}", {"acao": "avaliar", "nota": "5", "comentario": f"{MARCA} Pauta clara"})
        nota = self.banco(lambda: m.ConvidadoReuniao.query.get(cid).nota)
        self.confere(nota_invalida is None and nota == 5, "Convidado externo avalia a reunião (1 a 5)", "VAL", "Nota 9 recusada; nota 5 gravada.",
                     f"Nota inválida gravada: {nota_invalida}; final: {nota}.", "Feedback também de quem não tem conta", "Média")
        status, _, html = anonimo.pedir("GET", "/reuniao/convidado/codigo-inventado-123")
        status_post, _, _ = anonimo.pedir("POST", "/reuniao/convidado/codigo-inventado-123", {"acao": "checkin"})
        self.confere(status == 404 and "linkInvalido" in html and status_post == 404, "Link pessoal inventado não abre nada", "SEG",
                     "Código desconhecido: página de link inválido (404).", f"HTTP {status} / {status_post}.",
                     "Só o código sorteado para o convidado dá acesso", "Alta")
        status, destino, _ = anonimo.pedir("GET", f"/reunioes/{reuniao_id}")
        self.confere(status in (301, 302, 303) and destino != f"/reunioes/{reuniao_id}", "O link pessoal não abre a área interna", "SEG",
                     "Sem login, a página interna da reunião manda para o login.", f"HTTP {status}.",
                     "Convidado só vê a própria página", "Alta")
        status, _, ics = anonimo.pedir("GET", f"/reuniao/convidado/{codigo}/agenda.ics")
        self.confere(status == 200 and "BEGIN:VCALENDAR" in ics, "Convidado salva a reunião na agenda pelo link pessoal", "FLX",
                     "Arquivo .ics servido sem login.", f"HTTP {status}.", "Convite também para quem não tem conta", "Baixa")

        self.etapa("Reunião: gestão lança a presença do convidado e vê o tempo por instituição")
        self.post(f"/reunioes/{reuniao_id}/presenca", {"acao": "remover", "convidado_id": cid})
        removida = self.banco(lambda: m.ConvidadoReuniao.query.get(cid).check_in) is None
        inicio = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao_id).data_hora)
        self.post(f"/reunioes/{reuniao_id}/presenca", {"acao": "manual", "pessoa": f"c{cid}", "entrada": inicio.strftime("%H:%M"),
                                                       "saida": datetime.now().strftime("%H:%M"), "modalidade": "Presencial"})
        manual = self.banco(lambda: (lambda x: (x.registro_manual, x.total_minutos or 0))(m.ConvidadoReuniao.query.get(cid)))
        self.confere(removida and manual[0] and manual[1] > 0, "Gestão remove e lança a presença do convidado externo", "FLX",
                     f"Presença removida e lançada de novo pela gestão ({manual[1]} min).", f"Removida: {removida}; lançamento: {manual}.",
                     "Gestão corrige a presença de quem esqueceu", "Média")
        _, _, pagina = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}")
        self.confere('id="tempoInvestido"' in pagina and (instituicao or "") in pagina, "Tempo investido por instituição na reunião", "FLX",
                     f"O quadro soma o tempo de cada lado (inclusive {instituicao}).", "Quadro de tempo por instituição ausente.",
                     "Tempo dos participantes do parceiro e da instituição", "Alta", print_de=f"/reunioes/{reuniao_id}#cardPresenca")
        _, _, ata = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}?imprimir=1")
        self.confere("Tempo investido por instituição" in ata and "(convidado externo)" in ata, "Ata traz os convidados externos e o tempo", "FLX",
                     "A ata impressa lista o convidado e o tempo por instituição.", "A ata não traz o convidado externo ou o tempo.",
                     "Ata completa da Reunião de Alinhamento", "Média")
        return anonimo, codigo

    def gravacao_da_reuniao(self, reuniao_id, anonimo=None, codigo=None):
        """Mentor Administrador envia o arquivo da gravação: formato errado é recusado; participantes e convidados assistem."""
        m = _m()
        self.etapa("Reunião: arquivo da gravação")
        self.post(f"/reunioes/{reuniao_id}/gravacao", {}, {"arquivo": ("gravacao.exe", b"MZ\x90\x00 programa disfarcado")})
        recusado = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao_id).gravacao_arquivo) is None
        video = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 4096
        self.post(f"/reunioes/{reuniao_id}/gravacao", {}, {"arquivo": ("gravacao-funcional.mp4", video)})
        arquivo, tamanho = self.banco(lambda: (lambda r: (r.gravacao_arquivo, r.gravacao_tamanho))(m.ReuniaoInstitucional.query.get(reuniao_id)))
        status, _, _ = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}/gravacao")
        self.confere(recusado and bool(arquivo) and tamanho == len(video) and status == 200, "Envia o arquivo da gravação da reunião", "FLX",
                     "Executável recusado; vídeo MP4 gravado e servido.", f"Recusou o .exe: {recusado}; arquivo {arquivo} ({tamanho} bytes); HTTP {status}.",
                     "Gravação da reunião guardada na plataforma", "Alta", print_de=f"/reunioes/{reuniao_id}#cardGravacao")
        if arquivo:
            self.contexto["ids"]["gravacao"] = True
        if anonimo and codigo:
            status, _, _ = anonimo.pedir("GET", f"/reuniao/convidado/{codigo}/gravacao")
            self.confere(status == 200, "Convidado externo assiste à gravação pelo link pessoal", "FLX", "Gravação servida pelo link pessoal.",
                         f"HTTP {status}.", "Convidados externos também acessam a gravação", "Média")

    def gravacao_para_o_perfil(self, reuniao_id, participante):
        """Participante assiste à gravação; quem não participou não acessa."""
        if not self.contexto["ids"].get("gravacao"):
            return
        status, _, _ = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}/gravacao")
        if participante:
            self.confere(status == 200, f"{self.perfil} participante assiste à gravação", "PER", "Gravação servida.", f"HTTP {status}.",
                         "Participantes acessam a gravação", "Média")
        else:
            self.confere(status != 200, f"{self.perfil} que não participou não acessa a gravação", "PER", f"Acesso recusado (HTTP {status}).",
                         "Baixou a gravação de uma reunião da qual não participou.", "Gravação só para participantes e gestão", "Alta",
                         "Em gravacao_reuniao, conferir pode_ver_reuniao antes de servir o arquivo.")

    def gravacao_excluida(self):
        """Encerramento: a gestão exclui o arquivo da gravação (o arquivo sai do disco)."""
        m = _m()
        reuniao_id = self.contexto["ids"].get("reuniao")
        if not (reuniao_id and self.contexto["ids"].get("gravacao")):
            return
        import os
        from app import PASTA_GRAVACOES
        self.etapa("Reunião: exclusão do arquivo da gravação")
        arquivo = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao_id).gravacao_arquivo)
        self.post(f"/reunioes/{reuniao_id}/gravacao", {"acao": "excluir"})
        depois = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao_id).gravacao_arquivo)
        no_disco = bool(arquivo) and os.path.exists(os.path.join(PASTA_GRAVACOES, arquivo))
        self.confere(arquivo and depois is None and not no_disco, "Gestão exclui o arquivo da gravação", "FLX", "Registro e arquivo removidos.",
                     f"Registro: {depois}; arquivo ainda no disco: {no_disco}.", "Gestão controla a gravação guardada", "Baixa")

    # ------------------------------------------------------------------ Avaliação 360°: todos avaliam todos
    def avaliacao_da_gestao(self):
        """Mentor Administrador (gestão da instituição) avalia o jovem e não avalia a si mesmo como gestor."""
        m = _m()
        ciclo_id, aluno1 = self.contexto["ids"].get("ciclo"), self.usuario("aluno1")
        if not (ciclo_id and aluno1):
            return
        self.etapa("Avaliação 360°: a gestão da instituição avalia o jovem")
        eu = self.banco(lambda: m.Usuario.query.filter_by(email=self.email_logado).first().id)
        _, _, pagina = self.cliente.pedir("GET", "/avaliacoes")
        ok = self.avaliar("Jovem", aluno1["id"], [4, 4, 3, 4], f"{MARCA} Participativo nas palestras")
        proprio = self.avaliar("Gestor {apelido}", eu, [5, 5, 5, 5])
        self.confere(f'aval_{ciclo_id}_Jovem_{aluno1["id"]}' in pagina and ok and not proprio, "Gestão da instituição avalia o jovem", "FLX",
                     "Avaliação do jovem gravada; ninguém avalia a si mesmo.", f"Jovem na lista: {f'aval_{ciclo_id}_Jovem_' in pagina}; "
                     f"gravada: {ok}; autoavaliação aceita: {proprio}.", "Avaliação de todos: a gestão também avalia os jovens", "Alta",
                     print_de="/avaliacoes")

    def avaliacao_do_gestor_da_instituicao(self, notas, comentario=""):
        """Jovem ou gestor B2B avalia individualmente o gestor do projeto na instituição (o Mentor Administrador do fluxo)."""
        gestor_inst = self.usuario("mentoradmin")
        if not (self.contexto["ids"].get("ciclo") and gestor_inst):
            return False
        return self.avaliar("Gestor {apelido}", gestor_inst["id"], notas, comentario)

    # ------------------------------------------------------------------ Conteúdo do curso: aulas, testes e progresso automático
    APOSTILA = (b"# Apostila de Python\n\n## Aula 1 - Variaveis e tipos\nVariaveis guardam valores na memoria do computador durante a execucao. "
                b"O tipo inteiro representa numeros sem casas decimais no programa. Textos ficam em variaveis do tipo string entre aspas.\n\n"
                b"## Aula 2 - Estruturas de repeticao\nO comando while repete instrucoes enquanto a condicao continuar verdadeira. "
                b"O comando for percorre cada elemento de uma lista ou sequencia. Interromper o laco antecipadamente exige o comando break.\n\n"
                b"## Aula 3 - Funcoes\nFuncoes agrupam instrucoes reutilizaveis com um nome descritivo. Parametros recebem valores enviados "
                b"pela chamada da funcao. O comando return devolve o resultado calculado para quem chamou.\n")

    def conteudo_do_curso(self, curso_id):
        """Gestão monta o curso na plataforma: apostila dividida em aulas, teste gerado, vídeo do YouTube, pergunta manual."""
        m = _m()
        self.etapa("Conteúdo do curso: apostila dividida em aulas e testes de conhecimento")
        base = f"/admin/cursos/{curso_id}/conteudo"
        self.post(base, {"acao": "importar_documento", "modo": "acrescentar", "gerar_testes": "1"},
                  {"documento": ("apostila-funcional.md", self.APOSTILA)})
        aulas = self.banco(lambda: [(a.id, a.titulo, a.questoes.count()) for a in
                                    m.AulaCurso.query.filter_by(curso_id=curso_id).order_by(m.AulaCurso.ordem).all()])
        self.confere(len(aulas) == 3 and all(n >= 1 for _, _, n in aulas), "Apostila vira aulas com teste de conhecimento", "FLX",
                     f"{len(aulas)} aulas: " + "; ".join(f"{t} ({n} pergunta(s))" for _, t, n in aulas),
                     f"Aulas criadas: {aulas}.", "O documento é dividido em capítulos e cada aula ganha o teste", "Alta", print_de=base)
        self.post(base, {"acao": "salvar_aula", "titulo": f"{MARCA} Aula em video"}, {"video": ("programa.exe", b"MZ\x90\x00 disfarcado")})
        exe = self.banco(lambda: m.AulaCurso.query.filter_by(curso_id=curso_id, titulo=f"{MARCA} Aula em video").first())
        self.post(base, {"acao": "salvar_aula", "titulo": f"{MARCA} Aula em video", "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        video = self.banco(lambda: m.AulaCurso.query.filter_by(curso_id=curso_id, titulo=f"{MARCA} Aula em video").first())
        if video:
            self.post(base, {"acao": "salvar_questao", "aula_id": video.id, "enunciado": f"{MARCA} Sobre o que fala o video?",
                             "alternativa_0": "Python", "alternativa_1": "Culinaria", "correta": "0"})
            self.post(base, {"acao": "mover_aula", "aula_id": video.id, "direcao": "subir"})
        dados = self.banco(lambda: (lambda a: (a.youtube_id, a.questoes.count(), a.ordem))(m.AulaCurso.query.get(video.id))) if video else None
        self.confere(exe is None and dados and dados[0] == "dQw4w9WgXcQ" and dados[1] == 1 and dados[2] == 3,
                     "Aula com vídeo do YouTube e pergunta escrita à mão", "FLX", "Executável recusado; vídeo, pergunta e nova ordem gravados.",
                     f"Executável aceito: {exe is not None}; vídeo/perguntas/ordem: {dados}.", "Gestão monta a aula em vídeo e revisa o teste", "Alta")
        self.post(base, {"acao": "salvar_aula", "titulo": f"{MARCA} Aula descartada"})
        extra = self.banco(lambda: m.AulaCurso.query.filter_by(curso_id=curso_id, titulo=f"{MARCA} Aula descartada").first())
        if extra:
            self.post(base, {"acao": "excluir_aula", "aula_id": extra.id})
        sobrou = self.banco(lambda: m.AulaCurso.query.filter_by(curso_id=curso_id, titulo=f"{MARCA} Aula descartada").count())
        self.confere(extra is not None and sobrou == 0, "Gestão exclui uma aula", "FLX", "Aula criada e excluída.",
                     f"Criada: {extra is not None}; sobrou: {sobrou}.", "Gestão remove aulas do curso", "Baixa")
        self.contexto["ids"]["curso_com_aulas"] = curso_id

    def estudo_do_curso(self):
        """Aluno estuda dentro da plataforma: o vídeo e a leitura contam sozinhos, o teste aprova a aula e o percentual sobe."""
        import time
        import conteudo_curso
        m = _m()
        curso_id, eu = self.contexto["ids"].get("curso_com_aulas"), self.usuario("aluno1")
        if not (curso_id and eu):
            return
        acomp = self.banco(lambda: m.Acompanhamento.query.filter_by(aluno_id=eu["id"], curso_id=curso_id).first())
        if not acomp:
            self.registrar("Aluno sem matrícula no curso com aulas", FALHA, "FLX", "A turma não matriculou o aluno no curso com aulas.",
                           "Matrícula pela turma cria o acompanhamento", "Média")
            return
        self.etapa("Estudo dentro da plataforma: progresso automático")
        aulas = self.banco(lambda: [(a.id, a.video_tipo, a.texto) for a in
                                    m.AulaCurso.query.filter_by(curso_id=curso_id).order_by(m.AulaCurso.ordem).all()])
        status, _, pagina = self.cliente.pedir("GET", f"/meus-cursos/{acomp.id}")
        self.confere(status == 200 and "Teste seus conhecimentos" in pagina, "Aluno abre a sala de estudo do curso", "FLX",
                     "Aulas listadas com o teste.", f"HTTP {status}.", "O aluno estuda dentro da plataforma", "Alta",
                     print_de=f"/meus-cursos/{acomp.id}")
        texto = next((a for a in aulas if a[1] is None and a[2]), None)
        video = next((a for a in aulas if a[1] == "youtube"), None)
        if texto:
            self.cliente.pedir("GET", f"/meus-cursos/{acomp.id}?aula={texto[0]}")
            cedo, _, _ = self.cliente.pedir("POST", f"/meus-cursos/{acomp.id}/aula/{texto[0]}/progresso", json_corpo={"evento": "leitura"})
            time.sleep(conteudo_curso.segundos_de_leitura(texto[2]) + 1)
            self.post_json(f"/meus-cursos/{acomp.id}/aula/{texto[0]}/progresso", {"evento": "leitura"})
            lida = self.banco(lambda: bool((m.ProgressoAula.query.filter_by(acompanhamento_id=acomp.id, aula_id=texto[0]).first()
                                            or m.ProgressoAula()).leitura_concluida))
            self.confere(cedo == 409 and lida, "Leitura conta só depois do tempo mínimo", "REG",
                         "Leitura recusada logo ao abrir e aceita depois do tempo mínimo.",
                         f"Resposta ao abrir: HTTP {cedo}; leitura gravada: {lida}.", "Progresso da leitura não é marcado sem ler", "Média")
            questoes = self.banco(lambda: [(q.id, q.correta, len(q.lista_alternativas)) for q in m.QuestaoAula.query.filter_by(aula_id=texto[0]).all()])
            self.post(f"/meus-cursos/{acomp.id}/aula/{texto[0]}/teste", {f"q{i}": str((c + 1) % n) for i, c, n in questoes})
            reprovado = self.banco(lambda: m.ProgressoAula.query.filter_by(acompanhamento_id=acomp.id, aula_id=texto[0]).first().teste_aprovado)
            self.post(f"/meus-cursos/{acomp.id}/aula/{texto[0]}/teste", {f"q{i}": str(c) for i, c, _ in questoes})
            final = self.banco(lambda: (lambda p: (p.teste_aprovado, p.teste_nota, p.teste_tentativas, p.concluida_em is not None))(
                m.ProgressoAula.query.filter_by(acompanhamento_id=acomp.id, aula_id=texto[0]).first()))
            self.confere(not reprovado and final[0] and final[1] == 100 and final[2] == 2 and final[3], "Teste de conhecimento aprova a aula", "REG",
                         "Errando tudo não aprova; acertando tudo aprova (2 tentativas, vale a melhor nota) e a aula fica concluída.",
                         f"Aprovado errando: {reprovado}; depois: {final}.", "Teste com nota mínima e novas tentativas", "Alta",
                         print_de=f"/meus-cursos/{acomp.id}?aula={texto[0]}&ver=teste")
        if video:
            self.post_json(f"/meus-cursos/{acomp.id}/aula/{video[0]}/progresso",
                           {"evento": "video", "duracao": 200, "posicao": 120, "trechos": [[0, 60], [150, 200]]})
            pulado = self.banco(lambda: m.ProgressoAula.query.filter_by(acompanhamento_id=acomp.id, aula_id=video[0]).first().video_concluido)
            self.post_json(f"/meus-cursos/{acomp.id}/aula/{video[0]}/progresso",
                           {"evento": "video", "duracao": 200, "posicao": 150, "trechos": [[55, 150]]})
            assistido = self.banco(lambda: (lambda p: (p.video_concluido, p.segundos_assistidos))(
                m.ProgressoAula.query.filter_by(acompanhamento_id=acomp.id, aula_id=video[0]).first()))
            self.confere(not pulado and assistido[0] and assistido[1] == 200, "Vídeo conta só o que foi assistido", "REG",
                         "Com trechos pulados o vídeo não contou; ao completar os trechos, contou.",
                         f"Concluído com pulos: {pulado}; depois: {assistido}.", "Pular o vídeo não conclui a aula", "Alta")
        percentual = self.banco(lambda: m.Acompanhamento.query.get(acomp.id).percentual_conclusao)
        self.post("/acompanhamento", {"acompanhamento_id": acomp.id, "status": "Iniciado", "percentual_conclusao": "100",
                                      "observacao_aluno": f"{MARCA} Estudando"})
        depois = self.banco(lambda: m.Acompanhamento.query.get(acomp.id).percentual_conclusao)
        self.confere(0 < percentual < 100 and depois == percentual, "Progresso do acompanhamento é automático", "REG",
                     f"Percentual calculado pelas aulas: {percentual}%; o formulário não o altera.",
                     f"Percentual pelas aulas: {percentual}%; depois de enviar 100% no formulário: {depois}%.",
                     "Curso com aulas: o progresso vem das aulas e testes", "Alta", print_de="/acompanhamento")
        outro = self.banco(lambda: m.Acompanhamento.query.filter(m.Acompanhamento.aluno_id != eu["id"], m.Acompanhamento.curso_id == curso_id).first())
        if outro:
            status, _, _ = self.cliente.pedir("GET", f"/meus-cursos/{outro.id}")
            proibido, _, _ = self.cliente.pedir("POST", f"/meus-cursos/{outro.id}/aula/{aulas[0][0]}/progresso", json_corpo={"evento": "leitura"})
            self.confere(status == 302 and proibido == 403, "Aluno não abre nem marca o curso de outro aluno", "PER",
                         "Sala de outro aluno recusada e progresso recusado.", f"Sala: HTTP {status}; progresso: HTTP {proibido}.",
                         "Cada aluno só vê e registra o próprio estudo", "Alta")
