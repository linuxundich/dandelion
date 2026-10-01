# Namenssuche für die App

Stand: 2026-10-01 · App-ID-Schema: `de.linuxundich.<Name>`

> **Nachtrag 2026-10-01:** Ursprünglich war `io.github.linuxundich.<Name>` geplant. Umgestellt auf die Blog-Domain, damit Dandelion und Blocksatz demselben Schema folgen. Die Prüfung für Flathub läuft über `https://linuxundich.de/.well-known/org.flathub.VerifiedApps.txt`, siehe `blocksmith/docs/flathub-verification.md`.

Gesucht ist ein Name für eine native GNOME-App (GTK4/libadwaita). Man schreibt einen Beitrag einmal und veröffentlicht ihn auf Mastodon, Bluesky, X, Facebook und LinkedIn, sofort oder zeitgesteuert. Der Name soll kurz sein, sich auf Deutsch und Englisch aussprechen lassen, international verständlich und GNOME-typisch sein (vgl. Fragments, Tuba, Amberol, Foliate, Errands, Letterpress). Namen wie „Tootle“ scheiden aus.

## Methode

Alle Prüfungen liefen am 2026-10-01 automatisiert oder per Websuche:

| Quelle | Wie geprüft |
|---|---|
| GitHub | `gh api search/repositories`, einmal `"<name> in:name"` nach Sternen sortiert, einmal mit dem Zusatz `mastodon OR bluesky OR fediverse OR gtk OR libadwaita (OR crosspost)` |
| GitLab.com | REST-API `/api/v4/projects?search=<name>` |
| GNOME GitLab | REST-API auf gitlab.gnome.org. **Hinweis:** Die API hat mit HTTP 429 abgeblockt (`retry-after: 600`). Das Ergebnis eines zweiten Versuchs steht im Abschnitt „GNOME GitLab“ unten. |
| Flathub | `POST https://flathub.org/api/v2/search`. Gewertet wurden nur Treffer, deren App-Name den Kandidaten enthält. |
| AUR | RPC `https://aur.archlinux.org/rpc/v5/search/<name>?by=name` |
| Arch-Repos | `https://archlinux.org/packages/search/json/?name=<name>`. Für keinen Kandidaten gab es einen Treffer, deshalb fehlt die Spalte in der Tabelle. |
| Domains | RDAP über `rdap.org` (liefert das Registrierungsdatum). Wenn rdap.org drosselte (HTTP 429), wurde per DNS-over-HTTPS (`dns.google`, NS-Abfrage) nachgesehen. `dig` und `whois` sind auf diesem Rechner nicht installiert. NXDOMAIN heißt nur „wahrscheinlich frei“. Verbindlich ist erst die Abfrage beim Registrar. |
| Marken/Produkte | Websuche nach „<Name> app/software/social“. Das ist **keine** Markenrecherche bei DPMA, EUIPO oder USPTO. Vor einer endgültigen Entscheidung sollte man den Favoriten dort noch nachschlagen. |

Zur App-ID: `de.linuxundich.<Name>` ist für jeden Kandidaten frei, weil der Namensraum der eigenen Blog-Domain linuxundich.de gehört. Wichtiger ist, ob es auf Flathub schon eine App mit gleichem Anzeigenamen gibt. Das wurde bei jedem Kandidaten geprüft.

Nebenbefund: Auf Flathub gibt es derzeit **keinen** Crossposter für Mastodon, Bluesky und weitere Netzwerke. Die Suche nach „crosspost“ bringt keinen Treffer, „bluesky mastodon“ zeigt nur Clients wie Tuba und Tokodon. Die Nische ist also frei.

---

## Steckbriefe der 10 Kandidaten

### 1. Strew

