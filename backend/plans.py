"""Plan catalog, credit limits, and room/style constants for FlowSpace."""

# Stripe Price IDs (from the user's live Stripe account)
PLAN_TO_PRICE = {
    "pro": "price_1Tfm3YLjPaM58nJzBhAqXuuP",       # $9.99 / month
    "premium": "price_1Tfm3SLjPaM58nJzVF3GHEM0",   # $19.99 / month
}
PRICE_TO_PLAN = {v: k for k, v in PLAN_TO_PRICE.items()}

# Membership configuration
PLAN_LIMITS = {
    "free": {
        "name": "Free",
        "price": 0.0,
        "limit": 1,           # 1 transformation total (lifetime)
        "lifetime": True,     # never resets monthly
        "watermark": True,
        "hd": False,
        "pdf": False,
        "affiliate": False,
    },
    "pro": {
        "name": "Pro",
        "price": 9.99,
        "limit": 10,          # per month
        "lifetime": False,
        "watermark": False,
        "hd": True,
        "pdf": True,
        "affiliate": False,
    },
    "premium": {
        "name": "Premium",
        "price": 19.99,
        "limit": 1000,        # unlimited (fair-use cap)
        "lifetime": False,
        "watermark": False,
        "hd": True,
        "pdf": True,
        "affiliate": True,
    },
}


def plan_cfg(plan: str) -> dict:
    return PLAN_LIMITS.get(plan or "free", PLAN_LIMITS["free"])


ROOM_TYPES = [
    "garage", "closet", "pantry", "laundry", "bedroom", "office",
    "bathroom", "playroom", "kitchen", "living_room", "storage", "balcony", "other",
]

STYLES = [
    "modern", "minimalist", "family_friendly", "luxury", "budget_friendly",
    "neutral", "warm", "scandinavian", "industrial", "farmhouse", "custom",
]

ROOM_LABELS = {
    "garage": "Garage", "closet": "Closet", "pantry": "Pantry",
    "laundry": "Laundry Room", "bedroom": "Bedroom", "office": "Office",
    "bathroom": "Bathroom", "playroom": "Playroom", "kitchen": "Kitchen",
    "living_room": "Living Room", "storage": "Storage Room",
    "balcony": "Apartment Balcony", "other": "Other",
}

STYLE_LABELS = {
    "modern": "Modern", "minimalist": "Minimalist", "family_friendly": "Family-Friendly",
    "luxury": "Luxury", "budget_friendly": "Budget-Friendly", "neutral": "Neutral",
    "warm": "Warm", "scandinavian": "Scandinavian", "industrial": "Industrial",
    "farmhouse": "Farmhouse", "custom": "Custom",
}
