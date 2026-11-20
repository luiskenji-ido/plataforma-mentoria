"""
TAREFAS AGENDADAS DA PLATAFORMA (lembretes automáticos e backups agendados)
=======================================================
Rode de hora em hora. Cada tarefa usa uma 'referencia' na notificação,
por isso rodar várias vezes não repete o mesmo aviso.

No PythonAnywhere: aba "Tasks" › "Scheduled tasks" › Hourly, com o comando
    cd /home/<seu_usuario>/<pasta_do_projeto> && python3 tarefas_agendadas.py
No computador:
    python tarefas_agendadas.py
No contêiner (serviço "worker", processo próprio, separado do web):
    python tarefas_agendadas.py --continuo      roda agora e depois a cada TAREFAS_INTERVALO_SEGUNDOS (3600);
                                                SIGTERM termina a tarefa em andamento e sai sem começar outra.
"""
import logging
import os
from datetime import datetime, timedelta

from app import app
from models import db, CheckinVoluntariado, Usuario, EncaminhamentoReuniao, Banca, EnvioFormularioBanca, AvaliacaoBanca, EntregaTCC
from notificacoes import notificar, eh_conta_de_teste

log = logging.getLogger("tarefas")

# Relógio de voluntariado aberto há mais tempo que isto recebe o lembrete de check-out
HORAS_RELOGIO_ESQUECIDO = 4
AVISO_FIM_CICLO_DIAS = 2  # lembra as avaliações pendentes quando faltam estes dias para fechar o ciclo


def lembrar_checkout_esquecido(agora):
    """Seção 13 do projeto: 'Não se esqueça de registar o seu tempo de hoje!'"""
    from regras_negocio import regra
    limite = agora - timedelta(hours=int(regra('relogio_esquecido_horas', HORAS_RELOGIO_ESQUECIDO) or HORAS_RELOGIO_ESQUECIDO))
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


def avisar_ocorrencias_atrasadas(agora):
    """Ocorrência com prazo de retorno vencido e sem retorno do responsável: avisa o responsável e quem registrou, uma vez."""
    from models import Ocorrencia
    enviados = 0
    for o in Ocorrencia.query.filter(Ocorrencia.status != 'Resolvida', Ocorrencia.prazo_resposta < agora.date(),
                                     Ocorrencia.aviso_atraso_enviado.isnot(True)).all():
        if any(r.autor_id == o.responsavel_id and r.tipo in ('Retorno', 'Ação') for r in o.registros):
            continue  # o responsável já respondeu: está em tratativa
        enviados += notificar([p for p in (o.responsavel, o.registrado_por) if p and p.status == 'Ativo'],
                              ('notif_ocorrencia_atraso_titulo', {'nome': o.aluno.nome}),
                              ('notif_ocorrencia_atraso_msg', {'nome': o.aluno.nome, 'responsavel': o.responsavel.nome,
                                                               'prazo': o.prazo_resposta.strftime('%d/%m/%Y')}),
                              link=f"/ocorrencias/{o.id}", tipo='lembrete', referencia=f"ocorrencia-atraso:{o.id}",
                              por_email=not eh_conta_de_teste(o.aluno))
        o.aviso_atraso_enviado = True
    db.session.commit()
    return enviados


def lembrar_encaminhamentos_vencidos(agora):
    """Encaminhamento de reunião instituição × B2B com prazo vencido: avisa o responsável uma vez."""
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


