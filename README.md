# HIIT Kraft 30

30-Minuten-Heimtraining mit zwei Kurzhanteln (bis 15 kg): Timer, 3D-Figur zur Übungsausführung, Wiederholungs- und Gewichtsprotokoll mit Fortschrittsvergleich, Rückmeldung pro Satz, leichtere Varianten, Claude-Coach, Sprachsteuerung und Spotify.

- `index.html` – App (Oberfläche im Anatomieatlas-Stil nach `design/DESIGN.md`; Tafel A / Tafel B, Einstiegswochen, Rückmeldung Leicht/Passt/Zu hart, Varianten, Abbruch mit Grund, Check-in, Protokoll, Einstellungen). Farben und Schriften stehen als CSS-Variablen in `:root` am Anfang des `<style>` (`--paper`, `--ink`, `--rule`, `--muscle`, `--muscle-support`, `--skin`, `--accent-text`, `--muted`, `--pressed`, `--f-display`, `--f-label`, `--f-text`)
- `figure.js` – 3D-Figur: lädt `models/man.glb` bzw. `models/woman.glb` (GLTFLoader + DRACOLoader, Three.js r128), färbt die Muskeln je Übung, Kamera Seite/Vorne/Hinten, Zeitlupe, Beschriftung mit Hinweislinien
- `exercises-anatomy.js` – Muskelgruppen und je Übung aktive/unterstützende Muskeln, Funktion und Formhinweise (A, B)
- `models/` – die beiden Figuren (GLB mit Draco, je etwa 2 MB, alle Übungen als Animation)
- `tools/blender/` – Skripte, die die Figuren in Blender erzeugen, animieren und exportieren
- `rig.js` – einfache 3D-Figur aus Grundkörpern; Rückfall, wenn ein Modell nicht lädt (die Bildunterschrift zeigt dann den Fehler)
- `design/` – verbindliche Designvorgabe und Entwürfe
- `test/e2e.mjs` – Ende-zu-Ende-Test (Playwright), Screenshots in `test/screens/`
- `coach.js` – Claude-API-Client (Plananpassung, Fragen im Training, Auswertung, Progressionscheck), ohne Schlüssel lokale Regeln
- `voice.js` – Sprachsteuerung mit Aktivierungswort „Coach“ und Sprachausgabe (Browser oder ElevenLabs)
- `spotify.js` – Spotify Web Playback SDK und Web API (PKCE, ohne Server)
- `bpm.js` – Tempo der Lieder: Takt tippen und Nachschlagen bei GetSongBPM
- `hr.js` – Live-Puls per Web Bluetooth (Apple Watch mit HeartBLE oder Brustgurt)
- `health.js` – Schlaf- und Ruhewerte vom eigenen Health-Worker
- `worker/` – Cloudflare Worker, der die Werte vom iPhone-Kurzbefehl annimmt und an die App ausliefert
- `docs/kurzbefehl.md` – Schritt-für-Schritt-Anleitung für den Kurzbefehl

Daten liegen im localStorage des Browsers (Key `hiit30.v2`), auch die Schlüssel. Hosting über GitHub Pages: https://erikah-cge.github.io/hiit-kraft-30/

## Einrichtung

Alles ist optional, ohne Einrichtung läuft die App lokal mit festen Regeln. Die Einstellungen öffnest du über den Button „Einstellungen“ auf dem Startbildschirm.

### Claude-Coach (Anthropic-API-Schlüssel)

1. Unter https://console.anthropic.com einen API-Schlüssel anlegen (Guthaben nötig).
2. In den Einstellungen bei „Anthropic-API-Schlüssel“ eintragen. Modell: Vorgabe `claude-sonnet-5-5`.
3. „Verbindung testen“ drücken.

Der Browser ruft die API direkt auf (`anthropic-dangerous-direct-browser-access`). Der Schlüssel liegt unverschlüsselt im localStorage dieses Browsers, daher nur auf eigenen Geräten verwenden und am besten einen eigenen Schlüssel mit Ausgabenlimit anlegen.

