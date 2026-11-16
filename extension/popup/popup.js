/* ============================================
   BIS Sahayak — Chrome Extension Popup Logic (v2.1.0)
   
   Features:
   1. On-Demand Current Page Analysis (Privacy-first)
   2. Intelligent Multi-Host Backend Health Check (127.0.0.1 & localhost fallback)
   3. Informative Error Diagnostics (Backend offline, extraction, network, AI)
   4. Structured Page Context Retention for Follow-up Questions
   5. Prototype Image Attachment UI (+ button, file picker, thumbnail preview, remove)
   6. Trilingual Support (EN / HI / GU) across all states
   ============================================ */

// -------------------------------------------
// Configuration & Backend Discovery
// -------------------------------------------

const BACKEND_CANDIDATES = ['http://127.0.0.1:8000', 'http://localhost:8000'];
let activeBackendUrl = 'http://127.0.0.1:8000';

// -------------------------------------------
// State
// -------------------------------------------

let currentLang = 'en';
let currentConversationId = '';
let currentPageContext = null;
let lastExtractedPageData = null;
let attachedImageData = null;
let isAnalyzing = false;

// -------------------------------------------
// Multilingual Content
// -------------------------------------------

const LANG_STRINGS = {
  en: {
    welcome_title: 'Namaste! 🙏',
    welcome_body: "I'm BIS Sahayak — your browser copilot for Indian Standards, certification, hallmarking, and testing.",
    welcome_ask: 'Click "Read & Analyze This Page" above to check compliance, or ask a question below.',
    btn_analyze: 'Read & Analyze This Page',
    btn_retry: 'Retry Analysis',
    btn_selection: 'Analyze Selection',
    privacy_text: 'Analyzed only on click · Zero background tracking',
    active_tab: 'Active Tab',
    progress_title: 'Analyzing Page for BIS Compliance…',
    step1: 'Reading webpage content & specifications…',
    step2: 'Detecting product & certification claims…',
    step3: 'Sending to BIS Sahayak backend…',
    step4: 'Searching official Indian Standards (BIS RAG)…',
    step5: 'Generating BIS compliance report…',
    placeholder: 'Ask about standards, certification…',
    attach_image: 'Attach product image (Prototype)',
    remove_image: 'Remove image',
    image_attached_badge: 'Image Attached (Prototype)',
    connected: 'Connected',
    offline: 'Backend offline',
    connecting: 'Connecting…',
    copy: 'Copy',
    copied: 'Copied! ✓',
    followups: 'Suggested Follow-ups',
    cleared: 'New conversation started.',
    restricted_tab: 'Internal browser pages cannot be analyzed. Please open a product website.',
    err_backend_offline: 'BIS Sahayak backend is offline. Please start the server and try again.',
    err_network: 'Could not connect to BIS Sahayak backend. Verify that the server is running on port 8000.',
    err_extraction: 'Could not read meaningful product content from this page. Try selecting text on the page and click "Analyze Selection".',
    err_ai_service: 'AI compliance analysis is temporarily unavailable. Please try again.',
    err_unknown: 'An unexpected error occurred during analysis.',
    chips: [
      'LED bulb certification?',
      'Gold hallmarking required?',
      'Packaged water standard?',
      'How to get ISI mark?',
      'Footwear testing lab?',
      'Report fake ISI mark?'
    ]
  },
  hi: {
    welcome_title: 'नमस्ते! 🙏',
    welcome_body: 'मैं BIS सहायक हूँ — भारतीय मानकों, प्रमाणन, हॉलमार्किंग और परीक्षण के लिए आपका ब्राउज़र कोपायलट।',
    welcome_ask: 'प्रमाणन जांचने के लिए ऊपर "इस पृष्ठ को पढ़ें और विश्लेषण करें" पर क्लिक करें, या नीचे प्रश्न पूछें।',
    btn_analyze: 'इस पृष्ठ को पढ़ें और विश्लेषण करें',
    btn_retry: 'पुनः प्रयास',
    btn_selection: 'चयनित पाठ विश्लेषण',
    privacy_text: 'केवल क्लिक करने पर विश्लेषण · कोई बैकग्राउंड ट्रैकिंग नहीं',
    active_tab: 'सक्रिय टैब',
    progress_title: 'BIS अनुपालन हेतु पृष्ठ का विश्लेषण किया जा रहा है…',
    step1: 'वेबपेज सामग्री और विनिर्देश पढ़े जा रहे हैं…',
    step2: 'उत्पाद और प्रमाणन दावों की पहचान हो रही है…',
    step3: 'BIS सहायक बैकएंड को भेजा जा रहा है…',
    step4: 'आधिकारिक भारतीय मानक खोजे जा रहे हैं (BIS RAG)…',
    step5: 'BIS अनुपालन रिपोर्ट तैयार हो रही है…',
    placeholder: 'मानक, प्रमाणन के बारे में पूछें…',
    attach_image: 'उत्पाद की छवि संलग्न करें (प्रारूप)',
    remove_image: 'छवि हटाएं',
    image_attached_badge: 'छवि संलग्न (प्रारूप)',
    connected: 'कनेक्टेड',
    offline: 'ऑफ़लाइन',
    connecting: 'कनेक्ट हो रहा है…',
    copy: 'कॉपी',
    copied: 'कॉपी हो गया! ✓',
    followups: 'सुझाए गए प्रश्न',
    cleared: 'नई बातचीत शुरू हुई।',
    restricted_tab: 'ब्राउज़र आंतरिक पृष्ठों का विश्लेषण नहीं किया जा सकता। कृपया किसी उत्पाद पृष्ठ पर जाएं।',
    err_backend_offline: 'BIS सहायक बैकएंड ऑफ़लाइन है। कृपया सर्वर प्रारंभ करें और पुनः प्रयास करें।',
    err_network: 'BIS सहायक बैकएंड से कनेक्ट नहीं हो सका। जांचें कि सर्वर पोर्ट 8000 पर चल रहा है।',
    err_extraction: 'इस पृष्ठ से उत्पाद सामग्री पढ़ने में असमर्थ। पृष्ठ पर पाठ का चयन करें और "चयनित पाठ विश्लेषण" पर क्लिक करें।',
    err_ai_service: 'एआई अनुपालन विश्लेषण सेवा अस्थायी रूप से अनुपलब्ध है। कृपया पुनः प्रयास करें।',
    err_unknown: 'विश्लेषण के दौरान एक अनपेक्षित त्रुटि हुई।',
    chips: [
      'LED बल्ब प्रमाणन?',
      'सोने की हॉलमार्किंग?',
      'पैकेज्ड पानी का मानक?',
      'ISI मार्क कैसे लें?',
      'फुटवियर टेस्टिंग लैब?',
      'नकली ISI की शिकायत?'
    ]
  },
  gu: {
    welcome_title: 'નમસ્તે! 🙏',
    welcome_body: 'હું BIS સહાયક છું — ભારતીય ધોરણો, પ્રમાણન, હોલમાર્કિંગ અને પરીક્ષણ માટે તમારો બ્રાઉઝર કોપાયલટ.',
    welcome_ask: 'પાલન ચકાસવા માટે ઉપર "આ પૃષ્ઠ વાંચો અને વિશ્લેષણ કરો" પર ક્લિક કરો, અથવા નીચે પ્રશ્ન પૂછો.',
    btn_analyze: 'આ પૃષ્ઠ વાંચો અને વિશ્લેષણ કરો',
    btn_retry: 'ફરી પ્રયાસ',
    btn_selection: 'પસંદ કરેલ લખાણ વિશ્લેષણ',
    privacy_text: 'માત્ર ક્લિક પર વિશ્લેષણ · કોઈ બેકગ્રાઉન્ડ ટ્રેકિંગ નહીં',
    active_tab: 'સક્રિય ટેબ',
    progress_title: 'BIS પાલન માટે પૃષ્ઠનું વિશ્લેષણ થઈ રહ્યું છે…',
    step1: 'વેબપેજ સામગ્રી અને વિગતો વાંચવામાં આવી રહી છે…',
    step2: 'ઉત્પાદન અને પ્રમાણપત્ર દાવાઓની ઓળખ થઈ રહી છે…',
    step3: 'BIS સહાયક બેકએન્ડ પર મોકલાઈ રહ્યું છે…',
    step4: 'સત્તાવાર ભારતીય ધોરણો શોધવામાં આવી રહ્યા છે (BIS RAG)…',
    step5: 'BIS પાલન રિપોર્ટ તૈયાર થઈ રહ્યો છે…',
    placeholder: 'ધોરણો, પ્રમાણન વિશે પૂછો…',
    attach_image: 'ઉત્પાદન છબી જોડો (પ્રોટોટાઇપ)',
    remove_image: 'છબી દૂર કરો',
    image_attached_badge: 'છબી જોડાયેલ (પ્રોટોટાઇપ)',
    connected: 'કનેક્ટેડ',
    offline: 'ઑફલાઇન',
    connecting: 'કનેક્ટ થઈ રહ્યું છે…',
    copy: 'કૉપિ',
    copied: 'કૉપિ થઈ ગયું! ✓',
    followups: 'સૂચવેલા પ્રશ્નો',
    cleared: 'નવી વાતચીત શરૂ થઈ.',
    restricted_tab: 'બ્રાઉઝરના આંતરિક પૃષ્ઠોનું વિશ્લેષણ કરી શકાતું નથી. કૃપા કરીને ઉત્પાદન પૃષ્ઠ ખોલો.',
    err_backend_offline: 'BIS સહાયક બેકએન્ડ ઑફલાઇન છે. કૃપા કરીને સર્વર શરૂ કરો અને ફરી પ્રયાસ કરો.',
    err_network: 'BIS સહાયક બેકએન્ડ સાથે કનેક્ટ થઈ શક્યું નથી. પોર્ટ 8000 ચકાસો.',
    err_extraction: 'આ પૃષ્ઠમાંથી ઉત્પાદન વિગતો વાંચવામાં અસમર્થ. પૃષ્ઠ પર લખાણ પસંદ કરીને "પસંદ કરેલ લખાણ વિશ્લેષણ" પર ક્લિક કરો.',
    err_ai_service: 'AI પાલન વિશ્લેષણ સેવા અસ્થાયી રૂપે અનુપલબ્ધ છે. કૃપા કરીને ફરી પ્રયાસ કરો.',
    err_unknown: 'વિશ્લેષણ દરમિયાન અણધારી ભૂલ આવી.',
    chips: [
      'LED બલ્બ પ્રમાણન?',
      'સોનાનું હોલમાર્કિંગ?',
      'પેકેજ્ડ પાણીનું ધોરણ?',
      'ISI માર્ક કેવી રીતે મેળવવું?',
      'ફૂટવેર ટેસ્ટિંગ લેબ?',
      'નકલી ISI ની ફરિયાદ?'
    ]
  }
};

