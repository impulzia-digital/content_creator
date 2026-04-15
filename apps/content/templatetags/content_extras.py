from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def is_list(value):
    return isinstance(value, (list, tuple))


@register.filter
def format_cost(value):
    """Formatea un costo USD de forma legible.

    - >= $1.00   → $1.23
    - >= $0.01   → $0.08
    - < $0.01    → $0.0012
    - 0          → $0.00
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "$0.00"
    if val == 0:
        return "$0.00"
    if val >= 1:
        return f"${val:,.2f}"
    if val >= 0.01:
        return f"${val:.2f}"
    return f"${val:.4f}"