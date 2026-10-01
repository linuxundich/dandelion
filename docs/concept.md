# Dandelion – Konzept (Phase 2)

Stand: 2026-10-01 · App-ID `de.linuxundich.Dandelion` · Python 3.14 +
PyGObject · GTK 4.22 / libadwaita 1.9 · Lizenz GPL-3.0-or-later

Grundlagen: [platforms.md](platforms.md), [market.md](market.md),
[language.md](language.md).

---

## 1. Leitlinien

1. **Einmal schreiben, überall korrekt.** Zähler, Limits und Validierung bilden
   die Server-Logik exakt nach. Was rot ist, geht nicht raus.
2. **Rollen zuerst.** Die gewählte Rolle bestimmt Profile, Signatur, später
   auch Zeitslots und KI-Tonalität.
3. **Nichts geht verloren.** Autosave, Rückgängig, keine stillen Sendungen nach
   Suspend.
4. **Ehrlich zu Plattformgrenzen.** Kosten (X), Token-Abläufe (LinkedIn,
   Bluesky) und Einschränkungen (Facebook nur Seiten) werden dort erklärt, wo
   man sie braucht: beim Login und im Composer.
5. **GNOME-nativ.** HIG, adaptive Layouts, Tastatur, Hell/Dunkel, Akzentfarbe.

---

## 2. Informationsarchitektur

```
Dandelion (AdwApplicationWindow)
├── Verfassen            ← Startansicht
│   ├── Entwürfe (einblendbare Seitenleiste, F9)
│   ├── Editor: Rolle, Profile, Haupttext, Varianten, Medien, Optionen
│   └── Vorschau: eine Kachel pro gewähltem Profil
├── Geplant              ← Liste nach Tagen gruppiert, Filter Rolle/Plattform
└── Veröffentlicht       ← Verlauf mit Links, Ergebnis pro Profil

Primäres Menü (☰)
├── Neuer Beitrag                 Strg+N
├── Rollen und Profile            → AdwPreferencesDialog, Seite „Rollen“
├── Einstellungen                 Strg+,
├── Tastenkürzel                  Strg+?
└── Info zu Dandelion             → AdwAboutDialog

Dialoge (AdwDialog / AdwAlertDialog)
├── Alt-Text bearbeiten
├── Beitrag planen (Datum, Uhrzeit, Zeitzone)
├── Probleme vor dem Senden (Validierungsliste)
├── Senden: Fortschritt und Ergebnis pro Profil
├── Profil hinzufügen (AdwNavigationView: Plattform → Login → Bestätigung)
├── Verpasste Beiträge
└── Datenschutzhinweis KI (Phase 7)
```

**Navigation:** Drei gleichrangige Ansichten in einem `AdwViewStack`.

- **Breit:** `AdwViewSwitcher` in der Kopfleiste.
- **Schmal (< 550 sp):** `AdwViewSwitcherBar` unten.

Eine Seitenleiste mit `AdwNavigationSplitView` würde die Breite kosten, die der
Composer für Editor und Vorschau braucht. Deshalb ist der View Switcher hier
das bessere Muster (vgl. Uhren, Fragments).

**Begriffe in der UI:**

| Begriff | Bedeutung |
|---|---|
| Beitrag | ein Text mit Medien, der an mehrere Profile geht |
| Rolle | „Privat“, „linuxundich“, „tuxsucht“ … |
| Profil | ein Account auf einer Plattform (auch mehrere pro Plattform) |
| Variante | abweichender Text für eine Plattform (oder ein einzelnes Profil) |
| Ziel | ein Profil innerhalb eines bestimmten Beitrags, mit eigenem Status |

---

## 3. Wireframes

Die Skizzen sind schematisch. `[ ]` steht für Buttons, `( )` für
Toggle-Chips, `▾` für Dropdowns und `★` für die einzige Suggested Action einer
Ansicht.

### 3.1 Composer – breit (≥ 900 sp)

