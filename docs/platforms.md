# Plattform-Recherche: Mastodon, Bluesky, X, Facebook, LinkedIn

Stand: 2026-10-01. Recherchiert in den offiziellen Entwicklerdokumentationen bzw. im Quellcode der Referenzimplementierungen. Angaben ohne offizielle Quelle sind als **unbestätigt** markiert. Limits ändern sich oft. Die App sollte deshalb, wo möglich, zur Laufzeit abfragen (Mastodon `/api/v2/instance`, Bluesky `app.bsky.video.getUploadLimits`) statt Werte fest einzubauen.

Hinweis: `docs.bsky.app` lieferte am Recherchetag ein ungültiges TLS-Zertifikat. Die Bluesky-Doku wurde deshalb aus dem Quell-Repo `github.com/bluesky-social/bsky-docs` gelesen, die Lexika aus `github.com/bluesky-social/atproto`.

---

## 1. Mastodon

### Authentifizierung
- **Dynamische App-Registrierung pro Instanz:** `POST /api/v1/apps` mit `client_name`, `redirect_uris` (ab 4.3.0 als Array), `scopes`, `website`. Antwort: `client_id`, `client_secret`, ab 4.4.0 auch `client_secret_expires_at` (0 = läuft nicht ab). Quelle: https://docs.joinmastodon.org/methods/apps/
- **OAuth 2.0 Authorization Code**, **PKCE (nur S256) ab 4.3.0**. Quelle: https://docs.joinmastodon.org/methods/oauth/
- Der Token-Endpunkt verlangt laut Server-Metadaten weiterhin `client_secret_basic` oder `client_secret_post`. `none` (öffentlicher Client) steht nicht in der Liste. Das ist unproblematisch, weil das Secret pro Installation und Instanz dynamisch erzeugt wird und nicht in der App ausgeliefert wird.
- **Discovery:** `/.well-known/oauth-authorization-server` (RFC 8414) ab 4.3.0. Ältere Server liefern 404, dann auf Standardpfade zurückfallen. `grant_types_supported`: nur `authorization_code` und `client_credentials`.
- **Redirect-URIs:** `urn:ietf:wg:oauth:2.0:oob` wird offiziell unterstützt (der Code wird angezeigt und vom Nutzer kopiert). Loopback (`http://127.0.0.1:PORT/…`) wird in der Doku nicht ausdrücklich erwähnt. Da die Redirect-URI bei der dynamischen Registrierung frei gesetzt wird, funktioniert Loopback in der Praxis (**unbestätigt** als offizielle Zusage). Ein Custom-Scheme (`de.example.poster://oauth`) ist ebenfalls möglich.
- **Token-Lebensdauer:** Es gibt keine Refresh-Tokens (kein `refresh_token`-Grant). Access-Tokens laufen ohne festes Ablaufdatum, bis sie widerrufen werden. Widerruf über `POST /oauth/revoke`.
- **Scopes:** granular, z. B. `write:statuses`, `write:media`, `read:accounts` (für `verify_credentials`).

### Was per API erlaubt ist
Alles, was der Web-Client auch kann: Posten, Medien, Umfragen, CW, Sichtbarkeit, Antworten, Bearbeiten (`PUT /api/v1/statuses/:id`), Löschen, serverseitiges Planen. Seit 4.5 auch Zitate über `quoted_status_id` und `quote_approval_policy` (`public`/`followers`/`nobody`). Quelle: https://docs.joinmastodon.org/methods/statuses/

### Textlänge und Zählweise
- Limit pro Instanz: `GET /api/v2/instance` → `configuration.statuses.max_characters` (Standard 500) und `characters_reserved_per_url` (Standard 23). Quelle: https://docs.joinmastodon.org/entities/Instance/
- Laut Quellcode (`app/validators/status_length_validator.rb`):
  - Gezählt werden **Graphem-Cluster** (`each_grapheme_cluster`), nicht Bytes und nicht Codepoints.
  - Der **CW-Text (`spoiler_text`) zählt mit** und wird mit dem Text zusammengezählt.
  - Jede URL zählt pauschal **23**.
  - Bei Mentions zählt **nur der Username-Teil**: `@alice@example.social` zählt wie `@alice`.
  - Quelle: https://github.com/mastodon/mastodon/blob/main/app/validators/status_length_validator.rb
- Forks wie glitch-soc oder Hometown und viele Instanzen haben höhere Limits. Deshalb immer den Instanzwert verwenden.

### Medien
- Aus `configuration.media_attachments` und `configuration.statuses` (Beispielwerte aus der Doku, pro Instanz verschieden):
  - `max_media_attachments`: 4
  - `image_size_limit`: 16 MB
  - `image_matrix_limit`: 33.177.600 px
  - `video_size_limit`: ca. 99 MB
  - `video_frame_rate_limit`: 120 fps
  - `video_matrix_limit`: 8.294.400 px (4K)
  - `supported_mime_types`: JPEG, PNG, GIF, WebP, AVIF/HEIC je nach Version, MP4, WebM, MOV, Audio
  - Quelle: https://docs.joinmastodon.org/entities/Instance/
- Upload über `POST /api/v2/media` (`file`, `thumbnail`, `description`, `focus`). Bilder liefern **200** (synchron). Video, GIFV und Audio liefern **202** und werden asynchron verarbeitet. Dann `GET /api/v1/media/:id` abfragen: 206 heißt „läuft noch“, 200 heißt „fertig“. Quelle: https://docs.joinmastodon.org/methods/media/
- GIFs werden serverseitig in MP4 („gifv“) umgewandelt.
- Bild und Video lassen sich laut verbreiteter Praxis nicht in einem Beitrag mischen (**unbestätigt**: in der Doku nicht ausdrücklich genannt). Umfragen und Medien schließen sich gegenseitig aus. Das ist dokumentiert.

### Alt-Text
`description` beim Upload oder nachträglich über `PUT /api/v1/media/:id`. Maximal `description_limit`, Standard **1500** Zeichen. Quelle: https://docs.joinmastodon.org/entities/Instance/

### Link-Vorschau
Erzeugt der **Server** (OpenGraph-Abruf nach dem Posten). Der Client übergibt nichts. Eine Vorschau entsteht nur, wenn der Beitrag keine Medien hat.

### Threads, CW, Sichtbarkeit, Sprache
- Antworten über `in_reply_to_id`.
- CW über `spoiler_text` und `sensitive`.
- `visibility`: `public` | `unlisted` | `private` | `direct`.
- `language`: ISO 639-1.
- Hashtags stehen im Text. CamelCase wird für Screenreader empfohlen.
- `Idempotency-Key`-Header (wird 1 h gespeichert) schützt bei Wiederholungsversuchen vor Doppelposts. **Für den Scheduler unbedingt nutzen.**

### Zeitgesteuertes Posten serverseitig
Ja, über `scheduled_at` (ISO 8601) in `POST /api/v1/statuses`. Antwort ist ein `ScheduledStatus`. Verwaltung über `/api/v1/scheduled_statuses` (auflisten, Termin ändern, abbrechen). Quelle: https://docs.joinmastodon.org/methods/scheduled_statuses/

Laut Quellcode gelten diese Einschränkungen:
- mindestens **5 Minuten** in der Zukunft
- höchstens **25 geplante Beiträge pro Tag**
- höchstens **300 insgesamt**

Quelle: https://github.com/mastodon/mastodon/blob/main/app/models/scheduled_status.rb

