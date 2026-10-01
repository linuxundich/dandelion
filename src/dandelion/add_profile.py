# SPDX-License-Identifier: GPL-3.0-or-later
"""Profil hinzufügen: Plattform wählen, anmelden, Rollen zuordnen."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any

from gi.repository import Adw, GLib, Gtk

from .auth.oauth import LoopbackServer, parse_code_input
from .core.models import Profile, Role
from .platforms.base import PlatformError
from .util import spawn, system_language
from .widgets.avatars import AvatarCache

if TYPE_CHECKING:
    from .application import DandelionApplication

log = logging.getLogger(__name__)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/add-profile.ui")
class DandelionAddProfileDialog(Adw.Dialog):
    __gtype_name__ = "DandelionAddProfileDialog"

    nav: Adw.NavigationView = Gtk.Template.Child()
    instance_row: Adw.EntryRow = Gtk.Template.Child()
    mastodon_button: Gtk.Button = Gtk.Template.Child()
    mastodon_wait_group: Adw.PreferencesGroup = Gtk.Template.Child()
    mastodon_code_group: Adw.PreferencesGroup = Gtk.Template.Child()
    code_row: Adw.EntryRow = Gtk.Template.Child()
    handle_row: Adw.EntryRow = Gtk.Template.Child()
    password_row: Adw.PasswordEntryRow = Gtk.Template.Child()
    bluesky_button: Gtk.Button = Gtk.Template.Child()
    bluesky_wait_group: Adw.PreferencesGroup = Gtk.Template.Child()
    done_avatar: Adw.Avatar = Gtk.Template.Child()
    done_name: Gtk.Label = Gtk.Template.Child()
    done_handle: Gtk.Label = Gtk.Template.Child()
    done_roles_group: Adw.PreferencesGroup = Gtk.Template.Child()

    def __init__(self, app: DandelionApplication, on_added: Callable[[Profile], None],
                 platform: str | None = None, hint: str | None = None) -> None:
        super().__init__()
        self.app = app
        self.on_added = on_added
        self.pending: Any = None
        self.server: LoopbackServer | None = None
        self.profile: Profile | None = None
        self._role_checks: list[tuple[Role, Gtk.CheckButton]] = []
        self.connect("closed", lambda *_: self._cleanup())
        if platform == "mastodon":
            self.instance_row.set_text(hint or "")
            self.nav.push_by_tag("mastodon")
        elif platform == "bluesky":
            self.handle_row.set_text(hint or "")
            self.nav.push_by_tag("bluesky")

    def _cleanup(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None

    def _error(self, e: BaseException) -> None:
        msg = e.message if isinstance(e, PlatformError) else _("Sign-in failed.")
        if not isinstance(e, (PlatformError, asyncio.CancelledError, TimeoutError)):
            log.error("Anmeldung fehlgeschlagen", exc_info=e)
        self.add_toast(Adw.Toast(title=msg, timeout=8))
        self.mastodon_wait_group.set_visible(False)
        self.bluesky_wait_group.set_visible(False)
        self.mastodon_button.set_sensitive(True)
        self.bluesky_button.set_sensitive(True)

    # -- Mastodon --------------------------------------------------------------
    @Gtk.Template.Callback()
    def on_mastodon(self, *_args: object) -> None:
        self.nav.push_by_tag("mastodon")

    @Gtk.Template.Callback()
    def on_mastodon_login(self, *_args: object) -> None:
        instance = self.instance_row.get_text().strip()
        if not instance:
            self.instance_row.add_css_class("error")
            return
        self.instance_row.remove_css_class("error")
        self.mastodon_button.set_sensitive(False)
        self.mastodon_wait_group.set_visible(True)
        spawn(self._mastodon_flow(instance), on_error=self._error)

    async def _mastodon_flow(self, instance: str) -> None:
        mastodon = self.app.registry.get("mastodon")
        self._cleanup()
        self.server = LoopbackServer()
        redirect = self.server.start()
        self.pending = await mastodon.begin_login(instance, redirect)  # type: ignore[attr-defined]
        self.mastodon_code_group.set_visible(True)
        self._launch(self.pending.authorize_url())
        params = await self.server.wait()
        await self._mastodon_finish(params, redirect)

    async def _mastodon_finish(self, params: dict[str, str], redirect: str) -> None:
        if params.get("error"):
            raise PlatformError(_("The server denied the sign-in: {reason}").format(
                reason=params.get("error_description") or params["error"]))
        if params.get("state") and params["state"] != self.pending.state:
            raise PlatformError(_("The sign-in response did not match. Please try again."))
        mastodon = self.app.registry.get("mastodon")
        profile, secret = await mastodon.finish_login(  # type: ignore[attr-defined]
            self.pending, params["code"], redirect)
        await self._save_profile(mastodon, profile, secret)

    @Gtk.Template.Callback()
    def on_code_entered(self, *_args: object) -> None:
        if not self.pending:
            return
        params = parse_code_input(self.code_row.get_text())
        self._cleanup()
        # Der Code gehört zur Loopback-Adresse, auch wenn der Browser sie nicht erreicht hat
        spawn(self._mastodon_finish(params, self.pending.redirect_uri), on_error=self._error)

    @Gtk.Template.Callback()
    def on_open_again(self, *_args: object) -> None:
        if self.pending:
            self._launch(self.pending.authorize_url())

    def _launch(self, url: str) -> None:
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None)

    # -- Bluesky --------------------------------------------------------------
    @Gtk.Template.Callback()
    def on_bluesky(self, *_args: object) -> None:
        self.nav.push_by_tag("bluesky")

    @Gtk.Template.Callback()
    def on_create_app_password(self, *_args: object) -> None:
        self._launch("https://bsky.app/settings/app-passwords")

    @Gtk.Template.Callback()
    def on_bluesky_login(self, *_args: object) -> None:
        handle = self.handle_row.get_text().strip()
        password = self.password_row.get_text().strip()
        if not handle or not password:
            for row, value in ((self.handle_row, handle), (self.password_row, password)):
                (row.add_css_class if not value else row.remove_css_class)("error")
            return
        self.bluesky_button.set_sensitive(False)
        self.bluesky_wait_group.set_visible(True)

        async def run() -> None:
            bsky = self.app.registry.get("bluesky")
            profile, secret = await bsky.login_app_password(handle, password)  # type: ignore[attr-defined]
            await self._save_profile(bsky, profile, secret)

        spawn(run(), on_error=self._error)

    # -- Gemeinsam -----------------------------------------------------------
    async def _save_profile(self, platform: Any, profile: Profile, secret: dict[str, Any]) -> None:
        store = self.app.store
        existing = store.find_profile(profile.platform, profile.server, profile.remote_id)
        if existing:
            profile.id, profile.uuid, profile.label = existing.id, existing.uuid, existing.label
        try:
            limits = await platform.fetch_limits(profile)
            profile.limits_json = limits.to_json()
        except PlatformError:
            pass
        await platform.store_credentials(profile, secret)
        store.save_profile(profile)
        self.profile = profile
        self._show_done(new=existing is None)
        self.on_added(profile)

    def _show_done(self, new: bool) -> None:
        p = self.profile
        assert p is not None
        self.done_avatar.set_text(p.title)
        AvatarCache(self.app.http).apply(self.done_avatar, p.avatar_url)
        self.done_name.set_label(p.display_name or p.handle)
        self.done_handle.set_label(p.full_handle)
        store = self.app.store
        roles = store.roles()
        if not roles:
            roles = [store.save_role(Role(_("Personal"), "🏠", language=system_language()))]
        member_of = set(store.roles_of_profile(p.id))  # type: ignore[arg-type]
        for role in roles:
            row = Adw.ActionRow(title=GLib.markup_escape_text(f"{role.emoji} {role.name}"))
            check = Gtk.CheckButton(active=role.id in member_of or (new and len(roles) == 1),
                                    valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self._role_checks.append((role, check))
            self.done_roles_group.add(row)
        self.nav.push_by_tag("done")

    @Gtk.Template.Callback()
    def on_done(self, *_args: object) -> None:
        store = self.app.store
        if self.profile:
            current = set(store.roles_of_profile(self.profile.id))  # type: ignore[arg-type]
            for role, check in self._role_checks:
                if check.get_active() and role.id not in current:
                    store.set_role_profile(role.id, self.profile.id, True)  # type: ignore[arg-type]
                elif not check.get_active() and role.id in current:
                    store.set_role_profile(role.id, self.profile.id, False)  # type: ignore[arg-type]
            self.on_added(self.profile)
        self.close()
