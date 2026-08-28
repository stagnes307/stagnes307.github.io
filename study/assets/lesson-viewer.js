(() => {
  const buttons = [...document.querySelectorAll('[data-tab]')];
  const panels = {ff: document.getElementById('ff-panel'), cc: document.getElementById('cc-panel')};
  const frame = document.getElementById('cc-frame');
  const markdownHeading = /^ {0,3}#{1,6}(?:[ \t]+|$)/;
  const emojiHeading = /^(?:\p{Extended_Pictographic}|[\u2600-\u27bf])/u;
  const languageLabels = new Map([
    ['python', 'python'], ['파이썬', 'python'], ['r', 'r'], ['sql', 'sql'], ['json', 'json'],
    ['javascript', 'javascript'], ['js', 'javascript'], ['html', 'html'], ['xml', 'xml'],
    ['bash', 'bash'], ['shell', 'shell'],
  ]);

  const openCc = () => location.assign(frame.src);
  const activate = name => {
    if (!panels[name]) name = 'ff';
    buttons.forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === name)));
    Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== name; });
    if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  };

  const firstContentIndex = lines => lines.findIndex(line => line.trim());
  const isLegacyAiley = (text, metadata) => {
    const lines = text.replace(/\r\n?/g, '\n').split('\n');
    const firstIndex = firstContentIndex(lines);
    if (firstIndex < 0 || markdownHeading.test(lines[firstIndex])) return false;
    const hasTabularRows = lines.some(line => line.includes('\t'));
    const producer = metadata?.artifacts?.ff?.producer;
    if (producer === 'ailey-bailey-custom-gpt') return hasTabularRows;
    const pseudoHeadings = lines.filter(line => {
      const value = line.trim();
      return value.length <= 120 && emojiHeading.test(value);
    });
    return hasTabularRows && pseudoHeadings.length >= 3;
  };

  const appendBlank = output => {
    if (output.length && output[output.length - 1] !== '') output.push('');
  };
  const escapeLegacyMarkup = value => value.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escapeTableCell = value => value.trim()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\|/g, '\\|');
  const codeFence = lines => {
    const longest = Math.max(0, ...((lines.join('\n').match(/`+/g) || []).map(run => run.length)));
    return '`'.repeat(Math.max(3, longest + 1));
  };
  const looksLikeCode = line => /^(?:\s*(?:#|import\s|from\s|def\s|class\s|for\s|while\s|if\s|elif\s|else\s*:|try\s*:|except\b|return\b|print\s*\(|library\s*\(|SELECT\b|INSERT\b|UPDATE\b|CREATE\b|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*(?:=|<-|\())|\s*[\[\]{}()]\s*$)/i.test(line);
  const looksLikeMarkup = line => /^\s*(?:<!doctype\b|<!--|<\?xml\b|<\/?[A-Za-z][^>]*>)/i.test(line);
  const isPseudoSection = (line, previous, following) => {
    const value = line.trim();
    if (!value || value.length > 120) return false;
    if (emojiHeading.test(value)) return true;
    const isolated = !previous.trim() && !following.trim();
    return isolated && /^(?:\d{1,2}[.)]|[①-⑳])\s+\S/.test(value);
  };

  const formatLegacyMarkdown = text => {
    const lines = text.replace(/\r\n?/g, '\n').split('\n');
    const titleIndex = firstContentIndex(lines);
    const output = [];

    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      const value = line.trim();
      if (!value) {
        appendBlank(output);
        continue;
      }

      if (index === titleIndex) {
        appendBlank(output);
        output.push(`# ${escapeLegacyMarkup(value)}`);
        appendBlank(output);
        continue;
      }

      const language = languageLabels.get(value.toLowerCase());
      if (language) {
        const markupLanguage = language === 'html' || language === 'xml';
        const hasRunMarker = (lines[index + 1] || '').trim() === '실행됨';
        const bodyStart = index + (hasRunMarker ? 2 : 1);
        let bodyEnd = bodyStart;
        while (bodyEnd < lines.length && lines[bodyEnd].trim()) bodyEnd += 1;
        const body = lines.slice(bodyStart, bodyEnd);
        const markupCode = markupLanguage && body.some(looksLikeMarkup);
        if (body.length && (markupCode || hasRunMarker || body.some(looksLikeCode))) {
          const fence = codeFence(body);
          appendBlank(output);
          output.push(`${fence}${language}`, ...body, fence);
          appendBlank(output);
          index = bodyEnd - 1;
          continue;
        }
      }

      if (line.includes('\t')) {
        let end = index;
        while (end < lines.length && lines[end].includes('\t') && lines[end].trim()) end += 1;
        const rows = lines.slice(index, end).map(row => row.split('\t'));
        const width = rows[0].length;
        if (rows.length >= 2 && width >= 2 && rows.every(row => row.length === width)) {
          appendBlank(output);
          output.push(`| ${rows[0].map(escapeTableCell).join(' | ')} |`);
          output.push(`| ${rows[0].map(() => '---').join(' | ')} |`);
          rows.slice(1).forEach(row => output.push(`| ${row.map(escapeTableCell).join(' | ')} |`));
          appendBlank(output);
          index = end - 1;
          continue;
        }
      }

      const previous = lines[index - 1] || '';
      const following = lines[index + 1] || '';
      if (isPseudoSection(line, previous, following)) {
        appendBlank(output);
        output.push(`## ${escapeLegacyMarkup(value)}`);
        appendBlank(output);
        continue;
      }
      output.push(escapeLegacyMarkup(line));
    }
    return output.join('\n');
  };

  const textWithBreaks = node => {
    if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || '';
    if (node.nodeName === 'BR') return '\n';
    return [...node.childNodes].map(textWithBreaks).join('');
  };
  const decorateLegacyContent = panel => {
    panel.classList.add('ff-legacy');
    const paragraphs = [...panel.querySelectorAll(':scope > p')];
    paragraphs.forEach(paragraph => {
      const value = textWithBreaks(paragraph).trim();
      if (/^(?:#[^\s#]+)(?:\s+#[^\s#]+)+$/.test(value)) {
        paragraph.classList.add('ff-tags');
        return;
      }
      const lines = value.split('\n').filter(Boolean);
      const diagramLines = lines.filter(line => /\t|\s{2,}|[│└├┬┼╭╰↓↑→←]/.test(line));
      if (lines.length >= 3 && diagramLines.length >= 2) {
        paragraph.classList.add('ff-plain-grid');
        return;
      }
      const isKeyLine = value.length >= 3
        && value.length <= 42
        && !value.includes('\n')
        && !/[.!?。！？,:：;；]$/.test(value)
        && !/^(?:그리고|그러면|또는|예를 들어|즉|결과가|이라면)$/.test(value);
      if (isKeyLine) paragraph.classList.add('ff-key-line');
    });
    const title = panel.querySelector(':scope > h1');
    let lead = title?.nextElementSibling || null;
    while (lead && (!lead.matches('p') || lead.classList.contains('ff-tags'))) lead = lead.nextElementSibling;
    lead?.classList.add('ff-lead');
  };

  const renderRaw = (panel, text) => {
    const fallback = document.createElement('pre');
    fallback.className = 'raw-fallback';
    fallback.textContent = text;
    panel.replaceChildren(fallback);
  };
  const fetchText = fetch('./ff.md', {cache: 'no-store'})
    .then(response => { if (!response.ok) throw new Error(`FF ${response.status}`); return response.text(); });
  const fetchMetadata = fetch('./meta.json', {cache: 'no-store'})
    .then(response => response.ok ? response.json() : null)
    .catch(() => null);

  Promise.all([fetchText, fetchMetadata])
    .then(([text, metadata]) => {
      const legacy = isLegacyAiley(text, metadata);
      const markdown = legacy ? formatLegacyMarkdown(text) : text;
      if (window.marked && window.DOMPurify) {
        panels.ff.innerHTML = DOMPurify.sanitize(marked.parse(markdown, {gfm: true, breaks: legacy}));
        if (legacy) decorateLegacyContent(panels.ff);
      } else {
        renderRaw(panels.ff, text);
      }
    })
    .catch(error => {
      panels.ff.innerHTML = '<p>FF 내용을 불러오지 못했습니다.</p><pre></pre>';
      panels.ff.querySelector('pre').textContent = String(error);
    });
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
