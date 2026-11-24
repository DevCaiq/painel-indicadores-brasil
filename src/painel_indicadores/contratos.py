"""Campos essenciais do catálogo; extensões compatíveis são permitidas."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def hoje_brasil() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


class Cobertura(BaseModel):
    inicio: date | None
    fim: date | None
    observacoes: int = Field(ge=0)
    unidade_contagem: str
    completa: bool | None
    motivo: str


class Serie(BaseModel):
    codigo: int
    nome: str
    periodicidade: str
    unidade: str
    inicio_publico: date
    cobertura: Cobertura
    regra: str


class Metadados(BaseModel):
    camada: str
    versao_dados: int
    versao_core: int
    versao_gold: int
    data_publicacao: date | None = None
    desatualizado: bool = False
    motivo: str | None = None


class Catalogo(BaseModel):
    data: list[Serie]
    meta: Metadados


class FiltrosObservacoes(BaseModel):
    model_config = ConfigDict(frozen=True)
    codigo: int = Field(gt=0, strict=True)
    de: date
    ate: date

    @field_validator("de", "ate", mode="before")
    @classmethod
    def validar_data(cls, valor: object) -> object:
        if isinstance(valor, str) and not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", valor
        ):
            raise ValueError("Data deve usar YYYY-MM-DD.")
        return valor

    @model_validator(mode="after")
    def validar_periodo(self) -> Self:
        if not date(2020, 1, 1) <= self.de <= self.ate <= hoje_brasil():
            raise ValueError(
                "Período deve estar entre 2020 e hoje, em ordem crescente."
            )
        if (self.ate - self.de).days + 1 > 3660:
            raise ValueError("O período excede 3.660 dias inclusivos.")
        return self


class Observacao(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: date
    valor: Decimal

    @field_validator("valor", mode="before")
    @classmethod
    def validar_decimal(cls, valor: object) -> Decimal:
        if not isinstance(valor, (str, Decimal)):
            # Pydantic transforma ValueError em erro de contrato; TypeError escaparia.
            raise ValueError("Medida deve ser uma string decimal.")  # noqa: TRY004
        if isinstance(valor, str) and not re.fullmatch(
            r"-?[0-9]{1,14}\.[0-9]{6}", valor
        ):
            raise ValueError(
                "Medida deve usar seis casas e magnitude compatível com o produtor."
            )
        try:
            medida = Decimal(valor)
        except InvalidOperation:
            raise ValueError("Medida decimal inválida.") from None
        if not medida.is_finite():
            raise ValueError("Medida deve ser finita.")
        expoente = medida.as_tuple().exponent
        if medida.adjusted() > 13 or not isinstance(expoente, int) or expoente < -6:
            raise ValueError("Medida excede os limites numéricos do contrato.")
        return medida


class MetaObservacoes(Metadados):
    model_config = ConfigDict(frozen=True)
    codigo: int
    unidade: str
    de: date
    ate: date
    cobertura: Cobertura | None = None


class Pagina(BaseModel):
    limite: int = Field(ge=1, le=1000)
    tem_mais: bool
    proximo_cursor: str | None

    @model_validator(mode="after")
    def validar_cursor(self) -> Self:
        if self.tem_mais != bool(self.proximo_cursor):
            raise ValueError("Cursor e indicação de continuidade incompatíveis.")
        return self


class PaginaObservacoes(BaseModel):
    data: tuple[Observacao, ...]
    pagina: Pagina
    meta: MetaObservacoes


class ConjuntoObservacoes(BaseModel):
    model_config = ConfigDict(frozen=True)
    observacoes: tuple[Observacao, ...]
    meta: MetaObservacoes
    consulta_completa: bool
    motivo: str | None = None
    consultado_em: datetime | None = None


class MetaGold(MetaObservacoes):
    data_publicacao: date | None
    desatualizado: bool
    motivo: str | None


class Agregado(BaseModel):
    model_config = ConfigDict(frozen=True)
    periodo: date
    unidade: str
    observacoes: int = Field(ge=0)
    media: Decimal | None = None
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    ultimo: Decimal | None = None
    variacao: Decimal | None = None
    completo: bool | None
    parcial: bool
    motivo: str | None
    data_referencia: date

    @field_validator("media", "minimo", "maximo", "ultimo", "variacao", mode="before")
    @classmethod
    def validar_medida(cls, valor: object) -> Decimal | None:
        return None if valor is None else Observacao.validar_decimal(valor)


class PaginaAgregados(BaseModel):
    data: tuple[Agregado, ...]
    pagina: Pagina
    meta: MetaGold


class ConjuntoAgregados(BaseModel):
    model_config = ConfigDict(frozen=True)
    agregados: tuple[Agregado, ...]
    meta: MetaGold
    consulta_completa: bool
    motivo: str | None = None
    consultado_em: datetime | None = None


class Frescor(BaseModel):
    model_config = ConfigDict(frozen=True)
    codigo: int
    unidade: str
    cobertura: Cobertura | None
    ultima_consulta: datetime | None
    ultima_referencia: date | None
    ultima_publicacao: datetime | None
    defasado: bool | None
    politica: str
    calendario_homologado: bool
    motivo: str | None

    @field_validator("ultima_consulta", "ultima_publicacao")
    @classmethod
    def exigir_fuso(cls, valor: datetime | None) -> datetime | None:
        if valor is not None:
            if valor.tzinfo is None or valor.utcoffset() is None:
                raise ValueError("Timestamp da pipeline deve informar fuso.")
            return valor.astimezone(UTC)
        return None


class RespostaFrescor(BaseModel):
    data: tuple[Frescor, ...]
    meta: Metadados
    consultado_em: datetime | None = None

    @model_validator(mode="after")
    def validar_series(self) -> Self:
        if len({item.codigo for item in self.data}) != len(self.data):
            raise ValueError("Séries duplicadas no frescor.")
        return self
