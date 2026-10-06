"""
Email delivery via Resend.

Sends the FlowSpace Design Plan board, the Room Flow map, and the Companion
Guide PDF to the customer, and a notification copy to the admin inbox. Copy
and colors come from ``design_plan_standards``.
"""
from __future__ import annotations

import asyncio
import base64
import html
import logging
import os
import re
from typing import Optional, Tuple, List, Dict, Any

import resend

from design_plan_standards import (
    BRAND_GREEN,
    BRAND_GREIGE,
    BRAND_OFF,
    BRAND_TINTS,
    COMPANION_NAME,
    DESIGN_PLAN_LABEL,
    DESIGN_PLAN_NAME,
    EMAIL_COMPANION_COPY,
    EMAIL_DESIGN_PLAN_COPY,
    EMAIL_ROOM_FLOW_COPY,
    FONT_STACK,
    REVIEW_STATUS,
    TAGLINE,
)
from image_orientation import upright_jpeg_bytes
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


def _first_name(customer_name: str) -> str:
    parts = str(customer_name or "").strip().split()
    return parts[0] if parts else "there"

BLUEPRINT_COPY = EMAIL_DESIGN_PLAN_COPY
ROOM_FLOW_COPY = EMAIL_ROOM_FLOW_COPY

_GREEN = BRAND_GREEN
_MUTED = BRAND_TINTS["muted"]
_LABEL = f"margin:0 0 8px;font-size:12px;font-weight:600;letter-spacing:0.2em;text-transform:uppercase;color:{BRAND_GREEN};"
_BODY = f"margin:0 0 12px;font-size:16px;color:{_MUTED};line-height:1.6;"


