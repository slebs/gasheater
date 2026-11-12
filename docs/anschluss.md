# Anschluss des EMS-ESP-Gateways

## Anschlusspunkt: Wandsockel des RC310

Im Sockel sitzen links zwei Schraubklemmen, an denen das 2-adrige Buskabel aus der
Wohnungsstation ankommt. Das ist der EMS-Bus: Kleinspannung und verpolungssicher.

```
Wohnungsstation ──── 2-Draht EMS ────┬──── RC310 (Sockel, Schraubklemmen links)
                                     └──── EMS-ESP-Gateway (parallel, 2 Adern)
```

## Vorgehen

1. RC310 nach oben vom Sockel abziehen. Damit ist der Bus offen; die Station läuft mit ihren
   eigenen Drehreglern weiter.
2. Eine zweite Ader pro Klemme zuführen. Dafür Aderendhülsen (Zwillingshülsen) verwenden,
   z. B. aus einem Stück J-Y(St)Y 2x2x0,6 oder einer Klingelleitung.
3. Gateway an der EMS-Klemme anschließen; die Polung ist egal.
4. Gateway mit Strom versorgen. Ein USB-Netzteil ist stabiler als die Versorgung über den Bus.
5. RC310 wieder aufstecken und prüfen, dass er normal startet und keine Fehlermeldung zeigt.

## Regeln

- Nichts im 230-V-Bereich der Station (Control box) anfassen.
- Den Wärmezähler (Abrechnungsgerät, verplombt) nur optisch auslesen, nie öffnen oder abklemmen.
- Beim ersten Start EMS-ESP in „Read only“ betreiben.
- Sollwerte nicht im Minutentakt per Automation schreiben, weil das den Speicher des RC310 abnutzt.
