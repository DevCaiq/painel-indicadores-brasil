"""Formatação de medidas sem conversão para float."""

from decimal import ROUND_HALF_UP, Decimal, localcontext


def motivo_legivel(motivo: str | None) -> str:
    mensagens = {
        "PERIODO_EM_ANDAMENTO": "Período em andamento",
        "CALENDARIO_NAO_HOMOLOGADO": "Calendário da fonte não homologado",
        "PERIODOS_PUBLICADOS": "Cobertura baseada nos períodos publicados",
        "REFERENCIA_EM_DIA": "Referência dentro da política de frescor",
        "CORE_NOVO": "Há dados mais recentes aguardando publicação",
        "SEM_CALENDARIO": "Calendário da fonte não disponível",
    }
    return mensagens.get(motivo or "", motivo or "")


def formatar_decimal(valor: Decimal | None, casas: int = 2) -> str:
    if valor is None:
        return "Indisponível"
    if not valor.is_finite() or not 0 <= casas <= 6:
        raise ValueError("Valor ou precisão de apresentação inválidos.")
    with localcontext() as contexto:
        contexto.prec = max(
            28, len(valor.as_tuple().digits) + abs(valor.adjusted()) + casas + 2
        )
        arredondado = valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
        if arredondado == 0:
            arredondado = abs(arredondado)
        texto = f"{arredondado:,.{casas}f}"
    return texto.translate(str.maketrans(",.", ".,"))
