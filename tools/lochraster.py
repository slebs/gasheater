#!/usr/bin/env python3
"""Lochraster-Layout für das EMS-Interface (ESP32, 3,3 V).

Platziert die Bauteile auf einem 2,54-mm-Raster und verlegt die Verbindungen
automatisch (Lee-Routing, nur waagerecht/senkrecht, auf der Lötseite). Prüft
anschließend die Netzliste gegen docs/schaltplan.md: jedes Netz zusammenhängend,
keine Verbindung zwischen verschiedenen Netzen. Erzeugt zwei SVGs:
  docs/lochraster_bestueckung.svg  (Draufsicht Bauteilseite)
  docs/lochraster_loetseite.svg    (Lötseite, gespiegelt)
"""
import heapq
import sys
from collections import defaultdict

W, H = 36, 22  # Löcher (x 0..W-1, y 0..H-1)
P = 20         # px pro Raster im SVG
M = 40         # Rand im SVG

# ---------------------------------------------------------------- Bauteile
# kind, ref, value, pins: list of (x, y, net, pinlabel)
parts = []


def part(kind, ref, value, *pins, note=""):
    parts.append(dict(kind=kind, ref=ref, value=value, pins=list(pins), note=note))


# Eingang
part("terminal", "J1", "EMS-Bus", (1, 8, "T1", "1"), (1, 10, "T2", "2"))
part("inductor", "L1", "4,7µH", (3, 8, "T1", ""), (7, 8, "NL1", ""))
part("inductor", "L2", "4,7µH", (3, 10, "T2", ""), (7, 10, "NL2", ""))
part("ccap", "C1", "68p", (9, 8, "NL1", ""), (9, 10, "NL2", ""))
# Brückengleichrichter (Diode: erster Pin = Anode, zweiter = Kathode)
part("diode", "D1", "BAT46", (12, 7, "NL1", "A"), (12, 3, "VBUS", "K"))
part("diode", "D2", "BAT46", (12, 12, "GND", "A"), (12, 8, "NL1", "K"))
part("diode", "D3", "BAT46", (15, 7, "NL2", "A"), (15, 3, "VBUS", "K"))
part("diode", "D4", "BAT46", (15, 12, "GND", "A"), (15, 8, "NL2", "K"))
part("diode", "D5", "BAT46", (17, 12, "GND", "A"), (17, 3, "VBUS", "K"))
# RX
part("res", "R1", "10k", (19, 3, "VBUS", ""), (19, 7, "NA", ""))
part("res", "R2", "360R", (20, 7, "NA", ""), (20, 11, "UREF", ""))
part("diode", "D6", "1N4148", (20, 12, "UREF", "A"), (20, 16, "GND", "K"))
part("ccap", "C2", "10µ", (22, 5, "NA", ""), (24, 5, "P3", ""))
part("ccap", "C3", "1n", (22, 7, "NA", ""), (24, 7, "P2", ""))
part("res", "R3", "47k", (22, 13, "UREF", ""), (26, 13, "P3", ""))
part("res", "R4", "10k", (22, 15, "UREF", ""), (26, 15, "P2", ""))
part("res", "R5", "100k", (23, 17, "P2", ""), (27, 17, "GND", ""))
# LM393: links Pin1..4 (oben→unten), rechts Pin8..5
IX, IY = 27, 8
part("dip8", "U1", "LM393",
     (IX, IY + 0, "P1", "1"), (IX, IY + 1, "P2", "2"), (IX, IY + 2, "P3", "3"), (IX, IY + 3, "GND", "4"),
     (IX + 3, IY + 3, "UREF", "5"), (IX + 3, IY + 2, "P6", "6"), (IX + 3, IY + 1, "P7", "7"), (IX + 3, IY + 0, "VCC", "8"))
