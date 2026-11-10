"""Build the native error model with the pip-distributed Zig compiler."""
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from importlib.metadata import version

from selene_core.headers import get_include_directory


def build_native() -> Path:
    if platform.system() != "Linux":
        raise RuntimeError("faultline-qec v0.1 supports Linux (including WSL) only")
    source = Path(__file__).parent / "native" / "schedule.c"
    include = get_include_directory()
    digest = hashlib.sha256(source.read_bytes())
    for name in ("error_model.h", "runtime.h", "core_types.h"):
        digest.update((include / "selene" / name).read_bytes())
    digest.update((platform.machine() + version("ziglang")).encode())
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "faultline-qec" / digest.hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "libfaultline_schedule.so"
    if not target.exists():
        fd, temporary = tempfile.mkstemp(suffix=".so", dir=cache)
        os.close(fd)
        try:
            subprocess.run([sys.executable, "-m", "ziglang", "cc", "-shared", "-fPIC",
                            "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(include),
                            str(source), "-o", temporary], check=True, capture_output=True, text=True)
            os.replace(temporary, target)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Native build failed:\n{exc.stderr}") from exc
        finally:
            Path(temporary).unlink(missing_ok=True)
    return target
