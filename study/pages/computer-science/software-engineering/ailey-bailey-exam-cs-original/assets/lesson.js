(()=>{'use strict';
 const prefix='ailey-cs-integrated-v1:';
 const boundAreas=new WeakSet(),colored=new WeakSet();
 const safeRead=key=>{try{return localStorage.getItem(prefix+key)}catch{return null}};
 const safeWrite=(key,value)=>{try{localStorage.setItem(prefix+key,value);return true}catch{return false}};
 let config={id:'01',title:document.title},root=null,storageAvailable=true;
 function status(message){let node=document.getElementById('ab-page-status');if(!node){node=document.createElement('p');node.id='ab-page-status';node.className='ab-page-status';node.setAttribute('role','status');root?.prepend(node)}if(node)node.textContent=message}
 function readConfig(){try{const source=document.getElementById('ab-lesson-config');if(source)config={...config,...JSON.parse(source.textContent)}}catch{}config.id=String(config.id).padStart(2,'0')}
 function rgb(value){
  if(!value||/^(none|transparent|currentcolor)$/i.test(value)||value.startsWith('url('))return null;
  let parts=value.match(/^rgba?\(([^)]+)\)/i);
  if(parts){const n=parts[1].split(/[,\s/]+/).filter(Boolean).map(Number);if(n.length>3&&n[3]===0)return null;return n.slice(0,3)}
  if(/^#[\da-f]{3,8}$/i.test(value)){let h=value.slice(1);if(h.length===3||h.length===4)h=h.split('').map(x=>x+x).join('');if(h.length===8&&parseInt(h.slice(6),16)===0)return null;return [0,2,4].map(i=>parseInt(h.slice(i,i+2),16))}
  return null;
 }
 function family(color){
  const [r,g,b]=color.map(x=>x/255),max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min,l=(max+min)/2;
  if(delta<.07)return {name:'neutral',light:l,saturation:0};
  const saturation=delta/(1-Math.abs(2*l-1));
  let hue=max===r?((g-b)/delta)%6:max===g?(b-r)/delta+2:(r-g)/delta+4;hue=(hue*60+360)%360;
  const name=hue<20||hue>=345?'red':hue<70?'amber':hue<170?'green':hue<265?'blue':'purple';
  return {name,light:l,saturation};
 }
 function svgToken(value,node,property){
  const color=rgb(value);if(!color)return null;const f=family(color),text=/^(text|tspan)$/i.test(node.tagName);
  if(text){if(f.light>.85&&f.saturation<.2)return '#f5fbff';return f.name==='neutral'?'var(--ailey-cs-svg-ink)':`var(--ailey-cs-svg-text-${f.name})`}
  if(property==='stroke')return f.name==='neutral'?'var(--ailey-cs-svg-line)':`var(--ailey-cs-svg-text-${f.name})`;
  if(f.name==='neutral')return f.light<.45&&/^(path|polygon|polyline|circle)$/i.test(node.tagName)?'var(--ailey-cs-svg-line)':'var(--ailey-cs-svg-panel)';
  return f.light>.66?`var(--ailey-cs-svg-${f.name})`:`var(--ailey-cs-svg-strong-${f.name})`;
 }
 function adaptColors(scope){
  scope.querySelectorAll('svg :is(rect,path,circle,ellipse,line,polyline,polygon,text,tspan,stop)').forEach(node=>{
   if(colored.has(node))return;colored.add(node);const computed=getComputedStyle(node);
   for(const property of ['fill','stroke','stop-color']){
    const attr=node.getAttribute(property),value=attr===null?computed.getPropertyValue(property):attr;
    // Transparent space and paint servers retain their original meaning.
    if(!value||/^(none|transparent)$/i.test(value)||value.includes('url('))continue;
    const token=svgToken(value,node,property);if(!token)continue;
    const suffix=property==='stop-color'?'stop':property;
    node.dataset['abSvg'+suffix[0].toUpperCase()+suffix.slice(1)]=value;
    node.style.setProperty('--ailey-cs-svg-'+suffix,token);
   }
  });
  scope.querySelectorAll('article,section,aside,blockquote,figure,div,header,footer,span,p,li,dl,dt,dd,output,fieldset,form,details,caption,table,th,td,a').forEach(node=>{
   if(colored.has(node)||node.closest('svg,pre,code,.ab-lesson-toolbar'))return;colored.add(node);
   const computed=getComputedStyle(node),gradient=computed.backgroundImage!=='none',gradientColor=computed.backgroundImage.match(/rgba?\([^)]+\)/)?.[0],background=rgb(computed.backgroundColor)||(gradientColor?rgb(gradientColor):null);
   if(gradient)node.dataset.abGradient='adapted';
   if(background){const f=family(background);node.dataset.abSurface=f.name;node.style.setProperty('--ailey-cs-surface-color',f.name==='neutral'?'var(--ailey-cs-panel)':`var(--ailey-cs-${f.name==='purple'?'blue':f.name})`)}
   const color=rgb(computed.color);if(color&&family(color).light<.6)node.dataset.abTextColor='adapted';
  });
 }
 function accessibleRegions(scope){scope.querySelectorAll('.math-scroll,.table-scroll,.table-wrap,.ab-table-scroll,.code-scroll,[data-table-scroll]').forEach(region=>{region.tabIndex=0;if(!region.hasAttribute('role'))region.setAttribute('role','region');if(!region.hasAttribute('aria-label'))region.setAttribute('aria-label',region.classList.contains('math-scroll')?'수식 가로 스크롤':'표와 코드 가로 스크롤')})}
 function luminance(color){return color.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,value,i)=>sum+value*[.2126,.7152,.0722][i],0)}
 function contrast(a,b){const l=luminance(a),r=luminance(b);return (Math.max(l,r)+.05)/(Math.min(l,r)+.05)}
 function rgba(value){const match=String(value||'').match(/^rgba?\(([^)]+)\)/);if(match){const parts=match[1].split(/[,\s/]+/).filter(Boolean).map(Number);return [...parts.slice(0,3),parts.length>3?parts[3]:1]}const color=rgb(value);return color?[...color,1]:null}
 function composite(front,back){return front.slice(0,3).map((value,index)=>value*front[3]+back[index]*(1-front[3]))}
 function backgroundFor(node){
  const layers=[];
  for(let p=node;p;p=p.parentElement){const style=getComputedStyle(p),gradient=style.backgroundImage.match(/rgba?\([^)]+\)/)?.[0];if(gradient){const color=rgba(gradient);if(color)layers.push(color)}const background=rgba(style.backgroundColor);if(background)layers.push(background)}
  let result=document.documentElement.dataset.theme==='dark'?[20,32,37]:[248,250,248];for(let i=layers.length-1;i>=0;i--)result=composite(layers[i],result);return result;
 }
 function repairLightContrast(scope){
  if(document.documentElement.dataset.theme!=='light')return;
  scope.querySelectorAll('[data-ab-light-ink]').forEach(node=>node.removeAttribute('data-ab-light-ink'));
  scope.querySelectorAll('p,figcaption,caption,small,.note,.ab-visual-caption,.integration-caption,td,th,label,li,dt,dd,summary,h1,h2,h3,h4,strong,b,em,i,span,a,button,select,input').forEach(node=>{
   if(node.closest('svg,pre,code')||!node.getClientRects().length)return;
   const style=getComputedStyle(node),foregroundValue=rgba(style.color);if(!foregroundValue)return;
   const background=backgroundFor(node),foreground=composite(foregroundValue,background),large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&Number(style.fontWeight)>=700),minimum=large?3:4.5;
   if(contrast(foreground,background)>=minimum)return;
   const ink=contrast([36,59,63],background),paper=contrast([245,251,255],background);
   if(Math.max(ink,paper)>=minimum)node.dataset.abLightInk=ink>=paper?'dark':'light';
   else node.dataset.abLightInk=contrast([0,0,0],background)>=contrast([255,255,255],background)?'black':'white';
  });
 }
 function readableFigures(scope){
  scope.querySelectorAll('svg').forEach(svg=>{
   if(svg.getAttribute('aria-hidden')==='true'||(!svg.querySelector('text')&&svg.getAttribute('role')!=='img'))return;
   if(svg.parentElement?.classList.contains('ab-svg-scroll'))return;
   const width=svg.viewBox?.baseVal?.width||Number(svg.getAttribute('width'))||640;
   const sizes=[...svg.querySelectorAll('text,tspan')].map(text=>parseFloat(getComputedStyle(text).fontSize)).filter(value=>Number.isFinite(value)&&value>0);
   const minimumFont=sizes.length?Math.min(...sizes):16;
   const existing=parseFloat(getComputedStyle(svg).minWidth)||0;
   const minimumWidth=Math.ceil(Math.max(existing,width*14/minimumFont));
   const region=document.createElement('div');region.className='ab-svg-scroll';region.tabIndex=0;region.setAttribute('role','region');region.setAttribute('aria-label','그림 가로 스크롤');
   svg.before(region);region.append(svg);svg.style.setProperty('min-width',minimumWidth+'px','important');svg.style.setProperty('max-width','none','important');
   const hint=document.createElement('p');hint.className='ab-svg-hint';hint.textContent='그림 안을 좌우로 밀어 전체 흐름을 보세요. 키보드로는 그림 영역에서 방향키를 누릅니다.';hint.style.setProperty('color','var(--ailey-cs-muted)','important');hint.style.setProperty('-webkit-text-fill-color','currentColor','important');hint.style.setProperty('background-color','var(--ailey-cs-paper)','important');hint.hidden=minimumWidth<=region.clientWidth+1;region.after(hint);
   if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>{hint.hidden=svg.getBoundingClientRect().width<=region.clientWidth+1}).observe(region);
  });
 }
 function revealTarget(hash,scroll=true){
  const id=decodeURIComponent((hash||'').replace(/^#/,''));if(!id)return;
  const node=document.getElementById(id);if(!node)return;
  for(let parent=node.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
  if(scroll)requestAnimationFrame(()=>node.scrollIntoView({block:'start'}));
 }
 function answerStatus(area,message){let note=area.nextElementSibling;if(!note?.classList.contains('ab-answer-status')){note=document.createElement('p');note.className='ab-answer-status';note.setAttribute('role','status');area.after(note)}note.textContent=message}
 function initializeAnswers(scope){
  scope.querySelectorAll('textarea').forEach((area,index)=>{
   if(boundAreas.has(area))return;boundAreas.add(area);
   const stable=area.dataset.answer||area.id||'answer-'+(index+1);area.dataset.answer=stable;
   if(!area.id)area.id='ab-answer-'+config.id+'-'+(index+1);
   if(!area.getAttribute('aria-label')&&!document.querySelector('label[for="'+CSS.escape(area.id)+'"]'))area.setAttribute('aria-label',config.id+'강 답변 '+(index+1));
   const key='answer:'+config.id+':'+stable,saved=safeRead(key);if(saved!==null)area.value=saved;
   answerStatus(area,'먼저 내 답을 적고 해설을 확인하세요. 초안은 이 브라우저에 보관됩니다.');
   area.addEventListener('input',()=>{storageAvailable=safeWrite(key,area.value);answerStatus(area,storageAvailable?'답변 초안을 보관했습니다.':'브라우저에 보관하지 못했습니다. 답변을 복사하거나 파일로 내보내세요.')});
  });
 }
 function controls(){
  document.documentElement.dataset.abEmbedded=window.parent!==window?'true':'false';
  if(!document.getElementById('ab-lesson-toolbar')){
   const bar=document.createElement('nav');bar.id='ab-lesson-toolbar';bar.className='ab-lesson-toolbar';bar.setAttribute('aria-label','읽기 설정');
   bar.innerHTML='<a class="ab-back" href="../index.html?lesson='+config.id+'" target="_top">강좌 목차 · '+config.id+'강</a><label for="lesson-theme">화면 <select id="lesson-theme" data-theme-choice><option value="system">시스템 설정</option><option value="light">밝게</option><option value="dark">어둡게</option></select></label><div class="ab-text-controls"><button type="button" data-text-size="-1" aria-label="본문 글자 작게">글자 −</button><button type="button" data-text-size="1" aria-label="본문 글자 크게">글자 +</button></div>';
   root.before(bar);
  }
  if(!document.getElementById('ab-study-footer')){
   const footer=document.createElement('aside');footer.id='ab-study-footer';footer.className='ab-study-footer';
   footer.innerHTML='<label><input type="checkbox" data-lesson-read> 이 강을 읽고 내 말로 설명해 보았습니다.</label><p class="ab-storage-note">학습용 자가 진도입니다. 답변과 진도는 이 브라우저에만 보관되며 다른 기기와 동기화되지 않습니다.</p><div class="ab-footer-actions"><button type="button" data-answer-backup>답변·진도 파일로 내보내기</button></div><p data-read-status role="status"></p>';
   if(config.previous){const id=String(config.previous).padStart(2,'0');footer.querySelector('.ab-footer-actions').insertAdjacentHTML('beforeend','<a href="../index.html?lesson='+id+'" data-lesson="'+id+'" target="_top">← 이전 강</a>')}
   if(config.next){const id=String(config.next).padStart(2,'0');footer.querySelector('.ab-footer-actions').insertAdjacentHTML('beforeend','<a href="../index.html?lesson='+id+'" data-lesson="'+id+'" target="_top">다음 강 →</a>')}
   root.after(footer);
  }
  document.querySelectorAll('[data-lesson-read]').forEach(box=>box.checked=safeRead('read:'+config.id)==='true');
  const scale=Number(safeRead('font-scale'));if(scale>=.9&&scale<=1.3)document.documentElement.style.setProperty('--ailey-cs-font-scale',scale);
  window.ABTheme?.sync();
 }
 async function copyArea(id){
  const area=document.getElementById(id);if(!area)return false;const text='value'in area?area.value:area.textContent;
  if(!text.trim()){status('먼저 답변을 적어 주세요.');area.focus?.();return false}
  try{if(!navigator.clipboard?.writeText)throw Error('unavailable');await navigator.clipboard.writeText(text);status('답변을 복사했습니다. 자동 채점이나 외부 전송은 하지 않았습니다.');return true}catch{area.focus?.();area.select?.();status('답변을 선택했습니다. 복사 단축키로 직접 복사해 주세요.');return false}
 }
 function saveArea(id){const area=document.getElementById(id);if(!area)return;const key='answer:'+config.id+':'+(area.dataset.answer||area.id);const ok=safeWrite(key,area.value);answerStatus(area,ok?'답변을 보관했습니다. 자동 채점은 하지 않았습니다.':'브라우저 보관이 제한되어 있습니다. 답변을 복사하거나 파일로 내보내세요.')}
 function exportAnswers(){
  const answers={};try{for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key?.startsWith(prefix+'answer:')||key?.startsWith(prefix+'read:'))answers[key.slice(prefix.length)]=localStorage.getItem(key)}}catch{}
  document.querySelectorAll('textarea[data-answer]').forEach(area=>answers['answer:'+config.id+':'+area.dataset.answer]=area.value);
  const data={format:'ailey-cs-integrated-study-backup',version:1,exported_at:new Date().toISOString(),scope:'브라우저의 통합판 답변과 학습용 자가 진도',answers};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='ailey-cs-study-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 function updateDatasetDemo(){const output=document.getElementById('dataset-demo-result');if(!output)return;const chosen=document.querySelector('input[name="dataset-demo"]:checked');output.hidden=false;output.textContent='브라우저 요청이 만들어졌어. 선택값: '+(chosen?.value||'dataset-B')+'. 이 화면은 실제 서버와 연결되지 않은 학습용 시뮬레이션이야. DB는 변경되지 않아.'}
 function updateIdorDemo(){const target=document.getElementById('idor-target'),mode=document.getElementById('idor-mode'),output=document.getElementById('idor-output');if(!target||!mode||!output)return;const deny=target.value!=='E00001'&&mode.value==='secure',leak=target.value!=='E00001'&&mode.value==='unsafe';output.textContent='GET /api/employees/'+target.value+'/route — '+(deny?'403 Forbidden · 로그인한 사용자와 조회 대상이 달라 거절했습니다.':leak?'200 OK · 로그인만 확인해 다른 구성원의 자료가 노출되었습니다.':'200 OK · 로그인한 사용자 자신의 배정입니다.')+' 이 결과는 학습용 시뮬레이션이며 실제 서버 응답이 아닙니다.'}
 document.addEventListener('click',event=>{
  const control=event.target.closest('button,a');if(!control)return;
  const hash=control.getAttribute('href');if(hash?.startsWith('#')){revealTarget(hash);return}
  if(control.tagName==='A'){
   let destination=control.dataset.lesson,targetHash='';try{const url=new URL(control.href,location.href);if(url.origin===location.origin){destination=destination||url.searchParams.get('lesson');targetHash=url.hash}}catch{}
   if(destination&&window.parent!==window&&location.origin!=='null'){event.preventDefault();window.parent.postMessage({type:'ailey-integrated-navigate',lesson:String(destination).padStart(2,'0'),hash:targetHash},location.origin);return}
  }
  if(control.matches('[data-answer-backup]')){exportAnswers();return}
  if(control.matches('[data-text-size]')){const current=Number(getComputedStyle(document.documentElement).getPropertyValue('--ailey-cs-font-scale'))||1,next=Math.max(.9,Math.min(1.3,Math.round((current+Number(control.dataset.textSize)*.05)*100)/100));document.documentElement.style.setProperty('--ailey-cs-font-scale',next);safeWrite('font-scale',String(next));return}
  const copy=control.dataset.copyTarget||control.dataset.answer||(control.id==='ab-submit'?'ab-answers':control.id==='copy-reflection'?'reflection-answer':null);
  if(copy&&(control.matches('[data-copy-target],.copy-answer')||['ab-submit','copy-reflection'].includes(control.id))){event.preventDefault();copyArea(copy);return}
  if(control.dataset.clearTarget||control.id==='clear-reflection'){const area=document.getElementById(control.dataset.clearTarget||'reflection-answer');if(area){area.value='';area.dispatchEvent(new Event('input',{bubbles:true}));area.focus()}return}
  if(control.dataset.selectTarget){const area=document.getElementById(control.dataset.selectTarget);area?.focus();area?.select();return}
  if(control.dataset.saveTarget){saveArea(control.dataset.saveTarget);return}
  if(control.id==='dataset-demo-button')updateDatasetDemo();
 });
 document.addEventListener('change',event=>{
  const target=event.target;if(target.matches('[data-lesson-read]')){const ok=safeWrite('read:'+config.id,String(target.checked));document.querySelectorAll('[data-read-status]').forEach(node=>node.textContent=ok?'자가 진도를 보관했습니다.':'진도를 보관할 수 없습니다. 필요한 내용을 별도로 기록해 주세요.');if(window.parent!==window&&location.origin!=='null')window.parent.postMessage({type:'ailey-integrated-progress',lesson:config.id,read:target.checked},location.origin)}
  if(['idor-target','idor-mode'].includes(target.id))updateIdorDemo();
 });
 window.addEventListener('hashchange',()=>revealTarget(location.hash));
 window.addEventListener('ab:themechange',()=>{if(root)repairLightContrast(root)});
 document.addEventListener('toggle',event=>{if(event.target.tagName==='DETAILS'&&event.target.open)repairLightContrast(event.target)},true);
 window.addEventListener('storage',event=>{if(event.key===prefix+'read:'+config.id)document.querySelectorAll('[data-lesson-read]').forEach(box=>box.checked=event.newValue==='true')});
 let printClosed=[];window.addEventListener('beforeprint',()=>{printClosed=[...document.querySelectorAll('details:not([open])')];printClosed.forEach(d=>d.open=true)});window.addEventListener('afterprint',()=>{printClosed.forEach(d=>d.open=false);printClosed=[]});
 function init(){readConfig();root=document.getElementById('ai-content-placeholder');if(!root)return;initializeAnswers(root);adaptColors(root);accessibleRegions(root);readableFigures(root);controls();revealTarget(location.hash);repairLightContrast(root);document.getElementById('initial-loader')?.setAttribute('hidden','');}
 window.ABLesson={init,revealTarget,exportAnswers};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
 // An optional external renderer may remount the payload. Initialization stays repeatable.
 let scheduled=false;const observer=new MutationObserver(records=>{if(!records.some(record=>[...record.addedNodes].some(node=>node.nodeType===1&&(node.id==='ai-content-placeholder'||node.querySelector?.('#ai-content-placeholder')))))return;if(!scheduled){scheduled=true;queueMicrotask(()=>{scheduled=false;init()})}});
 if(document.body)observer.observe(document.body,{childList:true,subtree:true});else document.addEventListener('DOMContentLoaded',()=>observer.observe(document.body,{childList:true,subtree:true}),{once:true});
})();
