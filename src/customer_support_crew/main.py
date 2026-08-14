"""Kept so `crewai run` and the `customer_support_crew` script keep working.

The CLI itself lives in `cli/console.py`.
"""

from customer_support_crew.cli.console import run

__all__ = ["run"]

if __name__ == "__main__":
    run()
