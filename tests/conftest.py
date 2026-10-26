def pytest_addoption(parser):
    parser.addoption("--run-spark", action="store_true", help="Run host-side Spark/Delta integration checks")

def pytest_collection_modifyitems(config, items):
    import pytest
    if config.getoption("--run-spark"):
        return
    for item in items:
        if "spark" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="Use --run-spark in a host terminal"))
