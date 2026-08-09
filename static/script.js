let state = {};
let editingChannel = null;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const fmtUptime = s => {
  s = Number(s||0); const h=Math.floor(s/3600), m=Math.floor((s%3600)/60), sec=s%60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
};

async function api(url, opts={}) {
  const r = await fetch(url, {headers:{'Content-Type':'application/json'}, ...opts});
  const d = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(d.error || d.message || `HTTP ${r.status}`);
  return d;
}

async function loadAll(){
  try{
    state = await api('/api/channels');
    renderChannels();
    const dash = await api('/api/dashboard');
    $('statChannels').textContent=dash.channels;
    $('statRunning').textContent=dash.running_channels;
    $('statOutputs').textContent=dash.outputs;
    $('statRunningOutputs').textContent=dash.running_outputs;
    const logs = await api('/api/logs?limit=250');
    $('logs').textContent = logs.map(x=>`[${x.created_at}] [${x.level}] ${x.message}`).join('\n') || 'لا توجد سجلات.';
  }catch(e){ console.error(e); }
}

function renderChannels(){
  const box=$('channels');
  const list=Object.values(state);
  if(!list.length){box.innerHTML='<div class="empty">لا توجد قنوات. أضف أول قناة للبدء.</div>';return}
  box.innerHTML=list.map(c=>{
    const outs=c.outputs.map(o=>`
      <div class="output">
        <div class="output-row">
          <div><div class="output-name">${esc(o.name)}</div><div class="meta">${esc(o.protocol.toUpperCase())} · ${esc(o.mode)} · ${o.status==='running'?'يعمل':'متوقف'}</div></div>
          <span class="badge ${o.status==='running'?'run':'stop'}">${o.status==='running'?'● LIVE':'○ OFF'}</span>
        </div>
        <div class="meta">Uptime: ${fmtUptime(o.uptime)} · PID: ${o.pid||'-'} · Retries: ${o.retries||0}</div>
        <div class="actions">
          ${o.status==='running'
            ? `<button class="btn danger small" onclick="outputAction('${o.id}','stop')">إيقاف</button>`
            : `<button class="btn primary small" onclick="outputAction('${o.id}','start')">تشغيل</button>`}
          <button class="btn blue small" onclick="outputAction('${o.id}','restart')">إعادة تشغيل</button>
          <button class="btn ghost small" onclick="editOutput('${o.id}')">إعدادات</button>
          <button class="btn danger small" onclick="deleteOutput('${o.id}')">حذف</button>
        </div>
      </div>`).join('');

    return `<article class="channel">
      <div class="channel-head">
        <div><div class="channel-title">${esc(c.name)}</div><div class="source">${esc(c.source)}</div></div>
        <span class="badge ${c.running?'run':'stop'}">${c.running?'● RUNNING':'○ STOPPED'}</span>
      </div>
      ${outs || '<div class="empty" style="margin:14px">لا توجد مخارج</div>'}
      <div class="actions" style="padding:0 17px 17px">
        <button class="btn primary small" onclick="startChannel('${c.id}')">▶ الكل</button>
        <button class="btn danger small" onclick="stopChannel('${c.id}')">■ الكل</button>
        <button class="btn blue small" onclick="editChannel('${c.id}')">⚙ القناة</button>
        <button class="btn ghost small" onclick="previewChannel('${c.id}')">👁 معاينة</button>
        <button class="btn ghost small" onclick="probeChannel('${c.id}')">🔎 Probe</button>
        <button class="btn danger small" onclick="deleteChannel('${c.id}')">حذف</button>
      </div>
    </article>`;
  }).join('');
}

