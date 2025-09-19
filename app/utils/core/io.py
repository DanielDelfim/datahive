# app/utils/core/io.py
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

# Centraliza política de backup em paths.py
from app.config.paths import backup_path

def ler_json(path: Path) -> Any:
    """Lê JSON em UTF-8 e retorna objeto Python."""
    return json.loads(Path(path).read_text(encoding="utf-8"))

def atomic_write_json(target: Path, obj: Any, do_backup: bool = True) -> Path:
    """
    Grava JSON de forma atômica:
      1) cria diretório se necessário
      2) (opcional) faz backup do arquivo atual em .../backups/
      3) escreve em arquivo temporário no mesmo diretório
      4) faz replace atômico (os.replace) sobre o destino
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Backup do arquivo existente
    if do_backup and target.exists():
        bkp = backup_path(target)
        bkp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, bkp)

    # Escrita atômica
    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        encoding="utf-8",
        dir=str(target.parent),
        suffix=".json",
    ) as tmp:
        json.dump(obj, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, target)
    return target

def salvar_json(path: Path, data: Any, *, do_backup: bool = True) -> Path:
    """
    Compatível com chamadas existentes, mas agora ATÔMICO + BACKUP por padrão.
    """
    return atomic_write_json(path, data, do_backup=do_backup)
