"""The proven Siseli reader must be present in a clean source checkout."""

import hashlib
import importlib
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VENDOR_ROOT = REPOSITORY_ROOT / "energy" / "siseli"
EXPECTED_HASHES = {
    "__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "api.py": "34011224c25f01123b2b2fd1b939bf69a023a561b8492c748398bcbfda8cb0af",
    "const.py": "f8ddce94cc0dfbb7b746fdf5233f5926475ac8f87aa0164a3c418fc60f4054f9",
}


def test_tracked_siseli_vendor_snapshot_has_license_and_expected_content(monkeypatch) -> None:
    assert (VENDOR_ROOT / "LICENSE").is_file()
    assert "MIT License" in (VENDOR_ROOT / "LICENSE").read_text(encoding="utf-8")
    provenance = (VENDOR_ROOT / "UPSTREAM.md").read_text(encoding="utf-8")
    assert "Conexo-Casa/solar-of-things-ha" in provenance
    for filename, expected_hash in EXPECTED_HASHES.items():
        assert hashlib.sha256((VENDOR_ROOT / filename).read_bytes()).hexdigest() == expected_hash

    monkeypatch.syspath_prepend(str(REPOSITORY_ROOT / "energy"))
    module = importlib.import_module("siseli.api")
    assert callable(module.SolarOfThingsAPI)
