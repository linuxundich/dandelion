# SPDX-License-Identifier: GPL-3.0-or-later
"""Zeilen der Deck-Spalten: Beitrag, Benachrichtigung und Konversation."""

from __future__ import annotations

import html
import re
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Adw, GLib, Gtk, Pango

from ..reader.base import (
    POST_REASONS,
    FeedAccount,
    FeedCard,
    FeedConversation,
    FeedMedia,
    FeedPoll,
    FeedPost,
)
from ..reader.content import relative_time, to_markup, to_text
from ..util import spawn
from .avatars import AvatarCache
from .profile_chip import platform_badge

REASON_ICONS = {
    "favourite": "starred-symbolic", "boost": "media-playlist-repeat-symbolic",
    "follow": "contact-new-symbolic", "follow_request": "contact-new-symbolic",
    "poll": "view-list-bullet-symbolic", "update": "document-edit-symbolic",
}


def post_markup(post: FeedPost) -> str:
    return post.markup if post.markup is not None else to_markup(post.html)


def post_text(post: FeedPost) -> str:
    """Nur der Text, etwa für kurze Auszüge."""
    if post.markup is not None:
        return html.unescape(re.sub(r"<[^>]+>", "", post.markup))
    return to_text(post.html)


def excerpt(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def open_url(widget: Gtk.Widget, url: str) -> None:
    if url.startswith(("http://", "https://")):
        Gtk.UriLauncher(uri=url).launch(widget.get_root(), None, lambda *_args: None)


def _dim(text: str, *classes: str, ellipsize: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    for c in ("dim-label", *classes):
        label.add_css_class(c)
    if ellipsize:
        label.set_ellipsize(Pango.EllipsizeMode.END)
    return label


def _icon_count(icon: str, count: int, tooltip: str) -> Gtk.Box:
    box = Gtk.Box(spacing=4, tooltip_text=tooltip)
    image = Gtk.Image.new_from_icon_name(icon)
    image.add_css_class("dim-label")
    box.append(image)
    box.append(_dim(str(count), "caption", "numeric"))
    return box


def _info_line(icon: str, text: str) -> Gtk.Box:
    box = Gtk.Box(spacing=6)
    image = Gtk.Image.new_from_icon_name(icon)
    image.add_css_class("dim-label")
    box.append(image)
    label = _dim(text, "caption", ellipsize=True)
    label.set_hexpand(True)
    box.append(label)
    return box


def _clickable(widget: Gtk.Widget, url: str) -> None:
    if not url:
        return
    click = Gtk.GestureClick()
    click.connect("released", lambda *_args: open_url(widget, url))
    widget.add_controller(click)
    widget.set_cursor_from_name("pointer")


def _account_click(widget: Gtk.Widget, account: FeedAccount, actions) -> None:  # type: ignore[no-untyped-def]
    if actions is None:
        return
    click = Gtk.GestureClick()
    click.connect("released", lambda *_args: actions.account(widget, account))
    widget.add_controller(click)
    widget.set_cursor_from_name("pointer")


def avatar_for(account: FeedAccount, avatars: AvatarCache, size: int,
               network: str | None = None) -> Gtk.Widget:
    avatar = Adw.Avatar(size=size, text=account.name, show_initials=True, valign=Gtk.Align.START)
    avatars.apply(avatar, account.avatar_url)
    if network is None:
        return avatar
    overlay = Gtk.Overlay(child=avatar, valign=Gtk.Align.START)
    overlay.add_overlay(platform_badge(network))
    return overlay


# -- Bausteine -------------------------------------------------------------
def _tile(media: FeedMedia, height: int, avatars: AvatarCache) -> Gtk.Widget:
    overlay = Gtk.Overlay()
    overlay.add_css_class("feed-media")
    pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, height_request=height,
                      hexpand=True, alternative_text=media.alt or _("Image without description"))
    overlay.set_child(pic)
    url = media.preview_url or media.url
    avatars.load(url, lambda tex: tex is not None and pic.set_paintable(tex))
    if media.alt:
        badge = Gtk.Label(label=_("ALT"), halign=Gtk.Align.START, valign=Gtk.Align.END,
                          margin_start=6, margin_bottom=6)
        badge.add_css_class("alt-badge")
        overlay.add_overlay(badge)
        overlay.set_tooltip_text(excerpt(media.alt, 300))
    if media.kind in ("video", "gifv"):
        play = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
        play.set_pixel_size(32)
        play.add_css_class("feed-play")
        play.set_halign(Gtk.Align.CENTER)
        play.set_valign(Gtk.Align.CENTER)
        overlay.add_overlay(play)
    _clickable(overlay, media.url or url)
    return overlay


def media_widget(items: list[FeedMedia], avatars: AvatarCache) -> Gtk.Widget | None:
    """Bilder als Raster; Anhänge ohne Vorschau erscheinen als Hinweiszeile."""
    pictured = [m for m in items if m.preview_url or (m.kind == "image" and m.url)]
    missing = len(items) - len(pictured)
    if not items:
        return None
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    if pictured:
        grid = Gtk.Grid(column_spacing=4, row_spacing=4, column_homogeneous=True)
        n = len(pictured)
        height = 220 if n == 1 else 130
        for i, m in enumerate(pictured[:4]):
            wide = n == 1 or (n == 3 and i == 2)
            grid.attach(_tile(m, height, avatars), (i % 2) if not wide else 0, i // 2,
                        2 if wide else 1, 1)
        box.append(grid)
    if missing:
        box.append(_info_line("image-x-generic-symbolic",
                              ngettext("{n} attachment", "{n} attachments", missing)
                              .format(n=missing)))
    return box


def poll_widget(poll: FeedPoll) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    for title, votes in poll.options:
        share = votes / poll.votes if poll.votes else 0.0
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        head = Gtk.Box(spacing=8)
        label = Gtk.Label(label=title, xalign=0, hexpand=True, wrap=True)
        head.append(label)
        head.append(_dim(f"{round(share * 100)} %", "caption", "numeric"))
        row.append(head)
        bar = Gtk.ProgressBar(fraction=share)
        bar.add_css_class("feed-poll")
        row.append(bar)
        box.append(row)
    state = _("closed") if poll.expired else _("open")
    box.append(_dim(ngettext("{n} vote", "{n} votes", poll.votes).format(n=poll.votes)
                    + " · " + state, "caption"))
    return box


def card_widget(card: FeedCard, avatars: AvatarCache) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.add_css_class("feed-card")
    if card.image_url:
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, height_request=120,
                          alternative_text="")
        avatars.load(card.image_url, lambda tex: tex is not None and pic.set_paintable(tex))
        box.append(pic)
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8, margin_bottom=8,
                   margin_start=10, margin_end=10)
    title = Gtk.Label(label=card.title, xalign=0, wrap=True, lines=2,
                      ellipsize=Pango.EllipsizeMode.END)
    title.add_css_class("heading")
    text.append(title)
    if card.description:
        desc = _dim(excerpt(card.description, 200), "caption")
        desc.set_wrap(True)
        desc.set_lines(2)
        desc.set_ellipsize(Pango.EllipsizeMode.END)
        text.append(desc)
    host = GLib.Uri.parse(card.url, GLib.UriFlags.NONE).get_host() if card.url else ""
    text.append(_dim(host or card.url, "caption", ellipsize=True))
    box.append(text)
    _clickable(box, card.url)
    return box


