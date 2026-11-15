"""
TAREFAS AGENDADAS DA PLATAFORMA (lembretes automáticos e backups agendados)
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
from models import db, CheckinVoluntariado, Usuario, EncaminhamentoReuniao, Banca, EnvioFormularioBanca, AvaliacaoBanca
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


def enviar_formulario_banca(agora):
    """P13: X horas antes da banca (hora local), cada avaliador recebe o link do formulário; 2 h antes, lembrete
    a quem ainda não concluiu a etapa escrita. EnvioFormularioBanca evita repetir (remarcar apaga os envios)."""
    agora_local = datetime.now()
    enviados = 0
    for banca in Banca.query.filter(Banca.status.in_(['Agendada', 'Remarcada'])).all():
        if agora_local > banca.fim_previsto:
            continue
        janela = banca.data_hora - timedelta(hours=banca.horas_antes_formulario or 24)
        for avaliador in banca.avaliadores:
            ja = {e.tipo for e in EnvioFormularioBanca.query.filter_by(banca_id=banca.id, avaliador_id=avaliador.id)}
            parametros = {'projeto': banca.projeto.nome, 'data': banca.data_hora.strftime('%d/%m/%Y %H:%M'),
                          'local': banca.local or banca.link_sala or '—'}
            if agora_local >= janela and 'formulario' not in ja:
                enviados += notificar([avaliador], ('notif_form_banca_titulo', parametros), ('notif_form_banca_msg', parametros),
                                      link=f"/projetos/banca/{banca.projeto_id}", tipo='banca')
                db.session.add(EnvioFormularioBanca(banca_id=banca.id, avaliador_id=avaliador.id, tipo='formulario'))
            av = AvaliacaoBanca.query.filter_by(projeto_id=banca.projeto_id, avaliador_id=avaliador.id).first()
            if agora_local >= banca.data_hora - timedelta(hours=2) and 'lembrete_2h' not in ja \
                    and not (av and av.etapa_escrita_concluida_em):
                enviados += notificar([avaliador], ('notif_lembrete_banca_titulo', parametros), ('notif_lembrete_banca_msg', parametros),
                                      link=f"/projetos/banca/{banca.projeto_id}", tipo='banca')
                db.session.add(EnvioFormularioBanca(banca_id=banca.id, avaliador_id=avaliador.id, tipo='lembrete_2h'))
        db.session.commit()
    return enviados


def fechar_checkin_banca_esquecido(agora):
    """P09: check-in na banca ao vivo fecha sozinho 2 h depois do fim previsto."""
    fechados = 0
    abertos = CheckinVoluntariado.query.filter(CheckinVoluntariado.data_hora_fim.is_(None),
                                               CheckinVoluntariado.tipo_atividade == 'Avaliação de Banca Ao Vivo',
                                               CheckinVoluntariado.projeto_id.isnot(None)).all()
    for registro in abertos:
        banca = Banca.query.filter_by(projeto_id=registro.projeto_id).first()
        if not banca:
            continue
        # O relógio grava em UTC e a banca em hora local: compara pela diferença de fuso do servidor
        limite_utc = banca.fim_previsto + timedelta(hours=2) + (agora - datetime.now())
        if agora >= limite_utc:
            registro.data_hora_fim = max(limite_utc, registro.data_hora_inicio)
            registro.total_minutos = int((registro.data_hora_fim - registro.data_hora_inicio).total_seconds() / 60)
            registro.observacoes = ((registro.observacoes or '') + ' · check-out automático').strip(' ·')
            fechados += 1
    db.session.commit()
    return fechados


# As próximas adequações acrescentam aqui os lembretes delas
def executar_backups_agendados(agora):
    """Manutenção (DB): roda os agendamentos de backup vencidos (Diário, Semanal ou Mensal)."""
    import backup_servico
    return backup_servico.executar_vencidos(agora)


TAREFAS = [lembrar_checkout_esquecido, lembrar_encaminhamentos_vencidos, enviar_formulario_banca, fechar_checkin_banca_esquecido,
           executar_backups_agendados]


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
