# Marktanalyse: Crossposting und Social-Media-Planung

Stand: 2026-10-01. Recherchiert per Websuche, Herstellerseiten, Dokumentation,
Flathub-API, GitHub-API und Quellcode der GNOME-Apps. Preise in US-Dollar wie
vom Anbieter angegeben, ohne Steuern. Wo Drittquellen sich widersprechen oder
eine Angabe nicht verifizierbar war, ist das vermerkt.

Kurzfassung:

- Der Markt teilt sich in **teure Web-SaaS für Teams** (Hootsuite, Buffer,
  Publer, Fedica, Typefully) und **selbst gehostete Web-Dashboards** (Postiz,
  Mixpost). Alle sind Browser-Anwendungen. Keine davon läuft nativ auf dem
  Linux-Desktop.
- **Eine native GNOME/GTK-App für Crossposting gibt es nicht.** Flathub liefert
  für „crosspost“ keinen Treffer. Für „mastodon“ und „bluesky“ erscheinen nur
  Ein-Netzwerk-Clients (Tuba, Tokodon) und ein Web-Wrapper (Nora). Auf GitHub
  existiert mit *Hangar* ein GTK4/libadwaita-Client nur für Bluesky (Technical
  Preview, kein Crossposting). Der nächste Desktop-Konkurrent ist *SocialSox*,
  eine Electron-App mit 7 Sternen, die nur plant, solange sie läuft.
- Native Crossposter gibt es nur für Apple-Plattformen (Croissant, Bluestodon).
  Sie zeigen, dass Nutzer für ein schlankes „einmal schreiben, überall posten“
  zahlen, auch ohne Analytics und Team-Funktionen.
- Kein Produkt **erzwingt Alt-Texte**. Alle bieten sie optional an, manche mit
  KI-Vorschlag. Hier liegt eine echte Lücke.

---

## 1. Funktionstabelle

Legende: ✅ vorhanden · ⚠️ eingeschränkt, nur in teuren Tarifen oder nicht
eindeutig belegt · ❌ fehlt. Plattformkürzel: M = Mastodon, B = Bluesky,
X = X/Twitter, F = Facebook (nur Seiten), L = LinkedIn.

### 1.1 Hauptwettbewerber

| Funktion | Buffer | Hootsuite | Typefully | Fedica | Publer | Postiz | Mixpost | **Geplante App** |
|---|---|---|---|---|---|---|---|---|
| Unterstützte Plattformen (von M/B/X/F/L) | ✅ alle 5, dazu Threads, IG, TikTok u. a. | ⚠️ B/X/F/L; **Mastodon nur Monitoring, kein Posten** | ⚠️ M/B/X/L, dazu Threads, IG; **kein Facebook** | ✅ alle 5, dazu Threads, Pixelfed | ✅ alle 5, dazu Threads, WordPress u. a. | ✅ alle 5 von 34 Kanälen | ⚠️ Lite: nur F/X/M; Pro: alle 5 | ✅ alle 5 (gestaffelt: M/B im MVP) |
| Mehrere Accounts pro Plattform | ✅ (je Kanal bezahlt) | ✅ | ✅ | ✅ | ✅ (je Account bezahlt) | ✅ | ✅ unbegrenzt | ✅ |
| Workspaces / Rollen | ⚠️ Organisationen | ✅ Teams/Orgs | ✅ „Social Sets“ | ⚠️ | ✅ Workspaces (unbegrenzt in Bezahltarifen) | ✅ Kundengruppen + „Sets“ | ⚠️ Workspaces nur Pro | ✅ Rollen mit Farbe/Emoji |
| Textvarianten pro Plattform | ✅ | ✅ | ✅ | ✅ „Custom Posts“ | ✅ | ✅ Global vs. „Detach“ | ✅ „Post Versions“ | ✅ mit Erben vom Haupttext |
| Zeichenzähler pro Plattform | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ medienbewusst | ✅ | ✅ exakte Zählregeln (Grapheme, gewichtet, URL = 23) |
| Thread-Aufteilung | ✅ X/Threads/M/B | ⚠️ | ✅ Kernfunktion, Auto-Split | ✅ M/B/X/Threads | ✅ inkl. Anpassung je Teil | ✅ mit Verzögerung zwischen Teilen | ⚠️ | ✅ optional, (1/n) |
| Alt-Text-**Erzwingung** | ⚠️ optional, KI-Vorschlag | ⚠️ optional | ⚠️ optional | ⚠️ optional, „Describe with AI“ | ⚠️ optional | ⚠️ optional | ⚠️ optional | ✅ **Pflicht, blockiert Posten** |
| Vorschau pro Plattform | ✅ | ✅ | ✅ sehr genau | ⚠️ | ✅ pro Account, live | ✅ | ✅ | ✅ Kachel pro Profil |
| Scheduler / Queue mit Zeitslots | ✅ **Original**: wöchentliche Slots je Kanal | ⚠️ AutoSchedule nach „Best Time“ | ✅ Queue mit Slots | ✅ Queue, „Pipelines“ | ✅ Auto-Schedule | ✅ Slots je Kanal (für Tagesansicht, RSS, API) | ⚠️ Queue nur Pro | ✅ V1: Zeitpunkt; später Slots |
| Kalenderansicht | ✅ | ✅ Planner | ✅ | ✅ | ✅ | ✅ Tag/Woche/Monat/Liste, Drag & Drop | ✅ | ⚠️ V1 Liste, später Kalender |
| Entwürfe | ✅ | ✅ | ✅ Kernfunktion, teilbare Links | ✅ unbegrenzt | ✅ | ✅ | ✅ | ✅ Autosave |
| KI-Assistent | ✅ alle Tarife | ✅ „Wisdom“/OwlyWriter | ✅ lernt Schreibstil | ✅ | ✅ | ✅ OpenAI, Agent, MCP | ⚠️ nur Pro | ✅ optional: Gemini/OpenAI/Grok |
| Analytics | ✅ (bezahlt) | ✅ sehr umfangreich | ⚠️ v. a. X/LinkedIn | ✅ **Stärke** (Demografie, Sentiment) | ✅ | ✅ | ✅ (erweitert nur Pro) | ❌ bewusst nicht (später evtl. Basiszahlen) |
| Preis / Lizenz | Free (3 Kanäle, 10 Posts/Kanal); 5 $/Kanal/Monat; Team 10 $/Kanal | 99–399 $/Nutzer/Monat (jährlich) | Free; bezahlt ca. 10–39 $/Monat (Angaben schwanken) | Free (10 aktive geplante Posts); 10–129 $/Monat | Free (3 Accounts); ab 12 $/Monat (3 Accounts) | AGPL-3.0; Cloud 29–99 $/Monat | Lite frei (MIT); Pro 299 $ einmalig; Enterprise 1.199 $ | GPL-3.0-or-later, kostenlos |
| Self-hosting | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Docker: Postgres, Redis, Temporal | ✅ Laravel/PHP | ✅ läuft lokal, kein Server |
| Desktop-nativ | ❌ Web, Mobil, Browser-Erweiterung | ❌ | ❌ | ❌ | ❌ | ❌ Web, Browser-Erweiterung | ❌ | ✅ GTK4/libadwaita |

