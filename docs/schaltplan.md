# EMS-Interface: Schaltplan, Stückliste und Aufbau (ESP32, 3,3 V)

Vorlage ist der Schaltplan „EMSBus-UART-Converter“. Das ist das bekannte, aus einem Buderus-Servicekey
nachgebaute Design, das auch im bbqkees EMS-Wiki verwendet wird.
Hier wurde es angepasst für:

- **ESP32-C3 Super Mini**: Die Versorgung ist **3,3 V statt 5 V**. Dann liefert RX_OUT nie mehr als 3,3 V.
- **Bedrahtete Bauteile** für Lochraster, z. B. BC547B statt BC847B (SMD) und BAT46 statt BAT54S.
- **Vereinfacht:** Die Entstördrosseln L1/L2 (im Original „4,7 mH“, laut bbqkees eigentlich 4,7 µH), die
  Polyfuses F1/F2 und die Schutzdiode D5 entfallen. Begründung siehe Abschnitt 1a.

---

## 1. Funktionsweise kurz

- **Eingang:** Ein Brückengleichrichter aus 4 Dioden erzeugt aus dem Bus eine Gleichspannung (`VBUS`, ca. 12–17 V).
  Die Polung des Busses ist damit egal.
- **RX:** Über 10 k fließt ein kleiner Strom durch 360 Ω und eine 1N4148 nach GND. An der 1N4148
  entsteht die Referenz `U_REF` (≈ 0,6 V). Wenn der Master die Busspannung moduliert, ändert sich dieser Strom ein wenig.
  Das Signal wird kapazitiv auf Komparator A gekoppelt, dessen Ausgang an RX_OUT liegt.
- **TX:** Der ESP32 sendet auf TX_IN. Komparator B schaltet den Transistor, und der zieht über ca. 220 Ω Strom
  aus dem Bus (Strommodulation; so senden EMS-Slaves). In Ruhe (TX = High) ist der Transistor aus.

### 1a. Was gegenüber dem Original weggelassen wurde

| Bauteil | Original | Warum es entfallen kann |
|---|---|---|
| F1/F2 | Polyfuses, im Plan „N/A“ (nicht bestückt) | waren schon im Original nicht bestückt |
| L1/L2 | Entstördrosseln in den Busleitungen | nur EMV-Filterung. Viele Nachbauten laufen ohne; sie lassen sich später nachrüsten, wenn Störungen auftreten |
| D5 | BAT46 von GND nach VBUS | Hinter dem Brückengleichrichter kann VBUS nicht unter GND fallen. Ohne die Drosseln gibt es auch keine induktiven Spitzen mehr, die D5 abfangen müsste |

Die Funktion von RX und TX bleibt unverändert. Das ist eine Abwägung, kein Test: Sollten im Betrieb
Busfehler auftreten, wären die Drosseln das Erste, was man nachrüstet.

---

## 2. Netzliste

Netznamen: `L1`/`L2` = Busleitungen (direkt an J1), `VBUS` = Plus nach dem Gleichrichter, `NA` = Knoten nach dem 10-k-Widerstand,
`U_REF` = Referenz, `VCC` = **3V3 vom ESP32**, `GND` = Minus nach dem Gleichrichter = GND des ESP32.

### Eingang und Gleichrichter

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| J1 | Schraubklemme 2-pol. | Klemme 1 = `L1`, Klemme 2 = `L2` | | F1/F2/L1/L2 entfallen (Abschnitt 1a) |
| C1 | 68 pF | `L1` | `L2` | Keramik |
| D1 | BAT46 | Anode `L1` | Kathode `VBUS` | |
| D2 | BAT46 | Anode `GND` | Kathode `L1` | |
| D3 | BAT46 | Anode `L2` | Kathode `VBUS` | |
| D4 | BAT46 | Anode `GND` | Kathode `L2` | |

