SELECT count(*) AS sales, sum(sale_quantity) AS units, sum(sale_total_price) AS revenue
FROM analytics.fact_sales;

SELECT source_file, count(*) AS rows FROM analytics.fact_sales GROUP BY source_file ORDER BY source_file;

SELECT product_name, units, revenue, sales_rank FROM analytics.report_products
WHERE row_type = 'product' AND sales_rank <= 10 ORDER BY sales_rank;

SELECT product_category, revenue FROM analytics.report_products
WHERE row_type = 'category' ORDER BY revenue DESC;

SELECT product_name, avg_rating, review_count FROM analytics.report_products
WHERE row_type = 'product' ORDER BY product_name;

SELECT customer_email, customer_name, revenue, avg_check, spending_rank FROM analytics.report_customers
WHERE row_type = 'customer' AND spending_rank <= 10 ORDER BY spending_rank;

SELECT customer_country, customer_count FROM analytics.report_customers
WHERE row_type = 'country' ORDER BY customer_count DESC, customer_country;

SELECT row_type, period, sales_count, units, revenue, avg_check,
       previous_revenue, revenue_change, revenue_change_pct
FROM analytics.report_time ORDER BY row_type, period;

SELECT store_name, revenue, avg_check, revenue_rank FROM analytics.report_stores
WHERE row_type = 'store' AND revenue_rank <= 5 ORDER BY revenue_rank;

SELECT store_country, store_city, sales_count, revenue FROM analytics.report_stores
WHERE row_type = 'location' ORDER BY revenue DESC LIMIT 10;

SELECT store_country, sum(sales_count) AS sales_count, sum(revenue) AS revenue
FROM analytics.report_stores WHERE row_type = 'location'
GROUP BY store_country ORDER BY revenue DESC;

SELECT supplier_name, revenue, avg_product_price, revenue_rank FROM analytics.report_suppliers
WHERE row_type = 'supplier' AND revenue_rank <= 5 ORDER BY revenue_rank;

SELECT supplier_country, sales_count, revenue FROM analytics.report_suppliers
WHERE row_type = 'country' ORDER BY revenue DESC;

SELECT product_name, avg_rating, review_count, best_rating_rank,
       worst_rating_rank, reviews_rank, rating_sales_correlation
FROM analytics.report_quality ORDER BY best_rating_rank;

SELECT throwIf(count(*) != 10000 OR sum(sale_quantity) != 54623
               OR sum(sale_total_price) != toDecimal128('2529852.12', 2), 'Invalid sales totals')
FROM analytics.fact_sales;