### 1.2 Nischen-Crossposter und verwandte Projekte

| Produkt | Art / Plattform | Netzwerke | Planung | Bemerkung |
|---|---|---|---|---|
| **Croissant** | nativ iOS/iPadOS/macOS, Abo (ca. 2,99 $/Monat laut TechCrunch) | B, M, Threads | ❌ nicht belegt | Mehrere Accounts je Dienst, **Account-Gruppen**, Optionen pro Netzwerk, Alt-Text, CW. Kommt unserem Rollenkonzept am nächsten. |
| **Bluestodon** | nativ macOS/iOS | B, M | ❌ | Reiner Poster ohne Timeline. **Auto-Split an natürlichen Grenzen** (300/500 bzw. Instanzlimit), **Vorschau beider Threads nebeneinander**, Medien pro Plattform, Alt-Text. |
| **Openvibe** | Mobil-Client (iOS/Android), Desktop angekündigt | M, B, Nostr, Threads | ❌ | Vereinte Timeline plus Crossposting. Client, kein Planungswerkzeug. |
| **SocialSox** | Electron, MIT, 7 Sterne | M, X, B | ⚠️ nur solange App läuft | Einziger echter Desktop-Crossposter, aber kein GTK, wenig Verbreitung. |
| **Crossposter** (apoorvdarshan) | Next.js-Dashboard auf localhost, MIT | X, L, B, M, IG, YouTube, Nostr u. a. | ⚠️ nur solange Server läuft | Teilweise **inoffizielle Cookie-Integrationen** (X, IG). Gutes Negativbeispiel für ToS-Risiken. |
| **crosspost** (humanwhocodes) | JS-Bibliothek, CLI, MCP-Server, Apache-2.0, ca. 580 Sterne | B, M, X, L, Discord, Telegram, Dev.to, Nostr | ❌ | Saubere „Strategy“-Abstraktion je Netzwerk: Vorbild für unsere Backend-Schnittstelle. |
| **toot** | CLI/TUI, GPL-3.0 | nur M | ❌ | Etabliert, Single-Network. |
| **barkr**, **bluesky-crossposter**, **skymoth**, **mastodon-to-bluesky** | Python/Node-Dienste | M, B, X, Telegram, Discord, RSS | – | **Automatische Spiegelung** von einem Quellnetz in andere. Kein Composer, keine Varianten. Barkr nur Text. |
| **Sociabli** | Web-Dienst, „post once, sync everywhere“ | B, M u. a. | – | Sync-Dienst statt Composer. Aktueller Status nicht verifizierbar (Website lieferte keinen Inhalt). |
| **Flare** | Kotlin Multiplatform, Linux nur als AppImage, AGPL-3.0, ca. 1.500 Sterne | M, B, X, Misskey, Nostr, RSS | ❌ | Timeline-Client mit Crossposting. Nicht GTK, Linux ist Nebenplattform. |
| **CrispDeck** | Tauri 2 + Svelte, AGPL-3.0 | M, B, Threads | ❌ | Deck-Client mit Crossposting, sehr jung (0 Sterne). |
| **Hangar** | **GTK4/libadwaita, Rust**, MPL-2.0 | nur B | ❌ | Native GNOME-App, aber reiner Bluesky-Client, Technical Preview, nicht auf Flathub. |
| **Skeetdeck** | Web-Client | nur B | ❌ | TweetDeck-artiger Bluesky-Client, kein Crossposter. |
| **Tuba / Tokodon** | GTK4/libadwaita (Vala) bzw. KDE/Kirigami | Fediverse | ✅ Mastodon-native Planung | Ein-Netzwerk-Clients. Design-Vorbilder, keine Konkurrenz. |

**Flathub-Prüfung (API, 2026-10-01):** „crosspost“ → 0 Treffer. „bluesky“ →
Newelle (KI-Chat), Nora (SNS-Browser). „mastodon“/„fediverse“ → Tuba,
Tokodon, Nora, Aria (Misskey), Fedinspect u. a. „social media“ → Share
Preview, Manyverse, FeedDeck. Kein Crossposter, kein Social-Media-Planer.

---

## 2. Stärken und Schwächen je Produkt

### Buffer
- \+ Erfinder der **Queue mit festen Wochen-Slots** je Kanal; Optionen „Next
  Available“, „Prioritize“, „Now“, „Set Date and Time“.
- \+ Breite Netzwerkabdeckung inkl. Mastodon und Bluesky; Threads auf X,
  Threads, Mastodon, Bluesky.
- \+ KI-Assistent in allen Tarifen, KI-Vorschläge für Alt-Texte.
- − Preis pro Kanal: Wer drei Rollen mit je drei Profilen hat, zahlt schnell
  40 $+/Monat.
- − Alt-Text nur optional, Gratis-Tarif auf 10 geplante Posts pro Kanal begrenzt.

### Hootsuite
- \+ Enterprise-Funktionsumfang: Analytics, Social Listening, Freigaben,
  Inbox.
- \+ Bluesky-Publishing und -Listening in allen Bezahltarifen.
- − **Kein Posten auf Mastodon** (nur Monitoring seit April 2026).
- − Ab 99 $ pro Nutzer und Monat, für Einzelpersonen völlig überdimensioniert.
- − Schwerfällige Oberfläche, Fokus auf Marketing-Teams.