### RX-Stufe (Komparator A = LM393 Pins 1/2/3)

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| R1 | 10 k | `VBUS` | `NA` | |
| R2 | 360 Ω | `NA` | `U_REF` | |
| D6 | 1N4148 | Anode `U_REF` | Kathode `GND` | erzeugt `U_REF` ≈ 0,6 V |
| C2 | 10 µF | `NA` | LM393 **Pin 3** (IN+ A) | Keramik (X7R) empfohlen. Beim Elko: **Plus an `NA`** |
| R3 | 47 k | `U_REF` | LM393 **Pin 3** | |
| C3 | 1 nF | `NA` | LM393 **Pin 2** (IN− A) | Keramik |
| R4 | 10 k | `U_REF` | LM393 **Pin 2** | |
| R5 | 100 k | LM393 **Pin 2** | `GND` | |
| R6 | 4,7 k | `VCC` (3V3) | LM393 **Pin 1** (OUT A) | Pull-up, **an 3V3, nicht an 5 V** |
| R7 | 4,7 k | LM393 **Pin 1** | **RX_OUT → ESP32-C3 GPIO4** | |

### TX-Stufe (Komparator B = LM393 Pins 5/6/7)

| Bauteil | Wert | von | nach | Hinweis |
|---|---|---|---|---|
| — | Draht | `U_REF` | LM393 **Pin 5** (IN+ B) | |
| — | Draht | **TX_IN ← ESP32-C3 GPIO5** | LM393 **Pin 6** (IN− B) | |
| C4 | 10 nF | LM393 **Pin 6** | `GND` | |
| R8 | 4,7 k | `VCC` (3V3) | LM393 **Pin 7** (OUT B) = Basis Q1 | |
| Q1 | BC547B | B = Pin 7, E = `GND`, C = Knoten `TXC` | | NPN, TO-92 |
| R9 | 220 Ω, **1 W** | `VBUS` (über JP1) | `TXC` | ersetzt 4×910 Ω parallel (= 227 Ω). **Zulässig 210–250 Ω** |
| C5 | 1,5 nF | `TXC` | `GND` | |

### Versorgung LM393

| Bauteil | Wert | von | nach |
|---|---|---|---|
| — | | LM393 **Pin 8** (VCC) | ESP32 **3V3** |
| — | | LM393 **Pin 4** (GND) | ESP32 **GND** |
| C6 | 100 nF | Pin 8 | Pin 4 | so nah wie möglich am IC |

**LM393-Pinout (DIP-8, Kerbe oben links = Pin 1):**

```
        ┌──∪──┐
OUT A 1 │     │ 8 VCC (3V3)
IN− A 2 │     │ 7 OUT B
IN+ A 3 │     │ 6 IN− B
  GND 4 │     │ 5 IN+ B
        └─────┘
```

**BC547B (TO-92):** flache Seite zu dir, Beine nach unten, von links nach rechts **C – B – E**.
Bei Nachbauten anderer Hersteller vorher mit dem Datenblatt bzw. dem Diodentest prüfen.

---

## 3. Stückliste (bedrahtet)

| Anz. | Bauteil | Wert / Typ | wofür |
|---|---|---|---|
| 1 | IC | **LM393N** (DIP-8) + IC-Sockel | Komparatoren A und B |
| 4 | Schottky-Diode | **BAT46** (DO-35) | D1–D4 |
| 1 | Diode | **1N4148** | D6 |
| 1 | Transistor | **BC547B** (oder BC547C / BC548B) | Q1 |
| 2 | Widerstand | 10 kΩ | R1, R4 |
| 1 | Widerstand | 360 Ω | R2 |
| 1 | Widerstand | 47 kΩ | R3 |
| 1 | Widerstand | 100 kΩ | R5 |
| 3 | Widerstand | 4,7 kΩ | R6, R7, R8 |
| 1 | Widerstand | **220 Ω, 1 W** (alternativ 4× 910 Ω 0,25 W parallel) | R9 |
| 1 | Kondensator | 68 pF Keramik | C1 |
| 1 | Kondensator | 10 µF Keramik X7R (oder Elko ≥ 16 V) | C2 |
| 1 | Kondensator | 1 nF Keramik | C3 |
| 1 | Kondensator | 10 nF Keramik | C4 |
| 1 | Kondensator | 1,5 nF Keramik | C5 |
| 1 | Kondensator | 100 nF Keramik | C6 |
| 1 | Stiftleiste 2-pol. + Jumper | | JP1 (TX ein/aus) |
| 1 | Schraubklemme | 2-polig, RM 5,08 | Busanschluss |
| 2 | Buchsenleiste | 1×8 | ESP32-C3 steckbar |
| 1 | Lochrasterplatine | ca. 7×9 cm | |
| – | Kabel | 2-adrig, z. B. J-Y(St)Y 2×2×0,6 | Gateway ↔ RC310-Sockel |

