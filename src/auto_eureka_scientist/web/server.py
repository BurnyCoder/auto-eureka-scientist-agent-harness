"""Loopback-only HTTP controls and replayable SSE, with no browser-owned execution.

https://fastapi.tiangolo.com/tutorial/server-sent-events/
https://fastapi.tiangolo.com/advanced/events/
"""
import asyncio
from contextlib import asynccontextmanager
from importlib.resources import files
import json
from pathlib import Path
import secrets
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from ..config import RunConfig
from ..policy import policy_hash
from ..settings import schema, validate, resolve_settings, import_settings, save_preset, load_preset
from ..util import read_json, write_json, command, now
from ..workspace import initialize
from .service import Service


class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Spec(Input):
    text: str = Field(min_length=1)
    title: str = ''
    id: str | None = None
    enabled: bool = True
    settings: dict = Field(default_factory=dict,json_schema_extra=schema(partial=True,scope='cycle'))
    parameters: dict = Field(default_factory=dict)
    revision: int | None = None


class RunInput(Input):
    settings: dict = Field(default_factory=dict,json_schema_extra=schema(partial=True))
    specs: list[Spec] = Field(min_length=1)
    preset: str | None = None
    start: bool = True
    request_id: str = Field(default_factory=lambda:uuid.uuid4().hex)


class PatchInput(Input):
    settings: dict = Field(json_schema_extra=schema(partial=True))
    revision: int


class ActionInput(Input):
    kind: str
    payload: dict = Field(default_factory=dict)
    request_id: str = Field(default_factory=lambda:uuid.uuid4().hex)


class MessageInput(Input):
    text: str = Field(min_length=1)
    kind: str = 'steer'
    scope: str = 'next_invocation'
    delivery: str = 'next_turn'
    request_id: str = Field(default_factory=lambda:uuid.uuid4().hex)


