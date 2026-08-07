const messagesEl=document.getElementById("messages"),inputEl=document.getElementById("input"),
sendBtn=document.getElementById("sendBtn"),imageInput=document.getElementById("imageInput"),
audioInput=document.getElementById("audioInput"),fileHint=document.getElementById("fileHint"),
newChatBtn=document.getElementById("newChatBtn"),llmStatus=document.getElementById("llmStatus");
const sessionId="sess-"+Math.random().toString(36).slice(2,10);
let pendingFile=null,busy=false;
function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!==undefined)e.innerHTML=h;return e;}
function scrollDown(){messagesEl.scrollTop=messagesEl.scrollHeight;}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function addUser(t){const w=el("div","msg user");w.appendChild(el("div","avatar","🧑"));w.appendChild(el("div","bubble",esc(t)));messagesEl.appendChild(w);scrollDown();}
function addBot(){const w=el("div","msg bot");w.appendChild(el("div","avatar","🔍"));const b=el("div","bubble"),s=el("div","steps"),a=el("div","answer");b.appendChild(s);b.appendChild(a);w.appendChild(b);messagesEl.appendChild(w);scrollDown();return{bubble:b,steps:s,answer:a,tot:null};}
function addStep(se,t){const p=se.querySelector(".step:not(.done)");if(p)p.classList.add("done");const s=el("div","step");s.appendChild(el("span","spin"));s.appendChild(el("span","",esc(t)));se.appendChild(s);scrollDown();}
function finish(se){se.querySelectorAll(".step:not(.done)").forEach(s=>s.classList.add("done"));}
function ensureTot(ctx){if(ctx.tot)return ctx.tot;const p=el("div","tot-panel");p.appendChild(el("div","tot-title","🌳 Tree of Thought"));ctx.steps.after(p);ctx.tot=p;return p;}
function addBranch(ctx,n,sc){const p=ensureTot(ctx),r=el("div","branch-row");r.appendChild(el("div","branch-name",esc(n)));const bar=el("div","branch-bar"),f=el("div","branch-fill");bar.appendChild(f);r.appendChild(bar);r.appendChild(el("div","branch-score",Math.round(sc*100)+"%"));p.appendChild(r);requestAnimationFrame(()=>{f.style.width=Math.round(sc*100)+"%";});scrollDown();}
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
  bubble.appendChild(card);requestAnimationFrame(()=>{f.style.width=conf+"%";});scrollDown();
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
  finally{busy=false;sendBtn.disabled=false;inputEl.focus();}
}
sendBtn.addEventListener("click",send);
inputEl.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
inputEl.addEventListener("input",()=>{inputEl.style.height="auto";inputEl.style.height=Math.min(inputEl.scrollHeight,170)+"px";});
imageInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"image"};fileHint.textContent="🖼️ Image ready: "+pendingFile.file.name+" — press send.";}});
audioInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"audio"};fileHint.textContent="🎙️ Audio ready: "+pendingFile.file.name+" — press send.";}});
document.querySelectorAll(".chip").forEach(c=>c.addEventListener("click",()=>{inputEl.value=c.dataset.ex;inputEl.focus();}));
newChatBtn.addEventListener("click",async()=>{try{await fetch("/api/v1/reset",{method:"POST",body:new URLSearchParams({session_id:sessionId})});}catch{}location.reload();});
(async()=>{try{const r=await fetch("/health"),j=await r.json();
  if(j.llm_configured){llmStatus.textContent="● "+j.keys+" keys ready";llmStatus.className="llm-status ok";}
  else{llmStatus.textContent="● no API key";llmStatus.className="llm-status off";}
}catch{llmStatus.textContent="● offline";llmStatus.className="llm-status off";}})();
