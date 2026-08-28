(() => {
  const buttons = [...document.querySelectorAll('[data-tab]')];
  const panels = {ff: document.getElementById('ff-panel'), cc: document.getElementById('cc-panel')};
  const frame = document.getElementById('cc-frame');
  const openCc = () => location.assign(frame.src);
  const activate = name => {
    if (!panels[name]) name = 'ff';
    buttons.forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === name)));
    Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== name; });
    if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  };
  const renderRaw = text => `<pre class="raw-fallback"></pre>`;
  fetch('./ff.md', {cache: 'no-store'})
    .then(response => { if (!response.ok) throw new Error(`FF ${response.status}`); return response.text(); })
    .then(text => {
      if (window.marked && window.DOMPurify) panels.ff.innerHTML = DOMPurify.sanitize(marked.parse(text));
      else { panels.ff.innerHTML = renderRaw(text); panels.ff.querySelector('pre').textContent = text; }
    })
    .catch(error => { panels.ff.innerHTML = `<p>FF 내용을 불러오지 못했습니다.</p><pre></pre>`; panels.ff.querySelector('pre').textContent = String(error); });
  function resizeFrame() {
    try {
      const doc = frame.contentDocument;
      if (doc) frame.style.height = `${Math.max(640, doc.documentElement.scrollHeight, doc.body?.scrollHeight || 0)}px`;
    } catch (_) { /* The direct link remains available if iframe inspection fails. */ }
  }
  frame.addEventListener('load', () => {
    resizeFrame();
    setTimeout(resizeFrame, 500);
    setTimeout(resizeFrame, 1500);
  });
  buttons.forEach(button => button.addEventListener('click', () => {
    const name = button.dataset.tab;
    if (name === 'cc') {
      openCc();
      return;
    }
    activate(name);
  }));
  addEventListener('hashchange', () => {
    const name = location.hash.slice(1);
    if (name === 'cc') {
      openCc();
      return;
    }
    activate(name);
  });
  addEventListener('resize', resizeFrame);
  const initialTab = location.hash.slice(1) || 'ff';
  if (initialTab === 'cc') openCc();
  else activate(initialTab);
})();
