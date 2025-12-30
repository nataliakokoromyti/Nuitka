#!/usr/bin/env python
"""Run C code cache benchmarks multiple times and report medians."""

import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).parent


def _clear_caches_and_builds():
    sys.path.insert(0, str(REPO_ROOT))
    from nuitka.utils.AppDirs import getCacheDir

    def _remove_dir(path):
        if not path.exists():
            return
        for _ in range(3):
            try:
                shutil.rmtree(path)
                return
            except OSError:
                time.sleep(0.5)
        shutil.rmtree(path, ignore_errors=True)

    for cache_name in ("c-code-cache", "source-cache"):
        cache_dir = Path(getCacheDir(cache_name))
        _remove_dir(cache_dir)

    build_dir = REPO_ROOT / "test_caching.build"
    _remove_dir(build_dir)

    for filename in ("test_caching.exe", "test_caching.bin"):
        file_path = REPO_ROOT / filename
        if file_path.exists():
            file_path.unlink()


def _run_script(script_name, timeout_s=600):
    result = subprocess.run(
        ["python", script_name],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if result.returncode != 0:
        combined = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(
            "Benchmark failed: %s\n%s" % (script_name, combined[-4000:])
        )
    return result.stdout + "\n" + result.stderr


def _parse_c_code_cache(output):
    cold_match = re.search(r"Cold cache:\s+([0-9.]+)s", output)
    warm_match = re.search(r"Warm cache:\s+([0-9.]+)s", output)
    if not cold_match or not warm_match:
        raise ValueError("Failed to parse benchmark_c_code_cache output.")
    return float(cold_match.group(1)), float(warm_match.group(1))


def _parse_multifile_real(output):
    results = {}
    block_re = re.compile(r"^(\d+)\s+modules:\s*$", re.MULTILINE)
    for match in block_re.finditer(output):
        count = int(match.group(1))
        start = match.end()
        block = output[start:]
        cold_match = re.search(r"Cold:\s+([0-9.]+)s", block)
        warm_match = re.search(r"Warm:\s+([0-9.]+)s", block)
        if cold_match and warm_match:
            results[count] = (float(cold_match.group(1)), float(warm_match.group(1)))
    if not results:
        raise ValueError("Failed to parse benchmark_multifile_real output.")
    return results


def _parse_real_performance(output):
    results = {}
    header_re = re.compile(r"^(.+):\s*$", re.MULTILINE)
    for match in header_re.finditer(output):
        label = match.group(1).strip()
        if not label.endswith("stdlib modules"):
            continue
        start = match.end()
        block = output[start:]
        cold_match = re.search(r"Cold:\s+([0-9.]+)s", block)
        warm_match = re.search(r"Warm:\s+([0-9.]+)s", block)
        if cold_match and warm_match:
            results[label] = (float(cold_match.group(1)), float(warm_match.group(1)))
    if not results:
        raise ValueError("Failed to parse benchmark_real_performance output.")
    return results


def _median(values):
    return statistics.median(values)


def _run_benchmark(name, parser, runs):
    parsed_runs = []
    for i in range(runs):
        print("Starting %s run %d/%d..." % (name, i + 1, runs), flush=True)
        _clear_caches_and_builds()
        output = None
        for attempt in range(2):
            try:
                output = _run_script(name)
                break
            except RuntimeError as exc:
                if attempt == 0:
                    print("  Run failed, retrying once: %s" % exc, flush=True)
                    time.sleep(1.0)
                    _clear_caches_and_builds()
                else:
                    raise
        parsed_runs.append(parser(output))
        print("  Completed %s run %d/%d" % (name, i + 1, runs), flush=True)
    return parsed_runs


def _report_medians_c_code_cache(parsed_runs):
    cold_times = [item[0] for item in parsed_runs]
    warm_times = [item[1] for item in parsed_runs]
    cold_med = _median(cold_times)
    warm_med = _median(warm_times)
    saved = cold_med - warm_med
    percent = (saved / cold_med * 100.0) if cold_med else 0.0
    print("\nbenchmark_c_code_cache.py (median of %d runs)" % len(parsed_runs))
    print("  Cold:  %.2fs" % cold_med)
    print("  Warm:  %.2fs" % warm_med)
    print("  Saved: %.2fs (%.1f%% faster)" % (saved, percent))


def _report_medians_multifile(parsed_runs):
    module_counts = sorted(parsed_runs[0].keys())
    print("\nbenchmark_multifile_real.py (median of %d runs)" % len(parsed_runs))
    for count in module_counts:
        cold_times = [run[count][0] for run in parsed_runs]
        warm_times = [run[count][1] for run in parsed_runs]
        cold_med = _median(cold_times)
        warm_med = _median(warm_times)
        saved = cold_med - warm_med
        percent = (saved / cold_med * 100.0) if cold_med else 0.0
        print(
            "  %d modules: Cold %.2fs -> Warm %.2fs (%.1f%% faster)"
            % (count, cold_med, warm_med, percent)
        )


def _report_medians_real_performance(parsed_runs):
    labels = sorted(parsed_runs[0].keys())
    print("\nbenchmark_real_performance.py (median of %d runs)" % len(parsed_runs))
    for label in labels:
        cold_times = [run[label][0] for run in parsed_runs]
        warm_times = [run[label][1] for run in parsed_runs]
        cold_med = _median(cold_times)
        warm_med = _median(warm_times)
        saved = cold_med - warm_med
        percent = (saved / cold_med * 100.0) if cold_med else 0.0
        print("  %s:" % label)
        print("    Cold %.2fs -> Warm %.2fs (%.1f%% faster)" % (cold_med, warm_med, percent))


def main():
    runs = 3
    print("Running each benchmark %d times with cache clears." % runs)

    parsed_c_code = _run_benchmark("benchmark_c_code_cache.py", _parse_c_code_cache, runs)
    _report_medians_c_code_cache(parsed_c_code)

    parsed_multifile = _run_benchmark(
        "benchmark_multifile_real.py", _parse_multifile_real, runs
    )
    _report_medians_multifile(parsed_multifile)

    parsed_real_perf = _run_benchmark(
        "benchmark_real_performance.py", _parse_real_performance, runs
    )
    _report_medians_real_performance(parsed_real_perf)

    return 0


if __name__ == "__main__":
    sys.exit(main())
