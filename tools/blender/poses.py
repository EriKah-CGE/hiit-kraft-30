# Posen und Bewegungsschleifen für das MPFB-Rig "game_engine".
#
# Koordinaten (Blender, Ruhepose): X = linke Körperseite der Figur, -Y = vorne, Z = oben, Boden z = 0.
# Jede Übung beschreibt wenige Bewegungsparameter (z. B. Tiefe 0..1) als Schlüsselbilder; make(h) baut daraus
# die Zielwerte für den Solver (Becken, Wirbelsäule, IK-Ziele für Hände/Füße, Pole für Ellbogen/Knie).
# Gebacken wird jedes Einzelbild (FPS), damit Kontakte (Füße, Hände, Rücken) exakt halten.
import math, bpy
from mathutils import Vector, Matrix, Quaternion

FPS = 24
D = math.pi / 180

def V(x, y, z):
    return Vector((x, y, z))

def Rx(a): return Matrix.Rotation(a * D, 3, 'X')
def Ry(a): return Matrix.Rotation(a * D, 3, 'Y')
def Rz(a): return Matrix.Rotation(a * D, 3, 'Z')

def basis(d, f):
    d = d.normalized()
    f = (f - f.dot(d) * d)
    if f.length < 1e-6:
        f = Vector((0, 0, 1)) if abs(d.z) < .9 else Vector((0, -1, 0))
        f = (f - f.dot(d) * d)
    f.normalize()
    s = d.cross(f)
    return Matrix((d, f, s)).transposed()

def aim(dr, fr, dt, ft):
    return basis(dt, ft) @ basis(dr, fr).transposed()

def lerp(a, b, u):
    return a + (b - a) * u

def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)

def frame_from(up, front):
    """Rotation, die die Ruhe-Achsen (oben=+Z, vorne=-Y) auf up/front abbildet."""
    return aim(V(0, 0, 1), V(0, -1, 0), up, front)

SP = ('spine_01', 'spine_02', 'spine_03')
SPF = (0.3, 0.3, 0.4)
FINGERS = ('index', 'middle', 'ring', 'pinky')
GRIP_ANG = (72, 85, 55)
THUMB_ANG = (15, 35, 30)


class Body:
    """Körpermaße aus der Ruhepose."""
    def __init__(self, rig):
        bn = rig.data.bones
        self.h = {b.name: b.head_local.copy() for b in bn}
        self.t = {b.name: b.tail_local.copy() for b in bn}
        h = self.h
        self.T = (h['calf_l'] - h['thigh_l']).length
        self.S = (h['foot_l'] - h['calf_l']).length
        self.L = self.T + self.S
        self.UA = (h['lowerarm_l'] - h['upperarm_l']).length
        self.FA = (h['hand_l'] - h['lowerarm_l']).length
        self.ARM = self.UA + self.FA
        self.hipx = h['thigh_l'].x
        self.shx = h['upperarm_l'].x
        self.ankz = h['foot_l'].z
        self.ballz = h['ball_l'].z
        self.pel = h['pelvis'].copy()
        self.hipmid = (h['thigh_l'] + h['thigh_r']) / 2
        self.shmid = (h['upperarm_l'] + h['upperarm_r']) / 2
        self.dps = (self.shmid - self.hipmid).length
        self.height = max(v.z for v in self.t.values())
        self.footlen = (h['ball_l'] - h['foot_l']).length

    def stand_z(self, fx=None, bend=6):
        """Höhe der Hüftgelenk-Mitte im Stand bei leicht gebeugten Knien (bend Grad)."""
        fx = self.hipx * 0.9 if fx is None else fx
        k = math.radians(180 - bend)
        d = math.sqrt(self.T ** 2 + self.S ** 2 - 2 * self.T * self.S * math.cos(k))
        dx = abs(fx - self.hipx)
        return self.ankz + math.sqrt(max(0, d * d - dx * dx))


