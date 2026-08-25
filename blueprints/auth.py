"""Sign in and sign out."""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from db import query_one

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Already signed in? Go straight to the dashboard.
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_one(
            "SELECT user_id, username, password_hash, full_name, role, is_active "
            "FROM users WHERE username = %s",
            (username,),
        )

        # Deliberately one message for "no such user" and "wrong
        # password". Telling an attacker which half was correct hands
        # them a way to discover valid usernames.
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Username or password is incorrect.", "error")
            return render_template("login.html", username=username)

        if not user["is_active"]:
            flash("That account has been deactivated. Ask an administrator.", "error")
            return render_template("login.html", username=username)

        # Store only what the templates need. The password hash never
        # goes into the session.
        session.clear()
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["full_name"] = user["full_name"]
        session["role"] = user["role"]

        flash(f"Signed in as {user['full_name']}.", "success")

        # Send them where they were originally headed, if anywhere.
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("login.html", username="")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("auth.login"))
