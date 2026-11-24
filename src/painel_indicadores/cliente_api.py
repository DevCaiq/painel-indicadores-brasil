"""Consultas públicas síncronas com erros sanitizados."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from time import monotonic, sleep
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ValidationError

from painel_indicadores.contratos import (
    Agregado,
    Catalogo,
    ConjuntoAgregados,
    ConjuntoObservacoes,
    FiltrosObservacoes,
    MetaGold,
    Observacao,
    PaginaAgregados,
    PaginaObservacoes,
    RespostaFrescor,
)


class ErroDeConsulta(Exception):
    """Falha segura para apresentação ao usuário."""


class _MudancaDeGeracao(Exception):
    """Sinal interno para reiniciar um conjunto, sem misturar versões."""


class ClienteAPI:
    def __init__(
        self,
        cliente: httpx.Client,
        *,
        prazo_consulta: float = 30,
        limite_paginas: int = 10,
        limite_registros: int = 10000,
        relogio: Callable[[], float] = monotonic,
        esperar: Callable[[float], None] = sleep,
    ) -> None:
        if prazo_consulta <= 0 or limite_paginas < 1 or limite_registros < 1:
            raise ValueError("Limites de consulta devem ser positivos.")
        self._cliente = cliente
        self._prazo = prazo_consulta
        self._limite_paginas = limite_paginas
        self._limite_registros = limite_registros
        self._relogio = relogio
        self._esperar = esperar

    @property
    def servidor(self) -> str:
        return str(self._cliente.base_url)

    @property
    def prazo_consulta(self) -> float:
        return self._prazo

    def _restante(self, fim: float) -> float:
        restante = fim - self._relogio()
        if restante <= 0:
            raise ErroDeConsulta("Prazo da consulta esgotado; tente um período menor.")
        return restante

    def _espera_retry(self, resposta: httpx.Response) -> float | None:
        valor = resposta.headers.get("Retry-After")
        if valor is None:
            return 0.0 if resposta.status_code == 503 else None
        try:
            segundos = float(valor)
        except ValueError:
            try:
                instante = parsedate_to_datetime(valor)
                segundos = (instante - datetime.now(UTC)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                return None
        return max(0.0, segundos) if segundos <= 1 else None

    def _consultar_modelo[T: BaseModel](
        self,
        rota: str,
        parametros: dict[str, str | int],
        fim: float,
        modelo: type[T],
    ) -> T:
        for tentativa in range(2):
            restante = self._restante(fim)
            # Preservar os timeouts do cliente, reduzindo-os ao orçamento restante.
            tempos = self._cliente.timeout.as_dict()
            timeout = httpx.Timeout(
                **{
                    nome: min(valor if valor is not None else restante, restante)
                    for nome, valor in tempos.items()
                }
            )
            try:
                # Ler incrementalmente: respostas em gotejamento não podem prender
                # a consulta indefinidamente, mesmo sem disparar read timeout.
                with self._cliente.stream(
                    "GET", rota, params=parametros, timeout=timeout
                ) as resposta:
                    self._restante(fim)
                    corpo = bytearray()
                    if resposta.status_code == 200:
                        for bloco in resposta.iter_bytes():
                            self._restante(fim)
                            corpo.extend(bloco)
                            if len(corpo) > 4 * 1024 * 1024:
                                raise ErroDeConsulta(
                                    "Página excedeu o limite seguro de resposta."
                                )
                self._restante(fim)
            except httpx.RequestError:
                self._restante(fim)
                if tentativa == 0:
                    continue
                raise ErroDeConsulta(
                    "Falha temporária ao consultar o histórico."
                ) from None
            if resposta.status_code == 409:
                raise _MudancaDeGeracao
            if resposta.status_code in (429, 503) and tentativa == 0:
                espera = self._espera_retry(resposta)
                if espera is not None and espera < self._restante(fim):
                    self._esperar(espera)
                    continue
            if resposta.status_code != 200:
                raise ErroDeConsulta(
                    f"Histórico indisponível (HTTP {resposta.status_code}); tente novamente mais tarde."
                )
            try:
                pagina = modelo.model_validate_json(bytes(corpo))
                self._restante(fim)
                return pagina
            except ValidationError:
                raise ErroDeConsulta(
                    "A API retornou um histórico incompatível."
                ) from None
        raise ErroDeConsulta("Falha temporária ao consultar o histórico.")

    def buscar_observacoes(
        self,
        codigo: int,
        de: date,
        ate: date,
        *,
        prazo_consulta: float | None = None,
    ) -> ConjuntoObservacoes:
        filtros = FiltrosObservacoes(codigo=codigo, de=de, ate=ate)
        return cast(
            ConjuntoObservacoes,
            self._buscar_temporal(
                filtros,
                f"/api/v1/series/{codigo}/observacoes",
                prazo_consulta=prazo_consulta,
            ),
        )

    def buscar_agregados(
        self,
        codigo: int,
        de: date,
        ate: date,
        granularidade: Literal["mes", "ano"],
        *,
        prazo_consulta: float | None = None,
    ) -> ConjuntoAgregados:
        if granularidade not in ("mes", "ano"):
            raise ValueError("Granularidade inválida.")
        return cast(
            ConjuntoAgregados,
            self._buscar_temporal(
                FiltrosObservacoes(codigo=codigo, de=de, ate=ate),
                f"/api/v1/series/{codigo}/agregados",
                gold=True,
                granularidade=granularidade,
                prazo_consulta=prazo_consulta,
            ),
        )

    def buscar_ipca_12m(
        self, de: date, ate: date, *, prazo_consulta: float | None = None
    ) -> ConjuntoAgregados:
        return cast(
            ConjuntoAgregados,
            self._buscar_temporal(
                FiltrosObservacoes(codigo=433, de=de, ate=ate),
                "/api/v1/indicadores/ipca-12m",
                gold=True,
                prazo_consulta=prazo_consulta,
            ),
        )

    def buscar_frescor(self, *, prazo_consulta: float | None = None) -> RespostaFrescor:
        fim = self._relogio() + min(
            self._prazo, prazo_consulta if prazo_consulta is not None else self._prazo
        )
        try:
            resposta = self._consultar_modelo(
                "/api/v1/pipeline/frescor", {}, fim, RespostaFrescor
            )
        except _MudancaDeGeracao:
            raise ErroDeConsulta(
                "Frescor temporariamente indisponível; tente novamente."
            ) from None
        return resposta.model_copy(update={"consultado_em": datetime.now(UTC)})

    def _buscar_temporal(
        self,
        filtros: FiltrosObservacoes,
        rota: str,
        *,
        gold: bool = False,
        granularidade: str | None = None,
        prazo_consulta: float | None = None,
    ) -> ConjuntoObservacoes | ConjuntoAgregados:
        fim = self._relogio() + min(
            self._prazo, prazo_consulta if prazo_consulta is not None else self._prazo
        )
        for tentativa in range(2):
            try:
                return self._percorrer_paginas(filtros, fim, rota, gold, granularidade)
            except _MudancaDeGeracao:
                if tentativa == 1:
                    raise ErroDeConsulta(
                        "Os dados mudaram novamente; tente mais tarde."
                    ) from None
        raise ErroDeConsulta("Não foi possível obter uma geração estável.")

    def _percorrer_paginas(
        self,
        filtros: FiltrosObservacoes,
        fim: float,
        rota: str,
        gold: bool,
        granularidade: str | None,
    ) -> ConjuntoObservacoes | ConjuntoAgregados:
        parametros: dict[str, str | int] = {
            "de": filtros.de.isoformat(),
            "ate": filtros.ate.isoformat(),
            "limite": 1000,
        }
        if granularidade is not None:
            parametros["granularidade"] = granularidade
        registros: list[Observacao | Agregado] = []
        cursores: set[str] = set()
        geracao: int | None = None
        unidade: str | None = None
        desatualizado = False
        motivo_desatualizado = None
        for numero in range(self._limite_paginas):
            pagina: PaginaAgregados | PaginaObservacoes
            if gold:
                pagina = self._consultar_modelo(rota, parametros, fim, PaginaAgregados)
            else:
                pagina = self._consultar_modelo(
                    rota, parametros, fim, PaginaObservacoes
                )
            meta = pagina.meta
            if (
                meta.camada != ("gold" if gold else "core")
                or meta.codigo != filtros.codigo
                or meta.de != filtros.de
                or meta.ate != filtros.ate
                or meta.versao_dados != (meta.versao_gold if gold else meta.versao_core)
            ):
                raise ErroDeConsulta(
                    "Metadados incompatíveis com a consulta solicitada."
                )
            versao = meta.versao_gold if gold else meta.versao_core
            if geracao is not None and versao != geracao:
                raise _MudancaDeGeracao
            geracao = versao
            desatualizado = desatualizado or meta.desatualizado
            motivo_desatualizado = motivo_desatualizado or (
                meta.motivo if meta.desatualizado else None
            )
            if unidade is not None and unidade != meta.unidade:
                raise ErroDeConsulta("A unidade mudou durante a consulta.")
            unidade = meta.unidade
            if pagina.pagina.limite != 1000 or len(pagina.data) > 1000:
                raise ErroDeConsulta("Limite de página incompatível com a consulta.")
            ultimo = registros[-1] if registros else None
            anterior = (
                (ultimo.data if isinstance(ultimo, Observacao) else ultimo.periodo)
                if ultimo
                else None
            )
            for item in pagina.data:
                referencia = item.data if isinstance(item, Observacao) else item.periodo
                if isinstance(item, Agregado) and item.unidade != meta.unidade:
                    raise ErroDeConsulta(
                        "Unidade do agregado incompatível com seus metadados."
                    )
                if not filtros.de <= referencia <= filtros.ate or (
                    anterior and referencia <= anterior
                ):
                    raise ErroDeConsulta(
                        "Datas duplicadas, fora de ordem ou fora do período."
                    )
                anterior = referencia
            espaco = self._limite_registros - len(registros)
            registros.extend(pagina.data[:espaco])
            cursor = pagina.pagina.proximo_cursor
            if pagina.pagina.tem_mais and (not pagina.data or cursor in cursores):
                raise ErroDeConsulta("A paginação não apresentou progresso.")
            completa = not pagina.pagina.tem_mais and len(pagina.data) <= espaco
            atingiu_limite = (
                len(registros) >= self._limite_registros
                or numero + 1 == self._limite_paginas
            )
            if completa or atingiu_limite:
                motivo = (
                    None
                    if completa
                    else "Limite de consulta atingido; selecione um período menor."
                )
                if gold:
                    return ConjuntoAgregados(
                        agregados=cast(tuple[Agregado, ...], tuple(registros)),
                        meta=cast(
                            MetaGold,
                            meta.model_copy(
                                update={
                                    "desatualizado": desatualizado,
                                    "motivo": motivo_desatualizado or meta.motivo,
                                }
                            ),
                        ),
                        consulta_completa=completa,
                        motivo=motivo,
                        consultado_em=datetime.now(UTC),
                    )
                return ConjuntoObservacoes(
                    observacoes=cast(tuple[Observacao, ...], tuple(registros)),
                    meta=meta,
                    consulta_completa=completa,
                    motivo=motivo,
                    consultado_em=datetime.now(UTC),
                )
            if cursor is not None:
                cursores.add(cursor)
                parametros["cursor"] = cursor
        raise ErroDeConsulta("Não foi possível concluir a paginação.")

    def buscar_catalogo(self) -> Catalogo:
        try:
            resposta = self._cliente.get("/api/v1/series")
            resposta.raise_for_status()
            return Catalogo.model_validate_json(resposta.content)
        except httpx.HTTPStatusError as erro:
            raise ErroDeConsulta(
                f"API indisponível para esta consulta (HTTP {erro.response.status_code})."
            ) from None
        except httpx.RequestError:
            raise ErroDeConsulta(
                "Não foi possível consultar a API no prazo disponível."
            ) from None
        except ValidationError:
            raise ErroDeConsulta("A API retornou um catálogo incompatível.") from None

    def verificar_processo(self) -> bool:
        """Sondagem curta: não comprova banco, cobertura ou frescor."""
        try:
            with self._cliente.stream("GET", "/health", timeout=1.0) as resposta:
                return resposta.status_code == 200
        except httpx.RequestError:
            return False