function t(key) {
  return (LANG_STRINGS[currentLang] || LANG_STRINGS.en)[key]
      || LANG_STRINGS.en[key]
      || key;
}

// -------------------------------------------
// DOM References
// -------------------------------------------

const chatEl                = document.getElementById('chat');
const chipsEl               = document.getElementById('chips');
const inputEl               = document.getElementById('input');
const sendBtn               = document.getElementById('send');
const clearBtn              = document.getElementById('btn-clear');
const statusDot             = document.getElementById('status-dot');
const statusTxt             = document.getElementById('status-text');
const btnAnalyzePage        = document.getElementById('btn-analyze-page');
const btnAnalyzeText        = document.getElementById('btn-analyze-text');
const btnRetryPage          = document.getElementById('btn-retry-page');
const btnRetryText          = document.getElementById('btn-retry-text');
const btnAnalyzeSelection   = document.getElementById('btn-analyze-selection');
const btnSelectionText      = document.getElementById('btn-selection-text');
const pageTargetTitle       = document.getElementById('page-target-title');
const privacyText           = document.getElementById('privacy-text');
const pageBanner            = document.getElementById('page-banner');
const pageBannerText        = document.getElementById('page-banner-text');
const pageBannerClose       = document.getElementById('page-banner-close');
const openFullLink          = document.getElementById('open-full');

