"""Normalize observable provider events without fabricating progress or model reasoning.

https://learn.chatgpt.com/docs/developer-commands#codex-exec
https://code.claude.com/docs/en/headless#stream-responses
Unknown records remain inspectable and the transport retains the original bytes.
"""
import json


class EventSink:
    def __init__(self, store, run_id, **context):
        self.store,self.run_id,self.context=store,run_id,context
        self.pending=''

    def __call__(self,kind,data):
        self.store.event(self.run_id,kind,{**self.context,**data})

    def stream(self,channel,text):
        if channel!='stdout':
            self('log.'+channel,{'text':text})
            return
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            self.record(line)

    def finish(self):
        if self.pending: self.record(self.pending)
        self.pending=''

    def record(self,line):
        try: event=json.loads(line)
        except ValueError:
            self('log.stdout',{'text':line})
            return
        if not isinstance(event,dict):
            self('provider.event',{'value':event})
            return
        kind=event.get('type','unknown')
        item=event.get('item') or {}
        message=event.get('message') or {}
        inner=event.get('event')
        delta=(inner.get('delta') if isinstance(inner,dict) else None) or event.get('delta') or {}
        if isinstance(delta,dict) and delta.get('type')=='text_delta':
            self('agent.delta',{'text':delta.get('text','')})
        elif isinstance(item,dict) and item.get('type')=='agent_message':
            self('agent.message',{'text':item.get('text','')})
        elif isinstance(message,dict) and isinstance(message.get('content'),list):
            for block in message['content']:
                if not isinstance(block,dict): continue
                if block.get('type')=='text': self('agent.message',{'text':block.get('text','')})
                elif block.get('type') in ('tool_use','tool_result'): self('agent.tool',block)
        elif kind in ('item.started','item.updated','item.completed'):
            self('agent.tool',{'state':kind,'item':item})
        # Record terminal usage, errors, handoffs and unknown schemas for drill-down.
        self('provider.event',event)
