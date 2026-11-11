# Backlog

As of 2026-10-09, version 0.3.1. Shipped changes are in
[CHANGELOG.md](CHANGELOG.md).

## Release

- [ ] **Upload the AUR package.** PKGBUILD for 0.3.1 is in `build-aux/arch/`;
      fill in the checksum of the GitHub tarball after pushing the tag.
- [ ] **Submit to Flathub** (optional). The release manifest
      `build-aux/flatpak/de.linuxundich.Dandelion.release.json` builds from the
      Git tag. Still missing: verification via
      `linuxundich.de/.well-known/org.flathub.VerifiedApps.txt` and the pull
      request at Flathub.

## Testing with real accounts (done by the maintainer)

- [ ] Sign in to Mastodon and Bluesky and send a real post, also as a thread
      and scheduled on the Mastodon server.
- [ ] Create a developer app each for LinkedIn, Facebook and X and test the
      login.
- [ ] Try the writing assistant with a real API key.

## Deck (multi-column reader)

Concept and phases in [docs/deck-columns.md](docs/deck-columns.md).

- [x] Phase 1: read scope, `Reader` interface, Mastodon home column per profile,
      cache, Write | Read switch, polling every 60 s
- [x] Phase 2: media, polls, link cards; notifications and messages tabs; read
      markers and unread counts; Bluesky home and notifications
- [x] Phase 3: favourite, boost, bookmark, reply and quote sheet, quick post,
      follow, mute, block
- [x] Phase 4: streaming, lists, hashtags, "open as column", column setup page,
      keyboard navigation
- [x] Phase 5: narrow layout, filters, accessibility pass, German translation, 0.4.0 prepared
- [ ] Narrow layout seen at 400 px only; try 360 px and a very short window
- [ ] Screenshots: narrow deck and dark style of the deck
- [ ] Screen reader pass with Orca (labels are set, never listened to)
- [ ] Replace the `Gtk.ListBox` in the feed lists by a `Gtk.ListView` if long
      lists or many images feel slow
- [ ] Cap the image cache folder (avatars and previews grow without limit)
- [ ] Open images in a viewer instead of the browser
- [ ] Show the thread context of replies
- [ ] Streaming for lists and hashtags (own streams while their column is visible)
- [ ] Remove deleted posts from an open list when the stream reports a deletion
- [ ] Column widths and switching a column's feed in place (only own columns for now)
- [ ] Check the Mastodon stream and the Bluesky list calls against real servers (only
      a local WebSocket and fakes so far)
- [ ] Reply from the Messages tab (conversations) and mark them read
- [ ] Mastodon quotes (Mastodon 4.5 `quoted_status_id`) once servers support them
- [ ] Attach images to a quick post (use the full composer for now)
- [ ] Check the Bluesky bookmark, like and graph calls against a real account
      (written from the API description, tested with fakes only)

## Features

- [ ] **Videos** for Bluesky, X, LinkedIn and Facebook. So far videos only go
      to Mastodon.
- [ ] **Bluesky OAuth** as an alternative to the app password, with the
      metadata file on linuxundich.de.
- [ ] **Server-side scheduling on Facebook** (optional; Mastodon is done).
- [ ] **Small things:**
  - [ ] Prefill alt text from the image metadata (EXIF)
  - [ ] Make X Premium with up to 25,000 characters configurable
  - [ ] Bump the LinkedIn API version about once a year

## Done

- [x] UI redesign after [docs/ui-redesign.md](docs/ui-redesign.md): sidebar
      archive, editor surface, growing preview, calendar page (v0.3.0)
- [x] Phases 1 to 8 of the original brief (v0.1.0)
- [x] CHANGELOG created (v0.2.0)
- [x] Thread splitting for Mastodon, Bluesky and X (v0.2.0)
- [x] Server-side scheduling on Mastodon (v0.2.0)
- [x] Calendar view and time slots per role (v0.2.0)
- [x] Flatpak release manifest and shareable bundle with translations (v0.2.1)
- [x] New icon "halo" (v0.2.1)
- [x] Leaner writing assistant: little reasoning effort, smaller images (v0.2.2)
- [x] GitHub releases v0.1.0, v0.2.0, v0.2.1 and v0.2.2 (0.2.x with Flatpak bundle)
