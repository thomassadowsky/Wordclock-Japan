# Adapter für den Lichtsensor (Adafruit VEML7700, STEMMA QT 25,4 x 17,8 mm)
# Problem: auf den beiden Domen (LUX_C in wordclock_jp_build.py) steht die Platine
# ~1,8 mm über den oberen Rand hinaus und liegt auf der Kante der Lichtkerbe (z = -5) auf.
# Lösung: Adapter sitzt auf den Domen (Stifte in die Dom-Pilotlöcher + Kleber),
# trägt die Platine SHIFT mm weiter unten und HUB mm höher (Richtung Wand),
# sodass die Platine frei über der Kerbenkante liegt.
#
# Koordinaten relativ zu LUX_C: x quer, y nach oben (Richtung Rand), z = 0 auf den Domköpfen, +z Richtung Wand.
import numpy as np, zipfile
from manifold3d import CrossSection, Manifold

LUX_HX = 20.32            # Lochabstand Platine quer (= Domabstand)
LUX_HY = 12.70            # Lochabstand Platine hoch
SHIFT = 2.0               # Platine so viel tiefer (weg vom Rand)
HUB = 3.5                 # Adapterdicke = Platine so viel näher zur Wand (Kerbenkante liegt bei 2,0)
DOME_D = 5.5
PIN_D, PIN_L = 1.8, 2.5   # Stifte in die Dom-Pilotlöcher (Ø 2,1, 4,5 tief)
SCREW_PILOT = 2.2         # M2,5 Blechschraube / selbstschneidend, 5 mm lang
BODY_W, BODY_Y0, BODY_Y1, R = 26.0, -5.2, 3.2, 1.5

def rrect(w, y0, y1, r):
    return CrossSection.square((w-2*r, y1-y0)).translate((-(w-2*r)/2, y0)) + \
           CrossSection.square((w, y1-y0-2*r)).translate((-w/2, y0+r)) + \
           sum([CrossSection.circle(r, 32).translate((sx*(w/2-r), yy)) for sx in (-1,1) for yy in (y0+r, y1-r)], CrossSection())

body = Manifold.extrude(rrect(BODY_W, BODY_Y0, BODY_Y1, R), HUB)
for sx in (-1, 1):
    x = sx*LUX_HX/2
    body += Manifold.cylinder(PIN_L, PIN_D/2, PIN_D/2*0.85, 24).rotate((180,0,0)).translate((x, 0, 0))   # Stift nach unten, leicht konisch
    body -= Manifold.cylinder(HUB+1, SCREW_PILOT/2, SCREW_PILOT/2, 24).translate((x, -SHIFT, -0.5))      # Platinenschraube (untere Löcher)
# Mulde zwischen den Stiften als Kleberreservoir/Kabelluft nicht nötig - Unterseite plan, damit sie satt auf den Domen liegt

# Druckorientierung: Platinen-Auflage aufs Bett, Stifte zeigen nach oben
adapter_print = body.rotate((180,0,0)).translate((0,0,HUB))

# ---------- Kontrolle gegen den gedruckten Boden (Assembly-Koordinaten, LUX_C = (142.5, 271.6), Domkopf z = -3) ----------
PLATE, RIM_W = 285.0, 2.4
Y_EDGE = 11.0 + RIM_W                 # Dommitte -> Außenkante = 13,4
board_top = -SHIFT - 2.54 + 17.78
print(f'Platinen-Oberkante: {board_top-Y_EDGE:+.2f} mm relativ zur Außenkante (vorher {-2.54+17.78-Y_EDGE:+.2f})')
print(f'Adapter-Oberkante y = {BODY_Y1} < Randinnenseite 11,0 -> frei')
print(f'Platine liegt {HUB-2.0:.1f} mm über der Kerbenkante; Bauteilseite endet ca. {3+HUB+1.6+2.95:.1f} mm hinter dem Boden (Wand bei 12,0)')

def mesh(m):
    mm = m.to_mesh(); return np.array(mm.vert_properties)[:,:3], np.array(mm.tri_verts)
def write_3mf(path, name, m):
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
def write_stl(path, m):
    import trimesh; v,t = mesh(m); trimesh.Trimesh(v,t).export(path)

m = adapter_print
print('adapter genus', m.genus(), 'vol mm3 %.0f' % m.volume(), 'bbox', [round(x,2) for x in m.bounding_box()])
write_3mf('wordclock_jp_luxadapter.3mf', 'Wordclock JP Lichtsensor-Adapter', m)
write_stl('wordclock_jp_luxadapter.stl', m)