function channelForm(c=null){
  return `<div class="form">
    <div class="grid2">
      <div class="field"><label>اسم القناة</label><input id="cName" value="${esc(c?.name||'Football HD')}"></div>
      <div class="field"><label>Source URL</label><input id="cSource" value="${esc(c?.source||'')}" placeholder="https://...m3u8 / rtmp:// / rtsp://"></div>
    </div>
    <div class="field"><label>الوصف</label><textarea id="cDesc">${esc(c?.description||'')}</textarea></div>
    <div class="subhead">Logo / Processing</div>
    <div class="grid2">
      <div class="field"><label>رفع شعار</label><input id="logoFile" type="file" accept=".png,.jpg,.jpeg,.webp"></div>
      <div class="field"><label>Logo path</label><input id="logoPath" value="${esc(c?.logo_path||'')}" placeholder="اتركه فارغًا بدون شعار"></div>
      <div class="field"><label>الموقع</label><select id="logoPosition">
        ${['top-left','top-right','bottom-left','bottom-right','center'].map(x=>`<option ${x===(c?.logo_position||'top-right')?'selected':''}>${x}</option>`).join('')}
      </select></div>
      <div class="field"><label>الحجم %</label><input id="logoScale" type="number" min="5" max="50" value="${Math.round((c?.logo_scale||0.15)*100)}"></div>
    </div>
    <div class="grid2">
      <label class="check"><input id="cEnabled" type="checkbox" ${c?.enabled!==false&&c?.enabled!==0?'checked':''}> Enabled</label>
      <label class="check"><input id="cAuto" type="checkbox" ${c?.auto_start?'checked':''}> Auto start after restart</label>
    </div>
    <div class="actions">
      <button class="btn primary" onclick="saveChannel()">حفظ القناة</button>
      ${c?`<button class="btn blue" onclick="addOutput('${c.id}')">＋ إضافة Output</button>`:''}
      <button class="btn ghost" onclick="closeModal()">إلغاء</button>
    </div>
    ${c?`<div class="subhead">Outputs</div><div id="modalOutputs">${c.outputs.map(outputEditor).join('')}</div>`:''}
  </div>`;
}

