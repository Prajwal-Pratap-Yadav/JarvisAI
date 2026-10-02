import {Voice} from './voice.js';
const $ = id => document.getElementById(id);
const make = (tag, text = '', cls = '') => { const node=document.createElement(tag); node.textContent=text; if(cls) node.className=cls; return node; };
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.get('token')) { sessionStorage.setItem('jarvis-token', fragment.get('token')); history.replaceState(null,'',location.pathname); }
const token = sessionStorage.getItem('jarvis-token') || '';
let selected = null, snapshot = null, cursor = 0, eventCount = 0, audioState = null, socket = null, stopped = false;
const session = crypto.randomUUID();
const spoken = new Set();
const labels = {IDLE:'Ready when you are.',PLANNING:'Building a plan.',EXECUTING:'Working through your goal.',SELF_EVALUATING:'Checking the result.',RECOVERING:'Recovering with context.',CONFIRMATION_REQUIRED:'Your approval is needed.',COMPLETED:'Verified and complete.',FAILED:'An action needs attention.',LISTENING:'I’m listening.',SPEAKING:'Here’s what I found.'};
async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, {...options, headers:{'Content-Type':'application/json', Authorization:`Bearer ${token}`, ...options.headers}});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
function notice(error) { $('notice').textContent=error.message || String(error); $('notice').hidden=false; }
function guarded(handler) { return async event => { try { await handler(event); } catch(error) { notice(error); } }; }
function state(value, detail = '') {
  const actual=audioState || value;
  $('runtime-state').textContent=actual.replaceAll('_',' ');
  $('core').dataset.state=actual;
  $('core-label').textContent=labels[actual] || actual;
  if(detail) $('core-detail').textContent=detail;
}
const voice = new Voice({onCommand:command=>{ $('goal').value=command; $('command-form').requestSubmit(); }, onState:s=>{audioState=s==='IDLE'?null:s;state(s);}, onNotice:message=>$('voice-status').textContent=message, emit:kind=>api('voice',{method:'POST',body:JSON.stringify({kind})}).catch(()=>{}),canvas:$('waveform')});
function metric(data) {
  $('cpu').textContent=`${data.cpu_percent.toFixed(1)}%`; $('cpu-bar').value=data.cpu_percent;
  $('ram').textContent=`${data.ram_percent.toFixed(1)}%`; $('ram-bar').value=data.ram_percent;
  $('disk').textContent=`${(data.disk_free/1024**3).toFixed(1)} GB`;
  $('process-count').textContent=`${data.process_count} active processes`;
  $('gpu').textContent=data.gpu?.length?`${data.gpu[0].percent}%`:'Unavailable';
  $('uptime').textContent=`RUNTIME ${Math.floor(data.app_uptime/60)} MIN · LOCALHOST`;
}
function eventLine(event) {
  if (event.kind==='HEARTBEAT' || event.seq<=cursor) return;
  cursor=event.seq; eventCount++;
  if(event.kind==='SYSTEM_METRICS') { metric(event.data); return; }
  const line=make('div','','event'+(event.kind.includes('FAILED')?' error':''));
  const time=make('time',new Date(event.ts*1000).toLocaleTimeString([], {hour12:false}));
  line.append(time,make('strong',event.kind.replaceAll('_',' ')),make('p',Object.entries(event.data).filter(([k])=>!['arguments','validation'].includes(k)).map(([k,v])=>`${k}: ${typeof v==='object'?JSON.stringify(v):v}`).join(' · ').slice(0,250)));
  $('events').querySelector('.empty')?.remove(); $('events').append(line);
  while($('events').children.length>100) $('events').firstChild.remove();
  $('events').scrollTop=$('events').scrollHeight; $('event-count').textContent=`${eventCount} observed events · replay enabled`;
  if(event.kind==='SYSTEM_ALERT') { notice(event.data.title); }
  if(event.kind==='RUNTIME_STATE') state(event.data.state);
}
function connect() {
  if(stopped || !token) return;
  socket=new WebSocket(`ws://${location.host}/api/live`);
  socket.onopen=()=>{ socket.send(JSON.stringify({token,after:cursor})); $('connection').textContent='● CONNECTED'; };
  socket.onmessage=e=>{ try{eventLine(JSON.parse(e.data));}catch(error){notice(error);} };
  socket.onclose=()=>{ $('connection').textContent='RECONNECTING'; if(!stopped) setTimeout(connect,3000); };
}
function showView(name) {
  document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==`view-${name}`);
  document.querySelectorAll('[data-view]').forEach(v=>v.classList.toggle('active',v.dataset.view===name));
  if(name==='memory') loadMemory().catch(notice);
  if(name==='schedules') loadSchedules().catch(notice);
  if(name==='capabilities') loadCapabilities().catch(notice);
}
function renderApprovals(items) {
  $('approvals').replaceChildren();
  for(const item of items) {
    const box=make('section','','approval');
    box.append(make('h3',`Approval required · ${item.tool}`),make('p','Review this exact action. Approval is single-use and expires after ten minutes. Project tests and desktop input run with your operating-system permissions.'),make('pre',JSON.stringify(item.arguments,null,2)));
    for(const [allowed,label] of [[true,'Approve this action'],[false,'Deny']]) {
      const button=make('button',label,allowed?'primary':'danger');
      button.onclick=guarded(async()=>{ button.disabled=true; await api(`approvals/${item.id}`,{method:'POST',body:JSON.stringify({allowed})}); await refresh(); });
      box.append(button);
    }
    $('approvals').append(box);
  }
}
function renderRuns(runs) {
  $('task-count').textContent=`${runs.length} recent runs`;
  if(!runs.length) return;
  if(!selected) selected=runs[0].id;
  $('runs').replaceChildren();
  for(const run of runs) {
    const card=make('button','','run-card'+(run.id===selected?' selected':''));
    card.append(make('p',run.goal.slice(0,110)),make('span',`${run.status.replaceAll('_',' ')} · ${run.nodes.filter(n=>n.status==='completed').length}/${run.nodes.length} actions`,`status-${run.status}`));
    card.onclick=()=>{selected=run.id;renderRuns(runs);}; $('runs').append(card);
  }
  const run=runs.find(r=>r.id===selected); if(!run)return;
  const expanded=new Set([...$('run-detail').querySelectorAll('details[open]')].map(d=>d.dataset.id));
  const detail=$('run-detail'); detail.replaceChildren(make('h3',run.goal),make('p',`${run.id.slice(0,10)} · ${new Date(run.created*1000).toLocaleString()}`,'run-meta'));
  const actions=make('div','','run-actions');
  if(['running','pending','confirmation_required'].includes(run.status)) {
    const cancel=make('button','Cancel run','danger');cancel.onclick=guarded(async()=>{await api(`runs/${run.id}/cancel`,{method:'POST'});await refresh();});actions.append(cancel);
  }
  if(['failed','cancelled','interrupted'].includes(run.status)) {
    const replan=make('button','Replan with model'); replan.onclick=guarded(async()=>{replan.disabled=true; const next=await api(`runs/${run.id}/replan`,{method:'POST'}); selected=next.id;await refresh();});actions.append(replan);
  }
  const replay=make('button','Replay events');replay.onclick=guarded(async()=>{const items=await api(`events?run_id=${run.id}`);$('events').replaceChildren();const saved=cursor;cursor=0;items.forEach(eventLine);cursor=Math.max(saved,cursor);});actions.append(replay);detail.append(actions);
  for(const node of run.nodes) {
    const row=make('div','','node');
    const summary=make('div','','node-summary');summary.append(make('strong',node.id),make('span',node.tool),make('span',node.status.replaceAll('_',' '),`status-${node.status}`));row.append(summary);
    row.append(make('div',`Depends on: ${node.dependencies.join(', ')||'independent'} · ${node.attempts} attempt(s) · ${node.duration.toFixed(2)} s`,'dependency'));
    if(node.error)row.append(make('p',node.error,'status-failed small'));
    if(node.result){ const results=make('details');results.dataset.id=node.id;results.open=expanded.has(node.id);results.append(make('summary','Inspect result'),make('pre',JSON.stringify(node.result,null,2)));row.append(results); }
    detail.append(row);
  }
  if(run.validation)detail.append(make('p',run.validation.passed?'Validation: tool contracts and declared expectations passed.':'Validation: one or more actions did not complete.','muted small'));
  if(run.status==='completed' && !spoken.has(run.id) && $('speak-mode').checked) {
    spoken.add(run.id); const response=run.nodes.map(n=>n.result?.response||n.result?.report).filter(Boolean).join('\n');
    voice.speak(response || 'The requested tools completed and passed their declared checks. Inspect the results in your task workspace.');
  }
  const live=runs.find(r=>['running','confirmation_required','pending'].includes(r.status));
  const current=live || run;
  const runtime={pending:'PLANNING',running:'EXECUTING',confirmation_required:'CONFIRMATION_REQUIRED',completed:'COMPLETED',failed:'FAILED',cancelled:'IDLE',interrupted:'RECOVERING'}[current.status]||'IDLE';
  state(runtime,current.status==='running'?`${current.nodes.filter(n=>n.status==='completed').length} of ${current.nodes.length} actions verified`:'Execution state comes from the local runtime.');
  $('orbit').replaceChildren();
  const active=current.nodes.filter(n=>n.status==='running');
  if(active.length)$('orbit').append(make('span',[...new Set(active.map(n=>snapshot?.capabilities.find(t=>t.name===n.tool)?.agent||n.tool))].join(' · ').toUpperCase()));
  const stage={PLANNING:'plan',EXECUTING:'tool',CONFIRMATION_REQUIRED:'tool',SELF_EVALUATING:'validate',COMPLETED:'result',FAILED:'result'}[runtime]||'goal';
  document.querySelectorAll('[data-stage]').forEach(el=>el.classList.toggle('active',el.dataset.stage===stage));
}
async function refresh() { snapshot=await api('status');metric(snapshot.telemetry);renderApprovals(snapshot.approvals);renderRuns(snapshot.runs);return snapshot; }
async function settings() { const s=await api('settings');$('provider').value=s.provider;$('model').value=s.model;$('model-url').value=s.model_url;$('network-hosts').value=s.network_hosts.join(', ');$('desktop-enabled').checked=s.desktop_enabled;$('proactive').checked=s.proactive;$('workspace-path').textContent=s.workspace;$('settings-error').textContent='';$('settings-dialog').showModal(); }
async function loadMemory() {
  const memories=await api('memory');$('memories').replaceChildren();
  if(!memories.length)$('memories').append(make('p','No persistent memory saved.','empty'));
  for(const memory of memories) {
    const box=make('div','','record'), remove=make('button','Delete','danger');
    remove.onclick=guarded(async()=>{await api(`memory/${memory.id}`,{method:'DELETE'});await loadMemory();});
    box.append(remove,make('p',memory.content),make('span',`${memory.kind} · source: ${memory.source} · confidence: ${memory.confidence}`,'meta'));$('memories').append(box);
  }
}
async function loadSchedules() {
  const schedules=await api('schedules');$('schedules').replaceChildren();
  if(!schedules.length)$('schedules').append(make('p','No reminders scheduled.','empty'));
  for(const schedule of schedules) {
    const box=make('div','','record'),remove=make('button','Remove');remove.onclick=guarded(async()=>{await api(`schedules/${schedule.id}`,{method:'DELETE'});await loadSchedules();});
    box.append(remove,make('p',schedule.title),make('span',`${schedule.enabled?'Scheduled':'Delivered / disabled'} · ${new Date(schedule.due*1000).toLocaleString()}${schedule.interval?` · every ${schedule.interval}s`:''}`,'meta'));$('schedules').append(box);
  }
}
async function loadCapabilities() {
  const data=await api('capabilities');$('capabilities').replaceChildren();
  for(const tool of data.tools) {
    const box=make('article','','panel capability');box.append(make('h3',tool.name),make('p',tool.description),make('span',tool.agent.toUpperCase(),'tag'),make('span',`${tool.risk.toUpperCase()} RISK`,'tag'),make('p',`${tool.available?'Configured':'Unavailable'} · ${tool.availability_detail}`));
    const details=make('details');details.append(make('summary','Input schema and permissions'),make('pre',JSON.stringify({input:tool.input_schema,confirmation:tool.confirmation,timeout:tool.timeout,retries:tool.retry_policy},null,2)));box.append(details);$('capabilities').append(box);
  }
}
$('command-form').onsubmit=guarded(async event=>{event.preventDefault();$('notice').hidden=true;$('send-button').disabled=true;state('PLANNING');try{const run=await api('goals',{method:'POST',body:JSON.stringify({goal:$('goal').value,session})});selected=run.id;$('goal').value='';await refresh();}finally{$('send-button').disabled=false;}});
$('goal').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('command-form').requestSubmit();}};
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('goal').value=button.dataset.prompt;$('goal').focus();});
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>showView(button.dataset.view));
$('demo-button').onclick=()=>{$('goal').value='system status';$('command-form').requestSubmit();};
$('settings-button').onclick=guarded(settings);
$('close-settings').onclick=()=>$('settings-dialog').close();
$('settings-form').onsubmit=async event=>{event.preventDefault();try{await api('settings',{method:'PUT',body:JSON.stringify({provider:$('provider').value,model:$('model').value,model_url:$('model-url').value,network_hosts:$('network-hosts').value.split(',').map(s=>s.trim()).filter(Boolean),desktop_enabled:$('desktop-enabled').checked,proactive:$('proactive').checked})});$('settings-dialog').close();await refresh();}catch(error){$('settings-error').textContent=error.message;}};
$('provider').onchange=()=>{if($('provider').value==='ollama')$('model-url').value='http://127.0.0.1:11434';};
$('diagnostics-button').onclick=guarded(async()=>{$('diagnostics-dialog').showModal();$('diagnostics').textContent='Checking actual runtime capabilities…';const d=await api('diagnostics');$('diagnostics').replaceChildren();for(const key of ['core','memory','model','browser','computer','vision','audio']){const item=d[key],row=make('div','','diagnostic');row.append(make('strong',key.toUpperCase()),make('p',`${item.available===true?'READY':item.available===false?'NOT READY':'CHECK IN BROWSER'} · ${item.detail}`));$('diagnostics').append(row);}});
$('close-diagnostics').onclick=()=>$('diagnostics-dialog').close();
$('clear-events').onclick=()=>{$('events').replaceChildren();};
$('listen-button').onclick=guarded(()=>voice.start($('wake-mode').checked));
$('stop-voice').onclick=()=>voice.interrupt();
$('memory-form').onsubmit=guarded(async event=>{event.preventDefault();await api('memory',{method:'POST',body:JSON.stringify({kind:$('memory-kind').value,content:$('memory-content').value,source:'user'})});$('memory-content').value='';await loadMemory();});
$('schedule-form').onsubmit=guarded(async event=>{event.preventDefault();await api('schedules',{method:'POST',body:JSON.stringify({title:$('schedule-title').value,due:new Date($('schedule-due').value).getTime()/1000,interval:$('schedule-interval').value?Number($('schedule-interval').value):null})});await loadSchedules();});
$('graph-json').value=JSON.stringify({goal:'Inspect machine and workspace',nodes:[{id:'system',tool:'system.status',expect:{field:'ram_total',nonempty:true}},{id:'files',tool:'files.list',arguments:{path:'.'}}]},null,2);
$('graph-form').onsubmit=guarded(async event=>{event.preventDefault();const run=await api('plans',{method:'POST',body:JSON.stringify(JSON.parse($('graph-json').value))});selected=run.id;showView('control');await refresh();});
let poll;
(async()=>{try{if(!token)throw new Error('Open the private launch link printed by Jarvis to connect. The access token stays in this browser tab.');const first=await refresh();connect();if(!first.setup_complete)await settings();poll=setInterval(()=>refresh().catch(notice),3000);}catch(error){notice(error);$('connection').textContent='DISCONNECTED';}})();
window.addEventListener('pagehide',()=>{stopped=true;clearInterval(poll);socket?.close();voice.interrupt();});
