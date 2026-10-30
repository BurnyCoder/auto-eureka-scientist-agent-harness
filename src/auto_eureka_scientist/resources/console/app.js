/* Schema-driven local controls. Untrusted messages and artifacts only enter text nodes.
 * EventSource replay: https://html.spec.whatwg.org/multipage/server-sent-events.html
 */
const $ = selector => document.querySelector(selector);
const state = {meta:null, run:null, snapshot:null, events:[], source:null, tab:'activity', config:{}, newConfig:{}, settings:null, queue:[], cursor:0};
const clone = value => structuredClone(value);
const equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);
function node(tag, attrs={}, ...children) {
  const result=document.createElement(tag);
  for(const [key,value] of Object.entries(attrs)) {
    if(key==='class') result.className=value;
    else if(key==='text') result.textContent=value;
    else if(key.startsWith('on')) result.addEventListener(key.slice(2),value);
    else if(value!==false && value!==null) result.setAttribute(key,value===true?'':value);
  }
  for(const child of children.flat()) if(child!=null) result.append(child instanceof Node?child:document.createTextNode(String(child)));
  return result;
}
async function api(path, options={}) {
  const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Eureka-Token':state.meta?.token||'',...options.headers}});
  if(!response.ok) {const body=await response.json().catch(()=>({error:response.statusText}));throw Error(body.error||JSON.stringify(body.detail));}
  return response.json();
}
const post=(path,body,method='POST')=>api(path,{method,body:JSON.stringify(body)});
function fail(error) {
  const text=error.message||String(error);$('#error').textContent=text;$('#error').hidden=false;
  const dialog=[...document.querySelectorAll('dialog[open]')].at(-1);
  if(dialog){let alert=dialog.querySelector('.dialog-error');if(!alert){alert=node('p',{class:'dialog-error',role:'alert'});dialog.prepend(alert);}alert.textContent=text;alert.scrollIntoView({block:'nearest'});}
}
function toast(message) {$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>$('#toast').hidden=true,5000);}
function time(value) {
  if(!value || !state.config.show_timestamps) return '';
  const options={hour:'2-digit',minute:'2-digit',second:'2-digit'};
  if(state.config.timezone && state.config.timezone!=='local') options.timeZone=state.config.timezone;
  try{return new Intl.DateTimeFormat(undefined,options).format(new Date(value));}catch{return new Date(value).toLocaleTimeString();}
}
const duration=seconds=>`${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;
function styling(config) {
  const previous=state.config;
  for(const [key,id] of [['message_mode','message-kind'],['delivery','delivery'],['message_scope','message-scope']]) {
    if(config[key]!==previous[key])$('#'+id).value=config[key];
  }
  if(config.detail_tab!==previous.detail_tab)state.tab=config.detail_tab||'activity';
  if(config.log_filter!==previous.log_filter)state.activityFilter=config.log_filter;
  state.config=config;
  const root=document.documentElement;
  root.dataset.theme=config.theme||'system';root.dataset.density=config.density||'comfortable';
  root.style.fontSize=(config.font_size||14)+'px';root.style.setProperty('--queue',(config.queue_width||240)+'px');root.style.setProperty('--details',(config.details_width||360)+'px');
  const panels=config.panels||['queue','details'];
  $('#queue-panel').hidden=!panels.includes('queue');$('#details-panel').hidden=!panels.includes('details');
  $('.workspace').classList.toggle('no-queue',!panels.includes('queue'));$('.workspace').classList.toggle('no-details',!panels.includes('details'));
}
function notify(status) {
  if(!(state.config.notification_events||[]).includes(status)) return;
  toast('Research run: '+status.replaceAll('_',' '));
  if(state.config.browser_notifications && 'Notification' in window && Notification.permission==='granted') new Notification('Eureka research',{body:status.replaceAll('_',' ')});
  if(state.config.sound) {
    const audio=new AudioContext();const oscillator=audio.createOscillator(),gain=audio.createGain();
    gain.gain.value=.05;oscillator.frequency.value=660;oscillator.connect(gain);gain.connect(audio.destination);oscillator.start();oscillator.stop(audio.currentTime+.15);oscillator.onended=()=>audio.close();
  }
}
async function listRuns() {
  const runs=await api('/runs');$('#runs').replaceChildren();
  for(const run of runs) $('#runs').append(node('button',{class:'run-item'+(run.id===state.run?' selected':''),onclick:()=>selectRun(run.id)},
    node('strong',{text:run.task.split('\n')[0]||run.id}),node('span',{class:'small muted',text:`${run.config.model} · ${run.status.replaceAll('_',' ')}`})));
  return runs;
}
async function selectRun(id) {
  state.source?.close();state.run=id;state.events=[];state.cursor=0;
  history.replaceState(null,'','?run='+encodeURIComponent(id));
  await refresh();
  state.events=await api(`/runs/${id}/events?before=${state.snapshot.event_cursor+1}&limit=${state.config.history_page_size||200}`);
  state.cursor=state.events.at(-1)?.id||0;renderChat();renderDetails();
  state.source=new EventSource(`/api/runs/${id}/stream?after=${state.cursor}`);
  state.source.onopen=()=>{$('#connection').textContent='● Live connection';$('#connection').classList.add('live');};
  state.source.onerror=()=>{$('#connection').textContent='Reconnecting · history retained';$('#connection').classList.remove('live');};
  state.source.addEventListener('update',event=>{
    const data=JSON.parse(event.data);if(data.id<=state.cursor)return;
    state.cursor=data.id;state.events.push(data);state.events=state.events.slice(-(state.config.history_page_size||200));
    renderChat();if(state.tab==='activity')renderDetails();
    if(['run.finished','phase.accepted','settings.changed','message.answered'].includes(data.type))refresh().catch(fail);
  });
  await listRuns();
}
async function refresh() {
  if(!state.run || state.refreshing)return;
  state.refreshing=true;
  try {
    const snapshot=await api(`/runs/${state.run}`),previous=state.snapshot?.run.status;
    if(snapshot.run.id!==state.run)return;
    state.snapshot=snapshot;styling(snapshot.run.config);
    if(previous && previous!==snapshot.run.status) {notify(snapshot.run.status);listRuns().catch(fail);}
    const run=snapshot.run,active=snapshot.active_spec;
    $('#run-title').textContent=active?.title||snapshot.specs[0]?.title||'Research run';
    $('#run-subtitle').textContent=run.message||`Run ${run.id} · Cycle ${run.cycle} · ${snapshot.worker_alive?'Controller connected':'Controller idle — resume when ready'}`;
    $('#status').textContent=run.status.replaceAll('_',' ');$('#status').className='status '+run.status;
    const current=state.meta.phases[run.phase_index];
    const accepted=new Set(snapshot.phases.map(p=>p.name));
    const latest=snapshot.phases.at(-1),handoff=latest?.result;
    const reported=[...new Set(snapshot.attempts.flatMap(a=>a.result.models||[]))];
    $('#research-state').replaceChildren(
      node('div',{},node('strong',{text:handoff?'Recorded stage: '+handoff.stage:'Research stage not yet reported'}),handoff?` · updated ${time(latest.completed)||latest.completed}`:''),
      node('div',{text:'Next action: '+(run.status==='complete'?'Run complete':current||'Final verification and completion')+(handoff?.objective?' · Last objective: '+handoff.objective:'')}),
      node('details',{},node('summary',{text:'Model identity, activity, and blockers'}),node('p',{text:'Requested: '+run.config.model+(run.config.model_pin?' · pinned: '+run.config.model_pin:'')+' · Reported: '+(reported.join(', ')||'unavailable')}),
        node('p',{text:'Last recorded activity: '+(time(state.events.at(-1)?.at)||'unavailable')}),node('p',{text:'Blockers: '+(run.status==='blocked'?run.message:handoff?.issues?.join('; ')||'none reported')})));
    $('#phases').replaceChildren(...state.meta.phases.map((phase,index)=>node('div',{class:'phase'+(accepted.has(phase)?' accepted':'')+(phase===current?' current':''),title:`${phase}: ${accepted.has(phase)?'accepted':phase===current?'current':'pending'}`},node('span'),`${index+1}. ${phase}`)));
    const costs=snapshot.reported_cost_usd;
    const cards=[['Completed loops',`${run.loops_completed} / ${run.config.max_loops??(run.config.mode==='cycle'?1:'∞')}`,`${run.cycles_started} cycles started`],
      ['CLI calls',`${run.calls} / ${run.config.max_calls??'∞'}`,`${accepted.size} / 8 phases accepted`],
      ['Active time',duration(run.elapsed),run.config.max_minutes?`${duration(Math.max(0,run.config.max_minutes*60-run.elapsed))} remaining`:'No time limit'],
      ['Selected model',run.config.model,costs==null?'Cost not reported':`Reported cost $${costs.toFixed(4)}`]];
    $('#metrics').replaceChildren(...cards.map(([label,value,detail])=>node('div',{class:'metric'},node('span',{class:'label',text:label}),node('span',{class:'value',text:value,title:value}),node('small',{text:detail}))));
    $('#specs').replaceChildren(...snapshot.specs.map((spec,index)=>node('div',{class:'spec-item'+(active?.id===spec.id?' active':'')+(!spec.enabled?' disabled':'')},node('strong',{text:`${index+1}. ${spec.title}`}),node('small',{class:'muted',text:`Revision ${spec.revision} · ${spec.enabled?'Enabled':'Disabled'}${active?.id===spec.id?' · active snapshot r'+active.revision:''}`}))));
    $('#last-update').textContent=time(snapshot.telemetry.at);
    const cpu=snapshot.telemetry.process,gpus=snapshot.telemetry.machine_gpus;
    $('#telemetry').replaceChildren(node('div',{},node('strong',{text:'Process '}),cpu?`${cpu.cpu_percent.toFixed(1)}% CPU · ${(cpu.ram_bytes/1048576).toFixed(0)} MiB RAM`:'CPU / RAM unavailable'),
      ...(gpus||[]).map(gpu=>node('div',{},node('strong',{text:'Machine GPU '}),`${gpu.name} · ${gpu.utilization_percent}% · ${gpu.used_mib}/${gpu.total_mib} MiB`)),
      ...(!gpus?[node('div',{text:'Machine GPU telemetry unavailable'})]:[]),node('div',{text:`Last heartbeat ${time(run.updated)||run.updated}`}));
    for(const button of document.querySelectorAll('[data-action]'))button.disabled=(!state.run)||(button.dataset.action==='resume' && (snapshot.worker_alive||run.status==='complete'));
    if(costs!=null && run.config.cost_warning_usd!=null && costs>=run.config.cost_warning_usd && state.costWarn!==run.id) {toast('Reported provider cost reached the configured warning threshold.');state.costWarn=run.id;}
    renderChat();if(state.tab==='settings')renderDetails();
  } finally {state.refreshing=false;}
}
function bubble(label,body,at,kind='agent',status='') {
  return node('article',{class:'bubble '+kind},node('div',{class:'byline'},node('strong',{text:label}),node('span',{text:status}),node('time',{text:time(at)})),node('div',{class:'message-body',text:body}));
}
function renderChat() {
  if(!state.snapshot)return;
  const signature=JSON.stringify([state.run,state.snapshot.messages,state.events,state.config.show_timestamps,state.config.timezone,state.config.auto_scroll]);
  if(signature===state.chatSignature)return;state.chatSignature=signature;
  const opened=new Set([...$('#chat').querySelectorAll('details[open]')].map(d=>d.dataset.key));
  const entries=[];
  for(const message of state.snapshot.messages) {
    entries.push({at:message.at,element:bubble(message.kind==='ask'?'You · question':'You · steering',message.text,message.at,'user',message.status)});
    if(message.answer)entries.push({at:message.at+'z',element:bubble('Agent · answer',message.answer,message.at,'agent',message.status)});
  }
  for(const event of state.events.filter(e=>e.type==='phase.accepted')) {
    const handoff=event.data.handoff;
    const element=bubble(event.data.phase+' completed',handoff.summary,event.at,'phase-result',handoff.stage);
    const details=node('details',{'data-key':event.id,open:opened.has(String(event.id))},node('summary',{text:'Objective, observations, and evidence'}),node('pre',{text:JSON.stringify(handoff,null,2)}));element.append(details);
    entries.push({at:event.at,element});
  }
  const last=state.snapshot.attempts.at(-1);
  if(last && last.status!=='accepted') {
    const texts=state.events.filter(e=>e.data.attempt===last.id && ['agent.delta','agent.message'].includes(e.type));
    const text=texts.map(e=>e.data.text||'').join('');
    if(text)entries.push({at:texts[0].at,element:bubble('Agent · '+last.phase,text,texts[0].at,'agent',last.status)});
  }
  if(!entries.length) {
    const spec=state.snapshot.active_spec||state.snapshot.specs[0];
    entries.push({at:'',element:bubble('Research spec',spec?.text||'No enabled specs. Edit the queue to continue.',state.snapshot.run.created,'agent','Recorded input')});
  }
  entries.sort((a,b)=>a.at.localeCompare(b.at));
  const chat=$('#chat'),previous=chat.scrollTop;
  chat.replaceChildren(...entries.slice(-(state.config.history_page_size||200)).map(e=>e.element));
  chat.scrollTop=state.config.auto_scroll?chat.scrollHeight:previous;
}
async function action(kind,payload={}) {
  if(!state.run)return toast('Create or select a run first.');
  if(kind==='revisit') {
    const phase=await ask('Earlier phase to request (research, preregister, core, pilot, experiments, analysis, review, publish)','research');
    if(!phase)return;payload.phase=phase;
  }
  await post(`/runs/${state.run}/actions`,{kind,payload,request_id:crypto.randomUUID()});toast('Control queued: '+kind.replaceAll('_',' '));await refresh();
}
function setTab(tab) {state.tab=tab;document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',b.dataset.tab===tab);});renderDetails();}
function renderDetails() {
  const content=$('#detail-content'),opened=new Set([...content.querySelectorAll('details[open]')].map(d=>d.dataset.key));content.replaceChildren();if(!state.snapshot)return;
  if(state.tab==='activity') {
    const filter=node('select',{'aria-label':'Activity filter'},...['all','agent','stderr','control','publication'].map(value=>node('option',{value,text:value})));filter.value=state.activityFilter||'all';
    filter.onchange=()=>{state.activityFilter=filter.value;renderDetails();};
    const older=node('button',{text:'Load older',onclick:async()=>{
      const rows=await api(`/runs/${state.run}/events?before=${state.events[0]?.id||state.cursor+1}&limit=${state.config.history_page_size||200}`);
      if(!rows.length)return toast('Beginning of recorded event history.');
      state.events=rows;renderDetails();renderChat();toast('Showing older history. New live events continue arriving.');
    }});
    content.append(node('div',{class:'activity-tools'},filter,older));
    const events=state.events.filter(e=>filter.value==='all'||e.type.includes(filter.value));
    for(const event of events.slice().reverse()) {
      const label=event.type.replaceAll('.',' · ')+(event.data.phase?' · '+event.data.phase:'');
      content.append(node('details',{class:'activity-item','data-key':event.id,open:opened.has(String(event.id))},node('summary',{},label,node('small',{text:time(event.at)})),node('pre',{text:JSON.stringify(event.data,null,2)})));
    }
    const attempts=node('details',{'data-key':'logs',open:opened.has('logs')},node('summary',{text:'Full invocation prompts and raw logs'}));
    for(const attempt of state.snapshot.attempts.slice().reverse()) attempts.append(node('p',{class:'small'},`${attempt.id} · ${attempt.phase} · `,
      ...['prompt','stdout','stderr'].map(channel=>node('a',{href:`/api/runs/${state.run}/logs/${attempt.id}/${channel}`,target:'_blank',rel:'noopener',text:channel+' '}))));
    content.append(attempts);
  } else if(state.tab==='artifacts') {
    content.append(node('p',{class:'muted small',text:'Saved artifacts, reports, and model outputs for the current cycle.'}));
    api(`/runs/${state.run}/artifacts`).then(files=>{if(state.tab!=='artifacts')return;for(const file of files)content.append(node('div',{class:'file-row'},node('button',{text:file.path,onclick:()=>viewArtifact(file.path)}),node('small',{text:(file.bytes/1024).toFixed(1)+' KB'})));}).catch(fail);
    for(const receipt of state.snapshot.publications) {const url=receipt.value.url||receipt.value.html_url;if(url && /^https?:\/\//.test(url))content.append(node('p',{},node('a',{href:url,target:'_blank',rel:'noopener',text:receipt.key})));}
  } else if(state.tab==='diff') {
    content.append(node('p',{class:'small muted',text:'Read-only working-tree inspection. Request file changes in chat.'}));
    api('/diff').then(diff=>{if(state.tab==='diff')content.append(node('pre',{text:diff.status+'\n\n'+(diff.diff||'No tracked file diff.')}));}).catch(fail);
  } else {
    content.append(node('button',{text:'Open all settings',onclick:()=>openSettings('run')}));
    const desired=state.snapshot.run.config,effective=state.snapshot.effective_settings;
    const pending=Object.keys(desired).filter(key=>!equal(desired[key],effective[key]));
    content.append(node('p',{class:'small muted',text:`Configuration revision ${state.snapshot.run.revision}. ${pending.length} value(s) differ from the last worker-applied snapshot.`}));
    if(pending.length)content.append(node('pre',{text:JSON.stringify(Object.fromEntries(pending.map(k=>[k,{requested:desired[k],effective:effective[k],applies:state.meta.schema.properties[k]['x-apply']}])),null,2)}));
    content.append(node('details',{},node('summary',{text:'Effective settings'}),node('pre',{text:JSON.stringify(effective,null,2)})),
      node('details',{},node('summary',{text:'Configuration history'}),node('pre',{text:JSON.stringify(state.snapshot.settings_changes,null,2)})));
  }
}
async function viewArtifact(path) {
  $('#artifact-title').textContent=path;$('#artifact-view').replaceChildren();
  const url='/api/file?path='+encodeURIComponent(path);
  if(/\.(png|svg|jpg|jpeg|webp)$/i.test(path))$('#artifact-view').append(node('img',{src:url,alt:path}));
  else if(/\.(pdf|safetensors|npz|pt)$/i.test(path))$('#artifact-view').append(node('a',{href:url,target:'_blank',rel:'noopener',text:'Open or download saved artifact'}));
  else {const response=await fetch(url);if(!response.ok)throw Error('Artifact unavailable');$('#artifact-view').append(node('pre',{text:await response.text()}));}
  $('#artifact-dialog').showModal();
}
async function setup() {
  try {state.meta=await api('/meta');state.newConfig=clone(state.meta.defaults);
    populateSetup();$('#setup-dialog').showModal();}catch(error){fail(error);}
}
function populateSetup() {
  const config=state.newConfig;$('#setup-backend').value=config.backend;$('#setup-model').value=config.model|| (config.backend==='claude'?'haiku':'gpt-6-luna');
  $('#setup-loops').value=config.max_loops??'';$('#setup-infinite').checked=config.max_loops==null;$('#setup-loops').disabled=config.max_loops==null;$('#setup-minutes').value=config.max_minutes??'';
}
function readSetup() {
  Object.assign(state.newConfig,{backend:$('#setup-backend').value,model:$('#setup-model').value,
    max_loops:$('#setup-infinite').checked?null:Number($('#setup-loops').value),max_minutes:$('#setup-minutes').value?Number($('#setup-minutes').value):null});
  if(state.newConfig.mode==='cycle'&&(state.newConfig.max_loops==null||state.newConfig.max_loops>1))state.newConfig.mode='continuous';
}
async function listPresets(selected='') {
  const presets=await api('/presets');$('#preset-list').replaceChildren(node('option',{value:'',text:'Saved presets…'}),...presets.map(p=>node('option',{value:p,text:p})));
  $('#preset-list').value=selected;
}
async function openSettings(target) {
  if(target==='run'&&!state.snapshot)target='defaults';
  const base=clone(target==='new'?state.newConfig:target==='run'?state.snapshot.run.config:state.meta.defaults);
  state.settings={target,base,draft:clone(base),revision:state.snapshot?.run.revision};
  $('#settings-title').textContent=target==='new'?'New run settings':target==='run'?'Run settings':'Project defaults';
  $('#settings-notice').textContent=target==='run'?'Model, project, and publication identity require a new run. Other fields show their application boundary.':'Defaults can be overridden per run. Existing runs retain their saved settings.';
  $('#settings-search').value='';$('#changed-only').checked=false;
  await listPresets();
  renderSettings();$('#settings-dialog').showModal();
}
function settingsDiff() {
  const {base,draft}=state.settings;
  const diff=Object.fromEntries(Object.keys(draft).filter(k=>!equal(draft[k],base[k])).map(k=>[k,{before:base[k],after:draft[k]}]));
  $('#settings-diff').textContent=JSON.stringify(diff,null,2);return diff;
}
function renderSettings() {
  const panel=$('#settings-fields');panel.replaceChildren();const groups={};
  const {base,draft,target}=state.settings;const query=$('#settings-search').value.toLowerCase();
  for(const [key,definition] of Object.entries(state.meta.schema.properties)) {
    if(definition['x-advanced']&&!$('#advanced').checked&&!query)continue;
    if(query&&!`${key} ${definition.description} ${definition['x-category']}`.toLowerCase().includes(query))continue;
    const changed=!equal(base[key],draft[key]);if($('#changed-only').checked&&!changed)continue;
    const category=definition['x-category'];
    if(!groups[category]) {const section=node('section',{class:'settings-category'},node('h3',{text:category}));groups[category]=node('div',{class:'settings-grid'});section.append(groups[category]);panel.append(section);}
    const unsupported=definition['x-backends']&&!definition['x-backends'].includes(draft.backend);
    const locked=key==='project'||(target==='run'&&definition['x-apply']==='new run')||unsupported;
    const wrapper=node('div',{class:'setting-field'+(changed?' changed':'')});
    const label=node('label',{for:'setting-'+key,text:definition.title});let input;
    const type=Array.isArray(definition.type)?definition.type.find(t=>t!=='null'):definition.type;
    if(definition.enum)input=node('select',{},...definition.enum.map(value=>node('option',{value,text:value||'None'})));
    else if(type==='boolean')input=node('input',{type:'checkbox'});
    else if(type==='array'&&definition.items?.enum)input=node('select',{multiple:true},...definition.items.enum.map(value=>node('option',{value,text:value})));
    else if(type==='array'||key==='pinned_instructions')input=node('textarea',{rows:3});
    else input=node('input',{type:['integer','number'].includes(type)?'number':'text'});
    input.id='setting-'+key;input.disabled=locked;input.dataset.key=key;
    if(type==='boolean')input.checked=!!draft[key];
    else if(type==='array'&&definition.items?.enum)for(const option of input.options)option.selected=(draft[key]||[]).includes(option.value);
    else input.value=type==='array'?(draft[key]||[]).join('\n'):(draft[key]??'');
    if(definition.minimum!=null)input.min=definition.minimum;if(definition.maximum!=null)input.max=definition.maximum;if(type==='number')input.step='any';
    const update=()=>{
      let value;
      if(type==='boolean')value=input.checked;
      else if(type==='array')value=definition.items?.enum?[...input.selectedOptions].map(o=>o.value):input.value.split('\n').map(v=>v.trim()).filter(Boolean);
      else if(['number','integer'].includes(type))value=Number(input.value);
      else value=input.value;
      draft[key]=value;wrapper.classList.toggle('changed',!equal(value,base[key]));settingsDiff();
    };
    input.addEventListener('input',update);
    wrapper.append(label,input,node('p',{text:definition.description}),node('span',{class:'timing',text:definition['x-apply']+' · '+definition['x-scope']}));
    if(unsupported)wrapper.append(node('span',{class:'effective',text:'Unavailable for '+draft.backend+'. Supported by '+definition['x-backends'].join(', ')+'.'}));
    if(key==='project')wrapper.append(node('span',{class:'effective',text:'This server is attached to this project. Select a different project when launching the server.'}));
    if(Array.isArray(definition.type)&&definition.type.includes('null')) {
      const unset=node('input',{type:'checkbox','aria-label':definition.title+' unset'});unset.checked=draft[key]==null;input.disabled=locked||unset.checked;unset.disabled=locked;
      unset.onchange=()=>{input.disabled=unset.checked;if(unset.checked)draft[key]=null;else {input.value=base[key]??definition.minimum??1;update();}settingsDiff();};
      wrapper.append(node('label',{class:'check'},unset,'Unset / no limit'));
    }
    const effective=state.snapshot?.effective_settings[key];
    if(target==='run'&&!equal(base[key],effective))wrapper.append(node('span',{class:'effective',text:'Worker-applied value: '+JSON.stringify(effective)}));
    groups[category].append(wrapper);
  }
  settingsDiff();
}
async function applySettings() {
  const {target,draft}=state.settings;
  const changes=Object.fromEntries(Object.keys(settingsDiff()).map(k=>[k,draft[k]]));
  if(draft.browser_notifications&&'Notification' in window&&Notification.permission==='default')await Notification.requestPermission();
  if(target==='run') {await post(`/runs/${state.run}/settings`,{settings:changes,revision:state.settings.revision},'PATCH');await refresh();}
  else if(target==='new'){state.newConfig=clone(draft);populateSetup();}
  else {await post('/defaults',{schema_version:1,settings:draft},'PUT');state.meta.defaults=clone(draft);styling(draft);}
  $('#settings-dialog').close();toast('Settings saved. Application boundaries are recorded.');
}
function editQueue() {if(!state.snapshot)return toast('Create a run first.');state.queue=clone(state.snapshot.specs);renderQueue();$('#queue-dialog').showModal();}
function renderQueue() {
  const container=$('#queue-editor');container.replaceChildren();
  state.queue.forEach((spec,index)=>{
    const enabled=node('input',{type:'checkbox'});enabled.checked=spec.enabled!==false;enabled.onchange=()=>spec.enabled=enabled.checked;
    const title=node('input',{value:spec.title||'',placeholder:'Spec title'});title.oninput=()=>spec.title=title.value;
    const text=node('textarea',{rows:5});text.value=spec.text;text.oninput=()=>spec.text=text.value;
    const overrides=node('textarea',{rows:2,'aria-label':'Cycle setting overrides'});overrides.value=JSON.stringify(spec.settings||{},null,2);
    overrides.oninput=()=>{try{spec.settings=JSON.parse(overrides.value);overrides.setCustomValidity('');}catch{overrides.setCustomValidity('Enter a JSON object');}};
    const parameters=node('textarea',{rows:2,'aria-label':'Requested research parameters'});parameters.value=JSON.stringify(spec.parameters||{},null,2);
    parameters.oninput=()=>{try{spec.parameters=JSON.parse(parameters.value);parameters.setCustomValidity('');}catch{parameters.setCustomValidity('Enter a JSON object');}};
    const move=delta=>{const target=index+delta;if(target<0||target>=state.queue.length)return;[state.queue[index],state.queue[target]]=[state.queue[target],state.queue[index]];renderQueue();};
    container.append(node('section',{class:'queue-card'},node('div',{class:'row'},node('label',{class:'check'},enabled,`Spec ${index+1}`),
      node('button',{text:'↑',title:'Move up',onclick:()=>move(-1)}),node('button',{text:'↓',title:'Move down',onclick:()=>move(1)}),
      node('button',{text:'Duplicate',onclick:()=>{const copy=clone(spec);delete copy.id;delete copy.revision;state.queue.splice(index+1,0,copy);renderQueue();}}),
      node('button',{text:'Remove',onclick:()=>{state.queue.splice(index,1);renderQueue();}})),node('label',{},'Title',title),node('label',{},'Spec text',text),
      node('details',{},node('summary',{text:'Research parameters (JSON requests)'}),node('p',{class:'small muted',text:'Datasets, seeds and hyperparameters are requests to the agent, not controller-enforced settings. Changes to registered research require a new cycle.'}),parameters),
      node('details',{},node('summary',{text:'Advanced cycle setting overrides (JSON)'}),node('p',{class:'small muted',text:'Cycle-scoped keys: '+Object.entries(state.meta.schema.properties).filter(([,v])=>v['x-scope']==='cycle').map(([k])=>k).join(', ')}),overrides)));
  });
}
function ask(title,value='') {
  return new Promise(resolve=>{
    $('#prompt-title').textContent=title;$('#prompt-value').value=value;const dialog=$('#prompt-dialog');
    $('#prompt-form').onsubmit=event=>{event.preventDefault();const answer=$('#prompt-value').value;dialog.close();resolve(answer);};
    dialog.onclose=()=>resolve(null);dialog.showModal();$('#prompt-value').focus();
  });
}
document.querySelectorAll('[data-close]').forEach(button=>button.onclick=()=>$('#'+button.dataset.close).close());
document.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>action(button.dataset.action).catch(fail));
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>setTab(button.dataset.tab));
$('#new-run').onclick=setup;$('#empty-start').onclick=setup;$('#refresh-runs').onclick=()=>listRuns().catch(fail);$('#settings-button').onclick=()=>openSettings('run').catch(fail);
$('#more-actions').onchange=event=>{if(event.target.value)action(event.target.value).catch(fail);event.target.value='';};
$('#setup-backend').onchange=()=>{$('#setup-model').value=$('#setup-backend').value==='claude'?'haiku':'gpt-6-luna';};
$('#setup-infinite').onchange=()=>{$('#setup-loops').disabled=$('#setup-infinite').checked;if(!$('#setup-infinite').checked&&!$('#setup-loops').value)$('#setup-loops').value=1;};
$('#setup-advanced').onclick=()=>{readSetup();openSettings('new').catch(fail);};
$('#setup-form').onsubmit=async event=>{event.preventDefault();try{readSetup();const result=await post('/runs',{settings:state.newConfig,specs:[{title:$('#setup-title').value||'Research spec',text:$('#setup-spec').value}],request_id:crypto.randomUUID()});$('#setup-dialog').close();await selectRun(result.id);}catch(error){fail(error);}};
$('#composer').onsubmit=async event=>{event.preventDefault();if(!state.run)return toast('Create a run first.');const text=$('#message').value.trim();if(!text)return;try{await post(`/runs/${state.run}/messages`,{text,kind:$('#message-kind').value,scope:$('#message-scope').value,delivery:$('#delivery').value,request_id:crypto.randomUUID()});$('#message').value='';await refresh();}catch(error){fail(error);}};
$('#message').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&((state.config.send_key==='enter'&&!event.ctrlKey)||(state.config.send_key!=='enter'&&(event.ctrlKey||event.metaKey)))){event.preventDefault();$('#composer').requestSubmit();}};
$('#edit-queue').onclick=editQueue;$('#add-spec').onclick=()=>{state.queue.push({title:'New spec',text:'',enabled:true,settings:{}});renderQueue();};
$('#save-queue').onclick=async()=>{try{if(![...$('#queue-editor').querySelectorAll('textarea')].every(e=>e.reportValidity()))return;await post(`/runs/${state.run}/specs`,state.queue,'PUT');$('#queue-dialog').close();await refresh();toast('Future queue updated.');}catch(error){fail(error);}};
$('#settings-search').oninput=renderSettings;$('#advanced').onchange=renderSettings;$('#changed-only').onchange=renderSettings;$('#apply-settings').onclick=()=>applySettings().catch(fail);
$('#reset-settings').onclick=()=>{for(const [key,definition] of Object.entries(state.meta.schema.properties))if('default' in definition&&!(state.settings.target==='run'&&definition['x-apply']==='new run'))state.settings.draft[key]=clone(definition.default);renderSettings();};
$('#save-defaults').onclick=()=>post('/defaults',{schema_version:1,settings:state.settings.draft},'PUT').then(()=>toast('Project defaults saved for new runs.')).catch(fail);
$('#save-preset').onclick=async()=>{const name=await ask('Save or duplicate preset as');if(name){try{await post('/presets/'+encodeURIComponent(name),{schema_version:1,settings:state.settings.draft},'PUT');await listPresets(name);toast('Preset saved.');}catch(error){fail(error);}}};
$('#load-preset').onclick=async()=>{const name=$('#preset-list').value;if(name){try{const document=await api('/presets/'+encodeURIComponent(name));for(const [key,value] of Object.entries(document.settings))if(!(state.settings.target==='run'&&state.meta.schema.properties[key]['x-apply']==='new run'))state.settings.draft[key]=value;renderSettings();}catch(error){fail(error);}}};
$('#export-settings').onclick=()=>{const settings={...state.settings.draft};delete settings.project;delete settings.executable;const blob=new Blob([JSON.stringify({schema_version:1,settings},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=node('a',{href:url,download:'eureka-settings.json'});link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('#import-settings').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;const document=JSON.parse(await file.text());if(document.schema_version!==1||!document.settings)throw Error('Expected a versioned settings export.');for(const [key,value] of Object.entries(document.settings)){if(!state.meta.schema.properties[key])throw Error('Unknown setting: '+key);if(!(state.settings.target==='run'&&state.meta.schema.properties[key]['x-apply']==='new run'))state.settings.draft[key]=value;}renderSettings();}catch(error){fail(error);}finally{event.target.value='';}};
window.addEventListener('unhandledrejection',event=>{fail(event.reason);event.preventDefault();});
async function start() {
  state.meta=await api('/meta');styling(state.meta.defaults);$('#project-path').textContent=state.meta.project;
  $('#message-kind').value=state.config.message_mode;$('#delivery').value=state.config.delivery;$('#message-scope').value=state.config.message_scope;
  state.tab=state.config.detail_tab;const runs=await listRuns();const requested=new URLSearchParams(location.search).get('run');
  if(runs.length)await selectRun(runs.some(r=>r.id===requested)?requested:runs[0].id);
  else {$('#connection').textContent='● Local console ready';$('#connection').classList.add('live');}
  setTab(state.tab);setInterval(()=>refresh().catch(fail),1000);
}
start().catch(fail);
