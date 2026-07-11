-- Run this once against your Postgres database to create the schema.
-- The tables are also auto-created by the FastAPI app on startup,
-- but having this file shows the schema clearly (good for explaining
-- in interviews / vivas).

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artworks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(50) DEFAULT 'other',
    image_path VARCHAR(255) NOT NULL,
    artist_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stock INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    buyer_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    artwork_id INT NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    razorpay_order_id VARCHAR(100) UNIQUE NOT NULL,
    razorpay_payment_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | paid | failed
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);