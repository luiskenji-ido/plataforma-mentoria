"""Arquivos enviados pelas telas (comportamento capturado antes da troca do disco pelo armazenamento S3/local).

Os uploads vão para uma pasta temporária: o teste nunca grava na pasta uploads/ real.
"""

import io
import uuid
from datetime import datetime, timedelta

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def pasta_uploads(app_real, tmp_path, monkeypatch):
    """Aponta todas as pastas de upload do app (e o armazenamento) para tmp_path."""
    monkeypatch.setenv("PASTA_UPLOADS", str(tmp_path))
    monkeypatch.setenv("ARMAZENAMENTO", "local")
    try:
        import armazenamento

        armazenamento.esquecer()
    except ImportError:
        pass
    monkeypatch.setitem(app_real.app.config, "UPLOAD_FOLDER", str(tmp_path))
    for nome, sub in (
        ("PASTA_AULAS", "aulas"),
        ("PASTA_GRAVACOES", "reunioes"),
        ("PASTA_TCC", "tcc"),
        ("PASTA_ACERVO", "acervo"),
        ("PASTA_LOGOS", "logos"),
    ):
        if hasattr(app_real, nome):
            monkeypatch.setattr(app_real, nome, str(tmp_path / sub))
    yield tmp_path
    try:
        import armazenamento

        armazenamento.esquecer()
    except ImportError:
        pass


class Baixado:
    """Resposta lida e FECHADA (no Windows um arquivo aberto pelo send_file não pode ser apagado)."""

    def __init__(self, resposta):
        self.status_code, self.headers, self.mimetype = resposta.status_code, resposta.headers, resposta.mimetype
        self.data = resposta.get_data()
        resposta.close()


def baixar(navegador, url, **kw):
    return Baixado(navegador.get(url, **kw))


def _arquivos(pasta):
    return sorted(p.relative_to(pasta).as_posix() for p in pasta.rglob("*") if p.is_file())


def _criar(app_real, criados, modelo, **campos):
    with app_real.app.app_context():
        obj = modelo(**campos)
        app_real.db.session.add(obj)
        app_real.db.session.commit()
        criados.append((modelo, obj.id))
        return obj.id


# ------------------------------------------------------------------ logo do parceiro (empresa)
def test_logo_da_empresa_envia_serve_troca_e_remove(app_real, navegador, novo_usuario, criados, pasta_uploads):
    from models import Empresa

    _, email, senha = novo_usuario("Administrador")
    navegador.entrar(email, senha)
    empresa_id = _criar(app_real, criados, Empresa, nome=f"Parceira {uuid.uuid4().hex[:6]}")

    assert baixar(navegador, f"/empresas/{empresa_id}/logo").status_code == 404
    navegador.post(f"/empresas/{empresa_id}/logo/enviar", {"logo": (io.BytesIO(PNG), "logo.png")}, content_type="multipart/form-data")
    r = baixar(navegador, f"/empresas/{empresa_id}/logo")
    assert r.status_code == 200 and r.data == PNG and r.headers["X-Content-Type-Options"] == "nosniff"
    assert len(_arquivos(pasta_uploads)) == 1

    navegador.post(
        f"/empresas/{empresa_id}/logo/enviar", {"logo": (io.BytesIO(PNG + b"2"), "novo.png")}, content_type="multipart/form-data"
    )
    assert baixar(navegador, f"/empresas/{empresa_id}/logo").data == PNG + b"2"
    assert len(_arquivos(pasta_uploads)) == 1  # o antigo foi apagado

    navegador.post(f"/empresas/{empresa_id}/logo/enviar", {"acao": "remover"})
    assert baixar(navegador, f"/empresas/{empresa_id}/logo").status_code == 404
    assert _arquivos(pasta_uploads) == []


def test_logo_que_nao_e_imagem_e_recusado(app_real, navegador, novo_usuario, criados, pasta_uploads):
    from models import Empresa

    _, email, senha = novo_usuario("Administrador")
    navegador.entrar(email, senha)
    empresa_id = _criar(app_real, criados, Empresa, nome=f"Parceira {uuid.uuid4().hex[:6]}")
    falso = (io.BytesIO(b"<svg onload=alert(1)>"), "logo.png")
    navegador.post(f"/empresas/{empresa_id}/logo/enviar", {"logo": falso}, content_type="multipart/form-data")
    assert baixar(navegador, f"/empresas/{empresa_id}/logo").status_code == 404 and _arquivos(pasta_uploads) == []


