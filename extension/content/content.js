// BIS Sahayak — Content Script (MV3)
// Privacy-first page analysis: runs ONLY when explicitly requested by user.

// -------------------------------------------------------------
// Helper: Extract Schema.org JSON-LD product data
// -------------------------------------------------------------
function extractJsonLd() {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of scripts) {
    try {
      const data = JSON.parse(script.textContent);
      const items = Array.isArray(data) ? data : (data['@graph'] || [data]);
      for (const item of items) {
        const type = (item['@type'] || '').toLowerCase();
        if (type.includes('product')) {
          return {
            name: item.name || '',
            brand: typeof item.brand === 'object' ? (item.brand.name || '') : (item.brand || ''),
            model: item.model || item.mpn || '',
            category: item.category || '',
            description: (item.description || '').substring(0, 300),
            sku: item.sku || ''
          };
        }
      }
    } catch (e) {
      // Ignore invalid JSON-LD
    }
  }
  return null;
}

// -------------------------------------------------------------
// Helper: Extract technical specifications / key-value table
// -------------------------------------------------------------
function extractSpecifications() {
  const specs = {};
  // 1. Check definition lists (dl, dt, dd)
  const dts = document.querySelectorAll('dl dt');
  dts.forEach(dt => {
    const dd = dt.nextElementSibling;
    if (dd && dd.tagName.toLowerCase() === 'dd') {
      const key = dt.innerText.trim().replace(/[:\s]+$/, '');
      const val = dd.innerText.trim();
      if (key && val && key.length < 40 && val.length < 100) {
        specs[key] = val;
      }
    }
  });

  // 2. Check table rows in spec containers
  const specRows = document.querySelectorAll(
    '#productDetails_techSpec_section_1 tr, .prod-spec tr, .spec-table tr, .technical-details tr, [data-feature-name="technicalSpecifications"] tr, table.a-keyvalue tr'
  );
  specRows.forEach(row => {
    const th = row.querySelector('th, td:first-child');
    const td = row.querySelector('td:last-child');
    if (th && td && th !== td) {
      const key = th.innerText.trim().replace(/[:\s]+$/, '');
      const val = td.innerText.trim();
      if (key && val && key.length < 40 && val.length < 100) {
        specs[key] = val;
      }
    }
  });

  return specs;
}

// -------------------------------------------------------------
// Helper: Detect BIS, ISI, Hallmarking, and Standard Claims
// -------------------------------------------------------------
function detectClaims(text) {
  const claims = new Set();
  const lower = text.toLowerCase();

  // ISI Mark claims
  if (/\b(isi\s*mark|isi\s*certified|isi\s*approved|isi\s*certification)\b/i.test(text)) {
    claims.add("ISI Mark Claimed");
  }

  // BIS Certification claims
  if (/\b(bis\s*certified|bis\s*approved|bis\s*certification|bis\s*registered|bis\s*compliant)\b/i.test(text)) {
    claims.add("BIS Certification Claimed");
  }

  // Hallmarking / HUID claims
  if (/\b(hallmark|hallmarked|bis\s*hallmark|916\s*hallmark)\b/i.test(text)) {
    claims.add("Hallmark Claimed");
  }
  if (/\b(huid|hallmark\s*unique\s*identification)\b/i.test(text)) {
    claims.add("HUID Mentioned");
  }

  // Specific Indian Standards mentioned (e.g. IS 2347, IS 4151, IS 16102)
  const isMatches = text.match(/\bIS\s*[:\-]?\s*(\d{3,5}(?:\s*\(Part\s*\d+\))?(?::\d{4})?)\b/gi);
  if (isMatches) {
    isMatches.slice(0, 5).forEach(m => claims.add(`Standard Mentioned: ${m.replace(/\s+/g, ' ').trim()}`));
  }

  // Quality Control Order claims
  if (/\b(qco|quality\s*control\s*order)\b/i.test(text)) {
    claims.add("QCO Compliance Mentioned");
  }

  return Array.from(claims);
}