`AdwMultiLayoutView` mit dem Layout „breit“: Editor links, Vorschauspalte
rechts (`AdwOverlaySplitView`, Seitenleiste rechts, Breite 360–420 sp).

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ [▤] [+]          [ Verfassen | Geplant | Veröffentlicht ]     [★ Veröffentlichen ▾] ☰ │
├──────────────────────────────────────────────────┬───────────────────────────────┤
│ Rolle: [🐧 linuxundich ▾]                        │ Vorschau                  [⇔] │
│ ( ●🐘 @toff@social.tchncs.de ) ( ●🦋 @linuxundich.de )│ ┌───────────────────────────┐ │
│ ( ○🐘 @linuxundich@mastodon.social ) [+ Profil]  │ │ (◯) Christoph · @toff@…   │ │
│ ─────────────────────────────────────────────────│ │ Neuer Artikel: GNOME 50 … │ │
│ [ Haupttext | Mastodon | Bluesky ✎ ]             │ │ ┌─────┬─────┐             │ │
│ ┌───────────────────────────────────────────────┐│ │ │ img │ img │             │ │
│ │ Neuer Artikel: GNOME 50 im Test – was sich    ││ │ └─────┴─────┘             │ │
│ │ beim Wechsel von X11 auf Wayland ändert …     ││ │ ┌───────────────────────┐ │ │
│ │ https://linuxundich.de/gnome-50               ││ │ │ linuxundich.de        │ │ │
│ │                                               ││ │ │ GNOME 50 im Test      │ │ │
│ │ #GNOME #Linux                                 ││ │ └───────────────────────┘ │ │
│ └───────────────────────────────────────────────┘│ │ Mastodon · 312/500   ✓    │ │
│ ┌──────┐ ┌──────┐ ┌ ─ ─ ─┐                       │ └───────────────────────────┘ │
│ │ img  │ │ img  │   + Medien                     │ ┌───────────────────────────┐ │
│ │ ALT✓ │ │ALT ✗ │ └ ─ ─ ─┘                       │ │ (◯) linuxundich.de        │ │
│ └──────┘ └──────┘                                │ │ Neuer Artikel: GNOME 50 … │ │
│ ─────────────────────────────────────────────────│ │ … mehr anzeigen           │ │
│ [⚠ CW] [🌐 Deutsch ▾] [👁 Öffentlich ▾] [🧵 Thread]│ │ Bluesky · 312/300  ✗      │ │
│ ─────────────────────────────────────────────────│ └───────────────────────────┘ │
│ 🐘 312/500   🦋 312/300 ✗   [⚠ 2 Probleme]        │                               │
└──────────────────────────────────────────────────┴───────────────────────────────┘
```

- **Kopfleiste:** links `[▤]` blendet die Entwürfe-Seitenleiste ein und aus
  (F9), `[+]` startet einen neuen Beitrag. In der Mitte sitzt der View
  Switcher. Rechts ein `AdwSplitButton` „Veröffentlichen“ (suggested-action)
  mit Menü: „Planen…“ (Strg+Umschalt+Eingabe), „Als Entwurf behalten“.
- **Rollen-Dropdown:** ein Popover nach dem Vorbild von Fractal. Es zeigt
  Emoji bzw. Avatar, Farbe und Name der Rolle, darunter einen Link „Rollen
  verwalten“. Ein Rollenwechsel setzt die Profilauswahl zurück, mit
  Rückgängig-Toast.
- **Profil-Chips:** `GtkToggleButton` mit Avatar, Plattform-Symbol
  (stilisiert, kein Markenlogo) und Handle. Ein Statuspunkt zeigt den
  Verbindungsstatus: grün gültig, gelb läuft bald ab, rot Fehler.
  Accessible-Label: „Profil @toff@social.tchncs.de, Mastodon, ausgewählt“.
- **Varianten:** `AdwToggleGroup` mit „Haupttext“ und einem Eintrag pro
  gewählter Plattform. ✎ markiert eigene Varianten, siehe 3.3.
- **Editor:** `GtkSourceView` (ohne Syntaxhervorhebung) mit libspelling für die
  Rechtschreibprüfung. URLs, Mentions und Hashtags werden dezent per Tag
  hervorgehoben. Zeichen über dem Limit der strengsten gewählten Plattform
  bekommen einen roten Hintergrund-Tag (wie bei X oder Typefully).
- **Medienleiste:** Drag & Drop auf den ganzen Editor, Einfügen mit Strg+V,
  „+ Medien“ öffnet `GtkFileDialog`. Reihenfolge per Drag änderbar.
  Badge `ALT ✓` oder `ALT ✗` (Stil error). Ein Klick öffnet den
  Alt-Text-Dialog (3.4). Das Kontextmenü bietet „Entfernen“ und
  „Alt-Text bearbeiten“.
- **Optionen:**
  - `⚠ CW`: Toggle, blendet per `GtkRevealer` ein Eingabefeld für die
    Inhaltswarnung ein. Wirkt bei Mastodon als `spoiler_text` und bei Bluesky
    als Self-Label-Auswahl.
  - Sprache: Vorbelegung aus der Rolle bzw. Systemsprache.
  - Sichtbarkeit: nur aktiv, wenn ein Mastodon-Profil gewählt ist.
  - `🧵 Thread`: automatisches Aufteilen (Phase 5).
- **Statuszeile:** ein Zähler pro gewähltem Profil.
  - Stilklassen: normal, `warning` ab 90 %, `error` bei Überschreitung.
  - Haben zwei Mastodon-Profile verschiedene Instanzlimits, gibt es zwei
    Zähler.
  - `[⚠ 2 Probleme]` öffnet ein Popover mit der Validierungsliste (3.5).
- **Vorschau:**
  - Eine Kachel pro gewähltem Profil, in einer scrollbaren Spalte.
  - `[⇔]` blendet die Spalte aus (Strg+Umschalt+P).
  - Die Kachel zeigt stilisiert die Kürzung und „… mehr anzeigen“ der
    jeweiligen Plattform, das Bildraster (2×2, 1+2 …), die Link-Card und die
    Inhaltswarnung.

### 3.2 Composer – schmal (360–899 sp)

Das Layout „schmal“ der `AdwMultiLayoutView` legt die Vorschau in ein
`AdwBottomSheet`. Im eingeklappten Zustand zeigt die Bottom Bar die
Zählerzeile.

```
┌────────────────────────────────┐      ┌────────────────────────────────┐
│ [▤]   Verfassen   [★ Senden ▾] ☰│      │ [▤]   Verfassen   [★ Senden ▾] ☰│
├────────────────────────────────┤      ├────────────────────────────────┤
│ [🐧 linuxundich ▾]             │      │ (Editor abgedunkelt)           │
│ (●🐘 toff) (●🦋 lui) (○🐘 lui) ›│      ├──────────── ─── ───────────────┤
│ [ Haupttext | 🐘 | 🦋✎ ]       │      │ Vorschau                       │
│ ┌────────────────────────────┐ │      │ ┌────────────────────────────┐ │
│ │ Neuer Artikel: GNOME 50 im │ │      │ │ (◯) Christoph · @toff      │ │
│ │ Test – was sich beim …     │ │      │ │ Neuer Artikel: GNOME 50 …  │ │
│ │                            │ │      │ │ ┌──────┬──────┐            │ │
│ └────────────────────────────┘ │      │ │ │ img  │ img  │            │ │
│ [img ✓][img ✗][+]              │      │ │ └──────┴──────┘            │ │
│ [⚠][🌐▾][👁▾][🧵]               │      │ └────────────────────────────┘ │
├──────────── ─── ───────────────┤      │ ┌────────────────────────────┐ │
│ 🐘 312/500  🦋 312/300 ✗   ⌃   │      │ │ (◯) linuxundich.de  …      │ │
├────────────────────────────────┤      │ └────────────────────────────┘ │
│ [✎ Verfassen][🕓 Geplant][✓ …] │      └────────────────────────────────┘
└────────────────────────────────┘        Bottom Sheet aufgezogen
```

- Die Profil-Chips scrollen horizontal (`GtkScrolledWindow`, nur horizontal).
- Unter 400 sp zeigen die Chips nur noch Avatar und Plattform-Symbol, das
  Handle steht im Tooltip und im Accessible-Label.
- Der Button heißt kurz „Senden“. Das Label wechselt per `AdwBreakpoint`.

### 3.3 Varianten

```
[ Haupttext | Mastodon | Bluesky ✎ ]
┌──────────────────────────────────────────────────────────┐
│ ⓘ Bluesky verwendet eine eigene Fassung.  [Haupttext übernehmen] │  ← AdwBanner
├──────────────────────────────────────────────────────────┤
│ GNOME 50 im Test: Wayland-only, neue Einstellungen …     │
│ https://linuxundich.de/gnome-50                          │
└──────────────────────────────────────────────────────────┘
```

- Ohne eigene Variante zeigt der Plattform-Tab den geerbten Text read-only und
  ausgegraut, dazu den Button **„Für Bluesky anpassen“**. Ein Klick kopiert den
  Haupttext in die Variante.
- „Haupttext übernehmen“ verwirft die Variante, mit Rückgängig-Toast.
- Wird der Haupttext geändert, während eine Variante existiert, erscheint am
  Tab ein Hinweispunkt („Haupttext wurde seitdem geändert“).
- Varianten gelten für eine **Plattform**. Bei zwei Profilen derselben
  Plattform lässt sich zusätzlich eine **Profil-Variante** anlegen
  (Kontextmenü am Chip: „Eigene Fassung für dieses Profil“).

### 3.4 Alt-Text-Dialog (AdwDialog)

```
┌──────────────────────────────────────────────┐
│ [Abbrechen]      Alt-Text        [★ Fertig]  │
├──────────────────────────────────────────────┤
│        ┌──────────────────────────┐          │
│        │                          │          │
│        │          Bild            │          │
│        │                          │          │
│        └──────────────────────────┘          │
│  Beschreibe das Bild für Menschen, die es    │
│  nicht sehen können.                         │
│ ┌──────────────────────────────────────────┐ │
│ │ Screenshot der GNOME-50-Einstellungen …  │ │
│ └──────────────────────────────────────────┘ │
│ 142 / 1000 (X ist das strengste Limit)       │
│ ⓘ Seitenverhältnis 4:5 – Bluesky schneidet   │
│   in der Vorschau oben und unten ab.         │
│ [✦ Aus Bild erzeugen]   ← Phase 7, nur bei KI an │
└──────────────────────────────────────────────┘
```

- Vorbefüllung aus EXIF/XMP (`ImageDescription`, `dc:description`), wie bei
  Tuba.
- „Fertig“ ist auch mit leerem Text möglich. Das Badge bleibt dann `ALT ✗` und
  die Validierung blockiert.
- Strg+Eingabe schließt den Dialog mit „Fertig“.

### 3.5 Validierung vor dem Senden

Die Probleme sind dauerhaft im Popover `[⚠ n Probleme]` sichtbar. Bei Fehlern
ist „Veröffentlichen“ deaktiviert, der Tooltip nennt den Grund. Liegen nur
Warnungen vor, erscheint beim Senden ein AdwAlertDialog:

```
┌────────────────────────────────────────────┐
│          Trotz Warnungen senden?           │
│                                            │
│  Bluesky · @linuxundich.de                 │
│   ⚠ Kein Link-Vorschaubild gefunden        │
│  Mastodon · @toff@social.tchncs.de         │
│   ⚠ Kein Hashtag gesetzt                   │
│                                            │
│   [Abbrechen]         [★ Trotzdem senden]  │
└────────────────────────────────────────────┘
```

| Prüfung | Stufe |
|---|---|
| Text zu lang (pro Profil, korrekte Zählweise) | Fehler |
| Text leer und keine Medien | Fehler |
| Alt-Text fehlt (Mastodon immer, andere je nach Einstellung) | Fehler |
| Alt-Text zu lang für eine Plattform | Fehler |
| Zu viele oder unzulässige Medien (Anzahl, Format, Größe, Mischung) | Fehler |
| Profil abgemeldet oder Token abgelaufen | Fehler |
| Bluesky-Bytes > 3000, Facets nicht auflösbar | Fehler |
| Seitenverhältnis wird beschnitten | Warnung |
| Thread-Teil fast leer, Link ohne Vorschau | Warnung |
| X: Kosten des Beitrags (z. B. 0,20 $ wegen Link) | Hinweis |

### 3.6 Senden und Ergebnis (AdwDialog)

```
┌──────────────────────────────────────────────┐
│                 Senden          [Schließen]  │
├──────────────────────────────────────────────┤
│ ✓ Mastodon · @toff@social.tchncs.de          │
│   Veröffentlicht                    [↗ Öffnen] │
│ ◌ Bluesky · @linuxundich.de                  │
│   Lädt Bild 2 von 2 hoch …   (AdwSpinner)    │
│ ✗ Mastodon · @linuxundich@mastodon.social    │
│   Der Server ist nicht erreichbar.           │
│   [Erneut versuchen]                         │
└──────────────────────────────────────────────┘
```

- Alle Ziele laufen parallel (asyncio). Der Dialog lässt sich jederzeit
  schließen, das Senden läuft weiter. Am Ende kommt ein Toast „Veröffentlicht
  auf 2 von 3 Profilen“ mit der Aktion „Details“.
- Fehlgeschlagene Ziele bleiben im Verlauf als „Teilweise fehlgeschlagen“ und
  lassen sich dort einzeln wiederholen.
- Fehlermeldungen sind verständlich formuliert, technische Details stehen in
  einem einklappbaren Bereich („Technische Details“, ohne Tokens).

### 3.7 Beitrag planen (AdwDialog)

```
┌──────────────────────────────────────────────┐
│ [Abbrechen]   Beitrag planen    [★ Planen]   │
├──────────────────────────────────────────────┤
│ [Heute 18:00] [Morgen 08:00] [Mo 08:00]      │  ← Presets (Errands)
│ [Nächster Slot der Rolle]   ← später         │
│ ┌──────────────────────────────────────────┐ │
│ │        GtkCalendar (Oktober 2026)        │ │
│ └──────────────────────────────────────────┘ │
│  Uhrzeit            [ 08 ]:[ 00 ]            │  ← zwei AdwSpinRows
│  Zeitzone           Europe/Berlin ▾          │  ← AdwComboRow mit Suche
│  ⓘ Dandelion sendet auch bei geschlossenem   │
│    Fenster, solange du angemeldet bist.      │
└──────────────────────────────────────────────┘
```

- Zeitpunkte in der Vergangenheit sind gesperrt, die Fehlermeldung steht inline.
- Ist der Hintergrunddienst nicht aktiv (z. B. Background-Portal abgelehnt),
  warnt ein `AdwBanner` mit der Aktion „Aktivieren“.

### 3.8 Geplant

```
┌──────────────────────────────────────────────────────────────────┐
│ [+]        [ Verfassen | Geplant | Veröffentlicht ]        [🔍] ☰ │
├──────────────────────────────────────────────────────────────────┤
│ [Alle Rollen ▾] [Alle Plattformen ▾]                             │
│                                                                  │
│ Heute                                                            │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ 18:00  🐧 linuxundich  🐘🦋                               [⋮] │ │
│ │ Neuer Artikel: GNOME 50 im Test – was sich beim …            │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ 21:30  🏠 Privat  🐘   ⏸ Pausiert                         [⋮] │ │
│ │ Heute Abend Tatort mit …                                     │ │
│ └──────────────────────────────────────────────────────────────┘ │
│ Morgen, Donnerstag 2. Oktober                                    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ 08:00  🐧 tuxsucht  🐘🦋💼                                [⋮] │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
 [⋮] → Bearbeiten · Zeit ändern… · Pausieren/Fortsetzen · Jetzt senden
       · Duplizieren · ──── · Löschen (destructive)
