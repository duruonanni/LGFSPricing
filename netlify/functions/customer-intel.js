/**
 * Netlify Function: customer-intel
 * Calls GPT-4o, DeepSeek, and Claude in parallel.
 * Required env vars:
 *   OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
 *   DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
 *   ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
 */

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
  const clean = text.replace(/^```[\w]*\n?/m, '').replace(/\n?```$/m, '').trim();
  return JSON.parse(clean);
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
  if (!apiKey) throw new Error('API key not configured');
  if (!baseUrl) throw new Error('Base URL not configured');
  if (!model) throw new Error('Model name not configured');

  const endpoint = buildEndpoint(baseUrl, useAnthropicFormat);

  let headers, body;
  if (useAnthropicFormat) {
    headers = {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    };
    body = JSON.stringify({ model, max_tokens: 1024, messages: [{ role: 'user', content: prompt }] });
  } else {
    headers = {
      'authorization': `Bearer ${apiKey}`,
      'content-type': 'application/json',
    };
    body = JSON.stringify({ model, max_tokens: 1024, messages: [{ role: 'user', content: prompt }] });
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 28000);

  let res;
  try {
    res = await fetch(endpoint, { method: 'POST', headers, body, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json();

  if (data.error) {
    const msg = typeof data.error === 'string' ? data.error : (data.error.message || JSON.stringify(data.error));
    throw new Error(msg);
  }

  // Extract text: OpenAI format or Anthropic format
  const text = useAnthropicFormat
    ? data.content?.[0]?.text?.trim()
    : data.choices?.[0]?.message?.content?.trim();

  if (!text) throw new Error(`Empty response from API (HTTP ${res.status})`);
  return parseJSON(text);
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const name = ((event.queryStringParameters || {}).name || '').trim();
    if (!name) return jsonResponse({ error: 'Missing ?name= parameter' }, 400);

    const prompt = buildPrompt(name);

    const openaiKey    = process.env.OPENAI_API_KEY     || '';
    const openaiBase   = process.env.OPENAI_BASE_URL    || '';
    const openaiModel  = process.env.OPENAI_MODEL       || '';

    const deepseekKey  = process.env.DEEPSEEK_API_KEY   || '';
    const deepseekBase = process.env.DEEPSEEK_BASE_URL  || '';
    const deepseekModel= process.env.DEEPSEEK_MODEL     || '';

    const claudeKey    = process.env.ANTHROPIC_API_KEY  || '';
    const claudeBase   = process.env.ANTHROPIC_BASE_URL || '';
    const claudeModel  = process.env.ANTHROPIC_MODEL    || '';

    // Use native Anthropic format only if pointing at api.anthropic.com
    const claudeNative = claudeBase.includes('api.anthropic.com');

    const configs = [
      { label: 'GPT-4o',   fn: () => callModel(prompt, openaiKey,   openaiBase,   openaiModel,   false) },
      { label: 'DeepSeek', fn: () => callModel(prompt, deepseekKey, deepseekBase, deepseekModel, false) },
      { label: 'Claude',   fn: () => callModel(prompt, claudeKey,   claudeBase,   claudeModel,   claudeNative) },
    ];

    const settled = await Promise.allSettled(configs.map(c => c.fn()));
    const responses = settled.map((r, i) => ({
      model: configs[i].label,
      data: r.status === 'fulfilled'
        ? r.value
        : { error: String(r.reason?.message || r.reason || 'Unknown error') },
    }));

    return jsonResponse({ responses });

  } catch (err) {
    // Always return valid JSON even on unexpected errors
    return jsonResponse({ error: String(err.message || err) }, 500);
  }
};