- **Bedeutung:** engl. „streuen, verstreuen“, z. B. Saatgut oder Blüten. Das passt zum Bild: einmal schreiben, überall ausstreuen. Gesprochen /struː/, also wie „Struh“. Deutsche könnten es anfangs falsch als „Strew“ mit w lesen. Das Wort ist kurz (eine Silbe), aber nicht allen Nicht-Muttersprachlern geläufig.
- **Konnotation:** neutral bis positiv (Saat, Konfetti). Keine negativen Nebenbedeutungen gefunden.
- **GitHub:** nur 66 Repos mit „strew“ im Namen, alle unbedeutend (höchstens 3 Sterne): ein Mailinglisten-Server, ein Dotfiles-Tool, eine kleine Programmiersprache. Kein Bezug zu Social Media oder GTK.
- **GitLab.com:** keine echten Treffer, nur Teilstrings wie „chatstrew“.
- **Flathub:** keine App dieses Namens. **AUR:** nichts. **Arch:** nichts.
- **Marken/Produkte:** „Strew“ heißt eine Home-Education-App für Eltern (iOS/Android, strew.app, thestrew.com). Sie gehört zum Bildungsbereich, nicht zu Social Media oder Messaging, belegt aber die naheliegende Domain.
- **Domains:** strew.app ist vergeben (seit 2025-02-19, die Bildungs-App). strew.org ist vergeben (seit 2026-04-10). strew.dev existiert. **Wahrscheinlich frei:** getstrew.app, strewapp.org, strew.social.
- **Fazit:** das sauberste Ergebnis im ganzen Feld. Die Schwächen sind die belegte .app-Domain und eine kleine Ausspracheschwelle.

### 2. Dandelion

- **Bedeutung:** engl. „Löwenzahn“ bzw. „Pusteblume“. Ein Pusten, und die Samen fliegen in alle Richtungen. Das Bild ist sehr anschaulich und gibt ein schönes Icon her. Gesprochen /ˈdændɪlaɪən/. Auf Deutsch ist es gut sprechbar, aber dreisilbig und damit eher lang.
- **Konnotation:** positiv (Natur, Leichtigkeit). Löwenzahn gilt auch als Unkraut, das spielt aber kaum eine Rolle.
- **GitHub:** gut 2.000 Repos, darunter ein Git-Deploy-Tool (732 Sterne) und ein Grafik-Framework. **Kollision im Social-Media-Bereich:** `gsantner/dandelion` (116 Sterne) ist ein inoffizieller diaspora\*-Client für Android und steht auf F-Droid als „dandelion\*“. Das Repo ist nicht archiviert, der letzte Push war aber am 2023-02-11. Das Projekt ruht also.
- **GitLab.com:** kleinere Projekte wie Filterlisten und ein Minecraft-Server. Nichts mit Social-Media-Bezug.
- **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** Dandelion Chocolate; eine US-Marke „DANDELION“ von Dandelion Science Corp. für Neurostimulations-Software; ein Ad-Tech-Dienstleister (dandelioninc.com). Keine Social-Media-Marke.
- **Domains:** dandelion.app ist vergeben (seit 2024-02-14), dandelion.org auch (seit 1998). **Wahrscheinlich frei:** getdandelion.app, dandelionapp.org.
- **Fazit:** sehr bildstark und international verständlich. Der Name ist etwas lang, und es gibt den ruhenden diaspora\*-Client mit gleichem Namen.

### 3. Tidings

