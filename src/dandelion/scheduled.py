# SPDX-License-Identifier: GPL-3.0-or-later
"""Ansicht „Geplant“: alle geplanten, pausierten und verpassten Beiträge."""

from __future__ import annotations

from datetime import datetime
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gio, GLib, Gtk

from .core.models import Media, Post, PostState, Target, TargetState, Variant
from .core.scheduler import to_utc_iso
from .schedule_dialog import DandelionScheduleDialog
from .util import label_widget, day_label, first_line
from .widgets.month_calendar import DandelionMonthCalendar

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

STATES = (PostState.MISSED, PostState.SCHEDULED, PostState.PAUSED)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/scheduled.ui")
class DandelionScheduledView(Adw.BreakpointBin):
    __gtype_name__ = "DandelionScheduledView"

    service_banner: Adw.Banner = Gtk.Template.Child()
    stack: Gtk.Stack = Gtk.Template.Child()
    role_filter: Gtk.DropDown = Gtk.Template.Child()
    platform_filter: Gtk.DropDown = Gtk.Template.Child()
    list_box: Gtk.Box = Gtk.Template.Child()
    mode_group: Adw.ToggleGroup = Gtk.Template.Child()
    mode_stack: Gtk.Stack = Gtk.Template.Child()
    calendar: DandelionMonthCalendar = Gtk.Template.Child()

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self._loading = False
        app.scheduling.connect("changed", lambda *_: self.reload())
        app.scheduling.connect("notify::active", lambda *_: self._sync_banner())
        app.scheduling.connect("notify::available", lambda *_: self._sync_banner())
        self._sync_banner()
        try:
            mode = app.settings.get_string("scheduled-view")
        except Exception:
            mode = "list"
        self.mode_group.set_active_name(mode if mode in ("list", "calendar") else "list")

    @Gtk.Template.Callback()
    def on_mode_changed(self, *_args: object) -> None:
        mode = self.mode_group.get_active_name() or "list"
        self.mode_stack.set_visible_child_name(mode)
        if getattr(self, "app", None):
            self.app.settings.set_string("scheduled-view", mode)
            self.reload()

    @Gtk.Template.Callback()
    def on_calendar_activated(self, _cal: object, post_id: int) -> None:
        post = self.app.store.load_post(post_id)
        if post:
            self._edit(post)

    @Gtk.Template.Callback()
    def on_calendar_moved(self, _cal: object, post_id: int, year: int, month: int,
                          day: int) -> None:
        from datetime import UTC
        from zoneinfo import ZoneInfo
        post = self.app.store.load_post(post_id)
        if post is None or not post.scheduled_at:
            return
        tz = ZoneInfo(post.timezone) if post.timezone else None
        old = datetime.fromisoformat(post.scheduled_at)
        local = old.astimezone(tz) if tz else old.astimezone()
        new = local.replace(year=year, month=month, day=day)
        if new.date() == local.date():
            return
        if new <= datetime.now(UTC):
            self.win.toast(_("This time is in the past."))
            return
        state = PostState.SCHEDULED if post.state == PostState.MISSED else post.state
        store = self.app.store
        store.set_post_schedule(post_id, state, to_utc_iso(new))
        self._changed()

        def undo() -> None:
            store.set_post_schedule(post_id, post.state, post.scheduled_at)
            self._changed()

        from .schedule_dialog import format_when
        self.win.toast(_("Moved to {when}").format(when=format_when(new)), _("_Undo"), undo)

    def _sync_banner(self) -> None:
        s = self.app.scheduling
        self.service_banner.set_revealed(s.props.available and not s.props.active)

    @Gtk.Template.Callback()
    def on_enable_service(self, *_args: object) -> None:
        self.app.scheduling.enable(self.win)

    @Gtk.Template.Callback()
    def on_filter_changed(self, *_args: object) -> None:
        if not self._loading:
            self.reload()

    def _fill_filters(self) -> None:
        self._loading = True
        self._roles = [None, *self.app.store.roles()]
        sel = self.role_filter.get_selected()
        self.role_filter.set_model(Gtk.StringList.new(
            [_("All Roles")] + [f"{r.emoji} {r.name}" for r in self._roles[1:]]))
        self.role_filter.set_selected(sel if 0 <= sel < len(self._roles) else 0)
        self._platforms = [None, *[p.id for p in self.app.registry.all()]]
        sel = self.platform_filter.get_selected()
        self.platform_filter.set_model(Gtk.StringList.new(
            [_("All Platforms")] + [p.name for p in self.app.registry.all()]))
        self.platform_filter.set_selected(sel if 0 <= sel < len(self._platforms) else 0)
        self._loading = False

    def reload(self) -> None:
        if not getattr(self, "app", None):
            return
        self._fill_filters()
        while (child := self.list_box.get_first_child()) is not None:
            self.list_box.remove(child)
        store = self.app.store
        profiles = {p.id: p for p in store.profiles()}
        roles = {r.id: r for r in store.roles()}
        role = self._roles[self.role_filter.get_selected()] \
            if self.role_filter.get_selected() < len(self._roles) else None
        platform = self._platforms[self.platform_filter.get_selected()] \
            if self.platform_filter.get_selected() < len(self._platforms) else None

        posts = [p for pid in store.post_ids(STATES, order="scheduled_at")
                 if (p := store.load_post(pid))]
        total = len(posts)
        if role:
            posts = [p for p in posts if p.role_id == role.id]
        if platform:
            posts = [p for p in posts if any(
                t.enabled and profiles.get(t.profile_id) and
                profiles[t.profile_id].platform == platform for t in p.targets)]

        if (self.mode_group.get_active_name() or "list") == "calendar":
            self.calendar.set_posts([(p, roles.get(p.role_id)) for p in posts])
            self.stack.set_visible_child_name("list")
            return

        missed = [p for p in posts if p.state == PostState.MISSED]
        if missed:
            group = Adw.PreferencesGroup(
                title=_("Missed"),
                description=_("The computer was off or asleep at the planned time."))
            for post in missed:
                group.add(self._row(post, profiles, roles))
            self.list_box.append(group)

        group = None
        current = None
        for post in (p for p in posts if p.state != PostState.MISSED):
            day = day_label(post.scheduled_at) if post.scheduled_at else _("Without Date")
            if day != current:
                current = day
                group = Adw.PreferencesGroup(title=GLib.markup_escape_text(day))
                self.list_box.append(group)
            group.add(self._row(post, profiles, roles))  # type: ignore[union-attr]

        self.stack.set_visible_child_name("list" if total else "empty")
        if total and not posts:
            status = Adw.StatusPage(icon_name="system-search-symbolic", title=_("No Matches"),
                                    description=_("No scheduled post matches the filter."))
            status.add_css_class("compact")
            self.list_box.append(status)

    def _row(self, post: Post, profiles, roles) -> Adw.ActionRow:  # type: ignore[no-untyped-def]
        row = Adw.ActionRow(title=GLib.markup_escape_text(first_line(post.body) or _("Post")),
                            activatable=True)
        row.set_title_lines(2)
        when = datetime.fromisoformat(post.scheduled_at).astimezone() if post.scheduled_at else None
        time = Gtk.Label(label=when.strftime("%H:%M") if when else "–", width_chars=5)
        time.add_css_class("numeric")
        time.add_css_class("heading")
        row.add_prefix(time)

        parts = []
        if post.state == PostState.MISSED and when:
            parts.append(when.strftime("%d.%m."))
        role = roles.get(post.role_id)
        if role:
            parts.append(f"{role.emoji} {role.name}")
        handles = [profiles[t.profile_id].full_handle for t in post.targets
                   if t.enabled and t.profile_id in profiles]
        parts.append(", ".join(handles))
        row.set_subtitle(GLib.markup_escape_text(" · ".join(parts)))

        remote = [profiles[t.profile_id].full_handle for t in post.targets
                  if t.state == TargetState.SCHEDULED_REMOTE and t.profile_id in profiles]
        if remote:
            icon = Gtk.Image(icon_name="network-server-symbolic")
            label_widget(icon, _("Scheduled on the server: {profiles}").format(
                profiles=", ".join(remote)))
            row.add_suffix(icon)
        if post.state == PostState.PAUSED:
            badge = Gtk.Label(label=_("Paused"), valign=Gtk.Align.CENTER)
            badge.add_css_class("state-badge")
            row.add_suffix(badge)
        elif post.state == PostState.MISSED:
            icon = Gtk.Image(icon_name="appointment-missed-symbolic")
            icon.add_css_class("warning")
            row.add_suffix(icon)
            send = Gtk.Button(label=_("Send _Now"), use_underline=True, valign=Gtk.Align.CENTER)
            send.connect("clicked", lambda *_: self._send_now(post, confirm=False))
            row.add_suffix(send)

        group = Gio.SimpleActionGroup()
        menu = Gio.Menu()

        def add(name: str, label: str, cb, section: Gio.Menu) -> None:  # type: ignore[no-untyped-def]
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_: cb(post))
            group.add_action(act)
            section.append(label, f"row.{name}")

        main = Gio.Menu()
        add("edit", _("Edit"), self._edit, main)
        add("reschedule", _("Change Time…"), self._reschedule, main)
        if post.state == PostState.PAUSED:
            add("pause", _("Resume"), self._toggle_pause, main)
        elif post.state == PostState.SCHEDULED:
            add("pause", _("Pause"), self._toggle_pause, main)
        if post.state != PostState.MISSED:
            add("send", _("Send Now"), self._send_now, main)
        add("duplicate", _("Duplicate"), self._duplicate, main)
        menu.append_section(None, main)
        danger = Gio.Menu()
        if post.state == PostState.MISSED:
            add("discard", _("Move to Drafts"), self._to_drafts, danger)
        add("delete", _("Delete"), self._delete, danger)
        menu.append_section(None, danger)
        row.insert_action_group("row", group)
        more = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu,
                              valign=Gtk.Align.CENTER, tooltip_text=_("Actions"))
        more.add_css_class("flat")
        label_widget(more, more.get_tooltip_text() or "")
        row.add_suffix(more)
        row.connect("activated", lambda *_: self._edit(post))
        return row

    # -- Aktionen ------------------------------------------------------------
    def _changed(self) -> None:
        self.app.scheduling.schedule_changed()

    def _edit(self, post: Post) -> None:
        self.win.composer.edit_post(post.id)

    def _reschedule(self, post: Post) -> None:
        def done(when: datetime, tz: str) -> None:
            self.app.store.set_post_schedule(post.id, PostState.SCHEDULED, to_utc_iso(when), tz)  # type: ignore[arg-type]
            self._changed()
            self.win.toast(_("Rescheduled"))

        initial = datetime.fromisoformat(post.scheduled_at) if post.scheduled_at else None
        if initial and initial < datetime.now(initial.tzinfo):
            initial = None
        DandelionScheduleDialog(initial=initial, timezone=post.timezone,
                                service_active=self.app.scheduling.props.active,
                                on_schedule=done,
                                on_enable_service=lambda: self.app.scheduling.enable(self.win),
                                next_slot=self._next_slot(post)).present(self.win)

    def _next_slot(self, post: Post) -> datetime | None:
        from zoneinfo import ZoneInfo

        from .core.slots import next_free_slot
        from .schedule_dialog import system_timezone
        role = self.app.store.role(post.role_id) if post.role_id else None
        if not role or not role.slots:
            return None
        tz = ZoneInfo(self.app.settings.get_string("default-timezone") or system_timezone())
        taken = [datetime.fromisoformat(x) for x in self.app.store.scheduled_times(role.id)
                 if x != post.scheduled_at]
        return next_free_slot(role.slots, taken, datetime.now(tz))

    def _toggle_pause(self, post: Post) -> None:
        state = PostState.SCHEDULED if post.state == PostState.PAUSED else PostState.PAUSED
        self.app.store.set_post_schedule(post.id, state, post.scheduled_at)  # type: ignore[arg-type]
        self._changed()
        self.win.toast(_("Paused") if state == PostState.PAUSED else _("Resumed"))

    def _send_now(self, post: Post, confirm: bool = True) -> None:
        if not confirm:
            self.win.composer.retry(post.id, None)  # type: ignore[arg-type]
            return
        dialog = Adw.AlertDialog(heading=_("Publish Now?"),
                                 body=_("The post will be published immediately instead of at "
                                        "the planned time."))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("send", _("_Publish"))
        dialog.set_response_appearance("send", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: r == "send" and
                       self.win.composer.retry(post.id, None))  # type: ignore[arg-type]
        dialog.present(self.win)

    def _duplicate(self, post: Post) -> None:
        copy = Post(role_id=post.role_id, body=post.body, content_warning=post.content_warning,
                    language=post.language, visibility=post.visibility,
                    bluesky_label=post.bluesky_label, use_signature=post.use_signature,
                    variants=[Variant(v.platform, v.body, v.profile_id, v.content_warning,
                                      v.base_hash) for v in post.variants],
                    media=[Media(m.path, m.sha256, m.mime, m.bytes, width=m.width,
                                 height=m.height, alt_text=m.alt_text) for m in post.media],
                    targets=[Target(t.profile_id, t.enabled) for t in post.targets])
        self.app.store.save_post(copy)
        self.win.composer.edit_post(copy.id)  # type: ignore[arg-type]
        self.win.toast(_("Copy created as draft"))

    def _to_drafts(self, post: Post) -> None:
        self.app.store.set_post_schedule(post.id, PostState.DRAFT, None)  # type: ignore[arg-type]
        self._changed()
        self.win.composer.reload_drafts()
        self.win.toast(_("Moved to drafts"))

    def _delete(self, post: Post) -> None:
        store = self.app.store
        store.mark_post_deleted(post.id, True)  # type: ignore[arg-type]
        self._changed()

        def undo() -> None:
            store.mark_post_deleted(post.id, False)  # type: ignore[arg-type]
            self._changed()

        self.win.toast(_("Scheduled post deleted"), _("_Undo"), undo, timeout=10)
