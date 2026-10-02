# Backlog

Stand: 2026-10-02, Version 0.2.1

## Veröffentlichung

- [ ] **AUR-Paket hochladen.** PKGBUILD und `.SRCINFO` für 0.2.1 liegen fertig
      in `build-aux/arch/` (Prüfsumme eingetragen).
- [ ] **Flathub-Einreichung** (optional). Das Release-Manifest
      `build-aux/flatpak/de.linuxundich.Dandelion.release.json` baut aus dem
      Git-Tag. Es fehlen die Verifizierung über
      `linuxundich.de/.well-known/org.flathub.VerifiedApps.txt` und der
      Pull-Request bei Flathub.

## Testen mit echten Konten (macht Christoph selbst)

- [ ] Mastodon und Bluesky anmelden und einen echten Beitrag senden, auch als
      Thread und mit Planung auf dem Mastodon-Server.
- [ ] Für LinkedIn, Facebook und X je eine eigene Entwickler-App anlegen und den
      Login testen.
- [ ] Den KI-Assistenten mit einem echten API-Schlüssel ausprobieren.

## Funktionen

- [ ] **Videos** für Bluesky, X, LinkedIn und Facebook. Bisher gehen Videos nur
      zu Mastodon.
- [ ] **Bluesky-OAuth** als Alternative zum App-Passwort, mit der
      Metadaten-Datei auf linuxundich.de.
- [ ] **Serverseitiges Planen bei Facebook** (optional; Mastodon ist erledigt).
- [ ] **Kleinigkeiten:**
  - [ ] Alt-Text aus den Bildmetadaten (EXIF) vorbelegen
  - [ ] X Premium mit bis zu 25.000 Zeichen einstellbar machen
  - [ ] LinkedIn-API-Version etwa jährlich nachziehen

## Erledigt

- [x] Phasen 1 bis 8 aus dem Auftrag (v0.1.0)
- [x] CHANGELOG angelegt (v0.2.0)
- [x] Thread-Aufteilung für Mastodon, Bluesky und X (v0.2.0)
- [x] Serverseitiges Planen bei Mastodon (v0.2.0)
- [x] Kalenderansicht und Zeitslots pro Rolle (v0.2.0)
- [x] Flatpak-Release-Manifest und weitergebbares Bundle mit Übersetzungen (v0.2.1)
- [x] Neues Icon „Strahlenkranz“ (v0.2.1)
- [x] GitHub-Releases v0.1.0, v0.2.0 und v0.2.1 (0.2.x mit Flatpak-Bundle)
