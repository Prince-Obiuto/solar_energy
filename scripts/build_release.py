#!/usr/bin/env python3
"""Build a reviewed, secret-free source release without requiring Git on the VM."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    ".dockerignore",
    "README.md",
    "VERSION",
    "install.sh",
    "backend/Dockerfile",
    "backend/requirements.txt",
    "backend/alembic.ini",
    "backend/docker/entrypoint.py",
    "frontend/Dockerfile",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/index.html",
    "frontend/vite.config.js",
    "deployment/compose.yaml",
    "deployment/.env.example",
    "deployment/README.md",
    "deployment/nginx/default.conf",
    "deployment/scripts/backup.sh",
    "deployment/scripts/preflight.sh",
    "deployment/systemd/solar-energy.service",
    "deployment/systemd/solar-energy-backup.service",
    "deployment/systemd/solar-energy-backup.timer",
    "energy/siseli/LICENSE",
    "energy/siseli/UPSTREAM.md",
    "energy/siseli/__init__.py",
    "energy/siseli/api.py",
    "energy/siseli/const.py",
    "docs/system-guide.md",
}
RECURSIVE_PREFIXES = (
    "backend/apps/",
    "backend/migrations/",
    "frontend/src/",
    "frontend/public/",
)
FORBIDDEN_PARTS = {".git", "node_modules", ".venv", "venv", "__pycache__", "backups", "dist"}
FORBIDDEN_NAMES = {
    ".env", "devices.json", "snapshot.json", "tinytuya.json", "tuya-raw.json",
    "master.key", "postgres_password", "jwt_secret",
}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".dump", ".sqlite", ".sqlite3", ".db", ".pyc")
PRIVATE_KEY_MARKER = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
CONNECTION_PASSWORD = re.compile(rb"postgres(?:ql)?(?:\+psycopg)?://[^\s:@]+:[^\s@]+@", re.IGNORECASE)
SECRET_ASSIGNMENT = re.compile(
    rb"(?m)^\s*(?:BEVE_PASSWORD|SISELI_PASSWORD|TUYA_ACCESS_SECRET|TUYA_LOCAL_KEY|JWT_SECRET_KEY|POSTGRES_PASSWORD)\s*=\s*[^\s#]+"
)


def git_output(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def allowed(path: str) -> bool:
    return path in REQUIRED_FILES or path.startswith(RECURSIVE_PREFIXES)


def validate_path(path: str) -> None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not allowed(path):
        raise ValueError(f"Unapproved release path: {path}")
    if any(part in FORBIDDEN_PARTS for part in pure.parts):
        raise ValueError(f"Prohibited release path: {path}")
    if any(part.startswith(".env") and part != ".env.example" for part in pure.parts):
        raise ValueError(f"Environment file is prohibited: {path}")
    if pure.name in FORBIDDEN_NAMES or pure.name.endswith(FORBIDDEN_SUFFIXES):
        raise ValueError(f"Secret or generated file is prohibited: {path}")


def release_paths() -> list[str]:
    tracked = {name.decode() for name in git_output("ls-files", "-z").split(b"\0") if name}
    selected = {name for name in tracked if allowed(name)} | REQUIRED_FILES
    missing = sorted(name for name in REQUIRED_FILES if not (ROOT / name).is_file())
    if missing:
        raise ValueError("Required release files are missing: " + ", ".join(missing))
    for name in selected:
        validate_path(name)
        source = ROOT / name
        if not source.is_file() or source.is_symlink() or any(parent.is_symlink() for parent in source.parents if parent != ROOT):
            raise ValueError(f"Release source must be a regular non-symlink file: {name}")
    return sorted(selected)


def validate_content(path: Path, relative: str) -> None:
    content = path.read_bytes()
    if PRIVATE_KEY_MARKER.search(content) or CONNECTION_PASSWORD.search(content):
        raise ValueError(f"Private key or credential-bearing URL found in {relative}")
    # Assignments are suspicious in a release; variable names and sample text are not.
    if SECRET_ASSIGNMENT.search(content):
        raise ValueError(f"Credential assignment found in {relative}")


def normalized_tar_info(path: Path, arcname: str, epoch: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(arcname)
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = epoch
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
    else:
        info.size = path.stat().st_size
        info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
    return info


def build(output_dir: Path) -> tuple[Path, str]:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("VERSION must be a semantic version such as 1.0.0")
    paths = release_paths()
    commit = git_output("rev-parse", "HEAD").decode().strip()
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", git_output("show", "-s", "--format=%ct", "HEAD").decode().strip()))
    timestamp = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    package_name = f"solar-energy-system-v{version}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="solar-release-") as temporary:
        stage = Path(temporary) / package_name
        stage.mkdir()
        digests: dict[str, str] = {}
        for relative in paths:
            source = ROOT / relative
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination, follow_symlinks=False)
            destination.chmod(0o755 if os.access(source, os.X_OK) else 0o644)
            validate_content(destination, relative)
            digests[relative] = sha256(destination)

        manifest = {
            "version": version,
            "git_commit": commit,
            "source_dirty": bool(git_output("status", "--porcelain", "--untracked-files=all")),
            "build_timestamp_utc": timestamp,
            "timestamp_basis": "SOURCE_DATE_EPOCH" if "SOURCE_DATE_EPOCH" in os.environ else "git_commit_time",
            "supported_os": ["Ubuntu 22.04 LTS", "Ubuntu 24.04 LTS", "Ubuntu 26.04 LTS"],
            "components": ["FastAPI backend", "React/Nginx frontend", "PostgreSQL Compose", "tracked Siseli adaptation"],
            "files_sha256": digests,
        }
        (stage / "release-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        checksum_lines = [f"{sha256(stage / relative)}  {relative}" for relative in sorted([*paths, "release-manifest.json"])]
        (stage / "CONTENT_SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="ascii")

        # Re-scan the exact payload after generated metadata has been added.
        for path in stage.rglob("*"):
            if path.is_file():
                validate_content(path, path.relative_to(stage).as_posix())

        archive = output_dir / f"{package_name}.tar.gz"
        temporary_archive = output_dir / f".{package_name}.tar.gz.partial"
        with temporary_archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as tar:
                members = [stage, *sorted(stage.rglob("*"))]
                for member in members:
                    arcname = f"{package_name}/{member.relative_to(stage).as_posix()}" if member != stage else package_name
                    info = normalized_tar_info(member, arcname, epoch)
                    if member.is_file():
                        with member.open("rb") as source:
                            tar.addfile(info, source)
                    else:
                        tar.addfile(info)
        temporary_archive.replace(archive)
        digest = sha256(archive)
        temporary_sums = output_dir / ".SHA256SUMS.partial"
        temporary_sums.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
        temporary_sums.replace(output_dir / "SHA256SUMS")
    return archive, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        archive, digest = build(args.output_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Release build failed: {exc}\n")
    print(f"Built {archive.name} ({archive.stat().st_size} bytes)")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
