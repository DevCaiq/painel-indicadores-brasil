"""Regras puras e composição dos cards, sem acesso a banco ou ETL."""

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from time import monotonic
from typing import Literal

from pydantic import BaseModel, ConfigDict

from painel_indicadores.cache import CacheHistoricos
from painel_indicadores.cliente_api import ClienteAPI, ErroDeConsulta
from painel_indicadores.contratos import (
    Agregado,
    Cobertura,
    ConjuntoAgregados,
    ConjuntoObservacoes,
    RespostaFrescor,
    hoje_brasil,
)
from painel_indicadores.formatacao import motivo_legivel

SERIES = {
    432: ("Meta Selic", "% a.a."),
    433: ("IPCA mensal", "% a.m."),
    1: ("Dólar comercial venda", "R$/US$"),
}


class CardIndicador(BaseModel):
    model_config = ConfigDict(frozen=True)
    codigo: int
    nome: str
    unidade: str
    valor: Decimal | None = None
    referencia: date | None = None
    diferenca: Decimal | None = None
    unidade_diferenca: str | None = None
    referencia_anterior: date | None = None
    aviso: str | None = None
    cobertura: Cobertura | None = None


class MetricasPeriodo(BaseModel):
    model_config = ConfigDict(frozen=True)
    observacoes: int
    primeiro: Decimal | None = None
    ultimo: Decimal | None = None
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    consulta_completa: bool


class PanoramaIndicadores(BaseModel):
    cards: tuple[CardIndicador, ...]
    historicos: dict[int, ConjuntoObservacoes]


def valor_agregado(codigo: int, item: Agregado) -> Decimal | None:
    if codigo == 433:
        return item.variacao if item.completo is True and not item.parcial else None
    return item.ultimo


def criar_card_ipca_12m(conjunto: ConjuntoAgregados, hoje: date) -> CardIndicador:
    base = CardIndicador(
        codigo=1212,
        nome="IPCA em 12 meses",
        unidade="% em 12 meses",
        cobertura=conjunto.meta.cobertura,
    )
    if (
        not conjunto.consulta_completa
        or conjunto.meta.de != date(2020, 1, 1)
        or conjunto.meta.ate != hoje
    ):
        return base.model_copy(
            update={
                "aviso": "Acervo incompleto para determinar o último IPCA em 12 meses."
            }
        )
    if not conjunto.agregados:
        return base.model_copy(
            update={"aviso": "Não há períodos publicados para IPCA em 12 meses."}
        )
    ultimo = conjunto.agregados[-1]
    valor = valor_agregado(433, ultimo)
    aviso = None
    if valor is None:
        aviso = "IPCA em 12 meses incompleto: " + (
            motivo_legivel(ultimo.motivo) or "valor não disponível."
        )
    elif conjunto.meta.desatualizado:
        aviso = "Publicação gold desatualizada: " + (
            motivo_legivel(conjunto.meta.motivo) or "há dados mais recentes na base."
        )
    return base.model_copy(
        update={"valor": valor, "referencia": ultimo.periodo, "aviso": aviso}
    )


def criar_card(codigo: int, conjunto: ConjuntoObservacoes, hoje: date) -> CardIndicador:
    nome, unidade = SERIES[codigo]
    base = CardIndicador(
        codigo=codigo, nome=nome, unidade=unidade, cobertura=conjunto.meta.cobertura
    )
    if (
        not conjunto.consulta_completa
        or conjunto.meta.codigo != codigo
        or conjunto.meta.de != date(2020, 1, 1)
        or conjunto.meta.ate != hoje
    ):
        return base.model_copy(
            update={"aviso": "Acervo incompleto para determinar o último dado global."}
        )
    if not conjunto.observacoes:
        return base.model_copy(
            update={"aviso": "Não há dados disponíveis no acervo público."}
        )
    ordenadas = sorted(conjunto.observacoes, key=lambda item: item.data)
    ultima = ordenadas[-1]
    anterior = ordenadas[-2] if len(ordenadas) > 1 else None
    return base.model_copy(
        update={
            "valor": ultima.valor,
            "referencia": ultima.data,
            "diferenca": ultima.valor - anterior.valor if anterior else None,
            "referencia_anterior": anterior.data if anterior else None,
            "unidade_diferenca": "R$" if codigo == 1 else "p.p.",
            "aviso": (
                "A fonte informa cobertura incompleta; consulte a metodologia."
                if conjunto.meta.cobertura and conjunto.meta.cobertura.completa is False
                else None
            ),
        }
    )


def calcular_metricas(
    conjunto: ConjuntoObservacoes, de: date, ate: date
) -> MetricasPeriodo:
    if de > ate:
        raise ValueError("Período invertido.")
    observacoes = sorted(
        (item for item in conjunto.observacoes if de <= item.data <= ate),
        key=lambda item: item.data,
    )
    completa = (
        conjunto.consulta_completa
        and conjunto.meta.de <= de <= ate <= conjunto.meta.ate
    )
    if not observacoes:
        return MetricasPeriodo(observacoes=0, consulta_completa=completa)
    valores = [item.valor for item in observacoes]
    return MetricasPeriodo(
        observacoes=len(valores),
        primeiro=valores[0],
        ultimo=valores[-1],
        minimo=min(valores),
        maximo=max(valores),
        consulta_completa=completa,
    )