// Image attachment DOM
const btnAttachImage        = document.getElementById('btn-attach-image');
const imageFileInput        = document.getElementById('image-file-input');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreviewThumb     = document.getElementById('image-preview-thumb');
const imagePreviewName      = document.getElementById('image-preview-name');
const imagePreviewBadge     = document.getElementById('image-preview-badge');
const btnRemoveImage        = document.getElementById('btn-remove-image');

// -------------------------------------------
// Helpers
// -------------------------------------------

function escapeHTML(str) {
  const div = document.createElement('div');
  div.innerText = str || '';
  return div.innerHTML;
}

function formatAnswer(text) {
  if (!text) return '';

  let s = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Alerts & blockquotes
  s = s.replace(/&gt; \[\!(WARNING|CAUTION|IMPORTANT)\]\s*(.*?)(?=\n|$)/gi, '<div style="background:#FFF3E6;border-left:3px solid #F28C28;padding:6px 8px;margin:5px 0;border-radius:4px;font-size:11px;"><strong>⚠️ $1:</strong> $2</div>');
  s = s.replace(/&gt; (.*?)(?=\n|$)/g, '<blockquote style="border-left:3px solid #1357A6;padding-left:8px;margin:4px 0;color:#34445A;font-style:italic;">$1</blockquote>');

  // Headings
  s = s.replace(/### (.*?)(\n|$)/g, '<p style="font-weight:700;margin-top:6px;color:#0B1F3A;font-size:12px;">$1</p>');
  s = s.replace(/## (.*?)(\n|$)/g, '<p style="font-weight:700;margin-top:8px;color:#0B1F3A;font-size:13px;border-bottom:1px solid #E2E8F0;padding-bottom:2px;">$1</p>');
  s = s.replace(/# (.*?)(\n|$)/g, '<p style="font-weight:800;margin-top:10px;color:#0B1F3A;font-size:14px;">$1</p>');

  // Bold, code, lists
  s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;font-family:monospace;font-size:10.5px;color:#0B3B78;">$1</code>');

  // Checklist items
  s = s.replace(/\[ \]/g, '⬜');
  s = s.replace(/\[x\]/gi, '✅');

  // Markdown lists
  s = s.replace(/(?:^|\n)- (.*?)(?=\n|$)/g, '<li style="margin-left:14px;margin-bottom:2px;">$1</li>');
  s = s.replace(/(?:^|\n)\* (.*?)(?=\n|$)/g, '<li style="margin-left:14px;margin-bottom:2px;">$1</li>');

  // Line breaks
  s = s.replace(/\n\n/g, '<br><br>');
  s = s.replace(/\n/g, '<br>');

  return s;
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = `✓ ${t('copied')}`;
    btn.style.color = 'var(--seal)';
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.style.color = '';
    }, 2000);
  });
}