### Spotify

Voraussetzung: Spotify Premium.

1. Unter https://developer.spotify.com/dashboard eine App anlegen („Create app“), bei „Which API/SDKs are you planning to use?“ Web API und Web Playback SDK auswählen.
2. Als Redirect-URI exakt die Seitenadresse eintragen, so wie sie in den Einstellungen unter „Spotify“ angezeigt wird, z. B. `https://erikah-cge.github.io/hiit-kraft-30/` (mit Schrägstrich am Ende). Für lokale Tests zusätzlich z. B. `http://127.0.0.1:8000/`.
3. Unter „User Management“ das eigene Spotify-Konto (E-Mail) hinzufügen, solange die App im Entwicklungsmodus ist.
4. Die Client-ID in die Einstellungen kopieren und „Bei Spotify anmelden“ drücken. Nach der Rückleitung steht dort „angemeldet“.
5. „Playlists laden“ und eine Trainings-Playlist wählen. Optional Aufwärm-, Finisher- und Challenge-Lied suchen und auswählen, BPM eintragen, wenn die Figur im Takt laufen soll.

Die Musik läuft im Browser-Tab („HIIT Kraft 30“ als Spotify-Gerät). Spotify-Fehler erscheinen im Fuß der Trainingsansicht, das Training läuft ohne Musik weiter.

### Tempo (BPM) und Figur im Takt

Spotify liefert keine Tempo-Daten mehr, die App merkt sich das Tempo daher selbst je Titel (localStorage, `bpm`).

- Takt tippen: Im Training unter dem Timer „Takt tippen“ drücken (am PC Taste T), ab 4 Schlägen steht das Tempo fest und gilt für diesen Titel. Mehr als 2,5 s Pause beginnt neu.
- Feste Lieder: In den Einstellungen beim Aufwärm-, Finisher- und Challenge-Lied ein BPM-Feld.
- Automatisch: Unter https://getsongbpm.com/api einen kostenlosen Schlüssel anfordern (als Website die App-Adresse angeben, dort steht der verlangte Rücklink) und in den Einstellungen unter „Tempo (BPM)“ eintragen. Jeder neue Titel wird einmal nachgeschlagen, auch „nicht gefunden“ wird gespeichert. Getippte und eingetragene Werte haben Vorrang.

In den Sätzen dauert eine Wiederholung der Figur dann 4 Schläge, bei Stufe 1 (Tempo) etwa 3 s runter und 1 s hoch, auf ganze Schläge gerundet.

### Apple Watch

**Live-Puls während der Einheit**

1. Auf der Apple Watch die App HeartBLE installieren (App Store auf der Watch oder Watch-App am iPhone), öffnen und das Senden starten. Die Watch meldet sich dann als normaler Bluetooth-Pulsmesser. Ein Brustgurt mit Bluetooth geht genauso.
2. Die App in Chrome oder Edge öffnen, am PC, Mac oder Android-Handy. Safari und alle Browser auf dem iPhone können kein Web Bluetooth.
3. Einstellungen → „Apple Watch“ → „Live-Puls verwenden“ an, „Pulsgurt / Watch verbinden“, Gerät auswählen. Nach dem Neuladen der Seite muss neu verbunden werden (der Browser erlaubt die Geräteauswahl nur nach einem Klick); dafür erscheint auf dem Startbildschirm „Watch verbinden“.
4. Maximalpuls prüfen (Vorgabe 220 − 34 = 186). Der Ruhepuls kommt aus den Health-Daten, sonst 60, oder von Hand.

