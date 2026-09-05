"""
Email delivery via Resend.

Sends the completed FlowSpace Blueprint PDF to the customer
and a notification copy to the admin inbox.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Optional, Tuple

import resend

from pdf_generator import plan_title, space_label

logger = logging.getLogger(__name__)

DEFAULT_FROM = "FlowSpace <blueprints@flowspace.solutions>"
DEFAULT_ADMIN = "hello@flowspace.solutions"


def _from_email() -> str:
    return (os.environ.get("RESEND_FROM_EMAIL") or DEFAULT_FROM).strip() or DEFAULT_FROM


def _admin_email() -> str:
    return (os.environ.get("ADMIN_EMAIL") or DEFAULT_ADMIN).strip() or DEFAULT_ADMIN


def _customer_html(customer_name: str, space_type: str) -> str:
    space = plan_title(space_type)
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your FlowSpace Blueprint is Ready</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">

          <!-- Header -->
          <tr>
            <td style="background:#1F3D2C;padding:28px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">FlowSpace</span>
                    <span style="font-size:11px;color:#cfe2d7;margin-left:10px;letter-spacing:0.05em;">Clear space. Create flow. Live better.</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:48px 40px 32px;">
              <h1 style="margin:0 0 8px;font-size:28px;font-weight:300;color:#1F3D2C;letter-spacing:-0.5px;">
                Your Blueprint is Ready, {customer_name}! 🎉
              </h1>
              <p style="margin:0 0 24px;font-size:16px;color:#475569;line-height:1.7;">
                Your personalized <strong>{space}</strong> is attached to this email.
                Inside you'll find your complete FlowSpace Blueprint™ — designed specifically
                around your space, your style, and your wellbeing.
              </p>

              <!-- What's Inside Box -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;border-radius:12px;border:1px solid #bbf7d0;margin-bottom:28px;">
                <tr>
                  <td style="padding:24px 28px;">
                    <p style="margin:0 0 14px;font-size:13px;font-weight:700;color:#1F3D2C;text-transform:uppercase;letter-spacing:0.1em;">
                      What's Inside Your Blueprint
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Organized visual of your actual space</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Zones &amp; functional layout plan</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Curated shopping list with prices</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Optional paint note (consider only if it helps)</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Step-by-step action plan</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0;font-size:14px;color:#374151;">✓ &nbsp; Design strategy for lasting calm</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 32px;font-size:15px;color:#475569;line-height:1.7;">
                An organized space isn't just about aesthetics — it's about reducing the mental
                load of daily life. Your Blueprint is designed to create a space that feels as
                good as it looks. Open the attached PDF to get started.
              </p>

              <!-- Divider -->
              <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 32px;">

              <p style="margin:0;font-size:14px;color:#64748b;line-height:1.6;">
                Warmly,<br>
                <strong style="color:#1F3D2C;">The FlowSpace Team</strong><br>
                <a href="https://flowspace.solutions" style="color:#10b981;text-decoration:none;">flowspace.solutions</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;">
              <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;line-height:1.6;">
                FlowSpace · Better spaces, better living.<br>
                Questions? Reply to this email anytime.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _admin_html(customer_name: str, customer_email: str, space_type: str, lead_id: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:#1F3D2C;">New FlowSpace Blueprint Delivered ✅</h2>
  <table style="border-collapse:collapse;width:100%;max-width:480px;">
    <tr><td style="padding:8px 0;font-weight:600;color:#475569;">Customer</td><td>{customer_name}</td></tr>
    <tr><td style="padding:8px 0;font-weight:600;color:#475569;">Email</td><td>{customer_email}</td></tr>
    <tr><td style="padding:8px 0;font-weight:600;color:#475569;">Space</td><td>{space_label(space_type)}</td></tr>
    <tr><td style="padding:8px 0;font-weight:600;color:#475569;">Lead ID</td><td><code>{lead_id}</code></td></tr>
  </table>
  <p style="margin-top:20px;color:#475569;">The Blueprint PDF has been sent to the customer automatically. You can view and edit the plan in the admin panel.</p>
</body>
</html>
"""


async def send_blueprint(
    *,
    customer_name: str,
    customer_email: str,
    space_type: str,
    lead_id: str,
    pdf_bytes: bytes,
) -> Tuple[bool, Optional[str]]:
    """
    Send the PDF Blueprint to the customer and notify admin.

    Returns (True, None) on customer-email success. Admin notify failures are
    logged but do not fail the customer send. Returns (False, reason) if the
    customer email was not sent (missing key, Resend error, etc.).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not configured — skipping email")
        return False, "RESEND_API_KEY is not configured on this server"

    if not (customer_email or "").strip():
        return False, "Customer email is missing"

    resend.api_key = api_key
    space = plan_title(space_type)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (customer_name or "customer"))
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    filename = f"FlowSpace_{space.replace(' ', '_')}_{safe_name}.pdf"
    sender = _from_email()
    attachment = {
        "filename": filename,
        "content": pdf_b64,
        "content_type": "application/pdf",
    }

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": sender,
                "to": [customer_email.strip()],
                "subject": f"Your FlowSpace {space} is Ready ✨",
                "html": _customer_html(customer_name, space_type),
                "attachments": [attachment],
            },
        )
        logger.info("Blueprint email sent to %s", customer_email)
    except Exception as e:
        logger.exception("Customer email delivery failed: %s", e)
        return False, f"Resend customer send failed: {e}"

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": sender,
                "to": [_admin_email()],
                "subject": f"[FlowSpace] Blueprint delivered — {customer_name} ({space})",
                "html": _admin_html(customer_name, customer_email, space_type, lead_id),
                "attachments": [attachment],
            },
        )
        logger.info("Admin notification sent")
    except Exception as e:
        logger.warning("Admin notification failed (customer already sent): %s", e)

    return True, None