### Löschen
`DELETE /api/v1/statuses/:id`, optional mit `delete_media=true`. Gibt den Status zurück (für „Löschen und neu entwerfen“).

### Rate Limits
- 300 Anfragen pro 5 min pro Account und pro IP
- Medien-Upload 30 pro 30 min
- Löschen 30 pro 30 min
- Header `X-RateLimit-*`
- Quelle: https://docs.joinmastodon.org/api/rate-limits/

---

## 2. Bluesky (AT Protocol)

### Authentifizierung
Es gibt zwei Wege.

**a) App-Passwörter (Legacy, funktionieren weiterhin)**
- `com.atproto.server.createSession` mit Handle und App-Passwort. Liefert `accessJwt` (kurzlebig) und `refreshJwt`.
- Das Rate-Limit für `createSession` ist dokumentiert: 30 pro 5 min und 300 pro Tag pro Account. Quelle: https://github.com/bluesky-social/bsky-docs/blob/main/docs/advanced-guides/rate-limits.md
- Einfach umzusetzen, aber Bluesky empfiehlt OAuth als Hauptweg. Ein Auslaufdatum für App-Passwörter ist nicht angekündigt (**unbestätigt**).

**b) atproto OAuth.** Quelle: https://atproto.com/specs/oauth und https://github.com/bluesky-social/bsky-docs/blob/main/docs/advanced-guides/oauth-client.md
- Für alle Clients Pflicht: **PKCE (S256)**, **PAR** (Pushed Authorization Requests) und **DPoP** (pro Sitzung ein gebundener Schlüssel, Nonce-Handling).
- Die **`client_id` ist eine HTTPS-URL**, unter der ein JSON-Dokument mit den Client-Metadaten liegt. Für eine Desktop-App ohne Server reicht eine **statische Datei**, z. B. über GitHub Pages oder die Projekt-Website. Das ist der einzige „Server“, der gebraucht wird.
- Native Apps setzen `application_type: "native"` und `token_endpoint_auth_method: "none"` (öffentlicher Client). Die Referenzimplementierung erzwingt bei nativen Apps `none`.
- **Redirect-URIs für native Apps:**
  - **Custom-Scheme:** muss dem Hostnamen der `client_id` in umgekehrter Domain-Reihenfolge entsprechen und hat die Form `scheme:/pfad`. Beispiel: `client_id` `https://app.example.com/…` ergibt `com.example.app:/callback`. Unter Linux wird das über `x-scheme-handler/com.example.app` in der `.desktop`-Datei registriert.
  - **HTTPS-URL** mit demselben Origin wie die `client_id` (Universal Links). Für Desktop wenig sinnvoll.
  - **Loopback `http://127.0.0.1` / `http://[::1]`:** Die Spec nennt Loopback nur im Rahmen der „Localhost Client Development“-Ausnahme. Die **Referenzimplementierung** (`@atproto/oauth-provider`, `client-manager.ts`) akzeptiert Loopback-Redirects aber ausdrücklich für `application_type: native`, bei beliebigem Port (RFC 8252). `localhost` als Hostname wird abgelehnt, es muss die IP sein. Quelle: https://github.com/bluesky-social/atproto/blob/main/packages/oauth/oauth-provider/src/client/client-manager.ts. Ob Loopback bei allen PDS-Implementierungen und in Zukunft erlaubt bleibt, ist **unbestätigt**. Das Custom-Scheme ist der spec-konforme Weg.
  - **Entwicklungsmodus:** `client_id` = `http://localhost` (ohne Port) mit Redirect `http://127.0.0.1/…`. Es braucht kein gehostetes Metadaten-Dokument. Die Spec sagt nur, Server seien „encouraged“, das auch produktiv zu unterstützen. Nicht für Releases verwenden.
- **Token-Lebensdauer:**
  - Access-Token unter 30 min (Referenzimplementierung: 15 min).
  - Öffentliche Clients: Sitzung und Refresh-Token höchstens **2 Wochen**. Das ist seit 2025 von zuvor 1 Woche bzw. 2 Tagen erhöht worden. Refresh verlängert die Gesamtsitzung **nicht**.
  - Vertrauliche Clients: Refresh-Token 3 Monate (Spec erlaubt bis 180 Tage), Sitzung bis 2 Jahre.
  - Refresh-Tokens sind **Einmal-Tokens** (Rotation). Gleichzeitige Refreshes müssen serialisiert werden.
  - Quelle: https://github.com/bluesky-social/atproto-website/blob/main/src/app/%5Blocale%5D/blog/oauth-improvements/en.mdx
- **Konsequenz:** Mit OAuth als öffentlicher Client muss sich der Nutzer spätestens alle 2 Wochen neu anmelden. Für einen Scheduler mit Posts, die Wochen im Voraus geplant sind, ist das ein echtes UX-Problem. Mit App-Passwort gibt es diese Grenze nicht. Wie lange ein `refreshJwt` aus `createSession` gültig ist, ist nicht offiziell dokumentiert (**unbestätigt**, in der Praxis etwa 60–90 Tage, rollierend).
- **Scopes:** `atproto` (Pflicht), `transition:generic` (entspricht den Rechten eines App-Passworts), `transition:email`. Granulare Permission-Scopes (`repo:app.bsky.feed.post` usw.) sind spezifiziert. Wie weit sie produktiv ausgerollt sind, ist **unbestätigt**.

### Was per API erlaubt ist
Alles. Beiträge sind Records in `app.bsky.feed.post`, geschrieben mit `com.atproto.repo.createRecord`, oder atomar mehrere mit `applyWrites`, z. B. Post + Threadgate + Postgate. Es gibt keine Kosten und keine App-Registrierung außer dem OAuth-Metadatendokument.

### Textlänge und Zählweise
Lexikon `app.bsky.feed.post`: `text` mit `maxGraphemes: 300` **und** `maxLength: 3000`. Das zweite Limit wird in Lexika als UTF-8-Byte-Länge interpretiert. Quelle: https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/post.json
- URLs zählen **mit voller Länge**, es gibt keine Pauschale. Der offizielle Client kürzt die Anzeige, indem er **den Text selbst kürzt** (z. B. `example.com/artikel…`) und die volle URL nur im Link-Facet ablegt. Dasselbe Verfahren sollte unsere App anwenden.
- **Facets** (`app.bsky.richtext.facet`) für Links, Mentions und Hashtags mit `byteStart`/`byteEnd` als **UTF-8-Byte-Offsets** (Ende exklusiv). Mentions müssen vor dem Posten zu einer **DID** aufgelöst werden (`com.atproto.identity.resolveHandle`). Ohne Facet ist ein Link oder eine Mention nicht klickbar. Quelle: https://github.com/bluesky-social/bsky-docs/blob/main/docs/advanced-guides/posts.md
- Zusätzlich `tags`: bis 8 Hashtags außerhalb des Textes, je höchstens 64 Grapheme.

