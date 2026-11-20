# -*- coding: utf-8 -*-
"""
ARMAZENAMENTO DOS ARQUIVOS ENVIADOS (aulas, anexos, gravações, TCC, acervo, logos, base de conhecimento)
=======================================================================================================
O resto da plataforma só conhece CHAVES relativas, iguais às que já estão no banco (ex.: 'tcc/entrega_3_ab12.pdf',
'aulas/video_7_x.mp4', 'relatorio.pdf'). Onde os bytes ficam depende do ambiente:

- ARMAZENAMENTO=local (padrão): pasta uploads/ da plataforma (PythonAnywhere, servidor, desenvolvimento).
- ARMAZENAMENTO=s3: um bucket compatível com S3 (AWS S3 na nuvem, MinIO no docker-compose). O contêiner fica sem
  estado: qualquer réplica serve qualquer arquivo e nada se perde num reinício.
  Variáveis: S3_BUCKET, S3_PREFIXO (opcional), S3_REGIAO, S3_ENDPOINT (só MinIO/compatível) e as credenciais pelo
  caminho padrão da AWS (papel IAM da tarefa/instância; AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY só fora da AWS).

Download: o arquivo passa pelo próprio app (mesma origem: a política de segurança CSP e a checagem de permissão
continuam valendo), com suporte a Range (vídeos e gravações começam a tocar sem baixar tudo).
Chaves nunca saem da pasta/prefixo: '..', caminhos absolutos e barras invertidas são recusados.
"""

import mimetypes
import os
import re
import shutil

RAIZ_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
_CHAVE_VALIDA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/ ()À-ÿ]{0,250}$")
BLOCO = 1024 * 1024  # 1 MB por pedaço ao transmitir


class ChaveInvalida(ValueError):
    pass


def validar_chave(chave):
    """Chave relativa e segura (sem '..', sem absoluto, sem barra invertida, sem pastas vazias)."""
    chave = (chave or "").strip()
    partes = chave.split("/")
    if not _CHAVE_VALIDA.match(chave) or any(p in ("", ".", "..") for p in partes) or "\\" in chave:
        raise ChaveInvalida(chave)
    return chave


def _ler_tudo(origem):
    """origem: bytes, objeto com .read() (FileStorage do Flask, arquivo aberto) ou caminho de arquivo local."""
    if isinstance(origem, (bytes, bytearray)):
        return bytes(origem)
    if hasattr(origem, "read"):
        if hasattr(origem, "seek"):
            origem.seek(0)
        return origem.read()
    with open(origem, "rb") as f:
        return f.read()


