#     Copyright 2025, Kay Hayen, mailto:kay.hayen@gmail.com find license text at end of file


""" Caching of generated C code.

This module implements caching of Nuitka's generated C source files to avoid
regenerating C code for unchanged modules during incremental builds.

Pipeline:
    Python source ƒ+' AST ƒ+' Nuitka Tree ƒ+' [C Generation] ƒ+' .c files ƒ+' C compilation

When recompiling after source changes, Nuitka regenerates C code for all modules.
This cache stores generated .c files keyed by source hash, allowing reuse when
source is unchanged.
"""

import os
import shutil

from nuitka.PythonVersions import python_version
from nuitka.plugins.Hooks import getPluginsCacheContributionValues
from nuitka.Tracing import general
from nuitka.utils.AppDirs import getCacheDir
from nuitka.utils.Hashing import Hash
from nuitka.Version import version_string

# Bump this when the cache format or key inputs change.
_cache_format_version = 1

# Cache statistics
_cache_hits = 0
_cache_misses = 0


def _getCacheDir():
    """Get the directory for C code caching."""
    cache_dir = getCacheDir("c-code-cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir


def _makeSourceHash(module):
    """Create a hash of module source code for cache key.

    The hash includes:
    - Module source code
    - Nuitka version
    - Python version
    - Module full name

    This ensures cache invalidation when any relevant input changes.
    """
    hash_value = Hash()

    # Hash module source code
    source_filename = module.getCompileTimeFilename()
    try:
        hash_value.updateFromFile(source_filename)
    except OSError:
        # If we can't read source, can't cache
        return None

    # Hash cache format + Nuitka version (invalidate on upgrade or format change)
    hash_value.updateFromValues(_cache_format_version, version_string)

    # Hash Python version (invalidate on Python upgrade)
    hash_value.updateFromValues(python_version)

    # Hash module full name (to avoid collisions)
    full_name = module.getFullName()
    hash_value.updateFromValues(full_name.asString())

    # Plugins may influence generated C code for this module.
    hash_value.updateFromValues(*getPluginsCacheContributionValues(full_name))

    return hash_value.asHexDigest()


def _getCacheFilename(cache_hash, extension):
    """Get the cache filename for a given hash and extension."""
    cache_dir = _getCacheDir()
    return os.path.join(cache_dir, cache_hash + "." + extension)


def getCachedCCode(module, c_output_filename):
    """Retrieve cached C code for a module.

    Args:
        module: The module object
        c_output_filename: Where to write the cached .c file

    Returns:
        True if cache hit and files restored, False otherwise
    """
    global _cache_hits, _cache_misses

    cache_hash = _makeSourceHash(module)
    if cache_hash is None:
        _cache_misses += 1
        return False

    try:
        cached_c_file = _getCacheFilename(cache_hash, "c")

        if not os.path.isfile(cached_c_file):
            _cache_misses += 1
            return False

        # Copy cached .c file
        shutil.copy2(cached_c_file, c_output_filename)

        # Copy cached .const file if it exists
        cached_const_file = _getCacheFilename(cache_hash, "const")
        const_output_filename = c_output_filename.replace(".c", ".const")
        if os.path.isfile(cached_const_file):
            shutil.copy2(cached_const_file, const_output_filename)

        _cache_hits += 1
        return True

    except (OSError, IOError):
        # On any error, treat as cache miss
        _cache_misses += 1
        return False


def writeCachedCCode(module, c_source_filename):
    """Write C code to cache.

    Args:
        module: The module object
        c_source_filename: The generated .c file to cache
    """
    cache_hash = _makeSourceHash(module)
    if cache_hash is None:
        return

    try:
        # Cache the .c file
        cached_c_file = _getCacheFilename(cache_hash, "c")
        shutil.copy2(c_source_filename, cached_c_file)

        # Cache the .const file if it exists
        const_source_filename = c_source_filename.replace(".c", ".const")
        if os.path.isfile(const_source_filename):
            cached_const_file = _getCacheFilename(cache_hash, "const")
            shutil.copy2(const_source_filename, cached_const_file)

    except OSError as e:
        # Don't let caching failures break compilation, but report them.
        general.warning("Failed to write C code cache entry: %s" % e)


def getCacheStatistics():
    """Get cache hit/miss statistics."""
    return {
        "hits": _cache_hits,
        "misses": _cache_misses,
        "total": _cache_hits + _cache_misses,
        "hit_rate": (
            _cache_hits / (_cache_hits + _cache_misses)
            if (_cache_hits + _cache_misses) > 0
            else 0.0
        ),
    }


def reportCacheStatistics():
    """Report cache statistics to user."""
    stats = getCacheStatistics()

    if stats["total"] == 0:
        return

    general.info(
        "C code cache: %d hits, %d misses (%.1f%% hit rate)"
        % (stats["hits"], stats["misses"], stats["hit_rate"] * 100)
    )


#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
