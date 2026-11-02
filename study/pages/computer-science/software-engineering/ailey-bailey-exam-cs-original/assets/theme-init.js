/* Shared by the course shell and every integrated lesson. Run in <head>. */
(()=>{'use strict';
 const key='ailey-cs-integrated-v1:theme';
 const media=matchMedia('(prefers-color-scheme: dark)');
 const allowed=new Set(['system','light','dark']);
 let preference='system';
 try{const saved=localStorage.getItem(key);if(allowed.has(saved))preference=saved}catch{}
 const apply=()=>{
  const resolved=preference==='system'?(media.matches?'dark':'light'):preference;
  document.documentElement.dataset.theme=resolved;
  document.documentElement.dataset.themePreference=preference;
  document.documentElement.dataset.abUi='integrated';
  document.documentElement.style.colorScheme=resolved;
  document.querySelectorAll('[data-theme-choice]').forEach(select=>{select.value=preference});
  window.dispatchEvent(new CustomEvent('ab:themechange',{detail:{preference,resolved}}));
  return resolved;
 };
 window.ABTheme={
  getPreference:()=>preference,
  setPreference:(value,persist=true)=>{
   preference=allowed.has(value)?value:'system';
   if(persist)try{localStorage.setItem(key,preference)}catch{}
   return apply();
  },
  sync:()=>{try{const saved=localStorage.getItem(key);preference=allowed.has(saved)?saved:'system'}catch{}return apply()},
 };
 media.addEventListener('change',()=>{if(preference==='system')apply()});
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null)window.ABTheme.sync()});
 document.addEventListener('change',event=>{if(event.target.matches('[data-theme-choice]'))window.ABTheme.setPreference(event.target.value)});
 document.addEventListener('DOMContentLoaded',apply,{once:true});
 apply();
})();