def _faixa(cabecalho_range, tamanho):
    """'bytes=0-99' → (inicio, fim) inclusivo; None quando não há faixa válida (resposta inteira)."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (cabecalho_range or "").strip())
    if not m or tamanho == 0 or (not m.group(1) and not m.group(2)):
        return None
    if m.group(1):
        inicio = int(m.group(1))
        fim = min(int(m.group(2)), tamanho - 1) if m.group(2) else tamanho - 1
    else:  # sufixo: os últimos N bytes
        inicio, fim = max(0, tamanho - int(m.group(2))), tamanho - 1
    return (inicio, fim) if inicio <= fim < tamanho else None


def _cabecalho_download(nome, como_anexo):
    from werkzeug.http import dump_options_header

    nome = os.path.basename(nome or "arquivo")
    try:
        nome.encode("ascii")
        opcoes = {"filename": nome}
    except UnicodeEncodeError:
        from urllib.parse import quote

        opcoes = {"filename": nome.encode("ascii", "ignore").decode() or "arquivo", "filename*": "UTF-8''" + quote(nome)}
    return dump_options_header("attachment" if como_anexo else "inline", opcoes)


class DiscoLocal:
    nome = "local"

    def __init__(self, raiz=RAIZ_PADRAO):
        self.raiz = os.path.realpath(raiz)

    def caminho(self, chave):
        caminho = os.path.realpath(os.path.join(self.raiz, validar_chave(chave)))
        if not caminho.startswith(self.raiz + os.sep):
            raise ChaveInvalida(chave)
        return caminho

    def salvar(self, chave, origem):
        caminho = self.caminho(chave)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        if hasattr(origem, "save") and not isinstance(origem, (bytes, bytearray)):
            origem.save(caminho)  # FileStorage: grava em pedaços, sem carregar tudo na memória
        else:
            with open(caminho, "wb") as f:
                f.write(_ler_tudo(origem))
        return os.path.getsize(caminho)

    def existe(self, chave):
        try:
            return os.path.isfile(self.caminho(chave))
        except ChaveInvalida:
            return False

    def tamanho(self, chave):
        return os.path.getsize(self.caminho(chave))

    def ler(self, chave):
        with open(self.caminho(chave), "rb") as f:
            return f.read()

    def apagar(self, chave):
        try:
            os.remove(self.caminho(chave))
            return True
        except (OSError, ChaveInvalida):
            return False

    def copiar(self, origem, destino):
        alvo = self.caminho(destino)
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        shutil.copyfile(self.caminho(origem), alvo)

    def resposta(self, chave, como_anexo=False, nome_download=None, mimetype=None, max_age=None):
        from flask import send_file

        caminho = self.caminho(chave)
        kwargs = {"as_attachment": como_anexo, "download_name": nome_download or os.path.basename(caminho), "conditional": True}
        if mimetype:
            kwargs["mimetype"] = mimetype
        if max_age is not None:
            kwargs["max_age"] = max_age
        return send_file(caminho, **kwargs)


class S3:
    nome = "s3"

    def __init__(self, bucket, prefixo="", cliente=None, regiao=None, endpoint=None):
        if not bucket:
            raise ValueError("Defina S3_BUCKET para ARMAZENAMENTO=s3.")
        self.bucket = bucket
        self.prefixo = (prefixo or "").strip("/")
        if cliente is None:
            import boto3
            from botocore.config import Config

            cliente = boto3.client(
                "s3",
                region_name=regiao or None,
                endpoint_url=endpoint or None,
                config=Config(
                    retries={"max_attempts": 5, "mode": "standard"},
                    connect_timeout=5,
                    read_timeout=60,
                    max_pool_connections=20,
                    s3={"addressing_style": "path" if endpoint else "auto"},
                ),
            )
        self.cliente = cliente

    def _k(self, chave):
        chave = validar_chave(chave)
        return f"{self.prefixo}/{chave}" if self.prefixo else chave

    def salvar(self, chave, origem):
        dados = _ler_tudo(origem)
        tipo = mimetypes.guess_type(chave)[0] or "application/octet-stream"
        self.cliente.put_object(Bucket=self.bucket, Key=self._k(chave), Body=dados, ContentType=tipo)
        return len(dados)

    def _nao_existe(self, erro):
        codigo = getattr(erro, "response", {}).get("Error", {}).get("Code", "")
        return codigo in ("404", "NoSuchKey", "NotFound")

    def existe(self, chave):
        try:
            self.cliente.head_object(Bucket=self.bucket, Key=self._k(chave))
            return True
        except ChaveInvalida:
            return False
        except Exception as erro:
            if self._nao_existe(erro):
                return False
            raise

    def tamanho(self, chave):
        return int(self.cliente.head_object(Bucket=self.bucket, Key=self._k(chave))["ContentLength"])

    def ler(self, chave):
        return self.cliente.get_object(Bucket=self.bucket, Key=self._k(chave))["Body"].read()

    def apagar(self, chave):
        try:
            self.cliente.delete_object(Bucket=self.bucket, Key=self._k(chave))
            return True
        except ChaveInvalida:
            return False

    def copiar(self, origem, destino):
        self.cliente.copy_object(Bucket=self.bucket, Key=self._k(destino), CopySource={"Bucket": self.bucket, "Key": self._k(origem)})

    def resposta(self, chave, como_anexo=False, nome_download=None, mimetype=None, max_age=None):
        from flask import Response, request

        tamanho = self.tamanho(chave)
        faixa = _faixa(request.headers.get("Range"), tamanho)
        pedido = {"Bucket": self.bucket, "Key": self._k(chave)}
        if faixa:
            pedido["Range"] = f"bytes={faixa[0]}-{faixa[1]}"
        objeto = self.cliente.get_object(**pedido)
        corpo = objeto["Body"]

        def pedacos():
            try:
                while True:
                    bloco = corpo.read(BLOCO)
                    if not bloco:
                        break
                    yield bloco
            finally:
                corpo.close()

        tipo = mimetype or objeto.get("ContentType") or mimetypes.guess_type(chave)[0] or "application/octet-stream"
        resposta = Response(pedacos(), status=206 if faixa else 200, mimetype=tipo, direct_passthrough=True)
        resposta.headers["Accept-Ranges"] = "bytes"
        resposta.headers["Content-Length"] = str((faixa[1] - faixa[0] + 1) if faixa else tamanho)
        if faixa:
            resposta.headers["Content-Range"] = f"bytes {faixa[0]}-{faixa[1]}/{tamanho}"
        resposta.headers["Content-Disposition"] = _cabecalho_download(nome_download or chave, como_anexo)
        if max_age is not None:
            resposta.headers["Cache-Control"] = f"private, max-age={int(max_age)}"
        return resposta

    def verificar(self):
        """Prontidão: o bucket existe e as credenciais valem."""
        self.cliente.head_bucket(Bucket=self.bucket)


_ATUAL = {}


def atual():
    """Armazenamento escolhido pelo ambiente (um por processo)."""
    escolha = (os.environ.get("ARMAZENAMENTO") or "local").strip().lower()
    if _ATUAL.get("escolha") != escolha:
        if escolha == "s3":
            backend = S3(
                os.environ.get("S3_BUCKET", ""),
                os.environ.get("S3_PREFIXO", ""),
                regiao=os.environ.get("S3_REGIAO"),
                endpoint=os.environ.get("S3_ENDPOINT"),
            )
        elif escolha == "local":
            backend = DiscoLocal(os.environ.get("PASTA_UPLOADS") or RAIZ_PADRAO)
        else:
            raise ValueError(f"ARMAZENAMENTO inválido: {escolha} (use local ou s3).")
        _ATUAL.update(escolha=escolha, backend=backend)
    return _ATUAL["backend"]


def esquecer():
    """Para os testes: a próxima chamada de atual() relê o ambiente."""
    _ATUAL.clear()