part("ccap", "C6", "100n", (31, 6, "VCC", ""), (33, 6, "GND", ""))
part("res", "R6", "4k7", (26, 2, "VCC", ""), (30, 2, "P1", ""))
part("res", "R7", "4k7", (27, 4, "P1", ""), (31, 4, "RXO", ""))
# TX
part("ccap", "C4", "10n", (32, 13, "P6", ""), (32, 15, "GND", ""))
part("res", "R8", "4k7", (29, 13, "VCC", ""), (29, 17, "P7", ""))
part("to92", "Q1", "BC547B", (30, 19, "TXC", "C"), (31, 19, "P7", "B"), (32, 19, "GND", "E"))
part("jumper", "JP1", "TX ein", (23, 1, "VBUS", "1"), (24, 1, "JPX", "2"))
part("res1w", "R9", "220R 1W", (24, 20, "JPX", ""), (29, 20, "TXC", ""))
part("ccap", "C5", "1,5n", (26, 19, "TXC", ""), (28, 19, "GND", ""))
# Anschluss zum ESP32 (Dupont-Kabel)
part("header", "J2", "ESP32",
     (34, 8, "VCC", "3V3"), (34, 9, "GND", "GND"), (34, 10, "RXO", "D23"), (34, 11, "P6", "D5"))

# Soll-Netzliste (aus docs/schaltplan.md), unabhängig von der Platzierung notiert
EXPECTED = {
    "T1": {"J1.1", "L1.1"},
    "T2": {"J1.2", "L2.1"},
    "NL1": {"L1.2", "C1.1", "D1.A", "D2.K"},
    "NL2": {"L2.2", "C1.2", "D3.A", "D4.K"},
    "VBUS": {"D1.K", "D3.K", "D5.K", "R1.1", "JP1.1"},
    "GND": {"D2.A", "D4.A", "D5.A", "D6.K", "R5.2", "U1.4", "C6.2", "C4.2", "Q1.E", "C5.2", "J2.GND"},
    "NA": {"R1.2", "R2.1", "C2.1", "C3.1"},
    "UREF": {"R2.2", "D6.A", "R3.1", "R4.1", "U1.5"},
    "P3": {"C2.2", "R3.2", "U1.3"},
    "P2": {"C3.2", "R4.2", "R5.1", "U1.2"},
    "P1": {"U1.1", "R6.2", "R7.1"},
    "RXO": {"R7.2", "J2.D23"},
    "VCC": {"U1.8", "C6.1", "R6.1", "R8.1", "J2.3V3"},
    "P6": {"U1.6", "C4.1", "J2.D5"},
    "P7": {"U1.7", "R8.2", "Q1.B"},
    "TXC": {"Q1.C", "R9.2", "C5.1"},
    "JPX": {"JP1.2", "R9.1"},
}


def pin_id(p, i, lbl):
    return f"{p['ref']}.{lbl if lbl else i + 1}"


# ---------------------------------------------------------------- Prüfung Platzierung
pinmap = {}   # (x,y) -> (net, pinid)
for p in parts:
    for i, (x, y, net, lbl) in enumerate(p["pins"]):
        assert 0 <= x < W and 0 <= y < H, (p["ref"], x, y)
        if (x, y) in pinmap:
            sys.exit(f"Loch doppelt belegt: {(x, y)} {pinmap[(x, y)]} / {p['ref']}")
        pinmap[(x, y)] = (net, pin_id(p, i, lbl))

got = defaultdict(set)
for (x, y), (net, pid) in pinmap.items():
    got[net].add(pid)
if dict(got) != EXPECTED:
    for n in sorted(set(got) | set(EXPECTED)):
        if got.get(n) != EXPECTED.get(n):
            print("Netz-Abweichung", n, "ist", sorted(got.get(n, [])), "soll", sorted(EXPECTED.get(n, [])))
    sys.exit("Platzierung passt nicht zur Netzliste")

# ---------------------------------------------------------------- Routing
# Leitungen liegen auf der Lötseite. Muss eine Leitung eine fremde Leitung kreuzen,
# wird eine isolierte Drahtbrücke auf der Bauteilseite gesetzt (Sprung über 1 Loch).
import random

JUMP_COST = 25


