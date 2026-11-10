"""Validate canonical HA release tags and build the public integration archive."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

TAG = re.compile(
    r"v(?P<version>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?P<pre>-?(?:a|b|rc)[1-9]\d*)?)"
)
COMPONENT = Path("custom_components/dtek_monitor")


def metadata(root: Path, tag: str) -> dict:
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError("Use vMAJOR.MINOR.PATCH with an optional -rcN, aN or bN suffix")
    version = match["version"]
    component = root / COMPONENT
    if json.loads((component / "manifest.json").read_text())["version"] != version:
        raise ValueError("Tag does not match manifest version")
    changelog = (root / "CHANGELOG.md").read_text()
    section = re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n(.*?)(?=^## \[|\Z)",
        changelog,
        re.MULTILINE | re.DOTALL,
    )
    if not section or not section[1].strip():
        raise ValueError("Release requires a nonempty dated changelog entry")
    for path in [
        component / "account_history_api.py",
        *(component / "frontend").glob("*.js"),
    ]:
        if path.exists() and any(
            value != version
            for value in re.findall(r"\.js\?v=([^\"'\s]+)", path.read_text())
        ):
            raise ValueError(
                f"Frontend cache version does not match manifest: {path.name}"
            )
    prerelease = bool(match["pre"])
    policy = root / ".github/release-channel.json"
    if policy.exists():
        channel = json.loads(policy.read_text())
        if (
            not isinstance(channel, dict)
            or set(channel) != {"version", "prerelease"}
            or channel["version"] != version
            or type(channel["prerelease"]) is not bool
        ):
            raise ValueError("Release channel must explicitly match this version")
        prerelease = channel["prerelease"]
    return {
        "version": version,
        "prerelease": prerelease,
        "notes": re.sub(
            r"\]\((?![a-z]+:|#)([^)]+)\)",
            lambda link: f"](https://github.com/groove-max/ha-dtek-monitor/blob/{tag}/{link[1]})",
            section[1].strip() + "\n",
        ),
    }


def package(root: Path, target: Path) -> None:
    """Only committed component files belong in the release, never local caches."""
    names = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--", str(COMPONENT)], cwd=root
        )
        .decode()
        .split("\0")
    )
    names = [Path(name) for name in names if name]
    required = {
        "manifest.json",
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "__init__.py",
    }
    relative = {str(path.relative_to(COMPONENT)) for path in names}
    if not required.issubset(relative):
        raise ValueError("Component or distribution notices are missing")
    for path in names:
        if (
            (root / path).is_symlink()
            or "__pycache__" in path.parts
            or (path.suffix not in {".py", ".js", ".json", ".png", ".md", ""}
                and path != COMPONENT / "services.yaml")
        ):
            raise ValueError(f"Unexpected release file: {path}")
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for path in sorted(names):
            archive.write(root / path, path.relative_to(COMPONENT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = metadata(root, args.tag)
    if args.notes:
        args.notes.write_text(result["notes"])
    if args.archive:
        package(root, args.archive)
    output = (
        f"version={result['version']}\nprerelease={str(result['prerelease']).lower()}\n"
    )
    if path := os.environ.get("GITHUB_OUTPUT"):
        with Path(path).open("a") as stream:
            stream.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()
