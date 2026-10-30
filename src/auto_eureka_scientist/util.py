"""Shared filesystem, subprocess, and timestamp helpers; no shell interpolation."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import time


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def digest(path: Path) -> str:
    """Stream large checkpoints using https://docs.python.org/3/library/hashlib.html#hashlib.file_digest."""
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, value):
    """Replace atomically so interrupted writers cannot leave a half JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def command(args: list[str], cwd: Path, timeout: float = 120, check=True, cancelled=None,
            emit=None, termination_grace=2) -> str:
    """Drain both pipes with communicate; cancellation also covers publication tools.

    Retrying communicate after TimeoutExpired preserves captured bytes:
    https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
    """
    if cancelled and (reason:=cancelled()):
        raise InterruptedError(reason if isinstance(reason,str) else 'stop requested')
    if timeout <= 0:
        raise InterruptedError('time budget exhausted')
    deadline = time.monotonic()+timeout
    process = subprocess.Popen(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               text=True,encoding='utf-8',errors='replace',shell=False)
    offsets={'stdout':0,'stderr':0}
    def publish(channel,value):
        if not emit or value is None: return
        if isinstance(value,bytes): value=value.decode('utf-8',errors='replace')
        addition=value[offsets[channel]:]
        if addition: emit(channel,addition)
        offsets[channel]=len(value)
    try:
        while True:
            if cancelled and (reason:=cancelled()):
                raise InterruptedError(reason if isinstance(reason,str) else 'stop requested')
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(args,timeout)
            try:
                stdout,stderr = process.communicate(timeout=min(.2,remaining))
                break
            except subprocess.TimeoutExpired as partial:
                publish('stdout',partial.stdout)
                publish('stderr',partial.stderr)
    except BaseException:
        from .execution import terminate_tree
        terminate_tree(process.pid,termination_grace)
        process.communicate()
        raise
    publish('stdout',stdout)
    publish('stderr',stderr)
    if check and process.returncode:
        raise RuntimeError(f'{args[0]} {args[1] if len(args)>1 else ""} failed: {stderr or stdout}')
    return stdout.strip()


def log(message: str):
    print(f'[{now()}] {message}', flush=True)

