# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — BACKUP E RECUPERAÇÃO
Uso: python agentes_banco/agente_backup.py
Os backups rodam no serviço privado mentoria-backup (host separado, sem acesso público). Este agente só LÊ os
indicadores e os agendamentos dele pela API privada (escopo saude:ler) e avalia: ligação com o serviço, agendamentos
ativos e em dia, idade do último backup bem-sucedido (RPO), última restauração VERIFICADA (teste de restauração num
banco descartável, feito pelo serviço) e falhas registradas. Nunca dispara backup nem restauração.
"""

from datetime import datetime, timedelta

from base import AgenteBanco

LIMITE_IDADE = {"Diário": timedelta(hours=26), "Semanal": timedelta(days=8), "Mensal": timedelta(days=32)}
INTERVALO = {"Diário": "24 horas", "Semanal": "7 dias", "Mensal": "1 mês"}
VERIFICACAO_MAXIMA = timedelta(days=35)  # ao menos uma restauração testada por mês


class AgenteBackup(AgenteBanco):
    chave = "backup"
    nome = "Agente Backup e Recuperação"
    especialidade = "agendamentos, execução e restauração verificada dos backups (serviço privado de backup)"
    ROTEIRO = ["Ligação com o serviço privado de backup",
               "Agendamentos ativos e em dia",
               "Último backup bem-sucedido (RPO) e falhas",
               "Última restauração verificada num banco descartável (RTO)",
               "Retenção dos agendamentos"]

    def rodar(self):
        from app import app
        with app.app_context():
            import cliente_backup
            self.cb = cliente_backup
            saude = self.ligacao()
            if saude is None:
                return
            agendamentos = self.agendamentos(saude)
            self.execucoes(saude, agendamentos)
            self.verificacao(saude)
            self.retencao(agendamentos)

    def ligacao(self):
        self.etapa("Ligação com o serviço privado de backup")
        if not self.cb.configurado():
            self.achado("Serviço de backup não configurado", "Crítica", "BKP", "BACKUP_SERVICO_URL",
                        "A plataforma não faz mais backups sozinha: sem o serviço privado, não há backup nenhum.",
                        "Definir BACKUP_SERVICO_URL e BACKUP_SERVICO_TOKEN (README do mentoria-ecossistema).")
            return None
        saude = self.cb.saude()
        if saude is None:
            self.achado("Serviço de backup não respondeu", "Alta", "BKP", self.cb.url_base(),
                        "GET /api/v1/saude sem resposta em 2 s (serviço parado, VPN/enlace privado fora ou token recusado).",
                        "Conferir o serviço no host de backup (docker compose ps) e o enlace privado entre os hosts.")
            return None
        self.ok(f"Serviço de backup respondeu: situação {saude.get('situacao')}"
                + (f" ({saude['motivo']})" if saude.get("motivo") else ""))
        if not saude.get("agendador_ativo"):
            self.achado("O agendador do serviço de backup está desligado", "Alta", "BKP", "BACKUP_AGENDADOR_ATIVO",
                        "Nenhum backup agendado vai rodar (a plataforma também não roda mais os dela).",
                        "Ligar BACKUP_AGENDADOR_ATIVO=1 no serviço de backup.")
        return saude

    def agendamentos(self, saude):
        self.etapa("Agendamentos e agendador")
        todos = self.cb.agendamentos()
        ativos = [a for a in todos if a.get("status") == "Ativo"]
        if not todos:
            self.achado("Nenhum agendamento de backup cadastrado", "Alta", "BKP", "serviço de backup › Agendamentos",
                        "Os backups dependem de alguém lembrar de fazer o backup manual.",
                        "Criar os agendamentos padrão no serviço: flask --app servico agendamentos-padrao.")
        elif not ativos:
            self.achado(f"Todos os {len(todos)} agendamento(s) estão pausados", "Alta", "BKP", "serviço de backup › Agendamentos",
                        "Nenhum backup automático vai rodar.", "Reativar o agendamento principal.")
        else:
            self.ok(f"{len(ativos)} agendamento(s) ativo(s): " + ", ".join(f"{a['frequencia']} {a['horario']}" for a in ativos))
        agora = datetime.now()
        atrasados = [a for a in ativos if a.get("proxima_execucao") and datetime.fromisoformat(a["proxima_execucao"]) < agora - timedelta(hours=2)]
        if atrasados:
            self.achado(f"{len(atrasados)} agendamento(s) atrasado(s)", "Alta", "BKP", "serviço de backup › agendador",
                        "; ".join(f"#{a['id']} {a['frequencia']}: deveria ter rodado em {a['proxima_execucao']}" for a in atrasados),
                        "Conferir se o serviço de backup está rodando e com o agendador ligado.")
        elif ativos:
            self.ok("Agendamentos em dia (nenhuma execução atrasada)")
        return ativos

    def execucoes(self, saude, ativos):
        self.etapa("Execuções: último sucesso (RPO) e falhas")
        ultimo = saude.get("ultimo")
        if not ultimo:
            self.achado("Nenhum backup bem-sucedido registrado", "Crítica", "BKP", "serviço de backup › Histórico",
                        "Não existe cópia de segurança válida do banco.", "Fazer um backup agora no serviço de backup.")
            return
        idade = datetime.now() - ultimo
        limite = min((LIMITE_IDADE.get(a["frequencia"], timedelta(days=8)) for a in ativos), default=timedelta(days=8))
        if idade > limite:
            self.achado(f"Último backup bem-sucedido há {idade.days} dia(s) e {idade.seconds // 3600} h", "Alta", "BKP", "serviço de backup",
                        f"Último sucesso: {ultimo:%d/%m/%Y %H:%M}. Limite esperado pela frequência: {limite.days or 1} dia(s).",
                        "Conferir o agendador do serviço e rodar um backup agora.")
        else:
            self.ok(f"Último backup bem-sucedido há {idade.seconds // 3600 + idade.days * 24} h")
        if saude.get("situacao") == "Crítica":
            self.achado("O último backup falhou", "Alta", "BKP", "serviço de backup › Histórico", saude.get("motivo") or "",
                        "Ver o erro no histórico do serviço, corrigir e rodar de novo.")
        if saude.get("falhas"):
            self.achado(f"{saude['falhas']} falha(s) registrada(s) no serviço de backup", "Média", "BKP", "serviço de backup › Histórico",
                        "Falhas indicam disco cheio, banco inacessível pelo enlace privado ou permissão no bucket.",
                        "Ver os detalhes no histórico de execuções do serviço.")
        rpo = min((INTERVALO.get(a["frequencia"]) for a in ativos), default=None,
                  key=lambda x: {"24 horas": 1, "7 dias": 7, "1 mês": 30}.get(x, 99)) if ativos else None
        self.extras["rpo"] = rpo

    def verificacao(self, saude):
        self.etapa("Restauração verificada (teste num banco descartável)")
        verificado = saude.get("ultimo_verificado")
        if not verificado:
            self.achado("Nenhum backup com restauração verificada", "Alta", "BKP", "serviço de backup › Verificar restauração",
                        "Um backup criado e íntegro ainda pode falhar na hora de restaurar. A restauração de produção só aceita backup Verificado.",
                        "No serviço de backup, usar 'Verificar restauração' no backup mais recente (pelo menos uma vez por mês).")
            return
        idade = datetime.now() - verificado
        if idade > VERIFICACAO_MAXIMA:
            self.achado(f"Última restauração verificada há {idade.days} dia(s)", "Média", "BKP", "serviço de backup › Verificações",
                        "Sem teste recente, o tempo de recuperação (RTO) e a compatibilidade com o esquema atual são desconhecidos.",
                        "Verificar a restauração de um backup recente.")
        else:
            self.ok(f"Restauração verificada há {idade.days} dia(s) ({verificado:%d/%m/%Y %H:%M})")
        self.achado("RPO e RTO", "Informativa", "BKP", "serviço de backup",
                    f"RPO (perda máxima de dados): {self.extras.get('rpo') or 'indefinido (sem agendamento ativo)'}. "
                    "RTO: veja a duração das verificações na tela do serviço de backup.",
                    "Combinar com a gestão o RPO aceitável e ajustar a frequência dos agendamentos.")

    def retencao(self, ativos):
        self.etapa("Retenção")
        curtas = [a for a in ativos if (a.get("retencao") or 0) < 3]
        if curtas:
            self.achado(f"{len(curtas)} agendamento(s) com retenção menor que 3 cópias", "Baixa", "BKP",
                        ", ".join(f"#{a['id']} {a['frequencia']} (retém {a['retencao']})" for a in curtas),
                        "Com poucas cópias, um erro descoberto tarde não tem como ser desfeito.", "Reter pelo menos 7 diárias e 4 semanais.")
        elif ativos:
            self.ok("Retenção dos agendamentos adequada (3 cópias ou mais)")


if __name__ == "__main__":
    AgenteBackup().executar()
