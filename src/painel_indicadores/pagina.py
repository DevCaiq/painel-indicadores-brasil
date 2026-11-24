"""Filtros e composição da página; sem consultas externas nos templates."""

import calendar
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from math import ceil
from typing import Any, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, Field, ValidationError

from painel_indicadores.contratos import (
    ConjuntoAgregados,
    FiltrosObservacoes,
    RespostaFrescor,
)
from painel_indicadores.formatacao import motivo_legivel
from painel_indicadores.graficos import criar_grafico_linhas
from painel_indicadores.indicadores import (
    SERIES,
    CardIndicador,
    MetricasPeriodo,
    PanoramaIndicadores,
    criar_card_ipca_12m,
    valor_agregado,
)

TAMANHO_TABELA = 25


class FiltrosPagina(FiltrosObservacoes):
    pagina: int = Field(default=1, ge=1, le=100000)
    visualizacao: Literal["observacoes", "mes", "ano"] = "observacoes"


class ErroDeFiltros(ValueError):
    def __init__(self, campos: dict[str, str]) -> None:
        super().__init__("Revise os campos indicados.")
        self.campos = campos


class LinhaApresentacao(BaseModel):
    data: date
    valor: Decimal | None
    completo: bool | None = None
    parcial: bool = False
    motivo: str | None = None
    data_referencia: date | None = None


def subtrair_meses(dia: date, meses: int) -> date:
    indice = dia.year * 12 + dia.month - 1 - meses
    ano, mes = divmod(indice, 12)
    return date(ano, mes + 1, min(dia.day, calendar.monthrange(ano, mes + 1)[1]))


def resolver_filtros(parametros: Mapping[str, str], hoje: date) -> FiltrosPagina:
    erros: dict[str, str] = {}
    periodo = parametros.get("periodo", "1a")
    if periodo not in {"3m", "6m", "1a", "tudo"}:
        erros["de"] = "Escolha um período válido ou informe as datas explicitamente."
        periodo = "1a"
    try:
        codigo = int(parametros.get("codigo", "432"))
    except ValueError:
        codigo = 0
    if codigo not in SERIES:
        erros["codigo"] = "Escolha um dos indicadores disponíveis."
        codigo = 432
    try:
        numero_pagina = int(parametros.get("pagina", "1"))
    except ValueError:
        numero_pagina = 0
    visualizacao = parametros.get("visualizacao", "observacoes")
    if visualizacao not in ("observacoes", "mes", "ano"):
        erros["visualizacao"] = (
            "Escolha observações, agregado mensal ou agregado anual."
        )
        visualizacao = "observacoes"
    meses = {"3m": 3, "6m": 6, "1a": 12, "tudo": 12}[periodo]
    inicio = (
        date(2020, 1, 1)
        if periodo == "tudo"
        else max(date(2020, 1, 1), subtrair_meses(hoje, meses))
    )
    try:
        filtros = FiltrosPagina.model_validate(
            {
                "codigo": codigo,
                "de": parametros.get("de", inicio.isoformat()),
                "ate": parametros.get("ate", hoje.isoformat()),
                "pagina": numero_pagina,
                "visualizacao": visualizacao,
            }
        )
    except ValidationError as falha:
        for problema in falha.errors(include_input=False):
            campo = str(problema["loc"][0]) if problema["loc"] else None
            if campo in ("de", "ate"):
                erros[campo] = "Informe uma data válida no formato YYYY-MM-DD."
            elif campo == "pagina":
                erros["pagina"] = "Página inválida. Aplique os filtros novamente."
            else:
                mensagem = "Use um intervalo entre 01/01/2020 e hoje, com início anterior ou igual ao fim e até 3.660 dias."
                erros.update(de=mensagem, ate=mensagem)
        raise ErroDeFiltros(erros) from None
    if erros:
        raise ErroDeFiltros(erros)
    return filtros


