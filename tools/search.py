"""Workspace code search tool."""

import shutil
import subprocess

from .filesystem import IGNORED_PATH_NAMES


def search(root, path_policy, args):
    pattern = str(args.get("pattern", "")).strip()
    if not pattern:
        raise ValueError("pattern must not be empty")
    path = path_policy.resolve(args.get("path", "."))

    if shutil.which("rg"):
        result = subprocess.run(
            ["rg", "-n", "--smart-case", "--max-count", "200", pattern, str(path)],
            cwd=root,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or result.stderr.strip() or "(no matches)"

    matches = []
    files = (
        [path]
        if path.is_file()
        else [
            item
            for item in path.rglob("*")
            if item.is_file()
            and not any(part in IGNORED_PATH_NAMES for part in item.relative_to(root).parts)
        ]
    )
    for file_path in files:
        for number, line in enumerate(
            file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if pattern.lower() in line.lower():
                matches.append(f"{file_path.relative_to(root)}:{number}:{line}")
                if len(matches) >= 200:
                    return "\n".join(matches)
    return "\n".join(matches) or "(no matches)"
