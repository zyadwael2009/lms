from __future__ import annotations

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

from app.models import UserRole


def approved_required(view_func):
    """Allows access only to approved users (admins are always allowed)."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user.is_authenticated and current_user.is_admin:
            return view_func(*args, **kwargs)

        if not current_user.is_approved:
            flash("Your account is still pending admin approval.", "warning")
            return redirect(url_for("main.pending_approval"))

        return view_func(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles: UserRole):
    """Restricts access to the given user roles."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if current_user.role not in allowed_roles:
                flash("You are not authorized to view this page.", "danger")
                return redirect(url_for("main.index"))
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def admin_permission_required(permission: str):
    """Requires an admin with a matching scoped permission."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin:
                flash("Admin access is required.", "danger")
                return redirect(url_for("main.index"))

            if not current_user.has_admin_permission(permission):
                flash("You do not have permission for this admin area.", "warning")
                return redirect(url_for("admin.dashboard"))

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator
