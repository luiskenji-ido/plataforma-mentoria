# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — BACKUP E RECUPERAÇÃO
Uso: python agentes_banco/agente_backup.py
Valida os agendamentos de backup e se eles estão rodando com sucesso: agendamento ativo, agendador funcionando
(execuções em dia), idade do último backup bem-sucedido (RPO), falhas recentes, arquivo no disco, integridade do
arquivo e um TESTE DE RESTAURAÇÃO numa cópia temporária (o banco real não é tocado). Também avalia retenção,
cópia fora do servidor e o tempo estimado de recuperação (RTO).
"""
import os
import time
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

from base import AgenteBanco, tamanho_legivel

LIMITE_IDADE = {"Diário": timedelta(hours=26), "Semanal": timedelta(days=8), "Mensal": timedelta(days=32)}
INTERVALO = {"Diário": "24 horas", "Semanal": "7 dias", "Mensal": "1 mês"}


class AgenteBackup(AgenteBanco):
    chave = "backup"
    nome = "Agente Backup e Recuperação"
    especialidade = "agendamentos, execução, integridade e restauração dos backups"
    ROTEIRO = ["Agendamentos de backup ativos e agendador em funcionamento",
               "Último backup bem-sucedido (RPO) e falhas recentes",
               "Arquivo do último backup: existe e está íntegro",
               "Teste de restauração numa cópia temporária (RTO)",
               "Retenção, espaço em disco e cópia fora do servidor",
               "Mudanças nos agendamentos aprendidas com o Gerente de Banco de Dados"]

    def rodar(self):
        from app import app
        with app.app_context():
            import backup_servico
            self.bs = backup_servico
            self.agendamentos()
            ultimo = self.execucoes()
            self.arquivo_e_restauracao(ultimo)
            self.retencao_e_armazenamento()
            self.mudancas_aprendidas()

    def agendamentos(self):
        from models import AgendamentoBackup
        self.etapa("Agendamentos e agendador")
        todos = AgendamentoBackup.query.all()
        self.ativos = [a for a in todos if a.status == "Ativo"]
        if not todos:
            self.achado("Nenhum agendamento de backup cadastrado", "Alta", "BKP", "Manutenção (DB) › Agendamentos",
                        "Os backups dependem de alguém lembrar de clicar em 'Backup agora'. Uma falha no disco perde tudo desde o último.",
                        "Criar ao menos um agendamento Diário (ex.: 03:00) com retenção de 7 cópias e um Semanal com retenção de 4.",
                        ["https://www.sqlite.org/backup.html"])
        elif not self.ativos:
            self.achado(f"Todos os {len(todos)} agendamento(s) estão pausados", "Alta", "BKP", "Manutenção (DB) › Agendamentos",
                        "Nenhum backup automático vai rodar.", "Reativar o agendamento principal.")
        else:
            self.ok(f"{len(self.ativos)} agendamento(s) ativo(s): " + ", ".join(f"{a.frequencia} {a.horario}" for a in self.ativos))
        agora = datetime.now()
        atrasados = [a for a in self.ativos if a.proxima_execucao and a.proxima_execucao < agora - timedelta(hours=2)]
        if atrasados:
            self.achado(f"{len(atrasados)} agendamento(s) atrasado(s): o agendador não está rodando", "Alta", "BKP",
                        "tarefas_agendadas.py / PythonAnywhere › Tasks",
                        "; ".join(f"#{a.id} {a.frequencia}: deveria ter rodado em {a.proxima_execucao:%d/%m %H:%M}" for a in atrasados),
                        "No PythonAnywhere, criar a Scheduled task de hora em hora: cd /home/<usuario>/<pasta> && python3 tarefas_agendadas.py. "
                        "Localmente, os backups só rodam enquanto o site recebe acessos.")
        elif self.ativos:
            self.ok("Agendamentos em dia (nenhuma execução atrasada)")

    def execucoes(self):
        from models import RegistroBackup
        self.etapa("Execuções: último sucesso (RPO) e falhas")
        backups = RegistroBackup.query.filter(RegistroBackup.tipo.in_(self.bs.TIPOS_BACKUP))
        ultimo_ok = backups.filter(RegistroBackup.status.in_(self.bs.STATUS_OK)).order_by(RegistroBackup.data_registro.desc()).first()
        ultimo = backups.order_by(RegistroBackup.data_registro.desc()).first()
        agora = datetime.now()
        if not ultimo_ok:
            self.achado("Nenhum backup bem-sucedido registrado", "Crítica", "BKP", "registro_backup",
                        "Não existe cópia de segurança válida do banco.", "Fazer um backup agora (Manutenção (DB) › Backup agora) e criar um agendamento.")
            return None
        idade = agora - ultimo_ok.data_registro
        limite = min((LIMITE_IDADE.get(a.frequencia, timedelta(days=8)) for a in self.ativos), default=timedelta(days=8))
        if idade > limite:
            self.achado(f"Último backup bem-sucedido há {idade.days} dia(s) e {idade.seconds // 3600} h", "Alta", "BKP", "registro_backup",
                        f"Último sucesso: {ultimo_ok.data_registro:%d/%m/%Y %H:%M} ({ultimo_ok.arquivo}). Limite esperado pela frequência: "
                        f"{limite.days or 1} dia(s).", "Conferir o agendador e rodar um backup agora.")
        else:
            self.ok(f"Último backup bem-sucedido há {idade.seconds // 3600 + idade.days * 24} h ({ultimo_ok.arquivo})")
        if ultimo and ultimo.status == "Falha":
            self.achado("O último backup falhou", "Alta", "BKP", f"registro_backup #{ultimo.id}", ultimo.detalhes or "", "Ver o erro, corrigir e rodar de novo.")
        falhas = RegistroBackup.query.filter(RegistroBackup.status == "Falha", RegistroBackup.data_registro >= agora - timedelta(days=30)).count()
        total = backups.filter(RegistroBackup.data_registro >= agora - timedelta(days=30)).count()
        if falhas:
            self.achado(f"{falhas} de {total} backup(s) falharam nos últimos 30 dias", "Média", "BKP", "registro_backup",
                        "Falhas intermitentes indicam disco cheio, banco travado ou permissão de pasta.", "Ver os detalhes das falhas no histórico de backups.")
        else:
            self.ok(f"Nenhuma falha de backup nos últimos 30 dias ({total} execução(ões))")
        rpo = min((INTERVALO.get(a.frequencia) for a in self.ativos), default=None, key=lambda x: {"24 horas": 1, "7 dias": 7, "1 mês": 30}[x]) if self.ativos else None
        self.extras["rpo"] = rpo
        return ultimo_ok

    def arquivo_e_restauracao(self, ultimo):
        self.etapa("Arquivo do último backup e teste de restauração")
        if not ultimo:
            return
        caminho = self.bs.caminho_seguro(f"{ultimo.destino}/{ultimo.arquivo}") if ultimo.destino else None
        if not caminho:
            achados = [b for b in self.bs.listar_backups() if b["nome"] == ultimo.arquivo]
            caminho = os.path.join(self.bs.pasta_base(), achados[0]["relativo"]) if achados else None
        if not caminho or not os.path.exists(caminho):
            self.achado("O arquivo do último backup não está no disco", "Alta", "BKP", f"instance/backups/{ultimo.destino}/{ultimo.arquivo}",
                        "O histórico diz que o backup foi feito, mas o arquivo sumiu (apagado à mão ou pela retenção).", "Fazer um backup novo e conferir a retenção.")
            return
        ok, mensagem = self.bs.verificar_integridade(caminho)
        if not ok:
            self.achado("O arquivo do último backup está corrompido", "Crítica", "BKP", caminho, mensagem, "Fazer um backup novo imediatamente.")
            return
        self.ok(f"Último backup íntegro ({tamanho_legivel(os.path.getsize(caminho))})")
        # Teste de restauração: copia para uma pasta temporária, abre e compara com o banco atual
        pasta = tempfile.mkdtemp(prefix="teste_restauracao_")
        try:
            inicio = time.time()
            copia = os.path.join(pasta, "restaurado.db")
            shutil.copyfile(caminho, copia)
            con = sqlite3.connect(copia)
            atual = sqlite3.connect(f"file:{self.bs.caminho_banco()}?mode=ro", uri=True)
            try:
                tabelas_backup = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                tabelas_atual = {r[0] for r in atual.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                linhas = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in ("usuario", "projeto", "grupo") if t in tabelas_backup}
                integridade = con.execute("PRAGMA quick_check").fetchone()[0]
            finally:
                con.close()
                atual.close()
            segundos = time.time() - inicio
            faltando = sorted(tabelas_atual - tabelas_backup)
            if integridade != "ok" or "usuario" not in tabelas_backup:
                self.achado("Teste de restauração falhou", "Crítica", "BKP", caminho, f"quick_check: {integridade}", "Fazer um backup novo e repetir o teste.")
            else:
                self.ok(f"Teste de restauração OK em {segundos:.1f} s: " + ", ".join(f"{t} {n}" for t, n in linhas.items()))
                if faltando:
                    self.achado(f"Backup sem {len(faltando)} tabela(s) que o banco atual tem", "Baixa", "BKP", ", ".join(faltando[:8]),
                                "O backup é anterior à criação dessas tabelas; restaurar perde estes dados.", "Fazer um backup novo depois de mudanças no esquema.")
            self.extras["rto_seg"] = round(segundos, 1)
            self.achado("RPO e RTO estimados", "Informativa", "BKP", "backups",
                        f"RPO (perda máxima de dados): {self.extras.get('rpo') or 'indefinido (sem agendamento ativo)'}. "
                        f"RTO (tempo de restauração do arquivo): ~{segundos:.1f} s + reinício do app.",
                        "Combinar com a gestão o RPO aceitável e ajustar a frequência dos agendamentos.")
        finally:
            shutil.rmtree(pasta, ignore_errors=True)

    def retencao_e_armazenamento(self):
        self.etapa("Retenção, espaço e cópia fora do servidor")
        arquivos = self.bs.listar_backups()
        total = sum(a["tamanho"] for a in arquivos)
        livre = shutil.disk_usage(self.bs.pasta_base()).free
        self.ok(f"{len(arquivos)} arquivo(s) de backup ocupando {tamanho_legivel(total)}; {tamanho_legivel(livre)} livres no disco")
        if arquivos and livre < max(total, os.path.getsize(self.bs.caminho_banco()) * 5):
            self.achado("Pouco espaço livre para os próximos backups", "Alta", "BKP", self.bs.pasta_base(),
                        f"Livre: {tamanho_legivel(livre)}; backups: {tamanho_legivel(total)}.", "Reduzir a retenção ou liberar espaço.")
        curtas = [a for a in self.ativos if (a.retencao or 0) < 3]
        if curtas:
            self.achado(f"{len(curtas)} agendamento(s) com retenção menor que 3 cópias", "Baixa", "BKP",
                        ", ".join(f"#{a.id} {a.frequencia} (retém {a.retencao})" for a in curtas),
                        "Com poucas cópias, um erro descoberto tarde (ex.: dado apagado há 3 dias) não tem como ser desfeito.",
                        "Reter pelo menos 7 diárias e 4 semanais.")
        if arquivos:
            self.achado("Backups guardados só no mesmo servidor do banco", "Média", "BKP", "instance/backups",
                        "Se o servidor ou a conta do PythonAnywhere forem perdidos, os backups vão junto.",
                        "Baixar uma cópia por semana (Manutenção (DB) › Baixar) para um armazenamento da organização (ex.: Google Drive corporativo), "
                        "seguindo a regra 3-2-1: 3 cópias, 2 mídias, 1 fora do servidor.")
            self.achado("Backups sem criptografia", "Baixa", "RET", "instance/backups",
                        "Os arquivos .db têm dados pessoais (LGPD) legíveis por quem tiver acesso à pasta.",
                        "Criptografar a cópia guardada fora do servidor (ex.: arquivo .zip com AES ou cofre do Drive corporativo) e restringir o acesso.")

    def mudancas_aprendidas(self):
        self.etapa("Mudanças nos agendamentos aprendidas")
        import json
        mudancas = self.aprendizados_do_tipo("db_backup")
        if not mudancas:
            self.log("Nenhuma mudança nos agendamentos desde a linha de base")
            return
        ultima = json.loads(mudancas[-1].conteudo)
        antes, depois = ultima.get("antes", {}), ultima.get("depois", {})
        pausados = [i for i, a in depois.items() if a["status"] != "Ativo" and antes.get(i, {}).get("status") == "Ativo"]
        removidos = [i for i in antes if i not in depois]
        if pausados or removidos:
            self.achado(f"Agendamentos pausados/removidos recentemente ({mudancas[-1].codigo})", "Média", "BKP", "agendamento_backup",
                        (f"Pausados: {', '.join('#' + i for i in pausados)}. " if pausados else "") +
                        (f"Removidos: {', '.join('#' + i for i in removidos)}." if removidos else ""),
                        "Confirmar com quem alterou (Manutenção (DB) › Auditoria dos agendamentos) que foi intencional.")
        else:
            self.ok(f"{len(mudancas)} mudança(s) nos agendamentos aprendida(s), sem pausas ou remoções")


if __name__ == "__main__":
    AgenteBackup().executar()