class ServicoIndicadores:
    def __init__(
        self,
        cliente: ClienteAPI,
        cache: CacheHistoricos,
        *,
        relogio: Callable[[], float] = monotonic,
    ) -> None:
        self._cliente = cliente
        self._cache = cache
        self._relogio = relogio

    def _chave(self, rota: str, **parametros: str | int) -> str:
        return json.dumps(
            [
                self._cliente.servidor,
                rota,
                sorted(parametros.items()),
                "transformacao-2",
            ]
        )

    def obter_historico(
        self, codigo: int, de: date, ate: date, *, prazo_consulta: float | None = None
    ) -> ConjuntoObservacoes:
        chave = self._chave(
            f"/api/v1/series/{codigo}/observacoes",
            de=de.isoformat(),
            ate=ate.isoformat(),
            limite=1000,
        )
        return self._cache.obter(
            chave,
            lambda: self._cliente.buscar_observacoes(
                codigo, de, ate, prazo_consulta=prazo_consulta
            ),
        )

    def obter_gold(
        self,
        codigo: int,
        de: date,
        ate: date,
        granularidade: Literal["mes", "ano"],
        *,
        prazo_consulta: float | None = None,
    ) -> ConjuntoAgregados:
        chave = self._chave(
            f"/api/v1/series/{codigo}/agregados",
            de=de.isoformat(),
            ate=ate.isoformat(),
            granularidade=granularidade,
            limite=1000,
        )
        return self._cache.obter_tipado(
            chave,
            lambda: self._cliente.buscar_agregados(
                codigo, de, ate, granularidade, prazo_consulta=prazo_consulta
            ),
            ConjuntoAgregados,
        )

    def obter_ipca_12m(
        self, de: date, ate: date, *, prazo_consulta: float | None = None
    ) -> ConjuntoAgregados:
        chave = self._chave(
            "/api/v1/indicadores/ipca-12m",
            de=de.isoformat(),
            ate=ate.isoformat(),
            limite=1000,
        )
        return self._cache.obter_tipado(
            chave,
            lambda: self._cliente.buscar_ipca_12m(
                de, ate, prazo_consulta=prazo_consulta
            ),
            ConjuntoAgregados,
        )

    def obter_frescor(self, *, prazo_consulta: float | None = None) -> RespostaFrescor:
        return self._cache.obter_tipado(
            self._chave("/api/v1/pipeline/frescor"),
            lambda: self._cliente.buscar_frescor(prazo_consulta=prazo_consulta),
            RespostaFrescor,
        )

    def renovar(self, codigo: int, de: date, ate: date, visualizacao: str) -> None:
        hoje = hoje_brasil()
        chaves = [
            self._chave(
                f"/api/v1/series/{serie}/observacoes",
                de="2020-01-01",
                ate=hoje.isoformat(),
                limite=1000,
            )
            for serie in SERIES
        ]
        chaves.extend(
            [
                self._chave(
                    f"/api/v1/series/{codigo}/observacoes",
                    de=de.isoformat(),
                    ate=ate.isoformat(),
                    limite=1000,
                ),
                self._chave(
                    "/api/v1/indicadores/ipca-12m",
                    de="2020-01-01",
                    ate=hoje.isoformat(),
                    limite=1000,
                ),
                self._chave(
                    "/api/v1/indicadores/ipca-12m",
                    de=de.isoformat(),
                    ate=ate.isoformat(),
                    limite=1000,
                ),
                self._chave("/api/v1/pipeline/frescor"),
            ]
        )
        if visualizacao in ("mes", "ano"):
            chaves.append(
                self._chave(
                    f"/api/v1/series/{codigo}/agregados",
                    de=de.isoformat(),
                    ate=ate.isoformat(),
                    granularidade=visualizacao,
                    limite=1000,
                )
            )
        self._cache.invalidar(chaves)

    def obter_panorama(self, hoje: date | None = None) -> tuple[CardIndicador, ...]:
        return self.obter_contexto(hoje).cards

    def verificar_processo(self) -> bool:
        return self._cliente.verificar_processo()

    def obter_contexto(self, hoje: date | None = None) -> PanoramaIndicadores:
        hoje = hoje or hoje_brasil()
        fim = self._relogio() + self._cliente.prazo_consulta
        cards = []
        historicos = {}
        for codigo, (nome, unidade) in SERIES.items():
            try:
                restante = fim - self._relogio()
                if restante <= 0:
                    raise ErroDeConsulta("Prazo do panorama esgotado; tente novamente.")
                conjunto = self.obter_historico(
                    codigo, date(2020, 1, 1), hoje, prazo_consulta=restante
                )
                historicos[codigo] = conjunto
                cards.append(criar_card(codigo, conjunto, hoje))
            except ErroDeConsulta as erro:
                cards.append(
                    CardIndicador(
                        codigo=codigo, nome=nome, unidade=unidade, aviso=str(erro)
                    )
                )
        return PanoramaIndicadores(cards=tuple(cards), historicos=historicos)
