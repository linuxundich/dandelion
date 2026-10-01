# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Adw, Gdk, GLib, Gtk

from .core.models import Post, Profile, Target, TargetState
from .util import label_widget


class TargetRow(Adw.ActionRow):
    def __init__(self, profile: Profile, platform_name: str,
                 on_retry: Callable[[int], None]) -> None:
        super().__init__(title=GLib.markup_escape_text(profile.full_handle),
                         subtitle=platform_name)
        self.profile = profile
        self.set_subtitle_selectable(True)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.spinner = Adw.Spinner()
        self.stack.add_named(self.spinner, "busy")
        ok = Gtk.Image(icon_name="object-select-symbolic")
        ok.add_css_class("success")
        self.stack.add_named(ok, "ok")
        err = Gtk.Image(icon_name="dialog-error-symbolic")
        err.add_css_class("error")
        self.stack.add_named(err, "error")
        self.stack.add_named(Gtk.Box(), "idle")
        self.add_prefix(self.stack)

        self.open_button = Gtk.Button(icon_name="adw-external-link-symbolic", valign=Gtk.Align.CENTER,
                                      tooltip_text=_("Open Post"), visible=False)
        self.open_button.add_css_class("flat")
        label_widget(self.open_button, self.open_button.get_tooltip_text() or "")
        self.open_button.connect("clicked", self._open)
        self.add_suffix(self.open_button)
        self.retry_button = Gtk.Button(label=_("_Retry"), use_underline=True,
                                       valign=Gtk.Align.CENTER, visible=False)
        self.retry_button.connect("clicked", lambda *_: on_retry(profile.id))  # type: ignore[arg-type]
        self.add_suffix(self.retry_button)
        self.url: str | None = None
        self.platform_name = platform_name

    def _open(self, *_args: object) -> None:
        if self.url:
            Gtk.UriLauncher.new(self.url).launch(self.get_root(), None, None)

    def update(self, target: Target, stage: str) -> None:
        if stage.startswith("upload:"):
            _u, i, n = stage.split(":")
            self.stack.set_visible_child_name("busy")
            self.set_subtitle(_("Uploading media {i} of {n}").format(i=i, n=n))
        elif stage in ("start", "posting"):
            self.stack.set_visible_child_name("busy")
            self.set_subtitle(_("Publishing") if stage == "posting" else _("Preparing"))
            self.retry_button.set_visible(False)
        elif target.state == TargetState.PUBLISHED:
            self.stack.set_visible_child_name("ok")
            self.set_subtitle(_("Published"))
            self.url = target.remote_url
            self.open_button.set_visible(bool(self.url))
            self.retry_button.set_visible(False)
        elif target.state == TargetState.FAILED:
            self.stack.set_visible_child_name("error")
            self.set_subtitle(GLib.markup_escape_text(target.last_error or _("Failed")))
            self.retry_button.set_visible(True)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/send-dialog.ui")
class DandelionSendDialog(Adw.Dialog):
    __gtype_name__ = "DandelionSendDialog"

    target_list: Gtk.ListBox = Gtk.Template.Child()
    summary_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, post: Post, profiles: dict[int, Profile], platform_names: dict[str, str],
                 on_retry: Callable[[int], None]) -> None:
        super().__init__()
        self.rows: dict[int, TargetRow] = {}
        for t in post.targets:
            if not t.enabled or t.profile_id not in profiles:
                continue
            p = profiles[t.profile_id]
            row = TargetRow(p, platform_names.get(p.platform, p.platform), on_retry)
            self.rows[t.profile_id] = row
            self.target_list.append(row)
            if t.state == TargetState.PUBLISHED:
                row.update(t, "published")
            else:
                row.stack.set_visible_child_name("busy")
                row.set_subtitle(_("Waiting"))

    def update(self, target: Target, stage: str) -> None:
        row = self.rows.get(target.profile_id)
        if row:
            row.update(target, stage)

    def finish(self, post: Post) -> None:
        ok = sum(1 for t in post.targets if t.enabled and t.state == TargetState.PUBLISHED)
        total = sum(1 for t in post.targets if t.enabled)
        self.summary_label.set_label(ngettext(
            "Published on {ok} of {total} profile.", "Published on {ok} of {total} profiles.",
            total).format(ok=ok, total=total))
        self.summary_label.set_visible(True)


def copy_text(widget: Gtk.Widget, text: str) -> None:
    Gdk.Display.get_default().get_clipboard().set(text)
