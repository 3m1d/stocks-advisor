from __future__ import annotations

import argparse
from datetime import date, datetime


def parse_datetime(value: str) -> datetime:
    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {value}')


def parse_date(value: str) -> date:
    return parse_datetime(value).date()


def add_date_range_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--start', type=str, help='Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('--end', type=str, help='End datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Load from the day after the latest stored record through today (or --end).',
    )
