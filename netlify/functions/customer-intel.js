/**
 * Netlify Function: customer-intel
 * Calls GPT-4o, DeepSeek, and Claude in parallel using Node https module.
 * Required env vars:
 *   OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
 *   DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
 *   ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
 */

const https = require('https');
const http  = require('http');
const url   = require('url');

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

function buildPrompt(name) {
  return `You are a financial analyst helping assess lease financing risk for a B2B equipment leasing company (Lenovo Global Financial Services).

Analyse the company "${name}" and return ONLY a JSON object with these exact fields — no markdown, no explanation:
{
  "company_name": "official company name",
  "industry": "industry sector (e.g. Technology, Manufacturing, Healthcare, Retail, Finance, Government)",
  "industry_risk": "low or medium or high",
  "company_size": "small or mid-market or large or enterprise",
  "employees_estimate": "e.g. ~50,000",
  "revenue_estimate": "e.g. ~$5B USD annual revenue",
  "headquarters": "City, Country",
  "public_private": "public or private or government or unknown",
  "credit_outlook": "strong or good or moderate or weak or unknown",
  "gcr_recommendation": 5,
  "gcr_rationale": "1-2 sentence reason for the GCR score",
  "deal_size_recommendation": "0-100k or 100k-1M or 1M-2M or 2M-5M or 5M-10M or 10M-30M or 30M+",
  "suggested_term": 36,
  "pricing_notes": "any special considerations for pricing this customer (max 2 sentences)",
  "data_confidence": "high or medium or low"
}
GCR key: 1-4=low risk, 5=medium(default), 6=elevated, 7=high risk.
Return ONLY the JSON object, nothing else.`;
}

function parseJSON(text) {
  // 1. Try extracting content inside code fences  ```json ... ```
  const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) {
    try { return JSON.parse(fenceMatch[1].trim()); } catch(e) {}
  }

  // 2. Try the outermost { ... } block
  const objMatch = text.match(/\{[\s\S]*\}/);
  if (objMatch) {
    try { return JSON.parse(objMatch[0]); } catch(e) {
      throw new Error('JSON parse error: ' + e.message + ' — raw: ' + objMatch[0].slice(0, 120));
    }
  }

  // 3. Direct parse fallback
  return JSON.parse(text.trim());
}

// HTTP/HTTPS request using Node built-in modules
function httpRequest(endpoint, headers, body) {
  return new Promise((resolve, reject) => {
    const parsed = url.parse(endpoint);
    const isHttps = parsed.protocol === 'https:';
    const lib = isHttps ? https : http;

    const options = {
      hostname: parsed.hostname,
      port: parsed.port || (isHttps ? 443 : 80),
      path: parsed.path,
      method: 'POST',
      headers: { ...headers, 'Content-Length': Buffer.byteLength(body) },
      timeout: 8000,
      rejectUnauthorized: false,
    };

    const req = lib.request(options, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out')); });
    req.write(body);
    req.end();
  });
}

function buildEndpoint(base, isAnthropic) {
  if (!base) throw new Error('Base URL not configured');
  const b = base.replace(/\/$/, '');
  if (isAnthropic) {
    return b.endsWith('/v1/messages') ? b : b + '/v1/messages';
  }
  if (b.endsWith('/v1/chat/completions')) return b;
  if (b.endsWith('/v1')) return b + '/chat/completions';
  return b + '/v1/chat/completions';
}

async function callModel(prompt, apiKey, baseUrl, model, useAnthropicFormat) {
  if (!apiKey)   throw new Error('API key not configured');
  if (!baseUrl)  throw new Error('Base URL not configured');
  if (!model)    throw new Error('Model name not configured');

  const endpoint = buildEndpoint(baseUrl, useAnthropicFormat);
  const body = JSON.stringify({
    model,
    max_tokens: 1024,
    messages: [{ role: 'user', content: prompt }],
  });

  const headers = useAnthropicFormat
    ? { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' }
    : { 'authorization': `Bearer ${apiKey}`, 'content-type': 'application/json' };

  const { status, body: rawBody } = await httpRequest(endpoint, headers, body);

  let data;
  try { data = JSON.parse(rawBody); }
  catch(e) { throw new Error(`Invalid JSON response (HTTP ${status}): ${rawBody.slice(0, 200)}`); }

  if (data.error) {
    const msg = typeof data.error === 'string' ? data.error : (data.error.message || JSON.stringify(data.error));
    throw new Error(msg);
  }

  const text = useAnthropicFormat
    ? data.content?.[0]?.text?.trim()
    : data.choices?.[0]?.message?.content?.trim();

  if (!text) throw new Error(`Empty response (HTTP ${status})`);
  return parseJSON(text);
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const name = ((event.queryStringParameters) || {}).name || '';
    if (!name.trim()) return jsonResponse({ error: 'Missing ?name= parameter' }, 400);

    const prompt = buildPrompt(name.trim());

    const openaiKey    = process.env.OPENAI_API_KEY     || '';
    const openaiBase   = process.env.OPENAI_BASE_URL    || '';
    const openaiModel  = process.env.OPENAI_MODEL       || '';
    const geminiKey    = process.env.GEMINI_API_KEY     || '';
    const geminiBase   = process.env.GEMINI_BASE_URL    || '';
    const geminiModel  = process.env.GEMINI_MODEL       || '';
    const claudeKey    = process.env.ANTHROPIC_API_KEY  || '';
    const claudeBase   = process.env.ANTHROPIC_BASE_URL || '';
    const claudeModel  = process.env.ANTHROPIC_MODEL    || '';
    const claudeNative = claudeBase.includes('api.anthropic.com');

    const configs = [
      { label: 'GPT-4o',  fn: () => callModel(prompt, openaiKey,  openaiBase,  openaiModel,  false) },
      { label: 'Gemini',  fn: () => callModel(prompt, geminiKey,  geminiBase,  geminiModel,  false) },
      { label: 'Claude',  fn: () => callModel(prompt, claudeKey,  claudeBase,  claudeModel,  claudeNative) },
    ];

    const settled = await Promise.allSettled(configs.map(c => c.fn()));
    const responses = settled.map((r, i) => ({
      model: configs[i].label,
      data: r.status === 'fulfilled'
        ? r.value
        : { error: String(r.reason && r.reason.message ? r.reason.message : r.reason) },
    }));

    return jsonResponse({ responses });

  } catch (err) {
    return jsonResponse({ error: String(err && err.message ? err.message : err) }, 500);
  }
};
