DROP TABLE IF EXISTS clickhouse.analytics.sales_enriched;

CREATE TABLE clickhouse.analytics.sales_enriched WITH (engine = 'MergeTree') AS
SELECT f.source_row_id, f.sale_quantity, f.sale_total_price,
       c.email AS customer_email, c.first_name AS customer_first_name,
       c.last_name AS customer_last_name, c.country AS customer_country,
       p.product_name, p.product_category, p.product_price, p.product_rating, p.product_reviews,
       st.store_name, st.store_country, st.store_city,
       sp.supplier_name, sp.supplier_country, d.full_date
FROM clickhouse.analytics.fact_sales f
JOIN clickhouse.analytics.dim_customer c ON f.customer_key = c.customer_key
JOIN clickhouse.analytics.dim_product p ON f.product_key = p.product_key
JOIN clickhouse.analytics.dim_store st ON f.store_key = st.store_key
JOIN clickhouse.analytics.dim_supplier sp ON f.supplier_key = sp.supplier_key
JOIN clickhouse.analytics.dim_date d ON f.date_key = d.date_key;

DROP TABLE IF EXISTS clickhouse.analytics.report_products;

CREATE TABLE clickhouse.analytics.report_products WITH (engine = 'MergeTree') AS
WITH products AS (
    SELECT product_name, count(*) AS sales_count, sum(sale_quantity) AS units,
           sum(sale_total_price) AS revenue, avg(CAST(product_rating AS double)) AS avg_rating,
           sum(product_reviews) AS review_count
    FROM clickhouse.analytics.sales_enriched GROUP BY product_name
)
SELECT 'product' AS row_type, product_name, '' AS product_category,
       sales_count, units, revenue, avg_rating, review_count,
       row_number() OVER (ORDER BY units DESC, revenue DESC, product_name) AS sales_rank
FROM products
UNION ALL
SELECT 'category', '', product_category, count(*), sum(sale_quantity), sum(sale_total_price),
       CAST(NULL AS double), CAST(NULL AS bigint), CAST(NULL AS bigint)
FROM clickhouse.analytics.sales_enriched GROUP BY product_category;

DROP TABLE IF EXISTS clickhouse.analytics.report_customers;

CREATE TABLE clickhouse.analytics.report_customers WITH (engine = 'MergeTree') AS
WITH customers AS (
    SELECT customer_email, max(concat_ws(' ', customer_first_name, customer_last_name)) AS customer_name,
           count(*) AS sales_count, sum(sale_quantity) AS units, sum(sale_total_price) AS revenue,
           avg(CAST(sale_total_price AS double)) AS avg_check
    FROM clickhouse.analytics.sales_enriched GROUP BY customer_email
)
SELECT 'customer' AS row_type, customer_email, customer_name, '' AS customer_country,
       CAST(1 AS bigint) AS customer_count, sales_count, units, revenue, avg_check,
       row_number() OVER (ORDER BY revenue DESC, customer_email) AS spending_rank
FROM customers
UNION ALL
SELECT 'country', '', '', customer_country, count(DISTINCT customer_email),
       count(*), sum(sale_quantity), sum(sale_total_price), avg(CAST(sale_total_price AS double)),
       CAST(NULL AS bigint)
FROM clickhouse.analytics.sales_enriched GROUP BY customer_country;

DROP TABLE IF EXISTS clickhouse.analytics.report_time;