### Typefully
- \+ Bester **Schreib-Editor**: ablenkungsfrei, Thread-Blöcke mit Trenner oder
  Auto-Split, sehr genaue Vorschau.
- \+ „Social Sets“ bündeln Accounts, entsprechen konzeptionell unseren Rollen.
- \+ KI lernt den eigenen Schreibstil aus veröffentlichten Posts.
- − **Kein Facebook**; Analytics stark auf X/LinkedIn ausgerichtet.
- − Preisangaben uneinheitlich, Gratis-Tarif stark begrenzt.

### Fedica
- \+ Volle Unterstützung für **Mastodon, Bluesky, Pixelfed** inkl. Umfragen,
  Alt-Text, Link-Cards, CW-Labels; Threads gratis.
- \+ Stärkste Analytics im Feld (Demografie, Sentiment, Best Time).
- \+ „Custom Posts“ pro Netzwerk, KI-Alt-Text („Describe with AI“).
- − Gratis nur 10 aktive geplante Posts; Video und Thread-Abstände nur bezahlt.
- − Funktionsfülle macht die Oberfläche unübersichtlich.

### Publer
- \+ **Live-Vorschau pro Account**, auch für jeden einzelnen Thread-Teil.
- \+ Anpassung einzelner Thread-Teile pro Account, ohne die anderen zu ändern.
- \+ Workspaces in Bezahltarifen unbegrenzt; alle fünf Zielplattformen.
- − Abrechnung pro Account (ca. 4–7 $/Account/Monat).
- − Reine Web-App, keine Pflicht für Alt-Texte.

### Postiz
- \+ Open Source (AGPL-3.0), 34 Kanäle, sehr aktive Entwicklung (ca. 30 k Sterne).
- \+ Klares Composer-Modell **„Global“ vs. „Detach“** pro Kanal; Mentions nur
  im losgelösten Kanal, weil ein Handle nur auf einer Plattform gilt.
- \+ Kalender mit Tag/Woche/Monat/Liste, Drag & Drop; Zeitslots je Kanal
  strukturieren die Tagesansicht.
- \+ API, CLI und MCP-Server; Signaturen und gespeicherte Kanal-Sets.
- − Self-hosting schwergewichtig (Postgres, Redis, Temporal, Reverse Proxy,
  eigene Developer-Apps je Plattform).
- − Zeitslots folgen der **Browser-Zeitzone**, keine Zeitzone pro Kanal.
- − Alt-Text optional; Cloud ab 29 $/Monat ohne Gratis-Tarif.

### Mixpost
- \+ Einmalzahlung statt Abo, unbegrenzte Accounts und Nutzer.
- \+ „Post Versions“ pro Account, Kalender, Medienbibliothek, Labels, Vorlagen.
- − Lite nur Facebook-Seiten, X und Mastodon; **Bluesky und LinkedIn nur in Pro (299 $)**.
- − Queue, KI, Workspaces nur in Pro.
- − PHP/Laravel-Server nötig; für Einzelpersonen Overkill.

### Croissant / Bluestodon (native Apple-Crossposter)
- \+ Zeigen die Zielgruppe: Einzelpersonen, die schnell auf 2–3 offene Netze posten.
- \+ Croissant: Account-Gruppen; Bluestodon: Auto-Split und Vorschau nebeneinander.
- − Nur Apple-Plattformen, keine Planung (Croissant: nicht belegt), kein X/Facebook/LinkedIn.

### SocialSox (Electron)
- \+ Einziger Desktop-Crossposter für Linux mit M/X/B und Verlauf mit Zustellstatus.
- − Electron, kein GNOME-Look, Planung nur bei laufender App, Zugangsdaten in den Einstellungen.

---

## 3. Konkrete Übernahmen

### 3.1 Funktionen von den Wettbewerbern

