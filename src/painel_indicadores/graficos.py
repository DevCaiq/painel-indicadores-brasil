"""Especificações Plotly; float apenas na fronteira de visualização."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from html import escape
from typing import Any, Protocol

from painel_indicadores.contratos import Observacao
from painel_indicadores.formatacao import formatar_decimal
from painel_indicadores.indicadores import SERIES

CORES_SERIES = {432: "#1D4ED8", 433: "#7E22CE", 1: "#0F766E"}


class PontoVisual(Protocol):
    @property
    def data(self) -> date: ...
    @property
    def valor(self) -> Decimal | None: ...


def criar_grafico_linhas(
    codigo: int, linhas: Sequence[PontoVisual], unidade: str, *, linha: bool = False
) -> dict[str, Any]:
    grafico = criar_grafico(codigo, ())
    serie = grafico["data"][0]
    if unidade == "% em 12 meses":
        serie["name"] = "IPCA em 12 meses"
    serie["x"] = [item.data.isoformat() for item in linhas]
    serie["y"] = [
        float(item.valor) if item.valor is not None else None for item in linhas
    ]
    serie["customdata"] = [
        [
            item.data.strftime("%m/%Y" if codigo == 433 else "%d/%m/%Y"),
            formatar_decimal(item.valor, 4 if codigo == 1 else 2),
        ]
        for item in linhas
    ]
    unidade_segura = escape(unidade)
    serie["hovertemplate"] = (
        f"%{{customdata[0]}}<br><b>%{{customdata[1]}} {unidade_segura}</b><extra></extra>"
    )
    if linha:
        serie.pop("marker", None)
        serie.update(
            type="scatter",
            mode="lines+markers",
            connectgaps=False,
            line={"color": CORES_SERIES[codigo], "shape": "linear", "width": 2.5},
        )
    grafico["layout"]["yaxis"]["title"]["text"] = unidade_segura
    return grafico


def criar_grafico(codigo: int, observacoes: tuple[Observacao, ...]) -> dict[str, Any]:
    nome, unidade = SERIES[codigo]
    dados = sorted(observacoes, key=lambda item: item.data)
    serie: dict[str, Any] = {
        "name": nome,
        "x": [item.data.isoformat() for item in dados],
        "y": [float(item.valor) for item in dados],
        "customdata": [
            [
                item.data.strftime("%m/%Y" if codigo == 433 else "%d/%m/%Y"),
                formatar_decimal(item.valor, 4 if codigo == 1 else 2),
            ]
            for item in dados
        ],
        "hovertemplate": f"%{{customdata[0]}}<br><b>%{{customdata[1]}} {unidade}</b><extra></extra>",
    }
    if codigo == 433:
        serie.update(type="bar", marker={"color": CORES_SERIES[codigo]})
    else:
        serie.update(
            type="scatter",
            mode="lines+markers" if len(dados) == 1 else "lines",
            connectgaps=False,
            line={
                "color": CORES_SERIES[codigo],
                "width": 2.5,
                "shape": "hv" if codigo == 432 else "linear",
            },
        )
    return {
        "data": [serie],
        "layout": {
            "autosize": True,
            "showlegend": False,
            "hovermode": "closest",
            "paper_bgcolor": "#FFFFFF",
            "plot_bgcolor": "#FFFFFF",
            "separators": ",.",
            "font": {
                "family": "system-ui, Segoe UI, sans-serif",
                "size": 14,
                "color": "#475569",
            },
            "margin": {"t": 16, "r": 20, "b": 56, "l": 70},
            "xaxis": {
                "type": "date",
                "showgrid": False,
                "automargin": True,
                "nticks": 6,
                "tickformat": "%b\n%Y",
            },
            "yaxis": {
                "title": {"text": unidade},
                "gridcolor": "#E2E8F0",
                "zeroline": True,
                "zerolinecolor": "#64748B",
                "tickformat": ",.2f",
                "automargin": True,
                "rangemode": "tozero" if codigo == 433 else "normal",
            },
            "dragmode": "zoom",
            "transition": {"duration": 0},
        },
        "config": {
            "responsive": True,
            "displayModeBar": False,
            "scrollZoom": False,
            "locale": "pt-BR",
            "displaylogo": False,
        },
    }
