# Changelog

All notable changes to Dandelion are listed here.

## [Unreleased]

### Added

- **Alt text chat:** after a suggestion from Gemini, OpenAI or Grok you can ask
  for changes ("shorter", "mention the cable") and get a revised suggestion.
  The "Describe Image" button is always shown; without an API key it explains
  how to turn the assistant on.
- **Drag and drop** of images and videos from the file manager works anywhere
  in the composer, not only at the edge of the editor.

### Fixed

- The image preview in the alt text dialog and in the platform previews was
  blank for some files (for example WebP).

## 0.2.2 – 2026-10-03

### Changed

- **Writing assistant uses fewer tokens:** rephrasing, translating, adapting,
  hashtags and alt text ask Gemini and OpenAI for low reasoning effort, since
  thinking tokens are billed like output. A model that rejects the setting gets
  the same request again without it, and no longer receives it until restart.
- Images for alt text are always scaled down to at most 1600 pixels, not only
  files above 1.5 MB.

### Fixed

- Gemini thought summaries no longer end up in the suggestion.

## 0.2.1 – 2026-10-02

### Changed

- **New icon:** the seeds now fly away from the centre of the dandelion like rays,
  with dotted flight trails. The symbolic icon on the welcome page follows the same
  idea with three extended rays.

### Added

- Flatpak manifest for release builds (`de.linuxundich.Dandelion.release.json`)
  and a shareable single-file bundle; translations are included in the bundle.

## 0.2.0 – 2026-10-02

### Added

- **Threads:** long posts can be split into a thread on Mastodon, Bluesky and X.
  Breaks happen at paragraphs, then sentences, then words; URLs are never cut.
  A line with only `---` sets a break by hand. Numbering (`1/3`, `🧵 1/3` or none)
  is configurable. The preview shows all parts; a failed thread resumes at the
  missing part instead of posting again from the start.
- **Scheduling on the server (Mastodon):** per profile, scheduled posts can be
  handed to the Mastodon server right away so they appear even when the computer
  is off. Changes, rescheduling, pausing and deleting are synchronised; threads
  and posts less than five minutes ahead stay local. If the server refuses,
  Dandelion sends the post itself.
- **Calendar view** for scheduled posts with month navigation. Posts can be moved
  to another day by drag and drop; narrow windows show dots per day.
- **Time slots per role**, for example every Monday at 08:00. The schedule dialog
  offers the next free slot, and “In Next Free Slot” schedules with one click.

### Fixed

- On narrow windows the view switcher moved back to the bottom bar.

## 0.1.0 – 2026-10-02

First release.

- Mastodon, Bluesky, LinkedIn, Facebook pages and X
- Roles, several accounts per network, own wording per network or profile
- Exact character counters, previews, alt text checks
- Scheduled posts with a background service (systemd timer or Background portal)
- Optional writing assistant with Google Gemini, OpenAI or xAI
