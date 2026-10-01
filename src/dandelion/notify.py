# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop-Benachrichtigungen zu geplanten Beiträgen (GNotification)."""

from __future__ import annotations

from datetime import datetime
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Gio, GLib

from .core.models import Post, PostState, TargetState
from .core.scheduler import RunResult
from .util import first_line


def _planned(post: Post) -> str:
    if not post.scheduled_at:
        return ""
    return datetime.fromisoformat(post.scheduled_at).astimezone().strftime("%d.%m. %H:%M")


def notify_result(app: Gio.Application, settings: Gio.Settings, result: RunResult) -> None:
    for post in result.sent + result.late:
        ok = sum(1 for t in post.targets if t.enabled and t.state == TargetState.PUBLISHED)
        total = sum(1 for t in post.targets if t.enabled)
        text = first_line(post.body, 120)
        if post.state == PostState.PUBLISHED:
            if not settings.get_boolean("notify-success"):
                continue
            n = Gio.Notification.new(_("Scheduled post published"))
            body = ngettext("{text}\nPublished on {n} profile.", "{text}\nPublished on {n} profiles.",
                            total).format(text=text, n=total)
            if post in result.late:
                body += "\n" + _("Sent late, it was planned for {time}.").format(time=_planned(post))
            n.set_body(body)
        else:
            if not settings.get_boolean("notify-failure"):
                continue
            n = Gio.Notification.new(_("Scheduled post failed"))
            n.set_body(_("{text}\nPublished on {ok} of {total} profiles.").format(
                text=text, ok=ok, total=total))
            n.set_priority(Gio.NotificationPriority.HIGH)
            n.add_button(_("Details"), "app.show-history")
        n.set_default_action("app.show-history")
        app.send_notification(f"post-{post.id}", n)

    for post in result.missed:
        n = Gio.Notification.new(_("A scheduled post was not sent"))
        n.set_body(_("{text}\nIt was planned for {time}, but the computer was off or asleep.").format(
            text=first_line(post.body, 120), time=_planned(post)))
        n.set_priority(Gio.NotificationPriority.HIGH)
        n.add_button_with_target(_("Send Now"), "app.send-post", GLib.Variant("x", post.id))
        n.add_button_with_target(_("Discard"), "app.discard-post", GLib.Variant("x", post.id))
        n.set_default_action("app.show-scheduled")
        app.send_notification(f"post-{post.id}", n)
