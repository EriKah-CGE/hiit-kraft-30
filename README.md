# HIIT Kraft 30

30-Minuten-Heimtraining mit zwei Kurzhanteln (bis 15 kg): Timer, 3D-Figur zur Übungsausführung, Wiederholungs- und Gewichtsprotokoll mit Fortschrittsvergleich, Rückmeldung pro Satz, leichtere Varianten, Claude-Coach, Sprachsteuerung und Spotify.

- `index.html` – App v7 (Tag A / Tag B, Einstiegswochen, Rückmeldung Leicht/Passt/Zu hart, Varianten, Abbruch mit Grund, Check-in, Verlauf, Einstellungen)
- `rig.js` – 3D-Figur und Bewegungsposen inkl. Varianten (Three.js r128 von cdnjs)
- `coach.js` – Claude-API-Client (Plananpassung, Fragen im Training, Auswertung, Progressionscheck), ohne Schlüssel lokale Regeln
- `voice.js` – Sprachsteuerung mit Aktivierungswort „Coach“ und Sprachausgabe (Browser oder ElevenLabs)
- `spotify.js` – Spotify Web Playback SDK und Web API (PKCE, ohne Server)

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

### Sprachsteuerung und Ansagen

- Spracherkennung funktioniert in Chrome und Edge. Beim ersten Start fragt der Browser nach dem Mikrofon.
- Aktivierungswort „Coach“, danach der Befehl, z. B. „Coach, fertig zwölf“, „Coach, zu hart“, „Coach, wie lange noch“, „Coach, Musik leiser“. Alles, was kein fester Befehl ist, geht an den Claude-Coach.
- Ansagen lassen sich in den Einstellungen abschalten.

### ElevenLabs (optional)

Für eine natürlichere Stimme unter https://elevenlabs.io einen API-Schlüssel anlegen, in den Einstellungen „Stimme: ElevenLabs“ wählen, Schlüssel und optional eine Voice-ID eintragen. Ohne gültigen Schlüssel spricht die Browserstimme.

## Bedienung am PC

Leertaste = Satz fertig / Fortsetzen, Pfeil hoch/runter = Wiederholungen ±1, Pfeil rechts = Weiter, Pfeil links = Zurück, P = Pause. In Textfeldern sind die Tasten abgeschaltet.
