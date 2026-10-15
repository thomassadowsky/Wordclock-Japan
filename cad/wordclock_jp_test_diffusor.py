"""Diffusor-Test: drei Felder 日 nebeneinander mit unterschiedlich dickem Weiss.
Aufbau wie die Front: 1,8 mm schwarz mit ausgesparten Zeichen, darueber Weiss,
Sichtseite unten (gespiegelt), ein Farbwechsel M600 bei 2,0 mm fuer alle Felder.
Von vorne gesehen links -> rechts: 0,6 / 1,0 / 1,4 mm Weiss.
Markierung: 1 / 2 / 3 kleine Punkte unter dem Zeichen (leuchten mit)."""
import zipfile, numpy as np
from fontTools.ttLib import TTCollection
from fontTools.pens.basePen import BasePen
from manifold3d import CrossSection, Manifold, FillRule

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
P = 1000/30.0; CH = 24.0; T_BLACK = 1.8; MARGIN = 4.0
CHAR = "日"; WHITE = [0.6, 1.0, 1.4]; DOT_D = 1.4
W, Hh = len(WHITE)*P + 2*MARGIN, P + 2*MARGIN

ttc = TTCollection(FONT)
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

mx = lambda x: W - x          # Spiegelung (Sichtseite liegt auf dem Bett)
def glyph_cs(ch, cx, cy):
    g = gs[cmap[ord(ch)]]; pen = FlatPen(gs); g.draw(pen); s = CH/upm
    return CrossSection([np.array([(mx(cx-g.width*s/2+fx*s), cy-(880-500)*s+fy*s) for fx,fy in c])
                         for c in pen.contours], FillRule.NonZero)

cut = CrossSection()
for i in range(len(WHITE)):
    cx = MARGIN + (i+0.5)*P
    cut = cut + glyph_cs(CHAR, cx, Hh/2)
    for k in range(i+1):                                   # Markierungspunkte
        cut = cut + CrossSection.circle(DOT_D/2, 32).translate((mx(cx + (k-i/2)*3.0), MARGIN + 3.0))
test = Manifold.extrude(CrossSection.square((W, Hh)) - cut, T_BLACK)
for i, tw in enumerate(WHITE):                             # Weissbereiche je Feld
    x0 = 0 if i == 0 else MARGIN + i*P
    x1 = W if i == len(WHITE)-1 else MARGIN + (i+1)*P
    test += Manifold.cube((x1-x0, Hh, tw+0.02)).translate((mx(x1), 0, T_BLACK-0.02))
print('Maße %.1f x %.1f mm, Weiss' % (W, Hh), WHITE, 'genus', test.genus(), 'Vol %.1f cm3' % (test.volume()/1000))

mm = test.to_mesh(); v = np.array(mm.vert_properties)[:,:3]; t = np.array(mm.tri_verts)
name = 'Wordclock JP Diffusor-Test 0.6-1.0-1.4'
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
<build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 {150-W/2:.3f} {150-Hh/2:.3f} 0"/></build>
</model>'''
ct = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
with zipfile.ZipFile('wordclock_jp_test_diffusor.3mf','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml',ct); z.writestr('_rels/.rels',rels); z.writestr('3D/3dmodel.model',model)
    z.writestr('Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml',
      '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_print_z>\n'
      ' <code print_z="2" type="0" extruder="1" color="#FFFFFF" extra="" gcode="M600"/>\n'
      ' <mode value="SingleExtruder"/>\n</custom_gcodes_per_print_z>\n')
import trimesh; trimesh.Trimesh(v,t).export('wordclock_jp_test_diffusor.stl')