```

- `GtkListView` mit Sektionen (`GtkSectionModel`), Zeilen im Stil von
  `AdwActionRow` mit Rollenfarbe als schmalem Rand links.
- **Bearbeiten** lädt den Beitrag in den Composer. Ein `AdwBanner` zeigt dann
  „Geplanter Beitrag · Do 08:00“ mit dem Button „Planung aufheben“.
  Änderungen werden automatisch gespeichert.
- **Löschen** zeigt einen Rückgängig-Toast (10 s). Endgültig gelöscht wird erst
  nach Ablauf. Bei einem serverseitig geplanten Mastodon-Beitrag wird dann
  zusätzlich `cancel_scheduled` aufgerufen.
- **Jetzt senden** fragt per AdwAlertDialog nach.
- Leerzustand: `AdwStatusPage` mit Kalender-Symbol, „Nichts geplant“, Button
  „Beitrag verfassen“.
- Eine Kalenderansicht (Monat/Woche) folgt später, siehe market.md.

### 3.9 Veröffentlicht (Verlauf)

```
┌──────────────────────────────────────────────────────────────────┐
│ [+]        [ Verfassen | Geplant | Veröffentlicht ]        [🔍] ☰ │
├──────────────────────────────────────────────────────────────────┤
│ [Alle Rollen ▾] [Alle Plattformen ▾] [Nur Fehler ◻]              │
│ Heute                                                            │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ ▸ 09:12  🐧 linuxundich   ✓ 2   ✗ 1                         │ │  ← AdwExpanderRow
│ │   Neuer Artikel: GNOME 50 im Test …                          │ │
│ │   ├ 🐘 @toff@social.tchncs.de   ✓  [↗] [⋮]                    │ │
│ │   ├ 🦋 @linuxundich.de          ✓  [↗] [⋮]                    │ │
│ │   └ 🐘 @lui@mastodon.social     ✗ Zeitüberschreitung [Erneut] │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
 [⋮] pro Ziel → Link kopieren · Auf Plattform löschen… (AdwAlertDialog, destructive)
 [⋮] pro Beitrag → Als neuen Entwurf verwenden · Aus Verlauf entfernen
