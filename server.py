#!/usr/bin/env python3
"""
LGFS Price Grid Calculator - Local Server
==========================================
Run:  python3 server.py
Then: browser opens automatically at http://localhost:8765

No installation required - uses only Python standard library.
"""

import http.server, threading, urllib.request, urllib.parse, json, re, ssl, os, webbrowser, time, sys, io, email
import http.client
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT = 8765
ACTUAL_PORT = PORT
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE  = os.path.join(SCRIPT_DIR, 'index.html')

# SSL context (skip verification for simplicity)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode    = ssl.CERT_NONE

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

# Country slug → display name mapping
COUNTRY_SLUGS = [
    ('AUSTRALIA',       'australia'),
    ('AUSTRIA',         'austria'),
    ('BELGIUM',         'belgium'),
    ('BRAZIL',          'brazil'),
    ('CANADA',          'canada'),
    ('CHILE',           'chile'),
    ('COLOMBIA',        'colombia'),
    ('DENMARK',         'denmark'),
    ('FINLAND',         'finland'),
    ('FRANCE',          'france'),
    ('GERMANY',         'germany'),
    ('GREECE',          'greece'),
    ('HONG KONG',       'hong-kong'),
    ('INDIA',           'india'),
    ('IRELAND',         'ireland'),
    ('ITALY',           'italy'),
    ('JAPAN',           'japan'),
    ('MALAYSIA',        'malaysia'),
    ('MEXICO',          'mexico'),
    ('NETHERLANDS',     'netherlands'),
    ('NEW ZEALAND',     'new-zealand'),
    ('NORWAY',          'norway'),
    ('PERU',            'peru'),
    ('PHILIPPINES',     'philippines'),
    ('PORTUGAL',        'portugal'),
    ('SAUDI ARABIA',    'saudi-arabia'),
    ('SINGAPORE',       'singapore'),
    ('SOUTH KOREA',     'south-korea'),
    ('SPAIN',           'spain'),
    ('SWEDEN',          'sweden'),
    ('SWITZERLAND',     'switzerland'),
    ('THAILAND',        'thailand'),
    ('UNITED KINGDOM',  'united-kingdom'),
    ('UNITED STATES',   'united-states'),
]


