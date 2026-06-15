"""Renders the FlowSpace Design Plan PDF using WeasyPrint.
Portrait Letter, multi-page, readable fonts. Page 1 = design plan summary.
Page 2 = customer's AI-generated organized photos. Subsequent pages flow naturally.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)

LOGO_URL = (
    "https://customer-assets.emergentagent.com/job_organize-design/artifacts/"
    "rb6cf6gu_FlowSpace%20Logo.png"
)

CSS_STYLE = """
@page {
  size: Letter portrait;
  margin: 0.5in 0.55in 0.55in 0.55in;
  @bottom-right {
    content: "Page " counter(page) " of " counter(pages);
    font-family: "Helvetica", "Arial", sans-serif;
    font-size: 9px;
    color: #94a3b8;
  }
  @bottom-left {
    content: "FlowSpace.Solutions";
    font-family: "Helvetica", "Arial", sans-serif;
    font-size: 9px;
    color: #94a3b8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: "Helvetica", "Arial", sans-serif;
  color: #1f2937;
  background: #ffffff;
  font-size: 12px;
  line-height: 1.5;
}
.h1 { font-size: 28px; font-weight: 800; letter-spacing: 0.04em; color: #0f172a; margin: 0; }
.h2 { font-size: 13px; font-weight: 700; letter-spacing: 0.18em; color: #0f172a; }
.tagline { font-size: 10px; color: #4b5563; letter-spacing: 0.02em; margin-top: 4px; }

.page-break { page-break-before: always; }
.avoid-break { page-break-inside: avoid; }

/* ===== TOP BAR ===== */
.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}
.brand img { width: 130px; height: auto; display: block; }
.title-wrap { flex: 1; text-align: center; padding-top: 4px; }
.tags {
  font-size: 12px; font-weight: 700; letter-spacing: 0.16em;
  color: #1f2937; margin-top: 6px;
}
.tags .dot { color: #b6927a; margin: 0 8px; }
.tag-line {
  width: 60%; margin: 8px auto 0;
  height: 1px; background: linear-gradient(to right, transparent, #c7d2c5, transparent);
}
.summary { font-size: 12.5px; color: #374151; margin-top: 8px; font-style: italic; }

.designed-for {
  background: #4f6b58; color: #fff;
  border-radius: 12px; padding: 14px 16px;
  display: flex; gap: 10px; align-items: flex-start;
  margin-top: 14px;
}
.designed-for .leaf {
  width: 24px; height: 24px; border-radius: 50%; background: rgba(255,255,255,.15);
  display: inline-block; flex-shrink: 0; padding: 4px;
}
.designed-for h3 { font-size: 11px; font-weight: 800; letter-spacing: 0.16em; margin: 0; }
.designed-for p { margin: 4px 0 0; font-size: 11px; line-height: 1.45; opacity: 0.95; }

/* ===== MAIN IMAGE + ROOM NEEDS ===== */
.main-grid {
  display: flex; gap: 14px;
  margin-bottom: 18px;
}
.main-image-wrap {
  flex: 1.6;
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: #f3f4f6;
  height: 240px;
}
.main-image-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.image-label {
  position: absolute; top: 10px; left: 10px;
  background: #4f6b58; color: white;
  border-radius: 999px; padding: 5px 12px;
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.14em;
}
.right-col { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.needs h3 { font-size: 12.5px; font-weight: 800; letter-spacing: 0.16em; color: #0f172a; margin: 0 0 8px 0; }
.need-row { display: flex; gap: 9px; align-items: flex-start; padding: 3px 0; }
.need-icon {
  width: 26px; height: 26px; border-radius: 50%;
  background: #cfd9c8; color: #3a5a40; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px;
}
.need-icon.alt-1 { background: #d9e2d3; }
.need-icon.alt-2 { background: #f1d4cf; color: #8a4d44; }
.need-icon.alt-3 { background: #e5e9d8; }
.need-icon.alt-4 { background: #cfd9c8; }
.need-icon.alt-5 { background: #efe6c8; color: #826a2f; }
.need-title { font-size: 11.5px; font-weight: 700; color: #0f172a; line-height: 1.3; }
.need-body { font-size: 11px; color: #4b5563; line-height: 1.35; }

/* ===== SECTION BLOCKS ===== */
section.block {
  margin-bottom: 18px;
}
section.block h2 {
  font-size: 12.5px; font-weight: 800; letter-spacing: 0.16em;
  margin: 0 0 10px 0; color: #0f172a;
  padding-bottom: 6px;
  border-bottom: 1px solid #e5e7eb;
}

/* Floor plan */
.floor-plan-svg svg { width: 100%; height: auto; max-height: 280px; }
.floor-plan-note {
  font-size: 10.5px; color: #6b7280; margin-top: 6px; font-style: italic;
}

/* Zones */
.zone-row { display: flex; gap: 12px; padding: 7px 0; align-items: flex-start; }
.zone-num {
  width: 22px; height: 22px; border-radius: 50%;
  background: #4f6b58; color: white;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.zone-title { font-size: 12px; font-weight: 700; color: #0f172a; line-height: 1.35; }
.zone-body { font-size: 11px; color: #4b5563; line-height: 1.4; }

/* Wall color / shopping side-by-side row */
.color-shop {
  display: flex; gap: 14px;
}
.wall-color, .shopping {
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 14px;
  border: 1px solid #eceef0;
}
.wall-color { flex: 0.8; }
.shopping { flex: 1.2; }
.wall-color h3, .shopping h3 {
  font-size: 11.5px; font-weight: 800; letter-spacing: 0.14em;
  margin: 0 0 8px 0; color: #0f172a;
}
.wall-color .row { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.wall-color .name { font-size: 12px; font-weight: 700; }
.wall-color .reason { font-size: 11px; color: #475569; margin-top: 5px; max-width: 75%; line-height: 1.4; }
.color-swatch {
  width: 44px; height: 44px; border-radius: 50%;
  flex-shrink: 0; border: 1px solid #e5e7eb;
}

.shopping table { width: 100%; border-collapse: collapse; font-size: 11px; }
.shopping th, .shopping td {
  text-align: left; padding: 6px 4px;
  border-bottom: 1px solid #f1f5f9;
}
.shopping th { font-size: 9.5px; letter-spacing: 0.12em; color: #6b7280; }
.shopping td.num { text-align: right; }
.shopping tfoot td { font-weight: 800; padding-top: 8px; border: none; font-size: 11.5px; }

.budget-box {
  background: #4f6b58; color: white;
  border-radius: 10px; padding: 10px 14px;
  text-align: center; margin-top: 10px;
}
.budget-box h4 { font-size: 11px; font-weight: 800; letter-spacing: 0.14em; margin: 0; }
.budget-box p { font-size: 10.5px; margin: 4px 0 0; opacity: 0.95; }

/* Strategy cards */
.cards { display: flex; gap: 12px; }
.card {
  flex: 1;
  background: #ffffff;
  border: 1px solid #eceef0;
  border-radius: 12px;
  padding: 12px 14px;
}
.card h3 { font-size: 11px; font-weight: 800; letter-spacing: 0.18em; text-align: center; margin: 0 0 8px 0; }
.card ul { list-style: none; margin: 0; padding: 0; }
.card li {
  font-size: 11px;
  padding: 4px 0 4px 20px;
  position: relative;
  line-height: 1.4;
}
.card li::before {
  content: "✓";
  position: absolute; left: 0; top: 3px;
  color: #4f6b58;
  font-weight: 700;
  font-size: 12px;
}
.card.action li { padding-left: 22px; }
.card.action li::before {
  counter-increment: step;
  content: counter(step);
  background: #4f6b58; color: white;
  border-radius: 50%;
  width: 14px; height: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; font-weight: 700;
  top: 4px;
}
.card.action ul { counter-reset: step; }

/* ===== PHOTOS PAGE ===== */
.photos-intro {
  font-size: 12px; color: #4b5563; margin: 4px 0 16px;
}
.photo-block {
  margin-bottom: 18px;
  page-break-inside: avoid;
}
.photo-block .photo-frame {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}
.photo-block.full .photo-frame { height: 360px; }
.photo-block.half .photo-frame { height: 240px; }
.photo-block img { width: 100%; height: 100%; object-fit: cover; display: block; }
.photo-row { display: flex; gap: 12px; margin-bottom: 18px; }
.photo-row .photo-block { flex: 1; margin-bottom: 0; }
.photo-caption {
  margin-top: 6px;
  display: flex; align-items: center; gap: 8px;
}
.photo-tag {
  display: inline-block;
  background: #4f6b58; color: white;
  border-radius: 999px; padding: 4px 11px;
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.14em;
}
.photo-caption .label { font-size: 11px; color: #475569; }

.footnote {
  text-align: center; font-size: 10px; color: #6b7280;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}
"""


def _to_data_uri(b64: str) -> str:
    if not b64:
        return ""
    b64_clean = b64.split(",", 1)[1] if b64.startswith("data:") else b64
    return f"data:image/png;base64,{b64_clean}"


def _icon_circle(label: str, alt: int) -> str:
    glyphs = {
        "shopping-bag": "🛍",
        "bed": "🛏",
        "user": "◉",
        "leaf": "❦",
        "box": "▣",
        "lamp": "✦",
        "wrench": "⚒",
        "layout-grid": "▤",
        "spray": "✿",
        "compass": "✛",
        "shirt": "✦",
        "shoes": "◐",
        "folder": "▤",
        "watch": "◯",
        "star": "★",
    }
    g = glyphs.get(label, "●")
    return f'<span class="need-icon alt-{alt}">{g}</span>'


def _render_needs(needs: List[Dict[str, str]]) -> str:
    parts = []
    for i, n in enumerate(needs[:6]):
        icon = _icon_circle(n.get("icon", "leaf"), (i % 5) + 1)
        parts.append(
            f'<div class="need-row">{icon}'
            f'<div><div class="need-title">{n.get("title","")}</div>'
            f'<div class="need-body">{n.get("body","")}</div></div></div>'
        )
    return "".join(parts)


def _render_zones(zones: List[Dict[str, str]]) -> str:
    parts = []
    for i, z in enumerate(zones[:5], 1):
        parts.append(
            f'<div class="zone-row">'
            f'<div class="zone-num">{i}</div>'
            f'<div><div class="zone-title">{z.get("title","")}</div>'
            f'<div class="zone-body">{z.get("body","")}</div></div></div>'
        )
    return "".join(parts)


def _render_shopping(items: List[Dict[str, Any]]) -> tuple[str, int]:
    rows = []
    total = 0
    for it in items[:6]:
        qty = int(it.get("qty", 1) or 1)
        price = float(it.get("price", 0) or 0)
        subtotal = round(qty * price)
        total += subtotal
        rows.append(
            f'<tr><td>{it.get("item","")}</td>'
            f'<td class="num">{qty}</td>'
            f'<td class="num">${round(price)}</td>'
            f'<td class="num">${subtotal}</td></tr>'
        )
    body = "".join(rows)
    return body, round(total)


def _render_floor_plan_svg(width_ft: int, depth_ft: int, room_key: str) -> str:
    """Top-view svg with proper proportions + dimension labels."""
    W = 460
    H = 280
    scale = min((W - 80) / width_ft, (H - 80) / depth_ft)
    rect_w = width_ft * scale
    rect_h = depth_ft * scale
    x0 = (W - rect_w) / 2
    y0 = (H - rect_h) / 2 + 4

    furniture_svg = ""
    if room_key == "bedroom":
        bed_w = rect_w * 0.42
        bed_h = rect_h * 0.42
        bed_x = x0 + (rect_w - bed_w) / 2
        bed_y = y0 + 6
        furniture_svg += (
            f'<rect x="{bed_x:.1f}" y="{bed_y:.1f}" width="{bed_w:.1f}" height="{bed_h:.1f}" '
            f'rx="6" fill="#e7d9c4" stroke="#bba07a" stroke-width="1"/>'
        )
        pw = bed_w * 0.42; ph = bed_h * 0.18
        for i in (0, 1):
            px = bed_x + 6 + i * (pw + 6)
            furniture_svg += (
                f'<rect x="{px:.1f}" y="{bed_y + 6:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
                f'rx="3" fill="#cfe0e9" stroke="#9fb6c1" stroke-width="1"/>'
            )
        rug_w = rect_w * 0.6; rug_h = rect_h * 0.4
        rug_x = x0 + (rect_w - rug_w) / 2; rug_y = bed_y + bed_h - 4
        furniture_svg += (
            f'<rect x="{rug_x:.1f}" y="{rug_y:.1f}" width="{rug_w:.1f}" height="{rug_h:.1f}" '
            f'rx="4" fill="#efe7d3" stroke="#cdbb95" stroke-width="0.8" opacity="0.65"/>'
        )
        dw = rect_w * 0.12; dh = rect_h * 0.28
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + rect_h * 0.4:.1f}" width="{dw:.1f}" height="{dh:.1f}" '
            f'rx="3" fill="#c89a6a" stroke="#8a5e34" stroke-width="1"/>'
        )
    elif room_key == "garage":
        bw = rect_w * 0.6; bh = rect_h * 0.18
        furniture_svg += (
            f'<rect x="{x0 + (rect_w - bw) / 2:.1f}" y="{y0 + 4:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="2" fill="#cbd5e1" stroke="#64748b" stroke-width="1"/>'
        )
        cw = rect_w * 0.45; ch = rect_h * 0.55
        furniture_svg += (
            f'<rect x="{x0 + (rect_w - cw) / 2:.1f}" y="{y0 + rect_h * 0.35:.1f}" width="{cw:.1f}" height="{ch:.1f}" '
            f'rx="10" fill="#d6e3d6" stroke="#7d9b7d" stroke-width="1" stroke-dasharray="3 3"/>'
        )
    else:
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + 4:.1f}" width="{rect_w - 8:.1f}" height="{rect_h * 0.12:.1f}" '
            f'rx="2" fill="#dbe3d3" stroke="#7d9b7d" stroke-width="1"/>'
        )
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + rect_h - rect_h * 0.12 - 4:.1f}" width="{rect_w - 8:.1f}" height="{rect_h * 0.12:.1f}" '
            f'rx="2" fill="#dbe3d3" stroke="#7d9b7d" stroke-width="1"/>'
        )

    door_size = 26
    door_svg = (
        f'<path d="M {x0:.1f} {y0 + rect_h:.1f} L {x0 + door_size:.1f} {y0 + rect_h:.1f} '
        f'A {door_size} {door_size} 0 0 0 {x0:.1f} {y0 + rect_h - door_size:.1f} Z" '
        f'fill="none" stroke="#1f2937" stroke-width="1.2"/>'
    )

    dim_top = f'<text x="{W/2}" y="{y0 - 10}" font-size="11" text-anchor="middle" fill="#374151" font-weight="600">←  {width_ft} ft  →</text>'
    dim_right = (
        f'<text x="{x0 + rect_w + 16}" y="{y0 + rect_h/2 + 4}" font-size="11" font-weight="600" '
        f'fill="#374151" transform="rotate(90 {x0 + rect_w + 16} {y0 + rect_h/2 + 4})">↑  {depth_ft} ft  ↓</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{rect_w:.1f}" height="{rect_h:.1f}" '
        f'fill="#ffffff" stroke="#1f2937" stroke-width="2"/>'
        f'{furniture_svg}{door_svg}{dim_top}{dim_right}'
        f'</svg>'
    )


def _render_photos_page(main_image_b64: str, additional_images: List[str], labels: List[str]) -> str:
    """Page 2: customer's organized photos, full-width main + thumbnail row."""
    if not main_image_b64 and not additional_images:
        return ""

    blocks = []
    label0 = labels[0] if labels else "MAIN VIEW"
    if main_image_b64:
        blocks.append(
            f'<div class="photo-block full">'
            f'<div class="photo-frame"><img src="{_to_data_uri(main_image_b64)}"/></div>'
            f'<div class="photo-caption">'
            f'<span class="photo-tag">VIEW 1 — {label0}</span>'
            f'<span class="label">Your AI-organized space</span>'
            f'</div></div>'
        )

    # Remaining images: 2 per row half-width
    extras = [img for img in additional_images if img]
    label_pool = labels[1:] if labels else []
    pairs = []
    for i in range(0, len(extras), 2):
        pairs.append(extras[i:i + 2])

    for pi, pair in enumerate(pairs):
        row = []
        for j, img in enumerate(pair):
            idx = pi * 2 + j
            lbl_idx = idx
            lbl = label_pool[lbl_idx] if lbl_idx < len(label_pool) else f"VIEW {idx + 2}"
            row.append(
                f'<div class="photo-block half">'
                f'<div class="photo-frame"><img src="{_to_data_uri(img)}"/></div>'
                f'<div class="photo-caption">'
                f'<span class="photo-tag">VIEW {idx + 2} — {lbl}</span>'
                f'</div></div>'
            )
        if len(row) == 1:
            row.append('<div class="photo-block half" style="visibility:hidden"></div>')
        blocks.append(f'<div class="photo-row">{"".join(row)}</div>')

    return (
        '<div class="page-break">'
        '<h2 style="font-size:22px;letter-spacing:0.04em;font-weight:800;margin:0 0 4px 0">YOUR ORGANIZED SPACE</h2>'
        '<p class="photos-intro">These are your AI-generated visuals of how your room could look — organized, calm, and ready to live in.</p>'
        f'{"".join(blocks)}'
        '</div>'
    )


def render_design_plan_pdf(*, plan: Dict[str, Any], main_image_b64: str,
                            additional_images: Optional[List[str]] = None,
                            user_name: Optional[str] = None) -> bytes:
    additional_images = additional_images or []
    shopping_body, total = _render_shopping(plan.get("shopping", []))
    tags_html = ' <span class="dot">•</span> '.join(plan.get("keywords", []))
    floor = plan.get("floor_plan", {})
    floor_svg = _render_floor_plan_svg(
        int(floor.get("width_ft") or 12),
        int(floor.get("depth_ft") or 10),
        plan.get("room_key", "other"),
    )
    photos_page = _render_photos_page(main_image_b64, additional_images, plan.get("view_labels", []))

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>{plan.get('title')}</title></head>
<body>

  <div class="top">
    <div class="brand">
      <img src="{LOGO_URL}" alt="FlowSpace"/>
      <div class="tagline">Clear space. Create flow. Live better.</div>
    </div>
    <div class="title-wrap">
      <div class="h1">{plan.get('title','DESIGN PLAN')}</div>
      <div class="tags">{tags_html}</div>
      <div class="tag-line"></div>
      <div class="summary">{plan.get('summary','')}</div>
    </div>
  </div>

  <div class="designed-for avoid-break">
    <span class="leaf">
      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M11 20A7 7 0 0 1 4 13c0-7 7-9 13-9 0 4-2 11-6 13"/>
        <path d="M4 21c4-2 6-4 7-7"/>
      </svg>
    </span>
    <div>
      <h3>DESIGNED FOR HOW YOU LIVE</h3>
      <p>Smart choices. Everything in its place. Less stress. More time. More you.</p>
    </div>
  </div>

  <div class="main-grid avoid-break" style="margin-top:14px">
    <div class="main-image-wrap">
      <span class="image-label">3D VISUAL — FRONT VIEW</span>
      <img src="{_to_data_uri(main_image_b64)}" alt="Organized {plan.get('room_label','')}"/>
    </div>
    <div class="right-col needs">
      <h3>{plan.get('room_label','ROOM')} NEEDS</h3>
      {_render_needs(plan.get('room_needs', []))}
    </div>
  </div>

  <section class="block avoid-break">
    <h2>FLOOR PLAN (TOP VIEW)</h2>
    <div class="floor-plan-svg">{floor_svg}</div>
    <p class="floor-plan-note">Measurements are approximate. Adjust to your room as needed.</p>
  </section>

  <section class="block avoid-break">
    <h2>ROOM LAYOUT &amp; ZONES</h2>
    {_render_zones(plan.get('zones', []))}
  </section>

  <section class="block">
    <h2>COLOR &amp; SHOPPING LIST</h2>
    <div class="color-shop">
      <div class="wall-color">
        <h3>{plan.get('color', {}).get('title','WALL COLOR SUGGESTION')}</h3>
        <div class="row">
          <div>
            <div class="name">{plan.get('color', {}).get('name','')}</div>
            <div class="reason">{plan.get('color', {}).get('reason','')}</div>
          </div>
          <div class="color-swatch" style="background: {plan.get('color', {}).get('hex','#c8d3cf')};"></div>
        </div>
      </div>
      <div class="shopping">
        <h3>SHOPPING LIST &amp; ESTIMATED BUDGET</h3>
        <table>
          <thead><tr><th>ITEM</th><th class="num">QTY</th><th class="num">EST. PRICE</th><th class="num">SUBTOTAL</th></tr></thead>
          <tbody>{shopping_body}</tbody>
          <tfoot><tr><td>ESTIMATED TOTAL</td><td></td><td></td><td class="num">${total}</td></tr></tfoot>
        </table>
      </div>
    </div>
    <div class="budget-box">
      <h4>BUDGET RANGE: {plan.get('budget_range','$100 – $300')}</h4>
      <p>All items chosen to bring the biggest impact for your budget.</p>
    </div>
  </section>

  <section class="block">
    <h2>YOUR DESIGN ROADMAP</h2>
    <div class="cards">
      <div class="card">
        <h3>DESIGN STRATEGY</h3>
        <ul>{''.join(f'<li>{x}</li>' for x in plan.get('strategy', []))}</ul>
      </div>
      <div class="card action">
        <h3>SIMPLE ACTION PLAN</h3>
        <ul>{''.join(f'<li>{x}</li>' for x in plan.get('action_plan', []))}</ul>
      </div>
      <div class="card">
        <h3>BENEFITS</h3>
        <ul>{''.join(f'<li>{x}</li>' for x in plan.get('benefits', []))}</ul>
      </div>
    </div>
  </section>

  {photos_page}

  <p class="footnote">
    {('Prepared for ' + user_name + ' · ') if user_name else ''}
    FlowSpace.Solutions — Clear space. Create flow. Live better.
  </p>

</body>
</html>
"""
    pdf_bytes = HTML(string=html, base_url=".").write_pdf(stylesheets=[CSS(string=CSS_STYLE)])
    return pdf_bytes
