# Misst Posen am verformten Netz einer gebauten Figur (aus tools/blender/<figur>.blend).
# Aufruf: blender -b tools/blender/man.blend --python tools/blender/measure.py -- pushup,kneepushup,row,row1
#
# Je Übung in Startpose (Bild 0) und am Umkehrpunkt:
#   Brust      tiefster Punkt der vorderen Brustwand über dem Boden (m)
#   Becken/Oberschenkel/Knie  tiefster Punkt dieser Bereiche über dem Boden (m)
#   Rumpf      Winkel Hüftgelenkmitte -> 7. Halswirbel (Rückenmittellinie) zur Waagerechten (Grad)
#   BWS        Krümmung der Brustwirbelsäule auf der Rückenmittellinie: Winkel zwischen den Abschnitten
#              Th12 -> Th6 und Th6 -> C7 (Grad, + = rund)
#   HWS        Winkel zwischen Th6 -> C7 und C7 -> Hinterkopf (Grad, + = Kopf nach vorn-unten, - = Kopf überstreckt/nach vorn geschoben)
#              Bezug aufrechter Stand (walk, Mann): BWS +23, HWS -21 (Ruhehaltung des MakeHuman-Körpers)
#   Unterarm   Abweichung Ellbogen -> Handgelenk von der Senkrechten (Grad); Ellbogen = Gelenkwinkel (180 = gestreckt)
#   Abspreizen Winkel zwischen Oberarm und Rumpflängsachse (Grad)
#   Blick      Neigung der Kopf-Vorwärtsrichtung unter die Waagerechte und Auftreffpunkt auf dem Boden vor den Zehen
import bpy, sys, json, math
import numpy as np
from mathutils import Vector

keys = sys.argv[sys.argv.index('--') + 1].split(',') if '--' in sys.argv else ['pushup']
body = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('body_'))
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
meta = json.loads(rig['hiit'])['exercises']
FPS = 24
B = {b.name: b for b in rig.data.bones}
H = lambda n: np.array(B[n].head_local)
me0 = body.data
co0 = np.array([v.co for v in me0.vertices])
vg = {g.index: g.name for g in body.vertex_groups}
W = {}
for v in me0.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    W[v.index] = vg.get(best.group) if best else None
dom = np.array([W[i] or '' for i in range(len(co0))])
sh = H('upperarm_l'); hip = H('thigh_l'); knee = H('calf_l')
sp3 = H('spine_03'); sp2 = H('spine_02'); neck = H('neck_01'); headb = H('head')
x, y, z = co0[:, 0], co0[:, 1], co0[:, 2]
torso = np.isin(dom, ['spine_01', 'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r', 'pelvis'])
# vordere Brustwand: Rumpf, vor der Wirbelsäule, zwischen Achselhöhe und Rippenbogen
chest = torso & (np.abs(x) < 0.12) & (z > sh[2] - 0.24) & (z < sh[2] - 0.02) & (y < sp3[1] - 0.06)
pelvis = (dom == 'pelvis') | ((np.abs(z - hip[2]) < 0.10) & np.isin(dom, ['thigh_l', 'thigh_r', 'spine_01']))
thigh = np.isin(dom, ['thigh_l', 'thigh_r']) & (z > knee[2] + 0.08)
knees = (np.abs(z - knee[2]) < 0.06) & np.isin(dom, ['thigh_l', 'thigh_r', 'calf_l', 'calf_r'])
# Rückenmittellinie: hinterste Vertices nahe x = 0 auf bestimmten Ruhehöhen
def back_pt(zz, extra=0.0):
    m = (np.abs(x) < 0.012) & (np.abs(z - zz) < 0.012) & (y > sp3[1] - 0.05 + extra)
    idx = np.flatnonzero(m)
    return idx[np.argmax(y[idx])]
I_T12 = back_pt(sp2[2])
I_T6 = back_pt((sp2[2] + neck[2]) / 2 + 0.03)
I_C7 = back_pt(neck[2] + 0.01)
I_OCC = back_pt(headb[2] + 0.06, extra=-0.1)

