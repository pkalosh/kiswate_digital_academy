from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely get item from dict. Returns empty list if key not found.
    """
    if not dictionary:
        return []
    return dictionary.get(key, [])
