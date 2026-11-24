# EMS-Interface: Schaltplan, Stückliste und Aufbau (ESP32-C3, 3,3 V, nur Transistoren)

Vorlage ist der Schaltplan „EMSBus-UART-Converter“. Das ist das bekannte, aus einem Buderus-Servicekey
nachgebaute Design, das auch im bbqkees EMS-Wiki verwendet wird. Dort arbeitet ein LM393 als Komparator.
**In dieser Variante ersetzen BC547/BC548 den LM393.** Eingang (Brückengleichrichter) und Sendestufe
(Transistor + 220 Ω) bleiben gleich. Neu aufgebaut sind die Empfangsstufe und der Inverter vor dem Sendetransistor.

Weitere Anpassungen gegenüber dem Original:

- **ESP32-C3 Super Mini**: Die Logik läuft mit **3,3 V**. RX_OUT liefert nie mehr als 3,3 V.
- **Bedrahtete Bauteile** für Lochraster, z. B. BC547B/BC548B statt BC847B (SMD) und BAT46 statt BAT54S.
- **Vereinfacht:** Die Entstördrosseln L1/L2, die Polyfuses F1/F2 und die Schutzdiode D5 entfallen
  (Abschnitt 1b).

---

## 1. Schaltplan

Als Grafik: [`schaltplan_transistor.svg`](schaltplan_transistor.svg). Hier dieselbe Schaltung als Textskizze:

```
 EMS-Bus                Brückengleichrichter
 J1.1 ──┬────────────┬── D1 ►| ──┬───────────────────────────────────────── VBUS (12…17 V)
        │C1 68p      │           │
 J1.2 ──┴────────────┼── D3 ►| ──┘   D2, D4: Anode GND, Kathode an J1.1 bzw. J1.2

 ── RX: Differenzstufe mit gleitender Referenz ───────────────────────────────────────────

  VBUS ──R1 56k──┬── SIG ──R3 15k──┬── REF                 VBUS        VBUS
                 │                 │                        │           │
               R2 10k  C3 1n     R4 220k  C2 10µ          R6 33k        │
                 │      │          │       │                │           │
                GND    GND        GND     GND     N ────────┤           │
                                                            │C          │C
                               SIG ──────────────────── B─ Q2        Q3 ─B ──── REF
                                                            │E          │E
                                                            └────┬──────┘
                                                                TAIL
                                                               R5 4k7
                                                                GND
                                    3V3
                                     │
                                   R9 4k7
       N ──R7 68k──┬── B4            │
                   │                 ├──────────── RX_OUT → GPIO4
                 R8 10k        B4 ─B Q4
                   │                 │E
                  GND               GND

 ── TX: Inverter Q5, Stromsenke Q1 ─────────────────────────────────────────────────────

         3V3               3V3                  VBUS
          │                 │                    │
        R10 47k           R12 2k2               JP1 (TX ein/aus)
          │                 │                    │
 GPIO5 ───┴── TX_IN ─R11 10k─ B Q5 C ──┬── TXB  R13 220 Ω 1 W
                              │E       │         │
                             GND       └──── B Q1 C ── TXC ──C5 1,5n── GND
                                              │E
                                             GND
```

Alle Transistoren sind NPN im TO-92-Gehäuse. Q1 ist ein BC547B, Q2–Q5 sind BC548B. Die beiden Typen sind hier
austauschbar, weil keine Spannung über 30 V auftritt.

### 1a. Funktionsweise

- **Eingang:** Ein Brückengleichrichter aus 4 Dioden erzeugt aus dem Bus eine Gleichspannung (`VBUS`, ca. 12–17 V).
  Die Polung des Busses ist damit egal.