class Solver:
    def __init__(self, rig, body):
        self.rig = rig
        self.body = body
        self.B = Body(rig)
        bn = rig.data.bones
        self.bones = [b.name for b in bn]
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bn}
        self.Mrest = {b.name: b.matrix_local.copy() for b in bn}
        h, t = self.B.h, self.B.t
        self.h, self.t = h, t
        for pb in rig.pose.bones:
            pb.rotation_mode = 'QUATERNION'
        # Ruhe-Rahmen der Gliedmaßen
        self.rest = {}
        fwd = V(0, -1, 0)
        for s in 'lr':
            sg = 1 if s == 'l' else -1
            th, ca, fo, ba = 'thigh_' + s, 'calf_' + s, 'foot_' + s, 'ball_' + s
            self.rest[th] = (t[th] - h[th], fwd)
            self.rest[ca] = (t[ca] - h[ca], fwd)
            ua, la, ha = 'upperarm_' + s, 'lowerarm_' + s, 'hand_' + s
            du = (h[la] - h[ua]).normalized(); df = (h[ha] - h[la]).normalized()
            bic = df - df.dot(du) * du
            self.rest[ua] = (du, bic)
            # Handfläche: Normale aus Handrichtung und Querachse (Zeigefinger -> kleiner Finger)
            hd = (h['middle_01_' + s] - h[ha]).normalized()
            ac = (h['index_01_' + s] - h['pinky_01_' + s]).normalized()
            n = hd.cross(ac) if s == 'l' else ac.cross(hd)
            self.rest['palm_' + s] = n.normalized()
            self.rest['handdir_' + s] = hd
            self.rest['across_' + s] = ac
            self.rest[la] = (df, n)
            knuck = sum((h[f + '_01_' + s] for f in FINGERS), Vector()) / 4
            self.rest['gripc_' + s] = knuck + n * 0.03 - hd * 0.012
            self.rest['gripoff_' + s] = self.rest['gripc_' + s] - h[ha]
        self.prevq = {}

    # ------------------------------------------------------------ Lösen
    def solve(self, P):
        B, h, t = self.B, self.h, self.t
        Dm = {}; pos = {}
        # Becken
        if 'pframe' in P:
            up, fr = P['pframe']
            Dp = frame_from(V(*up), V(*fr))
        else:
            pi, ro, ya = P.get('prot', (0, 0, 0))
            Dp = Rz(ya) @ Ry(ro) @ Rx(pi)
        Dm['pelvis'] = Dp
        mode, tgt = P.get('pos', ('hipmid', B.hipmid))
        self._dz = P.get('dz', 0)
        tgt = Vector(tgt) + V(0, 0, self._dz)
        ref = {'pel': h['pelvis'], 'hipmid': B.hipmid, 'hip_l': h['thigh_l'], 'hip_r': h['thigh_r'], 'shmid': B.shmid}[mode]
        pos['pelvis'] = tgt - Dp @ (ref - h['pelvis'])
        def child(b, Dparent):
            p = self.parent[b]
            pos[b] = pos[p] + Dparent @ (h[b] - h[p])
        # Wirbelsäule
        f, l, tw = P.get('spine', (0, 0, 0))
        Dc = Dp
        for b, k in zip(SP, SPF):
            child(b, Dm[self.parent[b]])
            Dc = Dc @ Rz(tw * k) @ Ry(l * k) @ Rx(f * k)
            Dm[b] = Dc
        Dt = Dm['spine_03']
        f, l, tw = P.get('neck', (0, 0, 0))
        child('neck_01', Dt); Dm['neck_01'] = Dt @ Rz(tw * .6) @ Ry(l * .6) @ Rx(f * .6)
        child('head', Dm['neck_01']); Dm['head'] = Dm['neck_01'] @ Rz(tw * .4) @ Ry(l * .4) @ Rx(f * .4)
        # Beine
        for s in 'lr':
            self._leg(P, s, Dm, pos)
        # Anker: ganze Figur so verschieben, dass ein Kontaktpunkt auf der vorgegebenen Höhe liegt
        if P.get('anchor'):
            what, z = P['anchor']
            if what == 'balls':
                cur = min(pos['ball_l'].z, pos['ball_r'].z)
            elif what == 'knees':
                cur = min(pos['calf_l'].z, pos['calf_r'].z)
            else:
                cur = pos[what].z
            dz = z + getattr(self, '_dz', 0) - cur
            for k in pos:
                pos[k] = pos[k] + V(0, 0, dz)
            self._leg_targets_shift = dz
        # Schlüsselbeine, Arme
        for s in 'lr':
            sg = 1 if s == 'l' else -1
            el, pr = P.get('clav_' + s, (0, 0))
            child('clavicle_' + s, Dt)
            Dm['clavicle_' + s] = Dt @ Ry(-el * sg) @ Rz(-pr * sg)
            self._arm(P, s, Dm, pos)
        return Dm, pos

    def _frame(self, fr, Dm):
        return {'w': Matrix.Identity(3), 't': Dm['spine_03'], 'p': Dm['pelvis']}[fr]

    def _ik(self, root, tgt, a, b, pole):
        v = tgt - root
        d = v.length
        d = max(abs(a - b) + 1e-4, min(a + b - 1e-4, d))
        vn = v.normalized()
        ca = (a * a + d * d - b * b) / (2 * a * d)
        sa = math.sqrt(max(0, 1 - ca * ca))
        p = pole - pole.dot(vn) * vn
        if p.length < 1e-6:
            p = V(0, -1, 0) - V(0, -1, 0).dot(vn) * vn
        p.normalize()
        mid = root + a * (ca * vn + sa * p)
        end = root + vn * d
        return mid, end, p

    def _leg(self, P, s, Dm, pos):
        B, h, t = self.B, self.h, self.t
        sg = 1 if s == 'l' else -1
        th, ca, fo, ba = 'thigh_' + s, 'calf_' + s, 'foot_' + s, 'ball_' + s
        L = P['leg_' + s]
        pos[th] = pos['pelvis'] + Dm['pelvis'] @ (h[th] - h['pelvis'])
        Dp = Dm['pelvis']
        if 'ankle' in L:
            tgt = Vector(L['ankle']) + V(0, 0, P.get('dz', 0))
        else:
            tgt = pos[th] + Dp @ Vector(L['ankle_p'])
        pole = Dp @ Vector(L.get('pole', (0.12 * sg, -1, 0)))
        knee, ank, p = self._ik(pos[th], tgt, B.T, B.S, pole)
        Dm[th] = aim(*self.rest[th], knee - pos[th], p)
        pos[ca] = knee
        Dm[ca] = aim(*self.rest[ca], ank - knee, p)
        pos[fo] = ank
        fm = L.get('foot', ('w', 0, 0, 0))
        if fm[0] == 'w':
            Df = Rz(fm[1] * sg) @ Rx(fm[2]) @ Ry(fm[3] * sg if len(fm) > 3 else 0)
        elif fm[0] == 'ball':
            # Ferse angehoben, Fußballen auf Bodenhöhe fm[2]
            yaw = fm[1]; zb = fm[2] if len(fm) > 2 else B.ballz
            vr = h[ba] - h[fo]
            best = None
            for i in range(0, 91):
                Df = Rz(yaw * sg) @ Rx(i)
                z = (ank + Df @ vr).z
                if best is None or abs(z - zb) < best[0]:
                    best = (abs(z - zb), Df)
            Df = best[1]
        else:  # 'rel': (dorsi, inversion) relativ zum Unterschenkel
            Df = Dm[ca] @ Rx(-fm[1])
        Dm[fo] = Df
        pos[ba] = ank + Df @ (h[ba] - h[fo])
        if L.get('toes', 'flat') == 'flat' and fm[0] != 'rel':
            yaw = fm[1]
            Dm[ba] = Rz(yaw * sg)
        else:
            Dm[ba] = Df

    def _target(self, spec, s, Dm, pos):
        mode, v = spec[0], Vector(spec[1])
        sh = pos['upperarm_' + s]
        if mode == 'w': return v + V(0, 0, getattr(self, '_dz', 0))
        if mode == 's': return sh + v
        if mode == 't': return sh + Dm['spine_03'] @ v
        if mode == 'p': return pos['pelvis'] + Dm['pelvis'] @ v
        if mode == 'c': return pos['spine_03'] + Dm['spine_03'] @ v   # Brustkorb-Rahmen ab spine_03
        if mode == 'at': return pos[spec[2]] + v
        raise ValueError(mode)

    def _arm(self, P, s, Dm, pos):
        B, h = self.B, self.h
        sg = 1 if s == 'l' else -1
        A = P['arm_' + s]
        cl, ua, la, ha = 'clavicle_' + s, 'upperarm_' + s, 'lowerarm_' + s, 'hand_' + s
        pos[ua] = pos[cl] + Dm[cl] @ (h[ua] - h[cl])
        pv, pf = A.get('pole', ((0.2 * sg, 1, 0), 't'))
        pole = self._frame(pf, Dm) @ Vector(pv)
        pmv, pmf = A.get('palm', ((-sg, 0, 0), 't'))
        palm = (self._frame(pmf, Dm) @ Vector(pmv)).normalized()
        hd = A.get('hand_dir')
        hdir = (self._frame(hd[1], Dm) @ Vector(hd[0])).normalized() if hd else None
        if 'grip_at' in A:
            G = self._target(A['grip_at'], s, Dm, pos)
            wr = G - self.rest['gripoff_' + s]
            for it in range(3):
                elb, wrist, p = self._ik(pos[ua], wr, B.UA, B.FA, pole)
                Dla = aim(*self.rest[la], wrist - elb, palm)
                Dh = aim(self.rest['handdir_' + s], self.rest['palm_' + s], hdir, palm) if hdir else Dla
                wr = G - Dh @ self.rest['gripoff_' + s]
        else:
            wr = self._target(A['wrist'], s, Dm, pos)
        elb, wrist, p = self._ik(pos[ua], wr, B.UA, B.FA, pole)
        Dm[ua] = aim(*self.rest[ua], elb - pos[ua], -p)
        pos[la] = elb
        Dm[la] = aim(*self.rest[la], wrist - elb, palm)
        pos[ha] = wrist
        Dm[ha] = aim(self.rest['handdir_' + s], self.rest['palm_' + s], hdir, palm) if hdir else Dm[la]
        # Finger
        g = A.get('grip', 0.15)
        n = self.rest['palm_' + s]
        for fn in FINGERS:
            par = ha
            for j in (1, 2, 3):
                b = '%s_0%d_%s' % (fn, j, s)
                d = (self.t[b] - self.h[b]).normalized()
                ax = d.cross(n).normalized()
                pos[b] = pos[par] + Dm[par] @ (self.h[b] - self.h[par])
                Dm[b] = Dm[par] @ Matrix.Rotation(g * GRIP_ANG[j - 1] * D, 3, ax)
                par = b
        par = ha
        for j in (1, 2, 3):
            b = 'thumb_0%d_%s' % (j, s)
            d = (self.t[b] - self.h[b]).normalized()
            ax = d.cross(n).normalized()
            pos[b] = pos[par] + Dm[par] @ (self.h[b] - self.h[par])
            Dm[b] = Dm[par] @ Matrix.Rotation(g * THUMB_ANG[j - 1] * D, 3, ax)
            par = b

    # ------------------------------------------------------------ Anwenden / Backen
    def matrices(self, Dm, pos):
        M = {}
        for b in self.bones:
            if b in Dm:
                d4 = Dm[b].to_4x4()
                M[b] = Matrix.Translation(pos[b]) @ d4 @ Matrix.Translation(-self.h[b]) @ self.Mrest[b]
            else:
                p = self.parent[b]
                if p is None:
                    M[b] = self.Mrest[b].copy()
                else:
                    M[b] = M[p] @ self.Mrest[p].inverted() @ self.Mrest[b]
        basis = {}
        for b in self.bones:
            p = self.parent[b]
            if p is None:
                basis[b] = Matrix.Identity(4)
            else:
                rel = self.Mrest[p].inverted() @ self.Mrest[b]
                basis[b] = rel.inverted() @ M[p].inverted() @ M[b]
        return basis

    def apply(self, P):
        Dm, pos = self.solve(P)
        basis = self.matrices(Dm, pos)
        for pb in self.rig.pose.bones:
            pb.matrix_basis = basis[pb.name]
        return basis, pos

    def eval_minz(self):
        import numpy as np
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.body.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        mw = np.array(self.body.matrix_world)
        z = co @ mw[2, :3] + mw[2, 3]
        mn = float(z.min())
        box = None
        if getattr(self, '_want_box', False):
            w = co @ mw[:3, :3].T + mw[:3, 3]
            box = (w.min(axis=0).tolist(), w.max(axis=0).tolist())
        ev.to_mesh_clear()
        return mn, box

    def probe(self, P):
        Dm, pos = self.solve(P)
        return pos

    def bisect(self, f, lo, hi, it=40):
        flo = f(lo)
        for _ in range(it):
            mid = (lo + hi) / 2
            fm = f(mid)
            if (fm > 0) == (flo > 0):
                lo, flo = mid, fm
            else:
                hi = mid
        return (lo + hi) / 2

    def sample(self, ex, tau):
        keys = ex['keys']
        total = sum(d for d, _ in keys[1:])
        tau = tau % total if tau < total else total
        acc = 0
        for i in range(1, len(keys)):
            d = keys[i][0]
            if tau <= acc + d or i == len(keys) - 1:
                u = 0 if d == 0 else min(1, max(0, (tau - acc) / d))
                a, b = keys[i - 1][1], keys[i][1]
                e = ease(u)
                return {k: lerp(a[k], b.get(k, a[k]), e) for k in a}
            acc += d
        return dict(keys[-1][1])

    def bake_all(self, names):
        """Alle Übungen backen. Während des Backens ist keine Aktion zugewiesen (die Pose kommt direkt aus
        matrix_basis). Danach landen alle Übungen hintereinander in EINER Aktion "all"; figure.js schneidet
        sie über meta.start/frames wieder in Einzel-Clips."""
        rig = self.rig
        rig.animation_data_create()
        rig.animation_data.action = None
        for t in list(rig.animation_data.nla_tracks):
            rig.animation_data.nla_tracks.remove(t)
        self.meta_ex = {}
        baked = []
        for name in names:
            ex = build(name, self.B, self)
            rows, meta = self.bake(name, ex)
            baked.append((name, rows, meta))
        # eine gemeinsame Zeitleiste, 4 Bilder Abstand
        start = 0
        allrows = {}
        for name, rows, meta in baked:
            meta['start'] = start
            self.meta_ex[name] = meta
            for b, lst in rows.items():
                allrows.setdefault(b, []).extend((start + f, q, loc) for f, q, loc in lst)
            start += meta['frames'] + 4
        act = bpy.data.actions.new('all')
        act.use_fake_user = True
        rig.animation_data.action = act
        try:
            if rig.animation_data.action_slot is None and len(act.slots):
                rig.animation_data.action_slot = act.slots[0]
        except AttributeError:
            pass
        moving = {b for b, lst in allrows.items() if b == 'pelvis' or any(r[2].length > 1e-5 for r in lst)}
        for b, rows in allrows.items():
            self._write(act, b, 'rotation_quaternion', 4, rows, lambda r, i: r[1][i])
            if b in moving:
                self._write(act, b, 'location', 3, rows, lambda r, i: r[2][i])
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = start
        self.act = act
        for pb in rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        return act

    def _write(self, act, b, prop, n, rows, get):
        rig = self.rig
        dp = 'pose.bones["%s"].%s' % (b, prop)
        for i in range(n):
            if hasattr(act, 'fcurve_ensure_for_datablock'):
                fc = act.fcurve_ensure_for_datablock(rig, dp, index=i, group_name=b)
            else:
                fc = act.fcurves.new(dp, index=i, action_group=b)
            fc.keyframe_points.add(len(rows))
            co = []
            for r in rows:
                co += [r[0], get(r, i)]
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [1] * len(rows))  # LINEAR
            fc.update()

    def bake(self, name, ex):
        keys = ex['keys']
        total = sum(d for d, _ in keys[1:])
        nfr = max(2, round(total * FPS))
        rows = {}
        self.prevq = {}
        lowest = []
        self._want_box = True
        boxes = []
        turn_t = sum(d for d, _ in keys[1:ex.get('turn', 1) + 1])
        sample_frames = set(round(i * nfr / 8) for i in range(8)) | {round(turn_t * FPS)}
        self.poses = getattr(self, 'poses', {})
        for f in range(nfr + 1):
            h = self.sample(ex, f / FPS)
            P = ex['make'](h)
            if ex.get('ground'):
                self.apply(P)
                mz, _ = self.eval_minz()
                P = dict(P); P['dz'] = P.get('dz', 0) - mz + ex.get('ground_gap', 0.0)
            basis, pos = self.apply(P)
            if f in (0, round(turn_t * FPS)):
                self.poses[(name, f)] = {b: m.copy() for b, m in basis.items()}
            if f in sample_frames:
                mz, box = self.eval_minz()
                lowest.append((f, round(mz, 4)))
                boxes.append(box)
            for b, m in basis.items():
                if self.parent[b] is None:
                    continue
                loc, q, sc = m.decompose()
                pq = self.prevq.get(b)
                if pq is not None and pq.dot(q) < 0:
                    q = -q
                self.prevq[b] = q
                rows.setdefault(b, []).append((f, q, loc))
        mins = [b[0] for b in boxes if b]; maxs = [b[1] for b in boxes if b]
        bmin = [min(m[i] for m in mins) for i in range(3)]
        bmax = [max(m[i] for m in maxs) for i in range(3)]
        meta = dict(dur=round(total, 3), frames=nfr, turn=round(turn_t, 3), db=ex.get('db', 'none'),
                    side=ex.get('side', 'r'), lying=bool(ex.get('lying')),
                    box=[bmin, bmax], minz=min(l[1] for l in lowest), clips=ex.get('clips'))
        print('BAKE %-14s %5.2fs %4d frames  minz %s' % (name, total, nfr, lowest))
        return rows, meta

    def set_action_frame(self, name, frame):
        bpy.context.scene.frame_set(self.meta_ex[name]['start'] + frame)

    def preview(self, name, cam, render_view, outdir, fig):
        import os
        m = self.meta_ex[name]
        f = round(m['turn'] * FPS)
        self.set_action_frame(name, f)
        self.show_dumbbells(m['db'])
        bmin, bmax = m['box']
        c = Vector(((bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2, (bmin[2] + bmax[2]) / 2))
        size = max(bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2]) * 1.15
        for v in ('side_' + m['side'], 'front', 'back'):
            render_view(cam, c, v, os.path.join(outdir, '%s_%s_%s.png' % (fig, name, v)), size)
        self.set_action_frame(name, 0)
        render_view(cam, c, 'side_' + m['side'], os.path.join(outdir, '%s_%s_start.png' % (fig, name)), size)

    # ------------------------------------------------------------ Hanteln
    def attach_dumbbells(self, dbs, attach):
        self.dbs = dbs
        for pb in self.rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        for s in 'lr':
            ac = self.rest['across_' + s]
            n = self.rest['palm_' + s]
            M = basis(ac, n).to_4x4()
            M.translation = self.rest['gripc_' + s]
            attach(dbs['db_' + s], self.rig, 'hand_' + s, M)
        # Goblet: senkrecht vor dem Brustbein, an spine_03
        C = self.h['spine_03'] + GOBLET_C(self.B)
        M = basis(V(0, 0, 1), V(0, -1, 0)).to_4x4(); M.translation = C
        attach(dbs['db_goblet'], self.rig, 'spine_03', M)
        C = self.h['pelvis'] + HIP_DB(self.B)
        M = basis(V(1, 0, 0), V(0, 0, 1)).to_4x4(); M.translation = C
        attach(dbs['db_hip'], self.rig, 'pelvis', M)

    def show_dumbbells(self, mode):
        vis = {'db_l': mode in ('both', 'l'), 'db_r': mode in ('both', 'r'), 'db_goblet': mode == 'goblet', 'db_hip': mode == 'hip'}
        for k, o in self.dbs.items():
            o.hide_render = not vis[k]
            o.hide_viewport = False

    def prepare_export(self):
        for o in self.dbs.values():
            o.hide_render = False; o.hide_viewport = False
        bpy.context.scene.frame_set(0)

    def meta(self, names):
        # in glTF-Koordinaten (Y oben, Z = -Blender-Y)
        def g(v): return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]
        out = {'height': round(self.B.height, 4), 'fps': FPS, 'exercises': {}}
        for n, m in self.meta_ex.items():
            bmin, bmax = m['box']
            a, b = g(bmin), g(bmax)
            box = [[min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]]
            out['exercises'][n] = dict(m, box=box)
        return out


