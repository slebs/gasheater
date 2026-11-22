# Selbstbau: EMS-Interface + ESP32-C3 Super Mini

> Status: Schaltplan, Stückliste und Aufbau siehe **`schaltplan.md`**.

## Hardware

- **MCU:** ESP32-C3 Super Mini (USB-C). EMS-ESP hat dafür einen offiziellen Build (`c3_mini_4M`) und das
  Board-Profil `C3MINI`. Er passt zusammen mit der Schaltung auf die vorhandene Lochrasterplatine 5 × 7 cm.
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
| 3V3 für den Komparator | 3V3 | `3V` |
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

## Bekannte Eckdaten des Referenzdesigns (bbqkees EMS-Wiki)

- **Eingang:** Brückengleichrichter, daher ist die Polung des Busses egal. Zwei optionale Polyfuses (~300 mA)
  in den Buszuleitungen.
- **Empfang (RX):** Komparator LM393 an **3V3**, 100 nF Abblockkondensator direkt am IC.
  Für Read-only reicht der RX-Teil plus dieser Kondensator.
- **Senden (TX):** NPN-Transistor schaltet eine Last über den Bus. Die Last muss **210–250 Ω** haben,
  z. B. ein einzelner Widerstand mit 1 W und ~250 Ω statt 4 parallel geschalteter.
- **Dioden:** BAT46 überall statt BAT54S, laut Autor geht notfalls auch 1N4148.
- **Induktivitäten:** 4,7 µH. Im Schaltplan steht fälschlich „4,7mH“.
- **U_REF:** alle U_REF-Netze miteinander verbinden.
- **Optional:** Optokoppler auf der Logikseite zur galvanischen Trennung.
- **Service-Buchse:** deren 12-V-Pin nicht anschließen. Nicht gleichzeitig an Schraubklemme und
  Service-Buchse anklemmen.

## Ablauf

1. Komplette Platine (RX + TX, JP1 gezogen) aufbauen und mit dem Multimeter prüfen: `RX_OUT` liegt im Ruhezustand bei ~3,3 V und
   nie über 3,3 V.
2. EMS-ESP flashen (Variante `c3_mini_4M`), Board-Profil **C3MINI** wählen, **Read only** aktivieren.
3. An den RC310-Sockel parallel anklemmen (siehe `anschluss.md`) und die Geräteliste prüfen.
4. Erst danach JP1 stecken und Read only abschalten.

## Quellen

- bbqkees EMS-Wiki, EMS Interface: https://github.com/bbqkees/EMS-Wiki/blob/master/Documentation/EMS%20Interface/README.md
- rocksolidsr/esp-ems-board (ESP8266-Variante, BOM): https://github.com/rocksolidsr/esp-ems-board
- EMS-ESP32: https://github.com/emsesp/EMS-ESP32
- EMS-ESP-Doku: https://docs.emsesp.org/Configuring/ und https://docs.emsesp.org/Installing/