def customer_email_html(
    customer_name: str,
    space_type: str,
    *,
    project_title: str = "",
    preview_src: str = "",
    guide_href: str = "",
    room_flow_src: str = "",
    outline_note: str = "",
    story: str = "",
    released: bool = False,
) -> str:
    """Customer email layout a final send uses.

    The Design Plan preview is the first block in the body, then the Room Flow
    map as its own attachment when one is sent. The Companion Guide follows.
    The heading is the review status until the package is released. No review
    codes. ``preview_src`` / ``room_flow_src`` are ``cid:`` references on a
    real send, or a browser-readable URL or data URI when rendering locally.
    """
    space = (project_title or plan_title(space_type)).strip() or plan_title(space_type)
    story = html.escape(" ".join(str(story or "").split()))
    heading = html.escape(space) if released else REVIEW_STATUS
    story_block = (
        f'<p style="margin:0 0 16px;font-size:19px;color:{_GREEN};line-height:1.5;font-weight:300;">{story}</p>\n              '
        if story
        else ""
    )
    room_flow = ""
    if room_flow_src:
        outline = f" {outline_note.strip()}" if outline_note.strip() else ""
        room_flow = f"""
              <p style="{_LABEL}">Room Flow</p>
              <p style="{_BODY}">{ROOM_FLOW_COPY}</p>
              <img src="{room_flow_src}" alt="{space} Room Flow map" width="560" style="width:100%;max-width:560px;height:auto;border-radius:16px;display:block;margin:0 0 12px;border:0;">
              <p style="margin:0 0 28px;font-size:16px;color:{_MUTED};line-height:1.6;">Each zone has one job, with a clear path through the room.{outline}</p>
        """
    if preview_src:
        guide_link = ""
        if guide_href:
            guide_link = f"""
              <p style="margin:0 0 16px;">
                <a href="{guide_href}" style="color:{_GREEN};font-size:16px;font-weight:600;">Open the {COMPANION_NAME}</a>
              </p>
            """
        preview = f"""
              <p style="{_LABEL}">{DESIGN_PLAN_LABEL}</p>
              <p style="margin:0 0 12px;font-size:22px;line-height:1.25;color:{_GREEN};font-weight:600;">{space}</p>
              <p style="{_BODY}">{BLUEPRINT_COPY}</p>
              <img src="{preview_src}" alt="{space} {DESIGN_PLAN_NAME}" width="560" style="width:100%;max-width:560px;height:auto;border-radius:16px;display:block;margin:0 0 28px;border:0;">
              {room_flow}
              <p style="{_LABEL}">{COMPANION_NAME}</p>
              {guide_link}
              <p style="margin:0 0 24px;font-size:16px;color:{_MUTED};line-height:1.6;">{EMAIL_COMPANION_COPY}</p>
        """
    else:
        preview = f"""
              <p style="margin:0 0 24px;font-size:16px;color:{_MUTED};line-height:1.7;">
                Your personalized <strong>{space}</strong> is attached.
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
                <tr>
                  <td align="center" style="background:{_GREEN};border-radius:999px;padding:14px 18px;">
                    <span style="color:#ffffff;font-size:16px;font-weight:600;">Open your {DESIGN_PLAN_NAME}</span>
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
  <title>{heading}</title>
</head>
<body style="margin:0;padding:0;background:{BRAND_OFF};font-family:{FONT_STACK};">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND_OFF};padding:24px 0;">
    <tr>
      <td align="center" style="padding:0 16px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;">

          <tr>
            <td style="background:{_GREEN};padding:24px 20px;">
              <span style="font-size:22px;font-weight:500;color:#ffffff;letter-spacing:-0.3px;">FlowSpace</span>
              <div style="font-size:13px;color:{BRAND_TINTS['sage_light']};margin-top:4px;">{TAGLINE}</div>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 20px 24px;">
              <h1 style="margin:0 0 12px;font-size:26px;font-weight:600;color:{_GREEN};letter-spacing:-0.3px;line-height:1.2;">
                {heading}
              </h1>
              {story_block}<p style="margin:0 0 20px;font-size:16px;color:{_MUTED};line-height:1.6;">
                Hi {_first_name(customer_name)}. Start with your {DESIGN_PLAN_NAME} below.
              </p>
              {preview}
              <p style="margin:0 0 20px;font-size:16px;color:{_MUTED};line-height:1.6;">
                An organized space is about a lighter day, not just a prettier photo.
              </p>
              <p style="margin:0;font-size:16px;color:{_MUTED};line-height:1.6;">
                Warmly,<br>
                <strong style="color:{_GREEN};">The FlowSpace Team</strong><br>
                <a href="https://flowspace.solutions" style="color:{_GREEN};">flowspace.solutions</a>
              </p>
            </td>
          </tr>

          <tr>
            <td style="background:{BRAND_GREIGE};padding:16px 20px;">
              <p style="margin:0;font-size:13px;color:{_MUTED};text-align:center;line-height:1.5;">
                {TAGLINE}<br>
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



# Resend rejects a message over 40 MB (body plus base64 attachments). Leave headroom.
EMAIL_SIZE_BUDGET = 30_000_000

# Full resolution first; step down only when the whole message would not fit.
VIEW_JPEG_STEPS: Tuple[Tuple[Optional[int], int], ...] = (
    (None, 88),
    (2400, 86),
    (2000, 82),
    (1600, 78),
)


def attachment_slug(title: str) -> str:
    """``Nicholas's Nursery`` -> ``Nicholas-Nursery``. Never a lead id or a pipeline code."""
    text = re.sub(r"['’]s\b", "", title or "")
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "-".join(words) or "Design-Plan"


def display_filename(title: str, kind: str) -> str:
    """``Nicholas's Nursery`` + ``Design Plan`` -> ``Nicholas's Nursery — Design Plan.png``.

    Apostrophes and the em dash stay (Resend encodes non-ASCII filenames);
    only characters no filesystem accepts are removed.
    """
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title or "")
    text = re.sub(r"\s+", " ", text).strip() or "FlowSpace"
    return f"{text} — {kind}.png"


def _attachment(filename: str, data: bytes, content_type: str, content_id: str = "") -> dict:
    att = {
        "filename": filename,
        "content": base64.b64encode(data).decode("utf-8"),
        "content_type": content_type,
    }
    if content_id:
        att["content_id"] = content_id
    return att


def _view_sources(visuals: Optional[List[Dict[str, Any]]]) -> List[Tuple[str, bytes]]:
    out: List[Tuple[str, bytes]] = []
    for index, visual in enumerate(visuals or []):
        if not isinstance(visual, dict):
            continue
        raw = visual.get("bytes") or visual.get("png") or visual.get("content")
        if isinstance(raw, str):
            try:
                raw = base64.b64decode(raw)
            except Exception:
                continue
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            continue
        label = "-".join(re.findall(r"[A-Za-z0-9]+", str(visual.get("label") or ""))) or f"View-{index + 1}"
        out.append((label, bytes(raw)))
    return out