# ====================================================================== Übungen
def GOBLET_C(B):
    # Hantelmitte relativ zu spine_03 (Ruhe-Rahmen): vor dem Brustbein
    return V(0, -0.215 * B.height / 1.8, 0.05 * B.height / 1.8)

def HIP_DB(B):
    return V(0, -0.175 * B.height / 1.8, -0.035 * B.height / 1.8)

def sg_(s): return 1 if s == 'l' else -1

def stand_leg(B, s, x=None, y=0.0, yaw=7, z=None):
    sg = sg_(s)
    x = B.hipx * 0.95 if x is None else x
    return {'ankle': (x * sg, y, B.ankz if z is None else z), 'pole': (0.15 * sg, -1, 0), 'foot': ('w', yaw, 0, 0)}

def hang_arm(B, s, fwd=0.02, out=0.035, grip=1.0, palm=None, palm_frame='t'):
    sg = sg_(s)
    return {'wrist': ('s', (out * sg, -fwd, -B.ARM * 0.985)), 'pole': ((0.25 * sg, 1, 0.1), 't'),
            'palm': (palm or (-sg, 0, 0), palm_frame), 'grip': grip}

def hang_arm_w(B, s, fwd=0.0, out=0.035, grip=1.0, palm=(0, 1, 0)):
    """Arm hängt senkrecht (Welt) unter der Schulter, z. B. beim Vorbeugen."""
    sg = sg_(s)
    return {'wrist': ('s', (out * sg, -fwd, -B.ARM * 0.97)), 'pole': ((0.3 * sg, 1, 0), 'w'),
            'palm': (palm, 'w'), 'grip': grip}

def arm_fk(B, s, flex, abd=0, elbow=0, grip=0.2, palm=None, ab_plane=False):
    """Arm über Winkel im Rumpfrahmen: flex nach vorn (0 = hängt), abd seitlich, elbow Beugung nach vorn/oben."""
    sg = sg_(s)
    u = Rx(-flex) @ Ry(-abd * sg) @ V(0, 0, -1)   # Rx(-flex): unten -> vorne
    u = Vector((u.x, u.y, u.z))
    # Unterarm: Beugung in der Ebene aus Oberarm und "vorne-oben"
    ref = Rx(-(flex + 90)) @ V(0, 0, -1)
    ref = ref - ref.dot(u) * u
    if ref.length < 1e-6:
        ref = V(0, -1, 0)
    ref.normalize()
    f = math.cos(elbow * D) * u + math.sin(elbow * D) * ref
    wr = u * B.UA + f * B.FA
    pole = -ref if elbow > 3 else V(0.3 * sg, 1, 0)
    return {'wrist': ('t', tuple(wr)), 'pole': (tuple(pole + V(0.25 * sg, 0, 0)), 't'),
            'palm': (palm or (-sg, 0, 0), 't'), 'grip': grip}

def leg_fk(B, s, flex, knee, abd=0, pole=None, foot=('rel', 0)):
    """Bein über Winkel im Beckenrahmen: flex Hüftbeugung (Oberschenkel nach vorn), knee Beugung."""
    sg = sg_(s)
    u = Rx(-flex) @ Ry(-abd * sg) @ V(0, 0, -1)
    k = Rx(-(flex - knee)) @ Ry(-abd * sg) @ V(0, 0, -1)
    an = u * B.T + k * B.S
    pl = pole or tuple(Rx(-flex) @ V(0, -1, 0) + V(0.12 * sg, 0, 0))
    return {'ankle_p': tuple(an), 'pole': pl, 'foot': foot, 'toes': 'follow'}

