BEGIN TRANSACTION;

-- ==========================
-- USERS
-- ==========================
INSERT INTO users (username, password, fullname, role)
VALUES 
('admin@marine.com', 'admin123', 'Admin Marine', 'admin'),
('vendor@marine.com', 'vendor123', 'Vendor One', 'vendor'),
('consumer@marine.com', 'consumer123', 'Janelle', 'consumer');

-- ==========================
-- PRODUCTS
-- ==========================
INSERT INTO products (name, price, quantity, description, image_path, vendor_id)
VALUES
('Bangus', 180.0, 20, 'Fresh bangus from local farms', 'uploads/bangus.jpg', 2),
('Tilapia', 140.0, 10, 'Locally caught tilapia', 'uploads/tilapia.jpg', 2),
('Galunggong', 120.0, 25, 'Small pelagic fish', 'uploads/galunggong.jpg', 2),
('Shrimp', 350.0, 5, 'Fresh shrimp packs', 'uploads/shrimp.jpg', 2),
('Crab', 420.0, 2, 'Fresh crab per kg', 'uploads/crab.jpg', 2);

-- ==========================
-- SAMPLE CART FOR CONSUMER (buyer_id = 3)
-- ==========================
INSERT INTO cart (buyer_id) VALUES (3);

-- Add cart items
-- Use price_each = snapshot price at the time
INSERT INTO cart_items (cart_id, product_id, quantity, price_each, subtotal)
VALUES
(1, 1, 1, 180.0, 180.0),
(1, 3, 2, 120.0, 240.0);

-- ==========================
-- SAMPLE ORDERS
-- ==========================
INSERT INTO orders (buyer_id, status)
VALUES 
(3, 'Pending'),
(3, 'Delivered');

-- Order 1 items
INSERT INTO order_items (order_id, product_id, quantity, price_each, subtotal)
VALUES 
(1, 1, 2, 180.0, 360.0);

-- Order 2 items
INSERT INTO order_items (order_id, product_id, quantity, price_each, subtotal)
VALUES 
(2, 1, 1, 180.0, 180.0);

-- ==========================
-- PAYMENTS
-- ==========================
INSERT INTO payments (order_id, amount_paid, payment_method, payment_status)
VALUES 
(1, 360.0, 'GCash', 'Completed'),
(2, 180.0, 'COD', 'Pending');

COMMIT;
