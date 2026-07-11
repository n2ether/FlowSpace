#!/usr/bin/env python3
"""Validate FlowSpace production environment configuration without printing secrets."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - keeps the script usable in minimal shells.
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]


def load_local_envs() -> None:
    if not load_dotenv:
        return
    for path in (ROOT / ".env", ROOT / "backend" / ".env", ROOT / "frontend" / ".env"):
        if path.exists():
            load_dotenv(path, override=False)


def present(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def redacted(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        return "missing"
    if len(value) <= 8:
        return "set"
    return f"set ({value[:3]}...{value[-3:]})"


def main() -> int:
    load_local_envs()

    checks = [
        ("MONGO_URL", True),
        ("DB_NAME", True),
        ("REACT_APP_BACKEND_URL", True),
        ("PUBLIC_APP_URL", True),
        ("CORS_ORIGINS", True),
        ("STRIPE_SECRET_KEY", True),
        ("REPLICATE_API_TOKEN", True),
        ("RUNWAY_API_KEY", True),
        ("IMAGE_PROVIDER", False),
        ("VIDEO_PROVIDER", False),
        ("EMERGENT_LLM_KEY", False),
        ("SMTP_HOST", False),
    ]

    failures = []
    print("FlowSpace environment check")
    print("===========================")
    for name, required in checks:
        ok = present(name)
        label = "required" if required else "optional"
        print(f"{name:24} {label:8} {redacted(name)}")
        if required and not ok:
            failures.append(name)

    image_provider = (os.environ.get("IMAGE_PROVIDER") or "replicate").strip().lower()
    video_provider = (os.environ.get("VIDEO_PROVIDER") or "runway").strip().lower()
    require_payment = (os.environ.get("REQUIRE_PAYMENT_FOR_ROOM_JOBS") or "true").strip().lower()

    if image_provider != "replicate":
        failures.append("IMAGE_PROVIDER=replicate")
        print("ERROR: IMAGE_PROVIDER should be replicate for the selected production setup.")
    if video_provider != "runway":
        failures.append("VIDEO_PROVIDER=runway")
        print("ERROR: VIDEO_PROVIDER should be runway for the selected production setup.")
    if require_payment == "false":
        failures.append("REQUIRE_PAYMENT_FOR_ROOM_JOBS=true")
        print("ERROR: REQUIRE_PAYMENT_FOR_ROOM_JOBS must not be false in production.")

    if failures:
        print("\nMissing or invalid settings:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("\nEnvironment configuration looks ready for Replicate + Runway + Stripe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
