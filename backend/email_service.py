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


def _preview_url(lead_id: str) -> str:
    base = (os.environ.get("PUBLIC_APP_URL") or "https://flowspace.solutions").rstrip("/")
    return f"{base}/admin/leads/{lead_id}/blueprint"


def _customer_html(customer_name: str, space_type: str, *, two_files: bool) -> str:
    """Final customer email. Blueprint preview first, then the guide. No internal language."""
    space = plan_title(space_type)
    if two_files:
        preview = """
              <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#1F3D2C;">1 · Your Blueprint</p>
              <img src="cid:blueprint-preview" alt="Your FlowSpace Blueprint" width="400" style="width:100%;max-width:400px;height:auto;border-radius:16px;display:block;margin:0 0 12px;border:0;">
              <p style="margin:0 0 20px;font-size:16px;color:#475569;line-height:1.6;">The portrait plan — hero, what changed, and how the room flows. The same image is attached.</p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
                <tr>
                  <td align="center" style="background:#1F3D2C;border-radius:999px;padding:14px 18px;">
                    <span style="color:#ffffff;font-size:16px;font-weight:700;">Open the companion guide</span>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#1F3D2C;">2 · Companion guide</p>
              <p style="margin:0 0 24px;font-size:16px;color:#475569;line-height:1.6;">The guide is the attached PDF. Read it on your phone for the steps, shopping list, safety, climate, and weekly reset.</p>
        """
    else:
        preview = f"""
              <p style="margin:0 0 24px;font-size:16px;color:#475569;line-height:1.7;">
                Your personalized <strong>{space}</strong> is attached.
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
                <tr>
                  <td align="center" style="background:#1F3D2C;border-radius:999px;padding:14px 18px;">
                    <span style="color:#ffffff;font-size:16px;font-weight:700;">Open your Blueprint</span>
                  </td>
                </tr>
              </table>
        """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your FlowSpace Blueprint is Ready</title>
</head>
<body style="margin:0;padding:0;background:#f3eee6;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3eee6;padding:24px 0;">
    <tr>
      <td align="center" style="padding:0 16px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;overflow:hidden;">

          <tr>
            <td style="background:#1F3D2C;padding:24px 20px;">
              <span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">FlowSpace</span>
              <div style="font-size:13px;color:#cfe2d7;margin-top:4px;">Clear space. Create flow. Live better.</div>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 20px 24px;">
              <h1 style="margin:0 0 12px;font-size:28px;font-weight:500;color:#1F3D2C;letter-spacing:-0.4px;line-height:1.2;">
                Your Blueprint is ready, {customer_name}
              </h1>
              <p style="margin:0 0 20px;font-size:16px;color:#475569;line-height:1.6;">
                Start with the Blueprint. The companion guide comes after it.
              </p>
              {preview}
              <p style="margin:0 0 20px;font-size:16px;color:#475569;line-height:1.6;">
                An organized space is about a lighter day, not just a prettier photo.
              </p>
              <p style="margin:0;font-size:16px;color:#64748b;line-height:1.6;">
                Warmly,<br>
                <strong style="color:#1F3D2C;">The FlowSpace Team</strong><br>
                <a href="https://flowspace.solutions" style="color:#1F3D2C;">flowspace.solutions</a>
              </p>
            </td>
          </tr>

          <tr>
            <td style="background:#f7f4ef;padding:16px 20px;border-top:1px solid #e7e1d6;">
              <p style="margin:0;font-size:13px;color:#6e655c;text-align:center;line-height:1.5;">
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
  <p style="margin-top:20px;color:#475569;">The image board and companion guide have been sent to the customer. You can view and edit the plan in the admin panel.</p>
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
    board_bytes: Optional[bytes] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Send the companion PDF and, when present, the image board.

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
    stem = space.replace(" ", "_")
    pdf_filename = f"FlowSpace_{stem}_Companion_{safe_name}.pdf"
    sender = _from_email()
    attachments = []
    if board_bytes:
        attachments.append(
            {
                "filename": f"FlowSpace_{stem}_Blueprint_{safe_name}.png",
                "content": base64.b64encode(board_bytes).decode("utf-8"),
                "content_type": "image/png",
                "content_id": "blueprint-preview",
            }
        )
    attachments.append(
        {
            "filename": pdf_filename,
            "content": pdf_b64,
            "content_type": "application/pdf",
        }
    )

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": sender,
                "to": [customer_email.strip()],
                "subject": f"Your FlowSpace {space} is Ready ✨",
                "html": _customer_html(customer_name, space_type, two_files=bool(board_bytes)),
                "attachments": attachments,
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
                "attachments": attachments,
            },
        )
        logger.info("Admin notification sent")
    except Exception as e:
        logger.warning("Admin notification failed (customer already sent): %s", e)

    return True, None


