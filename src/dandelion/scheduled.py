# SPDX-License-Identifier: GPL-3.0-or-later
"""Kalenderseite und Aktionen für geplante, pausierte und verpasste Beiträge."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from gettext import ngettext
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gio, GLib, Gtk

from .core.models import Media, Post, PostState, Target, TargetState, Variant
from .core.scheduler import to_utc_iso
from .schedule_dialog import DandelionScheduleDialog
from .util import first_line, label_widget
from .widgets.month_calendar import PUBLISHED_STATES, DandelionMonthCalendar, post_time

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

STATES = (PostState.MISSED, PostState.SCHEDULED, PostState.PAUSED)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/scheduled.ui")
class DandelionScheduledView(Adw.BreakpointBin):
    """Kalenderseite: Monatsraster mit geplanten und veröffentlichten Beiträgen."""

    __gtype_name__ = "DandelionScheduledView"

    service_banner: Adw.Banner = Gtk.Template.Child()
    calendar: DandelionMonthCalendar = Gtk.Template.Child()
    day_box: Gtk.Box = Gtk.Template.Child()
    day_title: Gtk.Label = Gtk.Template.Child()
    day_list: Gtk.ListBox = Gtk.Template.Child()
    day_empty: Gtk.Label = Gtk.Template.Child()
    filter_popover: Gtk.Popover = Gtk.Template.Child()
    role_filter: Adw.ComboRow = Gtk.Template.Child()
    platform_filter: Adw.ComboRow = Gtk.Template.Child()

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self._loading = False
        self._roles: list = [None]
        self._platforms: list = [None]
        self._summary = ""
        app.scheduling.connect("changed", lambda *_: self.reload())
        app.scheduling.connect("notify::active", lambda *_: self._sync_banner())
        app.scheduling.connect("notify::available", lambda *_: self._sync_banner())
        self._sync_banner()
        group = Gio.SimpleActionGroup()
        for name, cb in (("previous", lambda: self.calendar.shift(-1)),
                         ("next", lambda: self.calendar.shift(1)),
                         ("today", self.calendar.go_today)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, cb=cb: cb())
            group.add_action(action)
        win.insert_action_group("calendar", group)

    # -- Kopfzeile -------------------------------------------------------------
    def title(self) -> tuple[str, str]:
        return self.calendar.title(), self._summary

    def filtered(self) -> bool:
        return bool(self.role_filter.get_selected() or self.platform_filter.get_selected())

    # -- Kalender --------------------------------------------------------------
    @Gtk.Template.Callback()
    def on_calendar_activated(self, _cal: object, post_id: int) -> None:
        post = self.app.store.load_post(post_id)
        if post is None:
            return
        if post.state in PUBLISHED_STATES:
            self.win.show_post(post.id)  # type: ignore[arg-type]
        else:
            self._edit(post)

    @Gtk.Template.Callback()
    def on_month_changed(self, *_args: object) -> None:
        self.reload()

    @Gtk.Template.Callback()
    def on_day_selected(self, *_args: object) -> None:
        self._fill_day_list()

    @Gtk.Template.Callback()
    def on_calendar_moved(self, _cal: object, post_id: int, year: int, month: int,
                          day: int) -> None:
        from datetime import UTC
        from zoneinfo import ZoneInfo
        post = self.app.store.load_post(post_id)
        if post is None:
            return
        if post.state == PostState.DRAFT:
            self.schedule_on(post, date(year, month, day))
            return
        if not post.scheduled_at or post.state not in STATES:
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

    def schedule_on(self, post: Post, day: date) -> None:
        """Ein Entwurf wurde auf einen Tag gezogen: Zeitplan-Dialog mit diesem Tag öffnen."""
        from zoneinfo import ZoneInfo

        from .core.slots import slot_times
        from .schedule_dialog import format_when, system_timezone
        tz = ZoneInfo(self.app.settings.get_string("default-timezone") or system_timezone())
        now = datetime.now(tz)
        if day < now.date():
            self.win.toast(_("This day is in the past."))
            return
        composer = self.win.composer
        if composer.post.id == post.id:
            composer.save_now()
            post = self.app.store.load_post(post.id) or post  # type: ignore[arg-type]

        role = self.app.store.role(post.role_id) if post.role_id else None
        initial = None
        if role and role.slots:
            taken = [datetime.fromisoformat(x) for x in self.app.store.scheduled_times(role.id)]
            start = max(now, datetime(day.year, day.month, day.day, tzinfo=tz))
            for when in slot_times(role.slots, start, days=0):
                if when.date() == day and not any(
                        abs((when - t).total_seconds()) < 60 for t in taken):
                    initial = when
                    break
        if initial is None:
            initial = datetime(day.year, day.month, day.day, 9, 0, tzinfo=tz)
            if initial <= now:
                initial = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        def done(when: datetime, zone: str) -> None:
            store = self.app.store
            store.set_post_schedule(post.id, PostState.SCHEDULED, to_utc_iso(when), zone)  # type: ignore[arg-type]
            if composer.post.id == post.id:
                fresh = store.load_post(post.id)  # type: ignore[arg-type]
                if fresh:
                    composer.load_post(fresh)
            self._changed()
            composer.reload_drafts()
            self.win.toast(_("Scheduled for {when}").format(when=format_when(when, zone)))

        DandelionScheduleDialog(initial=initial, timezone=post.timezone,
                                service_active=self.app.scheduling.props.active,
                                on_schedule=done,
                                on_enable_service=lambda: self.app.scheduling.enable(self.win),
                                next_slot=self._next_slot(post)).present(self.win)

    def _sync_banner(self) -> None:
        s = self.app.scheduling
        self.service_banner.set_revealed(s.props.available and not s.props.active)

    @Gtk.Template.Callback()
    def on_enable_service(self, *_args: object) -> None:
        self.app.scheduling.enable(self.win)

    @Gtk.Template.Callback()
    def on_filter_changed(self, *_args: object) -> None:
        if not getattr(self, "_loading", True):
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
        store = self.app.store
        profiles = {p.id: p for p in store.profiles()}
        roles = {r.id: r for r in store.roles()}
        role = self._roles[self.role_filter.get_selected()] \
            if self.role_filter.get_selected() < len(self._roles) else None
        platform = self._platforms[self.platform_filter.get_selected()] \
            if self.platform_filter.get_selected() < len(self._platforms) else None

        posts = [p for pid in store.post_ids(STATES, order="scheduled_at")
                 if (p := store.load_post(pid))]
        posts += [p for pid in store.post_ids(PUBLISHED_STATES,
                                              order="COALESCE(published_at, updated_at) DESC")
                  if (p := store.load_post(pid))]
        if role:
            posts = [p for p in posts if p.role_id == role.id]
        if platform:
            posts = [p for p in posts if any(
                t.enabled and profiles.get(t.profile_id) and
                profiles[t.profile_id].platform == platform for t in p.targets)]

        self.calendar.set_posts([(p, roles.get(p.role_id)) for p in posts],
                                self._free_slots(role))
        in_month = [p for p in posts if (w := post_time(p)) and
                    w.month == self.calendar.month and w.year == self.calendar.year]
        planned = sum(1 for p in in_month if p.state in STATES)
        published = len(in_month) - planned
        parts = []
        if planned:
            parts.append(ngettext("{n} scheduled", "{n} scheduled", planned).format(n=planned))
        if published:
            parts.append(ngettext("{n} published", "{n} published", published).format(
                n=published))
        self._summary = " · ".join(parts)
        self._profiles, self._role_map = profiles, roles
        self._fill_day_list()
        if self.win.stack.get_visible_child_name() == "scheduled":
            self.win.sync_title()

    def _free_slots(self, only_role) -> list:  # type: ignore[no-untyped-def]
        """Freie Zeitfenster der Rollen im sichtbaren Zeitraum (ab jetzt)."""
        from zoneinfo import ZoneInfo

        from .core.slots import slot_times
        from .schedule_dialog import system_timezone
        tz = ZoneInfo(self.app.settings.get_string("default-timezone") or system_timezone())
        start, end = self.calendar.month_range()
        now = datetime.now(tz)
        begin = max(now, datetime(start.year, start.month, start.day, tzinfo=tz))
        days = (end - begin.date()).days
        if days < 0:
            return []
        out = []
        for role in self.app.store.roles():
            if not role.slots or (only_role and role.id != only_role.id):
                continue
            taken = [datetime.fromisoformat(x) for x in self.app.store.scheduled_times(role.id)]
            for when in slot_times(role.slots, begin, days=days):
                if when.date() <= end and not any(
                        abs((when - t).total_seconds()) < 60 for t in taken):
                    out.append((when, role))
        return out

    def _fill_day_list(self) -> None:
        if not hasattr(self, "_profiles"):
            return
        self.day_list.remove_all()
        day = self.calendar.selected
        self.day_title.set_label(GLib.DateTime.new_local(day.year, day.month, day.day, 0, 0, 0)
                                 .format("%A, %e. %B") or "")
        entries = self.calendar.entries_for(day)
        for _when, post, _role in entries:
            if post.state in PUBLISHED_STATES:
                row = Adw.ActionRow(title=GLib.markup_escape_text(first_line(post.body) or
                                                                  _("Post")),
                                    subtitle=_("Published"), activatable=True)
                row.connect("activated", lambda _r, pid=post.id: self.win.show_post(pid))
            else:
                row = self._row(post, self._profiles, self._role_map)
            self.day_list.append(row)
        self.day_list.set_visible(bool(entries))
        self.day_empty.set_visible(not entries)

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
            send.connect("clicked", lambda *_: self.send_now(post, confirm=False))
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
        add("reschedule", _("Change Time…"), self.reschedule, main)
        if post.state == PostState.PAUSED:
            add("pause", _("Resume"), self.toggle_pause, main)
        elif post.state == PostState.SCHEDULED:
            add("pause", _("Pause"), self.toggle_pause, main)
        if post.state != PostState.MISSED:
            add("send", _("Send Now"), self.send_now, main)
        add("duplicate", _("Duplicate"), self.duplicate, main)
        menu.append_section(None, main)
        danger = Gio.Menu()
        if post.state == PostState.MISSED:
            add("discard", _("Move to Drafts"), self.to_drafts, danger)
        add("delete", _("Delete"), self.delete_post, danger)
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

    def reschedule(self, post: Post) -> None:
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

    def toggle_pause(self, post: Post) -> None:
        state = PostState.SCHEDULED if post.state == PostState.PAUSED else PostState.PAUSED
        self.app.store.set_post_schedule(post.id, state, post.scheduled_at)  # type: ignore[arg-type]
        self._changed()
        self.win.toast(_("Paused") if state == PostState.PAUSED else _("Resumed"))

    def send_now(self, post: Post, confirm: bool = True) -> None:
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

    def duplicate(self, post: Post) -> None:
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

    def to_drafts(self, post: Post) -> None:
        self.app.store.set_post_schedule(post.id, PostState.DRAFT, None)  # type: ignore[arg-type]
        self._changed()
        self.win.composer.reload_drafts()
        self.win.toast(_("Moved to drafts"))

    def delete_post(self, post: Post) -> None:
        store = self.app.store
        store.mark_post_deleted(post.id, True)  # type: ignore[arg-type]
        self._changed()

        def undo() -> None:
            store.mark_post_deleted(post.id, False)  # type: ignore[arg-type]
            self._changed()

        self.win.toast(_("Scheduled post deleted"), _("_Undo"), undo, timeout=10)
