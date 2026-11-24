"""Dados sintéticos identificados para exercitar falhas e paginação."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from painel_indicadores.cliente_api import ClienteAPI, ErroDeConsulta
from painel_indicadores.contratos import FiltrosObservacoes, Observacao

INICIO = date(2026, 1, 1)
FIM = date(2026, 3, 1)


def pagina(dados=None, cursor=None, versao=1, **meta):
    return {
        "data": dados
        if dados is not None
        else [{"data": "2026-01-01", "valor": "0.000000"}],
        "pagina": {
            "limite": 1000,
            "tem_mais": cursor is not None,
            "proximo_cursor": cursor,
        },
        "meta": {
            "camada": "core",
            "versao_dados": versao,
            "versao_core": versao,
            "versao_gold": 1,
            "codigo": 433,
            "unidade": "% no mes",
            "de": str(INICIO),
            "ate": str(FIM),
            **meta,
        },
    }


def executar(respostas, **opcoes):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        resposta = respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return (
            resposta
            if isinstance(resposta, httpx.Response)
            else httpx.Response(200, json=resposta)
        )

    http = httpx.Client(base_url="http://api", transport=httpx.MockTransport(responder))
    return http, ClienteAPI(http, **opcoes), pedidos


def test_percorre_paginas_preservando_filtros_e_decimal():
    http, cliente, pedidos = executar(
        [
            pagina(cursor="opaco"),
            pagina([{"data": "2026-02-01", "valor": "-0.120000"}], versao_gold=9),
        ]
    )
    with http:
        conjunto = cliente.buscar_observacoes(433, INICIO, FIM)
    assert conjunto.consulta_completa
    assert conjunto.observacoes[-1].valor == Decimal("-0.12")
    assert pedidos[1].url.params["cursor"] == "opaco"
    for pedido in pedidos:
        assert pedido.url.params["de"] == str(INICIO)
        assert pedido.url.params["ate"] == str(FIM)
        assert pedido.url.params["limite"] == "1000"


@pytest.mark.parametrize("primeira", [httpx.Response(409), pagina(versao=2)])
def test_reinicia_uma_vez_sem_concatenar_geracoes(primeira):
    respostas = [
        pagina(cursor="velho"),
        primeira,
        pagina([{"data": "2026-02-01", "valor": "1.000000"}], versao=3),
    ]
    http, cliente, pedidos = executar(respostas)
    with http:
        resultado = cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(resultado.observacoes) == 1
    assert resultado.meta.versao_core == 3
    assert "cursor" not in pedidos[-1].url.params


def test_segundo_conflito_interrompe():
    http, cliente, pedidos = executar([httpx.Response(409), httpx.Response(409)])
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(pedidos) == 2


@pytest.mark.parametrize(
    "respostas",
    [
        [
            pagina(cursor="igual"),
            pagina([{"data": "2026-02-01", "valor": "1.000000"}], cursor="igual"),
        ],
        [pagina(cursor="a"), pagina()],
        [pagina(codigo=1)],
        [pagina(de="2026-01-02")],
        [pagina([{"data": "2025-12-31", "valor": "1.000000"}])],
        [
            pagina(
                [
                    {"data": "2026-02-01", "valor": "1.000000"},
                    {"data": "2026-01-01", "valor": "1.000000"},
                ]
            )
        ],
        [httpx.Response(200, text="segredo")],
    ],
)
def test_recusa_contrato_incoerente(respostas):
    http, cliente, _ = executar(list(respostas))
    with http, pytest.raises(ErroDeConsulta) as erro:
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert "segredo" not in str(erro.value)


def test_limite_sinaliza_incompletude():
    http, cliente, _ = executar([pagina(cursor="mais")], limite_paginas=1)
    with http:
        resultado = cliente.buscar_observacoes(433, INICIO, FIM)
    assert not resultado.consulta_completa
    assert resultado.motivo


@pytest.mark.parametrize("status", [404, 422, 429])
def test_nao_repete_erro_sem_espera_aceitavel(status):
    http, cliente, pedidos = executar(
        [httpx.Response(status, headers={"Retry-After": "120"})]
    )
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    "falha",
    [
        httpx.Response(503),
        httpx.ReadTimeout("segredo"),
        httpx.Response(429, headers={"Retry-After": "0"}),
    ],
)
def test_repete_transitorio_uma_vez(falha):
    http, cliente, pedidos = executar([falha, pagina()])
    with http:
        assert cliente.buscar_observacoes(433, INICIO, FIM).consulta_completa
    assert len(pedidos) == 2


def test_prazo_inclui_resposta_e_impede_sucesso_tardio():
    instantes = iter([0, 0, 0, 31, 31, 31])
    http, cliente, pedidos = executar([pagina()], relogio=lambda: next(instantes, 31))
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(pedidos) <= 1


@pytest.mark.parametrize("valor", [None, 1.5, "NaN", "Infinity", "1,23", ""])
def test_decimal_invalido(valor):
    with pytest.raises(ValidationError):
        Observacao(data=INICIO, valor=valor)


@pytest.mark.parametrize(
    "de,ate", [(FIM, INICIO), (date(2019, 1, 1), FIM), (INICIO, date(2099, 1, 1))]
)
def test_filtros_invalidos(de, ate):
    with pytest.raises(ValidationError):
        FiltrosObservacoes(codigo=433, de=de, ate=ate)


def test_repeticao_transitoria_tem_limite():
    http, cliente, pedidos = executar([httpx.Response(503), httpx.Response(503)])
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(pedidos) == 2


def test_unidade_nao_pode_mudar_entre_paginas():
    http, cliente, _ = executar(
        [
            pagina(cursor="a"),
            pagina([{"data": "2026-02-01", "valor": "1.000000"}], unidade="R$/US$"),
        ]
    )
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)


def test_limite_de_registros_e_independente_de_paginas():
    http, cliente, pedidos = executar(
        [
            pagina(
                [
                    {"data": "2026-01-01", "valor": "1.000000"},
                    {"data": "2026-02-01", "valor": "2.000000"},
                ]
            ),
        ],
        limite_registros=1,
    )
    with http:
        conjunto = cliente.buscar_observacoes(433, INICIO, FIM)
    assert not conjunto.consulta_completa
    assert len(conjunto.observacoes) == 1
    assert len(pedidos) == 1


def test_pagina_final_no_limite_e_completa():
    http, cliente, _ = executar([pagina()], limite_paginas=1, limite_registros=1)
    with http:
        assert cliente.buscar_observacoes(433, INICIO, FIM).consulta_completa


def test_cursor_indicado_com_pagina_vazia_e_erro():
    http, cliente, _ = executar([pagina([], cursor="sem-progresso")])
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)


def test_data_de_filtro_exige_formato_iso():
    with pytest.raises(ValidationError):
        FiltrosObservacoes(codigo=433, de="2026-01-01T00:00:00", ate=FIM)


@pytest.mark.parametrize(
    "valor",
    ["1e1000000", "1_000.000000", " 1.000000 ", "99999999999999999999999999999.000000"],
)
def test_recusa_representacao_decimal_fora_do_contrato(valor):
    with pytest.raises(ValidationError):
        Observacao(data=INICIO, valor=valor)


def test_stream_lento_e_interrompido_antes_de_baixar_tudo():
    instante = [0.0]
    lidos = []
    fechado = []

    class CorpoLento(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                instante[0] += 1
                lidos.append(1)
                yield b" "

        def close(self):
            fechado.append(True)

    http, cliente, _ = executar(
        [
            httpx.Response(200, stream=CorpoLento()),
        ],
        prazo_consulta=3,
        relogio=lambda: instante[0],
    )
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_observacoes(433, INICIO, FIM)
    assert len(lidos) <= 3
    assert fechado
