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

from base import (AgenteFuncional, FALHA, ALERTA, MARCA, DOMINIO, senha_forte, mensagens, RAIZ_PROJETO, regra_da_plataforma)

# PNG de 1×1 pixel (logo do parceiro B2B)
PNG_MINIMO = __import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
PDF_MINIMO = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
              b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def _modelos():
    import models
    return models


def cobertura_da_ultima_execucao():
    """Funções exercitadas pelos agentes na última execução (relatórios Funcional_*.json mais recentes de cada agente)."""
    import glob
    from base import PASTA_RELATORIOS
    cobertas = set()
    for chave in ("administrador", "mentor_administrador", "gestor_parceiro", "professor", "mentor", "aluno", "avaliador", "encerramento"):
        arquivos = glob.glob(os.path.join(PASTA_RELATORIOS, "**", f"Funcional_{chave}_2*.json"), recursive=True)
        if arquivos:
            try:
                with open(max(arquivos, key=os.path.getmtime), encoding="utf-8") as f:
                    cobertas |= set(json.load(f).get("cobertura", []))
            except (OSError, ValueError):
                continue
    return cobertas


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
        # Uma função nova só fica "sem teste" se NENHUM agente da cadeia a exercita: conta o que já rodou nesta execução
        # e o que a última execução completa cobriu (ex.: o convite é testado pelo Mentor Administrador, depois do Administrador)
        acumulada = set(self.contexto.get("cobertura", [])) | self.cobertura
        self.contexto["cobertura"] = sorted(acumulada)
        cobertas = acumulada | set(self.contexto.get("cobertura_anterior") or cobertura_da_ultima_execucao())
        novas = sorted((set(self.regras.get("funcoes_novas", [])) & self._funcoes_do_perfil()) - cobertas)
        if novas:
            self.etapa("Funções novas aprendidas")
            self.registrar(f"{len(novas)} função(ões) nova(s) aprendida(s) sem teste funcional", ALERTA, "FLX",
                           ", ".join(novas), "Toda função nova entra no fluxo de teste", "Baixa",
                           "O Gerente de Funcionalidades aprendeu estas funções novas; criar o passo de teste correspondente.")

    def regra_reuniao(self, participante):
        """Reuniões ITM × B2B fora da gestão: participante vê a ata e salva na agenda; quem não participou não vê nada;
        ninguém fora da gestão envia convite (o envio dispara e-mails em nome da coordenação)."""
        m = _modelos()
        reuniao_id = self.contexto["ids"].get("reuniao")
        if not reuniao_id:
            return
        self.etapa(f"Regra: reunião ITM × B2B para o perfil {self.perfil}")
        status_ics, _, ics = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}/agenda.ics")
        abriu = status_ics == 200 and "BEGIN:VCALENDAR" in ics
        if participante:
            self.confere(abriu, f"{self.perfil} participante salva a reunião na agenda", "PER", "Baixou o .ics da reunião.",
                         f"HTTP {status_ics}: o participante não conseguiu baixar o .ics.", "Participante salva a reunião na agenda", "Média")
        else:
            self.confere(not abriu, f"{self.perfil} que não participou não vê a reunião", "PER", "Acesso ao .ics recusado.",
                         "Baixou o .ics de uma reunião da qual não participou.", "Só participantes e gestão veem a reunião", "Alta",
                         "Em agenda_reuniao_ics, conferir pode_ver_reuniao antes de gerar o arquivo.")
        self.post(f"/reunioes/{reuniao_id}/convite", {"via": "smtp"})
        enviado = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao_id).convite_enviado_em)
        self.confere(enviado is None, f"{self.perfil} não envia convite de reunião", "PER", "Envio de convite recusado.",
                     f"O perfil {self.perfil} conseguiu disparar o convite.", "Só a gestão envia convites", "Alta")
        self.presenca_na_reuniao(reuniao_id, participante)

    def avaliar(self, alvo_tipo, avaliado_id, notas, comentario=""):
        """Responde uma avaliação do ciclo 360° aberto pela gestão no fluxo (notas de 1 a 5 por critério)."""
        ciclo_id = self.contexto["ids"].get("ciclo")
        dados = {"ciclo_id": ciclo_id, "alvo_tipo": alvo_tipo, "comentario": comentario}
        if avaliado_id:
            dados["avaliado_id"] = avaliado_id
        dados.update({f"nota_{i}": n for i, n in enumerate(notas)})
        self.post("/avaliacoes/responder", dados)
        m = _modelos()
        meu_id = self.banco(lambda: m.Usuario.query.filter_by(email=self.email_logado).first().id)
        return self.banco(lambda: m.RespostaAvaliacao.query.filter_by(ciclo_id=ciclo_id, avaliador_id=meu_id, alvo_tipo=alvo_tipo,
                                                                       avaliado_id=avaliado_id).first() is not None)

    def presenca_na_reuniao(self, reuniao_id, participante):
        """Reunião de Alinhamento: participante faz check-in/out e avalia; quem não participa não registra presença."""
        m = _modelos()
        meu_id = self.banco(lambda: m.Usuario.query.filter_by(email=self.email_logado).first().id)
        self.etapa(f"Presença e avaliação da reunião ({self.perfil})")
        self.post(f"/reunioes/{reuniao_id}/presenca", {"acao": "checkin"})
        if not participante:
            presenca = self.banco(lambda: m.PresencaReuniao.query.filter_by(reuniao_id=reuniao_id, usuario_id=meu_id).first())
            self.confere(presenca is None, f"{self.perfil} que não participou não faz check-in", "PER", "Check-in recusado.",
                         "Registrou presença numa reunião da qual não participa.", "Só participantes registram presença", "Alta",
                         "Em presenca_reuniao, conferir se current_user está em reuniao.participantes.")
            return
        self.post(f"/reunioes/{reuniao_id}/presenca", {"acao": "checkout"})
        presenca = self.banco(lambda: m.PresencaReuniao.query.filter_by(reuniao_id=reuniao_id, usuario_id=meu_id).first())
        self.confere(presenca is not None and presenca.check_out is not None, f"{self.perfil} faz check-in e check-out na reunião", "FLX",
                     "Entrada e saída registradas (base das horas ESG).", "Presença não registrada.",
                     "Check-in/check-out real nas reuniões ITM × B2B", "Alta", print_de=f"/reunioes/{reuniao_id}")
        self.post(f"/reunioes/{reuniao_id}/feedback", {"nota": "9"})
        self.post(f"/reunioes/{reuniao_id}/feedback", {"nota": "4", "comentario": f"{MARCA} Reunião objetiva"})
        nota = self.banco(lambda: [f.nota for f in m.FeedbackReuniao.query.filter_by(reuniao_id=reuniao_id, usuario_id=meu_id).all()])
        self.confere(nota == [4], f"{self.perfil} avalia a reunião (nota 1 a 5)", "FLX", "Avaliação gravada; nota 9 recusada.",
                     f"Avaliações gravadas: {nota}.", "Feedback dos participantes da reunião", "Média")
        outro = self.banco(lambda: next((p.id for p in m.ReuniaoInstitucional.query.get(reuniao_id).participantes if p.id != meu_id), None))
        if outro:
            self.post(f"/reunioes/{reuniao_id}/presenca", {"acao": "manual", "usuario_id": outro, "entrada": "00:00", "saida": "00:30"})
            indevida = self.banco(lambda: m.PresencaReuniao.query.filter_by(reuniao_id=reuniao_id, usuario_id=outro, registro_manual=True).count())
            self.confere(indevida == 0, f"{self.perfil} não lança presença dos outros", "PER", "Lançamento recusado.",
                         "Lançou a presença de outra pessoa.", "Só a gestão lança presença de quem esqueceu", "Alta")

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
               "Assistente da Plataforma: base dos gerentes, documento PRD com versões, perguntas com fontes (sem consumir a IA)",
               "Provedores de IA: liga/desliga do Assistente, ordem de modelos validada e gasto do mês",
               "Cria o Mentor Administrador e passa a vez para ele"]

    def rodar(self):
        # A cobertura da execução anterior vira referência; a desta execução recomeça vazia
        anterior = self.contexto.get("cobertura") or []
        self.contexto.update({"execucao": self.contexto.get("execucao") or self.carimbo, "usuarios": {}, "ids": {},
                              "cobertura_anterior": anterior, "cobertura": []})
        sys.path.insert(0, os.path.join(RAIZ_PROJETO, "agentes_omnitest"))
        email_admin = "administrador_ominitest@local.com"
        from nucleo import preparar_usuario
        preparar_usuario("administrador")
        self.primeiro_acesso(email_admin, senha_de_teste())
        self.matriz_de_acesso("Administrador")

        self.etapa("Validações do cadastro de usuários")
        casos = [("e-mail inválido", {"email": "sem-arroba"}, "não é válido"),
                 ("e-mail já cadastrado", {"email": email_admin}, "já está cadastrado"),
                 ("senha fraca", {"email": f"senhafraca_{DOMINIO}", "senha": "abc12345"}, f"{regra_da_plataforma('senha_min_caracteres')} caracteres")]
        for nome, ajuste, trecho in casos:
            form = {"nome": f"{MARCA} Teste", "email": f"invalido_{DOMINIO}", "tipo_usuario": "Aluno", "status": "Ativo", "senha": senha_forte(),
                    "forcar_troca_senha": "False", **ajuste}
            _, _, html = self.post("/admin/usuarios", form)
            criado = self.banco(lambda: _modelos().Usuario.query.filter_by(email=form["email"]).count())
            self.confere(trecho in html and (criado == 0 or form["email"] == email_admin), f"Cadastro recusa {nome}", "VAL",
                         f"Recusado com a mensagem certa: {trecho}.", f"Não recusou como esperado. Mensagens: {' | '.join(mensagens(html))[:200]}",
                         f"Cadastro de usuário recusa {nome}", "Alta")

        self.parametros_de_regras()
        self.credenciais_dos_agentes()
        self.assistente_da_plataforma()
        self.provedores_de_ia()

        self.etapa("Cria o Mentor Administrador")
        self.criar_usuario("mentoradmin", "Mentor Administrador", "Mentor Administrador")
        self.reportar_cobertura()

    def assistente_da_plataforma(self):
        """Assistente da Plataforma (chat): base dos Agentes gerentes, documento PRD com versões, fonte desativada, formato
        recusado e perguntas com fontes. A conta de teste (@local.com) responde no modo offline: o agente NUNCA consome a IA.
        No fim apaga o que criou (documentos, arquivos e conversas)."""
        self.etapa("Assistente da Plataforma (chat e base de conhecimento)")
        m = _modelos()
        status, _, pagina = self.cliente.pedir("GET", "/admin/assistente")
        gerentes = self.banco(lambda: [(f.total_trechos, f.ativo) for f in m.FonteConhecimento.query.filter_by(tipo="GERENTES").all()])
        self.confere(status == 200 and 'id="cardChat"' in pagina and 'id="cardFontesBase"' in pagina and gerentes and gerentes[0][0] > 0,
                     "Assistente abre com a base dos Agentes gerentes", "FLX",
                     f"Página com chat e base; fonte dos gerentes com {gerentes[0][0] if gerentes else 0} trechos.",
                     f"HTTP {status}; fonte dos gerentes: {gerentes}.", "Chat bot com o conhecimento dos Agentes gerentes", "Alta",
                     print_de="/admin/assistente")

        def perguntar(texto, conversa_id=None):
            form = {"pergunta": texto}
            if conversa_id:
                form["conversa_id"] = str(conversa_id)
            st, _, corpo = self.post("/admin/assistente/perguntar", form, seguir=False)
            try:
                return st, json.loads(corpo)
            except ValueError:
                return st, {}

        self.post("/admin/assistente/sincronizar", {})
        st, dados = perguntar("Quais módulos cada perfil pode acessar?")
        resposta = dados.get("resposta") or {}
        conversas = [dados.get("conversa_id")] if dados.get("conversa_id") else []
        self.confere(st == 200 and resposta.get("modo") == "offline" and any(f.get("tipo") == "GERENTES" for f in resposta.get("fontes", [])),
                     "Pergunta respondida com fontes dos gerentes, sem consumir a IA", "FLX",
                     f"{len(resposta.get('fontes', []))} fonte(s) citada(s); modo {resposta.get('modo')} (conta de teste).",
                     f"HTTP {st}; resposta {str(dados)[:200]}.", "Respostas citam as fontes; agentes não gastam a IA", "Alta",
                     "Em chat_assistente.perguntar, contas @local.com usam resposta_offline e as fontes vêm de base_conhecimento.buscar.")

        termo = "girassolzinho"
        titulo = f"{MARCA} PRD do programa"
        prd = f"# PRD\n## Requisito {termo}\nO requisito {termo} define a jornada do jovem no programa.\n".encode("utf-8")
        self.post("/admin/assistente/documentos", {"tipo": "PRD", "titulo": titulo}, arquivos={"arquivo": ("prd.md", prd)})
        self.post("/admin/assistente/documentos", {"tipo": "PRD", "titulo": titulo},
                           arquivos={"arquivo": ("prd_v2.md", prd.replace(b"jornada", b"jornada completa"))})
        versoes = self.banco(lambda: [(f.id, f.versao, f.ativo, f.total_trechos, f.arquivo_caminho)
                                      for f in m.FonteConhecimento.query.filter_by(titulo=titulo).order_by(m.FonteConhecimento.versao).all()])
        certo = len(versoes) == 2 and versoes[0][2] is False and versoes[1][2] is True and versoes[1][1] == 2 and versoes[1][3] > 0
        self.confere(certo, "Documento PRD entra na base e o reenvio cria a versão 2", "FLX",
                     "v1 desativada e v2 ativa, com trechos.", f"Versões gravadas: {[(v[1], v[2], v[3]) for v in versoes]}.",
                     "Base pronta para receber PRD, PTD e DTD no fim do projeto", "Alta",
                     "Em base_conhecimento.adicionar_documento, mesmo tipo e título geram a versão seguinte e desativam as anteriores.")

        st, dados = perguntar(f"O que diz o requisito {termo}?", conversas[0] if conversas else None)
        fontes = (dados.get("resposta") or {}).get("fontes", [])
        ids_citados = {f.get("fonte_id") for f in fontes}
        ativa = versoes[-1][0] if versoes else None
        antiga = versoes[0][0] if versoes else None
        self.confere(st == 200 and ativa in ids_citados and antiga not in ids_citados, "Resposta cita o PRD ativo (e não a versão antiga)", "FLX",
                     "O trecho do PRD v2 aparece nas fontes.", f"Fontes citadas: {[(f.get('fonte'), f.get('versao')) for f in fontes]}.",
                     "Chat responde com base nos documentos do projeto", "Alta")

        if ativa:
            self.post(f"/admin/assistente/documentos/{ativa}/situacao", {"ativo": "0"})
        st, dados = perguntar(f"O que diz o requisito {termo}?", conversas[0] if conversas else None)
        fontes = (dados.get("resposta") or {}).get("fontes", [])
        self.confere(st == 200 and all(f.get("fonte_id") not in (ativa, antiga) for f in fontes), "Fonte desativada sai das respostas", "FLX",
                     "Com o PRD desativado, ele não é mais citado.", f"Ainda citou: {[f.get('fonte') for f in fontes]}.",
                     "Administrador escolhe quais fontes o Assistente usa", "Média")

        antes = self.banco(lambda: m.FonteConhecimento.query.count())
        self.post("/admin/assistente/documentos", {"tipo": "DTD", "titulo": f"{MARCA} executável"},
                           arquivos={"arquivo": ("programa.exe", b"MZ" * 40)})
        depois = self.banco(lambda: m.FonteConhecimento.query.count())
        self.confere(depois == antes, "Formato não aceito é recusado", "VAL", "O .exe foi recusado sem gravar nada.",
                     f"Fontes {antes} → {depois}.", "Só .md, .txt, .html, .docx e .pdf entram na base", "Alta")

        # Limpeza pelo próprio site: documentos (com os arquivos) e conversas criadas pelo teste
        for fonte_id, *_ in versoes:
            self.post(f"/admin/assistente/documentos/{fonte_id}/excluir", {})
        for conversa_id in conversas:
            self.post(f"/admin/assistente/conversa/{conversa_id}/excluir", {})
        sobras = self.banco(lambda: m.FonteConhecimento.query.filter_by(titulo=titulo).count())
        arquivos = [v[4] for v in versoes if v[4] and os.path.exists(v[4])]
        self.confere(sobras == 0 and not arquivos, "Excluir documento apaga os trechos e o arquivo", "FLX",
                     "Documentos de teste e arquivos removidos.", f"Sobraram {sobras} fonte(s) e {len(arquivos)} arquivo(s).",
                     "Exclusão de documento da base", "Média")

    def provedores_de_ia(self):
        """Provedores de IA: a tela mostra o gasto do mês e os usos; desligar o Assistente tira o chat do ar (e religa no fim,
        voltando ao estado de antes); ordem com modelo inexistente é recusada sem mudar nada. Nenhuma IA é chamada."""
        self.etapa("Provedores de IA (liga/desliga e ordem de modelos)")
        status, _, pagina = self.cliente.pedir("GET", "/admin/provedores-ia")
        self.confere(status == 200 and 'id="cardGastoIa"' in pagina and 'id="interruptor_assistente"' in pagina and 'id="cardPrecosIa"' in pagina,
                     "Tela de Provedores de IA com gasto, usos e preços", "FLX", "Gasto do mês, interruptores e preços na tela.",
                     f"HTTP {status} ou cartões ausentes.", "Administrador controla as IAs e o custo", "Alta", print_de="/admin/provedores-ia")

        import provedores_ia
        ligado_antes = self.banco(lambda: provedores_ia.ativo("assistente"))
        ordem_antes = self.banco(lambda: provedores_ia.ordem("assistente"))
        self.post("/admin/provedores-ia/uso/assistente", {"ligado": "0"})
        st, _, corpo = self.post("/admin/assistente/perguntar", {"pergunta": "teste com o Assistente desligado"}, seguir=False)
        _, _, painel = self.cliente.pedir("GET", "/dashboard")
        botao_no_painel = 'id="btnAssistenteMenu"' in painel
        self.confere(st == 409 and not botao_no_painel, "Assistente desligado não responde e some das páginas", "FLX",
                     "Pergunta recusada (409) e o botão de chat sumiu.", f"HTTP {st}; botão no painel: {botao_no_painel}.",
                     "Administrador liga e desliga o chat bot", "Alta",
                     "Em assistente_perguntar, recusar quando provedores_ia.ativo('assistente') for falso; no base.html, não incluir o botão.")
        self.post("/admin/provedores-ia/uso/assistente", {"ligado": "1" if ligado_antes else "0"})
        self.post("/admin/provedores-ia/uso/assistente", {"modelos": ["modelo-que-nao-existe"]})
        depois = self.banco(lambda: (provedores_ia.ativo("assistente"), provedores_ia.ordem("assistente")))
        self.confere(depois == (ligado_antes, ordem_antes), "Ordem com modelo inexistente é recusada e o estado volta ao de antes", "VAL",
                     f"Ordem mantida ({', '.join(ordem_antes)}) e Assistente {'ligado' if ligado_antes else 'desligado'} como antes.",
                     f"Antes {(ligado_antes, ordem_antes)} → depois {depois}.", "Só modelos cadastrados entram na ordem", "Alta")

        catalogo_antes = self.banco(lambda: provedores_ia.modelos())
        self.post("/admin/provedores-ia/precos", {"entrada_claude-haiku-5-5": "abc", "saida_claude-haiku-5-5": "0.5"})
        self.post("/admin/provedores-ia/modelos", {"provedor": "gemini", "modelo": "Modelo Inválido!", "nome": "x"})
        catalogo_depois = self.banco(lambda: provedores_ia.modelos())
        self.confere(catalogo_depois == catalogo_antes, "Preço e modelo inválidos são recusados sem gravar nada", "VAL",
                     "Preço não numérico e identificador de modelo inválido recusados.",
                     "O catálogo de modelos ou os preços mudaram.", "Preços e modelos só com valores válidos", "Média",
                     "Em provedores_ia.salvar_precos/adicionar_modelo, validar antes de gravar.")

    def credenciais_dos_agentes(self):
        """Área Agentes IA: o quadro de credenciais existe e NUNCA mostra a senha das contas de teste (só a situação).
        O agente não grava nada aqui: as credenciais reais do servidor não são alteradas pelo teste."""
        self.etapa("Credenciais dos agentes (só leitura)")
        status, _, pagina = self.cliente.pedir("GET", "/admin/agentes-ia")
        senha = senha_de_teste()
        self.confere(status == 200 and 'id="cardCredenciaisIa"' in pagina and (not senha or senha not in pagina),
                     "Credenciais dos agentes sem expor a senha", "SEG", "Quadro de credenciais presente; nenhum valor aparece na página.",
                     "Quadro ausente ou a senha das contas de teste aparece na página.",
                     "Administrador cadastra as credenciais dos agentes na plataforma, cifradas", "Alta", print_de="/admin/agentes-ia")

    def parametros_de_regras(self):
        """Tela Parâmetros de regras: abre com todos os grupos e RECUSA valores inválidos sem gravar nada.
        O agente não altera nenhuma regra real (o fluxo de teste não pode mudar o comportamento da plataforma)."""
        self.etapa("Parâmetros de regras (validações)")
        m = _modelos()
        _, _, pagina = self.cliente.pedir("GET", "/admin/parametros-regras")
        grupos = [g for g in ("frequencia", "notas", "banca", "seguranca") if f'id="grupo_{g}"' in pagina]
        self.confere(len(grupos) == 4, "Tela de parâmetros com todos os grupos de regras", "FLX", "Frequência, notas, banca e senhas.",
                     f"Grupos encontrados: {grupos}.", "Administrador ajusta as regras de negócio pela tela", "Média", print_de="/admin/parametros-regras")
        antes = self.banco(lambda: (m.ParametroRegra.query.count(), m.HistoricoParametro.query.count()))
        self.post("/admin/parametros-regras", {"valor_banca_peso_escrito": "70", "valor_banca_peso_apresentacao": "40", "valor_banca_peso_visual": "20"})
        self.post("/admin/parametros-regras", {"valor_freq_minima_pct": "150"})
        self.post("/admin/parametros-regras", {"acao": "criar", "nova_chave": "freq_minima_pct", "nova_nome": "Duplicada", "nova_tipo": "inteiro",
                                               "nova_valor": "1"})
        depois = self.banco(lambda: (m.ParametroRegra.query.count(), m.HistoricoParametro.query.count()))
        self.confere(depois == antes, "Parâmetros inválidos são recusados sem gravar nada", "VAL",
                     "Pesos que não somam 100%, frequência fora de 1 a 100 e código duplicado foram recusados.",
                     f"Algo foi gravado: parâmetros/histórico {antes} → {depois}.", "Regras só mudam com valores válidos", "Alta",
                     "Em regras_negocio.salvar_varios/criar, validar tipo, limites, soma dos pesos e código antes de gravar.")