- **Bedeutung:** engl. (gehoben) „Nachrichten, Kunde“, bekannt aus „glad tidings“. Gesprochen /ˈtaɪdɪŋz/. Das klingt literarisch und GNOME-typisch, ähnlich wie „Foliate“. Deutschen ist das Wort weniger geläufig.
- **Konnotation:** positiv, leicht altmodisch und weihnachtlich („good tidings“).
- **GitHub:** 187 Repos, darunter `poetaster/tidings`, ein RSS/Atom-Reader für **SailfishOS** (Linux-Mobil, 23 Sterne), `mozilla/django-tidings` (eine Benachrichtigungs-Bibliothek) und tidings-rss (OPML-Sammlungen, 579 Sterne).
- **GitLab.com:** `paveloom-g/apps/Tidings`, ein RSS-Reader („ohne eingebauten Browser“). Letzte Aktivität 2022-08-23, also inaktiv.
- **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** tidings.com ist ein kommerzieller Newsletter-Dienst, der Newsletter aus Facebook-Seiten baut. Das liegt nah an Social Media. Dazu kommen eine Android-App „Tidings News Feeds“ und ein UI-Kit.
- **Domains:** tidings.app ist vergeben (seit 2021-02-04), tidings.org auch (seit 1997). **Wahrscheinlich frei:** gettidings.app, tidingsapp.org.
- **Fazit:** stilistisch sehr passend. Mehrere Feed-Reader tragen schon diesen Namen, und ein Newsletter-Dienst mit Social-Media-Nähe ist eine leichte Belastung.

### 4. Sower

- **Bedeutung:** engl. „Sämann, Säer“. Gesprochen /ˈsoʊər/. Deutsche lesen es leicht als „Sauer“. International ist das Wort kaum bekannt.
- **Konnotation:** stark biblisch geprägt (Gleichnis vom Sämann). Mehrere christliche Apps heißen so.
- **GitHub:** `sower-proxy/sower`, ein transparenter Proxy mit 461 Sternen, außerdem ein Kubernetes-Job-Dispatcher.
- **GitLab.com:** nur Kleinkram. **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** die Bibel-Apps „Seed Sower“ und „The Sower“, Sower Solutions (Engineering-Software), SOWER (Pre-/Postprocessing an der University of Colorado).
- **Domains:** sower.app ist vergeben (seit 2024-07-15), sower.org auch (seit 1997). **Wahrscheinlich frei:** getsower.app, sowerapp.org.
- **Fazit:** Das Bild stimmt, aber Aussprache und religiöse Prägung sprechen dagegen.

### 5. Seedling

- **Bedeutung:** engl. „Sämling, Setzling“. Gesprochen /ˈsiːdlɪŋ/ und gut verständlich. Der Bezug ist eher „Wachstum“ als „Verteilen“.
- **Konnotation:** positiv, aber etwas niedlich. Der Name spielt nicht direkt auf „Veröffentlichen“ an.
- **GitHub:** gut 1.700 Repos, zum Beispiel bevy_seedling (Audio, 160 Sterne), eine Spring-Vorlage und `tskrio/seedling` (Aufgaben-App). Das Emoji `:seedling:` taucht in vielen READMEs auf und macht die Suche unscharf.
- **GitLab.com:** nur Kleinkram. **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** sehr viele Firmen mit diesem Namen: Seedling Earth (CO₂-Software), seedling.sh (Team-Anerkennung), eine Fruchtbarkeits-App, eine Coaching-App, die Kinder-App „Seedling Grow“. Keine Social-Media-Marke, aber der Name ist ziemlich verbraucht.
- **Domains:** seedling.app ist vergeben (seit 2018), seedling.org auch (seit 1998), getseedling.app existiert ebenfalls. **Wahrscheinlich frei:** seedlingapp.org.
- **Fazit:** unbedenklich, aber austauschbar und inhaltlich etwas daneben.

### 6. Fanfare

- **Bedeutung:** in DE und EN identisch, „Fanfare“ als festlicher Ankündigungsruf. Jeder versteht es sofort, gesprochen /ˈfænfɛər/ bzw. [fanˈfaːʁə].
- **Konnotation:** positiv, laut, „Aufmerksamkeit!“. Manche könnten es als marktschreierisch empfinden.
- **GitHub:** 243 Repos. Ein Account `fanfare` mit Browser-Erweiterungen (373 Sterne) und ein Anki-Add-on. Kein GTK- oder Social-Media-Bezug.
- **GitLab.com:** fast nur Seiten echter Blaskapellen. **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** **Fanfare Global** (Singapur, gegründet 2017) betreibt eine Social-Commerce- und Video-Sharing-App „Fanfare – Share, Earn, Shop“ für iOS und Android. Das ist eine Kollision im Social-Media-Bereich. Dazu kommt Fanfare Entertainment (Apps für Musiker).
- **Domains:** fanfare.app ist vergeben (seit 2018), fanfare.org auch (seit 2003), getfanfare.app existiert. **Wahrscheinlich frei:** fanfareapp.org.
- **Fazit:** schöner und klarer Name, aber eine Social-Media-App mit genau diesem Namen gibt es schon.

