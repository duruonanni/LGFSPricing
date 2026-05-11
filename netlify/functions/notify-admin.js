/**
 * Netlify Function: notify-admin
 * Sends an email to the admin when a new user registers.
 * Required env vars: RESEND_API_KEY, ADMIN_EMAIL, FROM_EMAIL
 */

const https = require('https');

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
};

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const { name, email } = JSON.parse(event.body || '{}');
    if (!name || !email) {
      return { statusCode: 400, headers: CORS_HEADERS, body: JSON.stringify({ error: 'Missing name or email' }) };
    }

    const resendKey  = process.env.RESEND_API_KEY  || '';
    const adminEmail = process.env.ADMIN_EMAIL      || '';
    const fromEmail  = process.env.FROM_EMAIL       || 'onboarding@resend.dev';

    // If not configured, silently skip (don't break signup flow)
    if (!resendKey || !adminEmail) {
      console.log('notify-admin: RESEND_API_KEY or ADMIN_EMAIL not set — skipping');
      return { statusCode: 200, headers: CORS_HEADERS, body: JSON.stringify({ ok: true, skipped: true }) };
    }

    const html = `
      <div style="font-family:Arial,sans-serif;max-width:520px;color:#1a202c">
        <div style="background:#1e3a8a;padding:20px 24px;border-radius:8px 8px 0 0">
          <h2 style="color:#fff;margin:0;font-size:18px">🔔 New User Registration</h2>
          <p style="color:#bfdbfe;margin:4px 0 0;font-size:13px">LGFS Price Grid Calculator</p>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
          <p style="margin:0 0 16px">A new user has registered and is awaiting role assignment:</p>
          <table style="border-collapse:collapse;width:100%;font-size:14px">
            <tr style="background:#fff">
              <td style="padding:10px 12px;border:1px solid #e2e8f0;font-weight:600;width:80px">Name</td>
              <td style="padding:10px 12px;border:1px solid #e2e8f0">${name}</td>
            </tr>
            <tr style="background:#f1f5f9">
              <td style="padding:10px 12px;border:1px solid #e2e8f0;font-weight:600">Email</td>
              <td style="padding:10px 12px;border:1px solid #e2e8f0">${email}</td>
            </tr>
          </table>
          <div style="margin-top:20px">
            <a href="https://lgfspricing.netlify.app"
               style="background:#1e3a8a;color:#fff;padding:10px 22px;text-decoration:none;border-radius:6px;font-size:14px;font-weight:600">
              Open Admin Panel →
            </a>
          </div>
          <p style="color:#6b7280;font-size:12px;margin-top:20px">
            Log in as Admin and go to the ⚙️ Admin tab to assign a role.
          </p>
        </div>
      </div>`;

    const payload = JSON.stringify({
      from: fromEmail,
      to:   [adminEmail],
      subject: `[LGFS] New registration: ${name} (${email})`,
      html,
    });

    await new Promise((resolve, reject) => {
      const req = https.request({
        hostname: 'api.resend.com',
        path:     '/emails',
        method:   'POST',
        headers: {
          'Authorization':  `Bearer ${resendKey}`,
          'Content-Type':   'application/json',
          'Content-Length': Buffer.byteLength(payload),
        },
        timeout: 10000,
      }, (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve();
          else reject(new Error(`Resend ${res.statusCode}: ${data.slice(0, 200)}`));
        });
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('Resend request timed out')); });
      req.write(payload);
      req.end();
    });

    return { statusCode: 200, headers: CORS_HEADERS, body: JSON.stringify({ ok: true }) };

  } catch (e) {
    // Log but don't fail — signup should succeed regardless of email status
    console.error('notify-admin error:', e.message);
    return { statusCode: 200, headers: CORS_HEADERS, body: JSON.stringify({ ok: true, warning: e.message }) };
  }
};