### Medien
- `app.bsky.embed.images`: **bis 4 Bilder**, je **2 MB** (`maxSize: 2000000`, früher 1 MB, die Doku-Prosa nennt teils noch 1 MB). Typ `image/*`. `alt` ist Pflichtfeld, `aspectRatio` optional, sollte aber gesetzt werden. Quelle: https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/images.json
- **Neu: `app.bsky.embed.gallery`**: bis 20 Elemente im Schema, Clients sollen derzeit **10** als weiches Limit durchsetzen. Je 2 MB. `alt` und `aspectRatio` sind Pflicht. Bisher nur Bilder. Ob die AppView das bereits für alle Nutzer rendert, ist **unbestätigt**. Vorerst `images` (4) verwenden und `gallery` hinter ein Feature-Flag legen. Quelle: https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/gallery.json
- `app.bsky.embed.video`: **1 Video**, nur `video/mp4`, bis **300 MB** (früher 100 MB). Optional `captions` (bis 20 VTT-Dateien à 20 KB), `alt`, `aspectRatio`, `presentation: "gif"` für GIF-artige Darstellung. Quelle: https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/video.json
- Ein PDS akzeptiert pro Blob höchstens 50 MB. Für große Videos ist deshalb der Weg über den Video-Dienst nötig: `getServiceAuth` → Upload an `https://video.bsky.app/xrpc/app.bsky.video.uploadVideo` → `getJobStatus` abfragen → BlobRef in den Post. Video setzt eine **bestätigte E-Mail-Adresse** voraus, außerdem gibt es Tageslimits. Quelle: https://github.com/bluesky-social/bsky-docs/blob/main/docs/tutorials/video.mdx
- Videolänge: 3 min seit März 2025. Laut Drittquellen 10 min seit August 2026, Tageslimit 25 Videos bzw. 10 GB (**unbestätigt**). Die tatsächlichen Werte liefert `app.bsky.video.getUploadLimits`.
- GIFs: als MP4-Video mit `presentation: gif`. Animierte GIFs als Bild-Blob werden nicht animiert dargestellt (**unbestätigt**).
- **Kein Mischen** von Bildern und Video. `embed` ist eine Union, es gibt genau einen Embed pro Post. `recordWithMedia` kombiniert Zitat und Medien.

### Alt-Text
Feld `alt` pro Bild bzw. Video. Das Lexikon definiert **kein** Maximum. Der offizielle Client begrenzt auf 2000 Zeichen (**unbestätigt**). Empfehlung: Wir begrenzen selbst auf 2000.

### Link-Vorschau
Der **Client muss sie selbst bauen**: Seite abrufen, `og:title`, `og:description` und `og:image` auslesen, das Bild als Blob hochladen (**höchstens 1 MB**, `image/*`), dann `app.bsky.embed.external` `{uri, title, description, thumb}` setzen. Ohne diesen Embed erscheint keine Karte. Ein Link-Embed ist nicht mit Bildern kombinierbar. Quelle: https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/external.json

### Threads, CW, Sichtbarkeit, Sprache
- **Antworten:** `reply: {root: {uri, cid}, parent: {uri, cid}}`. Für Threads die URI und CID des ersten Posts als `root` mitführen.
- **CW:** Self-Labels in `labels` (`com.atproto.label.defs#selfLabels`). Werte sind z. B. `sexual`, `nudity`, `porn`, `graphic-media`. Ein freier CW-Text wie bei Mastodon fehlt.
- **Sichtbarkeit:** Alles ist öffentlich. Es gibt kein unlisted und kein followers-only.
  - **Threadgate** (`app.bsky.feed.threadgate`, rkey = rkey des Root-Posts): steuert, wer antworten darf (bis zu 5 Regeln: mention, follower, following, list; leeres Array = niemand).
  - **Postgate** (`app.bsky.feed.postgate`): erlaubt, das Zitieren zu verbieten (`disableRule`).
- **Sprache:** `langs`, höchstens 3 BCP-47-Codes.
- **Hashtags:** im Text plus Tag-Facet, oder in `tags`.

### Zeitgesteuertes Posten serverseitig
**Nein.** `createdAt` ist nur ein vom Client gesetzter Zeitstempel und plant nichts. Planen muss die App lokal erledigen.

### Löschen
`com.atproto.repo.deleteRecord` (repo, collection, rkey). Zugehörige Threadgate- und Postgate-Records mitlöschen.

### Rate Limits
- Schreibpunkte pro Account: 5000 pro Stunde und 35.000 pro Tag. CREATE kostet 3 Punkte, UPDATE 2, DELETE 1.
- Gesamt pro IP: 3000 pro 5 min.
- Quelle: https://github.com/bluesky-social/bsky-docs/blob/main/docs/advanced-guides/rate-limits.md

---

## 3. X (Twitter)

### Kosten und API-Modell (wichtigste Änderung)
- X hat auf **Pay-per-Use mit Credits** umgestellt: „No subscriptions—pay only for what you use“. Laut Sekundärquellen gibt es für neue Entwickler seit 6. Februar 2026 **keine Free/Basic/Pro-Abos mehr** (Datum **unbestätigt** in der offiziellen Doku). Credits werden in der Developer Console gekauft, es gibt Spending-Limits und Auto-Recharge. Quelle: https://docs.x.com/x-api/getting-started/pricing
- Preise laut offizieller Tabelle:
  - **Post: Create**: **0,015 $ pro Request**
  - **Post: Create (with URL)**: **0,20 $ pro Request**. Das ist 13-mal teurer. Was genau als „with URL“ zählt, definiert die Doku nicht. Vermutlich jeder Post mit Link (**unbestätigt**).
  - Post: Create (summoned): 0,010 $
  - Media Metadata: 0,005 $. Ob der Medien-Upload selbst etwas kostet, ist nicht ausgewiesen (**unbestätigt**).
  - Interaction: Delete: 0,010 $. Ob das Post-Löschen darunter fällt, ist **unbestätigt**.
  - Reads: Posts 0,005 $, Users 0,010 $, eigene Daten („Owned Reads“) 0,001 $
- Ein „Link zum neuen Blogartikel“-Post kostet also 0,20 $. Für ein Blog-Crossposting-Tool ist das der Hauptkostentreiber.
- Abgerechnet wird pro **Developer-App bzw. Developer-Account**, nicht pro Endnutzer. Wenn wir eine gemeinsame App-ID ausliefern, zahlen **wir** für alle Nutzer.

### Authentifizierung
- **OAuth 2.0 Authorization Code mit PKCE** (S256 oder plain) im User-Kontext. App-Typ „Native App“ ist ein **öffentlicher Client ohne Secret**. Quelle: https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code
- Scopes zum Posten mit Medien: `tweet.write`, `tweet.read`, `users.read`, `media.write`, `offline.access` (für Refresh-Token).
- Access-Token gilt **2 Stunden**. Mit `offline.access` gibt es ein Refresh-Token. Refresh-Tokens rotieren nach verbreiteter Praxis (**unbestätigt** in der aktuellen Doku).
- Redirect: **exakter Abgleich** mit den im Portal hinterlegten Callback-URLs. `http://127.0.0.1:PORT/callback` ist möglich, aber der **Port muss fest** im Portal stehen. Freie Ports gibt es nicht, `localhost` ist teils problematisch. Quellen: https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code, https://devcommunity.x.com/t/why-cant-i-use-localhost-as-my-oauth-callback/708 (Port-Pflicht laut Community, **unbestätigt** offiziell). Ein Custom-Scheme (`myapp://`) wird im Portal akzeptiert (**unbestätigt**).
- OAuth 1.0a funktioniert weiterhin, braucht aber Consumer-Secret. Für Desktop nicht empfehlenswert.

