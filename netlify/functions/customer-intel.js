/**
 * Netlify Function: customer-intel
 * Calls all 3 AI models in parallel and returns combined results.
 * Env vars required:
 *   OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
 *   GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL
 *   ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
 */

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

data_confidence criteria:
  "high"   = publicly listed company or government body with verifiable financials and well-known profile
  "medium" = known private company or regional firm with partial public information
  "low"    = unfamiliar name, likely startup, ambiguous/conflicting information, or name could match multiple entities

GCR (Global Credit Rating) key:
1–4 = Low-to-medium risk, zero credit uplift → large listed enterprises, investment-grade rated, government bodies
5   = Medium risk, +1% credit uplift → DEFAULT for mid-market / unrated companies
6   = Elevated risk, +2% credit uplift → smaller private companies, weaker financials, cyclical/volatile sectors
7   = HIGH risk, +8% credit uplift → startups, distressed entities, very high-risk industries

deal_size_recommendation = estimated typical annual IT equipment finance volume for this type of customer.
suggested_term = most common lease term in months (24, 36, 48, or 60).
Return ONLY the JSON object, nothing else.`;
}

function parseJSON(text) {
  const clean = text.replace(/^```[a-z]*\n?/m, '').replace(/\n?```$/m, '').trim();
  return JSON.parse(clean);
}

async function callOpenAIFormat(prompt, apiKey, baseUrl, model) {
  if (!apiKey) throw new Error('API key not configured');
  const base = (baseUrl || '').replace(/\/$/, '');
  // Build endpoint: if already ends with /v1/chat/completions use as-is,
  // else append /v1/chat/completions
  let url;
  if (base.endsWith('/v1/chat/completions')) {
    url = base;
  } else if (base.endsWith('/v1')) {
    url = base + '/chat/completions';
  } else {
    url = base + '/v1/chat/completions';
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      messages: [{ role: 'user', content: prompt }],
    }),
    signal: AbortSignal.timeout(35000),
  });

  const data = await res.json();
  if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
  const text = data.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error(`Empty response (HTTP ${res.status})`);
  return parseJSON(text);
}

async function callAnthropicNative(prompt, apiKey, baseUrl, model) {
  if (!apiKey) throw new Error('API key not configured');
  const base = (baseUrl || 'https://api.anthropic.com').replace(/\/$/, '');
  const url = base.endsWith('/v1/messages') ? base : base + '/v1/messages';

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      messages: [{ role: 'user', content: prompt }],
    }),
    signal: AbortSignal.timeout(35000),
  });

  const data = await res.json();
  if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
  const text = data.content?.[0]?.text?.trim();
  if (!text) throw new Error(`Empty response (HTTP ${res.status})`);
  return parseJSON(text);
}

exports.handler = async (event) => {
  // CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
      body: '',
    };
  }

  const params = new URLSearchParams(event.rawQuery || event.queryStringParameters ? new URLSearchParams(event.queryStringParameters).toString() : '');
  const name = (event.queryStringParameters?.name || '').trim();
  if (!name) {
    return {
      statusCode: 400,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Missing ?name= parameter' }),
    };
  }

  const prompt = buildPrompt(name);

  // Determine if Anthropic is going through a proxy (use OpenAI format) or native
  const anthropicBase = process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com';
  const anthropicIsNative = anthropicBase.includes('api.anthropic.com');

  const configs = [
    {
      label: 'GPT-4o',
      fn: () => callOpenAIFormat(
        prompt,
        process.env.OPENAI_API_KEY || '',
        process.env.OPENAI_BASE_URL || 'https://api.openai.com',
        process.env.OPENAI_MODEL || 'gpt-4o',
      ),
    },
    {
      label: 'Gemini',
      fn: () => callOpenAIFormat(
        prompt,
        process.env.GEMINI_API_KEY || '',
        process.env.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com/v1beta/openai',
        process.env.GEMINI_MODEL || 'gemini-2.0-flash',
      ),
    },
    {
      label: 'Claude',
      fn: () => anthropicIsNative
        ? callAnthropicNative(
            prompt,
            process.env.ANTHROPIC_API_KEY || '',
            anthropicBase,
            process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5',
          )
        : callOpenAIFormat(
            prompt,
            process.env.ANTHROPIC_API_KEY || '',
            anthropicBase,
            process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-6',
          ),
    },
  ];

  const settled = await Promise.allSettled(configs.map(c => c.fn()));
  const responses = settled.map((r, i) => ({
    model: configs[i].label,
    data: r.status === 'fulfilled'
      ? r.value
      : { error: String(r.reason?.message || r.reason || 'Unknown error') },
  }));

  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({ responses }),
  };
};
