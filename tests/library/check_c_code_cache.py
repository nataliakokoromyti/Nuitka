#!/usr/bin/env python
#     Copyright 2025, Kay Hayen, mailto:kay.hayen@gmail.com find license text at end of file


"""Check C code cache hit/miss behavior with a warm rebuild."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_compile(source_path, output_dir, cache_dir):
    env = os.environ.copy()
    env["NUITKA_CACHE_DIR_C_CODE_CACHE"] = str(cache_dir)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nuitka",
            "--nofollow-imports",
            "--output-dir=%s" % output_dir,
            str(source_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])

    match = re.search(r"C code cache: (\d+) hits, (\d+) misses", result.stderr)
    if not match:
        raise RuntimeError("Missing C code cache stats in Nuitka output.")

    hits = int(match.group(1))
    misses = int(match.group(2))
    return hits, misses


def _clear_build_artifacts(source_path, output_dir):
    build_dir = Path(output_dir) / (Path(source_path).stem + ".build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    for suffix in (".exe", ".bin"):
        candidate = Path(output_dir) / (Path(source_path).stem + suffix)
        if candidate.exists():
            candidate.unlink()


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        cache_dir = temp_dir / "cache"
        output_dir = temp_dir / "out"
        output_dir.mkdir(parents=True, exist_ok=True)

        source_path = temp_dir / "cache_test.py"
        source_path.write_text("print('cache test')\n", encoding="utf-8")

        # Cold compile should report misses only.
        hits, misses = _run_compile(source_path, output_dir, cache_dir)
        if hits != 0 or misses == 0:
            raise SystemExit(
                "Expected cold run to have 0 hits and >0 misses, got %d/%d."
                % (hits, misses)
            )

        # Warm compile should report hits only.
        _clear_build_artifacts(source_path, output_dir)
        hits, misses = _run_compile(source_path, output_dir, cache_dir)
        if hits == 0 or misses != 0:
            raise SystemExit(
                "Expected warm run to have >0 hits and 0 misses, got %d/%d."
                % (hits, misses)
            )

    print("OK: C code cache hit/miss behavior verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
