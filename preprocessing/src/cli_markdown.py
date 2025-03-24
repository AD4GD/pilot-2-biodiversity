from rich.console import Console
from rich.table import Table
from typing import List

def print_table(title:str, in_table:dict[str,any]) -> None:
    """
    Print a table with the given title, fields, and values.

    Args:
        title (str): The title of the table.
        fields (List[str]): The list of fields.
        values (List[str]): The list of values.

    Returns:
        None
    """
    out_table = Table(title=title)
    out_table.add_column("Field", justify="center", style="cyan", no_wrap=True)
    out_table.add_column("Value", justify="center", style="magenta", no_wrap=True)
    for field, value in zip(in_table.keys(), in_table.values()):
        out_table.add_row(str(field), str(value))
    console = Console()
    console.print(out_table)