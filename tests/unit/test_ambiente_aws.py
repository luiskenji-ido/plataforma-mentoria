"""ambiente.aws_servico: reconhece o serviço da AWS pelas marcas do próprio ambiente, sem rede."""

import pytest

import ambiente


@pytest.fixture
def linux_sem_arquivos(monkeypatch):
    monkeypatch.setattr(ambiente.sys, "platform", "linux")
    monkeypatch.setattr(ambiente.os.path, "isdir", lambda _p: False)
    arquivos = {}
    monkeypatch.setattr(ambiente, "_ler_arquivo", lambda caminho: arquivos.get(caminho, ""))
    return arquivos


@pytest.mark.parametrize(
    "variavel, valor, esperado",
    [
        ("AWS_LAMBDA_FUNCTION_NAME", "f", "lambda"),
        ("AWS_EXECUTION_ENV", "AWS_Lambda_python3.12", "lambda"),
        ("ECS_CONTAINER_METADATA_URI_V4", "http://169.254.170.2/v4/x", "ecs"),
        ("AWS_EXECUTION_ENV", "AWS_ECS_FARGATE", "ecs"),
        ("AWS_APP_RUNNER_SERVICE_ID", "abc", "app_runner"),
        ("AWS_EXECUTION_ENV", "AWS_ElasticBeanstalk_Python", "elastic_beanstalk"),
    ],
)
def test_reconhece_pelas_variaveis(linux_sem_arquivos, monkeypatch, variavel, valor, esperado):
    monkeypatch.setenv(variavel, valor)
    assert ambiente.aws_servico() == esperado


def test_reconhece_ec2_pelo_fabricante(linux_sem_arquivos):
    linux_sem_arquivos["/sys/devices/virtual/dmi/id/sys_vendor"] = "Amazon EC2"
    assert ambiente.aws_servico() == "ec2"


def test_reconhece_ec2_pelo_hipervisor(linux_sem_arquivos):
    linux_sem_arquivos["/sys/hypervisor/uuid"] = "EC2abcd-1234"
    assert ambiente.aws_servico() == "ec2"


def test_fora_da_aws(linux_sem_arquivos):
    linux_sem_arquivos["/sys/devices/virtual/dmi/id/sys_vendor"] = "QEMU"
    assert ambiente.aws_servico() is None


def test_windows_so_pelas_variaveis(monkeypatch):
    monkeypatch.setattr(ambiente.sys, "platform", "win32")
    assert ambiente.aws_servico() is None