def fetch_country_rates(name, slug):
    """
    Fetch 3Y and 5Y government bond yields from worldgovernmentbonds.com.
    Returns dict: {'r3': float|None, 'r5': float|None}
    """
    page_url = f'https://www.worldgovernmentbonds.com/country/{slug}/'
    try:
        # Step 1: Load the country page to extract the internal SYMBOL id
        req = urllib.request.Request(page_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        m = re.search(r'"SYMBOL"\s*:\s*"(\d+)".*?"PAESE"\s*:\s*"([^"]+)".*?"BANDIERA"\s*:\s*"([^"]+)"',
                      html, re.DOTALL)
        if not m:
            return {'r3': None, 'r5': None, 'error': 'symbol not found'}
        symbol, paese, bandiera = m.group(1), m.group(2), m.group(3)

        # Step 2: POST to WP-JSON API (Origin must be worldgovernmentbonds.com)
        api_url = 'https://www.worldgovernmentbonds.com/wp-json/country/v1/main'
        payload = json.dumps({
            'GLOBALVAR': {
                'JS_VARIABLE':   'jsGlobalVars',
                'FUNCTION':      'Country',
                'DOMESTIC':      True,
                'ENDPOINT':      'https://www.worldgovernmentbonds.com/wp-json/country/v1/historical',
                'DATE_RIF':      '2099-12-31',
                'OBJ':           None,
                'COUNTRY1': {
                    'SYMBOL':          symbol,
                    'PAESE':           paese,
                    'PAESE_UPPERCASE': paese.upper(),
                    'BANDIERA':        bandiera,
                    'URL_PAGE':        slug,
                },
                'COUNTRY2': None, 'OBJ1': None, 'OBJ2': None,
            }
        }).encode()

        api_req = urllib.request.Request(api_url, data=payload, headers={
            'Content-Type': 'application/json',
            'Origin':       'https://www.worldgovernmentbonds.com',
            'Referer':      page_url,
            'User-Agent':   HEADERS['User-Agent'],
        }, method='POST')

        with urllib.request.urlopen(api_req, timeout=15, context=SSL_CTX) as resp:
            result = json.loads(resp.read().decode())

        if not result.get('success'):
            return {'r3': None, 'r5': None, 'error': 'API returned failure'}

        # Step 3: Parse mainTable HTML for 3Y / 5Y yields
        main_table = result.get('mainTable', '')
        yields = parse_yield_table(main_table)
        return yields

    except Exception as exc:
        return {'r3': None, 'r5': None, 'error': str(exc)[:120]}


def fetch_customer_intel(company_name, api_key_override=None,
                         base_url_override=None, model_override=None,
                         provider_override=None):
    """
    Call an LLM API to analyse a company and return pricing recommendations.
    Supports Anthropic and OpenAI API formats, plus custom proxy endpoints.
    Priority: UI settings > environment variables > defaults.
    provider: 'anthropic' (default) or 'openai'
    """
    provider = (provider_override or os.environ.get('LLM_PROVIDER', 'anthropic')).lower()
    is_openai = provider == 'openai'

    # Defaults per provider
    if is_openai:
        default_base  = 'https://api.openai.com'
        default_model = 'gpt-4o-mini'
        env_key       = os.environ.get('OPENAI_API_KEY', '')
    else:
        default_base  = 'https://api.anthropic.com'
        default_model = 'claude-haiku-4-5'
        env_key       = os.environ.get('ANTHROPIC_API_KEY', '')

    api_key  = api_key_override  or env_key
    model    = model_override    or os.environ.get('LLM_MODEL', default_model)
    base_url = base_url_override or default_base

    if not api_key:
        return {
            'error': 'API key not set',
            'hint': 'Enter your API key in the Countries &amp; Rates tab (🔑 AI Model Settings).'
        }

    # Parse base URL → host, port, endpoint path
    parsed   = urllib.parse.urlparse(base_url.rstrip('/'))
    host     = parsed.hostname or ('api.openai.com' if is_openai else 'api.anthropic.com')
    port     = parsed.port
    use_ssl  = parsed.scheme != 'http'
    path_pfx = parsed.path.rstrip('/')

    if is_openai:
        if path_pfx.endswith('/v1/chat/completions'):
            endpoint = path_pfx
        elif path_pfx.endswith('/v1'):
            endpoint = f'{path_pfx}/chat/completions'
        else:
            endpoint = f'{path_pfx}/v1/chat/completions'
    else:
        if path_pfx.endswith('/v1/messages'):
            endpoint = path_pfx
        else:
            endpoint = f'{path_pfx}/v1/messages'

    is_gemini = 'generativelanguage.googleapis.com' in base_url
    label = 'Gemini' if is_gemini else ('OpenAI' if is_openai else 'Anthropic')
    print(f'  → API: {label}  {"HTTPS" if use_ssl else "HTTP"} {host}{":"+str(port) if port else ""}{endpoint}  model: {model}')

    prompt = f"""You are a financial analyst helping assess lease financing risk for a B2B equipment leasing company (Lenovo Global Financial Services).

Analyse the company "{company_name}" and return ONLY a JSON object with these exact fields — no markdown, no explanation:
{{
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
}}

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
Return ONLY the JSON object, nothing else."""

    payload = json.dumps({
        'model': model,
        'max_tokens': 1024,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode()

    if is_openai:
        req_headers = {
            'authorization': f'Bearer {api_key}',
            'content-type':  'application/json',
        }
    else:
        req_headers = {
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
        }

    try:
        conn_cls = http.client.HTTPSConnection if use_ssl else http.client.HTTPConnection
        conn_args = {'timeout': 30}
        if port:
            conn = conn_cls(host, port, **conn_args)
        else:
            conn = conn_cls(host, **conn_args)

        conn.request('POST', endpoint, payload, req_headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())

        # Extract text from response (format differs by provider)
        text = None
        if is_openai:
            if 'choices' in data and data['choices']:
                text = data['choices'][0]['message']['content'].strip()
            elif 'error' in data:
                return {'error': data['error'].get('message', 'OpenAI API error')}
        else:
            if 'content' in data and data['content']:
                text = data['content'][0]['text'].strip()
            elif 'error' in data:
                return {'error': data['error'].get('message', 'API error')}

        if text is None:
            return {'error': f'Unexpected API response (HTTP {resp.status})'}

        # Strip markdown code fences if model wrapped the JSON
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text.strip())
        return json.loads(text)

    except json.JSONDecodeError as e:
        return {'error': f'JSON parse error: {str(e)[:100]}'}
    except Exception as e:
        err_str = str(e)
        if 'timed out' in err_str.lower() or 'timeout' in err_str.lower():
            is_gemini = 'generativelanguage.googleapis.com' in (base_url or '')
            if is_gemini:
                return {
                    'error': 'Connection to Gemini API timed out.',
                    'hint': 'generativelanguage.googleapis.com may not be reachable from your network. Try using a Custom Proxy instead.'
                }
            elif is_openai:
                return {
                    'error': 'Connection to OpenAI timed out.',
                    'hint': 'api.openai.com may not be reachable from your network. Try using a Custom Proxy with OpenAI format instead.'
                }
            else:
                return {
                    'error': 'Connection to Anthropic API timed out.',
                    'hint': 'api.anthropic.com may not be reachable from your network. Try using a Custom Proxy instead.'
                }
        return {'error': err_str[:200]}


def parse_quote_pdf(pdf_bytes):
    """
    Parse a Lenovo quotation PDF and extract asset lines.

    Supports two formats:
      • BRPAS format  – "PRODUCT AND SERVICE DETAILS" table
        columns: # | Part Number | Description | Qty | Unit price excl. GST | …
      • Special Bid   – "Product and/or Service Selection" table
        columns: ITEM No | Product Code | Description | … | Qty | … | Fixed Bid Price | …

    Returns list of dicts:
      {partNumber, description, qty, unitPrice, assetType, oem, skipped}
    """
    try:
        import pdfplumber
    except ImportError:
        return {'error': 'pdfplumber not installed. Run: pip install pdfplumber'}

    # ── Asset-type keyword classifier ────────────────────────────────
    # Checked in order; first match wins.
    # IMPORTANT: strong laptop/notebook keywords are checked FIRST so that
    # a description like "Monitor Notebook ThinkPad …" → Laptop, not Monitor.
    ASSET_RULES = [
        (['notebook', 'nb ', 'thinkpad', 'laptop'],              'Laptop / Desktop / AIO'),
        (['workstation', 'thinkstation'],                        'Workstation'),
        (['thinkvision', 'monitor', 'display'],                   'Monitors'),
        (['tablet', 'x12det', 'x1 tablet'],                      'Tablets'),
        (['iphone', 'ipad'],                                      'Apple iPhones'),
        (['motorola', 'moto '],                                   'Motorola Mobiles'),
        (['server', 'thinksystem', 'thinkagile'],                 'Servers'),
        (['storage', 'nas ', 'san '],                             'Storage'),
        (['switch', 'router', 'network', 'ethernet adapter'],     'Networking'),
        (['desktop', 'thinkcenter', 'tc ', ' aio'],              'Laptop / Desktop / AIO'),
    ]
    SERVICE_KEYWORDS = [
        'warranty', 'premier support', 'accidental damage',
        'cfs ', 'managed ', 'autopilot', 'install service',
        'mice_bo', 'case_bo', 'mouse', 'backpack', 'bag',
        'asset tag', 'electric test', 'handling charge',
        'bios settings', 'ready to provision', 'white glove',
    ]

    def classify(description):
        desc_l = description.lower()
        for kw in SERVICE_KEYWORDS:
            if kw in desc_l:
                return 'Peripherals / Soft Cost / Services'
        for keywords, atype in ASSET_RULES:
            if any(k in desc_l for k in keywords):
                return atype
        return 'Peripherals / Soft Cost / Services'

    def clean_price(raw):
        """Strip currency prefix and commas, return float."""
        if raw is None:
            return 0.0
        s = re.sub(r'[A-Z$€£¥,\s]', '', str(raw))
        try:
            return float(s)
        except ValueError:
            return 0.0

    def is_header_row(row):
        """True if this row looks like a column-header row."""
        if not row:
            return False
        joined = ' '.join(str(c or '') for c in row).lower()
        return any(h in joined for h in ['part number', 'product code', 'description', 'item no'])

    # ── Collect all tables across all pages ───────────────────────────
    all_tables = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for tbl in tables:
                    if tbl and len(tbl) >= 1:
                        all_tables.append(tbl)
    except Exception as e:
        return {'error': f'PDF read error: {str(e)[:200]}'}

    # ── Detect format and find the product table ──────────────────────
    # BRPAS format: header row has "Part Number" and "Description" and "Qty"
    # Special Bid : header row has "Product\nCode" / "Product Code" and "Qty"
    product_table = None
    fmt = None

    for tbl in all_tables:
        for row in tbl:
            if row is None:
                continue
            joined = ' '.join(str(c or '').replace('\n', ' ') for c in row).lower()
            if 'part number' in joined and 'description' in joined and 'qty' in joined:
                product_table = tbl
                fmt = 'brpas'
                break
            if ('product' in joined and 'code' in joined) and 'description' in joined and 'qty' in joined:
                product_table = tbl
                fmt = 'special_bid'
                break
        if product_table:
            break

    if not product_table:
        return {'error': 'Could not find product table in PDF. Supported formats: BRPAS quote and Lenovo Special Bid.'}

    # ── Determine column indices from header ──────────────────────────
    header_idx = 0
    for i, row in enumerate(product_table):
        if is_header_row(row):
            header_idx = i
            break

    header     = [str(c or '').replace('\n', ' ').lower().strip() for c in product_table[header_idx]]
    num_cols   = len(header)

    if fmt == 'brpas':
        idx_part = next((i for i,h in enumerate(header) if 'part' in h and 'number' in h), 1)
        idx_desc = next((i for i,h in enumerate(header) if 'description' in h), 2)
        idx_qty  = next((i for i,h in enumerate(header) if h.strip() == 'qty'), 3)
        idx_unit = next((i for i,h in enumerate(header) if 'unit price' in h or 'unit' in h), 4)
    else:  # special_bid
        idx_part = next((i for i,h in enumerate(header) if 'product' in h and 'code' in h), 1)
        idx_desc = next((i for i,h in enumerate(header) if 'description' in h), 2)
        idx_qty  = next((i for i,h in enumerate(header) if h.strip() == 'qty'), 5)
        idx_unit = next((i for i,h in enumerate(header) if 'fixed bid' in h or 'bid price' in h), None)
        if idx_unit is None:
            idx_unit = next((i for i,h in enumerate(header) if 'price' in h and i > idx_qty), 7)

    # ── Gather rows from tables (primary) ────────────────────────────
    # pdfplumber splits long product tables into one-row-per-table fragments.
    product_header_tbl_idx = all_tables.index(product_table)
    rows_to_scan = []
    for tbl in all_tables[product_header_tbl_idx:]:
        if rows_to_scan and len(tbl[0]) < num_cols - 2:
            break
        past_header = False
        for row in tbl:
            if is_header_row(row):
                past_header = True
                continue
            if not past_header and tbl is product_table:
                continue
            if past_header or tbl is not product_table:
                rows_to_scan.append(row)

    # ── Parse table rows ──────────────────────────────────────────────
    results   = []   # final list
    seen_keys = set()  # (part_number, qty, round(price,2))

    def add_result(part_num, description, qty, price):
        """Add a product line; skip duplicates and invalid rows."""
        if not part_num or qty <= 0 or price <= 0:
            return
        if 'grand total' in (description + part_num).lower():
            return
        key = (part_num, qty, round(price, 2))
        if key in seen_keys:
            return
        seen_keys.add(key)
        results.append({
            'partNumber':  part_num,
            'description': description or part_num,
            'qty':         qty,
            'unitPrice':   price,
            'assetType':   classify(description),
            'oem':         'Lenovo',
        })

    for row in rows_to_scan:
        if not row or all(c is None or str(c).strip() == '' for c in row):
            continue
        if is_header_row(row):
            continue

        def cell(idx, r=row):
            return str(r[idx] or '').replace('\n', ' ').strip() if idx < len(r) else ''

        part_num    = cell(idx_part)
        description = cell(idx_desc)
        qty_raw     = cell(idx_qty)
        price_raw   = cell(idx_unit)

        qty   = int(float(re.sub(r'[^\d.]', '', qty_raw) or '0')) if qty_raw else 0
        price = clean_price(price_raw)
        add_result(part_num, description, qty, price)

    # ── Text fallback: catch rows pdfplumber missed ───────────────────
    # Pattern per line: <line#>  <PARTCODE>  <qty>  <price>  …
    # Description text appears on the line(s) immediately BEFORE the data line.
    try:
        all_text = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                all_text.append(page.extract_text() or '')
        full_text = '\n'.join(all_text)

        sec_m = re.search(
            r'PRODUCT AND SERVICE DETAILS|Product and/or Service Selection',
            full_text, re.IGNORECASE)
        end_m = re.search(
            r'(?:CONFIGURATION DETAILS|Grand Total|TERMS AND CONDITIONS)',
            full_text[sec_m.end():] if sec_m else '', re.IGNORECASE)
        section = (full_text[sec_m.end(): sec_m.end() + end_m.start()]
                   if sec_m and end_m else full_text)

        # Pattern A – no inline description:
        #   <line#>  <PARTCODE>  <qty>  <price>  …
        pat_plain  = re.compile(
            r'^\s*\d{1,3}\s+([A-Z0-9]{6,14})\s+(\d+)\s+([A-Z]{0,3}[\d,]+\.\d{2})\b'
        )
        # Pattern B – inline description between part code and qty:
        #   <line#>  <PARTCODE>  <description text>  <qty>  <price>  …
        #   e.g.  "7 64A4MARXAU ThinkVision T24-40 23.8 inch Monitor 10 184.33 …"
        pat_inline = re.compile(
            r'^\s*\d{1,3}\s+([A-Z0-9]{6,14})\s+(.+?)\s+(\d+)\s+[A-Z]{0,3}([\d,]+\.\d{2})\s+[A-Z]{0,3}[\d,]+\.\d{2}'
        )

        text_lines   = section.splitlines()
        pending_desc = []   # description lines seen BEFORE current data line
        after_row    = False  # True right after we matched a data line

        for line in text_lines:
            m = pat_plain.match(line)
            if not m:
                m2 = pat_inline.match(line)
                if m2:
                    part, inline_desc, qty_s, price_s = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
                    qty   = int(qty_s)
                    price = clean_price(price_s)
                    key   = (part, qty, round(price, 2))
                    if key not in seen_keys:
                        # Prefer the inline description; prepend any clean pending_desc
                        before = ' '.join(d.strip() for d in pending_desc if d.strip())
                        desc   = (before + ' ' + inline_desc).strip() if before else inline_desc
                        add_result(part, desc, qty, price)
                    pending_desc = []
                    after_row    = True
                    continue
                # Not a data row
                s = line.strip()
                if after_row:
                    # Lines immediately after a data row are continuation desc for THAT row,
                    # not the next – discard them from pending_desc accumulation.
                    after_row = False
                    pending_desc = []
                elif s and not re.match(r'^[\d,.\s%()()\-AUD]+$', s) and not is_header_row([s]):
                    pending_desc.append(s)
                elif not s:
                    pending_desc = []
                continue

            # pat_plain matched
            part, qty_s, price_s = m.group(1), m.group(2), m.group(3)
            qty   = int(qty_s)
            price = clean_price(price_s)
            key   = (part, qty, round(price, 2))
            if key not in seen_keys:
                desc = re.sub(r'\s+', ' ', ' '.join(d.strip() for d in pending_desc if d.strip())).strip()
                add_result(part, desc, qty, price)
            pending_desc = []
            after_row    = True
    except Exception:
        pass  # best-effort; table results are kept

    if not results:
        return {'error': 'No valid product lines found in the detected table.'}

    return {'success': True, 'format': fmt, 'lines': results}


def parse_yield_table(html):
    """
    Parse the mainTable HTML fragment to extract 3-year and 5-year yields.
    Rows look like:  "3 years  0.012%  ..."
    """
    r3 = r5 = None
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        text = re.sub(r'<[^>]+>', ' ', row)
        text = re.sub(r'\s+', ' ', text).strip()
        # "3 years -0.073% ..." or "3 years 3.642% ..."
        m3 = re.match(r'^3\s+years?\s+([-+]?\d[\d.]*)\s*%', text, re.IGNORECASE)
        m5 = re.match(r'^5\s+years?\s+([-+]?\d[\d.]*)\s*%', text, re.IGNORECASE)
        if m3:
            r3 = round(float(m3.group(1)) / 100, 6)
        if m5:
            r5 = round(float(m5.group(1)) / 100, 6)
    return {'r3': r3, 'r5': r5}


# ─────────────────────────── HTTP Handler ────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._serve_file(HTML_FILE, 'text/html; charset=utf-8')
        elif self.path == '/api/rates':
            self._serve_rates()
        elif self.path == '/api/health':
            self._json({'status': 'ok', 'time': time.time()})
        elif self.path.startswith('/api/customer-intel'):
            self._serve_customer_intel()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        if self.path == '/api/parse-quote':
            self._serve_parse_quote()
        else:
            self.send_error(404, 'Not Found')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _serve_file(self, path, mime):
        try:
            with open(path, 'rb') as f:
                data = f.read()
            # Inject the actual server port so the page can reference it correctly
            if mime.startswith('text/html'):
                port_tag = f'<script>window.__SERVER_PORT__={ACTUAL_PORT};</script>'.encode()
                data = data.replace(b'</head>', port_tag + b'</head>', 1)
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, f'{os.path.basename(path)} not found')

    def _serve_rates(self):
        print('\n🔄  Fetching live bond rates…')
        start = time.time()
        results = {}
        errors  = {}

        with ThreadPoolExecutor(max_workers=6) as pool:
            future_map = {
                pool.submit(fetch_country_rates, name, slug): name
                for name, slug in COUNTRY_SLUGS
            }
            done = 0
            for fut in as_completed(future_map):
                name = future_map[fut]
                done += 1
                try:
                    data = fut.result()
                    results[name] = {'r3': data['r3'], 'r5': data['r5']}
                    ok = data['r3'] is not None and data['r5'] is not None
                    sym = '✓' if ok else '⚠'
                    r3s = f"{data['r3']*100:.3f}%" if data['r3'] is not None else 'n/a'
                    r5s = f"{data['r5']*100:.3f}%" if data['r5'] is not None else 'n/a'
                    print(f'  {sym} [{done:2d}/{len(COUNTRY_SLUGS)}] {name:<22} 3Y={r3s}  5Y={r5s}')
                    if 'error' in data:
                        errors[name] = data['error']
                except Exception as exc:
                    errors[name] = str(exc)[:80]
                    print(f'  ✗ [{done:2d}/{len(COUNTRY_SLUGS)}] {name:<22} ERROR: {errors[name]}')

        elapsed = time.time() - start
        print(f'\n✅  Done in {elapsed:.1f}s  ({len(results)} countries, {len(errors)} errors)\n')

        body = json.dumps({
            'success':   True,
            'timestamp': time.time(),
            'rates':     results,
            'errors':    errors,
        }).encode()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_customer_intel(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        name = (params.get('name') or [''])[0].strip()
        if not name:
            self._json({'error': 'Missing ?name= parameter'})
            return

        configs = [
            {
                'label':    'GPT-4o',
                'api_key':  os.environ.get('OPENAI_API_KEY', ''),
                'base_url': os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com'),
                'model':    os.environ.get('OPENAI_MODEL', 'gpt-4o'),
                'provider': 'openai',
            },
            {
                'label':    'Gemini',
                'api_key':  os.environ.get('GEMINI_API_KEY', ''),
                'base_url': os.environ.get('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai'),
                'model':    os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash'),
                'provider': 'openai',
            },
            {
                'label':    'Claude',
                'api_key':  os.environ.get('ANTHROPIC_API_KEY', ''),
                'base_url': os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com'),
                'model':    os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-6'),
                'provider': 'anthropic',
            },
        ]

        print(f'\n🔍  Customer intel: "{name}" — querying {len(configs)} models in parallel')

        def call(cfg):
            return fetch_customer_intel(
                name,
                api_key_override=cfg['api_key'] or None,
                base_url_override=cfg['base_url'],
                model_override=cfg['model'],
                provider_override=cfg['provider'],
            )

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(call, cfg) for cfg in configs]
            results = [f.result() for f in futures]

        responses = [{'model': configs[i]['label'], 'data': results[i]} for i in range(len(configs))]
        for r in responses:
            d = r['data']
            if 'error' in d:
                print(f'  ⚠  {r["model"]}: {d["error"]}')
            else:
                print(f'  ✓  {r["model"]}: GCR={d.get("gcr_recommendation")} '
                      f'{d.get("company_size")} confidence={d.get("data_confidence")}')

        self._json({'responses': responses})

    def _serve_parse_quote(self):
        """
        Receive a multipart/form-data POST with field 'file' = PDF bytes,
        parse the product table, return JSON asset lines.
        """
        content_type = self.headers.get('Content-Type', '')
        content_len  = int(self.headers.get('Content-Length', 0))
        raw_body     = self.rfile.read(content_len)

        # Extract boundary from Content-Type header
        boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
        if not boundary_match:
            self._json({'error': 'Expected multipart/form-data'})
            return

        boundary = boundary_match.group(1).encode()
        # Parse multipart: find the PDF part
        pdf_bytes = None
        parts = raw_body.split(b'--' + boundary)
        for part in parts:
            if b'Content-Disposition' not in part:
                continue
            # Split headers from body
            if b'\r\n\r\n' in part:
                header_block, body = part.split(b'\r\n\r\n', 1)
            elif b'\n\n' in part:
                header_block, body = part.split(b'\n\n', 1)
            else:
                continue
            # Strip trailing boundary markers
            body = body.rstrip(b'\r\n')
            if body.endswith(b'--'):
                body = body[:-2].rstrip(b'\r\n')
            header_text = header_block.decode('utf-8', errors='ignore')
            if 'name="file"' in header_text or 'filename=' in header_text:
                pdf_bytes = body
                break

        if not pdf_bytes:
            self._json({'error': 'No file field found in upload'})
            return

        print(f'\n📄  Parsing quote PDF ({len(pdf_bytes):,} bytes)…')
        result = parse_quote_pdf(pdf_bytes)
        if 'error' in result:
            print(f'  ⚠  {result["error"]}')
        else:
            print(f'  ✓  {len(result["lines"])} product lines extracted  (format: {result["format"]})')
        self._json(result)

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        pass  # suppress request logs


# ──────────────────────────── Entry Point ────────────────────────────

def find_free_port(start):
    import socket
    for port in range(start, start + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except OSError:
                continue
    return None


def main():
    if not os.path.exists(HTML_FILE):
        print(f'❌  index.html not found at: {HTML_FILE}')
        print('    Please make sure server.py is in the same folder as index.html')
        sys.exit(1)

    port = find_free_port(PORT)
    if port is None:
        print(f'❌  Could not find a free port near {PORT}. Please close other programs and try again.')
        sys.exit(1)

    global ACTUAL_PORT
    ACTUAL_PORT = port
    server = http.server.HTTPServer(('localhost', port), Handler)
    url    = f'http://localhost:{port}'

    print('═' * 55)
    print('  LGFS Price Grid Calculator')
    print('═' * 55)
    print(f'  Server: {url}')
    print(f'  Press Ctrl+C to stop\n')

    # Open browser after 1 second
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n\nServer stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
