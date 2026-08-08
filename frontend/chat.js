const messagesEl=document.getElementById("messages"),inputEl=document.getElementById("input"),
sendBtn=document.getElementById("sendBtn"),imageInput=document.getElementById("imageInput"),
audioInput=document.getElementById("audioInput"),fileHint=document.getElementById("fileHint"),
newChatBtn=document.getElementById("newChatBtn"),llmStatus=document.getElementById("llmStatus"),
historyList=document.getElementById("historyList");

let sessionId="sess-"+Math.random().toString(36).slice(2,10);
let pendingFile=null,busy=false;

function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!==undefined)e.innerHTML=h;return e;}
function scrollDown(){messagesEl.scrollTop=messagesEl.scrollHeight;}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function addUser(t){const w=el("div","msg user");w.appendChild(el("div","avatar","🧑"));w.appendChild(el("div","bubble",esc(t)));messagesEl.appendChild(w);scrollDown();}
function addBot(){const w=el("div","msg bot");w.appendChild(el("div","avatar","🔍"));const b=el("div","bubble"),s=el("div","steps"),a=el("div","answer");b.appendChild(s);b.appendChild(a);w.appendChild(b);messagesEl.appendChild(w);scrollDown();return{bubble:b,steps:s,answer:a,tot:null};}
function addBotText(t){const w=el("div","msg bot");w.appendChild(el("div","avatar","🔍"));const b=el("div","bubble");b.appendChild(el("div","answer",esc(t)));w.appendChild(b);messagesEl.appendChild(w);return b;}
function addStep(se,t){const p=se.querySelector(".step:not(.done)");if(p)p.classList.add("done");const s=el("div","step");s.appendChild(el("span","spin"));s.appendChild(el("span","",esc(t)));se.appendChild(s);scrollDown();}
function finish(se){se.querySelectorAll(".step:not(.done)").forEach(s=>s.classList.add("done"));}
function ensureTot(ctx){if(ctx.tot)return ctx.tot;const p=el("div","tot-panel");p.appendChild(el("div","tot-title","🌳 Tree of Thought"));ctx.steps.after(p);ctx.tot=p;return p;}
function addBranch(ctx,n,sc){const p=ensureTot(ctx),r=el("div","branch-row");r.appendChild(el("div","branch-name",esc(n)));const bar=el("div","branch-bar"),f=el("div","branch-fill");bar.appendChild(f);r.appendChild(bar);r.appendChild(el("div","branch-score",Math.round(sc*100)+"%"));p.appendChild(r);requestAnimationFrame(()=>{f.style.width=Math.round(sc*100)+"%";});scrollDown();}

function renderForensics(bubble,fg){
  if(!fg||fg.label==="not_checked")return;
  const card=el("div","forensics");card.appendChild(el("div","forensics-title","🔬 Image Forensics"));
  const row=el("div","forensics-row"),edited=fg.label==="likely_edited";
  row.appendChild(el("span","fchip "+(edited?"warn":"ok"),(edited?"⚠ Likely edited":"✓ Likely real")+" "+Math.round((fg.confidence||0)*100)+"%"));
  const sig=fg.signals||{};
  if(sig.ela&&sig.ela.score!=null)row.appendChild(el("span","fchip"+(sig.ela.flag?" warn":""),"ELA "+sig.ela.score));
  if(sig.exif){
    if(sig.exif.edited_software)row.appendChild(el("span","fchip warn","🚩 "+esc(sig.exif.software||"editor")));
    if(sig.exif.gps)row.appendChild(el("span","fchip","📍 "+sig.exif.gps.lat+", "+sig.exif.gps.lon));
    if(sig.exif.date)row.appendChild(el("span","fchip","📅 "+esc(sig.exif.date)));
    if(sig.exif.camera)row.appendChild(el("span","fchip","📷 "+esc(sig.exif.camera)));
  }
  if(sig.cnn&&sig.cnn.p_fake!=null)row.appendChild(el("span","fchip"+(sig.cnn.p_fake>=0.5?" warn":""),"CNN P(fake) "+sig.cnn.p_fake));
  card.appendChild(row);
  if(fg.reasons&&fg.reasons.length)card.appendChild(el("div","forensics-reasons","• "+fg.reasons.join(" • ")));
  bubble.appendChild(card);scrollDown();
}
function renderVerdict(bubble,v){
  const card=el("div","verdict-card"),conf=Math.round((v.confidence||0)*100);
  const head=el("div","verdict-head");
  head.appendChild(el("span","verdict-badge v-"+v.verdict,esc(v.verdict)));
  if(v.is_legal)head.appendChild(el("span","legal-chip","⚖️ Legal"));
  if(v.reflection&&Object.keys(v.reflection).length)head.appendChild(el("span","reflect-chip","✓ Reflected"));
  const cw=el("div","conf-wrap");cw.appendChild(el("div","conf-label",`<span>Confidence</span><span>${conf}%</span>`));
  const bar=el("div","conf-bar"),f=el("div","conf-fill");bar.appendChild(f);cw.appendChild(bar);head.appendChild(cw);card.appendChild(head);
  if(v.needs_human_review)card.appendChild(el("div","review-flag","⚠️ High-impact — flagged for human review."));
  if(v.evidence&&v.evidence.length){
    const bl=el("div","evidence-block");bl.appendChild(el("div","evidence-title","Evidence"));
    v.evidence.forEach(e=>{const it=el("div","evidence-item"),st=(e.source_type==="legal")?"legal":(e.stance||"neutral");
      it.appendChild(el("span","stance-tag st-"+st,st));const bo=el("div","ev-body"),sr=el("div","ev-source");
      sr.innerHTML=(e.url?`<a href="${e.url}" target="_blank" rel="noopener">${esc(e.title||e.url)}</a>`:esc(e.title||"Source"))+`<span class="ev-type">${esc(e.source_type||"web")}</span>`;
      bo.appendChild(sr);if(e.snippet)bo.appendChild(el("div","ev-snippet",esc(e.snippet)));it.appendChild(bo);bl.appendChild(it);});
    card.appendChild(bl);}
  bubble.appendChild(card);
  if(v.forgery)renderForensics(bubble,v.forgery);
  requestAnimationFrame(()=>{f.style.width=conf+"%";});scrollDown();
}

