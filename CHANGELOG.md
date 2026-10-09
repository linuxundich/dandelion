# Changelog

All notable changes to Dandelion are listed here.

## [Unreleased]

### Changed

- **New window layout with a sidebar** (UI redesign, phase 1): drafts,
  scheduled and published posts and the calendar now sit in one sidebar at
  full window height, grouped by state. The view switcher at the top and the
  separate drafts panel are gone. Right-click an entry for its actions
  (change time, pause, send now, duplicate, delete, use as new draft).
- **Search** (Ctrl+F) looks through drafts, scheduled and published posts at
  once.
- **The editor is a plain writing surface** (phase 2): no card, the text
  column stays centered and readable on wide windows, and an empty post shows
  "What's new?". The variant tabs mark platforms with their own text with a
  dot.
- **Leaner toolbar:** images, emoji, content warning, thread and assistant are
  icon buttons. Language, signature, Mastodon visibility and the Bluesky label
  moved into an options popover, grouped by platform; its button shows the
  current language and visibility.
- **New screenshots** in README and AppStream metadata.
- **Character count as a ring** with the remaining characters of the strictest
  profile.
- **The preview grows with the window** (phase 3) and shows its tiles in two
  columns from about 640 px. Below roughly 1100 px window width it is hidden
  and slides in over the editor when needed. Its header sums up how many
  profiles are ready; the row of profile chips with counters is gone, and a
  tile shows a character count only when that profile is over its limit.
- **Compact preview** is now a switch under Preferences › General instead of
  a toggle in the preview.
- **Calendar page** (phase 4): the month fills the window and shows published
  posts (dimmed, with a check mark) next to scheduled ones, plus the free time
  slots of the roles as dashed entries. Month navigation sits in the header
  bar, role and platform filters in a popover. Clicking a published post opens
  its detail page. In narrow windows the month shrinks to dots and the posts of
  the selected day are listed below. The separate list view is gone.
- **F9** now shows or hides the preview; Ctrl+2 opens the calendar.

### Added

- **Drag a draft from the sidebar onto a calendar day** to schedule it. The
  schedule dialog opens with that day and the role's free slot on it (or 9:00)
  preselected.
- **Emoji button** in the toolbar.
- **Detail page for published posts** with the text, images and one row per
  profile to open, copy, delete or retry.

- **Word limit for AI alt text**, 20 words by default, adjustable (0 = no
  limit) under Preferences › AI. The prompt asks for it, and longer answers are
  cut at a word boundary.
- **OpenRouter** as a fourth AI provider next to Gemini, OpenAI and xAI: one
  key for many models. The model list only shows models that accept images.
- **Alt text chat:** after a suggestion from Gemini, OpenAI or Grok you can ask
  for changes ("shorter", "mention the cable") and get a revised suggestion.
  The "Describe Image" button is always shown; without an API key it explains
  how to turn the assistant on.
- **Drag and drop** of images and videos from the file manager works anywhere
  in the composer, not only at the edge of the editor.

### Fixed

- In narrow windows the preview bar no longer covers the editor toolbar.
- The header shows "Draft" instead of "New Post" as soon as a new post is
  saved for the first time.
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
