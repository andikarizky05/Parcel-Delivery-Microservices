-- Seed User Service with sample data
\c user_service;

-- Insert sample customers
INSERT INTO users (id, email, password_hash, first_name, last_name, phone, user_type) VALUES
('customer-1', 'john.doe@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'John', 'Doe', '+1234567890', 'customer'),
('customer-2', 'jane.smith@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'Jane', 'Smith', '+1234567891', 'customer'),
('customer-3', 'bob.wilson@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'Bob', 'Wilson', '+1234567892', 'customer');

-- Insert sample drivers
INSERT INTO users (id, email, password_hash, first_name, last_name, phone, user_type) VALUES
('driver-1', 'mike.driver@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'Mike', 'Driver', '+1234567893', 'driver'),
('driver-2', 'sarah.delivery@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'Sarah', 'Delivery', '+1234567894', 'driver');

-- Insert sample admin
INSERT INTO users (id, email, password_hash, first_name, last_name, phone, user_type) VALUES
('admin-1', 'admin@parceldelivery.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/VcSAg/9qm', 'Admin', 'User', '+1234567895', 'admin');

-- Insert sample addresses
INSERT INTO addresses (id, user_id, address_type, street_address, city, state, postal_code, is_default) VALUES
('addr-1', 'customer-1', 'home', '123 Main St', 'New York', 'NY', '10001', true),
('addr-2', 'customer-2', 'home', '456 Oak Ave', 'Los Angeles', 'CA', '90210', true),
('addr-3', 'customer-3', 'home', '789 Pine Rd', 'Chicago', 'IL', '60601', true),
('addr-4', 'customer-1', 'work', '321 Business Blvd', 'New York', 'NY', '10002', false);

-- Seed Package Service with sample data
\c package_service;

INSERT INTO packages (id, tracking_number, sender_id, recipient_id, sender_address, recipient_address, weight, dimensions, status) VALUES
('pkg-1', 'PKG202412091234ABCD', 'customer-1', 'customer-2', '123 Main St, New York, NY 10001', '456 Oak Ave, Los Angeles, CA 90210', 2.5, '12x8x6', 'created'),
('pkg-2', 'PKG202412091235EFGH', 'customer-2', 'customer-3', '456 Oak Ave, Los Angeles, CA 90210', '789 Pine Rd, Chicago, IL 60601', 1.2, '8x6x4', 'in_transit'),
('pkg-3', 'PKG202412091236IJKL', 'customer-3', 'customer-1', '789 Pine Rd, Chicago, IL 60601', '123 Main St, New York, NY 10001', 3.8, '15x10x8', 'delivered');

-- Seed Delivery Service with sample data
\c delivery_service;

INSERT INTO deliveries (id, package_id, driver_id, pickup_address, delivery_address, status, estimated_delivery) VALUES
('del-1', 'pkg-1', 'driver-1', '123 Main St, New York, NY 10001', '456 Oak Ave, Los Angeles, CA 90210', 'assigned', '2024-12-15 14:00:00'),
('del-2', 'pkg-2', 'driver-2', '456 Oak Ave, Los Angeles, CA 90210', '789 Pine Rd, Chicago, IL 60601', 'in_transit', '2024-12-12 16:00:00'),
('del-3', 'pkg-3', 'driver-1', '789 Pine Rd, Chicago, IL 60601', '123 Main St, New York, NY 10001', 'delivered', '2024-12-10 10:00:00');

INSERT INTO delivery_routes (id, driver_id, route_name, deliveries, status) VALUES
('route-1', 'driver-1', 'East Coast Route', '["del-1", "del-3"]', 'active'),
('route-2', 'driver-2', 'Midwest Route', '["del-2"]', 'active');
