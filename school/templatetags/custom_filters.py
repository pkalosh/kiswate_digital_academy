from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Return value from dictionary by key, or None if key not found.
    Safely handles None or non-dict inputs."""
    if isinstance(d, dict):
        return d.get(key)
    return None


@register.filter
def startswith(value, prefix):
    """Check if a string starts with the given prefix."""
    if isinstance(value, str):
        return value.startswith(prefix)
    return False

@register.filter
def in_list(value, the_list):
    """
    Check if value is in a comma-separated string.
    Usage in template: {% if field.name|in_list:"enrollment_date,grade_level,send_email" %}
    """
    if value is None:
        return False
    return value in [x.strip() for x in the_list.split(',')]