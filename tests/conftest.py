# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dandelion.net.http import NetworkError, Request, Response  # noqa: E402


class FakeHttp:
    """Antwortet anhand registrierter (Methode, URL-Präfix)-Regeln und protokolliert Anfragen."""

    def __init__(self):
        self.routes = []
        self.requests: list[Request] = []

    def add(self, method, prefix, body=None, status=200, headers=None, raw=None):
        if callable(body):
            handler = body
        else:
            data = raw if raw is not None else json.dumps(body).encode() if body is not None else b""
            handler = lambda req: Response(status, headers or {"content-type": "application/json"},
                                           data, req.full_url())
        self.routes.append((method, prefix, handler))

    def fail(self, method, prefix):
        def handler(req):
            raise NetworkError("connection refused")
        self.routes.append((method, prefix, handler))

    async def send(self, req: Request) -> Response:
        self.requests.append(req)
        for method, prefix, handler in reversed(self.routes):
            if req.method == method and req.full_url().startswith(prefix):
                return handler(req)
        return Response(404, {}, b'{"error":"not found"}', req.url)

    def find(self, method, prefix):
        return [r for r in self.requests if r.method == method and r.full_url().startswith(prefix)]


@pytest.fixture
def http():
    return FakeHttp()


@pytest.fixture
def run():
    return lambda coro: asyncio.run(coro)
