# Selbstbau: EMS-Interface + ESP32-C3 Super Mini

> Status: Schaltplan, Stückliste und Aufbau siehe **`schaltplan.md`**.

## Hardware

- **MCU:** ESP32-C3 Super Mini (USB-C). EMS-ESP hat dafür einen offiziellen Build (`c3_mini_4M`) und das
  Board-Profil `C3MINI`. Er passt zusammen mit der Schaltung auf die vorhandene Lochrasterplatine 7 × 9 cm.
  Der ebenfalls vorhandene „D1 Mini ESP32“ wäre mit ca. 31 × 39 mm zu groß dafür.
- **Versorgung:** über die USB-C-Buchse (5-V-Netzteil). Nicht aus dem Bus versorgen, weil das
  bei Nachbauten mehrfach nicht stabil lief.
- **Hinweis zum Super Mini:** Viele Exemplare haben eine schwache Antenne. Wenn das WLAN instabil ist, in
  EMS-ESP die WLAN-Sendeleistung reduzieren (Network Settings) oder das Gateway näher an den Router bringen.

## Pinbelegung: EMS-ESP Board-Profil „C3MINI“

| Funktion | GPIO | Beschriftung Super Mini |
|---|---|---|
| EMS RX (vom Interface `RX_OUT`) | **GPIO4** | `4` (rechte Reihe) |
| EMS TX (zum Interface `TX_IN`) | **GPIO5** | `5` (linke Reihe, oben) |
| 3V3 für RX-Pull-up und TX-Inverter | 3V3 | `3V` |
| GND | GND | `G` |

Strapping-Pins (GPIO2, 8, 9) nicht verwenden.

Einstellungen in EMS-ESP:
- Firmware: Variante **`c3_mini_4M`**
- Settings → Application → Board Profile: **C3MINI** (RX GPIO4, TX GPIO5)
- EMS Tx Mode: **EMS+** (der RC310 ist ein EMS2.0/EMS+-Gerät), alternativ **Auto**
- EMS Bus ID: Standard **Gateway 2 (0x49)** lassen
- Erstinbetriebnahme mit **Read only**

Quelle: EMS-ESP-Doku „Configuring“, Tabelle der Board-Profile (C3MINI: RX 4, TX 5), Build-Ziele in
`platformio.ini` des EMS-ESP32-Repos.

## Eckdaten des Referenzdesigns (bbqkees EMS-Wiki) und was davon übernommen wurde

- **Eingang:** Brückengleichrichter, daher ist die Polung des Busses egal. *Übernommen* (4× BAT46).
  Die optionalen Polyfuses und die Entstördrosseln (laut bbqkees 4,7 µH statt der im Plan stehenden „4,7mH“)
  entfallen hier, siehe `schaltplan.md`, Abschnitt 1a.
- **Empfang (RX):** Komparator LM393 mit gleitender Referenz. *Ersetzt* durch eine Differenzstufe aus zwei BC548B
  mit gleitender Referenz (R3/R4/C2) und einen BC548B als Pegelwandler auf 3,3 V (siehe `schaltplan.md`).
- **Senden (TX):** NPN-Transistor schaltet eine Last über den Bus. Die Last muss **210–250 Ω** haben.
  *Übernommen* als ein einzelner Widerstand 220 Ω 1 W statt 4× 910 Ω parallel. Den Inverter davor (im Original
  Komparator B) übernimmt ein BC548B.
- **Dioden:** BAT46 statt BAT54S, laut Autor geht notfalls auch 1N4148.
- **U_REF:** entfällt in der Transistor-Variante.
- **Optional:** Optokoppler auf der Logikseite zur galvanischen Trennung. *Nicht verwendet.*
- **Service-Buchse:** deren 12-V-Pin nicht anschließen. Nicht gleichzeitig an Schraubklemme und
  Service-Buchse anklemmen. Hier wird ohnehin am RC310-Sockel angeschlossen.

## Ablauf

1. Komplette Platine (RX + TX, JP1 gezogen) nach `schaltplan.md` aufbauen und prüfen (Abschnitt 5): erst Durchgang
   ohne ESP32, dann mit ESP32: `RX_OUT` liegt im Ruhezustand bei ~3,3 V und nie darüber.
2. EMS-ESP flashen (Variante `c3_mini_4M`), Board-Profil **C3MINI** wählen, **Read only** aktivieren.
3. An den RC310-Sockel parallel anklemmen (siehe `anschluss.md`) und die Geräteliste prüfen.
4. Erst danach JP1 stecken und Read only abschalten.

## Quellen

- bbqkees EMS-Wiki, EMS Interface: https://github.com/bbqkees/EMS-Wiki/blob/master/Documentation/EMS%20Interface/README.md
- rocksolidsr/esp-ems-board (ESP8266-Variante, BOM): https://github.com/rocksolidsr/esp-ems-board
- EMS-ESP32: https://github.com/emsesp/EMS-ESP32
- EMS-ESP-Doku: https://docs.emsesp.org/Configuring/ und https://docs.emsesp.org/Installing/
