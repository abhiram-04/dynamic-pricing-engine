"""
api/guardrails.py
Business rules that bound every price recommendation.
These run AFTER the ML optimizer and can never be overridden.
"""

from config.settings import settings
from loguru import logger


class PriceGuardrails:
    """
    Hard constraints applied to every price recommendation:
      - Floor: never price below X% of base (protects margin)
      - Ceiling: never price above Y% of base (protects brand)
      - Max change: limit per-event swing to Z% (prevents customer shock)
      - Psychological pricing: round to .99 or .49
    """

    def __init__(
        self,
        floor_pct: float = None,
        ceiling_pct: float = None,
        max_change_pct: float = None,
        psychological_pricing: bool = True,
    ):
        self.floor_pct     = floor_pct     or settings.PRICE_FLOOR_PCT
        self.ceiling_pct   = ceiling_pct   or settings.PRICE_CEILING_PCT
        self.max_change_pct = max_change_pct or settings.MAX_PRICE_CHANGE_PCT
        self.psychological  = psychological_pricing

    def apply(
        self, recommended: float, base_price: float
    ) -> tuple[float, bool, str]:
        """
        Apply all guardrails to a recommended price.

        Returns:
            (final_price, guardrail_applied, reason_string)
        """
        price = recommended
        applied = False
        reason = ""

        # 1. Hard floor
        floor = base_price * self.floor_pct
        if price < floor:
            price = floor
            applied = True
            reason = f"Price floor applied (≥{self.floor_pct*100:.0f}% of base)"
            logger.debug(f"Floor guardrail: {recommended:.2f} → {price:.2f}")

        # 2. Hard ceiling
        ceiling = base_price * self.ceiling_pct
        if price > ceiling:
            price = ceiling
            applied = True
            reason = f"Price ceiling applied (≤{self.ceiling_pct*100:.0f}% of base)"
            logger.debug(f"Ceiling guardrail: {recommended:.2f} → {price:.2f}")

        # 3. Max per-event change
        max_delta = base_price * self.max_change_pct
        if abs(price - base_price) > max_delta:
            direction = 1 if price > base_price else -1
            price = base_price + direction * max_delta
            applied = True
            reason = f"Max change guardrail (≤{self.max_change_pct*100:.0f}% swing)"
            logger.debug(f"Max-change guardrail: {recommended:.2f} → {price:.2f}")

        # 4. Psychological pricing (.99 / .49 endings)
        if self.psychological and price >= 1.0:
            price = self._round_psychological(price)

        return round(price, 2), applied, reason

    @staticmethod
    def _round_psychological(price: float) -> float:
        """
        Round to nearest .99 or .49 charm price.
        e.g. 34.62 → 34.49, 34.87 → 34.99
        """
        base = int(price)
        frac = price - base
        if frac < 0.25:
            return base - 0.01          # e.g. 34.12 → 33.99
        elif frac < 0.74:
            return base + 0.49          # e.g. 34.55 → 34.49
        else:
            return base + 0.99          # e.g. 34.88 → 34.99