def lembrar_saida_esquecida(agora):
    """Saída esquecida: X minutos (Parâmetros de regras, padrão 30) depois do fim previsto da reunião instituição × B2B,
    da atividade extra ou da banca, avisa por e-mail quem ainda não fez o check-out (uma vez por presença)."""
    from models import PresencaReuniao, PresencaAtividadeExtra
    from regras_negocio import regra
    minutos = int(regra('checkout_esquecido_minutos', 30) or 30)
    local, enviados = datetime.now(), 0
    pendentes = []
    for p in PresencaReuniao.query.filter(PresencaReuniao.check_out.is_(None)).all():
        if p.reuniao and local >= p.reuniao.fim_previsto + timedelta(minutes=minutos):
            pendentes.append((p.usuario, p.reuniao.titulo, f"/reunioes/{p.reuniao_id}#cardPresenca", f"saida-reuniao:{p.id}"))
    for p in PresencaAtividadeExtra.query.filter(PresencaAtividadeExtra.check_out.is_(None)).all():
        if p.atividade and local >= p.atividade.fim_previsto + timedelta(minutes=minutos):
            pendentes.append((p.usuario, p.atividade.titulo, "/atividades-extras", f"saida-extra:{p.id}"))
    for registro in CheckinVoluntariado.query.filter(CheckinVoluntariado.data_hora_fim.is_(None),
                                                     CheckinVoluntariado.tipo_atividade == 'Avaliação de Banca Ao Vivo',
                                                     CheckinVoluntariado.projeto_id.isnot(None)).all():
        banca = Banca.query.filter_by(projeto_id=registro.projeto_id).first()
        if banca and local >= banca.fim_previsto + timedelta(minutes=minutos):
            pendentes.append((db.session.get(Usuario, registro.usuario_id), 'Banca do TCC', "/bancas", f"saida-banca:{registro.id}"))
    for pessoa, atividade, link, referencia in pendentes:
        if pessoa is None:
            continue
        enviados += notificar([pessoa], ('notif_saida_esquecida_titulo', {}),
                              ('notif_saida_esquecida_msg', {'atividade': atividade, 'minutos': minutos}),
                              link=link, tipo='lembrete', referencia=referencia, por_email=not eh_conta_de_teste(pessoa))
    return enviados


def avisar_prazo_entrega_tcc(agora):
    """Proximidade do prazo de entrega do TCC: X horas antes (padrão 48) do prazo do escrito ou dos slides,
    avisa por e-mail os jovens e mentores do grupo que ainda não entregaram (uma vez por prazo)."""
    from regras_negocio import regra
    horas = int(regra('prazo_tcc_aviso_horas', 48) or 48)
    local, enviados = datetime.now(), 0
    for banca in Banca.query.filter(Banca.status != 'Cancelada').all():
        projeto = banca.projeto
        if not projeto or not projeto.grupo:
            continue
        for tipo, prazo in (('Escrito final', banca.prazo_entrega_escrito), ('Slides da apresentação', banca.prazo_entrega_slides)):
            if not prazo or not (local < prazo <= local + timedelta(hours=horas)):
                continue
            if EntregaTCC.query.filter_by(projeto_id=projeto.id, tipo=tipo).first():
                continue
            pessoas = [p for p in projeto.grupo.membros if p.status == 'Ativo']
            teste = all(eh_conta_de_teste(p) for p in pessoas)
            enviados += notificar(pessoas, ('notif_prazo_tcc_titulo', {'tipo': tipo}),
                                  ('notif_prazo_tcc_msg', {'tipo': tipo, 'projeto': projeto.nome, 'prazo': prazo.strftime('%d/%m/%Y %H:%M')}),
                                  link='/projetos', tipo='lembrete', referencia=f"prazo-tcc:{banca.id}:{tipo}", por_email=not teste)
    return enviados


def abrir_microavaliacao(agora):
    """Abre sozinha a microavaliação (jovem ↔ mentor) a cada N dias (Parâmetros de regras; zero desliga). Dura 7 dias."""
    from models import CicloAvaliacao
    from app import abrir_ciclo_avaliacao
    from regras_negocio import regra
    dias = int(regra('micro_avaliacao_dias', 15) or 0)
    if dias <= 0:
        return 0
    hoje = datetime.now().date()
    ultimo = CicloAvaliacao.query.filter_by(tipo='Micro').order_by(CicloAvaliacao.inicio.desc()).first()
    if ultimo and (hoje - ultimo.inicio).days < dias:
        return 0
    return abrir_ciclo_avaliacao(CicloAvaliacao(titulo=f"Microavaliação {hoje:%d/%m/%Y}", tipo='Micro', inicio=hoje, fim=hoje + timedelta(days=6)))


def lembrar_avaliacao_pendente(agora):
    """Faltando 2 dias (ou menos) para fechar o ciclo, lembra uma vez quem ainda tem avaliações pendentes."""
    from app import ciclos_abertos, alvos_da_avaliacao, respostas_do_avaliador
    hoje, enviados = datetime.now().date(), 0
    for ciclo in ciclos_abertos():
        if (ciclo.fim - hoje).days > AVISO_FIM_CICLO_DIAS:
            continue
        pendentes = []
        for pessoa in Usuario.query.filter(Usuario.status == 'Ativo').all():
            alvos = alvos_da_avaliacao(pessoa, ciclo)
            if alvos and len(respostas_do_avaliador(pessoa, ciclo)) < len(alvos):
                pendentes.append(pessoa)
        enviados += notificar(pendentes, ('notif_avaliacao_lembrete_titulo', {'titulo': ciclo.titulo}),
                              ('notif_avaliacao_lembrete_msg', {'fim': ciclo.fim.strftime('%d/%m/%Y')}),
                              link='/avaliacoes', tipo='lembrete', referencia=f"avaliacao-lembrete:{ciclo.id}")
    return enviados