def route(net, src_set, dst, occ):
    dist = {(dst, None): 0}
    prev = {}
    pq = [(0, dst, None)]
    while pq:
        d, xy, dirn = heapq.heappop(pq)
        if dist.get((xy, dirn), 1e9) < d:
            continue
        if xy in src_set and xy != dst:
            path, key = [], (xy, dirn)
            path.append((xy, False))
            while key in prev:
                pk, jump = prev[key]
                path.append((pk[0], jump))
                key = pk
            path = path[::-1]
            # path: [(xy, jump_to_next?)...] -> list of holes and jump flags per step
            holes = [h for h, _ in path]
            jumps = [j for _, j in path[:-1]]
            return holes, jumps
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = xy[0] + dx, xy[1] + dy
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            o = occ.get((nx, ny))
            turn = 3 if dirn and dirn != (dx, dy) else 0
            if o is None or o == net:
                nd, k, jmp = d + 1 + turn, ((nx, ny), (dx, dy)), False
            else:
                # Sprung über eine fremde LEITUNG (kein Pin) auf ein freies/eigenes Loch
                if (nx, ny) in pinmap:
                    continue
                jx, jy = nx + dx, ny + dy
                if not (0 <= jx < W and 0 <= jy < H):
                    continue
                o2 = occ.get((jx, jy))
                if o2 is not None and o2 != net:
                    continue
                if xy in jump_ends or (jx, jy) in jump_ends:
                    continue
                nd, k, jmp = d + JUMP_COST + turn, ((jx, jy), (dx, dy)), True
            if nd < dist.get(k, 1e9):
                dist[k] = nd
                prev[k] = ((xy, dirn), jmp)
                heapq.heappush(pq, (nd, k[0], k[1]))
    return None


NETS = sorted(EXPECTED)


def try_order(order):
    global jump_ends
    jump_ends = set()
    occ = {xy: n for xy, (n, _) in pinmap.items()}
    wires = defaultdict(list)   # net -> list of hole-paths (nur Lötseite, zusammenhängend)
    jumps = []                  # (net, a, b) Drahtbrücken oben
    cost = 0
    for net in order:
        pins = [xy for xy, (n, _) in pinmap.items() if n == net]
        tree = {pins[0]}
        todo = pins[1:]
        while todo:
            todo.sort(key=lambda q: min(abs(q[0] - t[0]) + abs(q[1] - t[1]) for t in tree))
            q = todo.pop(0)
            r = route(net, tree, q, occ)
            if not r:
                return None
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
    return cost, wires, jumps


jump_ends = set()
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
best = None
base = ["GND", "VBUS", "VCC"]
for it in range(400):
    rest = [n for n in NETS if n not in base]
    random.shuffle(rest)
    order = (base + rest) if it % 2 == 0 else random.sample(NETS, len(NETS))
    r = try_order(order)
    if r and (best is None or r[0] < best[0]):
        best = r
if best is None:
    sys.exit("Routing fehlgeschlagen")
_, wires, jumps = best
# hintereinanderliegende, gerade Brücken desselben Netzes zusammenfassen
merged = True
while merged:
    merged = False
    for i, (n1, a1, b1) in enumerate(jumps):
        for j, (n2, a2, b2) in enumerate(jumps):
            if i != j and n1 == n2 and b1 == a2 and (a1[0] == b2[0] or a1[1] == b2[1]):
                jumps[i] = (n1, a1, b2)
                del jumps[j]
                # Zwischenloch wird nicht mehr gebraucht, falls keine Leitung daran hängt
                wires[n1] = [w for w in wires[n1] if w != [b1]]
                merged = True
                break
        if merged:
            break
ORDER = ["GND", "VBUS", "VCC", "UREF", "NA", "P2", "P3", "P1", "RXO", "P6", "P7", "TXC",
         "NL1", "NL2", "T1", "T2", "JPX"]

# ---------------------------------------------------------------- Verifikation
# Union-Find über Leitungen, dann: jedes Netz genau eine Komponente, keine Fremdnetze
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
comp_nets = defaultdict(set)
for xy, (net, _) in pinmap.items():
    comp_nets[find(xy)].add(net)
for net in EXPECTED:
    roots = {find(xy) for xy, (n, _) in pinmap.items() if n == net}
    if len(roots) != 1:
        sys.exit(f"Netz {net} nicht zusammenhängend")
for r, ns in comp_nets.items():
    if len(ns) != 1:
        sys.exit(f"Netze verbunden: {ns}")
