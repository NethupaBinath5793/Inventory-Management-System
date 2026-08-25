"""Categories - CRUD, admin only."""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import query_all, query_one, execute
from auth_helpers import login_required, admin_required

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/")
@login_required
def index():
    # The product count next to each category comes from a LEFT JOIN
    # with a GROUP BY, so categories with no products still show, as 0.
    categories = query_all("""
        SELECT c.category_id, c.name, c.description,
               COUNT(p.product_id)              AS product_count,
               COALESCE(SUM(p.quantity), 0)     AS units
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        GROUP BY c.category_id, c.name, c.description
        ORDER BY c.name
    """)
    return render_template("categories/list.html", categories=categories)


def _validate(form, category_id=None):
    errors = []
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()

    if not name:
        errors.append("Category name is required.")
    elif len(name) > 80:
        errors.append("Category name cannot be longer than 80 characters.")
    else:
        clash = query_one("SELECT category_id FROM categories WHERE name = %s", (name,))
        if clash and clash["category_id"] != category_id:
            errors.append(f"A category called {name} already exists.")

    return {"name": name, "description": description}, errors


@categories_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        values, errors = _validate(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("categories/form.html",
                                   category=values, mode="create")

        execute("INSERT INTO categories (name, description) VALUES (%s, %s)",
                (values["name"], values["description"]))
        flash(f"Category {values['name']} added.", "success")
        return redirect(url_for("categories.index"))

    return render_template("categories/form.html",
                           category={"name": "", "description": ""},
                           mode="create")


@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(category_id):
    category = query_one("SELECT * FROM categories WHERE category_id = %s",
                         (category_id,))
    if category is None:
        flash("That category no longer exists.", "error")
        return redirect(url_for("categories.index"))

    if request.method == "POST":
        values, errors = _validate(request.form, category_id=category_id)
        if errors:
            for message in errors:
                flash(message, "error")
            values["category_id"] = category_id
            return render_template("categories/form.html",
                                   category=values, mode="edit")

        execute("UPDATE categories SET name = %s, description = %s "
                "WHERE category_id = %s",
                (values["name"], values["description"], category_id))
        flash(f"Category {values['name']} updated.", "success")
        return redirect(url_for("categories.index"))

    return render_template("categories/form.html", category=category, mode="edit")


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete(category_id):
    category = query_one("SELECT name FROM categories WHERE category_id = %s",
                         (category_id,))
    if category is None:
        flash("That category no longer exists.", "error")
        return redirect(url_for("categories.index"))

    # The foreign key is ON DELETE SET NULL, so deleting would silently
    # orphan the products. Blocking it instead makes the consequence
    # visible and tells the user what to do first.
    in_use = query_one("SELECT COUNT(*) AS n FROM products WHERE category_id = %s",
                       (category_id,))["n"]
    if in_use:
        flash(f"{category['name']} still holds {in_use} product(s). "
              "Move them to another category first.", "error")
        return redirect(url_for("categories.index"))

    execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
    flash(f"Category {category['name']} deleted.", "success")
    return redirect(url_for("categories.index"))
