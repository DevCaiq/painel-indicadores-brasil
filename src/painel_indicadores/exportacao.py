"""Serialização CSV pura para downloads, com precisão e proteção de textos."""

import csv
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from io import StringIO

type CelulaCSV = str | Decimal | date | datetime | int | bool | None


def _proteger_texto(texto: str) -> str:
    """Neutraliza fórmulas, inclusive após espaços iniciais, sem perder o texto."""
    for caractere in texto:
        if caractere in "=+-@\t\r\n":
            return "'" + texto
        if not caractere.isspace():
            break
    return texto


def _formatar_celula(valor: CelulaCSV) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return _proteger_texto(valor)
    if isinstance(valor, bool):
        return "sim" if valor else "nao"
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def gerar_csv(
    colunas: tuple[str, ...], linhas: Iterable[tuple[CelulaCSV, ...]]
) -> bytes:
    """Gera UTF-8 com BOM, ponto decimal bruto, separador ';' e finais CRLF.

    Datas mantêm a informação fornecida: nenhum fuso ou instante é inferido.
    A quantidade de células deve coincidir com a de colunas em todas as linhas.
    """
    saida = StringIO(newline="")
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(_proteger_texto(coluna) for coluna in colunas)
    for numero, linha in enumerate(linhas, start=1):
        if len(linha) != len(colunas):
            raise ValueError(
                f"Linha {numero} tem {len(linha)} células; "
                f"esperadas {len(colunas)} colunas."
            )
        escritor.writerow(_formatar_celula(valor) for valor in linha)
    return saida.getvalue().encode("utf-8-sig")