Die Kosten liegen bei ca. 5–8 € plus Versand, z. B. bei Reichelt oder in einem Sortimentskasten.

---

## 4. Aufbau: alles auf einmal (RX + TX)

Die ganze Platine wird in einem Durchgang bestückt: Eingang, RX- und TX-Stufe, LM393, C6.

Damit TX beim ersten Test trotzdem sicher aus ist, gibt es **zwei Sicherungen**:

1. **Jumper JP1 in Reihe zu R9.** Dafür eine 2-polige Stiftleiste mit Jumper zwischen `VBUS` und R9 setzen
   (also `VBUS` → JP1 → R9 → `TXC`).
   - **Jumper gezogen:** Der Transistor kann keinen Strom aus dem Bus ziehen, die Platine liest nur mit.
   - **Jumper gesteckt:** TX aktiv.
2. **Software:** In EMS-ESP „Read only“ einschalten. Dann sendet der ESP32 gar nicht.

Ablauf: zuerst mit **gezogenem Jumper und Read only** testen. Wenn Telegramme ankommen, den Jumper stecken
und Read only ausschalten.

Zusätzliches Bauteil: 1× Stiftleiste 2-polig + 1× Jumper (JP1).

## 5. Prüfen vor dem ersten Anschluss

**Ohne Bus**, nur mit dem ESP32 per USB versorgt:
1. Pin 8 gegen Pin 4 ≈ **3,3 V**.
2. RX_OUT (GPIO4) ≈ **3,3 V** und **niemals mehr**.
3. Kein Kurzschluss zwischen den Busklemmen. Mit dem Ohmmeter messen; der Wert sollte im kΩ-Bereich liegen.

**Mit Bus** (am RC310-Sockel parallel angeklemmt, siehe `anschluss.md`):
1. `VBUS` gegen GND ≈ **12–17 V DC**.
2. `U_REF` gegen GND ≈ **0,5–0,7 V**.
3. Pin 3 ≈ `U_REF`, Pin 2 ≈ 0,9 × `U_REF`.
4. RX_OUT liegt meist auf ~3,3 V. Bei Busverkehr wackelt der Wert leicht, weil Datenbits ankommen.
5. Der RC310 muss normal weiterlaufen und darf keine Busstörung melden.

---

## 6. EMS-ESP einstellen

- Firmware **c3_mini_4M**, Board Profile: **C3MINI** (RX GPIO4, TX GPIO5)
- **Read only: an** beim ersten Test (JP1 gezogen)
- EMS Tx Mode: **EMS+** (RC310 = EMS2.0) oder **Auto**
- Im Dashboard prüfen: Es werden Telegramme empfangen, und RC310 und Station tauchen unter „Devices“ auf.
- Danach: JP1 stecken, Read only aus und in Console oder Dashboard auf **Tx-Fehler** achten.

---

## 7. Sicherheitshinweise

- Der Bus führt Kleinspannung (ca. 12–17 V). Trotzdem nicht unter Spannung umlöten.
- Die GND des ESP32 ist mit der Bus-Minusseite verbunden; galvanisch getrennt ist hier nichts. Das ist unkritisch,
  solange das USB-Netzteil ein normales, isoliertes Steckernetzteil ist.
- Bricht die Kommunikation des RC310 zusammen: Gateway abklemmen, und alles läuft wie vorher.

---

## 8. Lochraster-Plan

(wird nach der Layout-Optimierung ergänzt)