def mirror_h(h):
    return dict(h)

def body_stand(B, h, fx=None):
    return dict(pos=('hipmid', (0, h.get('hy', 0.0), B.stand_z(fx) - h.get('drop', 0))), prot=(h.get('pitch', 0), 0, 0),
                spine=(h.get('flex', 0), 0, 0), neck=(h.get('neck', 0), 0, 0))


EXERCISES = {}
def ex(fn):
    EXERCISES[fn.__name__[3:]] = fn
    return fn

def build(name, B, S):
    if name == 'probe':
        return EXERCISES['splitsquat'](B, S)
    return EXERCISES[name](B, S)

def K(*pairs):
    """Schlüsselbilder: K((dauer, dict), ...); das erste Bild schließt die Schleife am Ende."""
    keys = [(0, pairs[0][1])] + list(pairs[1:]) + [(pairs[0][0], pairs[0][1])]
    return keys


# ---------------------------------------------------------------- Stehende Übungen
def ball_pitch(B, ankz):
    """Fußneigung (Grad, 'w'-Modus), bei der der Fußballen bei Fußgelenkhöhe ankz auf dem Boden liegt."""
    vr = B.h['ball_l'] - B.h['foot_l']
    best = (9, 0)
    for i in range(0, 91):
        z = ankz + (Rx(i) @ vr).z
        if abs(z - B.ballz) < best[0]:
            best = (abs(z - B.ballz), i)
    return best[1]

def march(B, h, hip_flex, knee, foot_rel, on_ball, arm_amp, arm_elbow, hz_add, grip):
    """Laufen/Gehen auf der Stelle: u_l/u_r 0 (Fuß am Boden) .. 1 (Knie oben)."""
    sc = B.height / 1.8
    fx = B.hipx * 0.9
    hz = B.stand_z(fx, 4) + hz_add
    P = dict(pos=('hipmid', (0, 0.0, hz)), prot=(0, 0, 0), spine=(2, 0, 0), neck=(0, 0, 0))
    st_z = B.ankz + (0.035 * sc if on_ball else 0)
    st_pitch = ball_pitch(B, st_z) if on_ball else 0
    for s in 'lr':
        sg = sg_(s); o = 'r' if s == 'l' else 'l'
        u = h['u' + s]
        hip = V(B.hipx * sg, B.hipmid.y - B.h['pelvis'].y + B.h['thigh_l'].y * 0, hz)
        hip = V(B.h['thigh_' + s].x, B.h['thigh_' + s].y - B.hipmid.y, hz)
        fk = leg_fk(B, s, hip_flex * u, knee * u)
        a_up = hip + Vector(fk['ankle_p'])
        a_st = V(fx * sg, 0.0, st_z)
        an = lerp(a_st, a_up, u)
        # Unterschenkelneigung für die Fußneigung im Weltrahmen
        shin_pitch = (hip_flex - knee) * u
        pitch = lerp(st_pitch, -shin_pitch - foot_rel, u)
        P['leg_' + s] = {'ankle': tuple(an), 'pole': tuple(lerp(V(0.15 * sg, -1, 0), Vector(fk['pole']), u)),
                         'foot': ('w', 5, pitch, 0)}
        sw = h['u' + o] - h['u' + s]
        P['arm_' + s] = arm_fk(B, s, 8 + arm_amp * sw, 7, arm_elbow, grip=grip)
    return P

@ex
def ex_kniehebe(B, S):
    make = lambda h: march(B, h, 90, 95, 25, True, 42, 85, 0.035 * B.height / 1.8, 0.6)
    return dict(make=make, keys=K((0.14, {'ul': 1.0, 'ur': 0.0}), (0.26, {'ul': 0.0, 'ur': 0.0}), (0.14, {'ul': 0.0, 'ur': 1.0}), (0.26, {'ul': 0.0, 'ur': 0.0})), turn=0, side='r')

@ex
def ex_walk(B, S):
    make = lambda h: march(B, h, 32, 58, 8, False, 22, 28, -0.005, 0.3)
    return dict(make=make, keys=K((0.45, {'ul': 1.0, 'ur': 0.0}), (0.45, {'ul': 0.0, 'ur': 0.0}), (0.45, {'ul': 0.0, 'ur': 1.0}), (0.45, {'ul': 0.0, 'ur': 0.0})),
                turn=0, side='r')

def squat_body(B, d, fx, depth_hip_z, back, pitch, flex=0):
    # d: 0 Stand .. 1 unten
    z0 = B.stand_z(fx, 5)
    return dict(pos=('hipmid', (0, lerp(0.0, back, d), lerp(z0, depth_hip_z, d))), prot=(lerp(2, pitch, d), 0, 0),
                spine=(lerp(0, flex, d), 0, 0), neck=(lerp(0, -pitch * 0.45, d), 0, 0))

def squat_legs(B, P, fx, yaw, knee_out=0.35):
    for s in 'lr':
        sg = sg_(s)
        P['leg_' + s] = {'ankle': (fx * sg, 0.0, B.ankz), 'pole': (knee_out * sg, -1, 0), 'foot': ('w', yaw, 0, 0)}

@ex
def ex_sqa(B, S):
    fx = B.hipx * 1.35
    def make(h):
        d = h['d']
        P = squat_body(B, d, fx, 0.42 * B.height / 1.8, 0.20 * B.height / 1.8, 38, 6)
        squat_legs(B, P, fx, 15)
        for s in 'lr':
            P['arm_' + s] = arm_fk(B, s, h['arm'], 10, 8, grip=0.2, palm=(-sg_(s), 0, 0))
        return P
    # Arme: oben (180) -> beim Runtergehen nach vorn (90) -> beim Hochkommen Kreis nach hinten (über 270/360) zurück nach oben (540 = 180)
    k0 = {'d': 0.0, 'arm': 180.0}
    k1 = {'d': 1.0, 'arm': 90.0}
    k2 = {'d': 0.45, 'arm': 270.0}
    k3 = {'d': 0.0, 'arm': 540.0}
    keys = [(0, k0), (1.2, k1), (0.6, k2), (0.6, k3)]
    return dict(make=make, keys=keys, turn=1, side='r')

@ex
def ex_squatbw(B, S):
    fx = B.hipx * 1.35
    def make(h):
        d = h['d']
        P = squat_body(B, d, fx, 0.43 * B.height / 1.8, 0.21 * B.height / 1.8, 36, 4)
        squat_legs(B, P, fx, 14)
        for s in 'lr':
            P['arm_' + s] = arm_fk(B, s, lerp(12, 92, d), 8, lerp(10, 4, d), grip=0.25)
        return P
    return dict(make=make, keys=K((1.0, {'d': 0.0}), (1.0, {'d': 1.0})), turn=1, side='r')

@ex
def ex_goblet(B, S):
    fx = B.hipx * 1.45
    C = GOBLET_C(B)
    def make(h):
        d = h['d']
        P = squat_body(B, d, fx, 0.40 * B.height / 1.8, 0.17 * B.height / 1.8, 30, 2)
        squat_legs(B, P, fx, 20, 0.45)
        for s in 'lr':
            sg = sg_(s)
            # Hände umfassen die obere Scheibe von unten, Ellbogen zeigen nach unten
            P['arm_' + s] = {'grip_at': ('c', tuple(C + V(0.055 * sg, 0.015, 0.075))), 'pole': ((0.25 * sg, -0.1, -1), 't'),
                             'palm': ((-0.55 * sg, 0, 0.85), 't'), 'hand_dir': ((0.15 * sg, -0.45, 0.85), 't'), 'grip': 0.55}
        return P
    keys = [(0, {'d': 0.0}), (3.0, {'d': 1.0}), (0.4, {'d': 1.0}), (1.0, {'d': 0.0})]
    return dict(make=make, keys=keys, turn=1, db='goblet', side='r')

@ex
def ex_thruster(B, S):
    fx = B.hipx * 1.35
    def rack(s):
        sg = sg_(s)
        return {'wrist': ('t', (0.0 * sg, -0.11, 0.03)), 'pole': ((0.25 * sg, -0.7, -0.8), 't'), 'palm': ((-sg, 0, 0), 't'), 'grip': 1.0}
    def over(s):
        sg = sg_(s)
        return {'wrist': ('t', (-0.02 * sg, -0.03, B.ARM * 0.975)), 'pole': ((1.0 * sg, 0.2, -0.2), 't'), 'palm': ((-sg, 0, 0), 't'), 'grip': 1.0}
    def make(h):
        d, a = h['d'], h['a']
        P = squat_body(B, d, fx, 0.43 * B.height / 1.8, 0.17 * B.height / 1.8, 26, 0)
        squat_legs(B, P, fx, 14)
        for s in 'lr':
            r, o = rack(s), over(s)
            w = tuple(lerp(Vector(r['wrist'][1]), Vector(o['wrist'][1]), a))
            pl = tuple(lerp(Vector(r['pole'][0]), Vector(o['pole'][0]), a))
            P['arm_' + s] = dict(r, wrist=('t', w), pole=(pl, 't'))
            P['clav_' + s] = (12 * a, 0)
        return P
    keys = [(0, {'d': 1.0, 'a': 0.0}), (0.45, {'d': 0.15, 'a': 0.0}), (0.35, {'d': 0.0, 'a': 1.0}), (0.35, {'d': 0.0, 'a': 0.0}), (0.55, {'d': 1.0, 'a': 0.0})]
    return dict(make=make, keys=keys, turn=0, db='both', side='r')

