# Kurzbefehl: Schlaf und Ruhewerte an HIIT Kraft 30 senden

Der Kurzbefehl liest jeden Morgen Werte aus Health und schickt sie an den eigenen Cloudflare Worker. Die App holt sie von dort ab, zeigt sie auf dem Startbildschirm, füllt den Check-in vor und gibt sie dem Coach.

Gesendet wird ein JSON-Objekt, alle Felder sind optional:

```json
{"date":"2026-11-07","sleepHours":6.67,"sleepStart":"2026-11-06T23:10:00+01:00","sleepEnd":"2026-11-07T06:30:00+01:00","restingHr":58,"hrv":42,"steps":9123,"activeKcal":612}
```

Bezeichnungen in Anführungszeichen sind die deutschen Namen in der Kurzbefehle-App (iOS 18). Bezeichnungen mit **(unsicher)** konnten nicht gegen Apples Handbuch geprüft werden; wenn eine Aktion oder Option anders heißt, in der Aktionssuche nach dem Hauptwort suchen (zum Beispiel „Health“, „URL“, „Datum“).

Vorher bereitlegen:

- Worker-Adresse, z. B. `https://hiit-kraft-30-health.<konto>.workers.dev/health`
- Token (das beim Einrichten angezeigte, 64 Zeichen)

## 1. Kurzbefehl anlegen

Kurzbefehle-App → Tab „Kurzbefehle“ → „+“. Name oben antippen und „HIIT Health senden“ eintragen. Die folgenden Aktionen in dieser Reihenfolge über „Aktion hinzufügen“ bzw. das Suchfeld unten einfügen. Variablen legst du an, indem du nach einer Aktion „Variable festlegen“ einfügst und den Namen vergibst.

### A. Zeitpunkte

1. „Aktuelles Datum“ **(unsicher, heißt teils nur „Datum“ mit Wert „Aktuelles Datum“)**.
2. „Datum anpassen“: Option „Anfang von Tag“ **(unsicher)** → „Variable festlegen“: `HeuteBeginn`.
3. „Datum anpassen“: „Subtrahieren“, `1` „Tage“, Datum `HeuteBeginn` → „Variable festlegen“: `GesternBeginn`.
4. „Datum formatieren“: Datum „Aktuelles Datum“, Datumsformat „Eigene“, Format `yyyy-MM-dd`, Zeitformat „Keine“ → „Variable festlegen“: `Heute`.

### B. Schlaf der letzten Nacht

5. „Health-Proben suchen“
   - Typ: „Schlafanalyse“
   - Filter „Startdatum“ „ist in den letzten“ `18` „Stunden“
   - Filter „Wert“ „ist nicht“ „Im Bett“ und weiterer Filter „Wert“ „ist nicht“ „Wach“ **(unsicher, ob „ist nicht“ angeboten wird)**
   - Sortieren nach „Startdatum“, Reihenfolge „Älteste zuerst“, kein Limit
   - → „Variable festlegen“: `Schlafproben`

   Warum nicht „Wert ist Schlafend“: Seit watchOS 9 speichert die Watch die Schlafphasen als „Kern“, „Tief“ und „REM“. Ein Filter nur auf „Schlafend“ findet dann fast nichts. Deshalb „Im Bett“ und „Wach“ ausschließen; was übrig bleibt, ist geschlafene Zeit. Falls „ist nicht“ fehlt: vier Suchen mit „Wert ist Kern / Tief / REM / Schlafend“ und die Ergebnisse mit „Zu Variable hinzufügen“ sammeln.
6. „Wiederholen mit jedem Objekt in“ `Schlafproben`, darin:
   1. „Details von Health-Proben abrufen“: „Startdatum“ von „Wiederholungsobjekt“ → „Variable festlegen“: `PStart`
   2. „Details von Health-Proben abrufen“: „Enddatum“ von „Wiederholungsobjekt“ → „Variable festlegen“: `PEnde`
   3. „Zeit zwischen Daten abrufen“: von `PStart` bis `PEnde` in „Minuten“ **(unsicher: Aktion heißt evtl. „Zeit zwischen Daten ermitteln“)**
7. Nach „Wiederholung beenden“: „Statistik berechnen“: „Summe“ von „Wiederholungsergebnisse“.
8. „Berechnen“: Ergebnis `÷` `60`.
9. „Zahl runden“: auf „Hundertstel“ → „Variable festlegen“: `SchlafStunden`.
10. „Objekt aus Liste abrufen“: „Erstes Objekt“ aus `Schlafproben` → „Details von Health-Proben abrufen“: „Startdatum“ → „Datum formatieren“: „ISO 8601“, „Uhrzeit einschließen“ an → „Variable festlegen“: `SchlafStart`.
11. „Objekt aus Liste abrufen“: „Letztes Objekt“ aus `Schlafproben` → „Details von Health-Proben abrufen“: „Enddatum“ → „Datum formatieren“: „ISO 8601“, „Uhrzeit einschließen“ an → „Variable festlegen“: `SchlafEnde`.

### C. Ruhepuls (letzter Wert)

12. „Health-Proben suchen“: Typ „Ruheherzfrequenz“, Sortieren nach „Startdatum“, „Neueste zuerst“, Limit an, `1` Probe.
13. „Details von Health-Proben abrufen“: „Wert“ → „Variable festlegen“: `Ruhepuls`.

