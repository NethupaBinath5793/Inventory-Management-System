# StockRoom — Inventory Management System

A web-based inventory and stock control system built with Python (Flask),
MySQL, HTML and CSS. Submitted for **PUSL2021 Computing Group Project**,
Referral Coursework (C1).

The system tracks products across categories and suppliers, records every
movement of stock in and out with a full audit trail, and produces reports
on what needs reordering and what the inventory is worth.

---

## Contents

1. [What it does](#what-it-does)
2. [Technologies used](#technologies-used)
3. [Setup on WAMP Server](#setup-on-wamp-server)
4. [Signing in](#signing-in)
5. [Project structure](#project-structure)
6. [Database design](#database-design)
7. [Design decisions worth knowing](#design-decisions-worth-knowing)
8. [Troubleshooting](#troubleshooting)

---

## What it does

**Products (full CRUD)**
- Create, view, update and delete products
- Search by name or SKU, filter by category and by stock level, sort any
  column, paginated 10 to a page
- Each product has a detail page showing its full movement history

**Stock movements**
- Record stock received, issued, or adjusted after a stock take
- Cannot issue more units than are actually held
- Every movement records who did it, when, and why

**Categories and suppliers (full CRUD)**
- Cannot be deleted while products still reference them

**User accounts (full CRUD, administrators only)**
- Two roles: administrator and store assistant
- Passwords stored as PBKDF2-SHA256 hashes
- Cannot delete the last administrator, or lock yourself out of your own account

**Reports**
- Low stock: what to reorder, from whom, and roughly what it will cost
- Valuation: stock value by category, plus highest-value products
- Movement history over any date range
- All three export to CSV

---

## Technologies used

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.8+ | Required by Flask; readable and quick to build in |
| Web framework | Flask 3.0 | Lightweight, no imposed structure, easy to explain route by route |
| Templating | Jinja2 (ships with Flask) | Template inheritance means the layout is written once |
| Database | MySQL / MariaDB (WAMP) | Relational data with real foreign key relationships |
| DB driver | PyMySQL 1.1 | Pure Python, so it installs with pip and needs no C compiler on Windows |
| Password hashing | Werkzeug (ships with Flask) | PBKDF2-SHA256, no extra dependency |
| Front end | Hand-written HTML5 and CSS3 | No Bootstrap, no CDN — the interface renders with no internet connection |

There are only **three** direct dependencies (Flask, PyMySQL, Werkzeug), and
no JavaScript framework. Everything in `static/css/style.css` was written by
hand for this project.

---

## Setup on WAMP Server

### 1. Start WAMP

Launch WAMP Server and wait for the tray icon to turn **green**. Amber means
one of the services has not started — usually Apache losing port 80 to
another program.

### 2. Create the database

Open **phpMyAdmin** at <http://localhost/phpmyadmin> (default login is user
`root` with an empty password).

- Click the **Import** tab
- **Choose File** → select `database/schema.sql` from this project
- Scroll down and click **Import**

You should see `inventory_db` appear in the left sidebar with five tables.
The script creates the database, all tables, and the sample data in one go.

### 3. Install Python and the dependencies

Python 3.8 or newer, from <https://www.python.org/downloads/>. On Windows,
tick **"Add Python to PATH"** on the first screen of the installer, or the
`python` command will not be found afterwards.

Then, in Command Prompt, from inside the project folder:

```bat
cd path\to\inventory_system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

The virtual environment is optional but keeps these packages separate from
anything else on your machine.

### 4. Check the database settings

Open `config.py`. The defaults match a fresh WAMP install:

```python
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""      # blank on a fresh WAMP install
MYSQL_DB = "inventory_db"
```

If you set a root password in phpMyAdmin, put it in `MYSQL_PASSWORD`.

### 5. Run it

```bat
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

To stop the server, press `Ctrl + C` in the Command Prompt window.

---

## Signing in

Two accounts are created by the SQL script:

| Role | Username | Password | Can do |
|---|---|---|---|
| Administrator | `admin` | `Admin@123` | Everything, including managing products, suppliers, categories and user accounts |
| Store assistant | `staff` | `Staff@123` | Record stock movements, view products, read and export reports |

**Before you submit**, change these. Run `python create_admin.py` to set your
own username and password, then delete the demo block at the bottom of
`templates/login.html`.

Signing in as `staff` is a good way to demonstrate role separation: the
administration links disappear from the sidebar, and typing `/users/` into
the address bar still redirects away, because the check is on the route
rather than on the link.

---

## Project structure

```
inventory_system/
│
├── app.py                  Application factory, filters, error handlers
├── config.py               Database credentials and app settings
├── db.py                   Connection handling and query helpers
├── auth_helpers.py         @login_required and @admin_required decorators
├── create_admin.py         Command line tool to create/reset an admin account
├── requirements.txt        Python dependencies
│
├── database/
│   └── schema.sql          Tables, keys, indexes and sample data
│
├── blueprints/             One module per feature area
│   ├── auth.py             Sign in and out
│   ├── dashboard.py        Summary figures
│   ├── products.py         Product CRUD, search, filter, sort, pagination
│   ├── categories.py       Category CRUD
│   ├── suppliers.py        Supplier CRUD
│   ├── movements.py        Stock in / out / adjust (transactional)
│   ├── users.py            Account management
│   └── reports.py          Three reports plus CSV export
│
├── templates/              Jinja2 templates, all extending base.html
│   ├── base.html           Sidebar, navigation, flash messages
│   ├── login.html
│   ├── dashboard.html
│   ├── error.html
│   ├── products/           list, form, view
│   ├── categories/         list, form
│   ├── suppliers/          list, form
│   ├── movements/          list, form
│   ├── users/              list, form
│   └── reports/            index, low_stock, valuation, movements
│
└── static/
    └── css/style.css       All styling, written by hand
```

Each blueprint is a self-contained feature. Adding a new area means adding
one file and registering it in `app.py`, not editing a file that already
does five other things.

---

## Database design

Five tables in third normal form.

```
categories ──┐
             ├──< products >──── stock_movements >──── users
suppliers ───┘
```

| Table | Holds | Key relationships |
|---|---|---|
| `users` | Accounts, hashed passwords, roles | Referenced by `stock_movements` |
| `categories` | Product groupings | One category → many products |
| `suppliers` | Who stock is bought from | One supplier → many products |
| `products` | The catalogue and live stock figure | Belongs to one category and one supplier |
| `stock_movements` | Audit trail of every change | Belongs to one product and one user |

**Why deletes behave differently in each direction**

- Deleting a **category or supplier** sets `products.category_id` to `NULL`
  rather than deleting the products — the stock is still physically there.
  The application blocks the delete anyway and tells you to reassign first,
  so the `NULL` case only ever happens if someone edits the database directly.
- Deleting a **product** cascades to its `stock_movements` — once the product
  is gone there is nothing left to audit.
- Deleting a **user** sets `stock_movements.user_id` to `NULL` — the movement
  still happened and must stay in the record, even though the account is gone.

**Why quantity lives in two places**

`products.quantity` is the live figure the whole application reads, and
`stock_movements` is the history that explains it. Keeping the running total
on the product avoids summing the entire history on every page load. The risk
is the two drifting apart, so every route that changes the quantity also
writes a movement — including the product edit form, which logs the
difference as an adjustment.

---

## Design decisions worth knowing

**SQL injection.** Every query uses parameter placeholders (`%s`), so values
are sent to MySQL separately from the query text and can never be executed as
SQL. The one place a value has to be built into the query string is the sort
column on the product list, since a column name cannot be a parameter — so
the requested column is checked against a fixed whitelist first
(`SORTABLE` in `blueprints/products.py`).

**Transactions.** Recording a stock movement changes two tables. Both
statements run on one connection and are committed together; if the second
fails, the first is rolled back. Without this a movement could be logged
without the stock figure moving, and the two would silently disagree
(`blueprints/movements.py`).

**Deletes are POST, never GET.** A delete behind an `<a href>` can be
triggered by anything that follows links, including a browser prefetching
one. Every delete is a form with `method="post"` plus a confirmation dialog.

**Authorisation is on the route, not the link.** Hiding a button in the
sidebar is presentation; `@admin_required` on the route is the actual
control. Both are used, but only the second one stops someone typing the URL.

**Login errors are deliberately vague.** "Username or password is incorrect"
is shown for both an unknown user and a wrong password. Saying which half was
right would let someone discover valid usernames.

**No external front-end dependencies.** No Bootstrap, no Google Fonts, no
CDN. The system works identically on a machine with no internet connection,
which matters when demonstrating it.

---

## Troubleshooting

**`Can't connect to MySQL server on 'localhost'`**
WAMP is not running, or MySQL did not start. Check the tray icon is green.

**`Access denied for user 'root'@'localhost'`**
`MYSQL_PASSWORD` in `config.py` does not match your MySQL root password. On
a fresh WAMP install the password is blank (`""`).

**`Unknown database 'inventory_db'`**
`schema.sql` has not been imported. Go back to step 2.

**`ModuleNotFoundError: No module named 'flask'`**
Dependencies not installed, or the virtual environment is not active. Run
`venv\Scripts\activate` then `pip install -r requirements.txt`.

**`'python' is not recognized`**
Python is not on your PATH. Reinstall it and tick "Add Python to PATH", or
use the full path to `python.exe`.

**Port 5000 is already in use**
Change the last line of `app.py` to a different port, e.g. `port=5001`.

**The page loads but has no styling**
A stale cached stylesheet. Hard refresh with `Ctrl + F5`.
