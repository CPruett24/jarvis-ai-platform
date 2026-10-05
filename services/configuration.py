"""Load the existing dotenv configuration once, before consumers read it."""

from functools import lru_cache

from dotenv import load_dotenv


@lru_cache(maxsize=1)
def load_environment():
    load_dotenv()
