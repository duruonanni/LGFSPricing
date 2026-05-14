/**
 * Netlify Function: parse-quote
 * Parses Lenovo BRPAS or Special Bid PDF quote and returns asset lines.
 * Accepts: POST { file: "<base64 pdf>" }
 * Returns: { lines: [...], format: "brpas"|"special_bid" }
 */

const pdfParse = require('pdf-parse');

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function jsonResponse(body, statusCode) {
  return {
    statusCode: statusCode || 200,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    body: JSON.stringify(body),
  };
}

// ── Asset type classifier ─────────────────────────────────────
const ASSET_RULES = [
  [['notebook', 'nb ', 'thinkpad', 'laptop'],          'Laptop / Desktop / AIO'],
  [['workstation', 'thinkstation'],                    'Workstation'],
  [['thinkvision', 'monitor', 'display'],              'Monitors'],
  [['tablet', 'x12det', 'x1 tablet'],                  'Tablets'],
  [['iphone', 'ipad'],                                 'Apple iPhones'],
  [['motorola', 'moto '],                              'Motorola Mobiles'],
  [['server', 'thinksystem', 'thinkagile'],            'Servers'],
  [['storage', 'nas ', 'san '],                        'Storage'],
  [['switch', 'router', 'network', 'ethernet adapter'],'Networking'],
  [['desktop', 'thinkcenter', 'tc ', ' aio'],          'Laptop / Desktop / AIO'],
];
const SERVICE_KEYWORDS = [
  'warranty','premier support','accidental damage','cfs ','managed ',
  'autopilot','install service','mice_bo','case_bo','mouse','backpack',
  'bag','asset tag','electric test','handling charge','bios settings',
  'ready to provision','white glove',
];

function classify(desc) {
  const d = (desc || '').toLowerCase();
  for (const kw of SERVICE_KEYWORDS) {
    if (d.includes(kw)) return 'Peripherals / Soft Cost / Services';
  }
  for (const [kws, atype] of ASSET_RULES) {
    if (kws.some(k => d.includes(k))) return atype;
  }
  return 'Peripherals / Soft Cost / Services';
}

function cleanPrice(raw) {
  if (!raw) return 0;
  const s = String(raw).replace(/[A-Z$€£¥,\s]/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

function isHeaderLine(line) {
  const l = line.toLowerCase();
  return ['part number','product code','description','item no'].some(h => l.includes(h));
}

function parseQuoteText(fullText) {
  const results   = [];
  const seenKeys  = new Set();

  function addResult(partNum, description, qty, price) {
    if (!partNum || qty <= 0 || price <= 0) return;
    if ((description + partNum).toLowerCase().includes('grand total')) return;
    const key = `${partNum}|${qty}|${Math.round(price * 100)}`;
    if (seenKeys.has(key)) return;
    seenKeys.add(key);
    results.push({
      partNumber:  partNum,
      description: description || partNum,
      qty,
      unitPrice:   price,
      assetType:   classify(description),
      oem:         'Lenovo',
    });
  }

  // Detect format
  let fmt = 'brpas';
  if (/Product and\/or Service Selection/i.test(fullText)) fmt = 'special_bid';

  // Narrow to product section
  const secRe  = /PRODUCT AND SERVICE DETAILS|Product and\/or Service Selection/i;
  const endRe  = /CONFIGURATION DETAILS|Grand Total|TERMS AND CONDITIONS/i;
  const secM   = secRe.exec(fullText);
  let section  = fullText;
  if (secM) {
    const after = fullText.slice(secM.index + secM[0].length);
    const endM  = endRe.exec(after);
    section = endM ? after.slice(0, endM.index) : after;
  }

  // Pattern A: <line#>  <PARTCODE>  <qty>  <price>
  const patPlain  = /^\s*\d{1,3}\s+([A-Z0-9]{6,14})\s+(\d+)\s+([A-Z]{0,3}[\d,]+\.\d{2})\b/;
  // Pattern B: <line#>  <PARTCODE>  <desc>  <qty>  <price>  <price>
  const patInline = /^\s*\d{1,3}\s+([A-Z0-9]{6,14})\s+(.+?)\s+(\d+)\s+[A-Z]{0,3}([\d,]+\.\d{2})\s+[A-Z]{0,3}[\d,]+\.\d{2}/;

  const lines      = section.split('\n');
  let pendingDesc  = [];
  let afterRow     = false;

  for (const line of lines) {
    // Try Pattern A
    let m = patPlain.exec(line);
    if (!m) {
      // Try Pattern B
      const m2 = patInline.exec(line);
      if (m2) {
        const [, part, inlineDesc, qtyS, priceS] = m2;
        const qty   = parseInt(qtyS, 10);
        const price = cleanPrice(priceS);
        const key   = `${part}|${qty}|${Math.round(price * 100)}`;
        if (!seenKeys.has(key)) {
          const before = pendingDesc.join(' ').trim();
          const desc   = before ? `${before} ${inlineDesc}`.trim() : inlineDesc;
          addResult(part, desc, qty, price);
        }
        pendingDesc = [];
        afterRow    = true;
        continue;
      }
      // Not a data row
      const s = line.trim();
      if (afterRow) {
        afterRow    = false;
        pendingDesc = [];
      } else if (s && !/^[\d,.\s%()[\]\-AUD]+$/.test(s) && !isHeaderLine(s)) {
        pendingDesc.push(s);
      } else if (!s) {
        pendingDesc = [];
      }
      continue;
    }

    // Pattern A matched
    const [, part, qtyS, priceS] = m;
    const qty   = parseInt(qtyS, 10);
    const price = cleanPrice(priceS);
    const key   = `${part}|${qty}|${Math.round(price * 100)}`;
    if (!seenKeys.has(key)) {
      const desc = pendingDesc.join(' ').replace(/\s+/g, ' ').trim();
      addResult(part, desc, qty, price);
    }
    pendingDesc = [];
    afterRow    = true;
  }

  return { results, fmt };
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const body    = JSON.parse(event.body || '{}');
    const b64     = body.file || '';
    if (!b64) return jsonResponse({ error: 'Missing file (base64)' }, 400);

    const buffer  = Buffer.from(b64, 'base64');
    const parsed  = await pdfParse(buffer);
    const text    = parsed.text || '';

    if (!text.trim()) {
      return jsonResponse({ error: 'Could not extract text from PDF.' }, 422);
    }

    const { results, fmt } = parseQuoteText(text);

    if (!results.length) {
      // Return extracted text for debugging (first 3000 chars of product section)
      const secM2  = /PRODUCT AND SERVICE DETAILS|Product and\/or Service Selection/i.exec(text);
      const sample = secM2 ? text.slice(secM2.index, secM2.index + 3000) : text.slice(0, 3000);
      return jsonResponse({
        error: 'No product lines found. Supported formats: Lenovo BRPAS quote and Special Bid.',
        _debug_text: sample,
      }, 422);
    }

    return jsonResponse({ success: true, format: fmt, lines: results });

  } catch (err) {
    return jsonResponse({ error: String(err.message || err) }, 500);
  }
};
