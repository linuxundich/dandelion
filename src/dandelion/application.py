# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk

from .core.publisher import Publisher
from .core.secrets import LibsecretStore
from .core.store import Store
from .net.http import SoupHttpClient
from .platforms import Registry

log = logging.getLogger(__name__)


class DandelionApplication(Adw.Application):
    def __init__(self, version: str, app_id: str) -> None:
        super().__init__(application_id=app_id,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path="/de/linuxundich/Dandelion")
        self.version = version
        self.settings = Gio.Settings.new(app_id)
        self.store: Store | None = None
        self.http = SoupHttpClient()
        self.secrets = LibsecretStore()
        self.registry = Registry(self.http, self.secrets)
        self.publisher: Publisher | None = None

        self._add_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self._add_action("about", self.on_about)
        self._add_action("preferences", self.on_preferences, ["<primary>comma"])
        self._add_action("shortcuts", self.on_shortcuts, ["<primary>question"])
        self.set_accels_for_action("win.new-post", ["<primary>n"])
        self.set_accels_for_action("win.publish", ["<primary>Return"])
        self.set_accels_for_action("win.toggle-drafts", ["F9"])
        self.set_accels_for_action("win.toggle-preview", ["<primary><shift>p"])
        self.set_accels_for_action("win.add-media", ["<primary>o"])
        self.set_accels_for_action("win.save-draft", ["<primary>s"])
        self.set_accels_for_action("win.choose-role", ["<primary>r"])
        self.set_accels_for_action("win.view::composer", ["<primary>1"])
        self.set_accels_for_action("win.view::history", ["<primary>2"])
        self.set_accels_for_action("win.search", ["<primary>f"])
        self.set_accels_for_action("window.close", ["<primary>w"])

    def _add_action(self, name: str, callback, accels: list[str] | None = None) -> None:  # type: ignore[no-untyped-def]
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if accels:
            self.set_accels_for_action(f"app.{name}", accels)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self.store = Store()
        self.publisher = Publisher(self.store, self.registry)
        days = self.settings.get_int("draft-retention-days")
        if days:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
            self.store.purge_empty_drafts(cutoff)
        self.store.purge_deleted_posts()

    def do_activate(self) -> None:
        from .window import DandelionWindow
        win = self.props.active_window
        if not win:
            win = DandelionWindow(application=self)
        win.present()

    def do_shutdown(self) -> None:
        for win in self.get_windows():
            if hasattr(win, "flush"):
                win.flush()
        if self.store:
            self.store.purge_deleted_posts()
            self.store.close()
        Adw.Application.do_shutdown(self)

    # ------------------------------------------------------------------
    def on_about(self, *_args: object) -> None:
        about = Adw.AboutDialog(
            application_name="Dandelion",
            application_icon=self.get_application_id(),
            developer_name="Christoph Langner",
            version=self.version,
            website="https://github.com/linuxundich/dandelion",
            issue_url="https://github.com/linuxundich/dandelion/issues",
            license_type=Gtk.License.GPL_3_0,
            copyright="© 2026 Christoph Langner",
            comments=_("Write once, post to Mastodon, Bluesky and more."),
            # Translators: Replace "translator-credits" with your name/username,
            # and optionally an email or URL.
            translator_credits=_("translator-credits"),
        )
        about.present(self.props.active_window)

    def on_preferences(self, *_args: object) -> None:
        win = self.props.active_window
        if win and hasattr(win, "show_preferences"):
            win.show_preferences()

    def on_shortcuts(self, *_args: object) -> None:
        builder = Gtk.Builder.new_from_resource(
            "/de/linuxundich/Dandelion/ui/shortcuts-dialog.ui")
        dialog = builder.get_object("shortcuts_dialog")
        dialog.present(self.props.active_window)

    def notify(self, title: str, body: str, ident: str | None = None) -> None:
        n = Gio.Notification.new(title)
        n.set_body(body)
        self.send_notification(ident, n)

    @staticmethod
    def idle(callback) -> None:  # type: ignore[no-untyped-def]
        GLib.idle_add(lambda: (callback(), GLib.SOURCE_REMOVE)[1])
