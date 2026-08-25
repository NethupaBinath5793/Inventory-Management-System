"""
Products - the main CRUD screen.

This one file demonstrates all four operations the brief asks for:
    Create  -> create()
    Read    -> index() and view()
    Update  -> edit()
    Delete  -> delete()

Search, category filtering, sorting and pagination all sit on index().
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)

from db import query_all, query_one, execute
from auth_helpers import login_required, admin_required

products_bp = Blueprint("products", __name__)

# Only these columns may be sorted on. The sort column cannot be a
# query parameter, because a column name cannot be passed as a %s
# placeholder - it goes into the SQL string itself. Checking the user's
# choice against this whitelist is what keeps that safe.
SORTABLE = {
    "name": "p.name",
    "sku": "p.sku",
    "quantity": "p.quantity",
    "price": "p.unit_price",
    "updated": "p.updated_at",
}


def _validate(form, product_id=None):
    """
    Check a submitted product form.

    Returns (cleaned_values, errors). Validation lives in its own
    function because create() and edit() need exactly the same rules,
    and duplicating them is how the two screens drift apart.
    """
    errors = []

    sku = form.get("sku", "").strip().upper()
    name = form.get("name", "").strip()
    category_id = form.get("category_id") or None
    supplier_id = form.get("supplier_id") or None
    unit_price_raw = form.get("unit_price", "").strip()
    quantity_raw = form.get("quantity", "").strip()
    reorder_raw = form.get("reorder_level", "").strip()

    if not sku:
        errors.append("SKU is required.")
    elif len(sku) > 40:
        errors.append("SKU cannot be longer than 40 characters.")
    else:
        # SKU must be unique. On edit, the product's own row does not
        # count as a clash, hence the second condition.
        clash = query_one("SELECT product_id FROM products WHERE sku = %s", (sku,))
        if clash and clash["product_id"] != product_id:
            errors.append(f"SKU {sku} is already used by another product.")

    if not name:
        errors.append("Product name is required.")
    elif len(name) > 150:
        errors.append("Product name cannot be longer than 150 characters.")

    try:
        unit_price = float(unit_price_raw)
        if unit_price < 0:
            errors.append("Unit price cannot be negative.")
    except ValueError:
        unit_price = 0.0
        errors.append("Unit price must be a number.")

    try:
        quantity = int(quantity_raw)
        if quantity < 0:
            errors.append("Quantity cannot be negative.")
    except ValueError:
        quantity = 0
        errors.append("Quantity must be a whole number.")

    try:
        reorder_level = int(reorder_raw)
        if reorder_level < 0:
            errors.append("Reorder level cannot be negative.")
    except ValueError:
        reorder_level = 0
        errors.append("Reorder level must be a whole number.")

    cleaned = {
        "sku": sku,
        "name": name,
        "category_id": int(category_id) if category_id else None,
        "supplier_id": int(supplier_id) if supplier_id else None,
        "unit_price": unit_price,
        "quantity": quantity,
        "reorder_level": reorder_level,
    }
    return cleaned, errors


def _lookups():
    """Category and supplier lists for the dropdowns on the form."""
    return (
        query_all("SELECT category_id, name FROM categories ORDER BY name"),
        query_all("SELECT supplier_id, name FROM suppliers ORDER BY name"),
    )


# ----------------------------------------------------------------
# READ - list with search, filter, sort and pagination
# ----------------------------------------------------------------
@products_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", "")
    stock_filter = request.args.get("stock", "")
    sort = request.args.get("sort", "name")
    direction = "DESC" if request.args.get("dir") == "desc" else "ASC"
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 10

    # Conditions are collected in a list and joined with AND. Values go
    # into a parallel list and are passed as parameters, never glued
    # into the SQL string.
    conditions = []
    params = []

    if search:
        conditions.append("(p.name LIKE %s OR p.sku LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    if category_id:
        conditions.append("p.category_id = %s")
        params.append(category_id)

    if stock_filter == "low":
        conditions.append("p.quantity <= p.reorder_level AND p.quantity > 0")
    elif stock_filter == "out":
        conditions.append("p.quantity = 0")
    elif stock_filter == "ok":
        conditions.append("p.quantity > p.reorder_level")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order_column = SORTABLE.get(sort, "p.name")

    total = query_one(
        f"SELECT COUNT(*) AS n FROM products p {where}", params
    )["n"]

    total_pages = max(1, -(-total // per_page))   # ceiling division
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    products = query_all(f"""
        SELECT p.*, c.name AS category_name, s.name AS supplier_name
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
        {where}
        ORDER BY {order_column} {direction}
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    categories = query_all("SELECT category_id, name FROM categories ORDER BY name")

    return render_template(
        "products/list.html",
        products=products,
        categories=categories,
        search=search,
        category_id=category_id,
        stock_filter=stock_filter,
        sort=sort,
        direction=request.args.get("dir", "asc"),
        page=page,
        total_pages=total_pages,
        total=total,
    )


