# -*- coding: utf-8 -*-
"""
ROTAS DE BACKUP E RESTAURAÇÃO (Sistema › Manutenção (DB))
========================================================
Tela e downloads do Administrador:
    GET/POST /admin/banco                    manutencao_banco             saúde, agendamentos, backup, restauração, limpezas
    GET      /admin/banco/arquivo?f=         baixar_backup                baixa um arquivo da pasta de backups
    GET      /admin/banco/relatorio/<t>.csv  relatorio_auditoria_backup   execuções (filtro de datas) ou alterações

Os nomes dos endpoints são os mesmos de quando as rotas ficavam no app.py: url_for(), perfis_acesso.MODULOS, o
menu e os agentes continuam valendo. O trabalho fica no backup_servico.py (cópia, restauração, agendamentos) e as
decisões no backup_regras.py; aqui só há HTTP: permissão, formulário, mensagem e redirecionamento.

Este módulo é a fronteira do recurso de backup dentro do monólito: quando o serviço de backup privado assumir,
sai daqui (e do registrar() no app.py) e não de dentro do app.py.
"""

import csv
import io
import os
from datetime import datetime

from flask import Response, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

import backup_regras
import backup_servico as bs
from models import (
    Acompanhamento,
    AgendamentoBackup,
    AlteracaoAgendamentoBackup,
    AulaCurso,
    Curso,
    FeedbackSessao,
    HistoricoProgresso,
    HistoricoSenha,
    ProgressoAula,
    QADuvida,
    QuestaoAula,
    SegurancaUsuario,
    SessaoMentoria,
    Usuario,
    aluno_mentor,
    db,
)
from traducoes_literais import tt

ENDPOINT_TELA = "manutencao_banco"
CONFIRMACAO_LIMPEZA = "APAGAR"


def registrar(app, perfis_permitidos, atualizar_estrutura_banco):
    """Liga as rotas no app com os mesmos endpoints de antes.
    perfis_permitidos: regra nomeada PERFIS_ADMINISTRACAO_SISTEMA; atualizar_estrutura_banco: roda depois de restaurar."""

    def negar_se_nao_permitido():
        if current_user.tipo_usuario not in perfis_permitidos:
            flash("Acesso Negado.", "danger")
            return redirect(url_for("dashboard"))
        return None

    @login_required
    def manutencao_banco():
        """Manutenção (DB): saúde dos backups, agendamentos, backup imediato, restauração, histórico e zona de perigo."""
        negado = negar_se_nao_permitido()
        if negado:
            return negado
        if request.method == "POST":
            acao = request.form.get("acao")
            tratar = _ACOES.get(acao)
            if tratar:
                resposta = tratar(current_user.idioma, atualizar_estrutura_banco)
                if resposta is not None:
                    return resposta
            return redirect(url_for(ENDPOINT_TELA))
        return _tela()

    @login_required
    def baixar_backup():
        """Baixa um arquivo de backup do servidor (só os que estão na pasta de backups)."""
        negado = negar_se_nao_permitido()
        if negado:
            return negado
        caminho = bs.caminho_seguro(request.args.get("f"))
        if not caminho:
            flash(tt("Arquivo de backup não encontrado.", current_user.idioma), "warning")
            return redirect(url_for(ENDPOINT_TELA))
        bs.registrar(
            "Download",
            "Concluído",
            f"Arquivo baixado: {request.args.get('f')}",
            current_user.id,
            arquivo=os.path.basename(caminho),
            tamanho=os.path.getsize(caminho),
        )
        return send_file(caminho, as_attachment=True, download_name=os.path.basename(caminho))

    @login_required
    def relatorio_auditoria_backup(tipo):
        """Relatórios para auditoria: execuções (com o filtro de datas da tela) ou alterações dos agendamentos."""
        negado = negar_se_nao_permitido()
        if negado:
            return negado
        return _relatorio_csv(tipo)

    app.add_url_rule("/admin/banco", ENDPOINT_TELA, manutencao_banco, methods=["GET", "POST"])
    app.add_url_rule("/admin/banco/arquivo", "baixar_backup", baixar_backup)
    app.add_url_rule("/admin/banco/relatorio/<tipo>.csv", "relatorio_auditoria_backup", relatorio_auditoria_backup)


# ------------------------------------------------------------------------------
# Tela e relatórios
# ------------------------------------------------------------------------------
def _tela():
    data_inicio, data_fim = request.args.get("data_inicio"), request.args.get("data_fim")
    return render_template(
        "admin_banco.html",
        logs_backup=bs.historico_filtrado(data_inicio, data_fim).all(),
        data_inicio=data_inicio,
        data_fim=data_fim,
        agendamentos=AgendamentoBackup.query.order_by(AgendamentoBackup.id.desc()).all(),
        alteracoes=AlteracaoAgendamentoBackup.query.order_by(AlteracaoAgendamentoBackup.data.desc()).limit(200).all(),
        saude=bs.saude(),
        backups=bs.listar_backups(),
        subpastas=bs.subpastas(),
        frequencias=bs.FREQUENCIAS,
        tamanho_legivel=bs.tamanho_legivel,
        hoje=datetime.now().strftime("%Y-%m-%d"),
    )


