# HIIT Kraft 30

30-Minuten-Heimtraining mit zwei Kurzhanteln (bis 15 kg): Timer, 3D-Figur zur Übungsausführung, Wiederholungs- und Gewichtsprotokoll mit Fortschrittsvergleich, Rückmeldung pro Satz, leichtere Varianten, Claude-Coach, Sprachsteuerung und Spotify.

- `index.html` – App v7 (Tag A / Tag B, Einstiegswochen, Rückmeldung Leicht/Passt/Zu hart, Varianten, Abbruch mit Grund, Check-in, Verlauf, Einstellungen)
- `rig.js` – 3D-Figur und Bewegungsposen inkl. Varianten (Three.js r128 von cdnjs)
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

Die Musik läuft im Browser-Tab („HIIT Kraft 30“ als Spotify-Gerät). Spotify-Fehler erscheinen als Zeile unter dem Timer, das Training läuft ohne Musik weiter.

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

## Bedienung am PC

Leertaste = Satz fertig / Fortsetzen, Pfeil hoch/runter = Wiederholungen ±1, Pfeil rechts = Weiter, Pfeil links = Zurück, P = Pause, T = Takt tippen. In Textfeldern sind die Tasten abgeschaltet.
