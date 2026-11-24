# gasheater – Wohnungsstation smart machen (EMS-ESP)

Ziel: Die Buderus-Wohnungsstation samt Raumregler RC310 per **EMS-ESP** in Home Assistant bzw. per
MQTT/REST steuerbar machen. Der RC310 bleibt dabei als Regler in Betrieb. EMS-ESP schreibt Sollwerte
an den RC310, der weiter regelt.

## Anlage (Bestandsaufnahme)

| Komponente | Details |
|---|---|
| System | Zentralheizung mit Wohnungsstationen |
| Wohnungsstation | Buderus, Control box „Assembly Buderus“, NF51.03, 230 V; Drehregler für Warmwasser und Heizung |
| Raumregler | Buderus Logamatic **RC310**, Firmware NF18.06, Serie 06, DC 24 V |
| Bus | EMS (2-Draht, verpolungssicher), vom Wandsockel des RC310 direkt zur Station (nicht zur Zentrale) |
| Warmwasser | Plattenwärmetauscher in der Station (Durchlaufprinzip) |
| Wärmezähler | Sensus PolluCom F, optische Schnittstelle (IEC 870-5) |

## Lösung: Gateway im Selbstbau

- **Mikrocontroller:** ESP32-C3 Super Mini mit der Firmware EMS-ESP (Build `c3_mini_4M`, Board-Profil `C3MINI`)
- **Bus-Interface:** Nachbau des bekannten EMS-Interfaces, angepasst auf 3,3 V und vereinfacht. Statt des
  LM393 arbeiten nur Transistoren (1× BC547B, 4× BC548B). Alles sitzt auf einer Lochrasterplatine 7 × 9 cm.
- **Anschluss:** parallel an die zwei BUS-Schraubklemmen im Wandsockel des RC310 (Kleinspannung, ohne
  Eingriff in die Station)

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`docs/selbstbau.md`](docs/selbstbau.md) | Überblick Selbstbau: Hardware, Pinbelegung, EMS-ESP-Einstellungen, Ablauf |
| [`docs/schaltplan.md`](docs/schaltplan.md) | Schaltung, Netzliste, Stückliste, Aufbau, Prüfung, Lochraster-Plan |
| [`docs/schaltplan_transistor.svg`](docs/schaltplan_transistor.svg) | Schaltplan als Grafik (BC547/BC548) |
| [`docs/lochraster_c3_bestueckung.svg`](docs/lochraster_c3_bestueckung.svg) | Lochraster-Plan, Bauteilseite |
| [`docs/lochraster_c3_loetseite.svg`](docs/lochraster_c3_loetseite.svg) | Lochraster-Plan, Lötseite (gespiegelt) |
| [`docs/bestellliste.md`](docs/bestellliste.md) | Bestellliste mit Suchbegriffen |
| [`docs/anschluss.md`](docs/anschluss.md) | Anschluss am RC310-Sockel, Regeln |
| [`tools/lochraster.py`](tools/lochraster.py) | Erzeugt und prüft den Lochraster-Plan (Platzierung in `tools/placement.json`) |

## Plan

1. **Platine bauen** nach `docs/schaltplan.md`, alles in einem Durchgang. TX bleibt über den Jumper JP1 abschaltbar.
2. **Prüfen** ohne ESP32: Durchgang jedes Netzes, kein Durchgang zwischen VBUS, GND und 3V3.
3. **EMS-ESP flashen** (`c3_mini_4M`), Board-Profil `C3MINI`, **Read only** an, JP1 gezogen.
4. **Anschließen** am RC310-Sockel (`docs/anschluss.md`), Geräteliste und Telegramme prüfen.
5. **Auswertung:** Der RC310 wird von EMS-ESP unterstützt. Ob die Station selbst erkannt wird
   (Produkt-ID), ist offen. Falls nicht: Telegramme loggen und eigene Einträge/Custom Entities anlegen.
6. **Schreiben freischalten:** JP1 stecken, Read only aus. Solltemperatur und Betriebsart gehen über den RC310.
7. **Home Assistant:** MQTT-Discovery von EMS-ESP. Home Assistant braucht einen 64-Bit-Rechner. ODROID-XU4
   und ODROID-C1 sind 32-Bit und werden von aktuellen Versionen nicht mehr unterstützt. Günstig ist z. B. ein
   gebrauchter Thin-Client. EMS-ESP läuft bis dahin auch standalone über die eigene Weboberfläche.
8. **Optional:** Den Wärmezähler über einen IR-Lesekopf nur auslesen (Verbrauch in kWh).

## Offene Punkte vor dem Löten

- Lochrasterplatine wirklich 24 × 30 Löcher?
- Stiftreihen des Super Mini 6 Raster (15,24 mm) auseinander?
- Pinbeschriftung des Super Mini wie im Plan?
