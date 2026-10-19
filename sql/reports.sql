-- reports on the raw (uncleaned) data
-- the output of each query is pasted above it

-- a) order totals
-- discount/100.0 (not 100) because sqlite does integer division otherwise
--   total_orders | total_revenue | avg_order_value
--   -------------+---------------+----------------
--   180          | 99860.20      | 554.78
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;


-- b) COUNT(*) vs COUNT(rating)
--   count_star | count_rating | unrated_orders
--   -----------+--------------+---------------
--   180        | 165          | 15
SELECT COUNT(*) AS count_star,
       COUNT(rating) AS count_rating,
       COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;


-- c) customers with no orders
-- c1) left join
--   customer_id | name
--   ------------+-------
--   C045        | Vihaan
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- c2) same check with NOT IN
--   customer_id | name
--   ------------+-------
--   C045        | Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);


-- d) cities with return rate above 20%
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


-- e) top customers by spend
-- customer_id is the tie-break so the order stays the same if two spends are equal
-- e1) top 5
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
JOIN products p   ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY cu.customer_id, cu.name
ORDER BY total_spend DESC, cu.customer_id ASC
LIMIT 5;

-- e2) ranks 3 to 5 (same as the last three rows of e1)
--   customer_id | name  | total_spend
--   ------------+-------+------------
--   C008        | Meera | 4564.60
--   C011        | Arjun | 4111.00
--   C042        | Sanya | 3785.00
SELECT cu.customer_id, cu.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p   ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY cu.customer_id, cu.name
ORDER BY total_spend DESC, cu.customer_id ASC
LIMIT 3 OFFSET 2;


-- f) revenue by category (three-table join)
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
JOIN products p   ON o.product_id  = p.product_id
JOIN customers cu ON o.customer_id = cu.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;


-- g) names starting with A (10 rows)
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


-- h) distinct acquisition sources
--   acquisition_source
--   ------------------
--   Ad
--   Organic
--   Referral
--   Social
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;


-- i) loyalty tier
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

--   loyalty_tier | customers
--   -------------+----------
--   Gold         | 28
--   Silver       | 17
SELECT loyalty_tier, COUNT(*) AS customers
FROM customers
GROUP BY loyalty_tier
ORDER BY loyalty_tier;