```

- Suche (Strg+F) über `GtkSearchBar` im Volltext (SQLite FTS5).
- Leerzustand: `AdwStatusPage` „Noch nichts veröffentlicht“.

### 3.10 Rollen und Profile (AdwPreferencesDialog)

Seite **Rollen**:

```
┌──────────────────────────────────────────────────────────┐
│        [ Rollen | Allgemein | Planung | KI ]          ✕  │
├──────────────────────────────────────────────────────────┤
│  Rollen                                                  │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ ⠿ 🏠 Privat              2 Profile                  › │ │
│ │ ⠿ 🐧 linuxundich         3 Profile                  › │ │
│ │ ⠿ 🔍 tuxsucht            2 Profile                  › │ │
│ ├──────────────────────────────────────────────────────┤ │
│ │                  + Rolle hinzufügen                  │ │  ← AdwButtonRow
│ └──────────────────────────────────────────────────────┘ │
│  Alle Profile                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ (◯) 🐘 @toff@social.tchncs.de       ● Verbunden     › │ │
│ │ (◯) 🦋 @linuxundich.de              ● Läuft in 3 T. ab› │ │
│ │ (◯) 💼 Christoph Langner            ● Abgemeldet    › │ │
│ ├──────────────────────────────────────────────────────┤ │
│ │                 + Profil hinzufügen                  │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

- Rollen werden per Drag-Handle `⠿` sortiert, alternativ per Tastatur mit
  Alt+↑/↓ und den Kontextmenü-Einträgen „Nach oben“ und „Nach unten“.

**Unterseite Rolle** (`AdwPreferencesDialog.push_subpage`):

```
 ‹  linuxundich
  Darstellung
   Name                     [linuxundich          ]   ← AdwEntryRow
   Symbol                   🐧  [Emoji wählen]         ← GtkEmojiChooser
   Farbe                    ● ● ● ● ● ● ● ● ●          ← GNOME-Palette, Akzent-Chips
   Bild                     [Bild wählen…]             ← optional statt Emoji
  Profile
   ☑ 🐘 @toff@social.tchncs.de     Standardmäßig ausgewählt  [⏻]
   ☑ 🦋 @linuxundich.de            Standardmäßig ausgewählt  [⏻]
   ☐ 🐘 @lui@mastodon.social       nicht in dieser Rolle
  Voreinstellungen
   Sprache                  Deutsch ▾
   Sichtbarkeit (Mastodon)  Öffentlich ▾
   Signatur                 [#linux #gnome           ]   ← angehängt, abwählbar im Composer
   Stil für KI              [Locker, duzt, …         ]   ← Phase 7
  ────
   [ Rolle löschen ]  (destructive, AdwAlertDialog)
```

- Ein Profil kann in **mehreren** Rollen sein (n:m). Pro Zuordnung gibt es den
  Schalter „Standardmäßig ausgewählt“.

**Unterseite Profil:**

```
 ‹  @toff@social.tchncs.de
   (◯ Avatar)  Christoph · Mastodon · social.tchncs.de
  Status      ● Verbunden · Limit 500 Zeichen · 4 Bilder
              [Erneut anmelden]  [Limits aktualisieren]
  Anzeige     Anzeigename in Dandelion  [Toff (tchncs)]
  Optionen    Serverseitig planen, wenn möglich  [⏻]   ← Mastodon/Facebook, Phase 5
  ────
   [ Profil entfernen ] (destructive: löscht Tokens aus dem Schlüsselbund)
```

**Profil hinzufügen** (AdwDialog mit `AdwNavigationView`):

```
 1 Plattform wählen          2 Anmelden (Mastodon)            3 Fertig
 ┌────────────────────┐      ┌─────────────────────────────┐  ┌─────────────────────┐
 │ 🐘 Mastodon      › │      │ Instanz                     │  │ (◯) @toff@…         │
 │ 🦋 Bluesky       › │  →   │ [social.tchncs.de        ]  │→ │ Zu Rollen hinzufügen│
 │ 💼 LinkedIn      › │      │ [★ Im Browser anmelden]     │  │ ☑ linuxundich       │
 │ 📘 Facebook-Seite› │      │ Warte auf Browser … (Spinner)│  │ ☐ Privat            │
 │ ✕ X              › │      │ ▸ Code manuell eingeben     │  │ [★ Fertig]          │
 └────────────────────┘      └─────────────────────────────┘  └─────────────────────┘
```

- **Mastodon:** Instanz eingeben, App wird dynamisch registriert. Login im
  Systembrowser über `Gtk.UriLauncher` (Portal OpenURI), Loopback-Redirect
  auf 127.0.0.1 mit zufälligem Port. Fallback ist die manuelle Code-Eingabe.
