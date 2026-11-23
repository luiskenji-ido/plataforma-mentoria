"""encerramento: o processo principal do gunicorn só sai quando os clientes terminaram de receber as respostas."""

import encerramento as e

CABECALHO = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"
ESTABLISHED, FIN_WAIT2, TIME_WAIT, LISTEN = "01", "05", "06", "0A"


def linha(porta_local, estado, tx=0, porta_remota=0xC350):
    return f"   0: 0100007F:{porta_local:04X} 0100007F:{porta_remota:04X} {estado} {tx:08X}:00000000 00:00000000 00000000 0 0 1"


def test_conta_so_as_conexoes_abertas_da_porta_do_app():
    linhas = [
        CABECALHO,
        linha(8080, ESTABLISHED, tx=4_000_000),
        linha(8080, FIN_WAIT2),  # servidor já fechou, o cliente ainda lê o que está no buffer dele
        linha(8080, TIME_WAIT),  # cliente terminou
        linha(8080, LISTEN),
        linha(3306, ESTABLISHED, tx=10),  # outra porta (banco)
    ]
    assert e.conexoes_abertas(linhas, 8080) == (2, 4_000_000)


def test_linhas_estranhas_nao_contam():
    assert e.conexoes_abertas(["", "lixo", "a b c d e"], 8080) == (0, 0)


def test_ipv6_tambem_conta():
    ipv6 = "   0: 00000000000000000000000001000000:1F90 00000000000000000000000001000000:C350 04 00000400:00000000 00:0 0 0 0 1"
    assert e.conexoes_abertas([ipv6], 8080) == (1, 1024)


class Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.agora += segundos


def test_espera_ate_o_cliente_fechar():
    leituras = iter([[linha(8080, ESTABLISHED, tx=3_500_000)], [linha(8080, FIN_WAIT2)], [linha(8080, TIME_WAIT)]])
    relogio = Relogio()
    assert e.esperar_conexoes(8080, 8, ler=lambda: next(leituras), relogio=relogio, dormir=relogio.dormir) == 0
    assert relogio.agora < 1


def test_desiste_no_prazo_e_informa_quantas_ficaram():
    relogio = Relogio()
    ficaram = e.esperar_conexoes(8080, 2, ler=lambda: [linha(8080, FIN_WAIT2)], relogio=relogio, dormir=relogio.dormir)
    assert ficaram == 1 and 2 <= relogio.agora < 2.2


def test_sem_conexao_aberta_nao_espera():
    relogio = Relogio()
    assert e.esperar_conexoes(8080, 8, ler=lambda: [linha(8080, LISTEN)], relogio=relogio, dormir=relogio.dormir) == 0
    assert relogio.agora == 0