# Augen: die zwei kleinen Kugeln am Kopf (Ruhepose), für die Blickrichtung
import bmesh
_bm = bmesh.new(); _bm.from_mesh(me0); _bm.verts.ensure_lookup_table()
_seen = set(); EYES = []
for _v in _bm.verts:
    if _v.index in _seen:
        continue
    _st = [_v]; _c = []; _seen.add(_v.index)
    while _st:
        _x = _st.pop(); _c.append(_x.index)
        for _e in _x.link_edges:
            _o = _e.other_vert(_x)
            if _o.index not in _seen:
                _seen.add(_o.index); _st.append(_o)
    if len(_c) < 2000 and co0[_c, 1].mean() < headb[1]:
        EYES += _c
_bm.free()
EYES = np.array(EYES)

def ang2(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    return math.degrees(math.acos(max(-1, min(1, float(a @ b)))))

def signed_bend(p0, p1, p2, side):
    """Winkel zwischen p0->p1 und p1->p2; Vorzeichen über die Querachse side (+ = Beugung nach vorn)."""
    a = p1 - p0; b = p2 - p1
    s = np.sign(np.cross(a, b) @ side) or 1.0
    return ang2(a, b) * s

def measure(k, frame):
    sc = bpy.context.scene
    sc.frame_set(meta[k]['start'] + frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    mw = np.array(body.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]
    ev.to_mesh_clear()
    P = lambda n: np.array(rig.matrix_world @ rig.pose.bones[n].head)
    hm = (P('thigh_l') + P('thigh_r')) / 2
    side = P('thigh_l') - P('thigh_r'); side /= np.linalg.norm(side)
    c7 = co[I_C7]; t6 = co[I_T6]; t12 = co[I_T12]; occ = co[I_OCC]
    v = c7 - hm
    # Blick: Kopf-Vorwärtsrichtung (Ruhe -Y) ab Augenmitte bis zum Boden, Abstand vor den Fußspitzen
    pb = rig.pose.bones['head']
    R = np.array((rig.matrix_world.to_3x3() @ pb.matrix.to_3x3() @ pb.bone.matrix_local.to_3x3().inverted()))
    look = R @ np.array([0, -1.0, 0]); eye = co[EYES].mean(0) if len(EYES) else P('head')
    toes = (P('ball_l') + P('ball_r')) / 2
    fwd = np.array([look[0], look[1], 0]); fwd /= np.linalg.norm(fwd) + 1e-9
    blick = float((eye + look * (-eye[2] / look[2]) - toes) @ fwd) if look[2] < -0.05 else float('nan')
    blickw = math.degrees(math.atan2(-look[2], math.hypot(look[0], look[1])))
    out = dict(blick=blick, blickw=blickw,
        brust=float(co[chest, 2].min()), becken=float(co[pelvis, 2].min()), oberschenkel=float(co[thigh, 2].min()),
        knie=float(co[knees, 2].min()), boden=float(co[:, 2].min()),
        rumpf=math.degrees(math.atan2(v[2], math.hypot(v[0], v[1]))),
        bws=signed_bend(t12, t6, c7, side), hws=signed_bend(t6, c7, occ, side))
    for s in 'lr':
        e = P('lowerarm_' + s); w = P('hand_' + s); u = P('upperarm_' + s)
        out['unterarm_' + s] = ang2(w - e, np.array([0, 0, -1.0]))
        out['ellbogen_' + s] = 180 - ang2(e - u, w - e)
        out['abspreizen_' + s] = ang2(e - u, hm - (P('upperarm_l') + P('upperarm_r')) / 2)
    return out

for k in keys:
    m = meta[k]
    for label, f in (('start', 0), ('umkehr', round(m['turn'] * FPS))):
        r = measure(k, f)
        print('MESS %-11s %-6s Brust %.3f  Becken %.3f  Oberschenkel %.3f  Knie %.3f  Boden %.4f | Rumpf %5.1f  BWS %5.1f  HWS %5.1f | '
              'Unterarm %4.1f/%4.1f  Ellbogen %5.1f/%5.1f  Abspreizen %4.1f/%4.1f | Blick %4.1f Grad abwärts, %.2f m vor den Zehen' % (
              k, label, r['brust'], r['becken'], r['oberschenkel'], r['knie'], r['boden'], r['rumpf'], r['bws'], r['hws'],
              r['unterarm_l'], r['unterarm_r'], r['ellbogen_l'], r['ellbogen_r'], r['abspreizen_l'], r['abspreizen_r'], r['blickw'], r['blick']))
