"""Renders the FlowSpace Design Plan PDF using WeasyPrint.
Layout matches the provided Bedroom Design Plan reference: landscape A4,
white background, sage-green accents, rounded cards.
"""

from __future__ import annotations
import base64
import io
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
  size: 15in 11in;     /* landscape canvas (slightly bigger) */
  margin: 0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0.35in 0.45in;
  font-family: "Helvetica", "Arial", sans-serif;
  color: #1f2937;
  background: #ffffff;
  font-size: 10px;
  line-height: 1.35;
}
.h1 { font-size: 26px; font-weight: 800; letter-spacing: 0.04em; text-align: center; color: #0f172a; }
.h2 { font-size: 12px; font-weight: 700; letter-spacing: 0.16em; color: #0f172a; }
.tagline { font-size: 8.5px; color: #4b5563; letter-spacing: 0.02em; }

.row { display: flex; gap: 10px; }
.col { display: flex; flex-direction: column; gap: 10px; }

/* Top bar */
.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 10px;
}
.brand { width: 160px; }
.brand img { width: 120px; height: auto; display: block; }
.title-wrap { flex: 1; text-align: center; padding-top: 2px; }
.tags {
  font-size: 11px; font-weight: 700; letter-spacing: 0.14em;
  color: #1f2937; margin-top: 3px;
}
.tags .dot { color: #b6927a; margin: 0 7px; }
.tag-line {
  width: 60%; margin: 5px auto 0;
  height: 1px; background: linear-gradient(to right, transparent, #c7d2c5, transparent);
}
.summary { font-size: 11px; color: #374151; margin-top: 4px; }

.designed-for {
  width: 220px;
  background: #4f6b58;
  color: #fff;
  border-radius: 10px;
  padding: 9px 12px;
  display: flex; gap: 8px; align-items: flex-start;
}
.designed-for .leaf {
  width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,.15);
  display: inline-block; flex-shrink: 0; padding: 3px;
}
.designed-for h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0; }
.designed-for p { margin: 3px 0 0; font-size: 9px; line-height: 1.35; opacity: 0.95; }

/* Main grid */
.main-grid {
  display: flex; gap: 10px;
  margin-bottom: 10px;
}
.main-image-wrap {
  flex: 1.7;
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: #f3f4f6;
  height: 235px;
}
.main-image-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.image-label {
  position: absolute; top: 10px; left: 10px;
  background: #4f6b58; color: white;
  border-radius: 999px; padding: 4px 10px;
  font-size: 8.5px; font-weight: 700; letter-spacing: 0.12em;
}
.right-col { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.needs h3 { font-size: 11px; font-weight: 800; letter-spacing: 0.16em; color: #0f172a; margin: 0 0 6px 0; }
.need-row { display: flex; gap: 8px; align-items: flex-start; padding: 1px 0; }
.need-icon {
  width: 22px; height: 22px; border-radius: 50%;
  background: #cfd9c8; color: #3a5a40; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px;
}
.need-icon.alt-1 { background: #d9e2d3; }
.need-icon.alt-2 { background: #f1d4cf; color: #8a4d44; }
.need-icon.alt-3 { background: #e5e9d8; }
.need-icon.alt-4 { background: #cfd9c8; }
.need-icon.alt-5 { background: #efe6c8; color: #826a2f; }
.need-title { font-size: 10px; font-weight: 700; color: #0f172a; line-height: 1.2; }
.need-body { font-size: 9px; color: #4b5563; line-height: 1.25; }

/* Mid section */
.mid {
  display: flex; gap: 10px;
  margin-bottom: 10px;
}
.floor-plan {
  flex: 1.1;
  border-radius: 10px;
  padding: 8px 10px;
  background: #ffffff;
}
.floor-plan h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0 0 4px 0; }
.floor-plan-svg svg { width: 100%; height: auto; max-height: 170px; }

.zones {
  flex: 1.2;
  background: #ffffff;
  border-radius: 10px;
  padding: 8px 12px;
}
.zones h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0 0 4px 0; }
.zone-row { display: flex; gap: 8px; padding: 3px 0; align-items: flex-start; }
.zone-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: #4f6b58; color: white;
  font-size: 9px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.zone-title { font-size: 10px; font-weight: 700; color: #0f172a; line-height: 1.2; }
.zone-body { font-size: 9px; color: #4b5563; line-height: 1.25; }

.right-mid { flex: 1.05; display: flex; flex-direction: column; gap: 8px; }
.wall-color, .shopping {
  background: #ffffff;
  border-radius: 10px;
  padding: 8px 12px;
  border: 1px solid #eceef0;
}
.wall-color h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0 0 4px 0; }
.wall-color .row { justify-content: space-between; align-items: center; gap: 8px; }
.wall-color .name { font-size: 11px; font-weight: 700; }
.wall-color .reason { font-size: 9px; color: #475569; margin-top: 2px; max-width: 78%; line-height: 1.3; }
.color-swatch {
  width: 32px; height: 32px; border-radius: 50%;
  flex-shrink: 0; border: 1px solid #e5e7eb;
}

.shopping h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0 0 4px 0; }
.shopping table { width: 100%; border-collapse: collapse; font-size: 9px; }
.shopping th, .shopping td {
  text-align: left; padding: 3px 3px;
  border-bottom: 1px solid #f1f5f9;
}
.shopping th { font-size: 8px; letter-spacing: 0.12em; color: #6b7280; }
.shopping td.num { text-align: right; }
.shopping tfoot td { font-weight: 800; padding-top: 5px; border: none; }

.budget-box {
  background: #4f6b58; color: white;
  border-radius: 10px; padding: 8px 12px;
  text-align: center;
}
.budget-box h4 { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; margin: 0; }
.budget-box p { font-size: 9px; margin: 3px 0 0; opacity: 0.95; }

/* Additional views */
.views {
  display: flex; gap: 10px; margin-bottom: 8px;
}
.views .v-card {
  flex: 1;
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  background: #f3f4f6;
  height: 95px;
}
.views .v-card img { width: 100%; height: 100%; object-fit: cover; }
.views .v-label {
  position: absolute; left: 50%; bottom: 6px; transform: translateX(-50%);
  background: #4f6b58; color: white;
  padding: 3px 8px; border-radius: 999px;
  font-size: 8px; font-weight: 700; letter-spacing: 0.12em;
  white-space: nowrap;
}

/* Strategy cards */
.cards { display: flex; gap: 10px; }
.card {
  flex: 1;
  background: #ffffff;
  border: 1px solid #eceef0;
  border-radius: 10px;
  padding: 8px 12px;
}
.card h3 { font-size: 10px; font-weight: 800; letter-spacing: 0.16em; text-align: center; margin: 0 0 5px 0; }
.card ul { list-style: none; margin: 0; padding: 0; }
.card li {
  font-size: 9px;
  padding: 2px 0 2px 16px;
  position: relative;
  line-height: 1.3;
}
.card li::before {
  content: "✓";
  position: absolute; left: 0; top: 1px;
  color: #4f6b58;
  font-weight: 700;
  font-size: 10px;
}
.card.action li::before {
  counter-increment: step;
  content: counter(step);
  background: #4f6b58; color: white;
  border-radius: 50%;
  width: 12px; height: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 7px; font-weight: 700;
  top: 2px;
}
.card.action ul { counter-reset: step; }

.footnote {
  text-align: center; font-size: 8.5px; color: #6b7280; margin-top: 6px;
}
"""


def _to_data_uri(b64: str) -> str:
    if not b64:
        return ""
    b64_clean = b64.split(",", 1)[1] if b64.startswith("data:") else b64
    return f"data:image/png;base64,{b64_clean}"


def _icon_circle(label: str, alt: int) -> str:
    """SVG-less unicode/text icon inside a colored circle."""
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
    """Compact top-view svg with proper proportions + dimension labels."""
    W = 320
    H = 200
    # scale to fit while preserving aspect ratio
    scale = min((W - 60) / width_ft, (H - 60) / depth_ft)
    rect_w = width_ft * scale
    rect_h = depth_ft * scale
    x0 = (W - rect_w) / 2
    y0 = (H - rect_h) / 2 + 4

    # furniture by room type
    furniture_svg = ""
    if room_key == "bedroom":
        # bed centered on top wall
        bed_w = rect_w * 0.42
        bed_h = rect_h * 0.42
        bed_x = x0 + (rect_w - bed_w) / 2
        bed_y = y0 + 6
        furniture_svg += (
            f'<rect x="{bed_x:.1f}" y="{bed_y:.1f}" width="{bed_w:.1f}" height="{bed_h:.1f}" '
            f'rx="6" fill="#e7d9c4" stroke="#bba07a" stroke-width="1"/>'
        )
        # pillows
        pw = bed_w * 0.42
        ph = bed_h * 0.18
        for i in (0, 1):
            px = bed_x + 6 + i * (pw + 6)
            furniture_svg += (
                f'<rect x="{px:.1f}" y="{bed_y + 6:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
                f'rx="3" fill="#cfe0e9" stroke="#9fb6c1" stroke-width="1"/>'
            )
        # rug
        rug_w = rect_w * 0.6
        rug_h = rect_h * 0.4
        rug_x = x0 + (rect_w - rug_w) / 2
        rug_y = bed_y + bed_h - 4
        furniture_svg += (
            f'<rect x="{rug_x:.1f}" y="{rug_y:.1f}" width="{rug_w:.1f}" height="{rug_h:.1f}" '
            f'rx="4" fill="#efe7d3" stroke="#cdbb95" stroke-width="0.8" opacity="0.65"/>'
        )
        # dresser left wall
        dw = rect_w * 0.12
        dh = rect_h * 0.28
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + rect_h * 0.4:.1f}" width="{dw:.1f}" height="{dh:.1f}" '
            f'rx="3" fill="#c89a6a" stroke="#8a5e34" stroke-width="1"/>'
        )
    elif room_key == "garage":
        # workbench top wall
        bw = rect_w * 0.6
        bh = rect_h * 0.18
        furniture_svg += (
            f'<rect x="{x0 + (rect_w - bw) / 2:.1f}" y="{y0 + 4:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="2" fill="#cbd5e1" stroke="#64748b" stroke-width="1"/>'
        )
        # vehicle bay
        cw = rect_w * 0.45
        ch = rect_h * 0.55
        furniture_svg += (
            f'<rect x="{x0 + (rect_w - cw) / 2:.1f}" y="{y0 + rect_h * 0.35:.1f}" width="{cw:.1f}" height="{ch:.1f}" '
            f'rx="10" fill="#d6e3d6" stroke="#7d9b7d" stroke-width="1" stroke-dasharray="3 3"/>'
        )
    else:
        # generic shelving along walls
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + 4:.1f}" width="{rect_w - 8:.1f}" height="{rect_h * 0.12:.1f}" '
            f'rx="2" fill="#dbe3d3" stroke="#7d9b7d" stroke-width="1"/>'
        )
        furniture_svg += (
            f'<rect x="{x0 + 4:.1f}" y="{y0 + rect_h - rect_h * 0.12 - 4:.1f}" width="{rect_w - 8:.1f}" height="{rect_h * 0.12:.1f}" '
            f'rx="2" fill="#dbe3d3" stroke="#7d9b7d" stroke-width="1"/>'
        )

    # door arc bottom-left
    door_size = 22
    door_svg = (
        f'<path d="M {x0:.1f} {y0 + rect_h:.1f} L {x0 + door_size:.1f} {y0 + rect_h:.1f} '
        f'A {door_size} {door_size} 0 0 0 {x0:.1f} {y0 + rect_h - door_size:.1f} Z" '
        f'fill="none" stroke="#1f2937" stroke-width="1"/>'
    )

    # dimension labels
    dim_top = f'<text x="{W/2}" y="{y0 - 6}" font-size="9" text-anchor="middle" fill="#374151">←  {width_ft} ft  →</text>'
    dim_right = (
        f'<text x="{x0 + rect_w + 10}" y="{y0 + rect_h/2 + 3}" font-size="9" '
        f'fill="#374151" transform="rotate(90 {x0 + rect_w + 10} {y0 + rect_h/2 + 3})">↑  {depth_ft} ft  ↓</text>'
    )
    dim_bottom = f'<text x="{W/2}" y="{y0 + rect_h + 16}" font-size="9" text-anchor="middle" fill="#374151">←  {width_ft} ft  →</text>'

    svg = (
        f'<svg viewBox="0 0 {W} {H + 18}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{rect_w:.1f}" height="{rect_h:.1f}" '
        f'fill="#ffffff" stroke="#1f2937" stroke-width="2"/>'
        f'{furniture_svg}{door_svg}{dim_top}{dim_right}{dim_bottom}'
        f'</svg>'
    )
    return svg


def _render_views(images: List[str], labels: List[str]) -> str:
    if not images:
        return ""
    cards = []
    for i, img in enumerate(images[:4]):
        if not img:
            continue
        label = labels[i] if i < len(labels) else f"VIEW {i+1}"
        cards.append(
            f'<div class="v-card">'
            f'<img src="{_to_data_uri(img)}"/>'
            f'<span class="v-label">VIEW {i+1} — {label}</span>'
            f'</div>'
        )
    if not cards:
        return ""
    return f'<div class="views">{"".join(cards)}</div>'


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
    views_html = _render_views(additional_images, plan.get("view_labels", []))

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>{plan.get('title')}</title></head>
<body>

  <div class="top">
    <div class="brand">
      <img src="{LOGO_URL}" alt="FlowSpace"/>
      <div class="tagline" style="margin-top:6px">Clear space. Create flow. Live better.</div>
    </div>
    <div class="title-wrap">
      <div class="h1">{plan.get('title','DESIGN PLAN')}</div>
      <div class="tags">{tags_html}</div>
      <div class="tag-line"></div>
      <div class="summary">{plan.get('summary','')}</div>
    </div>
    <div class="designed-for">
      <span class="leaf">
        <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M11 20A7 7 0 0 1 4 13c0-7 7-9 13-9 0 4-2 11-6 13"/>
          <path d="M4 21c4-2 6-4 7-7"/>
        </svg>
      </span>
      <div>
        <h3>DESIGNED FOR HOW YOU LIVE</h3>
        <p>Smart choices. Everything in its place.<br/>Less stress. More time. More you.</p>
      </div>
    </div>
  </div>

  <div class="main-grid">
    <div class="main-image-wrap">
      <span class="image-label">3D VISUAL — FRONT VIEW</span>
      <img src="{_to_data_uri(main_image_b64)}" alt="Organized {plan.get('room_label','')}"/>
    </div>
    <div class="right-col needs">
      <h3>{plan.get('room_label','ROOM')} NEEDS</h3>
      {_render_needs(plan.get('room_needs', []))}
    </div>
  </div>

  <div class="mid">
    <div class="floor-plan">
      <h3>FLOOR PLAN (TOP VIEW)</h3>
      <div class="floor-plan-svg">{floor_svg}</div>
    </div>
    <div class="zones">
      <h3>ROOM LAYOUT &amp; ZONES</h3>
      {_render_zones(plan.get('zones', []))}
    </div>
    <div class="right-mid">
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
      <div class="budget-box">
        <h4>BUDGET RANGE: {plan.get('budget_range','$100 – $300')}</h4>
        <p>All items chosen to bring the biggest impact for your budget.</p>
      </div>
    </div>
  </div>

  {views_html}

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

  <p class="footnote">Note: Measurements are approximate. Adjust to your room as needed.{(' Prepared for ' + user_name + '.') if user_name else ''}</p>

</body>
</html>
"""
    pdf_bytes = HTML(string=html, base_url=".").write_pdf(stylesheets=[CSS(string=CSS_STYLE)])
    return pdf_bytes
