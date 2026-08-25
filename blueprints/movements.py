"""
Stock movements - recording goods in and goods out.

This is the one place in the application where two tables have to
change together: the movement is inserted and the product's quantity
is adjusted. If only one of those succeeded, the stock figure would
stop matching its own history. So both statements run inside a single
transaction, committed together or rolled back together.

Both roles can record movements - a store assistant handling deliveries
is exactly who this screen is for.
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)

from db import query_all, query_one, get_db
from auth_helpers import login_required

movements_bp = Blueprint("movements", __name__)


@movements_bp.route("/")
@login_required
def index():
    movement_type = request.args.get("type", "")
    search = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 20

    conditions = []
    params = []

    if movement_type in ("IN", "OUT", "ADJUST"):
        conditions.append("m.movement_type = %s")
        params.append(movement_type)

    if search:
        conditions.append("(p.name LIKE %s OR p.sku LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query_one(f"""
        SELECT COUNT(*) AS n
        FROM stock_movements m
        JOIN products p ON p.product_id = m.product_id
        {where}
    """, params)["n"]

    total_pages = max(1, -(-total // per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    movements = query_all(f"""
        SELECT m.*, p.name AS product_name, p.sku,
               u.full_name AS user_name
        FROM stock_movements m
        JOIN products p ON p.product_id = m.product_id
        LEFT JOIN users u ON u.user_id = m.user_id
        {where}
        ORDER BY m.created_at DESC, m.movement_id DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return render_template("movements/list.html",
                           movements=movements, movement_type=movement_type,
                           search=search, page=page, total_pages=total_pages,
                           total=total)


@movements_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    products = query_all("""
        SELECT product_id, sku, name, quantity
        FROM products ORDER BY name
    """)

    # Allow linking straight from a product page: /movements/new?product=7
    preselected = request.args.get("product", "")

    if request.method == "POST":
        product_id = request.form.get("product_id", "")
        movement_type = request.form.get("movement_type", "")
        quantity_raw = request.form.get("quantity", "").strip()
        note = request.form.get("note", "").strip()

        errors = []

        product = None
        if not product_id:
            errors.append("Choose a product.")
        else:
            product = query_one(
                "SELECT product_id, name, quantity FROM products WHERE product_id = %s",
                (product_id,))
            if product is None:
                errors.append("That product no longer exists.")

        if movement_type not in ("IN", "OUT", "ADJUST"):
            errors.append("Choose a movement type.")

        quantity = 0
        try:
            quantity = int(quantity_raw)
        except ValueError:
            errors.append("Quantity must be a whole number.")
        else:
            if movement_type in ("IN", "OUT") and quantity <= 0:
                errors.append("Quantity must be greater than zero.")
            if movement_type == "ADJUST" and quantity == 0:
                errors.append("An adjustment of zero would change nothing.")

        # The rule that matters: you cannot take out more than is there.
        # Without this check the quantity column goes negative and every
        # report downstream becomes wrong.
        if not errors and movement_type == "OUT" and quantity > product["quantity"]:
            errors.append(
                f"Only {product['quantity']} unit(s) of {product['name']} "
                f"are in stock. Reduce the quantity or record a delivery first."
            )

        if not errors and movement_type == "ADJUST":
            if product["quantity"] + quantity < 0:
                errors.append("That adjustment would put stock below zero.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("movements/form.html", products=products,
                                   preselected=product_id,
                                   form=request.form)

        # How the product's quantity should change.
        delta = quantity if movement_type == "IN" else \
                -quantity if movement_type == "OUT" else quantity

        # --- The transaction -------------------------------------
        # Both statements share one connection and one commit. If the
        # second one fails, the first is rolled back too, so a movement
        # is never recorded without the stock figure moving with it.
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO stock_movements
                        (product_id, user_id, movement_type, quantity, note)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product["product_id"], session["user_id"],
                      movement_type, quantity, note or None))

                cursor.execute("""
                    UPDATE products SET quantity = quantity + %s
                    WHERE product_id = %s
                """, (delta, product["product_id"]))
            connection.commit()
        except Exception:
            connection.rollback()
            flash("The movement could not be saved. Nothing was changed.", "error")
            return render_template("movements/form.html", products=products,
                                   preselected=product_id, form=request.form)

        label = {"IN": "Received", "OUT": "Issued", "ADJUST": "Adjusted"}[movement_type]
        flash(f"{label} {abs(quantity)} x {product['name']}.", "success")
        return redirect(url_for("products.view", product_id=product["product_id"]))

    return render_template("movements/form.html", products=products,
                           preselected=preselected, form={})
