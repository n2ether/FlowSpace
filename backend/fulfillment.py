"""
Helpers for matching a paid Stripe checkout to a FlowSpace lead
and deciding whether automation should start.

Kept independent of FastAPI/Mongo so the lookup rules can be unit-tested.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Statuses where a second auto-trigger would duplicate work.
IN_FLIGHT_OR_DONE = frozenset({"processing", "delivered"})
# Statuses the admin retry (or a failed-email re-run) may restart.
RESTARTABLE = frozenset({"new", "paid", "pdf_ready", "error"})


def checkout_lead_lookups(
    *,
    metadata: Optional[Dict[str, Any]] = None,
    customer_email: Optional[str] = None,
    transaction_lead_id: Optional[str] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Return Mongo queries in priority order for the lead that belongs to a payment.

    Priority:
      1. lead_id stored on the payment_transactions row (set at checkout create)
      2. lead_id / leadId in Stripe session metadata (sent by the intake form)
      3. Case-insensitive email match on a lead that has not finished delivery
    """
    metadata = metadata or {}
    lookups: List[Tuple[str, Dict[str, Any]]] = []

    tx_id = (transaction_lead_id or "").strip()
    if tx_id:
        lookups.append(("transaction.lead_id", {"id": tx_id}))

    meta_id = str(metadata.get("lead_id") or metadata.get("leadId") or "").strip()
    if meta_id and meta_id != tx_id:
        lookups.append(("metadata.lead_id", {"id": meta_id}))

    email = (customer_email or str(metadata.get("email") or "")).strip()
    if email:
        lookups.append(
            (
                "email",
                {
                    "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"},
                    "status": {"$in": ["new", "paid", "pdf_ready", "error"]},
                },
            )
        )
    return lookups


def should_auto_start_automation(status: Optional[str]) -> bool:
    """True unless the pipeline is already running or already emailed."""
    return (status or "new") not in IN_FLIGHT_OR_DONE
