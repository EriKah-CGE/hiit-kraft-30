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
# Maske: Textur mask_<figur> (siehe mask.py), R = Muskelgruppe/20, G = Kleidung/10, B = Seite (1 links, 0 rechts).
# Zusätzlich Farbattribut "mask" je Fläche (nur für die Beschriftungsanker).
# Muskelgruppen-IDs wie in exercises-anatomy.js (MUSCLES).
import bpy, bmesh, sys, os, math, importlib, json, addon_utils
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import poses, mask
importlib.reload(poses); importlib.reload(mask)

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
    # Kugeln ausdrücklich nur an den Kopf binden (beim Zusammenfügen landete ein Auge sonst auf einem Fingerknochen)
    head_vg = body.vertex_groups['head']
    tags = {body.vertex_groups[n].index for n in ('tag_eye', 'tag_hair') if n in body.vertex_groups}
    for v in body.data.vertices:
        gs = [g.group for g in v.groups]
        if any(g in tags for g in gs):
            for gi in gs:
                if gi not in tags and gi != head_vg.index:
                    body.vertex_groups[gi].remove([v.index])
            head_vg.add([v.index], 1.0, 'REPLACE')
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

# ---------------------------------------------------------------- Material (nur für Vorschau/Export-Basis)
def mask_material(body, fig):
    """Material mit der Maskentextur (wird als baseColorTexture exportiert; figure.js liest sie als Daten)."""
    mat = bpy.data.materials.new('skin')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 1.0
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images['mask_' + fig]
    tex.interpolation = 'Closest'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    body.data.materials.clear(); body.data.materials.append(mat)
    return tex

def show_mask_preview(body, fig, on):
    tex = next(n for n in body.data.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE')
    tex.image = bpy.data.images[('maskpreview_' if on else 'mask_') + fig]

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
    sc.display.shading.color_type = 'TEXTURE'
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

def render_view(cam, target, view, path, size=2.3, col='TEXTURE'):
    bpy.context.scene.display.shading.color_type = col
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
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    mask.bake(body, rig, FIG, os.path.join(HERE, 'out', FIG + '_mask.png'), os.path.join(HERE, 'out', FIG + '_maskpreview.png'),
              int(arg('--texres', '2048')))
    for g in list(body.vertex_groups):
        if g.name.startswith('tag_') or g.name == 'scalp':
            body.vertex_groups.remove(g)
    mask_material(body, FIG)
    prev = arg('--preview')
    only = arg('--only')
    keys = only.split(',') if only else list(poses.EXERCISES.keys())
    solver = poses.Solver(rig, body)
    dbs = dumbbells(rig, body, FIG)
    solver.attach_dumbbells(dbs, attach)
    if prev:
        os.makedirs(prev, exist_ok=True)
        show_mask_preview(body, FIG, True)
        cam = setup_render(int(arg('--res', '560')))
        if '--rest' in ARGS:
            solver.show_dumbbells('none')
            for v in ('front', 'back', 'side_r', 'q'):
                render_view(cam, Vector((0, 0, 0.95)), v, os.path.join(prev, '%s_rest_%s.png' % (FIG, v)))
            for v in ('front', 'back', 'side_r', 'side_l'):
                render_view(cam, Vector((0, 0, 1.25)), v, os.path.join(prev, '%s_zoomT_%s.png' % (FIG, v)), 0.95)
                render_view(cam, Vector((0, 0, 0.55)), v, os.path.join(prev, '%s_zoomL_%s.png' % (FIG, v)), 0.95)
    acts = solver.bake_all(keys)
    if prev:
        for k in keys:
            solver.preview(k, cam, render_view, prev, FIG)
    # Zusatzdaten für figure.js
    rig['hiit'] = json.dumps(solver.meta(keys))
    show_mask_preview(body, FIG, False)
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
