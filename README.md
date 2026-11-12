# gasheater – Wohnungsstation smart machen (EMS-ESP)

Ziel: Die Buderus-Wohnungsstation samt Raumregler RC310 per **EMS-ESP** (ESP32) in
Home Assistant bzw. per MQTT/REST steuerbar machen. Der RC310 bleibt dabei als Regler
in Betrieb.

## Anlage (Bestandsaufnahme)

| Komponente | Details |
|---|---|
| System | Zentralheizung mit Wohnungsstationen |
| Wohnungsstation | Buderus, Control box „Assembly Buderus“, NF51.03, 230 V; Drehregler für Warmwasser und Heizung |
| Raumregler | Buderus Logamatic **RC310**, Firmware NF18.06, Serie 06, DC 24 V |
| Bus | EMS (2-Draht, verpolungssicher), vom Wandsockel des RC310 direkt zur Station |
| Warmwasser | Plattenwärmetauscher in der Station (Durchlaufprinzip) |
| Wärmezähler | Sensus PolluCom F, optische Schnittstelle (IEC 870-5) |

## Plan

1. **Hardware:** fertiges EMS-ESP-Gateway von BBQKees (z. B. E32 V2) – kein Selbstbau.
2. **Anschluss:** parallel an die zwei BUS-Schraubklemmen im Wandsockel des RC310
   (Kleinspannung, ohne Eingriff in die Station). Siehe `docs/anschluss.md`.
3. **Erstinbetriebnahme read-only:** EMS-ESP mit aktivierter Option „Read only“ starten,
   Geräteliste und Rohtelegramme aufzeichnen.
4. **Auswertung:** Der RC310 wird von EMS-ESP unterstützt. Ob die Station selbst erkannt wird
   (Produkt-ID), ist offen. Falls nicht: Telegramme loggen und eigene Einträge/Custom Entities anlegen.
5. **Schreiben freischalten:** Solltemperatur und Betriebsart über den RC310.
6. **Home Assistant:** MQTT-Discovery von EMS-ESP.
7. **Optional:** Den Wärmezähler über einen IR-Lesekopf nur auslesen (Verbrauch in kWh).
