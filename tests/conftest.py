import os
import pytest

TEST_DB_PATH = "test_nexus_automata.db"

@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Ensure all test runs use an isolated test database and never touch production nexus_automata.db."""
    os.environ["NEXUS_DB_PATH"] = TEST_DB_PATH
    yield
    # Cleanup test db after test session
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    # Clean WAL & SHM files if present
    for ext in ["-wal", "-shm"]:
        fp = TEST_DB_PATH + ext
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