| Von | Was | Wie wir es umsetzen | Begründung |
|---|---|---|---|
| **Postiz** | Composer-Modell „Global“ vs. „Detach“ | Haupttext oben; je Profil eine Variante, die standardmäßig erbt (gesperrt, gedimmt). Button „Für diese Plattform anpassen“ löst sie. „Zurück zum Haupttext“ fragt per AdwAlertDialog nach. Mentions/Handles nur in gelösten Varianten. | Klarstes Modell im Markt, verhindert versehentliches Auseinanderlaufen der Texte. Passt exakt zur Anforderung „Varianten erben vom Haupttext“. |
| **Postiz** | Medienbewusster Zeichenzähler pro Kanal | Zähler je Profil, der Links (Mastodon/X: 23), Medien und CW einrechnet. | Nutzer sehen sofort, *welche* Plattform überläuft, statt global zu kürzen. |
| **Postiz** | „Sets“ und Signaturen | Rolle = gespeichertes Set von Profilen + optionale Signatur/Hashtag-Block pro Rolle. | Deckt „Rolle wählen → Profile vorausgewählt“ ab und spart Tipparbeit (z. B. „#linuxundich“-Footer). |
| **Postiz** | Kalender mit Tag/Woche/Monat/Liste und Drag & Drop | V1: Liste gruppiert nach Tag (AdwPreferencesGroup je Datum). Später Monatsraster mit Drag & Drop zum Umplanen. | Liste ist auf 360 px gut bedienbar; Kalender lohnt erst ab vielen geplanten Posts. |
| **Buffer** | Queue mit festen Wochen-Slots je Kanal | Später: Slots **pro Rolle** (nicht pro Kanal), z. B. „linuxundich: Mo–Fr 08:30, 17:00“. Aktionen „Nächster freier Slot“, „Ganz nach vorn“, „Jetzt“, „Zeitpunkt wählen“. Zeitzone pro Rolle. | Bewährtes Muster; Rollen statt Kanäle, weil der Nutzer in Rollen denkt. Postiz' Schwäche (nur Browser-Zeitzone) vermeiden. |
| **Typefully** | Ablenkungsfreier Editor, Thread-Blöcke | Editor mit großzügigen Rändern (AdwClamp), Fokusmodus per Taste; Thread-Teile über Trennzeile (z. B. Leerzeile + „---“) oder Auto-Split; jeder Teil mit eigenem Zähler. | Schreiben ist die Hauptaufgabe; Typefully beweist, dass Ruhe im Editor verkauft. |
| **Bluestodon** | Auto-Split an natürlichen Grenzen je Plattform | Split-Algorithmus: Absatz > Satz > Wort, Limits pro Plattform (B 300 Grapheme, M Instanzlimit), Nummerierung (1/n) optional, Vorschau zeigt Teile nebeneinander. | Bluesky und Mastodon brauchen unterschiedliche Teilungen desselben Texts. |
| **Publer** | Live-Vorschau pro Account, auch pro Thread-Teil | Vorschaukachel je ausgewähltem Profil (nicht nur je Plattform), mit Avatar, Name, Handle aus dem Account. | Zwei Mastodon-Accounts mit unterschiedlichen Instanzlimits brauchen getrennte Vorschauen. |
| **Fedica / Buffer** | KI-Alt-Text-Vorschlag | KI-Phase: „Alt-Text vorschlagen“ im Alt-Text-Editor, Länge nach strengstem Ziel (z. B. X 1000), immer als Vorschlag mit „Übernehmen“/„Verwerfen“. | Senkt die Hürde der Alt-Text-Pflicht. |
| **Typefully** | KI lernt Schreibstil | Stil-Prompt pro Rolle, optional aus eigenen letzten Posts abgeleitet (lokal gespeichert). | Rollen haben unterschiedliche Tonalität (privat vs. Blog). |
| **Croissant** | Account-Gruppen für schnellen Zugriff | Rollen-Umschalter direkt im Composer-Header (AdwSplitButton oder Dropdown mit Farbe/Emoji). | Rollenwechsel ist die häufigste Aktion nach dem Schreiben. |
| **SocialSox** | Verlauf mit Zustellstatus pro Plattform | Ansicht „Veröffentlicht“ mit Status je Profil, Link zum Beitrag, „Erneut versuchen“ für fehlgeschlagene Profile. | Teilfehler sind bei 5 Plattformen der Normalfall. |
| **crosspost (JS)** | Strategy-Interface pro Netzwerk | `authenticate`, `validate`, `upload_media`, `post`, `delete`, `get_limits` als Python-Protokoll ohne GTK-Abhängigkeit. | Testbar mit Mocks, vom Hintergrunddienst nutzbar, neue Netze leicht ergänzbar. |

### 3.2 Was wir bewusst **nicht** übernehmen
- **Analytics, Social Listening, Inbox, Freigabe-Workflows** (Hootsuite, Fedica, Buffer Team): Zielgruppe ist eine Person mit mehreren Rollen, kein Marketing-Team.
- **Inoffizielle Cookie-Integrationen** (apoorvdarshan/crossposter): ToS-Risiko, Sperrgefahr für Accounts.
- **Server-Pflicht** (Postiz, Mixpost): Der Scheduler läuft als systemd-User-Dienst lokal.
- **KI-Bild- und Video-Generierung** (Postiz): außerhalb des Kerns, Kostenfalle.
- **Abrechnung pro Kanal**: Die App ist frei; nur X verursacht API-Kosten beim Nutzer (Pay-per-Use seit Februar 2026, ca. 0,015 $ pro Post, 0,20 $ pro Post mit URL).

### 3.3 Design-Vorbilder aus GNOME/KDE

Geprüft im Quellcode (Tuba, Fractal, Newsflash, Apostrophe, Errands) bzw. aus
Dokumentation und Release-Notes. GNOME-Circle-Mitgliedschaft laut
apps.gnome.org vom 2026-10-01: Tuba, Newsflash, Apostrophe, Errands, Dialect,
Paper Clip, Secrets, Railway, Shortwave, Fragments, Amberol, Iotas und
**Share Preview** sind in Circle. Fractal, Foliate und Letterpress stehen
derzeit nicht in der Circle-Liste.

#### Tuba (Mastodon, Vala, Circle) – wichtigstes Vorbild für den Composer
Composer seit 0.10 komplett neu (Design: Tobias Bernard), Stand 0.11 vom 19.08.2026:
- **Container:** `AdwDialog` (500 × 400, `follows-content-size`, `can-close = false` gegen versehentliches Schließen), darin `AdwToastOverlay` → `AdwNavigationView` → `AdwToolbarView`. Unterdialoge (Alt-Text, Planung) werden als `AdwNavigationPage` in denselben Dialog **gepusht** statt als zweiter Dialog geöffnet.
- **Untere Leiste (GtkGrid):** Zeile 1 flache Icon-Buttons (Emoji, Custom-Emoji, Medien, Umfrage, CW-Toggle, „sensibel“); Zeile 2 Dropdowns (Sichtbarkeit, Sprache) mit Klasse `dropdown-circular`; rechts der Zähler; ganz rechts der Senden-Button über beide Zeilen.
- **Zeichenzähler:** Label mit Klassen `numeric`, `font-bold`, `accent`; zeigt „rest / limit“, ab Limit ≥ 1000 nur die Restzahl. Bei Überschreitung wechselt `accent` → `error`. Berechnung: Limit − Textlänge − CW-Länge − reservierte Zeichen; URLs und Mentions werden vor dem Zählen ersetzt, Zählung sprachabhängig (Locale des gewählten Sprach-Dropdowns).
- **Content-Warning:** Toggle-Button blendet über `GtkRevealer` (slide-up) ein `GtkEntry` oberhalb der Leiste ein. CW-Zeichen zählen mit.
- **Senden-Button:** `AdwSplitButton` mit Menü „Planen…“, „Als Entwurf speichern“, „Entwürfe…“. Beschriftung passt sich an (z. B. bei Direktnachricht).
- **Medien:** Drag & Drop mit Overlay „Medien zum Anhängen ablegen“, Einfügen aus der Zwischenablage, Fortschrittsanzeige, Umsortieren per Drag & Drop.
- **Alt-Text:** Jedes Anhang-Thumbnail trägt ein **„ALT“-Badge mit Kreuz (Klasse `error`) bzw. Haken (`success`)**. „Metadaten bearbeiten“ öffnet den Alt-Text-Editor mit **Fokuspunkt-Auswahl** als Navigationsseite; der Editor wächst mit dem Inhalt. Alt-Text wird **aus Bildmetadaten (EXIF/XMP via gexiv2) vorbefüllt** und auf das Instanzlimit gekürzt. Eigene Vorschaubilder seit 0.11.
- **Planung:** `AdwNavigationPage` mit `GtkCalendar` in einer `AdwPreferencesGroup`, darunter Stunden/Minuten/Sekunden als `GtkSpinButton` und **`AdwComboRow` für die Zeitzone**. Geplante Posts in eigener Seitenleisten-Ansicht.
- **Adaptiv:** `AdwBreakpoint` bei max. 430 sp schaltet `is-narrow`; dann rückt der Zähler in die obere Zeile und die Ränder schrumpfen von 32 auf 16 px.
- **Übernehmen:** praktisch das gesamte Muster. Unterschied: Wir brauchen den Composer als Hauptansicht (nicht nur Dialog), weil die Vorschauspalte daneben liegt; Alt-Text-Badge wird bei uns zur Sperre des Senden-Buttons.

#### Tokodon (KDE, Kirigami)
- Composer mit Alt-Text seit 23.02, Einfügen/Ablegen von Bildern seit 24.02; „TweetDeck-artige“ kontoübergreifende Aktionen.
- **Übernehmen:** die Idee, eine Aktion (Boost/Antwort) **mit einem anderen Account** auszuführen. Für uns: beim Erneut-Versuchen nach Fehler auf ein anderes Profil derselben Plattform ausweichen können. Sonst ist Tokodon kein GNOME-Stilvorbild.

#### Fractal (Matrix, Rust, Blueprint) – Account-Wechsel und Medien
- **Account-Wechsel:** Avatar-Button oben in der Seitenleiste öffnet ein `GtkPopover` mit `GtkListBox`: je Sitzung Avatar (40 px, Auswahlring), Anzeigename, darunter Benutzer-ID gedimmt (`dimmed`, `caption`), rechts ein Zahnrad „Kontoeinstellungen“ bzw. Fehler-Icon oder `AdwSpinner` während des Ladens. Unten Trenner und flacher Button „Konto _hinzufügen“.
- **Medien-Upload:** Anhängen-Button in der Nachrichtenleiste → Dateiauswahl → **`AdwDialog` (400 × 400) mit `AdwToolbarView`**, Kopfleiste ohne Fensterknöpfe, links „Abbrechen“, rechts „Senden“ (`suggested-action`), Inhalt eine Medienvorschau. Weiteres über ein „Mehr“-Menü (Standort, Markdown).
- **Login:** Fractal 14 (Juni 2026) setzt auf OAuth 2.0 im Browser; eigene Seite „Authentifizierung“ mit Erklärung und „Fortfahren“.
- **Übernehmen:** Popover-Muster 1:1 für den **Rollen-Umschalter** (Farbe/Emoji statt Avatar, Profilanzahl als Untertitel, Zahnrad → Rollen-Einstellungen, unten „Rolle hinzufügen“). Verbindungsstatus pro Profil wie Fractals Fehler-Icon/Spinner. Bestätigungsdialog für Medien nur, wenn Alt-Text fehlt (direkt mit Alt-Text-Feld).

#### Newsflash (RSS, Rust, Circle) – Account-Login und OAuth
- **Willkommensseite:** `AdwStatusPage` „RSS-Dienst hinzufügen“ in `AdwClamp`, Gruppen „Dieses Gerät“ und „Sync-Konto“; jeder Dienst ein `AdwActionRow` mit Logo.
- **OAuth:** Seite **„Login im Browser abschließen“** (`AdwStatusPage` mit Beschreibung), Login im Systembrowser; als Rückfall ein **`AdwEntryRow` „Redirect-URL“** zum Einfügen der Rückleitungs-URL, Button „Anmelden“ mit `AdwSpinner` im Busy-Zustand.
- **Passwort-Login:** `AdwPreferencesGroup` mit `AdwEntryRow` „Server-URL“, `AdwComboRow` „Anmelden mit“ (Passwort/Token), `AdwEntryRow` Benutzer, `AdwPasswordEntryRow`.
- **Eigenes API-Secret:** eigene Seite mit `AdwEntryRow` „Client-ID“ und „Client-Secret“ und zwei Buttons „Eigenes Secret verwenden“ / „Newsflash-Secret verwenden“.
- **Übernehmen:** genau dieses Dreigespann. Mastodon: Instanz-URL eingeben → Browser-OAuth (PKCE) → Status-Seite mit Redirect-Fallback. Bluesky: Handle + App-Passwort (bzw. OAuth) als Passwort-Seite. **X, LinkedIn, Facebook: Seite „Eigene App-Zugangsdaten“**, weil Nutzer dort eigene Developer-Apps brauchen (X Pay-per-Use, Facebook App-Review).

#### Apostrophe (Markdown, Python, Circle) – Editor/Vorschau-Split
- Vorschau-Layouts **„Volle Breite“, „Halbe Breite“ (nebeneinander), „Halbe Höhe“ (übereinander), „Fenster“ (separates Fenster)**, umschaltbar über einen Layout-Umschalter in der Kopfleiste. Seit 3.3 schmaler Modus für Mobilgeräte, Autosave/Absturzwiederherstellung, Inline-„Peek“-Popover. Fokus- und Hemingway-Modus, Wort-/Zeichenstatistik in der Fußzeile.
- **Übernehmen:** Composer mit Vorschaumodi „Nebeneinander“ (breit, `AdwOverlaySplitView` mit Vorschau rechts), „Nur Editor“ und auf schmalen Fenstern Vorschau im **`AdwBottomSheet`** oder als eigener Tab (`AdwViewSwitcher` in der unteren Leiste). Autosave mit Wiederherstellung von Apostrophe; Fokusmodus als Typefully-Ersatz.

#### Errands (Aufgaben, Python, Circle) – Datums- und Zeitauswahl
- Wiederverwendbarer Datetime-Picker: Titelzeile mit menschenlesbarem Datum (`title-2`), **Zeit-Presets als Buttons mit Symbol: 09:00 (Morgen), 13:00 (Sonne), 17:00 (Sonnenuntergang), 20:00 (Mond)**, Stunden/Minuten-Spinner, **Tag-Presets „Heute“, „Morgen“, „Jetzt“**, „Löschen“, darunter `GtkCalendar`.
- Hinweis: letzte Veröffentlichung Dezember 2025, Entwicklung ruhiger.
- **Übernehmen:** Presets als schnellster Weg zur Planung. Bei uns: Zeit-Presets **aus den Slots der Rolle** befüllen (Buffer-Idee), plus „Heute“/„Morgen“, Kalender und Zeitzonen-`AdwComboRow` (Tuba). Validierung „Zeitpunkt liegt in der Vergangenheit“ inline.

#### Share Preview (Circle) – Vorschaukacheln für Links
- Testet lokal, wie Link-Karten auf verschiedenen Plattformen aussehen, aus Open-Graph/Twitter-Card-Metadaten.
- **Übernehmen:** Darstellungslogik für **Link-Cards** in unseren Vorschaukacheln (Titel, Beschreibung, Bild, Domain; stilisiert statt Markenoptik). Gerade für linuxundich.de-Artikel relevant.

#### Weitere Circle-Apps (Muster)
- **Dialect:** Anbieterwahl mit Instanz-URL und API-Key in den Einstellungen → Vorbild für **KI-Anbieter-Einstellungen** (Gemini/OpenAI/Grok als `AdwComboRow`, Modell als `AdwComboRow`, Key als `AdwPasswordEntryRow`, Ablage in libsecret).
- **Railway:** viele austauschbare Anbieter (Verkehrsverbünde) hinter einer einheitlichen Oberfläche, plus Abfahrt/Ankunft-Datums-Zeit-Zeile → Bestätigt das Plugin-Modell und eine kompakte Datum/Zeit-Zeile.
- **Secrets:** sensibler Umgang mit Zugangsdaten → Tokens nur im Secret Service, nie anzeigen; „Abgelaufen“ als `AdwBanner` mit Aktion „Neu anmelden“.
- **Paper Clip:** Drag & Drop einer Datei → Formular aus `AdwEntryRow`s → Vorbild für den **Alt-Text-/Medien-Editor**.
- **Fragments:** Verbindung zu lokalem oder entferntem Dienst wählbar → Statusanzeige für den Hintergrunddienst („Planungsdienst läuft/gestoppt“).
- **Iotas, Amberol, Shortwave:** Konzentration auf eine Aufgabe, ruhige Oberfläche, saubere adaptive Layouts mit `AdwBreakpoint` und Bottom-Sheet (Shortwave-Player) → Haltung: Die App macht eine Sache sehr gut.

---

## 4. Priorisierte Feature-Liste

Orientiert an den Phasen aus dem Auftrag: MVP → Scheduler → LinkedIn/Facebook/X → KI.

### MVP (Muss) – Phase 4

| Feature | Begründung |
|---|---|
| Rollen anlegen/umbenennen/sortieren/löschen mit Farbe und Emoji; Rollen-Umschalter im Composer (Fractal-Popover) | Kern-Alleinstellung; kein Wettbewerber denkt in persönlichen Rollen. |
| Mehrere Profile pro Plattform je Rolle, einzeln abwählbar | Zwei Mastodon-Instanzen sind beim Nutzer Realität. |
| Login Mastodon (OAuth/PKCE über Systembrowser, Redirect-Fallback wie Newsflash) und Bluesky (App-Passwort bzw. OAuth) | Frei zugängliche APIs, keine Kosten, keine App-Review. |
| Verbindungsstatus pro Profil, Token-Erneuerung, Tokens nur in libsecret | Vertrauen und Sicherheit; Fehlerquelle Nr. 1 bei allen Tools. |
| Composer: Haupttext + Varianten mit Erben/„Anpassen“ (Postiz-Modell) | Ohne Varianten ist Crossposting zwischen 300 und 500 Zeichen unbrauchbar. |
| Exakte Live-Zähler je Profil (Bluesky Grapheme, Mastodon Instanzlimit, URL = 23, CW zählt mit), `accent`/`warning`/`error`-Klassen, Blockieren bei Überschreitung | Kernversprechen „einmal schreiben, überall korrekt“. |
| Medien per Drag & Drop, Zwischenablage, GtkFileDialog; Umsortieren | Grundfunktion, bei Tuba gesehen. |
| **Alt-Text-Pflicht** mit ALT-Badge (Tuba), Vorbefüllung aus EXIF/XMP, Längenprüfung je Plattform, Senden gesperrt bis vollständig | Alleinstellungsmerkmal; Barrierefreiheit ist im Fediverse Norm. |
| Vorschaukachel je Profil (Avatar, Name, Handle, Kürzung, Bildraster, CW, Link-Card nach Share-Preview-Logik) | Fehler vor dem Posten sehen; Publer/Typefully zeigen, dass das geschätzt wird. |
| Mastodon-Optionen: CW (Revealer), Sichtbarkeit, Sprache | Ohne CW/Sichtbarkeit ist die App für Fediverse-Nutzer zweitklassig. |
| Validierungsliste vor dem Senden (alle Probleme pro Plattform) | Bündelt Zähler, Alt-Text, Medienlimits. |
| Sofortiges Posten parallel, Ergebnis pro Profil mit Link, „Erneut versuchen“ einzeln | Teilfehler sind normal; SocialSox-Verlauf als Vorbild. |
| Entwürfe mit Autosave und Wiederherstellung (Apostrophe) | Datenverlust ist der größte Ärger beim Schreiben. |
| Adaptives Layout bis 360 px: Vorschau neben dem Editor bzw. im Bottom-Sheet | Vorgabe; Tuba/Apostrophe zeigen den Weg. |

### V1 (Soll) – Phasen 5 und 6

| Feature | Begründung |
|---|---|
| Planen mit Datum/Uhrzeit/Zeitzone: Errands-Presets + GtkCalendar + Zeitzonen-ComboRow (Tuba), Split-Button „Planen…“ | Zweithäufigster Anwendungsfall (Blogartikel morgens ankündigen). |
| Hintergrunddienst (systemd --user Timer bzw. Background-Portal), postet auch bei geschlossener GUI | Größter Vorteil gegenüber SocialSox und crossposter, die nur bei laufender App planen. |
| Verpasste Posts nach Suspend melden und nachfragen (konfigurierbar) | Kein stilles Nachsenden veralteter Inhalte. |
| Ansicht „Geplant“ als nach Tagen gruppierte Liste mit Filter Rolle/Plattform; bearbeiten, verschieben, pausieren, sofort posten, duplizieren, löschen mit Rückgängig-Toast | Verwaltung ist Pflicht, sobald geplant wird. |
| Ansicht „Veröffentlicht“ mit Links, optional Löschen auf der Plattform | Nachvollziehbarkeit. |
| GNotification bei Erfolg/Fehler | Hintergrunddienst braucht Rückmeldung. |
| Thread-Aufteilung: manuell per Trenner und Auto-Split an Absatz/Satz/Wort, (1/n) optional, Vorschau pro Teil | Typefully/Bluestodon-Stärke; nötig bei 300 Zeichen auf Bluesky. |
| LinkedIn (persönliches Profil über `w_member_social`, Self-Serve) | Ohne Review verfügbar; wichtig für berufliche Rollen. |
| Facebook **nur Seiten** (Graph API, App-Review) mit klarer Erklärung im Login | Private Profile sind per API unmöglich; Erwartung früh steuern. |
| X mit eigener Developer-App (Seite „Eigene App-Zugangsdaten“ nach Newsflash) und Kostenhinweis | Pay-per-Use seit Februar 2026; Nutzer zahlt selbst, muss es wissen. |
| Signatur/Hashtag-Block pro Rolle | Postiz-Idee, spart Routinearbeit. |

### Später (Kann) – Phase 7 und danach

| Feature | Begründung |
|---|---|
| KI-Assistent (Gemini/OpenAI/Grok): umformulieren, korrigieren, übersetzen, an Plattform anpassen, Hashtag-Chips, Alt-Text per Vision, Stil-Prompt pro Rolle; nur Vorschläge, Datenschutzhinweis, komplett abschaltbar | Mehrwert, aber nicht Kern; Datenschutz verlangt Opt-in. |
| Buffer-Queue: Wochen-Slots pro Rolle, „Nächster freier Slot“, „Ganz nach vorn“ | Lohnt erst bei regelmäßigem Posten; baut auf dem Scheduler auf. |
| Kalenderansicht Monat/Woche mit Drag & Drop (Postiz) | Liste reicht für den Anfang; Kalender ist aufwendig und auf 360 px schwierig. |
| Weitere Netze: Threads, Pixelfed (Fedica-Niveau) | Plugin-Schnittstelle macht es billig; Bedarf erst prüfen. |
| Blog-Integration: Artikel-URL einfügen → Titel/Teaser/Bild aus Open Graph vorbefüllen | Passt zu linuxundich/tuxsucht. |
| Vorlagen pro Rolle | Wiederkehrende Formate. |
| Basis-Kennzahlen (Likes/Boosts) im Verlauf | Nur wenn billig über die APIs zu holen; keine Analytics-Suite. |
| Wiederholende Posts | Selten gebraucht, Spam-Nähe. |

---

## 5. Abgrenzung und Alleinstellungsmerkmal

**Positionierung:** Der persönliche Crossposter für den GNOME-Desktop – für
Menschen mit mehreren Rollen (privat, Blog, Projekt), nicht für
Marketing-Teams.

1. **Einzige native GTK4/libadwaita-Crossposting-App.** Weder auf Flathub noch
   auf GitHub existiert ein GNOME-Crossposter. Die Web-Tools laufen im
   Browser, SocialSox ist Electron, Croissant und Bluestodon gibt es nur für
   Apple-Plattformen.
2. **Lokal, privat, ohne Server und ohne Abo.** Tokens im Secret Service,
   Daten in SQLite. Im Unterschied zu Postiz/Mixpost kein Docker-Stack, im
   Unterschied zu Buffer/Publer keine Abrechnung pro Kanal. Planung trotzdem
   zuverlässig über einen systemd-User-Dienst – das kann kein anderes
   Desktop-Tool.
3. **Rollen als Ordnungsprinzip.** Rolle wählen → passende Profile, Signatur,
   Zeitslots und KI-Tonalität sind gesetzt. Typefully („Social Sets“) und
   Croissant (Gruppen) kommen am nächsten, aber ohne Stil und Slots je Rolle.
4. **Alt-Text-Pflicht als Grundhaltung.** Kein Wettbewerber erzwingt
   Alt-Texte. Wir blockieren das Senden, helfen aber mit EXIF-Vorbefüllung und
   optionalem KI-Vorschlag. Das passt zur Fediverse-Kultur und zu GNOMEs
   Barrierefreiheitsanspruch.
5. **Fediverse und Bluesky zuerst, korrekt gezählt.** Instanzlimits per
   `/api/v2/instance`, Bluesky-Grapheme, X-Gewichtung, CW und Sichtbarkeit sind
   erstklassig, nicht nachgerüstet. Hootsuite kann nicht einmal auf Mastodon
   posten, Mixpost Lite nicht auf Bluesky.
6. **Ehrlich zu Plattformgrenzen.** Facebook nur Seiten, X mit eigener App und
   sichtbaren Kosten, LinkedIn über Self-Serve – erklärt im Login statt
   versteckt in Fehlermeldungen. Keine inoffiziellen Cookie-Integrationen.

**Bewusst außerhalb des Fokus:** Timelines/Lesen (dafür gibt es Tuba und
Hangar), Analytics, Team-Freigaben, Inbox, KI-Bildgenerierung.

**Risiken:** Pflegeaufwand bei Facebook/X-API-Änderungen; X-Kosten können
Nutzer abschrecken; Bluesky-OAuth und Mastodon-Instanzvielfalt verlangen
robuste Login-Flows. Gegenmittel: Plattformen als austauschbare Plugins, X und
Facebook erst nach stabilem MVP.

---

## Quellen

Kommerzielle Anbieter
- [Buffer Pricing](https://buffer.com/pricing)
- [Buffer: Setting up timezones and posting schedules](https://support.buffer.com/en-us/articles/setting-up-your-timezones-and-posting-schedules-P4iSag90Fl)
- [Buffer: Scheduling posts](https://support.buffer.com/en-us/articles/scheduling-posts-4Qdld7giAZ)
- [Buffer: Adding alt text to your images](https://support.buffer.com/article/618-adding-alt-text-to-your-images)
- [Buffer: Schedule to Bluesky](https://buffer.com/resources/schedule-to-bluesky/)
- [Hootsuite Plans](https://www.hootsuite.com/plans)
- [Hootsuite Bluesky](https://www.hootsuite.com/bluesky)
- [Fedica: How to schedule Mastodon posts in Hootsuite](https://fedica.com/blog/how-to-schedule-mastodon-posts-in-hootsuite/) (Mastodon bei Hootsuite nur Listening)
- [Typefully](https://typefully.com/)
- [SocialRails: Typefully Pricing 2026](https://socialrails.com/blog/typefully-pricing), [Kleo: Typefully Review](https://kleo.so/blog/typefully-review), [Toolworthy: Typefully Review](https://www.toolworthy.ai/tool/typefully)
- [Fedica: Supported platforms](https://fedica.com/platforms/)
- [SocialRails: Fedica Pricing 2026](https://socialrails.com/blog/fedica-pricing), [Fedica Review](https://bestsocialmediascheduler.com/reviews/fedica)
- [Publer: Threads für X, Threads, Mastodon, Bluesky](https://publer.com/blog/schedule-threads-for-twitter-x-mastodon-bluesky/)
- [Publer Bluesky-Integration](https://publer.com/integrations/bluesky)
- [Costbench: Publer Pricing 2026](https://costbench.com/software/social-media-management/publer/), [G2: Publer Pricing](https://www.g2.com/products/publer/pricing)

Open Source / selbst gehostet
- [Postiz-Dokumentation (Index)](https://docs.postiz.com/llms.txt)
- [Postiz: Global vs per-channel content](https://docs.postiz.com/general/composer/global-vs-per-channel.md)
- [Postiz: Posting time slots](https://docs.postiz.com/general/channels/time-slots.md)
- [Postiz: Writing the post](https://docs.postiz.com/general/composer/writing.md)
- [Postiz: Images and video](https://docs.postiz.com/general/composer/media.md)
- [Postiz: Plans and limits](https://docs.postiz.com/cloud/plans.md)
- [Postiz docker-compose.yaml](https://github.com/gitroomhq/postiz-app/blob/main/docker-compose.yaml)
- [TeqVolt: Postiz 29.6k Stars](https://teqvolt.com/open-source/postiz-29-6k-star-open-source-social-scheduler-buffer-alternative)
- [Mixpost Pricing](https://mixpost.app/pricing), [Mixpost](https://mixpost.app/)

Nischen-Crossposter und Tools
- [Croissant](https://anilineapps.com/croissant.html), [TechCrunch: Croissant debuts](https://techcrunch.com/2024/10/01/croissant-debuts-a-cross-posting-app-for-threads-bluesky-and-mastodon/)
- [Bluestodon](https://bluestodon.app/), [App Store](https://apps.apple.com/us/app/bluestodon-thread-splitter/id6767534644)
- [TechCrunch: Openvibe](https://techcrunch.com/2024/07/09/openvibe-combines-mastodon-bluesky-and-nostr-into-one-social-app), [Openvibe unterstützt Threads](https://techcrunch.com/2024/11/01/cross-posting-social-app-openvibe-now-supports-threads-too)
- [SocialSox](https://github.com/burninc0de/socialsox)
- [Crossposter (apoorvdarshan)](https://github.com/apoorvdarshan/crossposter)
- [crosspost (humanwhocodes)](https://github.com/humanwhocodes/crosspost)
- [toot](https://github.com/ihabunek/toot)
- [barkr](https://github.com/aitorres/barkr), [bluesky-crossposter](https://github.com/Linus2punkt0/bluesky-crossposter), [skymoth](https://github.com/thilobillerbeck/skymoth), [mastodon-to-bluesky](https://github.com/mauricerenck/mastodon-to-bluesky)
- [Sociabli bei bskyinfo](https://www.bskyinfo.com/tools/sociabli/), [sociab.li](https://sociab.li/)
- [Flare](https://github.com/DimensionDev/Flare), [CrispDeck](https://github.com/CrispStrobe/CrispDeck)
- [Hangar](https://github.com/sethcottle/hangar), [Skeetdeck](https://github.com/mary-ext/skeetdeck)
- Flathub-Suche über `https://flathub.org/api/v2/search` (Abfragen: crosspost, bluesky, mastodon, fediverse, social media, twitter, linkedin, post, schedule)

GNOME/KDE-Vorbilder
- [Tuba Releases](https://github.com/GeopJr/Tuba/releases), Quellcode `data/ui/dialogs/composer.ui`, `data/ui/dialogs/schedule.ui`, `src/Dialogs/Composer/Dialog.vala`, `src/Dialogs/Composer/Attachment.vala`
- [OMG! Ubuntu: Tuba 0.10](https://www.omgubuntu.co.uk/2025/08/tuba-0-10-mastodon-client-linux-new-features), [LWN: Tuba 0.11](https://lwn.net/Articles/1089537/), [OMG! Ubuntu: Tuba Scheduling & Drafts](https://www.omgubuntu.co.uk/2024/12/linux-mastodon-client-tuba-update-drafts)
- [Tokodon – KDE Applications](https://apps.kde.org/tokodon/)
- [Fractal Releases (GNOME GitLab)](https://gitlab.gnome.org/World/fractal/-/releases), Quellcode `src/account_switcher/*.blp`, `src/session_view/room_history/message_toolbar/attachment_dialog.blp`, `src/login/in_browser_page.blp`
- [Newsflash (GitLab)](https://gitlab.com/news-flash/news_flash_gtk), Quellcode `data/resources/ui_templates/login/{welcome,web,password,custom_api_secret}.blp`
- [Apostrophe (GNOME GitLab)](https://gitlab.gnome.org/World/apostrophe), `apostrophe/preview_layout_switcher.py`, Release-Notes 3.3/3.4
- [Errands](https://github.com/mrvladus/Errands), `errands/widgets/shared/datetime_picker.py`
- [GNOME Apps – Circle](https://apps.gnome.org/#circle), [GNOME Circle](https://circle.gnome.org/)

Plattform-Rahmenbedingungen (Details in `docs/platforms.md`)
- [X API Pricing 2026 (Postproxy)](https://postproxy.dev/blog/x-api-pricing-2026/), [Blotato: X API Pricing](https://www.blotato.com/blog/twitter-api-pricing)
- [Postpeer: Facebook Posting API nur für Seiten](https://www.postpeer.dev/blog/best-facebook-posting-api), [Meta: Page Feed](https://developers.facebook.com/docs/graph-api/reference/page/feed/)
- [Microsoft Learn: Share on LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin)
