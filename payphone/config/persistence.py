"""Anchored private state and durable JSON replacement shared by phone systems."""
import json
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def state_directory() -> Path:
    """Return the deployment state directory, independent of the current directory."""
    configured = os.environ.get("PAYPHONE_STATE_DIR")
    path = Path(configured).expanduser() if configured else REPOSITORY_ROOT / ".payphone_state"
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    return path.resolve()


def atomic_write_json(path: Path, data: dict, *,
                      commit: Optional[Callable[[Callable[[], None]], None]] = None) -> None:
    """Validate JSON before touching disk; fsync a private file then atomically replace.

    Optional commit runs the replacement closure under a final authorization guard,
    after staging/fsync, so cancellation during staging can still deny replacement.
    Errors propagate. A directory fsync error can occur *after* replacement, so callers
    must report an uncertain durability outcome rather than claiming a successful save.
    """
    if not isinstance(data, dict):
        raise ValueError("State must be a JSON object")
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        def replace() -> None:
            os.replace(temporary, path)

        if commit is None:
            replace()
        else:
            commit(replace)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
