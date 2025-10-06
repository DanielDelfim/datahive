from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from app.utils.core.io import atomic_write_json
from app.config.paths import backup_path  # função transversal para backup


def _sanitize_filename_part(s: str) -> str:
    # segura para compor nome de arquivo
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "latest"


@dataclass
class JsonFileSink:
    """Sink que grava resultados em JSON com backup+rotação.

    Compatível com DOIS modos de uso:

    (A) Modo legado por diretório/prefixo (usa .emit):
        JsonFileSink(output_dir=..., prefix="repo", keep=2, filename=None)
        sink.emit(payload, name="mg")

    (B) Modo por caminho único (usa .write) — compatível com build_sink(...):
        JsonFileSink(target_path=Path(...), do_backup=True, pretty=True)
        sink.write(payload, dry_run=False, debug=False)
    """

    # --- Modo (A)
    output_dir: Optional[Path] = None
    prefix: str = "results"
    keep: int = 2
    filename: Optional[str] = None  # permite preservar nome exato

    # --- Modo (B)
    target_path: Optional[Path] = None
    do_backup: bool = True
    pretty: bool = True  # mantido por compatibilidade (não altera formatação do atomic_write_json)

    # API legado
    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        """Grava usando convenção de diretório/prefixo/filename."""
        target = self._resolve_target_legacy(name)
        self._ensure_parent(target)
        atomic_write_json(target, result, do_backup=True)
        self._rotate_backups(target)

    # API atual (usada pelo build_sink do seu projeto)
    def write(self, payload: Any, *, dry_run: bool = False, debug: bool = False):
        """Grava em um path único (target_path). Se dry_run: não grava."""
        if self.target_path is None:
            # fallback: se só foi configurado o modo legado, delega para emit()
            if dry_run:
                if debug:
                    print("[DRY-RUN] JsonFileSink.emit (modo legado)")
                return
            self.emit(payload, name=None)
            return

        if dry_run:
            if debug:
                print(f"[DRY-RUN] json_file sink: destino={self.target_path}")
            return

        target = self.target_path
        self._ensure_parent(target)
        atomic_write_json(target, payload, do_backup=self.do_backup)
        self._rotate_backups(target)
        if debug:
            print(f"[INFO] Gravado: {target}")

    # -------- internos --------

    def _resolve_target_legacy(self, name: Optional[str]) -> Path:
        if self.filename:
            if self.output_dir is None:
                raise ValueError("output_dir é obrigatório quando usar filename.")
            return Path(self.output_dir) / self.filename
        if self.output_dir is None:
            raise ValueError("output_dir é obrigatório no modo legado.")
        base = f"{self.prefix}_{_sanitize_filename_part(name) if name else 'latest'}.json"
        return Path(self.output_dir) / base

    @staticmethod
    def _ensure_parent(target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_backups(self, target: Path) -> None:
        """
        Mantém no máx. 'keep' backups conforme a política vigente:
        - backup_path(target) define onde vivem os backups.
        """
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
