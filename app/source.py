import csv
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path


INTEGERS = {
    "id", "customer_age", "product_quantity", "sale_customer_id", "sale_seller_id",
    "sale_product_id", "sale_quantity", "product_reviews", "source_row_id", "source_row",
}
DECIMALS = {
    "product_price": (12, 2), "sale_total_price": (12, 2),
    "product_weight": (10, 2), "product_rating": (3, 1),
}
DATES = {"sale_date", "product_release_date", "product_expiry_date"}


def read_source(directory="/data"):
    def number(path):
        match = re.search(r"\((\d+)\)", path.stem)
        return int(match.group(1)) if match else 0

    files = sorted(Path(directory).glob("*.csv"), key=number)
    if len(files) != 10 or [number(path) for path in files] != list(range(10)):
        raise RuntimeError("Expected MOCK_DATA.csv and MOCK_DATA (1)..(9).csv")
    rows = []
    for file_index, path in enumerate(files):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
        if len(records) != 1000:
            raise RuntimeError(f"Expected 1000 records in {path.name}, got {len(records)}")
        for index, record in enumerate(records, start=1):
            if None in record or any(value is None for value in record.values()):
                raise ValueError(f"Malformed CSV record in {path.name}:{index}")
            row = {}
            for column, value in record.items():
                if value == "":
                    row[column] = None
                elif column in INTEGERS:
                    row[column] = int(value)
                elif column in DECIMALS:
                    row[column] = Decimal(value)
                elif column in DATES:
                    row[column] = datetime.strptime(value, "%m/%d/%Y").date()
                else:
                    row[column] = value
            row.update(source_file=path.name, source_row=index,
                       source_row_id=file_index * 1000 + index)
            if not row["sale_date"] or not row["sale_quantity"] or row["sale_quantity"] <= 0:
                raise ValueError(f"Invalid sale: {row['source_row_id']}")
            if row["sale_total_price"] is None or row["sale_total_price"] < 0:
                raise ValueError(f"Invalid sale amount: {row['source_row_id']}")
            rows.append(row)
    return rows


def column_type(name, clickhouse=False):
    if name in INTEGERS:
        kind = "Int64" if clickhouse else "BIGINT"
    elif name in DECIMALS:
        precision, scale = DECIMALS[name]
        kind = f"Decimal({precision},{scale})" if clickhouse else f"NUMERIC({precision},{scale})"
    elif name in DATES:
        kind = "Date" if clickhouse else "DATE"
    else:
        kind = "String" if clickhouse else "TEXT"
    if name in ("source_row_id", "source_file", "source_row"):
        if clickhouse:
            return kind
        return kind + (" PRIMARY KEY" if name == "source_row_id" else " NOT NULL")
    return f"Nullable({kind})" if clickhouse else kind
