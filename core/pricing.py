"""
Pricing rules. The Next.js frontend has the same functions in src/lib/pricing.ts for live
previews; the amounts charged always come from here. All amounts are whole birr.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

FREE_DELIVERY_THRESHOLD = 100_000  # purchases at or above this ship free
DELIVERY_FEE = 500
SAME_DAY_FEE = 450
SHOP_TZ = ZoneInfo("Africa/Addis_Ababa")


def shop_today() -> date:
    """Today's date in the shop's time zone, whatever zone the server runs in."""
    return datetime.now(SHOP_TZ).date()


def rental_base_price(rate: int, plans, days: int) -> int:
    """Price of renting for `days`: a matching plan if there is one, otherwise the day rate."""
    for plan in plans:
        if plan.days == days:
            return plan.price
    return rate * days


def rental_line_price(rate: int, plans, add_ons, selected_keys, days: int) -> int:
    per_day = sum(a.per_day for a in add_ons if a.key in selected_keys)
    return rental_base_price(rate, plans, days) + per_day * days


def compute_totals(
    purchases: int,
    rentals: int,
    deposit: int,
    percent_off: int = 0,
    pickup: bool = False,
    same_day: bool = False,
) -> dict:
    discount = round(purchases * percent_off / 100) if percent_off and purchases > 0 else 0
    goods = purchases - discount
    unlocked = goods >= FREE_DELIVERY_THRESHOLD
    delivery_fee = 0 if (pickup or purchases == 0 or unlocked) else DELIVERY_FEE
    same_day_fee = SAME_DAY_FEE if (same_day and purchases > 0 and not pickup) else 0
    return {
        "purchases": purchases,
        "discount": discount,
        "rentals": rentals,
        "deliveryFee": delivery_fee,
        "sameDayFee": same_day_fee,
        "deposit": deposit,
        "total": goods + rentals + delivery_fee + same_day_fee,  # charged now; the deposit is held separately
        "freeDeliveryRemaining": max(0, FREE_DELIVERY_THRESHOLD - goods),
    }