Im Training steht der Puls neben dem Timer, eingefärbt nach den fünf Zonen (Karvonen: Anteil der Herzfrequenzreserve, Zone 2 ab 60 %, Zone 3 ab 70 %, Zone 4 ab 80 %, Zone 5 ab 90 %). Die App speichert jede Sekunde einen Wert, dazu Durchschnitt und Maximum je Satz, Finisher und Challenge sowie die Zeit nach dem Finisher, bis der Puls unter 120 fällt. Mit „Wechsel nach Puls“ endet der Wechsel frühestens nach 15 s und spätestens nach 60 s, dazwischen, sobald der Puls unter 70 % des Maximalpulses liegt. Bricht die Verbindung ab, versucht die App dreimal neu zu verbinden.

**Schlaf und Ruhewerte (iPhone-Kurzbefehl → Cloudflare Worker → App)**

Einmalig den Worker einrichten (Cloudflare-Konto, kostenloser Tarif reicht):

```sh
cd worker
npm install
npx wrangler login
npx wrangler kv namespace create HEALTH        # ausgegebene id in wrangler.toml eintragen
npx wrangler secret put HEALTH_TOKEN           # zufälliges Token einfügen, z. B. aus: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
npx wrangler deploy
```

Das Token nur im Passwortmanager, im Kurzbefehl und in den App-Einstellungen ablegen, nie im Repo. Der Worker nimmt `POST /health` an und liefert `GET /health/latest` und `GET /health?days=7`, jeweils mit `Authorization: Bearer <Token>`. Browser-Zugriff ist nur von `https://erikah-cge.github.io` und von `http://127.0.0.1` erlaubt. Lokal testen: `.dev.vars` mit `HEALTH_TOKEN=…` anlegen (ist in `.gitignore`) und `npx wrangler dev`.

Dann am iPhone den Kurzbefehl nach [docs/kurzbefehl.md](docs/kurzbefehl.md) anlegen: Schlaf der letzten Nacht, letzter Ruhepuls, HRV der Nacht, Schritte und aktive Energie von gestern; Automation täglich 7:00 und beim Aufwachen.

In der App: Einstellungen → „Schlaf und Ruhewerte“ → Health-Server-URL und Token eintragen → „Verbindung testen“. Liegen Werte von heute oder gestern vor, zeigt der Startbildschirm „Letzte Nacht: 6:40 h Schlaf · Ruhepuls 58 · HRV 42“ und den Vergleich mit dem 7-Tage-Mittel, und der Check-in übernimmt die Schlafstufe (unter 5 h = 1, 5–6 = 2, 6–7 = 3, 7–8 = 4, ab 8 = 5). Ruhepuls 5 Schläge über dem Mittel oder HRV 15 % darunter heißt: leichter trainieren; der Coach und die lokalen Regeln nehmen dann 2,5 kg weniger und eine Wiederholung mehr Reserve.

### Sprachsteuerung und Ansagen

- Spracherkennung funktioniert in Chrome und Edge. Beim ersten Start fragt der Browser nach dem Mikrofon.
- Aktivierungswort „Coach“, danach der Befehl, z. B. „Coach, fertig zwölf“, „Coach, zu hart“, „Coach, wie lange noch“, „Coach, Musik leiser“. Alles, was kein fester Befehl ist, geht an den Claude-Coach.
- Ansagen lassen sich in den Einstellungen abschalten.

### ElevenLabs (optional)

Für eine natürlichere Stimme unter https://elevenlabs.io einen API-Schlüssel anlegen, in den Einstellungen „Stimme: ElevenLabs“ wählen, Schlüssel und optional eine Voice-ID eintragen. Ohne gültigen Schlüssel spricht die Browserstimme.

## 3D-Figuren

Zwei Figuren, passend zu den späteren Profilen: Mann (180 cm, etwa 82 kg, sportlich) und Frau (etwa 166 cm, normale Statur). Bis es Profile gibt, ist der Mann Standard; umschalten in den Einstellungen unter „Figur“.