def encoded_message_size(html: str, attachments: List[dict]) -> int:
    """Bytes Resend counts: the HTML body plus each base64 attachment."""
    return len((html or "").encode("utf-8")) + sum(len(a.get("content") or "") for a in attachments)


def package_attachments(
    *,
    title: str,
    html: str,
    pdf_bytes: bytes,
    board_bytes: Optional[bytes] = None,
    zone_map_bytes: Optional[bytes] = None,
    extra_visuals: Optional[List[Dict[str, Any]]] = None,
    draft: bool = False,
    budget: Optional[int] = None,
) -> List[dict]:
    """Board and zone map (PNG, full size), view photos (JPEG), then the companion PDF.

    The board and zone map go out twice: once inline (``content_id``) so the
    body shows them, and once as a plain attachment so mobile Gmail and Apple
    Mail list a downloadable tile. Mail clients do not list inline parts.

    View photos are the only part that bends to the size budget: quality and
    long edge step down, and as a last resort they are left out (they are
    still in the email body and the PDF). Size never fails a send.
    """
    budget = EMAIL_SIZE_BUDGET if budget is None else budget
    slug = attachment_slug(title)
    suffix = "-DRAFT" if draft else ""
    inline: List[dict] = []
    files: List[dict] = []
    if board_bytes:
        pngs = [(DESIGN_PLAN_NAME, board_bytes, "blueprint-preview")]
        if zone_map_bytes:
            pngs.append(("Room Flow", zone_map_bytes, "room-flow"))
        for kind, data, cid in pngs:
            name = display_filename(title, kind)
            inline.append(_attachment(name, data, "image/png", cid))
            files.append(_attachment(name, data, "image/png"))
    head = inline + files
    pdf = _attachment(f"{slug}-Companion{suffix}.pdf", pdf_bytes, "application/pdf")
    base = head + [pdf]
    sources = _view_sources(extra_visuals)
    if not sources:
        return base

    size = encoded_message_size(html, base)
    for step, (max_edge, quality) in enumerate(VIEW_JPEG_STEPS):
        views = []
        for label, raw in sources:
            jpeg = upright_jpeg_bytes(raw, quality=quality, max_edge=max_edge)
            if jpeg:
                views.append(_attachment(f"{label}.jpg", jpeg, "image/jpeg"))
        attachments = head + views + [pdf]
        size = encoded_message_size(html, attachments)
        if size <= budget:
            if step:
                logger.warning(
                    "Email size budget: view photos stepped down to long edge %s px, JPEG quality %s (%.1f MB encoded)",
                    max_edge,
                    quality,
                    size / 1e6,
                )
            return attachments

    size = encoded_message_size(html, base)
    logger.warning(
        "Email size budget: dropped %d view photo attachments (%s); they stay in the body and the PDF (%.1f MB encoded)",
        len(sources),
        ", ".join(f"{label}.jpg" for label, _raw in sources),
        size / 1e6,
    )
    if size > budget:
        logger.error("Email still over the %.0f MB budget at %.1f MB; sending anyway", budget / 1e6, size / 1e6)
    return base


def _customer_html(
    customer_name: str,
    space_type: str,
    *,
    two_files: bool,
    project_title: str = "",
    preview_src: str = "cid:blueprint-preview",
    room_flow_src: str = "",
    outline_note: str = "",
    story: str = "",
    released: bool = False,
) -> str:
    return customer_email_html(
        customer_name,
        space_type,
        project_title=project_title,
        preview_src=preview_src if two_files else "",
        room_flow_src=room_flow_src if two_files else "",
        outline_note=outline_note,
        story=story,
        released=released,
    )


