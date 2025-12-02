# school/templatetags/dict_filters.py
from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return {}  # return empty dict if None
    return dictionary.get(key, {})  # safely return empty dict if key not present
