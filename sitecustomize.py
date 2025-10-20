"""Runtime compatibility shims for third-party dependencies.

This module is imported automatically by Python when it is present on the
import path (see :mod:`site`).  We use it to provide compatibility fixes for
breaking changes in our transitive dependencies so our tests can execute using
newer versions of those libraries.
"""

from __future__ import annotations

from inspect import signature

try:  # pragma: no cover - defensive import
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


def _patch_httpx_client_app_kwarg() -> None:
    """Re-introduce the deprecated ``app`` kwarg for ``httpx.Client``.

    Starlette's :class:`~starlette.testclient.TestClient` still passes an
    ``app`` keyword argument to ``httpx.Client``.  httpx 0.28 removed that
    argument in favour of passing an ``ASGITransport`` instance.  When the
    newer httpx is present the tests crash during client construction.  This
    shim adds back support for the ``app`` kwarg by translating it into the
    appropriate transport object before delegating to the real constructor.
    """

    if httpx is None:  # pragma: no cover - nothing to do without httpx
        return

    client_init = signature(httpx.Client.__init__)
    if "app" in client_init.parameters:
        # Older httpx versions still support the ``app`` parameter so there is
        # no need to patch anything.
        return

    original_init = httpx.Client.__init__

    def patched_init(self, *args, app=None, **kwargs):  # type: ignore[override]
        if app is not None and "transport" not in kwargs:
            kwargs["transport"] = httpx.ASGITransport(app=app)
        return original_init(self, *args, **kwargs)

    httpx.Client.__init__ = patched_init  # type: ignore[assignment]


_patch_httpx_client_app_kwarg()