function addRow(role, html, rawText = '', attachedImg = null) {
  const row = document.createElement('div');
  row.className = 'row ' + role;

  const avatar = role === 'assistant' ? '<div class="avatar">IS</div>' : '';

  let copyBtnHTML = '';
  if (role === 'assistant' && rawText) {
    const encoded = encodeURIComponent(rawText);
    copyBtnHTML = `
      <div class="bubble-actions">
        <button class="bubble-copy" onclick="copyText(decodeURIComponent('${encoded}'), this)">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          ${t('copy')}
        </button>
      </div>
    `;
  }

  let imgHTML = '';
  if (attachedImg) {
    imgHTML = `
      <div style="margin-bottom:6px;">
        <img src="${attachedImg.dataUrl}" alt="Attached Product Image" style="max-width:140px;max-height:90px;border-radius:6px;border:1px solid rgba(255,255,255,0.3);display:block;" />
      </div>
    `;
  }

  row.innerHTML = `${avatar}<div class="bubble">${imgHTML}${html}${copyBtnHTML}</div>`;
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function addTyping() {
  const row = document.createElement('div');
  row.className = 'row assistant typing';
  row.innerHTML = '<div class="avatar">IS</div><div class="bubble"><span></span><span></span><span></span></div>';
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function buildCitations(citations) {
  if (!citations || !citations.length) return '';

  let html = '<div class="citations">';
  for (const c of citations) {
    const isLab = c.type === 'lab';
    const cls = isLab ? 'stamp lab' : 'stamp';
    const icon = isLab
      ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3"></path></svg>'
      : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>';

    const label = escapeHTML(c.is_number || c.label || 'BIS Standard');
    const url = c.source_url ? escapeHTML(c.source_url) : '';

    if (url) {
      html += `<a href="${url}" target="_blank" rel="noopener" class="${cls}" style="text-decoration:none;">${icon} ${label} ↗</a>`;
    } else {
      html += `<span class="${cls}">${icon} ${label}</span>`;
    }
  }
  html += '</div>';
  return html;
}

function renderFollowups(questions) {
  if (!questions || !questions.length) return;

  const box = document.createElement('div');
  box.className = 'followup-container';
  box.innerHTML = `<div class="followup-label">✦ ${t('followups')}</div><div class="followup-items"></div>`;

  const items = box.querySelector('.followup-items');
  questions.slice(0, 4).forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'followup-btn';
    btn.textContent = q;
    btn.addEventListener('click', () => {
      box.remove();
      handleQuery(q);
    });
    items.appendChild(btn);
  });

  chatEl.appendChild(box);
  chatEl.scrollTop = chatEl.scrollHeight;
}

// -------------------------------------------
// Intelligent Multi-Host Backend Health Check
// -------------------------------------------

async function checkBackend() {
  statusDot.className = 'status-dot';
  statusTxt.textContent = t('connecting');

  for (const candidate of BACKEND_CANDIDATES) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1800);
      const res = await fetch(`${candidate}/health`, { 
        method: 'GET',
        signal: controller.signal 
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data.status === 'ok' || data.status === 'healthy') {
          activeBackendUrl = candidate;
          statusDot.className = 'status-dot online';
          statusTxt.textContent = t('connected');
          return true;
        }
      }
    } catch (e) {
      // Try next candidate
    }
  }

  statusDot.className = 'status-dot offline';
  statusTxt.textContent = t('offline');
  return false;
}

// -------------------------------------------
// Active Tab Preview & Capability Check
// -------------------------------------------