- **RX:** Der Master sendet, indem er die Busspannung absenkt (Low-Bit ≈ 2–3 V unter dem Ruhepegel).
  - R1/R2 teilen `VBUS` auf `SIG` ≈ 0,15 × VBUS herunter (bei 15 V ≈ 2,2 V). C3 filtert kurze Störspitzen.
  - R3/R4 und C2 bilden daraus die **gleitende Referenz** `REF` ≈ 0,94 × Mittelwert von `SIG`
    (Zeitkonstante ≈ 0,14 s). Die Schwelle passt sich damit selbst an den Ruhepegel des Busses an, genau wie im Original.
  - Q2/Q3 sind eine **Differenzstufe** (Komparator). Im Ruhezustand liegt `SIG` ≈ 6 % über `REF`: Q2 leitet,
    sein Kollektor `N` liegt bei ≈ 2,8 V. Fällt der Bus um mehr als ca. 1,0–1,4 V, wird `SIG` < `REF`. Dann leitet Q3,
    Q2 sperrt, und `N` steigt über R6 auf ≈ 6–10 V (je nach Buspegel).
  - R7/R8 setzen die Schaltschwelle von Q4 auf `N` ≈ 4,7 V. Q4 sperrt bei `N` = 2,8 V sicher (Basis ≈ 0,36 V)
    und zieht bei einem Low-Bit `RX_OUT` auf ≈ 0 V. R9 zieht `RX_OUT` sonst auf 3,3 V.
  - Die Differenzstufe hängt nur am Bus (`VBUS`), nur Q4 und R9 hängen an 3V3. Q2 geht nie in die Sättigung
    (`N` bleibt über `SIG`), deshalb schaltet sie auch bei 9600 Baud sauber.
- **TX:** Der UART des ESP32 ist in Ruhe High. Q5 invertiert: TX_IN High → Q5 leitet → Basis von Q1 auf GND →
  Q1 sperrt. TX_IN Low → Q5 sperrt → R12 steuert Q1 durch → Q1 zieht über R13 (220 Ω) ca. 55–75 mA aus dem
  Bus (Strommodulation, so senden EMS-Slaves). Das ist dieselbe Funktion wie Komparator B im Original.
- **R10 (47 k) zieht TX_IN auf High.** Solange der ESP32 bootet, resettet oder nicht gesteckt ist, bleibt Q1 damit
  aus und der Bus wird nicht blockiert. Das ist eine Verbesserung gegenüber dem LM393-Original.

**Nachgerechnet** wurde die RX-Stufe mit einer Transientensimulation (Ebers-Moll-Modell, UART-Bitmuster bei 9600 Baud,
Referenz C2 eingeschwungen). Bei 12, 15 und 17 V Ruhepegel waren alle Bits ab einem Bus-Hub von 1,2, 1,4 bzw. 1,6 V
fehlerfrei (RX_OUT Low ≤ 0,1 V, High = 3,3 V). Kleinere Einbrüche bis ca. 1 V werden ignoriert. Die
LM393-Vorlage schaltet bei ca. 1,5 V Hub. Das ist eine Rechnung, kein Test am echten Bus.

### 1b. Was gegenüber dem Original weggelassen wurde

| Bauteil | Original | Warum es entfallen kann |
|---|---|---|
| F1/F2 | Polyfuses, im Plan „N/A“ (nicht bestückt) | waren schon im Original nicht bestückt |
| L1/L2 | Entstördrosseln in den Busleitungen | nur EMV-Filterung. Viele Nachbauten laufen ohne; sie lassen sich später nachrüsten, wenn Störungen auftreten |
| D5 | BAT46 von GND nach VBUS | Hinter dem Brückengleichrichter kann VBUS nicht unter GND fallen. Ohne die Drosseln gibt es auch keine induktiven Spitzen mehr, die D5 abfangen müsste |
| LM393, C6 | Komparator + 100 nF Abblockung | ersetzt durch Q2–Q5 (diese Variante) |
| D6, R2 (360 Ω), U_REF | Referenzdiode | Die Referenz kommt jetzt aus R3/R4/C2 |

Sollten im Betrieb Busfehler auftreten, wären die Drosseln das Erste, was man nachrüstet.

---

## 2. Netzliste

Netznamen: `L1`/`L2` = Busleitungen (direkt an J1), `VBUS` = Plus nach dem Gleichrichter, `VCC` = **3V3 vom ESP32**,
`GND` = Minus nach dem Gleichrichter = GND des ESP32.

### Eingang und Gleichrichter

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| J1 | Schraubklemme 2-pol. | Klemme 1 = `L1`, Klemme 2 = `L2` | | F1/F2/L1/L2 entfallen (Abschnitt 1b) |
| C1 | 68 pF | `L1` | `L2` | Keramik |
| D1 | BAT46 | Anode `L1` | Kathode `VBUS` | |
| D2 | BAT46 | Anode `GND` | Kathode `L1` | |
| D3 | BAT46 | Anode `L2` | Kathode `VBUS` | |
| D4 | BAT46 | Anode `GND` | Kathode `L2` | |