# ----------------------------------------------------------------
# READ - single product with its movement history
# ----------------------------------------------------------------
@products_bp.route("/<int:product_id>")
@login_required
def view(product_id):
    product = query_one("""
        SELECT p.*, c.name AS category_name,
               s.name AS supplier_name, s.phone AS supplier_phone,
               s.email AS supplier_email
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
        WHERE p.product_id = %s
    """, (product_id,))

    if product is None:
        flash("That product no longer exists.", "error")
        return redirect(url_for("products.index"))

    history = query_all("""
        SELECT m.*, u.full_name AS user_name
        FROM stock_movements m
        LEFT JOIN users u ON u.user_id = m.user_id
        WHERE m.product_id = %s
        ORDER BY m.created_at DESC, m.movement_id DESC
        LIMIT 25
    """, (product_id,))

    return render_template("products/view.html", product=product, history=history)


# ----------------------------------------------------------------
# CREATE
# ----------------------------------------------------------------
@products_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    categories, suppliers = _lookups()

    if request.method == "POST":
        values, errors = _validate(request.form)

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("products/form.html",
                                   product=values, categories=categories,
                                   suppliers=suppliers, mode="create")

        new_id = execute("""
            INSERT INTO products
                (sku, name, category_id, supplier_id, unit_price,
                 quantity, reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (values["sku"], values["name"], values["category_id"],
              values["supplier_id"], values["unit_price"],
              values["quantity"], values["reorder_level"]))

        # Opening stock is a real stock movement, so it is recorded as
        # one. Without this the audit trail would start with a gap.
        if values["quantity"] > 0:
            execute("""
                INSERT INTO stock_movements
                    (product_id, user_id, movement_type, quantity, note)
                VALUES (%s, %s, 'IN', %s, 'Opening stock on product creation')
            """, (new_id, session["user_id"], values["quantity"]))

        flash(f"{values['name']} added to the catalogue.", "success")
        return redirect(url_for("products.view", product_id=new_id))

    blank = {"sku": "", "name": "", "category_id": None, "supplier_id": None,
             "unit_price": "", "quantity": 0, "reorder_level": 10}
    return render_template("products/form.html", product=blank,
                           categories=categories, suppliers=suppliers,
                           mode="create")


# ----------------------------------------------------------------
# UPDATE
# ----------------------------------------------------------------
@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(product_id):
    product = query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if product is None:
        flash("That product no longer exists.", "error")
        return redirect(url_for("products.index"))

    categories, suppliers = _lookups()

    if request.method == "POST":
        values, errors = _validate(request.form, product_id=product_id)

        if errors:
            for message in errors:
                flash(message, "error")
            values["product_id"] = product_id
            return render_template("products/form.html", product=values,
                                   categories=categories, suppliers=suppliers,
                                   mode="edit")

        previous_quantity = product["quantity"]

        execute("""
            UPDATE products
            SET sku = %s, name = %s, category_id = %s, supplier_id = %s,
                unit_price = %s, quantity = %s, reorder_level = %s
            WHERE product_id = %s
        """, (values["sku"], values["name"], values["category_id"],
              values["supplier_id"], values["unit_price"],
              values["quantity"], values["reorder_level"], product_id))

        # If the edit changed the stock figure, log the difference as
        # an adjustment so products.quantity and the movement history
        # never disagree.
        difference = values["quantity"] - previous_quantity
        if difference != 0:
            execute("""
                INSERT INTO stock_movements
                    (product_id, user_id, movement_type, quantity, note)
                VALUES (%s, %s, 'ADJUST', %s, 'Quantity corrected on the product form')
            """, (product_id, session["user_id"], difference))

        flash(f"{values['name']} updated.", "success")
        return redirect(url_for("products.view", product_id=product_id))

    return render_template("products/form.html", product=product,
                           categories=categories, suppliers=suppliers,
                           mode="edit")


# ----------------------------------------------------------------
# DELETE
# ----------------------------------------------------------------
@products_bp.route("/<int:product_id>/delete", methods=["POST"])
@admin_required
def delete(product_id):
    # POST only. A delete behind a GET link can be triggered by
    # anything that follows links, including a browser prefetching one.
    product = query_one("SELECT name FROM products WHERE product_id = %s", (product_id,))
    if product is None:
        flash("That product no longer exists.", "error")
        return redirect(url_for("products.index"))

    # stock_movements has ON DELETE CASCADE, so the history goes too.
    execute("DELETE FROM products WHERE product_id = %s", (product_id,))
    flash(f"{product['name']} removed from the catalogue.", "success")
    return redirect(url_for("products.index"))
