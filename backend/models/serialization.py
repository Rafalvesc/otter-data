"""Preserve database precision and reject non-finite values in query evidence."""

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite decimal result")
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite float result")
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value