/* ===== Chat history sidebar ===== */
async function loadHistory(){
  try{
    const r=await fetch("/api/v1/sessions");const j=await r.json();
    const list=j.sessions||[];
    if(!list.length){historyList.innerHTML='<div class="history-empty">No past checks yet</div>';return;}
    historyList.innerHTML="";
    list.forEach(s=>{
      const item=el("div","history-item"+(s.id===sessionId?" active":""));
      item.dataset.id=s.id;
      item.appendChild(el("span","h-dot hv-"+(s.last_verdict||"none")));
      item.appendChild(el("span","h-title",esc(s.title||"New verification")));
      item.addEventListener("click",()=>openSession(s.id));
      historyList.appendChild(item);
    });
  }catch{/* ignore */}
}
async function openSession(id){
  if(busy)return;
  sessionId=id;
  try{
    const r=await fetch("/api/v1/sessions/"+id);const d=await r.json();
    messagesEl.innerHTML="";
    let vi=0;const verdicts=d.verdicts||[];
    (d.messages||[]).forEach(m=>{
      if(m.role==="user")addUser(m.content);
      else{
        const b=addBotText(m.content);
        // attach the matching verdict card (in order) to assistant messages that have one
        if(vi<verdicts.length){renderVerdict(b,verdicts[vi]);vi++;}
      }
    });
    // highlight active in sidebar
    document.querySelectorAll(".history-item").forEach(x=>x.classList.toggle("active",x.dataset.id===id));
    scrollDown();
  }catch{fileHint.textContent="⚠️ Couldn't load that chat.";}
}

async function send(){
  if(busy)return;const text=inputEl.value.trim();if(!text&&!pendingFile)return;
  let inputType=pendingFile?pendingFile.type:"text";
  addUser(text||`(${inputType} file: ${pendingFile.file.name})`);
  inputEl.value="";inputEl.style.height="auto";busy=true;sendBtn.disabled=true;
  const ctx=addBot();
  const fd=new FormData();fd.append("session_id",sessionId);fd.append("message",text);fd.append("input_type",inputType);
  if(pendingFile)fd.append("file",pendingFile.file);pendingFile=null;fileHint.textContent="";
  try{
    const resp=await fetch("/api/v1/chat",{method:"POST",body:fd});
    const rd=resp.body.getReader(),dec=new TextDecoder();let buf="",cur=null;
    while(true){const{value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});
      const parts=buf.split("\n\n");buf=parts.pop();
      for(const part of parts){const line=part.trim();if(!line.startsWith("data:"))continue;
        let p;try{p=JSON.parse(line.slice(5).trim());}catch{continue;}
        switch(p.event){
          case"step":addStep(ctx.steps,p.text);break;
          case"branch":addBranch(ctx,p.name,p.score);break;
          case"answer_start":finish(ctx.steps);cur=el("span","cursor");ctx.answer.appendChild(cur);break;
          case"answer_chunk":{const n=document.createTextNode(p.text);if(cur)ctx.answer.insertBefore(n,cur);else ctx.answer.appendChild(n);scrollDown();break;}
          case"verdict":renderVerdict(ctx.bubble,p);break;
          case"done":if(cur)cur.remove();break;
        }
      }
    }
  }catch(err){ctx.answer.appendChild(el("div","","⚠️ Connection error: "+esc(String(err))));}
  finally{busy=false;sendBtn.disabled=false;inputEl.focus();loadHistory();}
}