### RX-Stufe

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| R1 | 56 k | `VBUS` | `SIG` | |
| R2 | 10 k | `SIG` | `GND` | |
| C3 | 1 nF | `SIG` | `GND` | Keramik, Störfilter |
| R3 | 15 k | `SIG` | `REF` | |
| R4 | 220 k | `REF` | `GND` | |
| C2 | 10 µF | `REF` | `GND` | Keramik (X7R) empfohlen. Beim Elko: **Plus an `REF`** |
| Q2 | BC548B | B = `SIG`, C = `N`, E = `TAIL` | | |
| Q3 | BC548B | B = `REF`, C = `VBUS`, E = `TAIL` | | |
| R5 | 4,7 k | `TAIL` | `GND` | Emitterwiderstand der Differenzstufe |
| R6 | 33 k | `VBUS` | `N` | Kollektorwiderstand Q2 |
| R7 | 68 k | `N` | `B4` | |
| R8 | 10 k | `B4` | `GND` | |
| Q4 | BC548B | B = `B4`, C = `RX_OUT`, E = `GND` | | |
| R9 | 4,7 k | `VCC` (3V3) | `RX_OUT` | Pull-up, **an 3V3** |
| — | Draht | `RX_OUT` | **ESP32-C3 GPIO4** | |

### TX-Stufe

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| — | Draht | **ESP32-C3 GPIO5** | `TX_IN` | |
| R10 | 47 k | `VCC` (3V3) | `TX_IN` | hält TX aus, solange der ESP32 nicht treibt |
| R11 | 10 k | `TX_IN` | `B5` (Basis Q5) | |
| Q5 | BC548B | B = `B5`, C = `TXB`, E = `GND` | | Inverter |
| R12 | 2,2 k | `VCC` (3V3) | `TXB` | Basisstrom Q1 ≈ 1,2 mA |
| Q1 | BC547B | B = `TXB`, C = `TXC`, E = `GND` | | Stromsenke |
| JP1 | Jumper | `VBUS` | `JPX` | TX ein/aus |
| R13 | 220 Ω, **1 W** | `JPX` | `TXC` | ersetzt 4×910 Ω parallel (= 227 Ω). **Zulässig 210–250 Ω** |
| C5 | 1,5 nF | `TXC` | `GND` | |

**R12 ist kleiner als im LM393-Plan (2,2 k statt 4,7 k).** Mit 4,7 k an 3,3 V bekäme Q1 nur ≈ 0,55 mA Basisstrom
für ≈ 70 mA Kollektorstrom. Das reicht nur bei einem Exemplar mit hoher Stromverstärkung. Mit 2,2 k ist Q1 sicher gesättigt.

**BC547B/BC548B (TO-92):** flache Seite zu dir, Beine nach unten, von links nach rechts **C – B – E**.
Im Lochraster-Plan sind die Pins C/B/E an jedem Transistor beschriftet.
Bei Nachbauten anderer Hersteller vorher mit dem Datenblatt bzw. dem Diodentest prüfen.

---

## 3. Stückliste (bedrahtet)

