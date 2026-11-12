# Selbstbau: EMS-Interface + ESP32 DevKit V1

> Status: **Entwurf.** Die Bauteilwerte und die Verdrahtung werden erst eingetragen, wenn sie gegen
> den Referenzschaltplan (bbqkees EMS-Wiki, Bild) geprüft sind. Nicht nach Gedächtnis aufbauen.

## Hardware

- **MCU:** ESP32 DevKit V1 (ESP-WROOM-32), klassischer ESP32 und damit von EMS-ESP unterstützt.
- **Versorgung:** über die USB-Buchse des DevKits (5-V-Netzteil). Nicht aus dem Bus versorgen, weil das
  bei Nachbauten mehrfach nicht stabil lief.

## Pinbelegung (EMS-ESP Board-Profil „Custom“)

| Funktion | GPIO | Beschriftung DevKit | Warum |
|---|---|---|---|
| EMS RX (vom Interface `RX_OUT`) | **GPIO16** | `RX2` | kein Strapping-Pin, Hardware-UART2 |
| EMS TX (zum Interface `TX_IN`) | **GPIO17** | `TX2` | kein Strapping-Pin, Hardware-UART2 |
| 3V3 für den Komparator | 3V3 | `3V3` | LM393 läuft an 3,3 V |
| GND | GND | `GND` | |

Diese Pins nicht verwenden: GPIO0, 2, 12 und 15 (Strapping-Pins), GPIO1 und 3 (USB-Seriell), GPIO6–11 (Flash).

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

1. RX-Stufe aufbauen und mit dem Multimeter prüfen: `RX_OUT` liegt im Ruhezustand bei ~3,3 V und
   nie über 3,3 V.
2. EMS-ESP flashen (Web-Installer), Board-Profil „Custom“ wählen, RX=16, TX=17 eintragen, **Read only** aktivieren.
3. An den RC310-Sockel parallel anklemmen (siehe `anschluss.md`) und die Geräteliste prüfen.
4. Erst danach die TX-Stufe ergänzen und Read only abschalten.

## Quellen

- bbqkees EMS-Wiki, EMS Interface: https://github.com/bbqkees/EMS-Wiki/blob/master/Documentation/EMS%20Interface/README.md
- rocksolidsr/esp-ems-board (ESP8266-Variante, BOM): https://github.com/rocksolidsr/esp-ems-board
- EMS-ESP32: https://github.com/emsesp/EMS-ESP32
