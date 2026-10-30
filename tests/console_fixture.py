"""Offline browser acceptance server with real owned workers and fake CLI transport.

Run: uv run --extra ui python tests/console_fixture.py --project tmp/console --serve
Only this test entry point replaces inference/publication; production has no fake flag.
"""
import argparse
import asyncio
from pathlib import Path
import sys

from auto_eureka_scientist import engine, operator, phases
from auto_eureka_scientist.config import RunConfig
from auto_eureka_scientist.state import Store
from auto_eureka_scientist.web.server import create_app
from test_pipeline import FakePublisher


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--port',type=int,default=8776)
    parser.add_argument('--run-id')
    parser.add_argument('--maintenance',action='store_true')
    args=parser.parse_args()
    project=args.project.resolve()
    if args.serve:
        import uvicorn
        app=create_app(project,RunConfig(str(project),'claude',publish=False,max_loops=1,
            pause_before=['preregister'],gpu_monitor=False,open_browser=False))
        app.state.service.worker_command=[sys.executable,str(Path(__file__).resolve())]
        uvicorn.run(app,host='127.0.0.1',port=args.port)
        return
    def fake_invocation(config,logs,env,**kwargs):
        return [sys.executable,str(Path(__file__).with_name('fake_cli.py')),
                *(['--codex-fixture'] if config.backend=='codex' else [])],None
    engine.invocation=operator.invocation=fake_invocation
    phases.retrieve_sources=lambda cycle:[]
    engine.commit=lambda *args:'offline-fixture'
    engine.render=lambda *args,**kwargs:{}
    publisher=FakePublisher(); publisher.fail_once=False
    store=Store(project)
    try: asyncio.run(engine.Controller(store,args.run_id,publisher=publisher).run(maintenance=args.maintenance))
    finally: store.close()


if __name__=='__main__': main()
