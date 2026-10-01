# Composer-Layout: Konzept zur Überarbeitung

Stand: 2026-10-01 · Anlass: Screenshot mit zwei Profilen. Der Editor wirkt
leer, die Vorschauspalte voll.

## Befund

1. **Der Editor endet zu früh.** Das Textfeld hat eine feste Mindesthöhe von
   180 px. Darunter folgt nur noch die Optionszeile, die untere Hälfte der
   Spalte bleibt leer.
2. **Die Elemente schweben lose.** Rolle, Chips, Varianten-Tabs, Textfeld, ein
   einzelnes Medien-Symbol und die Optionen stehen ohne gemeinsamen Rahmen
   untereinander.
3. **Die Vorschau zeigt alles in voller Länge.** Jede Kachel enthält den
   kompletten Text und eine Link-Karte mit 140 px hohem Bild, eine Kachel wird
   etwa 500 px hoch. Ab zwei Profilen muss man scrollen.
4. **Die Proportionen kippen.** Die Seitenleiste nimmt bis zu 40 % (max.
   440 px) ein und ist dicht gefüllt. Die Editorspalte ist breiter, aber leer.

## Konzept „Briefbogen und kompakte Vorschau“

### A – Der Editor wird eine durchgehende Karte

```
 🐧 Linux und Ich ▾   an  (● @linuxundich@social…) (● @linuxundich.de) (+)
┌──────────────────────────────────────────────────────────────┐
│ Haupttext   Mastodon   Bluesky                               │  ← Tabs als Kartenkopf
├──────────────────────────────────────────────────────────────┤
│ Dies ist Test …                                              │
│                                                              │  ← Textfeld wächst
│ https://linuxundich.de/…                                     │    mit dem Fenster
│ #Gnome #Linux                                                │    (vexpand)
│                                                              │
│ [img] [img] [ + ]                                            │  ← Medien in der Karte
├──────────────────────────────────────────────────────────────┤
│ 🖼  ⚠ CW  Deutsch ▾  Öffentlich ▾  Signatur        242 / 300 │  ← Werkzeugleiste
└──────────────────────────────────────────────────────────────┘
```

- **Kopfzeile wie bei E-Mails („Von … an …“).** Rolle und Profil-Chips stehen
  in einer Zeile über der Karte.
- **Eine Karte umschließt alles, was zum Text gehört.** Dazu zählen die
  Varianten-Tabs als Kartenkopf, das Textfeld, die Medienleiste und eine
  Werkzeugleiste am unteren Kartenrand.
- **Das Textfeld füllt die verfügbare Höhe** (`vexpand`, Mindesthöhe 240 px).
  So bleibt auf großen Fenstern kein Leerraum, auf kleinen scrollt das Textfeld
  selbst.
- **Die Werkzeugleiste sitzt unten in der Karte**, wie bei Tuba und Fractal.
  Sie enthält Medien hinzufügen, CW, Sprache, Sichtbarkeit und Signatur.
  Rechts steht der Zähler des strengsten Profils.
- **Das Banner der Varianten-Tabs** („verwendet den Haupttext / Anpassen“)
  wandert als schmale Infozeile in den Kartenkopf, statt als graues Banner
  darüber zu liegen.

### B – Die Vorschau wird standardmäßig kompakt

- **Text auf vier Zeilen begrenzt**, dahinter „… mehr“. Ein Klick klappt die
  Kachel auf.
- **Link-Karte kompakt:** Vorschaubild 56 × 56 links, Website und Titel
  rechts. In der vollen Ansicht bleibt die große Karte.
- **Bildraster** 96 px statt 120 bis 180 px hoch.
- **Im Kopf der Spalte gibt es den Schalter „Kompakt | Voll“** (GSettings
  `preview-density`). Die Statusleiste und das Zusammenfassen gleicher
  Darstellungen bleiben.
- **Ergebnis:** Etwa vier bis sechs Kacheln passen ohne Scrollen.

### C – Proportionen

- **Vorschauspalte:** `sidebar-width-fraction` 0,33, min. 300 px, max.
  380 px.
- **Editor:** `Adw.Clamp` mit max. 760 px, vertikal ohne Begrenzung. Auf sehr
  breiten Fenstern bleibt der Editor zentriert und lesbar, Leerraum gibt es
  dann nur seitlich.
- **Ränder:** Beide Spalten bekommen gleiche Abstände von 12 bis 18 px oben,
  damit die Überschriften auf einer Linie stehen.

### D – Schmales Layout

- **Die Werkzeugleiste bricht um** (`Adw.WrapBox`). Der Zähler bleibt rechts
  in der letzten Zeile.
- **Die Vorschau im Bottom Sheet** ist immer kompakt.

## Umsetzung (geschätzt)

| Schritt | Aufwand |
|---|---|
| Composer-Blueprint: Kopfzeile, Karte, Werkzeugleiste, vexpand | mittel |
| Varianten-Banner als Infozeile im Kartenkopf | klein |
| PreviewTile: Modus kompakt/voll, Zeilenbegrenzung, kompakte Link-Karte | mittel |
| GSettings-Schlüssel `preview-density`, Schalter in der Spalte | klein |
| Proportionen, Abstände, CSS, Prüfung hell/dunkel/schmal | klein |