async function updateActiveTabPreview() {
  if (!chrome.tabs || !chrome.tabs.query) {
    if (pageTargetTitle) pageTargetTitle.textContent = `${t('active_tab')}: Ready`;
    return;
  }

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      if (pageTargetTitle) pageTargetTitle.textContent = `${t('active_tab')}: —`;
      return;
    }

    const url = tab.url || '';
    const isRestricted = url.startsWith('chrome://') || 
                         url.startsWith('chrome-extension://') || 
                         url.startsWith('edge://') || 
                         url.startsWith('about:');

    if (isRestricted) {
      if (pageTargetTitle) pageTargetTitle.textContent = t('restricted_tab');
      if (btnAnalyzePage) btnAnalyzePage.disabled = true;
      if (btnAnalyzeSelection) btnAnalyzeSelection.style.display = 'none';
      return;
    }

    if (btnAnalyzePage) btnAnalyzePage.disabled = false;
    const rawTitle = tab.title || url;
    const cleanTitle = rawTitle.length > 36 ? rawTitle.substring(0, 36) + '…' : rawTitle;
    if (pageTargetTitle) pageTargetTitle.textContent = `${t('active_tab')}: ${cleanTitle}`;

    // Check if user has selected text
    chrome.tabs.sendMessage(tab.id, { action: 'analyzeSelectedText' }, (resp) => {
      if (chrome.runtime.lastError) return;
      if (resp && resp.selectedText && resp.selectedText.length > 5) {
        if (btnAnalyzeSelection) btnAnalyzeSelection.style.display = 'inline-flex';
      }
    });
  } catch (err) {
    console.log('Tab preview note:', err);
  }
}

// -------------------------------------------
// On-Demand Page Analysis Pipeline
// -------------------------------------------

async function runAnalysisPipeline(pageData) {
  if (isAnalyzing) return;
  isAnalyzing = true;

  if (btnAnalyzePage) btnAnalyzePage.disabled = true;
  if (btnRetryPage) btnRetryPage.style.display = 'none';
  if (chipsEl) chipsEl.style.display = 'none';

  // 1. Verify backend health
  const isHealthy = await checkBackend();
  if (!isHealthy) {
    isAnalyzing = false;
    if (btnAnalyzePage) btnAnalyzePage.disabled = false;
    if (btnRetryPage) btnRetryPage.style.display = 'inline-flex';
    addRow('assistant', `
      <p style="color:var(--danger);font-weight:700;">🔴 ${t('err_backend_offline')}</p>
      <p style="font-size:11px;margin-top:4px;">${t('backend_help') || 'Start server:'}</p>
      <p style="font-family:monospace;font-size:10px;background:#f1f5f9;padding:4px 6px;border-radius:4px;margin-top:4px;">
        cd backend &amp;&amp; python -m uvicorn main:app --port 8000 --reload
      </p>
    `);
    return;
  }

  // 2. Render 5-Step Animated Progress Card
  const progressRow = document.createElement('div');
  progressRow.className = 'row assistant';
  progressRow.innerHTML = `
    <div class="avatar">IS</div>
    <div class="bubble" style="width:100%;">
      <div class="analysis-progress-card">
        <div class="progress-header">
          <div class="step-spinner"></div>
          <span>${t('progress_title')}</span>
        </div>
        <div class="progress-step active" id="p-step-1">
          <span class="step-icon"><div class="step-spinner"></div></span>
          <span>${t('step1')}</span>
        </div>
        <div class="progress-step" id="p-step-2">
          <span class="step-icon">○</span>
          <span>${t('step2')}</span>
        </div>
        <div class="progress-step" id="p-step-3">
          <span class="step-icon">○</span>
          <span>${t('step3')}</span>
        </div>
        <div class="progress-step" id="p-step-4">
          <span class="step-icon">○</span>
          <span>${t('step4')}</span>
        </div>
        <div class="progress-step" id="p-step-5">
          <span class="step-icon">○</span>
          <span>${t('step5')}</span>
        </div>
      </div>
    </div>
  `;
  chatEl.appendChild(progressRow);
  chatEl.scrollTop = chatEl.scrollHeight;

  function markStep(num, status) {
    const el = document.getElementById(`p-step-${num}`);
    if (!el) return;
    el.className = `progress-step ${status}`;
    const icon = el.querySelector('.step-icon');
    if (!icon) return;
    if (status === 'done') icon.innerHTML = '✓';
    else if (status === 'active') icon.innerHTML = '<div class="step-spinner"></div>';
    else icon.innerHTML = '○';
  }

  try {
    // Validate extracted text
    const textContent = (pageData.content || pageData.main_text || '').trim();
    if (!textContent && !pageData.title) {
      throw new Error('ERR_EXTRACTION');
    }

    lastExtractedPageData = pageData;
    markStep(1, 'done');
    markStep(2, 'done');
    markStep(3, 'active');

    // Show top banner with detected title
    const pTitle = pageData.productName || pageData.title || '';
    if (pageBanner && pageBannerText && pTitle) {
      const shortTitle = pTitle.length > 36 ? pTitle.substring(0, 36) + '…' : pTitle;
      pageBannerText.textContent = `📄 ${shortTitle}`;
      pageBanner.style.display = 'flex';
    }

    markStep(3, 'done');
    markStep(4, 'active');

    // Send payload to active backend
    const res = await fetch(`${activeBackendUrl}/api/analyze-page`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        page: pageData,
        language: currentLang,
        conversation_id: currentConversationId
      })
    });

    if (!res.ok) {
      throw new Error(`SERVER_ERR_${res.status}`);
    }

    markStep(4, 'done');
    markStep(5, 'active');

    const data = await res.json();
    progressRow.remove();

    if (data.conversation_id) {
      currentConversationId = data.conversation_id;
      chrome.storage.local.set({ bis_conv_id: currentConversationId });
    }

    // Persist structured page context for subsequent follow-up queries
    currentPageContext = {
      url: pageData.url,
      title: pageData.title,
      domain: pageData.domain,
      type: pageData.type || 'product_page',
      product: {
        name: pageData.productName || pageData.title,
        brand: pageData.brand,
        model: pageData.model,
        category: pageData.category,
        material: pageData.material,
        price: pageData.price
      },
      claims: pageData.claims || [],
      analysis: data.markdown_report || data.answer,
      citations: data.citations || []
    };
    chrome.storage.local.set({ bis_page_context: currentPageContext });

    statusDot.className = 'status-dot online';
    statusTxt.textContent = t('connected');

    const reportContent = data.markdown_report || data.answer || 'Analysis complete.';
    const answerHTML = formatAnswer(reportContent);
    const citationsHTML = buildCitations(data.citations || data.sources);

    addRow('assistant', answerHTML + citationsHTML, reportContent);

    // Dynamic smart follow-up suggestions
    if (data.suggested_questions && data.suggested_questions.length > 0) {
      renderFollowups(data.suggested_questions);
    }

  } catch (err) {
    progressRow.remove();
    console.error('Analyze page error:', err);

    let userErrMsg = t('err_unknown');
    if (err.message === 'ERR_EXTRACTION') {
      userErrMsg = t('err_extraction');
      if (btnAnalyzeSelection) btnAnalyzeSelection.style.display = 'inline-flex';
    } else if (err.message && err.message.startsWith('SERVER_ERR')) {
      userErrMsg = `${t('err_ai_service')} (${err.message})`;
    } else if (err.name === 'TypeError' || err.message.includes('fetch')) {
      userErrMsg = t('err_network');
      statusDot.className = 'status-dot offline';
      statusTxt.textContent = t('offline');
    }

    if (btnRetryPage) btnRetryPage.style.display = 'inline-flex';

    addRow('assistant', `
      <p style="color:var(--danger);font-weight:700;">⚠️ ${escapeHTML(userErrMsg)}</p>
      <p style="font-size:11px;color:var(--stone);margin-top:4px;">Click <strong>Retry</strong> or select relevant product text and try again.</p>
    `);
  } finally {
    isAnalyzing = false;
    if (btnAnalyzePage) btnAnalyzePage.disabled = false;
  }
}

async function handleAnalyzePage() {
  if (isAnalyzing) return;
  if (!chrome.tabs || !chrome.tabs.query) return;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return;

  const url = tab.url || '';
  if (url.startsWith('chrome://') || url.startsWith('chrome-extension://') || url.startsWith('edge://') || url.startsWith('about:')) {
    addRow('assistant', `<p>⚠️ <strong>${t('restricted_tab')}</strong></p>`);
    return;
  }

  // 1. Extract content script data
  let pageData = null;
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'analyzeCurrentPage' });
    if (response && response.data) {
      pageData = response.data;
    }
  } catch (msgErr) {
    // Inject content script and retry
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content/content.js']
      });
      await new Promise(r => setTimeout(r, 200));
      const retryResp = await chrome.tabs.sendMessage(tab.id, { action: 'analyzeCurrentPage' });
      if (retryResp && retryResp.data) {
        pageData = retryResp.data;
      }
    } catch (injectErr) {
      console.warn('Content script injection fallback failed:', injectErr);
    }
  }

  // Scripting direct fallback
  if (!pageData) {
    try {
      const evalRes = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => ({
          title: document.title || '',
          pageTitle: document.title || '',
          url: window.location.href,
          domain: window.location.hostname,
          type: 'product_page',
          content: (document.body ? document.body.innerText : '').substring(0, 3200),
          main_text: (document.body ? document.body.innerText : '').substring(0, 3200),
          claims: []
        })
      });
      if (evalRes && evalRes[0] && evalRes[0].result) {
        pageData = evalRes[0].result;
      }
    } catch (evalErr) {
      console.warn('Scripting evaluation failed:', evalErr);
    }
  }

  if (!pageData) {
    addRow('assistant', `<p style="color:var(--danger);font-weight:700;">⚠️ ${t('err_extraction')}</p>`);
    if (btnRetryPage) btnRetryPage.style.display = 'inline-flex';
    return;
  }

  await runAnalysisPipeline(pageData);
}

