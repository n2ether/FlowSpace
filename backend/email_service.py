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
from typing import Optional, Tuple, List, Dict, Any

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


def _file_stem(title: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (title or "Blueprint"))
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "Blueprint"



def _first_name(customer_name: str) -> str:
    parts = str(customer_name or "").strip().split()
    return parts[0] if parts else "there"

def customer_email_html(
    customer_name: str,
    space_type: str,
    *,
    project_title: str = "",
    preview_src: str = "",
    guide_href: str = "",
    room_flow_src: str = "",
) -> str:
    """Customer email layout a final send uses.

    The Blueprint preview is the first block in the body, then the room-flow
    zone map when one is attached. The companion guide follows. No review
    codes, no package status. ``preview_src`` / ``room_flow_src`` are
    ``cid:`` references on a real send, or a browser-readable URL or data URI
    when rendering the same layout locally.
    """
    space = (project_title or plan_title(space_type)).strip() or plan_title(space_type)
    room_flow = ""
    if room_flow_src:
        room_flow = f"""
              <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#1F3D2C;">Room flow</p>
              <img src="{room_flow_src}" alt="{space} room flow map" width="560" style="width:100%;max-width:560px;height:auto;border-radius:16px;display:block;margin:0 0 12px;border:0;">
              <p style="margin:0 0 28px;font-size:16px;color:#475569;line-height:1.6;">The zone map — each zone has one job, with a clear path through the room.</p>
        """
    if preview_src:
        guide_link = ""
        if guide_href:
            guide_link = f"""
              <p style="margin:0 0 16px;">
                <a href="{guide_href}" style="color:#1F3D2C;font-size:16px;font-weight:700;">Open the companion guide</a>
              </p>
            """
        preview = f"""
              <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#1F3D2C;">Your Blueprint</p>
              <p style="margin:0 0 12px;font-size:20px;line-height:1.3;color:#1F3D2C;font-weight:600;">{space}</p>
              <img src="{preview_src}" alt="{space} Blueprint" width="560" style="width:100%;max-width:560px;height:auto;border-radius:16px;display:block;margin:0 0 12px;border:0;">
              <p style="margin:0 0 28px;font-size:16px;color:#475569;line-height:1.6;">The portrait plan — hero, what changed, and how the room flows. The same image is attached.</p>
              {room_flow}
              <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#1F3D2C;">Companion guide</p>
              {guide_link}
              <p style="margin:0 0 24px;font-size:16px;color:#475569;line-height:1.6;">Next, open the attached companion guide on your phone for safety essentials, climate comfort, why it helps, the shopping list, and each before and after.</p>
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
  <title>{REVIEW_STATUS}</title>
</head>
<body style="margin:0;padding:0;background:#f3eee6;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3eee6;padding:24px 0;">
    <tr>
      <td align="center" style="padding:0 16px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;">

          <tr>
            <td style="background:#1F3D2C;padding:24px 20px;">
              <span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">FlowSpace</span>
              <div style="font-size:13px;color:#cfe2d7;margin-top:4px;">Clear space. Create flow. Live better.</div>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 20px 24px;">
              <h1 style="margin:0 0 12px;font-size:28px;font-weight:500;color:#1F3D2C;letter-spacing:-0.4px;line-height:1.2;">
                {REVIEW_STATUS}
              </h1>
              <p style="margin:0 0 20px;font-size:16px;color:#475569;line-height:1.6;">
                Hi {_first_name(customer_name)}. Start with the portrait plan below.
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



def _png_attachment(filename: str, png: bytes, content_id: str = "") -> dict:
    att = {
        "filename": filename,
        "content": base64.b64encode(png).decode("utf-8"),
        "content_type": "image/png",
    }
    if content_id:
        att["content_id"] = content_id
    return att


def _extra_visual_attachments(
    visuals: Optional[List[Dict[str, Any]]],
    *,
    stem: str,
    safe_name: str,
    draft: bool = False,
) -> List[dict]:
    """Attach key client-facing visuals as full-size PNG files (in addition to body embeds)."""
    out: List[dict] = []
    prefix = f"FlowSpace_{stem}_DRAFT_" if draft else f"FlowSpace_{stem}_"
    for index, visual in enumerate(visuals or []):
        if not isinstance(visual, dict):
            continue
        raw = visual.get("bytes") or visual.get("png") or visual.get("content")
        if not raw:
            continue
        if isinstance(raw, str):
            try:
                raw = base64.b64decode(raw)
            except Exception:
                continue
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            continue
        label = "".join(
            ch if ch.isalnum() or ch in "-_" else "_"
            for ch in str(visual.get("label") or visual.get("name") or f"visual_{index + 1}")
        )
        out.append(_png_attachment(f"{prefix}{label}_{safe_name}.png", bytes(raw)))
    return out


def _zone_map_attachment(filename: str, png: bytes) -> dict:
    return {
        "filename": filename,
        "content": base64.b64encode(png).decode("utf-8"),
        "content_type": "image/png",
        "content_id": "room-flow",
    }


def _customer_html(
    customer_name: str,
    space_type: str,
    *,
    two_files: bool,
    project_title: str = "",
    preview_src: str = "cid:blueprint-preview",
    room_flow_src: str = "",
) -> str:
    return customer_email_html(
        customer_name,
        space_type,
        project_title=project_title,
        preview_src=preview_src if two_files else "",
        room_flow_src=room_flow_src if two_files else "",
    )


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
    project_title: str = "",
    zone_map_bytes: Optional[bytes] = None,
    extra_visuals: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Send the companion PDF and, when present, the image board and zone map.

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
    shown = (project_title or "").strip()
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (customer_name or "customer"))
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    stem = _file_stem(shown) if shown else space.replace(" ", "_")
    pdf_filename = f"FlowSpace_{stem}_Companion_{safe_name}.pdf"
    subject = (
        f"Your FlowSpace Blueprint is ready — {shown} ✨"
        if shown
        else f"Your FlowSpace {space} is Ready ✨"
    )
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
    if board_bytes and zone_map_bytes:
        attachments.append(_zone_map_attachment(f"FlowSpace_{stem}_Room_Flow_{safe_name}.png", zone_map_bytes))
    attachments.extend(
        _extra_visual_attachments(extra_visuals, stem=stem, safe_name=safe_name, draft=False)
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
                "subject": subject,
                "html": _customer_html(
                    customer_name,
                    space_type,
                    two_files=bool(board_bytes),
                    project_title=shown,
                    room_flow_src="cid:room-flow" if zone_map_bytes else "",
                ),
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


REVIEW_STATUS = "DRAFT. Review version. Not yet approved. Customer release held."


def _review_sheet_html(customer_name: str, lead_id: str, *, incomplete: bool) -> str:
    missing = " A required after is still missing, so customer release held." if incomplete else ""
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:#1F3D2C;">FlowSpace contact sheet — DRAFT</h2>
  <p>{REVIEW_STATUS}{missing}</p>
  <p>This is a review sheet for {customer_name} (lead <code>{lead_id}</code>).</p>
  <p>Each row is one source photo and the after edited from that same camera. It is not the customer image board and not the companion PDF.</p>
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
                "subject": f"FlowSpace DRAFT — review version, not yet approved ({customer_name or lead_id})",
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

def _draft_package_html(
    customer_name: str,
    lead_id: str,
    space_type: str,
    *,
    project_title: str = "",
    preview_src: str = "",
    room_flow_src: str = "",
) -> str:
    """Draft review uses the customer email layout, with a review-version banner.

    The banner is the only draft marker. The body under it is the layout a
    later customer send would use. This function does not release the package.
    """
    inner = customer_email_html(
        customer_name,
        space_type,
        project_title=project_title,
        preview_src=preview_src,
        room_flow_src=room_flow_src,
    )
    inner = inner.replace(
        f"Your Blueprint is ready, {customer_name}",
        REVIEW_STATUS,
    )
    inner = inner.replace("Your FlowSpace Blueprint is Ready", "FlowSpace DRAFT — review version")
    preview = _preview_url(lead_id)
    banner = f"""
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#1F3D2C;padding:16px 0;">
    <tr>
      <td align="center" style="padding:0 16px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
          <tr>
            <td style="color:#ffffff;font-family:Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;">
              <strong>{REVIEW_STATUS}</strong>
              <a href="{preview}" style="color:#cfe2d7;">Open the mobile preview</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
