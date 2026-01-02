#!/usr/bin/env python
"""Correctness check for C code cache hit/miss behavior."""

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

    if output_dir.exists():
        shutil.rmtree(output_dir)

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

    match = re.search(r"C code cache:\s+(\d+)\s+hits,\s+(\d+)\s+misses", result.stderr)
    if not match:
        raise RuntimeError("Cache stats not found in output.")

    return int(match.group(1)), int(match.group(2))


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        source_path = temp_dir / "cache_test.py"
        output_dir = temp_dir / "out"
        cache_dir = temp_dir / "cache"

        source_path.write_text("print('ok')\n", encoding="utf-8")

        hits, misses = _run_compile(source_path, output_dir, cache_dir)
        if hits != 0 or misses == 0:
            raise AssertionError(
                "Expected cold compile to be misses only, got hits=%d misses=%d"
                % (hits, misses)
            )

        hits, misses = _run_compile(source_path, output_dir, cache_dir)
        if hits == 0 or misses != 0:
            raise AssertionError(
                "Expected warm compile to be hits only, got hits=%d misses=%d"
                % (hits, misses)
            )

    print("OK: C code cache hit/miss behavior verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
