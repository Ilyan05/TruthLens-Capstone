/* ============================================================
   TruthLens Chat — Phase 3
   - streams steps + typed answer
   - verdict card with confidence bar
   - EVIDENCE list with stance badges (supporting/contradicting/neutral)
============================================================ */
const messagesEl = document.getElementById("messages");
const inputEl     = document.getElementById("input");
const sendBtn     = document.getElementById("sendBtn");
const imageInput  = document.getElementById("imageInput");
const audioInput  = document.getElementById("audioInput");
const fileHint    = document.getElementById("fileHint");
const newChatBtn  = document.getElementById("newChatBtn");
const llmStatus   = document.getElementById("llmStatus");

const sessionId = "sess-" + Math.random().toString(36).slice(2, 10);
let pendingFile = null, busy = false;

function el(t, c, h){const e=document.createElement(t);if(c)e.className=c;if(h!==undefined)e.innerHTML=h;return e;}
function scrollDown(){messagesEl.scrollTop=messagesEl.scrollHeight;}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

function addUserMsg(text){
  const w=el("div","msg user");w.appendChild(el("div","avatar","🧑"));
  w.appendChild(el("div","bubble",escapeHtml(text)));messagesEl.appendChild(w);scrollDown();
}
function addBotShell(){
  const w=el("div","msg bot");w.appendChild(el("div","avatar","🔍"));
  const b=el("div","bubble"),s=el("div","steps"),a=el("div","answer");
  b.appendChild(s);b.appendChild(a);w.appendChild(b);messagesEl.appendChild(w);scrollDown();
  return {bubble:b,steps:s,answer:a};
}
function addStep(stepsEl,text){
  const p=stepsEl.querySelector(".step:not(.done)");if(p)p.classList.add("done");
  const s=el("div","step");s.appendChild(el("span","spin"));
  s.appendChild(el("span","",escapeHtml(text)));stepsEl.appendChild(s);scrollDown();
}
function finishSteps(stepsEl){stepsEl.querySelectorAll(".step:not(.done)").forEach(s=>s.classList.add("done"));}

function renderVerdict(bubble,v){
  const card=el("div","verdict-card");
  const conf=Math.round((v.confidence||0)*100);
  const head=el("div","verdict-head");
  head.appendChild(el("span","verdict-badge v-"+v.verdict,escapeHtml(v.verdict)));
  const cw=el("div","conf-wrap");
  cw.appendChild(el("div","conf-label",`<span>Confidence</span><span>${conf}%</span>`));
  const bar=el("div","conf-bar"),fill=el("div","conf-fill");bar.appendChild(fill);cw.appendChild(bar);
  head.appendChild(cw);card.appendChild(head);

  if(v.needs_human_review)
    card.appendChild(el("div","review-flag","⚠️ High-impact topic — flagged for human review."));

  if(v.evidence&&v.evidence.length){
    const block=el("div","evidence-block");
    block.appendChild(el("div","evidence-title","Evidence"));
    v.evidence.forEach(e=>{
      const item=el("div","evidence-item");
      const stance=(e.stance||"neutral");
      item.appendChild(el("span","stance-tag st-"+stance,stance));
      const body=el("div","ev-body");
      const src=el("div","ev-source");
      src.innerHTML=(e.url?`<a href="${e.url}" target="_blank" rel="noopener">${escapeHtml(e.title||e.url)}</a>`
                          :escapeHtml(e.title||"Source"))
                    +`<span class="ev-type">${escapeHtml(e.source_type||"web")}</span>`;
      body.appendChild(src);
      if(e.snippet)body.appendChild(el("div","ev-snippet",escapeHtml(e.snippet)));
      item.appendChild(body);block.appendChild(item);
    });
    card.appendChild(block);
  }
  bubble.appendChild(card);
  requestAnimationFrame(()=>{fill.style.width=conf+"%";});
  scrollDown();
}

async function send(){
  if(busy)return;
  const text=inputEl.value.trim();
  if(!text&&!pendingFile)return;
  let inputType=pendingFile?pendingFile.type:"text";
  addUserMsg(text||`(${inputType} file: ${pendingFile.file.name})`);
  inputEl.value="";inputEl.style.height="auto";busy=true;sendBtn.disabled=true;
  const {bubble,steps,answer}=addBotShell();

  const fd=new FormData();
  fd.append("session_id",sessionId);fd.append("message",text);fd.append("input_type",inputType);
  if(pendingFile)fd.append("file",pendingFile.file);
  pendingFile=null;fileHint.textContent="";

  try{
    const resp=await fetch("/api/v1/chat",{method:"POST",body:fd});
    const reader=resp.body.getReader();const dec=new TextDecoder();
    let buffer="",cursor=null;
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buffer+=dec.decode(value,{stream:true});
      const parts=buffer.split("\n\n");buffer=parts.pop();
      for(const part of parts){
        const line=part.trim();if(!line.startsWith("data:"))continue;
        let p;try{p=JSON.parse(line.slice(5).trim());}catch{continue;}
        switch(p.event){
          case "step":addStep(steps,p.text);break;
          case "answer_start":finishSteps(steps);cursor=el("span","cursor");answer.appendChild(cursor);break;
          case "answer_chunk":{const n=document.createTextNode(p.text);
            if(cursor)answer.insertBefore(n,cursor);else answer.appendChild(n);scrollDown();break;}
          case "verdict":renderVerdict(bubble,p);break;
          case "done":if(cursor)cursor.remove();break;
        }
      }
    }
  }catch(err){
    answer.appendChild(el("div","","⚠️ Connection error: "+escapeHtml(String(err))));
  }finally{busy=false;sendBtn.disabled=false;inputEl.focus();}
}

sendBtn.addEventListener("click",send);
inputEl.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
inputEl.addEventListener("input",()=>{inputEl.style.height="auto";inputEl.style.height=Math.min(inputEl.scrollHeight,170)+"px";});
imageInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"image"};
  fileHint.textContent="🖼️ Image ready: "+pendingFile.file.name+" — press send to verify.";}});
audioInput.addEventListener("change",e=>{if(e.target.files[0]){pendingFile={file:e.target.files[0],type:"audio"};
  fileHint.textContent="🎙️ Audio ready: "+pendingFile.file.name+" — press send to verify.";}});
document.querySelectorAll(".chip").forEach(c=>c.addEventListener("click",()=>{inputEl.value=c.dataset.ex;inputEl.focus();}));
newChatBtn.addEventListener("click",async()=>{
  try{await fetch("/api/v1/reset",{method:"POST",body:new URLSearchParams({session_id:sessionId})});}catch{}
  location.reload();
});

(async()=>{
  try{const r=await fetch("/health");const j=await r.json();
    if(j.llm_configured){llmStatus.textContent="● LLM ready";llmStatus.className="llm-status ok";}
    else{llmStatus.textContent="● no API key";llmStatus.className="llm-status off";}
  }catch{llmStatus.textContent="● offline";llmStatus.className="llm-status off";}
})();
