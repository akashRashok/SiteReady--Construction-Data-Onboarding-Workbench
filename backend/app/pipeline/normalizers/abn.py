"""Australian Business Number (ABN) validation (PRD section 11 / 20)."""

from __future__ import annotations

import re
from dataclasses import dataclass

ABN_WEIGHTS = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]


@dataclass(frozen=True)
class AbnResult:
    is_valid: bool
    normalised: str | None
    raw: str


def validate_abn(raw: str | None) -> AbnResult:
    """Validate an ABN using the official checksum.

    1. Strip spaces and non-digit separators.
    2. Require exactly 11 digits.
    3. Subtract 1 from the first digit.
    4. Multiply digits by the weights.
    5. Sum the products.
    6. Valid when the sum is divisible by 89.
    """
    raw = raw or ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11:
        return AbnResult(False, None, raw)

    weighted = list(digits)
    values = [int(d) for d in weighted]
    values[0] -= 1
    total = sum(v * w for v, w in zip(values, ABN_WEIGHTS))
    if total % 89 == 0:
        return AbnResult(True, digits, raw)
    return AbnResult(False, None, raw)
