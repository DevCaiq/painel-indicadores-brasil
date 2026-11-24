"""Amostras sintéticas para a exportação CSV, sem serviços externos."""

import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO

import pytest

from painel_indicadores.exportacao import CelulaCSV, gerar_csv


def ler_csv(conteudo: bytes) -> list[list[str]]:
    return list(csv.reader(StringIO(conteudo.decode("utf-8-sig")), delimiter=";"))


def test_codificacao_delimitador_e_escape() -> None:
    conteudo = gerar_csv(("descrição", "fonte"), [("a;b", 'aspas " e\nlinha')])

    assert conteudo.startswith(b"\xef\xbb\xbf")
    assert conteudo.decode("utf-8-sig") == (
        'descrição;fonte\r\n"a;b";"aspas "" e\nlinha"\r\n'
    )


def test_preserva_precisao_ausencia_booleanos_e_datas() -> None:
    valores: tuple[CelulaCSV, ...] = (
        Decimal("-12345678901234567890.123456789"),
        Decimal("1E-8"),
        Decimal("0.00"),
        None,
        0,
        -3,
        True,
        False,
        date(2026, 11, 23),
        datetime(2026, 11, 23, 12, 34, 56, tzinfo=timezone(timedelta(hours=-3))),
        datetime(2026, 11, 23, 12, 34, 56),
    )

    resultado = ler_csv(
        gerar_csv(tuple(str(i) for i in range(len(valores))), [valores])
    )

    assert resultado[1] == [
        "-12345678901234567890.123456789",
        "0.00000001",
        "0.00",
        "",
        "0",
        "-3",
        "sim",
        "nao",
        "2026-11-23",
        "2026-11-23T12:34:56-03:00",
        "2026-11-23T12:34:56",
    ]


@pytest.mark.parametrize(
    "texto",
    [
        "=1+1",
        "+1",
        "-1",
        "@SOMA(A1)",
        "\ttexto",
        "\rtexto",
        "\ntexto",
        "  =1",
        " \ttexto",
        "\u2003+1",
    ],
)
def test_neutraliza_formulas_em_textos_e_cabecalhos(texto: str) -> None:
    assert ler_csv(gerar_csv((texto,), [(texto,)])) == [["'" + texto], ["'" + texto]]


def test_preserva_texto_comum_e_consumidor_iteravel() -> None:
    linhas = ((texto,) for texto in ("São Paulo", "  texto", "", "1-2", "'original"))
    assert ler_csv(gerar_csv(("nome",), linhas))[1:] == [
        ["São Paulo"],
        ["  texto"],
        [""],
        ["1-2"],
        ["'original"],
    ]


@pytest.mark.parametrize("linha", [(), ("um", "dois")])
def test_rejeita_quantidade_incoerente_de_celulas(linha: tuple[CelulaCSV, ...]) -> None:
    with pytest.raises(ValueError, match="colunas"):
        gerar_csv(("unica",), [linha])


def test_sem_linhas_mantem_cabecalho() -> None:
    assert ler_csv(gerar_csv(("indicador", "valor"), [])) == [["indicador", "valor"]]
