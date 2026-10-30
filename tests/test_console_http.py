"""Real socket SSE replay and owned-worker shutdown, using the offline transport."""
from pathlib import Path
import socket
import sys
import threading
import time

import httpx
import pytest
import uvicorn

from auto_eureka_scientist.web.server import create_app


@pytest.fixture
def server(tmp_path):
    app=create_app(tmp_path)
    app.state.service.worker_command=[sys.executable,str(Path(__file__).with_name('console_fixture.py'))]
    listener=socket.socket();listener.bind(('127.0.0.1',0))
    host=uvicorn.Server(uvicorn.Config(app,log_level='warning'))
    thread=threading.Thread(target=lambda:host.run(sockets=[listener]),daemon=True)
    thread.start()
    deadline=time.monotonic()+10
    while not host.started:
        if time.monotonic()>deadline:raise RuntimeError('Local fixture server did not start')
        time.sleep(.01)
    with httpx.Client(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}',timeout=10) as client:
        client.headers['X-Eureka-Token']=client.get('/api/meta').json()['token']
        yield client,app.state.service
    host.should_exit=True;thread.join(timeout=10)
    assert not thread.is_alive()


def test_sse_durable_ids_reconnect_and_pagination(server):
    client,service=server
    run=client.post('/api/runs',json={'start':False,'settings':{'publish':False,'gpu_monitor':False},'specs':[{'text':'Offline SSE'}]}).json()['id']
    first=service.store.event(run,'fixture.text',{'text':'žluťoučký 🔬'})
    second=service.store.event(run,'fixture.text',{'text':'second'})
    with client.stream('GET',f'/api/runs/{run}/stream',headers={'Last-Event-ID':str(first)}) as stream:
        assert stream.status_code==200 and stream.headers['content-type'].startswith('text/event-stream')
        lines=[]
        for line in stream.iter_lines():
            lines.append(line)
            if not line and any(item.startswith('data:') for item in lines):break
    assert f'id: {second}' in lines
    assert 'second' in ''.join(lines) and 'žluťoučký' not in ''.join(lines)
    page=client.get(f'/api/runs/{run}/events',params={'before':second,'limit':1}).json()
    assert page[0]['id']==first and page[0]['data']['text']=='žluťoučký 🔬'


def test_worker_continues_without_browser_and_server_stop_is_resumable(server):
    client,service=server
    (service.project/'fixture-delay').write_text('5')
    response=client.post('/api/runs',json={'settings':{'publish':False,'gpu_monitor':False,'heartbeat_seconds':.1},'specs':[{'text':'Offline lifecycle'}]})
    assert response.status_code==200,response.text
    run=response.json()['id']
    deadline=time.monotonic()+15
    while service.store.get(run)['calls']==0:
        assert time.monotonic()<deadline
        time.sleep(.02)
    worker=service.workers[run]
    assert worker.poll() is None  # No EventSource or browser exists in this test.
    duplicate=client.post(f'/api/runs/{run}/actions',json={'kind':'pause','request_id':'pause-once'})
    assert duplicate.status_code==200
    while worker.poll() is None:
        assert time.monotonic()<deadline
        time.sleep(.02)
    row=service.store.get(run)
    assert row['status']=='paused' and row['calls']==1
    assert client.post(f'/api/runs/{run}/actions',json={'kind':'pause','request_id':'pause-once'}).status_code==200
    assert service.store.get(run)['calls']==1
    client.post(f'/api/runs/{run}/actions',json={'kind':'resume'})
    deadline=time.monotonic()+15
    while service.store.get(run)['calls']<2:
        assert time.monotonic()<deadline
        time.sleep(.02)
    service.close()  # Same path as normal FastAPI server lifespan shutdown.
    from auto_eureka_scientist.state import Store
    reopened=Store(service.project)
    try:
        stopped=reopened.get(run)
        assert stopped['status']=='stopped' and stopped['calls']==2 and stopped['owner_pid']==0
    finally:reopened.close()
