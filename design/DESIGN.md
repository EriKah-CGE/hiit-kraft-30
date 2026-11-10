# Designvorgabe HIIT Kraft 30 (verbindlich)

Freigegeben am 10.11.2026. Die drei Entwürfe in diesem Ordner zeigen die Bildschirme:

- `start.html`: Startbildschirm mit heutiger Einheit, Check-in, Coach, Woche, Fortschritt
- `satz.html`: Training während eines Satzes
- `wechsel.html`: Pause bzw. Wechsel zur nächsten Übung

Die Dateien stammen aus einem Design-Werkzeug. Das `<x-dc>`-Gerüst, `support.js` und der `DCLogic`-Block gehören nicht zur App. Maßgeblich sind Aufbau, Inline-Styles, Farben, Schriften und die SVG-Skizzen. Die Skizzen sind Platzhalter für die 3D-Figur.

## Leitidee

Anatomieatlas bzw. Physiotherapie-Lehrbuch: warmes Altpapier, Sepia-Tinte, Muskeln in Ziegelrot, Beschriftungen mit nummerierten Hinweislinien. Keine abgerundeten Karten, keine Schatten, keine Verläufe, keine Emojis, keine Icons im App-Baukasten-Stil. Struktur entsteht nur durch Linien, Raster und Typografie.

## Farben

| Rolle | Wert |
|---|---|
| Papier (Hintergrund) | `#EBDDC3` |
| Tinte (Text, Rahmen, primäre Buttons) | `#3A2619` |
| Hilfslinien, Tabellentrenner | `#C9AF88` |
| Muskel aktiv | `#B23A1E` |
| Muskel unterstützend | `#E3A57C` |
| Haut der Figur | `#EAC9A2` |
| Akzenttext (Vergleich, aktueller Tag) | `#9C3518` |
| gedämpfter Text | `#7D6249` |

Primärer Button: Fläche `#3A2619`, Text `#EBDDC3`. Gewählter Zustand in Auswahlgruppen genauso.

## Schriften (Google Fonts)

- Archivo, schmal (`font-stretch` 62–75 %), Gewicht 800–900, Großbuchstaben: Übungsnamen, große Zahlen (Zähler, Countdown), App-Name
- Spectral (Serife): Beschriftungen, Abschnittsköpfe, Tabellenköpfe, Buttons; meist 12–13 px, Großbuchstaben mit `letter-spacing: .06–.08em`
- IBM Plex Sans: Fließtext, Tabelleninhalte, Hinweise
- Zahlen immer mit `font-variant-numeric: tabular-nums`

## Linien und Raster

- Kopf- und Fußzeile: 2 px Tinte
- Spaltentrenner und Rahmen: 1 px Tinte
- Zeilentrenner in Listen und `dl`: 1 px `#C9AF88`
- Zweispaltiges Raster auf großen Bildschirmen (PC ist Hauptgerät), außen 44 px Rand
- Datenpaare als `dl` mit Label-Spalte links (Spectral, Großbuchstaben) und Wert rechts
- Auswahlgruppen (Leicht/Passt/Zu hart, Müde/Normal/Fit) als zusammenhängende Leiste mit 1 px Rahmen, keine Einzelpillen

## Figur und Beschriftung

- Die Figur steht auf einer feinen Bodenlinie, ohne Bühne oder Hintergrund
- Arbeitende Muskeln `#B23A1E`, unterstützende `#E3A57C`, Rest Haut
- Beschriftungen: Punkt auf dem Muskel, abgewinkelte 1-px-Linie, daneben Nummer und Name in Spectral (fett), darunter eine kurze Funktion
- Formhinweise (Knie über Fuß usw.) mit Buchstaben A, B statt Zahlen
- Bildunterschrift im Atlasstil („Abb. 1 …")
