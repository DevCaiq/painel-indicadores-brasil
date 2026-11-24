"""Proteções em memória para atualização do cache de dados públicos."""

import hashlib
import hmac
import math
import secrets
import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit

_CHAVE_ASSINATURA = secrets.token_bytes(32)
_VALIDADE_TOKEN = 7200
_LIMITE_RESERVAS = 128


class ErroDeAtualizacao(Exception):
    """Recusa segura que pode ser apresentada na resposta HTTP."""

    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def _normalizar_origem(origem: str | None) -> tuple[str, str, int] | None:
    if not origem or any(caractere.isspace() for caractere in origem):
        return None
    if any(caractere in origem for caractere in ("?", "#", "\\")):
        return None
    try:
        partes = urlsplit(origem)
        if (
            partes.scheme not in ("http", "https")
            or not partes.hostname
            or partes.path
            or partes.username is not None
            or partes.password is not None
            or partes.netloc.endswith(":")
        ):
            return None
        porta = partes.port
        return (
            partes.scheme.lower(),
            partes.hostname.lower(),
            porta if porta is not None else (443 if partes.scheme == "https" else 80),
        )
    except ValueError:
        return None


class ProtecaoAtualizacao:
    """Valida CSRF e espaça atualizações compartilhadas por conjunto.

    Uma instância deve ser compartilhada por toda a aplicação. As reservas são
    locais ao processo; não coordenam trabalhadores de servidor distintos.
    """

    def __init__(
        self,
        intervalo: float = 30,
        *,
        relogio: Callable[[], float] = time.monotonic,
        relogio_utc: Callable[[], float] = time.time,
    ) -> None:
        if not math.isfinite(intervalo) or intervalo <= 0:
            raise ValueError("O intervalo deve ser positivo e finito.")
        self._intervalo = intervalo
        self._relogio = relogio
        self._relogio_utc = relogio_utc
        self._reservas: dict[str, float] = {}
        self._trava = threading.Lock()

    def emitir_token(self) -> str:
        """Emite token imprevisível com instante UTC e assinatura HMAC."""
        conteudo = f"{int(self._relogio_utc())}.{secrets.token_hex(32)}"
        assinatura = hmac.new(
            _CHAVE_ASSINATURA, conteudo.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return f"{conteudo}.{assinatura}"

    def validar(
        self,
        token_enviado: str,
        token_cookie: str | None,
        origem: str | None,
        origem_esperada: str,
    ) -> None:
        """Exige origem exata e token assinado idêntico ao cookie."""
        erro = ErroDeAtualizacao(
            403, "Atualização não autorizada. Recarregue a página e tente novamente."
        )
        esperada = _normalizar_origem(origem_esperada)
        if esperada is None or _normalizar_origem(origem) != esperada:
            raise erro
        if not token_enviado or not token_cookie or len(token_enviado) > 256:
            raise erro
        if not hmac.compare_digest(
            token_enviado.encode("utf-8"), token_cookie.encode("utf-8")
        ):
            raise erro
        try:
            instante, aleatorio, assinatura = token_enviado.split(".")
            conteudo = f"{instante}.{aleatorio}".encode("ascii")
            assinatura_esperada = hmac.new(
                _CHAVE_ASSINATURA, conteudo, hashlib.sha256
            ).hexdigest()
            assinatura_valida = hmac.compare_digest(
                assinatura.encode("utf-8"), assinatura_esperada.encode("ascii")
            )
            idade = self._relogio_utc() - int(instante)
        except (ValueError, UnicodeError):
            raise erro from None
        if not assinatura_valida or not 0 <= idade < _VALIDADE_TOKEN:
            raise erro

    def reservar(self, chave: str) -> None:
        """Reserva uma atualização sem espera e sem expulsar reservas ativas."""
        with self._trava:
            agora = self._relogio()
            expiradas = [
                chave_reservada
                for chave_reservada, instante in self._reservas.items()
                if agora - instante >= self._intervalo
            ]
            for chave_expirada in expiradas:
                del self._reservas[chave_expirada]
            if chave in self._reservas or len(self._reservas) >= _LIMITE_RESERVAS:
                raise ErroDeAtualizacao(
                    429,
                    "Aguarde alguns instantes antes de atualizar os dados novamente.",
                )
            self._reservas[chave] = agora