def montar_pagina(
    filtros: FiltrosPagina,
    panorama: PanoramaIndicadores,
    *,
    gold: ConjuntoAgregados | None = None,
    ipca_12m: ConjuntoAgregados | None = None,
    frescor: RespostaFrescor | None = None,
    avisos_extras: list[str] | None = None,
) -> dict[str, Any]:
    conjunto = (
        panorama.historicos.get(filtros.codigo)
        if filtros.visualizacao == "observacoes"
        else gold
    )
    card = next(item for item in panorama.cards if item.codigo == filtros.codigo)
    dados: tuple[LinhaApresentacao, ...] = ()
    if gold is not None and filtros.visualizacao != "observacoes":
        card = card.model_copy(
            update={
                "unidade": gold.meta.unidade,
                "nome": "IPCA" if filtros.codigo == 433 else card.nome,
            }
        )
        dados = tuple(
            LinhaApresentacao(
                data=item.periodo,
                valor=valor_agregado(filtros.codigo, item),
                completo=item.completo,
                parcial=item.parcial,
                motivo=item.motivo,
                data_referencia=item.data_referencia,
            )
            for item in gold.agregados
        )
    elif conjunto is not None and filtros.visualizacao == "observacoes":
        historico = panorama.historicos[filtros.codigo]
        dados = tuple(
            LinhaApresentacao(data=item.data, valor=item.valor)
            for item in historico.observacoes
            if filtros.de <= item.data <= filtros.ate
        )
    paginas = max(1, ceil(len(dados) / TAMANHO_TABELA))
    numero = min(filtros.pagina, paginas)
    inicio = (numero - 1) * TAMANHO_TABELA
    parametros = {
        "codigo": filtros.codigo,
        "de": filtros.de.isoformat(),
        "ate": filtros.ate.isoformat(),
        "visualizacao": filtros.visualizacao,
    }
    navegacao = []
    for indice in sorted(
        {1, paginas, *range(max(1, numero - 1), min(paginas, numero + 1) + 1)}
    ):
        navegacao.append(
            {
                "numero": indice,
                "url": "/?" + urlencode({**parametros, "pagina": indice}) + "#tabela",
            }
        )
    avisos = list(avisos_extras or [])
    if conjunto and not conjunto.consulta_completa:
        avisos.append(
            "Consulta incompleta: "
            + (conjunto.motivo or "nem todas as páginas foram obtidas.")
        )
    if gold is not None and filtros.visualizacao != "observacoes":
        if gold.meta.desatualizado:
            avisos.append(
                "Gold desatualizada: "
                + (motivo_legivel(gold.meta.motivo) or "há dados core mais recentes.")
            )
        if any(
            item.parcial or item.completo is False or item.valor is None
            for item in dados
        ):
            avisos.append(
                "Há períodos parciais ou sem valor válido. As lacunas e seus motivos são preservados na tabela e na exportação."
            )
    metricas = None
    if conjunto is not None:
        validos = [item.valor for item in dados if item.valor is not None]
        metricas = MetricasPeriodo(
            observacoes=len(dados),
            primeiro=dados[0].valor if dados else None,
            ultimo=dados[-1].valor if dados else None,
            minimo=min(validos) if validos else None,
            maximo=max(validos) if validos else None,
            consulta_completa=conjunto.consulta_completa,
        )
    modo = (
        "Observações históricas"
        if filtros.visualizacao == "observacoes"
        else (
            "Inflação composta" if filtros.codigo == 433 else "Último valor publicado"
        )
        + (" no mês" if filtros.visualizacao == "mes" else " no ano")
    )
    dados_12 = (
        tuple(
            LinhaApresentacao(
                data=item.periodo,
                valor=valor_agregado(433, item),
                completo=item.completo,
                parcial=item.parcial,
                motivo=item.motivo,
                data_referencia=item.data_referencia,
            )
            for item in ipca_12m.agregados
            if filtros.de <= item.periodo <= filtros.ate
        )
        if ipca_12m
        else ()
    )
    detalhe_12: dict[str, Any] = {
        "card": CardIndicador(
            codigo=1212,
            nome="IPCA em 12 meses",
            unidade="% em 12 meses",
            aviso="Indicador temporariamente indisponível.",
        ),
        "linhas": (),
        "grafico": None,
        "meta": None,
        "completa": False,
        "aviso": "Indicador temporariamente indisponível.",
    }
    if ipca_12m is not None:
        detalhe_12 = {
            "card": criar_card_ipca_12m(ipca_12m, ipca_12m.meta.ate),
            "linhas": dados_12,
            "grafico": criar_grafico_linhas(433, dados_12, "% em 12 meses", linha=True)
            if any(item.valor is not None for item in dados_12)
            else None,
            "meta": ipca_12m.meta,
            "completa": ipca_12m.consulta_completa,
            "aviso": ipca_12m.motivo,
        }
    grafico = (
        criar_grafico_linhas(
            filtros.codigo,
            dados,
            card.unidade,
            linha=filtros.visualizacao != "observacoes" and filtros.codigo != 433,
        )
        if any(item.valor is not None for item in dados)
        else None
    )
    if grafico and filtros.visualizacao == "ano":
        grafico["layout"]["xaxis"]["tickformat"] = "%Y"
    diagnostico = (
        next((item for item in frescor.data if item.codigo == filtros.codigo), None)
        if frescor
        else None
    )
    if (
        conjunto
        and conjunto.meta.cobertura
        and conjunto.meta.cobertura.completa is False
    ):
        avisos.append(
            "A fonte informa cobertura incompleta. "
            + motivo_legivel(conjunto.meta.cobertura.motivo)
        )
    return {
        "cards": panorama.cards + (detalhe_12["card"],),
        "conjunto": conjunto,
        "modo": modo,
        "visualizacao": filtros.visualizacao,
        "ipca_12m": detalhe_12,
        "frescor": diagnostico,
        "frescor_meta": frescor.meta if frescor else None,
        "consulta_frescor": frescor.consultado_em if frescor else None,
        "consultado_em": conjunto.consultado_em if conjunto else None,
        "url_csv": "/exportar.csv?" + urlencode(parametros),
        "url_csv_12": "/exportar.csv?"
        + urlencode({**parametros, "codigo": 433, "tipo": "ipca12m"}),
        "exportavel": conjunto is not None and conjunto.consulta_completa,
        "selecionado": card,
        "observacoes": dados,
        "linhas": dados[inicio : inicio + TAMANHO_TABELA],
        "grafico": grafico,
        "metricas": metricas,
        "erro": (card.aviso or "Dados indisponíveis para esta visualização.")
        if conjunto is None
        else None,
        "avisos": avisos,
        "pagina_tabela": numero,
        "paginas": paginas,
        "navegacao": navegacao,
        "faixa": f"{inicio + 1}–{min(inicio + TAMANHO_TABELA, len(dados))} de {len(dados)}"
        if dados
        else "0 registros",
        "atalhos": [
            {
                "nome": nome,
                "url": "/?"
                + urlencode(
                    {
                        "codigo": filtros.codigo,
                        "periodo": periodo,
                        "visualizacao": filtros.visualizacao,
                    }
                ),
            }
            for nome, periodo in [
                ("3 meses", "3m"),
                ("6 meses", "6m"),
                ("1 ano", "1a"),
                ("Desde 2020", "tudo"),
            ]
        ],
    }
