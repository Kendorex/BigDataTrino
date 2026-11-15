DROP TABLE IF EXISTS clickhouse.analytics.staging_sales;

CREATE TABLE clickhouse.analytics.staging_sales
WITH (engine = 'MergeTree') AS
SELECT * FROM clickhouse.source.mock_data
UNION ALL
SELECT * FROM postgresql.public.mock_data;
