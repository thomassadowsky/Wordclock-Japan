import numpy as np, zipfile, math
from fontTools.ttLib import TTCollection
from fontTools.pens.basePen import BasePen
from manifold3d import CrossSection, Manifold, FillRule

# ---------- Parameter ----------
PLATE = 285.0            # Außenmaß
N = 8                    # 8x8 Felder
P = 1000/30.0            # 33.33 mm = 30 LEDs/m
OFF = (PLATE - N*P)/2    # 9.17 mm Rand
CH = 24.0                # Zeichengröße (Em)
T_BLACK, T_WHITE = 1.8, 1.0      # Weiss 1,0 mm (Diffusor-Test 26.09.2026)
HOLE_POS, HOLE_D_FRONT, HOLE_D_PILOT = 5.5, 3.3, 2.6
H = 22.0                 # Lichtraster-Höhe über der LED-Ebene
WALL_OUT, WALL_GRID = 2.4, 1.6

G = ["今は月火水木金土","日曜日の午前後零","一二三四五六七八","九十一二時半二三",
     "四五十一二三四五","六七八九分ちょう","どです。おはよう","ございまやすみ！"]

ttc = TTCollection('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
font = next(f for f in ttc.fonts if 'JP' in f['name'].getDebugName(1))
gs = font.getGlyphSet(); cmap = font.getBestCmap(); upm = font['head'].unitsPerEm

class FlatPen(BasePen):
    def __init__(s, gs): super().__init__(gs); s.contours=[]; s.cur=[]
    def _moveTo(s,p): s.cur=[p]
    def _lineTo(s,p): s.cur.append(p)
    def _curveToOne(s,p1,p2,p3):
        p0=s.cur[-1]
        for i in range(1,13):
            t=i/12; a=(1-t)**3; b=3*(1-t)**2*t; c=3*(1-t)*t*t; d=t**3
            s.cur.append((a*p0[0]+b*p1[0]+c*p2[0]+d*p3[0], a*p0[1]+b*p1[1]+c*p2[1]+d*p3[1]))
    def _qCurveToOne(s,p1,p2):
        p0=s.cur[-1]
        for i in range(1,9):
            t=i/8; s.cur.append(((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0],(1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1]))
    def _closePath(s):
        if len(s.cur)>2: s.contours.append(s.cur)
        s.cur=[]
    _endPath=_closePath

def glyph_cs(ch, cx, cy, mirror):
    g = gs[cmap[ord(ch)]]; pen = FlatPen(gs); g.draw(pen); s = CH/upm
    polys=[]
    for c in pen.contours:
        pts=[]
        for fx,fy in c:
            x = cx - g.width*s/2 + fx*s
            y = cy - (880-500)*s + fy*s
            if mirror: x = PLATE - x
            pts.append((x,y))
        polys.append(np.array(pts))
    return CrossSection(polys, FillRule.NonZero)

def rect(x0,y0,x1,y1): return CrossSection.square((x1-x0,y1-y0)).translate((x0,y0))
def circle(x,y,d): return CrossSection.circle(d/2, 48).translate((x,y))
def box(x0,y0,z0,x1,y1,z1): return Manifold.cube((x1-x0,y1-y0,z1-z0)).translate((x0,y0,z0))
corners=[(HOLE_POS,HOLE_POS),(PLATE-HOLE_POS,HOLE_POS),(HOLE_POS,PLATE-HOLE_POS),(PLATE-HOLE_POS,PLATE-HOLE_POS)]
def cell_center(r,c): return OFF+(c+0.5)*P, PLATE-(OFF+(r+0.5)*P)

# ---------- Front (Sichtseite unten, gespiegelt) ----------
glyphs = CrossSection()
for r,row in enumerate(G):
    for c,ch in enumerate(row):
        cx,cy = cell_center(r,c)
        glyphs = glyphs + glyph_cs(ch,cx,cy,mirror=True)
sq = rect(0,0,PLATE,PLATE)
holes = CrossSection()
for x,y in corners: holes = holes + circle(x,y,HOLE_D_FRONT)
black = Manifold.extrude(sq - glyphs - holes, T_BLACK)
white = Manifold.extrude(sq - holes, T_WHITE+0.02).translate((0,0,T_BLACK-0.02))
front = black + white

# ---------- Rückwand, zweiteilig: Boden (LED-Träger) + Lichtraster ----------
# Montage: Streifen in die Kanäle des Bodens kleben, verkabeln, dann das Raster
# aufsetzen (Wände greifen in Nuten) und von hinten verschrauben.
BASE_T = 3.0             # Bodenplatte
STRIP_W, STRIP_CLR = 10.0, 0.3     # Streifenbreite + Spiel je Seite
CH_D = 1.0               # Tiefe Streifenkanal und Wandnut
GROOVE_CLR = 0.2         # Spiel der Wand in der Nut je Seite
NOTCH_H_IN, NOTCH_H_OUT = 1.5, 4.0 # Durchlass unter den Wänden (über Bodenoberkante)
POST_D, NODE_D = 8.0, 7.0          # Eckpfosten / Schraubknoten im Raster
PILOT_DEPTH = 10.0
HOLE_CLR = 3.4           # M3 Durchgang im Boden
Z0 = BASE_T              # Oberkante Boden = LED-Ebene
top = Z0 + H             # Oberkante Raster = Auflage der Front
g0, g1 = OFF-WALL_GRID/2, OFF+N*P+WALL_GRID/2
gx = lambda k: OFF+k*P            # Rasterlinien / Kreuzungen
NODES_REAR = [(gx(2),gx(1)),(gx(6),gx(1)),(gx(1),gx(4)),(gx(7),gx(4)),(gx(2),gx(6)),(gx(6),gx(6))]  # Senkkopf von hinten
row_y = [cell_center(r,0)[1] for r in range(N)]
cw = STRIP_W + 2*STRIP_CLR

# --- Boden ---
boden = Manifold.extrude(sq, BASE_T)
cut = Manifold()
for yc in row_y:   # Streifenkanäle über die volle Breite (Enden liegen im Kabelkanal)
    cut += box(WALL_OUT+0.5, yc-cw/2, Z0-CH_D, PLATE-WALL_OUT-0.5, yc+cw/2, Z0+1)
    for c in range(N):   # Markierungen: LED-Mitte je Spalte
        xc = OFF+(c+0.5)*P
        cut += box(xc-0.5, yc-cw/2-1.2, Z0-CH_D, xc+0.5, yc+cw/2+1.2, Z0+1)
gw = WALL_GRID/2 + GROOVE_CLR
for k in range(N+1):   # Nuten für die Rasterwände
    x = gx(k)
    cut += box(x-gw, g0-GROOVE_CLR, Z0-CH_D, x+gw, g1+GROOVE_CLR, Z0+1)
    cut += box(g0-GROOVE_CLR, x-gw, Z0-CH_D, g1+GROOVE_CLR, x+gw, Z0+1)
for x,y in corners:    # Ecken: M3 Senkkopf von hinten ins Raster
    cut += Manifold.cylinder(BASE_T+2, HOLE_CLR/2, HOLE_CLR/2, 32).translate((x,y,-1))
    cut += Manifold.cylinder(1.7, 3.2, HOLE_CLR/2, 32).translate((x,y,-0.01))
for x,y in NODES_REAR:   # M3 Senkkopf von hinten in die Schraubknoten des Rasters
    cut += Manifold.cylinder(BASE_T+2, HOLE_CLR/2, HOLE_CLR/2, 32).translate((x,y,-1))
    cut += Manifold.cylinder(1.7, 3.2, HOLE_CLR/2, 32).translate((x,y,-0.01))
# Kabeldurchführungen an jedem Streifenende (links + rechts je Zeile) im Kabelkanal
SLOT_W, SLOT_L = 5.0, 11.0
for yc in row_y:
    for xs in (WALL_OUT+0.5, PLATE-WALL_OUT-0.5-SLOT_W):
        cut += box(xs, yc-SLOT_L/2, -1, xs+SLOT_W, yc+SLOT_L/2, BASE_T+1)
boden -= cut

# --- Lichtraster (Assembly-Koordinaten: Wände stehen in den Nuten ab Z0-CH_D) ---
wb = Z0 - CH_D
raster = Manifold.extrude(sq - rect(WALL_OUT,WALL_OUT,PLATE-WALL_OUT,PLATE-WALL_OUT), H).translate((0,0,Z0))
walls = Manifold()
for k in range(N+1):
    x = gx(k)
    walls += box(x-WALL_GRID/2, g0, wb, x+WALL_GRID/2, g1, top)
    walls += box(g0, x-WALL_GRID/2, wb, g1, x+WALL_GRID/2, top)
notch = Manifold()
for k in range(N+1):   # Durchlass für Streifen (innen) bzw. Streifen + Kabel (außen)
    hh = NOTCH_H_OUT if k in (0, N) else NOTCH_H_IN
    for yc in row_y:
        notch += box(gx(k)-2, yc-(cw+0.4)/2, wb-0.1, gx(k)+2, yc+(cw+0.4)/2, Z0+hh)
raster += walls - notch
for x,y in corners:    # Eckpfosten: oben Front-Schraube, unten Boden-Schraube
    raster += Manifold.cylinder(H, POST_D/2, POST_D/2, 48).translate((x,y,Z0))
for x,y in NODES_REAR:   # Schraubknoten auf Rasterkreuzungen
    raster += Manifold.cylinder(H, NODE_D/2, NODE_D/2, 40).translate((x,y,Z0))
for x,y in corners:
    raster -= Manifold.cylinder(PILOT_DEPTH, HOLE_D_PILOT/2, HOLE_D_PILOT/2, 32).translate((x,y,top-PILOT_DEPTH))
    raster -= Manifold.cylinder(PILOT_DEPTH, HOLE_D_PILOT/2, HOLE_D_PILOT/2, 32).translate((x,y,Z0-0.01))
for x,y in NODES_REAR:
    raster -= Manifold.cylinder(PILOT_DEPTH, HOLE_D_PILOT/2, HOLE_D_PILOT/2, 32).translate((x,y,Z0-0.01))

# ---------- Rückseite des Bodens = offene Technikwanne ----------
# Assembly-Koordinaten: Rückseite des Bodens = z 0, Richtung Wand = negatives z.
RIM_H, RIM_W = 12.0, 2.4                     # umlaufender Rand = Wandabstand hinter dem Boden
rim = Manifold.extrude(sq - rect(RIM_W,RIM_W,PLATE-RIM_W,PLATE-RIM_W), RIM_H).translate((0,0,-RIM_H))
# Aufhängeklötze oben mit Schlüsselloch (Kopf <= 8,5 mm, Schaft <= 4,2 mm), Abstand der Wandschrauben = gx(6)-gx(2)
PAD_W, PAD_L = 24.0, 40.0
HANG = [gx(2), gx(6)]
for x in HANG:
    rim += box(x-PAD_W/2, PLATE-RIM_W-PAD_L, -RIM_H, x+PAD_W/2, PLATE-RIM_W+0.01, 0.01)
KH = [(x, PLATE-RIM_W-PAD_L+10) for x in HANG]
# Feather V2: 4 Dome für M2,5 (Lochabstand 45,72 x 17,78 = Feather-Standard, bitte nachmessen)
FW_HX, FW_HY = 45.72, 17.78
FW_C = (gx(4), gx(1))                        # Mitte der vier Löcher, USB-C zeigt nach rechts
USBB_HX = 15.24                              # USB-C-Breakout (Adafruit 4090, 20,4 x 14,2): 2 Löcher, bitte nachmessen
USBB_C = (gx(7)-12, gx(2)+4)
# Lichtsensor (Adafruit VEML7700 / BH1750, STEMMA QT, 25,4 x 17,8 mm; Lochabstand 20,32 x 12,7)
# oben mittig, Sensor zeigt zur Wand; Kerbe im oberen Rand lässt Raumlicht von oben herein
# 14.10.2026: Platine stand 1,8 mm über den Rand und lag auf der Kerbenkante (z = -5) auf ->
#   2 mm tiefer gesetzt (Oberkante 0,16 mm innerhalb der Außenkante) und Dome 6,5 mm hoch
#   (Platine 1,5 mm frei über der Kerbenkante) = Lage wie mit wordclock_jp_luxadapter.py
LUX_HX = 20.32
LUX_C = (PLATE/2, PLATE-RIM_W-11-2.0)        # Mitte der unteren Platinenlöcher
LUX_DOME_H = 6.5
DOME_H, DOME_D, DOME_PILOT = 3.0, 5.5, 2.1   # Bauteile max. 8 mm hoch -> 1 mm Luft zur Wand
domes = [(FW_C[0]+sx*FW_HX/2, FW_C[1]+sy*FW_HY/2, DOME_H) for sx in (-1,1) for sy in (-1,1)]
domes += [(USBB_C[0]+sx*USBB_HX/2, USBB_C[1], DOME_H) for sx in (-1,1)]
domes += [(LUX_C[0]+sx*LUX_HX/2, LUX_C[1], LUX_DOME_H) for sx in (-1,1)]
for x,y,dh in domes:
    rim += Manifold.cylinder(dh, DOME_D/2, DOME_D/2, 32).translate((x,y,-dh))
# Y-Kabel: Halterung für die USB-C-Buchse (Eingang) hinter einem Fenster im unteren Rand
SOCK_W, SOCK_T, SOCK_L = 14.0, 8.0, 26.0     # Gehäuse der Buchse, + 0,4 Spiel (Testdruck 30.09.: 12,5 zu eng)
SOCK_X = gx(6)-15
sw, st = SOCK_W+0.4, SOCK_T+0.4
cradle = box(SOCK_X-sw/2-2, RIM_W-0.01, -st-1.5, SOCK_X+sw/2+2, RIM_W+SOCK_L+2, 0.01)
cradle -= box(SOCK_X-sw/2, RIM_W-1, -st-2, SOCK_X+sw/2, RIM_W+SOCK_L, 1)         # Bett, zur Wand hin offen
cradle -= box(SOCK_X-4.5, RIM_W+SOCK_L-1, -st-2, SOCK_X+4.5, RIM_W+SOCK_L+3, 1)   # Kabelschlitz im Anschlag (9 mm)
rim += cradle
# Kabelbinder-Ösen entlang der Seiten und neben dem Feather
TIES = [(12, gx(k)) for k in (2,4,6)] + [(PLATE-12, gx(k)) for k in (2,4,6)] + [(FW_C[0], FW_C[1]+FW_HY/2+10)]
for x,y in TIES:
    rim += box(x-4, y-4, -4.0, x+4, y+4, 0.01)
boden += rim
for x,y in TIES:                 # Tunnel für Kabelbinder (bis 4 mm breit), quer
    boden -= box(x-5, y-2.3, -1.8, x+5, y+2.3, 0.01)
for x,y,dh in domes:
    boden -= Manifold.cylinder(dh+1.5, DOME_PILOT/2, DOME_PILOT/2, 24).translate((x,y,-dh-0.01))   # bis 1,5 mm in die Platte
boden -= box(SOCK_X-sw/2, -1, -st, SOCK_X+sw/2, RIM_W+1, 0.02)                    # Fenster im Rand
boden -= box(LUX_C[0]-14, PLATE-RIM_W-1, -RIM_H-1, LUX_C[0]+14, PLATE+1, -RIM_H+7)   # Lichtkerbe oben (7 mm tief)
for x,y in KH:
    zw = -RIM_H
    boden -= Manifold.cylinder(8.0, 4.5, 4.5, 40).translate((x,y,zw-0.01))           # Einführloch Ø9
    boden -= box(x-2.1, y, zw-0.01, x+2.1, y+10, zw+2.5)                            # Schlitz 4,2
    boden -= box(x-4.5, y, zw+2.5, x+4.5, y+10, zw+8.0)                             # Kopfkanal
    boden -= Manifold.cylinder(5.5, 4.5, 4.5, 40).translate((x,y+10,zw+2.5))
# Mausohren gegen Warping (0,4 mm, nach dem Druck abbrechen) - an der Frontseite = Druckbett
def ears(zbed, sign):
    m = Manifold()
    for x,y in [(1.5,1.5),(PLATE-1.5,1.5),(1.5,PLATE-1.5),(PLATE-1.5,PLATE-1.5)]:   # max. 298 mm breit
        m += Manifold.cylinder(0.4, 8, 8, 48).translate((x,y,zbed if sign>0 else zbed-0.4))
    for x,y in corners:   # Schraublöcher in den Ecken nicht mit dem Mausohr verschließen
        m -= Manifold.cylinder(2, HOLE_CLR/2, HOLE_CLR/2, 32).translate((x,y,zbed-1))
    return m
boden_print = (boden + ears(Z0, -1)).rotate((180,0,0)).translate((0,PLATE,BASE_T))   # Wanne nach oben
raster_print = (raster + ears(top, -1)).rotate((180,0,0)).translate((0,PLATE,top))

# ---------- Export ----------
def mesh(m):
    mm = m.to_mesh(); return np.array(mm.vert_properties)[:,:3], np.array(mm.tri_verts)
def write_3mf(path, name, m, color_change_z=None):
    v,t = mesh(m)
    vs = "\n".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a,b,c in v)
    ts = "\n".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in t)
    model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