| Anz. | Bauteil | Wert / Typ | wofür |
|---|---|---|---|
| 1 | Transistor | **BC547B** (oder BC548B) | Q1 |
| 4 | Transistor | **BC548B** (oder BC547B) | Q2–Q5 |
| 4 | Schottky-Diode | **BAT46** (DO-35) | D1–D4 |
| 1 | Widerstand | 56 kΩ | R1 |
| 3 | Widerstand | 10 kΩ | R2, R8, R11 |
| 1 | Widerstand | 15 kΩ | R3 |
| 1 | Widerstand | 220 kΩ | R4 |
| 2 | Widerstand | 4,7 kΩ | R5, R9 |
| 1 | Widerstand | 33 kΩ | R6 |
| 1 | Widerstand | 68 kΩ | R7 |
| 1 | Widerstand | 47 kΩ | R10 |
| 1 | Widerstand | 2,2 kΩ | R12 |
| 1 | Widerstand | **220 Ω, 1 W** (alternativ 4× 910 Ω 0,25 W parallel) | R13 |
| 1 | Kondensator | 68 pF Keramik | C1 |
| 1 | Kondensator | 10 µF Keramik X7R (oder Elko ≥ 25 V) | C2 |
| 1 | Kondensator | 1 nF Keramik | C3 |
| 1 | Kondensator | 1,5 nF Keramik | C5 |
| 1 | Stiftleiste 2-pol. + Jumper | | JP1 (TX ein/aus) |
| 1 | Schraubklemme | 2-polig, RM 5,08 | Busanschluss |
| 2 | Buchsenleiste | 1×8 | ESP32-C3 steckbar |
| 1 | Lochrasterplatine | 7 × 9 cm (24 × 30 Löcher) | vorhanden |
| – | Schaltdraht | verzinnt 0,6 mm + isolierter Draht | Lötseite + Drahtbrücken |
| – | Kabel | 2-adrig, z. B. J-Y(St)Y 2×2×0,6 | Gateway ↔ RC310-Sockel |

Gegenüber der LM393-Variante entfallen LM393, IC-Sockel, 1N4148, 360 Ω, 100 kΩ und die Kondensatoren 10 nF und 100 nF.
Die Kosten liegen bei ca. 5 € plus Versand, z. B. bei Reichelt oder in einem Sortimentskasten.

---

## 4. Aufbau: alles auf einmal (RX + TX)

Die ganze Platine wird in einem Durchgang bestückt: Eingang, RX- und TX-Stufe.

Damit TX beim ersten Test trotzdem sicher aus ist, gibt es **zwei Sicherungen**:

1. **Jumper JP1 in Reihe zu R13.** Dafür eine 2-polige Stiftleiste mit Jumper zwischen `VBUS` und R13 setzen
   (also `VBUS` → JP1 → R13 → `TXC`).
   - **Jumper gezogen:** Q1 kann keinen Strom aus dem Bus ziehen, die Platine liest nur mit.
   - **Jumper gesteckt:** TX aktiv.
2. **Software:** In EMS-ESP „Read only“ einschalten. Dann sendet der ESP32 gar nicht.

Ablauf: zuerst mit **gezogenem Jumper und Read only** testen. Wenn Telegramme ankommen, den Jumper stecken
und Read only ausschalten.

## 5. Prüfen vor dem ersten Anschluss

**Zuerst ohne ESP32:** jedes Netz mit dem Durchgangsprüfer prüfen (siehe Abschnitt 8).

**Dann ohne Bus**, ESP32-C3 gesteckt und per USB versorgt:
1. 3V3 gegen GND ≈ **3,3 V**.
2. RX_OUT (GPIO4) ≈ **3,3 V** und **niemals mehr** (ohne Bus sperrt Q4).
3. TXB (Basis Q1) ≈ **0,1 V**, solange der ESP32 TX auf High hält. Liegt hier ≈ 0,7 V, wäre Q1 an (Q5 falsch herum?).
4. Kein Kurzschluss zwischen den Busklemmen. Mit dem Ohmmeter messen; der Wert sollte im kΩ-Bereich liegen.

**Mit Bus** (am RC310-Sockel parallel angeklemmt, siehe `anschluss.md`, JP1 gezogen):
1. `VBUS` gegen GND ≈ **12–17 V DC**.
2. `SIG` ≈ 0,15 × VBUS (bei 15 V ≈ 2,2 V), `REF` etwa 0,1–0,2 V darunter. C2 braucht nach dem Anklemmen ca. 1 s.
3. `TAIL` ≈ `SIG` − 0,6 V, `N` (Kollektor Q2) ≈ **2,5–3 V**, Basis Q4 ≈ 0,35 V.
4. RX_OUT liegt meist auf ~3,3 V. Bei Busverkehr wackelt der Wert leicht, weil Datenbits ankommen.
5. Der RC310 muss normal weiterlaufen und darf keine Busstörung melden.

Die Platine zieht im Ruhezustand ca. 0,5–0,7 mA aus dem Bus (LM393-Variante: ca. 1,5 mA).

---

## 6. EMS-ESP einstellen

