#!/usr/bin/env python
"""Benchmark C code cache using only C code generation time.

This uses --devel-profile-compilation and reads the code-generation profile to
avoid noise from C compilation and linking.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def clear_build_directory():
    """Clear the build directory."""
    build_dir = Path("test_caching.build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    result_file = (
        Path("test_caching.exe") if os.name == "nt" else Path("test_caching.bin")
    )
    if result_file.exists():
        result_file.unlink()


def clear_c_code_cache():
    """Clear the C code cache."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent))

    from nuitka.utils.AppDirs import getCacheDir

    cache_dir = Path(getCacheDir("c-code-cache"))
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"Cleared C code cache: {cache_dir}")


def _profile_total_seconds(profile_path):
    import pstats

    stats = pstats.Stats(str(profile_path))
    return stats.total_tt


def run_codegen_profile():
    """Run Nuitka with compile-time profiling and return codegen seconds."""
    with tempfile.TemporaryDirectory() as output_dir:
        result = subprocess.run(
            [
                "python",
                "-m",
                "nuitka",
                "--devel-profile-compilation",
                "--output-dir=%s" % output_dir,
                "test_caching.py",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("Compilation failed!")
            print(result.stderr)
            return None, None, None

        profile_path = Path(output_dir) / "code-generation.prof"
        if not profile_path.exists():
            print("Compilation finished but profiling output is missing.")
            print(result.stderr)
            return None, None, None

        codegen_seconds = _profile_total_seconds(profile_path)

        ast_cache_line = None
        c_code_cache_line = None
        for line in result.stderr.split("\n"):
            if "Source AST cache:" in line:
                ast_cache_line = line
            if "C code cache:" in line:
                c_code_cache_line = line

        return codegen_seconds, ast_cache_line, c_code_cache_line


def main():
    print("=" * 70)
    print("C Code Cache - CODE GENERATION ONLY")
    print("=" * 70)

    print("\nClearing build directory and caches...")
    clear_build_directory()
    clear_c_code_cache()

    print("\n[1/2] Cold cache compilation (profiling code generation)...")
    cold_time, cold_ast, cold_c = run_codegen_profile()
    if cold_time is None:
        print("ERROR: Cold cache compilation failed")
        return 1

    print(f"  Codegen time: {cold_time:.3f}s")
    if cold_ast:
        print(f"  {cold_ast}")
    if cold_c:
        print(f"  {cold_c}")

    clear_build_directory()

    print("\n[2/2] Warm cache compilation (profiling code generation)...")
    warm_time, warm_ast, warm_c = run_codegen_profile()
    if warm_time is None:
        print("ERROR: Warm cache compilation failed")
        return 1

    print(f"  Codegen time: {warm_time:.3f}s")
    if warm_ast:
        print(f"  {warm_ast}")
    if warm_c:
        print(f"  {warm_c}")

    print("\n" + "=" * 70)
    print("RESULTS (C CODE GENERATION ONLY)")
    print("=" * 70)

    saved = cold_time - warm_time
    percent = (saved / cold_time * 100.0) if cold_time else 0.0

    print(f"\nCold codegen:  {cold_time:.3f}s")
    print(f"Warm codegen:  {warm_time:.3f}s")
    print(f"Time saved:    {saved:.3f}s ({percent:.1f}% faster)")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
