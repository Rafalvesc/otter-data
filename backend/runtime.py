"""Use a Psycopg-compatible asyncio loop, including on Windows."""

import asyncio


def create_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