<metadata name="Title">{name}</metadata>
<resources><object id="1" type="model" name="{name}"><mesh><vertices>
{vs}
</vertices><triangles>
{ts}
</triangles></mesh></object></resources>
<build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 {150-(v[:,0].min()+v[:,0].max())/2:.3f} {150-(v[:,1].min()+v[:,1].max())/2:.3f} 0"/></build>
</model>'''
    ct = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',ct); z.writestr('_rels/.rels',rels); z.writestr('3D/3dmodel.model',model)
        if color_change_z:
            z.writestr('Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml',
              f'<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_print_z>\n'
              f' <code print_z="{color_change_z}" type="0" extruder="1" color="#FFFFFF" extra="" gcode="M600"/>\n'
              f' <mode value="SingleExtruder"/>\n</custom_gcodes_per_print_z>\n')
def write_stl(path, m):
    import trimesh; v,t = mesh(m); trimesh.Trimesh(v,t).export(path)

for nm,m in [('front',front),('boden',boden_print),('raster',raster_print)]:
    print(nm, 'genus',m.genus(), 'vol cm3 %.1f'%(m.volume()/1000), 'bbox',[round(x,2) for x in m.bounding_box()], 'tris', m.num_tri())
write_3mf('wordclock_jp_front.3mf','Wordclock JP Front', front, color_change_z="1.8")   # M600 vor der letzten schwarzen Schicht: Spülreste landen unsichtbar im Füllmuster
write_3mf('wordclock_jp_boden.3mf','Wordclock JP Boden mit Technikwanne', boden_print)
write_3mf('wordclock_jp_raster.3mf','Wordclock JP Lichtraster', raster_print)
write_stl('wordclock_jp_front.stl', front); write_stl('wordclock_jp_boden.stl', boden_print); write_stl('wordclock_jp_raster.stl', raster_print)

