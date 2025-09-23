# app/utils/core/result_sink/json_file_sink.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config.paths import backup_path, atomic_write_json  # helpers exigidos


def _sanitize_filename_part(s: str) -> str:
    # segura para compor nome de arquivo
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "latest"


@dataclass
class JsonFileSink:
    """Sink que grava resultados em JSON com backup+rotação.

    ATENÇÃO: Use APENAS em SCRIPTS (responsáveis por escrita em disco).

    Params:
        output_dir: diretório de saída (centralizado fora deste módulo).
        prefix: prefixo do nome do arquivo (ex.: "reposicao", "ads").
        keep: quantas versões manter no diretório de backup do arquivo.
              Obs.: atomic_write_json(do_backup=True) cria o backup; aqui
              fazemos a rotação, mantendo no máx. 'keep' por alvo lógico.

    Convenção de nomes:
        target = output_dir / f"{prefix}_{name or 'latest'}.json"

    Exemplo:
        sink = JsonFileSink(output_dir=Path(DATA_DIR)/"results", prefix="repo", keep=2)
        sink.emit(payload, name="mg")
    """
    output_dir: Path
    prefix: str = "results"
    keep: int = 2
    filename: Optional[str] = None  # << permite preservar nome exato

    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.filename:
            target = self.output_dir / self.filename
        else:
            base = f"{self.prefix}_{_sanitize_filename_part(name) if name else 'latest'}.json"
            target = self.output_dir / base

        # Escreve com backup atômico
        atomic_write_json(target, result, do_backup=True)

        # Rotaciona backups (mantém no máx. self.keep)
        self._rotate_backups(target)

    # --- internos ---

    def _rotate_backups(self, target: Path) -> None:
        """
        Mantém no máx. 'keep' backups para o arquivo 'target'.

        Suposição: backup_path(target) devolve um diretório ou caminho
        padronizado onde os backups são criados por atomic_write_json().
        Aqui listamos e aplicamos política LRU simples por data de modificação.
        """
        bkp_dir = Path(backup_path(target))
        if not bkp_dir.exists() or not bkp_dir.is_dir():
            return

        # Critério: arquivos que começam com o stem do target
        stem = target.stem  # ex.: results_mg
        candidates = sorted(
            [p for p in bkp_dir.iterdir() if p.is_file() and p.name.startswith(stem)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        # Mantém 'keep' mais recentes; remove o restante
        for old in candidates[self.keep :]:
            try:
                old.unlink(missing_ok=True)
            except Exception:
                # Evita quebrar execução por erro de permissão/bloqueio: log simples
                # (o script chamador pode ter logger próprio)
                print(f"[WARN] Falha ao remover backup antigo: {old}")
