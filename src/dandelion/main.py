# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import logging
import os
import sys
import warnings

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Spelling", "1")
gi.require_version("Soup", "3.0")
gi.require_version("Secret", "1")


def main(version: str, app_id: str) -> int:
    level = logging.DEBUG if os.environ.get("DANDELION_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    # asyncio läuft in der GLib-Hauptschleife (PyGObject ≥ 3.50)
    from gi.events import GLibEventLoopPolicy
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(GLibEventLoopPolicy())

    if "--run-due" in sys.argv:
        from .runner import run_due
        return run_due(app_id)

    from gi.repository import GtkSource
    GtkSource.init()

    from .application import DandelionApplication
    app = DandelionApplication(version, app_id)
    return app.run(sys.argv)
