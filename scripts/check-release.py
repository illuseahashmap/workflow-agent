"""Verify the checked-out submodules against the reviewed release manifest."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
for path, expected in manifest["repositories"].items():
    actual = subprocess.check_output(["git", "-C", str(root / path), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "ls-files", "--stage", "--", path], cwd=root, text=True).split()
    if len(tree) < 2 or tree[0] != "160000" or tree[1] != expected or actual != expected:
        raise SystemExit(f"Release revision mismatch: {path}")
    if subprocess.check_output(["git", "-C", str(root / path), "status", "--porcelain"], text=True).strip():
        raise SystemExit(f"Release source is dirty: {path}")
    print(f"Verified {path}: {actual}")
