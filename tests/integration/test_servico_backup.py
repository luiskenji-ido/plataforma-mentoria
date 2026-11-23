"""Backup e restauração fora da plataforma pública: endereços antigos, worker e o backup prévio do DBA pelo serviço."""

from datetime import datetime

import pytest

ENDERECOS_ANTIGOS = [
    ("get", "/admin/banco"),
    ("post", "/admin/banco"),
    ("get", "/admin/banco/arquivo?f=manuais/x.sql.gz"),
    ("get", "/admin/banco/relatorio/execucoes.csv"),
    ("get", "/admin/banco/relatorio/alteracoes.csv"),
    ("post", "/admin/ambiente/backups-padrao"),
]


@pytest.mark.parametrize("perfil", ["Administrador", "Mentor Administrador", "Aluno"])
def test_enderecos_antigos_de_backup_nao_existem(novo_usuario, novo_navegador, perfil):
    _, email, senha = novo_usuario(perfil)
    nav = novo_navegador()
    nav.entrar(email, senha)
    for metodo, caminho in ENDERECOS_ANTIGOS:
        r = getattr(nav, metodo)(caminho, data={"acao": "backup"}) if metodo == "post" else nav.get(caminho)
        assert r.status_code == 404, (perfil, metodo, caminho, r.status_code)


def test_menu_e_telas_nao_apontam_para_backup(novo_usuario, novo_navegador, monkeypatch):
    _, email, senha = novo_usuario("Administrador")
    nav = novo_navegador()
    nav.entrar(email, senha)
    for caminho in ("/dashboard", "/admin/ambiente", "/admin/agentes-banco", "/admin/agentes-funcionalidades"):
        r = nav.get(caminho)
        assert r.status_code == 200, caminho
        assert b"/admin/banco" not in r.data, caminho
    monkeypatch.setenv("BACKUP_PAINEL_URL", "https://backup.mentoria.interno:8443/admin/banco")
    assert b"https://backup.mentoria.interno:8443/admin/banco" in nav.get("/admin/ambiente").data  # só o atalho para a VPN


def test_worker_e_requisicoes_nao_rodam_backup(app_real):
    import tarefas_agendadas

    nomes = [t.__name__ for t in tarefas_agendadas.TAREFAS]
    assert not [n for n in nomes if "backup" in n]
    assert not hasattr(app_real, "iniciar_agendador") and not hasattr(app_real, "rotina_de_backups")


def test_requisicoes_de_mudanca_seguem_no_intervalo_de_5_min(app_real, monkeypatch):
    mudancas = []
    monkeypatch.setattr(app_real, "_ULTIMA_VERIFICACAO_TAREFAS", [datetime.min])
    monkeypatch.setattr(app_real, "_executar_mudancas_com_seguranca", lambda: mudancas.append(1))
    cliente = app_real.app.test_client()
    cliente.get("/")
    cliente.get("/")
    assert mudancas == [1]


def test_dba_sem_servico_configurado_nao_altera_nada(app_real, monkeypatch, novo_usuario):
    import banco_manutencao

    admin_id, _, _ = novo_usuario("Administrador")
    monkeypatch.delenv("BACKUP_SERVICO_URL", raising=False)
    executou = []
    monkeypatch.setattr(banco_manutencao, "_executar_mysql", lambda *a: executou.append(a) or "Concluída")
    with app_real.app.app_context():
        registro = banco_manutencao.executar("otimizar", admin_id)
        assert registro.status == "Falha" and "BACKUP_SERVICO_URL" in registro.detalhes
        app_real.db.session.delete(registro)
        app_real.db.session.commit()
    assert executou == []


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
