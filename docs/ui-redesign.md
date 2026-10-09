# UI redesign: sidebar archive, editor surface, growing preview

As of 2026-10-09 · Dandelion 0.2.2 · GTK 4.24 / libadwaita 1.10 locally,
Flatpak runtime GNOME 50 (libadwaita 1.9). Supersedes the proportions in
[layout-redesign.md](layout-redesign.md).

## Findings

Measured on the blueprints and a screenshot of a 1918 px wide window:

| Area | Width | Limit |
|---|---|---|
| Drafts sidebar | 320 | `max-sidebar-width: 320` |
| empty | 230 | |
| Editor card | 760 | `Adw.Clamp maximum-size: 760` |
| empty | 230 | |
| Preview | 380 | `max-sidebar-width: 380` |

1. **The content does not grow with the window.** 460 px (24 %) stay empty;
   every column has a hard maximum, so a larger window only adds margin.
2. **Two header bars on top of each other.** The drafts sidebar lives inside
   the composer page, below the window header bar, and has its own header.
   The HIG puts a sidebar at full height with a split header.
3. **The drafts toggle sits in the window header but only works on
   "Compose".** It does nothing on "Scheduled" and "Published".
4. **Empty text field without a placeholder.** The media tile sits at the
   bottom of the card, about 650 px below the cursor.
5. **The toolbar mixes scopes.** Language applies to all profiles, visibility
   only to Mastodon, the content label only to Bluesky. Seven labelled
   controls wrap below 900 px.
6. **The character count appears three times** (toolbar, status strip,
   every preview tile); the status strip repeats the profile chips.
7. **Card inside a card.** Editor and preview tiles are both cards on grey,
   equally weighted.
8. **Variant tabs** are a flat ToggleGroup; it is not visible which platform
   has its own text.

## Decisions (2026-10-09)

| Question | Decision |
|---|---|
| Model | **A – archive in the sidebar** (mail client model) |
| Editor | **Surface**, no card |
| Preview | Open by default from **1100 sp**, below that via button or F9 |
| Calendar | **Page in the content area**, not a dialog |

Rejected: B (view switcher stays, drafts in a header popover) and C (one
preview column per profile). C's per-profile columns may come back later as
a layout for very wide windows.

## Target layout

```
┌ Sidebar (full height) ─┬ Content ──────────────────────────────────────────┐
│ [✎]  Dandelion  [⌕][☰] │        Draft · Private · saved 10:14   [▣][Publish▾][☰] │
│ 📅 Calendar            │ From 🏠 Private ▾  to (● @toff…) (● @chris…) (+)  │ Preview  ✓ 2 ready │
│ DRAFTS              3  │ [Shared | Mastodon | Bluesky•]                    │ ┌──────────────┐  │
│ ▸ Endlich 2,5 GbE …    │                                                   │ │ tile         │  │
│   Fernhilfe 1.5.0 …    │ Text directly on the view surface, ≤ 72 chars     │ └──────────────┘  │
│ SCHEDULED           2  │                                                   │ ┌──────────────┐  │
│   Pulsgeber 0.4.1 Fr 9 │ [img][img][+]                                     │ │ tile         │  │
│ PUBLISHED         128  │ 🖼 ☺ ⚠ ≡ ★              [⚙ Options · Deutsch] (100) │ └──────────────┘  │
│   Gnomos …             │                                                   │                    │
│   Show all 128         │                                                   │                    │
└────────────────────────┴───────────────────────────────────────────────────┴────────────────────┘
```

### Window shell

- `Adw.NavigationSplitView` at the window root, sidebar 260–300 sp. It
  collapses below 860 sp: list and content become two navigation pages.
- The sidebar is an `Adw.Sidebar` (libadwaita 1.9) with the sections
  *Calendar* (single item), *Drafts*, *Scheduled*, *Published* (latest 5 plus
  "Show all"). Items show role emoji, first line, role and time; platform
  dots as suffix.
- Sidebar header: New Post, search (filters all sections), main menu.
- `Adw.ViewSwitcher`, `Adw.ViewSwitcherBar` and the composer's inner
  `OverlaySplitView` for drafts are removed.
- Context menus on items via `setup-menu`: for scheduled posts the actions of
  today's row menu (edit, change time, pause/resume, send now, duplicate,
  back to drafts, delete); for drafts duplicate and delete.

### Content pages