@ex
def ex_press(B, S):
    def make(h):
        a = h['a']
        P = body_stand(B, {})
        for s in 'lr':
            sg = sg_(s)
            P['leg_' + s] = stand_leg(B, s, x=B.hipx * 1.0)
            low = Vector((0.13 * sg, -0.06, 0.04))   # Hanteln auf Schulterhöhe, leicht vor und außerhalb
            up = Vector((-0.015 * sg, -0.04, B.ARM * 0.975))
            pl = lerp(Vector((0.35 * sg, -0.3, -1)), Vector((1.0 * sg, 0.15, -0.25)), a)
            P['arm_' + s] = {'wrist': ('t', tuple(lerp(low, up, a))), 'pole': (tuple(pl), 't'),
                             'palm': ((0, -1, 0), 't'), 'grip': 1.0}
            P['clav_' + s] = (14 * a, 0)
        return P
    return dict(make=make, keys=K((1.0, {'a': 0.0}), (1.0, {'a': 1.0})), turn=1, db='both', side='r')

@ex
def ex_chest(B, S):
    def make(h):
        a = h['a']
        P = body_stand(B, {})
        P['spine'] = (-2 * a, 0, 0)
        for s in 'lr':
            sg = sg_(s)
            P['leg_' + s] = stand_leg(B, s, x=B.hipx * 1.0)
            # Hände hinter dem Rücken verschränkt, Arme gestreckt nach hinten-oben
            w = Vector((0.025 * sg, 0, 0)) + lerp(V(0, 0.20, 0.93), V(0, 0.40, 1.06), a) * (B.height / 1.8)
            P['arm_' + s] = {'wrist': ('w', tuple(w)), 'pole': ((0.6 * sg, 0.3, -0.4), 't'), 'palm': ((-sg, 0.3, 0), 't'), 'grip': 0.6}
            P['clav_' + s] = (-4 * a, -14 * a)
        return P
    return dict(make=make, keys=K((2.0, {'a': 0.0}), (2.0, {'a': 1.0})), turn=1, side='r')

def split_pose(B, d, front, back_y, front_y, lean=6, bottom_hz=None, top_hz=None, arms='hang', hy=None):
    """Schrittstellung: front ('l' oder 'r') vorne. d 0 oben .. 1 unten."""
    bk = 'r' if front == 'l' else 'l'
    sgf, sgb = sg_(front), sg_(bk)
    bottom_hz = bottom_hz if bottom_hz is not None else 0.11 * B.height / 1.8 + B.T
    hy = 0.0 if hy is None else hy
    hz = lerp(top_hz, bottom_hz, d)
    P = dict(pos=('hipmid', (0, hy, hz)), prot=(lerp(2, lean, d), 0, 0), spine=(0, 0, 0), neck=(-lean * .5 * d, 0, 0))
    P['leg_' + front] = {'ankle': (B.hipx * 0.95 * sgf, front_y, B.ankz), 'pole': (0.12 * sgf, -1, 0), 'foot': ('w', 6, 0, 0)}
    P['leg_' + bk] = {'ankle': (B.hipx * 0.95 * sgb, back_y, B.ankz + 0.055), 'pole': (0.05 * sgb, -1, 0.0), 'foot': ('ball', 4)}
    for s in 'lr':
        P['arm_' + s] = hang_arm(B, s, fwd=0.015, out=0.06)
    return P

@ex
def ex_splitsquat(B, S):
    sc = B.height / 1.8
    fy = -0.42 * sc; by = 0.46 * sc
    def make(h):
        return split_pose(B, h['d'], 'l', by, fy, 6, top_hz=0.86 * sc, bottom_hz=0.115 * sc + B.T * 0.97, hy=0.0)
    return dict(make=make, keys=K((1.2, {'d': 0.0}), (1.2, {'d': 1.0})), turn=1, db='both', side='r')

def lunge_make(B, sc, weights=True):
    def make(h):
        # h: dl = Ausfallschritt mit linkem Bein vorn (rechts zurück) 0..1, dr = umgekehrt, lift = Fuß in der Luft
        P = None
        for front, k in (('l', 'dl'), ('r', 'dr')):
            u = h[k]
            if u > 0.0005 or (front == 'l' and h['dr'] <= 0.0005):
                bk = 'r' if front == 'l' else 'l'
                sgf, sgb = sg_(front), sg_(bk)
                by = lerp(0.0, 0.90 * sc, u)
                hy = lerp(0.0, 0.43 * sc, u)
                hz = lerp(B.stand_z(B.hipx * 0.95, 4), 0.115 * sc + B.T * 0.97, ease(min(1, u * 1.05)))
                P = dict(pos=('hipmid', (0, hy, hz)), prot=(lerp(1, 7, u), 0, 0), spine=(0, 0, 0), neck=(-3 * u, 0, 0))
                P['leg_' + front] = {'ankle': (B.hipx * 0.95 * sgf, 0.0, B.ankz), 'pole': (0.12 * sgf, -1, 0), 'foot': ('w', 6, 0, 0)}
                lift = h['lift']
                bz = B.ankz + lerp(0, 0.055, min(1, u * 2.5)) + lift * 0.09 * sc
                bl = {'ankle': (B.hipx * 0.95 * sgb, by, bz), 'pole': (0.05 * sgb, -1, 0.0)}
                bl['foot'] = ('w', 4, u * ball_pitch(B, B.ankz + 0.055) + lift * 12 * (1 - u), 0)
                P['leg_' + bk] = bl
                break
        for s in 'lr':
            if weights:
                P['arm_' + s] = hang_arm(B, s, fwd=0.015, out=0.06)
            else:
                P['arm_' + s] = hands_on_hips(B, s)
        return P
    return make

def hands_on_hips(B, s):
    sg = sg_(s)
    sc = B.height / 1.8
    return {'wrist': ('p', (0.165 * sg * sc, -0.035 * sc, 0.085 * sc)), 'pole': ((1.0 * sg, 0.45, 0.0), 't'),
            'palm': ((-sg, 0.2, 0), 't'), 'hand_dir': ((0.1 * sg, -0.7, -0.6), 'p'), 'grip': 0.1}

def lunge_ex(B, S, weights):
    sc = B.height / 1.8
    st = {'dl': 0.0, 'dr': 0.0, 'lift': 0.0}
    keys = [(0, st),
            (0.35, {'dl': 0.45, 'dr': 0.0, 'lift': 1.0}), (0.55, {'dl': 1.0, 'dr': 0.0, 'lift': 0.0}),
            (0.45, {'dl': 0.45, 'dr': 0.0, 'lift': 1.0}), (0.35, {'dl': 0.0, 'dr': 0.0, 'lift': 0.0}),
            (0.35, {'dl': 0.0, 'dr': 0.45, 'lift': 1.0}), (0.55, {'dl': 0.0, 'dr': 1.0, 'lift': 0.0}),
            (0.45, {'dl': 0.0, 'dr': 0.45, 'lift': 1.0}), (0.35, st)]
    return dict(make=lunge_make(B, sc, weights), keys=keys, turn=2, db='both' if weights else 'none', side='r')

@ex
def ex_lunge(B, S):
    return lunge_ex(B, S, True)

@ex
def ex_lungebw(B, S):
    return lunge_ex(B, S, False)

def hinge(B, d, pitch, knee_back, hip_back, hz_top, hz_bot):
    return dict(pos=('hipmid', (0, lerp(0.0, hip_back, d), lerp(hz_top, hz_bot, d))), prot=(lerp(0, pitch, d), 0, 0),
                spine=(0, 0, 0), neck=(lerp(0, -12, d), 0, 0))

@ex
def ex_rdl(B, S):
    sc = B.height / 1.8
    def make(h):
        d = h['d']
        P = hinge(B, d, 70, 0, 0.23 * sc, B.stand_z(B.hipx * 0.95, 8), B.stand_z(B.hipx * 0.95, 20) - 0.035 * sc)
        P['spine'] = (lerp(0, -7, d), 0, 0); P['neck'] = (lerp(0, 6, d), 0, 0)
        for s in 'lr':
            P['leg_' + s] = stand_leg(B, s, x=B.hipx * 0.95, yaw=4)
            P['arm_' + s] = hang_arm_w(B, s, fwd=lerp(0.06, -0.02, d) * sc, out=0.0, palm=(0, 1, 0))
            P['arm_' + s]['pole'] = ((0.6 * sg_(s), 1, 0), 'w')
            P['clav_' + s] = (0, lerp(0, -10, d))
        return P
    return dict(make=make, keys=K((1.4, {'d': 0.0}), (1.4, {'d': 1.0})), turn=1, db='both', side='r')

