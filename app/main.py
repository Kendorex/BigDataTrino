import argparse

from common import run_sql
from load import load_sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("all", "load", "star", "reports", "check"), default="all", nargs="?")
    command = parser.parse_args().command
    if command in ("all", "load"):
        load_sources()
    if command in ("all", "star"):
        run_sql("/sql/trino/01_union.sql")
        run_sql("/sql/trino/02_star.sql")
    if command in ("all", "reports"):
        run_sql("/sql/trino/03_reports.sql")
    if command in ("all", "check"):
        from verify import verify
        verify()


if __name__ == "__main__":
    main()
