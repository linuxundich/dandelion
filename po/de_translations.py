#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Erzeugt bzw. aktualisiert po/de.po aus dandelion.pot und dem Wörterbuch unten.

    meson compile -C _build dandelion-pot && python3 po/de_translations.py

Einträge, die hier fehlen, bleiben unübersetzt (msgstr leer). Für neue
Texte das Wörterbuch ergänzen; bestehende Übersetzungen aus de.po bleiben
erhalten, wenn sie hier nicht vorkommen.
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent

DE: dict[str, str | tuple[str, str]] = {
    "Dandelion": "Dandelion",
    "Social Media Poster": "Social-Media-Poster",
    "Write once, post to Mastodon, Bluesky and more":
        "Einmal schreiben, auf Mastodon, Bluesky und mehr veröffentlichen",
    "Mastodon;Bluesky;Fediverse;Social;Post;Crosspost;Toot;":
        "Mastodon;Bluesky;Fediverse;Social;Post;Beitrag;Crossposting;Tröt;",
    "Write once, post everywhere": "Einmal schreiben, überall veröffentlichen",
    "Dandelion lets you write a post once and publish it to several social networks at the same time.":
        "Mit Dandelion schreibst du einen Beitrag einmal und veröffentlichst ihn gleichzeitig in mehreren sozialen Netzwerken.",
    "Roles group your profiles, for example private and work accounts":
        "Rollen bündeln deine Profile, etwa private und berufliche Konten",
    "Several accounts per network, such as two Mastodon instances":
        "Mehrere Konten pro Netzwerk, zum Beispiel zwei Mastodon-Instanzen",
    "Exact character counters and a preview for every profile":
        "Exakte Zeichenzähler und eine Vorschau für jedes Profil",
    "Alt text for images is required where it matters":
        "Alt-Texte für Bilder sind Pflicht, wo es darauf ankommt",
    "Credentials are stored in the system keyring":
        "Zugangsdaten liegen im Schlüsselbund des Systems",
    "Christoph Langner": "Christoph Langner",
    "First preview with Mastodon and Bluesky.": "Erste Vorschau mit Mastodon und Bluesky.",
    "Window width": "Fensterbreite",
    "Window height": "Fensterhöhe",
    "Window maximized": "Fenster maximiert",
    "Show the drafts sidebar": "Seitenleiste mit Entwürfen anzeigen",
    "Show the preview column": "Vorschauspalte anzeigen",
    "UUID of the last used role": "UUID der zuletzt verwendeten Rolle",
    "Require alt text on every platform": "Alt-Text auf allen Plattformen verlangen",
    "Mastodon always requires alt text. If enabled, missing alt text blocks posting on all platforms instead of only showing a warning.":
        "Mastodon verlangt immer einen Alt-Text. Wenn aktiviert, blockiert ein fehlender Alt-Text das Senden auf allen Plattformen, statt nur zu warnen.",
    "Check spelling": "Rechtschreibung prüfen",
    "Append the role signature to new posts": "Signatur der Rolle an neue Beiträge anhängen",
    "Numbering of thread parts": "Nummerierung der Thread-Teile",
    "Delete empty drafts after this many days (0 = never)":
        "Leere Entwürfe nach so vielen Tagen löschen (0 = nie)",
    "Notify on successful scheduled posts": "Bei erfolgreich geplanten Beiträgen benachrichtigen",
    "Notify on failed scheduled posts": "Bei fehlgeschlagenen geplanten Beiträgen benachrichtigen",
    "What to do with missed scheduled posts": "Umgang mit verpassten geplanten Beiträgen",
    "Minutes after which a scheduled post counts as missed":
        "Minuten, nach denen ein geplanter Beitrag als verpasst gilt",
    "Default time zone (empty = system)": "Standard-Zeitzone (leer = System)",
    "Enable AI features": "KI-Funktionen aktivieren",
    "Drafts": "Entwürfe",
    "New Post": "Neuer Beitrag",
    "Main Menu": "Hauptmenü",
    "_Publish": "_Veröffentlichen",
    "Publish to all selected profiles": "Auf allen ausgewählten Profilen veröffentlichen",
    "Search": "Suchen",
    "Compose": "Verfassen",
    "Published": "Veröffentlicht",
    "_Send": "_Senden",
    "_New Post": "_Neuer Beitrag",
    "_Roles and Profiles": "_Rollen und Profile",
    "_Preferences": "_Einstellungen",
    "_Keyboard Shortcuts": "_Tastenkürzel",
    "_About Dandelion": "_Info zu Dandelion",
    "No Drafts": "Keine Entwürfe",
    "Posts you start writing are saved here automatically.":
        "Beiträge, die du zu schreiben beginnst, werden hier automatisch gespeichert.",
    "Welcome to Dandelion": "Willkommen bei Dandelion",
    "Add your Mastodon and Bluesky profiles to write a post once and publish it everywhere.":
        "Füge deine Mastodon- und Bluesky-Profile hinzu, um einen Beitrag einmal zu schreiben und überall zu veröffentlichen.",
    "_Add Profile": "Profil _hinzufügen",
    "Preview": "Vorschau",
    "Role": "Rolle",
    "Problems": "Probleme",
    "Content warning": "Inhaltswarnung",
    "Post text": "Beitragstext",
    "Add Images": "Bilder hinzufügen",
    "Content Warning": "Inhaltswarnung",
    "CW": "CW",
    "Language": "Sprache",
    "Visibility on Mastodon": "Sichtbarkeit auf Mastodon",
    "Content label for Bluesky": "Inhaltslabel für Bluesky",
    "Append the signature of this role": "Signatur dieser Rolle anhängen",
    "Signature": "Signatur",
    "_Manage Roles": "Rollen _verwalten",
    "Search published posts": "Veröffentlichte Beiträge durchsuchen",
    "Nothing Published Yet": "Noch nichts veröffentlicht",
    "Published posts appear here with links to every platform.":
        "Veröffentlichte Beiträge erscheinen hier mit Links zu jeder Plattform.",
    "Roles": "Rollen",
    "A role bundles profiles, language, visibility and a signature, for example “Private” or “Blog”.":
        "Eine Rolle bündelt Profile, Sprache, Sichtbarkeit und eine Signatur, zum Beispiel „Privat“ oder „Blog“.",
    "Profiles": "Profile",
    "Login data is stored in the system keyring.": "Anmeldedaten liegen im Schlüsselbund des Systems.",
    "General": "Allgemein",
    "Writing": "Schreiben",
    "Require Alt Text Everywhere": "Alt-Text überall verlangen",
    "Mastodon always requires alt text. Other platforms only show a warning unless this is enabled.":
        "Mastodon verlangt immer einen Alt-Text. Andere Plattformen zeigen nur eine Warnung, solange dies nicht aktiviert ist.",
    "Check Spelling": "Rechtschreibung prüfen",
    "Append Role Signature": "Signatur der Rolle anhängen",
    "Can be turned off for each post": "Lässt sich für jeden Beitrag abschalten",
    "Show Preview": "Vorschau anzeigen",
    "Delete Empty Drafts After": "Leere Entwürfe löschen nach",
    "Days, 0 keeps them forever": "Tagen, 0 behält sie für immer",
    "Appearance": "Darstellung",
    "Name": "Name",
    "Symbol": "Symbol",
    "Choose Emoji": "Emoji wählen",
    "Color": "Farbe",
    "Profiles in this role. Preselected profiles are switched on for every new post.":
        "Profile in dieser Rolle. Vorausgewählte Profile sind bei jedem neuen Beitrag eingeschaltet.",
    "Defaults": "Voreinstellungen",
    "Signature or Hashtags": "Signatur oder Hashtags",
    "Delete Role": "Rolle löschen",
    "Profile": "Profil",
    "Connection": "Verbindung",
    "Status": "Status",
    "Limits": "Limits",
    "Check Connection": "Verbindung prüfen",
    "Sign In Again": "Erneut anmelden",
    "Display": "Anzeige",
    "Name in Dandelion": "Name in Dandelion",
    "Remove Profile": "Profil entfernen",
    "Add Profile": "Profil hinzufügen",
    "Choose the network of the profile.": "Wähle das Netzwerk des Profils.",
    "And other Fediverse servers": "Und andere Fediverse-Server",
    "Sign in with an app password": "Anmeldung mit App-Passwort",
    "Coming Later": "Folgt später",
    "Facebook Page": "Facebook-Seite",
    "Enter the address of your server. Dandelion opens the login page in your browser.":
        "Gib die Adresse deines Servers ein. Dandelion öffnet die Anmeldeseite in deinem Browser.",
    "Server": "Server",
    "_Sign In With Browser": "Im Browser _anmelden",
    "Waiting for the browser": "Warte auf den Browser",
    "Enter Code Manually": "Code manuell eingeben",
    "If the browser cannot return to Dandelion": "Falls der Browser nicht zu Dandelion zurückkehren kann",
    "Code or address from the browser": "Code oder Adresse aus dem Browser",
    "Open Login Page Again": "Anmeldeseite erneut öffnen",
    "Use an app password instead of your main password. You can revoke it at any time in the Bluesky settings.":
        "Verwende ein App-Passwort statt deines Hauptpassworts. Du kannst es jederzeit in den Bluesky-Einstellungen widerrufen.",
    "Handle, e.g. name.bsky.social": "Handle, z. B. name.bsky.social",
    "Handle or profile address": "Handle oder Profiladresse",
    "App Password": "App-Passwort",
    "Create App Password": "App-Passwort erstellen",
    "_Sign In": "_Anmelden",
    "Profile Added": "Profil hinzugefügt",
    "Use in Roles": "In Rollen verwenden",
    "_Done": "_Fertig",
    "Alt Text": "Alt-Text",
    "_Cancel": "_Abbrechen",
    "Describe the image for people who cannot see it.":
        "Beschreibe das Bild für Menschen, die es nicht sehen können.",
    "Alt text": "Alt-Text",
    "Publishing": "Veröffentlichen",
    "Publish": "Veröffentlichen",
    "Save Draft": "Entwurf speichern",
    "Choose Role": "Rolle wählen",
    "Undo": "Rückgängig",
    "Redo": "Wiederholen",
    "View": "Ansicht",
    "Show Drafts": "Entwürfe anzeigen",
    "Preferences": "Einstellungen",
    "Keyboard Shortcuts": "Tastenkürzel",
    "Close Window": "Fenster schließen",
    "Quit": "Beenden",
    "Write once, post to Mastodon, Bluesky and more.":
        "Einmal schreiben, auf Mastodon, Bluesky und mehr veröffentlichen.",
    "translator-credits": "Christoph Langner",
    "Personal": "Privat",
    "{n} profile": ("{n} Profil", "{n} Profile"),
    "No Role": "Keine Rolle",
    "Role: {name}": "Rolle: {name}",
    "Append signature: {signature}": "Signatur anhängen: {signature}",
    "More Profiles": "Weitere Profile",
    "Own Text for This Profile": "Eigener Text für dieses Profil",
    "Role changed to “{name}”": "Rolle zu „{name}“ gewechselt",
    "_Undo": "_Rückgängig",
    "Main Text": "Haupttext",
    "{name} uses its own text.": "{name} verwendet einen eigenen Text.",
    "The main text has changed since.": "Der Haupttext wurde seitdem geändert.",
    "_Use Main Text": "Haupttext _übernehmen",
    "{name} uses the main text.": "{name} verwendet den Haupttext.",
    "_Customize": "_Anpassen",
    "Own text discarded": "Eigener Text verworfen",
    "Cannot publish: {n} problem": ("Veröffentlichen nicht möglich: {n} Problem",
                                    "Veröffentlichen nicht möglich: {n} Probleme"),
    "within the limit": "innerhalb des Limits",
    "over the limit": "über dem Limit",
    "close to the limit": "nahe am Limit",
    "{platform} {handle}: {used} of {limit} characters, {state}":
        "{platform} {handle}: {used} von {limit} Zeichen, {state}",
    "All Profiles": "Alle Profile",
    "{n} problem": ("{n} Problem", "{n} Probleme"),
    "No Preview": "Keine Vorschau",
    "Select a profile to see how the post will look.":
        "Wähle ein Profil, um zu sehen, wie der Beitrag aussehen wird.",
    "Images and Videos": "Bilder und Videos",
    "Could not add “{name}”": "„{name}“ konnte nicht hinzugefügt werden",
    "“{name}” is not an image or video": "„{name}“ ist kein Bild und kein Video",
    "Very tall or wide images are cropped in the timeline preview on most platforms.":
        "Sehr hohe oder breite Bilder werden in der Timeline-Vorschau der meisten Plattformen beschnitten.",
    "Media removed": "Medium entfernt",
    "Empty Post": "Leerer Beitrag",
    "Delete Draft": "Entwurf löschen",
    "Draft deleted": "Entwurf gelöscht",
    "Draft saved": "Entwurf gespeichert",
    "Publish Despite Warnings?": "Trotz Warnungen veröffentlichen?",
    "_Publish Anyway": "_Trotzdem veröffentlichen",
    "This post is already being published": "Dieser Beitrag wird bereits veröffentlicht",
    "Published on {n} profile": ("Auf {n} Profil veröffentlicht", "Auf {n} Profilen veröffentlicht"),
    "Published on {ok} of {total} profiles": "Auf {ok} von {total} Profilen veröffentlicht",
    "_Details": "_Details",
    "Publishing failed": "Veröffentlichen fehlgeschlagen",
    "No Results": "Keine Ergebnisse",
    "Try a different search.": "Versuche eine andere Suche.",
    "Post": "Beitrag",
    "{n} published": "{n} veröffentlicht",
    "{n} failed": "{n} fehlgeschlagen",
    "Open Post": "Beitrag öffnen",
    "Copy Link": "Link kopieren",
    "Delete on {platform}": "Auf {platform} löschen",
    "{platform} · deleted": "{platform} · gelöscht",
    "Not published": "Nicht veröffentlicht",
    "_Retry": "_Erneut versuchen",
    "Use as New Draft": "Als neuen Entwurf verwenden",
    "Link copied": "Link kopiert",
    "Delete Post on {platform}?": "Beitrag auf {platform} löschen?",
    "The post will be removed from {handle}. This cannot be undone.":
        "Der Beitrag wird von {handle} entfernt. Das lässt sich nicht rückgängig machen.",
    "_Delete": "_Löschen",
    "Post deleted on {platform}": "Beitrag auf {platform} gelöscht",
    "The post could not be deleted": "Der Beitrag konnte nicht gelöscht werden",
    "Blue": "Blau",
    "Teal": "Blaugrün",
    "Green": "Grün",
    "Yellow": "Gelb",
    "Orange": "Orange",
    "Red": "Rot",
    "Pink": "Pink",
    "Purple": "Lila",
    "Slate": "Schiefer",
    "Add Role": "Rolle hinzufügen",
    "Move Up": "Nach oben",
    "Move Down": "Nach unten",
    "More": "Mehr",
    "New Role": "Neue Rolle",
    "No profiles yet": "Noch keine Profile",
    "Include {handle} in this role": "{handle} in diese Rolle aufnehmen",
    "Preselected for new posts": "Bei neuen Beiträgen vorausgewählt",
    "Preselect {handle}": "{handle} vorauswählen",
    "Delete Role “{name}”?": "Rolle „{name}“ löschen?",
    "The profiles stay available in the other roles.":
        "Die Profile bleiben in den anderen Rollen verfügbar.",
    "{n} character": ("{n} Zeichen", "{n} Zeichen"),
    "{n} image": ("{n} Bild", "{n} Bilder"),
    "alt text up to {n}": "Alt-Text bis {n}",
    "Connection checked": "Verbindung geprüft",
    "Remove Profile?": "Profil entfernen?",
    "{handle} is removed from Dandelion and its login data is deleted from the keyring. Published posts stay online.":
        "{handle} wird aus Dandelion entfernt und die Anmeldedaten werden aus dem Schlüsselbund gelöscht. Veröffentlichte Beiträge bleiben online.",
    "_Remove": "_Entfernen",
    "Sign-in failed.": "Anmeldung fehlgeschlagen.",
    "The server denied the sign-in: {reason}": "Der Server hat die Anmeldung abgelehnt: {reason}",
    "The sign-in response did not match. Please try again.":
        "Die Antwort auf die Anmeldung passte nicht. Bitte versuche es erneut.",
    "{n} / {max}": "{n} / {max}",
    "{platform} has the strictest limit": "{platform} hat das strengste Limit",
    "{n} characters": "{n} Zeichen",
    "Uploading media {i} of {n}": "Lade Medium {i} von {n} hoch",
    "Preparing": "Wird vorbereitet",
    "Failed": "Fehlgeschlagen",
    "Waiting": "Wartet",
    "Published on {ok} of {total} profile.": ("Auf {ok} von {total} Profil veröffentlicht.",
                                              "Auf {ok} von {total} Profilen veröffentlicht."),
    "Yesterday": "Gestern",
    "Today": "Heute",
    "Public": "Öffentlich",
    "Quiet Public": "Still öffentlich",
    "Followers Only": "Nur Follower",
    "Mentioned Only": "Nur Erwähnte",
    "No Label": "Kein Label",
    "Suggestive": "Anzüglich",
    "Nudity": "Nacktheit",
    "Adult Content": "Inhalte für Erwachsene",
    "Graphic Media": "Drastische Darstellungen",
    "Signed in": "Angemeldet",
    "Sign-in failed": "Anmeldung fehlgeschlagen",
    "You can close this tab and return to Dandelion.":
        "Du kannst diesen Tab schließen und zu Dandelion zurückkehren.",
    "Return to Dandelion and try again.": "Kehre zu Dandelion zurück und versuche es erneut.",
    "Not signed in. Please sign in again in the preferences.":
        "Nicht angemeldet. Bitte melde dich in den Einstellungen erneut an.",
    "The post is empty.": "Der Beitrag ist leer.",
    "The text is {n} character too long.": ("Der Text ist {n} Zeichen zu lang.",
                                            "Der Text ist {n} Zeichen zu lang."),
    "The text uses too many bytes (emoji and special characters count more).":
        "Der Text belegt zu viele Bytes (Emoji und Sonderzeichen zählen mehr).",
    "At most {n} image is allowed.": ("Höchstens {n} Bild ist erlaubt.",
                                      "Höchstens {n} Bilder sind erlaubt."),
    "Videos are not supported for {platform} yet.":
        "Videos werden für {platform} noch nicht unterstützt.",
    "At most {n} video is allowed.": ("Höchstens {n} Video ist erlaubt.",
                                      "Höchstens {n} Videos sind erlaubt."),
    "Images and videos cannot be combined.": "Bilder und Videos lassen sich nicht kombinieren.",
    "The file format of media {n} is not supported.":
        "Das Dateiformat von Medium {n} wird nicht unterstützt.",
    "Media {n} is larger than {size}.": "Medium {n} ist größer als {size}.",
    "Media {n} has no alt text.": "Medium {n} hat keinen Alt-Text.",
    "The alt text of media {n} is longer than {max} characters.":
        "Der Alt-Text von Medium {n} ist länger als {max} Zeichen.",
    "Select at least one profile.": "Wähle mindestens ein Profil.",
    "The profile no longer exists.": "Das Profil existiert nicht mehr.",
    "An unexpected error occurred.": "Ein unerwarteter Fehler ist aufgetreten.",
    "The login has expired. Please sign in again.":
        "Die Anmeldung ist abgelaufen. Bitte melde dich erneut an.",
    "The server could not find the requested resource.":
        "Der Server konnte die angeforderte Ressource nicht finden.",
    "The file is too large for this server.": "Die Datei ist zu groß für diesen Server.",
    "The server rejected the post.": "Der Server hat den Beitrag abgelehnt.",
    "Too many requests. Please try again later.":
        "Zu viele Anfragen. Bitte versuche es später erneut.",
    "The server is currently unavailable.": "Der Server ist derzeit nicht erreichbar.",
    "Unexpected answer from the server (HTTP {status}).":
        "Unerwartete Antwort vom Server (HTTP {status}).",
    "Please enter the address of your Mastodon server, for example mastodon.social.":
        "Bitte gib die Adresse deines Mastodon-Servers ein, zum Beispiel mastodon.social.",
    "No Mastodon server was found at {instance}.": "Unter {instance} wurde kein Mastodon-Server gefunden.",
    "No login data found. Please sign in again.":
        "Keine Anmeldedaten gefunden. Bitte melde dich erneut an.",
    "The server could not be reached. Check your internet connection.":
        "Der Server ist nicht erreichbar. Prüfe deine Internetverbindung.",
    "The server rejected the post: {reason}": "Der Server hat den Beitrag abgelehnt: {reason}",
    "Bluesky could not be reached. Check your internet connection.":
        "Bluesky ist nicht erreichbar. Prüfe deine Internetverbindung.",
    "Bluesky did not accept the login. Check the handle and the app password.":
        "Bluesky hat die Anmeldung nicht akzeptiert. Prüfe Handle und App-Passwort.",
    "This Bluesky account has been suspended.": "Dieses Bluesky-Konto wurde gesperrt.",
    "A file is too large for Bluesky.": "Eine Datei ist zu groß für Bluesky.",
    "Bluesky rejected the post: {reason}": "Bluesky hat den Beitrag abgelehnt: {reason}",
    "The handle {handle} was not found on Bluesky.":
        "Das Handle {handle} wurde auf Bluesky nicht gefunden.",
    "Unsupported identity: {did}": "Nicht unterstützte Identität: {did}",
    "No Bluesky server (PDS) was found for this account.":
        "Für dieses Konto wurde kein Bluesky-Server (PDS) gefunden.",
    "Videos are not supported for Bluesky yet.": "Videos werden für Bluesky noch nicht unterstützt.",
    "Edit alt text": "Alt-Text bearbeiten",
    "Media {n}, edit alt text": "Medium {n}, Alt-Text bearbeiten",
    "Alt text present for media {n}": "Alt-Text für Medium {n} vorhanden",
    "Alt text missing for media {n}": "Alt-Text für Medium {n} fehlt",
    "Remove": "Entfernen",
    "Remove media {n}": "Medium {n} entfernen",
    "Edit Alt Text": "Alt-Text bearbeiten",
    "Move Left": "Nach links",
    "Move Right": "Nach rechts",
    "Preview for {handle} on {platform}": "Vorschau für {handle} auf {platform}",
    "Show more": "Mehr anzeigen",
    "Show": "Anzeigen",
    "Hide": "Verbergen",
    "signed in": "angemeldet",
    "login expires soon": "Anmeldung läuft bald ab",
    "signed out": "abgemeldet",
    "connection error": "Verbindungsfehler",
    "selected": "ausgewählt",
    "not selected": "nicht ausgewählt",
    "Profile {handle} on {platform}, {status}, {state}":
        "Profil {handle} auf {platform}, {status}, {state}",
    # Phase 5: Planen
    "More Publishing Options": "Weitere Optionen zum Veröffentlichen",
    "Scheduled": "Geplant",
    "_Schedule…": "_Planen …",
    "_Unschedule": "Planung _aufheben",
    "Scheduling": "Planung",
    "Background Service": "Hintergrunddienst",
    "Publishes scheduled posts even when the Dandelion window is closed.":
        "Veröffentlicht geplante Beiträge auch, wenn das Fenster von Dandelion geschlossen ist.",
    "Publish in the Background": "Im Hintergrund veröffentlichen",
    "Next Post": "Nächster Beitrag",
    "Notifications": "Benachrichtigungen",
    "When a Scheduled Post Was Published": "Wenn ein geplanter Beitrag veröffentlicht wurde",
    "When a Scheduled Post Failed": "Wenn ein geplanter Beitrag fehlgeschlagen ist",
    "Missed Posts": "Verpasste Beiträge",
    "What happens when the computer was off or asleep at the planned time.":
        "Was passiert, wenn der Rechner zum geplanten Zeitpunkt aus war oder geschlafen hat.",
    "Action": "Aktion",
    "Ask": "Nachfragen",
    "Send Anyway": "Trotzdem senden",
    "Do Not Send": "Nicht senden",
    "Counts as Missed After": "Gilt als verpasst nach",
    "Minutes after the planned time": "Minuten nach dem geplanten Zeitpunkt",
    "Time Zone": "Zeitzone",
    "Default Time Zone": "Standard-Zeitzone",
    "Schedule Post": "Beitrag planen",
    "_Schedule": "_Planen",
    "Without the background service, posts are only sent while Dandelion is open.":
        "Ohne Hintergrunddienst werden Beiträge nur gesendet, solange Dandelion geöffnet ist.",
    "_Enable": "_Aktivieren",
    "Quick Choice": "Schnellauswahl",
    "Date": "Datum",
    "Time": "Uhrzeit",
    "Hour": "Stunde",
    "Minute": "Minute",
    "Scheduled posts are only sent while Dandelion is open.":
        "Geplante Beiträge werden nur gesendet, solange Dandelion geöffnet ist.",
    "_Enable Background Service": "Hintergrunddienst _aktivieren",
    "Nothing Scheduled": "Nichts geplant",
    "Use “Schedule…” next to the publish button to plan a post.":
        "Mit „Planen …“ neben dem Veröffentlichen-Knopf planst du einen Beitrag.",
    "_Write a Post": "Beitrag _verfassen",
    "Filter by role": "Nach Rolle filtern",
    "Filter by platform": "Nach Plattform filtern",
    "Schedule": "Planen",
    "Run without a window to publish scheduled posts":
        "Ohne Fenster laufen, um geplante Beiträge zu veröffentlichen",
    "A Scheduled Post Was Not Sent": ("Ein geplanter Beitrag wurde nicht gesendet",
                                      "{n} geplante Beiträge wurden nicht gesendet"),
    "The computer was off or asleep at the planned time.":
        "Der Rechner war zum geplanten Zeitpunkt aus oder im Ruhezustand.",
    "_Decide Later": "_Später entscheiden",
    "Move to _Drafts": "In _Entwürfe verschieben",
    "_Send Now": "Jetzt _senden",
    "This post has been published in the meantime": "Dieser Beitrag wurde inzwischen veröffentlicht",
    "Scheduled for {when}. Changes are saved automatically.":
        "Geplant für {when}. Änderungen werden automatisch gespeichert.",
    "Paused, planned for {when}.": "Pausiert, geplant für {when}.",
    "Missed, it was planned for {when}.": "Verpasst, geplant war {when}.",
    "Schedule removed, the post is a draft again": "Planung aufgehoben, der Beitrag ist wieder ein Entwurf",
    "Scheduled for {when}": "Geplant für {when}",
    "System ({zone})": "System ({zone})",
    "Not available: the systemd user instance cannot be reached.":
        "Nicht verfügbar: Die systemd-Benutzerinstanz ist nicht erreichbar.",
    "Active": "Aktiv",
    "Inactive: posts are only sent while Dandelion is open.":
        "Inaktiv: Beiträge werden nur gesendet, solange Dandelion geöffnet ist.",
    "Nothing scheduled": "Nichts geplant",
    "today": "heute",
    "tomorrow": "morgen",
    "{day} at {time}": "{day} um {time}",
    "In One Hour": "In einer Stunde",
    "This Evening, 18:00": "Heute Abend, 18:00",
    "Tomorrow, 08:00": "Morgen, 08:00",
    "Tomorrow, 12:00": "Morgen, 12:00",
    "Monday, 08:00": "Montag, 08:00",
    "This time is in the past.": "Dieser Zeitpunkt liegt in der Vergangenheit.",
    "Will be published {when}.": "Wird {when} veröffentlicht.",
    "That is {when} in your local time.": "Das ist {when} in deiner Ortszeit.",
    "All Roles": "Alle Rollen",
    "All Platforms": "Alle Plattformen",
    "Missed": "Verpasst",
    "Without Date": "Ohne Datum",
    "No Matches": "Keine Treffer",
    "No scheduled post matches the filter.": "Kein geplanter Beitrag passt zum Filter.",
    "Paused": "Pausiert",
    "Send _Now": "Jetzt _senden",
    "Edit": "Bearbeiten",
    "Change Time…": "Zeit ändern …",
    "Resume": "Fortsetzen",
    "Pause": "Pausieren",
    "Send Now": "Jetzt senden",
    "Duplicate": "Duplizieren",
    "Move to Drafts": "In Entwürfe verschieben",
    "Delete": "Löschen",
    "Actions": "Aktionen",
    "Rescheduled": "Neu geplant",
    "Resumed": "Fortgesetzt",
    "Publish Now?": "Jetzt veröffentlichen?",
    "The post will be published immediately instead of at the planned time.":
        "Der Beitrag wird sofort statt zum geplanten Zeitpunkt veröffentlicht.",
    "Copy created as draft": "Kopie als Entwurf angelegt",
    "Moved to drafts": "In Entwürfe verschoben",
    "Scheduled post deleted": "Geplanter Beitrag gelöscht",
    "Scheduled post published": "Geplanter Beitrag veröffentlicht",
    "{text}\nPublished on {n} profile.": ("{text}\nAuf {n} Profil veröffentlicht.",
                                          "{text}\nAuf {n} Profilen veröffentlicht."),
    "Sent late, it was planned for {time}.": "Verspätet gesendet, geplant war {time}.",
    "Scheduled post failed": "Geplanter Beitrag fehlgeschlagen",
    "{text}\nPublished on {ok} of {total} profiles.": "{text}\nAuf {ok} von {total} Profilen veröffentlicht.",
    "Details": "Details",
    "A scheduled post was not sent": "Ein geplanter Beitrag wurde nicht gesendet",
    "{text}\nIt was planned for {time}, but the computer was off or asleep.":
        "{text}\nGeplant war {time}, aber der Rechner war aus oder im Ruhezustand.",
    "Discard": "Verwerfen",
    "Dandelion publishes scheduled posts even when its window is closed.":
        "Dandelion veröffentlicht geplante Beiträge auch bei geschlossenem Fenster.",
    # Vorschau-Spalte
    "Status of all selected profiles": "Status aller ausgewählten Profile",
    "Show _All": "_Alle anzeigen",
    "Filtered: {name}": "Gefiltert: {name}",
    "{platform} · {n} profile": ("{platform} · {n} Profil", "{platform} · {n} Profile"),
    "{n} over the limit": ("{n} über dem Limit", "{n} über dem Limit"),
    # Layout: Composer-Karte und kompakte Vorschau
    "to": "an",
    "Compact": "Kompakt",
    "Full": "Voll",
    "Show less": "Weniger anzeigen",
    "Show compact preview tiles": "Kompakte Vorschaukacheln anzeigen",
    "Strictest limit: {platform} {handle}, {used} of {limit} characters":
        "Strengstes Limit: {platform} {handle}, {used} von {limit} Zeichen",
    # Phase 6: LinkedIn, Facebook, X
    "With Your Own Developer App": "Mit eigener Entwickler-App",
    "These networks only allow posting through an app that you register yourself.":
        "Diese Netzwerke erlauben das Posten nur über eine App, die du selbst registrierst.",
    "Personal profile": "Persönliches Profil",
    "Pages you manage, not personal profiles": "Seiten, die du verwaltest, keine privaten Profile",
    "Costs per post apply": "Kosten pro Beitrag",
    "Your Developer App": "Deine Entwickler-App",
    "Open Developer Portal": "Entwicklerportal öffnen",
    "Redirect Address": "Redirect-Adresse",
    "Copy": "Kopieren",
    "Client ID": "Client-ID",
    "Client Secret": "Client-Secret",
    "Client Secret (optional)": "Client-Secret (optional)",
    "App Secret": "App-Geheimnis",
    "App ID": "App-ID",
    "The sign-in took too long. Please try again.":
        "Die Anmeldung hat zu lange gedauert. Bitte versuche es erneut.",
    "Create an app in the LinkedIn developer portal and add the products “Share on LinkedIn” and “Sign In with LinkedIn using OpenID Connect”. Enter the redirect address below under “Authorized redirect URLs”. Dandelion can only post to your personal profile. A sign-in is valid for 60 days.":
        "Lege im LinkedIn-Entwicklerportal eine App an und füge die Produkte „Share on LinkedIn“ und „Sign In with LinkedIn using OpenID Connect“ hinzu. Trage die Redirect-Adresse unten unter „Authorized redirect URLs“ ein. Dandelion kann nur auf dein persönliches Profil posten. Eine Anmeldung gilt 60 Tage.",
    "Create an app of the type “Business” at developers.facebook.com, keep it in development mode and add “Facebook Login”. Enter the redirect address below under “Valid OAuth Redirect URIs”. Dandelion can only post to pages you manage, not to your personal profile.":
        "Lege unter developers.facebook.com eine App vom Typ „Business“ an, belasse sie im Entwicklungsmodus und füge „Facebook Login“ hinzu. Trage die Redirect-Adresse unten unter „Gültige OAuth-Redirect-URIs“ ein. Dandelion kann nur auf Seiten posten, die du verwaltest, nicht auf dein privates Profil.",
    "Create an app of the type “Native App” with read and write permissions in the X developer portal and enter the redirect address below as callback. X charges your developer account for every post: about $0.015, or $0.20 if the post contains a link.":
        "Lege im X-Entwicklerportal eine App vom Typ „Native App“ mit Lese- und Schreibrechten an und trage die Redirect-Adresse unten als Callback ein. X berechnet deinem Entwicklerkonto jeden Beitrag: etwa 0,015 $, mit Link 0,20 $.",
    "Redirect address copied": "Redirect-Adresse kopiert",
    "The sign-in was cancelled: {reason}": "Die Anmeldung wurde abgebrochen: {reason}",
    "{n} page added": ("{n} Seite hinzugefügt", "{n} Seiten hinzugefügt"),
    "Port {port} is already in use. Close the other program and try again.":
        "Port {port} ist bereits belegt. Schließe das andere Programm und versuche es erneut.",
    "{platform} could not be reached. Check your internet connection.":
        "{platform} ist nicht erreichbar. Prüfe deine Internetverbindung.",
    "X charges your developer account about {cost} for this post because it contains a link.":
        "X berechnet deinem Entwicklerkonto für diesen Beitrag etwa {cost}, weil er einen Link enthält.",
    "X charges your developer account about {cost} for this post.":
        "X berechnet deinem Entwicklerkonto für diesen Beitrag etwa {cost}.",
    "Your X developer account has no credits left. Top up credits in the X developer console.":
        "Dein X-Entwicklerkonto hat kein Guthaben mehr. Lade in der X Developer Console Guthaben auf.",
    "X refused the request: {reason}": "X hat die Anfrage abgelehnt: {reason}",
    "not permitted": "nicht erlaubt",
    "X rejected the post: {reason}": "X hat den Beitrag abgelehnt: {reason}",
    "Videos are not supported for X yet.": "Videos werden für X noch nicht unterstützt.",
    "The LinkedIn login has expired. Please sign in again.":
        "Die LinkedIn-Anmeldung ist abgelaufen. Bitte melde dich erneut an.",
    "LinkedIn no longer supports this version of the API. Please update Dandelion.":
        "LinkedIn unterstützt diese API-Version nicht mehr. Bitte aktualisiere Dandelion.",
    "LinkedIn rejected the post: {reason}": "LinkedIn hat den Beitrag abgelehnt: {reason}",
    "The login expires in {days} days.": "Die Anmeldung läuft in {days} Tagen ab.",
    "Videos are not supported for LinkedIn yet.": "Videos werden für LinkedIn noch nicht unterstützt.",
    "No Facebook page was found that you are allowed to post to. Posting to personal profiles is not possible.":
        "Es wurde keine Facebook-Seite gefunden, auf der du posten darfst. Auf private Profile kann nicht gepostet werden.",
    "The Facebook login is no longer valid. Please sign in again.":
        "Die Facebook-Anmeldung ist nicht mehr gültig. Bitte melde dich erneut an.",
    "Facebook denied the permission: {reason}": "Facebook hat die Berechtigung verweigert: {reason}",
    "Facebook rejected the post: {reason}": "Facebook hat den Beitrag abgelehnt: {reason}",
    "Videos are not supported for Facebook yet.": "Videos werden für Facebook noch nicht unterstützt.",
}


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def unesc(parts: str) -> str:
    raw = "".join(re.findall(r'"(.*)"', parts))
    return raw.replace('\\n', "\n").replace('\\"', '"').replace("\\\\", "\\")


def main() -> None:
    pot = (HERE / "dandelion.pot").read_text(encoding="utf-8")
    blocks = pot.split("\n\n")
    header = (
        'msgid ""\nmsgstr ""\n'
        '"Project-Id-Version: dandelion\\n"\n'
        '"Last-Translator: Christoph Langner <mail@christoph-langner.de>\\n"\n'
        '"Language-Team: German\\n"\n'
        '"PO-Revision-Date: 2026-10-01 18:00+0200\\n"\n'
        '"Language: de\\n"\n'
        '"MIME-Version: 1.0\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Content-Transfer-Encoding: 8bit\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
    )
    out = [header]
    missing = []
    for block in blocks[1:]:
        m = re.search(r'msgid ((?:".*"\n?)+)(?:msgid_plural ((?:".*"\n?)+))?msgstr', block)
        if not m:
            continue
        msgid = unesc(m.group(1))
        comments = "\n".join(line for line in block.splitlines() if line.startswith("#"))
        tr = DE.get(msgid)
        if tr is None:
            missing.append(msgid)
        ctx = re.search(r'msgctxt ((?:".*"\n?)+)msgid', block)
        entry = (comments + "\n" if comments else "")
        if ctx:
            entry += f'msgctxt "{esc(unesc(ctx.group(1)))}"\n'
        entry += f'msgid "{esc(msgid)}"\n'
        if m.group(2):
            plural = unesc(m.group(2))
            one, many = tr if isinstance(tr, tuple) else ("", "")
            entry += (f'msgid_plural "{esc(plural)}"\nmsgstr[0] "{esc(one)}"\n'
                      f'msgstr[1] "{esc(many)}"\n')
        else:
            entry += f'msgstr "{esc(tr if isinstance(tr, str) else "")}"\n'
        out.append(entry)
    (HERE / "de.po").write_text("\n".join(out), encoding="utf-8")
    if missing:
        print("Unübersetzt:", *missing, sep="\n  ")


if __name__ == "__main__":
    main()