def quote_widget(quote: FeedPost) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.add_css_class("feed-card")
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8, margin_bottom=8,
                    margin_start=10, margin_end=10)
    name = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
    name.set_markup(f"<b>{GLib.markup_escape_text(quote.account.name)}</b>  "
                    f"<span alpha='60%'>@{GLib.markup_escape_text(quote.account.acct)}</span>")
    inner.append(name)
    text = Gtk.Label(xalign=0, wrap=True, lines=6, ellipsize=Pango.EllipsizeMode.END,
                     use_markup=True)
    text.set_markup(post_markup(quote))
    inner.append(text)
    box.append(inner)
    _clickable(box, quote.url)
    return box


def post_details(post: FeedPost, avatars: AvatarCache) -> Gtk.Box:
    """Text, Medien, Umfrage, Linkkarte und Zitat eines Beitrags."""
    details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    if post_markup(post):
        content = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                            use_markup=True, halign=Gtk.Align.FILL)
        # to_markup und facets_markup liefern immer wohlgeformtes Markup (siehe Tests)
        content.set_markup(post_markup(post))
        details.append(content)
    media = media_widget(post.media, avatars)
    if media:
        details.append(media)
    if post.poll:
        details.append(poll_widget(post.poll))
    if post.card:
        details.append(card_widget(post.card, avatars))
    if post.quote:
        details.append(quote_widget(post.quote))
    return details


