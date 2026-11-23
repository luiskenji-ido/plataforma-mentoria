"""Backup e restauração (Manutenção (DB)) pelo HTTP, contra o MySQL de teste (descartável).

Cobre as rotas que saíram do app.py para rotas_backup.py (mesmos endpoints), a reserva atômica dos agendamentos
vencidos e uma restauração de ponta a ponta. Precisa do mysqldump/mysql no computador que roda os testes.
"""

import shutil
import uuid
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(not (shutil.which("mysqldump") and shutil.which("mysql")), reason="precisa do mysql-client")


@pytest.fixture
def pasta_backups(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("BACKUP_DIR_EXTERNO", raising=False)
    return tmp_path / "backups"


@pytest.fixture
def historico_limpo(app_real):
    """Apaga, no fim, as linhas de backup que o teste criou (as tabelas de backup sobrevivem à restauração)."""
    from models import AgendamentoBackup, AlteracaoAgendamentoBackup, RegistroBackup

    db = app_real.db
    modelos = (RegistroBackup, AgendamentoBackup, AlteracaoAgendamentoBackup)
    with app_real.app.app_context():
        maiores = {m: db.session.query(db.func.max(m.id)).scalar() or 0 for m in modelos}
    yield
    with app_real.app.app_context():
        for modelo, maior in maiores.items():
            modelo.query.filter(modelo.id > maior).delete()
        db.session.commit()


@pytest.fixture
def admin(novo_usuario, novo_navegador):
    _, email, senha = novo_usuario("Administrador")
    nav = novo_navegador()
    nav.entrar(email, senha)
    return nav


def _registros(app_real, **filtro):
    from models import RegistroBackup

    with app_real.app.app_context():
        return [(r.tipo, r.status, r.arquivo) for r in RegistroBackup.query.filter_by(**filtro).order_by(RegistroBackup.id).all()]


def _detalhes(app_real, pasta):
    from models import RegistroBackup

    with app_real.app.app_context():
        return [r.detalhes for r in RegistroBackup.query.filter_by(destino=pasta)]


@pytest.mark.parametrize("perfil", ["Mentor Administrador", "Admin B2B", "Aluno"])
def test_so_o_administrador_usa_as_rotas_de_backup(app_real, novo_usuario, novo_navegador, pasta_backups, historico_limpo, perfil):
    _, email, senha = novo_usuario(perfil)
    nav = novo_navegador()
    nav.entrar(email, senha)
    antes = len(_registros(app_real))
    for resposta in (
        nav.get("/admin/banco"),
        nav.post("/admin/banco", {"acao": "backup", "pasta": "manuais"}),
        nav.get("/admin/banco/arquivo?f=manuais/x.sql.gz"),
        nav.get("/admin/banco/relatorio/execucoes.csv"),
    ):
        assert resposta.status_code == 302 and "/admin/banco" not in resposta.headers["Location"]
    assert len(_registros(app_real)) == antes
    assert not pasta_backups.exists() or not any(pasta_backups.rglob("*.sql.gz"))


def test_tela_abre_com_saude_e_agendamentos(admin, pasta_backups, historico_limpo):
    r = admin.get("/admin/banco")
    assert r.status_code == 200 and b"agendamento" in r.data.lower()


def test_agendamento_invalido_e_recusado_e_valido_e_auditado(app_real, admin, pasta_backups, historico_limpo):
    from models import AgendamentoBackup, AlteracaoAgendamentoBackup

    pasta = "it_" + uuid.uuid4().hex[:8]
    base = {"acao": "novo_agendamento", "frequencia": "Diário", "data_inicio": "2026-01-01", "retencao": "3", "pasta": pasta}
    admin.post("/admin/banco", {**base, "horario": "25:00"})
    with app_real.app.app_context():
        assert AgendamentoBackup.query.filter_by(pasta=pasta).count() == 0
    admin.post("/admin/banco", {**base, "horario": "02:30"})
    with app_real.app.app_context():
        ag = AgendamentoBackup.query.filter_by(pasta=pasta).one()
        assert (ag.frequencia, ag.horario, ag.retencao, ag.status) == ("Diário", "02:30", 3, "Ativo")
        assert ag.proxima_execucao > datetime.now() and ag.proxima_execucao.strftime("%H:%M") == "02:30"
        assert [a.acao for a in AlteracaoAgendamentoBackup.query.filter_by(agendamento_id=ag.id)] == ["Criado"]
        ident = ag.id
    admin.post("/admin/banco", {"acao": "pausar", "agendamento_id": ident})
    with app_real.app.app_context():
        assert AgendamentoBackup.query.get(ident).status == "Pausado"
        assert [a.acao for a in AlteracaoAgendamentoBackup.query.filter_by(agendamento_id=ident)] == ["Criado", "Pausado"]


def test_backup_imediato_baixar_e_relatorio(app_real, admin, pasta_backups, historico_limpo):
    pasta = "it_" + uuid.uuid4().hex[:8]
    assert admin.post("/admin/banco", {"acao": "backup", "pasta": pasta}).status_code == 302
    arquivos = list((pasta_backups / pasta).glob("mentoria_backup_*.sql.gz"))
    assert len(arquivos) == 1, _detalhes(app_real, pasta)
    nome = arquivos[0].name
    assert ("Imediato", "Concluído", nome) in _registros(app_real, destino=pasta)

    r = admin.get(f"/admin/banco/arquivo?f={pasta}/{nome}")
    assert r.status_code == 200 and r.data[:2] == b"\x1f\x8b"  # gzip
    assert ("Download", "Concluído", nome) in _registros(app_real, arquivo=nome)

    assert admin.get("/admin/banco/arquivo?f=../../etc/passwd").status_code == 302

    csv = admin.get("/admin/banco/relatorio/execucoes.csv")
    assert csv.status_code == 200 and csv.mimetype == "text/csv" and nome.encode() in csv.data


def test_agendamento_vencido_roda_uma_vez_mesmo_com_dois_processos(app_real, pasta_backups, historico_limpo):
    """Dois processos leem o mesmo agendamento vencido: só quem ganha a reserva atômica faz o backup."""
    from sqlalchemy.orm.attributes import set_committed_value

    import backup_servico
    from models import AgendamentoBackup

    db = app_real.db
    with app_real.app.app_context():
        agora = datetime.now()
        ag = AgendamentoBackup(
            frequencia="Diário",
            horario="03:00",
            data_inicio=(agora - timedelta(days=3)).date(),
            status="Ativo",
            retencao=2,
            pasta="it_" + uuid.uuid4().hex[:8],
            proxima_execucao=agora - timedelta(minutes=1),
        )
        db.session.add(ag)
        db.session.commit()
        ident, lida = ag.id, ag.proxima_execucao

        assert backup_servico.reservar_execucao(ag, agora) is True  # processo A
        db.session.expire_all()
        ag_b = db.session.get(AgendamentoBackup, ident)
        set_committed_value(ag_b, "proxima_execucao", lida)  # processo B ainda tem a leitura antiga em memória
        assert backup_servico.reservar_execucao(ag_b, agora) is False
        db.session.rollback()
        assert db.session.get(AgendamentoBackup, ident).proxima_execucao > agora


def test_executar_vencidos_faz_o_backup_e_aplica_a_retencao(app_real, pasta_backups, historico_limpo):
    import backup_servico
    from models import AgendamentoBackup

    db = app_real.db
    pasta = "it_" + uuid.uuid4().hex[:8]
    with app_real.app.app_context():
        agora = datetime.now()
        ag = AgendamentoBackup(
            frequencia="Diário", horario="03:00", data_inicio=(agora - timedelta(days=3)).date(), status="Ativo", retencao=1, pasta=pasta
        )
        db.session.add(ag)
        db.session.commit()
        for _ in range(2):
            ag.proxima_execucao = datetime.now() - timedelta(minutes=1)
            db.session.commit()
            assert backup_servico.executar_vencidos(datetime.now()) >= 1
        assert len(list((pasta_backups / pasta).glob(f"mentoria_backup_ag{ag.id}_diario_*.sql.gz"))) == 1  # retenção 1
        assert backup_servico.executar_vencidos(datetime.now()) == 0  # nada vencido de novo


def test_restauracao_de_ponta_a_ponta_no_banco_descartavel(app_real, admin, novo_usuario, pasta_backups, historico_limpo):
    """Backup → dado novo → restaurar → o dado novo some, o admin continua e o histórico de backups é preservado."""
    from models import RegistroBackup, Usuario

    pasta = "it_" + uuid.uuid4().hex[:8]
    admin.post("/admin/banco", {"acao": "backup", "pasta": pasta})
    (arquivo,) = (pasta_backups / pasta).glob("*.sql.gz")
    marcador_id, _, _ = novo_usuario("Aluno")  # criado DEPOIS do backup

    r = admin.post("/admin/banco", {"acao": "restaurar", "arquivo_existente": f"{pasta}/{arquivo.name}"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/banco")
    with app_real.app.app_context():
        assert app_real.db.session.get(Usuario, marcador_id) is None
        tipos = [x.tipo for x in RegistroBackup.query.filter(RegistroBackup.arquivo.isnot(None)).order_by(RegistroBackup.id)]
    assert "Segurança (pré-restauração)" in tipos and tipos[-1] == "Restauração"
    assert ("Restauração", "Concluído", arquivo.name) in _registros(app_real, arquivo=arquivo.name)
    assert list((pasta_backups / "seguranca").glob("*.sql.gz")), "cópia do banco anterior guardada antes de restaurar"
    assert admin.get("/admin/banco").status_code == 200  # a sessão do admin sobrevive (a conta está no backup)