def _review_sheet_html(customer_name: str, lead_id: str, *, incomplete: bool) -> str:
    state = "incomplete" if incomplete else "ready for review"
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:#1F3D2C;">FlowSpace contact sheet — not final</h2>
  <p>This is a review sheet for {customer_name} (lead <code>{lead_id}</code>). It is {state}.</p>
  <p>Each row is one source photo and the after edited from that same camera. It is not the customer image board and not the companion PDF.</p>
  <p>Do not send the final package until the sheet is approved. If a row has no after, the package stays incomplete.</p>
</body>
</html>
"""


async def send_contact_sheet(
    *,
    to_email: str,
    customer_name: str,
    lead_id: str,
    png_bytes: bytes,
    incomplete: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Email the review contact sheet. Does not mark a package final."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not configured — skipping contact sheet email")
        return False, "RESEND_API_KEY is not configured on this server"
    recipient = (to_email or "").strip()
    if not recipient:
        return False, "Review recipient is missing"

    resend.api_key = api_key
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (customer_name or "customer"))
    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": _from_email(),
                "to": [recipient],
                "subject": f"FlowSpace review sheet — not final ({customer_name or lead_id})",
                "html": _review_sheet_html(customer_name or "the customer", lead_id, incomplete=incomplete),
                "attachments": [
                    {
                        "filename": f"FlowSpace_Contact_Sheet_{safe_name}.png",
                        "content": base64.b64encode(png_bytes).decode("utf-8"),
                        "content_type": "image/png",
                    }
                ],
            },
        )
        logger.info("Contact sheet sent to %s for lead %s (not final)", recipient, lead_id)
        return True, None
    except Exception as exc:
        logger.exception("Contact sheet email failed: %s", exc)
        return False, f"Resend contact sheet send failed: {exc}"

def _draft_package_html(customer_name: str, lead_id: str, space_type: str) -> str:
    space = plan_title(space_type)
    preview = _preview_url(lead_id)
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:#1F3D2C;">FlowSpace DRAFT portrait Blueprint + companion — not final</h2>
  <p>Hi {customer_name},</p>
  <p>Attached is the <strong>DRAFT</strong> portrait Blueprint and companion guide for lead <code>{lead_id}</code> ({space}).</p>
  <p><strong>This is for your review only.</strong> It is not the customer final package. Please reply with any notes before we send final.</p>
  <p>Mobile preview (review only, does not send final): <a href="{preview}">{preview}</a></p>
  <ul>
    <li>Portrait Blueprint — hero, what changed, room flow, palette, roadmap</li>
    <li>Companion guide — steps, shopping list, safety, climate, weekly reset, and per-source before/after pages</li>
  </ul>
  <p>Warmly,<br>The FlowSpace Team</p>
</body>
</html>
"""


async def send_draft_package(
    *,
    to_email: str,
    customer_name: str,
    space_type: str,
    lead_id: str,
    pdf_bytes: bytes,
    board_bytes: Optional[bytes] = None,
    cc_emails: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """Email DRAFT board + companion PDF for review. Does not mark a package final."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not configured — skipping draft package email")
        return False, "RESEND_API_KEY is not configured on this server"
    recipient = (to_email or "").strip()
    if not recipient:
        return False, "Draft recipient is missing"

    resend.api_key = api_key
    space = plan_title(space_type)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (customer_name or "customer"))
    stem = space.replace(" ", "_")
    attachments = []
    if board_bytes:
        attachments.append(
            {
                "filename": f"FlowSpace_{stem}_DRAFT_Blueprint_{safe_name}.png",
                "content": base64.b64encode(board_bytes).decode("utf-8"),
                "content_type": "image/png",
            }
        )
    attachments.append(
        {
            "filename": f"FlowSpace_{stem}_DRAFT_Companion_{safe_name}.pdf",
            "content": base64.b64encode(pdf_bytes).decode("utf-8"),
            "content_type": "application/pdf",
        }
    )
    payload = {
        "from": _from_email(),
        "to": [recipient],
        "subject": f"FlowSpace DRAFT — not final ({customer_name or lead_id})",
        "html": _draft_package_html(customer_name or "there", lead_id, space_type),
        "attachments": attachments,
    }
    cc = [e.strip() for e in (cc_emails or []) if (e or "").strip()]
    if cc:
        payload["cc"] = cc
    try:
        await asyncio.to_thread(resend.Emails.send, payload)
        logger.info("Draft package sent to %s for lead %s (not final)", recipient, lead_id)
        return True, None
    except Exception as exc:
        logger.exception("Draft package email failed: %s", exc)
        return False, f"Resend draft package send failed: {exc}"

