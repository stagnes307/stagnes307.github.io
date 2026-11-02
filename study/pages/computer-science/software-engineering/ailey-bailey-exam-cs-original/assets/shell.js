(()=>{'use strict';
 const prefix='ailey-cs-integrated-v1:';
 const $=selector=>document.querySelector(selector);
 let parsed=[];try{parsed=JSON.parse($('#lesson-data').textContent)}catch{}
 const lessons=Array.isArray(parsed)?parsed:parsed.lessons||[];
 const nav=$('#nav'),menu=$('#menu'),shade=$('#shade'),frame=$('#lesson-frame');
 const overview=$('#overview'),stage=$('#lesson-stage');
 let current=lessons[0]?.id||'01',edition='integrated',lastFocus=null;
 const normalize=id=>String(id||'').padStart(2,'0');
 const find=id=>lessons.find(lesson=>normalize(lesson.id)===normalize(id));
 const mobile=()=>matchMedia('(max-width:850px)').matches;
 const read=key=>{try{return localStorage.getItem(prefix+key)}catch{return null}};
 const write=(key,value)=>{try{localStorage.setItem(prefix+key,value);return true}catch{return false}};
 function closeDrawer(restore=false){nav.classList.remove('open');shade.hidden=true;menu.setAttribute('aria-expanded','false');nav.removeAttribute('role');nav.removeAttribute('aria-modal');document.body.classList.remove('drawer');if(restore)lastFocus?.focus()}
 function openDrawer(){lastFocus=document.activeElement;nav.classList.add('open');shade.hidden=false;menu.setAttribute('aria-expanded','true');nav.setAttribute('role','dialog');nav.setAttribute('aria-modal','true');document.body.classList.add('drawer');$('#close').focus()}
 menu.addEventListener('click',openDrawer);$('#close').addEventListener('click',()=>closeDrawer(true));shade.addEventListener('click',()=>closeDrawer(true));
 window.addEventListener('resize',()=>{if(!mobile())closeDrawer()});
 document.addEventListener('keydown',event=>{
  if(!nav.classList.contains('open'))return;
  if(event.key==='Escape'){event.preventDefault();closeDrawer(true)}
  if(event.key==='Tab'){
   const focusable=[...nav.querySelectorAll('button,a,select,summary')].filter(node=>!node.disabled&&node.getClientRects().length);
   if(!focusable.length)return;
   if(event.shiftKey&&document.activeElement===focusable[0]){event.preventDefault();focusable.at(-1).focus()}
   else if(!event.shiftKey&&document.activeElement===focusable.at(-1)){event.preventDefault();focusable[0].focus()}
  }
 });
 function progress(){
  let count=0;
  for(const lesson of lessons){const id=normalize(lesson.id),done=read('read:'+id)==='true';if(done)count++;
   document.querySelectorAll('#lesson-nav [data-lesson="'+id+'"]').forEach(link=>{let mark=link.querySelector('.ab-read-mark');if(!mark){mark=document.createElement('span');mark.className='ab-read-mark';link.append(mark)}mark.textContent=done?'✓':'';mark.setAttribute('aria-label',done?'읽고 설명해 봄':'아직 읽음 표시 없음')});
  }
  $('#course-progress').textContent='자가 진도 '+count+' / '+lessons.length;
 }
 function pathFor(id,version){return (version==='original'?'lessons/':'revised/')+normalize(id)+'.html'}
 function updateURL(id,version,hash='',push=true){const url=new URL(location.href);url.searchParams.delete('view');url.searchParams.set('lesson',normalize(id));if(version==='original')url.searchParams.set('edition','original');else url.searchParams.delete('edition');url.hash=hash;history[push?'pushState':'replaceState'](null,'',url)}
 function render(id,{version='integrated',hash='',push=false,focus=false}={}){
  const lesson=find(id)||lessons[0];if(!lesson)return;current=normalize(lesson.id);edition=version==='original'?'original':'integrated';
  overview.hidden=true;stage.hidden=false;
  const path=pathFor(current,edition),src=path+hash;
  // Moving to another heading in an already loaded lesson has no load event.
  let sameDocument=false;
  try{const target=new URL(src,location.href),loaded=new URL(frame.contentWindow.location.href);sameDocument=target.origin===loaded.origin&&target.pathname===loaded.pathname&&target.search===loaded.search&&frame.contentDocument?.readyState==='complete'}catch{}
  if(sameDocument)$('#frame-status').textContent='';
  if(frame.getAttribute('src')!==src){if(!sameDocument)$('#frame-status').textContent='수업을 여는 중입니다.';frame.src=src}
  frame.title=current+' '+lesson.title;
  $('#lesson-title').textContent=current+' '+lesson.title;
  $('#course-path').textContent=[lesson.major,lesson.middle].filter(Boolean).join(' → ');
  $('#edition').value=edition;
  $('#edition-note').textContent=edition==='original'?'받은 원본을 그대로 제공합니다. 원본의 외부 Canvas 화면과 설정을 사용합니다.':'쉬운 연결 설명·직접 확인하는 연습을 원래 수업 안에 더했습니다.';
  $('#direct').href=src;
  $('#direct').textContent=edition==='original'?'원본만 열기':'수업만 열기';
  const index=lessons.indexOf(lesson);$('#previous-lesson').disabled=index===0;$('#next-lesson').disabled=index===lessons.length-1;$('#lesson-position').textContent=(index+1)+' / '+lessons.length;
  document.querySelectorAll('#lesson-nav [data-lesson]').forEach(link=>{if(normalize(link.dataset.lesson)===current){link.setAttribute('aria-current','page');for(let p=link.parentElement;p&&p!==nav;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true}else link.removeAttribute('aria-current')});
  document.title=lesson.title+' | Ailey & Bailey '+(edition==='original'?'원본':'통합판');write('last',current);if(push)updateURL(current,edition,hash,true);closeDrawer();
  if(focus)$('#reader').focus({preventScroll:true});
 }
 function showOverview(push=false){overview.hidden=false;stage.hidden=true;document.title='Ailey & Bailey · 18강을 읽는 길';document.querySelectorAll('#lesson-nav [aria-current]').forEach(link=>link.removeAttribute('aria-current'));closeDrawer();if(push){const url=new URL(location.href);url.searchParams.set('view','overview');url.hash='';history.pushState(null,'',url)}$('#reader').focus({preventScroll:true})}
 function restore(){const params=new URLSearchParams(location.search);if(params.get('view')==='overview'||(!params.has('lesson')&&!read('last'))){showOverview();return}render(params.get('lesson')||read('last'),{version:params.get('edition'),hash:location.hash})}
 document.addEventListener('click',event=>{
  const link=event.target.closest('a');if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  if(link.hasAttribute('data-overview')){event.preventDefault();showOverview(true);return}
  let id=link.dataset.lesson,hash='';
  if(!id){try{const url=new URL(link.href,location.href);if(url.origin===location.origin&&url.searchParams.has('lesson')){id=url.searchParams.get('lesson');hash=url.hash}}catch{}}
  if(!id||!find(id))return;event.preventDefault();render(id,{version:edition,hash,push:true,focus:true});
 });
 $('#show-overview').addEventListener('click',()=>showOverview(true));
 $('#edition').addEventListener('change',()=>render(current,{version:$('#edition').value,hash:location.hash,push:true,focus:true}));
 $('#previous-lesson').addEventListener('click',()=>{const index=lessons.findIndex(x=>normalize(x.id)===current);if(index>0)render(lessons[index-1].id,{version:edition,push:true,focus:true})});
 $('#next-lesson').addEventListener('click',()=>{const index=lessons.findIndex(x=>normalize(x.id)===current);if(index<lessons.length-1)render(lessons[index+1].id,{version:edition,push:true,focus:true})});
 function syncTheme(){try{if(edition==='integrated')frame.contentWindow.ABTheme?.setPreference(window.ABTheme?.getPreference()||'system',false)}catch{}}
 frame.addEventListener('load',()=>{
  $('#frame-status').textContent='';syncTheme();
  try{
   const win=frame.contentWindow,doc=frame.contentDocument;
   doc.querySelectorAll('a[data-lesson],a[data-overview]').forEach(link=>link.target='_top');
   const mirrorHash=()=>{const hash=win.location.hash;if(hash!==location.hash&&!stage.hidden){const url=new URL(location.href);url.hash=hash;history.replaceState(null,'',url);$('#direct').href=pathFor(current,edition)+hash}};
   win.addEventListener('hashchange',mirrorHash);
   if(location.hash&&edition==='integrated')win.ABLesson?.revealTarget(location.hash);
  }catch{}
 });
 window.addEventListener('ab:themechange',syncTheme);
 window.addEventListener('storage',event=>{if(event.key?.startsWith(prefix+'read:'))progress()});
 window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==frame.contentWindow)return;if(event.data?.type==='ailey-integrated-progress')progress();if(event.data?.type==='ailey-integrated-navigate'&&find(event.data.lesson))render(event.data.lesson,{version:'integrated',hash:event.data.hash||'',push:true,focus:true})});
 window.addEventListener('popstate',restore);
 window.addEventListener('hashchange',()=>{if(stage.hidden)return;try{if(edition==='integrated')frame.contentWindow.ABLesson?.revealTarget(location.hash)}catch{}});
 $('#backup-all').addEventListener('click',()=>{
  try{if(edition==='integrated'&&frame.contentWindow.ABLesson?.exportAnswers){frame.contentWindow.ABLesson.exportAnswers();return}}catch{}
  const answers={};try{for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key?.startsWith(prefix+'answer:')||key?.startsWith(prefix+'read:'))answers[key.slice(prefix.length)]=localStorage.getItem(key)}}catch{}
  const payload={format:'ailey-cs-integrated-study-backup',version:1,exported_at:new Date().toISOString(),scope:'브라우저의 통합판 답변과 자가 진도',answers};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='ailey-cs-study-backup.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 progress();restore();window.ABTheme?.sync();
})();
