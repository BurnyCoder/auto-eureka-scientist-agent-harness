"""Exercise real subprocess pipes, cancellation, and lossless event capture."""
import asyncio
import json
import sys
import time

from auto_eureka_scientist.execution import execute


def test_long_unicode_output_and_both_pipes(tmp_path):
    script = tmp_path / "fake cli.py"
    script.write_text(
        "import sys,json\n"
        "p=sys.stdin.read()\n"
        "print(json.dumps({'type':'message','text':p+'ž'*100000}),flush=True)\n"
        "print('diagnostic'*20000,file=sys.stderr,flush=True)\n",
        encoding="utf-8",
    )
    result = asyncio.run(execute([sys.executable, str(script)], "hello $() `x`", tmp_path,
                                tmp_path / "logs", time.monotonic() + 15, lambda: False,
                                echo=False))
    assert result.returncode == 0
    assert json.loads((tmp_path / "logs/stdout.jsonl").read_text())['text'].endswith('ž'*100000)
    assert (tmp_path / "logs/stderr.log").read_text().count('diagnostic') == 20000
    assert (tmp_path / "logs/prompt.txt").read_text() == "hello $() `x`"


def test_deadline_and_stop_are_distinct(tmp_path):
    for reason, cancel in [("budget_exhausted", lambda: False), ("stopped", lambda: True)]:
        result = asyncio.run(execute([sys.executable, '-c', 'import time; time.sleep(60)'], '',
                                    tmp_path, tmp_path / reason, time.monotonic() + .2,
                                    cancel, echo=False))
        assert result.reason == reason
        assert result.returncode != 0

