-- ============================================================
--  StockRoom - Inventory Management System
--  Database schema and seed data
--  Target: MySQL / MariaDB (WAMP Server, imported via phpMyAdmin)
-- ============================================================

CREATE DATABASE IF NOT EXISTS inventory_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE inventory_db;

-- Dropped child-first so foreign keys never block the drop.
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS users;


-- ------------------------------------------------------------
-- 1. users
--    Two roles. 'admin' manages the catalogue and other users,
--    'staff' records stock movements and reads reports.
-- ------------------------------------------------------------
CREATE TABLE users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 2. categories
-- ------------------------------------------------------------
CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255) DEFAULT NULL
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 3. suppliers
-- ------------------------------------------------------------
CREATE TABLE suppliers (
    supplier_id    INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(120) NOT NULL,
    contact_person VARCHAR(100) DEFAULT NULL,
    phone          VARCHAR(30)  DEFAULT NULL,
    email          VARCHAR(120) DEFAULT NULL,
    address        VARCHAR(255) DEFAULT NULL
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 4. products
--    quantity is the live stock figure. It is never edited by
--    hand after creation - it only changes through a row in
--    stock_movements, so the two always agree.
--
--    ON DELETE SET NULL: deleting a category or supplier must
--    not delete the products underneath it. The product stays,
--    its link is cleared, and it shows as "Uncategorised".
-- ------------------------------------------------------------
CREATE TABLE products (
    product_id    INT AUTO_INCREMENT PRIMARY KEY,
    sku           VARCHAR(40)  NOT NULL UNIQUE,
    name          VARCHAR(150) NOT NULL,
    category_id   INT          DEFAULT NULL,
    supplier_id   INT          DEFAULT NULL,
    unit_price    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    quantity      INT          NOT NULL DEFAULT 0,
    reorder_level INT          NOT NULL DEFAULT 10,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_product_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_product_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        ON DELETE SET NULL,

    INDEX idx_product_name (name),
    INDEX idx_product_category (category_id)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 5. stock_movements
--    The audit trail. Every change to products.quantity leaves
--    a row here saying who did it, when, and why.
--
--    ON DELETE CASCADE from products: if a product is removed,
--    its history goes with it (there is nothing left to audit).
--    ON DELETE SET NULL from users: if a user account is
--    removed, the movement record survives without an owner.
-- ------------------------------------------------------------
CREATE TABLE stock_movements (
    movement_id   INT AUTO_INCREMENT PRIMARY KEY,
    product_id    INT NOT NULL,
    user_id       INT DEFAULT NULL,
    movement_type ENUM('IN', 'OUT', 'ADJUST') NOT NULL,
    quantity      INT NOT NULL,
    note          VARCHAR(255) DEFAULT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_movement_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_movement_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE SET NULL,

    INDEX idx_movement_date (created_at)
) ENGINE=InnoDB;


-- ============================================================
--  SEED DATA
-- ============================================================

-- Passwords below are PBKDF2-SHA256 hashes, not plain text.
--   admin / Admin@123
--   staff / Staff@123
-- Change these before any real use. To create your own hash,
-- run:  python create_admin.py
INSERT INTO users (username, password_hash, full_name, role) VALUES
('admin', 'pbkdf2:sha256:600000$KaJU5FCJJt1S7DhG$c488e8ce5ce43225d8b91bd0f963b9779b43f19f2b0a835ccc33d2b20a1031db', 'System Administrator', 'admin'),
('staff', 'pbkdf2:sha256:600000$oB9g2ftCj1cxtI7C$a6c6f6f4b60d290d176401231c9d51569ae0d5e4568bb949734c9fa1897a1508', 'Store Assistant', 'staff');

INSERT INTO categories (name, description) VALUES
('Laptops',      'Portable computers and notebooks'),
('Peripherals',  'Keyboards, mice, webcams and docks'),
('Storage',      'Hard drives, SSDs and memory cards'),
('Networking',   'Routers, switches and cabling'),
('Accessories',  'Cases, cables and adapters');

INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES
('Metro Tech Distributors', 'Nadeesha Perera', '011-2345678', 'sales@metrotech.lk',  '14 Galle Road, Colombo 03'),
('Island Computer Supplies', 'Ruwan Silva',     '031-2233445', 'orders@islandcs.lk',  '82 Main Street, Negombo'),
('Pinnacle Hardware',        'Ayesha Fernando', '081-4567890', 'info@pinnacle.lk',    '5 Temple Road, Kandy');

INSERT INTO products (sku, name, category_id, supplier_id, unit_price, quantity, reorder_level) VALUES
('LPT-1001', 'Acer Aspire 5 15.6" Core i5',    1, 1, 185000.00, 12,  5),
('LPT-1002', 'Lenovo IdeaPad Slim 3 Ryzen 5',  1, 1, 162500.00,  3,  5),
('LPT-1003', 'HP Pavilion 14 Core i7',         1, 3, 249000.00,  7,  4),
('PER-2001', 'Logitech K380 Wireless Keyboard',2, 2,   9800.00, 45, 20),
('PER-2002', 'Logitech M170 Wireless Mouse',   2, 2,   3250.00, 18, 25),
('PER-2003', 'Logitech C920 HD Webcam',        2, 1,  22400.00,  9, 10),
('STG-3001', 'Samsung 980 NVMe SSD 500GB',     3, 1,  18750.00, 32, 15),
('STG-3002', 'Seagate Barracuda 2TB HDD',      3, 3,  21900.00,  6, 10),
('STG-3003', 'SanDisk Ultra 128GB microSD',    3, 2,   4600.00, 60, 30),
('NET-4001', 'TP-Link Archer C6 Router',       4, 2,  11500.00, 14,  8),
('NET-4002', 'D-Link 8-Port Gigabit Switch',   4, 3,   9750.00,  4,  6),
('NET-4003', 'Cat6 Ethernet Cable 305m Box',   4, 2,  32000.00,  2,  3),
('ACC-5001', 'Laptop Backpack 15.6"',          5, 2,   5400.00, 27, 12),
('ACC-5002', 'USB-C to HDMI Adapter',          5, 1,   4250.00, 11, 15),
('ACC-5003', 'Universal Laptop Charger 65W',   5, 3,   7800.00, 19, 10);

-- A short history so the dashboard and reports are not empty on
-- first run. These are illustrative and do not recalculate the
-- quantities above.
INSERT INTO stock_movements (product_id, user_id, movement_type, quantity, note, created_at) VALUES
(1,  1, 'IN',     15, 'Opening stock',                DATE_SUB(NOW(), INTERVAL 21 DAY)),
(4,  1, 'IN',     50, 'Opening stock',                DATE_SUB(NOW(), INTERVAL 21 DAY)),
(7,  1, 'IN',     40, 'Opening stock',                DATE_SUB(NOW(), INTERVAL 21 DAY)),
(1,  2, 'OUT',     3, 'Sold - invoice INV-0431',      DATE_SUB(NOW(), INTERVAL 14 DAY)),
(4,  2, 'OUT',     5, 'Sold - invoice INV-0433',      DATE_SUB(NOW(), INTERVAL 12 DAY)),
(2,  1, 'IN',      8, 'Purchase order PO-118',        DATE_SUB(NOW(), INTERVAL 10 DAY)),
(2,  2, 'OUT',     5, 'Sold - invoice INV-0440',      DATE_SUB(NOW(), INTERVAL 6 DAY)),
(7,  2, 'OUT',     8, 'Sold - invoice INV-0442',      DATE_SUB(NOW(), INTERVAL 5 DAY)),
(8,  2, 'OUT',     4, 'Sold - invoice INV-0445',      DATE_SUB(NOW(), INTERVAL 3 DAY)),
(11, 1, 'ADJUST', -1, 'Damaged unit written off',     DATE_SUB(NOW(), INTERVAL 2 DAY)),
(9,  2, 'IN',     30, 'Purchase order PO-121',        DATE_SUB(NOW(), INTERVAL 1 DAY));
