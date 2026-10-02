"""Build native portable archives on the target OS; never cross-label binaries."""

import builtins
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from jarvis import __version__


def main():
    root = Path(__file__).resolve().parents[1]
    if platform.system() not in {"Windows", "Linux"} or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise SystemExit("Portable builds currently support native Windows/Linux x64 only")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--onedir",
            "--name",
            "JarvisAI",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / "build"),
            "--specpath",
            str(root / "build"),
            "--collect-all",
            "jarvis",
            "--collect-all",
            "uvicorn",
            "--collect-all",
            "websockets",
            "--copy-metadata",
            "jarvis-ai-runtime",
            str(root / "main.py"),
        ],
        check=True,
    )
    package = root / "dist" / "JarvisAI"
    for name in ["LICENSE", "README.md", "THIRD_PARTY.md", "requirements.lock"]:
        shutil.copy(root / name, package / name)
    shutil.copytree(root / "docs", package / "docs", dirs_exist_ok=True)
    notices = package / "THIRD-PARTY-LICENSES"
    notices.mkdir(exist_ok=True)
    for dist in importlib.metadata.distributions():
        for entry in dist.files or []:
            if any(
                part.lower().startswith(("license", "copying", "notice")) for part in entry.parts
            ):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    destination = (
                        notices
                        / dist.metadata["Name"]
                        / str(entry).replace("/", "_").replace("\\", "_")
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(source, destination)
    # CPython ships its complete license through this standard interactive printer.
    printer = getattr(builtins, "license", None)
    if printer and hasattr(printer, "_Printer__setup"):
        printer._Printer__setup()
        (notices / "PYTHON-LICENSE.txt").write_text(
            "\n".join(printer._Printer__lines), encoding="utf-8"
        )
    suffix = ".exe" if platform.system() == "Windows" else ""
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/smoke_package.py"),
            "--executable",
            str(package / ("JarvisAI" + suffix)),
        ],
        check=True,
    )
    revision = os.getenv("GITHUB_SHA", "unversioned-source")
    dirty = None
    if (root / ".git").exists():
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
        )
    metadata = {
        "version": __version__,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "source_commit": revision,
        "source_dirty": dirty,
    }
    (package / "BUILD-INFO.json").write_text(json.dumps(metadata, indent=2))
    archive = shutil.make_archive(
        str(root / "dist" / f"Jarvis-{__version__}-{platform.system()}-x64"),
        "zip",
        root / "dist",
        "JarvisAI",
    )
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive + ".sha256").write_text(f"{digest}  {Path(archive).name}\n")
    print(f"Built and smoke-tested: {Path(archive).name}")


if __name__ == "__main__":
    main()
