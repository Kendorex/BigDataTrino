DROP TABLE IF EXISTS clickhouse.analytics.fact_sales;
DROP TABLE IF EXISTS clickhouse.analytics.dim_customer;
DROP TABLE IF EXISTS clickhouse.analytics.dim_seller;
DROP TABLE IF EXISTS clickhouse.analytics.dim_product;
DROP TABLE IF EXISTS clickhouse.analytics.dim_store;
DROP TABLE IF EXISTS clickhouse.analytics.dim_supplier;
DROP TABLE IF EXISTS clickhouse.analytics.dim_date;

CREATE TABLE clickhouse.analytics.dim_customer WITH (engine = 'MergeTree') AS
SELECT source_row_id AS customer_key, source_row_id, sale_customer_id AS source_customer_id,
       customer_first_name AS first_name, customer_last_name AS last_name,
       customer_age AS age, customer_email AS email, customer_country AS country,
       customer_postal_code AS postal_code, customer_pet_type AS pet_type,
       customer_pet_name AS pet_name, customer_pet_breed AS pet_breed
FROM clickhouse.analytics.staging_sales;

CREATE TABLE clickhouse.analytics.dim_seller WITH (engine = 'MergeTree') AS
SELECT source_row_id AS seller_key, source_row_id, sale_seller_id AS source_seller_id,
       seller_first_name AS first_name, seller_last_name AS last_name,
       seller_email AS email, seller_country AS country, seller_postal_code AS postal_code
FROM clickhouse.analytics.staging_sales;

CREATE TABLE clickhouse.analytics.dim_product WITH (engine = 'MergeTree') AS
SELECT source_row_id AS product_key, source_row_id, sale_product_id AS source_product_id,
       product_name, product_category, product_price, product_quantity, pet_category,
       product_weight, product_color, product_size, product_brand, product_material,
       product_description, product_rating, product_reviews, product_release_date, product_expiry_date
FROM clickhouse.analytics.staging_sales;

CREATE TABLE clickhouse.analytics.dim_store WITH (engine = 'MergeTree') AS
SELECT row_number() OVER (ORDER BY store_name, store_location, store_city, store_state,
                                  store_country, store_phone, store_email) AS store_key, stores.*
FROM (
    SELECT DISTINCT store_name, store_location, store_city, store_state,
                    store_country, store_phone, store_email
    FROM clickhouse.analytics.staging_sales
) stores;

CREATE TABLE clickhouse.analytics.dim_supplier WITH (engine = 'MergeTree') AS
SELECT row_number() OVER (ORDER BY supplier_name, supplier_contact, supplier_email,
                                  supplier_phone, supplier_address, supplier_city, supplier_country) AS supplier_key,
       suppliers.*
FROM (
    SELECT DISTINCT supplier_name, supplier_contact, supplier_email, supplier_phone,
                    supplier_address, supplier_city, supplier_country
    FROM clickhouse.analytics.staging_sales
) suppliers;

CREATE TABLE clickhouse.analytics.dim_date WITH (engine = 'MergeTree') AS
SELECT year(sale_date) * 10000 + month(sale_date) * 100 + day(sale_date) AS date_key,
       sale_date AS full_date, year(sale_date) AS year, quarter(sale_date) AS quarter,
       month(sale_date) AS month, day(sale_date) AS day, day_of_week(sale_date) AS day_of_week
FROM (SELECT DISTINCT sale_date FROM clickhouse.analytics.staging_sales);

CREATE TABLE clickhouse.analytics.fact_sales WITH (engine = 'MergeTree') AS
SELECT r.source_row_id, r.source_file, r.source_row, r.id AS source_id,
       r.source_row_id AS customer_key, r.source_row_id AS seller_key, r.source_row_id AS product_key,
       st.store_key, sp.supplier_key,
       year(r.sale_date) * 10000 + month(r.sale_date) * 100 + day(r.sale_date) AS date_key,
       r.sale_quantity, r.sale_total_price
FROM clickhouse.analytics.staging_sales r
JOIN clickhouse.analytics.dim_store st
    ON r.store_name IS NOT DISTINCT FROM st.store_name
   AND r.store_location IS NOT DISTINCT FROM st.store_location
   AND r.store_city IS NOT DISTINCT FROM st.store_city
   AND r.store_state IS NOT DISTINCT FROM st.store_state
   AND r.store_country IS NOT DISTINCT FROM st.store_country
   AND r.store_phone IS NOT DISTINCT FROM st.store_phone
   AND r.store_email IS NOT DISTINCT FROM st.store_email
JOIN clickhouse.analytics.dim_supplier sp
    ON r.supplier_name IS NOT DISTINCT FROM sp.supplier_name
   AND r.supplier_contact IS NOT DISTINCT FROM sp.supplier_contact
   AND r.supplier_email IS NOT DISTINCT FROM sp.supplier_email
   AND r.supplier_phone IS NOT DISTINCT FROM sp.supplier_phone
   AND r.supplier_address IS NOT DISTINCT FROM sp.supplier_address
   AND r.supplier_city IS NOT DISTINCT FROM sp.supplier_city
   AND r.supplier_country IS NOT DISTINCT FROM sp.supplier_country;
