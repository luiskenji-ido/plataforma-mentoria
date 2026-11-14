"""
TAREFAS AGENDADAS DA PLATAFORMA (lembretes automáticos)
=======================================================
Rode de hora em hora. Cada tarefa usa uma 'referencia' na notificação,
por isso rodar várias vezes não repete o mesmo aviso.

No PythonAnywhere: aba "Tasks" › "Scheduled tasks" › Hourly, com o comando
    cd /home/<seu_usuario>/<pasta_do_projeto> && python3 tarefas_agendadas.py
No computador:
    python tarefas_agendadas.py
"""
from datetime import datetime, timedelta

from app import app
from models import db, CheckinVoluntariado, Usuario, EncaminhamentoReuniao
from notificacoes import notificar

# Relógio de voluntariado aberto há mais tempo que isto recebe o lembrete de check-out
HORAS_RELOGIO_ESQUECIDO = 4


def lembrar_checkout_esquecido(agora):
    """Seção 13 do projeto: 'Não se esqueça de registar o seu tempo de hoje!'"""
    limite = agora - timedelta(hours=HORAS_RELOGIO_ESQUECIDO)
    abertos = CheckinVoluntariado.query.filter(CheckinVoluntariado.data_hora_fim.is_(None),
                                               CheckinVoluntariado.data_hora_inicio <= limite).all()
    enviados = 0
    for registro in abertos:
        pessoa = db.session.get(Usuario, registro.usuario_id)
        enviados += notificar(
            [pessoa],
            ('notif_checkout_titulo', {}),
            ('notif_checkout_msg', {'atividade': registro.tipo_atividade,
                                    'inicio': registro.data_hora_inicio.strftime('%d/%m/%Y %H:%M')}),
            link='/dashboard', tipo='lembrete', referencia=f"checkout:{registro.id}")
    return enviados


def lembrar_encaminhamentos_vencidos(agora):
    """Encaminhamento de reunião ITM × Aon com prazo vencido: avisa o responsável uma vez."""
    vencidos = EncaminhamentoReuniao.query.filter(EncaminhamentoReuniao.status == 'Pendente',
                                                  EncaminhamentoReuniao.prazo < agora.date(),
                                                  EncaminhamentoReuniao.responsavel_id.isnot(None)).all()
    enviados = 0
    for enc in vencidos:
        enviados += notificar(
            [enc.responsavel],
            ('notif_enc_titulo', {}),
            ('notif_enc_msg', {'descricao': enc.descricao[:200], 'prazo': enc.prazo.strftime('%d/%m/%Y'),
                               'reuniao': enc.reuniao.titulo}),
            link=f"/reunioes/{enc.reuniao_id}", tipo='lembrete', referencia=f"enc-atraso:{enc.id}")
    return enviados


# As próximas adequações acrescentam aqui os lembretes delas (prazos do TCC, formulário da banca...)
TAREFAS = [lembrar_checkout_esquecido, lembrar_encaminhamentos_vencidos]


def executar_tarefas():
    agora = datetime.utcnow()
    with app.app_context():
        for tarefa in TAREFAS:
            try:
                print(f"[{agora:%d/%m/%Y %H:%M}] {tarefa.__name__}: {tarefa(agora)} aviso(s)")
            except Exception as erro:
                db.session.rollback()
                print(f"[{agora:%d/%m/%Y %H:%M}] {tarefa.__name__}: ERRO {erro}")


if __name__ == "__main__":
    executar_tarefas()
