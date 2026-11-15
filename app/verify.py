import math
from collections import defaultdict
from datetime import date
from decimal import Decimal

from common import ch_rows, pg_connection, trino_query
from source import DATES, DECIMALS, INTEGERS, read_source


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def compare(actual, expected, label):
    if expected is None or actual is None:
        require(expected is None and actual is None, f"{label}: {actual!r} != {expected!r}")
    elif isinstance(expected, (int, float, Decimal)):
        difference = abs(Decimal(str(actual)) - Decimal(str(expected)))
        tolerance = Decimal("0.000001") if isinstance(expected, float) else Decimal(0)
        require(difference <= tolerance, f"{label}: {actual!r} != {expected!r}")
    else:
        require(actual == expected, f"{label}: {actual!r} != {expected!r}")


def normalize(name, value):
    if value is None:
        return None
    if name in INTEGERS:
        return int(value)
    if name in DECIMALS:
        return Decimal(str(value))
    if name in DATES:
        return value if isinstance(value, date) else date.fromisoformat(value)
    return value


def check_source_rows(actual, expected, label):
    require(len(actual) == len(expected), f"{label}: unexpected row count {len(actual)}")
    expected_by_id = {row["source_row_id"]: row for row in expected}
    seen = set()
    for record in actual:
        key = int(record["source_row_id"])
        require(key in expected_by_id and key not in seen, f"{label}: duplicate/unexpected key {key}")
        seen.add(key)
        for name, value in expected_by_id[key].items():
            require(normalize(name, record[name]) == value, f"{label}: mismatch {key}.{name}")
    print(f"{label} OK: {len(actual)} rows, all source fields match", flush=True)


def star_column(name):
    explicit = {
        "id": "f.source_id", "source_row_id": "f.source_row_id", "source_file": "f.source_file",
        "source_row": "f.source_row", "sale_customer_id": "c.source_customer_id",
        "sale_seller_id": "s.source_seller_id", "sale_product_id": "p.source_product_id",
        "sale_date": "d.full_date", "sale_quantity": "f.sale_quantity",
        "sale_total_price": "f.sale_total_price", "pet_category": "p.pet_category",
    }
    if name in explicit:
        return explicit[name]
    for prefix, alias in (("customer_", "c"), ("seller_", "s"), ("product_", "p"),
                          ("store_", "st"), ("supplier_", "sp")):
        if name.startswith(prefix):
            return alias + "." + (name.removeprefix(prefix) if alias in ("c", "s") else name)
    raise ValueError(f"Unknown source column: {name}")


def group_rows(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return groups


def metrics(rows):
    return {"sales_count": len(rows), "units": sum(row["sale_quantity"] for row in rows),
            "revenue": sum((row["sale_total_price"] for row in rows), Decimal(0))}


def mean(rows, field):
    values = [row[field] for row in rows if row[field] is not None]
    return float(sum(values) / len(values)) if values else None


def check_report(table, row_type, fields, groups, extras=None, ranking=None):
    where = f" WHERE row_type = '{row_type}'" if row_type else ""
    actual = ch_rows(f"SELECT * FROM analytics.{table}{where}")
    require(len(actual) == len(groups), f"{table}/{row_type}: unexpected number of groups")
    ranks = {}
    if ranking:
        rank_column, ordering = ranking
        ranks = {key: index for index, key in enumerate(sorted(groups, key=ordering), start=1)}
    seen = set()
    for record in actual:
        key = tuple(record[field] for field in fields)
        require(key in groups and key not in seen, f"{table}: unexpected/duplicate group {key}")
        seen.add(key)
        expected = metrics(groups[key])
        if extras:
            expected.update(extras(groups[key]))
        if ranking:
            expected[rank_column] = ranks[key]
        for name, value in expected.items():
            compare(record[name], value, f"{table}/{key}/{name}")


def check_reports(rows):
    products = group_rows(rows, ["product_name"])
    product_extras = lambda group: {"avg_rating": mean(group, "product_rating"),
                                     "review_count": sum(row["product_reviews"] for row in group)}
    check_report("report_products", "product", ["product_name"], products, product_extras,
                 ("sales_rank", lambda key: (-metrics(products[key])["units"],
                                             -metrics(products[key])["revenue"], key)))
    check_report("report_products", "category", ["product_category"], group_rows(rows, ["product_category"]))
    customers = group_rows(rows, ["customer_email"])
    check_report("report_customers", "customer", ["customer_email"], customers,
                 lambda group: {"avg_check": mean(group, "sale_total_price"), "customer_count": 1,
                                "customer_name": max(" ".join(filter(None, (r["customer_first_name"], r["customer_last_name"]))) for r in group)},
                 ("spending_rank", lambda key: (-metrics(customers[key])["revenue"], key)))
    check_report("report_customers", "country", ["customer_country"], group_rows(rows, ["customer_country"]),
                 lambda group: {"customer_count": len({r["customer_email"] for r in group}),
                                "avg_check": mean(group, "sale_total_price")})
    for entity, table in (("store", "report_stores"), ("supplier", "report_suppliers")):
        groups = group_rows(rows, [entity + "_name"])
        extra = (lambda group: {"avg_check": mean(group, "sale_total_price")}) if entity == "store" else (
            lambda group: {"avg_product_price": mean(group, "product_price")})
        check_report(table, entity, [entity + "_name"], groups, extra,
                     ("revenue_rank", lambda key: (-metrics(groups[key])["revenue"], key)))
        fields = ["store_country", "store_city"] if entity == "store" else ["supplier_country"]
        check_report(table, "location" if entity == "store" else "country", fields,
                     group_rows(rows, fields), extra)
    check_report("report_quality", None, ["product_name"], products, product_extras)
    rankings = {
        "best_rating_rank": sorted(products, key=lambda key: (-mean(products[key], "product_rating"), key)),
        "worst_rating_rank": sorted(products, key=lambda key: (mean(products[key], "product_rating"), key)),
        "reviews_rank": sorted(products, key=lambda key: (-product_extras(products[key])["review_count"], key)),
    }
    xs = [mean(group, "product_rating") for group in products.values()]
    ys = [float(metrics(group)["units"]) for group in products.values()]
    x_mean, y_mean = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = math.sqrt(sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys))
    correlation = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator if denominator else None
    for record in ch_rows("SELECT * FROM analytics.report_quality"):
        key = (record["product_name"],)
        for name, ordered in rankings.items():
            compare(record[name], ordered.index(key) + 1, f"quality/{key}/{name}")
        compare(record["rating_sales_correlation"], correlation, "rating-sales correlation")
    check_time(rows)
    print("REPORTS OK: all 6 reports match independent CSV aggregates, rankings and period comparisons", flush=True)


