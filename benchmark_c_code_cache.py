#!/usr/bin/env python
"""Benchmark C code cache performance improvement.

Measures the time savings from caching generated C code for incremental builds.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path


def clear_build_directory():
    """Clear the build directory."""
    build_dir = Path("test_caching.build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    result_file = Path("test_caching.exe") if os.name == "nt" else Path("test_caching.bin")
    if result_file.exists():
        result_file.unlink()


def clear_c_code_cache():
    """Clear the C code cache."""
    # Import here to avoid issues if nuitka not in path
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from nuitka.utils.AppDirs import getCacheDir

    cache_dir = Path(getCacheDir("c-code-cache"))
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"Cleared C code cache: {cache_dir}")


def run_compilation():
    """Run Nuitka compilation and measure time."""
    start = time.perf_counter()

    result = subprocess.run(
        ["python", "-m", "nuitka", "test_caching.py"],
        capture_output=True,
        text=True,
    )

    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print("Compilation failed!")
        print(result.stderr)
        return None, None, None

    # Parse cache statistics from output
    ast_cache_line = None
    c_code_cache_line = None

    for line in result.stderr.split("\n"):
        if "Source AST cache:" in line:
            ast_cache_line = line
        if "C code cache:" in line:
            c_code_cache_line = line

    return elapsed, ast_cache_line, c_code_cache_line


def main():
    """Run C code cache benchmark."""
    print("=" * 70)
    print("C Code Cache Performance Benchmark")
    print("=" * 70)

    # Clear everything
    print("\nClearing build directory and caches...")
    clear_build_directory()
    clear_c_code_cache()

    # First run (cold cache)
    print("\n[1/2] Cold cache compilation (no C code cache)...")
    cold_time, cold_ast, cold_c = run_compilation()

    if cold_time is None:
        print("ERROR: Cold cache compilation failed")
        return 1

    print(f"  Time: {cold_time:.2f}s")
    if cold_ast:
        print(f"  {cold_ast}")
    if cold_c:
        print(f"  {cold_c}")

    # Clean build output but keep cache
    clear_build_directory()

    # Second run (warm cache)
    print("\n[2/2] Warm cache compilation (C code cache enabled)...")
    warm_time, warm_ast, warm_c = run_compilation()

    if warm_time is None:
        print("ERROR: Warm cache compilation failed")
        return 1

    print(f"  Time: {warm_time:.2f}s")
    if warm_ast:
        print(f"  {warm_ast}")
    if warm_c:
        print(f"  {warm_c}")

    # Analysis
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    time_saved = cold_time - warm_time
    speedup_percent = (time_saved / cold_time * 100) if cold_time > 0 else 0

    print(f"\nCold cache:  {cold_time:.2f}s")
    print(f"Warm cache:  {warm_time:.2f}s")
    print(f"Time saved:  {time_saved:.2f}s ({speedup_percent:.1f}% faster)")

    print("\n" + "=" * 70)
    print("BREAKDOWN")
    print("=" * 70)

    print("\nCold cache (no caching):")
    if cold_ast:
        print(f"  AST: {cold_ast.split(':', 1)[1].strip()}")
    if cold_c:
        print(f"  C code: {cold_c.split(':', 1)[1].strip()}")

    print("\nWarm cache (both caches active):")
    if warm_ast:
        print(f"  AST: {warm_ast.split(':', 1)[1].strip()}")
    if warm_c:
        print(f"  C code: {warm_c.split(':', 1)[1].strip()}")

    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    if speedup_percent > 20:
        verdict = "SIGNIFICANT - C code caching provides substantial speedup"
    elif speedup_percent > 10:
        verdict = "MODERATE - C code caching provides noticeable speedup"
    elif speedup_percent > 5:
        verdict = "SMALL - C code caching provides minor speedup"
    else:
        verdict = "MINIMAL - C code caching benefit is marginal"

    print(f"\n{verdict}")
    print(f"\nFor single-module projects, C code caching saves ~{time_saved:.1f}s")
    print(f"For projects with N modules, savings scale linearly (N * {time_saved:.1f}s)")
    print(f"\nExample: 50-module project = ~{time_saved * 50:.0f}s saved on incremental builds")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
