# Backlog

As of 2026-10-03, version 0.2.2. Shipped changes are in
[CHANGELOG.md](CHANGELOG.md).

## Release

- [ ] **Upload the AUR package.** PKGBUILD and `.SRCINFO` for 0.2.2 are ready
      in `build-aux/arch/` (checksum filled in).
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

## Features

- [ ] **UI redesign** after [docs/ui-redesign.md](docs/ui-redesign.md): sidebar
      archive, editor surface, growing preview, calendar page. Phases 1–5,
      each reviewed before the next.
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

- [x] Phases 1 to 8 of the original brief (v0.1.0)
- [x] CHANGELOG created (v0.2.0)
- [x] Thread splitting for Mastodon, Bluesky and X (v0.2.0)
- [x] Server-side scheduling on Mastodon (v0.2.0)
- [x] Calendar view and time slots per role (v0.2.0)
- [x] Flatpak release manifest and shareable bundle with translations (v0.2.1)
- [x] New icon "halo" (v0.2.1)
- [x] Leaner writing assistant: little reasoning effort, smaller images (v0.2.2)
- [x] GitHub releases v0.1.0, v0.2.0, v0.2.1 and v0.2.2 (0.2.x with Flatpak bundle)