def test_aluno_nao_troca_logo(app_real, navegador, novo_usuario, criados, pasta_uploads):
    from models import Empresa

    _, email, senha = novo_usuario("Aluno")
    navegador.entrar(email, senha)
    empresa_id = _criar(app_real, criados, Empresa, nome=f"Parceira {uuid.uuid4().hex[:6]}")
    navegador.post(f"/empresas/{empresa_id}/logo/enviar", {"logo": (io.BytesIO(PNG), "logo.png")}, content_type="multipart/form-data")
    assert _arquivos(pasta_uploads) == []


# ------------------------------------------------------------------ gravação da reunião
@pytest.fixture
def reuniao(app_real, criados, novo_usuario):
    from models import ReuniaoInstitucional

    admin_id, email, senha = novo_usuario("Administrador")
    rid = _criar(
        app_real, criados, ReuniaoInstitucional, titulo="Reunião IT", data_hora=datetime.now() - timedelta(hours=1), criado_por_id=admin_id
    )
    return rid, email, senha


def test_gravacao_envia_toca_por_faixa_e_exclui(navegador, reuniao, pasta_uploads):
    rid, email, senha = reuniao
    navegador.entrar(email, senha)
    video = bytes(range(256)) * 40
    navegador.post(f"/reunioes/{rid}/gravacao", {"arquivo": (io.BytesIO(video), "Reunião 1.mp4")}, content_type="multipart/form-data")
    assert [a.split("/")[0] for a in _arquivos(pasta_uploads)] == ["reunioes"]

    inteiro = baixar(navegador, f"/reunioes/{rid}/gravacao")
    assert inteiro.status_code == 200 and inteiro.data == video and inteiro.mimetype == "video/mp4"
    parte = baixar(navegador, f"/reunioes/{rid}/gravacao", headers={"Range": "bytes=10-19"})
    assert parte.status_code == 206 and parte.data == video[10:20]
    assert parte.headers["Content-Range"] == f"bytes 10-19/{len(video)}"

    navegador.post(f"/reunioes/{rid}/gravacao", {"acao": "excluir"})
    assert baixar(navegador, f"/reunioes/{rid}/gravacao").status_code == 404 and _arquivos(pasta_uploads) == []


def test_gravacao_recusa_formato_e_arquivo_vazio(navegador, reuniao, pasta_uploads):
    rid, email, senha = reuniao
    navegador.entrar(email, senha)
    navegador.post(f"/reunioes/{rid}/gravacao", {"arquivo": (io.BytesIO(b"MZ"), "virus.exe")}, content_type="multipart/form-data")
    navegador.post(f"/reunioes/{rid}/gravacao", {"arquivo": (io.BytesIO(b""), "vazio.mp4")}, content_type="multipart/form-data")
    assert _arquivos(pasta_uploads) == []


# ------------------------------------------------------------------ anexos das tarefas do projeto
@pytest.fixture
def tarefa_do_grupo(app_real, criados, novo_usuario):
    from models import Grupo, Projeto, Tarefa, Usuario

    aluno_id, email_aluno, senha_aluno = novo_usuario("Aluno")
    outro_id, email_outro, senha_outro = novo_usuario("Aluno")
    with app_real.app.app_context():
        db = app_real.db
        grupo = Grupo(nome=f"Grupo IT {uuid.uuid4().hex[:6]}")
        grupo.membros.append(db.session.get(Usuario, aluno_id))
        db.session.add(grupo)
        db.session.commit()
        criados.append((Grupo, grupo.id))
        projeto = Projeto(nome="Projeto IT", grupo_id=grupo.id)
        db.session.add(projeto)
        db.session.commit()
        criados.append((Projeto, projeto.id))
        tarefa = Tarefa(projeto_id=projeto.id, descricao="Tarefa IT")
        db.session.add(tarefa)
        db.session.commit()
        criados.append((Tarefa, tarefa.id))
        return tarefa.id, (email_aluno, senha_aluno), (email_outro, senha_outro)