### 7. Crier

- **Bedeutung:** engl. „Ausrufer“, als „town crier“ der Stadtausrufer. Gesprochen /ˈkraɪər/. Deutsche hören darin leicht „cry“ und denken an Weinen. Ohne „Town“ davor verstehen es viele nicht.
- **Konnotation:** zweideutig. Ein „crier“ kann auch ein Schreihals oder Heulsuse sein.
- **GitHub:** **direkte Funktionskollision.** `queelius/crier` (18 Sterne, auch auf PyPI) ist ein CLI-Werkzeug, das genau diese Aufgabe erledigt: Crossposting nach Bluesky, Mastodon, Threads, dev.to, Hashnode und weitere. Dazu kommt `skorotkiewicz/crier` (Push-Benachrichtigungen, 34 Sterne).
- **GitLab.com:** Varianten von „towncrier“ (Changelog-Werkzeug). **Flathub / Arch:** nichts.
- **AUR:** `crier` und `crier-bin` sind belegt (das Push-Tool von skorotkiewicz).
- **Marken/Produkte:** die regionale News-App „Town Crier Wire“. Außerdem ist „towncrier“ ein bekanntes Python-Changelog-Werkzeug.
- **Domains:** crier.app ist vergeben (seit 2026-01-05), crier.org auch (seit 2004). **Wahrscheinlich frei:** getcrier.app, crierapp.org.
- **Fazit:** gestrichen. Ein gleichnamiger Crossposter existiert, das AUR-Paket ist belegt, und die Konnotation ist ungünstig.

### 8. Carillon

- **Bedeutung:** frz./engl. „Glockenspiel“ (im Turm). Viele Glocken klingen gleichzeitig, das ist eine schöne Metapher für viele Netzwerke auf einmal. Aussprache: EN /ˈkærɪlɒn/, FR [kaʁiˈjɔ̃]. Wie man es richtig sagt, ist unklar.
- **Konnotation:** positiv, festlich, kirchlich.
- **GitHub:** `pimalaya/carillon`, ein CLI, das PIM-Sammlungen überwacht (67 Sterne, aus dem Umfeld von himalaya). Außerdem Hackintosh-Bootsounds.
- **GitLab.com:** zwei Arduino-Projekte. **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** **Carillon (carillon.dev)** ist ein europäischer Push-Benachrichtigungsdienst von Exostack, also nah an Messaging. Dazu kommen eine Gebäude-App mit Messenger und Kirchen-Apps.
- **Domains:** carillon.app ist vergeben (seit 2022), carillon.org auch (seit 1996). **Wahrscheinlich frei:** getcarillon.app, carillonapp.org.
- **Fazit:** elegant, aber für Deutsche schwer auszusprechen und nah an einem Push-Dienst.

### 9. Herald

