"""Tischständer für die japanische Wordclock (Nachttisch).
Die Uhr wird von oben in eine Rinne gestellt und lehnt 10° nach hinten.
Zwei Varianten für das Netzteilkabel an der Buchse unten im Rand:
  winkel: 90°-USB-C-Stecker, Rinne 26 mm über dem Tisch
  gerade: gerader USB-C-Stecker, Rinne 51 mm über dem Tisch
Unter der Rinne ist der Ständer hohl (Rippen), das Kabel läuft nach hinten raus.
Koordinaten: X = Breite (wie Uhr von vorne), Y = nach hinten, Z = nach oben."""
import math, numpy as np
from manifold3d import CrossSection, Manifold, JoinType
import runpy
B = runpy.run_path("wordclock_jp_build.py")          # Maße der Uhr
PLATE, SOCK_X, write_3mf = B["PLATE"], B["SOCK_X"], B["write_3mf"]
CLK_D = B["RIM_H"] + B["BASE_T"] + B["H"] + B["T_BLACK"] + B["T_WHITE"]   # 39,8 mm
SOCK_A = B["T_BLACK"] + B["T_WHITE"] + B["H"] + B["BASE_T"] + B["st"]/2   # Buchsenmitte ab Front

TH = math.radians(10.0)
d = np.array([math.cos(TH), -math.sin(TH)])      # Tiefe der Uhr (Front -> Rückseite)
u = np.array([math.sin(TH),  math.cos(TH)])      # Hochrichtung der Uhr
S = CLK_D + 0.8                                  # Rinnenbreite mit Spiel
LIP_T, LIP_H = 3.0, 7.0                          # Lippe vorne (verdeckt nur den Rand unter den Zeichen)
WALL, BACK_H, BACK_LOW, SIDE_W = 4.0, 40.0, 10.0, 25.0   # Lehne: außen hoch (Seitenränder der Uhr), Mitte niedrig
FLOOR = 4.0                                      # Mindeststärke des Rinnenbodens
FOOT_D = 115.0                                   # Standtiefe (Kippsicherheit)
RIB_T, RIB_H = 4.0, 22.0                         # Rippen, Abstützhöhe an der Lehne
W = PLATE

def ext(pts):
    """2D-Profil (Y,Z) über die volle Breite W extrudieren -> (X,Y,Z)."""
    m = Manifold.extrude(CrossSection([np.array(pts)]), W)
    return m.transform([[0,0,1,0],[1,0,0,0],[0,1,0,0]])
def ext_x(pts, x0, x1):
    m = Manifold.extrude(CrossSection([np.array(pts)]), x1-x0)
    return m.transform([[0,0,1,x0],[1,0,0,0],[0,1,0,0]])

def staender(H, pocket):
    C0 = np.array([LIP_T, H])                     # Unterkante Front der Uhr
    P = lambda a, b: tuple(C0 + a*d + b*u)
    y_back = P(S+WALL, -FLOOR)[0]
    z_fb = P(S+WALL, -FLOOR)[1]                    # tiefster Punkt der Bodenunterseite
    floor = [P(-LIP_T,-FLOOR), P(S+WALL,-FLOOR), P(S+WALL,0), P(0,0), P(-LIP_T,0)]   # 4 mm, 10° geneigt
    lip   = [P(-LIP_T,-FLOOR), P(0,-FLOOR), P(0,LIP_H), P(-LIP_T,LIP_H)]
    back_lo = [P(S,-FLOOR), P(S+WALL,-FLOOR), P(S+WALL,BACK_LOW), P(S,BACK_LOW)]
    back_hi = [P(S,-FLOOR), P(S+WALL,-FLOOR), P(S+WALL,BACK_H), P(S,BACK_H)]
    yl = min(P(-LIP_T,0)[0], 0.0)
    skirt = [(yl,0), (LIP_T,0), P(0,-FLOOR), P(-LIP_T,0), (yl, P(-LIP_T,0)[1])]
    m = ext(floor) + ext(lip) + ext(back_lo) + ext(skirt) + ext_x(back_hi, 0, SIDE_W) + ext_x(back_hi, W-SIDE_W, W)
    # Rippen: tragen den Boden und stützen die Lehne bis zur Standtiefe ab
    qt = P(S+WALL, RIB_H)
    rib = [(yl,0), (FOOT_D,0), (FOOT_D,3.0), qt, P(S+WALL,-FLOOR), P(-LIP_T,-FLOOR)]
    rcs = CrossSection([np.array(rib)])
    # Aussparung nur unter dem Rinnenboden (oben begrenzt durch den Boden), Abstützung hinten bleibt voll
    cut_r = CrossSection.square((y_back-12.0, 400.0)).translate((6.0, -10.0))
    rcs = rcs - (rcs.offset(-6.0, JoinType.Miter) ^ cut_r)
    px0, px1 = SOCK_X-pocket[0]/2, SOCK_X+pocket[0]/2
    for xc in (RIB_T/2, 50, 100, 145, px0-RIB_T/2-3, px1+RIB_T/2+3, 248, W-RIB_T/2):
        m += Manifold.extrude(rcs, RIB_T).transform([[0,0,1,xc-RIB_T/2],[1,0,0,0],[0,1,0,0]])
    # Durchbruch im Rinnenboden unter der Buchse
    a0, a1 = SOCK_A-pocket[1]/2, SOCK_A+pocket[1]/2
    hole = [P(a0,-50), P(a1,-50), P(a1,5), P(a0,5)]
    m -= ext_x(hole, px0, px1)
    return m, H

for name, H, pocket in (("winkel", 26.0, (26.0, 20.0)), ("gerade", 51.0, (20.0, 14.0))):
    m, H = staender(H, pocket)
    print(name, "genus", m.genus(), "Vol %.0f cm3" % (m.volume()/1000), "bbox", [round(v,1) for v in m.bounding_box()])
    write_3mf("wordclock_jp_staender_%s.3mf" % name, "Wordclock JP Tischstaender %s" % name, m)
    B["write_stl"]("wordclock_jp_staender_%s.stl" % name, m)
    globals()["st_"+name] = m
