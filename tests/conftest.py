import atexit
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

TEST_DB_PATH = Path(__file__).resolve().parent / "tmp" / "test.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ['DATABASE_URL'] = f"sqlite:///{TEST_DB_PATH}"
os.environ.setdefault('STRIPE_ENABLED', 'true')
os.environ.setdefault('STRIPE_SECRET_KEY', 'sk_test_stub')


class _StripeStubHandler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode()
        form = parse_qs(raw)
        self.server.records.append({"path": self.path, "form": form})

        if self.path == "/v1/customers":
            self._json({"id": "cus_test", "object": "customer"})
        elif self.path == "/v1/payment_methods":
            token = form.get("card[token]", [""])[0]
            if not token:
                self._json({"error": {"message": "Missing card token"}}, status=400)
            else:
                self._json({"id": "pm_test", "object": "payment_method"})
        elif self.path == "/v1/payment_intents":
            if form.get("payment_method", [""])[0] != "pm_test":
                self._json({"error": {"message": "Unknown payment method"}}, status=400)
            else:
                self._json({"id": "pi_test", "object": "payment_intent", "status": "succeeded"})
        elif self.path == "/v1/charges":
            self._json({"id": "ch_test", "object": "charge", "status": "succeeded"})
        else:
            self._json({"error": {"message": "Not found"}}, status=404)

    def log_message(self, format, *args):  # pragma: no cover - silence
        return


def _allocate_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_stripe_stub():
    port = _allocate_port()
    server = HTTPServer(("127.0.0.1", port), _StripeStubHandler)
    server.records = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    os.environ['STRIPE_API_BASE'] = f"http://127.0.0.1:{port}"
    return server, thread


_STRIPE_STUB_SERVER, _STRIPE_STUB_THREAD = _start_stripe_stub()


def _stop_stripe_stub():  # pragma: no cover - shutdown hook
    _STRIPE_STUB_SERVER.shutdown()
    _STRIPE_STUB_THREAD.join()


atexit.register(_stop_stripe_stub)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import after env
from app.main import app as gateway_app, get_db, stripe as gateway_stripe
from app.db import Base, SessionLocal as ProductionSessionLocal

gateway_stripe.api_base = os.environ['STRIPE_API_BASE']

SQLALCHEMY_DATABASE_URL_TEST = os.environ['DATABASE_URL']

engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL_TEST, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_startup():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine_test)

# Set overrides
gateway_app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def client():
    override_startup()
    test_client = TestClient(gateway_app)
    yield test_client
    Base.metadata.drop_all(bind=engine_test)
    engine_test.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

# Override for direct DB access in tests
import app.db as db_module
db_module.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session")
def stripe_stub():
    return _STRIPE_STUB_SERVER


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    mock_r = Mock()
    mock_r.get.return_value = None
    mock_r.set.return_value = None
    monkeypatch.setattr('app.main.r', mock_r)
