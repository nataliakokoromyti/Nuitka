#!/usr/bin/env python
"""Benchmark with REAL multi-file projects to show actual scaling."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def clear_caches():
    """Clear Nuitka caches."""
    sys.path.insert(0, str(Path(__file__).parent))
    from nuitka.utils.AppDirs import getCacheDir

    for cache_name in ["c-code-cache", "source-cache"]:
        cache_dir = Path(getCacheDir(cache_name))
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


def create_multimodule_project(temp_dir, num_modules):
    """Create a project with N Python modules using REAL code patterns."""
    project_dir = Path(temp_dir) / "realproject"
    project_dir.mkdir(exist_ok=True)

    # Create package __init__.py
    (project_dir / "__init__.py").write_text("")

    # Create N modules with REAL stdlib code
    for i in range(num_modules):
        code = f'''"""Module {i} - uses real Python stdlib."""

import json
import os
import sys
import datetime
import pathlib
import hashlib

class DataProcessor{i}:
    """Process data using stdlib."""

    def __init__(self):
        self.data = {{}}
        self.timestamp = datetime.datetime.now()

    def process(self, input_data):
        """Process input using json, hashlib, pathlib."""
        # Hash the input
        h = hashlib.sha256(str(input_data).encode()).hexdigest()

        # Create path
        p = pathlib.Path('.') / f'output_{{h[:8]}}.json'

        # Build result
        result = {{
            'module_id': {i},
            'hash': h,
            'path': str(p),
            'timestamp': str(self.timestamp),
            'input': input_data,
        }}

        self.data = result
        return json.dumps(result)

    def validate(self):
        """Validate data."""
        if not self.data:
            return False
        required = ['module_id', 'hash', 'timestamp']
        return all(k in self.data for k in required)

def process_data_{i}(data):
    """Process data with module {i}."""
    processor = DataProcessor{i}()
    result = processor.process(data)
    if processor.validate():
        return result
    return None
'''
        (project_dir / f"module{i}.py").write_text(code)

    # Create main file that imports all modules
    imports = "\n".join([f"from realproject import module{i}" for i in range(num_modules)])
    uses = "\n    ".join([f"result = module{i}.process_data_{i}({{'{i}': {i}}})" for i in range(num_modules)])

    main_code = f'''"""Main file that uses all modules."""

{imports}

def main():
    """Use all modules."""
    {uses}
    print("Processed {num_modules} modules")
    return 0

if __name__ == '__main__':
    main()
'''

    main_file = Path(temp_dir) / "main.py"
    main_file.write_text(main_code)

    return main_file


def compile_and_time(main_file):
    """Compile and return elapsed time + cache stats."""
    start = time.perf_counter()

    result = subprocess.run(
        ["python", "-m", "nuitka", "--follow-imports", str(main_file)],
        capture_output=True,
        text=True,
    )

    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print(f"COMPILATION FAILED:")
        print(result.stderr[-1000:])
        return None, None, None

    # Extract cache stats
    c_cache = None
    for line in result.stderr.split("\n"):
        if "C code cache:" in line:
            c_cache = line.strip()
            break

    return elapsed, c_cache, result.stderr


def benchmark_multimodule(num_modules):
    """Benchmark with N real Python modules."""
    print(f"\n{'='*70}")
    print(f"Testing with {num_modules} Python modules (REAL stdlib code)")
    print(f"{'='*70}")

    temp_dir = tempfile.mkdtemp()

    try:
        # Create project
        main_file = create_multimodule_project(temp_dir, num_modules)

        # Cold compilation
        print(f"\n[1] COLD CACHE - Generate C for {num_modules} modules")
        clear_caches()

        # Clear build
        build_dir = main_file.parent / "main.build"
        if build_dir.exists():
            shutil.rmtree(build_dir)

        cold_time, cold_cache, _ = compile_and_time(main_file)
        if cold_time is None:
            return None

        print(f"  Total time: {cold_time:.2f}s")
        print(f"  {cold_cache}")

        # Warm compilation
        print(f"\n[2] WARM CACHE - Reuse cached C for {num_modules} modules")

        # Clear build but keep cache
        if build_dir.exists():
            shutil.rmtree(build_dir)

        warm_time, warm_cache, _ = compile_and_time(main_file)
        if warm_time is None:
            return None

        print(f"  Total time: {warm_time:.2f}s")
        print(f"  {warm_cache}")

        # Results
        time_saved = cold_time - warm_time
        percent_faster = (time_saved / cold_time * 100) if cold_time > 0 else 0

        print(f"\n{'='*70}")
        print(f"RESULTS for {num_modules} modules")
        print(f"{'='*70}")
        print(f"Cold cache:  {cold_time:.2f}s")
        print(f"Warm cache:  {warm_time:.2f}s")
        print(f"Time saved:  {time_saved:.2f}s ({percent_faster:.1f}% faster)")

        return {
            'num_modules': num_modules,
            'cold_time': cold_time,
            'warm_time': warm_time,
            'time_saved': time_saved,
            'percent_faster': percent_faster,
        }

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run benchmarks with different module counts."""
    print("="*70)
    print("REAL MULTI-MODULE PERFORMANCE BENCHMARK")
    print("Testing with REAL Python code (stdlib usage)")
    print("="*70)

    # Test different sizes
    module_counts = [10, 25, 50]

    results = []
    for count in module_counts:
        result = benchmark_multimodule(count)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*70)
    print("FINAL RESULTS - REAL CODE, REAL MEASUREMENTS")
    print("="*70)

    for r in results:
        print(f"\n{r['num_modules']} modules:")
        print(f"  Cold:  {r['cold_time']:.2f}s")
        print(f"  Warm:  {r['warm_time']:.2f}s")
        print(f"  Saved: {r['time_saved']:.2f}s ({r['percent_faster']:.1f}% faster)")

    print("\n" + "="*70)
    print("SCALING ANALYSIS")
    print("="*70)

    if len(results) >= 2:
        # Calculate per-module savings
        for r in results:
            per_module = r['time_saved'] / r['num_modules']
            print(f"{r['num_modules']} modules: ~{per_module*1000:.1f}ms saved per module")

    return 0


if __name__ == "__main__":
    sys.exit(main())
