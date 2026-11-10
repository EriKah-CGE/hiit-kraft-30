# Baut die Figuren für HIIT Kraft 30 mit MPFB2 (MakeHuman) in Blender und exportiert models/<figur>.glb
#
# Aufruf (Blender 5.2 mit MPFB-Erweiterung):
#   blender -b --python tools/blender/build_models.py -- man            # Mann bauen und exportieren
#   blender -b --python tools/blender/build_models.py -- woman
#   blender -b --python tools/blender/build_models.py -- man --only splitsquat,pushup --preview out/
# Optionen:
#   --only a,b      nur diese Animationen (zum schnellen Prüfen; Export dann nach models/test-<figur>.glb)
#   --preview DIR   Standbilder der Umkehrpunkte aus Seite/Vorne/Hinten nach DIR rendern
#   Die .blend-Datei landet immer unter tools/blender/<figur>.blend (nicht im Repo), der Export läuft
#   danach in einem frischen Blender-Prozess über export_glb.py.
#   --noexport      kein GLB schreiben
#
# Farbkanal "mask" (Fläche für Fläche konstant): R = Muskelgruppe/20, G = Kleidung/10, B = Seite (1 links, 0 rechts, .5 Mitte)
# Muskelgruppen-IDs wie in exercises-anatomy.js (MUSCLES).
import bpy, bmesh, sys, os, math, importlib, json, addon_utils
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import poses
importlib.reload(poses)

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['man']
FIG = ARGS[0]
def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default

PARAMS = {
    'man':   dict(gender=1.0, age=0.5, muscle=0.80, weight=0.77, height=0.555, proportions=0.75),
    'woman': dict(gender=0.0, age=0.5, muscle=0.50, weight=0.65, height=0.55,  proportions=0.6, cupsize=0.5, firmness=0.6),
}

MUSCLE = dict(chest=1, delt_front=2, delt_side=3, triceps=4, biceps=5, upper_back=6, lats=7, lower_back=8,
              abs=9, obliques=10, glutes=11, quads=12, hamstrings=13, adductors=14, calves=15)
CLOTH = dict(skin=0, shorts=1, top=2, eye=3, hair=4)

# ---------------------------------------------------------------- Körper
def mpfb():
    addon_utils.enable('bl_ext.blender_org.mpfb', default_set=True)
    P = 'bl_ext.blender_org.mpfb.services.'
    return (importlib.import_module(P + 'humanservice').HumanService,
            importlib.import_module(P + 'targetservice').TargetService)

def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for c in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials):
        for x in list(c):
            c.remove(x)

def group_centroid(obj, name):
    gi = obj.vertex_groups[name].index
    pts = [v.co for v in obj.data.vertices if any(g.group == gi and g.weight > .5 for g in v.groups)]
    return sum(pts, Vector()) / len(pts) if pts else None

def build_body(fig):
    HS, TS = mpfb()
    d = TS.get_default_macro_info_dict()
    d.update(PARAMS[fig])
    body = HS.create_human(macro_detail_dict=d, scale=0.1, feet_on_ground=True)
    body.name = 'body_' + fig
    rig = HS.add_builtin_rig(body, 'game_engine', import_weights=True)
    rig.name = 'rig_' + fig
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    # Formziele (Shape Keys) fest einrechnen
    if body.data.shape_keys:
        bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    eyes = {s: group_centroid(body, 'joint-%s-eye' % s) for s in 'lr'}
    scalp_idx = body.vertex_groups['scalp'].index
    # Hilfsgeometrie (Kleidungs-Helfer, Gelenkwürfel) löschen
    drop = {body.vertex_groups[n].index for n in ('HelperGeometry', 'JointCubes')}
    bm = bmesh.new(); bm.from_mesh(body.data)
    dl = bm.verts.layers.deform.active
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if any(g in drop and w > .5 for g, w in v[dl].items())], context='VERTS')
    bm.to_mesh(body.data); bm.free()
    for m in list(body.modifiers):
        if m.type == 'MASK':
            body.modifiers.remove(m)
    # nur die Gruppen der Knochen behalten
    bones = {b.name for b in rig.data.bones}
    keep_extra = {'scalp'}
    for g in list(body.vertex_groups):
        if g.name not in bones and g.name not in keep_extra:
            body.vertex_groups.remove(g)
    # Augen: ruhige, geschlossene Kugeln (kein Augendetail)
    head_vg = body.vertex_groups['head']
    for s in 'lr':
        c = eyes[s]
        if c is None:
            continue
        add_sphere(body, c, 0.0128, head_vg, tag='eye')
    if fig == 'woman':
        # Haarknoten am Hinterkopf
        hc = head_center(body, rig)
        add_sphere(body, hc + Vector((0, 0.115, 0.035)), 0.045, head_vg, tag='hair', scale=(1, .85, .95))
    # Unterteilung (eine Stufe) vor dem Armature-Modifier anwenden, Gewichte werden mit interpoliert
    sub = body.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    bpy.ops.object.modifier_move_to_index(modifier='sub', index=0)
    bpy.ops.object.modifier_apply(modifier='sub')
    for p in body.data.polygons:
        p.use_smooth = True
    return body, rig