- **Bluesky:** Handle und **App-Passwort** (`AdwPasswordEntryRow`, Standard),
  mit Link „App-Passwort in Bluesky erstellen“. Darunter optional „Stattdessen
  im Browser anmelden (OAuth)“, mit dem Hinweis „Sitzung muss alle 14 Tage
  erneuert werden“.
- **LinkedIn, Facebook, X (Phase 6):** Erst eine Erklärseite, was die Plattform
  erlaubt, mit einer Anleitung zur eigenen Developer-App. Dann
  `AdwEntryRow`/`AdwPasswordEntryRow` für Client-ID und Secret (Secret direkt
  in libsecret), dann der Login. Bei X zusätzlich der Kostenhinweis.

### 3.11 Einstellungen (weitere Seiten im AdwPreferencesDialog)

| Seite | Gruppe | Einstellung (Widget) | GSettings-Schlüssel |
|---|---|---|---|
| Allgemein | Verfassen | Alt-Text für alle Plattformen verlangen (SwitchRow) | `require-alt-text-everywhere` |
| | | Rechtschreibprüfung (SwitchRow) | `spellcheck` |
| | | Signatur der Rolle automatisch anhängen (SwitchRow) | `append-signature` |
| | | Vorschau standardmäßig anzeigen (SwitchRow) | `show-preview` |
| | Threads | Nummerierung (ComboRow: aus, „1/n“, „🧵 1/n“) | `thread-numbering` |
| | Entwürfe | Leere Entwürfe nach n Tagen löschen (SpinRow) | `draft-retention-days` |
| Planung | Hintergrunddienst | Status mit Aktion „Aktivieren“ / „Deaktivieren“ | – (systemd/Portal) |
| | | Benachrichtigungen bei Erfolg (SwitchRow) | `notify-success` |
| | | Benachrichtigungen bei Fehler (SwitchRow) | `notify-failure` |
| | Verpasste Beiträge | Verhalten (ComboRow: nachfragen, trotzdem senden, verwerfen) | `missed-policy` |
| | | Toleranz in Minuten (SpinRow, Standard 15) | `missed-grace-minutes` |
| | | Standard-Zeitzone (ComboRow) | `default-timezone` |
| KI (Phase 7) | Allgemein | KI-Funktionen aktivieren (SwitchRow, Standard aus) | `ai-enabled` |
| | Anbieter | Anbieter (ComboRow: Gemini, OpenAI, xAI), Modell (ComboRow), API-Schlüssel (PasswordEntryRow → libsecret) | `ai-provider`, `ai-model-*` |

---

## 4. Tastenkürzel

| Kürzel | Aktion |
|---|---|
| Strg+N | Neuer Beitrag |
| Strg+Eingabe | Veröffentlichen |
| Strg+Umschalt+Eingabe | Planen… |
| Strg+S | Entwurf sofort speichern (sonst Autosave) |
| Strg+Z / Strg+Umschalt+Z | Rückgängig / Wiederholen (auch nach Rollenwechsel und Variante verwerfen) |
| Strg+O | Medien hinzufügen |
| Strg+V | Einfügen, auch Bilder |
| Strg+Umschalt+P | Vorschau ein- und ausblenden |
| Strg+R | Rolle wählen (öffnet das Popover) |
| Strg+1 / 2 / 3 | Verfassen / Geplant / Veröffentlicht |
| Strg+F | Suchen (Geplant, Veröffentlicht) |
| F9 | Entwürfe-Seitenleiste |
| Strg+, | Einstellungen |
| Strg+? | Tastenkürzel |
| Strg+W / Strg+Q | Fenster schließen / Beenden |

Den Shortcuts-Dialog liefert ab libadwaita 1.8 `AdwShortcutsDialog`. Der Dialog
wird aus einer `.blp`-Datei erzeugt.

---

## 5. Architektur

### 5.1 Komponenten

```
                ┌─────────────────────────── dandelion (ein GApplication-Prozess) ───────┐
                │  UI (Blueprint, Widgets)                                               │
                │     │  Signale / Properties                                            │
                │  ViewModels (GObject: ComposerModel, ScheduleModel, HistoryModel)      │
                │     │                                                                  │
                │  core/                                                                 │
                │   ├─ counting.py    (Grapheme, twitter-text v3, URL-/Mention-Regeln)   │
                │   ├─ validation.py  (Issue-Liste aus Draft + Limits)                   │
                │   ├─ splitting.py   (Thread-Aufteilung)                                │
                │   ├─ publisher.py   (parallel senden, Retry, Idempotenz)               │
                │   ├─ scheduler.py   (fällige Beiträge beanspruchen, nächster Termin)   │
                │   ├─ store/         (SQLite, Migrationen, Repositories)                │
                │   └─ secrets.py     (libsecret)                                        │
                │  platforms/  base.py · mastodon.py · bluesky.py · linkedin.py · …      │
                │  auth/       oauth.py (PKCE, Loopback-Server), dpop.py                 │
                │  net/        http.py (libsoup3, User-Agent, Timeouts, Log-Redaktion)   │
                │  ai/         base.py · gemini.py · openai.py · xai.py   (Phase 7)      │
                └────────────────────────────────────────────────────────────────────────┘
```

- `core/`, `platforms/`, `auth/`, `net/` und `ai/` importieren **kein Gtk**
  (nur GLib/Gio, Soup, Secret). Dadurch sind sie in pytest ohne Display
  testbar und auch im Hintergrundmodus verwendbar.
- Plattform-Plugins implementieren das Protokoll `PlatformPlugin` aus
  [platforms.md §7.3](platforms.md). Sie registrieren sich über eine Tabelle
  in `platforms/__init__.py`. Ein neues Netzwerk braucht nur ein neues Modul
  plus Symbol.
- HTTP läuft über **libsoup3** mit dem asyncio-Wrapper. libsoup3 respektiert
  die Proxy-Einstellungen von GNOME und funktioniert im Flatpak ohne Extras.
  Der Logger schwärzt die Header `Authorization`, `DPoP` und `Cookie` sowie die
  Query-Parameter `code`, `access_token` und `client_secret` zentral.

### 5.2 Datenhaltung

