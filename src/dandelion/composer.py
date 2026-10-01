# SPDX-License-Identifier: GPL-3.0-or-later
"""Der Composer: Rolle, Profile, Text mit Varianten, Medien, Vorschau, Senden."""

from __future__ import annotations

import logging
import os
from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, GtkSource, Spelling

from .alt_text_dialog import DandelionAltTextDialog
from .core import imaging
from .core.compose import base_text, composition_for, text_hash
from .core.counting import find_hashtags, find_mentions, find_urls
from .core.models import Media, Post, PostState, Profile, Role, Target, Variant
from .core.publisher import AlreadySending
from .core.store import media_dir
from .core.validation import Report, validate
from .net.linkcard import LinkCard, fetch_card
from .send_dialog import DandelionSendDialog
from .util import (
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
from .widgets.media_tile import MediaTile
from .widgets.preview_tile import PreviewTile
from .widgets.profile_chip import ProfileChip

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

    drafts_split: Adw.OverlaySplitView = Gtk.Template.Child()
    drafts_stack: Gtk.Stack = Gtk.Template.Child()
    drafts_list: Gtk.ListBox = Gtk.Template.Child()
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
    chips_box: Gtk.Box = Gtk.Template.Child()
    variant_group: Adw.ToggleGroup = Gtk.Template.Child()
    variant_banner: Adw.Banner = Gtk.Template.Child()
    cw_revealer: Gtk.Revealer = Gtk.Template.Child()
    cw_entry: Gtk.Entry = Gtk.Template.Child()
    cw_button: Gtk.ToggleButton = Gtk.Template.Child()
    text_view: GtkSource.View = Gtk.Template.Child()
    editor_scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    media_tiles: Gtk.Box = Gtk.Template.Child()
    add_media_button: Gtk.Button = Gtk.Template.Child()
    language_dropdown: Gtk.DropDown = Gtk.Template.Child()
    visibility_dropdown: Gtk.DropDown = Gtk.Template.Child()
    label_dropdown: Gtk.DropDown = Gtk.Template.Child()
    signature_button: Gtk.ToggleButton = Gtk.Template.Child()
    counters_box: Gtk.FlowBox = Gtk.Template.Child()
    preview_tiles: Gtk.Box = Gtk.Template.Child()

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

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.editor_scroller.add_controller(drop)

        self.preview_split.set_show_sidebar(self.settings.get_boolean("show-preview"))
        self.drafts_split.set_show_sidebar(self.settings.get_boolean("drafts-sidebar-visible"))
        self.drafts_split.connect("notify::show-sidebar", self._on_drafts_shown)
        self._style.connect("notify::accent-color-rgba", lambda *_: self._update_tags_color())
        self._style.connect("notify::dark", self._on_dark_changed)
        self._apply_scheme(self._inherit_buffer)
        self.layout_view.connect("notify::layout-name", lambda *_: self._on_layout_changed())

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
        while (child := self.chips_box.get_first_child()) is not None:
            self.chips_box.remove(child)
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
            self.chips[pid] = chip
            self.chips_box.append(chip)
        others = [p for p in self.profiles.values() if p.id not in shown]
        if others:
            menu_button = Gtk.MenuButton(icon_name="list-add-symbolic",
                                         tooltip_text=_("More Profiles"))
            menu_button.add_css_class("flat")
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
                toggle = Adw.Toggle(name=key, label=label + (" ✎" if self._variant(key) else ""))
                toggle.set_tooltip(label)
                self.variant_group.add(toggle)
            self.variant_group.set_active_name(current if current in wanted else MAIN)
            self._loading = False
        else:
            for i, (key, label) in enumerate(keys):
                self.variant_group.get_toggle(i).set_label(
                    label + (" ✎" if self._variant(key) else ""))
        self.variant_group.set_visible(len(keys) > 1)
        self._show_variant()

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

    def _show_variant(self) -> None:
        key = self.variant_group.get_active_name() or MAIN
        if key == MAIN:
            self.text_view.set_buffer(self.buffers[MAIN])
            self.text_view.set_editable(True)
            self.text_view.remove_css_class("inherited")
            self.variant_banner.set_revealed(False)
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
            self.variant_banner.set_title(title)
            self.variant_banner.set_button_label(_("_Use Main Text"))
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
            self.variant_banner.set_title(_("{name} uses the main text.").format(name=name))
            self.variant_banner.set_button_label(_("_Customize"))
        self.variant_banner.set_revealed(True)

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
    def on_signature_toggled(self, button: Gtk.ToggleButton) -> None:
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
        self.visibility_dropdown.set_visible("mastodon" in platforms)
        self.label_dropdown.set_visible("bluesky" in platforms and bool(self.post.media))
        self._update_counters()
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

    def _update_counters(self) -> None:
        self.counters_box.remove_all()
        summary = []
        for t in self.report.targets if self.report else []:
            c = t.count
            label = Gtk.Label(label=f"{t.platform.name} {t.profile.label or '@' + t.profile.handle}"
                              f"  {c.used}/{c.limit}")
            label.add_css_class("caption")
            label.add_css_class("numeric")
            state = _("within the limit")
            if c.over:
                label.add_css_class("error")
                state = _("over the limit")
            elif c.ratio >= 0.9:
                label.add_css_class("warning")
                state = _("close to the limit")
            label.update_property([Gtk.AccessibleProperty.LABEL], [
                _("{platform} {handle}: {used} of {limit} characters, {state}").format(
                    platform=t.platform.name, handle=t.profile.full_handle, used=c.used,
                    limit=c.limit, state=state)])
            self.counters_box.append(label)
            summary.append(f"{t.platform.name} {c.used}/{c.limit}")
        self.sheet_bar_label.set_label(_("Preview") + (" · " + " · ".join(summary)
                                                      if summary else ""))

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
        self.issues_label.set_label(ngettext("{n} problem", "{n} problems",
                                             n_err + n_warn).format(n=n_err + n_warn))
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
        for i, m in enumerate(self.post.media):
            self.media_tiles.append(MediaTile(
                m, i, total, required, on_edit_alt=self._edit_alt,
                on_remove=self._remove_media, on_move=self._move_media))

    def _update_previews(self) -> None:
        while (child := self.preview_tiles.get_first_child()) is not None:
            self.preview_tiles.remove(child)
        targets = self.report.targets if self.report else []
        if not targets:
            status = Adw.StatusPage(icon_name="view-reveal-symbolic", title=_("No Preview"),
                                    description=_("Select a profile to see how the post "
                                                  "will look."))
            status.add_css_class("compact")
            self.preview_tiles.append(status)
            return
        accent = _rgba_hex(self._style.get_accent_color_rgba())
        for t in targets:
            comp = composition_for(self.post, t.profile, self.role)
            urls = find_urls(comp.text)
            card = self.link_cards.get(urls[0].value) if urls else None
            self.preview_tiles.append(PreviewTile(t.platform, t.profile, comp, t.limits, t.count,
                                                  self.avatars, card, accent))

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

        DandelionAltTextDialog(media, limit, limit_platform, hints, done).present(self.win)

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
    def set_drafts_visible(self, visible: bool) -> None:
        self.drafts_split.set_show_sidebar(visible)

    def set_preview_visible(self, visible: bool) -> None:
        if self.layout_view.get_layout_name() == "narrow":
            self.sheet.set_open(visible)
        else:
            self.preview_split.set_show_sidebar(visible)

    def _on_drafts_shown(self, *_args: object) -> None:
        shown = self.drafts_split.get_show_sidebar()
        action = self.win.lookup_action("toggle-drafts") if self.win else None
        if action and action.get_state().get_boolean() != shown:
            action.set_state(GLib.Variant.new_boolean(shown))
        if shown:
            self.reload_drafts()

    def _on_layout_changed(self) -> None:
        narrow = self.layout_view.get_layout_name() == "narrow"
        for chip in self.chips.values():
            chip.set_compact(narrow and self.get_width() < 420)

    def reload_drafts(self) -> None:
        self.drafts_list.remove_all()
        ids = self.store.post_ids([PostState.DRAFT])
        roles = {r.id: r for r in self.roles}
        for pid in ids:
            post = self.store.load_post(pid)
            if post is None or (post.is_empty() and post.id != self.post.id):
                continue
            row = Adw.ActionRow(activatable=True)
            row.post_id = pid  # type: ignore[attr-defined]
            title = first_line(post.body) or _("Empty Post")
            row.set_title(GLib.markup_escape_text(title))
            role = roles.get(post.role_id)
            row.set_subtitle(" · ".join(x for x in (role.emoji + " " + role.name if role else "",
                                                     format_time(post.updated_at)) if x))
            row.set_title_lines(2)
            delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text=_("Delete Draft"))
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, p=pid: self._delete_draft(p))
            row.add_suffix(delete)
            self.drafts_list.append(row)
            if pid == self.post.id:
                self.drafts_list.select_row(row)
        self.drafts_stack.set_visible_child_name("list" if self.drafts_list.get_first_child()
                                                 else "empty")

    @Gtk.Template.Callback()
    def on_draft_activated(self, _list: Gtk.ListBox, row: Adw.ActionRow) -> None:
        pid = row.post_id  # type: ignore[attr-defined]
        if pid == self.post.id:
            return
        self.save_now()
        post = self.store.load_post(pid)
        if post:
            self.load_post(post)
        if self.drafts_split.get_collapsed():
            self.drafts_split.set_show_sidebar(False)

    def _delete_draft(self, post_id: int) -> None:
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
            self.win.stack.set_visible_child_name("composer")
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
        self.refresh()
        self.reload_drafts()

    def save_now(self, toast: bool = False) -> None:
        self._autosave_cancel()
        if not self.app or self.post.state != PostState.DRAFT:
            return
        if self.post.id is None and self.post.is_empty():
            return
        new = self.post.id is None
        self.store.save_post(self.post)
        if new:
            self.reload_drafts()
        if toast:
            self.win.toast(_("Draft saved"))

    def _autosave_cancel(self) -> None:
        if self._autosave._source:
            GLib.source_remove(self._autosave._source)
            self._autosave._source = 0

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

