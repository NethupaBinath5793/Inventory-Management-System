"""
Dashboard - the landing page after sign in.

Everything here is a SELECT. The point of the page is to answer the
question a store manager actually walks in with: what is running out,
what has moved recently, and what is the stock worth.
"""

from flask import Blueprint, render_template

from db import query_all, query_one
from auth_helpers import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    # Headline numbers. COALESCE guards against SUM() returning NULL
    # when the table is empty, which would print "None" in the page.
    totals = query_one("""
        SELECT
            COUNT(*)                             AS product_count,
            COALESCE(SUM(quantity), 0)           AS units_in_stock,
            COALESCE(SUM(quantity * unit_price), 0) AS stock_value
        FROM products
    """)

    low_stock_count = query_one("""
        SELECT COUNT(*) AS n FROM products WHERE quantity <= reorder_level
    """)["n"]

    out_of_stock_count = query_one("""
        SELECT COUNT(*) AS n FROM products WHERE quantity = 0
    """)["n"]

    supplier_count = query_one("SELECT COUNT(*) AS n FROM suppliers")["n"]

    # The items that need reordering, worst first.
    low_stock_items = query_all("""
        SELECT p.product_id, p.sku, p.name, p.quantity, p.reorder_level,
               c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        WHERE p.quantity <= p.reorder_level
        ORDER BY (p.quantity - p.reorder_level) ASC, p.name ASC
        LIMIT 8
    """)

    recent_movements = query_all("""
        SELECT m.movement_id, m.movement_type, m.quantity, m.note, m.created_at,
               p.name AS product_name, p.sku,
               u.full_name AS user_name
        FROM stock_movements m
        JOIN products p ON p.product_id = m.product_id
        LEFT JOIN users u ON u.user_id = m.user_id
        ORDER BY m.created_at DESC, m.movement_id DESC
        LIMIT 8
    """)

    # Stock spread across categories, for the bar list on the page.
    by_category = query_all("""
        SELECT COALESCE(c.name, 'Uncategorised') AS category_name,
               COUNT(p.product_id)               AS product_count,
               COALESCE(SUM(p.quantity), 0)      AS units
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        GROUP BY c.category_id, c.name
        ORDER BY units DESC
    """)

    # Work out the widest bar so the template can scale the rest
    # against it. Doing the arithmetic here keeps the template simple.
    max_units = max([row["units"] for row in by_category], default=0) or 1
    for row in by_category:
        row["bar_percent"] = round(row["units"] / max_units * 100)

    return render_template(
        "dashboard.html",
        totals=totals,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        supplier_count=supplier_count,
        low_stock_items=low_stock_items,
        recent_movements=recent_movements,
        by_category=by_category,
    )