def head_center(body, rig):
    b = rig.data.bones['head']
    return (b.head_local + b.tail_local) / 2

def add_sphere(body, center, r, vg, tag, scale=(1, 1, 1)):
    me = bpy.data.meshes.new('tmp')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2])) + center
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new('tmp_' + tag, me)
    bpy.context.collection.objects.link(o)
    g = o.vertex_groups.new(name=vg.name)
    g.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    t = o.vertex_groups.new(name='tag_' + tag)
    t.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True); body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()

# ---------------------------------------------------------------- Muskel- und Kleidungsmaske
def classify(body, rig, fig):
    B = {b.name: b for b in rig.data.bones}
    H = lambda n: B[n].head_local
    T = lambda n: B[n].tail_local
    me = body.data
    vg_by_index = {g.index: g.name for g in body.vertex_groups}
    def dom_bone(vidx):
        best, bw = None, 0
        for v in vidx:
            for g in me.vertices[v].groups:
                n = vg_by_index.get(g.group)
                if n in B and g.weight > bw:
                    best, bw = n, g.weight
        return best
    def tagged(vidx, tag):
        n = 'tag_' + tag
        if n not in body.vertex_groups:
            return False
        gi = body.vertex_groups[n].index
        return all(any(g.group == gi for g in me.vertices[v].groups) for v in vidx)
    scalp = body.vertex_groups['scalp'].index if 'scalp' in body.vertex_groups else -1

    sh_z = H('upperarm_l').z           # Schultergelenk
    sh_x = H('upperarm_l').x
    clav_z = H('clavicle_l').z
    neck_z = H('neck_01').z
    hip_z = H('thigh_l').z             # Hüftgelenk
    pel_z = H('pelvis').z
    sp1_z = H('spine_01').z
    sp2_z = H('spine_02').z
    sp3_z = H('spine_03').z
    knee_z = H('calf_l').z
    ankle_z = H('foot_l').z
    sc = (H('head').z + 0.17) / 1.8 if False else (sh_z - ankle_z) / (1.435 - 0.078) if False else 1.0
    sc = (sh_z - H('foot_l').z) / 1.357
    chest_bot = sh_z - 0.185 * sc                      # Unterkante Brustmuskel
    rib_z = sp2_z + 0.02                               # unterer Rippenbogen (ungefähr)
    crest_z = hip_z + 0.085                            # Beckenkamm
    fold_z = hip_z - 0.10                              # Gesäßfalte
    torso_cy = {}                                      # Rumpfmitte (y) je Höhe für vorne/hinten

    out = []
    for p in me.polygons:
        c = p.center; n = p.normal
        x, y, z = c; ax = abs(x)
        side = 1.0 if x > 0.004 else (0.0 if x < -0.004 else 0.5)
        vid = list(p.vertices)
        g = 0; cl = CLOTH['skin']
        if tagged(vid, 'eye'):
            out.append((0, CLOTH['eye'], side)); continue
        if tagged(vid, 'hair'):
            out.append((0, CLOTH['hair'], side)); continue
        bone = dom_bone(vid)
        front = n.y < -0.25; back = n.y > 0.25
        if bone is None:
            out.append((0, 0, side)); continue
        b = bone
        if b.startswith(('upperarm', 'lowerarm')) or (b.startswith('clavicle') and ax > sh_x - 0.05):
            sgn = 1 if b.endswith('_l') else -1
            sh = H('upperarm' + b[-2:])
            el = H('lowerarm' + b[-2:])
            ua = (el - sh)
            t = (c - sh).dot(ua.normalized()) / ua.length
            lat = Vector((sgn, 0, 0))
            if b.startswith('lowerarm'):
                g = 0
            elif t < 0.38 and (c - sh).length < 0.16:
                # Deltamuskel: vorne / seitlich (hinten bleibt Haut)
                if n.y < -0.35:
                    g = MUSCLE['delt_front']
                elif n.y < 0.35 and (n.dot(lat) > 0.2 or n.z > 0.4):
                    g = MUSCLE['delt_side']
            elif 0.3 <= t <= 0.95 and b.startswith('upperarm'):
                if n.y < -0.1:
                    g = MUSCLE['biceps']
                elif n.y > 0.1:
                    g = MUSCLE['triceps']
        elif b.startswith(('thigh',)) or (b == 'pelvis' and z < hip_z - 0.02 and False):
            sgn = 1 if b.endswith('_l') else -1
            if z < fold_z + 0.03 and z > knee_z + 0.04:
                med = n.x * sgn < -0.3
                if back and n.y > 0.35:
                    g = MUSCLE['hamstrings']
                elif med and z > knee_z + 0.33 * (hip_z - knee_z) and n.y > -0.7:
                    g = MUSCLE['adductors']
                elif n.y < 0.2:
                    g = MUSCLE['quads']
            elif z >= fold_z + 0.03 and back:
                g = MUSCLE['glutes']
            elif z >= fold_z + 0.03 and n.y < 0.2 and n.x * sgn > 0.3 and z < hip_z:
                g = MUSCLE['quads']
        elif b.startswith('calf'):
            if back and z > ankle_z + 0.35 * (knee_z - ankle_z) and z < knee_z - 0.02:
                g = MUSCLE['calves']
        elif b in ('pelvis', 'spine_01', 'spine_02', 'spine_03') or b.startswith('clavicle'):
            if z < hip_z + 0.11 and z > fold_z - 0.02 and back and ax > 0.012:
                g = MUSCLE['glutes']
            elif front and z > chest_bot and z < clav_z + 0.005 and ax < sh_x - 0.025 and ax > 0.012:
                g = MUSCLE['chest']
            elif front and ax < 0.062 and z <= chest_bot and z > hip_z - 0.03:
                g = MUSCLE['abs']
            elif n.y < 0.3 and ax >= 0.062 and z <= chest_bot - 0.02 and z > crest_z - 0.02 and not back:
                g = MUSCLE['obliques']
            elif back or (n.y > -0.15 and abs(n.x) > 0.55 and z > chest_bot - 0.02):
                if back and ((z > sh_z - 0.12 * sc and ax < sh_x - 0.01) or (z > sh_z - 0.21 * sc and ax < 0.085 * sc)):
                    g = MUSCLE['upper_back']
                elif back and ax < 0.065 * sc and z > crest_z - 0.04 and z < rib_z + 0.05:
                    g = MUSCLE['lower_back']
                elif z > rib_z - 0.07 and z <= sh_z - 0.04 and ax >= 0.055 * sc:
                    g = MUSCLE['lats']
        elif b.startswith('neck'):
            if back and z < neck_z + 0.07 and ax < 0.09:
                g = MUSCLE['upper_back']
        # Kleidung
        if fig in ('man', 'woman'):
            thigh_end = hip_z - (0.40 if fig == 'man' else 0.30) * (hip_z - knee_z)
            if z < pel_z + 0.075 and z > thigh_end and (b in ('pelvis', 'spine_01') or b.startswith('thigh')):
                cl = CLOTH['shorts']
        if fig == 'woman':
            if z > chest_bot - 0.035 and z < sh_z - 0.035 and b in ('spine_02', 'spine_03') + ('clavicle_l', 'clavicle_r') and ax < sh_x - 0.035:
                cl = CLOTH['top']
        if scalp >= 0 and all(any(gg.group == scalp for gg in me.vertices[v].groups) for v in vid):
            cl = CLOTH['hair']
        out.append((g, cl, side))
    # Glätten: Einzelflächen an Gruppenrändern der Mehrheit der Nachbarn anpassen
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    # Mehrheitsfilter über Kanten- und Eckennachbarn (inkl. der Fläche selbst): füllt Löcher, nimmt Zacken weg
    nbrs = []
    for f in bm.faces:
        ns = set()
        for v in f.verts:
            for f2 in v.link_faces:
                if f2.index != f.index:
                    ns.add(f2.index)
        nbrs.append(list(ns))
    for it in range(6):
        new = list(out)
        for fi, ns in enumerate(nbrs):
            cnt = {out[fi][0]: 1.5}
            for j in ns:
                k = out[j][0]
                cnt[k] = cnt.get(k, 0) + 1
            k, c = max(cnt.items(), key=lambda kv: kv[1])
            if k != out[fi][0] and c > (len(ns) + 1.5) * 0.5:
                new[fi] = (k,) + out[fi][1:]
        out = new
    bm.free()
    attr = me.color_attributes.get('mask') or me.color_attributes.new('mask', 'FLOAT_COLOR', 'CORNER')
    for p in me.polygons:
        g, cl, side = out[p.index]
        col = (g / 20.0, cl / 10.0, side, 1.0)
        for li in p.loop_indices:
            attr.data[li].color = col
    # Vorschau-Farben (nur für die Kontroll-Renderings, wird vor dem Export entfernt)
    pal = {0: (.82, .62, .45), 1: (.9, .1, .1), 2: (1, .55, 0), 3: (1, .9, 0), 4: (.2, .8, .2), 5: (0, .6, .5), 6: (.1, .4, 1), 7: (.5, .2, .9),
           8: (.9, .2, .8), 9: (.55, .35, .1), 10: (.95, .6, .7), 11: (.1, .1, .5), 12: (.0, .9, .9), 13: (.4, .6, .0), 14: (1, 1, 1), 15: (.3, .3, .3)}
    cpal = {1: (.35, .25, .18), 2: (.45, .3, .2), 3: (.25, .2, .15), 4: (.2, .13, .08)}
    pv = me.color_attributes.get('preview') or me.color_attributes.new('preview', 'FLOAT_COLOR', 'CORNER')
    for p in me.polygons:
        g, cl, side = out[p.index]
        c = pal[g] if g else cpal.get(cl, pal[0])
        for li in p.loop_indices:
            pv.data[li].color = c + (1,)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find('mask')
    counts = {}
    for g, cl, s in out:
        counts[g] = counts.get(g, 0) + 1
    print('MASK faces per group', sorted(counts.items()))
    print('THRESH sh_z %.3f clav_z %.3f hip_z %.3f chest_bot %.3f rib_z %.3f crest %.3f fold %.3f sp2 %.3f sp3 %.3f' % (sh_z, clav_z, hip_z, chest_bot, rib_z, crest_z, fold_z, sp2_z, sp3_z))
    rng = {}
    for pi, (g, cl, sd) in enumerate(out):
        z = me.polygons[pi].center.z
        a, b = rng.get(g, (9, -9)); rng[g] = (min(a, z), max(b, z))
    print('ZRANGE', {k: (round(v[0], 3), round(v[1], 3)) for k, v in sorted(rng.items())})
    for g in list(body.vertex_groups):
        if g.name.startswith('tag_') or g.name == 'scalp':
            body.vertex_groups.remove(g)

