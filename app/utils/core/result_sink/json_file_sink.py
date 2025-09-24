# app/utils/core/result_sink/json_file_sink.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.core.io import atomic_write_json
from app.config.paths import backup_path # função transversal para backup


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
        Mantém no máx. 'keep' backups conforme a **política vigente do projeto**:
        - `backup_path(target)` define **onde** os backups vivem.
        - Aqui listamos o **diretório de backups** e aplicamos LRU por mtime.
        """
        # Onde a política aponta para o backup alvo
        bkp_example = Path(backup_path(target))
        bkp_dir = bkp_example.parent
        if not bkp_dir.exists() or not bkp_dir.is_dir():
            return

        stem = target.stem
        suffix = target.suffix

        candidates = []
        try:
            for p in bkp_dir.iterdir():
                if not p.is_file():
                    continue
                name = p.name
                # Critério amplo: mesmo stem e mesmo sufixo (permite timestamps no nome)
                if name.startswith(stem) and name.endswith(suffix):
                    candidates.append(p)
        except Exception:
            return

        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in candidates[self.keep:]:
            try:
                old.unlink(missing_ok=True)
            except Exception:
                print(f"[WARN] Falha ao remover backup antigo: {old}")