### Was per API erlaubt ist
`POST /2/tweets` mit diesen Feldern (Quelle: https://docs.x.com/x-api/posts/create-post):
- `text`
- `media.media_ids` (1–4) und `tagged_user_ids`
- `reply.in_reply_to_tweet_id`
- `poll` (2–4 Optionen, 5–10.080 min)
- `reply_settings` (`following`, `mentionedUsers`, `subscribers`, `verified`)
- `made_with_ai`, `paid_partnership`
- `community_id`, `nullcast`
- `quote_tweet_id` ist laut Doku **nur im Enterprise-Plan** verfügbar.

**Antwort-Einschränkung seit Februar 2026:** Programmatische Antworten sind nur noch erlaubt, wenn der Original-Autor den Account @erwähnt oder zitiert. Das gilt für Free, Basic, Pro und Pay-per-Use. Antworten auf **eigene** Posts, also Threads, sollen weiter funktionieren. Quellen: https://x.com/XDevelopers/status/2026084506822730185, https://devcommunity.x.com/t/restricting-programmatic-replies-does-this-affect-replying-to-itself/257955 (Selbst-Antworten: Community-Aussage, **unbestätigt**).

### Textlänge und Zählweise
- **280 gewichtete Zeichen.** Konfiguration twitter-text v3: Standard-Latein und Interpunktion haben Gewicht 1, CJK und **alle Emoji** (auch mit Hautton-ZWJ-Sequenzen) Gewicht 2. Text wird NFC-normalisiert, **URLs zählen 23** (t.co). Medien zählen 0. Automatisch eingefügte Reply-Mentions zählen nicht. Quelle: https://docs.x.com/fundamentals/counting-characters
- Zum Zählen die offizielle **twitter-text**-Konfiguration bzw. Bibliothek verwenden (Python-Port vorhanden) oder die Gewichtsbereiche nachbauen.
- **Premium:** bis **25.000 Zeichen** („Long posts“, auf allen Premium-Stufen). Ob die API Langposts für Premium-Nutzer annimmt und wie das abgerechnet wird, ist **unbestätigt**. Die App sollte standardmäßig 280 annehmen und Premium als Nutzeroption anbieten.

### Medien
Quelle: https://docs.x.com/x-api/media/quickstart/best-practices
- **4 Fotos ODER 1 animiertes GIF ODER 1 Video** pro Post. Kein Mischen.
- Bilder: JPG, PNG, GIF, WEBP, höchstens **5 MB**.
- Animierte GIFs: höchstens **15 MB**, 1280×1080, 350 Frames.
- Video (`tweet_video`): laut aktueller Doku 8 GB und 20 min für Standard-Accounts, 16 GB und 125 min für Premium. Empfohlen werden H.264 High Profile und AAC-LC.
  - Ältere Doku nannte 512 MB und 140 s. Die neuen Werte stammen aus der offiziellen Doku. Ob sie für alle Nicht-Premium-Accounts gelten, ist **unbestätigt**.
  - Die Doku warnt ausdrücklich: Ein Upload kann erfolgreich sein und der Post trotzdem mit **403** abgelehnt werden, wenn das Video die Berechtigungen des Nutzers überschreitet.
- **Upload: v2-Endpunkte.** Quelle: https://docs.x.com/x-api/media/quickstart/media-upload-chunked
  - einfach: `POST /2/media/upload`
  - chunked: `POST /2/media/upload/initialize` → `/{id}/append` (Chunks à 4–5 MB) → `/{id}/finalize` → Status über `GET /2/media/upload?command=STATUS` abfragen, bis `succeeded`.
  - `media_category`: `tweet_image`, `tweet_gif`, `tweet_video`.
  - Scope `media.write` (funktioniert mit OAuth-2-User-Token). Der v1.1-Endpunkt `upload.twitter.com/1.1/media/upload.json` gilt als abgelöst (genaues Abschaltdatum **unbestätigt**). Nicht mehr verwenden.

### Alt-Text
`POST /2/media/metadata` mit `{id, metadata: {alt_text: {text}}}`, höchstens **1000** Zeichen. Quelle: https://docs.x.com/x-api/media/create-media-metadata

### Link-Vorschau
Der **Server** erzeugt sie (Twitter Cards aus `twitter:*`/OG-Tags). Der Client übergibt nur die URL im Text. Kosten siehe oben (0,20 $).

### Threads, CW, Sichtbarkeit, Sprache
- Threads über `reply.in_reply_to_tweet_id` auf den eigenen vorherigen Post.
- Kein CW-Feld. Für Medien gibt es ein Sensitive-Flag nur in den Account-Einstellungen; per API pro Post gibt es keine dokumentierte Entsprechung (**unbestätigt**).
- Sichtbarkeit: nur `reply_settings`.
- Sprache wird automatisch erkannt, es gibt kein `lang`-Feld beim Erstellen.

### Zeitgesteuertes Posten serverseitig
Nicht über die öffentliche v2-API (Scheduling gibt es nur in der Ads-API bzw. im Web-UI). Die App muss lokal planen.

### Löschen
`DELETE /2/tweets/:id` (Scope `tweet.write`). Bearbeiten über `edit_options` ist für Premium-Accounts vorgesehen.

### Rate Limits
Quelle: https://docs.x.com/x-api/fundamentals/rate-limits
- `POST /2/tweets`: 100 pro 15 min pro Nutzer, 10.000 pro 24 h pro App
- `DELETE /2/tweets/:id`: 50 pro 15 min pro Nutzer
- `POST /2/media/upload`: 500 pro 15 min pro Nutzer
- `initialize`/`append`/`finalize`: je 1875 pro 15 min
- `POST /2/media/metadata`: 500 pro 15 min
- Zusätzlich gilt das plattformweite Tageslimit pro Account (historisch 2400 Posts pro Tag, **unbestätigt** aktuell).

---

## 4. Facebook (Meta Graph API)

### Aktuelle Version
**Graph API v26.0** (29.07.2026). v25.0 vom 18.02.2026 ist bis 29.07.2028 verfügbar. Versionen leben etwa 2 Jahre. Quelle: https://developers.facebook.com/docs/graph-api/changelog

### Was per API erlaubt ist
- **Nur Facebook-Seiten** (Pages). Posten auf **private Profile ist nicht möglich**. `publish_actions` wurde 2018 abgeschafft, es gibt keinen Nachfolger.
- **Gruppen: nicht mehr möglich.** Die Groups API inklusive `publish_to_groups` wurde mit v19 angekündigt und am **22.04.2024 für alle Versionen entfernt**. Quellen: https://www.sprinklr.com/help/articles/getting-started-facebook/meta-deprecates-facebook-groups-api/66229eb25f9dd9599d632712, https://ecamm.com/blog/facebook-groups-to-discontinue-third-party-access/ (Sekundärquellen; offizielle Changelog-Seite zu v19 nicht direkt geprüft).
- Seitenbeitrag: `POST /{page-id}/feed` mit `message`, `link`, `published`, `scheduled_publish_time`, `attached_media`, `child_attachments` usw. Dafür nötig:
  - **Page Access Token** eines Nutzers mit Task `CREATE_CONTENT`
  - Berechtigungen `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
  - Quellen: https://developers.facebook.com/docs/pages-api/posts, https://developers.facebook.com/docs/graph-api/reference/page/feed

### Authentifizierung
- Facebook Login, manueller Flow für **Desktop-Apps**:
  - Redirect `https://www.facebook.com/connect/login_success.html` in einer **WebView** (WebKitGTK möglich), dann das Token aus dem URL-Fragment lesen.
  - Desktop-Apps müssen `response_type=token` verwenden. Das ist der implizite Flow und liefert ein kurzlebiges User-Token (1–2 h).
  - PKCE ist für diesen Flow **nicht dokumentiert**.
  - Quelle: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow
- Code-Tausch und Langzeit-Token brauchen das **App-Secret**. Meta verbietet ausdrücklich, das im Client zu verwenden: „Make this call from your server, not a client.“ Quelle: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived
- Token-Kette:
  - kurzlebiges User-Token (etwa 1–2 h)
  - → mit App-Secret: **Long-lived User Token** (etwa **60 Tage**)
  - → `GET /me/accounts`: **Long-lived Page Token ohne Ablaufdatum** (wird nur in bestimmten Fällen ungültig, z. B. bei Passwortwechsel oder Rollenentzug)
  - Ein Page-Token aus einem **kurzlebigen** User-Token ist nur etwa 1 h gültig (**unbestätigt** in der aktuellen Doku, früher dokumentiert).
- Alternative ohne Secret im Client: **System-User-Token** aus dem Meta Business Manager (läuft nicht ab). Der Nutzer erzeugt es selbst und fügt es in die App ein. Technisch einfach, aber nur für technisch versierte Nutzer zumutbar.

### App Review und Business-Verifizierung
- `pages_manage_posts`, `pages_read_engagement` und `pages_show_list` sind laut Permissions-Referenz „App Review Required“. Quelle: https://developers.facebook.com/docs/permissions
- Ohne App Review (Standard Access, App im Development-Modus) funktionieren die Berechtigungen nur für Nutzer mit **Rolle in der App** (Admin, Developer, Tester).
- Für eine öffentlich verteilte App brauchen wir also **App Review mit Screencast, Datenschutzerklärung und gegebenenfalls Business-Verifizierung**. Ob Business-Verifizierung für Advanced Access dieser Page-Berechtigungen aktuell Pflicht ist, ist **unbestätigt**: Die Referenz sagt „No“, in der Praxis verlangt Meta sie oft.

### Textlänge
Ein offizielles Limit für `message` ist in der Graph-API-Doku nicht genannt. Üblich zitiert werden **63.206 Zeichen** (**unbestätigt**). Im Feed wird nach wenigen Zeilen auf „Mehr anzeigen“ gekürzt (etwa 400–480 Zeichen, **unbestätigt**). Link-Titel in der Vorschau werden nach etwa 35 Zeichen gekürzt (laut Feed-Referenz).

### Medien
- **Fotos:** `POST /{page-id}/photos` (`url` oder `source`, `caption`). JPEG, BMP, PNG, GIF, TIFF. Höchstens **4 MB**, PNG am besten unter 1 MB. Quelle: https://developers.facebook.com/docs/graph-api/reference/page/photos/
- **Mehrere Fotos:** jedes Foto mit `published=false` (bzw. `temporary=true` für geplante Posts) hochladen, dann `POST /{page-id}/feed` mit `attached_media=[{"media_fbid": …}]`. Ein Maximum ist nicht dokumentiert (**unbestätigt**, in der Praxis bis etwa 10 empfehlenswert).
- **Video:** Resumable Upload API (`POST /{app-id}/uploads` → Upload → File-Handle → `POST /{page-id}/videos`). Quelle: https://developers.facebook.com/docs/video-api/guides/publishing. Grenzen wie bis 10 GB und 240 min stehen nicht in der gelesenen Seite (**unbestätigt**). Reels nutzen eigene Endpunkte.
- Bild und Video in einem Feed-Post mischen: nicht vorgesehen (**unbestätigt**).

### Alt-Text
`alt_text_custom` beim Foto-Upload (`/photos`). Eine Maximallänge ist nicht dokumentiert (**unbestätigt**).

### Link-Vorschau
Der **Server** erzeugt sie aus dem `link`-Parameter (Open Graph). Die Overrides `name`, `description`, `picture` und `thumbnail` stehen noch in der Referenz, funktionieren aber nur bei verifizierten Domain-Eigentümern (**unbestätigt** für v26).

### Threads, Sichtbarkeit, Sprache
- Keine Antwortketten im Sinne von Threads (Kommentare gibt es über `/{post-id}/comments`, das ist etwas anderes).
- `targeting`/`feed_targeting` erlauben Zielgruppeneinschränkungen.
- Kein CW, kein Sprachfeld (außer Targeting nach Locale).

### Zeitgesteuertes Posten serverseitig
**Ja.** `published=false` plus `scheduled_publish_time` (Unix-Zeit, ISO 8601 oder strtotime). Die Doku widerspricht sich beim Zeitraum: Die Pages-API-Anleitung nennt **10 min bis 30 Tage**, die Feed-Referenz **10 min bis 75 Tage**. Sicher ist 10 min bis 30 Tage.

### Löschen und Bearbeiten
`DELETE /{page-post-id}`. Bearbeiten über `POST /{page-post-id}` geht nur bei Posts, die die eigene App erstellt hat.

### Rate Limits
Page-Aufrufe unterliegen den **Business Use Case (BUC) Rate Limits**, die sich nach den Interaktionen der Seite richten. Header `X-Business-Use-Case-Usage`. Quelle: https://developers.facebook.com/docs/graph-api/overview/rate-limiting (für ein paar Posts am Tag unkritisch).

---

## 5. LinkedIn

### Produkte und Scopes
- **Persönliches Profil:**
  - Produkt **„Share on LinkedIn“** (self-serve, sofort verfügbar) gibt `w_member_social`.
  - Für die Person-URN zusätzlich **„Sign In with LinkedIn using OpenID Connect“** (`openid profile`, `email`). Aus `sub` von `/v2/userinfo` wird `urn:li:person:{sub}`.
  - Quelle: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
- **Unternehmensseite:** `w_organization_social` gibt es nur über die **Community Management API**, ein „Vetted Product“ mit Development- und Standard-Tier. Voraussetzungen:
  - Sie ist **nur für registrierte juristische Personen und kommerzielle Use-Cases** verfügbar.
  - Verifizierte geschäftliche E-Mail-Adresse, Organisation und Domain.
  - Die App muss von der zugehörigen LinkedIn-Seite verifiziert sein.
  - Die Community Management API muss in einer **neuen App ohne andere Produkte** beantragt werden.
  - Für Standard-Tier: Screencast und Datenschutzerklärung.
  - Development-Tier: 500 Anfragen pro App und 100 pro Mitglied pro Tag.
  - Quellen: https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review, https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview
- `w_organization_social` erfordert die Seitenrolle ADMINISTRATOR, CONTENT_ADMIN oder DIRECT_SPONSORED_CONTENT_POSTER.

### Posts API vs. UGC API
- Die **Posts API (`POST https://api.linkedin.com/rest/posts`) ersetzt `ugcPosts`.** Pflicht-Header:
  - `Linkedin-Version: YYYYMM` (aktuell bis **202609** dokumentiert; **202510 wird am 15.10.2026 abgeschaltet**, Versionen leben etwa 1 Jahr)
  - `X-Restli-Protocol-Version: 2.0.0`
  - Quelle: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- Die „Share on LinkedIn“-Doku zeigt noch `v2/ugcPosts` und `assets?action=registerUpload` (Stand 2021/2023). `w_member_social` funktioniert aber auch mit `/rest/posts`, `/rest/images` und `/rest/videos`. Images API und Videos API ersetzen die Assets API.
- Antwort: 201, Post-ID im Header `x-restli-id` (`urn:li:share:…` bzw. `urn:li:ugcPost:…`).

### Authentifizierung
- **Standard 3-legged OAuth: Der Token-Tausch verlangt zwingend `client_secret`.** Redirect-URLs müssen absolut sein, ohne `#`, Parameter werden ignoriert. Die Doku zeigt HTTPS-Beispiele. Ob `http://localhost`/`127.0.0.1` als registrierte Redirect-URL für den Standard-Flow erlaubt ist, ist **unbestätigt**: in der Praxis funktioniert es, wenn die URL exakt mit Port registriert ist. Quelle: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- **Native PKCE-Flow** (`/oauth/native-pkce/authorization`, Loopback `http://127.0.0.1:{port}` mit beliebigem Port, Token-Tausch mit `code_verifier` ohne Secret) existiert. LinkedIn schaltet ihn aber **nur auf Anfrage über den LinkedIn-Ansprechpartner frei**, faktisch also nur für Partner. Quelle: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Für Native-Flows verlangt LinkedIn den System-Browser, keine WebView. Mit `enable_extended_login=true` sind Google/Apple/Passkey-Login auch in nativen Apps möglich.
- **Access-Token: 60 Tage.** Programmatische Refresh-Tokens gibt es nur „for a limited set of partners“. Alle anderen erneuern über einen erneuten Auth-Flow. Der läuft ohne Consent-Dialog durch, solange der Nutzer bei linkedin.com eingeloggt ist und das alte Token noch gilt. Ein neuer Scope invalidiert alle alten Tokens.

### Textlänge und Besonderheiten
- `commentary` bis **3000 Zeichen**. Die Zahl steht in der API-Doku nicht explizit (Fehler `FIELD_LENGTH_TOO_LONG`). 3000 ist der verbreitete Wert aus der LinkedIn-Hilfe (**unbestätigt** als API-Limit). Ob nach UTF-16-Codeunits oder Codepoints gezählt wird, ist **unbestätigt**. Konservativ zählen.
- **little-Text-Format:** `commentary` ist kein Klartext. **Alle reservierten Zeichen müssen mit Backslash escaped werden, auch wenn sie nicht zu einem Element gehören**:
  `| { } @ [ ] ( ) < > # \ * _ ~`
  - Mention: `@[Name](urn:li:person:…)` bzw. `urn:li:organization:…`. Der Name muss exakt passen.
  - Hashtag: `#wort` oder `{hashtag|\#|wort}`.
  - Ein nicht escaptes `(` oder `*` kann zu abgeschnittenem oder verstümmeltem Text führen. Eine eigene Escape-Funktion ist Pflicht.
  - Quelle: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format
- Im Feed wird nach etwa 210 Zeichen auf „…mehr“ gekürzt (**unbestätigt**).

### Medien
- **Bilder:** `POST /rest/images?action=initializeUpload` → `PUT` auf `uploadUrl` → `urn:li:image:…`. JPG, PNG, GIF (bis 250 Frames), unter 36.152.320 Pixel. Eine Dateigrößengrenze ist nicht genannt. Quelle: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api
- **Mehrere Bilder:** `content.multiImage.images`, **2 bis 20 Bilder**. Quelle: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api
- **Video:** Videos API: `initializeUpload` (mit `fileSizeBytes`) → Teile à 4 MB per `PUT` hochladen, ETags sammeln → `finalizeUpload` → `status` abfragen, bis `AVAILABLE`. Bedingungen: **3 s bis 30 min, 75 KB bis 500 MB** (Feed-Spezifikation; `fileSizeBytes` erlaubt bis 5 GB), nur MP4. Thumbnail und Untertitel (nur Englisch, SRT) sind optional. Quelle: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api
- Außerdem Dokumente (PDF, PPT) und Umfragen.
- Kein Mischen: `content` enthält genau einen Typ (media | multiImage | article | poll).

### Alt-Text
`content.media.altText` bzw. `multiImage.images[].altText`. Höchstens **4086 Zeichen**, empfohlen unter 120.

### Link-Vorschau
**Muss man selbst mitgeben.** „The Posts API does not support URL scraping for article post creation“. Für eine Link-Karte braucht es `content.article` mit `source`, `title`, `description` und `thumbnail` (`urn:li:image:…`, vorher über die Images API hochgeladen). Wie bei Bluesky muss unsere App also OG-Daten abrufen und das Thumbnail hochladen. Eine URL nur im `commentary` erzeugt keine Karte (**unbestätigt**, verbreitete Erfahrung).

### Threads, Sichtbarkeit, Sprache
- Keine Threads. Kommentare laufen über die Comments API.
- `visibility`: `PUBLIC` | `CONNECTIONS` | `LOGGED_IN` | `CONTAINER`.
- `isReshareDisabledByAuthor`.
- Kein CW, kein Sprachfeld.

### Zeitgesteuertes Posten serverseitig
**Nein**, nicht in der Posts API. Bei Erstellung ist nur `lifecycleState: PUBLISHED` erlaubt. Die App muss lokal planen.

### Löschen
`DELETE /rest/posts/{encoded urn}` (idempotent, 204). Bearbeiten über `PARTIAL_UPDATE` (nur commentary und einige weitere Felder).

### Rate Limits
„Share on LinkedIn“: **150 Requests pro Mitglied und Tag**, 100.000 pro App und Tag. Medien-Uploads zählen mit (**unbestätigt**, ob jeder Upload-Schritt einzeln zählt). Quelle: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin

---

## 6. Vergleichstabelle

| | Mastodon | Bluesky | X | Facebook (Seite) | LinkedIn |
|---|---|---|---|---|---|
| **Textlimit** | pro Instanz, Std. 500 | 300 Grapheme + 3000 Byte | 280 gewichtet (Premium 25.000) | ~63.206 (unbestätigt) | 3000 (unbestätigt als API-Wert) |
| **Zählweise** | Grapheme; URL = 23; Mention nur @user; CW zählt mit | Grapheme; URLs voll; Facets in UTF-8-Bytes | twitter-text v3: CJK/Emoji = 2; URL = 23; NFC | Zeichen | little-Format, Escaping Pflicht |
| **Bilder/Post** | 4 (Instanz) | 4 (`images`), Galerie 10 (neu) | 4 | mehrere über `attached_media` | 1 bzw. 2–20 (multiImage) |
| **Bildgröße** | 16 MB (Instanz) | 2 MB | 5 MB (GIF 15 MB) | 4 MB | < 36 MPx |
| **Video** | 1, ~99 MB (Instanz), asynchron | 1, MP4, 300 MB, 3 min (10 min unbestätigt), asynchron über video.bsky.app | 1, bis 20 min / 8 GB (Std.), asynchron | Resumable Upload | 1, MP4, 3 s–30 min, 75 KB–500 MB |
| **Mischen Bild+Video** | nein (unbestätigt) | nein | nein | nein (unbestätigt) | nein |
| **Alt-Text** | ja, 1500 (Instanz) | ja, kein Lexikon-Limit | ja, 1000 | ja (`alt_text_custom`), Limit ? | ja, 4086 |
| **Link-Card** | Server | **Client baut** `embed.external` + Thumb (≤ 1 MB) | Server | Server (`link`) | **Client baut** `content.article` + Thumb |
| **Threads** | `in_reply_to_id` | `reply.root/parent` | `in_reply_to_tweet_id` (nur eigene/summoned) | – | – |
| **CW** | `spoiler_text` | Self-Labels | – | – | – |
| **Sichtbarkeit** | public/unlisted/private/direct | öffentlich + Threadgate/Postgate | `reply_settings` | Targeting | PUBLIC/CONNECTIONS/LOGGED_IN |
| **Sprache** | `language` | `langs` (≤ 3) | – (auto) | – | – |
| **Server-Scheduling** | **ja** (≥ 5 min, 25/Tag, 300 total) | nein | nein | **ja** (10 min–30 Tage) | nein |
| **Löschen** | ja | ja | ja | ja | ja |
| **Auth** | OAuth2 + PKCE, dynamische Registrierung, Secret pro Instanz | App-Passwort oder OAuth (PKCE+PAR+DPoP, öffentlicher Client, Metadaten-JSON gehostet) | OAuth2 PKCE, öffentlicher Client möglich | FB Login (WebView, Token-Flow); Langzeit-Token nur mit Secret | OAuth2 **mit Secret**; PKCE nur für Partner |
| **Token-Laufzeit** | unbegrenzt, kein Refresh | OAuth öffentlich: max. 2 Wochen; App-PW: Refresh-JWT | 2 h + Refresh (`offline.access`) | Page-Token unbegrenzt (aus Long-lived User Token) | 60 Tage, kein Refresh (außer Partner) |
| **Schreib-Rate-Limit** | 300/5 min; Medien 30/30 min | 5000 Pkt./h, 35.000/Tag | 100/15 min/User; 10k/Tag/App | BUC-basiert | 150 Req./Mitglied/Tag |
| **Kosten** | 0 | 0 | **0,015 $/Post; 0,20 $ mit URL** | 0 (aber App Review) | 0 (Seiten: Vetting nur für Firmen) |
| **Freigabe nötig** | nein | nein | Developer-Account + Credits | App Review (+ ggf. Business-Verifizierung) | Profil: nein; Seite: Community-Management-Vetting |

---

## 7. Konsequenzen für die App

### 7.1 Empfohlene Auth-Flows (Desktop, ohne eigenen Server)

Grundsatz: **In einer ausgelieferten Desktop-App ist ein Client-Secret nicht geheim.** Es lässt sich aus Flatpak, AUR-Paket oder Binary extrahieren. Plattformen, die beim Token-Tausch ein Secret verlangen, sind ohne Backend nur mit **eigenen Developer-Apps der Nutzer (BYO-Keys)** sauber nutzbar.

| Plattform | Empfohlener Flow | Secret nötig? | Eigene Developer-App der Nutzer? |
|---|---|---|---|
| Mastodon | Pro Instanz `POST /api/v1/apps` beim ersten Login. Authorization Code + PKCE (ab 4.3), Loopback-Redirect `http://127.0.0.1:{zufälliger Port}/callback` im System-Browser, Fallback `urn:ietf:wg:oauth:2.0:oob` mit Code-Eingabe. Token in libsecret. | Ja, aber dynamisch pro Installation erzeugt, also unkritisch | Nein |
| Bluesky | **Standard: atproto OAuth als nativer öffentlicher Client.** Metadaten-JSON statisch hosten (z. B. `https://<projekt>.github.io/oauth/client-metadata.json`), Redirect über Custom-Scheme in Reverse-Domain-Form (z. B. `io.github.<user>:/callback`, registriert per `.desktop` `MimeType=x-scheme-handler/…`), alternativ Loopback (laut Referenzimplementierung erlaubt). DPoP-Schlüssel in libsecret. **Fallback/Option: App-Passwort**, weil OAuth-Sitzungen öffentlicher Clients nach 2 Wochen hart enden. Das kollidiert mit lange im Voraus geplanten Posts. | Nein | Nein |
| X | OAuth 2.0 PKCE, App-Typ „Native App“ (öffentlicher Client), Scopes `tweet.read tweet.write users.read media.write offline.access`, Loopback mit **festem Port** (im Portal registriert). | Nein | **Faktisch ja.** Abgerechnet wird pro Developer-App. Eine gemeinsame Client-ID würde uns alle Kosten aufbürden und ist missbrauchsanfällig. Empfehlung: Nutzer tragen eigene Client-ID ein (BYO) und bezahlen ihre Credits selbst. Optional ein gemeinsamer Client nur als bewusste Projektentscheidung mit Budget. |
| Facebook | **BYO-App:** Nutzer legt eine Meta-App an (Development-Modus, er ist Admin, also ist kein App Review nötig), trägt App-ID und App-Secret lokal ein (sein eigenes Secret, liegt in libsecret). Login über WebKitGTK-WebView mit `login_success.html` → kurzlebiges Token → lokal gegen Long-lived User Token tauschen → Page-Token ohne Ablauf. **Alternative:** Nutzer fügt ein System-User-Token aus dem Business Manager ein. Eine gemeinsame App-ID mit eingebettetem Secret ist **nicht** zulässig. | Ja (für Langzeit-Token) | **Ja**, solange wir kein Backend und keinen App Review haben |
| LinkedIn | **BYO-App:** Nutzer legt eine LinkedIn-App an, fügt „Share on LinkedIn“ und „Sign In with LinkedIn using OpenID Connect“ hinzu (self-serve), registriert `http://127.0.0.1:{fester Port}/callback` und trägt Client-ID und Secret lokal ein. Flow: Authorization Code mit Secret im System-Browser. Erneuerung alle 60 Tage per Browser-Re-Auth (meist ohne Dialog). Native PKCE nur, falls LinkedIn es uns als Partner freischaltet. Unternehmensseiten nur mit Community-Management-Vetting, das für ein Open-Source-Hobbyprojekt ohne Firma praktisch nicht erreichbar ist. | Ja | **Ja** |

Allgemein:
- Tokens und Secrets über **libsecret** (Secret Service / GNOME Keyring) speichern, nie in GSettings oder Klartext-Dateien.
- Einen Loopback-Server nur kurz an 127.0.0.1 binden und `state` prüfen.
- System-Browser über `Gtk.UriLauncher` bzw. das xdg-desktop-portal OpenURI starten. Im Flatpak funktioniert das ohne zusätzliche Rechte. Ein Custom-Scheme erfordert den MIME-Eintrag in der `.desktop`-Datei.

### 7.2 Risiken
1. **X-Kosten:** Pay-per-Use ohne Gratis-Stufe. **0,20 $ pro Post mit Link.** Programmatische Antworten auf fremde Posts sind gesperrt, Zitieren ist nur mit Enterprise möglich. Die Preise können sich kurzfristig ändern. Die UI muss die Kosten vor dem Posten anzeigen, und Credits bzw. 402-Fehler müssen sauber behandelt werden. X sollte ein optionales Plugin sein.
2. **Facebook App Review:** Ohne Review nur mit BYO-App im Development-Modus nutzbar. Dazu kommen Versionswechsel etwa alle 2 Jahre, Gruppen sind tot, private Profile gehen nicht. Die WebView-Pflicht für Desktop-Login ist mit WebKitGTK machbar, aber Meta kann eingebettete Logins jederzeit einschränken.
3. **LinkedIn:** Secret-Pflicht (BYO-App), 60-Tage-Tokens ohne Refresh, monatliche Versionsheader mit etwa einem Jahr Laufzeit (Pflege). Das little-Escaping ist fehleranfällig. Unternehmensseiten sind praktisch unerreichbar (nur für Firmen mit Vetting).
4. **Bluesky OAuth:** 2-Wochen-Sitzungsgrenze für öffentliche Clients. Wir brauchen ein gehostetes Metadaten-JSON (Domain-Abhängigkeit: ändert sich die Domain, ändert sich die `client_id`). Wer DPoP selbst implementiert, muss Nonces und Rotation fehlerfrei behandeln. Gibt es in Python keine ausgereifte Bibliothek, ist das Aufwand (**unbestätigt**: Stand der Python-Bibliotheken nicht geprüft). Neue Features (Galerie, längere Videos) kommen schnell.
5. **Mastodon:** Instanzvielfalt (alte Versionen ohne PKCE und Discovery, Forks mit anderen Limits). Das Server-Scheduling ist auf 25 Posts pro Tag und 300 insgesamt begrenzt.
6. **Lokaler Scheduler:** Für Bluesky, X und LinkedIn muss die App zum Zeitpunkt laufen. Wir brauchen einen Hintergrunddienst (systemd-User-Timer bzw. `org.freedesktop.portal.Background`/Autostart) plus Nachholen verpasster Termine. Mastodon und Facebook können optional serverseitig planen. Dann muss die App die serverseitige ID für Änderungen und Abbrüche speichern.

### 7.3 Skizze der Plugin-Schnittstelle

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Optional
from datetime import datetime

class TextCounting(Enum):
    GRAPHEMES = "graphemes"              # Mastodon, Bluesky
    TWITTER_WEIGHTED = "twitter_v3"      # X
    UTF16 = "utf16"                      # Facebook/LinkedIn (konservativ, unbestätigt)

class LinkCardMode(Enum):
    SERVER = "server"                    # Mastodon, X, Facebook
    CLIENT_EMBED = "client_embed"        # Bluesky, LinkedIn: OG holen + Thumb hochladen
    NONE = "none"

@dataclass
class MediaLimits:
    max_images: int                      # 4 / 4(10 Galerie) / 4 / n / 20
    min_images_multi: int = 1            # LinkedIn multiImage: 2
    max_videos: int = 1
    max_gifs: int = 1
    allow_mixed: bool = False
    image_mime_types: list[str] = field(default_factory=list)
    video_mime_types: list[str] = field(default_factory=list)
    max_image_bytes: Optional[int] = None
    max_image_pixels: Optional[int] = None
    max_gif_bytes: Optional[int] = None
    max_video_bytes: Optional[int] = None
    max_video_duration_s: Optional[float] = None
    min_video_duration_s: Optional[float] = None
    max_video_pixels: Optional[int] = None
    max_video_fps: Optional[float] = None
    link_thumb_max_bytes: Optional[int] = None   # Bluesky 1 MB
    async_processing: bool = False               # Video muss abgefragt werden

@dataclass
class PlatformLimits:
    platform: str
    account_id: str
    max_chars: int                       # 500 (Instanz) / 300 / 280|25000 / 63206 / 3000
    max_bytes: Optional[int]             # Bluesky 3000
    counting: TextCounting
    url_weight: Optional[int]            # 23 bei Mastodon/X, None = volle Länge
    mention_counts_domain: bool          # Mastodon: False
    cw_counts_toward_limit: bool         # Mastodon: True
    reserved_chars_escape: Optional[str] # LinkedIn little: r"|{}@[]()<>#\*_~"
    media: MediaLimits
    alt_text_max: Optional[int]          # 1500 / None(→2000 selbst) / 1000 / None / 4086
    alt_text_supported: bool
    link_card: LinkCardMode
    supports_threads: bool
    supports_content_warning: bool       # Mastodon: Freitext; Bluesky: Labels
    content_labels: list[str]            # Bluesky Self-Labels
    visibility_options: list[str]
    supports_language: bool
    max_languages: int                   # Bluesky 3, Mastodon 1
    supports_polls: bool
    server_scheduling: bool
    schedule_min_offset_s: Optional[int] # Mastodon 300, Facebook 600
    schedule_max_offset_s: Optional[int] # Facebook 30 Tage
    schedule_daily_limit: Optional[int]  # Mastodon 25
    supports_edit: bool
    supports_delete: bool
    cost_per_post: Optional[float]       # X 0.015
    cost_per_post_with_link: Optional[float]  # X 0.20
    write_rate_limit: Optional[str]      # zur Anzeige / zum Drosseln
    token_expires_at: Optional[datetime] # Re-Auth-Hinweis (LinkedIn 60 d, Bluesky 14 d)
    fetched_at: datetime                 # Mastodon-Instanzwerte cachen (z. B. 24 h)

@dataclass
class ValidationIssue:
    severity: str                        # "error" | "warning"
    code: str                            # "too_long", "missing_alt", "too_many_images", ...
    message: str
    span: Optional[tuple[int, int]] = None

class PlatformPlugin(Protocol):
    id: str
    display_name: str

    async def authenticate(self, account_hint: Optional[str] = None) -> "Account": ...
    async def refresh(self, account: "Account") -> "Account": ...
    async def get_limits(self, account: "Account") -> PlatformLimits: ...
    def count(self, text: str, limits: PlatformLimits) -> int: ...
    def validate(self, draft: "Draft", limits: PlatformLimits) -> list[ValidationIssue]: ...
    def transform(self, draft: "Draft", limits: PlatformLimits) -> "Draft": ...
        # z. B. LinkedIn-Escaping, Bluesky-URL-Kürzung + Facets, Thread-Splitting
    async def upload_media(self, account: "Account", media: "MediaItem",
                           progress=None) -> "UploadedMedia": ...
        # inkl. Abfragen bei asynchroner Verarbeitung, Alt-Text setzen
    async def build_link_card(self, account: "Account", url: str) -> Optional["LinkCard"]: ...
    async def post(self, account: "Account", draft: "Draft",
                   media: list["UploadedMedia"], *,
                   reply_to: Optional["PostRef"] = None,
                   scheduled_at: Optional[datetime] = None,
                   idempotency_key: Optional[str] = None) -> "PostRef": ...
        # PostRef: id, url, ggf. cid (Bluesky), scheduled_id (Mastodon/FB)
    async def delete(self, account: "Account", ref: "PostRef") -> None: ...
    async def cancel_scheduled(self, account: "Account", ref: "PostRef") -> None: ...
    async def revoke(self, account: "Account") -> None: ...
```

Hinweise zur Implementierung:
- `get_limits` liefert für Mastodon die Werte live aus `/api/v2/instance` (gecacht) und für Bluesky die Video-Limits aus `getUploadLimits`. Für die übrigen Plattformen liefert es statische, versionierte Werte.
- `validate` arbeitet rein lokal und schnell (für die Live-Zähler-Anzeige im Editor). `count` muss pro Plattform exakt die Server-Logik nachbilden: Mastodon-Regex für URLs und Mentions, twitter-text v3 für X.
- Die Alt-Text-Pflicht wird als Warnung (oder per Nutzer-Einstellung als Fehler) ausgegeben.
- `post` mit `idempotency_key` (Mastodon nativ, sonst lokale Deduplizierung über gespeicherte PostRefs), damit der Scheduler bei Wiederholungsversuchen keine Doppelposts erzeugt.
