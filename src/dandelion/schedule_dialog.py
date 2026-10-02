# SPDX-License-Identifier: GPL-3.0-or-later
"""Datum, Uhrzeit und Zeitzone für einen geplanten Beitrag."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cache
from gettext import gettext as _
from zoneinfo import ZoneInfo, available_timezones

from gi.repository import Adw, GLib, Gtk


@cache
def all_timezones() -> list[str]:
    zones = sorted(z for z in available_timezones()
                   if "/" in z and not z.startswith(("Etc/", "SystemV/", "posix/", "right/")))
    return ["UTC", *zones]


def system_timezone() -> str:
    ident = GLib.TimeZone.new_local().get_identifier()
    return ident if ident in all_timezones() else "UTC"


def format_when(dt: datetime, tz: str | None = None) -> str:
    local = dt.astimezone(ZoneInfo(tz)) if tz else dt.astimezone()
    now = datetime.now(local.tzinfo)
    if local.date() == now.date():
        day = _("today")
    elif local.date() == (now + timedelta(days=1)).date():
        day = _("tomorrow")
    else:
        day = local.strftime("%a, %d.%m.%Y")
    return _("{day} at {time}").format(day=day, time=local.strftime("%H:%M"))


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/schedule-dialog.ui")
class DandelionScheduleDialog(Adw.Dialog):
    __gtype_name__ = "DandelionScheduleDialog"

    schedule_button: Gtk.Button = Gtk.Template.Child()
    service_banner: Adw.Banner = Gtk.Template.Child()
    presets_box: Adw.WrapBox = Gtk.Template.Child()
    calendar: Gtk.Calendar = Gtk.Template.Child()
    hour_row: Adw.SpinRow = Gtk.Template.Child()
    minute_row: Adw.SpinRow = Gtk.Template.Child()
    tz_row: Adw.ComboRow = Gtk.Template.Child()
    summary_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, *, initial: datetime | None, timezone: str | None,
                 service_active: bool, on_schedule: Callable[[datetime, str], None],
                 on_enable_service: Callable[[], None],
                 next_slot: datetime | None = None) -> None:
        super().__init__()
        self._loading = True
        self._on_schedule = on_schedule
        self._on_enable = on_enable_service
        self._next_slot = next_slot
        self.service_banner.set_revealed(not service_active)

        self.zones = all_timezones()
        self.tz_row.set_model(Gtk.StringList.new(self.zones))
        self.tz_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        tz = timezone if timezone in self.zones else system_timezone()
        self.tz_row.set_selected(self.zones.index(tz))

        if initial is None:
            initial = (datetime.now(UTC) + timedelta(hours=1)).replace(minute=0, second=0)
        self._set(initial)
        self._build_presets()
        self._loading = False
        self.on_changed()

    # -- Werte -------------------------------------------------------------
    def tz(self) -> str:
        return self.zones[self.tz_row.get_selected()]

    def value(self) -> datetime:
        date = self.calendar.get_date()
        return datetime(date.get_year(), date.get_month(), date.get_day_of_month(),
                        int(self.hour_row.get_value()), int(self.minute_row.get_value()),
                        tzinfo=ZoneInfo(self.tz()))

    def _set(self, when: datetime) -> None:
        local = when.astimezone(ZoneInfo(self.tz()))
        self.calendar.select_day(GLib.DateTime.new_local(local.year, local.month, local.day,
                                                         12, 0, 0))
        self.hour_row.set_value(local.hour)
        self.minute_row.set_value(local.minute)

    def _build_presets(self) -> None:
        tzinfo = ZoneInfo(self.tz())
        now = datetime.now(tzinfo)
        today = now.replace(second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        monday = today + timedelta(days=(7 - today.weekday()) or 7)
        presets: list[tuple[str, datetime]] = []
        if self._next_slot:
            presets.append((_("Next Free Slot · {when}").format(
                when=self._next_slot.astimezone(tzinfo).strftime("%a %d.%m. %H:%M")),
                self._next_slot))
        presets.append((_("In One Hour"),
                        (now + timedelta(hours=1)).replace(second=0, microsecond=0)))
        if now.hour < 17:
            presets.append((_("This Evening, 18:00"), today.replace(hour=18, minute=0)))
        presets += [
            (_("Tomorrow, 08:00"), tomorrow.replace(hour=8, minute=0)),
            (_("Tomorrow, 12:00"), tomorrow.replace(hour=12, minute=0)),
            (_("Monday, 08:00"), monday.replace(hour=8, minute=0)),
        ]
        for i, (label, when) in enumerate(presets):
            btn = Gtk.Button(label=label)
            btn.add_css_class("pill")
            if i == 0 and self._next_slot:
                btn.add_css_class("accent-pill")
            btn.connect("clicked", lambda _b, w=when: self._apply_preset(w))
            self.presets_box.append(btn)

    def _apply_preset(self, when: datetime) -> None:
        self._loading = True
        self._set(when)
        self._loading = False
        self.on_changed()

    # -- Rückmeldungen -------------------------------------------------------
    @Gtk.Template.Callback()
    def on_output(self, row: Adw.SpinRow) -> bool:
        row.set_text(f"{int(row.get_value()):02d}")
        return True

    @Gtk.Template.Callback()
    def on_changed(self, *_args: object) -> None:
        if self._loading:
            return
        try:
            when = self.value()
        except ValueError:
            return
        label = self.summary_label
        label.remove_css_class("error")
        label.remove_css_class("dim-label")
        if when <= datetime.now(UTC) + timedelta(seconds=30):
            label.set_label(_("This time is in the past."))
            label.add_css_class("error")
            self.schedule_button.set_sensitive(False)
            return
        text = _("Will be published {when}.").format(when=format_when(when, self.tz()))
        if self.tz() != system_timezone():
            text += " " + _("That is {when} in your local time.").format(
                when=format_when(when))
        label.set_label(text)
        label.add_css_class("dim-label")
        self.schedule_button.set_sensitive(True)

    @Gtk.Template.Callback()
    def on_cancel(self, *_args: object) -> None:
        self.close()

    @Gtk.Template.Callback()
    def on_schedule(self, *_args: object) -> None:
        self._on_schedule(self.value(), self.tz())
        self.close()

    @Gtk.Template.Callback()
    def on_enable_service(self, *_args: object) -> None:
        self._on_enable()
        self.service_banner.set_revealed(False)