n_seg = sum(len(p) - 1 for ps in wires.values() for p in ps)
print(f"OK: {len(EXPECTED)} Netze, {len(pinmap)} Pins, {n_seg} Leitungsabschnitte, "
      f"{len(jumps)} Drahtbrücken oben, keine Kurzschlüsse")
for net, ja, jb in jumps:
    print("  Brücke", net, ja, "->", jb)

# ---------------------------------------------------------------- SVG
COL = {
    "GND": "#1f2937", "VBUS": "#dc2626", "VCC": "#ea580c", "UREF": "#7c3aed", "NA": "#0891b2",
    "P1": "#16a34a", "P2": "#2563eb", "P3": "#db2777", "RXO": "#15803d", "P6": "#ca8a04",
    "P7": "#9333ea", "TXC": "#b91c1c", "NL1": "#0d9488", "NL2": "#4f46e5", "T1": "#0d9488",
    "T2": "#4f46e5", "JPX": "#be123c",
}
NETNAME = {
    "GND": "GND", "VBUS": "VBUS (+12…17 V)", "VCC": "3V3", "UREF": "U_REF (≈0,6 V)", "NA": "Knoten NA",
    "P1": "LM393 Pin 1 (OUT A)", "P2": "LM393 Pin 2", "P3": "LM393 Pin 3", "RXO": "RX_OUT → D23",
    "P6": "TX_IN ← D5 (Pin 6)", "P7": "LM393 Pin 7 / Basis Q1", "TXC": "Kollektor Q1", "NL1": "Bus-Leitung 1",
    "NL2": "Bus-Leitung 2", "T1": "Klemme 1", "T2": "Klemme 2", "JPX": "JP1 → R9",
}


def X(x, mirror):
    return M + ((W - 1 - x) if mirror else x) * P


def Y(y):
    return M + y * P


