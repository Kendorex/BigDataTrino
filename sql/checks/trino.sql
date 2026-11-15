SELECT 'clickhouse' AS source, count(*) AS rows FROM clickhouse.source.mock_data
UNION ALL
SELECT 'postgresql', count(*) FROM postgresql.public.mock_data;

SELECT count(*) AS sales, sum(sale_quantity) AS units, sum(sale_total_price) AS revenue
FROM clickhouse.analytics.fact_sales;

SELECT product_name, units, revenue, sales_rank FROM clickhouse.analytics.report_products
WHERE row_type = 'product' AND sales_rank <= 10 ORDER BY sales_rank;