def create_app(project: Path,launch_config=None,*,launch_overrides=None,launch_preset=None):
    project=Path(project).resolve()
    service=Service(project)
    token=secrets.token_urlsafe(32)
    launch_config=launch_config or RunConfig(str(project),'claude',max_loops=1,mode='continuous')
    assets=files('auto_eureka_scientist').joinpath('resources','console')

    def new_config(explicit=None,preset_name=None):
        """Read current project defaults while preserving environment and explicit precedence."""
        path=project/'.eureka/settings.json'
        defaults={**launch_config.to_dict(),**(import_settings(read_json(path)) if path.exists() else {})}
        selected=preset_name or launch_preset
        preset=load_preset(project,selected) if selected else {}
        return RunConfig(**resolve_settings(project,{**(launch_overrides or {}),**(explicit or {})},
            defaults=defaults,preset=preset))

    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(service.close)

    app=FastAPI(title='Auto Eureka research console',lifespan=lifespan)
    app.state.service=service

    @app.middleware('http')
    async def local_requests(request,call_next):
        if request.url.hostname not in ('127.0.0.1','localhost','::1'):
            return JSONResponse({'error':'Loopback host required'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if (origin and origin!=str(request.base_url).rstrip('/')) or not secrets.compare_digest(request.headers.get('x-eureka-token',''),token):
                return JSONResponse({'error':'Same-origin request token required'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.exception_handler(ValueError)
    async def bad_request(request,exc):
        return JSONResponse({'error':str(exc)},status_code=409 if 'conflict' in str(exc) else 400)

    @app.get('/')
    def index():
        return Response(assets.joinpath('index.html').read_text(encoding='utf-8'),media_type='text/html',
            headers={'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"})

    @app.get('/assets/{name}')
    def asset(name:str):
        if name not in ('app.js','style.css'): raise ValueError('Unknown asset')
        return Response(assets.joinpath(name).read_text(encoding='utf-8'),media_type='text/javascript' if name.endswith('.js') else 'text/css')

    @app.get('/api/meta')
    def meta():
        from ..contracts import PHASES
        return {'token':token,'schema':schema(),'defaults':new_config().to_dict(),'phases':PHASES,'project':str(project)}

    @app.get('/api/runs')
    def runs(): return service.store.list_runs()

    @app.post('/api/runs')
    def create(body:RunInput):
        with service.lock:
            if 'project' in body.settings and Path(body.settings['project']).resolve()!=project:
                raise ValueError('This server is attached to another project; relaunch with --project')
            with service.store.lock:
                saved=service.store.db.execute('SELECT run_id,payload FROM actions WHERE id=?',(body.request_id,)).fetchone()
            payload=body.model_dump_json()
            if saved:
                if saved['payload']!=payload: raise ValueError('Run request identity conflict')
                return {'id':saved['run_id']}
            config=new_config(body.settings,body.preset)
            entries=[s.model_dump(exclude_none=True) for s in body.specs]
            initialize(project,profile=config.profile,task=entries[0]['text'])
            run_id=service.store.create(config,entries[0]['text'],policy_hash())
            service.store.set_specs(run_id,entries)
            with service.store.lock,service.store.db:
                service.store.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?)',
                    (body.request_id,run_id,'create',payload,'applied',now(),'{}'))
            if body.start: service.launch(run_id)
            return {'id':run_id}

    @app.get('/api/runs/{run_id}')
    def snapshot(run_id:str): return service.snapshot(run_id)

    @app.get('/api/runs/{run_id}/settings')
    def effective_settings(run_id:str):
        snapshot=service.snapshot(run_id)
        return {'revision':snapshot['run']['revision'],'desired':snapshot['run']['config'],
                'effective':snapshot['effective_settings'],'history':snapshot['settings_changes']}

    @app.get('/api/runs/{run_id}/messages')
    def messages(run_id:str,limit:int=200):
        service.store.get(run_id)
        return service.store.messages(run_id,limit=min(max(limit,1),2000))

    @app.get('/api/runs/{run_id}/actions')
    def actions(run_id:str,limit:int=200):
        service.store.get(run_id)
        return service.store.actions(run_id,pending=False,limit=min(max(limit,1),2000))

    @app.get('/api/runs/{run_id}/specs')
    def queue(run_id:str):
        service.store.get(run_id)
        return service.store.specs(run_id)

    @app.get('/api/runs/{run_id}/events')
    def events(run_id:str,after:int=0,before:int|None=None,limit:int=200):
        service.store.get(run_id)
        return service.store.events(run_id,after=after,before=before,limit=limit)

    @app.get('/api/runs/{run_id}/stream',response_class=EventSourceResponse)
    async def stream(run_id:str,request:Request,after:int=0):
        service.store.get(run_id)
        cursor=max(after,int(request.headers.get('last-event-id') or 0))
        while not await request.is_disconnected():
            rows=await asyncio.to_thread(service.store.events,run_id,after=cursor,limit=200)
            for row in rows:
                cursor=row['id']
                yield ServerSentEvent(data=row,id=str(cursor),event='update')
            config=service.store.get(run_id)['config']
            await asyncio.sleep(config.get('stream_batch_ms',100)/1000)

    @app.patch('/api/runs/{run_id}/settings')
    def patch(run_id:str,body:PatchInput):
        result=service.store.patch_settings(run_id,body.settings,expected_revision=body.revision)
        restart={k:v for k,v in body.settings.items() if schema()['properties'][k]['x-apply']=='server restart'}
        if restart:
            path=project/'.eureka/settings.json'
            defaults=import_settings(read_json(path)) if path.exists() else {}
            write_json(path,{'schema_version':1,'settings':{**defaults,**restart}})
        return result

    @app.put('/api/runs/{run_id}/specs')
    def specs(run_id:str,body:list[Spec]):
        return service.store.set_specs(run_id,[s.model_dump(exclude_none=True) for s in body])

    @app.post('/api/runs/{run_id}/actions')
    def action(run_id:str,body:ActionInput):
        return service.action(run_id,body.kind,body.payload,body.request_id)

    @app.post('/api/runs/{run_id}/messages')
    def message(run_id:str,body:MessageInput):
        if body.delivery not in ('next_turn','interrupt_now'): raise ValueError('Unknown delivery timing')
        result=service.store.add_message(run_id,body.text,kind=body.kind,scope=body.scope,request_id=body.request_id)
        run=service.store.get(run_id)
        if result['status']=='queued' and body.delivery=='interrupt_now' and service.alive(run):
            service.store.enqueue_action(run_id,'interrupt',request_id=body.request_id+'-interrupt')
        if result['status']=='queued' and body.kind=='ask' and not service.alive(run): service.launch(run_id,maintenance=True)
        return result

    @app.get('/api/presets')
    def presets(): return [p.stem for p in (project/'.eureka/presets').glob('*.json')]

    @app.get('/api/presets/{name}')
    def preset(name:str): return {'schema_version':1,'settings':load_preset(project,name)}

    @app.put('/api/presets/{name}')
    def put_preset(name:str,document:dict):
        values=import_settings(document); save_preset(project,name,values)
        return {'saved':name}

    @app.put('/api/defaults')
    def put_defaults(document:dict):
        values=import_settings(document)
        values={k:v for k,v in values.items() if k not in ('project','executable')}
        write_json(project/'.eureka/settings.json',{'schema_version':1,'settings':values})
        return {'saved':True}

    @app.get('/api/runs/{run_id}/artifacts')
    def artifacts(run_id:str): return service.artifacts(run_id)

    @app.get('/api/file')
    def artifact(path:str):
        checked=service.safe_file(path)
        return FileResponse(checked,headers={'Content-Security-Policy':"sandbox; default-src 'none'",'Cache-Control':'no-store'})

    @app.get('/api/runs/{run_id}/logs/{attempt}/{channel}')
    def raw_log(run_id:str,attempt:int,channel:str):
        names={'stdout':'stdout.jsonl','stderr':'stderr.log','prompt':'prompt.txt'}
        if channel not in names: raise ValueError('Unknown log channel')
        record=next((a for a in service.store.attempts(run_id) if a['id']==attempt),None)
        if not record: raise ValueError('Unknown attempt')
        path=project/'.eureka'/run_id/f'{attempt:04d}-{record["phase"]}'/names[channel]
        if not path.is_file(): raise ValueError('Log not available')
        return FileResponse(path,media_type='text/plain',headers={'Cache-Control':'no-store'})

    @app.get('/api/diff')
    def diff():
        return {'status':command(['git','status','--short'],project,timeout=5),
                'diff':command(['git','diff','--no-ext-diff','--no-textconv'],project,timeout=5)}

    return app


def serve(project,config,*,overrides=None,preset=None):
    import uvicorn
    import threading
    import webbrowser
    if config.open_browser:
        timer=threading.Timer(1.0,lambda:webbrowser.open(f'http://127.0.0.1:{config.port}'))
        timer.daemon=True; timer.start()
    uvicorn.run(create_app(project,launch_overrides=overrides,launch_preset=preset),host='127.0.0.1',port=config.port)
