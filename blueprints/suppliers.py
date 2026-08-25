"""Suppliers - CRUD, admin only."""

import re

from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import query_all, query_one, execute
from auth_helpers import login_required, admin_required

suppliers_bp = Blueprint("suppliers", __name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


@suppliers_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()

    if search:
        suppliers = query_all("""
            SELECT s.*, COUNT(p.product_id) AS product_count
            FROM suppliers s
            LEFT JOIN products p ON p.supplier_id = s.supplier_id
            WHERE s.name LIKE %s OR s.contact_person LIKE %s
            GROUP BY s.supplier_id
            ORDER BY s.name
        """, (f"%{search}%", f"%{search}%"))
    else:
        suppliers = query_all("""
            SELECT s.*, COUNT(p.product_id) AS product_count
            FROM suppliers s
            LEFT JOIN products p ON p.supplier_id = s.supplier_id
            GROUP BY s.supplier_id
            ORDER BY s.name
        """)

    return render_template("suppliers/list.html", suppliers=suppliers, search=search)


def _validate(form):
    errors = []
    name = form.get("name", "").strip()
    contact_person = form.get("contact_person", "").strip()
    phone = form.get("phone", "").strip()
    email = form.get("email", "").strip()
    address = form.get("address", "").strip()

    if not name:
        errors.append("Supplier name is required.")
    elif len(name) > 120:
        errors.append("Supplier name cannot be longer than 120 characters.")

    # Email and phone are optional, but if given they must look right.
    if email and not EMAIL_PATTERN.match(email):
        errors.append("Email address is not in a valid format.")

    if phone and not re.match(r"^[0-9+\-\s()]{6,30}$", phone):
        errors.append("Phone number may only contain digits, spaces, +, - and ().")

    return {
        "name": name, "contact_person": contact_person, "phone": phone,
        "email": email, "address": address,
    }, errors


@suppliers_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        values, errors = _validate(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("suppliers/form.html",
                                   supplier=values, mode="create")

        execute("""
            INSERT INTO suppliers (name, contact_person, phone, email, address)
            VALUES (%s, %s, %s, %s, %s)
        """, (values["name"], values["contact_person"], values["phone"],
              values["email"], values["address"]))

        flash(f"Supplier {values['name']} added.", "success")
        return redirect(url_for("suppliers.index"))

    blank = {"name": "", "contact_person": "", "phone": "",
             "email": "", "address": ""}
    return render_template("suppliers/form.html", supplier=blank, mode="create")


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(supplier_id):
    supplier = query_one("SELECT * FROM suppliers WHERE supplier_id = %s",
                         (supplier_id,))
    if supplier is None:
        flash("That supplier no longer exists.", "error")
        return redirect(url_for("suppliers.index"))

    if request.method == "POST":
        values, errors = _validate(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            values["supplier_id"] = supplier_id
            return render_template("suppliers/form.html",
                                   supplier=values, mode="edit")

        execute("""
            UPDATE suppliers
            SET name = %s, contact_person = %s, phone = %s,
                email = %s, address = %s
            WHERE supplier_id = %s
        """, (values["name"], values["contact_person"], values["phone"],
              values["email"], values["address"], supplier_id))

        flash(f"Supplier {values['name']} updated.", "success")
        return redirect(url_for("suppliers.index"))

    return render_template("suppliers/form.html", supplier=supplier, mode="edit")


@suppliers_bp.route("/<int:supplier_id>/delete", methods=["POST"])
@admin_required
def delete(supplier_id):
    supplier = query_one("SELECT name FROM suppliers WHERE supplier_id = %s",
                         (supplier_id,))
    if supplier is None:
        flash("That supplier no longer exists.", "error")
        return redirect(url_for("suppliers.index"))

    in_use = query_one("SELECT COUNT(*) AS n FROM products WHERE supplier_id = %s",
                       (supplier_id,))["n"]
    if in_use:
        flash(f"{supplier['name']} still supplies {in_use} product(s). "
              "Reassign them first.", "error")
        return redirect(url_for("suppliers.index"))

    execute("DELETE FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    flash(f"Supplier {supplier['name']} deleted.", "success")
    return redirect(url_for("suppliers.index"))
