/**
 * Netlify Function: parse-quote
 * Parses Lenovo BRPAS or Special Bid PDF quote and returns asset lines.
 * Accepts: POST { file: "<base64 pdf>" }
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

// ── Asset classifier ──────────────────────────────────────────
const ASSET_RULES = [
  [['notebook','nb ','thinkpad','laptop'],         'Laptop / Desktop / AIO'],
  [['workstation','thinkstation'],                 'Workstation'],
  [['thinkvision','monitor','display'],            'Monitors'],
  [['tablet','x12det','x1 tablet'],               'Tablets'],
  [['iphone','ipad'],                             'Apple iPhones'],
  [['motorola','moto '],                          'Motorola Mobiles'],
  [['server','thinksystem','thinkagile'],         'Servers'],
  [['storage','nas ','san '],                     'Storage'],
  [['switch','router','network','ethernet adapter'],'Networking'],
  [['desktop','thinkcenter','tc ',' aio'],        'Laptop / Desktop / AIO'],
];
const SERVICE_KEYWORDS = [
  'warranty','premier support','accidental damage','cfs ','managed ',
  'autopilot','install service','mouse','backpack','bag','asset tag',
  'electric test','handling charge','bios settings','ready to provision',
  'white glove','mice_bo','case_bo',
];
function classify(text) {
  const t = (text || '').toLowerCase();
  for (const kw of SERVICE_KEYWORDS) if (t.includes(kw)) return 'Peripherals / Soft Cost / Services';
  for (const [kws, atype] of ASSET_RULES) if (kws.some(k => t.includes(k))) return atype;
  return 'Peripherals / Soft Cost / Services';
}
function cleanPrice(s) {
  const n = parseFloat(String(s || '').replace(/[A-Z$€£¥,\s]/g, ''));
  return isNaN(n) ? 0 : n;
}
function isHeaderLine(l) {
  const t = l.toLowerCase();
  return ['part number','product code','description','item no','unit price','total price'].some(h => t.includes(h));
}

// ── Core parser – handles pdf-parse column-concatenated output ────────────
function parseQuoteText(fullText) {
  const results  = [];
  const seenKeys = new Set();

  function addLine(partNum, description, qty, price) {
    if (!partNum || qty <= 0 || price <= 0) return;
    if (/(grand total)/i.test(partNum + description)) return;
    const k = `${partNum}|${qty}|${Math.round(price * 100)}`;
    if (seenKeys.has(k)) return;
    seenKeys.add(k);
    results.push({
      partNumber:  partNum.slice(0, 14),
      description: description || partNum,
      qty,
      unitPrice:   price,
      assetType:   classify(partNum + ' ' + description),
      oem:         'Lenovo',
    });
  }

  // Narrow to product section
  const secM = /PRODUCT AND SERVICE DETAILS|Product and\/or Service Selection/i.exec(fullText);
  if (!secM) return results;
  const after = fullText.slice(secM.index + secM[0].length);
  const endM  = /Grand Total|CONFIGURATION DETAILS|TERMS AND CONDITIONS/i.exec(after);
  const section = endM ? after.slice(0, endM.index) : after;

  // Tail pattern: <qty_integer><price1.xx><price2.xx><price3.xx> at end of line
  // Handles prices with commas (e.g. 2,626.30) and without
  const TAIL = /(\d+)(\d[\d,]*\.\d{2})(\d[\d,]*\.\d{2})(\d[\d,]*\.\d{2})$/;

  // Start-of-item: <1-2 digit line#><ALL_CAPS_DIGITS part code ≥8 chars>
  const ITEM_START = /^(\d{1,2})([A-Z0-9]{8,14})/;
  // Pure sub-reference code (to skip): all-caps-digits, no spaces, 5-14 chars
  const SUB_CODE = /^[A-Z0-9]{5,14}$/;

  const lines        = section.split('\n').map(l => l.trim()).filter(Boolean);
  let pendingPart    = null;
  let pendingDescs   = [];

  function flush(qty, price) {
    if (pendingPart && qty > 0 && price > 0) {
      addLine(pendingPart, pendingDescs.join(' ').trim(), qty, price);
    }
    pendingPart  = null;
    pendingDescs = [];
  }

  for (const line of lines) {
    if (/grand total/i.test(line)) break;
    if (isHeaderLine(line)) continue;

    const tailM = TAIL.exec(line);

    if (tailM) {
      let qty    = parseInt(tailM[1], 10);
      let price  = cleanPrice(tailM[2]);
      // Validate qty × price ≈ total_excl (tailM[3]).
      // If off, the regex absorbed the leading digit of price into qty — restore it.
      const totalExcl = cleanPrice(tailM[3]);
      if (qty > 0 && price > 0 && totalExcl > 0) {
        const expected = qty * price;
        const tol = Math.max(1, totalExcl * 0.02);
        if (Math.abs(expected - totalExcl) > tol) {
          // Try: move last digit of qty to front of price string
          const qtyStr   = tailM[1];
          const priceStr = tailM[2];
          const fixedQty   = parseInt(qtyStr.slice(0, -1) || '0', 10);
          const fixedPrice = cleanPrice(qtyStr.slice(-1) + priceStr);
          if (fixedQty > 0 && Math.abs(fixedQty * fixedPrice - totalExcl) < tol) {
            qty   = fixedQty;
            price = fixedPrice;
          }
        }
      }
      const prefix = line.slice(0, line.length - tailM[0].length).trim();

      const itemM = ITEM_START.exec(prefix);
      if (itemM) {
        // ── Single-line item: line# + partCode + description all on one line ──
        flush(0, 0);  // commit any previous pending (no prices = skip)
        const rawCode  = itemM[2];                    // greedy [A-Z0-9]{8,14}
        const afterCode = prefix.slice(itemM[0].length).trim(); // remaining text = description

        // Part code may have absorbed start of description (both are uppercase).
        // Heuristic: if rawCode > 11 chars, check if last chars form a word start
        // by trying 10-11 char split. Else use rawCode as-is.
        let partNum = rawCode;
        let desc    = afterCode;
        if (rawCode.length > 11) {
          // Try to split at 10 chars
          partNum = rawCode.slice(0, 10);
          desc    = (rawCode.slice(10) + ' ' + afterCode).trim();
        }
        addLine(partNum, desc, qty, price);

      } else if (prefix === '' && pendingPart) {
        // ── Prices-only line for a multi-line item ──
        flush(qty, price);

      } else if (pendingPart) {
        // Stray prices line — also check as a prices-only flush
        flush(qty, price);
      }
      continue;
    }

    // ── No price tail — may be start of multi-line item or description ──
    const itemStartM = ITEM_START.exec(line);
    if (itemStartM) {
      const rest = line.slice(itemStartM[0].length).trim();
      if (!rest || SUB_CODE.test(rest)) {
        // Pure item start: line# + partCode, description follows on next lines
        flush(0, 0);
        pendingPart  = itemStartM[2];
        pendingDescs = [];
      } else {
        // Has description inline but no prices yet (unusual; accumulate)
        flush(0, 0);
        pendingPart  = itemStartM[2];
        pendingDescs = rest ? [rest] : [];
      }
    } else if (pendingPart) {
      if (SUB_CODE.test(line)) {
        // Skip sub-reference codes (e.g. "21WQCT01" after part "21WQCT01WW")
      } else {
        pendingDescs.push(line);
      }
    }
  }

  return results;
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const body = JSON.parse(event.body || '{}');
    const b64  = body.file || '';
    if (!b64) return jsonResponse({ error: 'Missing file (base64)' }, 400);

    const buf    = Buffer.from(b64, 'base64');
    const parsed = await pdfParse(buf);
    const text   = parsed.text || '';

    if (!text.trim()) {
      return jsonResponse({ error: 'Could not extract text from PDF.' }, 422);
    }

    const lines = parseQuoteText(text);

    if (!lines.length) {
      const secM = /PRODUCT AND SERVICE DETAILS|Product and\/or Service Selection/i.exec(text);
      const sample = secM ? text.slice(secM.index, secM.index + 3000) : text.slice(0, 3000);
      return jsonResponse({
        error: 'No product lines found. Supported formats: Lenovo BRPAS quote and Special Bid.',
        _debug_text: sample,
      }, 422);
    }

    const fmt = /Product and\/or Service Selection/i.test(text) ? 'special_bid' : 'brpas';
    return jsonResponse({ success: true, format: fmt, lines });

  } catch (err) {
    return jsonResponse({ error: String(err.message || err) }, 500);
  }
};
