"""浏览器引擎。工具只认页面操作，下载和启动命令按引擎分开。"""

from __future__ import annotations

from typing import Protocol
from pathlib import Path
from dataclasses import dataclass

from ..gsbrowseruse_config.host import system_token, machine_token, platform_label

OBSCURA_VERSION = "0.2.5"
LIGHTPANDA_VERSION = "1.0.2"
_OBSCURA_ROOT = f"https://github.com/h4ckf0r0day/obscura/releases/download/v{OBSCURA_VERSION}"
_LIGHTPANDA_ROOT = f"https://github.com/lightpanda-io/browser/releases/download/{LIGHTPANDA_VERSION}"

# 校验值不含 sha256: 前缀。Lightpanda 固定 1.0.2，不跟每日 nightly。
_OBSCURA_DIGESTS: dict[str, str] = {
    "obscura-x86_64-linux.tar.gz": "2116764b99bc084fae3668b68aa535b4cf456e4498845b47493ad4123e83ca36",
    "obscura-aarch64-linux.tar.gz": "24c549a348b1d464e80aa3f643bc0c874b0a2942fb7836c683528028d0fbb190",
    "obscura-x86_64-macos.tar.gz": "9f354cf929a577491d6ba0ef451e07baefffd19d34115330f69a0e463771d6cd",
    "obscura-aarch64-macos.tar.gz": "fcca31eba4280cd67a2e226ef4b015e432d5c089f78cefd074ad12bbc8e23345",
    "obscura-x86_64-windows.zip": "9e56fa1cc1f9e4fb78926f7e9f36c40166b65177541ad7b7fd9645944c49174e",
    "obscura-x86_64-linux-stealth.tar.gz": "d9175cf7573d0243fc303a6f1a3b68affc757af0b5549cacb018e9670988316c",
    "obscura-aarch64-linux-stealth.tar.gz": "e28ed5ff2dbabe8d820c7b1ef56e6005399aff15912c7774777719e66a021a32",
    "obscura-x86_64-macos-stealth.tar.gz": "95ace7af8bb3eecbaa6c64b4869be2eaf421b8ced0a25c3b9981e18f8e681de6",
    "obscura-aarch64-macos-stealth.tar.gz": "9baab9b1d2e0862adb70ce2c81903b5a799bee026038130b9141fab597874100",
    "obscura-x86_64-windows-stealth.zip": "33c15a57c2c09e1bd8738bbb5d757107bded9749827d4248b7234d4bb5ed7303",
}
_LIGHTPANDA_DIGESTS: dict[str, str] = {
    "lightpanda-x86_64-linux": "ae7d01d261efb9e480e18ce3424533332883863bcf70b12a4321b5733f37e19e",
    "lightpanda-aarch64-linux": "ac546dfc43c533430da92b75ab36f2a29da7d6324d5d38baf606ef2e0d849345",
    "lightpanda-x86_64-macos": "91a775ecc67937d8d79c1b1a315748e52157804f18f629c6e1c6332a46255fc6",
    "lightpanda-aarch64-macos": "9f3ee749a55d1abc5f8fdda0d9559c3b2abcec5bff5bfe902bc06c0a89538ec4",
}


@dataclass(frozen=True)
class Asset:
    engine_id: str
    version: str
    name: str
    digest: str
    platform: str
    packed: bool
    program: str
    worker: str | None
    url: str


class BrowserEngine(Protocol):
    engine_id: str

    def resolve(self, system: str, machine: str, stealth: bool) -> Asset: ...

    def serve_args(
        self,
        binary: Path,
        port: int,
        *,
        stealth: bool,
        private_network: bool,
        fonts: str,
    ) -> list[str]: ...


class ObscuraEngine:
    engine_id = "obscura"

    def resolve(self, system: str, machine: str, stealth: bool) -> Asset:
        os_name = system_token(system)
        arch = machine_token(machine)
        if os_name == "windows" and arch != "x86_64":
            raise RuntimeError("Windows 只有 x86_64 安装包。")
        suffix = ".zip" if os_name == "windows" else ".tar.gz"
        marker = "-stealth" if stealth else ""
        name = f"obscura-{arch}-{os_name}{marker}{suffix}"
        if os_name == "windows":
            program, worker = "obscura.exe", "obscura-worker.exe"
        else:
            program, worker = "obscura", "obscura-worker"
        return Asset(
            engine_id=self.engine_id,
            version=f"v{OBSCURA_VERSION}",
            name=name,
            digest=_digest(_OBSCURA_DIGESTS, name),
            platform=platform_label(system, machine),
            packed=True,
            program=program,
            worker=worker,
            url=f"{_OBSCURA_ROOT}/{name}",
        )

    def serve_args(
        self,
        binary: Path,
        port: int,
        *,
        stealth: bool,
        private_network: bool,
        fonts: str,
    ) -> list[str]:
        # 不传 --storage-dir：那是进程级 cookie，用户之间会串。
        cmd = [
            str(binary),
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
            "--quiet",
        ]
        if stealth:
            cmd.append("--stealth")
        if private_network:
            cmd.append("--allow-private-network")
        if fonts and Path(fonts).is_dir():
            cmd.extend(["--font-dir", fonts])
        return cmd


class LightpandaEngine:
    engine_id = "lightpanda"

    def resolve(self, system: str, machine: str, stealth: bool) -> Asset:
        del stealth
        os_name = system_token(system)
        arch = machine_token(machine)
        if os_name == "windows":
            raise RuntimeError("Lightpanda 没有 Windows 安装包。请改用 Obscura，或在 Linux 环境里运行核心。")
        name = f"lightpanda-{arch}-{os_name}"
        return Asset(
            engine_id=self.engine_id,
            version=f"v{LIGHTPANDA_VERSION}",
            name=name,
            digest=_digest(_LIGHTPANDA_DIGESTS, name),
            platform=platform_label(system, machine),
            packed=False,
            program="lightpanda",
            worker=None,
            url=f"{_LIGHTPANDA_ROOT}/{name}",
        )

    def serve_args(
        self,
        binary: Path,
        port: int,
        *,
        stealth: bool,
        private_network: bool,
        fonts: str,
    ) -> list[str]:
        del stealth, private_network, fonts
        return [str(binary), "serve", "--host", "127.0.0.1", "--port", str(port)]


OBSCURA = ObscuraEngine()
LIGHTPANDA = LightpandaEngine()


def get_engine(engine_id: str) -> BrowserEngine:
    if engine_id == OBSCURA.engine_id:
        return OBSCURA
    if engine_id == LIGHTPANDA.engine_id:
        return LIGHTPANDA
    raise RuntimeError(f"没有这个浏览器引擎：{engine_id}")


def engine_label(engine_id: str) -> str:
    if engine_id == LIGHTPANDA.engine_id:
        return "Lightpanda"
    return "Obscura"


def variant_label(variant: str) -> str:
    if variant == "stealth":
        return "隐身"
    return "普通"


def _digest(table: dict[str, str], name: str) -> str:
    if name not in table:
        raise RuntimeError(f"没有这个安装包的校验值：{name}")
    return table[name]
