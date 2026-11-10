# Exportiert eine von build_models.py gespeicherte Figur als GLB (Draco), in einem frischen Blender-Prozess.
# Aufruf: blender -b tools/blender/man.blend --python tools/blender/export_glb.py -- models/man.glb
#
# Warum ein eigener Prozess: Direkt nach dem Backen in derselben Sitzung exportiert hat der glTF-Exporter
# (Blender 5.2) die Figur bei einzelnen Übungen versetzt ausgegeben; aus der gespeicherten Datei stimmt es.
import bpy, sys, os

out = sys.argv[sys.argv.index('--') + 1]
body = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('body_'))
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
dbs = [o for o in bpy.data.objects if o.name in ('db_l', 'db_r', 'db_goblet', 'db_hip')]
ca = body.data.color_attributes
if ca.get('preview'):
    ca.remove(ca['preview'])
ca.active_color = ca['mask']
for o in dbs:
    o.hide_render = False; o.hide_viewport = False
for o in bpy.data.objects:
    o.select_set(False)
for o in [body, rig] + dbs:
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.context.scene.frame_set(0)

kw = dict(filepath=os.path.abspath(out), export_format='GLB', use_selection=True,
          export_apply=False, export_yup=True,
          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
          export_draco_position_quantization=14, export_draco_normal_quantization=10,
          export_draco_texcoord_quantization=12, export_draco_color_quantization=10,
          export_draco_generic_quantization=12,
          export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_anim_single_armature=True,
          export_frame_range=False, export_force_sampling=True, export_optimize_animation_size=True,
          export_def_bones=True, export_extras=True, export_skins=True, export_morph=False,
          export_materials='EXPORT', export_texcoords=False, export_normals=True)
props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
for k in list(kw):
    if k not in props:
        print('Exportoption fehlt, übersprungen:', k); kw.pop(k)
for k, v in (('export_vertex_color', 'ACTIVE'), ('export_all_vertex_colors', False), ('export_active_vertex_color_when_no_material', True)):
    if k in props:
        kw[k] = v
bpy.ops.export_scene.gltf(**kw)
print('EXPORT', out, os.path.getsize(out) // 1024, 'KB')