- **Bedeutung:** engl. „Herold, Verkünder“. Gesprochen /ˈhɛrəld/. Auf Deutsch kennt man „Herold“, das Wort ist also verständlich.
- **Konnotation:** neutral bis positiv. Allerdings ist „Herald“ ein häufiger Zeitungsname (Herald Sun, New York Herald, Miami Herald).
- **GitHub:** gut 2.600 Repos und damit stark verbraucht. Darunter ein Terminal-Mailclient `herald-email/herald-mail-app` (146 Sterne), django-herald (Messaging), nagios-herald und das Release-Ankündigungs-Werkzeug `n8han/herald`.
- **GitLab.com:** unter anderem ein Slack-Geburtstagsbot und ein VK-zu-Slack-Bot.
- **AUR:** `herald` ist belegt (eine systemd-Journal-zu-XMPP-Brücke). **Flathub / Arch:** nichts.
- **Marken/Produkte:** viele Zeitungsmarken. Ein Social-Media-Produkt mit diesem Namen wurde nicht gefunden.
- **Domains:** herald.app ist vergeben (seit 2018), herald.org auch (seit 1997), getherald.app existiert.
- **Fazit:** verbraucht, das AUR-Paket ist belegt, die Verwechslungsgefahr mit Zeitungen ist hoch.

### 10. Salvo

- **Bedeutung:** „Salve“, also ein gleichzeitiger Schuss aus vielen Rohren. Gesprochen /ˈsælvoʊ/, auf Deutsch sofort als „Salve“ verständlich.
- **Konnotation:** **militärisch.** Für ein freundliches GNOME-Werkzeug passt das schlecht.
- **GitHub:** `salvo-rs/salvo`, ein großes Rust-Webframework mit 4.434 Sternen. Das ist die dominierende Kollision.
- **GitLab.com:** nur Kleinkram. **Flathub / AUR / Arch:** nichts.
- **Marken/Produkte:** **Salvo (wearesalvo.com)** übernimmt Social-Media-Management und das Planen von Facebook- und Instagram-Beiträgen für Handwerksbetriebe. Das ist eine Kollision im selben Feld. Dazu kommen eine Dating-App und Salvo Health.
- **Domains:** salvo.app ist vergeben (seit 2018), salvo.org auch (seit 2004), getsalvo.app existiert.
- **Fazit:** gestrichen, wegen der Social-Media-Firma gleichen Namens, des großen Rust-Projekts und der Militärassoziation.

---

## Übersicht

Legende für die Bewertung: ★★★ sehr gut · ★★ brauchbar · ★ problematisch · ✗ gestrichen

| Name | Bedeutung | GitHub/GitLab | Flathub | AUR | Marken | .app | .org | Bewertung |
|---|---|---|---|---|---|---|---|---|
| **Strew** | streuen, verstreuen | nur Kleinstprojekte, nichts Relevantes | frei | frei | Home-Education-App „Strew“ (kein Social Media) | vergeben (2025) | vergeben (2026) | ★★★ |
| **Dandelion** | Pusteblume, Löwenzahn | diaspora\*-Client für Android (ruht seit 2023), Git-Deploy-Tool | frei | frei | Dandelion Chocolate, Neurotech-Marke | vergeben (2024) | vergeben (1998) | ★★½ |
| **Tidings** | Kunde, Nachrichten | Sailfish-Feedreader, alter RSS-Reader auf GitLab, django-tidings | frei | frei | tidings.com (Newsletter aus Facebook-Seiten) | vergeben (2021) | vergeben (1997) | ★★ |
| **Seedling** | Setzling | viele, keins relevant (Emoji verwässert die Suche) | frei | frei | viele Firmen (CO₂, HR, Fruchtbarkeit) | vergeben (2018) | vergeben (1998) | ★★ |
| **Sower** | Sämann | Proxy „sower“ (461 Sterne) | frei | frei | Bibel-Apps, Engineering-Software | vergeben (2024) | vergeben (1997) | ★½ |
| **Fanfare** | Fanfare | nichts Relevantes | frei | frei | **Fanfare Global: Social-Commerce-App** | vergeben (2018) | vergeben (2003) | ★½ |
| **Carillon** | Glockenspiel | pimalaya/carillon (CLI) | frei | frei | carillon.dev (Push-Dienst) | vergeben (2022) | vergeben (1996) | ★½ |
| **Herald** | Herold | sehr viele, u. a. Mailclient, Messaging-Bibliotheken | frei | **belegt** (`herald`) | Zeitungsnamen | vergeben (2018) | vergeben (1997) | ★ |
| **Crier** | Ausrufer | **queelius/crier = Crossposter für Bluesky/Mastodon** | frei | **belegt** (`crier`) | Town Crier Wire, towncrier | vergeben (2026) | vergeben (2004) | ✗ |
| **Salvo** | Salve | salvo-rs (4,4k Sterne) | frei | frei | **wearesalvo.com: Social-Media-Management** | vergeben (2018) | vergeben (2004) | ✗ |

