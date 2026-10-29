"""Shared filesystem, subprocess, and timestamp helpers; no shell interpolation."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, value):
    """Replace atomically so interrupted writers cannot leave a half JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def command(args: list[str], cwd: Path, timeout: float = 120, check=True) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=max(.1, timeout), shell=False)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} {args[1] if len(args)>1 else ""} failed: {result.stderr or result.stdout}')
    return result.stdout.strip()


def log(message: str):
    print(f'[{now()}] {message}', flush=True)

