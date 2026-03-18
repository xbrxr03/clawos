"""dashd entry point."""
import logging
logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s %(message)s")
from services.dashd.api import run
if __name__ == "__main__":
    run()
