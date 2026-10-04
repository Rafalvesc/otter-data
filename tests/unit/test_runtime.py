import asyncio

from uvicorn import Config


def test_native_server_loop_setting_builds_a_selector_loop():
    # backend/__main__.py passes this string; uvicorn uses a custom value as the loop factory.
    factory = Config("backend.main:app", loop="backend.runtime:create_loop").get_loop_factory()
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
