#!/usr/bin/env python3
"""Lochraster-Layout für das EMS-Interface (ESP32-C3 Super Mini auf Lochraster 5 × 7 cm, 3,3 V).

- Bauteile werden auf einem 2,54-mm-Raster platziert (Platzierung in tools/placement.json,
  per --optimize automatisch verbessert: Simulated Annealing auf minimale Drahtlänge).
- Leitungen werden automatisch verlegt (nur waagerecht/senkrecht, Lötseite). Wo eine
  Kreuzung nötig ist, wird eine isolierte Drahtbrücke auf der Bauteilseite gesetzt.
- Danach wird die Verdrahtung gegen die Soll-Netzliste (docs/schaltplan.md) geprüft:
  jedes Netz zusammenhängend, keine Verbindung zwischen fremden Netzen.

Aufruf:
  python3 tools/lochraster.py docs              # Plan aus tools/placement.json erzeugen
  python3 tools/lochraster.py docs --optimize   # Platzierung neu optimieren (dauert einige Minuten)
"""
import heapq
import json
import math
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PLACEMENT_FILE = os.path.join(HERE, "placement.json")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = args[0] if args else "docs"
OPTIMIZE = "--optimize" in sys.argv
ITERS = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--iters=")), 700)

P = 20   # px pro Raster im SVG
M = 40   # Rand im SVG

# ------------------------------------------------------------------ Board / ESP32-C3 Super Mini
W, H = 18, 24           # Lochrasterplatine 5 × 7 cm = 18 × 24 Löcher
OFF = 0                 # Platzierung absolut
EX0, GAP = 0, 6         # Super Mini: Stiftreihen 6 Raster = 15,24 mm auseinander
EX1 = EX0 + GAP
EY0 = 1                 # erste Stiftreihe; USB-C ragt über den oberen Rand hinaus
# Pinbelegung, Draufsicht, USB-C oben (Beschriftung auf dem Board: links 5…21, rechts 5V/G/3V/4…0)
ESP_L = ["IO5", "IO6", "IO7", "IO8", "IO9", "IO10", "IO20", "IO21"]
ESP_R = ["5V", "GND", "3V3", "IO4", "IO3", "IO2", "IO1", "IO0"]
ESP_USE = {"IO4": "RXO", "IO5": "P6", "GND": "GND", "3V3": "VCC"}   # EMS-ESP Profil C3MINI: RX 4, TX 5
# Sperrfläche für Bauteile (das Modul steckt auf Buchsenleisten darüber). Leitungen darunter sind erlaubt.
KEEP_BODY = {(x, y) for x in range(EX0, EX1 + 1) for y in range(0, EY0 + 8)}

# ------------------------------------------------------------------ Bauteil-Vorlagen
# Pins relativ zu Pin 1, Rotation r = 0..3 (90°-Schritte, echte Drehung, nie gespiegelt)
TEMPL = {
    "res": [(0, 0), (4, 0)],
    "res1w": [(0, 0), (5, 0)],
    "diode": [(0, 0), (4, 0)],          # Pin 1 = Anode, Pin 2 = Kathode
    "ccap": [(0, 0), (2, 0)],
    "jumper": [(0, 0), (1, 0)],
    "terminal": [(0, 0), (0, 2)],
    "dip8": [(0, 0), (0, 1), (0, 2), (0, 3), (3, 3), (3, 2), (3, 1), (3, 0)],   # Pin 1..8
    "to92": [(0, 0), (1, 0), (2, 0)],   # C, B, E; flache Seite Richtung +y (r=0)
}
ALLOWED_R = {"dip8": (0, 2), "to92": (0, 2), "terminal": (0,),
             # r = 4..7: stehend eingebaut (Raster 2,54 mm), nur Widerstände (¼ W) und Dioden
             "res": tuple(range(8)), "diode": tuple(range(8))}
UPRIGHT = {"res": [(0, 0), (1, 0)], "diode": [(0, 0), (1, 0)]}

