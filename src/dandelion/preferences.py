# SPDX-License-Identifier: GPL-3.0-or-later
"""Einstellungen, Rollen und Profile."""

from __future__ import annotations

from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from .schedule_dialog import all_timezones, format_when, system_timezone
from .core.models import ROLE_COLORS, Profile, ProfileStatus, Role
from .util import label_widget, LANGUAGES, VISIBILITY_LABELS, Debouncer, spawn, system_language
from .widgets.avatars import AvatarCache
from .widgets.profile_chip import STATUS_TEXT

if TYPE_CHECKING:
    from .application import DandelionApplication

COLOR_NAMES = {
    "blue": _("Blue"), "teal": _("Teal"), "green": _("Green"), "yellow": _("Yellow"),
    "orange": _("Orange"), "red": _("Red"), "pink": _("Pink"), "purple": _("Purple"),
    "slate": _("Slate"),
}


def _platform_name(app: DandelionApplication, platform_id: str) -> str:
    return app.registry.get(platform_id).name if platform_id in app.registry else platform_id


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/preferences.ui")
class DandelionPreferences(Adw.PreferencesDialog):
    __gtype_name__ = "DandelionPreferences"

    roles_list: Gtk.ListBox = Gtk.Template.Child()
    profiles_list: Gtk.ListBox = Gtk.Template.Child()
    alt_everywhere_row: Adw.SwitchRow = Gtk.Template.Child()
    spellcheck_row: Adw.SwitchRow = Gtk.Template.Child()
    compact_preview_row: Adw.SwitchRow = Gtk.Template.Child()
    signature_row: Adw.SwitchRow = Gtk.Template.Child()
    preview_row: Adw.SwitchRow = Gtk.Template.Child()
    retention_row: Adw.SpinRow = Gtk.Template.Child()
    numbering_row: Adw.ComboRow = Gtk.Template.Child()
    service_row: Adw.SwitchRow = Gtk.Template.Child()
    next_row: Adw.ActionRow = Gtk.Template.Child()
    notify_success_row: Adw.SwitchRow = Gtk.Template.Child()
    notify_failure_row: Adw.SwitchRow = Gtk.Template.Child()
    missed_row: Adw.ComboRow = Gtk.Template.Child()
    grace_row: Adw.SpinRow = Gtk.Template.Child()
    tz_row: Adw.ComboRow = Gtk.Template.Child()
    ai_enabled_row: Adw.SwitchRow = Gtk.Template.Child()
    ai_provider_group: Adw.PreferencesGroup = Gtk.Template.Child()
    provider_row: Adw.ComboRow = Gtk.Template.Child()
    key_row: Adw.PasswordEntryRow = Gtk.Template.Child()
    alt_words_row: Adw.SpinRow = Gtk.Template.Child()
    model_row: Adw.ComboRow = Gtk.Template.Child()
    load_models_row: Adw.ButtonRow = Gtk.Template.Child()

    def __init__(self, app: DandelionApplication, win: Gtk.Window) -> None:
        super().__init__()
        self.app = app
        self.win = win
        self.store = app.store
        self.avatars = AvatarCache(app.http)
        s = app.settings
        flags = Gio.SettingsBindFlags.DEFAULT
        s.bind("require-alt-text-everywhere", self.alt_everywhere_row, "active", flags)
        s.bind("spellcheck", self.spellcheck_row, "active", flags)
        s.bind("append-signature", self.signature_row, "active", flags)
        s.bind("show-preview", self.preview_row, "active", flags)
        s.bind("preview-compact", self.compact_preview_row, "active", flags)
        s.bind("draft-retention-days", self.retention_row, "value", flags)
        numbering = ("off", "fraction", "thread-fraction")
        self.numbering_row.set_selected(numbering.index(s.get_string("thread-numbering")))
        self.numbering_row.connect("notify::selected", lambda r, _p: s.set_string(
            "thread-numbering", numbering[r.get_selected()]))
        s.bind("notify-success", self.notify_success_row, "active", flags)
        s.bind("notify-failure", self.notify_failure_row, "active", flags)
        s.bind("missed-grace-minutes", self.grace_row, "value", flags)
        self._setup_scheduling()
        self._setup_ai()
        self.reload()

    # -- KI ---------------------------------------------------------------
    _PROVIDERS = ("gemini", "openai", "xai", "openrouter")

    def _setup_ai(self) -> None:
        s = self.app.settings
        s.bind("ai-enabled", self.ai_enabled_row, "active", Gio.SettingsBindFlags.DEFAULT)
        s.bind("ai-enabled", self.ai_provider_group, "sensitive", Gio.SettingsBindFlags.GET)
        s.bind("ai-alt-text-words", self.alt_words_row, "value", Gio.SettingsBindFlags.DEFAULT)
        self._ai_loading = True
        pid = self.app.ai.provider_id
        self.provider_row.set_selected(self._PROVIDERS.index(pid))
        self.provider_row.connect("notify::selected", self._on_provider_changed)
        self.model_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None,
                                                                 "string"))
        self.model_row.connect("notify::selected", self._on_model_selected)
        self._show_provider()
        self._ai_loading = False

    def _current_provider(self) -> str:
        return self._PROVIDERS[self.provider_row.get_selected()]

    def _set_models(self, models: list[str], current: str) -> None:
        if current not in models:
            models = [current, *models]
        self._models = models
        self._ai_loading = True
        self.model_row.set_model(Gtk.StringList.new(models))
        self.model_row.set_selected(models.index(current))
        self._ai_loading = False

    def _show_provider(self) -> None:
        pid = self._current_provider()
        self._set_models([], self.app.ai.model(pid))
        self.key_row.set_text("")

        async def load_key() -> None:
            key = await self.app.ai.api_key(pid)
            if pid == self._current_provider():
                self.key_row.set_text(key or "")

        spawn(load_key())

    def _on_provider_changed(self, *_args: object) -> None:
        if self._ai_loading:
            return
        self.app.settings.set_string("ai-provider", self._current_provider())
        self._show_provider()

    def _on_model_selected(self, *_args: object) -> None:
        if self._ai_loading or not getattr(self, "_models", None):
            return
        self.app.ai.set_model(self._current_provider(),
                              self._models[self.model_row.get_selected()])

    @Gtk.Template.Callback()
    def on_key_apply(self, *_args: object) -> None:
        pid = self._current_provider()
        key = self.key_row.get_text()

        async def run() -> None:
            await self.app.ai.set_api_key(pid, key)
            self.add_toast(Adw.Toast(title=_("API key saved") if key.strip()
                                     else _("API key removed")))
            if key.strip():
                await self._load_models(pid, key.strip())

        spawn(run(), on_error=lambda e: self.add_toast(Adw.Toast(title=str(e))))

    @Gtk.Template.Callback()
    def on_key_link(self, *_args: object) -> None:
        url = self.app.ai.provider(self._current_provider()).key_url
        Gtk.UriLauncher.new(url).launch(self.win, None, None)

    @Gtk.Template.Callback()
    def on_load_models(self, *_args: object) -> None:
        pid = self._current_provider()

        async def run() -> None:
            key = await self.app.ai.api_key(pid)
            if not key:
                self.add_toast(Adw.Toast(title=_("Enter and save an API key first.")))
                return
            await self._load_models(pid, key)

        spawn(run())

    async def _load_models(self, pid: str, key: str) -> None:
        from .ai import AIError
        provider = self.app.ai.provider(pid)
        self.load_models_row.set_sensitive(False)
        try:
            models = await provider.list_models(key)
        except AIError as e:
            self.add_toast(Adw.Toast(title=e.message, timeout=8))
            return
        finally:
            self.load_models_row.set_sensitive(True)
        if not models:
            self.add_toast(Adw.Toast(title=_("The provider returned no suitable models.")))
            return
        current = self.app.ai.model(pid)
        if current not in models:
            current = provider.pick_default(models)
            self.app.ai.set_model(pid, current)
        if pid == self._current_provider():
            self._set_models(models, current)
        self.add_toast(Adw.Toast(title=ngettext("{n} model available", "{n} models available",
                                                len(models)).format(n=len(models))))

    @Gtk.Template.Callback()
    def on_reset_privacy(self, *_args: object) -> None:
        self.app.settings.set_strv("ai-privacy-accepted", [])
        self.add_toast(Adw.Toast(title=_("Privacy notices will be shown again")))

    # -- Planung -------------------------------------------------------------
    _POLICIES = ("ask", "send", "discard")

    def _setup_scheduling(self) -> None:
        s = self.app.settings
        sched = self.app.scheduling
        self.missed_row.set_selected(self._POLICIES.index(s.get_string("missed-policy")))
        self.missed_row.connect("notify::selected", lambda r, _p: s.set_string(
            "missed-policy", self._POLICIES[r.get_selected()]))

        zones = all_timezones()
        self._zones = ["", *zones]
        self.tz_row.set_model(Gtk.StringList.new(
            [_("System ({zone})").format(zone=system_timezone()), *zones]))
        self.tz_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        current = s.get_string("default-timezone")
        self.tz_row.set_selected(self._zones.index(current) if current in self._zones else 0)
        self.tz_row.connect("notify::selected", lambda r, _p: s.set_string(
            "default-timezone", self._zones[r.get_selected()]))

        self._service_lock = False
        self.service_row.connect("notify::active", self._on_service_toggled)
        sched.connect("notify::active", lambda *_: self._sync_service())
        sched.connect("notify::available", lambda *_: self._sync_service())
        sched.connect("changed", lambda *_: self._sync_service())
        self._sync_service()

    def _sync_service(self) -> None:
        sched = self.app.scheduling
        self._service_lock = True
        self.service_row.set_active(sched.props.active)
        self._service_lock = False
        self.service_row.set_sensitive(sched.props.available)
        if not sched.props.available:
            self.service_row.set_subtitle(_("Not available: the systemd user instance cannot "
                                            "be reached."))
        elif sched.props.active:
            self.service_row.set_subtitle(_("Active"))
        else:
            self.service_row.set_subtitle(_("Inactive: posts are only sent while Dandelion "
                                            "is open."))
        nxt = sched.scheduler().next_due()
        self.next_row.set_subtitle(format_when(nxt) if nxt else _("Nothing scheduled"))

    def _on_service_toggled(self, row: Adw.SwitchRow, _pspec: object) -> None:
        if self._service_lock:
            return
        if row.get_active():
            self.app.scheduling.enable(self.win)
        else:
            self.app.scheduling.disable()

    def reload(self) -> None:
        self._fill_roles()
        self._fill_profiles()

    # -- Rollen --------------------------------------------------------------
    def _fill_roles(self) -> None:
        self.roles_list.remove_all()
        roles = self.store.roles()
        for idx, role in enumerate(roles):
            self.roles_list.append(self._role_row(role, idx, len(roles)))
        add = Adw.ButtonRow(title=_("Add Role"), start_icon_name="list-add-symbolic")
        add.connect("activated", lambda *_: self._add_role())
        self.roles_list.append(add)

    def _role_row(self, role: Role, idx: int, total: int) -> Adw.ActionRow:
        n = len(self.store.role_profiles(role.id))  # type: ignore[arg-type]
        row = Adw.ActionRow(title=GLib.markup_escape_text(role.name), activatable=True,
                            subtitle=ngettext("{n} profile", "{n} profiles", n).format(n=n))
        handle = Gtk.Image(icon_name="list-drag-handle-symbolic")
        handle.add_css_class("dim-label")
        emoji = Gtk.Label(label=role.emoji or "•")
        emoji.add_css_class("role-emoji")
        emoji.add_css_class(f"role-{role.color}")
        # add_prefix() stellt voran: zuerst das Emoji, dann den Griff ganz links
        row.add_prefix(emoji)
        row.add_prefix(handle)

        menu = Gio.Menu()
        menu.append(_("Move Up"), "role.up")
        menu.append(_("Move Down"), "role.down")
        group = Gio.SimpleActionGroup()
        for name, delta, enabled in (("up", -1, idx > 0), ("down", 1, idx < total - 1)):
            act = Gio.SimpleAction.new(name, None)
            act.set_enabled(enabled)
            act.connect("activate", lambda _a, _p, d=delta, r=role: self._move_role(r, d))
            group.add_action(act)
        row.insert_action_group("role", group)
        more = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu,
                              valign=Gtk.Align.CENTER, tooltip_text=_("More"))
        more.add_css_class("flat")
        label_widget(more, more.get_tooltip_text() or "")
        row.add_suffix(more)
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        row.connect("activated", lambda *_: self._open_role(role))

        # Tastatur: Alt+Pfeil verschiebt
        shortcuts = Gtk.ShortcutController()
        for accel, delta in (("<alt>Up", -1), ("<alt>Down", 1)):
            shortcuts.add_shortcut(Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string(accel),
                Gtk.CallbackAction.new(lambda *_a, d=delta, r=role: (self._move_role(r, d), True)[1])))
        row.add_controller(shortcuts)

        # Ziehen und Ablegen
        source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        source.connect("prepare", lambda *_a, r=role: Gdk.ContentProvider.new_for_value(r.id))
        source.connect("drag-begin", lambda src, _d, w=row: src.set_icon(
            Gtk.WidgetPaintable.new(w), 0, 0))
        handle.add_controller(source)
        target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
        target.connect("drop", lambda _t, value, _x, _y, r=role: self._drop_role(value, r))
        row.add_controller(target)
        return row

    def _move_role(self, role: Role, delta: int) -> None:
        ids = [r.id for r in self.store.roles()]
        i = ids.index(role.id)
        j = max(0, min(len(ids) - 1, i + delta))
        ids.insert(j, ids.pop(i))
        self.store.reorder_roles(ids)  # type: ignore[arg-type]
        self._fill_roles()

    def _drop_role(self, dragged_id: int, onto: Role) -> bool:
        ids = [r.id for r in self.store.roles()]
        if dragged_id not in ids or dragged_id == onto.id:
            return False
        ids.remove(dragged_id)
        ids.insert(ids.index(onto.id), dragged_id)
        self.store.reorder_roles(ids)  # type: ignore[arg-type]
        self._fill_roles()
        return True

    def _add_role(self) -> None:
        used = {r.color for r in self.store.roles()}
        color = next((c for c in ROLE_COLORS if c not in used), "blue")
        role = self.store.save_role(Role(_("New Role"), "💬", color, language=system_language()))
        self._fill_roles()
        self._open_role(role)

    def _open_role(self, role: Role) -> None:
        page = DandelionRolePage(self, role)
        self.push_subpage(page)

    # -- Profile -------------------------------------------------------------
    def _fill_profiles(self) -> None:
        self.profiles_list.remove_all()
        for p in self.store.profiles():
            row = Adw.ActionRow(title=GLib.markup_escape_text(p.label or p.full_handle),
                                activatable=True)
            status = STATUS_TEXT[p.status]
            row.set_subtitle(f"{_platform_name(self.app, p.platform)} · {status}")
            avatar = Adw.Avatar(size=32, text=p.title, show_initials=True)
            self.avatars.apply(avatar, p.avatar_url)
            row.add_prefix(avatar)
            if p.status != ProfileStatus.OK:
                icon = Gtk.Image(icon_name="dialog-warning-symbolic")
                icon.add_css_class("warning" if p.status == ProfileStatus.EXPIRING else "error")
                row.add_suffix(icon)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda *_a, prof=p: self.push_subpage(
                DandelionProfilePage(self, prof)))
            self.profiles_list.append(row)
        add = Adw.ButtonRow(title=_("Add Profile"), start_icon_name="list-add-symbolic")
        add.connect("activated", lambda *_: self.add_profile())
        self.profiles_list.append(add)

    def add_profile(self, platform: str | None = None, hint: str | None = None) -> None:
        from .add_profile import DandelionAddProfileDialog

        def added(_p: Profile) -> None:
            self.reload()

        DandelionAddProfileDialog(self.app, on_added=added, platform=platform,
                                  hint=hint).present(self)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/role-page.ui")
