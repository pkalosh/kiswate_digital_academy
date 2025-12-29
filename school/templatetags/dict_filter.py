from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """
    Returns the value for a dictionary key.
    Handles objects as keys (e.g., slot objects) as well.
    """
    if not d:
        return None
    try:
        return d.get(key)
    except (KeyError, TypeError):
        return None
