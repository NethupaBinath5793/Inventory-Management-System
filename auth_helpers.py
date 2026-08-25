"""
Access control decorators.

Two rules cover the whole application:

  @login_required   - you must be signed in
  @admin_required   - you must be signed in AND have the admin role

Putting these on the route functions keeps the check in one place. A
page is protected because it is decorated, not because some template
happened to hide a link - hiding a button in the navigation does not
stop anyone typing the URL.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Sign in to continue.", "error")
            # Remember where they were headed so login can send them back.
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Sign in to continue.", "error")
            return redirect(url_for("auth.login", next=request.path))
        if session.get("role") != "admin":
            flash("That area is limited to administrators.", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)
    return wrapped