// -------------------------------------------------------------
// Main Extraction Function: Deep Clean & Structured Representation
// -------------------------------------------------------------
function extractPageData() {
  const url = window.location.href;
  const title = document.title || '';

  // 1. Meta tags
  const getMeta = (name) => {
    const el = document.querySelector(`meta[name="${name}" i], meta[property="${name}" i]`);
    return el ? el.getAttribute('content') || '' : '';
  };

  const meta = {
    description: getMeta('description') || getMeta('og:description'),
    ogTitle: getMeta('og:title'),
    ogType: getMeta('og:type'),
    brand: getMeta('product:brand') || getMeta('brand'),
    category: getMeta('product:category') || getMeta('category')
  };

  // 2. Schema.org JSON-LD
  const jsonLd = extractJsonLd();

  // 3. Headings & Product Titles
  const headings = [];
  const mainTitleEl = document.querySelector(
    '#productTitle, .product-title, [data-automation-id="product-title"], h1'
  );
  if (mainTitleEl && mainTitleEl.innerText.trim()) {
    headings.push(mainTitleEl.innerText.trim());
  }

  document.querySelectorAll('h1, h2').forEach(el => {
    const txt = el.innerText.trim();
    if (txt && txt.length > 5 && txt.length < 150 && !headings.includes(txt)) {
      headings.push(txt);
    }
  });

  // 4. Specifications table
  const specs = extractSpecifications();

  // 5. Cleaned Main Content Text
  // Clone the relevant container to safely remove junk without altering user's live DOM
  const mainContainer = document.querySelector('main, article, [role="main"], #centerCol, #dp-container') || document.body;
  const clone = mainContainer.cloneNode(true);

  // Strip noise elements
  const junkSelectors = [
    'script', 'style', 'noscript', 'nav', 'header', 'footer',
    '[role="banner"]', '[role="navigation"]', '.nav', '.navbar',
    '.ad', '.ads', '.advertisement', '#cookie-banner', '.cookie',
    '.modal', '.popup', 'iframe', 'svg', 'form', 'input', 'textarea',
    'select', 'button', '.reviews', '#reviews', '.comments', '#comments'
  ];
  clone.querySelectorAll(junkSelectors.join(',')).forEach(el => el.remove());

  let rawText = clone.innerText || '';
  // Collapse whitespace
  rawText = rawText.replace(/\s+/g, ' ').trim();

  // Detect explicit certification claims
  const claims = detectClaims(rawText);
  const isiClaims = claims.filter(c => c.toLowerCase().includes('isi'));
  const bisClaims = claims.filter(c => c.toLowerCase().includes('bis'));
  const huidClaims = claims.filter(c => c.toLowerCase().includes('huid') || c.toLowerCase().includes('hallmark'));
  const standardNumbers = claims.filter(c => c.toLowerCase().includes('standard mentioned')).map(c => c.replace('Standard Mentioned: ', ''));

  // Truncate clean text to ~3500 characters for token efficiency
  const cleanedText = rawText.substring(0, 3500);

  const domain = window.location.hostname || '';
  const mainHeading = (headings && headings.length > 0) ? headings[0] : title;
  const productName = (jsonLd && jsonLd.name) ? jsonLd.name : mainHeading;
  const brand = (jsonLd && jsonLd.brand) || meta.brand || specs['Brand'] || specs['Brand Name'] || specs['Manufacturer'] || '';
  const model = (jsonLd && jsonLd.model) || specs['Model'] || specs['Model Number'] || specs['Item Model Number'] || '';
  const category = (jsonLd && jsonLd.category) || meta.category || specs['Category'] || '';
  const material = specs['Material'] || specs['Primary Material'] || specs['Outer Material'] || '';
  const price = specs['Price'] || meta.price || '';
  const manufacturer = specs['Manufacturer'] || specs['Manufactured By'] || brand || '';
  const countryOfOrigin = specs['Country of Origin'] || specs['Country Of Origin'] || '';

  let pageType = 'document';
  const urlLower = url.toLowerCase();
  if (jsonLd && jsonLd.name) {
    pageType = 'product_page';
  } else if (urlLower.includes('/dp/') || urlLower.includes('/product') || urlLower.includes('/item/') || Object.keys(specs).length > 2) {
    pageType = 'product_page';
  } else if (claims.length > 0) {
    pageType = 'product_page';
  }

  return {
    url: url,
    title: title,
    pageTitle: title,
    domain: domain,
    type: pageType,
    mainHeading: mainHeading,
    productName: productName,
    brand: brand,
    model: model,
    category: category,
    description: (jsonLd && jsonLd.description) || meta.description || '',
    price: price,
    specifications: specs,
    specs: specs,
    manufacturer: manufacturer,
    material: material,
    countryOfOrigin: countryOfOrigin,
    claims: claims,
    isiClaims: isiClaims,
    bisClaims: bisClaims,
    huid: huidClaims,
    standardNumbers: standardNumbers,
    content: cleanedText,
    main_text: cleanedText,
    metadata: meta,
    jsonLd: jsonLd,
    headings: headings.slice(0, 6)
  };
}

// -------------------------------------------------------------
// Selection capture for quick lookups
// -------------------------------------------------------------
document.addEventListener('mouseup', () => {
  const selection = window.getSelection().toString().trim();
  if (selection.length > 5 && selection.length < 2000) {
    try {
      chrome.storage.local.set({
        last_selected_text: selection,
        last_selected_url: window.location.href,
        last_selected_title: document.title
      });
    } catch (e) {
      // Storage unavailable or context invalidated
    }
  }
});

// -------------------------------------------------------------
// Message Listener
// -------------------------------------------------------------
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyzeCurrentPage') {
    try {
      const pageData = extractPageData();
      sendResponse({ success: true, data: pageData });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
    return true;
  }

  if (request.action === 'analyzeSelectedText') {
    try {
      const selection = window.getSelection().toString().trim();
      const pageData = extractPageData();
      if (selection) {
        pageData.content = selection;
        pageData.main_text = selection;
        pageData.selectedText = selection;
      }
      sendResponse({ success: true, data: pageData, selectedText: selection });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
    return true;
  }

  // Backward compatibility
  if (request.action === 'getPageContext') {
    const title = document.title || '';
    const mainEl = document.querySelector('main, article, [role="main"], #productTitle, .product-title');
    const text = mainEl ? mainEl.innerText : document.body.innerText;
    sendResponse({
      title: title,
      text: (text || '').substring(0, 3000),
      url: window.location.href
    });
    return true;
  }
});
