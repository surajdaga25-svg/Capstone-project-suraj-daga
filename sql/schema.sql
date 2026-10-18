-- Mamaearth Returns & Growth Intelligence Pipeline
-- Part 1, Task 1: relational schema (SQLite-compatible)

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id        VARCHAR(10) PRIMARY KEY,
    name               VARCHAR(50) NOT NULL,
    city               VARCHAR(50) NOT NULL,
    city_tier          INT NOT NULL,
    signup_date        DATE NOT NULL,
    acquisition_source VARCHAR(20) NOT NULL
);

CREATE TABLE products (
    product_id   VARCHAR(10) PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category     VARCHAR(30) NOT NULL,
    price        DECIMAL(10,2) NOT NULL
);

-- discount_pct and rating deliberately have no NOT NULL:
-- a missing promo code / missing rating is a legitimate NULL, not an error.
CREATE TABLE orders (
    order_id       VARCHAR(10) PRIMARY KEY,
    customer_id    VARCHAR(10) NOT NULL,
    product_id     VARCHAR(10) NOT NULL,
    order_date     DATE NOT NULL,
    quantity       INT NOT NULL,
    discount_pct   INT,
    payment_method VARCHAR(10) NOT NULL,
    rating         INT,
    returned       INT NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
);