| Sidebar item | Content |
|---|---|
| Draft | Composer |
| Scheduled post | Composer with the schedule banner (as today's "Edit") |
| Published post | Read-only detail: text, media, one row per platform with open / copy link / delete / retry, "Use as New Draft" |
| Show all (published) | Searchable list, today's `history` view without the clamp |
| Calendar | Month page, see below |

### Composer

- No `.card`; the text sits on the view surface. `Adw.Clamp` only on the text
  column (about 72 characters, ~760 sp), the surrounding area takes the view
  background.
- Placeholder "What's new?" in the text view.
- "From … to …" line stays (role button with colour edge, profile chips,
  `Adw.WrapBox`).
- Variants: `Adw.InlineViewSwitcher` "Shared · Mastodon · Bluesky"; a dot
  marks platforms with their own text, a dim caption explains it.
- Attachments directly above the toolbar, 116 px tiles with ALT badge and an
  add tile; drag and drop stays.
- Toolbar with symbolic buttons and tooltips: images, emoji, CW, thread,
  assistant. On the right a button "Options" with a popover grouped by scope:
  *All profiles* (language, signature), then one group per selected
  platform (Mastodon visibility, Bluesky label, …). Platforms without a
  selected profile do not appear.
- One counter: a ring with the remaining characters of the strictest profile.

### Preview

- `Adw.OverlaySplitView` at the end of the content, `sidebar-width-fraction`
  0.36, min 320 sp, **no fixed maximum**; from 640 sp pane width the tiles
  flow into two columns.
- Shown by default from 1100 sp; toggle button in the header and F9.
- Header "Preview" plus a summary ("2 profiles ready" / "1 problem"); the
  status strip goes away. Tiles show a count only when a profile is over its
  limit.
- Compact/full density stays as a setting, no longer as a toggle in the pane.

### Calendar page

- Full month grid in the content area, header with previous/next/today,
  centered title "October 2026" with a summary ("5 scheduled · 4
  published"), role and platform filters on the right.
- Published posts appear dimmed with a check mark; free time slots of the
  roles appear dashed.
- **Drag a draft from the sidebar onto a day** to schedule it. The drop
  opens the schedule dialog with the day and the role's next free slot
  preselected. Moving entries between days stays as today.
- Clicking an entry selects it in the sidebar and opens it.
- Narrow: compact month with dots, list of the selected day below.

### Narrow (< 600 sp)

- Collapsed split view: sidebar list → content page with back button.
- Preview in an `Adw.BottomSheet` (as today), bar shows "Preview · 2 profiles
  ready".
- "Publish" becomes "Send".

## Phases

Each phase ends with a review by the maintainer before the next one starts.

1. **Window shell and sidebar.** *Done 2026-10-09:* `archive.py` fills the
   `Adw.Sidebar`, `post_view.py` is the published detail page; the sidebar
   switches to page mode when collapsed; F9 toggles the preview. Phase 1 kept
   the composer's preview breakpoint at 700 sp and the old list/calendar view
   as the calendar page.
   Originally planned: NavigationSplitView, `Adw.Sidebar` with
   the four sections and context menus, content stack (composer, published
   detail, published list, calendar placeholder). Remove the view switcher
   and the inner drafts split. Settings: drop `drafts-sidebar-visible`,
   map `scheduled-view` to the last selected sidebar item.
2. **Composer surface.** *Done 2026-10-09:* `widgets/counter_ring.py`;
   text column centered by dynamic `left/right-margin` on the GtkSource.View
   (728 px), header and toolbar clamped to the same width; options popover
   uses `Adw.ComboRow`/`Adw.SwitchRow`. Variant tabs stay an
   `Adw.ToggleGroup` (framed), which is what InlineViewSwitcher draws.
   Originally planned: Remove the card, placeholder, InlineViewSwitcher with
   variant dots, attachment row, symbolic toolbar, options popover, counter
   ring.
3. **Preview pane.** *Done 2026-10-09:* fraction 0.4, 320–900 px; composer
   breakpoint at 860 sp collapses it into an overlay of max. 420 px (hidden
   by default), at 700 sp the bottom sheet takes over. Two columns are two
   vertical boxes filled alternately once the pane is 640 px wide. The
   toggle button follows the overlay and the sheet; only the docked state is
   saved as `show-preview`.
   Originally planned: Growing width, two columns, default visibility by
   breakpoint, F9, summary header, drop the status strip.
4. **Calendar page.** *Done 2026-10-09:* `DandelionMonthCalendar` without its
   own header (navigation via `calendar.*` actions in a month row above the
   grid, since 0.3.1 not in the header bar where it clashed with the back button;
   filters in `scheduled.filter_popover`). Dragging out of the sidebar works
   with a `Gtk.DragSource` on the whole `Adw.Sidebar` in the **capture**
   phase (bubble phase never fires, the list claims the pointer) that maps the
   picked widget to an entry through its prefix widget. GSettings key
   `scheduled-view` removed. The filter button uses an own
   `funnel-symbolic` icon from the gresource (Adwaita has none).
   Originally planned: Move `DandelionMonthCalendar` into the content,
   filters in the header, slots, drag source on draft items, drop opens the
   schedule dialog.
5. **Narrow layouts and polish.** *Done 2026-10-09, released as 0.3.0:*
   screenshots come from a headless GNOME session with a seeded copy of the
   database, `DANDELION_OFFLINE=1` and a memory secret store, so no profile
   shows a login error. Widths checked: 420, 900, 1060, 1280 px; 1920 px not
   available in the test session.
   Originally planned: Checks at 360, 600, 860, 1100 and 1920 sp in
   light and dark, keyboard navigation, shortcuts dialog, screenshots in
   README and metainfo, CHANGELOG, release.

## Risks

- **Drag source on sidebar items.** `Adw.Sidebar` offers drop targets
  (`drop`, `drop-enter`) but no API to drag an item out (confirmed in phase 1).
  Idea for phase 4: a `Gtk.DragSource` on the whole sidebar that picks the item
  under the pointer via its prefix widget. If a `Gtk.DragSource`
  cannot be attached to its rows, the sidebar falls back to a `Gtk.ListBox`
  with the `navigation-sidebar` style class, which looks the same.
- **Runtime.** `Adw.Sidebar` needs libadwaita 1.9; the Flatpak runtime is
  GNOME 50, the PKGBUILD must require `libadwaita>=1.9`.
- **Scheduled list features** (filters, pause, send now) move from a full
  page into the sidebar context menu and the calendar; nothing may get lost.
