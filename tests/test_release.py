"""安装包文件名、校验和压缩包路径。"""

from __future__ import annotations

import io
import json
import hashlib
import tarfile
import zipfile
from pathlib import Path

import pytest

from GsBrowserUse.gsbrowseruse_install.archive import assert_digest, extract_archive
from GsBrowserUse.gsbrowseruse_install.engines import OBSCURA, LIGHTPANDA
from GsBrowserUse.gsbrowseruse_install.manifest import _read_one


@pytest.mark.parametrize(
    ("system", "machine", "stealth", "expected", "label", "program"),
    [
        ("win32", "AMD64", False, "obscura-x86_64-windows.zip", "windows-x86_64", "obscura.exe"),
        ("linux", "x86_64", False, "obscura-x86_64-linux.tar.gz", "linux-x86_64", "obscura"),
        ("linux", "aarch64", True, "obscura-aarch64-linux-stealth.tar.gz", "linux-aarch64", "obscura"),
        ("darwin", "arm64", False, "obscura-aarch64-macos.tar.gz", "macos-aarch64", "obscura"),
        ("macos", "x86_64", True, "obscura-x86_64-macos-stealth.tar.gz", "macos-x86_64", "obscura"),
    ],
)
def test_asset_name(system: str, machine: str, stealth: bool, expected: str, label: str, program: str) -> None:
    asset = OBSCURA.resolve(system, machine, stealth)
    assert asset.name == expected
    assert asset.platform == label
    assert asset.program == program
    assert len(asset.digest) == 64
    assert asset.packed is True
    assert asset.url.endswith("/" + expected)


def test_windows_arm_has_no_build() -> None:
    with pytest.raises(RuntimeError, match="x86_64"):
        OBSCURA.resolve("win32", "ARM64", False)


def test_bad_digest_deletes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pack.bin"
    path.write_bytes(b"nope")
    with pytest.raises(RuntimeError, match="校验失败"):
        assert_digest(path, "0" * 64)
    assert not path.exists()


def test_matching_digest_keeps_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pack.bin"
    payload = b"ok"
    path.write_bytes(payload)
    assert_digest(path, hashlib.sha256(payload).hexdigest())
    assert path.read_bytes() == payload


def test_extract_keeps_names_inside_the_directory(tmp_path: Path) -> None:
    archive = tmp_path / "pack.tar.gz"
    with tarfile.open(archive, "w:gz") as packed:
        _add_tar(packed, "../outside.txt", b"evil")
        _add_tar(packed, "nested/obscura", b"browser")
    dest = tmp_path / "out"
    extract_archive(archive, dest)
    assert (dest / "obscura").read_bytes() == b"browser"
    assert (dest / "outside.txt").read_bytes() == b"evil"
    assert not (tmp_path / "outside.txt").exists()


def test_zip_extract_keeps_names_inside_the_directory(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr("../outside.txt", b"evil")
        packed.writestr("nested/obscura.exe", b"browser")
    dest = tmp_path / "out"
    extract_archive(archive, dest)
    assert (dest / "obscura.exe").read_bytes() == b"browser"
    assert not (tmp_path / "outside.txt").exists()


def _add_tar(packed: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    packed.addfile(info, io.BytesIO(payload))


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("linux", "x86_64", "lightpanda-x86_64-linux"),
        ("linux", "aarch64", "lightpanda-aarch64-linux"),
        ("darwin", "arm64", "lightpanda-aarch64-macos"),
        ("macos", "x86_64", "lightpanda-x86_64-macos"),
    ],
)
def test_lightpanda_asset_is_a_raw_binary(system: str, machine: str, expected: str) -> None:
    asset = LIGHTPANDA.resolve(system, machine, True)
    assert asset.name == expected
    assert asset.packed is False
    assert asset.program == "lightpanda"
    assert asset.worker is None
    assert len(asset.digest) == 64


def test_lightpanda_refuses_windows() -> None:
    with pytest.raises(RuntimeError, match="Windows"):
        LIGHTPANDA.resolve("win32", "AMD64", False)


def test_serve_commands_stay_on_the_engine() -> None:
    obscura = OBSCURA.serve_args(Path("obscura"), 9, stealth=False, private_network=False, fonts="")
    assert "--storage-dir" not in obscura
    assert "--workers" in obscura
    lightpanda = LIGHTPANDA.serve_args(Path("lightpanda"), 9, stealth=True, private_network=True, fonts="C:/fonts")
    assert lightpanda == [str(Path("lightpanda")), "serve", "--host", "127.0.0.1", "--port", "9"]


def test_manifest_without_engine_is_obscura(tmp_path: Path) -> None:
    program = tmp_path / "obscura.exe"
    program.write_bytes(b"x")
    raw = {
        "version": "v0.2.5",
        "path": str(program),
        "platform": "windows-x86_64",
        "variant": "render",
        "installed_at": "2026-10-27T19:27:30",
    }
    path = tmp_path / "install.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    info = _read_one(path)
    assert info is not None
    assert info["engine"] == "obscura"