"""
    marker = '<body style="margin:0;padding:0;background:#f3eee6;font-family:\'Helvetica Neue\',Helvetica,Arial,sans-serif;">'
    if marker in inner:
        return inner.replace(marker, marker + banner, 1)
    return banner + inner


async def send_draft_package(
    *,
    to_email: str,
    customer_name: str,
    space_type: str,
    lead_id: str,
    pdf_bytes: bytes,
    board_bytes: Optional[bytes] = None,
    cc_emails: Optional[list] = None,
    project_title: str = "",
    zone_map_bytes: Optional[bytes] = None,
    extra_visuals: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[str]]:
    """Email DRAFT board, zone map, and companion PDF for review. Does not mark a package final."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not configured — skipping draft package email")
        return False, "RESEND_API_KEY is not configured on this server"
    recipient = (to_email or "").strip()
    if not recipient:
        return False, "Draft recipient is missing"

    resend.api_key = api_key
    space = plan_title(space_type)
    shown = (project_title or "").strip()
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (customer_name or "customer"))
    stem = _file_stem(shown) if shown else space.replace(" ", "_")
    attachments = []
    if board_bytes:
        attachments.append(
            {
                "filename": f"FlowSpace_{stem}_DRAFT_Blueprint_{safe_name}.png",
                "content": base64.b64encode(board_bytes).decode("utf-8"),
                "content_type": "image/png",
                "content_id": "blueprint-preview",
            }
        )
    if board_bytes and zone_map_bytes:
        attachments.append(_zone_map_attachment(f"FlowSpace_{stem}_DRAFT_Room_Flow_{safe_name}.png", zone_map_bytes))
    attachments.extend(
        _extra_visual_attachments(extra_visuals, stem=stem, safe_name=safe_name, draft=True)
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
        "subject": f"FlowSpace DRAFT — review version, not yet approved ({customer_name or lead_id})",
        "html": _draft_package_html(
            customer_name or "there",
            lead_id,
            space_type,
            project_title=(project_title or "").strip(),
            preview_src="cid:blueprint-preview" if board_bytes else "",
            room_flow_src="cid:room-flow" if board_bytes and zone_map_bytes else "",
        ),
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

