# Deck: a multi-column Mastodon reader inside Dandelion

Concept, 2026-11-11 · based on Dandelion 0.3.1. Status: **proposal, nothing built**.
Mockups: [deck-mockups.html](deck-mockups.html).

**Status 2026-11-11:** phases 1 to 5 are implemented (nothing tried against a
real account yet). Deviations: the feed
lists use a `Gtk.ListBox` with at most 60 + 40 per step rows instead of a
`Gtk.ListView`; read positions are stored as timestamps and mapped to the
server markers (Mastodon) or `updateSeen` (Bluesky); Bluesky has no *Messages*
tab yet (phase 6). Lists, hashtags and bookmarks are own columns (not switched in
place inside a profile column); the column setup is a dialog, not a page.

## Goal

Dandelion writes once and posts everywhere. The deck adds the other half:
**reading**. Every Mastodon and Bluesky profile that belongs to a role gets its own column
with its timeline (the accounts, lists and hashtags it follows), its
notifications and its private messages. Switch the role and the deck shows the
columns of that role's profiles. No second app for reading, no second login.

## Decisions to confirm

| # | Question | Recommendation |
|---|---|---|
| 1 | One column per profile or one per feed? | **One column per profile with tabs** *Home · Notifications · Messages*. Lists, hashtags and bookmarks switch inside the same column or pop out as their own column. This is what "a column per profile with all its messages and subscriptions" asks for and keeps the deck at 3 to 4 columns per role. |
| 2 | Where does the deck live? | **Second mode of the existing window**: *Write* / *Read* toggle on top of the sidebar. Same window, same roles, same account setup. |
| 3 | Which networks? | **Mastodon and Bluesky.** Both behind one `Reader` interface and one normalised post model, so a column does not know the network. X, LinkedIn and Facebook get no columns (no usable read API; X charges per call). Bluesky details below. |
| 4 | Scopes | Mastodon logins today are write-only. Existing profiles must grant reading once ("Allow reading" banner on the profile). New logins ask for it right away. |
| 5 | Live updates | **Streaming API** (WebSocket) while the deck is visible, polling as fallback. Desktop notifications from the background service are an opt-in later phase. |
| 6 | Boosts and replies | Shown by default; per column switch "hide boosts" and "hide replies". |

## Information architecture

```
Role  ──has──▶  Profiles (Mastodon, Bluesky)  ──each──▶  Profile column
                                                  ├─ Home            (accounts you follow)
                                                  ├─ Notifications   (mentions, boosts, favourites, follows, polls)
                                                  ├─ Messages        (direct conversations)
                                                  └─ ⋯ Lists · Followed hashtags · Bookmarks · Favourites
                                                       └─ "Open as column"
```

- A profile in several roles shows up in each of those decks but shares **one
  cache, one stream and one read position**. Reading a post in "Blog" marks it
  read in "Private".
- Column order, width and extra columns are stored per role.
- Window width decides the layout, like the composer already does:

| Width | Layout |
|---|---|
| ≥ 1400 sp | 3 to 4 columns side by side, sidebar open |
| 900 – 1399 sp | 2 to 3 columns, sidebar collapsed to icons |
| < 900 sp | one column at a time, swipe or bottom switcher between profiles |
| 360 sp | same, composer as full page |

## Screens

1. **Deck** (wide): roles in the sidebar with unread counts, one column per
   profile, tab strip per column, reply and compose inline.
2. **Column anatomy**: header with avatar, handle, instance, unread dot, tab
   strip, post row (boost, reply, favourite, bookmark, share, content warning,
   media, poll, link card, alt badge).
3. **Reply / quick post** in the column: opens the existing composer as a
   small sheet with the profile preselected. Full cross-posting stays in
   *Write*.
4. **Add column** dialog and the role's **Columns** page.
5. **Narrow** (phone width).

## Architecture

New package `src/dandelion/reader/`, nothing in `platforms/` is bent out of
shape:

| Module | Job |
|---|---|
| `reader/base.py` | `Reader` interface (load, load more, actions, unread, mark read) and the normalised post model: author, rich text, media, counts, labels. |
| `reader/mastodon.py` | REST: home, notifications, conversations, lists, tag timelines, markers, filters, status actions. Reuses `Mastodon._api()` for tokens and errors. |
| `reader/bluesky.py` | XRPC: timeline, notifications, chats, saved feeds, lists, bookmarks, actions. Reuses the session handling of `platforms/bluesky.py`. |
| `reader/stream.py` | Mastodon: WebSocket per profile (`/api/v1/streaming`, libsoup 3), one `user` stream for home and notifications; list and hashtag streams only while their column is visible. Backoff and polling fallback. |
| `reader/cache.py` | SQLite tables `status`, `account`, `notification`, `conversation`, `column`, `read_marker`. Keeps the last ~400 posts per feed, media on disk with size limit. |
| `reader/content.py` | Mastodon HTML → Pango markup (links, mentions, hashtags, custom emoji, line breaks), content warnings, sensitive media, no WebView. |
| `ui/deck.blp`, `ui/column.blp` | Deck container and column. |
| `widgets/status_row.py`, `media_grid.py`, `poll_view.py` | Post row, media grid, polls. `preview_tile.py` and avatar code are reused. |