def _relatorio_csv(tipo):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    if tipo == "alteracoes":
        escritor.writerow(["Data/Hora", "Agendamento", "Ação", "Usuário", "Detalhes"])
        for a in AlteracaoAgendamentoBackup.query.order_by(AlteracaoAgendamentoBackup.data.desc()).all():
            escritor.writerow(
                [
                    a.data.strftime("%d/%m/%Y %H:%M:%S"),
                    a.agendamento_id,
                    a.acao,
                    a.usuario.nome if a.usuario else "sistema",
                    a.detalhes or "",
                ]
            )
    else:
        registros = bs.historico_filtrado(request.args.get("data_inicio"), request.args.get("data_fim")).all()
        cabecalho, linhas = bs.exportar_historico_csv(registros)
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)
    nome = f"auditoria_backup_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        "﻿" + saida.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={nome}"}
    )


def _avisar_resultado_do_backup(registro, idioma):
    if registro.status == "Concluído":
        flash(tt("Backup concluído e validado: {arquivo}", idioma).format(arquivo=registro.arquivo), "success")
    else:
        flash(tt("O backup falhou: {erro}", idioma).format(erro=registro.detalhes), "danger")


# ------------------------------------------------------------------------------
# Ações do formulário (cada uma devolve None para voltar à tela, ou a própria resposta)
# ------------------------------------------------------------------------------
def _acao_backup_imediato(idioma, _atualizar):
    """Backup imediato (fica no servidor, na pasta de backups/<pasta>, e pode ser baixado depois)."""
    _avisar_resultado_do_backup(bs.fazer_backup("Imediato", request.form.get("pasta"), current_user.id), idioma)


def _acao_salvar_agendamento(idioma, _atualizar):
    """Criar ou editar agendamento."""
    dados = backup_regras.validar_agendamento(
        request.form.get("frequencia"), request.form.get("horario"), request.form.get("data_inicio"), request.form.get("retencao")
    )
    if dados is None:
        flash(tt("Confira a frequência, o horário (HH:MM), a data de início e a retenção (1 a 365).", idioma), "warning")
        return redirect(url_for(ENDPOINT_TELA))
    if request.form.get("acao") == "novo_agendamento":
        agendamento = AgendamentoBackup(criado_por_id=current_user.id, status="Ativo")
        db.session.add(agendamento)
        antes = None
    else:
        agendamento = db.session.get(AgendamentoBackup, request.form.get("agendamento_id", type=int))
        if not agendamento:
            return redirect(url_for(ENDPOINT_TELA))
        antes = bs.descrever(agendamento)
    agendamento.frequencia, agendamento.horario, agendamento.data_inicio = dados.frequencia, dados.horario, dados.data_inicio
    agendamento.retencao, agendamento.pasta = dados.retencao, bs.nome_de_pasta(request.form.get("pasta") or "agendados")
    db.session.flush()
    agendamento.proxima_execucao = bs.calcular_proxima(agendamento, datetime.now())
    if antes is None:
        bs.registrar_alteracao(agendamento.id, "Criado", bs.descrever(agendamento), current_user.id)
        flash(
            tt("Agendamento criado. Próxima execução: {data}", idioma).format(data=agendamento.proxima_execucao.strftime("%d/%m/%Y %H:%M")),
            "success",
        )
    else:
        bs.registrar_alteracao(agendamento.id, "Editado", f"De: {antes} | Para: {bs.descrever(agendamento)}", current_user.id)
        flash(tt("Agendamento atualizado.", idioma), "success")
    db.session.commit()


def _acao_no_agendamento(idioma, _atualizar):
    """Pausar, retomar, executar agora ou excluir agendamento."""
    acao = request.form.get("acao")
    agendamento = db.session.get(AgendamentoBackup, request.form.get("agendamento_id", type=int))
    if not agendamento:
        return None
    if acao == "pausar":
        agendamento.status = "Pausado"
        bs.registrar_alteracao(agendamento.id, "Pausado", bs.descrever(agendamento), current_user.id)
        flash(tt("Agendamento pausado.", idioma), "info")
    elif acao == "retomar":
        agendamento.status = "Ativo"
        agendamento.proxima_execucao = bs.calcular_proxima(agendamento, datetime.now())
        bs.registrar_alteracao(agendamento.id, "Retomado", bs.descrever(agendamento), current_user.id)
        flash(tt("Agendamento retomado.", idioma), "success")
    elif acao == "executar":
        bs.registrar_alteracao(agendamento.id, "Executado manualmente", bs.descrever(agendamento), current_user.id)
        db.session.commit()
        _avisar_resultado_do_backup(bs.executar_agendamento(agendamento, current_user.id), idioma)
    else:
        bs.registrar_alteracao(agendamento.id, "Excluído", bs.descrever(agendamento), current_user.id)
        db.session.delete(agendamento)
        flash(tt("Agendamento excluído. Os arquivos já gerados continuam na pasta.", idioma), "info")
    db.session.commit()


