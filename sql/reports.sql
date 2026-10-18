-- ===========================================================================
-- Part 1, Task 3: report queries (run against the RAW, uncleaned data)
-- Run order: sql/schema.sql -> sql/seed_data.sql -> sql/reports.sql
-- Each query is preceded by its exact output, pasted as a comment.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- a) Order totals (raw data)
-- Revenue per row = quantity * price * (1 - discount_pct/100); NULL discount treated as 0% via COALESCE.
-- NOTE: divide by 100.0, not 100 - SQLite integer division would turn discount/100 into 0 for every row.
-- ---------------------------------------------------------------------------
-- Output:
--   total_orders | total_revenue | avg_order_value
--   -------------+---------------+----------------
--   180          | 99860.20      | 554.78
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;


-- ---------------------------------------------------------------------------
-- b) COUNT(*) vs COUNT(column)
-- COUNT(*) counts every row; COUNT(rating) skips NULLs, so the difference = orders with no rating yet.
-- ---------------------------------------------------------------------------
-- Output:
--   count_star | count_rating | unrated_orders
--   -----------+--------------+---------------
--   180        | 165          | 15
SELECT COUNT(*) AS count_star,
       COUNT(rating) AS count_rating,
       COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;


-- ---------------------------------------------------------------------------
-- c) LEFT JOIN with a genuine zero-match row, cross-checked with NOT IN
-- Two independent queries must return the same customer.
-- ---------------------------------------------------------------------------
-- c1) LEFT JOIN + HAVING COUNT(order_id) = 0
-- Output:
--   customer_id | name
--   ------------+-------
--   C045        | Vihaan
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- c2) NOT IN confirmation
-- Output:
--   customer_id | name
--   ------------+-------
--   C045        | Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);


-- ---------------------------------------------------------------------------
-- d) GROUP BY + HAVING: cities with return rate above 20%
-- return_rate_pct = returned orders / total orders * 100, rounded to 1 decimal.
-- ---------------------------------------------------------------------------
-- Output:
--   city      | total_orders | returned_orders | return_rate_pct
--   ----------+--------------+-----------------+----------------
--   Jaipur    | 19           | 8               | 42.1
--   Lucknow   | 49           | 15              | 30.6
--   Bangalore | 33           | 8               | 24.2
SELECT cu.city,
       COUNT(*) AS total_orders,
       SUM(o.returned) AS returned_orders,
       ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY cu.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;


-- ---------------------------------------------------------------------------
-- e) Ranking with ORDER BY + LIMIT / OFFSET
-- Tie-break note: customer_id ASC makes the order deterministic when two customers have equal total_spend,
-- so LIMIT/OFFSET pages are stable and OFFSET 2 reliably lines up with ranks 3-5 of the top-5 query.
-- ---------------------------------------------------------------------------
-- e1) Top 5
-- Output:
--   customer_id | name    | total_spend
--   ------------+---------+------------
--   C043        | Reyansh | 12920.00
--   C026        | Isha    | 8371.60
--   C008        | Meera   | 4564.60
--   C011        | Arjun   | 4111.00
--   C042        | Sanya   | 3785.00
SELECT cu.customer_id, cu.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY cu.customer_id, cu.name
ORDER BY total_spend DESC, cu.customer_id ASC
LIMIT 5;

-- e2) Ranks 3-5 via LIMIT 3 OFFSET 2 (must equal the last three rows of e1)
-- Output:
--   customer_id | name  | total_spend
--   ------------+-------+------------
--   C008        | Meera | 4564.60
--   C011        | Arjun | 4111.00
--   C042        | Sanya | 3785.00
SELECT cu.customer_id, cu.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY cu.customer_id, cu.name
ORDER BY total_spend DESC, cu.customer_id ASC
LIMIT 3 OFFSET 2;


-- ---------------------------------------------------------------------------
-- f) Three-table JOIN with GROUP BY: revenue by category
-- customers is joined to confirm the three-way join compiles (Part 3 will need it); only orders+products affect the numbers.
-- ---------------------------------------------------------------------------
-- Output:
--   category     | order_count | category_revenue
--   -------------+-------------+-----------------
--   Haircare     | 54          | 44956.10
--   Skincare     | 60          | 27346.00
--   Babycare     | 30          | 16805.00
--   PersonalCare | 36          | 10753.10
SELECT p.category,
       COUNT(*) AS order_count,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;


-- ---------------------------------------------------------------------------
-- g) LIKE pattern match: customer names starting with 'A'
-- ---------------------------------------------------------------------------
-- Output:
--   customer_id | name
--   ------------+-------
--   C001        | Aarav
--   C003        | Aditi
--   C004        | Ananya
--   C011        | Arjun
--   C021        | Aryan
--   C030        | Anika
--   C031        | Aditya
--   C036        | Aisha
--   C041        | Ayaan
--   C044        | Aria
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;


-- ---------------------------------------------------------------------------
-- h) DISTINCT acquisition sources
-- ---------------------------------------------------------------------------
-- Output:
--   acquisition_source
--   ------------------
--   Ad
--   Organic
--   Referral
--   Social
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;


-- ---------------------------------------------------------------------------
-- i) ALTER TABLE + UPDATE with CASE
-- NOTE: ALTER TABLE ADD COLUMN fails if loyalty_tier already exists. To re-run this file from the top,
-- reload sql/schema.sql and sql/seed_data.sql first (schema.sql drops and recreates all tables).
-- ---------------------------------------------------------------------------
-- i1) Add column
-- Output: (no result set; statement executed, rows affected: n/a)
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

-- i2) Populate every row (no WHERE clause)
-- Output: (no result set; statement executed, rows affected: 45)
UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

-- i3) Verify
-- Output:
--   loyalty_tier | customers
--   -------------+----------
--   Gold         | 28
--   Silver       | 17
SELECT loyalty_tier, COUNT(*) AS customers
FROM customers
GROUP BY loyalty_tier
ORDER BY loyalty_tier;