function outputEditor(o){
  return `<div class="output-list"><div class="form">
    <div class="grid2">
      <div class="field"><label>اسم Output</label><input id="oName_${o.id}" value="${esc(o.name)}"></div>
      <div class="field"><label>Protocol</label><select id="oProtocol_${o.id}">${['rtmp','rtmps','srt','mpegts'].map(x=>`<option ${x===o.protocol?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Server URL</label><input id="oServer_${o.id}" value="${esc(o.server)}"></div>
      <div class="field"><label>Stream Key</label><input id="oKey_${o.id}" value="${esc(o.stream_key||'')}" type="password"></div>
      <div class="field"><label>Mode</label><select id="oMode_${o.id}">${[['copy','COPY: بدون إعادة ترميز'],['audio_copy','VIDEO COPY + AUDIO'],['transcode','FULL TRANSCODE']].map(x=>`<option value="${x[0]}" ${x[0]===o.mode?'selected':''}>${x[1]}</option>`).join('')}</select></div>
      <div class="field"><label>Video Codec</label><select id="oCodec_${o.id}">${['libx264','libx265','h264_nvenc','hevc_nvenc','h264_qsv','h264_amf'].map(x=>`<option ${x===o.video_codec?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Resolution</label><input id="oRes_${o.id}" value="${esc(o.resolution)}"></div>
      <div class="field"><label>FPS</label><input id="oFps_${o.id}" type="number" value="${o.fps}"></div>
      <div class="field"><label>Bitrate</label><input id="oBit_${o.id}" value="${esc(o.video_bitrate)}"></div>
      <div class="field"><label>Preset</label><input id="oPreset_${o.id}" value="${esc(o.preset)}"></div>
      <div class="field"><label>GOP / Keyframe</label><input id="oGop_${o.id}" type="number" value="${o.gop}"></div>
      <div class="field"><label>Profile</label><input id="oProfile_${o.id}" value="${esc(o.profile)}" placeholder="high"></div>
      <div class="field"><label>Level</label><input id="oLevel_${o.id}" value="${esc(o.level)}" placeholder="4.1"></div>
      <div class="field"><label>Pixel Format</label><input id="oPix_${o.id}" value="${esc(o.pix_fmt)}" placeholder="yuv420p"></div>
      <div class="field"><label>Tune</label><input id="oTune_${o.id}" value="${esc(o.tune)}" placeholder="zerolatency"></div>
      <div class="field"><label>Audio Codec</label><select id="oACodec_${o.id}">${['aac','copy','libopus','libmp3lame'].map(x=>`<option ${x===o.audio_codec?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Audio Bitrate</label><input id="oABit_${o.id}" value="${esc(o.audio_bitrate)}"></div>
      <div class="field"><label>Sample Rate</label><input id="oRate_${o.id}" type="number" value="${o.sample_rate}"></div>
      <div class="field"><label>Audio Channels</label><input id="oChannels_${o.id}" type="number" min="1" max="8" value="${o.audio_channels}"></div>
    </div>
    <div class="field"><label>Extra FFmpeg Args (متقدم)</label><input id="oExtra_${o.id}" value="${esc(o.extra_args)}" placeholder="-maxrate 3000k -bufsize 6000k"></div>
    <div class="grid2">
      <label class="check"><input id="oEnabled_${o.id}" type="checkbox" ${o.enabled?'checked':''}> Enabled</label>
      <label class="check"><input id="oAuto_${o.id}" type="checkbox" ${o.auto_start?'checked':''}> Auto start</label>
    </div>
    <div class="actions"><button class="btn primary small" onclick="saveOutput('${o.id}')">حفظ Output</button></div>
  </div></div>`;
}

function openChannelModal(){
  editingChannel=null; $('modalTitle').textContent='قناة جديدة'; $('modalBody').innerHTML=channelForm(); $('modal').classList.remove('hidden');
  $('logoFile').addEventListener('change', uploadLogo);
}
function closeModal(){ $('modal').classList.add('hidden'); }
async function editChannel(id){
  const c=state[id]; editingChannel=id; $('modalTitle').textContent=`إعدادات: ${c.name}`; $('modalBody').innerHTML=channelForm(c); $('modal').classList.remove('hidden');
  $('logoFile').addEventListener('change', uploadLogo);
}
async function uploadLogo(e){
  const f=e.target.files[0]; if(!f)return;
  const fd=new FormData(); fd.append('logo',f);
  const r=await fetch('/upload_logo',{method:'POST',body:fd}); const d=await r.json();
  if(d.path) $('logoPath').value=d.path; else alert(d.error||'فشل الرفع');
}

async function saveChannel(){
  const payload={name:$('cName').value,source:$('cSource').value,description:$('cDesc').value,logo_path:$('logoPath').value,
    logo_position:$('logoPosition').value,logo_scale:Number($('logoScale').value)/100,enabled:$('cEnabled').checked,auto_start:$('cAuto').checked};
  try{
    if(editingChannel) await api('/api/channels/'+editingChannel,{method:'PUT',body:JSON.stringify(payload)});
    else await api('/api/channels',{method:'POST',body:JSON.stringify(payload)});
    closeModal(); await loadAll();
  }catch(e){alert(e.message)}
}

async function addOutput(channelId){
  const data={name:'Output '+((state[channelId]?.outputs?.length||0)+1),server:'rtmp://example.com/live',stream_key:'',mode:'transcode',start:false};
  try{await api(`/api/channels/${channelId}/outputs`,{method:'POST',body:JSON.stringify(data)}); await loadAll(); editChannel(channelId)}catch(e){alert(e.message)}
}

async function editOutput(outputId){
  const o=Object.values(state).flatMap(c=>c.outputs).find(x=>x.id===outputId); if(!o)return;
  const c=state[Object.keys(state).find(id=>state[id].outputs.some(x=>x.id===outputId))];
  editChannel(c.id);
}
async function saveOutput(id){
  const v=k=>$(k+'_'+id).value;
  const b=k=>$(k+'_'+id).checked;
  const payload={name:v('oName'),protocol:v('oProtocol'),server:v('oServer'),stream_key:v('oKey'),mode:v('oMode'),
    video_codec:v('oCodec'),resolution:v('oRes'),fps:Number(v('oFps')),video_bitrate:v('oBit'),preset:v('oPreset'),
    gop:Number(v('oGop')),profile:v('oProfile'),level:v('oLevel'),pix_fmt:v('oPix'),tune:v('oTune'),
    audio_codec:v('oACodec'),audio_bitrate:v('oABit'),sample_rate:Number(v('oRate')),audio_channels:Number(v('oChannels')),
    extra_args:v('oExtra'),enabled:b('oEnabled'),auto_start:b('oAuto')};
  try{await api('/api/outputs/'+id,{method:'PUT',body:JSON.stringify(payload)});alert('تم حفظ الـ Output');await loadAll();}catch(e){alert(e.message)}
}
async function outputAction(id,action){try{await api('/api/outputs/'+id+'/'+action,{method:'POST'});await loadAll()}catch(e){alert(e.message)}}
async function deleteOutput(id){if(confirm('حذف هذا الـ Output؟')){await api('/api/outputs/'+id,{method:'DELETE'});await loadAll()}}
async function startChannel(id){await api('/api/channels/'+id+'/start',{method:'POST'});await loadAll()}
async function stopChannel(id){await api('/api/channels/'+id+'/stop',{method:'POST'});await loadAll()}
async function deleteChannel(id){if(confirm('حذف القناة وكل مخارجها؟')){await api('/api/channels/'+id,{method:'DELETE'});await loadAll()}}
async function previewChannel(id){
  try{const d=await api('/api/channels/'+id+'/preview',{method:'POST'});const w=window.open();w.document.write(`<title>Preview</title><img style="max-width:100%" src="${d.preview}">`)}catch(e){alert(e.message)}
}
async function probeChannel(id){
  try{const d=await api('/api/channels/'+id+'/probe',{method:'POST'});alert(JSON.stringify(d,null,2))}catch(e){alert(e.message)}
}
setInterval(loadAll,5000); loadAll();