def lembrar_avaliacao_reuniao(agora):
    """Reunião instituição × B2B: 1 hora depois do fim, lembra quem esteve presente e ainda não avaliou (uma vez)."""
    from models import PresencaReuniao, FeedbackReuniao
    local, enviados = datetime.now(), 0
    for presenca in PresencaReuniao.query.filter(PresencaReuniao.check_out.isnot(None)).all():
        reuniao = presenca.reuniao
        if not reuniao or not (local - timedelta(days=7) <= reuniao.fim_previsto <= local - timedelta(hours=1)):
            continue
        if FeedbackReuniao.query.filter_by(reuniao_id=reuniao.id, usuario_id=presenca.usuario_id).first():
            continue
        enviados += notificar([presenca.usuario], ('notif_reuniao_feedback_titulo', {'titulo': reuniao.titulo}),
                              ('notif_reuniao_feedback_msg', {}), link=f"/reunioes/{reuniao.id}#cardFeedback", tipo='lembrete',
                              referencia=f"reuniao-feedback:{reuniao.id}", por_email=not eh_conta_de_teste(presenca.usuario))
    return enviados


def fechar_presenca_reuniao_esquecida(agora):
    """Reunião instituição × B2B: check-out esquecido fecha no fim previsto, 2 h depois do fim (marcado como automático)."""
    from models import PresencaReuniao
    from app import fechar_presenca_reuniao, sincronizar_voluntariado_reuniao, CHECKOUT_REUNIAO_AUTOMATICO_H
    local = datetime.now()  # a reunião é gravada em hora local
    fechadas, reunioes = 0, set()
    for presenca in PresencaReuniao.query.filter(PresencaReuniao.check_out.is_(None)).all():
        reuniao = presenca.reuniao
        if reuniao and local >= reuniao.fim_previsto + timedelta(hours=CHECKOUT_REUNIAO_AUTOMATICO_H):
            fechar_presenca_reuniao(presenca, reuniao.fim_previsto, automatico=True)
            reunioes.add(reuniao)
            fechadas += 1
    for reuniao in reunioes:
        sincronizar_voluntariado_reuniao(reuniao)
    # Convidados externos (link pessoal, sem conta): mesma regra, sem horas ESG
    from models import ConvidadoReuniao
    for convidado in ConvidadoReuniao.query.filter(ConvidadoReuniao.check_in.isnot(None), ConvidadoReuniao.check_out.is_(None)).all():
        reuniao = convidado.reuniao
        if reuniao and local >= reuniao.fim_previsto + timedelta(hours=CHECKOUT_REUNIAO_AUTOMATICO_H):
            fechar_presenca_reuniao(convidado, reuniao.fim_previsto, automatico=True)
            fechadas += 1
    db.session.commit()
    return fechadas


# As próximas adequações acrescentam aqui os lembretes delas
def executar_backups_agendados(agora):
    """Manutenção (DB): roda os agendamentos de backup vencidos (Diário, Semanal ou Mensal)."""
    import backup_servico
    return backup_servico.executar_vencidos(agora)


def aprender_mudancas_da_plataforma(agora):
    """Agente Gerente Técnico: percebe perfis e rotas novos e distribui os aprendizados aos agentes (autônomo)."""
    import conhecimento
    return len(conhecimento.detectar_mudancas('Agente Gerente Técnico (tarefa de hora em hora)'))


def aprender_seguranca(agora):
    """Gerente de Segurança: aprende rotas, perfis, dados sensíveis e componentes novos (aplicados na hora) e,
    uma vez por dia, pesquisa vulnerabilidades na OSV.dev (fonte oficial; os avisos ficam pendentes de aprovação)."""
    import conhecimento_seguranca
    novos = len(conhecimento_seguranca.detectar_mudancas('Gerente de Segurança (tarefa de hora em hora)'))
    try:
        novos += len(conhecimento_seguranca.pesquisar_vulnerabilidades('Gerente de Segurança (tarefa diária)'))
    except Exception as erro:
        db.session.rollback()
        log.warning("OSV.dev indisponível: %s: %s", type(erro).__name__, erro)
    return novos