Details that matter:

- **List performance:** every column uses `Gtk.ListView` with a model, so
  long timelines stay cheap; images load lazily and are cached.
- **Deck container:** a horizontal `Gtk.ScrolledWindow` with fixed-width
  columns (min 340, default 380 sp) and snap scrolling; below 900 sp an
  `Adw.Carousel`.
- **Read position:** Mastodon markers API (`home`, `notifications`) so the
  position follows the account across devices.
- **Scopes:** `read write:statuses write:media write:favourites
  write:bookmarks write:conversations` (replaces the current write-only set
  in `platforms/mastodon.py`). Profiles with the old token get
  `status_detail = "read scope missing"` and the banner.
- **Secrets, network, i18n:** same keyring, same `net/http.py`, all strings
  German and English via the existing `po/` setup.
- **No AI calls in the reader.** The writing assistant stays in the composer.

## Bluesky

Same column, same tabs; the differences stay inside `reader/bluesky.py`.

| Column | Mastodon | Bluesky |
|---|---|---|
| Home | home timeline | `app.bsky.feed.getTimeline` (follows) |
| Notifications | notifications | `listNotifications`, read position via `updateSeen` |
| Messages | conversations | chat conversations (`chat.bsky.convo`) |
| ⋯ More feeds | lists, followed hashtags, bookmarks | saved feeds, lists, bookmarks |
| Actions | boost, favourite | repost, like, quote, bookmark |

- **Login:** app passwords already allow reading, so **no re-login** for Home
  and Notifications. Chats need an app password with chat access; the Messages
  tab shows a notice with "Update app password" until then. Bluesky OAuth
  (already in the backlog) would replace this later.
- **Live updates:** Bluesky has no personal stream. The deck polls every
  30 to 60 s while the window is open and pauses when it is hidden.
- **Text:** posts carry facets (links, mentions, tags) instead of HTML, so
  rendering is simpler than on Mastodon.
- **Content warnings:** Bluesky has labels. They use the same fold-out as
  Mastodon content warnings.
- **Missing counterparts:** no polls, no followed hashtags; groups of chats
  only if the API offers them.
- **Visual:** a small network badge on the avatar of a column and in the
  sidebar; no separate colour scheme.

## Phases

Each phase ends with a release and a pause for your approval, as for the
earlier redesign.

| Phase | Content | Result |
|---|---|---|
| 1 | Mastodon scopes + re-authorisation, `Reader` interface and post model, Mastodon reader, `cache.py`, `content.py`, window mode toggle, one read-only Home column per Mastodon profile, polling every 60 s | Reading works, nothing interactive |
| 2 | Status row complete (media, polls, CW, link cards), notifications and messages tabs, read markers, unread counts in the sidebar; **Bluesky Home and Notifications** (`reader/bluesky.py`, facets, labels, polling) | Full read-only deck for both networks |
| 3 | Interaction: favourite/like, boost/repost, bookmark, reply and quote sheet, quick post, follow/unfollow from a profile popover, mute/block | Daily usable |
| 4 | Streaming, lists, followed hashtags, bookmarks, "open as column", column setup page, keyboard navigation (J/K, R, F, B) | Power use |
| 5 | Narrow layout polish, content filters, per-column options, accessibility pass, README and screenshots | 0.4.0 |
| 6 (optional) | Bluesky chats (app password with chat access), desktop notifications from the background service, Bluesky OAuth | after 0.4.0 |

Estimate: phases 1 to 3 are the bulk (~60 % of the work); status rendering
(`content.py`, media grid, polls) is the part most likely to take longer than
planned.

## Risks

- **Scope creep.** A reader is a second app. Mitigation: the phase pauses, and
  the cut line "read, reply, favourite, boost, bookmark" for 0.4.0. No
  search, no profile pages, no admin features.
- **Attention on a metered background service.** Streaming runs only while
  the window is open until phase 6.
- **HTML rendering** without a WebView will not be pixel-perfect; unusual
  markup falls back to plain text with an "open in browser" link.
- **Instance rate limits** (300 requests / 5 min): one stream per profile and
  a shared cache keep a deck of 4 profiles far below it.
- **Bluesky polling** is less timely than Mastodon streaming and costs
  requests; the interval is configurable and pauses while the window is hidden.
- **Two networks, one post model:** features that exist on one side only
  (polls, labels, quotes) must degrade cleanly instead of bloating the model.
- **Positioning:** the tagline "Write once, post everywhere" needs a second
  half, for example "…and read it all in one deck."

## Decisions on the former open questions (2026-11-11)

1. **Messages** are direct conversations only. Mentions are a filter
   (*All | Mentions*) at the top of the Notifications tab, as in the official
   Mastodon and Bluesky apps.
2. **Pop-out columns** into separate windows: later, not in 0.4.0.
3. **Bluesky chats** use an app password with chat access first (phase 6).
   Bluesky OAuth stays a separate backlog item; the reader talks to a small
   auth interface so the switch does not touch the columns.