# ---------------------------------------------------------------- Material (nur für Vorschau/Export-Basis)
def preview_material(body):
    mat = bpy.data.materials.new('skin')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.82, 0.58, 0.38, 1)
    bsdf.inputs['Roughness'].default_value = 1.0
    body.data.materials.clear(); body.data.materials.append(mat)

# ---------------------------------------------------------------- Hanteln
def dumbbells(rig, body, fig):
    ink = bpy.data.materials.new('dumbbell'); ink.use_nodes = True
    b = next(n for n in ink.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.042, 0.019, 0.010, 1); b.inputs['Roughness'].default_value = 1
    grip = bpy.data.materials.new('dumbbell_grip'); grip.use_nodes = True
    b = next(n for n in grip.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.20, 0.12, 0.07, 1); b.inputs['Roughness'].default_value = 1
    objs = {}
    for name in ('db_l', 'db_r', 'db_goblet', 'db_hip'):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        # Griff entlang lokaler X-Achse, Länge 0,14 m; Scheiben sechseckig
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.0165, radius2=0.0165, depth=0.15)
        for v in r['verts']:
            v.co = Vector((v.co.z, v.co.x, v.co.y))
        for f in bm.faces:
            f.material_index = 1
        for sx in (-1, 1):
            r = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.058, radius2=0.058, depth=0.065)
            for v in r['verts']:
                v.co = Vector((v.co.z + sx * 0.105, v.co.x, v.co.y))
        bm.to_mesh(me); bm.free()
        me.materials.append(ink); me.materials.append(grip)
        o = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(o)
        objs[name] = o
    return objs