class DandelionRolePage(Adw.NavigationPage):
    __gtype_name__ = "DandelionRolePage"

    name_row: Adw.EntryRow = Gtk.Template.Child()
    emoji_button: Gtk.MenuButton = Gtk.Template.Child()
    color_box: Gtk.Box = Gtk.Template.Child()
    profiles_group: Adw.PreferencesGroup = Gtk.Template.Child()
    language_row: Adw.ComboRow = Gtk.Template.Child()
    visibility_row: Adw.ComboRow = Gtk.Template.Child()
    signature_row: Adw.EntryRow = Gtk.Template.Child()
    ai_style_row: Adw.EntryRow = Gtk.Template.Child()
    slots_group: Adw.PreferencesGroup = Gtk.Template.Child()

    def __init__(self, prefs: DandelionPreferences, role: Role) -> None:
        super().__init__()
        self.prefs = prefs
        self.store = prefs.store
        self.role = role
        self._loading = True
        self._save = Debouncer(400, self._save_now)
        self.set_title(role.name)
        self.name_row.set_text(role.name)
        self.emoji_button.set_label(role.emoji or "💬")
        self.signature_row.set_text(role.signature)
        self.ai_style_row.set_text(role.ai_style)
        self.ai_style_row.set_visible(prefs.app.settings.get_boolean("ai-enabled"))

        first: Gtk.ToggleButton | None = None
        for color in ROLE_COLORS:
            btn = Gtk.ToggleButton(tooltip_text=COLOR_NAMES[color])
            btn.add_css_class("color-button")
            btn.add_css_class(f"role-bg-{color}")
            btn.update_property([Gtk.AccessibleProperty.LABEL], [COLOR_NAMES[color]])
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.set_active(color == role.color)
            btn.connect("toggled", lambda b, c=color: b.get_active() and self._set_color(c))
            self.color_box.append(btn)

        self._lang_codes = [c for c, _n in LANGUAGES]
        self.language_row.set_model(Gtk.StringList.new([n for _c, n in LANGUAGES]))
        self.language_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None,
                                                                     "string"))
        code = role.language or system_language()
        self.language_row.set_selected(self._lang_codes.index(code)
                                       if code in self._lang_codes else 0)
        self.language_row.connect("notify::selected", lambda *_: self._changed())
        self._vis_codes = list(VISIBILITY_LABELS)
        self.visibility_row.set_model(Gtk.StringList.new(
            [VISIBILITY_LABELS[c][0] for c in self._vis_codes]))
        vis = role.visibility or "public"
        self.visibility_row.set_selected(self._vis_codes.index(vis))
        self.visibility_row.connect("notify::selected", lambda *_: self._changed())

        self._fill_profiles()
        self._slot_rows: list[Gtk.Widget] = []
        self._fill_slots()
        self._loading = False
        self.connect("hidden", lambda *_: (self._save.flush(), self.prefs.reload()))

    def _fill_profiles(self) -> None:
        members = {rp.profile_id: rp for rp in self.store.role_profiles(self.role.id)}  # type: ignore[arg-type]
        profiles = self.store.profiles()
        if not profiles:
            row = Adw.ActionRow(title=_("No profiles yet"))
            self.profiles_group.add(row)
            return
        for p in profiles:
            rp = members.get(p.id)  # type: ignore[arg-type]
            row = Adw.ActionRow(title=GLib.markup_escape_text(p.label or p.full_handle),
                                subtitle=_platform_name(self.prefs.app, p.platform))
            check = Gtk.CheckButton(active=rp is not None, valign=Gtk.Align.CENTER)
            check.update_property([Gtk.AccessibleProperty.LABEL],
                                  [_("Include {handle} in this role").format(handle=p.full_handle)])
            row.add_prefix(check)
            row.set_activatable_widget(check)
            switch = Gtk.Switch(active=bool(rp and rp.preselected), valign=Gtk.Align.CENTER,
                                sensitive=rp is not None,
                                tooltip_text=_("Preselected for new posts"))
            switch.update_property([Gtk.AccessibleProperty.LABEL],
                                   [_("Preselect {handle}").format(handle=p.full_handle)])
            row.add_suffix(switch)

            def on_check(c: Gtk.CheckButton, sw: Gtk.Switch = switch, prof: Profile = p) -> None:
                self.store.set_role_profile(self.role.id, prof.id, c.get_active(),  # type: ignore[arg-type]
                                            preselected=True)
                sw.set_sensitive(c.get_active())
                sw.set_active(c.get_active())

            def on_switch(sw: Gtk.Switch, _pspec: object, prof: Profile = p,
                          c: Gtk.CheckButton = check) -> None:
                if c.get_active():
                    self.store.set_role_profile(self.role.id, prof.id, True,  # type: ignore[arg-type]
                                                preselected=sw.get_active())

            check.connect("toggled", on_check)
            switch.connect("notify::active", on_switch)
            self.profiles_group.add(row)

    _WEEKDAYS = (_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"),
                 _("Saturday"), _("Sunday"))

    def _fill_slots(self) -> None:
        for row in self._slot_rows:
            self.slots_group.remove(row)
        self._slot_rows = []
        for idx, (weekday, hm) in enumerate(sorted(self.role.slots,
                                                   key=lambda s: (int(s[0]), str(s[1])))):
            row = Adw.ActionRow(title=self._WEEKDAYS[int(weekday)], subtitle=str(hm))
            row.add_prefix(Gtk.Image(icon_name="alarm-symbolic"))
            remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER)
            remove.add_css_class("flat")
            label_widget(remove, _("Remove slot {day} {time}").format(
                day=self._WEEKDAYS[int(weekday)], time=hm))
            remove.connect("clicked", lambda _b, s=[weekday, hm]: self._remove_slot(s))
            row.add_suffix(remove)
            self.slots_group.add(row)
            self._slot_rows.append(row)

        add = Adw.ActionRow(title=_("Add Slot"))
        day = Gtk.DropDown.new_from_strings(list(self._WEEKDAYS))
        day.set_valign(Gtk.Align.CENTER)
        label_widget(day, _("Weekday"))
        hour = Gtk.SpinButton.new_with_range(0, 23, 1)
        minute = Gtk.SpinButton.new_with_range(0, 55, 5)
        hour.set_value(8)
        for spin, name in ((hour, _("Hour")), (minute, _("Minute"))):
            spin.set_valign(Gtk.Align.CENTER)
            spin.set_wrap(True)
            spin.set_numeric(True)
            spin.connect("output", lambda sp: (sp.set_text(f"{int(sp.get_value()):02d}"), True)[1])
            label_widget(spin, name)
        button = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER)
        button.add_css_class("flat")
        label_widget(button, _("Add Slot"))
        button.connect("clicked", lambda *_: self._add_slot(
            day.get_selected(), f"{int(hour.get_value()):02d}:{int(minute.get_value()):02d}"))
        for w in (day, hour, Gtk.Label(label=":"), minute, button):
            add.add_suffix(w)
        self.slots_group.add(add)
        self._slot_rows.append(add)

    def _add_slot(self, weekday: int, hm: str) -> None:
        if [weekday, hm] not in self.role.slots:
            self.role.slots.append([weekday, hm])
            self.store.save_role(self.role)
        self._fill_slots()

    def _remove_slot(self, slot: list[object]) -> None:
        self.role.slots = [s for s in self.role.slots if [int(s[0]), str(s[1])] !=
                           [int(slot[0]), str(slot[1])]]  # type: ignore[call-overload]
        self.store.save_role(self.role)
        self._fill_slots()

    def _set_color(self, color: str) -> None:
        self.role.color = color
        self._changed()

    @Gtk.Template.Callback()
    def on_name_changed(self, *_args: object) -> None:
        self._changed()

    @Gtk.Template.Callback()
    def on_signature_changed(self, *_args: object) -> None:
        self._changed()

    @Gtk.Template.Callback()
    def on_emoji_picked(self, _chooser: Gtk.EmojiChooser, emoji: str) -> None:
        self.role.emoji = emoji
        self.emoji_button.set_label(emoji)
        self._changed()

    def _changed(self) -> None:
        if not self._loading:
            self._save()

    def _save_now(self) -> None:
        name = self.name_row.get_text().strip()
        if name:
            self.role.name = name
            self.set_title(name)
        self.role.signature = self.signature_row.get_text()
        self.role.ai_style = self.ai_style_row.get_text()
        i = self.language_row.get_selected()
        self.role.language = self._lang_codes[i] if i < len(self._lang_codes) else None
        i = self.visibility_row.get_selected()
        self.role.visibility = self._vis_codes[i] if i < len(self._vis_codes) else None
        self.store.save_role(self.role)

    @Gtk.Template.Callback()
    def on_delete(self, *_args: object) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Delete Role “{name}”?").format(name=self.role.name),
            body=_("The profiles stay available in the other roles."))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("delete", _("_Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response == "delete":
                self._save = Debouncer(1, lambda: None)
                self.store.delete_role(self.role.id)  # type: ignore[arg-type]
                self.prefs.pop_subpage()

        dialog.connect("response", on_response)
        dialog.present(self.prefs)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/profile-page.ui")
class DandelionProfilePage(Adw.NavigationPage):
    __gtype_name__ = "DandelionProfilePage"

    avatar: Adw.Avatar = Gtk.Template.Child()
    name_label: Gtk.Label = Gtk.Template.Child()
    handle_label: Gtk.Label = Gtk.Template.Child()
    status_row: Adw.ActionRow = Gtk.Template.Child()
    status_icon: Gtk.Image = Gtk.Template.Child()
    limits_row: Adw.ActionRow = Gtk.Template.Child()
    label_row: Adw.EntryRow = Gtk.Template.Child()
    server_group: Adw.PreferencesGroup = Gtk.Template.Child()
    server_row: Adw.SwitchRow = Gtk.Template.Child()

    def __init__(self, prefs: DandelionPreferences, profile: Profile) -> None:
        super().__init__()
        self.prefs = prefs
        self.app = prefs.app
        self.profile = profile
        self._loading = True
        self.label_row.set_text(profile.label)
        self._loading = False
        self._save = Debouncer(400, lambda: self.app.store.save_profile(self.profile))
        from .core.remote_schedule import server_scheduling, set_server_scheduling
        self.server_group.set_visible(profile.platform == "mastodon")
        self.server_row.set_active(server_scheduling(profile))

        def on_server(row: Adw.SwitchRow, _pspec: object) -> None:
            set_server_scheduling(self.profile, row.get_active())
            self.app.store.save_profile(self.profile)
            self.app.scheduling.schedule_changed()

        self.server_row.connect("notify::active", on_server)
        self._show()
        self.connect("hidden", lambda *_: (self._save.flush(), self.prefs.reload()))

    def _show(self) -> None:
        p = self.profile
        self.set_title(p.label or p.full_handle)
        self.avatar.set_text(p.title)
        self.prefs.avatars.apply(self.avatar, p.avatar_url)
        self.name_label.set_label(p.display_name or p.handle)
        self.handle_label.set_label(f"{p.full_handle} · {_platform_name(self.app, p.platform)}")
        self.status_row.set_subtitle(GLib.markup_escape_text(
            STATUS_TEXT[p.status].capitalize() + (f" – {p.status_detail}" if p.status_detail
                                                  else "")))
        ok = p.status == ProfileStatus.OK
        self.status_icon.set_from_icon_name("object-select-symbolic" if ok
                                            else "dialog-warning-symbolic")
        for c in ("success", "error", "warning"):
            self.status_icon.remove_css_class(c)
        self.status_icon.add_css_class("success" if ok else "error")
        if p.platform in self.app.registry:
            lim = self.app.registry.get(p.platform).limits_for(p)
            parts = [ngettext("{n} character", "{n} characters", lim.max_chars).format(
                n=lim.max_chars),
                ngettext("{n} image", "{n} images", lim.max_images).format(n=lim.max_images)]
            if lim.alt_text_max:
                parts.append(_("alt text up to {n}").format(n=lim.alt_text_max))
            self.limits_row.set_subtitle(" · ".join(parts))

    @Gtk.Template.Callback()
    def on_label_changed(self, *_args: object) -> None:
        if not self._loading:
            self.profile.label = self.label_row.get_text().strip()
            self._save()

    @Gtk.Template.Callback()
    def on_refresh(self, *_args: object) -> None:
        async def run() -> None:
            platform = self.app.registry.get(self.profile.platform)
            self.profile = await platform.refresh_profile(self.profile)
            self.app.store.save_profile(self.profile)
            self._show()
            self.prefs.add_toast(Adw.Toast(title=_("Connection checked")))

        spawn(run())

    @Gtk.Template.Callback()
    def on_relogin(self, *_args: object) -> None:
        hint = self.profile.server if self.profile.platform == "mastodon" else self.profile.handle
        self.prefs.add_profile(self.profile.platform, hint)

    @Gtk.Template.Callback()
    def on_remove(self, *_args: object) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Remove Profile?"),
            body=_("{handle} is removed from Dandelion and its login data is deleted from the "
                   "keyring. Published posts stay online.").format(handle=self.profile.full_handle))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("remove", _("_Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response != "remove":
                return

            async def run() -> None:
                if self.profile.platform in self.app.registry:
                    await self.app.registry.get(self.profile.platform).logout(self.profile)
                self.app.store.delete_profile(self.profile.id)  # type: ignore[arg-type]
                self.prefs.pop_subpage()
                self.prefs.reload()

            spawn(run())

        dialog.connect("response", on_response)
        dialog.present(self.prefs)