# -- Zeilen ------------------------------------------------------------------
def _frame(unread: bool) -> Gtk.Box:
    root = Gtk.Box(spacing=10)
    root.add_css_class("feed-row")
    if unread:
        root.add_css_class("unread")
    return root


def _reason_caption(post: FeedPost) -> str | None:
    if post.boosted_by:
        return _("{name} boosted").format(name=post.boosted_by.name)
    return {"mention": _("Mentioned you"), "reply": _("Replied to you"),
            "quote": _("Quoted your post"), "status": _("New post"),
            "update": _("Edited a post")}.get(post.reason or "")


def _action_button(icon: str, count: int, tip: str, callback) -> Gtk.Button:  # type: ignore[no-untyped-def]
    btn = Gtk.Button(tooltip_text=tip)
    btn.add_css_class("flat")
    btn.add_css_class("feed-act")
    box = Gtk.Box(spacing=4)
    box.append(Gtk.Image.new_from_icon_name(icon))
    label = Gtk.Label(label=str(count) if count else "")
    label.add_css_class("caption")
    label.add_css_class("numeric")
    box.append(label)
    btn.set_child(box)
    btn.update_property([Gtk.AccessibleProperty.LABEL], [tip])
    btn.connect("clicked", lambda *_args: callback())
    return btn


def _toggle_button(post: FeedPost, kind: str, actions, tip: str) -> Gtk.ToggleButton:  # type: ignore[no-untyped-def]
    """Favorit, Boost oder Lesezeichen: schaltet sofort um und macht es bei einem Fehler rückgängig."""
    attr = {"favourite": "favourited", "boost": "boosted", "bookmark": "bookmarked"}[kind]
    count_attr = {"favourite": "likes", "boost": "boosts"}.get(kind)
    icons = {"favourite": ("non-starred-symbolic", "starred-symbolic"),
             "boost": ("media-playlist-repeat-symbolic",) * 2,
             "bookmark": ("bookmark-new-symbolic", "user-bookmarks-symbolic")}[kind]
    btn = Gtk.ToggleButton(active=getattr(post, attr), tooltip_text=tip)
    for c in ("flat", "feed-act", f"feed-act-{kind}"):
        btn.add_css_class(c)
    box = Gtk.Box(spacing=4)
    image = Gtk.Image.new_from_icon_name(icons[1] if btn.get_active() else icons[0])
    label = Gtk.Label()
    label.add_css_class("caption")
    label.add_css_class("numeric")
    box.append(image)
    box.append(label)
    btn.set_child(box)
    btn.update_property([Gtk.AccessibleProperty.LABEL], [tip])

    def show() -> None:
        on = getattr(post, attr)
        image.set_from_icon_name(icons[1] if on else icons[0])
        n = getattr(post, count_attr) if count_attr else 0
        label.set_label(str(n) if n else "")
        label.set_visible(bool(n))

    def apply(on: bool) -> None:
        setattr(post, attr, on)
        if count_attr:
            setattr(post, count_attr, max(0, getattr(post, count_attr) + (1 if on else -1)))
        show()

    handler = 0

    def on_toggled(b: Gtk.ToggleButton) -> None:
        on = b.get_active()
        apply(on)

        async def run() -> None:
            if await actions.toggle(post, kind, on):
                return
            apply(not on)                                  # Fehler: zurücksetzen
            b.handler_block(handler)
            b.set_active(not on)
            b.handler_unblock(handler)
        spawn(run())

    handler = btn.connect("toggled", on_toggled)
    show()
    if kind == "boost" and post.visibility in ("private", "direct"):
        btn.set_sensitive(False)
        btn.set_tooltip_text(_("This post cannot be boosted"))
    return btn