# ref: (kind, value, [(net, pinlabel), ...])
PARTS = {
    "J1": ("terminal", "EMS-Bus", [("NL1", "1"), ("NL2", "2")]),
    "C1": ("ccap", "68p", [("NL1", ""), ("NL2", "")]),
    "D1": ("diode", "BAT46", [("NL1", "A"), ("VBUS", "K")]),
    "D2": ("diode", "BAT46", [("GND", "A"), ("NL1", "K")]),
    "D3": ("diode", "BAT46", [("NL2", "A"), ("VBUS", "K")]),
    "D4": ("diode", "BAT46", [("GND", "A"), ("NL2", "K")]),
    "R1": ("res", "10k", [("VBUS", ""), ("NA", "")]),
    "R2": ("res", "360R", [("NA", ""), ("UREF", "")]),
    "D6": ("diode", "1N4148", [("UREF", "A"), ("GND", "K")]),
    "C2": ("ccap", "10µ", [("NA", ""), ("P3", "")]),
    "C3": ("ccap", "1n", [("NA", ""), ("P2", "")]),
    "R3": ("res", "47k", [("UREF", ""), ("P3", "")]),
    "R4": ("res", "10k", [("UREF", ""), ("P2", "")]),
    "R5": ("res", "100k", [("P2", ""), ("GND", "")]),
    "U1": ("dip8", "LM393", [("P1", "1"), ("P2", "2"), ("P3", "3"), ("GND", "4"),
                             ("UREF", "5"), ("P6", "6"), ("P7", "7"), ("VCC", "8")]),
    "C6": ("ccap", "100n", [("VCC", ""), ("GND", "")]),
    "R6": ("res", "4k7", [("VCC", ""), ("P1", "")]),
    "R7": ("res", "4k7", [("P1", ""), ("RXO", "")]),
    "C4": ("ccap", "10n", [("P6", ""), ("GND", "")]),
    "R8": ("res", "4k7", [("VCC", ""), ("P7", "")]),
    "Q1": ("to92", "BC547B", [("TXC", "C"), ("P7", "B"), ("GND", "E")]),
    "JP1": ("jumper", "TX ein", [("VBUS", "1"), ("JPX", "2")]),
    "R9": ("res1w", "220R 1W", [("JPX", ""), ("TXC", "")]),
    "C5": ("ccap", "1,5n", [("TXC", ""), ("GND", "")]),
}

# Soll-Netzliste (aus docs/schaltplan.md, vereinfachte Variante ohne L1/L2/D5)
EXPECTED = {
    "NL1": {"J1.1", "C1.1", "D1.A", "D2.K"},
    "NL2": {"J1.2", "C1.2", "D3.A", "D4.K"},
    "VBUS": {"D1.K", "D3.K", "R1.1", "JP1.1"},
    "GND": {"D2.A", "D4.A", "D6.K", "R5.2", "U1.4", "C6.2", "C4.2", "Q1.E", "C5.2", "ESP.GND"},
    "NA": {"R1.2", "R2.1", "C2.1", "C3.1"},
    "UREF": {"R2.2", "D6.A", "R3.1", "R4.1", "U1.5"},
    "P3": {"C2.2", "R3.2", "U1.3"},
    "P2": {"C3.2", "R4.2", "R5.1", "U1.2"},
    "P1": {"U1.1", "R6.2", "R7.1"},
    "RXO": {"R7.2", "ESP.IO4"},
    "VCC": {"U1.8", "C6.1", "R6.1", "R8.1", "ESP.3V3"},
    "P6": {"U1.6", "C4.1", "ESP.IO5"},
    "P7": {"U1.7", "R8.2", "Q1.B"},
    "TXC": {"Q1.C", "R9.2", "C5.1"},
    "JPX": {"JP1.2", "R9.1"},
}
NETS = sorted(EXPECTED)


def rot(dx, dy, r):
    return [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][r]


def pin_id(ref, i, lbl):
    return f"{ref}.{lbl if lbl else i + 1}"


def esp_pins():
    pins = []
    for i, lbl in enumerate(ESP_L):
        pins.append((EX0, EY0 + i, ESP_USE.get(lbl, f"NC:{lbl}"), lbl))
    for i, lbl in enumerate(ESP_R):
        pins.append((EX1, EY0 + i, ESP_USE.get(lbl, f"NC:{lbl}"), lbl))
    return pins