def check_time(rows):
    groups = defaultdict(list)
    for row in rows:
        full_date = row["sale_date"]
        groups[("month", full_date.strftime("%Y-%m"))].append(row)
        groups[("year", str(full_date.year))].append(row)
    first, last = min(row["sale_date"] for row in rows), max(row["sale_date"] for row in rows)
    month = first.replace(day=1)
    while month <= last:
        groups.setdefault(("month", month.strftime("%Y-%m")), [])
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    actual = ch_rows("SELECT * FROM analytics.report_time ORDER BY row_type, period")
    require(len(actual) == len(groups), "Unexpected time periods")
    previous = {}
    seen = set()
    for record in actual:
        kind, period = record["row_type"], record["period"]
        key = (kind, period)
        require(key in groups and key not in seen, f"Unexpected/duplicate time period {key}")
        seen.add(key)
        summary = metrics(groups[key])
        revenue = summary["revenue"]
        old = previous.get(kind)
        summary.update(year=int(period[:4]), month=int(period[5:]) if kind == "month" else 0,
                       avg_check=float(revenue / len(groups[key])) if groups[key] else None,
                       previous_revenue=old, revenue_change=revenue - old if old is not None else None,
                       revenue_change_pct=float((revenue - old) / old * 100) if old else None)
        for name, value in summary.items():
            compare(record[name], value, f"report_time/{key}/{name}")
        previous[kind] = revenue


def verify():
    rows = read_source()
    with pg_connection() as connection:
        cursor = connection.execute("SELECT * FROM mock_data ORDER BY source_row_id")
        columns = [column.name for column in cursor.description]
        actual = [dict(zip(columns, row)) for row in cursor]
    check_source_rows(actual, rows[5000:], "POSTGRES SOURCE")
    check_source_rows(ch_rows("SELECT * FROM source.mock_data"), rows[:5000], "CLICKHOUSE SOURCE")
    counts = trino_query("SELECT count(*) FROM clickhouse.source.mock_data UNION ALL SELECT count(*) FROM postgresql.public.mock_data")
    require(counts == [[5000], [5000]], f"Trino source counts: {counts}")
    check_source_rows(ch_rows("SELECT * FROM analytics.staging_sales"), rows, "TRINO UNION")
    projections = ", ".join(f"{star_column(name)} AS {name}" for name in rows[0])
    actual = ch_rows(f"""
        SELECT {projections} FROM analytics.fact_sales f
        INNER JOIN analytics.dim_customer c ON f.customer_key = c.customer_key
        INNER JOIN analytics.dim_seller s ON f.seller_key = s.seller_key
        INNER JOIN analytics.dim_product p ON f.product_key = p.product_key
        INNER JOIN analytics.dim_store st ON f.store_key = st.store_key
        INNER JOIN analytics.dim_supplier sp ON f.supplier_key = sp.supplier_key
        INNER JOIN analytics.dim_date d ON f.date_key = d.date_key
    """)
    check_source_rows(actual, rows, "STAR")
    for entity in ("customer", "seller", "product", "store", "supplier", "date"):
        if entity in ("customer", "seller", "product"):
            expected = len(rows)
        elif entity == "date":
            expected = len({row["sale_date"] for row in rows})
        else:
            fields = [field for field in rows[0] if field.startswith(entity + "_")]
            expected = len({tuple(row[field] for field in fields) for row in rows})
        result = ch_rows(f"SELECT count(*) AS rows, uniqExact({entity}_key) AS keys FROM analytics.dim_{entity}")[0]
        require(int(result["rows"]) == expected == int(result["keys"]), f"Invalid dim_{entity}")
    require(int(ch_rows("SELECT count(*) AS rows FROM analytics.sales_enriched")[0]["rows"]) == 10000,
            "Invalid enriched star row count")
    check_reports(rows)
    summary = metrics(rows)
    print(f"CHECK OK: {summary['sales_count']} sales, {summary['units']} units, revenue {summary['revenue']}", flush=True)