def _acao_restaurar(idioma, atualizar_estrutura_banco):
    """Restaurar (arquivo da lista ou enviado), com cópia de segurança do banco atual antes."""
    caminho = bs.caminho_seguro(request.form.get("arquivo_existente"))
    enviado = request.files.get("arquivo_db")
    if not caminho and enviado and enviado.filename:
        if not enviado.filename.lower().endswith(bs.EXTENSOES):
            flash(tt("Envie um arquivo .db (SQLite) ou .sql.gz (MySQL) gerado pelo backup da plataforma.", idioma), "warning")
            return redirect(url_for(ENDPOINT_TELA))
        caminho = os.path.join(bs.pasta_de("enviados"), f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(enviado.filename)}")
        enviado.save(caminho)
    if not caminho:
        flash(tt("Escolha um backup da lista ou envie um arquivo.", idioma), "warning")
        return redirect(url_for(ENDPOINT_TELA))
    usuario_id = current_user.id
    ok, info = bs.restaurar(caminho, usuario_id, atualizar_estrutura_banco)
    if not ok:
        flash(tt("Restauração cancelada: {erro}", idioma).format(erro=info), "danger")
        return None
    flash(tt("Banco restaurado. A cópia do banco anterior foi guardada em: {arquivo}", idioma).format(arquivo=info), "success")
    if not db.session.get(Usuario, usuario_id):
        logout_user()
        flash(tt("Sua conta não existe no backup restaurado: entre com uma conta desse backup.", idioma), "warning")
        return redirect(url_for("login"))
    return None


def _acao_limpar_dados(idioma, _atualizar):
    """Zona de perigo: apaga os dados (exige digitar APAGAR e faz backup de segurança antes)."""
    if (request.form.get("confirmacao") or "").strip().upper() != CONFIRMACAO_LIMPEZA:
        flash(tt("Para apagar os dados, digite APAGAR no campo de confirmação.", idioma), "warning")
        return redirect(url_for(ENDPOINT_TELA))
    seguranca = bs.fazer_backup("Segurança (pré-limpeza)", "seguranca", current_user.id)
    if seguranca.status != "Concluído":
        flash(tt("Limpeza cancelada: não foi possível fazer o backup de segurança.", idioma), "danger")
        return redirect(url_for(ENDPOINT_TELA))
    try:
        _apagar_dados_exceto(current_user.id)
        bs.registrar(
            "Limpeza de dados",
            "Concluído",
            f"Dados apagados; só a conta de {current_user.nome} foi preservada. Backup de segurança: {seguranca.arquivo}.",
            current_user.id,
            arquivo=seguranca.arquivo,
        )
        flash(tt("Dados apagados. Backup de segurança guardado em: {arquivo}", idioma).format(arquivo=seguranca.arquivo), "success")
    except Exception as e:
        db.session.rollback()
        bs.registrar("Limpeza de dados", "Falha", f"Erro: {e}", current_user.id)
        flash(tt("Erro ao apagar os dados: {erro}", idioma).format(erro=e), "danger")
    return None


def _apagar_dados_exceto(usuario_id):
    """Ordem das exclusões: filhas antes das mães (chaves estrangeiras)."""
    QADuvida.query.delete()
    FeedbackSessao.query.delete()
    SessaoMentoria.query.delete()
    HistoricoProgresso.query.delete()
    ProgressoAula.query.delete()
    QuestaoAula.query.delete()
    AulaCurso.query.delete()
    Acompanhamento.query.delete()
    HistoricoSenha.query.filter(HistoricoSenha.usuario_id != usuario_id).delete()
    SegurancaUsuario.query.filter(SegurancaUsuario.usuario_id != usuario_id).delete()
    Curso.query.delete()
    db.session.execute(aluno_mentor.delete())
    Usuario.query.filter(Usuario.id != usuario_id).delete()
    db.session.commit()


def _acao_apagar_historico(idioma, _atualizar):
    """Apagar o histórico de execuções (guarda um CSV de auditoria antes e registra quem apagou)."""
    total, arquivo = bs.apagar_historico(current_user.id, current_user.nome)
    flash(
        tt("{total} registro(s) apagado(s). Cópia em CSV guardada em: auditoria/{arquivo}", idioma).format(total=total, arquivo=arquivo),
        "success",
    )


_ACOES = {
    "backup": _acao_backup_imediato,
    "novo_agendamento": _acao_salvar_agendamento,
    "editar_agendamento": _acao_salvar_agendamento,
    "pausar": _acao_no_agendamento,
    "retomar": _acao_no_agendamento,
    "executar": _acao_no_agendamento,
    "excluir": _acao_no_agendamento,
    "restaurar": _acao_restaurar,
    "limpar": _acao_limpar_dados,
    "limpar_auditoria": _acao_apagar_historico,
}
