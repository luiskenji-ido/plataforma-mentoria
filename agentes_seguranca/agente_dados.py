# -*- coding: utf-8 -*-
"""
AGENTE DE SEGURANÇA — INCONSISTÊNCIAS DE DADOS
Uso: python agentes_seguranca/agente_dados.py
Procura no banco dados inconsistentes que hoje não quebram nada, mas podem virar vulnerabilidade:
senhas e respostas de segurança mal guardadas, contas de teste, perfis inválidos, registros órfãos e integridade do SQLite.
Só LÊ o banco (não altera nada).
"""
import os
from datetime import datetime, timedelta

from base import AgenteSeguranca, RAIZ_PROJETO



def senha_de_teste():
    """Senha das contas de teste (variável OMNITEST_SENHA, no .env fora do Git)."""
    if os.environ.get("OMNITEST_SENHA"):
        return os.environ["OMNITEST_SENHA"]
    try:
        from dotenv import dotenv_values
        return dotenv_values(os.path.join(RAIZ_PROJETO, ".env")).get("OMNITEST_SENHA") or ""
    except ImportError:
        return ""


class AgenteDados(AgenteSeguranca):
    chave = "dados"
    nome = "Agente Inconsistências de Dados"
    especialidade = "dados inconsistentes no banco que podem gerar vulnerabilidades"
    ROTEIRO = ["Senhas fora do bcrypt e respostas de segurança em texto puro",
               "Contas de teste com senha conhecida e contas administrativas",
               "Perfis inválidos, perfis personalizados inconsistentes e e-mails duplicados",
               "Bloqueios, senhas antigas e contas sem perguntas de segurança",
               "Registros órfãos, arquivos sumidos e integridade do SQLite"]

    def rodar(self):
        from app import app, bcrypt
        with app.app_context():
            self.bcrypt = bcrypt
            self.credenciais()
            self.contas()
            self.perfis()
            self.ciclo_de_vida()
            self.integridade()

    def credenciais(self):
        from models import Usuario, SegurancaUsuario
        self.etapa("Senhas e respostas de segurança")
        usuarios = Usuario.query.all()
        fracas = [u.email for u in usuarios if not (u.senha or "").startswith(("$2b$", "$2a$", "$2y$"))]
        if fracas:
            self.achado("Senhas que não estão em bcrypt", "Crítica", "A02", "CWE-916", f"tabela usuario ({len(fracas)} conta(s))",
                        "Contas: " + ", ".join(fracas[:6]), "Forçar a troca de senha dessas contas; todas as senhas devem ser gravadas com bcrypt.")
        else:
            self.ok(f"{len(usuarios)} senhas em bcrypt")
        seguranca = SegurancaUsuario.query.all()
        em_texto = [s for s in seguranca if any(r and not str(r).startswith(("$2b$", "pbkdf2:", "scrypt:")) for r in (s.resposta_1, s.resposta_2, s.resposta_3))]
        if em_texto:
            self.achado("Respostas de segurança gravadas em texto puro", "Alta", "A02", "CWE-256", f"tabela seguranca_usuario ({len(em_texto)} registro(s))",
                        "As respostas da recuperação de senha ficam legíveis no banco (minúsculas, sem hash). Quem obtiver um backup recupera qualquer conta.",
                        "Guardar as respostas com hash (bcrypt) normalizado em minúsculas e comparar com bcrypt.check_password_hash na recuperação; migrar as existentes.",
                        ["https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html"])
        else:
            self.ok("Respostas de segurança com hash")

    def contas(self):
        from models import Usuario
        self.etapa("Contas de teste e administrativas")
        teste = [u for u in Usuario.query.filter(Usuario.email.like("%ominitest%") | Usuario.email.like("%@local.com")).all()]
        senha = senha_de_teste()
        conhecidas = [u.email for u in teste if u.status == "Ativo" and senha and self._senha_eh(u, senha)]
        import app as modulo_app
        import seguranca_web
        barradas_em_producao = hasattr(modulo_app, "conta_de_teste_bloqueada")
        liberadas = os.environ.get("OMNITEST_PERMITIR_EM_PRODUCAO") == "1"
        if conhecidas and (not barradas_em_producao or (seguranca_web.EM_PRODUCAO and liberadas)):
            self.achado("Contas de teste ativas com senha conhecida", "Alta", "A07", "CWE-798", f"tabela usuario ({len(conhecidas)} conta(s))",
                        "Ex.: " + ", ".join(conhecidas[:6]) + ". Quem souber a senha dos agentes de teste entra nessas contas.",
                        "Antes de produção: desativar ou apagar as contas *_ominitest e @local.com (massa_dados.py --remover) ou trocar a senha.")
        elif conhecidas and seguranca_web.EM_PRODUCAO:
            self.achado("Contas de teste no banco de produção", "Baixa", "A07", "CWE-798", f"tabela usuario ({len(conhecidas)} conta(s))",
                        "Ex.: " + ", ".join(conhecidas[:6]) + ". O login delas é barrado em produção, mas os registros continuam no banco.",
                        "Apagar as contas e a massa de teste em produção (agentes_omnitest/massa_dados.py --remover).")
        elif conhecidas:
            self.achado(f"{len(conhecidas)} conta(s) de teste no ambiente de desenvolvimento", "Informativa", "A07", "", "tabela usuario",
                        "Usadas pelos agentes de teste. Em produção (PythonAnywhere) o login dessas contas é barrado pelo app.",
                        "Nada a fazer aqui; antes de publicar um banco, rode agentes_omnitest/massa_dados.py --remover.")
        else:
            self.ok("Nenhuma conta de teste ativa com a senha conhecida")
        admins = Usuario.query.filter_by(tipo_usuario="Administrador", status="Ativo").all()
        self.achado(f"{len(admins)} conta(s) Administrador ativa(s)", "Informativa", "A01", "CWE-250", "tabela usuario",
                    ", ".join(a.email for a in admins[:10]), "Revisar periodicamente: manter só quem precisa de acesso total (princípio do menor privilégio).")

    def _senha_eh(self, usuario, senha):
        try:
            return self.bcrypt.check_password_hash(usuario.senha, senha)
        except ValueError:
            return False

    def perfis(self):
        from models import Usuario, PerfilPersonalizado
        from perfis_acesso import PERFIS_BASE
        self.etapa("Perfis de acesso e e-mails")
        invalidos = [f"{u.email} ({u.tipo_usuario})" for u in Usuario.query.all() if u.tipo_usuario not in PERFIS_BASE]
        if invalidos:
            self.achado("Usuários com perfil inexistente", "Média", "A01", "CWE-285", "tabela usuario",
                        ", ".join(invalidos[:8]), "Corrigir o tipo_usuario: perfis fora da lista caem em regras inesperadas de acesso.")
        else:
            self.ok("Todos os usuários têm um perfil válido")
        problemas = []
        for u in Usuario.query.filter(Usuario.perfil_personalizado_id.isnot(None)).all():
            perfil = u.perfil_personalizado
            if not perfil:
                problemas.append(f"{u.email}: perfil personalizado apagado")
            elif perfil.perfil_base != u.tipo_usuario:
                problemas.append(f"{u.email}: perfil-base {perfil.perfil_base} ≠ tipo {u.tipo_usuario}")
            elif not perfil.ativo:
                problemas.append(f"{u.email}: perfil '{perfil.nome}' inativo")
        if problemas:
            self.achado("Usuários com perfil personalizado inconsistente", "Média", "A01", "CWE-285", "usuario × perfil_personalizado",
                        "; ".join(problemas[:8]), "Reatribuir o perfil no Cadastro: o acesso efetivo pode ficar maior ou menor que o esperado.")
        else:
            self.ok(f"{PerfilPersonalizado.query.count()} perfil(is) personalizado(s) consistentes")
        emails = {}
        for u in Usuario.query.all():
            emails.setdefault((u.email or "").strip().lower(), []).append(u.email)
        duplicados = [v for v in emails.values() if len(v) > 1]
        if duplicados:
            self.achado("E-mails duplicados (diferença só de maiúsculas/espaços)", "Média", "A07", "CWE-289", "tabela usuario",
                        "; ".join(" / ".join(d) for d in duplicados[:6]), "Unificar as contas e normalizar o e-mail (strip().lower()) no cadastro e no login.")
        else:
            self.ok("Nenhum e-mail duplicado")

    def ciclo_de_vida(self):
        from models import Usuario, SegurancaUsuario
        self.etapa("Bloqueios, senhas antigas e recuperação")
        incoerentes = [u.email for u in Usuario.query.filter(Usuario.tentativas_login >= 5, Usuario.status == "Ativo").all()]
        if incoerentes:
            self.achado("Contas com 5+ tentativas falhas que continuam ativas", "Média", "A07", "CWE-307", "tabela usuario",
                        ", ".join(incoerentes[:8]), "Conferir a regra de bloqueio: a conta deveria estar Bloqueada até um administrador liberar.")
        else:
            self.ok("Regra de bloqueio coerente")
        limite = datetime.utcnow() - timedelta(days=180)
        antigas = Usuario.query.filter(Usuario.status == "Ativo", Usuario.data_ultima_troca_senha < limite).count()
        if antigas:
            self.achado(f"{antigas} conta(s) ativa(s) sem trocar a senha há mais de 180 dias", "Baixa", "A07", "CWE-262", "tabela usuario",
                        f"{antigas} conta(s).", "Aplicar a expiração de senha que o painel já avisa ou exigir troca no próximo login.")
        else:
            self.ok("Nenhuma senha com mais de 180 dias")
        com_perguntas = {s.usuario_id for s in SegurancaUsuario.query.all()}
        sem = Usuario.query.filter(Usuario.status == "Ativo").all()
        sem = [u.email for u in sem if u.id not in com_perguntas]
        if sem:
            self.achado(f"{len(sem)} conta(s) ativa(s) sem perguntas de segurança", "Baixa", "A07", "CWE-640", "seguranca_usuario",
                        ", ".join(sem[:8]), "Essas contas não conseguem recuperar a senha sozinhas; o app já pede o cadastro no próximo login.")
        else:
            self.ok("Todas as contas ativas têm perguntas de segurança")

    def integridade(self):
        from models import db, EntregaTCC, Banca
        self.etapa("Integridade do banco e dos arquivos")
        con = db.engine.raw_connection()
        try:
            cur = con.cursor()
            resultado = cur.execute("PRAGMA integrity_check").fetchone()[0]
            chaves = cur.execute("PRAGMA foreign_key_check").fetchall()
            fk_ligado = cur.execute("PRAGMA foreign_keys").fetchone()[0]
            orfaos_grupo = cur.execute("SELECT COUNT(*) FROM grupo_usuario gu LEFT JOIN usuario u ON u.id = gu.usuario_id WHERE u.id IS NULL").fetchone()[0]
        finally:
            con.close()
        if resultado != "ok":
            self.achado("Banco SQLite com erro de integridade", "Alta", "A08", "CWE-1284", "instance/mentoria.db", resultado,
                        "Restaurar um backup íntegro (Manutenção › Restaurar) e investigar a causa.")
        else:
            self.ok("PRAGMA integrity_check = ok")
        if chaves:
            self.achado(f"{len(chaves)} registro(s) apontando para dados apagados (chaves estrangeiras quebradas)", "Média", "A08", "CWE-1284",
                        "instance/mentoria.db", str(chaves[:8]), "Limpar os órfãos e ligar PRAGMA foreign_keys=ON nas conexões do SQLite.")
        else:
            self.ok("Nenhuma chave estrangeira quebrada")
        if not fk_ligado:
            self.achado("SQLite sem verificação de chaves estrangeiras", "Baixa", "A04", "CWE-1284", "configuração do SQLAlchemy",
                        "PRAGMA foreign_keys está desligado (padrão do SQLite): exclusões deixam registros órfãos.",
                        "Ligar com um listener 'connect' do SQLAlchemy: cursor.execute('PRAGMA foreign_keys=ON').",
                        ["https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support"])
        if orfaos_grupo:
            self.achado(f"{orfaos_grupo} vínculo(s) de grupo com usuário apagado", "Baixa", "A08", "CWE-1284", "tabela grupo_usuario",
                        f"{orfaos_grupo} linha(s).", "Apagar os vínculos órfãos ao excluir usuários.")
        from app import PASTA_TCC
        sumidos = [e.arquivo for e in EntregaTCC.query.all() if not os.path.exists(os.path.join(PASTA_TCC, e.arquivo))]
        if sumidos:
            self.achado(f"{len(sumidos)} entrega(s) de TCC sem o arquivo no disco", "Baixa", "A08", "CWE-1284", "uploads/tcc",
                        ", ".join(sumidos[:6]), "Restaurar os arquivos do backup ou marcar as entregas como indisponíveis.")
        else:
            self.ok("Todos os arquivos de entrega existem")
        sem_projeto = [b.id for b in Banca.query.all() if not b.projeto]
        if sem_projeto:
            self.achado("Bancas sem projeto", "Baixa", "A08", "CWE-1284", "tabela banca", f"Bancas: {sem_projeto[:8]}", "Apagar ou reatribuir as bancas órfãs.")
        uploads = os.path.join(RAIZ_PROJETO, "uploads")
        soltos = [n for n in os.listdir(uploads) if os.path.isfile(os.path.join(uploads, n)) and n.lower().endswith((".exe", ".bat", ".js", ".html", ".svg", ".php"))] if os.path.isdir(uploads) else []
        if soltos:
            self.achado("Arquivos de tipo executável/ativo na pasta de uploads", "Média", "A04", "CWE-434", "uploads/", ", ".join(soltos[:8]),
                        "Restringir as extensões aceitas nos uploads e servir anexos com Content-Disposition: attachment.")
        else:
            self.ok("Nenhum arquivo ativo (html/svg/js/exe) em uploads/")


if __name__ == "__main__":
    AgenteDados().executar()
