"""Release packaging and installer safety checks; no host installation occurs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts" / "build_release.py"


def test_release_archive_contains_only_approved_source(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "solar-energy-system-v1.0.0.tar.gz" in result.stdout
    checksum = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"], cwd=tmp_path, capture_output=True, text=True
    )
    assert checksum.returncode == 0

    archive = tmp_path / "solar-energy-system-v1.0.0.tar.gz"
    with tarfile.open(archive, "r:gz") as bundle:
        names = {member.name for member in bundle.getmembers()}
        root = "solar-energy-system-v1.0.0"
        for required in (
            "install.sh", "VERSION", "CONTENT_SHA256SUMS", "release-manifest.json",
            "deployment/compose.yaml", "deployment/systemd/solar-energy.service",
            "backend/apps/main.py", "frontend/package-lock.json", "energy/siseli/api.py",
        ):
            assert f"{root}/{required}" in names
        installer = bundle.getmember(f"{root}/install.sh")
        assert installer.mode & 0o111
        assert not any(
            segment in {".git", "node_modules", ".venv", "__pycache__", "devices.json", "master.key"}
            for name in names for segment in Path(name).parts
        )
        manifest_file = bundle.extractfile(f"{root}/release-manifest.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)
        assert manifest["version"] == "1.0.0"
        assert "energy/siseli/api.py" in manifest["files_sha256"]


def test_release_secret_marker_is_rejected(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("build_release", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = tmp_path / "key.txt"
    candidate.write_text("-----BEGIN PRIVATE KEY-----\nnot a real key\n")
    with pytest.raises(ValueError, match="Private key"):
        module.validate_content(candidate, "key.txt")


def test_installer_help_and_read_only_bad_hostname(tmp_path: Path) -> None:
    subprocess.run(["bash", str(ROOT / "install.sh"), "--help"], check=True, capture_output=True)
    subprocess.run([sys.executable, str(BUILDER), "--output-dir", str(tmp_path)], check=True, capture_output=True)
    with tarfile.open(tmp_path / "solar-energy-system-v1.0.0.tar.gz", "r:gz") as bundle:
        bundle.extractall(tmp_path, filter="data")
    extracted = tmp_path / "solar-energy-system-v1.0.0"
    result = subprocess.run(
        ["bash", str(extracted / "install.sh"), "--check", "--hostname", "invalid_host", "--cert", "/missing", "--key", "/missing"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Invalid production hostname" in result.stderr
    assert not (extracted / "deployment" / ".env").exists()


def test_installer_rejects_extra_unlisted_release_file(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(BUILDER), "--output-dir", str(tmp_path)], check=True, capture_output=True)
    with tarfile.open(tmp_path / "solar-energy-system-v1.0.0.tar.gz", "r:gz") as bundle:
        bundle.extractall(tmp_path, filter="data")
    extracted = tmp_path / "solar-energy-system-v1.0.0"
    (extracted / "backend" / "apps" / "unlisted.txt").write_text("unlisted payload")
    result = subprocess.run(
        ["bash", str(extracted / "install.sh"), "--check", "--hostname", "example.com", "--cert", "/missing", "--key", "/missing"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unexpected files" in result.stderr