def _more_button(post: FeedPost, actions) -> Gtk.MenuButton:  # type: ignore[no-untyped-def]
    pop = Gtk.Popover()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

    def item(icon: str, text: str, callback) -> None:  # type: ignore[no-untyped-def]
        row = Gtk.Box(spacing=8)
        row.append(Gtk.Image.new_from_icon_name(icon))
        row.append(Gtk.Label(label=text, xalign=0))
        b = Gtk.Button(child=row)
        b.add_css_class("flat")
        b.connect("clicked", lambda *_a: (pop.popdown(), callback()))
        box.append(b)

    if actions.can_quote():
        item("format-indent-more-symbolic", _("Quote"), lambda: actions.quote(post))
    if post.url:
        item("web-browser-symbolic", _("Open in Browser"), lambda: open_url(btn, post.url))
        item("edit-copy-symbolic", _("Copy Link"),
             lambda: btn.get_clipboard().set(post.url))
    pop.set_child(box)
    btn = Gtk.MenuButton(icon_name="view-more-symbolic", popover=pop, tooltip_text=_("More"))
    btn.add_css_class("flat")
    btn.add_css_class("feed-act")
    btn.update_property([Gtk.AccessibleProperty.LABEL], [_("More")])
    return btn


def action_bar(post: FeedPost, actions) -> Gtk.Box:  # type: ignore[no-untyped-def]
    bar = Gtk.Box(spacing=2, margin_top=2, margin_start=-8)
    bar.append(_action_button("mail-reply-sender-symbolic", post.replies, _("Reply"),
                              lambda: actions.reply(post)))
    bar.append(_toggle_button(post, "boost", actions, _("Boost")))
    bar.append(_toggle_button(post, "favourite", actions, _("Favourite")))
    bar.append(_toggle_button(post, "bookmark", actions, _("Bookmark")))
    spacer = Gtk.Box(hexpand=True)
    bar.append(spacer)
    bar.append(_more_button(post, actions))
    return bar