GNOME GitLab: siehe den folgenden Abschnitt. Arch-Repos: für keinen Kandidaten ein Paket.

### GNOME GitLab

Nach der 10-minütigen Sperre ergab die zweite API-Abfrage für alle zehn Kandidaten (und Samara) HTTP 200 mit **leerer Trefferliste**. Eine Gegenprobe mit einem bekannten Projekt („fragments“) war danach nicht mehr möglich, weil die API wieder mit HTTP 429 sperrte. Deshalb lässt sich nicht ausschließen, dass die anonyme Suche schlicht nichts zurückgibt. Auch die Websuche mit `site:gitlab.gnome.org` fand für Strew, Dandelion und Tidings nichts. **Vorläufiges Ergebnis:** keine Kollision auf GNOME GitLab bekannt. Für den Favoriten sollte man das einmal eingeloggt im Browser unter https://gitlab.gnome.org/explore/projects?name=strew bestätigen.

### Vorab aussortiert (Startliste und eigene Ideen)

Diese Namen wurden mit denselben automatischen Abfragen geprüft (Flathub, AUR, Arch, RDAP), teilweise auch auf GitHub, und dann verworfen:

| Name | Grund |
|---|---|
| Waft | **AUR:** „Waft“ ist schon ein GTK4/libadwaita-Shell-Projekt (waft-launcher, waft-overview, waft-settings und weitere) und damit eine direkte Kollision im GNOME-Umfeld. |
| Chorus | **Flathub:** „Chorus“ existiert bereits (`space.f1nn.chorus`), dazu viele Audio-Plugins im AUR. |
| Flock | Flock war ein Social-Media-Browser (2005–2011), Flock.com ist ein Team-Messenger, und `flock` ist ein bekanntes Unix-Kommando. |
| Murmur | So heißt der Server von Mumble (AUR `murmur-git`), dazu der IRC-Client `murmur-bin`. |
| Pollen | Pollen ist ein bekanntes Racket-Publishing-System (1,2k Sterne), dazu kommt Pollen Robotics. Außerdem steht der Name für Allergie. |
| Kite | völlig verbraucht (Kite-KI-Coding, Kubernetes-Dashboard, koding/kite …). |
| Spread | Spread-Toolkit (Messaging), Assoziation mit Tabellenkalkulation, zu generisch. |
| Echoes | generisch, kaum unterscheidbar, außerdem „Echo“ (Amazon). |
| Polycast | klingt technisch und nicht GNOME-typisch. Polymer „Polycasts“, PHP-Bibliothek PolyCast. polycast.org war allerdings wahrscheinlich frei. |
| Bellman | Bellman-Ford-Algorithmus, zk-SNARK-Bibliothek „bellman“ (1,1k Sterne), „bell man“ klingt nach Hotelpage. |
| Bugle | `rknightuk/bugle` ist ein ActivityPub-Server, also Fediverse-Kollision. |
| Missive, Megaphone, Proclaim | Missive ist ein bekannter Team-Mail-Client, Megaphone eine Podcast-Werbeplattform (Spotify), Proclaim eine Kirchen-Präsentationssoftware (Faithlife). |
| Ripple, Starling, Volley, Plume | Ripple (Krypto), Starling (Bank, Starling Message Queue, ein neuer Linux-Desktop „Starling“), Volley (Google-Netzwerkbibliothek), Plume (föderierte Blog-Software im AUR). |
| Samara, Wisp, Flurry | Samara (Flugsamen des Ahorns) ist hübsch, erinnert aber vor allem an die russische Stadt. Wisp: Gleam-Webframework, Lisp-Dialekt. Flurry: Yahoo-Analytics-SDK. |

