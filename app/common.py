import base64
import json
import os
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from trino.dbapi import connect


def pg_connection():
    return psycopg.connect(
        host=os.getenv("PG_HOST", "postgres"), dbname=os.getenv("PG_DATABASE", "lab_db"),
        user=os.getenv("PG_USER", "postgres"), password=os.getenv("PG_PASSWORD", "postgres"),
    )


def ch_query(query, data=b""):
    credentials = f"{os.getenv('CH_USER', 'lab')}:{os.getenv('CH_PASSWORD', 'lab')}"
    auth = base64.b64encode(credentials.encode()).decode()
    params = urlencode({"query": query, "wait_end_of_query": "1"})
    request = Request(os.getenv("CH_URL", "http://clickhouse:8123") + "/?" + params,
                      data=data, headers={"Authorization": "Basic " + auth}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:
            return response.read().decode()
    except HTTPError as error:
        raise RuntimeError(error.read().decode()) from error


def ch_rows(query):
    return [json.loads(line, parse_float=Decimal) for line in ch_query(query + " FORMAT JSONEachRow").splitlines()]


def trino_query(query):
    with connect(host=os.getenv("TRINO_HOST", "trino"), port=8080, user="lab",
                 catalog="clickhouse", schema="analytics", request_timeout=180) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            cursor.close()


def run_sql(path):
    statements = Path(path).read_text(encoding="utf-8").split(";")
    for statement in statements:
        if statement.strip():
            first_line = next(line.strip() for line in statement.splitlines() if line.strip())
            print(first_line, flush=True)
            trino_query(statement.strip())
