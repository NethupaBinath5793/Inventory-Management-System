"""
Reports.

Three read-only views over the same data, plus CSV export so the
figures can be opened in Excel. Nothing here writes to the database.
"""

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, Response

from db import query_all, query_one
from auth_helpers import login_required

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/")
@login_required
def index():
    return render_template("reports/index.html")


# ----------------------------------------------------------------
# Low stock - what needs ordering
# ----------------------------------------------------------------
@reports_bp.route("/low-stock")
@login_required
def low_stock():
    items = query_all("""
        SELECT p.product_id, p.sku, p.name, p.quantity, p.reorder_level,
               p.unit_price,
               (p.reorder_level - p.quantity) AS shortfall,
               c.name AS category_name,
               s.name AS supplier_name, s.phone AS supplier_phone
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
        WHERE p.quantity <= p.reorder_level
        ORDER BY shortfall DESC, p.name
    """)

    # Rough cost of bringing everything back up to its reorder level.
    restock_cost = sum(
        max(row["shortfall"], 0) * float(row["unit_price"]) for row in items
    )

    return render_template("reports/low_stock.html",
                           items=items, restock_cost=restock_cost)


# ----------------------------------------------------------------
# Valuation - what the stock is worth, by category
# ----------------------------------------------------------------
@reports_bp.route("/valuation")
@login_required
def valuation():
    rows = query_all("""
        SELECT COALESCE(c.name, 'Uncategorised')       AS category_name,
               COUNT(p.product_id)                      AS product_count,
               COALESCE(SUM(p.quantity), 0)             AS units,
               COALESCE(SUM(p.quantity * p.unit_price), 0) AS value
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        GROUP BY c.category_id, c.name
        ORDER BY value DESC
    """)

    grand_total = sum(float(row["value"]) for row in rows)

    # Share of total value, worked out here so the template only prints.
    for row in rows:
        row["share"] = round(float(row["value"]) / grand_total * 100, 1) \
            if grand_total else 0

    top_items = query_all("""
        SELECT p.sku, p.name, p.quantity, p.unit_price,
               (p.quantity * p.unit_price) AS line_value,
               c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        ORDER BY line_value DESC
        LIMIT 10
    """)

    return render_template("reports/valuation.html", rows=rows,
                           grand_total=grand_total, top_items=top_items)


# ----------------------------------------------------------------
# Movement history over a date range
# ----------------------------------------------------------------
def _date_range():
    """Read from/to from the query string, defaulting to the last 30 days."""
    today = datetime.now().date()
    default_from = today - timedelta(days=30)

    def parse(value, fallback):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return fallback

    date_from = parse(request.args.get("from"), default_from)
    date_to = parse(request.args.get("to"), today)

    # A backwards range returns nothing and looks like a bug, so swap it.
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    return date_from, date_to


@reports_bp.route("/movements")
@login_required
def movements():
    date_from, date_to = _date_range()

    # BETWEEN on a DATETIME column would miss everything logged after
    # midnight on the closing day, so the upper bound is the next day.
    params = (date_from, date_to + timedelta(days=1))

    summary = query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN movement_type = 'IN'  THEN quantity END), 0) AS total_in,
            COALESCE(SUM(CASE WHEN movement_type = 'OUT' THEN quantity END), 0) AS total_out,
            COUNT(*) AS movement_count
        FROM stock_movements
        WHERE created_at >= %s AND created_at < %s
    """, params)

    rows = query_all("""
        SELECT m.*, p.sku, p.name AS product_name, u.full_name AS user_name
        FROM stock_movements m
        JOIN products p ON p.product_id = m.product_id
        LEFT JOIN users u ON u.user_id = m.user_id
        WHERE m.created_at >= %s AND m.created_at < %s
        ORDER BY m.created_at DESC, m.movement_id DESC
    """, params)

    busiest = query_all("""
        SELECT p.name AS product_name, p.sku,
               SUM(ABS(m.quantity)) AS units_moved,
               COUNT(*) AS movement_count
        FROM stock_movements m
        JOIN products p ON p.product_id = m.product_id
        WHERE m.created_at >= %s AND m.created_at < %s
        GROUP BY p.product_id, p.name, p.sku
        ORDER BY units_moved DESC
        LIMIT 5
    """, params)

    return render_template("reports/movements.html",
                           rows=rows, summary=summary, busiest=busiest,
                           date_from=date_from, date_to=date_to)


# ----------------------------------------------------------------
# CSV export
# ----------------------------------------------------------------
@reports_bp.route("/export/<report>")
@login_required
def export(report):
    """
    Build a CSV in memory and send it as a download.

    io.StringIO lets the csv module write to a string instead of a
    file, so nothing is ever saved to disk on the server.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if report == "low-stock":
        writer.writerow(["SKU", "Product", "Category", "In stock",
                         "Reorder level", "Shortfall", "Supplier"])
        for row in query_all("""
            SELECT p.sku, p.name, p.quantity, p.reorder_level,
                   (p.reorder_level - p.quantity) AS shortfall,
                   c.name AS category_name, s.name AS supplier_name
            FROM products p
            LEFT JOIN categories c ON c.category_id = p.category_id
            LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
            WHERE p.quantity <= p.reorder_level
            ORDER BY shortfall DESC
        """):
            writer.writerow([row["sku"], row["name"],
                             row["category_name"] or "Uncategorised",
                             row["quantity"], row["reorder_level"],
                             row["shortfall"], row["supplier_name"] or "-"])
        filename = "low_stock_report.csv"

    elif report == "inventory":
        writer.writerow(["SKU", "Product", "Category", "Supplier",
                         "Unit price", "Quantity", "Stock value"])
        for row in query_all("""
            SELECT p.sku, p.name, p.unit_price, p.quantity,
                   (p.quantity * p.unit_price) AS line_value,
                   c.name AS category_name, s.name AS supplier_name
            FROM products p
            LEFT JOIN categories c ON c.category_id = p.category_id
            LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
            ORDER BY p.name
        """):
            writer.writerow([row["sku"], row["name"],
                             row["category_name"] or "Uncategorised",
                             row["supplier_name"] or "-",
                             row["unit_price"], row["quantity"],
                             row["line_value"]])
        filename = "inventory_report.csv"

    elif report == "movements":
        date_from, date_to = _date_range()
        writer.writerow(["Date", "SKU", "Product", "Type",
                         "Quantity", "Recorded by", "Note"])
        for row in query_all("""
            SELECT m.created_at, m.movement_type, m.quantity, m.note,
                   p.sku, p.name AS product_name, u.full_name AS user_name
            FROM stock_movements m
            JOIN products p ON p.product_id = m.product_id
            LEFT JOIN users u ON u.user_id = m.user_id
            WHERE m.created_at >= %s AND m.created_at < %s
            ORDER BY m.created_at DESC
        """, (date_from, date_to + timedelta(days=1))):
            writer.writerow([
                row["created_at"].strftime("%Y-%m-%d %H:%M"),
                row["sku"], row["product_name"], row["movement_type"],
                row["quantity"], row["user_name"] or "-", row["note"] or ""])
        filename = f"movements_{date_from}_to_{date_to}.csv"

    else:
        return "Unknown report", 404

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
