"""Cache local de conjuntos completos, com TTL e orçamento de bytes serializados."""

from collections import OrderedDict
from collections.abc import Callable, Iterable
from threading import RLock
from time import monotonic

from pydantic import BaseModel

from painel_indicadores.contratos import ConjuntoObservacoes


class CacheHistoricos:
    def __init__(
        self,
        *,
        validade: float = 300,
        maximo_entradas: int = 64,
        maximo_bytes: int = 16 * 1024 * 1024,
        relogio: Callable[[], float] = monotonic,
    ) -> None:
        if validade <= 0 or maximo_entradas < 1 or maximo_bytes < 1:
            raise ValueError("Limites do cache devem ser positivos.")
        self._validade = validade
        self._maximo_entradas = maximo_entradas
        self._maximo_bytes = maximo_bytes
        self._relogio = relogio
        self._trava = RLock()
        self._entradas: OrderedDict[str, tuple[float, bytes, int]] = OrderedDict()
        self._bytes = 0

    def _remover(self, chave: str) -> None:
        self._bytes -= self._entradas.pop(chave)[2]

    def obter(
        self,
        chave: str,
        carregar: Callable[[], ConjuntoObservacoes],
    ) -> ConjuntoObservacoes:
        return self.obter_tipado(chave, carregar, ConjuntoObservacoes)

    def invalidar(self, chaves: Iterable[str]) -> None:
        with self._trava:
            for chave in chaves:
                if chave in self._entradas:
                    self._remover(chave)

    def obter_tipado[T: BaseModel](
        self,
        chave: str,
        carregar: Callable[[], T],
        tipo: type[T],
    ) -> T:
        # Uma carga por vez no processo inicial: evita duplicação e rajadas na API.
        with self._trava:
            agora = self._relogio()
            for antiga, (expira, _, _) in list(self._entradas.items()):
                if expira <= agora:
                    self._remover(antiga)
            entrada = self._entradas.get(chave)
            if entrada:
                self._entradas.move_to_end(chave)
                return tipo.model_validate_json(entrada[1])
            resultado = carregar()
            if getattr(resultado, "consulta_completa", True):
                dados = resultado.model_dump_json().encode("utf-8")
                tamanho = len(dados) + len(chave.encode("utf-8"))
                if tamanho <= self._maximo_bytes:
                    while self._entradas and (
                        len(self._entradas) >= self._maximo_entradas
                        or self._bytes + tamanho > self._maximo_bytes
                    ):
                        self._remover(next(iter(self._entradas)))
                    self._entradas[chave] = (
                        self._relogio() + self._validade,
                        dados,
                        tamanho,
                    )
                    self._bytes += tamanho
            return resultado