CREATE TABLE clickhouse.analytics.report_time WITH (engine = 'MergeTree') AS
WITH bounds AS (
    SELECT date_trunc('month', min(full_date)) AS lo, date_trunc('month', max(full_date)) AS hi
    FROM clickhouse.analytics.sales_enriched
), calendar AS (
    SELECT month_start FROM bounds CROSS JOIN UNNEST(sequence(lo, hi, INTERVAL '1' MONTH)) AS t(month_start)
), monthly AS (
    SELECT date_trunc('month', full_date) AS month_start, count(*) AS sales_count,
           sum(sale_quantity) AS units, sum(sale_total_price) AS revenue
    FROM clickhouse.analytics.sales_enriched GROUP BY date_trunc('month', full_date)
), filled AS (
    SELECT 'month' AS row_type, year(c.month_start) AS year, month(c.month_start) AS month,
           substr(CAST(c.month_start AS varchar), 1, 7) AS period,
           coalesce(m.sales_count, BIGINT '0') AS sales_count, coalesce(m.units, BIGINT '0') AS units,
           coalesce(m.revenue, DECIMAL '0.00') AS revenue
    FROM calendar c LEFT JOIN monthly m ON c.month_start = m.month_start
), periods AS (
    SELECT * FROM filled
    UNION ALL
    SELECT 'year', year, 0, CAST(year AS varchar), sum(sales_count), sum(units), sum(revenue)
    FROM filled GROUP BY year
), previous AS (
    SELECT *, lag(revenue) OVER (PARTITION BY row_type ORDER BY year, month) AS previous_revenue
    FROM periods
)
SELECT *, CAST(revenue AS double) / nullif(sales_count, 0) AS avg_check,
       revenue - previous_revenue AS revenue_change,
       (CAST(revenue AS double) - CAST(previous_revenue AS double))
           / nullif(CAST(previous_revenue AS double), 0) * 100 AS revenue_change_pct
FROM previous;

DROP TABLE IF EXISTS clickhouse.analytics.report_stores;

CREATE TABLE clickhouse.analytics.report_stores WITH (engine = 'MergeTree') AS
WITH stores AS (
    SELECT store_name, count(*) AS sales_count, sum(sale_quantity) AS units,
           sum(sale_total_price) AS revenue, avg(CAST(sale_total_price AS double)) AS avg_check
    FROM clickhouse.analytics.sales_enriched GROUP BY store_name
)
SELECT 'store' AS row_type, store_name, '' AS store_country, '' AS store_city,
       sales_count, units, revenue, avg_check,
       row_number() OVER (ORDER BY revenue DESC, store_name) AS revenue_rank
FROM stores
UNION ALL
SELECT 'location', '', store_country, store_city, count(*), sum(sale_quantity),
       sum(sale_total_price), avg(CAST(sale_total_price AS double)), CAST(NULL AS bigint)
FROM clickhouse.analytics.sales_enriched GROUP BY store_country, store_city;

DROP TABLE IF EXISTS clickhouse.analytics.report_suppliers;

CREATE TABLE clickhouse.analytics.report_suppliers WITH (engine = 'MergeTree') AS
WITH suppliers AS (
    SELECT supplier_name, count(*) AS sales_count, sum(sale_quantity) AS units,
           sum(sale_total_price) AS revenue, avg(CAST(product_price AS double)) AS avg_product_price
    FROM clickhouse.analytics.sales_enriched GROUP BY supplier_name
)
SELECT 'supplier' AS row_type, supplier_name, '' AS supplier_country,
       sales_count, units, revenue, avg_product_price,
       row_number() OVER (ORDER BY revenue DESC, supplier_name) AS revenue_rank
FROM suppliers
UNION ALL
SELECT 'country', '', supplier_country, count(*), sum(sale_quantity),
       sum(sale_total_price), avg(CAST(product_price AS double)), CAST(NULL AS bigint)
FROM clickhouse.analytics.sales_enriched GROUP BY supplier_country;

DROP TABLE IF EXISTS clickhouse.analytics.report_quality;

CREATE TABLE clickhouse.analytics.report_quality WITH (engine = 'MergeTree') AS
WITH products AS (
    SELECT product_name, count(*) AS sales_count, sum(sale_quantity) AS units,
           sum(sale_total_price) AS revenue, avg(CAST(product_rating AS double)) AS avg_rating,
           sum(product_reviews) AS review_count
    FROM clickhouse.analytics.sales_enriched GROUP BY product_name
)
SELECT p.*,
       row_number() OVER (ORDER BY avg_rating DESC, product_name) AS best_rating_rank,
       row_number() OVER (ORDER BY avg_rating, product_name) AS worst_rating_rank,
       row_number() OVER (ORDER BY review_count DESC, product_name) AS reviews_rank,
       c.rating_sales_correlation
FROM products p
CROSS JOIN (
    SELECT corr(avg_rating, CAST(units AS double)) AS rating_sales_correlation FROM products
) c;
