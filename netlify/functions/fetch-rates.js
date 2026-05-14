/**
 * Netlify Function: fetch-rates
 * Server-side proxy for worldgovernmentbonds.com — bypasses browser CORS.
 * Returns 3Y and 5Y government bond yields for all LGFS countries.
 */

const https = require('https');

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
};

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36';

const COUNTRY_SLUGS = [
  ['AUSTRALIA',     'australia'],
  ['AUSTRIA',       'austria'],
  ['BELGIUM',       'belgium'],
  ['BRAZIL',        'brazil'],
  ['CANADA',        'canada'],
  ['CHILE',         'chile'],
  ['COLOMBIA',      'colombia'],
  ['DENMARK',       'denmark'],
  ['FINLAND',       'finland'],
  ['FRANCE',        'france'],
  ['GERMANY',       'germany'],
  ['GREECE',        'greece'],
  ['HONG KONG',     'hong-kong'],
  ['INDIA',         'india'],
  ['IRELAND',       'ireland'],
  ['ITALY',         'italy'],
  ['JAPAN',         'japan'],
  ['MALAYSIA',      'malaysia'],
  ['MEXICO',        'mexico'],
  ['NETHERLANDS',   'netherlands'],
  ['NEW ZEALAND',   'new-zealand'],
  ['NORWAY',        'norway'],
  ['PERU',          'peru'],
  ['PHILIPPINES',   'philippines'],
  ['PORTUGAL',      'portugal'],
  ['SAUDI ARABIA',  'saudi-arabia'],
  ['SINGAPORE',     'singapore'],
  ['SOUTH KOREA',   'south-korea'],
  ['SPAIN',         'spain'],
  ['SWEDEN',        'sweden'],
  ['SWITZERLAND',   'switzerland'],
  ['THAILAND',      'thailand'],
  ['UNITED KINGDOM','united-kingdom'],
  ['UNITED STATES', 'united-states'],
];

// ── HTTP helpers ───────────────────────────────────────────────
function httpsGet(url, extraHeaders = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const opts = {
      hostname:           parsed.hostname,
      path:               parsed.pathname + parsed.search,
      method:             'GET',
      rejectUnauthorized: false,
      headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9', ...extraHeaders },
    };
    const req = https.request(opts, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end',  () => resolve(Buffer.concat(chunks).toString('utf8')));
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => { req.destroy(); reject(new Error('GET timeout')); });
    req.end();
  });
}

function httpsPost(url, body, extraHeaders = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const parsed  = new URL(url);
    const bufBody = Buffer.from(body, 'utf8');
    const opts = {
      hostname:           parsed.hostname,
      path:               parsed.pathname + parsed.search,
      method:             'POST',
      rejectUnauthorized: false,
      headers: {
        'User-Agent':     UA,
        'Content-Type':   'application/json',
        'Content-Length': bufBody.length,
        ...extraHeaders,
      },
    };
    const req = https.request(opts, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end',  () => resolve(Buffer.concat(chunks).toString('utf8')));
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => { req.destroy(); reject(new Error('POST timeout')); });
    req.write(bufBody);
    req.end();
  });
}

// ── Parse 3Y / 5Y yields from mainTable HTML ──────────────────
function parseYieldTable(html) {
  const r = { r3: null, r5: null };
  const rows = html.match(/<tr[\s\S]*?<\/tr>/g) || [];
  for (const row of rows) {
    const text = row.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const m3 = text.match(/^3\s+years?\s+([-+]?\d[\d.]*)\s*%/i);
    const m5 = text.match(/^5\s+years?\s+([-+]?\d[\d.]*)\s*%/i);
    if (m3) r.r3 = Math.round(parseFloat(m3[1]) / 100 * 1e6) / 1e6;
    if (m5) r.r5 = Math.round(parseFloat(m5[1]) / 100 * 1e6) / 1e6;
  }
  return r;
}

// ── Fetch rates for one country ────────────────────────────────
async function fetchCountryRates(name, slug) {
  const pageUrl = `https://www.worldgovernmentbonds.com/country/${slug}/`;
  try {
    const html = await httpsGet(pageUrl);

    // Extract SYMBOL / PAESE / BANDIERA from page JS
    const m = html.match(/"SYMBOL"\s*:\s*"(\d+)"[\s\S]{0,400}?"PAESE"\s*:\s*"([^"]+)"[\s\S]{0,400}?"BANDIERA"\s*:\s*"([^"]+)"/);
    if (!m) return { r3: null, r5: null, error: 'symbol not found' };
    const [, symbol, paese, bandiera] = m;

    const payload = JSON.stringify({
      GLOBALVAR: {
        JS_VARIABLE: 'jsGlobalVars',
        FUNCTION:    'Country',
        DOMESTIC:    true,
        ENDPOINT:    'https://www.worldgovernmentbonds.com/wp-json/country/v1/historical',
        DATE_RIF:    '2099-12-31',
        OBJ:         null,
        COUNTRY1: {
          SYMBOL:          symbol,
          PAESE:           paese,
          PAESE_UPPERCASE: paese.toUpperCase(),
          BANDIERA:        bandiera,
          URL_PAGE:        slug,
        },
        COUNTRY2: null, OBJ1: null, OBJ2: null,
      },
    });

    const apiRaw = await httpsPost(
      'https://www.worldgovernmentbonds.com/wp-json/country/v1/main',
      payload,
      { Origin: 'https://www.worldgovernmentbonds.com', Referer: pageUrl },
    );
    const result = JSON.parse(apiRaw);
    if (!result.success) return { r3: null, r5: null, error: 'API returned failure' };

    return parseYieldTable(result.mainTable || '');
  } catch (e) {
    return { r3: null, r5: null, error: String(e.message || e).slice(0, 120) };
  }
}

// ── Handler ────────────────────────────────────────────────────
exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    // Fetch all countries in parallel (best-effort within timeout)
    const results = {};
    const errors  = {};

    await Promise.allSettled(
      COUNTRY_SLUGS.map(async ([name, slug]) => {
        const data = await fetchCountryRates(name, slug);
        results[name] = { r3: data.r3, r5: data.r5 };
        if (data.error) errors[name] = data.error;
      })
    );

    const body = JSON.stringify({
      success:   true,
      timestamp: Date.now() / 1000,
      rates:     results,
      errors,
    });

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
      body,
    };
  } catch (err) {
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
      body: JSON.stringify({ error: String(err.message || err) }),
    };
  }
};
