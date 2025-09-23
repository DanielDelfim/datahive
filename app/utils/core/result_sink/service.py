# app/utils/core/result_sink/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, Literal, Any

# Tipos suportados (extensível futuramente: "null", "multi")
SinkKind = Literal["json", "stdout"]


class ResultSink(Protocol):
    """Contrato para destino de resultados.

    Deve ser utilizado por SCRIPTS que produzem artefatos (JSONs) ou logs
    de conferência. Páginas/dashboards não devem escrever em disco.
    """

    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        """Despacha um resultado.

        Args:
            result: dicionário serializável em JSON.
            name: rótulo/nome lógico do conjunto de resultados (opcional).
        """
        ...


@dataclass
class SinkConfig:
    kind: SinkKind
    # kwargs livres para o sink concreto (ex.: output_dir, prefix, keep)
    options: dict[str, Any] | None = None


def make_sink(kind: SinkKind, **kwargs: Any) -> ResultSink:
    """Fábrica de sinks.

    Examples:
        >>> from pathlib import Path
        >>> sink = make_sink("json", output_dir=Path("/tmp/results"), prefix="repo", keep=2)
        >>> sink.emit({"ok": True}, name="mg")
        >>> sink = make_sink("stdout")
        >>> sink.emit({"msg": "preview"}, name="dry-run")
    """
    if kind == "json":
        from app.utils.core.result_sink.json_file_sink import JsonFileSink
        return JsonFileSink(**kwargs)
    elif kind == "stdout":
        from .stdout_sink import StdoutSink
        return StdoutSink()
    else:
        raise ValueError(f"Sink '{kind}' não suportado.")


def resolve_sink_from_flags(
    *,
    to_file: bool,
    to_stdout: bool = True,
    **kwargs: Any,
) -> ResultSink:
    """Ajuda scripts a decidir o destino dos resultados.

    Recomendado para scripts via flags CLI:
      --to-file/--no-to-file   | --stdout/--no-stdout

    Estratégia:
      - Se to_file: usa JsonFileSink (kwargs devem incluir 'output_dir', etc.)
      - Caso contrário: StdoutSink

    Returns:
        ResultSink pronto para uso no script.
    """
    if to_file:
        return make_sink("json", **kwargs)
    # fallback padrão é imprimir em tela para conferência
    if to_stdout:
        return make_sink("stdout")
    # Se nada for escolhido, ainda assim imprimimos (seguro)
    return make_sink("stdout")