def post_row(post: FeedPost, avatars: AvatarCache, unread: bool = False,
             actions=None) -> Gtk.Box:  # type: ignore[no-untyped-def]
    root = _frame(unread)
    avatar = avatar_for(post.account, avatars, 36)
    _account_click(avatar, post.account, actions)
    root.append(avatar)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    root.append(body)

    caption = _reason_caption(post)
    if caption:
        body.append(_dim(caption, "caption", ellipsize=True))

    head = Gtk.Box(spacing=6)
    name = Gtk.Label(label=post.account.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
    name.add_css_class("heading")
    _account_click(name, post.account, actions)
    head.append(name)
    age = _dim(relative_time(post.created_at) if post.created_at else "", "caption", "numeric")
    age.set_hexpand(True)
    age.set_xalign(1)
    head.append(age)
    body.append(head)
    body.append(_dim(f"@{post.account.acct}", "caption", ellipsize=True))

    details = post_details(post, avatars)
    details.set_margin_top(4)
    if post.spoiler or (post.sensitive and post.media):
        revealer = Gtk.Revealer(child=details)
        toggle = Gtk.ToggleButton(label=_("Show"), valign=Gtk.Align.CENTER)
        toggle.add_css_class("flat")
        toggle.connect("toggled", lambda b: (
            revealer.set_reveal_child(b.get_active()),
            b.set_label(_("Hide") if b.get_active() else _("Show"))))
        row = Gtk.Box(spacing=8, margin_top=4)
        label = Gtk.Label(label=post.spoiler or _("Sensitive content"), xalign=0, wrap=True,
                          hexpand=True)
        label.add_css_class("heading")
        row.append(label)
        row.append(toggle)
        body.append(row)
        body.append(revealer)
    else:
        body.append(details)

    if actions is not None and post.ref:
        body.append(action_bar(post, actions))
    else:
        counts = Gtk.Box(spacing=16, margin_top=4)
        for icon, n, tip in (("mail-reply-sender-symbolic", post.replies, _("Replies")),
                             ("media-playlist-repeat-symbolic", post.boosts, _("Boosts")),
                             ("starred-symbolic", post.likes, _("Favourites"))):
            if n:
                counts.append(_icon_count(icon, n, tip))
        if counts.get_first_child():
            body.append(counts)

    root.update_property([Gtk.AccessibleProperty.LABEL],
                         [f"{post.account.name}: {excerpt(post_text(post), 200)}"])
    return root


def notification_row(post: FeedPost, avatars: AvatarCache, unread: bool = False) -> Gtk.Box:
    """Favorit, Boost, Follower, Umfrage: eine kompakte Zeile mit Auszug."""
    root = _frame(unread)
    icon = Gtk.Image.new_from_icon_name(REASON_ICONS.get(post.reason or "", "dialog-information-symbolic"))
    icon.set_valign(Gtk.Align.START)
    icon.set_pixel_size(20)
    icon.set_margin_top(4)
    icon.add_css_class("accent")
    root.append(icon)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
    root.append(body)
    head = Gtk.Box(spacing=8)
    head.append(avatar_for(post.account, avatars, 28))
    name = GLib.markup_escape_text(post.account.name)
    text = {
        "favourite": _("<b>{name}</b> favourited your post"),
        "boost": _("<b>{name}</b> boosted your post"),
        "follow": _("<b>{name}</b> followed you"),
        "follow_request": _("<b>{name}</b> wants to follow you"),
        "poll": _("A poll you took part in has ended"),
        "update": _("<b>{name}</b> edited a post"),
    }.get(post.reason or "", _("<b>{name}</b>")).format(name=name)
    label = Gtk.Label(xalign=0, wrap=True, hexpand=True, use_markup=True, valign=Gtk.Align.CENTER)
    label.set_markup(text)
    head.append(label)
    age = _dim(relative_time(post.created_at) if post.created_at else "", "caption", "numeric")
    age.set_valign(Gtk.Align.START)
    head.append(age)
    body.append(head)
    if post.subject:
        quote = Gtk.Label(label=excerpt(post_text(post.subject)), xalign=0, wrap=True, lines=3,
                          ellipsize=Pango.EllipsizeMode.END)
        quote.add_css_class("feed-excerpt")
        quote.add_css_class("dim-label")
        body.append(quote)
    elif post.reason == "follow":
        body.append(_dim(f"@{post.account.acct}", "caption", ellipsize=True))
    root.update_property([Gtk.AccessibleProperty.LABEL], [re.sub(r"<[^>]+>", "", text)])
    return root


def conversation_row(conv: FeedConversation, avatars: AvatarCache) -> Gtk.Box:
    root = _frame(conv.unread)
    first = conv.accounts[0] if conv.accounts else FeedAccount("", "?", "?")
    root.append(avatar_for(first, avatars, 36))
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    root.append(body)
    names = ", ".join(a.name for a in conv.accounts[:2])
    if len(conv.accounts) > 2:
        names += " " + ngettext("and {n} other", "and {n} others", len(conv.accounts) - 2).format(
            n=len(conv.accounts) - 2)
    head = Gtk.Box(spacing=6)
    name = Gtk.Label(label=names or first.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
    name.add_css_class("heading")
    head.append(name)
    age = _dim(relative_time(conv.created_at) if conv.created_at else "", "caption", "numeric")
    age.set_hexpand(True)
    age.set_xalign(1)
    head.append(age)
    body.append(head)
    if conv.last:
        text = Gtk.Label(label=excerpt(post_text(conv.last), 140), xalign=0, wrap=True, lines=2,
                         ellipsize=Pango.EllipsizeMode.END)
        if not conv.unread:
            text.add_css_class("dim-label")
        body.append(text)
    if conv.unread:
        dot = Gtk.Box(width_request=9, height_request=9, valign=Gtk.Align.CENTER)
        dot.add_css_class("unread-dot")
        root.append(dot)
    root.update_property([Gtk.AccessibleProperty.LABEL],
                         [f"{names}: {excerpt(post_text(conv.last), 120) if conv.last else ''}"])
    return root
