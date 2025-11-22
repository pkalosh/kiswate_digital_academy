from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Return value from dictionary by key, or None if key not found."""
    return d.get(key)