@ex
def ex_row(B, S):
    sc = B.height / 1.8
    def make(h):
        a = h['a']
        P = hinge(B, 1.0, 66, 0, 0.20 * sc, 0, B.stand_z(B.hipx * 0.95, 24) - 0.03 * sc)
        P['spine'] = (-5, 0, 0); P['neck'] = (6, 0, 0)
        for s in 'lr':
            sg = sg_(s)
            P['leg_' + s] = stand_leg(B, s, x=B.hipx * 0.95, yaw=4)
            lowp = hang_arm_w(B, s, fwd=0.0, out=0.0, palm=(-sg, 0, 0))
            low = Vector(lowp['wrist'][1])
            # oben: Hände neben dem unteren Rippenbogen, Ellbogen hinten am Körper vorbei
            P['arm_' + s] = {'wrist': ('t', tuple(lerp(Vector((0.03 * sg, -0.20, -B.ARM * 0.9)), Vector((0.02 * sg, -0.02, -0.33 * sc)), a))) if False else ('s', None),
                             'pole': (tuple(lerp(Vector((0.3 * sg, 1, 0)), Vector((0.15 * sg, 1.0, -0.35)), a)), 't'),
                             'palm': ((-sg, 0, 0), 't'), 'grip': 1.0}
            P['_low_' + s] = low
            P['clav_' + s] = (0, lerp(6, -14, a))
        # Untere Position: senkrecht unter der Schulter (Welt); obere im Rumpfrahmen -> über Probe in Welt umrechnen
        pos = S.probe(dict(P, arm_l=hang_arm_w(B, 'l'), arm_r=hang_arm_w(B, 'r')))
        Dm, _ = S.solve(dict(P, arm_l=hang_arm_w(B, 'l'), arm_r=hang_arm_w(B, 'r')))
        for s in 'lr':
            sg = sg_(s)
            sh = pos['upperarm_' + s]
            lo = sh + V(0.0 * sg, 0.0, -B.ARM * 0.97)
            T3 = Dm['spine_03']
            el = sh + T3 @ (V(0.06 * sg, 0, 0) + (V(0, 0, -1) * math.cos(38 * D) + V(0, 1, 0) * math.sin(38 * D)) * B.UA)
            hi = el + V(0, 0, -B.FA * 0.97)
            P['arm_' + s]['wrist'] = ('w', tuple(lerp(lo, hi, a)))
            P['arm_' + s]['pole'] = (tuple(lerp(V(0.3 * sg, 1, 0), V(0.25 * sg, 1, 0.1), a)), 't')
            P.pop('_low_' + s)
        return P
    return dict(make=make, keys=K((1.0, {'a': 0.0}), (1.0, {'a': 1.0})), turn=1, db='both', side='r')

@ex
def ex_row1(B, S):
    sc = B.height / 1.8
    def make(h):
        a = h['a']
        P = dict(pos=('hipmid', (0, 0.06 * sc, 0.84 * sc)), prot=(48, 0, 0), spine=(-4, 0, 0), neck=(4, 0, 0))
        P['leg_l'] = {'ankle': (B.hipx * 1.0, -0.38 * sc, B.ankz), 'pole': (0.12, -1, 0), 'foot': ('w', 6, 0, 0)}
        P['leg_r'] = {'ankle': (-B.hipx * 1.0, 0.36 * sc, B.ankz), 'pole': (-0.1, -1, 0), 'foot': ('w', 8, 0, 0)}
        # linke Hand stützt sich auf dem vorderen Knie ab (Position aus der Probe)
        P['arm_l'] = {'wrist': ('w', (0, 0, 0)), 'pole': ((0.5, 1.0, 0), 't'), 'palm': ((0, 0, -1), 'w'),
                      'hand_dir': ((0.1, -1, -0.25), 'w'), 'grip': 0.3}
        P['arm_r'] = hang_arm_w(B, 'r', palm=(1, 0, 0))
        pos = S.probe(P)
        Dm, _ = S.solve(P)
        knee = pos['calf_l']
        P['arm_l']['wrist'] = ('w', tuple(knee + V(-0.005, 0.07 * sc, 0.085 * sc)))
        sh = pos['upperarm_r']
        lo = sh + V(0, -0.02, -B.ARM * 0.97)
        el = sh + Dm['spine_03'] @ (V(-0.06, 0, 0) + (V(0, 0, -1) * math.cos(40 * D) + V(0, 1, 0) * math.sin(40 * D)) * B.UA)
        hi = el + V(0, 0, -B.FA * 0.97)
        P['arm_r'] = {'wrist': ('w', tuple(lerp(lo, hi, a))), 'pole': (tuple(lerp(V(-0.3, 1, 0), V(-0.25, 1.0, 0.1), a)), 't'),
                      'palm': ((1, 0, 0), 't'), 'grip': 1.0}
        P['clav_r'] = (0, lerp(8, -14, a))
        return P
    return dict(make=make, keys=K((0.9, {'a': 0.0}), (0.9, {'a': 1.0})), turn=1, db='r', side='r')

@ex
def ex_slrdl(B, S):
    sc = B.height / 1.8
    def make(h):
        d = h['d']
        pitch = lerp(0, 80, d)
        # Standbein links (unter dem Hüftgelenk), freies Bein rechts in Verlängerung des Rumpfes
        P = dict(prot=(pitch, 0, 0), spine=(lerp(0, -6, d), 0, 0), neck=(lerp(0, 5, d), 0, 0))
        hz = lerp(B.stand_z(B.hipx * 0.6, 8), B.stand_z(B.hipx * 0.6, 22), d)
        P['pos'] = ('hip_l', (B.hipx * 0.95, lerp(0.0, 0.05 * sc, d), hz))
        P['leg_l'] = {'ankle': (B.hipx * 0.85, 0.0, B.ankz), 'pole': (0.12, -1, 0), 'foot': ('w', 4, 0, 0)}
        ext = lerp(-12, 0, d)   # oben leicht hinter dem Körper, unten in Linie
        P['leg_r'] = leg_fk(B, 'r', lerp(-6, 0, d), lerp(40, 3, d), foot=('rel', lerp(-30, 0, d)))
        for s in 'lr':
            P['arm_' + s] = hang_arm_w(B, s, fwd=lerp(0.04, -0.02, d) * sc, out=0.0, palm=(0, 1, 0))
            P['arm_' + s]['pole'] = ((0.6 * sg_(s), 1, 0), 'w')
        return P
    return dict(make=make, keys=K((1.4, {'d': 0.0}), (1.4, {'d': 1.0})), turn=1, db='both', side='l')

@ex
def ex_burpee(B, S):
    sc = B.height / 1.8
    pu = pushup_make(B, S, knees=False)
    top = pu({'d': 0.0}); low = pu({'d': 1.0})
    ptop = S.probe(top); plow = S.probe(low)
    stand_hz = B.stand_z(B.hipx * 0.95, 4)
    sq_hy, sq_hz, sq_pitch, sq_flex = 0.10 * sc, 0.42 * sc, 62, 25
    hm = lambda p: (p['thigh_l'] + p['thigh_r']) / 2
    pl_pitch_top = math.degrees(math.atan2(-top['pframe'][0][1], top['pframe'][0][2]))
    pl_pitch_low = math.degrees(math.atan2(-low['pframe'][0][1], low['pframe'][0][2]))
    fpitch = {s: ball_pitch(B, ptop['foot_' + s].z) for s in 'lr'}
    def make(h):
        q, fl, fr, dd = h['q'], h['fl'], h['fr'], h['d']
        fb = (fl + fr) / 2
        hp_pl = lerp(hm(ptop), hm(plow), dd)
        hy = lerp(lerp(0.0, sq_hy, q), hp_pl.y, fb)
        hz = lerp(lerp(stand_hz, sq_hz, q), hp_pl.z, fb)
        pitch = lerp(lerp(0, sq_pitch, q), lerp(pl_pitch_top, pl_pitch_low, dd), fb)
        P = dict(pos=('hipmid', (0, hy, hz)), prot=(pitch, 0, 0), spine=(lerp(sq_flex * q, 0, fb), 0, 0),
                 neck=(lerp(-15 * q, 0, fb), 0, 0))
        for s, f in (('l', fl), ('r', fr)):
            sg = sg_(s)
            a_st = V(B.hipx * 0.95 * sg, 0.0, B.ankz)
            a_pl = lerp(ptop['foot_' + s], plow['foot_' + s], dd)
            lift = math.sin(math.pi * f) * 0.09 * sc
            an = lerp(a_st, a_pl, f) + V(0, 0, lift)
            P['leg_' + s] = {'ankle': tuple(an), 'pole': (0.15 * sg, -1, 0), 'foot': ('w', lerp(6, 2, f), f * fpitch[s], 0)}
        for s in 'lr':
            sg = sg_(s)
            floor_w = Vector(top['arm_' + s]['wrist'][1])
            pole_top = Vector(top['arm_' + s]['pole'][0])
            if fb <= 0:
                probe = S.probe(dict(P, arm_l=hang_arm(B, 'l'), arm_r=hang_arm(B, 'r')))
                hang = probe['upperarm_' + s] + V(0.04 * sg, -0.02, -B.ARM * 0.985)
                e = ease(q)
                w = lerp(hang, floor_w, e)
            else:
                w = floor_w
                e = 1.0
            P['arm_' + s] = {'wrist': ('w', tuple(w)), 'pole': (tuple(lerp(V(0.25 * sg, 1, 0.1), pole_top, e)), 't'),
                             'palm': (tuple(lerp(V(-sg, 0, 0), V(0, 0, -1), e)), 'w'),
                             'hand_dir': (tuple(lerp(V(0, 0, -1), V(0.15 * sg, -1, 0), e)), 'w'), 'grip': lerp(0.2, -0.25, e)}
        return P
    st = {'q': 0.0, 'fl': 0.0, 'fr': 0.0, 'd': 0.0}
    sq = {'q': 1.0, 'fl': 0.0, 'fr': 0.0, 'd': 0.0}
    keys = [(0, st), (0.6, sq),
            (0.35, {'q': 1.0, 'fl': 1.0, 'fr': 0.0, 'd': 0.0}), (0.35, {'q': 1.0, 'fl': 1.0, 'fr': 1.0, 'd': 0.0}),
            (0.55, {'q': 1.0, 'fl': 1.0, 'fr': 1.0, 'd': 1.0}), (0.55, {'q': 1.0, 'fl': 1.0, 'fr': 1.0, 'd': 0.0}),
            (0.35, {'q': 1.0, 'fl': 1.0, 'fr': 0.0, 'd': 0.0}), (0.35, sq), (0.6, st)]
    return dict(make=make, keys=keys, turn=4, side='r', ground=True)