def svg(mirror):
    bw, bh = 2 * M + (W - 1) * P, 2 * M + (H - 1) * P
    legend_w = 440
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw + legend_w}" height="{max(bh, 640)}" '
         f'viewBox="0 0 {bw + legend_w} {max(bh, 640)}" font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="100%" height="100%" fill="#ffffff"/>',
         f'<rect x="{M - 18}" y="{M - 18}" width="{(W - 1) * P + 36}" height="{(H - 1) * P + 36}" rx="6" '
         f'fill="#d9b382" stroke="#a07a4a"/>']
    # Koordinaten
    for x in range(W):
        if x % 5 == 0:
            o.append(f'<text x="{X(x, mirror)}" y="{M - 24}" font-size="9" text-anchor="middle" fill="#7a5a30">{x}</text>')
    for y in range(H):
        if y % 5 == 0:
            o.append(f'<text x="{M - 26}" y="{Y(y) + 3}" font-size="9" text-anchor="end" fill="#7a5a30">{y}</text>')
    # Löcher
    for x in range(W):
        for y in range(H):
            o.append(f'<circle cx="{X(x, mirror)}" cy="{Y(y)}" r="3.2" fill="#f3e2c3" stroke="#b08850" stroke-width="0.8"/>')
    # Leitungen
    wop = 1.0 if mirror else 0.35
    ww = 5 if mirror else 3.5
    for net, paths in wires.items():
        for path in paths:
            pts = " ".join(f"{X(x, mirror)},{Y(y)}" for x, y in path)
            o.append(f'<polyline points="{pts}" fill="none" stroke="{COL[net]}" stroke-width="{ww}" '
                     f'stroke-linecap="round" stroke-linejoin="round" opacity="{wop}"/>')
    # Drahtbrücken auf der Bauteilseite (isoliert)
    for net, (ax, ay), (bx, by) in jumps:
        x1, y1, x2, y2 = X(ax, mirror), Y(ay), X(bx, mirror), Y(by)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ox, oy = (-(y2 - y1) * 0.35, (x2 - x1) * 0.35)
        o.append(f'<path d="M {x1} {y1} Q {mx + ox} {my + oy} {x2} {y2}" fill="none" stroke="{COL[net]}" '
                 f'stroke-width="3" stroke-dasharray="{"4 3" if mirror else "none"}" opacity="{0.5 if mirror else 1}"/>')
        o.append(f'<circle cx="{x1}" cy="{y1}" r="3" fill="{COL[net]}"/><circle cx="{x2}" cy="{y2}" r="3" fill="{COL[net]}"/>')
    # Lötpunkte an Pins
    for (x, y), (net, _) in pinmap.items():
        o.append(f'<circle cx="{X(x, mirror)}" cy="{Y(y)}" r="{4.5 if mirror else 3.6}" fill="#c0c0c0" stroke="#555" stroke-width="0.8"/>')
    # Bauteile
    cop = 0.25 if mirror else 1.0
    for p in parts:
        pts = [(X(x, mirror), Y(y)) for x, y, _, _ in p["pins"]]
        xs, ys = [a for a, _ in pts], [b for _, b in pts]
        k = p["kind"]
        g = [f'<g opacity="{cop}">']
        if k in ("res", "res1w", "inductor", "diode", "ccap", "jumper"):
            (x1, y1), (x2, y2) = pts[0], pts[1]
            g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#777" stroke-width="1.6"/>')
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            horiz = abs(x2 - x1) > abs(y2 - y1)
            L = abs(x2 - x1) + abs(y2 - y1)
            if k == "ccap":
                bl, bt, fill = min(L - 6, 26), 13, "#e8b04a" if p["value"] in ("10µ",) else "#f0c75e"
                rx = 6
            elif k == "jumper":
                bl, bt, fill, rx = L + 12, 12, "#222", 2
            else:
                bl = min(L - 14, 46 if k == "res1w" else 30)
                bt = 14 if k == "res1w" else (10 if k == "diode" else 11)
                fill = {"res": "#e9d7b0", "res1w": "#cfd8dc", "inductor": "#6b8e23", "diode": "#c2410c"}[k]
                if p["value"] == "1N4148":
                    fill = "#f59e0b"
                rx = 3
            w_, h_ = (bl, bt) if horiz else (bt, bl)
            g.append(f'<rect x="{cx - w_ / 2}" y="{cy - h_ / 2}" width="{w_}" height="{h_}" rx="{rx}" '
                     f'fill="{fill}" stroke="#333" stroke-width="1"/>')
            if k == "diode":  # Ring an Kathode
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
            # Beschriftung
            if not mirror:
                lab = f'{p["ref"]} {p["value"]}'
                below = p["ref"] in ("R9",)
                if horiz:
                    ty = cy + h_ / 2 + 10 if below else cy - h_ / 2 - 3
                    g.append(f'<text x="{cx}" y="{ty}" font-size="9" text-anchor="middle" fill="#111">{lab}</text>')
                else:
                    g.append(f'<text x="{cx + w_ / 2 + 3}" y="{cy + 3}" font-size="9" fill="#111">{lab}</text>')
        elif k == "dip8":
            x0, x1_ = min(xs), max(xs)
            y0, y1_ = min(ys), max(ys)
            g.append(f'<rect x="{x0 + 5}" y="{y0 - 12}" width="{x1_ - x0 - 10}" height="{y1_ - y0 + 24}" rx="3" fill="#222" stroke="#000"/>')
            nx_ = (x0 + x1_) / 2
            g.append(f'<path d="M {nx_ - 6} {y0 - 12} A 6 6 0 0 0 {nx_ + 6} {y0 - 12}" fill="#666"/>')
            if not mirror:
                g.append(f'<circle cx="{x0 + 12}" cy="{y0 - 4}" r="2.5" fill="#888"/>')
                g.append(f'<text x="{nx_}" y="{(y0 + y1_) / 2 + 4}" font-size="10" fill="#fff" text-anchor="middle" '
                         f'transform="rotate(-90 {nx_} {(y0 + y1_) / 2})">LM393</text>')
                g.append(f'<text x="{nx_}" y="{y0 - 18}" font-size="9" text-anchor="middle">U1 (Kerbe oben)</text>')
            for (a, b), (_, _, _, lbl) in zip(pts, p["pins"]):
                if not mirror:
                    side = -1 if a == x0 else 1
                    g.append(f'<text x="{a + side * 9}" y="{b + 3}" font-size="8" text-anchor="{"end" if side < 0 else "start"}" fill="#111">{lbl}</text>')
        elif k == "to92":
            x0, x1_ = min(xs), max(xs)
            y0 = ys[0]
            # flache Seite nach unten (zum Betrachter = Richtung +y)
            g.append(f'<path d="M {x0 - 6} {y0 + 6} L {x1_ + 6} {y0 + 6} A {(x1_ - x0) / 2 + 6} 14 0 0 0 {x0 - 6} {y0 + 6} Z" fill="#222"/>')
            if not mirror:
                for (a, b), (_, _, _, lbl) in zip(pts, p["pins"]):
                    g.append(f'<text x="{a}" y="{b + 17}" font-size="8" text-anchor="middle">{lbl}</text>')
                g.append(f'<text x="{x1_ + 10}" y="{y0 + 4}" font-size="9">Q1 BC547B</text>')
        elif k in ("terminal", "header"):
            x0, x1_ = min(xs), max(xs)
            y0, y1_ = min(ys), max(ys)
            fill = "#2e8b57" if k == "terminal" else "#222"
            pad = 9 if k == "terminal" else 6
            g.append(f'<rect x="{x0 - pad}" y="{y0 - pad}" width="{x1_ - x0 + 2 * pad}" height="{y1_ - y0 + 2 * pad}" rx="2" fill="{fill}"/>')
            for (a, b), (_, _, _, lbl) in zip(pts, p["pins"]):
                g.append(f'<rect x="{a - 3}" y="{b - 3}" width="6" height="6" fill="#d4af37"/>')
                if not mirror:
                    if k == "header":
                        g.append(f'<text x="{a - 12}" y="{b + 3}" font-size="9" text-anchor="end" font-weight="bold">{lbl}</text>')
            if not mirror:
                if k == "terminal":
                    g.append(f'<text x="{x0 - 10}" y="{y0 - 14}" font-size="9">J1 EMS-Bus</text>')
                else:
                    g.append(f'<text x="{x0 - 30}" y="{y0 - 12}" font-size="9">J2 → ESP32</text>')
        g.append("</g>")
        o += g
    # Legende
    lx = bw + 10
    title = "Lötseite (gespiegelt)" if mirror else "Bestückungsseite (Draufsicht)"
    o.append(f'<text x="{lx}" y="30" font-size="15" font-weight="bold">EMS-Interface – {title}</text>')
    sub = ("So siehst du die Platine beim Löten (umgedreht). Leitungen = Drahtbrücken/Lötzinn."
           if mirror else "Bauteile von oben. Leitungen liegen auf der Lötseite (blass dargestellt).")
    o.append(f'<text x="{lx}" y="48" font-size="9.5" fill="#444">{sub}</text>')
    yy = 72
    for net in ORDER:
        o.append(f'<rect x="{lx}" y="{yy - 9}" width="22" height="6" fill="{COL[net]}"/>')
        o.append(f'<text x="{lx + 28}" y="{yy - 3}" font-size="10">{NETNAME[net]}</text>')
        yy += 15
    yy += 8
    notes = [
        "Raster 2,54 mm, Platine ≥ 36 × 22 Löcher (ca. 9 × 6 cm).",
        "Dioden: schwarzer Ring = Kathode (K).",
        "U1: Kerbe/Punkt oben links = Pin 1. Sockel verwenden!",
        "Q1 BC547B: flache Seite unten, Pins C–B–E von links.",
        "JP1 gezogen = TX aus (nur Mitlesen).",
        "R9 = 220 Ω 1 W (oder 4×910 Ω parallel).",
        "C2 10 µF: Keramik. Elko: Plus an NA (Seite R1).",
        "J2 mit Dupont-Kabeln an ESP32: 3V3, GND, D23, D5.",
        "Gebogene Linien = isolierte Drahtbrücke auf der Bauteilseite.",
        "Vor Inbetriebnahme: Durchgangsprüfung jedes Netzes.",
    ]
    for n in notes:
        o.append(f'<text x="{lx}" y="{yy}" font-size="9.5" fill="#222">• {n}</text>')
        yy += 14
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs"
    open(f"{out}/lochraster_bestueckung.svg", "w").write(svg(False))
    open(f"{out}/lochraster_loetseite.svg", "w").write(svg(True))
    print("SVGs geschrieben")
