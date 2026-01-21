from django import template

register = template.Library()

@register.filter
def in_list(value, the_list):
    return value in the_list
