"""Transactional email (Resend) — delivers the generated PDF report."""
import asyncio
import logging
import os

import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
REPORT_BCC = os.environ.get("REPORT_BCC", "")


def _html(user_name: str, room_label: str) -> str:
    first = (user_name or "there").split(" ")[0]
    return f"""\
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;font-family:Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
      <tr><td style="padding:28px 32px 8px 32px;">
        <span style="font-size:20px;font-weight:700;color:#0f172a;">FlowSpace Solutions</span>
      </td></tr>
      <tr><td style="height:1px;background:#e2e8f0;"></td></tr>
      <tr><td style="padding:28px 32px;">
        <h1 style="margin:0 0 12px 0;font-size:24px;font-weight:300;color:#0f172a;">Your {room_label} plan is ready 🎉</h1>
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#475569;">
          Hi {first}, your personalized AI organization report for your <strong>{room_label}</strong> is attached as a PDF.
          It includes your before/after concept, a step-by-step plan, a shopping list, and estimated cost &amp; time.
        </p>
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#475569;">
          Open the attachment to view the full plan. You can also revisit it anytime from your FlowSpace dashboard.
        </p>
        <p style="margin:24px 0 0 0;font-size:13px;color:#94a3b8;">
          AI-generated room transformations are conceptual renderings and may not perfectly reflect actual
          dimensions, installation requirements, product availability, labor costs, or final results.
        </p>
      </td></tr>
      <tr><td style="padding:16px 32px 28px 32px;border-top:1px solid #e2e8f0;">
        <span style="font-size:13px;color:#94a3b8;">FlowSpace Solutions · flowspace.solutions</span>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _send(to_email: str, subject: str, html: str, pdf_bytes: bytes, filename: str):
    resend.api_key = RESEND_API_KEY
    params = {
        "from": f"FlowSpace Solutions <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "attachments": [{"filename": filename, "content": list(pdf_bytes)}],
    }
    if REPORT_BCC and REPORT_BCC.lower() != to_email.lower():
        params["bcc"] = [REPORT_BCC]
    return resend.Emails.send(params)


async def send_plan_email(to_email: str, user_name: str, room_label: str, pdf_bytes: bytes) -> bool:
    """Email the PDF report to the user (BCC the business inbox). Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping plan email")
        return False
    if not to_email:
        return False
    subject = f"Your FlowSpace organization plan — {room_label}"
    filename = f"FlowSpace_{room_label.replace(' ', '_')}.pdf"
    try:
        res = await asyncio.to_thread(_send, to_email, subject, _html(user_name, room_label), pdf_bytes, filename)
        logger.info(f"Plan email sent to {to_email} (id={res.get('id') if isinstance(res, dict) else res})")
        return True
    except Exception as e:
        logger.error(f"Plan email failed for {to_email}: {e}")
        return False



def _reset_html(name: str, link: str) -> str:
    first = (name or "there").split(" ")[0]
    return f"""\
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;font-family:Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
      <tr><td style="padding:28px 32px 8px 32px;">
        <span style="font-size:20px;font-weight:700;color:#0f172a;">FlowSpace Solutions</span>
      </td></tr>
      <tr><td style="height:1px;background:#e2e8f0;"></td></tr>
      <tr><td style="padding:28px 32px;">
        <h1 style="margin:0 0 12px 0;font-size:22px;font-weight:300;color:#0f172a;">Reset your password</h1>
        <p style="margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#475569;">
          Hi {first}, we received a request to reset your FlowSpace password. Click the button below to choose a new one. This link expires in 1 hour.
        </p>
        <a href="{link}" style="display:inline-block;background:#10b981;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 28px;border-radius:9999px;">Reset password</a>
        <p style="margin:20px 0 0 0;font-size:13px;color:#94a3b8;">If you didn't request this, you can safely ignore this email.</p>
      </td></tr>
      <tr><td style="padding:16px 32px 28px 32px;border-top:1px solid #e2e8f0;">
        <span style="font-size:13px;color:#94a3b8;">FlowSpace Solutions · flowspace.solutions</span>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _send_simple(to_email: str, subject: str, html: str):
    resend.api_key = RESEND_API_KEY
    return resend.Emails.send({
        "from": f"FlowSpace Solutions <{SENDER_EMAIL}>",
        "to": [to_email], "subject": subject, "html": html,
    })


async def send_password_reset_email(to_email: str, name: str, link: str) -> bool:
    if not RESEND_API_KEY or not to_email:
        logger.warning("RESEND_API_KEY not set — skipping reset email")
        return False
    try:
        await asyncio.to_thread(_send_simple, to_email, "Reset your FlowSpace password", _reset_html(name, link))
        return True
    except Exception as e:
        logger.error(f"Reset email failed for {to_email}: {e}")
        return False