def email_body_html(
    *,
    customer_name: str,
    space_type: str,
    project_title: str = "",
    outline_note: str = "",
    story: str = "",
    draft: bool = False,
    lead_id: str = "",
    preview_src: str = "",
    room_flow_src: str = "",
    released: bool = False,
) -> str:
    """The exact HTML a send uses. The preview endpoint passes data URIs where a send passes ``cid:``.

    A draft is always a review version. A customer layout keeps the review heading
    until ``released`` (``design_plan_standards.is_released``).
    """
    title = (project_title or "").strip()
    room_flow_src = room_flow_src if preview_src else ""
    if draft:
        return _draft_package_html(
            customer_name or "there",
            lead_id,
            space_type,
            project_title=title,
            preview_src=preview_src,
            room_flow_src=room_flow_src,
            outline_note=outline_note,
            story=story,
        )
    return _customer_html(
        customer_name or "there",
        space_type,
        two_files=bool(preview_src),
        project_title=title,
        preview_src=preview_src,
        room_flow_src=room_flow_src,
        outline_note=outline_note,
        story=story,
        released=released,
    )


def _cid_sources(board_bytes: Optional[bytes], zone_map_bytes: Optional[bytes]) -> Dict[str, str]:
    return {
        "preview_src": "cid:blueprint-preview" if board_bytes else "",
        "room_flow_src": "cid:room-flow" if board_bytes and zone_map_bytes else "",
    }


def _admin_html(customer_name: str, customer_email: str, space_type: str, lead_id: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:{BRAND_GREEN};">New FlowSpace {DESIGN_PLAN_NAME} Delivered ✅</h2>
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
    outline_note: str = "",
    story: str = "",
    released: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Send the companion PDF and, when present, the Design Plan board and zone map.

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
    subject = f"Your FlowSpace {DESIGN_PLAN_NAME} — {shown}" if shown else f"Your FlowSpace {space}"
    sender = _from_email()
    html = email_body_html(
        customer_name=customer_name,
        space_type=space_type,
        project_title=shown,
        outline_note=outline_note,
        story=story,
        released=released,
        **_cid_sources(board_bytes, zone_map_bytes),
    )
    attachments = await asyncio.to_thread(
        package_attachments,
        title=shown or space,
        html=html,
        pdf_bytes=pdf_bytes,
        board_bytes=board_bytes,
        zone_map_bytes=zone_map_bytes,
        extra_visuals=extra_visuals,
    )

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": sender,
                "to": [customer_email.strip()],
                "subject": subject,
                "html": html,
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
                "subject": f"[FlowSpace] {DESIGN_PLAN_NAME} delivered — {customer_name} ({space})",
                "html": _admin_html(customer_name, customer_email, space_type, lead_id),
                "attachments": attachments,
            },
        )
        logger.info("Admin notification sent")
    except Exception as e:
        logger.warning("Admin notification failed (customer already sent): %s", e)

    return True, None


def _review_sheet_html(customer_name: str, lead_id: str, *, incomplete: bool) -> str:
    missing = " A required after is still missing, so customer release held." if incomplete else ""
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Helvetica,Arial,sans-serif;color:#1f2937;padding:20px;">
  <h2 style="color:{BRAND_GREEN};">FlowSpace contact sheet — DRAFT</h2>
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
    outline_note: str = "",
    story: str = "",
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
        outline_note=outline_note,
        story=story,
        released=False,
    )
    preview = _preview_url(lead_id)
    banner = f"""
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND_GREEN};padding:16px 0;">
    <tr>
      <td align="center" style="padding:0 16px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
          <tr>
            <td style="color:#ffffff;font-family:{FONT_STACK};font-size:14px;line-height:1.5;">
              <strong>{REVIEW_STATUS}</strong>
              <a href="{preview}" style="color:{BRAND_TINTS['sage_light']};">Open the mobile preview</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
"""
    marker = re.search(r"<body[^>]*>", inner)
    if marker:
        return inner[: marker.end()] + banner + inner[marker.end() :]
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
    outline_note: str = "",
    story: str = "",
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
    html = email_body_html(
        customer_name=customer_name,
        space_type=space_type,
        project_title=shown,
        outline_note=outline_note,
        story=story,
        draft=True,
        lead_id=lead_id,
        **_cid_sources(board_bytes, zone_map_bytes),
    )
    attachments = await asyncio.to_thread(
        package_attachments,
        title=shown or space,
        html=html,
        pdf_bytes=pdf_bytes,
        board_bytes=board_bytes,
        zone_map_bytes=zone_map_bytes,
        extra_visuals=extra_visuals,
        draft=True,
    )
    payload = {
        "from": _from_email(),
        "to": [recipient],
        "subject": f"FlowSpace DRAFT — review version, not yet approved ({customer_name or shown or space})",
        "html": html,
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

