"""Output formatting: JSON and Rich table."""
from __future__ import annotations

import json
from io import StringIO

from rich.console import Console
from rich.table import Table


def format_json(listings: list[dict], fields: list[str] | None = None) -> str:
    """Format listings as a JSON string, optionally filtering to specified fields."""
    if fields:
        listings = [{k: item[k] for k in fields if k in item} for item in listings]
    return json.dumps(listings, ensure_ascii=False, indent=2, default=str)


def format_table(
    listings: list[dict], columns: list[str] | None = None
) -> str:
    """Format listings as a Rich table rendered to a string."""
    if not listings:
        return ""

    if columns is None:
        columns = list(listings[0].keys())

    table = Table(show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)

    for item in listings:
        row = [str(item.get(col, "")) for col in columns]
        table.add_row(*row)

    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    console.print(table)
    return buf.getvalue()
