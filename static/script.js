let state = {};
let editingChannel = null;
let loading = false;
let refreshTimer = null;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const fmtUptime = s => {
  s=Number(s||0); const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
};
async function api(url, opts={}) {
  const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts});
  const d=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(d.error||d.message||`HTTP ${r.status}`);
  return d;
}
async function loadAll(force=false){
  if(loading && !force)return;
  loading=true;
  try{
    const d=await api('/api/state');
    state=d.channels||{};
    const dash=d.dashboard||{};
    $('statChannels').textContent=dash.channels||0;
    $('statRunning').textContent=dash.running_channels||0;
    $('statOutputs').textContent=dash.outputs||0;
    $('statRunningOutputs').textContent=dash.running_outputs||0;
    $('logs').textContent=(d.logs||[]).map(x=>`[${x.created_at}] [${x.level}] ${x.message}`).join('\n')||'لا توجد سجلات.';
    renderChannels();
  }catch(e){console.error(e)}
  finally{loading=false}
}
function renderChannels(){
  const box=$('channels'), list=Object.values(state);
  if(!list.length){box.innerHTML='<div class="empty">لا توجد قنوات. أضف أول قناة للبدء.</div>';return}
  box.innerHTML=list.map(c=>{
    const outs=c.outputs.map(o=>`
      <div class="output">
        <div class="output-row">
          <div>
            <div class="output-name">${esc(o.name)}</div>
            <div class="meta">${esc(o.protocol.toUpperCase())} · ${esc(modeLabel(o.mode))} · ${o.status==='running'?'يعمل':'متوقف'}</div>
          </div>
          <span class="badge ${o.status==='running'?'run':'stop'}">${o.status==='running'?'● LIVE':'○ OFF'}</span>
        </div>
        <div class="meta">Uptime: ${fmtUptime(o.uptime)} · PID: ${o.pid||'-'} · Retries: ${o.retries||0}</div>
        <div class="quick-key">
          <span class="key-label">المفتاح</span>
          <input id="quickKey_${o.id}" type="password" placeholder="${o.has_key?'•••••••• (أدخل الجديد فقط)':'أدخل Stream Key'}" autocomplete="off">
          <button class="btn ghost small" onclick="quickKey('${o.id}')">حفظ المفتاح</button>
        </div>
        <div class="actions">
          ${o.status==='running'
            ? `<button class="btn danger small" onclick="outputAction('${o.id}','stop',this)">إيقاف</button>`
            : `<button class="btn primary small" onclick="outputAction('${o.id}','start',this)">تشغيل</button>`}
          <button class="btn blue small" onclick="outputAction('${o.id}','restart',this)">إعادة تشغيل</button>
          <button class="btn ghost small" onclick="editChannel('${c.id}')">إعدادات</button>
          <button class="btn danger small" onclick="deleteOutput('${o.id}')">حذف</button>
        </div>
      </div>`).join('');
    return `<article class="channel">
      <div class="channel-head">
        <div><div class="channel-title">${esc(c.name)}</div><div class="source">${esc(c.source)}</div></div>
        <span class="badge ${c.running?'run':'stop'}">${c.running?'● RUNNING':'○ STOPPED'}</span>
      </div>
      ${outs||'<div class="empty" style="margin:14px">لا توجد مخارج</div>'}
      <div class="actions channel-actions">
        <button class="btn primary small" onclick="startChannel('${c.id}')">▶ الكل</button>
        <button class="btn danger small" onclick="stopChannel('${c.id}')">■ الكل</button>
        <button class="btn blue small" onclick="editChannel('${c.id}')">⚙ القناة</button>
        <button class="btn ghost small" onclick="addOutput('${c.id}',true)">＋ بنفس الإعدادات</button>
        <button class="btn ghost small" onclick="addOutput('${c.id}',false)">＋ إعدادات جديدة</button>
        <button class="btn ghost small" onclick="previewChannel('${c.id}')">👁 معاينة</button>
        <button class="btn ghost small" onclick="probeChannel('${c.id}')">🔎 Probe</button>
        <button class="btn danger small" onclick="deleteChannel('${c.id}')">حذف</button>
      </div>
    </article>`;
  }).join('');
}
function modeLabel(m){return {copy:'COPY',audio_copy:'Video Copy + Audio',transcode:'Transcode'}[m]||m}
function channelForm(c=null){
 return `<div class="form">
  <div class="grid2">
   <div class="field"><label>اسم القناة</label><input id="cName" value="${esc(c?.name||'Football HD')}"></div>
   <div class="field"><label>Source URL</label><input id="cSource" value="${esc(c?.source||'')}" placeholder="https://...m3u8 / rtmp:// / rtsp://"></div>
  </div>
  <div class="field"><label>الوصف</label><textarea id="cDesc">${esc(c?.description||'')}</textarea></div>
  <details class="advanced"><summary>Logo / Processing</summary>
   <div class="grid2">
    <div class="field"><label>رفع شعار</label><input id="logoFile" type="file" accept=".png,.jpg,.jpeg,.webp"></div>
    <div class="field"><label>Logo path</label><input id="logoPath" value="${esc(c?.logo_path||'')}"></div>
    <div class="field"><label>الموقع</label><select id="logoPosition">${['top-left','top-right','bottom-left','bottom-right','center'].map(x=>`<option ${x===(c?.logo_position||'top-right')?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>الحجم %</label><input id="logoScale" type="number" min="5" max="50" value="${Math.round((c?.logo_scale||0.15)*100)}"></div>
   </div>
  </details>
  <div class="grid2">
   <label class="check"><input id="cEnabled" type="checkbox" ${c?.enabled!==false&&c?.enabled!==0?'checked':''}> Enabled</label>
   <label class="check"><input id="cAuto" type="checkbox" ${c?.auto_start?'checked':''}> Auto start</label>
  </div>
  <div class="actions"><button class="btn primary" onclick="saveChannel()">حفظ القناة</button><button class="btn ghost" onclick="closeModal()">إلغاء</button></div>
  ${c?`<div class="subhead">Outputs</div><div id="modalOutputs">${c.outputs.map(outputEditor).join('')}</div>`:''}
 </div>`;
}
function outputEditor(o){
 return `<div class="output-list" id="editor_${o.id}">
  <div class="output-editor-head"><b>${esc(o.name)}</b><span class="badge ${o.status==='running'?'run':'stop'}">${o.status==='running'?'LIVE':'OFF'}</span></div>
  <div class="form">
   <div class="grid2">
    <div class="field"><label>اسم Output</label><input id="oName_${o.id}" value="${esc(o.name)}"></div>
    <div class="field"><label>المنصة</label><select id="oProtocol_${o.id}">${['rtmp','rtmps','srt','mpegts'].map(x=>`<option ${x===o.protocol?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>Server</label><select id="oServer_${o.id}">${serverOptions(o.server)}</select></div>
    <div class="field"><label>Stream Key</label><input id="oKey_${o.id}" type="password" value="${esc(o.stream_key||'')}" placeholder="أدخل المفتاح"></div>
    <div class="field"><label>طريقة البث</label><select id="oMode_${o.id}">${[['copy','COPY - بدون معالجة'],['audio_copy','Video COPY + Audio'],['transcode','تحسين / معالجة']].map(x=>`<option value="${x[0]}" ${x[0]===o.mode?'selected':''}>${x[1]}</option>`).join('')}</select></div>
    <div class="field"><label>جودة جاهزة</label><select id="oQuality_${o.id}">
      ${[['balanced','متوازن'],['football','Football'],['clean','Clean'],['sharp','Sharp'],['high','High Quality'],['custom','Custom']].map(x=>`<option value="${x[0]}" ${x[0]===(o.quality_preset||'balanced')?'selected':''}>${x[1]}</option>`).join('')}
    </select></div>
    <div class="field"><label>الدقة</label><select id="oRes_${o.id}">${['1920x1080','1280x720','854x480','640x360'].map(x=>`<option ${x===o.resolution?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>FPS</label><select id="oFps_${o.id}">${[25,30,50,60].map(x=>`<option ${x==o.fps?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>Bitrate</label><select id="oBit_${o.id}">${['1500k','2500k','3500k','5000k','6000k','8000k'].map(x=>`<option ${x===o.video_bitrate?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>ترميز الفيديو</label><select id="oCodec_${o.id}">${['libx264','libx265','h264_nvenc','hevc_nvenc','h264_qsv','h264_amf'].map(x=>`<option ${x===o.video_codec?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>Preset</label><select id="oPreset_${o.id}">${['ultrafast','superfast','veryfast','faster','fast','medium'].map(x=>`<option ${x===o.preset?'selected':''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>Audio</label><select id="oABit_${o.id}">${['96k','128k','160k','192k'].map(x=>`<option ${x===o.audio_bitrate?'selected':''}>${x}</option>`).join('')}</select></div>
   </div>
   <details class="advanced">
    <summary>تحسين الصورة والفلاتر</summary>
    <label class="check"><input id="oFilters_${o.id}" type="checkbox" ${o.filters_enabled?'checked':''}> تفعيل الفلاتر</label>
    <div class="grid2 filter-grid">
      <div class="field"><label>Sharpen</label><input id="oSharpen_${o.id}" type="range" min="0" max="2" step=".1" value="${o.sharpen||0}" oninput="rangeVal(this)"><output>${o.sharpen||0}</output></div>
      <div class="field"><label>Denoise</label><select id="oDenoise_${o.id}">${['off','light','medium','strong'].map(x=>`<option ${x===o.denoise?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Deblock</label><select id="oDeblock_${o.id}">${['off','light','medium'].map(x=>`<option ${x===o.deblock?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Brightness</label><input id="oBrightness_${o.id}" type="range" min="-.1" max=".1" step=".01" value="${o.brightness||0}" oninput="rangeVal(this)"><output>${o.brightness||0}</output></div>
      <div class="field"><label>Contrast</label><input id="oContrast_${o.id}" type="range" min=".8" max="1.2" step=".01" value="${o.contrast||1}" oninput="rangeVal(this)"><output>${o.contrast||1}</output></div>
      <div class="field"><label>Saturation</label><input id="oSaturation_${o.id}" type="range" min=".8" max="1.3" step=".01" value="${o.saturation||1}" oninput="rangeVal(this)"><output>${o.saturation||1}</output></div>
      <div class="field"><label>Gamma</label><input id="oGamma_${o.id}" type="range" min=".8" max="1.2" step=".01" value="${o.gamma||1}" oninput="rangeVal(this)"><output>${o.gamma||1}</output></div>
      <div class="field"><label>Scaling</label><select id="oScaling_${o.id}">${['lanczos','bicubic','bilinear','fast_bilinear'].map(x=>`<option ${x===(o.scaling||'lanczos')?'selected':''}>${x}</option>`).join('')}</select></div>
    </div>
   </details>
   <details class="advanced"><summary>إعدادات متقدمة</summary>
    <div class="grid2">
      <div class="field"><label>GOP</label><input id="oGop_${o.id}" type="number" value="${o.gop||60}"></div>
      <div class="field"><label>Audio Sample Rate</label><select id="oRate_${o.id}">${[44100,48000].map(x=>`<option ${x==o.sample_rate?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label>Audio Channels</label><select id="oChannels_${o.id}"><option ${o.audio_channels==2?'selected':''}>2</option><option ${o.audio_channels==1?'selected':''}>1</option></select></div>
      <div class="field"><label>Profile</label><select id="oProfile_${o.id}"><option value="" ${!o.profile?'selected':''}>Auto</option><option ${o.profile==='high'?'selected':''}>high</option><option ${o.profile==='main'?'selected':''}>main</option></select></div>
    </div>
    <div class="field"><label>Extra FFmpeg Args</label><input id="oExtra_${o.id}" value="${esc(o.extra_args)}" placeholder="-maxrate 3000k -bufsize 6000k"></div>
   </details>
   <div class="grid2">
    <label class="check"><input id="oEnabled_${o.id}" type="checkbox" ${o.enabled?'checked':''}> Enabled</label>
    <label class="check"><input id="oAuto_${o.id}" type="checkbox" ${o.auto_start?'checked':''}> Auto start</label>
   </div>
   <div class="actions"><button class="btn primary small" onclick="saveOutput('${o.id}')">حفظ Output</button><button class="btn danger small" onclick="deleteOutput('${o.id}')">حذف</button></div>
  </div>
 </div>`;
}
function serverOptions(current){
 const opts=['rtmp://example.com/live','rtmps://example.com/live','srt://example.com:9000'];
 if(current && !opts.includes(current)) opts.unshift(current);
 return opts.map(x=>`<option ${x===current?'selected':''}>${esc(x)}</option>`).join('');
}
function rangeVal(el){el.nextElementSibling.value=el.value}
function openChannelModal(){editingChannel=null;$('modalTitle').textContent='قناة جديدة';$('modalBody').innerHTML=channelForm();$('modal').classList.remove('hidden');bindLogo()}
function closeModal(){$('modal').classList.add('hidden')}
function editChannel(id){const c=state[id];if(!c)return;editingChannel=id;$('modalTitle').textContent=`إعدادات: ${c.name}`;$('modalBody').innerHTML=channelForm(c);$('modal').classList.remove('hidden');bindLogo()}
function bindLogo(){const f=$('logoFile');if(f)f.addEventListener('change',uploadLogo)}
async function uploadLogo(e){const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('logo',f);const r=await fetch('/upload_logo',{method:'POST',body:fd});const d=await r.json();if(d.path)$('logoPath').value=d.path;else alert(d.error||'فشل الرفع')}
async function saveChannel(){
 const payload={name:$('cName').value,source:$('cSource').value,description:$('cDesc').value,logo_path:$('logoPath')?.value||'',logo_position:$('logoPosition')?.value||'top-right',logo_scale:Number($('logoScale')?.value||15)/100,enabled:$('cEnabled').checked,auto_start:$('cAuto').checked};
 try{if(editingChannel)await api('/api/channels/'+editingChannel,{method:'PUT',body:JSON.stringify(payload)});else await api('/api/channels',{method:'POST',body:JSON.stringify(payload)});closeModal();await loadAll(true)}catch(e){alert(e.message)}
}
async function addOutput(channelId,clone=true){
 const c=state[channelId];if(!c)return;
 const base=clone&&c.outputs.length?c.outputs[0]:{};
 const data={...base,name:`Output ${c.outputs.length+1}`,server:clone&&base.server?base.server:'rtmp://example.com/live',stream_key:'',start:false};
 ['id','channel_id','created_at','updated_at','status','uptime','pid','returncode','retries','has_key'].forEach(k=>delete data[k]);
 try{await api(`/api/channels/${channelId}/outputs`,{method:'POST',body:JSON.stringify(data)});await loadAll(true);editChannel(channelId)}catch(e){alert(e.message)}
}
async function editOutput(id){const o=findOutput(id);if(o)editChannel(o.channel_id)}
function findOutput(id){for(const c of Object.values(state)){const o=c.outputs.find(x=>x.id===id);if(o)return o}return null}
async function saveOutput(id){
 const v=k=>$(k+'_'+id)?.value; const b=k=>$(k+'_'+id)?.checked;
 const payload={
  name:v('oName'),protocol:v('oProtocol'),server:v('oServer'),stream_key:v('oKey'),mode:v('oMode'),
  quality_preset:v('oQuality'),video_codec:v('oCodec'),resolution:v('oRes'),fps:Number(v('oFps')),
  video_bitrate:v('oBit'),preset:v('oPreset'),gop:Number(v('oGop')||60),profile:v('oProfile')||'',
  audio_codec:'aac',audio_bitrate:v('oABit'),sample_rate:Number(v('oRate')||48000),
  audio_channels:Number(v('oChannels')||2),extra_args:v('oExtra')||'',enabled:b('oEnabled'),
  auto_start:b('oAuto'),filters_enabled:b('oFilters'),sharpen:Number(v('oSharpen')||0),
  denoise:v('oDenoise'),deblock:v('oDeblock'),brightness:Number(v('oBrightness')||0),
  contrast:Number(v('oContrast')||1),saturation:Number(v('oSaturation')||1),
  gamma:Number(v('oGamma')||1),scaling:v('oScaling')
 };
 try{await api('/api/outputs/'+id,{method:'PUT',body:JSON.stringify(payload)});await loadAll(true);alert('تم الحفظ')}catch(e){alert(e.message)}
}
async function quickKey(id){
 const el=$('quickKey_'+id);const key=(el?.value||'').trim();if(!key)return alert('اكتب المفتاح الجديد');
 try{await api('/api/outputs/'+id+'/key',{method:'POST',body:JSON.stringify({stream_key:key})});el.value='';await loadAll(true);alert('تم تغيير المفتاح');}catch(e){alert(e.message)}
}
async function outputAction(id,action,btn){
 if(btn){btn.disabled=true;btn.dataset.old=btn.textContent;btn.textContent='جاري...'}
 try{await api('/api/outputs/'+id+'/'+action,{method:'POST'});setTimeout(()=>loadAll(true),250)}
 catch(e){alert(e.message);if(btn){btn.disabled=false;btn.textContent=btn.dataset.old}}
}
async function deleteOutput(id){if(confirm('حذف هذا الـ Output؟')){await api('/api/outputs/'+id,{method:'DELETE'});await loadAll(true)}}
async function startChannel(id){await api('/api/channels/'+id+'/start',{method:'POST'});setTimeout(()=>loadAll(true),250)}
async function stopChannel(id){await api('/api/channels/'+id+'/stop',{method:'POST'});await loadAll(true)}
async function deleteChannel(id){if(confirm('حذف القناة وكل مخارجها؟')){await api('/api/channels/'+id,{method:'DELETE'});await loadAll(true)}}
async function previewChannel(id){try{const d=await api('/api/channels/'+id+'/preview',{method:'POST'});const w=window.open();w.document.write(`<title>Preview</title><img style="max-width:100%" src="${d.preview}">`)}catch(e){alert(e.message)}}
async function probeChannel(id){try{const d=await api('/api/channels/'+id+'/probe',{method:'POST'});alert(JSON.stringify(d,null,2))}catch(e){alert(e.message)}}
loadAll(true);
refreshTimer=setInterval(()=>loadAll(false),2000);
