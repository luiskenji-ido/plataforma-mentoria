# -*- coding: utf-8 -*-
"""
AGENTES DE FUNCIONALIDADES — a corrida de revezamento pelo fluxo da plataforma
Uso: python agentes_funcionalidades/agente_fluxo.py <agente>
Ordem (o Gerente chama um de cada vez; cada um cria os usuários e os dados que o próximo precisa):
  administrador → mentor_administrador → gestor_parceiro → professor → mentor → aluno → avaliador → encerramento
"""
import os
import sys
import json
from datetime import datetime, timedelta, date

from base import (AgenteFuncional, FALHA, ALERTA, MARCA, DOMINIO, senha_forte, mensagens, RAIZ_PROJETO)

PDF_MINIMO = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
              b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def _modelos():
    import models
    return models


def senha_de_teste():
    if os.environ.get("OMNITEST_SENHA"):
        return os.environ["OMNITEST_SENHA"]
    from dotenv import dotenv_values
    return dotenv_values(os.path.join(RAIZ_PROJETO, ".env")).get("OMNITEST_SENHA") or ""


class AgenteDoFluxo(AgenteFuncional):
    """Utilidades comuns aos agentes da cadeia."""

    def __init__(self):
        super().__init__()
        self.cobertura = set()

    def post(self, caminho, form=None, arquivos=None, seguir=True):
        """POST de um formulário da plataforma (registra a função coberta)."""
        try:
            import app as modulo_app
            adaptador = modulo_app.app.url_map.bind("localhost")
            self.cobertura.add(adaptador.match(caminho.split("?")[0], method="POST")[0])
        except Exception:
            pass
        status, destino, html = self.cliente.pedir("POST", caminho, form, arquivos, seguir=seguir)
        return status, destino, html

    def usuario(self, papel):
        return self.contexto["usuarios"].get(papel)

    def criar_usuario(self, papel, tipo, nome, extras=None):
        """Cadastro pela tela Cadastros (gerenciar_usuarios), validando o resultado no banco."""
        email = f"{papel}_{DOMINIO}"
        senha = senha_forte()
        form = {"nome": f"{MARCA} {nome}", "email": email, "tipo_usuario": tipo, "status": "Ativo", "senha": senha, "forcar_troca_senha": "False"}
        form.update(extras or {})
        _, _, html = self.post("/admin/usuarios", form)
        criado = self.banco(lambda: _modelos().Usuario.query.filter_by(email=email).first())
        self.confere(criado is not None and criado.tipo_usuario == tipo, f"Cria o usuário {nome} ({tipo})", "FLX",
                     f"Usuário {email} criado como {tipo}.", f"Não criou o usuário. Mensagens: {' | '.join(mensagens(html))[:300]}",
                     f"{self.perfil} cadastra o perfil {tipo}", "Crítica", print_de="/admin/usuarios")
        if criado:
            self.contexto["usuarios"][papel] = {"email": email, "senha": senha, "id": criado.id, "tipo": tipo}
        return criado

    def _funcoes_do_perfil(self):
        """Funções (POST) dos módulos do perfil, pelas regras aprendidas."""
        import perfis_acesso
        meus = set(self.regras.get("modulos_por_base", {}).get(self.perfil, []))
        return {e for mod in meus if mod in perfis_acesso.MODULOS for e in perfis_acesso.MODULOS[mod][2] if e in self.regras.get("rotas_post", [])}

    def reportar_cobertura(self):
        """Registra as funções exercitadas (o Gerente calcula a cobertura da cadeia inteira) e avisa das funções novas aprendidas."""
        if not self.regras.get("modulos"):
            return
        self.log(f"Funções exercitadas por este agente: {', '.join(sorted(self.cobertura)) or 'nenhuma'}")
        novas = sorted(set(self.regras.get("funcoes_novas", [])) & self._funcoes_do_perfil())
        if novas:
            self.etapa("Funções novas aprendidas")
            self.registrar(f"{len(novas)} função(ões) nova(s) aprendida(s) sem teste funcional", ALERTA, "FLX",
                           ", ".join(novas), "Toda função nova entra no fluxo de teste", "Baixa",
                           "O Gerente de Funcionalidades aprendeu estas funções novas; criar o passo de teste correspondente.")

    def gerar_relatorio(self):
        dados = super().gerar_relatorio()
        dados["cobertura"] = sorted(self.cobertura)
        dados["funcoes_do_perfil"] = sorted(self._funcoes_do_perfil()) if self.regras.get("modulos") else []
        with open(dados["prompt"].replace("_prompt.md", ".json"), "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
        return dados


# ==============================================================================
# 1. ADMINISTRADOR
# ==============================================================================
class AgenteAdministrador(AgenteDoFluxo):
    chave, nome, perfil = "administrador", "Agente Administrador (Funcional)", "Administrador"
    ROTEIRO = ["Login e onboarding do Administrador", "Matriz de acesso do perfil (regras aprendidas)",
               "Validações do cadastro de usuários: e-mail inválido, duplicado e senha fraca",
               "Cria o Mentor Administrador e passa a vez para ele"]

    def rodar(self):
        self.contexto.update({"execucao": self.contexto.get("execucao") or self.carimbo, "usuarios": {}, "ids": {}})
        sys.path.insert(0, os.path.join(RAIZ_PROJETO, "agentes_omnitest"))
        email_admin = "administrador_ominitest@local.com"
        from nucleo import preparar_usuario
        preparar_usuario("administrador")
        self.primeiro_acesso(email_admin, senha_de_teste())
        self.matriz_de_acesso("Administrador")

        self.etapa("Validações do cadastro de usuários")
        casos = [("e-mail inválido", {"email": "sem-arroba"}, "não é válido"),
                 ("e-mail já cadastrado", {"email": email_admin}, "já está cadastrado"),
                 ("senha fraca", {"email": f"senhafraca_{DOMINIO}", "senha": "abc12345"}, "10 caracteres")]
        for nome, ajuste, trecho in casos:
            form = {"nome": f"{MARCA} Teste", "email": f"invalido_{DOMINIO}", "tipo_usuario": "Aluno", "status": "Ativo", "senha": senha_forte(),
                    "forcar_troca_senha": "False", **ajuste}
            _, _, html = self.post("/admin/usuarios", form)
            criado = self.banco(lambda: _modelos().Usuario.query.filter_by(email=form["email"]).count())
            self.confere(trecho in html and (criado == 0 or form["email"] == email_admin), f"Cadastro recusa {nome}", "VAL",
                         f"Recusado com a mensagem certa: {trecho}.", f"Não recusou como esperado. Mensagens: {' | '.join(mensagens(html))[:200]}",
                         f"Cadastro de usuário recusa {nome}", "Alta")

        self.etapa("Cria o Mentor Administrador")
        self.criar_usuario("mentoradmin", "Mentor Administrador", "Mentor Administrador")
        self.reportar_cobertura()


# ==============================================================================
# 2. MENTOR ADMINISTRADOR — monta todo o programa
# ==============================================================================
class AgenteMentorAdministrador(AgenteDoFluxo):
    chave, nome, perfil = "mentor_administrador", "Agente Mentor Administrador (Funcional)", "Mentor Administrador"
    ROTEIRO = ["Primeiro acesso: perguntas de segurança, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Regra: Mentor Administrador não cria Administrador", "Cria os cursos do catálogo",
               "Cria Gestor Parceiro, Mentor, Professor, 2 Alunos e o Avaliador da banca",
               "Cria a empresa parceira (gestor e mentor), o grupo e a turma (matrícula automática)",
               "Matricula outro aluno, cria o projeto, a tarefa e agenda a banca com o avaliador"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("mentoradmin")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        self.matriz_de_acesso("Mentor Administrador")

        self.etapa("Regra: o Mentor Administrador não pode criar Administradores")
        email = f"adminindevido_{DOMINIO}"
        self.post("/admin/usuarios", {"nome": f"{MARCA} Admin indevido", "email": email, "tipo_usuario": "Administrador", "status": "Ativo",
                                      "senha": senha_forte(), "forcar_troca_senha": "False"})
        criado = self.banco(lambda: m.Usuario.query.filter_by(email=email).first())
        self.confere(criado is None, "Mentor Administrador não cria Administrador", "PER",
                     "Cadastro de Administrador recusado para o Mentor Administrador.",
                     "O Mentor Administrador criou um usuário Administrador (escalada de privilégio).",
                     "Só o Administrador cria Administradores", "Alta",
                     "Em gerenciar_usuarios/editar_usuario/novo_usuario_rapido: se current_user não for Administrador, recusar tipo 'Administrador'.")

        self.etapa("Catálogo de cursos")
        cursos = []
        for nome, tipo in (("Python para Dados", "Técnico"), ("Comunicação e Carreira", "Comportamental")):
            self.post("/admin/turmas", {"acao": "novo_curso", "nome": f"{MARCA} {nome}", "plataforma": "Alura", "tipo": tipo, "carga_horaria": "20",
                                        "link": "https://exemplo.org/curso", "exige_certificado": "Sim", "status": "Ativo"})
            curso = self.banco(lambda: m.Curso.query.filter_by(nome_curso=f"{MARCA} {nome}").first())
            self.confere(curso is not None, f"Cria o curso {nome}", "FLX", "Curso no catálogo.", "Curso não foi criado.", "Catálogo de cursos", "Alta",
                         print_de="/admin/turmas")
            if curso:
                cursos.append(curso.id)
        self.contexto["ids"]["cursos"] = cursos

        self.etapa("Cadastro dos perfis do programa")
        self.criar_usuario("gestor", "Admin B2B", "Gestor Parceiro")
        mentor = self.criar_usuario("mentor", "Mentor", "Mentor")
        self.criar_usuario("professor", "Professor", "Professor")
        for papel, nome in (("aluno1", "Aluno Um"), ("aluno2", "Aluno Dois")):
            self.criar_usuario(papel, "Aluno", nome, {"modalidade_participacao": "Presencial", "mentores": [mentor.id] if mentor else []})
        ids_novos = [u["id"] for p, u in self.contexto["usuarios"].items() if p in ("gestor", "mentor", "professor", "aluno1", "aluno2")]
        herdados = self.banco(lambda: [f"id {i}" for i in ids_novos if m.SegurancaUsuario.query.filter_by(usuario_id=i).count()
                                       or m.TermoAceite.query.filter_by(usuario_id=i).count() or m.HistoricoSenha.query.filter_by(usuario_id=i).count()])
        self.confere(not herdados, "Contas novas nascem sem dados de outra conta", "INT",
                     f"{len(ids_novos)} conta(s) nova(s) sem perguntas, termo ou histórico herdados.",
                     "Contas novas já nasceram com perguntas/termo/histórico de outra conta: " + ", ".join(herdados),
                     "Conta nova não herda credenciais de usuário apagado (o SQLite reaproveita ids)", "Crítica",
                     "Apagar os dados ligados ao usuário junto com ele e limpar órfãos ao inserir (models._conta_nova_sem_heranca).")
        a1 = self.banco(lambda: m.Usuario.query.filter_by(email=f"aluno1_{DOMINIO}").first())
        self.confere(a1 is not None and mentor is not None and any(x.id == mentor.id for x in self.banco(lambda: list(m.Usuario.query.get(a1.id).mentores))),
                     "Aluno vinculado ao mentor no cadastro", "INT", "O aluno ficou com o mentor escolhido.", "O vínculo aluno–mentor não foi gravado.",
                     "Cadastro do aluno grava os mentores escolhidos", "Média")

        senha_av = senha_forte()
        email_av = f"avaliador_{DOMINIO}"
        self.post("/bancas/avaliadores", {"acao": "criar", "nome_completo": f"{MARCA} Avaliador Banca", "email": email_av, "senha": senha_av,
                                          "empresa_origem": "", "area_atuacao": "Dados", "curriculo_minibio": "Executivo convidado (teste funcional)"})
        av = self.banco(lambda: m.Usuario.query.filter_by(email=email_av).first())
        perfil_av = self.banco(lambda: m.PerfilAvaliador.query.filter_by(usuario_id=av.id).first() if av else None)
        self.confere(av is not None and av.tipo_usuario == "Avaliador Banca" and perfil_av is not None, "Cria o Avaliador da banca", "FLX",
                     "Avaliador e perfil de avaliador criados (troca de senha obrigatória no primeiro acesso).", "Avaliador não foi criado.",
                     "Cadastro de avaliadores da banca", "Crítica", print_de="/bancas/avaliadores")
        if av:
            self.contexto["usuarios"]["avaliador"] = {"email": email_av, "senha": senha_av, "id": av.id, "tipo": "Avaliador Banca"}

        self.etapa("Regra: cadastro rápido do Hub segue a política de senha")
        email_rapido = f"rapido_{DOMINIO}"
        self.post("/admin/turmas", {"acao": "novo_usuario_rapido", "nome_usuario": f"{MARCA} Rápido", "email_usuario": email_rapido,
                                    "tipo_usuario_rapido": "Aluno", "senha_usuario": "123"})
        rapido = self.banco(lambda: m.Usuario.query.filter_by(email=email_rapido).first())
        self.confere(rapido is None, "Cadastro rápido recusa senha fraca", "VAL", "Senha '123' recusada.",
                     "O cadastro rápido do Hub Educacional criou usuário com a senha '123' (sem a política de senha).",
                     "Todo cadastro de usuário aplica a política de senha forte", "Alta",
                     "Em gerenciar_turmas (acao 'novo_usuario_rapido'), validar a senha com o mesmo padrão de gerenciar_usuarios.")

        self.etapa("Importação de alunos por planilha (CSV)")
        import re as _re
        planilha = f"nome,email\n{MARCA} Importado,importado_{DOMINIO}\nLinha ruim,sem-arroba\n".encode()
        _, _, retorno = self.post("/admin/turmas", {"acao": "importar_csv"}, {"arquivo_csv": ("alunos_funcional.csv", planilha)})
        linhas = [x.split(";") for x in retorno.lstrip("﻿").splitlines() if ";" in x]
        senha = linhas[1][2] if len(linhas) > 1 and len(linhas[1]) > 2 else ""
        importado = self.banco(lambda: m.Usuario.query.filter_by(email=f"importado_{DOMINIO}").first())
        invalido = self.banco(lambda: m.Usuario.query.filter_by(email="sem-arroba").count())
        forte = bool(_re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{10,}$', senha))
        self.confere(importado is not None and importado.forcar_troca_senha and forte and invalido == 0,
                     "Importação por CSV com senha provisória forte e troca obrigatória", "REG",
                     "Aluno importado com senha provisória aleatória (planilha baixada), troca obrigatória e linha inválida ignorada.",
                     f"Importado: {bool(importado)}; senha forte: {forte}; e-mails inválidos criados: {invalido}.",
                     "Toda conta nasce com senha forte e troca obrigatória (nada de senha fixa)", "Alta",
                     "Em gerenciar_turmas (importar_csv), gerar senha provisória aleatória por aluno e entregar a planilha de senhas.")

        self.etapa("Empresa parceira, grupo e turma")
        gestor, aluno1, aluno2 = self.usuario("gestor"), self.usuario("aluno1"), self.usuario("aluno2")
        self.post("/admin/turmas", {"acao": "nova_empresa", "nome": f"{MARCA} Empresa Parceira", "contato_nome": "Contato Funcional",
                                    "contato_email": f"contato_{DOMINIO}", "gestor_id": gestor["id"] if gestor else "", "mentores_ids": [mentor.id] if mentor else []})
        empresa = self.banco(lambda: m.Empresa.query.filter_by(nome=f"{MARCA} Empresa Parceira").first())
        mentores_emp = self.banco(lambda: [x.id for x in m.Empresa.query.get(empresa.id).mentores]) if empresa else []
        self.confere(empresa is not None and gestor and empresa.gestor_id == gestor["id"] and mentor and mentor.id in mentores_emp,
                     "Cria a empresa parceira com gestor e mentor", "FLX", "Empresa com o Gestor Parceiro e o mentor vinculados.",
                     "Empresa não criada ou sem os vínculos.", "Empresa parceira com gestor B2B e mentores", "Crítica", print_de="/admin/turmas")
        self.contexto["ids"]["empresa"] = empresa.id if empresa else None

        self.post("/admin/grupos", {"nome": f"{MARCA} Grupo TCC", "descricao": "Grupo do teste funcional",
                                    "membros": [x for x in (aluno1 and aluno1["id"], mentor and mentor.id) if x]})
        grupo = self.banco(lambda: m.Grupo.query.filter_by(nome=f"{MARCA} Grupo TCC").first())
        membros = self.banco(lambda: sorted(x.id for x in m.Grupo.query.get(grupo.id).membros)) if grupo else []
        self.confere(grupo is not None and aluno1 and aluno1["id"] in membros, "Cria o grupo do TCC com aluno e mentor", "FLX",
                     f"Grupo com {len(membros)} membro(s).", "Grupo não criado ou sem os membros.", "Grupo de TCC", "Crítica", print_de="/admin/grupos")
        self.contexto["ids"]["grupo"] = grupo.id if grupo else None

        hoje = date.today()
        self.post("/admin/turmas", {"acao": "nova_turma", "nome": f"{MARCA} Turma sem curso", "empresa_id": empresa.id if empresa else "",
                                    "data_inicio": hoje.isoformat(), "data_termino": (hoje + timedelta(days=90)).isoformat()})
        sem_curso = self.banco(lambda: m.Turma.query.filter_by(nome=f"{MARCA} Turma sem curso").first())
        self.confere(sem_curso is None, "Turma sem curso é recusada", "VAL", "A turma exige ao menos um curso.", "Criou turma sem curso.",
                     "Turma precisa de pelo menos um curso", "Média")
        self.post("/admin/turmas", {"acao": "nova_turma", "nome": f"{MARCA} Turma", "empresa_id": empresa.id if empresa else "",
                                    "grupo_id": grupo.id if grupo else "", "cursos_ids": cursos, "data_inicio": hoje.isoformat(),
                                    "data_termino": (hoje + timedelta(days=90)).isoformat()})
        turma = self.banco(lambda: m.Turma.query.filter_by(nome=f"{MARCA} Turma").first())
        acomps = self.banco(lambda: m.Acompanhamento.query.filter(m.Acompanhamento.aluno_id == aluno1["id"], m.Acompanhamento.curso_id.in_(cursos)).count()) if aluno1 else 0
        self.confere(turma is not None and acomps == len(cursos), "Turma criada com matrícula automática do grupo", "REG",
                     f"Turma criada; o aluno do grupo ganhou {acomps} acompanhamento(s), um por curso.",
                     f"Turma não criada ou matrícula incompleta ({acomps} de {len(cursos)} acompanhamentos).",
                     "Alunos do grupo são matriculados em todos os cursos da turma", "Crítica", print_de="/admin/turmas")
        self.contexto["ids"]["turma"] = turma.id if turma else None

        if turma and aluno2:
            self.post("/admin/turmas", {"acao": "matricular_alunos", "turma_id": turma.id, "alunos_ids": [aluno2["id"]]})
            acomps2 = self.banco(lambda: m.Acompanhamento.query.filter(m.Acompanhamento.aluno_id == aluno2["id"], m.Acompanhamento.curso_id.in_(cursos)).count())
            self.confere(acomps2 == len(cursos), "Matrícula de aluno avulso na turma", "REG", f"{acomps2} acompanhamento(s) criados para o aluno.",
                         f"Matrícula incompleta ({acomps2} de {len(cursos)}).", "Matrícula cria um acompanhamento por curso da turma", "Alta")

        self.etapa("Projeto, tarefa e banca")
        self.post("/projetos", {"nome": f"{MARCA} Projeto sem grupo", "descricao": "x"})
        sem_grupo = self.banco(lambda: m.Projeto.query.filter_by(nome=f"{MARCA} Projeto sem grupo").first())
        self.confere(sem_grupo is None, "Projeto sem grupo é recusado", "VAL", "Projeto exige grupo.", "Criou projeto sem grupo.", "Projeto pertence a um grupo", "Média")
        self.post("/projetos", {"nome": f"{MARCA} Projeto TCC", "descricao": "Projeto do teste funcional", "grupo_id": grupo.id if grupo else ""})
        projeto = self.banco(lambda: m.Projeto.query.filter_by(nome=f"{MARCA} Projeto TCC").first())
        self.confere(projeto is not None and projeto.status == "Em Andamento", "Cria o projeto do grupo", "FLX", "Projeto em andamento.",
                     "Projeto não criado.", "Projeto de TCC do grupo", "Crítica", print_de="/projetos")
        self.contexto["ids"]["projeto"] = projeto.id if projeto else None
        if projeto:
            self.post("/projetos/nova_tarefa", {"projeto_id": projeto.id, "descricao": f"{MARCA} Levantamento de requisitos",
                                                "data_inicio": hoje.isoformat(), "data_fim": (hoje + timedelta(days=7)).isoformat(),
                                                "responsavel": "Aluno Um", "status": "Pendente"})
            tarefa = self.banco(lambda: m.Tarefa.query.filter_by(projeto_id=projeto.id).first())
            self.confere(tarefa is not None, "Cria a tarefa do projeto", "FLX", "Tarefa criada.", "Tarefa não criada.", "Planejamento do projeto", "Média")
            self.contexto["ids"]["tarefa"] = tarefa.id if tarefa else None

            data_banca = datetime.now() + timedelta(days=3)
            prazo = datetime.now() + timedelta(days=2)
            form_banca = {"acao": "salvar", "projeto_id": projeto.id, "data_hora": data_banca.strftime("%Y-%m-%dT%H:%M"), "local": "Sala Funcional",
                          "duracao_apresentacao_min": 15, "duracao_perguntas_min": 10, "horas_antes_formulario": 24,
                          "prazo_entrega_escrito": prazo.strftime("%Y-%m-%dT%H:%M"), "prazo_entrega_slides": prazo.strftime("%Y-%m-%dT%H:%M"),
                          "prazo_leitura_avaliadores": prazo.strftime("%Y-%m-%dT%H:%M"),
                          "avaliadores": [x["id"] for x in (self.usuario("avaliador"),) if x]}
            self.post("/bancas", form_banca)
            banca = self.banco(lambda: m.Banca.query.filter_by(projeto_id=projeto.id).first())
            avaliadores = self.banco(lambda: [x.id for x in m.Banca.query.get(banca.id).avaliadores]) if banca else []
            self.confere(banca is not None and self.usuario("avaliador") and self.usuario("avaliador")["id"] in avaliadores,
                         "Agenda a banca com o avaliador escalado", "FLX", f"Banca em {data_banca:%d/%m %H:%M} com {len(avaliadores)} avaliador(es).",
                         "Banca não agendada ou sem avaliador.", "Banca do TCC com avaliadores", "Crítica", print_de="/bancas")
            self.contexto["ids"]["banca"] = banca.id if banca else None
            self.post("/bancas", form_banca)
            duplicadas = self.banco(lambda: m.Banca.query.filter_by(projeto_id=projeto.id).count())
            self.confere(duplicadas == 1, "Segunda banca para o mesmo projeto é recusada", "REG", "Só uma banca por projeto.",
                         f"{duplicadas} bancas para o mesmo projeto.", "Uma banca por projeto", "Média")
        self.reportar_cobertura()


# ==============================================================================
# 3. GESTOR PARCEIRO (Admin B2B)
# ==============================================================================
class AgenteGestorParceiro(AgenteDoFluxo):
    chave, nome, perfil = "gestor_parceiro", "Agente Gestor Parceiro (Funcional)", "Admin B2B"
    ROTEIRO = ["Primeiro acesso: perguntas e termo", "Matriz de acesso do perfil",
               "Regra: só vê a turma e a banca da sua empresa", "Regra: avaliador só da própria empresa", "Relatório ESG da empresa"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("gestor")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        self.matriz_de_acesso("Admin B2B")

        self.etapa("Isolamento dos dados da empresa")
        _, _, html = self.cliente.pedir("GET", "/admin/turmas")
        outras = self.banco(lambda: [t.nome for t in m.Turma.query.filter(m.Turma.empresa_id != self.contexto["ids"].get("empresa")).all() if t.nome])
        vistas = [n for n in outras if n and n in html]
        self.confere(f"{MARCA} Turma" in html, "Vê a turma da sua empresa no Hub", "REG", "A turma da empresa aparece.", "A turma da própria empresa não aparece.",
                     "Gestor Parceiro acompanha as turmas da sua empresa", "Alta", print_de="/admin/turmas")
        self.confere(not vistas, "Não vê turmas de outras empresas", "REG", f"Nenhuma das {len(outras)} turma(s) de outras empresas aparece.",
                     "Aparecem turmas de outras empresas: " + ", ".join(vistas[:5]), "Gestor Parceiro só vê os dados da sua empresa (LGPD)", "Alta",
                     "Filtrar gerenciar_turmas por Empresa.gestor_id == current_user.id quando o perfil for Admin B2B.")
        _, _, html = self.cliente.pedir("GET", "/bancas")
        self.confere(f"{MARCA} Projeto TCC" in html, "Vê a banca do projeto com jovens da sua empresa", "REG", "A banca aparece na agenda.",
                     "A banca do projeto da empresa não aparece.", "Agenda de bancas filtrada pela empresa", "Média", print_de="/bancas")

        self.etapa("Regra: avaliador só da própria empresa")
        email = f"avaliadoroutra_{DOMINIO}"
        self.post("/bancas/avaliadores", {"acao": "criar", "nome_completo": f"{MARCA} Avaliador outra empresa", "email": email, "senha": senha_forte(),
                                          "empresa_origem": "Outra Empresa Qualquer"})
        indevido = self.banco(lambda: m.Usuario.query.filter_by(email=email).first())
        self.confere(indevido is None, "Recusa avaliador de outra empresa", "PER", "Cadastro recusado.", "Criou avaliador de outra empresa.",
                     "Gestor Parceiro só cadastra avaliadores da sua empresa", "Alta")

        self.etapa("Relatório ESG")
        status, _, corpo = self.cliente.pedir("GET", "/admin/exportar-relatorio-esg")
        self.confere(status == 200, "Exporta o relatório ESG", "FLX", "Relatório gerado.", f"HTTP {status}.", "Relatório ESG da empresa", "Média")
        self.reportar_cobertura()


# ==============================================================================
# 4. PROFESSOR
# ==============================================================================
class AgenteProfessor(AgenteDoFluxo):
    chave, nome, perfil = "professor", "Agente Professor (Funcional)", "Professor"
    ROTEIRO = ["Primeiro acesso: perguntas, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Lança as notas da turma no diário de classe", "Regra: notas de 0 a 10", "Regra: Professor não cria grupos"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("professor")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        self.matriz_de_acesso("Professor")

        self.etapa("Diário de classe")
        turma_id = self.contexto["ids"].get("turma")
        aluno1 = self.usuario("aluno1")
        acomp = self.banco(lambda: m.Acompanhamento.query.filter(m.Acompanhamento.aluno_id == aluno1["id"],
                                                                m.Acompanhamento.curso_id.in_(self.contexto["ids"].get("cursos", []))).first())
        if not (turma_id and acomp):
            self.registrar("Diário de classe sem turma ou acompanhamento", FALHA, "FLX", "O Mentor Administrador não deixou a turma pronta.",
                           "Turma com alunos matriculados", "Alta")
            return
        self.post(f"/admin/notas?turma_id={turma_id}", {f"nota_tecnica_{acomp.id}": "8,5", f"nota_postura_{acomp.id}": "9"})
        gravado = self.banco(lambda: m.Acompanhamento.query.get(acomp.id))
        self.confere(gravado.nota_tecnica == 8.5 and gravado.nota_postura == 9.0, "Lança notas técnica e de postura", "FLX",
                     "Notas 8,5 e 9 gravadas.", f"Gravado: {gravado.nota_tecnica} / {gravado.nota_postura}.", "Diário de classe", "Alta",
                     print_de=f"/admin/notas?turma_id={turma_id}")
        self.post(f"/admin/notas?turma_id={turma_id}", {f"nota_tecnica_{acomp.id}": "15", f"nota_postura_{acomp.id}": "-2"})
        fora = self.banco(lambda: m.Acompanhamento.query.get(acomp.id))
        self.confere(fora.nota_tecnica == 8.5 and fora.nota_postura == 9.0, "Notas fora de 0 a 10 são recusadas", "VAL",
                     "Notas inválidas recusadas; as anteriores foram mantidas.",
                     f"Aceitou nota técnica {fora.nota_tecnica} e postura {fora.nota_postura}.", "Notas entre 0 e 10", "Média",
                     "Em gerenciar_notas, validar 0 <= nota <= 10 e informar o erro ao usuário.")
        if fora.nota_tecnica != 8.5:
            self.post(f"/admin/notas?turma_id={turma_id}", {f"nota_tecnica_{acomp.id}": "8,5", f"nota_postura_{acomp.id}": "9"})

        self.etapa("Regra: Professor não cria grupos")
        self.post("/admin/grupos", {"nome": f"{MARCA} Grupo indevido", "descricao": "x"})
        indevido = self.banco(lambda: m.Grupo.query.filter_by(nome=f"{MARCA} Grupo indevido").first())
        self.confere(indevido is None, "Professor não cria grupos", "PER", "Criação de grupo recusada.", "O Professor criou um grupo.",
                     "Só a gestão cria grupos", "Alta")
        self.reportar_cobertura()


# ==============================================================================
# 5. MENTOR
# ==============================================================================
class AgenteMentor(AgenteDoFluxo):
    chave, nome, perfil = "mentor", "Agente Mentor (Funcional)", "Mentor"
    ROTEIRO = ["Primeiro acesso: perguntas, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Agenda uma sessão de mentoria com o aluno (notificação)", "Registra o parecer no acompanhamento",
               "Lança horas de voluntariado do TCC (ESG)", "Regra: lançamento no futuro é recusado"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("mentor")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        self.matriz_de_acesso("Mentor")
        aluno1 = self.usuario("aluno1")

        self.etapa("Sessão de mentoria")
        amanha = date.today() + timedelta(days=1)
        self.post("/sessoes", {"acao": "agendar", "aluno_id": aluno1["id"], "data_sessao": amanha.isoformat(), "hora_inicio": "10:00",
                               "hora_fim": "11:00", "observacoes": f"{MARCA} Pauta da sessão"})
        sessao = self.banco(lambda: m.SessaoMentoria.query.filter_by(mentor_id=eu["id"], aluno_id=aluno1["id"]).first())
        aviso = self.banco(lambda: m.FeedbackSessao.query.filter_by(sessao_id=sessao.id, lida_pelo_aluno=False).count()) if sessao else 0
        self.confere(sessao is not None and aviso >= 1, "Agenda sessão e notifica o aluno", "FLX", "Sessão criada e aviso pendente para o aluno.",
                     "Sessão não criada ou sem aviso ao aluno.", "Agendamento de sessão notifica o aluno", "Alta", print_de="/sessoes")
        self.contexto["ids"]["sessao"] = sessao.id if sessao else None

        self.etapa("Parecer no acompanhamento")
        acomp = self.banco(lambda: m.Acompanhamento.query.filter_by(aluno_id=aluno1["id"]).first())
        if acomp:
            self.post("/acompanhamento", {"acao": "atualizar_parecer_livre", "acompanhamento_id": acomp.id, "observacao": f"{MARCA} Parecer do mentor"})
            gravado = self.banco(lambda: m.Acompanhamento.query.get(acomp.id).observacao)
            self.confere(gravado == f"{MARCA} Parecer do mentor", "Registra o parecer do mentor", "FLX", "Parecer gravado.", f"Gravado: {gravado}.",
                         "Mentor registra parecer no acompanhamento do aluno", "Média", print_de="/acompanhamento")

        self.etapa("Voluntariado (ESG)")
        projeto_id = self.contexto["ids"].get("projeto")
        ontem = date.today() - timedelta(days=1)
        self.post("/voluntariado/manual", {"tipo_atividade": "Leitura Assíncrona de TCC", "projeto_id": projeto_id, "data": ontem.isoformat(),
                                           "hora_inicio": "09:00", "hora_fim": "10:30"})
        horas = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu["id"]).all())
        self.confere(any(h.projeto_id == projeto_id for h in horas), "Lança horas de leitura do TCC", "FLX",
                     f"{len(horas)} lançamento(s) gravado(s) e vinculado(s) ao projeto.", "Lançamento não gravado.", "Horas de voluntariado para o ESG", "Média")
        futuro = date.today() + timedelta(days=5)
        antes = len(horas)
        self.post("/voluntariado/manual", {"tipo_atividade": "Leitura Assíncrona de TCC", "projeto_id": projeto_id, "data": futuro.isoformat(),
                                           "hora_inicio": "09:00", "hora_fim": "10:00"})
        depois = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=eu["id"]).count())
        self.confere(depois == antes, "Lançamento no futuro é recusado", "VAL", "Data futura recusada.", "Aceitou horas numa data futura.",
                     "Nada de horas no futuro", "Média")
        self.reportar_cobertura()


# ==============================================================================
# 6. ALUNO
# ==============================================================================
class AgenteAluno(AgenteDoFluxo):
    chave, nome, perfil = "aluno", "Agente Aluno (Funcional)", "Aluno"
    ROTEIRO = ["Primeiro acesso: perguntas de segurança (o aluno não assina o termo corporativo)", "Matriz de acesso do perfil",
               "Registra a frequência (uma por dia)", "Anotação no acompanhamento e retorno da sessão",
               "Entrega o TCC escrito e os slides (regras de formato)", "Regras: não cria projeto, não agenda sessão, não entra na sala da banca",
               "Regra: não cria tarefa em projeto de outro grupo"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("aluno1")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        self.matriz_de_acesso("Aluno")
        projeto_id = self.contexto["ids"].get("projeto")

        self.etapa("Frequência")
        self.post("/registrar_frequencia", {"tipo_presenca": "Presencial", "observacoes": f"{MARCA}"})
        self.post("/registrar_frequencia", {"tipo_presenca": "Presencial", "observacoes": f"{MARCA} repetida"})
        hoje = self.banco(lambda: m.Frequencia.query.filter(m.Frequencia.usuario_id == eu["id"]).count())
        self.confere(hoje == 1, "Frequência registrada uma vez por dia", "REG", "Uma presença hoje; a repetição foi ignorada.",
                     f"{hoje} registros no mesmo dia.", "Uma frequência por dia", "Média", print_de="/dashboard")

        self.etapa("Acompanhamento e sessão")
        acomp = self.banco(lambda: m.Acompanhamento.query.filter_by(aluno_id=eu["id"]).first())
        if acomp:
            self.post("/acompanhamento", {"acao": "atualizar_anotacao_livre", "acompanhamento_id": acomp.id, "observacao_aluno": f"{MARCA} Minhas anotações"})
            gravado = self.banco(lambda: m.Acompanhamento.query.get(acomp.id).observacao_aluno)
            self.confere(gravado == f"{MARCA} Minhas anotações", "Anotação do aluno no acompanhamento", "FLX", "Anotação gravada.", f"Gravado: {gravado}.",
                         "Aluno registra suas anotações", "Média", print_de="/acompanhamento")
        sessao_id = self.contexto["ids"].get("sessao")
        if sessao_id:
            self.post("/sessoes", {"acao": "enviar_feedback", "sessao_id": sessao_id, "comentario": f"{MARCA} Obrigado pela mentoria"})
            retorno = self.banco(lambda: m.FeedbackSessao.query.filter_by(sessao_id=sessao_id, autor_id=eu["id"]).count())
            self.confere(retorno == 1, "Aluno responde na sessão de mentoria", "FLX", "Comentário do aluno gravado.", "Comentário não gravado.",
                         "Aluno dá retorno da sessão", "Média", print_de="/sessoes")

        self.etapa("Entregas do TCC")
        if projeto_id:
            _, _, html = self.post(f"/projetos/{projeto_id}/entregas", {"tipo": "Escrito final", "observacao": f"{MARCA}"},
                                   {"arquivo": ("tcc_funcional.txt", b"texto")})
            invalida = self.banco(lambda: m.EntregaTCC.query.filter_by(projeto_id=projeto_id).count())
            self.confere(invalida == 0, "Entrega em formato errado é recusada", "VAL", "Arquivo .txt recusado para o escrito final (só PDF).",
                         "Aceitou .txt como escrito final.", "Escrito final só em PDF; slides em PDF/PPT", "Média")
            for tipo, nome in (("Escrito final", "tcc_funcional.pdf"), ("Slides da apresentação", "slides_funcional.pdf")):
                self.post(f"/projetos/{projeto_id}/entregas", {"tipo": tipo, "observacao": f"{MARCA}"}, {"arquivo": (nome, PDF_MINIMO)})
            entregas = self.banco(lambda: sorted(e.tipo for e in m.EntregaTCC.query.filter_by(projeto_id=projeto_id).all()))
            self.confere(entregas == ["Escrito final", "Slides da apresentação"], "Entrega o TCC escrito e os slides", "FLX",
                         "Escrito final e slides entregues (avaliador notificado).", f"Entregas gravadas: {entregas}.", "Entregas do TCC", "Crítica",
                         print_de="/projetos")

        self.etapa("Regras do perfil Aluno")
        self.post("/projetos", {"nome": f"{MARCA} Projeto do aluno", "descricao": "x", "grupo_id": self.contexto["ids"].get("grupo")})
        criado = self.banco(lambda: m.Projeto.query.filter_by(nome=f"{MARCA} Projeto do aluno").first())
        self.confere(criado is None, "Aluno não cadastra projeto", "PER", "Cadastro de projeto recusado.", "O aluno criou um projeto.",
                     "Aluno vê os projetos do grupo, mas não cadastra", "Alta")
        self.post("/sessoes", {"acao": "agendar", "aluno_id": eu["id"], "data_sessao": date.today().isoformat(), "hora_inicio": "10:00",
                               "hora_fim": "11:00", "observacoes": f"{MARCA} indevida"})
        indevida = self.banco(lambda: m.SessaoMentoria.query.filter_by(observacoes=f"{MARCA} indevida").first())
        self.confere(indevida is None, "Aluno não agenda sessão", "PER", "Agendamento recusado.", "O aluno agendou uma sessão.",
                     "Só mentores agendam sessões", "Alta")
        if projeto_id:
            status, destino, _ = self.cliente.pedir("GET", f"/projetos/banca/{projeto_id}")
            self.confere(status in (302, 303) and destino != f"/projetos/banca/{projeto_id}", "Aluno não entra na sala da banca", "PER",
                         f"Redirecionado para {destino}.", f"HTTP {status}: a sala da banca abriu para o aluno.", "Sala da banca só para avaliadores e gestão", "Alta")

        self.etapa("Regra: tarefas só nos projetos do próprio grupo")
        outro = self.banco(lambda: m.Projeto.query.filter(m.Projeto.grupo_id != self.contexto["ids"].get("grupo")).first())
        if outro:
            self.post("/projetos/nova_tarefa", {"projeto_id": outro.id, "descricao": f"{MARCA} Tarefa indevida", "status": "Pendente"})
            indevida = self.banco(lambda: m.Tarefa.query.filter_by(descricao=f"{MARCA} Tarefa indevida").first())
            self.confere(indevida is None, "Aluno não cria tarefa em projeto de outro grupo", "PER", "Criação recusada.",
                         f"O aluno criou uma tarefa no projeto '{outro.nome}', de outro grupo (IDOR).",
                         "Só membros do grupo (e a gestão) mexem nas tarefas do projeto", "Alta",
                         "Em nova_tarefa/atualizar_tarefa/deletar_tarefa, conferir se current_user é membro do grupo do projeto ou da gestão.")
        else:
            self.log("Não há projeto de outro grupo para testar")
        self.reportar_cobertura()


# ==============================================================================
# 7. AVALIADOR DA BANCA
# ==============================================================================
class AgenteAvaliador(AgenteDoFluxo):
    chave, nome, perfil = "avaliador", "Agente Avaliador da Banca (Funcional)", "Avaliador Banca"
    PAGINA_SONDA = "/minhas-bancas"  # o avaliador é restrito às páginas da banca
    ROTEIRO = ["Primeiro acesso: troca de senha obrigatória, perguntas e termo", "Regra: o avaliador só vê as áreas da banca",
               "Vê a banca em 'Minhas bancas'", "Regra: nota abaixo de 7 exige justificativa",
               "Avalia as etapas escrita e oral; a banca fecha sozinha e calcula a nota (40/40/20)"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("avaliador")
        eu["senha"] = self.primeiro_acesso(eu["email"], eu["senha"])
        projeto_id = self.contexto["ids"].get("projeto")

        self.etapa("Área restrita do avaliador")
        status, destino, _ = self.cliente.pedir("GET", "/projetos")
        self.confere(destino == "/minhas-bancas", "Avaliador fica restrito às áreas da banca", "PER", "Páginas fora da banca levam para 'Minhas bancas'.",
                     f"/projetos respondeu HTTP {status} (destino {destino}).", "Avaliador convidado só vê o que é da banca", "Alta")
        _, _, html = self.cliente.pedir("GET", "/minhas-bancas")
        self.confere(f"{MARCA} Projeto TCC" in html, "Vê a banca para a qual foi escalado", "FLX", "A banca aparece em 'Minhas bancas'.",
                     "A banca não aparece.", "Avaliador vê suas bancas", "Alta", print_de="/minhas-bancas")

        self.etapa("Avaliação do TCC")
        if not projeto_id:
            return
        self.post(f"/projetos/banca/{projeto_id}", {"acao": "etapa_escrita", "nota_escrita": "6"})
        sem_just = self.banco(lambda: m.AvaliacaoBanca.query.filter_by(projeto_id=projeto_id, avaliador_id=eu["id"]).first())
        self.confere(sem_just is None or sem_just.nota_escrita is None, "Nota abaixo de 7 sem justificativa é recusada", "REG",
                     "A plataforma exigiu a justificativa.", "Aceitou nota 6 sem justificativa.", "Nota < 7 exige justificativa (10+ caracteres)", "Média")
        self.post(f"/projetos/banca/{projeto_id}", {"acao": "etapa_escrita", "nota_escrita": "8,5"})
        self.post(f"/projetos/banca/{projeto_id}", {"acao": "etapa_oral", "nota_apresentacao": "9", "nota_visual": "8",
                                                    "feedback_jovens": f"{MARCA} Ótima apresentação"})
        projeto = self.banco(lambda: m.Projeto.query.get(projeto_id))
        banca = self.banco(lambda: m.Banca.query.filter_by(projeto_id=projeto_id).first())
        esperada = round(8.5 * 0.4 + 9 * 0.4 + 8 * 0.2, 2)
        self.confere(projeto.nota_final == esperada, "Nota final pela fórmula oficial (40/40/20)", "REG",
                     f"Nota final {projeto.nota_final} = 8,5×0,4 + 9×0,4 + 8×0,2.", f"Nota final {projeto.nota_final}; esperado {esperada}.",
                     "Nota final = escrito 40% + apresentação 40% + visual 20%", "Alta", print_de=f"/projetos/banca/{projeto_id}")
        self.confere(banca.status == "Realizada" and projeto.status == "Concluído", "Banca fecha quando todos os avaliadores concluem", "REG",
                     "Banca realizada e projeto concluído (nota ≥ 7).", f"Banca '{banca.status}', projeto '{projeto.status}'.",
                     "Com todos os avaliadores concluídos, a banca encerra e o projeto é aprovado com nota ≥ 7", "Alta")
        self.reportar_cobertura()


# ==============================================================================
# 8. ENCERRAMENTO (Mentor Administrador)
# ==============================================================================
class AgenteEncerramento(AgenteDoFluxo):
    chave, nome, perfil = "encerramento", "Agente Encerramento do Ciclo (Mentor Administrador)", "Mentor Administrador"
    ROTEIRO = ["Publica o resultado da banca para o grupo", "Aprova a versão final e leva o TCC para o acervo",
               "Emite o certificado do aluno e confere a verificação pública", "Regra: certificado só para quem participou do projeto"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("mentoradmin")
        self.etapa("Login do Mentor Administrador")
        status, destino = self.entrar(eu["email"], eu["senha"])
        self.confere(destino not in (None, "/"), "Mentor Administrador volta à plataforma", "ACE", f"Login aceito ({destino}).",
                     f"Login recusado (HTTP {status}).", "Login com a senha definida no primeiro acesso", "Crítica")
        projeto_id, banca_id = self.contexto["ids"].get("projeto"), self.contexto["ids"].get("banca")
        if not (projeto_id and banca_id):
            return

        self.etapa("Publicação do resultado")
        self.post("/bancas", {"acao": "publicar", "banca_id": banca_id})
        projeto = self.banco(lambda: m.Projeto.query.get(projeto_id))
        avisos = self.banco(lambda: m.Notificacao.query.filter_by(usuario_id=self.usuario("aluno1")["id"], referencia=f"resultado:{projeto_id}").count())
        self.confere(projeto.notas_publicadas and avisos == 1, "Publica o resultado e avisa o grupo", "FLX", "Notas publicadas e aluno notificado.",
                     f"Publicado: {projeto.notas_publicadas}; avisos ao aluno: {avisos}.", "Resultado divulgado aos jovens", "Alta", print_de="/bancas")

        self.etapa("Acervo de TCCs")
        self.post(f"/projetos/{projeto_id}/aprovar-versao-final", {"tema": f"{MARCA} Dados", "resumo": "Resumo do TCC funcional",
                                                                    "palavras_chave": "teste", "visibilidade": "Pública"})
        item = self.banco(lambda: m.TCCAcervo.query.filter_by(projeto_id=projeto_id).first())
        self.confere(item is not None and item.arquivo_pdf, "Aprova a versão final para o acervo", "FLX", "TCC copiado para o acervo.",
                     "O TCC não entrou no acervo.", "Versão final aprovada vai para o acervo", "Alta", print_de="/biblioteca")
        if item:
            self.confere(item.visibilidade == "Interna", "Sem autorização registrada o TCC não fica público", "REG",
                         "Pedido 'Pública' sem autorização → ficou 'Interna'.", f"Ficou '{item.visibilidade}' sem autorização.",
                         "Publicação só com autorização dos jovens/responsáveis (LGPD)", "Alta")

        self.etapa("Certificados")
        aluno1, aluno2 = self.usuario("aluno1"), self.usuario("aluno2")
        status, destino, html = self.cliente.pedir("GET", f"/certificado/{projeto_id}/{aluno1['id']}")
        cert = self.banco(lambda: m.CertificadoEmitido.query.filter_by(projeto_id=projeto_id, usuario_id=aluno1["id"]).first())
        self.confere(status == 200 and cert is not None, "Emite o certificado do aluno", "FLX", f"Certificado {cert.codigo if cert else ''} emitido.",
                     f"HTTP {status}; certificado não registrado.", "Certificado para quem concluiu o TCC", "Alta",
                     print_de=f"/certificado/{projeto_id}/{aluno1['id']}")
        if cert:
            from base import Cliente
            publico = Cliente()
            status, _, html = publico.pedir("GET", f"/certificado/verificar/{cert.codigo}")
            self.confere(status == 200 and cert.codigo in html, "Verificação pública do certificado", "FLX", "O código confere sem login.",
                         f"HTTP {status} na verificação.", "Qualquer pessoa confere a autenticidade pelo código", "Média")
        status, destino, _ = self.cliente.pedir("GET", f"/certificado/{projeto_id}/{aluno2['id']}")
        indevido = self.banco(lambda: m.CertificadoEmitido.query.filter_by(projeto_id=projeto_id, usuario_id=aluno2["id"]).first())
        self.confere(indevido is None, "Certificado recusado para quem não participou", "REG", f"Recusado (destino {destino}).",
                     "Emitiu certificado para aluno fora do grupo.", "Certificado só para participantes do projeto", "Alta")
        self.reportar_cobertura()


AGENTES = {a.chave: a for a in (AgenteAdministrador, AgenteMentorAdministrador, AgenteGestorParceiro, AgenteProfessor, AgenteMentor,
                                AgenteAluno, AgenteAvaliador, AgenteEncerramento)}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in AGENTES:
        print("Uso: python agentes_funcionalidades/agente_fluxo.py <" + "|".join(AGENTES) + ">")
        sys.exit(2)
    AGENTES[sys.argv[1]]().executar()
    print(json.dumps({"fim": sys.argv[1]}))