sendBtn.addEventListener("click",send);
inputEl.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
inputEl.addEventListener("input",()=>{inputEl.style.height="auto";inputEl.style.height=Math.min(inputEl.scrollHeight,170)+"px";});
imageInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"image"};fileHint.textContent="🖼️ Image ready: "+pendingFile.file.name+" — press send.";}});
audioInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"audio"};fileHint.textContent="🎙️ Audio ready: "+pendingFile.file.name+" — press send.";}});
document.querySelectorAll(".chip").forEach(c=>c.addEventListener("click",()=>{inputEl.value=c.dataset.ex;inputEl.focus();}));

/* New Verification = fresh session (keeps history in sidebar) */
newChatBtn.addEventListener("click",()=>{
  sessionId="sess-"+Math.random().toString(36).slice(2,10);
  messagesEl.innerHTML="";
  addBotText("New verification started. Submit a claim as text, audio, or image.");
  document.querySelectorAll(".history-item").forEach(x=>x.classList.remove("active"));
  fileHint.textContent="";inputEl.focus();
});

/* ===== Mic dropdown: Record (live) or Upload ===== */
const micBtn=document.getElementById("micBtn"),micMenu=document.getElementById("micMenu"),
  recordItem=document.getElementById("recordItem"),uploadItem=document.getElementById("uploadItem");
let mediaRecorder=null,recChunks=[],recTimer=null,recSeconds=0,recBarEl=null;
micBtn.addEventListener("click",e=>{e.stopPropagation();micMenu.hidden=!micMenu.hidden;});
document.addEventListener("click",()=>{micMenu.hidden=true;});
uploadItem.addEventListener("click",()=>{micMenu.hidden=true;audioInput.click();});
recordItem.addEventListener("click",()=>{micMenu.hidden=true;startRecording();});
function fmtTime(s){const m=Math.floor(s/60),ss=s%60;return `${m}:${ss<10?"0":""}${ss}`;}
function showRecBar(){
  recBarEl=el("div","recording-bar");
  recBarEl.innerHTML=`<span class="rec-dot"></span><span class="rec-time" id="recTime">0:00</span>
    <span class="rec-label">Recording… speak your claim</span>
    <button class="rec-btn rec-stop" id="recStop">Stop &amp; use</button>
    <button class="rec-btn rec-cancel" id="recCancel">Cancel</button>`;
  fileHint.after(recBarEl);
  document.getElementById("recStop").addEventListener("click",()=>stopRecording(true));
  document.getElementById("recCancel").addEventListener("click",()=>stopRecording(false));
}
function clearRecBar(){if(recBarEl){recBarEl.remove();recBarEl=null;}if(recTimer){clearInterval(recTimer);recTimer=null;}recSeconds=0;}
async function startRecording(){
  if(!navigator.mediaDevices||!window.MediaRecorder){fileHint.textContent="⚠️ Mic recording not supported — use Upload.";return;}
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    recChunks=[];mediaRecorder=new MediaRecorder(stream);
    mediaRecorder.ondataavailable=ev=>{if(ev.data.size>0)recChunks.push(ev.data);};
    mediaRecorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());};
    mediaRecorder.start();showRecBar();
    recTimer=setInterval(()=>{recSeconds++;const t=document.getElementById("recTime");if(t)t.textContent=fmtTime(recSeconds);},1000);
  }catch{fileHint.textContent="⚠️ Mic access denied. Allow microphone or use Upload.";}
}
function stopRecording(useIt){
  if(!mediaRecorder)return;
  if(mediaRecorder.state!=="inactive")mediaRecorder.stop();
  const captured=recSeconds;clearRecBar();
  if(useIt){setTimeout(()=>{
    const blob=new Blob(recChunks,{type:"audio/webm"});
    const file=new File([blob],"mic-recording.webm",{type:"audio/webm"});
    pendingFile={file:file,type:"audio"};
    fileHint.textContent=`🎙️ Recording ready (${fmtTime(captured)}) — press send to verify.`;
  },200);}else{fileHint.textContent="";}
  mediaRecorder=null;
}

/* ===== init ===== */
loadHistory();
(async()=>{try{const r=await fetch("/health"),j=await r.json();
  if(j.llm_configured){llmStatus.textContent="● "+j.keys+" keys ready";llmStatus.className="llm-status ok";}
  else{llmStatus.textContent="● no API key";llmStatus.className="llm-status off";}
}catch{llmStatus.textContent="● offline";llmStatus.className="llm-status off";}})();