@ex
def ex_hipflex(B, S):
    sc = B.height / 1.8
    def make(h):
        a = h['a']
        kz = 0.065 * sc                        # Kniegelenk hinten knapp über der Matte
        hy = lerp(0.03, -0.09, a) * sc         # Becken schiebt nach vorn
        hz = kz + B.T * lerp(0.995, 0.975, a)
        P = dict(pos=('hipmid', (0, hy, hz)), prot=(lerp(0, -7, a), 0, 0), spine=(lerp(0, 4, a), 0, 0), neck=(0, 0, 0))
        # vorn links: Fuß aufgestellt, Knie ca. 90 Grad
        P['leg_l'] = {'ankle': (B.hipx * 0.95, -0.50 * sc, B.ankz), 'pole': (0.12, -1, 0.1), 'foot': ('w', 6, 0, 0)}
        # hinten rechts: Knie am Boden, Fußrücken auf der Matte
        P['leg_r'] = {'ankle': (-B.hipx * 0.95, 0.03 * sc + B.S * 0.995 * 1.0, 0.05 * sc), 'pole': (-0.05, -0.6, -1), 'foot': ('rel', -62)}
        for s in 'lr':
            P['arm_' + s] = hands_on_hips(B, s)
        # Knie hinten genau auf die Mattenhöhe bringen
        pos = S.probe(P)
        dz = kz - pos['calf_r'].z
        P['pos'] = ('hipmid', (0, hy, hz + dz))
        return P
    return dict(make=make, keys=K((2.0, {'a': 0.0}), (2.0, {'a': 1.0})), turn=1, side='r', ground=True)


# ---------------------------------------------------------------- Liegen und Stütz
def supine(B, alpha, spine_flex=0, shoulder_y=0.0, shoulder_z=None):
    """Rückenlage, Kopf Richtung +Y. alpha = Anhebung des Beckens (Grad), Drehpunkt Schultern."""
    sc = B.height / 1.8
    a = alpha * D
    up = V(0, math.cos(a), -math.sin(a))
    fr = V(0, math.sin(a), math.cos(a))
    shz = shoulder_z if shoulder_z is not None else 0.095 * sc
    S0 = V(0, shoulder_y, shz)
    hip = S0 - up * B.dps
    return dict(pframe=(tuple(up), tuple(fr)), pos=('hipmid', tuple(hip)), spine=(spine_flex, 0, 0), neck=(0, 0, 0))

def supine_arms_floor(B, P, s, sc):
    sg = sg_(s)
    hip = Vector(P['pos'][1])
    return {'wrist': ('w', (sg * (B.shx + 0.07 * sc), hip.y + 0.06 * sc, 0.04 * sc)), 'pole': ((0, 0, 1), 'w'),
            'palm': ((0, 0, -1), 'w'), 'hand_dir': ((0.05 * sg, -1, 0), 'w'), 'grip': 0.1}

def bridge_feet(B, sc, s, ankle_y):
    sg = sg_(s)
    return {'ankle': (B.hipx * 0.95 * sg, ankle_y, B.ankz), 'pole': (0.12 * sg, -1, 0.2), 'foot': ('w', 4, 0, 0)}

@ex
def ex_bridge2(B, S):
    sc = B.height / 1.8
    ay = -(1.07 * sc)   # Füße: Fersen ca. 30 cm vor dem Gesäß
    def make(h):
        al = h['al']
        P = supine(B, al, shoulder_z=0.095 * sc)
        for s in 'lr':
            P['leg_' + s] = bridge_feet(B, sc, s, ay)
            P['arm_' + s] = supine_arms_floor(B, P, s, sc)
            P['arm_' + s]['wrist'] = ('w', (sg_(s) * (B.shx + 0.08 * sc), -0.40 * sc, 0.04 * sc))
        return P
    keys = [(0, {'al': 0.0}), (1.0, {'al': 26.0}), (0.5, {'al': 26.0}), (1.0, {'al': 0.0})]
    return dict(make=make, keys=keys, turn=2, side='r', lying=True, ground=True,
                clips=['bridge2', 'catcow'])

@ex
def ex_catcow(B, S):
    sc = B.height / 1.8
    # Vierfüßlerstand: Hände unter den Schultern, Knie unter den Hüften; Rücken abwechselnd rund (Katze) und hohl (Kuh)
    def make(h):
        c = h['c']  # +1 Katze, -1 Kuh
        hz = 0.065 * sc + B.T
        P = dict(pframe=(tuple(V(0, -1, 0)), tuple(V(0, 0, -1))), pos=('hipmid', (0, 0.0, hz)))
        P['prot'] = (0, 0, 0)
        P['pframe'] = (tuple(Rx(-12 * c) @ V(0, -1, 0)), tuple(Rx(-12 * c) @ V(0, 0, -1)))
        P['spine'] = (28 * c, 0, 0)
        P['neck'] = (25 * c, 0, 0)
        for s in 'lr':
            sg = sg_(s)
            P['leg_' + s] = {'ankle_p': (0, B.S * 0.99, -B.T * 0.99), 'pole': (0.05 * sg, -1, 0), 'foot': ('rel', -55)}
            P['leg_' + s] = {'ankle': (B.hipx * 0.95 * sg, B.S * 0.99, 0.055 * sc), 'pole': (0.05 * sg, -1, 0.4), 'foot': ('rel', -55)}
        pos0 = S.probe(dict(P, spine=(0, 0, 0), neck=(0, 0, 0), arm_l=hang_arm(B, 'l'), arm_r=hang_arm(B, 'r'), pframe=(tuple(V(0, -1, 0)), tuple(V(0, 0, -1)))))
        for s in 'lr':
            sg = sg_(s)
            sh = pos0['upperarm_' + s]
            P['arm_' + s] = {'wrist': ('w', (sh.x, sh.y, 0.048 * sc)), 'pole': ((0.2 * sg, 0, -1), 'w'), 'palm': ((0, 0, -1), 'w'),
                             'hand_dir': ((0.1 * sg, -1, 0), 'w'), 'grip': -0.25}
        return P
    return dict(make=make, keys=K((1.6, {'c': 1.0}), (1.6, {'c': -1.0})), turn=0, side='r', lying=True, ground=True)

@ex
def ex_bridge2w(B, S):
    sc = B.height / 1.8
    ay = -(1.07 * sc)
    C = HIP_DB(B)
    def make(h):
        al = h['al']
        P = supine(B, al, shoulder_z=0.095 * sc)
        for s in 'lr':
            sg = sg_(s)
            P['leg_' + s] = bridge_feet(B, sc, s, ay)
            P['arm_' + s] = {'grip_at': ('p', tuple(C + V(0.045 * sg, 0.0, 0))), 'pole': ((0.8 * sg, 0.6, 0), 't'),
                             'palm': ((0, 1, 0), 'p'), 'hand_dir': ((-0.35 * sg, 0, -0.9), 'p'), 'grip': 1.0}
        return P
    keys = [(0, {'al': 0.0}), (1.0, {'al': 26.0}), (0.5, {'al': 26.0}), (1.0, {'al': 0.0})]
    return dict(make=make, keys=keys, turn=2, db='hip', side='r', lying=True, ground=True)

@ex
def ex_bridge1(B, S):
    sc = B.height / 1.8
    ay = -(0.98 * sc)
    C = HIP_DB(B)
    def make(h):
        al = h['al']
        P = supine(B, al, shoulder_z=0.095 * sc)
        P['leg_l'] = bridge_feet(B, sc, 'l', ay)
        P['leg_l']['ankle'] = (B.hipx * 0.6, ay, B.ankz)
        # freies Bein: Oberschenkel parallel zum Standbein, Knie gestreckt
        pos = S.probe(dict(P, leg_r=leg_fk(B, 'r', 40, 0), arm_l=hang_arm(B, 'l'), arm_r=hang_arm(B, 'r')))
        Dm, _ = S.solve(dict(P, leg_r=leg_fk(B, 'r', 40, 0), arm_l=hang_arm(B, 'l'), arm_r=hang_arm(B, 'r')))
        th = (pos['calf_l'] - pos['thigh_l']).normalized()
        th_p = Dm['pelvis'].transposed() @ th
        an = th_p * B.L * 0.995 + V(-0.03, 0, 0)
        P['leg_r'] = {'ankle_p': tuple(an), 'pole': tuple(Dm['pelvis'].transposed() @ V(0, 0, 1) * 0 + V(-0.1, -1, 0)), 'foot': ('rel', -10), 'toes': 'follow'}
        for s in 'lr':
            sg = sg_(s)
            P['arm_' + s] = {'grip_at': ('p', tuple(C + V(0.045 * sg, 0.0, 0))), 'pole': ((0.8 * sg, 0.6, 0), 't'),
                             'palm': ((0, 1, 0), 'p'), 'hand_dir': ((-0.35 * sg, 0, -0.9), 'p'), 'grip': 1.0}
        return P
    keys = [(0, {'al': 0.0}), (1.0, {'al': 24.0}), (0.5, {'al': 24.0}), (1.0, {'al': 0.0})]
    return dict(make=make, keys=keys, turn=2, db='hip', side='r', lying=True, ground=True)