# ==============================================================================
# 2. MENTOR ADMINISTRADOR — monta todo o programa
# ==============================================================================
class AgenteMentorAdministrador(AgenteDoFluxo):
    chave, nome, perfil = "mentor_administrador", "Agente Mentor Administrador (Funcional)", "Mentor Administrador"
    ROTEIRO = ["Primeiro acesso: perguntas de segurança, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Regra: Mentor Administrador não cria Administrador", "Cria os cursos do catálogo",
               "Cria Gestor Parceiro, Mentor, Professor, 2 Alunos e o Avaliador da banca",
               "Cria a empresa parceira (gestor e mentor), o grupo e a turma (matrícula automática)",
               "Matricula outro aluno, cria o projeto, a tarefa e agenda a banca com o avaliador",
               'Reunião ITM × B2B: ata, arquivo .ics, Salvar na agenda e convite que nunca vai para contas de teste']

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
        from regras_negocio import padrao_senha_forte
        forte = bool(_re.match(self.banco(padrao_senha_forte), senha))
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
        self.reuniao_e_convite()
        self.abrir_ciclo_360()
        self.reportar_cobertura()

    def abrir_ciclo_360(self):
        m = _modelos()
        empresa_id = self.contexto["ids"].get("empresa")
        self.etapa("Avaliação 360°: abre o ciclo do parceiro")
        hoje = date.today()
        titulo = f"{MARCA} Avaliação 360°"
        base = {"acao": "criar", "titulo": titulo, "tipo": "360", "inicio": hoje.isoformat(), "fim": (hoje + timedelta(days=7)).isoformat(),
                "empresa_id": empresa_id or ""}
        self.post("/avaliacoes/ciclos", dict(base, fim=(hoje - timedelta(days=3)).isoformat()))
        self.post("/avaliacoes/ciclos", base)
        ciclos = self.banco(lambda: [(c.id, c.empresa_id) for c in m.CicloAvaliacao.query.filter_by(titulo=titulo).all()])
        self.confere(len(ciclos) == 1 and ciclos[0][1] == empresa_id, "Abre o ciclo de avaliação 360° do parceiro", "FLX",
                     "Ciclo aberto (o período inválido foi recusado).", f"Ciclos gravados: {ciclos}.",
                     "Avaliação de todos: jovem, mentor, gestores ITM e B2B e o programa", "Alta", print_de="/avaliacoes#ciclos")
        if not ciclos:
            return
        self.contexto["ids"]["ciclo"] = ciclos[0][0]
        mentor, aluno1 = self.usuario("mentor"), self.usuario("aluno1")
        avisados = self.banco(lambda: {n.usuario_id for n in m.Notificacao.query.filter_by(referencia=f"avaliacao-ciclo:{ciclos[0][0]}").all()})
        self.confere(mentor["id"] in avisados and aluno1["id"] in avisados, "Quem avalia é avisado", "FLX",
                     f"{len(avisados)} pessoa(s) avisada(s) no sino.", f"Avisados: {sorted(avisados)}.", "Aviso de avaliação aberta", "Média")

    def remarcar_reuniao(self, reuniao, base):
        """Remarca a reunião para agora (abre o check-in dos participantes) trocando a modalidade: vira histórico e aviso."""
        m = _modelos()
        self.etapa("Reunião de Alinhamento: remarcação, pontos do parceiro e gravação")
        inicio = (datetime.now() - timedelta(minutes=10)).replace(second=0, microsecond=0)
        form = dict(base, tipo="Alinhamento", data_hora=inicio.strftime("%Y-%m-%dT%H:%M"), modalidade="Presencial", local_ou_link="Sala do ITM",
                    pontos_parceiro=f"{MARCA} Jovens chegando atrasados às palestras", contar_voluntariado="on",
                    motivo_alteracao=f"{MARCA} Antecipada a pedido do parceiro")
        form.pop("enviar_convite", None)
        self.post(f"/reunioes/{reuniao.id}/editar", dict(form, link_gravacao="javascript:alert(1)"))
        def situacao():
            r = m.ReuniaoInstitucional.query.get(reuniao.id)
            return type("Situacao", (), {"link_gravacao": r.link_gravacao, "tipo": r.tipo, "pontos_parceiro": r.pontos_parceiro,
                                         "controle_presenca": r.controle_presenca, "alteracoes": [a.mudancas for a in r.alteracoes]})
        r = self.banco(situacao)
        self.confere(r.link_gravacao is None and not r.alteracoes, "Link de gravação inválido é recusado", "VAL", "Só links http(s) são aceitos.",
                     f"Gravou o link {r.link_gravacao}.", "Gravação só por link http(s)", "Alta",
                     "Em salvar_reuniao_do_formulario, aceitar só esquema http/https no link da gravação.")
        self.post(f"/reunioes/{reuniao.id}/editar", dict(form, link_gravacao="https://drive.google.com/funcional-gravacao"))
        r = self.banco(situacao)
        mudancas = r.alteracoes[0] if r.alteracoes else ""
        avisados = self.banco(lambda: {n.usuario_id for n in m.Notificacao.query.filter(m.Notificacao.referencia.like(f"reuniao-alterada:{reuniao.id}:%")).all()})
        mentor = self.usuario("mentor")
        self.confere(len(r.alteracoes) == 1 and "Modalidade: Online → Presencial" in mudancas and (not mentor or mentor["id"] in avisados),
                     "Remarcação vai para o histórico e avisa os participantes", "FLX",
                     f"Histórico: {mudancas.replace(chr(10), '; ')}; {len(avisados)} participante(s) avisado(s).",
                     f"Histórico: {len(r.alteracoes)} registro(s); avisados: {sorted(avisados)}.",
                     "Alterações de data e modalidade com histórico e aviso", "Alta", print_de=f"/reunioes/{reuniao.id}")
        self.confere(r.tipo == "Alinhamento" and (r.pontos_parceiro or "").startswith(MARCA) and r.link_gravacao and r.controle_presenca,
                     "Reunião de Alinhamento com pontos do parceiro e gravação", "FLX", "Tipo, pontos do parceiro e link da gravação gravados.",
                     f"Tipo {r.tipo}; pontos {bool(r.pontos_parceiro)}; gravação {r.link_gravacao}.",
                     "B2B pontua as falhas do programa na Reunião de Alinhamento", "Média")

    def contas_microsoft(self, reuniao_id):
        """Microsoft 365 ao lado do Gmail: a lista "Contas conectadas" oferece as duas contas; o login vai para a Microsoft
        (o agente NÃO segue o redirecionamento: nenhuma conta real é usada) e resposta forjada é recusada."""
        m = _modelos()
        self.etapa("Contas conectadas: Gmail e Microsoft 365")
        _, _, pagina = self.cliente.pedir("GET", f"/reunioes/{reuniao_id}")
        self.confere('id="listaContasConvite"' in pagina and 'id="opcaoContaMicrosoft"' in pagina, "Lista de contas com Gmail e Microsoft 365", "FLX",
                     "A lista 'Contas conectadas' oferece o Microsoft 365 (Outlook).", "Lista de contas ausente ou sem o Microsoft 365.",
                     "Cliente usa Office 365: convite pelo Outlook", "Alta", print_de=f"/reunioes/{reuniao_id}")
        status, destino, _ = self.cliente.pedir("GET", f"/conectar-microsoft?voltar=/reunioes/{reuniao_id}")
        microsoft = bool(destino) and "/oauth2/v2.0/authorize" in destino
        interno = bool(destino) and destino.startswith("/reunioes")
        self.confere(status in (302, 303) and (microsoft or interno), "Conectar Microsoft 365 leva ao login oficial (ou avisa que falta configurar)", "FLX",
                     "Redireciona para o login da Microsoft." if microsoft else "Aplicativo ainda não configurado: volta para a reunião com aviso.",
                     f"HTTP {status}; destino {destino}.", "Login oficial da Microsoft, sem senha na plataforma", "Alta")
        meu_id = self.banco(lambda: m.Usuario.query.filter_by(email=self.email_logado).first().id)
        self.cliente.pedir("GET", "/oauth-microsoft/callback?code=forjado&state=forjado")
        conectada = self.banco(lambda: m.ContaConectada.query.filter_by(usuario_id=meu_id).count())
        self.confere(conectada == 0, "Resposta forjada do Microsoft 365 é recusada", "SEG", "Sem o 'state' do pedido, nada é salvo.",
                     "Uma resposta forjada conectou uma conta.", "Proteção contra CSRF no retorno do login", "Crítica",
                     "Em oauth_microsoft, comparar o state recebido com o guardado na sessão (hmac.compare_digest).")

    def reuniao_e_convite(self):
        """Reuniões ITM × B2B: registra a ata, confere o arquivo de agenda (.ics) e os links "Salvar na agenda", e garante que
        o convite NUNCA sai para contas de teste — o agente não dispara e-mail de verdade (só contas @local.com e domínios .test)."""
        m = _modelos()
        self.etapa("Reunião ITM × B2B e convite por e-mail")
        mentor, gestor, professor = self.usuario("mentor"), self.usuario("gestor"), self.usuario("professor")
        empresa_id = self.contexto["ids"].get("empresa")
        _, _, formulario = self.cliente.pedir("GET", "/reunioes/nova")
        self.confere('id="rParceiro"' in formulario and f'value="{empresa_id}"' in formulario, "Formulário oferece o parceiro B2B da reunião", "FLX",
                     "Campo Parceiro B2B com a empresa parceira do programa.", "Campo Parceiro B2B ausente ou sem a empresa.",
                     "Reunião ITM × B2B indica o parceiro", "Média")
        quando = (datetime.now() + timedelta(days=5)).replace(hour=14, minute=30, second=0, microsecond=0)
        titulo = f"{MARCA} Alinhamento ITM × B2B"
        # O Professor não pertence ao parceiro: mesmo enviado à força, o servidor tem de descartá-lo
        base_reuniao = {"titulo": titulo, "empresa_id": empresa_id or "", "data_hora": quando.strftime("%Y-%m-%dT%H:%M"),
                        "duracao_minutos": "45", "modalidade": "Online", "local_ou_link": "https://meet.google.com/funcional-teste",
                        "pauta": "Cronograma, bancas; certificados", "participantes": [x["id"] for x in (mentor, gestor, professor) if x],
                        "participantes_externos": "Parceiro Externo – Empresa Teste – parceiro@empresa-funcional.test",
                        "enviar_convite": "1", "convite_via": "smtp"}
        self.post("/reunioes/nova", base_reuniao)
        reuniao = self.banco(lambda: m.ReuniaoInstitucional.query.filter_by(titulo=titulo).first())
        participantes = self.banco(lambda: sorted(p.id for p in m.ReuniaoInstitucional.query.get(reuniao.id).participantes)) if reuniao else []
        self.confere(reuniao is not None and all(x["id"] in participantes for x in (mentor, gestor) if x), "Registra a reunião ITM × B2B com participantes",
                     "FLX", f"Reunião gravada com {len(participantes)} participante(s) da plataforma.", "Reunião não gravada ou sem os participantes.",
                     "Gestão registra reuniões com participantes internos e externos", "Alta", print_de="/reunioes")
        if not reuniao:
            return
        self.confere(reuniao.empresa_id == empresa_id and (not professor or professor["id"] not in participantes),
                     "Participantes limitados ao parceiro B2B escolhido", "REG",
                     "Reunião ligada à empresa parceira; o Professor (fora do parceiro) foi descartado pelo servidor.",
                     f"Parceiro gravado: {reuniao.empresa_id}; participantes: {participantes}.",
                     "Com parceiro escolhido, só entram o gestor B2B, os mentores e os avaliadores da empresa", "Alta",
                     "Em salvar_reuniao_do_formulario, filtrar os participantes por ids_do_parceiro(empresa).")
        self.contexto["ids"]["reuniao"] = reuniao.id
        self.confere(reuniao.convite_enviado_em is None, "Convite não vai para contas de teste", "REG",
                     "Nenhum convite enviado: todos os convidados são contas de teste ou domínios .test.",
                     f"Convite registrado como enviado ({reuniao.convite_enviado_via}) para: {reuniao.convite_destinatarios}.",
                     "Contas de teste (@local.com, .test) nunca recebem convite", "Crítica",
                     "Em convites_reuniao.destinatarios, ignorar DOMINIOS_DE_TESTE antes de montar a lista.")

        status, _, ics = self.cliente.pedir("GET", f"/reunioes/{reuniao.id}/agenda.ics")
        inicio_utc = (quando + timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")
        fim_utc = (quando + timedelta(hours=3, minutes=45)).strftime("%Y%m%dT%H%M%SZ")
        partes_ok = all(p in ics for p in ("BEGIN:VCALENDAR", "METHOD:PUBLISH", f"DTSTART:{inicio_utc}", f"DTEND:{fim_utc}",
                                           f"UID:reuniao-{reuniao.id}@", "SUMMARY:"))
        linhas_ok = all(len(linha.encode("utf-8")) <= 75 for linha in ics.split("\r\n"))
        self.confere(status == 200 and partes_ok and linhas_ok and "ATTENDEE" not in ics, "Arquivo de agenda (.ics) da reunião", "FLX",
                     f"iCalendar válido: 14:30 de Brasília = {inicio_utc[9:13]} UTC, 45 min, linhas de até 75 bytes.",
                     f"HTTP {status}; campos obrigatórios {'ok' if partes_ok else 'faltando'}; linhas {'ok' if linhas_ok else 'acima de 75 bytes'}.",
                     "Salvar a reunião no Outlook, Apple e outros pelo .ics (RFC 5545)", "Alta")
        self.confere("\\;" in ics and "\\," in ics, "Texto da pauta escapado no .ics", "VAL", "Ponto e vírgula e vírgula escapados.",
                     "Pauta sem escape: agendas podem cortar o texto.", "Texto escapado conforme a RFC 5545", "Baixa")

        _, _, pagina = self.cliente.pedir("GET", f"/reunioes/{reuniao.id}")
        provedores = {"Google Agenda": "calendar.google.com", "Outlook.com": "outlook.live.com", "Microsoft 365": "outlook.office.com",
                      "Yahoo Agenda": "calendar.yahoo.com", ".ics": f"/reunioes/{reuniao.id}/agenda.ics"}
        faltando = [nome for nome, alvo in provedores.items() if alvo not in pagina]
        self.confere(not faltando, "Salvar na agenda: Google, Outlook, Microsoft 365, Yahoo e .ics", "FLX",
                     "Os 5 destinos de agenda aparecem na página da reunião.", f"Faltando: {', '.join(faltando)}.",
                     "Botão Salvar na minha agenda com os provedores mais usados", "Média", print_de=f"/reunioes/{reuniao.id}")
        self.confere("cardConvite" in pagina and "Sem convite" in pagina and "Parceiro Externo" in pagina,
                     "Painel de convite separa contas de teste", "REG",
                     "As contas de teste e o domínio .test aparecem em 'Sem convite'.", "Painel de convite ausente ou sem a lista de contas de teste.",
                     "Painel de convite mostra quem recebe e quem fica de fora", "Média")

        self.post(f"/reunioes/{reuniao.id}/convite", {"via": "smtp", "convidados": ["parceiro@empresa-funcional.test", self.usuario("mentor")["email"]]})
        depois = self.banco(lambda: m.ReuniaoInstitucional.query.get(reuniao.id).convite_enviado_em)
        self.confere(depois is None, "Reenvio manual também ignora contas de teste", "REG", "Nada foi enviado.",
                     "O reenvio disparou convite para conta de teste.", "Contas de teste nunca recebem convite", "Crítica")

        self.contas_microsoft(reuniao.id)

        # Desconectar o Gmail só limpa a conexão desta sessão (o agente nunca conecta um Gmail de verdade)
        _, _, html = self.post("/desconectar-gmail", {})
        _, _, pagina = self.cliente.pedir("GET", f"/reunioes/{reuniao.id}")
        self.confere("Gmail conectado:" not in pagina and "cardConvite" in pagina, "Desconectar Gmail volta ao estado sem conta conectada", "FLX",
                     "Sessão sem Gmail; o painel de convite continua disponível.", "Painel ainda mostra um Gmail conectado.",
                     "Coordenação desconecta o Gmail quando quiser", "Baixa")
        self.remarcar_reuniao(reuniao, base_reuniao)


# ==============================================================================
# 3. GESTOR PARCEIRO (Admin B2B)
# ==============================================================================
class AgenteGestorParceiro(AgenteDoFluxo):
    chave, nome, perfil = "gestor_parceiro", "Agente Gestor Parceiro (Funcional)", "Admin B2B"
    ROTEIRO = ["Primeiro acesso: perguntas e termo", "Matriz de acesso do perfil",
               "Regra: só vê a turma e a banca da sua empresa", "Regra: avaliador só da própria empresa", "Relatório ESG da empresa",
               "Envia o logo da empresa para o certificado (só PNG/JPG/WEBP de verdade)"]

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
        self.logo_da_empresa()
        self.avaliacao_do_gestor()
        self.reportar_cobertura()

    def avaliacao_do_gestor(self):
        mentor = self.usuario("mentor")
        if not self.contexto["ids"].get("ciclo"):
            return
        self.etapa("Avaliação 360°: gestor B2B avalia o mentor, a gestão ITM e o programa")
        ok = self.avaliar("Mentor", mentor["id"], [3, 4, 4, 4], f"{MARCA} Precisa responder mais rápido") and \
            self.avaliar("Gestão ITM", None, [4, 4, 5]) and self.avaliar("Programa", None, [5, 4, 4])
        self.confere(ok, "Gestor B2B avalia mentor, gestão ITM e programa", "FLX", "Três avaliações gravadas.", "Alguma avaliação não foi gravada.",
                     "Gestores B2B avaliam mentores e o programa", "Alta", print_de="/avaliacoes")
        professor = self.usuario("professor")
        if professor:
            indevida = self.avaliar("Mentor", professor["id"], [1, 1, 1, 1])
            self.confere(not indevida, "Gestor B2B não avalia quem não é da empresa", "PER", "Avaliação recusada.",
                         "Avaliou um mentor de fora da empresa.", "Cada um avalia só quem acompanha", "Alta",
                         "Em responder_avaliacao, conferir o alvo em alvos_da_avaliacao(current_user, ciclo).")

    def logo_da_empresa(self):
        """Logo do parceiro B2B no certificado: recusa SVG e arquivo disfarçado; aceita PNG de verdade e o serve sem login."""
        m = _modelos()
        empresa_id = self.contexto["ids"].get("empresa")
        if not empresa_id:
            return
        self.etapa("Logo da empresa parceira (certificado)")
        self.post(f"/empresas/{empresa_id}/logo/enviar", {}, {"logo": ("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>")})
        self.post(f"/empresas/{empresa_id}/logo/enviar", {}, {"logo": ("logo.png", b"GIF89a arquivo disfarcado")})
        indevido = self.banco(lambda: m.Empresa.query.get(empresa_id).logo_arquivo)
        self.confere(indevido is None, "Recusa logo em SVG ou arquivo disfarçado", "VAL", "SVG e GIF com extensão .png recusados.",
                     f"Gravou o arquivo {indevido}.", "Logo só em PNG, JPG ou WEBP conferidos pelo conteúdo", "Alta",
                     "Em enviar_logo_empresa, conferir os bytes iniciais do arquivo (não só a extensão) e recusar SVG.")
        self.post(f"/empresas/{empresa_id}/logo/enviar", {}, {"logo": ("logo.png", PNG_MINIMO)})
        logo = self.banco(lambda: m.Empresa.query.get(empresa_id).logo_arquivo)
        from base import Cliente
        status, _, corpo = Cliente().pedir("GET", f"/empresas/{empresa_id}/logo")
        self.confere(bool(logo) and status == 200 and "PNG" in corpo[:8], "Envia o logo da empresa para o certificado", "FLX",
                     "Logo gravado e servido (sem login) para o certificado.", f"Logo: {logo}; HTTP {status} ao abrir a imagem.",
                     "Parceiro B2B coloca o próprio logo no certificado", "Média", print_de="/admin/turmas")


# ==============================================================================
# 4. PROFESSOR
# ==============================================================================
class AgenteProfessor(AgenteDoFluxo):
    chave, nome, perfil = "professor", "Agente Professor (Funcional)", "Professor"
    ROTEIRO = ["Primeiro acesso: perguntas, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Lança as notas da turma no diário de classe", "Regra: notas de 0 a 10", "Regra: Professor não cria grupos",
               'Regra: quem não participou não vê a reunião nem envia convite']

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

        self.etapa("Situação do aluno pelas regras parametrizadas")
        _, _, diario = self.cliente.pedir("GET", f"/admin/notas?turma_id={turma_id}")
        from regras_negocio import regra
        media_minima = self.banco(lambda: regra("nota_minima_diario"))
        esperado = "Aprovado" if 8.75 >= float(media_minima) else "Reprovado por nota"
        self.confere('id="regraDiario"' in diario and esperado in diario, "Diário mostra a situação do aluno pela regra atual", "REG",
                     f"Média 8,75 com média mínima {media_minima}: '{esperado}', sem falsa alerta de faltas.",
                     f"Situação '{esperado}' ou a legenda da regra não apareceram no diário.",
                     "Diário calcula aprovado/reprovado por nota e por faltas (Parâmetros de regras)", "Média", print_de=f"/admin/notas?turma_id={turma_id}")
        self.confere("Em risco" not in diario.split('id="regraDiario"')[-1], "Aluno sem faltas não aparece em risco", "REG",
                     "Nenhum aluno sem faltas marcado em risco.", "Aluno sem nenhuma falta apareceu 'Em risco'.",
                     "Risco por faltas só com faltas registradas", "Média",
                     "Em situacao_frequencia, só marcar 'Em risco' quando houver faltas.")

        self.etapa("Regra: Professor não cria grupos")
        self.post("/admin/grupos", {"nome": f"{MARCA} Grupo indevido", "descricao": "x"})
        indevido = self.banco(lambda: m.Grupo.query.filter_by(nome=f"{MARCA} Grupo indevido").first())
        self.confere(indevido is None, "Professor não cria grupos", "PER", "Criação de grupo recusada.", "O Professor criou um grupo.",
                     "Só a gestão cria grupos", "Alta")
        self.regra_reuniao(participante=False)
        self.reportar_cobertura()


# ==============================================================================
# 5. MENTOR
# ==============================================================================
class AgenteMentor(AgenteDoFluxo):
    chave, nome, perfil = "mentor", "Agente Mentor (Funcional)", "Mentor"
    ROTEIRO = ["Primeiro acesso: perguntas, termo e trilha do TCC", "Matriz de acesso do perfil",
               "Agenda uma sessão de mentoria com o aluno (notificação)", "Registra o parecer no acompanhamento",
               "Lança horas de voluntariado do TCC (ESG)", "Regra: lançamento no futuro é recusado",
               'Regra: participante salva a reunião na agenda, mas não envia convite',
               "Registra ocorrência com responsável e prazo do retorno", "Pede a desistência de um jovem (a gestão confirma)"]

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

        self.etapa("Gráficos do projeto (Gantt e gráficos sob demanda)")
        if projeto_id:
            _, _, pagina = self.cliente.pedir("GET", "/projetos")
            import re as _re
            series = _re.search(rf'<script type="application/json" id="seriesProjeto{projeto_id}">(.*?)</script>', pagina, _re.S)
            dados = json.loads(series.group(1)) if series else {}
            self.confere(f'id="abaGraficos{projeto_id}"' in pagina and "gantt-barra" in pagina.split(f'id="graficosProjeto{projeto_id}"')[-1],
                         "Aba Gráficos com o Gantt das tarefas", "FLX", "Cronograma com a barra da tarefa do projeto.",
                         "Aba Gráficos ou barra do Gantt ausente.", "Mentor acompanha o cronograma do projeto", "Média", print_de="/projetos")
            self.confere(sum(dados.get("status", {}).get("valores", [])) >= 1 and {"responsavel", "horas", "prazo"} <= set(dados),
                         "Dados para gráficos sob demanda", "FLX", f"{len(dados)} tipos de gráfico com as tarefas do projeto.",
                         "Séries dos gráficos vazias ou incompletas.", "Mentor gera gráficos do projeto para o acompanhamento", "Baixa")
        self.regra_reuniao(participante=True)
        self.ocorrencia_e_desistencia()
        self.avaliacao_do_mentor()
        self.ata_do_encontro()
        self.reportar_cobertura()

    def ata_do_encontro(self):
        """Ata digital estruturada: resumo, fontes e plano de ação; os próximos passos vão para o jovem."""
        m = _modelos()
        eu, aluno1 = self.usuario("mentor"), self.usuario("aluno1")
        self.etapa("Ata estruturada do encontro e próximos passos")
        ata = {"ata_resumo": f"{MARCA} Revisamos o problema de pesquisa e a metodologia.", "ata_fontes": "Manual de TCC do programa",
               "ata_plano_acao": "Reescrever a introdução\nTrazer três referências", "enviar_proximos_passos": "1"}
        futura = self.contexto["ids"].get("sessao")
        if futura:
            self.post(f"/sessoes/{futura}/ata", ata)
            cedo = self.banco(lambda: m.SessaoMentoria.query.get(futura).ata_registrada_em)
            self.confere(cedo is None, "Ata antes do encontro é recusada", "VAL", "Só depois do encontro.", "Registrou ata de um encontro futuro.",
                         "Ata registrada depois do encontro", "Média")
        ontem = date.today() - timedelta(days=1)
        self.post("/sessoes", {"acao": "agendar", "aluno_id": aluno1["id"], "data_sessao": ontem.isoformat(), "hora_inicio": "15:00",
                               "hora_fim": "16:00", "observacoes": f"{MARCA} Encontro de ontem"})
        passada = self.banco(lambda: m.SessaoMentoria.query.filter_by(mentor_id=eu["id"], observacoes=f"{MARCA} Encontro de ontem").first())
        if not passada:
            self.log("Sessão passada não criada: ata não testada")
            return
        self.contexto["ids"]["sessao_ata"] = passada.id
        self.post(f"/sessoes/{passada.id}/ata", ata)
        s = self.banco(lambda: m.SessaoMentoria.query.get(passada.id))
        aviso = self.banco(lambda: m.Notificacao.query.filter(m.Notificacao.usuario_id == aluno1["id"],
                                                                m.Notificacao.referencia.like(f"proximos-passos:{passada.id}:%")).count())
        self.confere(bool(s.ata_resumo and s.ata_fontes and s.ata_plano_acao and s.proximos_passos_enviados_em) and aviso == 1,
                     "Registra a ata estruturada e envia os próximos passos", "FLX",
                     "Resumo, fontes e plano de ação gravados; o jovem recebeu os próximos passos.",
                     f"Ata incompleta ou sem aviso ao jovem (avisos: {aviso}).",
                     "Ata digital com resumo das deliberações, fontes recomendadas e plano de ação", "Alta", print_de="/sessoes")

    def avaliacao_do_mentor(self):
        if not self.contexto["ids"].get("ciclo"):
            return
        self.etapa("Avaliação 360°: mentor avalia o jovem")
        aluno1 = self.usuario("aluno1")
        _, _, painel = self.cliente.pedir("GET", "/dashboard")
        self.confere('id="alertaAvaliacoes"' in painel, "Painel avisa das avaliações pendentes", "FLX", "Aviso de avaliações no painel.",
                     "Painel sem o aviso de avaliações pendentes.", "Pendência de avaliação visível", "Média", print_de="/dashboard")
        self.avaliar("Jovem", aluno1["id"], [7, 3, 3, 4])
        recusada = not self.avaliar("Jovem", aluno1["id"], [7, 3, 3, 4])
        gravada = self.avaliar("Jovem", aluno1["id"], [4, 3, 3, 4], f"{MARCA} Bom progresso")
        self.confere(recusada and gravada, "Mentor avalia o jovem (notas de 1 a 5)", "FLX", "Nota 7 recusada; avaliação gravada.",
                     "Aceitou nota fora de 1–5 ou não gravou a avaliação.", "Mentor avalia o jovem", "Alta")

    def ocorrencia_e_desistencia(self):
        m = _modelos()
        aluno1, aluno2, responsavel = self.usuario("aluno1"), self.usuario("aluno2"), self.usuario("mentoradmin")
        self.etapa("Ocorrência sobre o jovem (retorno com prazo)")
        base_form = {"aluno_id": aluno1["id"], "responsavel_id": responsavel["id"], "categoria": "Entregas", "contexto": "Mentoria",
                     "gravidade": "Média", "acoes": "Conversa individual na mentoria."}
        self.post("/ocorrencias/nova", dict(base_form, descricao=f"{MARCA} Prazo no passado não pode",
                                            prazo_resposta=(date.today() - timedelta(days=1)).isoformat()))
        indevida = self.banco(lambda: m.Ocorrencia.query.filter(m.Ocorrencia.descricao == f"{MARCA} Prazo no passado não pode").count())
        self.confere(indevida == 0, "Ocorrência com prazo no passado é recusada", "VAL", "Prazo vencido recusado.",
                     "Aceitou prazo de retorno no passado.", "Prazo do retorno a partir de hoje", "Média")
        self.post("/ocorrencias/nova", dict(base_form, descricao=f"{MARCA} Jovem atrasou duas entregas seguidas.",
                                            prazo_resposta=(date.today() + timedelta(days=3)).isoformat()))
        oc = self.banco(lambda: m.Ocorrencia.query.filter(m.Ocorrencia.descricao == f"{MARCA} Jovem atrasou duas entregas seguidas.").first())
        avisos = self.banco(lambda: {n.usuario_id for n in m.Notificacao.query.filter_by(referencia=f"ocorrencia:{oc.id}").all()}) if oc else set()
        self.confere(oc is not None and responsavel["id"] in avisos and aluno1["id"] not in avisos, "Registra ocorrência e avisa o responsável",
                     "FLX", f"Ocorrência gravada; {len(avisos)} pessoa(s) da equipe avisada(s); o jovem não.",
                     f"Ocorrência: {bool(oc)}; avisados: {sorted(avisos)}.", "Ocorrência com ações, responsável, prazo e aviso (sem expor ao jovem)",
                     "Alta", print_de="/ocorrencias")
        if oc:
            self.contexto["ids"]["ocorrencia"] = oc.id
            _, _, pagina = self.cliente.pedir("GET", "/ocorrencias")
            self.confere(f"/ocorrencias/{oc.id}" in pagina and "Aguardando retorno" in pagina, "Painel mostra o sinal da ocorrência", "FLX",
                         "Ocorrência listada com o sinal 'Aguardando retorno'.", "Ocorrência ou sinal ausente no painel.",
                         "Sinal de alerta para retorno pendente", "Média", print_de="/ocorrencias")

        self.etapa("Pedido de desistência (a gestão confirma)")
        self.post("/desistencias", {"aluno_id": aluno2["id"], "categoria": "Trabalho", "motivo": f"{MARCA} Começou a trabalhar no horário dos encontros.",
                                    "data_saida": date.today().isoformat(), "confirmar_agora": "1"})
        pedido = self.banco(lambda: m.Desistencia.query.filter_by(usuario_id=aluno2["id"]).first())
        self.confere(pedido is not None and pedido.status == "Solicitada", "Mentor registra o pedido de desistência", "FLX",
                     "Pedido gravado como 'Solicitada' (o mentor não confirma sozinho).", f"Pedido: {pedido.status if pedido else 'não gravado'}.",
                     "Mentor pede a desistência; a gestão confirma", "Alta", print_de="/desistencias")
        if pedido:
            self.contexto["ids"]["desistencia"] = pedido.id
            self.post(f"/desistencias/{pedido.id}/decidir", {"acao": "confirmar"})
            situacao = self.banco(lambda: m.Desistencia.query.get(pedido.id).status)
            self.confere(situacao == "Solicitada", "Mentor não confirma a desistência", "PER", "Confirmação recusada ao mentor.",
                         f"O mentor confirmou a desistência (status {situacao}).", "Só a gestão ITM ou o gestor B2B confirmam", "Alta",
                         "Em decidir_desistencia, conferir pode_decidir_desistencia antes de qualquer ação.")


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

        if self.contexto["ids"].get("ciclo"):
            self.etapa("Avaliação 360°: jovem avalia o mentor e o programa")
            mentor = self.usuario("mentor")
            ok = self.avaliar("Mentor", mentor["id"], [2, 3, 4, 4], f"{MARCA} Demora a responder no chat") and self.avaliar("Programa", None, [5, 5, 4])
            self.confere(ok, "Jovem avalia o mentor e o programa", "FLX", "Avaliações gravadas.", "Avaliação não gravada.",
                         "Jovem avalia o mentor", "Alta", print_de="/avaliacoes")
            _, _, pagina = self.cliente.pedir("GET", "/avaliacoes")
            self.confere('id="resultados"' not in pagina and 'id="ciclos"' not in pagina and "Ruído de comunicação" not in pagina,
                         "Jovem não vê resultados, ciclos nem alertas", "PER", "Só as avaliações dele.",
                         "A página mostra resultados, ciclos ou alertas ao jovem.", "Resultados só para a gestão", "Alta")

        sessao_ata = self.contexto["ids"].get("sessao_ata")
        if sessao_ata:
            self.etapa("Ata do encontro (só leitura)")
            _, _, pagina = self.cliente.pedir("GET", "/sessoes")
            self.confere(f'id="modalAta{sessao_ata}"' in pagina and "Reescrever a introdução" in pagina and f"/sessoes/{sessao_ata}/ata" not in pagina,
                         "Jovem vê a ata e os próximos passos, sem editar", "PER", "Ata visível só para leitura.",
                         "Ata ausente ou com formulário de edição para o jovem.", "Só o mentor registra a ata; o jovem consulta", "Alta",
                         print_de="/sessoes")
            self.post(f"/sessoes/{sessao_ata}/ata", {"ata_resumo": f"{MARCA} Alterada pelo jovem", "ata_plano_acao": "x"})
            resumo = self.banco(lambda: m.SessaoMentoria.query.get(sessao_ata).ata_resumo or "")
            self.confere("Alterada pelo jovem" not in resumo, "Jovem não altera a ata", "PER", "Alteração recusada.", "O jovem alterou a ata.",
                         "Só o mentor registra a ata", "Alta")

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
               "Emite o certificado do aluno e confere a verificação pública", "Regra: certificado só para quem participou do projeto",
               "Confirma a desistência (jovem sai da turma e do mentor) e reativa", "Dá retorno e resolve a ocorrência",
               "Certificado com o logo do parceiro B2B; remove o logo", "Lança a presença de quem esqueceu o check-in da reunião",
               "Mentor desistente: substituto assume os jovens; reativação"]

    def rodar(self):
        m = _modelos()
        eu = self.usuario("mentoradmin")
        self.etapa("Login do Mentor Administrador")
        status, destino = self.entrar(eu["email"], eu["senha"])
        self.confere(destino not in (None, "/"), "Mentor Administrador volta à plataforma", "ACE", f"Login aceito ({destino}).",
                     f"Login recusado (HTTP {status}).", "Login com a senha definida no primeiro acesso", "Crítica")
        self.desistencia_e_ocorrencia()
        self.presenca_lancada_pela_gestao()
        self.resultado_da_avaliacao()
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
        self.logo_no_certificado(projeto_id, aluno1)
        self.mentor_desistente()
        self.reportar_cobertura()

    def mentor_desistente(self):
        """Mentor desistente: o Professor do fluxo assume os jovens, grupos, turmas e sessões futuras; as horas ficam com o mentor."""
        m = _modelos()
        mentor, professor = self.usuario("mentor"), self.usuario("professor")
        if not (mentor and professor):
            return
        self.etapa("Mentor desistente: substituição e reativação")
        horas_antes = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(usuario_id=mentor["id"]).count())
        jovens = self.banco(lambda: sorted(a.id for a in m.Usuario.query.get(mentor["id"]).alunos))
        form = {"mentor_id": mentor["id"], "substituto_id": "", "data_saida": date.today().isoformat(), "categoria": "Trabalho",
                "motivo": f"{MARCA} Mudou de área e não terá agenda."}
        self.post("/desistencias/mentor", form)
        recusado = self.banco(lambda: m.Usuario.query.get(mentor["id"]).status) == "Ativo"
        self.confere(recusado, "Sem substituto, o desligamento de mentor com jovens é recusado", "VAL", "Pediu o substituto.",
                     "Desligou o mentor sem ninguém para assumir os jovens.", "Jovens nunca ficam sem mentor", "Alta")
        self.post("/desistencias/mentor", dict(form, substituto_id=professor["id"]))
        def situacao():
            mt, pf = m.Usuario.query.get(mentor["id"]), m.Usuario.query.get(professor["id"])
            return (mt.status, sorted(a.id for a in mt.alunos), sorted(a.id for a in pf.alunos),
                    m.CheckinVoluntariado.query.filter_by(usuario_id=mentor["id"]).count())
        status, do_mentor, do_professor, horas = self.banco(situacao)
        self.confere(status == "Desistente" and not do_mentor and set(jovens) <= set(do_professor) and horas == horas_antes,
                     "Mentor desistente: substituto assume os jovens e as horas ficam", "REG",
                     f"{len(jovens)} jovem(ns) passaram ao substituto; {horas} lançamento(s) de horas continuam com o mentor.",
                     f"Status {status}; jovens do mentor {do_mentor}; do substituto {do_professor}; horas {horas_antes}→{horas}.",
                     "Transferência dos jovens e grupos para o substituto, mantendo as horas", "Crítica", print_de="/desistencias")
        registro = self.banco(lambda: m.Desistencia.query.filter_by(usuario_id=mentor["id"]).first())
        if registro:
            self.post(f"/desistencias/{registro.id}/decidir", {"acao": "reativar"})
            reativado = self.banco(lambda: m.Usuario.query.get(mentor["id"]).status) == "Ativo"
            self.confere(reativado, "Gestão reativa o mentor", "FLX", "Acesso devolvido; os jovens seguem com o substituto.",
                         "O mentor continuou desligado.", "Mentor pode voltar ao programa", "Média")

    def _situacao_jovem(self, usuario_id):
        m = _modelos()
        return self.banco(lambda: (lambda u: (u.status, len(u.turmas_como_aluno), u.mentores.count()))(m.Usuario.query.get(usuario_id)))

    def resultado_da_avaliacao(self):
        m = _modelos()
        ciclo_id, mentor = self.contexto["ids"].get("ciclo"), self.usuario("mentor")
        if not ciclo_id:
            return
        self.etapa("Avaliação 360°: alerta de ruído de comunicação, resultados e encerramento")
        _, _, pagina = self.cliente.pedir("GET", "/avaliacoes")
        alertas = pagina.split('id="alertas"')[-1].split('id="resultados"')[0]
        self.confere("Ruído de comunicação" in alertas and f"{MARCA} Mentor" in alertas, "Alerta de ruído de comunicação do mentor", "REG",
                     "Média de Comunicação 2,5 (jovem 2 e gestor B2B 3) abaixo do limite 3,5: alerta na aba Alertas.",
                     "O alerta de ruído de comunicação não apareceu.", "Alerta de ruído de comunicação (limite em Parâmetros de regras)", "Alta",
                     print_de="/avaliacoes#alertas")
        resultados = pagina.split('id="resultados"')[-1].split('id="ciclos"')[0]
        self.confere(f"{MARCA} Demora a responder no chat" in resultados, "Gestão ITM vê resultados e comentários", "FLX",
                     "Médias por critério e comentários na aba Resultados.", "Comentários ausentes nos resultados.", "Resultados da avaliação 360°", "Média")
        self.post("/avaliacoes/ciclos", {"acao": "encerrar", "ciclo_id": ciclo_id})
        encerrado = self.banco(lambda: m.CicloAvaliacao.query.get(ciclo_id).encerrado_em is not None)
        self.confere(encerrado, "Gestão encerra o ciclo", "FLX", "Ciclo encerrado.", "O ciclo continuou aberto.", "Encerramento do ciclo", "Baixa")

    def presenca_lancada_pela_gestao(self):
        m = _modelos()
        rid, gestor = self.contexto["ids"].get("reuniao"), self.usuario("gestor")
        if not (rid and gestor):
            return
        self.etapa("Reunião: presença de quem esqueceu o check-in (gestão)")
        inicio = self.banco(lambda: m.ReuniaoInstitucional.query.get(rid).data_hora)
        self.post(f"/reunioes/{rid}/presenca", {"acao": "manual", "usuario_id": gestor["id"], "entrada": inicio.strftime("%H:%M"),
                                                "saida": datetime.now().strftime("%H:%M"), "modalidade": "Online"})
        horas = self.banco(lambda: m.CheckinVoluntariado.query.filter_by(reuniao_id=rid, usuario_id=gestor["id"]).first())
        self.confere(horas is not None and horas.total_minutos > 0, "Gestão lança a presença de quem esqueceu (vira hora ESG)", "FLX",
                     f"{horas.total_minutos if horas else 0} minuto(s) lançados no voluntariado do gestor B2B.", "Presença ou hora ESG não lançada.",
                     "Horas da reunião pela presença real", "Média", print_de=f"/reunioes/{rid}")
        _, _, ata = self.cliente.pedir("GET", f"/reunioes/{rid}?imprimir=1")
        self.confere("Presença (check-in e check-out)" in ata and "Histórico de alterações" in ata and "Avaliação dos participantes" in ata,
                     "Ata com presença, alterações e avaliação", "FLX", "A ata impressa traz presença, histórico e avaliação.",
                     "A ata impressa não traz presença, histórico ou avaliação.", "Ata completa da Reunião de Alinhamento", "Média")

    def desistencia_e_ocorrencia(self):
        m = _modelos()
        aluno2 = self.usuario("aluno2")
        did = self.contexto["ids"].get("desistencia")
        if did:
            self.etapa("Desistência: confirmação da gestão e reativação")
            self.post(f"/desistencias/{did}/decidir", {"acao": "confirmar", "observacao": f"{MARCA} Confirmada com a família."})
            estado = self._situacao_jovem(aluno2["id"])
            diagnostico = ""
            if estado[0] != "Desistente":
                # Falha intermitente já vista uma vez: guarda o diagnóstico para achar a causa se voltar a acontecer
                import time
                pedido = self.banco(lambda: (lambda d: (d.status, str(d.decidido_em), d.decidido_por_id) if d else None)(m.Desistencia.query.get(did)))
                time.sleep(2)
                depois = self._situacao_jovem(aluno2["id"])
                diagnostico = f" Pedido no banco (status, decidido_em, por): {pedido}. Releitura 2 s depois: {depois}."
            self.confere(estado[0] == "Desistente" and estado[1:] == (0, 0), "Gestão confirma: jovem sai da turma e do mentor", "REG",
                         "Jovem 'Desistente', fora da turma, do grupo e sem mentor (histórico guardado).",
                         f"Situação (status, turmas, mentores): {estado}.{diagnostico}", "Desistente sai da turma, do grupo e dos mentores", "Crítica",
                         print_de="/desistencias")
            from base import Cliente
            _, destino, _ = Cliente().pedir("POST", "/", {"email": aluno2["email"], "senha": aluno2["senha"]})
            self.confere(destino in (None, "/"), "Desistente não entra na plataforma", "ACE", "Login recusado com aviso para procurar a coordenação.",
                         f"Login aceito (destino {destino}).", "Participação encerrada bloqueia o acesso", "Alta")
            self.post(f"/desistencias/{did}/decidir", {"acao": "reativar"})
            estado = self._situacao_jovem(aluno2["id"])
            self.confere(estado[0] == "Ativo" and estado[1] >= 1 and estado[2] >= 1, "Reativação devolve turma e mentor", "FLX",
                         "Jovem ativo de novo, na mesma turma e com o mesmo mentor.", f"Situação (status, turmas, mentores): {estado}.",
                         "Jovem desistente pode voltar ao programa", "Alta")
        oid = self.contexto["ids"].get("ocorrencia")
        if oid:
            self.etapa("Ocorrência: retorno do responsável e desfecho")
            self.post(f"/ocorrencias/{oid}", {"acao": "registrar", "tipo": "Retorno", "texto": f"{MARCA} Falei com a família; combinamos novo prazo."})
            situacao = self.banco(lambda: m.Ocorrencia.query.get(oid).status)
            self.confere(situacao == "Em tratativa", "Retorno do responsável põe a ocorrência em tratativa", "FLX", "Status 'Em tratativa'.",
                         f"Status: {situacao}.", "Retorno registrado muda o sinal de alerta", "Média", print_de=f"/ocorrencias/{oid}")
            self.post(f"/ocorrencias/{oid}", {"acao": "resolver", "texto": f"{MARCA} Jovem voltou a entregar no prazo."})
            situacao = self.banco(lambda: m.Ocorrencia.query.get(oid).status)
            self.confere(situacao == "Resolvida", "Responsável resolve a ocorrência com o desfecho", "FLX", "Status 'Resolvida'.",
                         f"Status: {situacao}.", "Ocorrência fechada com desfecho registrado", "Média")

    def logo_no_certificado(self, projeto_id, aluno):
        m = _modelos()
        empresa_id = self.contexto["ids"].get("empresa")
        logo = self.banco(lambda: m.Empresa.query.get(empresa_id).logo_arquivo) if empresa_id else None
        if not logo:
            return
        self.etapa("Logo do parceiro B2B no certificado")
        _, _, html = self.cliente.pedir("GET", f"/certificado/{projeto_id}/{aluno['id']}")
        self.confere(f"/empresas/{empresa_id}/logo" in html, "Certificado mostra o logo do parceiro B2B", "FLX", "Logo da empresa ao lado do logo ITM.",
                     "O logo da empresa não aparece no certificado.", "Parceiros B2B colocam o logo no certificado", "Média",
                     print_de=f"/certificado/{projeto_id}/{aluno['id']}")
        self.post(f"/empresas/{empresa_id}/logo/enviar", {"acao": "remover"})
        from app import PASTA_LOGOS
        apagado = not os.path.exists(os.path.join(PASTA_LOGOS, logo)) and self.banco(lambda: m.Empresa.query.get(empresa_id).logo_arquivo) is None
        self.confere(apagado, "Remove o logo da empresa", "FLX", "Logo removido do cadastro e do disco.",
                     "O arquivo do logo continuou no disco ou no cadastro.", "Gestão remove o logo do parceiro", "Baixa")


AGENTES = {a.chave: a for a in (AgenteAdministrador, AgenteMentorAdministrador, AgenteGestorParceiro, AgenteProfessor, AgenteMentor,
                                AgenteAluno, AgenteAvaliador, AgenteEncerramento)}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in AGENTES:
        print("Uso: python agentes_funcionalidades/agente_fluxo.py <" + "|".join(AGENTES) + ">")
        sys.exit(2)
    AGENTES[sys.argv[1]]().executar()
    print(json.dumps({"fim": sys.argv[1]}))