def aprender_banco_de_dados(agora):
    """Gerente de Banco de Dados: aprende motor, esquema, índices, agendamentos de backup e drivers (aplicados na hora),
    guarda a foto diária de crescimento e busca a documentação oficial dos bancos que passarem a ser necessários (pendente)."""
    import conhecimento_banco
    return len(conhecimento_banco.detectar_mudancas('Gerente de Banco de Dados (tarefa de hora em hora)'))


def aprender_funcionalidades(agora):
    """Gerente de Funcionalidades: aprende as regras de negócio (módulos dos perfis, regras do app) e as funções novas."""
    import conhecimento_funcional
    return len(conhecimento_funcional.detectar_mudancas('Gerente de Funcionalidades (tarefa de hora em hora)'))


def aplicar_mudancas_aprovadas(agora):
    """Requisições de mudança de parâmetros aprovadas cuja data agendada chegou: passam a valer (hora local do servidor)."""
    import mudancas
    return mudancas.aplicar_vencidas()



def executar_mudancas_de_codigo(agora):
    """Requisição de mudança de código aprovada e na data agendada: o Agente Orquestrador executor roda sozinho
    (commit automático se todas as equipes aprovarem; senão rollback). Também leva o resultado para a CR."""
    from app import executar_mudancas_de_codigo as executar
    return executar()


TAREFAS = [aplicar_mudancas_aprovadas, executar_mudancas_de_codigo, lembrar_checkout_esquecido, lembrar_encaminhamentos_vencidos, avisar_ocorrencias_atrasadas, enviar_formulario_banca, fechar_checkin_banca_esquecido,
           fechar_presenca_reuniao_esquecida, abrir_microavaliacao, lembrar_avaliacao_pendente, lembrar_avaliacao_reuniao,
           lembrar_saida_esquecida, avisar_prazo_entrega_tcc,
           executar_backups_agendados, aprender_mudancas_da_plataforma, aprender_seguranca, aprender_banco_de_dados, aprender_funcionalidades]


def executar_tarefas(parar=None):
    """Roda todas as tarefas uma vez. 'parar' (threading.Event): pedido de desligamento, checado entre as tarefas.
    Devolve {tarefa: resultado ou 'ERRO'}."""
    agora = datetime.utcnow()
    resultados = {}
    with app.app_context():
        for tarefa in TAREFAS:
            if parar is not None and parar.is_set():
                log.info("desligamento pedido: as tarefas restantes ficam para a próxima rodada")
                break
            try:
                resultados[tarefa.__name__] = tarefa(agora)
                log.info("%s: %s aviso(s)", tarefa.__name__, resultados[tarefa.__name__], extra={"evento": "tarefa"})
            except Exception as erro:
                db.session.rollback()
                resultados[tarefa.__name__] = "ERRO"
                log.error("%s falhou: %s: %s", tarefa.__name__, type(erro).__name__, erro, extra={"evento": "tarefa"})
    import ambiente
    ambiente.anotar_execucao_das_tarefas()   # a tela Ambiente e compatibilidade mostra se as tarefas estão rodando
    return resultados


INTERVALO_PADRAO = 3600  # segundos entre as rodadas no modo contínuo


def rodar_continuo(parar, intervalo=None, rodada=executar_tarefas):
    """Rodadas até 'parar' ser ligado (SIGTERM/SIGINT). A espera entre rodadas acorda na hora no desligamento."""
    intervalo = intervalo or int(os.environ.get("TAREFAS_INTERVALO_SEGUNDOS") or INTERVALO_PADRAO)
    rodadas = 0
    while not parar.is_set():
        rodada(parar)
        rodadas += 1
        parar.wait(intervalo)
    log.info("worker encerrado depois de %d rodada(s)", rodadas)
    return rodadas


if __name__ == "__main__":
    import signal
    import sys
    import threading

    if "--continuo" in sys.argv:
        parar = threading.Event()
        for sinal in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sinal, lambda *_: parar.set())
        rodar_continuo(parar)
    else:
        executar_tarefas()