// -------------------------------------------
// Analyze Selected Text Fallback
// -------------------------------------------

async function handleAnalyzeSelection() {
  if (isAnalyzing) return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return;

  try {
    const resp = await chrome.tabs.sendMessage(tab.id, { action: 'analyzeSelectedText' });
    if (resp && resp.data && resp.selectedText) {
      await runAnalysisPipeline(resp.data);
    } else {
      addRow('assistant', `<p>⚠️ Please select text on the webpage first, then click "Analyze Selection".</p>`);
    }
  } catch (err) {
    addRow('assistant', `<p>⚠️ Could not capture selection. Refresh the webpage and try selecting again.</p>`);
  }
}

// -------------------------------------------
// Conversation-Aware Follow-Up Chat (/api/chat)
// -------------------------------------------

async function handleQuery(text) {
  const query = (text || '').trim();
  if (!query && !attachedImageData) return;

  // Add user message with thumbnail if image attached
  addRow('user', escapeHTML(query || 'Attached product image for compliance check'), query, attachedImageData);
  
  // Clear input and prototype image attachment
  inputEl.value = '';
  clearAttachedImage();
  if (chipsEl) chipsEl.style.display = 'none';

  const typingRow = addTyping();

  try {
    const res = await fetch(`${activeBackendUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: query || 'Analyze attached product image for BIS compliance',
        language: currentLang,
        conversation_id: currentConversationId,
        page_context: currentPageContext || ''
      })
    });

    if (!res.ok) {
      throw new Error(`Server error: ${res.status}`);
    }

    const data = await res.json();
    typingRow.remove();

    if (data.conversation_id) {
      currentConversationId = data.conversation_id;
      chrome.storage.local.set({ bis_conv_id: currentConversationId });
    }

    statusDot.className = 'status-dot online';
    statusTxt.textContent = t('connected');

    const answerHTML = formatAnswer(data.answer || 'No answer returned.');
    const citationsHTML = buildCitations(data.citations || data.sources);

    addRow('assistant', answerHTML + citationsHTML, data.answer);

    // Dynamic smart follow-up suggestions
    if (data.suggested_questions && data.suggested_questions.length > 0) {
      renderFollowups(data.suggested_questions);
    }

  } catch (err) {
    typingRow.remove();
    console.error('BIS Sahayak chat error:', err);

    await checkBackend();

    addRow('assistant', `
      <p style="color:var(--danger);font-weight:700;">⚠️ ${t('err_network')}</p>
      <p style="font-size:11px;margin-top:4px;">Ensure server is running: <code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;">python -m uvicorn main:app --port 8000</code></p>
    `);
  }
}

// -------------------------------------------
// Image Attachment Prototype Handlers
// -------------------------------------------

function clearAttachedImage() {
  attachedImageData = null;
  if (imageFileInput) imageFileInput.value = '';
  if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
}

if (btnAttachImage && imageFileInput) {
  btnAttachImage.addEventListener('click', () => {
    imageFileInput.click();
  });

  imageFileInput.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      attachedImageData = {
        name: file.name,
        size: file.size,
        type: file.type,
        dataUrl: event.target.result
      };

      if (imagePreviewThumb) imagePreviewThumb.src = attachedImageData.dataUrl;
      if (imagePreviewName) imagePreviewName.textContent = file.name;
      if (imagePreviewBadge) imagePreviewBadge.textContent = t('image_attached_badge');
      if (imagePreviewContainer) imagePreviewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
  });
}

if (btnRemoveImage) {
  btnRemoveImage.addEventListener('click', clearAttachedImage);
}

// -------------------------------------------
// Clear Conversation
// -------------------------------------------

function clearConversation() {
  chatEl.innerHTML = '';
  currentConversationId = '';
  currentPageContext = null;
  lastExtractedPageData = null;
  clearAttachedImage();
  if (pageBanner) pageBanner.style.display = 'none';
  if (btnRetryPage) btnRetryPage.style.display = 'none';
  if (btnAnalyzeSelection) btnAnalyzeSelection.style.display = 'none';
  chrome.storage.local.remove(['bis_conv_id', 'bis_page_context', 'last_selected_text']);

  addRow('assistant', `
    <p><strong>${t('welcome_title')}</strong></p>
    <p>${t('welcome_body')}</p>
    <p>${t('welcome_ask')}</p>
  `);

  renderChips();
}

// -------------------------------------------
// Quick Action Chips
// -------------------------------------------

function renderChips() {
  if (!chipsEl) return;
  chipsEl.innerHTML = '';
  chipsEl.style.display = 'flex';

  const chips = t('chips');
  if (!Array.isArray(chips)) return;

  for (const label of chips) {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.textContent = label;
    btn.addEventListener('click', () => handleQuery(label));
    chipsEl.appendChild(btn);
  }
}

// -------------------------------------------
// Language Switching
// -------------------------------------------

function setLanguage(lang) {
  currentLang = lang;
  chrome.storage.local.set({ bis_lang: lang });

  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === lang);
  });

  if (btnAnalyzeText) btnAnalyzeText.textContent = t('btn_analyze');
  if (btnRetryText) btnRetryText.textContent = t('btn_retry');
  if (btnSelectionText) btnSelectionText.textContent = t('btn_selection');
  if (privacyText) privacyText.textContent = t('privacy_text');
  if (inputEl) inputEl.placeholder = t('placeholder');
  if (btnAttachImage) btnAttachImage.title = t('attach_image');
  if (imagePreviewBadge) imagePreviewBadge.textContent = t('image_attached_badge');

  updateActiveTabPreview();
  renderChips();
}

// -------------------------------------------
// Event Listeners
// -------------------------------------------

sendBtn.addEventListener('click', () => handleQuery(inputEl.value));
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleQuery(inputEl.value);
});

clearBtn.addEventListener('click', clearConversation);

btnAnalyzePage.addEventListener('click', handleAnalyzePage);
if (btnRetryPage) btnRetryPage.addEventListener('click', () => {
  if (lastExtractedPageData) runAnalysisPipeline(lastExtractedPageData);
  else handleAnalyzePage();
});
if (btnAnalyzeSelection) btnAnalyzeSelection.addEventListener('click', handleAnalyzeSelection);

document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => setLanguage(btn.dataset.lang));
});

if (pageBannerClose) {
  pageBannerClose.addEventListener('click', () => {
    pageBanner.style.display = 'none';
    currentPageContext = null;
    chrome.storage.local.remove(['bis_page_context', 'last_selected_text']);
  });
}

if (openFullLink) {
  openFullLink.addEventListener('click', (e) => {
    e.preventDefault();
    const targetUrl = `${activeBackendUrl}/`;
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
      chrome.tabs.create({ url: targetUrl });
    } else {
      window.open(targetUrl, '_blank');
    }
  });
}

// -------------------------------------------
// Initialize
// -------------------------------------------

(async function init() {
  // Load saved state
  if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(['bis_lang', 'bis_conv_id', 'bis_page_context'], (res) => {
      if (res.bis_lang && ['en', 'hi', 'gu'].includes(res.bis_lang)) {
        currentLang = res.bis_lang;
        document.querySelectorAll('.lang-btn').forEach(btn => {
          btn.classList.toggle('active', btn.dataset.lang === currentLang);
        });
        if (btnAnalyzeText) btnAnalyzeText.textContent = t('btn_analyze');
        if (btnRetryText) btnRetryText.textContent = t('btn_retry');
        if (btnSelectionText) btnSelectionText.textContent = t('btn_selection');
        if (privacyText) privacyText.textContent = t('privacy_text');
      }
      if (res.bis_conv_id) {
        currentConversationId = res.bis_conv_id;
      }
      if (res.bis_page_context) {
        currentPageContext = res.bis_page_context;
        if (pageBanner && pageBannerText && currentPageContext.title) {
          const shortTitle = currentPageContext.title.length > 36 ? currentPageContext.title.substring(0, 36) + '…' : currentPageContext.title;
          pageBannerText.textContent = `📄 ${shortTitle}`;
          pageBanner.style.display = 'flex';
        }
      }
    });
  }

  // Welcome message
  addRow('assistant', `
    <p><strong>${t('welcome_title')}</strong></p>
    <p>${t('welcome_body')}</p>
    <p>${t('welcome_ask')}</p>
  `);

  renderChips();
  await checkBackend();
  await updateActiveTabPreview();
  if (inputEl) inputEl.focus();
})();
