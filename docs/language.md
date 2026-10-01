# Sprachentscheidung: Python/PyGObject oder Rust/gtk-rs

Stand: 2026-10-01. Geprüft auf dem Zielsystem (Arch, GNOME 50): gtk4 4.22.5,
libadwaita 1.9.4, python 3.14.7, python-gobject 3.56.3, meson 1.12.1,
rustup stable. Die GI-Typelibs für Adw-1, Soup-3.0, Secret-1 und Xdp-1.0/XdpGtk4
(libportal) sind installiert. `blueprint-compiler` (extra, 0.22.2) fehlt noch
und wird für beide Varianten gebraucht.

## Vergleich

| Kriterium | Python + PyGObject | Rust + gtk-rs |
|---|---|---|
| **Wartbarkeit** | Kurzer, gut lesbarer Code; schnelle Iteration ohne Kompilieren. Fehler zeigen sich erst zur Laufzeit, deshalb sind Typ-Hints, mypy und Tests Pflicht. | Typsystem fängt viele Fehler beim Kompilieren ab, Refactoring ist sicher. GObject-Subclassing (`imp`-Module, `glib::Properties`) ist aber sehr boilerplate-lastig, die Lernkurve ist steil. |
| **Async-HTTP** | PyGObject ≥ 3.50 integriert asyncio in die GLib-Hauptschleife (`gi.events.GLibEventLoopPolicy`, lokal getestet). Damit `async`/`await` direkt im UI-Code, HTTP über libsoup3 (GI) oder httpx. Kein Thread-Jonglieren. | `glib::spawn_future_local` plus reqwest auf einer separaten tokio-Runtime oder soup3-rs. Funktioniert gut, die Brücke zwischen tokio und GLib ist aber Handarbeit (Channels, `Send`-Grenzen). |
| **Plattform-Bibliotheken** | Keine Pflicht-Abhängigkeiten über GNOME hinaus. Für Graphem-Zählung reicht Pango (Log-Attrs) oder das Modul `regex` (`\X`), für die X-Gewichtung ein kleiner eigener Port der twitter-text-Konfiguration. | Crates `unicode-segmentation` und `twitter-text` vorhanden; atrium (AT Protocol) und megalodon (Mastodon) als optionale Clients. |
| **Paketierung AUR** | Trivial: `depends=(python-gobject libadwaita libsoup3 libsecret libportal)`. Kein Build-Schritt außer Meson und Blueprint. | Gut machbar, aber Build dauert Minuten und braucht `cargo` als makedepend. Offline-Builds brauchen `cargo fetch --locked`. |
| **Paketierung Flatpak** | GNOME-Runtime bringt alles mit; Python-Zusatzpakete (falls nötig) per `flatpak-pip-generator`. | `flatpak-cargo-generator` für Hunderte Crates, Rust-SDK-Extension. Mehr Aufwand, aber gut etabliert (Fractal, Newsflash). |
| **Hintergrunddienst** | Interpreter-Start ca. 150–300 ms, RSS ca. 30–50 MB. Als timer-getriebener Kurzläufer (Start, Senden, Beenden) unkritisch. | Winziger statischer Binary, wenige MB RSS. Elegant, bei einem Kurzläufer aber kein spürbarer Vorteil. |
| **GNOME-Ökosystem** | Apostrophe, Dialect, Gaphor, Letterpress, Wike, Komikku sind Python-Apps. Gute Beispiele, Blueprint und Meson sind Standard. | Fractal, Newsflash, Shortwave, Amberol, Fragments (seit 3.0) sind Rust-Apps. Sehr gute Vorlagen. |
| **Mitarbeit Dritter / eigene Pflege** | Niedrige Einstiegshürde, gut lesbar auch ohne Spezialkenntnisse. | Höhere Hürde, dafür meist robusterer Code. |

## Empfehlung: Python 3.14 + PyGObject

1. **Schnellster Weg zum MVP.** Die Komplexität der App liegt in Plattform-APIs,
   OAuth-Flows, Zählregeln und UI, nicht in Rechenleistung. Hier zahlt sich die
   kurze Iterationszeit aus.
2. **Async ist sauber gelöst.** Durch die asyncio-Integration von PyGObject
   laufen parallele Uploads und Posts auf fünf Plattformen ohne Threads im
   UI-Prozess.
3. **Paketierung ist am einfachsten.** Fast alle Abhängigkeiten stammen aus der
   GNOME-Runtime bzw. den Arch-Repos. Das hält PKGBUILD und Flatpak-Manifest
   schlank.
4. **Wartbarkeit absichern.** Strikte Typ-Hints mit mypy, ruff, pytest. Die
   Plattform-Backends werden reine Python-Klassen ohne GTK-Abhängigkeit, damit
   sie gemockt und auch vom Hintergrunddienst genutzt werden können.

**Wann Rust die bessere Wahl wäre:** wenn die App langfristig von mehreren
Leuten gepflegt wird, die Rust bereits beherrschen, oder wenn du
Laufzeitfehler grundsätzlich vermeiden willst und den höheren Initialaufwand
in Kauf nimmst.

## Geplanter Stack (bei Python)

- UI: GTK 4.22 / libadwaita 1.9, Blueprint
- HTTP: libsoup3 per GI (respektiert Proxy-Einstellungen des Systems);
  Alternative httpx
- Secrets: libsecret (`Secret-1`)
- Portale: libportal (`Xdp-1.0`, `XdpGtk4`) für OpenURI und Background
- Datenbank: `sqlite3` aus der Standardbibliothek, Migrationen versioniert
- Tests: pytest, gemockte HTTP-Antworten
- Build: Meson, gettext (`i18n`-Modul)