@ex
def ex_floorpress(B, S):
    sc = B.height / 1.8
    ay = -(1.05 * sc)
    def make(h):
        a = h['a']
        P = supine(B, 0, shoulder_z=0.095 * sc)
        for s in 'lr':
            P['leg_' + s] = bridge_feet(B, sc, s, ay)
        pos = S.probe(dict(P, arm_l=hang_arm(B, 'l'), arm_r=hang_arm(B, 'r')))
        for s in 'lr':
            sg = sg_(s)
            sh = pos['upperarm_' + s]
            # unten: Oberarm 45 Grad vom Körper auf dem Boden, Unterarm senkrecht
            el = sh + V(sg * B.UA * math.sin(45 * D), -B.UA * math.cos(45 * D), 0)
            el.z = 0.045 * sc
            low = el + V(0, 0, B.FA * 0.98)
            up = sh + V(-0.03 * sg, -0.05 * sc, B.ARM * 0.97)
            P['arm_' + s] = {'wrist': ('w', tuple(lerp(low, up, a))), 'pole': (tuple(lerp(V(0.5 * sg, -0.7, -1), V(1 * sg, -0.5, -0.4), a)), 'w'),
                             'palm': (tuple(V(0.35 * -sg, -1, 0)), 'w'), 'grip': 1.0}
        return P
    return dict(make=make, keys=K((1.0, {'a': 1.0}), (1.0, {'a': 0.0})), turn=1, db='both', side='r', lying=True, ground=True)

def deadbug_make(B, S, arms=True):
    sc = B.height / 1.8
    def make(h):
        P = supine(B, 0, spine_flex=4, shoulder_z=0.095 * sc)
        P['prot'] = None
        for s in 'lr':
            sg = sg_(s)
            e = h['e' + s]   # Bein gestreckt 0..1
            hf = lerp(90, 18, e); kn = lerp(90, 2, e)
            P['leg_' + s] = leg_fk(B, s, hf, kn, foot=('rel', lerp(0, -10, e)))
            P['leg_' + s]['pole'] = tuple(Rx(-hf) @ V(0, -1, 0) + V(0.1 * sg, 0, 0))
        for s in 'lr':
            sg = sg_(s)
            o = 'r' if s == 'l' else 'l'
            if arms:
                e = h['e' + o]   # Gegenarm über den Kopf
                ang = lerp(90, 172, e)
                P['arm_' + s] = arm_fk(B, s, ang, 6, 0, grip=0.2, palm=(-sg, 0, 0))
                P['arm_' + s]['pole'] = ((1.0 * sg, 0, 0), 't')
            else:
                P['arm_' + s] = supine_arms_floor(B, P, s, sc)
        P.pop('prot')
        return P
    return make

@ex
def ex_deadbug(B, S):
    z = {'el': 0.0, 'er': 0.0}
    keys = K((1.2, z), (1.2, {'el': 1.0, 'er': 0.0}), (1.2, z), (1.2, {'el': 0.0, 'er': 1.0}))
    return dict(make=deadbug_make(B, S, True), keys=keys, turn=1, side='r', lying=True, ground=True)

@ex
def ex_deadbuglegs(B, S):
    z = {'el': 0.0, 'er': 0.0}
    keys = K((1.2, z), (1.2, {'el': 1.0, 'er': 0.0}), (1.2, z), (1.2, {'el': 0.0, 'er': 1.0}))
    return dict(make=deadbug_make(B, S, False), keys=keys, turn=1, side='r', lying=True, ground=True)

def pushup_make(B, S, knees=False):
    sc = B.height / 1.8
    wz = 0.048 * sc
    def body(theta):
        th = theta * D
        up = V(0, -math.cos(th), math.sin(th))
        fr = V(0, -math.sin(th), -math.cos(th))
        P = dict(pframe=(tuple(up), tuple(fr)), pos=('hipmid', (0, 0, 1.0)), spine=(0, 0, 0), neck=(0, 0, 0))
        for s in 'lr':
            sg = sg_(s)
            if knees:
                # Oberschenkel in Linie, Knie gebeugt, Unterschenkel zeigen nach oben
                P['leg_' + s] = leg_fk(B, s, 0, 95, abd=-1, foot=('rel', -30))
                P['leg_' + s]['ankle_p'] = tuple(Vector(P['leg_' + s]['ankle_p']) + V(-0.03 * sg, 0, 0))
            else:
                P['leg_' + s] = {'ankle_p': (-0.035 * sg, 0.0, -B.L * 0.997), 'pole': (0.05 * sg, -1, 0), 'foot': ('ball', 2), 'toes': 'flat'}
            P['arm_' + s] = hang_arm(B, s)
        P['anchor'] = ('knees', 0.055 * sc) if knees else ('balls', B.ballz + 0.004)
        return P
    def shz(P):
        pos = S.probe(P)
        return (pos['upperarm_l'].z + pos['upperarm_r'].z) / 2
    # Winkel für oben (Arme gestreckt) und unten (Brust knapp über dem Boden)
    top_z = wz + B.ARM * 0.985 + 0.01 * sc
    low_z = 0.19 * sc
    th_top = S.bisect(lambda t: shz(body(t)) - top_z, 0, 60)
    th_low = S.bisect(lambda t: shz(body(t)) - low_z, -5, 40)
    Ptop = body(th_top)
    ptop = S.probe(Ptop)
    hands = {s: V(sg_(s) * (B.shx + 0.045 * sc), ptop['upperarm_' + s].y + 0.01 * sc, wz) for s in 'lr'}
    def make(h):
        d = h['d']
        P = body(lerp(th_top, th_low, d))
        for s in 'lr':
            sg = sg_(s)
            P['arm_' + s] = {'wrist': ('w', tuple(hands[s])), 'pole': ((0.42 * sg, 0.3, -1.0), 't'),
                             'palm': ((0, 0, -1), 'w'), 'hand_dir': ((0.15 * sg, -1, 0), 'w'), 'grip': -0.25}
        return P
    return make

@ex
def ex_pushup(B, S):
    return dict(make=pushup_make(B, S, False), keys=K((1.0, {'d': 0.0}), (1.0, {'d': 1.0})), turn=1, side='r', lying=True, ground=True)

@ex
def ex_kneepushup(B, S):
    return dict(make=pushup_make(B, S, True), keys=K((1.0, {'d': 0.0}), (1.0, {'d': 1.0})), turn=1, side='r', lying=True, ground=True)

def sideplank_make(B, S, knees=False):
    sc = B.height / 1.8
    # rechte Seite unten, Kopf Richtung -Y, Bauch zeigt nach +X (Seitenansicht von links zeigt die Linie)
    def body(inc):
        a = inc * D
        up = V(0, -math.cos(a), math.sin(a))
        fr = V(1, 0, 0)
        P = dict(pframe=(tuple(up), tuple(fr)), pos=('hipmid', (0, 0, 0.5)), spine=(0, 0, 0), neck=(0, 3, 0))
        if knees:
            P['leg_r'] = leg_fk(B, 'r', -5, 90, abd=-4, foot=('rel', -20))
            P['leg_l'] = leg_fk(B, 'l', -5, 90, abd=4, foot=('rel', -20))
            P['leg_l']['ankle_p'] = tuple(Vector(P['leg_l']['ankle_p']) + V(-0.07, 0, 0))
            P['leg_r']['ankle_p'] = tuple(Vector(P['leg_r']['ankle_p']) + V(0.03, 0, 0))
            P['anchor'] = ('calf_r', 0.06 * sc)
        else:
            P['leg_r'] = {'ankle_p': (0.075, 0, -B.L * 0.997), 'pole': (-0.05, -1, 0), 'foot': ('rel', -15), 'toes': 'follow'}
            P['leg_l'] = {'ankle_p': (-0.04, 0, -B.L * 0.997), 'pole': (0.05, -1, 0), 'foot': ('rel', -15), 'toes': 'follow'}
            P['anchor'] = ('foot_r', 0.05 * sc)
        P['arm_l'] = hands_on_hips(B, 'l')
        P['arm_r'] = hang_arm(B, 'r')
        return P
    def shz(P):
        return S.probe(P)['upperarm_r'].z
    target = 0.06 * sc + B.UA * 0.99
    def make(h):
        inc0 = S.bisect(lambda t: shz(body(t)) - target, 0, 40)
        P = body(inc0 + h['lift'])
        pos = S.probe(P)
        sh = pos['upperarm_r']
        el = V(sh.x, sh.y, 0.06 * sc)
        P['arm_r'] = {'wrist': ('w', tuple(el + V(B.FA * 0.97, -0.02 * sc, 0))), 'pole': ((0, 0, -1), 'w'), 'palm': ((0, 0, -1), 'w'),
                      'hand_dir': ((1, -0.1, 0), 'w'), 'grip': 0.25}
        return P
    return make

@ex
def ex_sideplank(B, S):
    return dict(make=sideplank_make(B, S, False), keys=K((1.5, {'lift': 0.0}), (1.5, {'lift': 2.5})), turn=1, side='l', lying=True, ground=True)

@ex
def ex_sideplankknee(B, S):
    return dict(make=sideplank_make(B, S, True), keys=K((1.5, {'lift': 0.0}), (1.5, {'lift': 2.5})), turn=1, side='l', lying=True, ground=True)
