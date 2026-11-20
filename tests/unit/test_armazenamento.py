"""armazenamento: chaves seguras, faixas (Range) e o backend S3 com um cliente falso em memória."""

import io

import pytest
from flask import Flask

import armazenamento as arm


@pytest.mark.parametrize("chave", ["relatorio.pdf", "tcc/entrega_3_ab12.pdf", "aulas/video 7 (final).mp4", "acervo/Ação_ç.pdf"])
def test_chaves_validas(chave):
    assert arm.validar_chave(chave) == chave


@pytest.mark.parametrize("chave", ["", "../segredo", "tcc/../../etc/passwd", "/etc/passwd", "a\\b", "tcc//x", "./x", "x/./y", None])
def test_chaves_perigosas_sao_recusadas(chave):
    with pytest.raises(arm.ChaveInvalida):
        arm.validar_chave(chave)


@pytest.mark.parametrize(
    "cabecalho, tamanho, esperado",
    [
        ("bytes=0-99", 1000, (0, 99)),
        ("bytes=900-", 1000, (900, 999)),
        ("bytes=-100", 1000, (900, 999)),
        ("bytes=0-5000", 1000, (0, 999)),
        ("bytes=1000-", 1000, None),
        ("bytes=50-10", 1000, None),
        ("bytes=-", 1000, None),
        ("items=0-1", 1000, None),
        (None, 1000, None),
        ("bytes=0-1", 0, None),
    ],
)
def test_faixa(cabecalho, tamanho, esperado):
    assert arm._faixa(cabecalho, tamanho) == esperado


def test_nome_do_download_com_acento_vai_codificado():
    cab = arm._cabecalho_download("aulas/Introdução.pdf", True)
    assert cab.startswith("attachment") and "filename*=UTF-8''Introdu%C3%A7%C3%A3o.pdf" in cab


# ------------------------------------------------------------------ S3 com cliente falso
class ErroCliente(Exception):
    def __init__(self, codigo):
        super().__init__(codigo)
        self.response = {"Error": {"Code": codigo}}


class CorpoFalso(io.BytesIO):
    pass


class ClienteS3Falso:
    def __init__(self):
        self.objetos = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objetos[(Bucket, Key)] = (bytes(Body), ContentType)

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objetos:
            raise ErroCliente("404")
        return {"ContentLength": len(self.objetos[(Bucket, Key)][0])}

    def get_object(self, Bucket, Key, Range=None):
        dados, tipo = self.objetos[(Bucket, Key)]
        if Range:
            inicio, fim = (int(x) for x in Range.split("=")[1].split("-"))
            dados = dados[inicio : fim + 1]
        return {"Body": CorpoFalso(dados), "ContentType": tipo}

    def delete_object(self, Bucket, Key):
        self.objetos.pop((Bucket, Key), None)

    def copy_object(self, Bucket, Key, CopySource):
        self.objetos[(Bucket, Key)] = self.objetos[(CopySource["Bucket"], CopySource["Key"])]

    def head_bucket(self, Bucket):
        if Bucket != "mentoria":
            raise ErroCliente("NoSuchBucket")


@pytest.fixture
def s3():
    return arm.S3("mentoria", prefixo="uploads", cliente=ClienteS3Falso())


def test_s3_salva_le_copia_e_apaga_com_prefixo(s3):
    assert s3.salvar("tcc/a.pdf", io.BytesIO(b"%PDF-1")) == 6
    assert ("mentoria", "uploads/tcc/a.pdf") in s3.cliente.objetos
    assert s3.cliente.objetos[("mentoria", "uploads/tcc/a.pdf")][1] == "application/pdf"
    assert s3.existe("tcc/a.pdf") and s3.ler("tcc/a.pdf") == b"%PDF-1" and s3.tamanho("tcc/a.pdf") == 6
    s3.copiar("tcc/a.pdf", "acervo/b.pdf")
    assert s3.ler("acervo/b.pdf") == b"%PDF-1"
    assert s3.apagar("tcc/a.pdf") and not s3.existe("tcc/a.pdf")


def test_s3_nao_aceita_chave_perigosa(s3):
    with pytest.raises(arm.ChaveInvalida):
        s3.salvar("../fora.txt", b"x")
    assert s3.existe("../fora.txt") is False


def test_s3_erro_que_nao_e_404_sobe(s3, monkeypatch):
    monkeypatch.setattr(s3.cliente, "head_object", lambda **k: (_ for _ in ()).throw(ErroCliente("AccessDenied")))
    with pytest.raises(ErroCliente):
        s3.existe("x.pdf")


def test_s3_resposta_inteira_e_parcial(s3):
    s3.salvar("aulas/v.mp4", b"0123456789")
    app = Flask(__name__)
    with app.test_request_context("/"):
        r = s3.resposta("aulas/v.mp4")
        assert r.status_code == 200 and b"".join(r.response) == b"0123456789" and r.headers["Accept-Ranges"] == "bytes"
        assert r.headers["Content-Disposition"].startswith("inline")
    with app.test_request_context("/", headers={"Range": "bytes=2-5"}):
        r = s3.resposta("aulas/v.mp4", como_anexo=True, nome_download="Aula 1.mp4")
        assert r.status_code == 206 and b"".join(r.response) == b"2345"
        assert r.headers["Content-Range"] == "bytes 2-5/10" and r.headers["Content-Length"] == "4"
        assert r.headers["Content-Disposition"].startswith("attachment")


def test_s3_prontidao(s3):
    s3.verificar()
    with pytest.raises(ErroCliente):
        arm.S3("outro", cliente=ClienteS3Falso()).verificar()


def test_escolha_pelo_ambiente(monkeypatch):
    arm.esquecer()
    monkeypatch.setenv("ARMAZENAMENTO", "ftp")
    with pytest.raises(ValueError, match="ARMAZENAMENTO"):
        arm.atual()
    arm.esquecer()
    monkeypatch.setenv("ARMAZENAMENTO", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(ValueError, match="S3_BUCKET"):
        arm.atual()
    arm.esquecer()
