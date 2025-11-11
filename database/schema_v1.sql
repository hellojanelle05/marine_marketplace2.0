BEGIN TRANSACTION;

-- ==============================
-- USERS TABLE
-- ==============================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    fullname TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ==============================
-- PRODUCTS TABLE
-- ==============================
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    image_path TEXT,
    vendor_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vendor_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ==============================
-- ORDERS TABLE
-- ==============================
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ==============================
-- ORDER ITEMS TABLE
-- ==============================
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    price_each REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- ==============================
-- PAYMENTS TABLE
-- ==============================
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    amount_paid REAL NOT NULL,
    payment_method TEXT CHECK(payment_method IN ('GCash','Credit Card','Cash on Delivery','COD')),
    payment_status TEXT DEFAULT 'Pending',
    payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

COMMIT;

-- ==============================
-- SAMPLE DATA
-- ==============================
INSERT INTO users (username, password, fullname, role)
VALUES 
('admin@marine.com', 'admin123', 'Admin Marine', 'admin'),
('vendor@marine.com', 'vendor123', 'Vendor One', 'vendor'),
('consumer@marine.com', 'consumer123', 'Janelle', 'consumer');

INSERT INTO products (name, price, quantity, description, image_path, vendor_id)
VALUES
('Bangus', 180.0, 20, 'Fresh bangus from local farms', 'uploads/bangus.jpg', 2),
('Tilapia', 140.0, 10, 'Locally caught tilapia', 'uploads/tilapia.jpg', 2),
('Galunggong', 120.0, 25, 'Small pelagic fish', 'uploads/galunggong.jpg', 2),
('Shrimp', 350.0, 5, 'Fresh shrimp packs', 'uploads/shrimp.jpg', 2),
('Crab', 420.0, 2, 'Fresh crab per kg', 'uploads/crab.jpg', 2);

INSERT INTO orders (buyer_id, status)
VALUES (3, 'Pending'), (3, 'Delivered');

INSERT INTO order_items (order_id, product_id, quantity, price_each, subtotal)
VALUES (1, 1, 2, 180.0, 360.0),
       (2, 1, 1, 180.0, 180.0);

INSERT INTO payments (order_id, amount_paid, payment_method, payment_status)
VALUES (1, 360.0, 'GCash', 'Completed'),
       (2, 180.0, 'COD', 'Pending');
