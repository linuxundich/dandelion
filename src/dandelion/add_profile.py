# SPDX-License-Identifier: GPL-3.0-or-later
"""Profil hinzufügen: Plattform wählen, anmelden, Rollen zuordnen."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING, Any

from gi.repository import Adw, GLib, Gtk

from .auth.oauth import LoopbackServer, OAuthError, parse_code_input
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
    app_page: Adw.NavigationPage = Gtk.Template.Child()
    app_intro: Gtk.Label = Gtk.Template.Child()
    redirect_row: Adw.ActionRow = Gtk.Template.Child()
    client_id_row: Adw.EntryRow = Gtk.Template.Child()
    client_secret_row: Adw.PasswordEntryRow = Gtk.Template.Child()
    app_login_button: Gtk.Button = Gtk.Template.Child()
    app_wait_group: Adw.PreferencesGroup = Gtk.Template.Child()

    def __init__(self, app: DandelionApplication, on_added: Callable[[Profile], None],
                 platform: str | None = None, hint: str | None = None) -> None:
        super().__init__()
        self.app = app
        self.on_added = on_added
        self.pending: Any = None
        self.server: LoopbackServer | None = None
        self.profile: Profile | None = None
        self.profiles_added: list[Profile] = []
        self._app_platform: Any = None
        self._role_checks: list[tuple[Role, Gtk.CheckButton]] = []
        self.connect("closed", lambda *_: self._cleanup())
        if platform == "mastodon":
            self.instance_row.set_text(hint or "")
            self.nav.push_by_tag("mastodon")
        elif platform == "bluesky":
            self.handle_row.set_text(hint or "")
            self.nav.push_by_tag("bluesky")
        elif platform in ("linkedin", "facebook", "x"):
            self._open_app_page(platform)

    def _cleanup(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None

    def _error(self, e: BaseException) -> None:
        if isinstance(e, PlatformError):
            msg = e.message
        elif isinstance(e, OAuthError):
            msg = str(e)
        elif isinstance(e, TimeoutError):
            msg = _("The sign-in took too long. Please try again.")
        else:
            msg = _("Sign-in failed.")
        if not isinstance(e, (PlatformError, OAuthError, asyncio.CancelledError, TimeoutError)):
            log.error("Anmeldung fehlgeschlagen", exc_info=e)
        self.add_toast(Adw.Toast(title=msg, timeout=8))
        self.mastodon_wait_group.set_visible(False)
        self.bluesky_wait_group.set_visible(False)
        self.mastodon_button.set_sensitive(True)
        self.bluesky_button.set_sensitive(True)
        self.app_wait_group.set_visible(False)
        self.app_login_button.set_sensitive(True)

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
    # -- Eigene Entwickler-App (LinkedIn, Facebook, X) ----------------------
    _APP_INTROS = {
        "linkedin": _("Create an app in the LinkedIn developer portal and add the products "
                      "“Share on LinkedIn” and “Sign In with LinkedIn using OpenID Connect”. "
                      "Enter the redirect address below under “Authorized redirect URLs”. "
                      "Dandelion can only post to your personal profile. A sign-in is valid "
                      "for 60 days."),
        "facebook": _("Create an app of the type “Business” at developers.facebook.com, keep "
                      "it in development mode and add “Facebook Login”. Enter the redirect "
                      "address below under “Valid OAuth Redirect URIs”. Dandelion can only "
                      "post to pages you manage, not to your personal profile."),
        "x": _("Create an app of the type “Native App” with read and write permissions in "
               "the X developer portal and enter the redirect address below as callback. "
               "X charges your developer account for every post: about $0.015, or $0.20 "
               "if the post contains a link."),
    }

    @Gtk.Template.Callback()
    def on_linkedin(self, *_args: object) -> None:
        self._open_app_page("linkedin")

    @Gtk.Template.Callback()
    def on_facebook(self, *_args: object) -> None:
        self._open_app_page("facebook")

    @Gtk.Template.Callback()
    def on_x(self, *_args: object) -> None:
        self._open_app_page("x")

    def _open_app_page(self, platform_id: str) -> None:
        platform = self.app.registry.get(platform_id)
        self._app_platform = platform
        self.app_page.set_title(_("Facebook Page") if platform_id == "facebook"
                                else platform.name)
        self.app_intro.set_label(self._APP_INTROS[platform_id])
        self.redirect_row.set_subtitle(platform.redirect_uri)
        mode = platform.client_secret_mode
        self.client_secret_row.set_visible(mode != "none")
        self.client_secret_row.set_title(_("Client Secret (optional)") if mode == "optional"
                                         else _("App Secret") if platform_id == "facebook"
                                         else _("Client Secret"))
        self.client_id_row.set_title(_("App ID") if platform_id == "facebook"
                                     else _("Client ID"))
        self.nav.push_by_tag("app")

        async def prefill() -> None:
            creds = await platform.client_credentials()
            if creds:
                self.client_id_row.set_text(creds.get("client_id", ""))
                self.client_secret_row.set_text(creds.get("client_secret", ""))

        spawn(prefill())

    @Gtk.Template.Callback()
    def on_open_portal(self, *_args: object) -> None:
        if self._app_platform:
            self._launch(self._app_platform.portal_url)

    @Gtk.Template.Callback()
    def on_copy_redirect(self, *_args: object) -> None:
        if self._app_platform:
            self.get_clipboard().set(self._app_platform.redirect_uri)
            self.add_toast(Adw.Toast(title=_("Redirect address copied")))

    @Gtk.Template.Callback()
    def on_app_login(self, *_args: object) -> None:
        platform = self._app_platform
        if platform is None:
            return
        client_id = self.client_id_row.get_text().strip()
        client_secret = self.client_secret_row.get_text().strip()
        missing_secret = platform.client_secret_mode == "required" and not client_secret
        for row, bad in ((self.client_id_row, not client_id),
                         (self.client_secret_row, missing_secret)):
            (row.add_css_class if bad else row.remove_css_class)("error")
        if not client_id or missing_secret:
            return
        self.app_login_button.set_sensitive(False)
        self.app_wait_group.set_visible(True)
        spawn(self._app_flow(platform, client_id, client_secret), on_error=self._error)

    async def _app_flow(self, platform: Any, client_id: str, client_secret: str) -> None:
        await platform.set_client_credentials(client_id, client_secret)
        login = platform.begin_app_login(client_id, client_secret)
        self._cleanup()
        self.server = LoopbackServer()
        self.server.start(port=platform.redirect_port, host=platform.redirect_host)
        self._launch(login.url)
        params = await self.server.wait()
        if params.get("error"):
            raise PlatformError(_("The sign-in was cancelled: {reason}").format(
                reason=params.get("error_description") or params["error"]))
        if params.get("state") != login.state:
            raise PlatformError(_("The sign-in response did not match. Please try again."))
        results = await platform.complete_app_login(login, params["code"])
        for profile, secret in results:
            await self._store_profile(platform, profile, secret)
        self._show_done()

    # -- Gemeinsam -----------------------------------------------------------
    async def _save_profile(self, platform: Any, profile: Profile, secret: dict[str, Any]) -> None:
        await self._store_profile(platform, profile, secret)
        self._show_done()

    async def _store_profile(self, platform: Any, profile: Profile,
                             secret: dict[str, Any]) -> None:
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
        profile._is_new = existing is None  # type: ignore[attr-defined]
        self.profiles_added.append(profile)
        self.profile = profile

    def _show_done(self) -> None:
        added = self.profiles_added
        p = added[0]
        self.done_avatar.set_text(p.title)
        AvatarCache(self.app.http).apply(self.done_avatar, p.avatar_url)
        if len(added) == 1:
            self.done_name.set_label(p.display_name or p.handle)
            self.done_handle.set_label(p.full_handle)
        else:
            self.done_name.set_label(ngettext("{n} page added", "{n} pages added",
                                              len(added)).format(n=len(added)))
            self.done_handle.set_label(", ".join(a.display_name or a.handle for a in added))
        store = self.app.store
        roles = store.roles()
        if not roles:
            roles = [store.save_role(Role(_("Personal"), "🏠", language=system_language()))]
        member_of = set(store.roles_of_profile(p.id))  # type: ignore[arg-type]
        new = any(getattr(a, "_is_new", False) for a in added)
        for role in roles:
            row = Adw.ActionRow(title=GLib.markup_escape_text(f"{role.emoji} {role.name}"))
            check = Gtk.CheckButton(active=role.id in member_of or (new and len(roles) == 1),
                                    valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self._role_checks.append((role, check))
            self.done_roles_group.add(row)
        self.nav.push_by_tag("done")
        for profile in added:
            self.on_added(profile)

    @Gtk.Template.Callback()
    def on_done(self, *_args: object) -> None:
        store = self.app.store
        for profile in self.profiles_added:
            current = set(store.roles_of_profile(profile.id))  # type: ignore[arg-type]
            for role, check in self._role_checks:
                if check.get_active() and role.id not in current:
                    store.set_role_profile(role.id, profile.id, True)  # type: ignore[arg-type]
                elif not check.get_active() and role.id in current:
                    store.set_role_profile(role.id, profile.id, False)  # type: ignore[arg-type]
            self.on_added(profile)
        self.close()
