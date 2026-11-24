"""Configuração independente do produtor."""

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracaoPainel(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    url_base_api: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")
    tempo_conexao_segundos: float = Field(default=3, gt=0)
    tempo_leitura_segundos: float = Field(default=10, gt=0)
    prazo_consulta_segundos: float = Field(default=30, gt=0, allow_inf_nan=False)
    limite_paginas: int = Field(default=10, ge=1, le=100)
    validade_cache_segundos: float = Field(default=300, gt=0, allow_inf_nan=False)
    limite_entradas_cache: int = Field(default=64, ge=1, le=1024)
    limite_bytes_cache: int = Field(default=16 * 1024 * 1024, ge=1)
    intervalo_atualizacao_segundos: float = Field(default=30, gt=0, allow_inf_nan=False)

    @field_validator("url_base_api")
    @classmethod
    def validar_url(cls, valor: AnyHttpUrl) -> AnyHttpUrl:
        if valor.username or valor.password or valor.query or valor.fragment:
            raise ValueError("URL deve conter apenas o endereço confiável da API.")
        return valor
