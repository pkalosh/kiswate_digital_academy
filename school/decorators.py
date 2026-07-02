from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """Require user to have at least one of the listed boolean role flags."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('userauths:sign-in')
            if not any(getattr(request.user, role, False) for role in roles):
                messages.error(request, "You do not have permission to access this page.")
                return redirect('school:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def kiswate_admin_required(view_func):
    """Restrict view to Kiswate platform admins and superusers."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('userauths:sign-in')
        u = request.user
        if not (u.is_superuser or getattr(u, 'is_kiswate_user', False) or getattr(u, 'is_kiswate_admin', False)):
            messages.error(request, "Access denied.")
            return redirect('school:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapped


def parent_required(view_func):
    """Restrict view to authenticated parents."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('userauths:sign-in')
        if not getattr(request.user, 'is_parent', False):
            messages.error(request, "This section is for parents only.")
            return redirect('userauths:sign-in')
        return view_func(request, *args, **kwargs)
    return wrapped


def school_admin_required(view_func):
    """Restrict view to principals, deputy principals, and school admins."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('userauths:sign-in')
        u = request.user
        if not (u.is_superuser or getattr(u, 'is_admin', False) or
                getattr(u, 'is_principal', False) or getattr(u, 'is_deputy_principal', False)):
            messages.error(request, "Access denied.")
            return redirect('school:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapped
