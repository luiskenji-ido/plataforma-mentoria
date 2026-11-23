"""Monólito ligado ao serviço privado de backup: o agendador num lugar só e o backup prévio do DBA pela API."""

from datetime import datetime

import pytest


@pytest.fixture
def agendador_no_servico(monkeypatch):
    monkeypatch.setenv("BACKUP_AGENDADOR", "servico")


def test_com_agendador_no_servico_as_requisicoes_nao_rodam_backup(app_real, monkeypatch, agendador_no_servico):
    import backup_servico

    chamadas, mudancas = [], []
    monkeypatch.setattr(app_real, "_ULTIMA_VERIFICACAO_BACKUP", [datetime.min])
    monkeypatch.setattr(backup_servico, "executar_vencidos", lambda agora: chamadas.append(agora))
    monkeypatch.setattr(app_real, "_executar_mudancas_com_seguranca", lambda: mudancas.append(1))
    app_real.app.test_client().get("/")
    assert chamadas == [] and mudancas == [1]  # as requisições de mudança continuam com o mesmo intervalo


def test_sem_a_variavel_o_comportamento_de_sempre(app_real, monkeypatch):
    import backup_servico

    monkeypatch.delenv("BACKUP_AGENDADOR", raising=False)
    chamadas = []
    monkeypatch.setattr(app_real, "_ULTIMA_VERIFICACAO_BACKUP", [datetime.min])
    monkeypatch.setattr(backup_servico, "executar_vencidos", lambda agora: chamadas.append(agora))
    app_real.app.test_client().get("/")
    assert len(chamadas) == 1


def test_com_agendador_no_servico_o_worker_e_a_thread_nao_rodam_backup(app_real, monkeypatch, agendador_no_servico):
    import threading

    import backup_servico
    import tarefas_agendadas

    monkeypatch.setattr(backup_servico, "executar_vencidos", lambda *_: pytest.fail("o worker rodou backup agendado"))
    assert tarefas_agendadas.executar_backups_agendados(datetime.now()) == 0
    antes = threading.active_count()
    app_real.iniciar_agendador(app_real.app)
    assert threading.active_count() == antes  # a thread do 'python app.py' não foi criada


def test_dba_com_servico_fora_do_ar_nao_altera_nada(app_real, monkeypatch, novo_usuario):
    import banco_manutencao
    import cliente_backup

    admin_id, _, _ = novo_usuario("Administrador")
    monkeypatch.setenv("BACKUP_SERVICO_URL", "https://backup.invalido:8443")
    monkeypatch.setattr(
        cliente_backup, "pedir_backup", lambda *a, **k: (_ for _ in ()).throw(cliente_backup.ErroServicoBackup("inacessível"))
    )
    executou = []
    monkeypatch.setattr(banco_manutencao, "_executar_mysql", lambda *a: executou.append(a) or "Concluída")
    with app_real.app.app_context():
        registro = banco_manutencao.executar("otimizar", admin_id)
        assert registro.status == "Falha" and "nada foi alterado" in registro.detalhes and "inacessível" in registro.detalhes
        app_real.db.session.delete(registro)
        app_real.db.session.commit()
    assert executou == []


def test_dba_usa_o_backup_do_servico(app_real, monkeypatch, novo_usuario):
    import banco_manutencao
    import cliente_backup

    admin_id, _, _ = novo_usuario("Administrador")
    monkeypatch.setenv("BACKUP_SERVICO_URL", "https://backup.mentoria.interno:8443")
    pedidos = []
    monkeypatch.setattr(
        cliente_backup,
        "pedir_backup",
        lambda motivo, solicitante=None, **k: pedidos.append((motivo, solicitante.id)) or {"status": "Concluído", "arquivo": "srv.sql.gz"},
    )
    monkeypatch.setattr(banco_manutencao, "_executar_mysql", lambda *a: "Concluída")
    with app_real.app.app_context():
        registro = banco_manutencao.executar("otimizar", admin_id)
        assert registro.status == "Concluída" and registro.backup_arquivo == "srv.sql.gz"
        app_real.db.session.delete(registro)
        app_real.db.session.commit()
    assert pedidos == [("pre_manutencao: otimizar", admin_id)]
