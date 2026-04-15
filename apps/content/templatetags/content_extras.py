from django import template

register = template.Library()


@register.filter
def is_list(value):
    return isinstance(value, (list, tuple))


@register.filter
def format_cost(value):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if amount == 0:
        return "$0.00"
    if amount >= 1:
        return f"${amount:.2f}"
    if amount >= 0.01:
        return f"${amount:.2f}"
    return f"${amount:.4f}"