def attach(obj, rig, bone, world_matrix):
    """Objekt an Knochen hängen, so dass es in der aktuellen Pose bei world_matrix liegt."""
    obj.parent = rig
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    pb = rig.pose.bones[bone]
    # Bone-Parent: Ursprung am Knochenende (tail)
    bone_world = rig.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = bone_world.inverted() @ world_matrix

# ---------------------------------------------------------------- Vorschau-Renderer
def setup_render(res=640):
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_WORKBENCH'
    except TypeError as e:
        print(e)
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'VERTEX'
    sc.display.shading.show_object_outline = True
    sc.display.shading.object_outline_color = (0.23, 0.15, 0.10)
    sc.render.resolution_x = res; sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new('w')
    cam = bpy.data.objects.get('pcam')
    if not cam:
        cam = bpy.data.objects.new('pcam', bpy.data.cameras.new('pcam'))
        bpy.context.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    sc.camera = cam
    return cam

def render_view(cam, target, view, path, size=2.3, col='VERTEX'):
    bpy.context.scene.display.shading.color_type = col
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.color_attributes.get('preview'):
            o.data.color_attributes.active_color = o.data.color_attributes['preview']
    dirs = {'side_r': Vector((-1, 0, 0)), 'side_l': Vector((1, 0, 0)), 'front': Vector((0, -1, 0)), 'back': Vector((0, 1, 0)),
            'top': Vector((0, -0.05, 1)), 'q': Vector((-0.7, -0.7, 0.35))}
    d = dirs[view].normalized()
    cam.location = target + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = size
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- Ablauf
def main():
    clear_scene()
    bpy.context.scene.render.fps = poses.FPS
    bpy.context.scene.render.fps_base = 1
    body, rig = build_body(FIG)
    classify(body, rig, FIG)
    preview_material(body)
    prev = arg('--preview')
    only = arg('--only')
    keys = only.split(',') if only else list(poses.EXERCISES.keys())
    solver = poses.Solver(rig, body)
    dbs = dumbbells(rig, body, FIG)
    solver.attach_dumbbells(dbs, attach)
    if prev:
        os.makedirs(prev, exist_ok=True)
        cam = setup_render(int(arg('--res', '560')))
        if '--rest' in ARGS:
            solver.show_dumbbells('none')
            for v in ('front', 'back', 'side_r', 'q'):
                render_view(cam, Vector((0, 0, 0.95)), v, os.path.join(prev, '%s_rest_%s.png' % (FIG, v)))
    acts = solver.bake_all(keys)
    if prev:
        for k in keys:
            solver.preview(k, cam, render_view, prev, FIG)
    # Zusatzdaten für figure.js
    rig['hiit'] = json.dumps(solver.meta(keys))
    # .blend speichern (Quelle für Export und für Änderungen von Hand), dann im frischen Prozess exportieren
    blend = os.path.join(HERE, ('test-' if only else '') + FIG + '.blend')
    solver.prepare_export()
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print('BLEND', blend)
    if '--noexport' not in ARGS:
        import subprocess
        out = os.path.join(REPO, 'models', ('test-' if only else '') + FIG + '.glb')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = subprocess.run([bpy.app.binary_path, '-b', blend, '--python', os.path.join(HERE, 'export_glb.py'), '--', out],
                           capture_output=True, text=True)
        print('\n'.join(l for l in r.stdout.splitlines() if l.startswith(('EXPORT', 'Exportoption', 'Error', 'Traceback'))))
        if r.returncode:
            print(r.stderr[-2000:])

main()
