#!/usr/bin/env python
"""Correctness check for C code cache hit/miss behavior."""

import os
import re
import shutil
import subprocess
import sys
import tempfile


try:
    unicode  # pylint: disable=used-before-assignment
except NameError:
    unicode = str


def _toText(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _run_compile(source_path, output_dir, cache_dir):
    env = os.environ.copy()
    env["NUITKA_CACHE_DIR_C_CODE_CACHE"] = cache_dir

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nuitka",
            "--nofollow-imports",
            "--output-dir=%s" % output_dir,
            source_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    stdout, stderr = process.communicate()
    stdout = _toText(stdout)
    stderr = _toText(stderr)

    if process.returncode != 0:
        raise RuntimeError(stderr[-2000:])

    match = re.search(r"C code cache:\s+(\d+)\s+hits,\s+(\d+)\s+misses", stderr)
    if not match:
        raise RuntimeError("Cache stats not found in output.")

    return int(match.group(1)), int(match.group(2))


def main():
    temp_dir = tempfile.mkdtemp()
    try:
        source_path = os.path.join(temp_dir, "cache_test.py")
        output_dir = os.path.join(temp_dir, "out")
        cache_dir = os.path.join(temp_dir, "cache")

        with open(source_path, "w") as f:
            f.write("print('ok')\n")

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
    finally:
        shutil.rmtree(temp_dir)

    print("OK: C code cache hit/miss behavior verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