def _enviar_anexo(navegador, tarefa_id, nome, conteudo, excluir=()):
    dados = {
        "tarefa_id": str(tarefa_id),
        "descricao": "Tarefa IT",
        "status": "Em andamento",
        "percentual_conclusao": "10",
        "arquivos_anexos": (io.BytesIO(conteudo), nome),
    }
    if excluir:
        dados["materiais_excluir"] = list(excluir)
    return navegador.post("/projetos/atualizar_tarefa", dados, content_type="multipart/form-data")


def _anexos(app_real, tarefa_id):
    from models import Tarefa

    with app_real.app.app_context():
        return (app_real.db.session.get(Tarefa, tarefa_id).arquivo_anexo or "").split("|")


def test_membro_do_grupo_anexa_e_abre_o_proprio_anexo(app_real, navegador, tarefa_do_grupo, pasta_uploads):
    tarefa_id, (email, senha), _ = tarefa_do_grupo
    navegador.entrar(email, senha)
    _enviar_anexo(navegador, tarefa_id, "relatorio.pdf", b"%PDF-1.4 a")
    (anexo,) = _anexos(app_real, tarefa_id)
    assert anexo.startswith("Aluno::")
    nome = anexo.split("::", 1)[1]
    r = baixar(navegador, f"/uploads/{nome}")
    assert r.status_code == 200 and r.data == b"%PDF-1.4 a"


def test_quem_nao_e_do_grupo_nao_abre_o_anexo(app_real, navegador, novo_navegador, tarefa_do_grupo, pasta_uploads):
    tarefa_id, (email, senha), (email_outro, senha_outro) = tarefa_do_grupo
    navegador.entrar(email, senha)
    _enviar_anexo(navegador, tarefa_id, "relatorio.pdf", b"%PDF-1.4 a")
    nome = _anexos(app_real, tarefa_id)[0].split("::", 1)[1]
    outro = novo_navegador()
    outro.entrar(email_outro, senha_outro)
    r = baixar(outro, f"/uploads/{nome}")
    assert r.status_code == 302 and b"%PDF" not in r.data


def test_anexos_com_o_mesmo_nome_nao_se_sobrescrevem(app_real, navegador, tarefa_do_grupo, novo_usuario, criados, pasta_uploads):
    tarefa_id, (email, senha), _ = tarefa_do_grupo
    navegador.entrar(email, senha)
    _enviar_anexo(navegador, tarefa_id, "relatorio.pdf", b"%PDF primeiro")
    _enviar_anexo(navegador, tarefa_id, "relatorio.pdf", b"%PDF segundo")
    nomes = [a.split("::", 1)[1] for a in _anexos(app_real, tarefa_id)]
    assert len(nomes) == 2 and len(set(nomes)) == 2
    assert {baixar(navegador, f"/uploads/{n}").data for n in nomes} == {b"%PDF primeiro", b"%PDF segundo"}


def test_excluir_anexo_apaga_o_arquivo(app_real, navegador, tarefa_do_grupo, pasta_uploads):
    tarefa_id, (email, senha), _ = tarefa_do_grupo
    navegador.entrar(email, senha)
    _enviar_anexo(navegador, tarefa_id, "a.pdf", b"%PDF a")
    (anexo,) = _anexos(app_real, tarefa_id)
    _enviar_anexo(navegador, tarefa_id, "b.pdf", b"%PDF b", excluir=[anexo])
    restantes = _anexos(app_real, tarefa_id)
    assert len(restantes) == 1 and restantes[0].endswith("b.pdf")
    assert len(_arquivos(pasta_uploads)) == 1


@pytest.mark.parametrize("nome", ["../app.py", "..%2Fapp.py", "%2e%2e%2fapp.py"])
def test_uploads_nao_sai_da_pasta(navegador, novo_usuario, nome, pasta_uploads):
    _, email, senha = novo_usuario("Administrador")
    navegador.entrar(email, senha)
    assert baixar(navegador, f"/uploads/{nome}").status_code == 404