- Körper: erzeugt mit [MPFB 2](https://static.makehumancommunity.org/mpfb.html) (MakeHuman-Erweiterung für Blender, Version 2.0.17, Blender 5.2). Das Plugin selbst steht unter GPL-3.0, die damit erzeugten MakeHuman-Körper (Basismesh, Formziele, Rig „game_engine“ mit Gewichten) sind CC0 und liegen nicht unter der GPL. Keine weiteren fremden Assets: Augen, Haarknoten und Hanteln sind im Skript gebaut.
- Oberfläche: matte Haut `#EAC9A2`, eng anliegende Sportkleidung in Sepia (beide Figuren: kurzärmeliges Shirt `--cloth-top` und Shorts `--cloth-shorts`, Farben in `index.html` unter `:root`), ruhige geschlossene Augen, feine Tintenkontur (Hülle mit konstanter Pixelbreite im Shader). Arbeitende Muskeln färben Shirt und Shorts an ihrer Stelle mit.
- Muskelmaske: Textur `mask_<figur>` (2048 × 2048, im GLB als Basisfarbtextur), erzeugt von `tools/blender/mask.py`. Kanäle: R = Muskelgruppe (ID wie `MUSCLES` in `exercises-anatomy.js`, Wert/20), G = Kleidung (1 Shorts, 2 Shirt, 3 Auge, 4 Haar), B = Körperseite (1 links, 0 rechts). Für jedes Texel wird der Punkt auf dem Körper in Ruhepose bestimmt und über glatte Regeln in Gliedmaßen- bzw. Rumpfkoordinaten (Länge entlang des Knochens, Winkel um die Achse) einer Gruppe zugeordnet; so entstehen geschlossene Flächen mit Kurven als Grenzen statt Netzkanten. `figure.js` liest die Textur ungefiltert und mischt die Farben von vier Nachbartexeln: scharfe, nicht treppige Übergänge. Gruppen: Brust, vordere und seitliche Schulter, Trizeps, Bizeps, oberer Rücken, breiter Rückenmuskel, unterer Rücken, gerader und schräge Bauchmuskeln, Gesäß, Quadrizeps, hintere Oberschenkel, Adduktoren, Waden. Die Formen sind eine Atlas-Näherung, keine exakte Anatomie; Grenzen ändert man in `mask.py` (`classify`). Zusätzlich trägt das Farbattribut `COLOR_0` je Fläche dieselbe Einteilung, nur für die Beschriftungsanker.
- Animationen: alle Übungen inklusive Varianten (bridge1 bridge2 bridge2w burpee chest deadbug deadbuglegs floorpress goblet hipflex kneepushup kniehebe lunge lungebw press pushup rdl row row1 sideplank sideplankknee slrdl splitsquat sqa squatbw thruster walk, dazu catcow für den zweiten Teil von „Hüftbrücke + Katze-Kuh“). Sie liegen hintereinander in einer Animation „all“ (24 Bilder/s); Start und Länge jeder Übung, Kamera-Rahmen, Hanteln und Umkehrpunkt stehen als JSON in den Extras des Rigs (`hiit`), `figure.js` schneidet daraus die Clips. Probesätze zeigen den Split Squat.
- Beschriftung: Die Ankerpunkte der Muskeln sind Vertices nahe dem Schwerpunkt der Gruppe und werden über die Knochengewichte mitbewegt; Formhinweise hängen an Gelenken des Rigs. Liegt ein Muskel auf der abgewandten Seite, wird seine Beschriftung ausgeblendet.

### Figuren neu bauen

Voraussetzung: Blender 5.2 mit der MPFB-Erweiterung (über Edit → Preferences → Get Extensions → „MPFB“ installieren).

```sh
blender -b --python tools/blender/build_models.py -- man
blender -b --python tools/blender/build_models.py -- woman
```

Das Skript baut Körper, Maske, Rig und alle Animationen, speichert `tools/blender/<figur>.blend` (nicht im Repo) und exportiert danach in einem frischen Blender-Prozess über `tools/blender/export_glb.py` nach `models/<figur>.glb` (in derselben Sitzung exportiert hat Blender 5.2 einzelne Übungen versetzt). Dauer je Figur etwa 6–8 Minuten.

Nützliche Optionen:

- `--only splitsquat,pushup` nur diese Übungen, Ausgabe nach `models/test-<figur>.glb` und `tools/blender/test-<figur>.blend`
- `--preview <ordner> [--rest] [--res 360]` Kontrollbilder je Übung (Umkehrpunkt von Seite/Vorne/Hinten und Startpose) mit farbig markierten Muskelgruppen
- `--noexport` nur bauen und speichern

### Eine Übungsanimation ändern

Die Bewegungen stehen in `tools/blender/poses.py`, je Übung eine Funktion `ex_<schlüssel>`. Sie beschreibt wenige Bewegungsparameter als Schlüsselbilder (z. B. `d` = Tiefe 0…1 mit Dauer in Sekunden) und eine Funktion `make(h)`, die daraus Ziele für den Solver baut: Lage des Beckens, Beugung von Wirbelsäule und Hals, Fußgelenk- und Handgelenkziele (IK) mit Pol-Richtungen für Knie und Ellbogen, Hand- und Fußstellung. Für jedes Einzelbild wird neu gelöst, daher bleiben Füße und Hände exakt am Boden. Vorgehen:

1. Funktion in `poses.py` anpassen (z. B. Tiefe, Vorneigung, Dauer der Schlüsselbilder).
2. Schnell prüfen: `blender -b --python tools/blender/build_models.py -- man --only <schlüssel> --preview vorschau/` und die Bilder ansehen. Das Protokoll zeigt je Übung `minz` (tiefster Punkt, sollte etwa 0 sein).
3. Beide Figuren neu bauen (siehe oben) und `models/*.glb` committen.

Von Hand in Blender: `tools/blender/man.blend` öffnen, in der Aktion „all“ den Bildbereich der Übung bearbeiten (Start steht in den Rig-Eigenschaften unter `hiit`), speichern und mit `blender -b tools/blender/man.blend --python tools/blender/export_glb.py -- models/man.glb` exportieren. Beim nächsten Lauf von `build_models.py` werden Handänderungen überschrieben; dauerhafte Änderungen gehören nach `poses.py`.

Muskeln und Formhinweise einer Übung stehen in `exercises-anatomy.js` und brauchen keinen Neubau.

## Bedienung am PC

Leertaste = Training starten (Startbildschirm) / Satz fertig / Fortsetzen, Pfeil hoch/runter = Wiederholungen ±1, Pfeil rechts = Weiter, Pfeil links = Zurück, P = Pause, T = Takt tippen. In Textfeldern sind die Tasten abgeschaltet.

Im Satz schaltet die Leiste unter der Figur die Ansicht (Seite, Vorne, Hinten) und die Zeitlupe (halbe Geschwindigkeit); die Wahl merkt sich der Browser unter `hiit30.view`. Im Wechsel verlängert „+15 s“ die Pause.

## Tests

```sh
npm i playwright && npx playwright install chromium
node test/e2e.mjs .
```

Prüft Start, Check-in, Sätze, Varianten, Abbruch, Protokoll, Einstellungen, Coach (gemockte API), Sprachbefehle und das Laden alter Daten in 1600×900 und 390×844. Kontaktbögen aller Übungen am Umkehrpunkt (beide Figuren, drei Ansichten) liegen in `test/screens/figuren/`, die Bildschirme in 1440×900 und 1920×1080 in `test/screens/`.

Kontaktbögen neu erzeugen (Playwright, Python mit Pillow):

```
node test/figuren.cjs . out/fig man 1440 900 "" --start pushup,kneepushup,burpee,catcow,row,row1,rdl,slrdl
python test/sheet.py out/fig "man-*-side.png" test/screens/figuren/mann-side.png 6
```

`figuren.cjs` schreibt zusätzlich `<figur>-report.json`: sichtbare, verdeckte und abgeschnittene Beschriftungen je Ansicht und die Ankerprüfung (liegt jeder Beschriftungsanker in der Maske auf seiner Muskelgruppe).
