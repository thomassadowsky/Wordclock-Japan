"""Teststreifen der Frontplatte: einige Zeichen aus einer Rasterzeile.
Gleicher Aufbau wie die echte Front (1,8 mm schwarz mit ausgesparten Zeichen,
0,6 mm weiss, Sichtseite unten, Schrift gespiegelt, M600 bei 2,0 mm).
Aufruf: python3 wordclock_jp_testfront.py [ZEILE] [SPALTE_VON] [SPALTE_BIS]
        (1-basiert, Standard: Zeile 2, Spalten 2-4 = 日曜日)"""
import sys, zipfile, numpy as np
from fontTools.ttLib import TTCollection
from fontTools.pens.basePen import BasePen
from manifold3d import CrossSection, Manifold, FillRule

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
P = 1000/30.0; CH = 24.0; T_BLACK, T_WHITE = 1.8, 0.6; MARGIN = 4.0
G = ["今日は月火水木金","土日曜日の午前後","一二三四五六七八","九十一二時半二三",
     "四五十一二三四五","六七八九分ちょう","どですおはようご","ざいまやすみ！心"]
row = int(sys.argv[1]) if len(sys.argv) > 1 else 2
c0  = int(sys.argv[2]) if len(sys.argv) > 2 else 2
c1  = int(sys.argv[3]) if len(sys.argv) > 3 else 4
chars = G[row-1][c0-1:c1]
W, Hh = len(chars)*P + 2*MARGIN, P + 2*MARGIN

ttc = TTCollection(FONT)
font = next(f for f in ttc.fonts if 'JP' in f['name'].getDebugName(1))
gs = font.getGlyphSet(); cmap = font.getBestCmap(); upm = font['head'].unitsPerEm

class FlatPen(BasePen):   # identisch zu wordclock_jp_build.py
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

def glyph_cs(ch, cx, cy):
    g = gs[cmap[ord(ch)]]; pen = FlatPen(gs); g.draw(pen); s = CH/upm
    polys = []
    for c in pen.contours:
        polys.append(np.array([(W-(cx-g.width*s/2+fx*s), cy-(880-500)*s+fy*s) for fx,fy in c]))  # gespiegelt
    return CrossSection(polys, FillRule.NonZero)

glyphs = CrossSection()
for i,ch in enumerate(chars):
    glyphs = glyphs + glyph_cs(ch, MARGIN+(i+0.5)*P, Hh/2)
sq = CrossSection.square((W, Hh))
black = Manifold.extrude(sq - glyphs, T_BLACK)
white = Manifold.extrude(sq, T_WHITE+0.02).translate((0,0,T_BLACK-0.02))
test = black + white
print(chars, 'Maße %.1f x %.1f x %.1f mm' % (W, Hh, T_BLACK+T_WHITE), 'genus', test.genus(), 'Vol %.1f cm3' % (test.volume()/1000))

mm = test.to_mesh(); v = np.array(mm.vert_properties)[:,:3]; t = np.array(mm.tri_verts)
name = 'Wordclock JP Test %s' % chars
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
with zipfile.ZipFile('wordclock_jp_test_front.3mf','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml',ct); z.writestr('_rels/.rels',rels); z.writestr('3D/3dmodel.model',model)
    z.writestr('Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml',
      '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_print_z>\n'
      ' <code print_z="2" type="0" extruder="1" color="#FFFFFF" extra="" gcode="M600"/>\n'
      ' <mode value="SingleExtruder"/>\n</custom_gcodes_per_print_z>\n')
import trimesh; trimesh.Trimesh(v,t).export('wordclock_jp_test_front.stl')
