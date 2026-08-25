"""
User accounts - admin only.

Passwords are stored as PBKDF2-SHA256 hashes via Werkzeug. A plain
password is never written to the database and never leaves this module.
"""

import re

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from werkzeug.security import generate_password_hash

from db import query_all, query_one, execute
from auth_helpers import admin_required

users_bp = Blueprint("users", __name__)

HASH_METHOD = "pbkdf2:sha256:600000"


@users_bp.route("/")
@admin_required
def index():
    users = query_all("""
        SELECT u.user_id, u.username, u.full_name, u.role,
               u.is_active, u.created_at,
               COUNT(m.movement_id) AS movement_count
        FROM users u
        LEFT JOIN stock_movements m ON m.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY u.role, u.full_name
    """)
    return render_template("users/list.html", users=users)


def _password_problems(password):
    """A short, explicit password policy."""
    problems = []
    if len(password) < 8:
        problems.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password):
        problems.append("Password must contain at least one letter.")
    if not re.search(r"[0-9]", password):
        problems.append("Password must contain at least one number.")
    return problems


@users_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "staff")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []

        if not username:
            errors.append("Username is required.")
        elif not re.match(r"^[a-z0-9_.]{3,50}$", username):
            errors.append("Username may use lowercase letters, numbers, "
                          "dots and underscores, 3 to 50 characters.")
        elif query_one("SELECT user_id FROM users WHERE username = %s", (username,)):
            errors.append(f"The username {username} is already taken.")

        if not full_name:
            errors.append("Full name is required.")

        if role not in ("admin", "staff"):
            errors.append("Choose a valid role.")

        errors.extend(_password_problems(password))
        if password != confirm:
            errors.append("The two passwords do not match.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("users/form.html",
                                   user={"username": username,
                                         "full_name": full_name,
                                         "role": role, "is_active": 1},
                                   mode="create")

        execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
        """, (username, generate_password_hash(password, method=HASH_METHOD),
              full_name, role))

        flash(f"Account created for {full_name}.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html",
                           user={"username": "", "full_name": "",
                                 "role": "staff", "is_active": 1},
                           mode="create")


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(user_id):
    user = query_one("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if user is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("users.index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "staff")
        is_active = 1 if request.form.get("is_active") else 0
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []

        if not full_name:
            errors.append("Full name is required.")
        if role not in ("admin", "staff"):
            errors.append("Choose a valid role.")

        # An admin locking themselves out is a real failure mode, and
        # it is easy to do by accident on your own account.
        if user_id == session["user_id"]:
            if role != "admin":
                errors.append("You cannot remove your own administrator role.")
            if not is_active:
                errors.append("You cannot deactivate your own account.")

        # Password fields are optional on edit - blank means unchanged.
        if password or confirm:
            errors.extend(_password_problems(password))
            if password != confirm:
                errors.append("The two passwords do not match.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("users/form.html",
                                   user={"user_id": user_id,
                                         "username": user["username"],
                                         "full_name": full_name,
                                         "role": role, "is_active": is_active},
                                   mode="edit")

        if password:
            execute("""
                UPDATE users
                SET full_name = %s, role = %s, is_active = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, role, is_active,
                  generate_password_hash(password, method=HASH_METHOD), user_id))
        else:
            execute("""
                UPDATE users SET full_name = %s, role = %s, is_active = %s
                WHERE user_id = %s
            """, (full_name, role, is_active, user_id))

        flash(f"Account for {full_name} updated.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", user=user, mode="edit")


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete the account you are signed in with.", "error")
        return redirect(url_for("users.index"))

    user = query_one("SELECT full_name, role FROM users WHERE user_id = %s",
                     (user_id,))
    if user is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("users.index"))

    # Never let the last administrator be deleted - there would be no
    # way back into the user management screens.
    if user["role"] == "admin":
        admin_count = query_one(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1"
        )["n"]
        if admin_count <= 1:
            flash("This is the only active administrator account. "
                  "Create another before deleting this one.", "error")
            return redirect(url_for("users.index"))

    # stock_movements.user_id is ON DELETE SET NULL, so the audit trail
    # survives the account being removed.
    execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    flash(f"Account for {user['full_name']} deleted.", "success")
    return redirect(url_for("users.index"))