### D. HRV (Durchschnitt letzte Nacht)

14. „Health-Proben suchen“: Typ „Herzfrequenzvariabilität“, Filter „Startdatum“ „ist in den letzten“ `12` „Stunden“, kein Limit.
15. „Details von Health-Proben abrufen“: „Wert“.
16. „Statistik berechnen“: „Durchschnitt“.
17. „Zahl runden“: auf „Ganzzahl“ **(unsicher: Option heißt evtl. „Einer“)** → „Variable festlegen“: `HRV`.

### E. Schritte und aktive Energie von gestern

18. „Health-Proben suchen“: Typ „Schritte“, Filter „Startdatum“ „ist zwischen“ `GesternBeginn` und `HeuteBeginn` **(unsicher: „liegt zwischen“)**, „Gruppieren nach“ „Tag“.
    „Gruppieren nach Tag“ ist wichtig: Health fasst dann iPhone und Watch ohne doppelte Schritte zu einer Tagessumme zusammen.
19. „Details von Health-Proben abrufen“: „Wert“ → „Statistik berechnen“: „Summe“ → „Variable festlegen“: `Schritte`.
20. Schritte 18 und 19 mit Typ „Aktive Energie“ wiederholen → „Variable festlegen“: `AktiveKcal`.

### F. Wörterbuch und senden

21. „Wörterbuch“, Einträge über „Neues Objekt hinzufügen“ (Typ in Klammern):
    - `date` (Text): `Heute`
    - `sleepHours` (Zahl): `SchlafStunden`
    - `sleepStart` (Text): `SchlafStart`
    - `sleepEnd` (Text): `SchlafEnde`
    - `restingHr` (Zahl): `Ruhepuls`
    - `hrv` (Zahl): `HRV`
    - `steps` (Zahl): `Schritte`
    - `activeKcal` (Zahl): `AktiveKcal`
22. „Inhalte von URL abrufen“
    - URL: Worker-Adresse mit `/health` am Ende
    - Pfeil aufklappen: Methode „POST“
    - „Header“: „Neuer Header“ → Schlüssel `Authorization`, Wert `Bearer ` + Token (mit Leerzeichen nach Bearer); zweiter Header `Content-Type` = `application/json`
    - „Anfragetext“: „Datei“ und als Datei das „Wörterbuch“ aus Schritt 21 wählen **(unsicher: ein Wörterbuch als Datei wird als JSON gesendet; falls nicht, „Anfragetext: JSON“ wählen und die acht Felder aus Schritt 21 dort direkt eintragen)**
23. Optional zum Testen: „Mitteilung anzeigen“ mit „Inhalte von URL“. Der Server antwortet mit `{"ok":true,"saved":{…}}` oder einer Fehlermeldung (`Nicht autorisiert` = Token falsch, `Ungültige Felder` = Wert außerhalb des Bereichs).

Beim ersten Ausführen fragt iOS nach Zugriff auf jede Health-Datenart und nach der Erlaubnis, Daten an die Worker-Domain zu senden: jeweils erlauben. Nachträglich: Health-App → Profilbild → „Apps“ → „Kurzbefehle“.

Nicht vorhandene Werte (keine HRV-Messung, Watch nachts nicht getragen) schickt Kurzbefehle als leeren Text oder 0. Der Server lässt solche Felder weg, der Rest wird gespeichert.

## 2. Automation um 7:00

Kurzbefehle-App → Tab „Automation“ → „+“ (bzw. „Neue Automation“) **(unsicher: in älteren Versionen „Persönliche Automation erstellen“)**.

1. Auslöser „Tageszeit“: `07:00`, „Täglich“.
2. „Sofort ausführen“ wählen, „Bei Ausführung benachrichtigen“ aus.
3. „Weiter“ → „Neue leere Automation“ → Aktion „Kurzbefehl ausführen“ → „HIIT Health senden“.

## 3. Zweite Automation beim Aufwachen

Ein Auslöser „Beim Öffnen der App HIIT Kraft 30“ geht nicht, weil die App eine Webseite ist und keine installierte App. Ersatz:

1. „Automation“ → „+“ → Auslöser „Schlafen“ → „Aufwachen“ **(unsicher: in manchen Versionen „Beim Aufwachen“ bzw. „Schlafenszeit endet“)**. Setzt einen Schlafplan in der Health-App voraus.
2. „Sofort ausführen“, Aktion „Kurzbefehl ausführen“ → „HIIT Health senden“.

Ohne Schlafplan: Auslöser „Wecker“ → „Wird gestoppt“. Mehrere Sendungen am selben Tag schaden nicht, der Server führt sie unter dem Datum zusammen.

## 4. Prüfen

In der App: Einstellungen → „Schlaf und Ruhewerte“ → Health-Server-URL und Token eintragen → „Verbindung testen“. Erwartet: „Verbindung steht, letzte Daten vom …“. Auf dem Startbildschirm erscheint dann die Karte „Erholung“ mit „Letzte Nacht: …“.

Von Hand am Rechner (Token einsetzen):

```sh
curl -H "Authorization: Bearer <TOKEN>" https://hiit-kraft-30-health.<konto>.workers.dev/health/latest
```
