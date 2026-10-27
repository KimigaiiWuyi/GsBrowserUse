"""解压安装包。只取文件名，避免压缩包里的 ../ 写到目录外面。"""

from __future__ import annotations

import shutil
import hashlib
import tarfile
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def assert_digest(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual == expected:
        return
    path.unlink()
    raise RuntimeError("安装包校验失败，已删除下载文件。")


def _safe_base(name: str) -> str | None:
    base = Path(name).name
    if not base or base in {".", ".."}:
        return None
    return base


def extract_archive(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        _unzip(archive, dest)
        return
    _untar(archive, dest)


def _unzip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as packed:
        for info in packed.infolist():
            if info.is_dir():
                continue
            base = _safe_base(info.filename)
            if base is None:
                continue
            target = dest / base
            with packed.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)


def _untar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:*") as packed:
        for member in packed.getmembers():
            if not member.isfile() or member.issym() or member.islnk():
                continue
            base = _safe_base(member.name)
            if base is None:
                continue
            extracted = packed.extractfile(member)
            if extracted is None:
                continue
            target = dest / base
            with extracted, target.open("wb") as out:
                shutil.copyfileobj(extracted, out)