| Was | Wo |
|---|---|
| Einstellungen | GSettings `de.linuxundich.Dandelion` |
| Rollen, Profile (ohne Secrets), Beiträge, Ziele, Verlauf | `$XDG_DATA_HOME/dandelion/dandelion.db` (SQLite, WAL) |
| Medien eines Beitrags | `$XDG_DATA_HOME/dandelion/media/<sha256>.<ext>` (Kopie, damit geplante Beiträge nicht von verschobenen Originaldateien abhängen) |
| Avatare, Instanz-Limits, Link-Card-Daten | `$XDG_CACHE_HOME/dandelion/` |
| Tokens, App-Passwörter, Client-Secrets, DPoP-Schlüssel, KI-Keys | libsecret |
| Log | journald (stdout/stderr über systemd bzw. GLib-Log), ohne Secrets |

**libsecret-Schema** `de.linuxundich.Dandelion.Credential`:

| Attribut | Werte |
|---|---|
| `profile` | Profil-UUID oder `ai` |
| `kind` | `oauth` (JSON mit access/refresh/expires/dpop), `app-password`, `client-credentials` (BYO-App), `api-key` |

Das Label ist lesbar, z. B. „Dandelion: Mastodon @toff@social.tchncs.de“, damit
man den Eintrag in Seahorse bzw. Passwörter zuordnen kann.

### 5.3 Datenmodell (SQLite)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (version INTEGER NOT NULL);