def build(place):
    """place: ref -> (x_rel, y, r). Liefert (parts, bodies) oder None bei Kollision/außerhalb."""
    parts = []
    used = {}     # Loch -> ref (Pins)
    body = {}     # Loch -> ref (Bauteilkörper auf der Oberseite)
    for ref, (kind, value, pins) in PARTS.items():
        x0, y0, r = place[ref]
        x0 += OFF
        abs_pins = []
        tpl = TEMPL[kind]
        if r >= 4:
            tpl, r = UPRIGHT[kind], r - 4
        for (dx, dy), (net, lbl) in zip(tpl, pins):
            ox, oy = rot(dx, dy, r)
            x, y = x0 + ox, y0 + oy
            if not (0 <= x < W and 0 <= y < H) or (x, y) in KEEP_BODY:
                return None
            abs_pins.append((x, y, net, lbl))
        cells = set()
        if kind in ("res", "res1w", "diode", "ccap"):
            (ax, ay, *_), (bx, by, *_) = abs_pins
            n = abs(bx - ax) + abs(by - ay)
            for t in range(1, n):
                cells.add((ax + (bx - ax) * t // n, ay + (by - ay) * t // n))
        elif kind == "dip8":
            xs = sorted({q[0] for q in abs_pins})
            ys = sorted({q[1] for q in abs_pins})
            for x in range(xs[0] + 1, xs[-1]):
                for y in ys:
                    cells.add((x, y))
        elif kind == "to92":
            fs = 1 if abs_pins[0][0] < abs_pins[2][0] else -1   # flache Seite +y bei fs=1
            for x, y, *_ in abs_pins:
                cells.add((x, y - fs))                          # runde Seite
        for x, y, *_ in abs_pins:
            if (x, y) in used or (x, y) in body:
                return None
            used[(x, y)] = ref
        for c in cells:
            if c in used or c in body or c in KEEP_BODY:
                return None
        for c in cells:
            body[c] = ref
        parts.append(dict(kind=kind, ref=ref, value=value, pins=abs_pins, upright=place[ref][2] >= 4))
    parts.append(dict(kind="esp", ref="ESP", value="ESP32 DevKit V1", pins=esp_pins()))
    return parts, set(body)


def make_pinmap(parts):
    pinmap = {}
    for p in parts:
        for i, (x, y, net, lbl) in enumerate(p["pins"]):
            pinmap[(x, y)] = (net, pin_id(p["ref"], i, lbl))
    return pinmap


# ------------------------------------------------------------------ Routing
JUMP_COST = 25


def route(net, src_set, dst, occ, pinmap, bodies, jump_ends):
    dist = {(dst, None): 0}
    prev = {}
    pq = [(0, dst, None)]
    while pq:
        d, xy, dirn = heapq.heappop(pq)
        if dist.get((xy, dirn), 1e9) < d:
            continue
        if xy in src_set and xy != dst:
            path, key = [(xy, False)], (xy, dirn)
            while key in prev:
                pk, jump = prev[key]
                path.append((pk[0], jump))
                key = pk
            path = path[::-1]
            return [h for h, _ in path], [j for _, j in path[:-1]]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = xy[0] + dx, xy[1] + dy
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            o = occ.get((nx, ny))
            turn = 3 if dirn and dirn != (dx, dy) else 0
            if o is None or o == net:
                cands = [(d + 1 + turn, ((nx, ny), (dx, dy)), False)]
            else:
                cands = []
            # isolierte Drahtbrücke auf der Bauteilseite: gerade, über 1–5 Löcher hinweg
            if xy not in pinmap and xy not in bodies and xy not in KEEP_BODY and xy not in jump_ends:
                for L in range(2, 7):
                    jx, jy = xy[0] + dx * L, xy[1] + dy * L
                    if not (0 <= jx < W and 0 <= jy < H):
                        break
                    mid = [(xy[0] + dx * t, xy[1] + dy * t) for t in range(1, L)]
                    if any(m in KEEP_BODY for m in mid):
                        break
                    if all(occ.get(m) in (None, net) for m in mid):
                        continue          # direkter Weg ist frei, keine Brücke nötig
                    o2 = occ.get((jx, jy))
                    if o2 is not None and o2 != net:
                        continue
                    if (jx, jy) in pinmap or (jx, jy) in bodies or (jx, jy) in KEEP_BODY or (jx, jy) in jump_ends:
                        continue
                    cands.append((d + JUMP_COST + L + turn, ((jx, jy), (dx, dy)), True))
            for nd, k, jmp in cands:
                if nd < dist.get(k, 1e9):
                    dist[k] = nd
                    prev[k] = ((xy, dirn), jmp)
                    heapq.heappush(pq, (nd, k[0], k[1]))
    return None


def try_order(order, pinmap, bodies, allow_fail=False):
    jump_ends = set()
    occ = {xy: n for xy, (n, _) in pinmap.items()}
    wires, jumps, cost = defaultdict(list), [], 0
    fails = 0
    for net in order:
        pins = [xy for xy, (n, _) in pinmap.items() if n == net]
        tree, todo = {pins[0]}, pins[1:]
        while todo:
            todo.sort(key=lambda q: min(abs(q[0] - t[0]) + abs(q[1] - t[1]) for t in tree))
            q = todo.pop(0)
            r = route(net, tree, q, occ, pinmap, bodies, jump_ends)
            if not r:
                if not allow_fail:
                    return ("FAIL", net)
                fails += 1
                cost += 200
                continue
            holes, jf = r
            seg = [holes[0]]
            for i, j in enumerate(jf):
                if j:
                    wires[net].append(seg)
                    jumps.append((net, holes[i], holes[i + 1]))
                    jump_ends.update((holes[i], holes[i + 1]))
                    cost += JUMP_COST
                    seg = [holes[i + 1]]
                else:
                    seg.append(holes[i + 1])
                    cost += 1
            wires[net].append(seg)
            for h in holes:
                occ[h] = net
                tree.add(h)
    if allow_fail:
        return cost, fails
    return cost, wires, jumps


def route_all(pinmap, bodies, n_orders, seed=1):
    rnd = random.Random(seed)
    best = None
    base = ["GND", "VBUS", "VCC"]
    for it in range(n_orders):
        rest = [n for n in NETS if n not in base]
        rnd.shuffle(rest)
        order = (base + rest) if it % 2 == 0 else rnd.sample(NETS, len(NETS))
        # gescheitertes Netz nach vorne ziehen und neu versuchen (einfaches Rip-up)
        for _ in range(10):
            r = try_order(order, pinmap, bodies)
            if r[0] != "FAIL":
                break
            order = [r[1]] + [n for n in order if n != r[1]]
        if r[0] != "FAIL" and (best is None or r[0] < best[0]):
            best = r
    return best


# ------------------------------------------------------------------ Platzierung
def hpwl(place):
    b = build(place)
    if not b:
        return None
    pts = defaultdict(list)
    for p in b[0]:
        for x, y, net, _ in p["pins"]:
            if not net.startswith("NC:"):
                pts[net].append((x, y))
    span = sum((max(x for x, _ in v) - min(x for x, _ in v)) + (max(y for _, y in v) - min(y for _, y in v))
               for v in pts.values())
    # Abstandsstrafe: Pins verschiedener Netze direkt nebeneinander blockieren Leitungswege
    hole = {}
    for p in b[0]:
        for x, y, net, _ in p["pins"]:
            hole[(x, y)] = net
    crowd = 0
    for (x, y), n in hole.items():
        free = 0
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            m = hole.get(q)
            if m is not None and m != n:
                crowd += 1
            if m is None and q not in b[1] and 0 <= q[0] < W and 0 <= q[1] < H:
                free += 1
        if free == 0 and not n.startswith("NC:"):
            crowd += 10          # Pin ohne freies Nachbarloch: nicht anschließbar
    return span + 2 * crowd


def moves(rnd, cur):
    cand = dict(cur)
    refs = list(PARTS)
    ref = rnd.choice(refs)
    x, y, r = cand[ref]
    kind = PARTS[ref][0]
    m = rnd.random()
    if m < 0.6:
        cand[ref] = (x + rnd.randint(-2, 2), y + rnd.randint(-2, 2), r)
    elif m < 0.85:
        cand[ref] = (x, y, rnd.choice(ALLOWED_R.get(kind, (0, 1, 2, 3))))
    else:
        same = [q for q in refs if PARTS[q][0] == kind and q != ref]
        if same:
            q = rnd.choice(same)
            cand[ref], cand[q] = cand[q], cand[ref]
    return cand


def initial_placement():
    if os.path.exists(PLACEMENT_FILE):
        return {k: tuple(v) for k, v in json.load(open(PLACEMENT_FILE)).items()}
    # Greedy: Bauteile nacheinander an die gültige Stelle mit kleinster Netz-Spannweite setzen
    rnd = random.Random(3)
    place = {}
    order = ["U1", "C6", "R6", "R7", "C4", "R8", "Q1", "C5", "R9", "JP1", "R3", "R4", "R5", "C2", "C3",
             "R2", "D6", "R1", "D1", "D2", "D3", "D4", "C1", "J1"]
    global PARTS
    full = PARTS
    for ref in order:
        best = None
        for x in range(W):
            for y in range(H):
                for r in ALLOWED_R.get(full[ref][0], (0, 1, 2, 3)):
                    PARTS = {k: full[k] for k in list(place) + [ref]}
                    cand = dict(place)
                    cand[ref] = (x, y, r)
                    c = hpwl(cand)
                    if c is not None and (best is None or c < best[0]):
                        best = (c, (x, y, r))
        PARTS = full
        if best is None:
            sys.exit(f"Kein Platz für {ref}")
        place[ref] = best[1]
    # Simulated Annealing auf Netz-Spannweite (schnell)
    cur, cc = dict(place), hpwl(place)
    for i in range(20000):
        T = 6.0 * (1 - i / 20000) + 0.05
        cand = moves(rnd, cur)
        c = hpwl(cand)
        if c is not None and (c < cc or rnd.random() < math.exp((cc - c) / T)):
            cur, cc = cand, c
    print(f"  Startplatzierung (HPWL {cc})", flush=True)
    return cur


def evaluate(place, n_orders):
    b = build(place)
    if not b:
        return None
    parts, bodies = b
    pinmap = make_pinmap(parts)
    r = route_all(pinmap, bodies, n_orders)
    if not r:
        return None
    return r[0], parts, bodies, pinmap, r


def graded(place, n_orders):
    """Kosten auch für nicht vollständig verlegbare Platzierungen (200 je fehlender Verbindung)."""
    b = build(place)
    if not b:
        return None
    parts, bodies = b
    pinmap = make_pinmap(parts)
    rnd = random.Random(1)
    best = None
    base = ["GND", "VBUS", "VCC"]
    for it in range(n_orders):
        rest = [n for n in NETS if n not in base]
        rnd.shuffle(rest)
        order = (base + rest) if it % 2 == 0 else rnd.sample(NETS, len(NETS))
        c, f = try_order(order, pinmap, bodies, allow_fail=True)
        if best is None or c < best[0]:
            best = (c, f)
    return best


def optimize(place, iters, n_orders=6):
    rnd = random.Random(7)
    cur = dict(place)
    g = graded(cur, n_orders)
    if g is None:
        sys.exit("Startplatzierung ungültig")
    cur_cost = g[0]
    print(f"  Start: Kosten {cur_cost} (fehlend {g[1]})", flush=True)
    best, best_cost = (dict(cur), cur_cost) if g[1] == 0 else (None, 1e9)
    T0 = 40.0
    for i in range(iters):
        T = T0 * (1 - i / iters) + 0.5
        cand = moves(rnd, cur)
        g = graded(cand, n_orders)
        if g is None:
            continue
        c, f = g
        if c < cur_cost or rnd.random() < math.exp((cur_cost - c) / T):
            cur, cur_cost = cand, c
            if f == 0 and c < best_cost:
                best, best_cost = dict(cand), c
                print(f"  iter {i}: Kosten {c}", flush=True)
        if i % 100 == 0:
            print(f"  … iter {i}: aktuell {cur_cost}", flush=True)
    if best is None:
        sys.exit("Keine vollständig verdrahtbare Platzierung gefunden")
    return best


# ------------------------------------------------------------------ Verifikation
def verify(pinmap, wires, jumps):
    got = defaultdict(set)
    for (x, y), (net, pid) in pinmap.items():
        if not net.startswith("NC:"):
            got[net].add(pid)
    if dict(got) != EXPECTED:
        for n in sorted(set(got) | set(EXPECTED)):
            if got.get(n) != EXPECTED.get(n):
                print("Netz-Abweichung", n, sorted(got.get(n, [])), "soll", sorted(EXPECTED.get(n, [])))
        sys.exit("Platzierung passt nicht zur Netzliste")
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    hole_net = {}
    for net, paths in wires.items():
        for path in paths:
            for a, b in zip(path, path[1:]):
                assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
                union(a, b)
            for xy in path:
                if hole_net.setdefault(xy, net) != net:
                    sys.exit(f"KURZSCHLUSS bei {xy}: {hole_net[xy]} / {net}")
    for net, ja, jb in jumps:
        union(ja, jb)
        for xy in (ja, jb):
            if hole_net.setdefault(xy, net) != net:
                sys.exit(f"KURZSCHLUSS an Brücke {xy}")
    for xy, (net, pid) in pinmap.items():
        if hole_net.get(xy, net) != net:
            sys.exit(f"KURZSCHLUSS an Pin {pid}")
        find(xy)
    for net in EXPECTED:
        roots = {find(xy) for xy, (n, _) in pinmap.items() if n == net}
        if len(roots) != 1:
            sys.exit(f"Netz {net} nicht zusammenhängend")
    comp = defaultdict(set)
    for xy, (net, _) in pinmap.items():
        comp[find(xy)].add(net)
    for ns in comp.values():
        if len(ns) != 1:
            sys.exit(f"Netze verbunden: {ns}")


def merge_jumps(wires, jumps):
    merged = True
    while merged:
        merged = False
        for i, (n1, a1, b1) in enumerate(jumps):
            for j, (n2, a2, b2) in enumerate(jumps):
                if i != j and n1 == n2 and b1 == a2 and (a1[0] == b2[0] or a1[1] == b2[1]):
                    jumps[i] = (n1, a1, b2)
                    del jumps[j]
                    wires[n1] = [w for w in wires[n1] if w != [b1]]
                    merged = True
                    break
            if merged:
                break


# ------------------------------------------------------------------ SVG
COL = {
    "GND": "#1f2937", "VBUS": "#dc2626", "VCC": "#ea580c", "UREF": "#7c3aed", "NA": "#0891b2",
    "P1": "#16a34a", "P2": "#2563eb", "P3": "#db2777", "RXO": "#15803d", "P6": "#ca8a04",
    "P7": "#9333ea", "TXC": "#b91c1c", "NL1": "#0d9488", "NL2": "#4f46e5", "JPX": "#be123c",
}
NETNAME = {
    "GND": "GND", "VBUS": "VBUS (+12…17 V)", "VCC": "3V3", "UREF": "U_REF (≈0,6 V)", "NA": "Knoten NA",
    "P1": "LM393 Pin 1 (OUT A)", "P2": "LM393 Pin 2", "P3": "LM393 Pin 3", "RXO": "RX_OUT → D23",
    "P6": "TX_IN ← D5 (Pin 6)", "P7": "LM393 Pin 7 / Basis Q1", "TXC": "Kollektor Q1",
    "NL1": "Bus-Leitung 1", "NL2": "Bus-Leitung 2", "JPX": "JP1 → R9",
}
ORDER = ["GND", "VBUS", "VCC", "UREF", "NA", "P2", "P3", "P1", "RXO", "P6", "P7", "TXC", "NL1", "NL2", "JPX"]


def svg(parts, pinmap, wires, jumps, mirror):
    def X(x):
        return M + ((W - 1 - x) if mirror else x) * P

    def Y(y):
        return M + y * P

    bw, bh = 2 * M + (W - 1) * P, 2 * M + (H - 1) * P
    legend_w = 450
    hh = max(bh, 600)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw + legend_w}" height="{hh}" '
         f'viewBox="0 0 {bw + legend_w} {hh}" font-family="Helvetica,Arial,sans-serif">',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         f'<rect x="{M - 18}" y="{M - 18}" width="{(W - 1) * P + 36}" height="{(H - 1) * P + 36}" rx="6" '
         f'fill="#d9b382" stroke="#a07a4a"/>']
    for x in range(W):
        if x % 5 == 0:
            o.append(f'<text x="{X(x)}" y="{M - 24}" font-size="9" text-anchor="middle" fill="#7a5a30">{x}</text>')
    for y in range(H):
        if y % 5 == 0:
            o.append(f'<text x="{M - 26}" y="{Y(y) + 3}" font-size="9" text-anchor="end" fill="#7a5a30">{y}</text>')
    for x in range(W):
        for y in range(H):
            o.append(f'<circle cx="{X(x)}" cy="{Y(y)}" r="3.2" fill="#f3e2c3" stroke="#b08850" stroke-width="0.8"/>')
    wop, ww = (1.0, 5) if mirror else (0.35, 3.5)
    for net, paths in wires.items():
        for path in paths:
            if len(path) < 2:
                continue
            pts = " ".join(f"{X(x)},{Y(y)}" for x, y in path)
            o.append(f'<polyline points="{pts}" fill="none" stroke="{COL[net]}" stroke-width="{ww}" '
                     f'stroke-linecap="round" stroke-linejoin="round" opacity="{wop}"/>')
    for net, (ax, ay), (bx, by) in jumps:
        x1, y1, x2, y2 = X(ax), Y(ay), X(bx), Y(by)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ox, oy = -(y2 - y1) * 0.35, (x2 - x1) * 0.35
        o.append(f'<path d="M {x1} {y1} Q {mx + ox} {my + oy} {x2} {y2}" fill="none" stroke="{COL[net]}" '
                 f'stroke-width="3" stroke-dasharray="{"4 3" if mirror else "none"}" opacity="{0.5 if mirror else 1}"/>')
        o.append(f'<circle cx="{x1}" cy="{y1}" r="3" fill="{COL[net]}"/><circle cx="{x2}" cy="{y2}" r="3" fill="{COL[net]}"/>')
    for (x, y), (net, _) in pinmap.items():
        if net.startswith("NC:"):
            continue
        o.append(f'<circle cx="{X(x)}" cy="{Y(y)}" r="{4.5 if mirror else 3.6}" fill="#c0c0c0" stroke="#555" stroke-width="0.8"/>')
    cop = 0.25 if mirror else 1.0
    for p in parts:
        pts = [(X(x), Y(y)) for x, y, _, _ in p["pins"]]
        xs, ys = [a for a, _ in pts], [b for _, b in pts]
        k = p["kind"]
        g = [f'<g opacity="{cop}">']
        if k in ("res", "res1w", "diode", "ccap", "jumper"):
            (x1, y1), (x2, y2) = pts
            g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#777" stroke-width="1.6"/>')
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            horiz = abs(x2 - x1) > abs(y2 - y1)
            L = abs(x2 - x1) + abs(y2 - y1)
            if p.get("upright"):
                # stehend: Körper als Kreis über Pin 1, Draht zurück zu Pin 2
                bxp, byp = pts[0]
                col = {"res": "#e9d7b0", "diode": "#c2410c"}[k]
                if p["value"] == "1N4148":
                    col = "#f59e0b"
                g.append(f'<circle cx="{bxp}" cy="{byp}" r="8" fill="{col}" stroke="#333" stroke-width="1"/>')
                if k == "diode":
                    kx2, ky2 = pts[1]
                    g.append(f'<text x="{kx2}" y="{ky2 + 3}" font-size="8" text-anchor="middle" font-weight="bold" fill="#111">K</text>')
                if not mirror:
                    g.append(f'<text x="{bxp}" y="{byp - 11}" font-size="8.5" text-anchor="middle" fill="#111">{p["ref"]} {p["value"]}</text>')
                g.append("</g>")
                o += g
                continue
            if k == "ccap":
                bl, bt, rx = min(L - 6, 26), 13, 6
                fill = "#e8b04a" if p["value"] == "10µ" else "#f0c75e"
            elif k == "jumper":
                bl, bt, fill, rx = L + 12, 12, "#222", 2
            else:
                bl = min(L - 14, 46 if k == "res1w" else 30)
                bt = 14 if k == "res1w" else (10 if k == "diode" else 11)
                fill = {"res": "#e9d7b0", "res1w": "#cfd8dc", "diode": "#c2410c"}[k]
                if p["value"] == "1N4148":
                    fill = "#f59e0b"
                rx = 3
            w_, h_ = (bl, bt) if horiz else (bt, bl)
            g.append(f'<rect x="{cx - w_ / 2}" y="{cy - h_ / 2}" width="{w_}" height="{h_}" rx="{rx}" '
                     f'fill="{fill}" stroke="#333" stroke-width="1"/>')
            if k == "diode":
                kx, ky = pts[1]
                if horiz:
                    bx = cx + (w_ / 2 - 4) * (1 if kx > cx else -1)
                    g.append(f'<rect x="{bx - 2}" y="{cy - h_ / 2}" width="4" height="{h_}" fill="#111"/>')
                else:
                    by = cy + (h_ / 2 - 4) * (1 if ky > cy else -1)
                    g.append(f'<rect x="{cx - w_ / 2}" y="{by - 2}" width="{w_}" height="4" fill="#111"/>')
            if k == "jumper":
                for (a, b) in pts:
                    g.append(f'<rect x="{a - 3}" y="{b - 3}" width="6" height="6" fill="#d4af37"/>')
            if not mirror:
                lab = f'{p["ref"]} {p["value"]}'
                if horiz:
                    g.append(f'<text x="{cx}" y="{cy - h_ / 2 - 3}" font-size="9" text-anchor="middle" fill="#111">{lab}</text>')
                else:
                    g.append(f'<text x="{cx + w_ / 2 + 3}" y="{cy + 3}" font-size="9" fill="#111">{lab}</text>')
        elif k == "dip8":
            x0, x1_ = min(xs), max(xs)
            y0, y1_ = min(ys), max(ys)
            g.append(f'<rect x="{x0 + 5}" y="{y0 - 12}" width="{x1_ - x0 - 10}" height="{y1_ - y0 + 24}" rx="3" fill="#222" stroke="#000"/>')
            nx_ = (x0 + x1_) / 2
            p1x, p1y = pts[0]
            top = p1y == y0
            ny = y0 - 12 if top else y1_ + 12
            g.append(f'<path d="M {nx_ - 6} {ny} A 6 6 0 0 {0 if top else 1} {nx_ + 6} {ny}" fill="#666"/>')
            if not mirror:
                g.append(f'<circle cx="{p1x + (7 if p1x == x0 else -7)}" cy="{p1y + (4 if top else -4)}" r="2.5" fill="#bbb"/>')
                g.append(f'<text x="{nx_}" y="{(y0 + y1_) / 2 + 4}" font-size="10" fill="#fff" text-anchor="middle" '
                         f'transform="rotate(-90 {nx_} {(y0 + y1_) / 2})">LM393</text>')
                ty = y0 - 18 if top else y1_ + 26
                g.append(f'<text x="{nx_}" y="{ty}" font-size="9" text-anchor="middle">U1 (Kerbe {"oben" if top else "unten"}, Pin 1 ●)</text>')
                for (a, b), (_, _, _, lbl) in zip(pts, p["pins"]):
                    side = -1 if a == x0 else 1
                    g.append(f'<text x="{a + side * 9}" y="{b + 3}" font-size="8" text-anchor="{"end" if side < 0 else "start"}" fill="#111">{lbl}</text>')
        elif k == "to92":
            x0, x1_ = min(xs), max(xs)
            y0 = ys[0]
            bx = [q[0] for q in p["pins"]]
            fs = 1 if bx[0] < bx[2] else -1
            r = (x1_ - x0) / 2 + 6
            g.append(f'<path d="M {x0 - 6} {y0 + 6 * fs} L {x1_ + 6} {y0 + 6 * fs} A {r} 14 0 0 {0 if fs > 0 else 1} {x0 - 6} {y0 + 6 * fs} Z" fill="#222"/>')
            if not mirror:
                for (a, b), (_, _, _, lbl) in zip(pts, p["pins"]):
                    g.append(f'<text x="{a}" y="{b + (17 if fs > 0 else -11)}" font-size="8" text-anchor="middle">{lbl}</text>')
                g.append(f'<text x="{x0 - 10}" y="{y0 + 3}" font-size="9" text-anchor="end">Q1</text>')
        elif k == "terminal":
            x0, x1_ = min(xs), max(xs)
            y0, y1_ = min(ys), max(ys)
            g.append(f'<rect x="{x0 - 9}" y="{y0 - 9}" width="{x1_ - x0 + 18}" height="{y1_ - y0 + 18}" rx="2" fill="#2e8b57"/>')
            for (a, b) in pts:
                g.append(f'<rect x="{a - 3}" y="{b - 3}" width="6" height="6" fill="#d4af37"/>')
            if not mirror:
                g.append(f'<text x="{x0 - 10}" y="{y0 - 14}" font-size="9">J1 EMS-Bus</text>')
        elif k == "esp":
            x0, x1_ = min(xs), max(xs)
            y0, y1_ = min(ys), max(ys)
            g.append(f'<rect x="{x0 - 12}" y="{y0 - 1.6 * P}" width="{x1_ - x0 + 24}" height="{y1_ - y0 + 2.4 * P}" rx="4" '
                     f'fill="#111827" fill-opacity="{0.06 if mirror else 0.16}" stroke="#111827" stroke-width="1.5" stroke-dasharray="6 3"/>')
            cx = (x0 + x1_) / 2
            g.append(f'<rect x="{cx - 18}" y="{y0 - 1.6 * P - 8}" width="36" height="22" rx="4" fill="#9ca3af" opacity="0.8"/>')
            for (a, b), (_, _, net, lbl) in zip(pts, p["pins"]):
                used = not net.startswith("NC:")
                g.append(f'<rect x="{a - 4}" y="{b - 4}" width="8" height="8" fill="{"#d4af37" if used else "#555"}"/>')
                if not mirror:
                    inner = 1 if a == x0 else -1
                    g.append(f'<text x="{a + inner * 9}" y="{b + 3}" font-size="8" text-anchor="{"start" if inner > 0 else "end"}" '
                             f'fill="{"#111" if used else "#667"}" font-weight="{"bold" if used else "normal"}">{lbl}</text>')
            if not mirror:
                g.append(f'<text x="{cx}" y="{y1_ + 1.3 * P}" font-size="9" text-anchor="middle" font-weight="bold">ESP32-C3 Super Mini</text>')
                g.append(f'<text x="{cx}" y="{y0 - 1.6 * P + 7}" font-size="8" text-anchor="middle">USB-C</text>')
        g.append("</g>")
        o += g
    lx = bw + 10
    title = "Lötseite (gespiegelt)" if mirror else "Bestückungsseite (Draufsicht)"
    o.append(f'<text x="{lx}" y="30" font-size="15" font-weight="bold">EMS-Interface – {title}</text>')
    sub = ("So siehst du die Platine beim Löten (umgedreht). Leitungen = Draht/Lötzinn."
           if mirror else "Bauteile von oben. Leitungen liegen auf der Lötseite (blass dargestellt).")
    o.append(f'<text x="{lx}" y="48" font-size="9.5" fill="#444">{sub}</text>')
    yy = 72
    for net in ORDER:
        o.append(f'<rect x="{lx}" y="{yy - 9}" width="22" height="6" fill="{COL[net]}"/>')
        o.append(f'<text x="{lx + 28}" y="{yy - 3}" font-size="10">{NETNAME[net]}</text>')
        yy += 15
    yy += 8
    notes = [
        f"Raster 2,54 mm, Platine ≥ {W} × {H} Löcher (ca. {W * 0.254:.1f} × {H * 0.254:.1f} cm).",
        f"ESP32-C3-Stiftreihen: {GAP} Raster = {GAP * 2.54:.2f} mm ({GAP - 1} freie Löcher dazwischen).",
        "ESP32-C3 auf 2 Buchsenleisten 1×8 stecken, USB-C zeigt über den Rand.",
        "Genutzte Pins (gold): 3V3, GND, IO4 (RX), IO5 (TX).",
        "Unter dem Modul dürfen Leitungen (Lötseite) liegen, keine Bauteile.",
        "Dioden: schwarzer Ring = Kathode (bei stehenden: Pin „K“).",
        "Kreis = stehend eingebaut: Körper sitzt auf diesem Loch, Draht zum Nachbarloch.",
        "U1: Kerbe/Punkt = Pin 1 wie gezeichnet. Sockel verwenden!",
        "Q1 BC547B: flache Seite wie gezeichnet, Pins C/B/E beschriftet.",
        "JP1 gezogen = TX aus (nur Mitlesen).",
        "R9 = 220 Ω 1 W (oder 4×910 Ω parallel).",
        "C2 10 µF: Keramik. Elko: Plus an den NA-Pin.",
        "Gebogene Linien = isolierte Drahtbrücke auf der Bauteilseite.",
        "Vor Inbetriebnahme: Durchgangsprüfung jedes Netzes.",
    ]
    for n in notes:
        o.append(f'<text x="{lx}" y="{yy}" font-size="9.5" fill="#222">• {n}</text>')
        yy += 14
    o.append("</svg>")
    return "\n".join(o)


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    place = initial_placement()
    if OPTIMIZE:
        print("Optimiere Platzierung …", flush=True)
        place = optimize(place, ITERS)
        with open(PLACEMENT_FILE, "w") as f:
            json.dump({k: list(v) for k, v in place.items()}, f, indent=1, sort_keys=True)
        print(f"Platzierung gespeichert: {PLACEMENT_FILE}")
    ev = evaluate(place, 400)
    if ev is None:
        sys.exit("Platzierung ungültig oder nicht routbar")
    _, parts, bodies, pinmap, (cost, wires, jumps) = ev
    merge_jumps(wires, jumps)
    verify(pinmap, wires, jumps)
    n_seg = sum(len(p) - 1 for ps in wires.values() for p in ps)
    n_pins = sum(1 for v in pinmap.values() if not v[0].startswith("NC:"))
    print(f"OK: {len(EXPECTED)} Netze, {n_pins} genutzte Pins, {n_seg} Leitungsabschnitte, "
          f"{len(jumps)} Drahtbrücken oben, keine Kurzschlüsse")
    for net, ja, jb in jumps:
        print("  Brücke", net, ja, "->", jb)
    tag = "c3"
    with open(f"{OUT}/lochraster_{tag}_bestueckung.svg", "w") as f:
        f.write(svg(parts, pinmap, wires, jumps, False))
    with open(f"{OUT}/lochraster_{tag}_loetseite.svg", "w") as f:
        f.write(svg(parts, pinmap, wires, jumps, True))
    print("SVGs geschrieben")
