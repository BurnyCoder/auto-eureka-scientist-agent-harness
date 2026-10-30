"""Lossless asynchronous CLI transport with cancellation of owned process trees.

Sources: https://docs.python.org/3/library/asyncio-subprocess.html
and https://psutil.readthedocs.io/en/latest/#kill-process-tree
"""
import asyncio
import codecs
from dataclasses import dataclass
import os
from pathlib import Path
import time

import psutil

from .util import now


@dataclass
class Execution:
    returncode: int
    reason: str
    elapsed: float


def terminate_tree(pid: int, grace: float = 2):
    """Terminate only descendants of this invocation, not unrelated CLI sessions."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        parent.terminate()
        _, alive = psutil.wait_procs([*children,parent], timeout=grace)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass


async def execute(argv: list[str], prompt: str, cwd: Path, logs: Path, deadline: float,
                  cancelled, *, env=None, echo=True, emit=None, no_output_timeout=None,
                  termination_grace=2) -> Execution:
    logs.mkdir(parents=True, exist_ok=True)
    (logs / 'prompt.txt').write_text(prompt, encoding='utf-8')
    if echo:
        print(f'[{now()}] PROMPT\n{prompt}\n[{now()}] START {argv[0]}', flush=True)
    started = time.monotonic()
    last_output = started
    process = await asyncio.create_subprocess_exec(*argv, cwd=cwd, env=env,
                  stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                  stderr=asyncio.subprocess.PIPE, start_new_session=os.name != 'nt')
    reason = 'exited'
    if emit:
        emit('process.started',{'pid':process.pid,'created':psutil.Process(process.pid).create_time(),
             'command':argv[0],'logs':str(logs)})
    descendants = {}
    # Chunk reads avoid StreamReader.readline's default line-length limit on tool output.
    async def drain(reader, filename, channel):
        nonlocal last_output
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        with (logs / filename).open('wb') as raw, (logs / f'{channel}.transcript.log').open('w',encoding='utf-8') as transcript:
            while data := await reader.read(65536):
                raw.write(data)
                raw.flush()
                text = decoder.decode(data)
                last_output = time.monotonic()
                if emit: emit.stream(channel,text)
                transcript.write(f'[{now()}] {text}')
                transcript.flush()
                if echo:
                    print(text, end='', flush=True)
            tail = decoder.decode(b'', final=True)
            if tail:
                transcript.write(tail)
                if echo:
                    print(tail,end='',flush=True)

    async def feed():
        try:
            process.stdin.write(prompt.encode('utf-8'))
            await process.stdin.drain()
            process.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass

    readers = [asyncio.create_task(drain(process.stdout,'stdout.jsonl','stdout')),
               asyncio.create_task(drain(process.stderr,'stderr.log','stderr')),
               asyncio.create_task(feed())]
    try:
        while process.returncode is None or not all(reader.done() for reader in readers):
            try:
                for child in psutil.Process(process.pid).children(recursive=True):
                    if emit and child.pid not in descendants:
                        emit('process.child',{'pid':child.pid,'created':child.create_time()})
                    descendants[child.pid] = child
            except psutil.NoSuchProcess:
                pass
            cancellation = cancelled()
            if cancellation:
                reason = cancellation if isinstance(cancellation,str) else 'stopped'
                break
            if time.monotonic() >= deadline:
                reason = 'budget_exhausted'
                break
            if no_output_timeout and time.monotonic()-last_output >= no_output_timeout:
                reason = 'no_output_timeout'
                break
            await asyncio.sleep(.1)
        if process.returncode is None:
            await asyncio.to_thread(terminate_tree, process.pid, termination_grace)
        # A parent can exit while a background child still holds the output pipes.
        for child in descendants.values():
            try:
                if child.is_running():
                    child.kill()
            except psutil.NoSuchProcess:
                pass
        await process.wait()
        await asyncio.gather(*readers)
    except BaseException:
        await asyncio.to_thread(terminate_tree, process.pid, termination_grace)
        await process.wait()
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise
    if emit:
        emit.finish()
        emit('process.finished',{'pid':process.pid,'returncode':process.returncode,'reason':reason})
    return Execution(process.returncode, reason, time.monotonic()-started)