CREATE TABLE role (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  emoji         TEXT,
  color         TEXT NOT NULL DEFAULT 'blue',   -- Name aus der GNOME-Palette
  avatar_path   TEXT,
  position      INTEGER NOT NULL,
  language      TEXT,                           -- BCP 47, z. B. 'de'
  visibility    TEXT,                           -- Mastodon-Vorgabe
  signature     TEXT,
  ai_style      TEXT,                           -- Phase 7
  created_at    TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE profile (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,           -- Schlüssel für libsecret
  platform      TEXT NOT NULL,                  -- 'mastodon', 'bluesky', …
  server        TEXT,                           -- Instanz / PDS / NULL
  remote_id     TEXT NOT NULL,                  -- Account-ID bzw. DID
  handle        TEXT NOT NULL,
  display_name  TEXT,
  label         TEXT,                           -- eigener Anzeigename in Dandelion
  avatar_url    TEXT,
  auth_method   TEXT NOT NULL,                  -- 'oauth', 'app-password', 'byo-oauth'
  status        TEXT NOT NULL DEFAULT 'ok',     -- ok | expiring | expired | error
  status_detail TEXT,
  token_expires_at TEXT,
  limits_json   TEXT,                           -- gecachte PlatformLimits
  limits_fetched_at TEXT,
  options_json  TEXT,                           -- z. B. server_scheduling
  created_at    TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (platform, server, remote_id)
);

CREATE TABLE role_profile (                     -- n:m
  role_id       INTEGER NOT NULL REFERENCES role(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
  preselected   INTEGER NOT NULL DEFAULT 1,
  position      INTEGER NOT NULL,
  PRIMARY KEY (role_id, profile_id)
);

CREATE TABLE post (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,
  role_id       INTEGER REFERENCES role(id) ON DELETE SET NULL,
  state         TEXT NOT NULL,
    -- draft | scheduled | paused | sending | published | partial | failed | missed
  body          TEXT NOT NULL DEFAULT '',       -- Haupttext
  content_warning TEXT,
  language      TEXT,
  visibility    TEXT,
  thread_mode   TEXT NOT NULL DEFAULT 'off',    -- off | auto | manual
  scheduled_at  TEXT,                           -- UTC, ISO 8601
  timezone      TEXT,                           -- IANA, für Anzeige und Bearbeitung
  claimed_until TEXT,                           -- Lease gegen Doppelversand
  created_at    TEXT NOT NULL, updated_at TEXT NOT NULL,
  published_at  TEXT,
  deleted_at    TEXT                            -- für Rückgängig-Toast, dann echtes DELETE
);
CREATE INDEX post_due ON post(state, scheduled_at);

CREATE TABLE post_variant (
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  platform      TEXT NOT NULL,
  profile_id    INTEGER REFERENCES profile(id) ON DELETE CASCADE,  -- NULL = gilt für die Plattform
  body          TEXT NOT NULL,
  content_warning TEXT,
  base_hash     TEXT,                           -- Hash des Haupttexts beim Abzweigen
  UNIQUE (post_id, platform, profile_id)
);

CREATE TABLE media (
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  path          TEXT NOT NULL,                  -- Kopie im Datenverzeichnis
  sha256        TEXT NOT NULL,
  mime          TEXT NOT NULL,
  bytes         INTEGER NOT NULL,
  width INTEGER, height INTEGER, duration_s REAL,
  alt_text      TEXT,
  focus_x REAL, focus_y REAL                    -- Mastodon-Fokuspunkt (später)
);

CREATE TABLE post_target (                      -- ein Profil eines Beitrags
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE RESTRICT,
  enabled       INTEGER NOT NULL DEFAULT 1,
  state         TEXT NOT NULL DEFAULT 'pending',
    -- pending | sending | published | failed | deleted | scheduled_remote
  idempotency_key TEXT NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT,                           -- verständlicher Text
  last_error_detail TEXT,                       -- technisch, ohne Secrets
  remote_url    TEXT,                           -- Link auf den ersten Teil
  remote_scheduled_id TEXT,                     -- Mastodon/Facebook serverseitig
  published_at  TEXT,
  UNIQUE (post_id, profile_id)
);

CREATE TABLE post_target_part (                 -- Thread-Teile bzw. Einzelbeitrag
  target_id     INTEGER NOT NULL REFERENCES post_target(id) ON DELETE CASCADE,
  idx           INTEGER NOT NULL,
  remote_id     TEXT,                           -- Status-ID / at-URI / Tweet-ID / URN
  remote_cid    TEXT,                           -- Bluesky
  remote_url    TEXT,
  PRIMARY KEY (target_id, idx)
);

CREATE TABLE media_upload (                     -- Upload-Cache für Retry
  media_id      INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
  remote_ref    TEXT NOT NULL,                  -- Media-ID bzw. Blob-JSON
  uploaded_at   TEXT NOT NULL,
  expires_at    TEXT,
  PRIMARY KEY (media_id, profile_id)
);

CREATE VIRTUAL TABLE post_fts USING fts5(body, content='post', content_rowid='id');
```

Die Zustände eines Beitrags werden aus seinen Zielen abgeleitet: Alle
veröffentlicht ergibt `published`, einige `partial`, keines `failed`.
Thread-Teile entstehen zum Sendezeitpunkt aus Text und Limits. Gespeichert
werden nur die Remote-Referenzen in `post_target_part`. Bricht ein Thread nach
Teil 2 ab, setzt der Retry bei Teil 3 an und antwortet auf Teil 2.

### 5.4 Ablauf beim Senden

```
Publisher.send(post)
 ├─ UPDATE post SET state='sending', claimed_until=now+10min
 │    WHERE id=? AND state IN ('draft','scheduled','missed','partial','failed')
 │    → 0 Zeilen: ein anderer Prozess sendet bereits → abbrechen
 ├─ für jedes aktive Ziel parallel (asyncio.gather, pro Plattform begrenzt):
 │    ├─ Token prüfen/erneuern (refresh), sonst Ziel → failed „Bitte neu anmelden“
 │    ├─ Text = Variante(Profil) ?? Variante(Plattform) ?? Haupttext (+ Signatur)
 │    ├─ plugin.transform() → Teile (Thread), Facets, Escaping
 │    ├─ Medien hochladen (Cache media_upload, Alt-Text setzen, Video abfragen)
 │    ├─ Link-Card bauen, falls nötig (Bluesky/LinkedIn: OG + Thumbnail)
 │    ├─ Teile posten ab dem ersten fehlenden idx, jeweils Referenz speichern
 │    └─ Ziel → published | failed (Fehler übersetzt)
 ├─ Zustand des Beitrags ableiten, claimed_until = NULL
 └─ GNotification (im Hintergrund) bzw. Ergebnisdialog/Toast (mit Fenster)
```

Retries sind automatisch nur bei Netzwerkfehlern, 5xx und 429 möglich
(Backoff 30 s, 2 min, 10 min, höchstens drei Versuche). 4xx-Fehler werden
nicht wiederholt. Mastodon bekommt den Header `Idempotency-Key`. Bei den
anderen Plattformen verhindert die gespeicherte Teil-Referenz Doppelposts.

---

## 6. Hintergrunddienst

### 6.1 Anforderungen

- Geplante Beiträge werden auch bei geschlossenem Fenster gesendet.
- Zwischen zwei Terminen soll der Dienst möglichst keine Ressourcen belegen.
- Nach Suspend, Ausschalten oder Absturz werden verpasste Termine erkannt und
  gemeldet bzw. nachgefragt, nicht still gesendet.
- Es darf nie doppelt gesendet werden, auch wenn GUI und Dienst gleichzeitig
  laufen.
- Er muss im nativen Paket (AUR) und im Flatpak funktionieren.

### 6.2 Erwogene Ansätze

| Ansatz | Vorteile | Nachteile |
|---|---|---|
| A: Dauerhafter Daemon (systemd-User-Service bzw. Autostart) mit internen Timern | Ein Codepfad, sofortige Reaktion | 30–50 MB RAM dauerhaft; GLib-Timer basieren auf `CLOCK_MONOTONIC` und laufen bei Suspend nicht weiter, man muss also selbst nachrechnen |
| B: systemd-Timer minütlich, Kurzläufer prüft DB | Simpel, robust | 1440 Python-Starts pro Tag, unnötige Last auf dem Laptop |
| **C: systemd-Timer mit dynamischem `OnCalendar` auf den nächsten Termin + Kurzläufer** | Kein Prozess zwischen Terminen; systemd übernimmt Uhrzeit, Zeitzone, Suspend und `Persistent=` | Nicht im Flatpak verfügbar; ein Drop-in muss geschrieben und neu geladen werden |
| D: Transiente Timer per `systemd-run --user --on-calendar` | Kein Drop-in | Überlebt keinen Neustart |

### 6.3 Entscheidung: ein Scheduler-Kern, zwei Auslöser

Der eigentliche Ablauf ist überall gleich: `dandelion --run-due`
(`core/scheduler.py`) beansprucht fällige Beiträge, sendet sie, klassifiziert
verpasste Termine und berechnet den nächsten Termin. Nur der **Auslöser**
unterscheidet sich.

**Nativ (AUR, Meson-Installation): Ansatz C**

```ini
# /usr/lib/systemd/user/dandelion-scheduler.service
[Unit]
Description=Dandelion: geplante Beiträge senden
After=network-online.target graphical-session.target
[Service]
Type=oneshot
ExecStart=/usr/bin/dandelion --run-due
# kein Restart: der nächste Timer-Lauf holt nach

# /usr/lib/systemd/user/dandelion-scheduler.timer
[Unit]
Description=Dandelion: nächster geplanter Beitrag
[Timer]
OnStartupSec=2min          # nach Login auf Verpasstes prüfen
Persistent=true            # verpasste OnCalendar-Läufe nachholen
AccuracySec=5s
WakeSystem=false           # Rechner nicht aufwecken
[Install]
WantedBy=timers.target

# ~/.config/systemd/user/dandelion-scheduler.timer.d/next.conf  (von Dandelion geschrieben)
[Timer]
OnCalendar=
OnCalendar=2026-10-02 08:00:00 UTC
```

- Nach jeder Änderung an geplanten Beiträgen und am Ende jedes Laufs schreibt
  Dandelion `next.conf` neu. Danach ruft es per D-Bus
  `org.freedesktop.systemd1.Manager.Reload` auf (User-Manager) und startet den
  Timer neu. Ist nichts geplant, wird das Drop-in entfernt.
- Aktiviert wird der Timer beim ersten geplanten Beitrag über
  `EnableUnitFiles` + `StartUnit` (D-Bus), nach Rückfrage in der UI.
- **Suspend:** Ein `OnCalendar`-Termin, der in den Schlaf fällt, löst direkt
  nach dem Aufwachen aus. **Ausgeschaltet:** `Persistent=true` und
  `OnStartupSec` lösen nach dem Login aus. In beiden Fällen erkennt der Lauf an
  `now − scheduled_at > missed-grace-minutes`, dass der Termin verpasst ist.

**Flatpak: Background-Portal + Autostart (Variante von A)**

- Beim Aktivieren ruft Dandelion `org.freedesktop.portal.Background.RequestBackground`
  auf, mit `autostart=true` und `commandline=["dandelion", "--background"]`.
  Der Nutzer muss das einmal erlauben.
- `--background` startet dieselbe GApplication **ohne Fenster** (`hold()`).
  Wird später das Fenster geöffnet, landet der Aufruf dank GApplication-
  Einzelinstanz im selben Prozess. GUI und Dienst teilen sich also Zustand und
  Publisher.
- Der Weckmechanismus ist ein GLib-Timeout bis zum nächsten Termin, höchstens
  60 s lang. Bei jedem Aufwachen wird die Wanduhr mit `scheduled_at`
  verglichen. Das fängt Suspend und Zeitumstellungen ab, ohne logind-Zugriff.
- Gibt es keine geplanten Beiträge mehr, beendet sich der Hintergrundprozess
  (`release()`). Beim nächsten Planen startet ihn die GUI wieder, nach dem
  nächsten Login der Autostart.
- Den Ansatz C gibt es im Flatpak nicht, weil die Sandbox keinen Zugriff auf
  den systemd-User-Manager hat. Das Portal ist der vorgesehene Weg.

**Warum zwei Auslöser?** Nativ ist C die sparsamste und robusteste Lösung:
null RAM zwischen Terminen, und systemd übernimmt Uhrzeit und Suspend. Im
Flatpak gibt es keinen sauberen Zugang zu systemd, also nutzen wir das Portal.
Der Prozess läuft dort nur, solange etwas geplant ist. Der Scheduler-Kern ist
identisch, getestet wird er mit einer injizierbaren Uhr.

### 6.4 Doppelversand ausschließen

- Ein Beitrag wird atomar per `UPDATE … WHERE state IN (…)` beansprucht, mit
  Lease `claimed_until`. SQLite im WAL-Modus serialisiert die Schreibzugriffe.
- Stürzt ein Prozess ab, läuft die Lease nach 10 Minuten ab. Danach gilt der
  Beitrag als `partial`/`failed`, er wird **nicht** automatisch erneut
  gesendet.
- Pro Ziel und Teil wird die Remote-Referenz sofort nach dem Erfolg
  geschrieben, bevor der nächste Teil startet.

### 6.5 Verpasste Beiträge

| `missed-policy` | Verhalten |
|---|---|
| `ask` (Standard) | Beitrag → `missed`. GNotification „Ein geplanter Beitrag wurde nicht gesendet“ mit den Aktionen **Jetzt senden**, **Neu planen…** und **Verwerfen**. Beim nächsten Öffnen des Fensters erscheint zusätzlich ein Dialog mit allen verpassten Beiträgen. |
| `send` | sofort senden, Benachrichtigung „verspätet gesendet (geplant 08:00)“ |
| `discard` | Beitrag → `missed`, Benachrichtigung, kein Versand |

Die Benachrichtigungsaktionen sind `app.`-Actions der GApplication. Sie laufen
per D-Bus-Aktivierung auch dann, wenn kein Prozess läuft.

### 6.6 Serverseitiges Planen (optional, Phase 5)

Für Mastodon (≥ 5 min Vorlauf, ≤ 25 pro Tag) und Facebook (10 min bis 30 Tage)
kann ein Profil „Serverseitig planen“ nutzen. Der Beitrag geht dann schon beim
Planen an den Server (`scheduled_at`), das Ziel bekommt den Zustand
`scheduled_remote`. Vorteil: Er erscheint auch bei ausgeschaltetem Rechner.
Nachteil: Medien werden sofort hochgeladen, und Änderungen erfordern Abbrechen
und neu Anlegen. Die Option ist standardmäßig aus.

---

## 7. Mehrsprachigkeit, Barrierefreiheit, Qualität

- **gettext**, Domain `dandelion`. Quelltexte auf Englisch, `po/de.po` von
  Anfang an. Plural über `ngettext` („1 Problem“ / „2 Probleme“).
- **Barrierefreiheit:**
  - Jedes Icon-only-Element bekommt ein `accessible-label` (z. B.
    „Alt-Text fehlt für Bild 2“).
  - Zähler setzen `accessible-description` und melden Überschreitungen über
    `Gtk.Accessible.announce()`.
  - Vollständige Tab-Reihenfolge.
  - Farben nur aus Stilklassen und `var(--accent-bg-color)` usw., keine harten
    Werte. Rollenfarben sind nie die einzige Information, das Emoji bzw. der
    Name steht immer daneben.
- **Tests (pytest):**
  - `counting` mit Fixtures aus der Mastodon- und twitter-text-Testsuite
    (Conformance-YAML)
  - `validation`
  - `splitting`
  - `scheduler` mit Fake-Uhr: Suspend, Zeitumstellung, Lease-Ablauf,
    `missed-policy`
  - `publisher` mit gemocktem Soup-Transport: Teilfehler, Retry ab Teil n
  - Plattform-Plugins mit aufgezeichneten JSON-Antworten
- **Werkzeuge:** ruff, mypy (strict für `core/` und `platforms/`), CI über
  GitHub Actions (Tests + `flatpak-builder --sandbox`-Build).

---

## 8. Projektstruktur (geplant)

```
dandelion/
├── meson.build · meson_options.txt · COPYING · README.md
├── data/
│   ├── de.linuxundich.Dandelion.desktop.in
│   ├── de.linuxundich.Dandelion.metainfo.xml.in
│   ├── de.linuxundich.Dandelion.gschema.xml
│   ├── de.linuxundich.Dandelion.service.in      (D-Bus-Aktivierung)
│   ├── systemd/dandelion-scheduler.{service,timer}
│   └── icons/hicolor/{scalable,symbolic}/apps/
├── po/  (LINGUAS, POTFILES.in, de.po)
├── src/dandelion/
│   ├── main.py · application.py · window.py
│   ├── ui/        *.blp  (window, composer, preview-tile, schedule-view, history-view,
│   │                     preferences, role-page, profile-page, add-profile, alt-text,
│   │                     schedule-dialog, send-dialog, shortcuts)
│   ├── widgets/   profile_chip.py · media_strip.py · counter_bar.py · preview_tile.py
│   ├── viewmodels/
│   ├── core/  ·  platforms/  ·  auth/  ·  net/  ·  ai/
├── tests/
├── build-aux/
│   ├── flatpak/de.linuxundich.Dandelion.json
│   └── arch/PKGBUILD
└── docs/
```

---

## 9. Entscheidungen und offene Fragen

| Thema | Stand |
|---|---|
| Entwürfe | ✅ Seitenleiste im Composer (F9) |
| Bluesky-Login | ✅ App-Passwort als Standard, OAuth optional |
| Alt-Text-Pflicht | ✅ Nur Mastodon blockiert; andere Plattformen Warnung, Pflicht für alle per Einstellung `require-alt-text-everywhere` |
| Profil in mehreren Rollen (n:m) | ✅ ja, mit „Standardmäßig ausgewählt“ pro Rolle |
| Signatur/Hashtag-Block pro Rolle | ✅ im MVP; im Composer pro Beitrag abwählbar |
| Ablage der Bluesky-OAuth-Metadaten | ✅ **linuxundich.de** (entschieden 2026-10-01, ersetzt GitHub Pages): `https://linuxundich.de/dandelion/oauth/client-metadata.json`, statisch im Webroot unter `/hosts/linuxundich.de/dandelion/oauth/`. Das Redirect-Schema ist damit `de.linuxundich:/callback` und passt zur App-ID `de.linuxundich.Dandelion`. Die Datei wird angelegt, sobald OAuth implementiert wird. |

Konzept freigegeben am 2026-10-01.
