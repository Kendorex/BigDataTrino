import json

from common import ch_query, pg_connection
from source import column_type, read_source


def load_sources():
    rows = read_source()
    columns = list(rows[0])
    pg_columns = ", ".join(f"{column} {column_type(column)}" for column in columns)
    with pg_connection() as connection:
        connection.execute(f"CREATE TABLE IF NOT EXISTS mock_data ({pg_columns})")
        connection.execute("TRUNCATE mock_data")
        with connection.cursor().copy(f"COPY mock_data ({', '.join(columns)}) FROM STDIN") as copy:
            for row in rows[5000:]:
                copy.write_row([row[column] for column in columns])
    ch_query("CREATE DATABASE IF NOT EXISTS source")
    ch_query("CREATE DATABASE IF NOT EXISTS analytics")
    ch_columns = ", ".join(f"{column} {column_type(column, True)}" for column in columns)
    ch_query(f"CREATE TABLE IF NOT EXISTS source.mock_data ({ch_columns}) ENGINE = MergeTree ORDER BY source_row_id")
    ch_query("TRUNCATE TABLE source.mock_data")
    payload = "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in rows[:5000])
    ch_query("INSERT INTO source.mock_data FORMAT JSONEachRow", (payload + "\n").encode())
    print("LOAD OK: ClickHouse = MOCK_DATA.csv + (1)..(4), PostgreSQL = (5)..(9); 5000 rows each", flush=True)