- Firmware **c3_mini_4M**, Board Profile: **C3MINI** (RX GPIO4, TX GPIO5)
- **Read only: an** beim ersten Test (JP1 gezogen)
- EMS Tx Mode: **EMS+** (RC310 = EMS2.0) oder **Auto**
- Im Dashboard prüfen: Es werden Telegramme empfangen, und RC310 und Station tauchen unter „Devices“ auf.
- Danach: JP1 stecken, Read only aus und in Console oder Dashboard auf **Tx-Fehler** achten.

Die Polarität ist dieselbe wie beim LM393-Interface (Bus Low → RX_OUT Low, TX_IN Low → Strom aus dem Bus).
In EMS-ESP muss nichts invertiert werden.

---

## 7. Sicherheitshinweise

- Der Bus führt Kleinspannung (ca. 12–17 V). Trotzdem nicht unter Spannung umlöten.
- Die GND des ESP32 ist mit der Bus-Minusseite verbunden; galvanisch getrennt ist hier nichts. Das ist unkritisch,
  solange das USB-Netzteil ein normales, isoliertes Steckernetzteil ist.
- `N` und der Kollektor von Q3 führen bis zu `VBUS` (17 V). Diese Netze dürfen nie an einen ESP32-Pin.
- Bricht die Kommunikation des RC310 zusammen: Gateway abklemmen, und alles läuft wie vorher.

---

## 8. Lochraster-Plan (ESP32-C3 Super Mini, Platine 7 × 9 cm)

- `lochraster_c3_bestueckung.svg`: Draufsicht auf die Bauteilseite
- `lochraster_c3_loetseite.svg`: Lötseite, gespiegelt (so liegt die Platine beim Löten vor dir)

**Platine:** die vorhandene Lochrasterplatine 7 × 9 cm (24 × 30 Löcher). Koordinaten (x, y) zählen von oben
links auf der Bauteilseite, die Achsen sind beschriftet. Die USB-C-Buchse des Super Mini zeigt nach oben
über den Rand. Die Bauteile belegen etwa die Löcher x = 0…20, y = 0…28; rechts und unten bleibt Rand frei.

**Vor dem Löten prüfen:**
1. Die Platine hat wirklich 24 × 30 Löcher (Löcher einer Längs- und einer Querreihe zählen).
2. Die Stiftreihen des Super Mini liegen 6 Raster auseinander (15,24 mm, also 5 freie Löcher dazwischen).
3. Die Pinbeschriftung auf deinem Super Mini stimmt mit dem Plan überein (links 5…21, rechts 5V, G, 3V, 4…0).

Wenn eins davon nicht passt: Bescheid geben, dann wird der Plan angepasst.

**Platzsparend:** Widerstände, die im Plan als Kreis gezeichnet sind, stehen senkrecht. Der Körper sitzt auf dem
Loch mit dem Kreis, der Draht wird zurückgebogen und kommt ins Nachbarloch. Bei einer stehenden Diode ist das mit
„K“ markierte Loch die Kathode.

**Transistoren:** Q1–Q5 wie gezeichnet einbauen; die Pins C/B/E sind im Plan an jedem Transistor beschriftet.

**Drahtbrücken auf der Bauteilseite** (isolierter Draht, gerade, im Plan als Bogen gezeichnet):

| Netz | von | nach |
|---|---|---|
| Basis Q4 (B4) | (6, 9) | (6, 14) |
| VBUS | (12, 11) | (12, 16) |
| VBUS | (7, 18) | (13, 18) |

Alle übrigen Verbindungen liegen auf der Lötseite als blanker Draht oder Lötbrücke entlang der Lochreihen.
Unter dem Modul dürfen Leitungen auf der Lötseite liegen, aber keine Bauteile.

Den Plan erzeugt `tools/lochraster.py` (`python3 tools/lochraster.py docs`). Die Platzierung steht in
`tools/placement.json` und lässt sich mit `--optimize` neu berechnen. Das Skript verlegt die Leitungen
und prüft sie automatisch gegen die Netzliste oben: alle Netze zusammenhängend, keine Verbindung
zwischen fremden Netzen.

**Vor dem ersten Einschalten** (ESP32-C3 noch nicht gesteckt) jedes Netz mit dem Durchgangsprüfer abklappern.
Zwischen VBUS, GND und 3V3 darf kein Durchgang sein.
