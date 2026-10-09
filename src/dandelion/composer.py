# SPDX-License-Identifier: GPL-3.0-or-later
"""Der Composer: Rolle, Profile, Text mit Varianten, Medien, Vorschau, Senden."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING

import gi

gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Graphene, Gtk, GtkSource, Spelling  # noqa: E402

from .alt_text_dialog import DandelionAltTextDialog
from .core import imaging
from .core.compose import base_text, composition_for, text_hash
from .core.counting import find_hashtags, find_mentions, find_urls
from .core.models import Media, Post, PostState, Profile, Role, Target, Variant
from .core.publisher import AlreadySending
from .core.scheduler import to_utc_iso
from .core.store import EDITABLE_STATES, PostLocked, media_dir
from .schedule_dialog import DandelionScheduleDialog, format_when
from .core.validation import Report, validate
from .net.linkcard import LinkCard, fetch_card
from .send_dialog import DandelionSendDialog
from .util import (
    label_widget,
    CONTENT_LABEL_NAMES,
    LANGUAGES,
    VISIBILITY_LABELS,
    Debouncer,
    first_line,
    format_time,
    spawn,
    system_language,
)
from .widgets.avatars import AvatarCache
from .widgets.counter_ring import DandelionCounterRing
from .widgets.media_tile import MediaTile
from .widgets.preview_tile import PreviewTile
from .widgets.profile_chip import ProfileChip, platform_badge

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

log = logging.getLogger(__name__)
MAIN = "main"


def _rgba_hex(rgba: Gdk.RGBA) -> str:
    return "{:02x}{:02x}{:02x}".format(int(rgba.red * 255), int(rgba.green * 255),
                                       int(rgba.blue * 255))


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/composer.ui")
class DandelionComposer(Adw.BreakpointBin):
    __gtype_name__ = "DandelionComposer"

    main_stack: Gtk.Stack = Gtk.Template.Child()
    layout_view: Adw.MultiLayoutView = Gtk.Template.Child()
    preview_split: Adw.OverlaySplitView = Gtk.Template.Child()
    sheet: Adw.BottomSheet = Gtk.Template.Child()
    sheet_bar_label: Gtk.Label = Gtk.Template.Child()
    role_button: Gtk.MenuButton = Gtk.Template.Child()
    role_emoji: Gtk.Label = Gtk.Template.Child()
    role_label: Gtk.Label = Gtk.Template.Child()
    role_popover: Gtk.Popover = Gtk.Template.Child()
    role_list: Gtk.ListBox = Gtk.Template.Child()
    issues_button: Gtk.MenuButton = Gtk.Template.Child()
    issues_icon: Gtk.Image = Gtk.Template.Child()
    issues_label: Gtk.Label = Gtk.Template.Child()
    issues_list: Gtk.Box = Gtk.Template.Child()
    chips_box: Adw.WrapBox = Gtk.Template.Child()
    variant_group: Adw.ToggleGroup = Gtk.Template.Child()
    card_head: Gtk.Box = Gtk.Template.Child()
    variant_info: Gtk.Box = Gtk.Template.Child()
    variant_info_label: Gtk.Label = Gtk.Template.Child()
    variant_info_button: Gtk.Button = Gtk.Template.Child()
    media_box: Gtk.ScrolledWindow = Gtk.Template.Child()
    strict_counter: DandelionCounterRing = Gtk.Template.Child()
    density_group: Adw.ToggleGroup = Gtk.Template.Child()
    ai_button: Gtk.MenuButton = Gtk.Template.Child()
    ai_revealer: Gtk.Revealer = Gtk.Template.Child()
    ai_title: Gtk.Label = Gtk.Template.Child()
    ai_spinner: Adw.Spinner = Gtk.Template.Child()
    ai_result: Gtk.Label = Gtk.Template.Child()
    ai_tags: Adw.WrapBox = Gtk.Template.Child()
    ai_actions: Gtk.Box = Gtk.Template.Child()
    ai_retry_button: Gtk.Button = Gtk.Template.Child()
    ai_accept_button: Gtk.Button = Gtk.Template.Child()
    schedule_banner: Adw.Banner = Gtk.Template.Child()
    cw_revealer: Gtk.Revealer = Gtk.Template.Child()
    cw_entry: Gtk.Entry = Gtk.Template.Child()
    cw_button: Gtk.ToggleButton = Gtk.Template.Child()
    thread_button: Gtk.ToggleButton = Gtk.Template.Child()
    text_view: GtkSource.View = Gtk.Template.Child()
    text_scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    editor_box: Gtk.Box = Gtk.Template.Child()
    placeholder_label: Gtk.Label = Gtk.Template.Child()
    options_content: Adw.ButtonContent = Gtk.Template.Child()
    mastodon_options: Adw.PreferencesGroup = Gtk.Template.Child()
    bluesky_options: Adw.PreferencesGroup = Gtk.Template.Child()
    media_tiles: Gtk.Box = Gtk.Template.Child()
    add_media_button: Gtk.Button = Gtk.Template.Child()
    language_dropdown: Adw.ComboRow = Gtk.Template.Child()
    visibility_dropdown: Adw.ComboRow = Gtk.Template.Child()
    label_dropdown: Adw.ComboRow = Gtk.Template.Child()
    signature_button: Adw.SwitchRow = Gtk.Template.Child()
    preview_tiles: Gtk.Box = Gtk.Template.Child()
    preview_scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    status_strip: Adw.WrapBox = Gtk.Template.Child()
    filter_hint: Gtk.Box = Gtk.Template.Child()
    filter_label: Gtk.Label = Gtk.Template.Child()

    can_publish = GObject.Property(type=bool, default=False)

    def __init__(self) -> None:
        super().__init__()
        self.app: DandelionApplication | None = None
        self.win: DandelionWindow | None = None
        self.post = Post()
        self.role: Role | None = None
        self.roles: list[Role] = []
        self.profiles: dict[int, Profile] = {}
        self.chips: dict[int, ProfileChip] = {}
        self.buffers: dict[str, GtkSource.Buffer] = {}
        self.report: Report | None = None
        self.link_cards: dict[str, LinkCard | None] = {}
        self._preview_show_all = False
        self._tile_for_profile: dict[int, Gtk.Widget] = {}
        self._loading = False
        self._autosave = Debouncer(800, self.save_now)
        self._refresh = Debouncer(150, self.refresh)
        self._inherit_buffer = GtkSource.Buffer()
        self._style = Adw.StyleManager.get_default()

    # ------------------------------------------------------------------
    # Einrichtung
    # ------------------------------------------------------------------
    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.store = app.store
        self.settings = app.settings
        self.avatars = AvatarCache(app.http)

        self._lang_codes = [c for c, _n in LANGUAGES]
        self.language_dropdown.set_model(Gtk.StringList.new([n for _c, n in LANGUAGES]))
        self.language_dropdown.set_expression(Gtk.PropertyExpression.new(
            Gtk.StringObject, None, "string"))
        self.language_dropdown.connect("notify::selected", self._on_option_changed)
        self._vis_codes = list(VISIBILITY_LABELS)
        self.visibility_dropdown.set_model(Gtk.StringList.new(
            [VISIBILITY_LABELS[c][0] for c in self._vis_codes]))
        self.visibility_dropdown.connect("notify::selected", self._on_option_changed)
        self._label_codes = list(CONTENT_LABEL_NAMES)
        self.label_dropdown.set_model(Gtk.StringList.new(
            [CONTENT_LABEL_NAMES[c] for c in self._label_codes]))
        self.label_dropdown.connect("notify::selected", self._on_option_changed)

        self.buffers[MAIN] = self._new_buffer()
        self.text_view.set_buffer(self.buffers[MAIN])
        self._inherit_buffer.set_text("")
        self._spell = None
        try:
            checker = Spelling.Checker.get_default()
            self._spell_checker = checker
        except Exception:  # libspelling ohne Wörterbücher
            self._spell_checker = None
        self._attach_spelling(self.buffers[MAIN])
        self.text_view.connect("paste-clipboard", self._on_paste)
        self.text_view.connect("notify::buffer", lambda *_: self._sync_placeholder())
        self.text_scroller.get_hadjustment().connect("changed", self._on_text_width)

        # Auf dem ganzen Fenster, in der Capture-Phase: sonst schluckt die
        # Textansicht das Ablegen, und nur der Editorrand nähme Dateien an.
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        self.preview_split.set_show_sidebar(self.settings.get_boolean("show-preview"))
        self._loading = True
        self.density_group.set_active_name(
            "compact" if self.settings.get_boolean("preview-compact") else "full")
        self._loading = False
        self._style.connect("notify::accent-color-rgba", lambda *_: self._update_tags_color())
        self._style.connect("notify::dark", self._on_dark_changed)
        self._apply_scheme(self._inherit_buffer)
        self.layout_view.connect("notify::layout-name", lambda *_: self._on_layout_changed())
        self.sheet.connect("notify::bottom-bar-height", lambda *_: self._sync_bottom_space())

        self._setup_ai()
        self.reload_profiles()
        last = self.store.post_ids([PostState.DRAFT], limit=1)
        if last:
            post = self.store.load_post(last[0])
            if post:
                self.load_post(post)
        else:
            self.new_post(save_current=False)
        self.reload_drafts()
        spawn(self._refresh_profiles())

    def _new_buffer(self) -> GtkSource.Buffer:
        buf = GtkSource.Buffer()
        buf.set_highlight_syntax(False)
        buf.set_highlight_matching_brackets(False)
        accent = self._style.get_accent_color_rgba()
        buf.create_tag("entity", foreground_rgba=accent)
        buf.connect("changed", self._on_buffer_changed)
        buf.connect("changed", lambda *_: self._sync_placeholder())
        self._apply_scheme(buf)
        return buf

    def _apply_scheme(self, buf: GtkSource.Buffer) -> None:
        name = "Adwaita-dark" if self._style.get_dark() else "Adwaita"
        scheme = GtkSource.StyleSchemeManager.get_default().get_scheme(name)
        if scheme:
            buf.set_style_scheme(scheme)

    def _on_dark_changed(self, *_args: object) -> None:
        for buf in [*self.buffers.values(), self._inherit_buffer]:
            self._apply_scheme(buf)

    def _attach_spelling(self, buf: GtkSource.Buffer) -> None:
        if not self._spell_checker:
            return
        adapter = Spelling.TextBufferAdapter.new(buf, self._spell_checker)
        adapter.set_enabled(self.settings.get_boolean("spellcheck"))
        buf._spell_adapter = adapter  # Referenz halten
        if self._spell is None:
            self._spell = adapter
            self.text_view.set_extra_menu(adapter.get_menu_model())
            self.text_view.insert_action_group("spelling", adapter)

    def _update_tags_color(self) -> None:
        accent = self._style.get_accent_color_rgba()
        for buf in self.buffers.values():
            tag = buf.get_tag_table().lookup("entity")
            if tag:
                tag.props.foreground_rgba = accent
        self._refresh()

    async def _refresh_profiles(self) -> None:
        """Prüft beim Start alle Anmeldungen und aktualisiert Limits und Avatare."""
        if os.environ.get("DANDELION_OFFLINE"):
            return
        for profile in list(self.profiles.values()):
            if profile.platform not in self.app.registry:
                continue
            platform = self.app.registry.get(profile.platform)
            try:
                updated = await platform.refresh_profile(profile)
            except Exception:
                log.exception("Profil %s konnte nicht geprüft werden", profile.full_handle)
                continue
            self.store.save_profile(updated)
        self.reload_profiles()

    # ------------------------------------------------------------------
    # Rollen und Profile
    # ------------------------------------------------------------------
    def reload_profiles(self) -> None:
        if not self.app:
            return
        self.profiles = {p.id: p for p in self.store.profiles()}  # type: ignore[misc]
        self.roles = self.store.roles()
        if self.profiles and not self.roles:
            role = self.store.save_role(Role(_("Personal"), "🏠", language=system_language()))
            for pid in self.profiles:
                self.store.set_role_profile(role.id, pid, True)  # type: ignore[arg-type]
            self.roles = [role]
        self.main_stack.set_visible_child_name("composer" if self.profiles else "no-profiles")
        if self.role:
            self.role = next((r for r in self.roles if r.id == self.role.id), None)
        if self.role is None and self.roles:
            last = self.settings.get_string("last-role")
            self.role = next((r for r in self.roles if r.uuid == last), self.roles[0])
            if not self.post.targets:
                self.post.targets = self._default_targets(self.role)
        self.post.targets = [t for t in self.post.targets if t.profile_id in self.profiles]
        self._fill_role_list()
        self._show_role()
        self._build_chips()
        self._refresh()

    def _fill_role_list(self) -> None:
        while (row := self.role_list.get_first_child()) is not None:
            self.role_list.remove(row)
        for role in self.roles:
            row = Adw.ActionRow(title=GLib.markup_escape_text(role.name), activatable=True)
            row.role = role  # type: ignore[attr-defined]
            emoji = Gtk.Label(label=role.emoji or "•")
            emoji.add_css_class(f"role-{role.color}")
            row.add_prefix(emoji)
            n = len(self.store.role_profiles(role.id))  # type: ignore[arg-type]
            row.set_subtitle(ngettext("{n} profile", "{n} profiles", n).format(n=n))
            if self.role and role.id == self.role.id:
                row.add_suffix(Gtk.Image(icon_name="object-select-symbolic"))
            self.role_list.append(row)

    def _show_role(self) -> None:
        role = self.role
        self.role_emoji.set_label(role.emoji if role else "")
        self.role_label.set_label(role.name if role else _("No Role"))
        for c in [c for c in self.role_button.get_css_classes() if c.startswith("role-")]:
            if c != "role-button":
                self.role_button.remove_css_class(c)
        if role:
            self.role_button.add_css_class(f"role-{role.color}")
            self.role_button.update_property([Gtk.AccessibleProperty.LABEL],
                                             [_("Role: {name}").format(name=role.name)])
        has_sig = bool(role and role.signature.strip())
        self.signature_button.set_visible(has_sig)
        if has_sig:
            self.signature_button.set_tooltip_text(
                _("Append signature: {signature}").format(signature=role.signature.strip()))

    def _default_targets(self, role: Role | None) -> list[Target]:
        if not role:
            return []
        return [Target(rp.profile_id, enabled=rp.preselected)
                for rp in self.store.role_profiles(role.id)  # type: ignore[arg-type]
                if rp.profile_id in self.profiles]

    def _build_chips(self) -> None:
        # Im selben Container stehen auch Rollen-Knopf und „an“; nur Chips entfernen
        for widget in getattr(self, "_chip_widgets", []):
            self.chips_box.remove(widget)
        self._chip_widgets: list[Gtk.Widget] = []
        self.chips.clear()
        shown: list[int] = []
        if self.role:
            shown = [rp.profile_id for rp in self.store.role_profiles(self.role.id)  # type: ignore[arg-type]
                     if rp.profile_id in self.profiles]
        shown += [t.profile_id for t in self.post.targets if t.profile_id not in shown]
        enabled = {t.profile_id for t in self.post.targets if t.enabled}
        for pid in shown:
            profile = self.profiles[pid]
            name = self.app.registry.get(profile.platform).name \
                if profile.platform in self.app.registry else profile.platform
            chip = ProfileChip(profile, name, self.avatars)
            chip.set_active(pid in enabled)
            chip.connect("toggled", self._on_chip_toggled)
            self._add_chip_menu(chip)
            chip.set_compact(self.layout_view.get_layout_name() == "narrow")
            self.chips[pid] = chip
            self.chips_box.append(chip)
            self._chip_widgets.append(chip)
        others = [p for p in self.profiles.values() if p.id not in shown]
        if others:
            menu_button = Gtk.MenuButton(icon_name="list-add-symbolic",
                                         tooltip_text=_("More Profiles"))
            menu_button.add_css_class("flat")
            label_widget(menu_button, menu_button.get_tooltip_text() or "")
            menu_button.add_css_class("circular")
            pop = Gtk.Popover()
            box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            box.add_css_class("navigation-sidebar")
            for p in others:
                row = Adw.ActionRow(title=GLib.markup_escape_text(p.full_handle),
                                    subtitle=p.platform.capitalize(), activatable=True)
                row.profile_id = p.id  # type: ignore[attr-defined]
                box.append(row)
            box.connect("row-activated", lambda _b, r: (pop.popdown(),
                                                        self._add_extra_profile(r.profile_id)))
            pop.set_child(box)
            menu_button.set_popover(pop)
            self.chips_box.append(menu_button)
            self._chip_widgets.append(menu_button)

    def _add_chip_menu(self, chip: ProfileChip) -> None:
        group = Gio.SimpleActionGroup()
        act = Gio.SimpleAction.new("own-text", None)
        act.connect("activate", lambda *_: self._create_profile_variant(chip.profile))
        group.add_action(act)
        chip.insert_action_group("chip", group)
        menu = Gio.Menu()
        menu.append(_("Own Text for This Profile"), "chip.own-text")
        pop = Gtk.PopoverMenu.new_from_model(menu)
        pop.set_parent(chip)
        click = Gtk.GestureClick(button=3)
        click.connect("pressed", lambda *_: pop.popup())
        chip.add_controller(click)
        longpress = Gtk.GestureLongPress()
        longpress.connect("pressed", lambda *_: pop.popup())
        chip.add_controller(longpress)

    def _add_extra_profile(self, profile_id: int) -> None:
        self.post.targets.append(Target(profile_id, enabled=True))
        self._build_chips()
        self._changed()

    def _on_chip_toggled(self, chip: ProfileChip) -> None:
        pid = chip.profile.id
        target = next((t for t in self.post.targets if t.profile_id == pid), None)
        if target is None:
            self.post.targets.append(Target(pid, enabled=chip.get_active()))  # type: ignore[arg-type]
        else:
            target.enabled = chip.get_active()
        self._changed()

    def popup_roles(self) -> None:
        if self.roles:
            self.role_button.popup()

    @Gtk.Template.Callback()
    def on_role_activated(self, _list: Gtk.ListBox, row: Adw.ActionRow) -> None:
        self.role_popover.popdown()
        role: Role = row.role  # type: ignore[attr-defined]
        if self.role and role.id == self.role.id:
            return
        prev_role, prev_targets = self.role, self.post.targets
        self._set_role(role)

        def undo() -> None:
            self.role = prev_role
            self.post.role_id = prev_role.id if prev_role else None
            self.post.targets = prev_targets
            self._fill_role_list()
            self._show_role()
            self._build_chips()
            self._changed()

        self.win.toast(_("Role changed to “{name}”").format(name=role.name), _("_Undo"), undo)

    def _set_role(self, role: Role) -> None:
        self.role = role
        self.post.role_id = role.id
        self.post.targets = self._default_targets(role)
        self.post.use_signature = self.settings.get_boolean("append-signature")
        self.settings.set_string("last-role", role.uuid)
        self._loading = True
        self.signature_button.set_active(self.post.use_signature)
        self._select_language(self.post.language or role.language)
        self._select_visibility(role.visibility)
        self._loading = False
        self._fill_role_list()
        self._show_role()
        self._build_chips()
        self._changed()

    @Gtk.Template.Callback()
    def on_add_profile_clicked(self, *_args: object) -> None:
        from .add_profile import DandelionAddProfileDialog
        dialog = DandelionAddProfileDialog(self.app, on_added=lambda _p: self.reload_profiles())
        dialog.present(self.win)

    # ------------------------------------------------------------------
    # Varianten
    # ------------------------------------------------------------------
    def _selected_profiles(self) -> list[Profile]:
        enabled = [t.profile_id for t in self.post.targets if t.enabled]
        return [self.profiles[pid] for pid in enabled if pid in self.profiles]

    def _variant_keys(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = [(MAIN, _("Main Text"))]
        seen: set[str] = set()
        for p in self._selected_profiles():
            if p.platform not in seen and p.platform in self.app.registry:
                seen.add(p.platform)
                keys.append((f"platform:{p.platform}", self.app.registry.get(p.platform).name))
        for v in self.post.variants:
            if v.profile_id is not None and v.profile_id in self.profiles:
                p = self.profiles[v.profile_id]
                keys.append((f"profile:{p.id}", p.label or p.full_handle))
        return keys

    def _rebuild_variant_group(self) -> None:
        keys = self._variant_keys()
        current = self.variant_group.get_active_name() or MAIN
        existing = [self.variant_group.get_toggle(i).get_name()
                    for i in range(self.variant_group.get_n_toggles())]
        wanted = [k for k, _l in keys]
        if existing != wanted:
            self._loading = True
            self.variant_group.remove_all()
            for key, label in keys:
                toggle = Adw.Toggle(name=key, child=self._variant_label(key, label))
                toggle.set_tooltip(label)
                self.variant_group.add(toggle)
            self.variant_group.set_active_name(current if current in wanted else MAIN)
            self._loading = False
        else:
            for i, (key, label) in enumerate(keys):
                self.variant_group.get_toggle(i).set_child(self._variant_label(key, label))
        self.card_head.set_visible(len(keys) > 1)
        self._show_variant()

    def _variant_label(self, key: str, label: str) -> Gtk.Widget:
        """Beschriftung eines Varianten-Tabs; ein Punkt zeigt einen eigenen Text an."""
        box = Gtk.Box(spacing=6, margin_start=6, margin_end=6)
        box.append(Gtk.Label(label=label))
        if self._variant(key):
            dot = Gtk.Box(valign=Gtk.Align.CENTER)
            dot.add_css_class("variant-dot")
            box.append(dot)
            box.update_property([Gtk.AccessibleProperty.LABEL],
                                [_("{name}, own text").format(name=label)])
        return box

    def _variant(self, key: str) -> Variant | None:
        if key.startswith("platform:"):
            platform = key.split(":", 1)[1]
            return next((v for v in self.post.variants
                         if v.platform == platform and v.profile_id is None), None)
        if key.startswith("profile:"):
            pid = int(key.split(":", 1)[1])
            return next((v for v in self.post.variants if v.profile_id == pid), None)
        return None

    def _key_platform_name(self, key: str) -> str:
        if key.startswith("platform:"):
            pid = key.split(":", 1)[1]
            return self.app.registry.get(pid).name if pid in self.app.registry else pid
        pid = int(key.split(":", 1)[1])
        p = self.profiles.get(pid)
        return (p.label or p.full_handle) if p else ""

    @Gtk.Template.Callback()
    def on_variant_changed(self, *_args: object) -> None:
        if not self._loading:
            self._show_variant()
            # Die Vorschau folgt dem Tab; ein „Alle anzeigen“ gilt nur bis zum nächsten Wechsel
            self._preview_show_all = False
            self._update_previews()

    def _show_variant(self) -> None:
        key = self.variant_group.get_active_name() or MAIN
        if key == MAIN:
            self.text_view.set_buffer(self.buffers[MAIN])
            self.text_view.set_editable(True)
            self.text_view.remove_css_class("inherited")
            self.variant_info.set_visible(False)
            self._sync_placeholder()
            return
        name = self._key_platform_name(key)
        variant = self._variant(key)
        if variant:
            buf = self.buffers.get(key)
            if buf is None:
                buf = self._new_buffer()
                self._loading = True
                buf.set_text(variant.body)
                self._loading = False
                self._attach_spelling(buf)
                self.buffers[key] = buf
            self.text_view.set_buffer(buf)
            self.text_view.set_editable(True)
            self.text_view.remove_css_class("inherited")
            changed = variant.base_hash and variant.base_hash != text_hash(self.post.body)
            title = _("{name} uses its own text.").format(name=name)
            if changed:
                title += " " + _("The main text has changed since.")
            self.variant_info_label.set_label(title)
            self.variant_info_button.set_label(_("_Use Main Text"))
        else:
            if key.startswith("profile:"):
                p = self.profiles.get(int(key.split(":", 1)[1]))
                inherited = base_text(self.post, p) if p else self.post.body
            else:
                inherited = self.post.body
            self._inherit_buffer.set_text(inherited)
            self.text_view.set_buffer(self._inherit_buffer)
            self.text_view.set_editable(False)
            self.text_view.add_css_class("inherited")
            self.variant_info_label.set_label(_("{name} uses the main text.").format(name=name))
            self.variant_info_button.set_label(_("_Customize"))
        self.variant_info.set_visible(True)
        self._sync_placeholder()

    @Gtk.Template.Callback()
    def on_variant_banner_clicked(self, *_args: object) -> None:
        key = self.variant_group.get_active_name() or MAIN
        variant = self._variant(key)
        if variant:
            self._discard_variant(key, variant)
        else:
            self._create_variant(key)

    def _create_variant(self, key: str) -> None:
        if key.startswith("platform:"):
            v = Variant(platform=key.split(":", 1)[1], body=self.post.body,
                        base_hash=text_hash(self.post.body))
        else:
            p = self.profiles[int(key.split(":", 1)[1])]
            v = Variant(platform=p.platform, profile_id=p.id, body=base_text(self.post, p),
                        base_hash=text_hash(self.post.body))
        self.post.variants.append(v)
        self.buffers.pop(key, None)
        self._rebuild_variant_group()
        self.text_view.grab_focus()
        self._changed()

    def _create_profile_variant(self, profile: Profile) -> None:
        key = f"profile:{profile.id}"
        if not self._variant(key):
            self._create_variant(key)
        self._rebuild_variant_group()
        self.variant_group.set_active_name(key)

    def _discard_variant(self, key: str, variant: Variant) -> None:
        self.post.variants.remove(variant)
        buf = self.buffers.pop(key, None)
        self._rebuild_variant_group()
        self._changed()

        def undo() -> None:
            self.post.variants.append(variant)
            if buf:
                self.buffers[key] = buf
            self._rebuild_variant_group()
            self.variant_group.set_active_name(key)
            self._changed()

        self.win.toast(_("Own text discarded"), _("_Undo"), undo)

    # ------------------------------------------------------------------
    # Änderungen
    # ------------------------------------------------------------------
    def _on_buffer_changed(self, buf: GtkSource.Buffer) -> None:
        self._highlight(buf)
        if self._loading:
            return
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        if buf is self.buffers.get(MAIN):
            self.post.body = text
        else:
            key = next((k for k, b in self.buffers.items() if b is buf), None)
            variant = self._variant(key) if key else None
            if variant:
                variant.body = text
        self._changed()

    def _highlight(self, buf: GtkSource.Buffer) -> None:
        start, end = buf.get_bounds()
        buf.remove_tag_by_name("entity", start, end)
        text = buf.get_text(start, end, False)
        for span in find_urls(text) + find_mentions(text) + find_hashtags(text):
            buf.apply_tag_by_name("entity", buf.get_iter_at_offset(span.start),
                                  buf.get_iter_at_offset(span.end))

    @Gtk.Template.Callback()
    def on_cw_toggled(self, button: Gtk.ToggleButton) -> None:
        self.cw_revealer.set_reveal_child(button.get_active())
        if button.get_active():
            self.cw_entry.grab_focus()
        if not self._loading:
            self.post.content_warning = self.cw_entry.get_text() if button.get_active() else ""
            self._changed()

    @Gtk.Template.Callback()
    def on_cw_changed(self, entry: Gtk.Entry) -> None:
        if not self._loading and self.cw_button.get_active():
            self.post.content_warning = entry.get_text()
            self._changed()

    @Gtk.Template.Callback()
    def on_thread_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._loading:
            return
        if button.get_active():
            numbering = self.settings.get_string("thread-numbering")
            self.post.thread_mode = "plain" if numbering == "off" else numbering
        else:
            self.post.thread_mode = "off"
        self._changed()

    @Gtk.Template.Callback()
    def on_signature_toggled(self, button: Adw.SwitchRow, *_args: object) -> None:
        if not self._loading:
            self.post.use_signature = button.get_active()
            self._changed()

    def _on_option_changed(self, *_args: object) -> None:
        if self._loading:
            return
        i = self.language_dropdown.get_selected()
        self.post.language = self._lang_codes[i] if i < len(self._lang_codes) else None
        i = self.visibility_dropdown.get_selected()
        self.post.visibility = self._vis_codes[i] if i < len(self._vis_codes) else None
        i = self.label_dropdown.get_selected()
        code = self._label_codes[i] if i < len(self._label_codes) else ""
        self.post.bluesky_label = code or None
        self._set_spell_language(self.post.language)
        self._changed()

    def _select_language(self, code: str | None) -> None:
        code = code or system_language()
        if code in self._lang_codes:
            self.language_dropdown.set_selected(self._lang_codes.index(code))
        self._set_spell_language(code)

    def _select_visibility(self, code: str | None) -> None:
        code = code or "public"
        self.visibility_dropdown.set_selected(self._vis_codes.index(code)
                                              if code in self._vis_codes else 0)

    def _set_spell_language(self, code: str | None) -> None:
        if not self._spell_checker or not code:
            return
        provider = self._spell_checker.get_provider()
        langs = provider.list_languages()
        for i in range(langs.get_n_items()):
            ident = langs.get_item(i).get_code()
            if ident == code or ident.startswith(code + "_"):
                self._spell_checker.set_language(ident)
                return

    def _changed(self) -> None:
        if self._loading:
            return
        self._autosave()
        self._refresh()

    # ------------------------------------------------------------------
    # Prüfen, Zähler, Vorschau
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if not self.app:
            return
        self._rebuild_variant_group()
        profiles = list(self.profiles.values())
        self.report = validate(self.post, self.role, profiles, self.app.registry,
                               self.settings.get_boolean("require-alt-text-everywhere"))
        selected = self._selected_profiles()
        platforms = {p.platform for p in selected}
        self.mastodon_options.set_visible("mastodon" in platforms)
        self.bluesky_options.set_visible("bluesky" in platforms and bool(self.post.media))
        self._sync_options_label()
        self.thread_button.set_visible(any(
            self.app.registry.get(p).default_limits().supports_threads
            for p in platforms if p in self.app.registry))
        self._update_status_strip()
        self._rebuild_ai_menu()
        self._update_issues()
        self._update_media()
        self._update_previews()
        self._maybe_fetch_card()
        self.props.can_publish = self.report.can_send and bool(selected)
        if self.win:
            self.win._sync_publish()

    def publish_tooltip(self) -> str:
        if not self.report:
            return ""
        errors = self.report.errors
        if not errors:
            return _("Publish to all selected profiles")
        return ngettext("Cannot publish: {n} problem", "Cannot publish: {n} problems",
                        len(errors)).format(n=len(errors))

    def _update_status_strip(self) -> None:
        """Eine kompakte Zeile pro Profil: Avatar, Name, Zähler, Status."""
        while (child := self.status_strip.get_first_child()) is not None:
            self.status_strip.remove(child)
        targets = self.report.targets if self.report else []
        over = 0
        for t in targets:
            c = t.count
            btn = Gtk.Button()
            btn.add_css_class("status-chip")
            box = Gtk.Box(spacing=5)
            avatar = Adw.Avatar(size=18, text=t.profile.title, show_initials=True)
            self.avatars.apply(avatar, t.profile.avatar_url)
            overlay = Gtk.Overlay(child=avatar)
            overlay.add_overlay(platform_badge(t.profile.platform, 8))
            box.append(overlay)
            platform_label = Gtk.Label(label=t.platform.name)
            platform_label.add_css_class("dim-label")
            box.append(platform_label)
            box.append(Gtk.Label(label=t.profile.label or t.profile.handle, ellipsize=3,
                                 max_width_chars=20))
            counter = Gtk.Label(label=f"{c.used}/{c.limit}")
            counter.add_css_class("numeric")
            counter.add_css_class("dim-label")
            box.append(counter)
            if len(t.parts) > 1:
                parts_label = Gtk.Label(label=f"· {len(t.parts)}×")
                parts_label.add_css_class("dim-label")
                parts_label.set_tooltip_text(ngettext("{n} part", "{n} parts", len(t.parts)).format(
                    n=len(t.parts)))
                box.append(parts_label)
            state = _("within the limit")
            errors = [i for i in t.issues if i.severity == "error"]
            if c.over:
                over += 1
                state = _("over the limit")
                counter.remove_css_class("dim-label")
                counter.add_css_class("error")
            elif c.ratio >= 0.9:
                state = _("close to the limit")
                counter.remove_css_class("dim-label")
                counter.add_css_class("warning")
            if t.issues:
                icon = Gtk.Image(icon_name="dialog-error-symbolic" if errors
                                 else "dialog-warning-symbolic")
                icon.add_css_class("error" if errors else "warning")
                box.append(icon)
            btn.set_child(box)
            text = _("{platform} {handle}: {used} of {limit} characters, {state}").format(
                platform=t.platform.name, handle=t.profile.full_handle, used=c.used,
                limit=c.limit, state=state)
            if t.issues:
                text += ". " + " ".join(i.message for i in t.issues)
            btn.update_property([Gtk.AccessibleProperty.LABEL], [text])
            btn.set_tooltip_text(text)
            btn.connect("clicked", lambda _b, pid=t.profile.id: self._scroll_to_preview(pid))
            self.status_strip.append(btn)
        self.status_strip.set_visible(len(targets) > 1)
        self._update_strict_counter(targets)
        summary = _("Preview")
        if targets:
            summary += " · " + ngettext("{n} profile", "{n} profiles", len(targets)).format(
                n=len(targets))
        if over:
            summary += " · " + ngettext("{n} over the limit", "{n} over the limit",
                                        over).format(n=over)
        self.sheet_bar_label.set_label(summary)

    def _update_issues(self) -> None:
        while (child := self.issues_list.get_first_child()) is not None:
            self.issues_list.remove(child)
        rep = self.report
        # Ein leerer Beitrag ist kein „Problem“, Senden ist ohnehin gesperrt
        if not rep or rep.issue_count == 0 or self.post.is_empty():
            self.issues_button.set_visible(False)
            return
        groups: list[tuple[str, list]] = []
        if rep.general:
            groups.append((_("All Profiles"), rep.general))
        for t in rep.targets:
            if t.issues:
                groups.append((f"{t.platform.name} · {t.profile.full_handle}", t.issues))
        for title, issues in groups:
            head = Gtk.Label(label=title, xalign=0, ellipsize=3)
            head.add_css_class("heading")
            self.issues_list.append(head)
            for issue in issues:
                row = Gtk.Box(spacing=8)
                icon = Gtk.Image(icon_name="dialog-error-symbolic" if issue.severity == "error"
                                 else "dialog-warning-symbolic", valign=Gtk.Align.START)
                icon.add_css_class("error" if issue.severity == "error" else "warning")
                row.append(icon)
                row.append(Gtk.Label(label=issue.message, xalign=0, wrap=True, hexpand=True,
                                     max_width_chars=40))
                self.issues_list.append(row)
        n_err, n_warn = len(rep.errors), len(rep.warnings)
        text = ngettext("{n} problem", "{n} problems", n_err + n_warn).format(n=n_err + n_warn)
        self.issues_label.set_label(str(n_err + n_warn))
        self.issues_button.set_tooltip_text(text)
        self.issues_button.update_property([Gtk.AccessibleProperty.LABEL], [text])
        self.issues_icon.set_from_icon_name("dialog-error-symbolic" if n_err
                                            else "dialog-warning-symbolic")
        for w in (self.issues_icon, self.issues_label):
            w.remove_css_class("error")
            w.remove_css_class("warning")
            w.add_css_class("error" if n_err else "warning")
        self.issues_button.set_visible(True)

    def _alt_required(self) -> bool:
        if self.settings.get_boolean("require-alt-text-everywhere"):
            return bool(self._selected_profiles())
        return any(t.limits.alt_text_required for t in (self.report.targets if self.report else []))

    def _update_media(self) -> None:
        while (child := self.media_tiles.get_first_child()) is not None:
            self.media_tiles.remove(child)
        required = self._alt_required()
        total = len(self.post.media)
        self.media_box.set_visible(total > 0)
        for i, m in enumerate(self.post.media):
            self.media_tiles.append(MediaTile(
                m, i, total, required, on_edit_alt=self._edit_alt,
                on_remove=self._remove_media, on_move=self._move_media))

    def _update_strict_counter(self, targets: list) -> None:  # type: ignore[type-arg]
        """Ring in der Werkzeugleiste: das Profil, das seinem Limit am nächsten ist."""
        ring = self.strict_counter
        if not targets:
            ring.set_visible(False)
            return

        def tightness(t) -> float:  # type: ignore[no-untyped-def]
            c = t.count
            ratio = c.used / c.limit if c.limit else 0.0
            if c.bytes_limit:
                ratio = max(ratio, (c.bytes_used or 0) / c.bytes_limit)
            return ratio

        t = max(targets, key=tightness)
        c = t.count
        ring.set_count(c.used, c.limit)
        ring.set_visible(True)
        text = _("Strictest limit: {platform} {handle}, {used} of {limit} characters").format(
            platform=t.platform.name, handle=t.profile.full_handle, used=c.used, limit=c.limit)
        ring.set_tooltip_text(text)
        ring.update_property([Gtk.AccessibleProperty.LABEL], [text])

    def _sync_options_label(self) -> None:
        parts = []
        item = self.language_dropdown.get_selected_item()
        if item is not None:
            parts.append(item.get_string())
        if self.mastodon_options.get_visible():
            item = self.visibility_dropdown.get_selected_item()
            if item is not None:
                parts.append(item.get_string())
        self.options_content.set_label(" · ".join(parts))

    def _sync_placeholder(self) -> None:
        buf = self.text_view.get_buffer()
        self.placeholder_label.set_visible(buf.get_char_count() == 0
                                           and self.text_view.get_editable())

    def _on_text_width(self, adj: Gtk.Adjustment) -> None:
        """Hält die Textspalte bei breitem Fenster mittig und lesbar breit."""
        width = int(adj.get_page_size())
        margin = max(16, (width - 728) // 2)
        if margin != self.placeholder_label.get_margin_start():
            self.text_view.set_left_margin(margin)
            self.text_view.set_right_margin(margin)
            self.placeholder_label.set_margin_start(margin)

    @Gtk.Template.Callback()
    def on_emoji_clicked(self, *_args: object) -> None:
        self.text_view.grab_focus()
        self.text_view.emit("insert-emoji")

    @Gtk.Template.Callback()
    def on_density_changed(self, *_args: object) -> None:
        if not self.app or self._loading:
            return
        self.settings.set_boolean("preview-compact",
                                  self.density_group.get_active_name() != "full")
        self._update_previews()

    def _preview_filter(self) -> tuple[str | None, int | None, str]:
        """(Plattform, Profil, Beschriftung) passend zum aktiven Varianten-Tab."""
        key = self.variant_group.get_active_name() or MAIN
        if self._preview_show_all or key == MAIN:
            return None, None, ""
        if key.startswith("platform:"):
            pid = key.split(":", 1)[1]
            return pid, None, self._key_platform_name(key)
        profile_id = int(key.split(":", 1)[1])
        return None, profile_id, self._key_platform_name(key)

    def _update_previews(self) -> None:
        while (child := self.preview_tiles.get_first_child()) is not None:
            self.preview_tiles.remove(child)
        self._tile_for_profile.clear()
        targets = self.report.targets if self.report else []
        if not targets:
            self.filter_hint.set_visible(False)
            status = Adw.StatusPage(icon_name="view-reveal-symbolic", title=_("No Preview"),
                                    description=_("Select a profile to see how the post "
                                                  "will look."))
            status.add_css_class("compact")
            self.preview_tiles.append(status)
            return

        platform_filter, profile_filter, label = self._preview_filter()
        if platform_filter:
            shown = [t for t in targets if t.profile.platform == platform_filter]
        elif profile_filter is not None:
            shown = [t for t in targets if t.profile.id == profile_filter]
        else:
            shown = list(targets)
        self.filter_hint.set_visible(bool(label))
        if label:
            self.filter_label.set_label(_("Filtered: {name}").format(name=label))

        # Gleich aussehende Profile zu einer Kachel zusammenfassen
        accent = _rgba_hex(self._style.get_accent_color_rgba())
        groups: dict[tuple, list] = {}
        for t in shown:
            comp = composition_for(self.post, t.profile, self.role)
            key = (
                t.platform.id,
                t.platform.display_text(comp.text),
                comp.content_warning if t.limits.supports_content_warning else "",
                comp.content_label or "",
                tuple((m.path, m.alt_text) for m in comp.media),
                t.count.used, t.count.limit, tuple(t.parts),
                tuple((i.severity, i.code, i.message) for i in t.issues),
            )
            groups.setdefault(key, []).append((t, comp))

        def rank(items: list) -> tuple[int, int]:
            issues = items[0][0].issues
            severity = 0 if any(i.severity == "error" for i in issues) else 1 if issues else 2
            order = [p.id for p in self.app.registry.all()].index(items[0][0].platform.id) \
                if items[0][0].platform.id in [p.id for p in self.app.registry.all()] else 99
            return severity, order

        for items in sorted(groups.values(), key=rank):
            t, comp = items[0]
            urls = find_urls(comp.text)
            card = self.link_cards.get(urls[0].value) if urls else None
            compact = (self.settings.get_boolean("preview-compact")
                       or self.layout_view.get_layout_name() == "narrow")
            tile = PreviewTile(t.platform, [it[0].profile for it in items], comp, t.limits,
                               t.count, self.avatars, card, accent, t.issues, compact=compact,
                               parts=t.parts)
            for it in items:
                self._tile_for_profile[it[0].profile.id] = tile
            self.preview_tiles.append(tile)

    def _scroll_to_preview(self, profile_id: int) -> None:
        if profile_id not in self._tile_for_profile:
            # Durch den Tab-Filter ausgeblendet: vorübergehend alle zeigen
            self._preview_show_all = True
            self._update_previews()
        tile = self._tile_for_profile.get(profile_id)
        if tile is None:
            return
        if self.layout_view.get_layout_name() == "narrow":
            self.sheet.set_open(True)
        else:
            self.preview_split.set_show_sidebar(True)

        def scroll() -> bool:
            ok, point = tile.compute_point(self.preview_tiles.get_parent(),
                                           Graphene.Point().init(0, 0))
            if ok:
                adj = self.preview_scroller.get_vadjustment()
                adj.set_value(max(0.0, point.y - 12))
            tile.add_css_class("flash")
            GLib.timeout_add(900, lambda: (tile.remove_css_class("flash"), False)[1])
            return False

        GLib.idle_add(scroll)

    @Gtk.Template.Callback()
    def on_show_all_previews(self, *_args: object) -> None:
        self._preview_show_all = True
        self._update_previews()

    def _maybe_fetch_card(self) -> None:
        texts = [self.post.body] + [v.body for v in self.post.variants]
        for text in texts:
            urls = find_urls(text)
            if urls and urls[0].value not in self.link_cards:
                url = urls[0].value
                self.link_cards[url] = None
                spawn(self._fetch_card(url))

    async def _fetch_card(self, url: str) -> None:
        card = await fetch_card(self.app.http, url)
        self.link_cards[url] = card
        if card:
            self._refresh()

    # ------------------------------------------------------------------
    # Medien
    # ------------------------------------------------------------------
    def open_file_dialog(self) -> None:
        dialog = Gtk.FileDialog(title=_("Add Images"), modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(name=_("Images and Videos"))
        f.add_mime_type("image/*")
        f.add_mime_type("video/*")
        filters.append(f)
        dialog.set_filters(filters)
        dialog.set_default_filter(f)

        def done(d: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                files = d.open_multiple_finish(result)
            except GLib.Error:
                return
            self.add_files([files.get_item(i) for i in range(files.get_n_items())])

        dialog.open_multiple(self.win, None, done)

    def add_files(self, files: list[Gio.File]) -> None:
        added = 0
        for f in files:
            path = f.get_path()
            if not path:
                continue
            try:
                dest, info = imaging.import_file(path, media_dir())
            except (OSError, GLib.Error) as e:
                self.win.toast(_("Could not add “{name}”").format(name=f.get_basename()))
                log.info("Datei nicht importiert: %s", e)
                continue
            if not (info.mime.startswith("image/") or info.mime.startswith("video/")):
                self.win.toast(_("“{name}” is not an image or video").format(name=f.get_basename()))
                continue
            self.post.media.append(Media(path=str(dest), sha256=info.sha256, mime=info.mime,
                                         bytes=info.bytes, width=info.width, height=info.height))
            added += 1
        if added:
            self._changed()

    def _on_drop(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        self.add_files(list(value.get_files()))
        return True

    def _on_paste(self, view: GtkSource.View) -> None:
        clipboard = view.get_clipboard()
        formats = clipboard.get_formats()
        if formats.contain_gtype(Gdk.FileList) and not formats.contain_mime_type("text/plain"):
            view.stop_emission_by_name("paste-clipboard")

            def got_files(cb: Gdk.Clipboard, res: Gio.AsyncResult) -> None:
                try:
                    value = cb.read_value_finish(res)
                except GLib.Error:
                    return
                self.add_files(list(value.get_files()))

            clipboard.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, got_files)
        elif formats.contain_gtype(Gdk.Texture) and not formats.contain_mime_type("text/plain"):
            view.stop_emission_by_name("paste-clipboard")

            def got_texture(cb: Gdk.Clipboard, res: Gio.AsyncResult) -> None:
                try:
                    texture = cb.read_texture_finish(res)
                except GLib.Error:
                    return
                data = texture.save_to_png_bytes().get_data()
                dest, info = imaging.import_bytes(bytes(data), "image/png", media_dir())
                self.post.media.append(Media(path=str(dest), sha256=info.sha256, mime=info.mime,
                                             bytes=info.bytes, width=info.width,
                                             height=info.height))
                self._changed()

            clipboard.read_texture_async(None, got_texture)

    def _edit_alt(self, media: Media) -> None:
        limit, limit_platform, hints = None, None, []
        for t in self.report.targets if self.report else []:
            lim = t.limits.alt_text_max
            if lim and (limit is None or lim < limit):
                limit, limit_platform = lim, t.platform.name
        if media.width and media.height:
            ratio = media.width / media.height
            if ratio < 0.75 or ratio > 2.0:
                hints.append(_("Very tall or wide images are cropped in the timeline preview "
                               "on most platforms."))

        def done(text: str) -> None:
            media.alt_text = text
            self._changed()

        dialog: DandelionAltTextDialog
        ai_on = self.app.ai.enabled
        dialog = DandelionAltTextDialog(
            media, limit, limit_platform, hints, done,
            ai_suggest=(lambda then: self.app.ai.confirm_privacy(dialog, True, then))
            if ai_on else None,
            ai_generate=self.ai_alt_text if ai_on else None,
            ai_provider=self.app.ai.provider().name if ai_on else "")
        dialog.present(self.win)

    def _remove_media(self, media: Media) -> None:
        idx = self.post.media.index(media)
        self.post.media.remove(media)
        self._changed()

        def undo() -> None:
            self.post.media.insert(idx, media)
            self._changed()

        self.win.toast(_("Media removed"), _("_Undo"), undo)

    def _move_media(self, media: Media, delta: int) -> None:
        i = self.post.media.index(media)
        j = max(0, min(len(self.post.media) - 1, i + delta))
        self.post.media.insert(j, self.post.media.pop(i))
        self._changed()

    # ------------------------------------------------------------------
    # Entwürfe
    # ------------------------------------------------------------------
    def set_preview_visible(self, visible: bool) -> None:
        if self.layout_view.get_layout_name() == "narrow":
            self.sheet.set_open(visible)
        else:
            self.preview_split.set_show_sidebar(visible)

    def _on_layout_changed(self) -> None:
        narrow = self.layout_view.get_layout_name() == "narrow"
        for chip in self.chips.values():
            chip.set_compact(narrow)
        self._sync_bottom_space()

    def _sync_bottom_space(self) -> None:
        """Im schmalen Layout liegt die Vorschau-Leiste über dem Editor: Platz freihalten."""
        narrow = self.layout_view.get_layout_name() == "narrow"
        self.editor_box.set_margin_bottom(self.sheet.get_bottom_bar_height() if narrow else 0)

    def reload_drafts(self) -> None:
        if self.win:
            self.win.archive.reload()

    def delete_draft(self, post_id: int) -> None:
        self.store.mark_post_deleted(post_id, True)
        if post_id == self.post.id:
            self.new_post(save_current=False)
        self.reload_drafts()

        def undo() -> None:
            self.store.mark_post_deleted(post_id, False)
            self.reload_drafts()

        self.win.toast(_("Draft deleted"), _("_Undo"), undo)

    def new_post(self, save_current: bool = True) -> None:
        if save_current:
            self.save_now()
        post = Post(role_id=self.role.id if self.role else None,
                    use_signature=self.settings.get_boolean("append-signature"),
                    targets=self._default_targets(self.role))
        self.load_post(post)
        if self.win:
            self.win.show_view("composer")
        self.text_view.grab_focus()

    def load_post(self, post: Post) -> None:
        self._loading = True
        self.post = post
        if post.role_id:
            self.role = next((r for r in self.roles if r.id == post.role_id), self.role)
        for key in [k for k in self.buffers if k != MAIN]:
            del self.buffers[key]
        self.buffers[MAIN].set_text(post.body)
        self.buffers[MAIN].set_modified(False)
        self.cw_button.set_active(bool(post.content_warning))
        self.cw_entry.set_text(post.content_warning)
        self.cw_revealer.set_reveal_child(bool(post.content_warning))
        self.signature_button.set_active(post.use_signature)
        self.thread_button.set_active(post.thread_mode != "off")
        self._select_language(post.language or (self.role.language if self.role else None))
        self._select_visibility(post.visibility or (self.role.visibility if self.role else None))
        label = post.bluesky_label or ""
        self.label_dropdown.set_selected(self._label_codes.index(label)
                                         if label in self._label_codes else 0)
        if self.variant_group.get_n_toggles():
            self.variant_group.set_active_name(MAIN)
        self._loading = False
        # Werte aus den Auswahlfeldern übernehmen (Vorbelegung aus der Rolle)
        self._on_option_changed()
        self._fill_role_list()
        self._show_role()
        self._build_chips()
        self.text_view.set_buffer(self.buffers[MAIN])
        self._show_schedule_banner()
        self.refresh()
        self.reload_drafts()

    def save_now(self, toast: bool = False) -> None:
        self._autosave_cancel()
        if not self.app or str(self.post.state) not in EDITABLE_STATES:
            return
        if self.post.id is None and self.post.is_empty():
            return
        new = self.post.id is None
        if self.post.state != PostState.DRAFT:
            GLib.idle_add(lambda: (self.app.scheduling._queue_remote_sync(5), False)[1])
        try:
            self.store.save_post(self.post, guard_editable=True)
        except PostLocked:
            # Der Hintergrunddienst hat den Beitrag inzwischen gesendet
            self.win.toast(_("This post has been published in the meantime"))
            self.new_post(save_current=False)
            return
        if new:
            self.reload_drafts()
        if toast:
            self.win.toast(_("Draft saved"))

    def _autosave_cancel(self) -> None:
        if self._autosave._source:
            GLib.source_remove(self._autosave._source)
            self._autosave._source = 0

    # ------------------------------------------------------------------
    # KI-Assistent (nur Vorschläge, nichts wird ungefragt übernommen)
    # ------------------------------------------------------------------
    _TRANSLATE = (("de", "Deutsch"), ("en", "English"), ("fr", "Français"), ("es", "Español"),
                  ("it", "Italiano"), ("nl", "Nederlands"))

    def _setup_ai(self) -> None:
        self._ai_task = None
        self._ai_request: tuple[str, str, str] | None = None   # (Art, Argument, Ziel-Tab)
        self._ai_answer: str | list[str] | None = None
        group = Gio.SimpleActionGroup()
        for name in ("rephrase", "translate", "adapt"):
            act = Gio.SimpleAction.new(name, GLib.VariantType.new("s"))
            act.connect("activate", lambda a, v, n=name: self._ai_start(n, v.get_string()))
            group.add_action(act)
        tags = Gio.SimpleAction.new("hashtags", None)
        tags.connect("activate", lambda *_: self._ai_start("hashtags", ""))
        group.add_action(tags)
        self.insert_action_group("ai", group)
        self.settings.bind("ai-enabled", self.ai_button, "visible", Gio.SettingsBindFlags.GET)
        self.settings.connect("changed::ai-enabled", lambda *_: (
            None if self.settings.get_boolean("ai-enabled") else self.on_ai_discard()))

    def _rebuild_ai_menu(self) -> None:
        menu = Gio.Menu()
        tone = Gio.Menu()
        for mode, label in (("shorter", _("Shorter")), ("longer", _("Longer")),
                            ("casual", _("More Casual")), ("factual", _("More Factual"))):
            tone.append(label, f"ai.rephrase::{mode}")
        menu.append_section(None, tone)
        fix = Gio.Menu()
        fix.append(_("Correct Spelling and Grammar"), "ai.rephrase::correct")
        translate = Gio.Menu()
        for _code, name in self._TRANSLATE:
            translate.append(name, f"ai.translate::{name}")
        fix.append_submenu(_("Translate"), translate)
        menu.append_section(None, fix)
        extra = Gio.Menu()
        platforms: list[str] = []
        for p in self._selected_profiles():
            if p.platform not in platforms and p.platform in self.app.registry:
                platforms.append(p.platform)
        if platforms:
            adapt = Gio.Menu()
            for pid in platforms:
                adapt.append(self.app.registry.get(pid).name, f"ai.adapt::{pid}")
            extra.append_submenu(_("Adapt for Platform"), adapt)
        extra.append(_("Suggest Hashtags"), "ai.hashtags")
        menu.append_section(None, extra)
        self.ai_button.set_menu_model(menu)

    def _ai_source(self, key: str) -> str:
        """Text des Tabs, auf den sich der Vorschlag bezieht."""
        if key == MAIN:
            return self.post.body
        variant = self._variant(key)
        if variant:
            return variant.body
        if key.startswith("profile:"):
            p = self.profiles.get(int(key.split(":", 1)[1]))
            return base_text(self.post, p) if p else self.post.body
        return self.post.body

    def _ai_start(self, kind: str, arg: str) -> None:
        key = self.variant_group.get_active_name() or MAIN
        if kind == "adapt":
            key = f"platform:{arg}"
            source = self._ai_source(key) if self._variant(key) else self.post.body
        else:
            source = self._ai_source(key)
        if not source.strip():
            self.win.toast(_("Write some text first"))
            return
        self._ai_request = (kind, arg, key)
        self.app.ai.confirm_privacy(self.win, False, lambda: self._ai_run(source))

    def _ai_run(self, source: str) -> None:
        from .ai import tasks
        kind, arg, key = self._ai_request  # type: ignore[misc]
        titles = {"shorter": _("Shorter"), "longer": _("Longer"), "casual": _("More Casual"),
                  "factual": _("More Factual"), "correct": _("Corrected")}
        if kind == "rephrase":
            title = titles.get(arg, arg)
        elif kind == "translate":
            title = _("Translation: {language}").format(language=arg)
        elif kind == "adapt":
            title = _("Adapted for {platform}").format(platform=self.app.registry.get(arg).name)
        else:
            title = _("Hashtag Suggestions")
        provider = self.app.ai.provider().name
        self.ai_title.set_label(f"{title} · {provider}")
        self.ai_result.set_label(_("Waiting for the answer"))
        self.ai_result.add_css_class("dim-label")
        self.ai_result.set_visible(True)
        self.ai_tags.set_visible(False)
        self.ai_spinner.set_visible(True)
        self.ai_accept_button.set_sensitive(False)
        self.ai_retry_button.set_sensitive(False)
        self.ai_revealer.set_reveal_child(True)
        self._ai_answer = None

        async def run() -> None:
            ctx = await self.app.ai.context(self.role)
            if kind == "rephrase":
                answer: str | list[str] = await tasks.rephrase(ctx, source, arg)
            elif kind == "translate":
                answer = await tasks.translate(ctx, source, arg)
            elif kind == "adapt":
                platform = self.app.registry.get(arg)
                limits = min((platform.limits_for(p) for p in self._selected_profiles()
                              if p.platform == arg), key=lambda lim: lim.max_chars,
                             default=platform.default_limits())
                answer = await tasks.adapt(ctx, source, arg, platform.name, limits.max_chars)
            else:
                pid = arg or (key.split(":", 1)[1] if key.startswith("platform:") else None)
                answer = await tasks.hashtags(ctx, source, pid)
            self._ai_show(answer)

        def failed(e: BaseException) -> None:
            self.ai_spinner.set_visible(False)
            self.ai_retry_button.set_sensitive(True)
            self.ai_result.set_label(getattr(e, "message", None) or str(e))
            log.info("KI-Anfrage fehlgeschlagen: %s", getattr(e, "detail", e))

        self._ai_source_text = source
        self._ai_task = spawn(run(), on_error=failed)

    def _ai_show(self, answer: str | list[str]) -> None:
        self._ai_answer = answer
        self.ai_spinner.set_visible(False)
        self.ai_retry_button.set_sensitive(True)
        self.ai_result.remove_css_class("dim-label")
        if isinstance(answer, list):
            self.ai_result.set_visible(not answer)
            self.ai_result.set_label(_("No suggestions"))
            for child in list(self._ai_tag_buttons()):
                self.ai_tags.remove(child)
            for tag in answer:
                btn = Gtk.ToggleButton(label=tag, active=True)
                btn.add_css_class("tag-chip")
                self.ai_tags.append(btn)
            self.ai_tags.set_visible(bool(answer))
            self.ai_accept_button.set_sensitive(bool(answer))
        else:
            self.ai_result.set_label(answer)
            self.ai_accept_button.set_sensitive(bool(answer.strip()))

    def _ai_tag_buttons(self) -> list[Gtk.ToggleButton]:
        out, child = [], self.ai_tags.get_first_child()
        while child is not None:
            out.append(child)
            child = child.get_next_sibling()
        return out

    @Gtk.Template.Callback()
    def on_ai_discard(self, *_args: object) -> None:
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
        self._ai_answer = None
        self.ai_revealer.set_reveal_child(False)

    @Gtk.Template.Callback()
    def on_ai_retry(self, *_args: object) -> None:
        if self._ai_request:
            self._ai_run(self._ai_source_text)

    @Gtk.Template.Callback()
    def on_ai_accept(self, *_args: object) -> None:
        if self._ai_request is None or self._ai_answer is None:
            return
        kind, arg, key = self._ai_request
        if isinstance(self._ai_answer, list):
            tags = [b.get_label() for b in self._ai_tag_buttons() if b.get_active()]
            current = self._ai_source(key)
            tags = [t for t in tags if t.lower() not in current.lower()]
            if not tags:
                self.on_ai_discard()
                return
            last = current.rstrip().splitlines()[-1] if current.strip() else ""
            joiner = " " if last.startswith("#") else "\n\n"
            new_text = current.rstrip() + joiner + " ".join(tags)
        else:
            new_text = self._ai_answer
        self._apply_ai_text(key, new_text)
        self.ai_revealer.set_reveal_child(False)

    def _apply_ai_text(self, key: str, text: str) -> None:
        """Übernimmt Text in den Ziel-Tab; rückgängig per Toast oder Strg+Z."""
        created = False
        if key != MAIN and self._variant(key) is None:
            self._create_variant(key)
            created = True
        if key != MAIN:
            self._rebuild_variant_group()
            self.variant_group.set_active_name(key)
            self._show_variant()
        buf = self.buffers[MAIN] if key == MAIN else self.buffers.get(key)
        if buf is None:
            return
        old = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        buf.begin_user_action()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        buf.insert(buf.get_start_iter(), text)
        buf.end_user_action()

        def undo() -> None:
            variant = self._variant(key)
            if created and variant:
                self._discard_variant_silent(key, variant)
                return
            target = self.buffers[MAIN] if key == MAIN else self.buffers.get(key)
            if target:
                target.begin_user_action()
                target.delete(target.get_start_iter(), target.get_end_iter())
                target.insert(target.get_start_iter(), old)
                target.end_user_action()

        self.win.toast(_("Suggestion applied"), _("_Undo"), undo)

    def _discard_variant_silent(self, key: str, variant: Variant) -> None:
        self.post.variants.remove(variant)
        self.buffers.pop(key, None)
        self._rebuild_variant_group()
        self.variant_group.set_active_name(MAIN)
        self._show_variant()
        self._changed()

    async def ai_alt_text(self, media: Media, limit: int | None, previous: str = "",
                          instruction: str = "") -> str:
        """Alt-Text-Vorschlag für ein Bild (vom Alt-Text-Dialog aufgerufen)."""
        from .ai import ImageInput, tasks
        data = imaging.load_bytes(media.path)
        mime = media.mime
        # Auch kleine Dateien mit vielen Pixeln verkleinern: Mehr als 1600 px
        # verbessern keinen Alt-Text, kosten aber Bild-Tokens.
        large = max(media.width or 0, media.height or 0) > 1600
        if large or len(data) > 1_500_000 or mime not in ("image/jpeg", "image/png",
                                                          "image/webp"):
            data, mime, _w, _h = imaging.shrink_to(data, 1_500_000, max_dim=1600)
        ctx = await self.app.ai.context(self.role)
        code = self.post.language or (self.role.language if self.role else None) or "de"
        language = dict(LANGUAGES).get(code, code)
        return await tasks.alt_text(ctx, ImageInput(mime, data), limit, language,
                                    self.post.body, previous, instruction,
                                    self.settings.get_int("ai-alt-text-words"))

    # ------------------------------------------------------------------
    # Planen
    # ------------------------------------------------------------------
    def _show_schedule_banner(self) -> None:
        post = self.post
        if post.state == PostState.DRAFT or not post.scheduled_at:
            self.schedule_banner.set_revealed(False)
            if self.win:
                self.win.sync_title()
            return
        when = format_when(datetime.fromisoformat(post.scheduled_at), post.timezone)
        title = {
            PostState.SCHEDULED: _("Scheduled for {when}. Changes are saved automatically."),
            PostState.PAUSED: _("Paused, planned for {when}."),
            PostState.MISSED: _("Missed, it was planned for {when}."),
        }.get(post.state, "{when}").format(when=when)
        self.schedule_banner.set_title(title)
        self.schedule_banner.set_revealed(True)
        if self.win:
            self.win.sync_title()

    @Gtk.Template.Callback()
    def on_unschedule(self, *_args: object) -> None:
        if self.post.id is None:
            return
        prev = (self.post.state, self.post.scheduled_at)
        self.post.state = PostState.DRAFT
        self.post.scheduled_at = None
        self.save_now()
        self._show_schedule_banner()
        self.app.scheduling.schedule_changed()

        def undo() -> None:
            self.post.state, self.post.scheduled_at = prev
            self.save_now()
            self._show_schedule_banner()
            self.app.scheduling.schedule_changed()

        self.win.toast(_("Schedule removed, the post is a draft again"), _("_Undo"), undo)

    def edit_post(self, post_id: int) -> None:
        if post_id != self.post.id:
            self.save_now()
            post = self.store.load_post(post_id)
            if post is None:
                return
            self.load_post(post)
        self.win.show_view("composer")

    def next_slot(self, exclude_iso: str | None = None) -> datetime | None:
        """Nächster freier Zeitslot der aktuellen Rolle (oder None)."""
        from zoneinfo import ZoneInfo

        from .core.slots import next_free_slot
        from .schedule_dialog import system_timezone
        role = self.role
        if not role or not role.slots:
            return None
        tz = ZoneInfo(self.settings.get_string("default-timezone") or system_timezone())
        taken = [datetime.fromisoformat(x) for x in self.store.scheduled_times(role.id)
                 if x != exclude_iso]
        return next_free_slot(role.slots, taken, datetime.now(tz))

    def schedule_next_slot(self) -> None:
        self._refresh.flush()
        if not self.report or not self.props.can_publish:
            return
        when = self.next_slot(self.post.scheduled_at)
        if when is None:
            self.win.toast(_("This role has no time slots. Add them in the role settings."))
            return
        self._do_schedule(when, str(when.tzinfo))

    def schedule(self) -> None:
        self._refresh.flush()
        if not self.report or not self.props.can_publish:
            return
        initial = None
        if self.post.scheduled_at:
            initial = datetime.fromisoformat(self.post.scheduled_at)
            if initial < datetime.now(initial.tzinfo):
                initial = None
        tz = self.post.timezone or self.settings.get_string("default-timezone") or None
        DandelionScheduleDialog(initial=initial, timezone=tz,
                                service_active=self.app.scheduling.props.active,
                                on_schedule=self._do_schedule,
                                on_enable_service=lambda: self.app.scheduling.enable(self.win),
                                next_slot=self.next_slot(self.post.scheduled_at)
                                ).present(self.win)

    def _do_schedule(self, when: datetime, tz: str) -> None:
        post = self.post
        post.targets = [t for t in post.targets if t.enabled]
        post.state = PostState.SCHEDULED
        post.scheduled_at = to_utc_iso(when)
        post.timezone = tz
        try:
            self.store.save_post(post, guard_editable=True)
        except PostLocked:
            self.win.toast(_("This post has been published in the meantime"))
            return
        self.app.scheduling.schedule_changed()
        self.new_post(save_current=False)

        def undo() -> None:
            self.store.set_post_schedule(post.id, PostState.DRAFT, None)  # type: ignore[arg-type]
            self.app.scheduling.schedule_changed()
            self.edit_post(post.id)  # type: ignore[arg-type]

        self.win.toast(_("Scheduled for {when}").format(when=format_when(when, tz)),
                       _("_Undo"), undo)

    # ------------------------------------------------------------------
    # Senden
    # ------------------------------------------------------------------
    def publish(self) -> None:
        self._refresh.flush()
        if not self.report or not self.props.can_publish:
            return
        warnings = self.report.warnings
        if not warnings:
            self._do_publish()
            return
        lines = []
        for t in self.report.targets:
            for i in t.issues:
                if i.severity == "warning":
                    lines.append(f"{t.platform.name} · {t.profile.full_handle}: {i.message}")
        dialog = Adw.AlertDialog(heading=_("Publish Despite Warnings?"),
                                 body="\n".join(lines))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("send", _("_Publish Anyway"))
        dialog.set_response_appearance("send", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("send")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: r == "send" and self._do_publish())
        dialog.present(self.win)

    def _do_publish(self) -> None:
        post = self.post
        # nur aktive Ziele behalten, abgewählte nicht als Ziel speichern
        post.targets = [t for t in post.targets if t.enabled]
        self.store.save_post(post)
        names = {p.id: p.name for p in self.app.registry.all()}
        dialog = DandelionSendDialog(post, self.profiles, names,
                                     on_retry=lambda pid: self.retry(post.id, {pid}, dialog))
        dialog.present(self.win)
        spawn(self._run_send(post.id, None, dialog))
        self.new_post(save_current=False)

    def retry(self, post_id: int, profile_ids: set[int] | None,
              dialog: DandelionSendDialog | None = None) -> None:
        spawn(self._run_send(post_id, profile_ids, dialog))

    async def _run_send(self, post_id: int, only: set[int] | None,
                        dialog: DandelionSendDialog | None) -> None:
        def on_update(_post: Post, target: Target, stage: str) -> None:
            if dialog:
                dialog.update(target, stage)

        try:
            result = await self.app.publisher.send(post_id, only_profiles=only,
                                                   on_update=on_update)
        except AlreadySending:
            self.win.toast(_("This post is already being published"))
            return
        if dialog:
            dialog.finish(result)
        ok = sum(1 for t in result.targets if t.enabled and t.state == "published")
        total = sum(1 for t in result.targets if t.enabled)
        if ok == 0:
            text = _("Publishing failed")
        elif ok == total:
            text = ngettext("Published on {n} profile", "Published on {n} profiles",
                            total).format(n=total)
        else:
            text = _("Published on {ok} of {total} profiles").format(ok=ok, total=total)
        self.win.toast(text, _("_Details"), self.win.show_history)
        self.win.history.reload()
        self.app.scheduling.schedule_changed()