---

## Empfehlung

### Favorit: **Strew**

- **Bedeutung passt genau:** „to strew“ heißt etwas weit verstreuen. Genau das tut die App: einen Beitrag schreiben und auf alle Netzwerke verteilen. Das Bild der Saat, die man mit der Hand ausstreut, gibt ein klares, GNOME-taugliches Icon her (Hand oder Wurfbewegung mit Körnern oder Punkten in Netzwerkfarben).
- **Kurz und GNOME-typisch:** eine Silbe, ein englisches Alltagsverb, im selben Stil wie Errands, Fragments oder Tuba.
- **Kaum Kollisionen:** kein relevantes GitHub- oder GitLab-Projekt, nichts auf Flathub, im AUR oder in den Arch-Repos, keine Social-Media- oder Messaging-Marke. Unter den geprüften Namen ist das Feld hier mit Abstand am freiesten.
- **Schwächen, ehrlich benannt:**
  1. strew.app gehört einer Home-Education-App und strew.org ist ebenfalls vergeben. Als Ausweichdomains sind getstrew.app, strewapp.org und strew.social laut DNS wahrscheinlich frei. Für eine GNOME-App reicht ohnehin `linuxundich.github.io/strew` oder eine Seite auf linuxundich.de.
  2. Die Aussprache /struː/ ist für Deutsche nicht selbsterklärend. In README und App-Info kann man das mit einem Hinweis („spricht sich wie *Stru*“) entschärfen.
  3. Eine echte Markenrecherche (DPMA, EUIPO, USPTO) steht noch aus.
- App-ID: `de.linuxundich.Strew`

### Alternative 1: **Dandelion**

Die Pusteblume ist das anschaulichste Bild im ganzen Feld: einmal pusten, und alles fliegt in alle Richtungen. Der Name ist international verständlich und gibt ein sehr schönes Icon her. Auf Flathub, im AUR und in den Arch-Repos ist er frei. Dagegen spricht die Länge (drei Silben) und vor allem der gleichnamige diaspora\*-Client „dandelion\*“ für Android, also ein Projekt im selben Themenfeld. Er ruht zwar seit Februar 2023, steht aber noch auf F-Droid. App-ID: `de.linuxundich.Dandelion`

### Alternative 2: **Tidings**

Klingt nach GNOME (literarisch wie Foliate) und bedeutet „Nachrichten, Kunde“. Auf Flathub, im AUR und in den Arch-Repos ist der Name frei. Allerdings gibt es schon Feed-Reader mit diesem Namen (SailfishOS, ein inaktives GitLab-Projekt), und tidings.com verkauft einen Newsletter-Dienst, der auf Facebook-Seiten aufsetzt. Außerdem ist „Tidings“ für Deutsche weniger geläufig als die beiden anderen Namen. App-ID: `de.linuxundich.Tidings`

## Quellen (Auswahl)

- Crier, Crossposter: https://github.com/queelius/crier · https://dev.to/queelius/crier-cross-post-your-content-everywhere-3i0
- dandelion\* (diaspora\*-Client): https://github.com/gsantner/dandelion · https://f-droid.org/en/packages/com.github.dfa.diaspora_android/
- Strew (Home-Education-App): https://strew.app/
- Fanfare Global: https://apps.apple.com/us/app/fanfare-share-earn-shop/id6448972883
- Tidings Newsletter: https://tidings.com/ · Tidings für SailfishOS: https://github.com/poetaster/tidings
- Carillon Push-Dienst: https://www.carillon.dev/
- Salvo Social-Media-Management: https://wearesalvo.com/social-media
- Seedling-Firmen: https://www.seedling.earth/en-us · https://www.seedling.sh/
- Dandelion-Marke: https://uspto.report/TM/90054330
