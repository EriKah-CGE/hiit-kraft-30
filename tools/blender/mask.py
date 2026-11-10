# Muskel- und Kleidungsmaske als Textur (statt Fläche für Fläche).
#
# Für jedes Texel der MakeHuman-UV-Abwicklung wird der Punkt auf der Körperoberfläche (Ruhepose) bestimmt
# und mit glatten Regeln in Gliedmaßen- bzw. Rumpfkoordinaten einer Muskelgruppe zugeordnet. Die Grenzen
# folgen dadurch Kurven statt Netzkanten. figure.js liest die Textur ohne Filterung und glättet die Kanten
# selbst (vier Texel, Farbe gemischt, nicht die Gruppen-ID).
#
# Kanäle: R = Muskelgruppe/20, G = Kleidung/10 (0 Haut, 1 Shorts, 2 Shirt, 3 Auge, 4 Haar), B = Seite (1 links = +X, 0 rechts)
import bpy, math
import numpy as np

MUSCLE = dict(chest=1, delt_front=2, delt_side=3, triceps=4, biceps=5, upper_back=6, lats=7, lower_back=8,
              abs=9, obliques=10, glutes=11, quads=12, hamstrings=13, adductors=14, calves=15)
CLOTH = dict(skin=0, shorts=1, top=2, eye=3, hair=4)

PAL = {0: (.82, .62, .45), 1: (.9, .1, .1), 2: (1, .55, 0), 3: (1, .9, 0), 4: (.2, .8, .2), 5: (0, .6, .5), 6: (.1, .4, 1), 7: (.5, .2, .9),
       8: (.9, .2, .8), 9: (.55, .35, .1), 10: (.95, .6, .7), 11: (.1, .1, .5), 12: (.0, .9, .9), 13: (.4, .6, .0), 14: (1, 1, 1), 15: (.3, .3, .3)}
CPAL = {1: (.35, .25, .18), 2: (.62, .5, .36), 3: (.25, .2, .15), 4: (.2, .13, .08)}


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def pwl(x, xs, ys):
    return np.interp(x, xs, ys)


def vertex_features(body, rig):
    me = body.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    nor = np.empty(n * 3, np.float32); me.vertices.foreach_get('normal', nor); nor = nor.reshape(-1, 3)
    names = {g.index: g.name for g in body.vertex_groups}
    keys = ['torso', 'clav_l', 'clav_r', 'arm_l', 'arm_r', 'thigh_l', 'thigh_r', 'calf_l', 'calf_r', 'foot', 'neck', 'head',
            'scalp', 'eye', 'hair']
    K = {k: i for i, k in enumerate(keys)}
    def key(nm):
        if nm in ('pelvis', 'spine_01', 'spine_02', 'spine_03'): return 'torso'
        if nm.startswith('clavicle'): return 'clav' + nm[-2:]
        if nm.startswith(('upperarm', 'lowerarm', 'hand', 'thumb', 'index', 'middle', 'ring', 'pinky')): return 'arm' + nm[-2:]
        if nm.startswith('thigh'): return 'thigh' + nm[-2:]
        if nm.startswith('calf'): return 'calf' + nm[-2:]
        if nm.startswith(('foot', 'ball')): return 'foot'
        if nm == 'neck_01': return 'neck'
        if nm == 'head': return 'head'
        if nm == 'scalp': return 'scalp'
        if nm == 'tag_eye': return 'eye'
        if nm == 'tag_hair': return 'hair'
        return None
    W = np.zeros((n, len(keys)), np.float32)
    gmap = {gi: K[key(nm)] for gi, nm in names.items() if key(nm)}
    for v in me.vertices:
        for g in v.groups:
            k = gmap.get(g.group)
            if k is not None:
                W[v.index, k] += g.weight
    return co, nor, W, K


def rasterize(me, res):
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tl = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', tl); tl = tl.reshape(-1, 3)
    tv = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('vertices', tv); tv = tv.reshape(-1, 3)
    uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    T = uv[tl] * res - 0.5          # Texelmitten liegen auf ganzen Zahlen
    idx_l, tri_l, bary_l = [], [], []
    eps = 1e-3
    for t in range(nt):
        p = T[t]
        x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
        if x1 - x0 > res // 4 or (x1 == x0 and y1 == y0):
            continue
        xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1, res - 1) + 1), np.arange(max(y0, 0), min(y1, res - 1) + 1))
        xs = xs.ravel(); ys = ys.ravel()
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -eps) & (l1 >= -eps) & (l2 >= -eps)
        if not m.any():
            continue
        idx_l.append(ys[m] * res + xs[m]); tri_l.append(np.full(m.sum(), t, np.int32))
        bary_l.append(np.stack([l0[m], l1[m], l2[m]], 1))
    idx = np.concatenate(idx_l); tri = np.concatenate(tri_l); bary = np.clip(np.concatenate(bary_l), 0, 1)
    bary /= bary.sum(1, keepdims=True)
    return idx, tri, bary, tv, tl, uv


def landmarks(rig):
    B = {b.name: b for b in rig.data.bones}
    H = lambda n: np.array(B[n].head_local)
    L = {}
    for s in 'lr':
        L['sh' + s] = H('upperarm_' + s); L['el' + s] = H('lowerarm_' + s); L['wr' + s] = H('hand_' + s)
        L['hip' + s] = H('thigh_' + s); L['knee' + s] = H('calf_' + s); L['ank' + s] = H('foot_' + s)
    L['neck'] = H('neck_01'); L['head'] = H('head'); L['clav'] = H('clavicle_l')
    L['pel'] = H('pelvis'); L['sp1'] = H('spine_01'); L['sp2'] = H('spine_02'); L['sp3'] = H('spine_03')
    return L


def limb(P, a, b, sgn):
    """t entlang a->b (0..1), phi um die Achse: 0 vorne (-Y), +90 außen, -90 innen, +-180 hinten; r Abstand zur Achse."""
    ax = b - a; L2 = ax @ ax
    t = ((P - a) @ ax) / L2
    rad = P - a - t[:, None] * ax
    axn = ax / math.sqrt(L2)
    f = np.array([0, -1, 0.]); f = f - (f @ axn) * axn; f /= np.linalg.norm(f)
    lat = np.cross(axn, f) * (1 if np.cross(axn, f)[0] * sgn > 0 else -1)
    phi = np.degrees(np.arctan2(rad @ lat, rad @ f))
    return t, phi, np.linalg.norm(rad, axis=1)


def classify(P, N, W, K, L, fig, torso_prof):
    n = len(P)
    g = np.zeros(n, np.int16); cl = np.zeros(n, np.int16)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; ax = np.abs(x)
    side = (x > 0).astype(np.float32)
    keys = ['torso', 'clav', 'arm', 'thigh', 'calf', 'foot', 'neck', 'head']
    Wg = np.stack([W[:, K['torso']], W[:, K['clav_l']] + W[:, K['clav_r']], W[:, K['arm_l']] + W[:, K['arm_r']],
                   W[:, K['thigh_l']] + W[:, K['thigh_r']], W[:, K['calf_l']] + W[:, K['calf_r']], W[:, K['foot']],
                   W[:, K['neck']], W[:, K['head']]], 1)
    reg = np.array(keys)[Wg.argmax(1)]
    sh_z = L['shl'][2]; sh_x = L['shl'][0]; clav_z = L['clav'][2]; neck_z = L['neck'][2]
    hip_z = L['hipl'][2]; hip_x = L['hipl'][0]; hip_y = L['hipl'][1]; pel_z = L['pel'][2]
    sp1_z, sp2_z, sp3_z = L['sp1'][2], L['sp2'][2], L['sp3'][2]
    knee_z = L['kneel'][2]; ank_z = L['ankl'][2]
    sc = (sh_z - ank_z) / 1.357
    # Rumpfquerschnitt: Mitte und halbe Tiefe je Höhe -> Winkel um den Rumpf (0 vorne, 90 seitlich, 180 hinten)
    zs, yc, hd, hw = torso_prof
    yc_ = np.interp(z, zs, yc); hd_ = np.interp(z, zs, hd); hw_ = np.interp(z, zs, hw)
    ang = np.degrees(np.arctan2(ax / hw_, -(y - yc_) / hd_))
    tor = np.isin(reg, ('torso', 'clav', 'neck'))
    # --- Arme (Deltamuskel, Bizeps, Trizeps)
    for s, sgn in (('l', 1), ('r', -1)):
        on = (x * sgn > 0)
        t, phi, r = limb(P, L['sh' + s], L['el' + s], sgn)
        near = on & (np.linalg.norm(P - L['sh' + s], axis=1) < 0.16 * sc)
        cand = on & ((reg == 'arm') | ((reg == 'clav') | (reg == 'torso')) & (ax > sh_x - 0.045 * sc))
        # Deltamuskel: Kappe über dem Gelenk, Spitze (Ansatz) außen bei t ~ .48
        tmax = 0.50 - 0.30 * np.clip(np.abs(phi - 85) / 150, 0, 1) ** 1.3
        delt = cand & near & (t > -0.6) & (t < tmax) & (phi > -80) & (phi < 205) & (r < 0.13 * sc)
        delt &= ~((t < 0.12) & (phi > -80) & (phi < 0) & (ax < sh_x - 0.02 * sc))   # nicht in den Brustmuskel
        front = delt & (phi < 62)
        lat_ = delt & (phi >= 62) & (phi < 150)
        g[front] = MUSCLE['delt_front']; g[lat_] = MUSCLE['delt_side']
        ua = on & (reg == 'arm') & ~delt & (t > 0.08)
        bic = ua & (phi > -85) & (phi < 45) & (t < 0.86 - 0.06 * np.clip(np.abs(phi + 20) / 65, 0, 1) ** 2)
        psi = (phi + 360) % 360 - 180      # 0 = hinten
        tri = ua & (np.abs(psi + 5) < 75) & (t < 0.93 - 0.12 * np.clip(np.abs(psi + 5) / 75, 0, 1) ** 2)
        g[bic] = MUSCLE['biceps']; g[tri] = MUSCLE['triceps']
        # Shirt: kurzer Ärmel
        sleeve = on & (reg == 'arm') & (t < 0.40 + 0.04 * np.cos(np.radians(phi)))
        cl[sleeve] = CLOTH['top']
    # --- Beine
    for s, sgn in (('l', 1), ('r', -1)):
        on = (x * sgn > 0)
        t, phi, r = limb(P, L['hip' + s], L['knee' + s], sgn)
        psi = (phi + 360) % 360 - 180
        th = on & (reg == 'thigh')
        qmed = -38 - 60 * smooth(0.50, 0.84, t)
        qlat = 118 - 10 * smooth(0.6, 0.9, t)
        qtop = 0.06 + 0.10 * smooth(40, 110, phi)
        qbot = 0.86 - 0.08 * (np.clip(phi, 0, 120) / 115) ** 2 + 0.06 * smooth(-20, -85, phi)
        quad = th & (phi > qmed) & (phi < qlat) & (t > qtop) & (t < qbot)
        hw_ = 58 - 18 * smooth(0.55, 0.9, t)
        ham = th & (np.abs(psi) < hw_) & (t > 0.13 + 0.08 * (psi / 58) ** 2) & (t < 0.89 - 0.07 * np.clip(psi / hw_, -1, 1) ** 2)
        tend = 0.66 - 0.36 * smooth(55, 150, -phi)
        add = th & (phi <= qmed) & (phi > -158) & (t > -0.05) & (t < tend) & ~ham
        g[quad] = MUSCLE['quads']; g[ham] = MUSCLE['hamstrings']; g[add] = MUSCLE['adductors']
        # Wade
        t2, phi2, _ = limb(P, L['knee' + s], L['ank' + s], sgn)
        psi2 = (phi2 + 360) % 360 - 180
        # zwei Köpfe als Ovale, der innere (psi > 0) reicht tiefer
        t_end = 0.55 + 0.05 * np.sin(np.radians(np.clip(psi2, -90, 90))); t_beg = 0.05
        cc = (t_beg + t_end) / 2; hh = (t_end - t_beg) / 2
        wcalf = 82 * np.sqrt(np.clip(1 - ((t2 - cc) / hh) ** 2, 0, 1)) ** 0.7
        calf = on & (reg == 'calf') & (np.abs(psi2) < wcalf) & (t2 > t_beg) & (t2 < t_end)
        g[calf] = MUSCLE['calves']
        # Shorts: Hosenbein bis t_hem
        hem = 0.40 if fig == 'man' else 0.30
        cl[on & (reg == 'thigh') & (t < hem + 0.03 * np.cos(np.radians(phi)))] = CLOTH['shorts']
    # --- Gesäß (Rumpf oder Oberschenkel, hinten)
    fold = hip_z - 0.085 * sc + 0.045 * sc * smooth(0.04, 0.13, ax)
    gtop = hip_z + 0.055 * sc + 0.07 * sc * smooth(0.02, 0.15, ax)
    behind = (y > hip_y + 0.005) & (ang > 100)
    glute = np.isin(reg, ('torso', 'thigh')) & behind & (z > fold) & (z < gtop) & (ax > 0.008)
    g[glute] = MUSCLE['glutes']
    # --- Rumpf
    zb = sh_z - 0.195 * sc + 0.07 * sc * smooth(0.0, 0.17 * sc, ax) ** 1.5      # Unterkante Brustmuskel
    zt = clav_z - 0.012 * sc + 0.02 * sc * (ax / sh_x)
    # Fächer: seitlich zur Achsel hin schmaler
    xl = np.interp(z, [sh_z - 0.16 * sc, sh_z - 0.09 * sc, sh_z - 0.02 * sc, clav_z + 0.01 * sc],
                   [0.09 * sc, sh_x - 0.05 * sc, sh_x - 0.035 * sc, sh_x - 0.055 * sc])
    chest = tor & (ang < 78) & (z > zb) & (z < zt) & (ax > 0.013) & (ax < xl) & (g == 0)
    g[chest] = MUSCLE['chest']
    absw = 0.058 * sc * (0.72 + 0.28 * smooth(hip_z - 0.035 * sc, hip_z + 0.07 * sc, z) + 0.12 * np.clip((z - hip_z) / (sh_z - hip_z), 0, 1))
    zab = sh_z - 0.19 * sc
    ab = tor & (ang < 70) & (ax < absw) & (z > hip_z - 0.035 * sc) & (z < zab) & (g == 0)
    g[ab] = MUSCLE['abs']
    obl_lo = hip_z + 0.015 * sc + 0.075 * sc * smooth(0.0, 0.08 * sc, ax - absw)
    obl_hi = zb - 0.01 * sc - 0.06 * sc * smooth(60, 110, ang)
    obl = tor & (ang < 112) & (ax >= absw + 0.004) & (z > obl_lo) & (z < obl_hi) & (g == 0)
    g[obl] = MUSCLE['obliques']
    # oberer Rücken (Trapez + Rautenmuskeln): Raute vom Nacken bis unter die Schulterblätter
    zz = [sp2_z - 0.015 * sc, sh_z - 0.12 * sc, sh_z - 0.02 * sc, clav_z + 0.03 * sc, neck_z + 0.075 * sc]
    ww = [0.0, 0.085 * sc, sh_x - 0.03 * sc, 0.095 * sc, 0.032 * sc]
    wub = np.interp(z, zz, ww, left=-1, right=-1)
    back = (ang > 105) | ((z > clav_z) & (N[:, 2] > 0.25) & (y > yc_ - 0.01))
    ub = (tor | (reg == 'head') & (z < neck_z + 0.075 * sc)) & back & (ax < wub) & (g == 0)
    ub &= ~((reg == 'head'))
    g[ub] = MUSCLE['upper_back']
    # Rückenstrecker (unterer Rücken): zwei Stränge neben der Wirbelsäule
    lbw = 0.052 * sc * np.sqrt(np.clip(1 - ((z - (hip_z + sp3_z) / 2) / ((sp3_z - hip_z) / 2)) ** 2, 0, 1)) ** 0.5
    lb = tor & (ang > 135) & (ax < lbw) & (ax > 0.006) & (z > hip_z + 0.05 * sc) & (g == 0)
    g[lb] = MUSCLE['lower_back']
    # breiter Rückenmuskel: von der Achsel schräg zur Taille
    lat_lo = sp1_z + 0.03 * sc + 0.13 * sc * smooth(0.06 * sc, 0.16 * sc, ax)
    lt = tor & (ang > 92) & (z > lat_lo) & (z < sh_z - 0.065 * sc) & (ax > 0.045 * sc) & (g == 0)
    g[lt] = MUSCLE['lats']
    # --- Kleidung Rumpf
    waist = pel_z + 0.075 * sc
    shorts = np.isin(reg, ('torso',)) & (z < waist)
    cl[shorts] = CLOTH['shorts']
    backness = smooth(60, 150, ang)
    zneck = clav_z - 0.005 * sc + (neck_z + 0.012 * sc - clav_z) * backness + 0.06 * sc * smooth(0.04 * sc, 0.10 * sc, ax)
    shirt = np.isin(reg, ('torso', 'clav', 'neck')) & (z >= waist) & (z < zneck)
    cl[shirt] = CLOTH['top']
    # Kopfhaut / Augen / Haarknoten
    cl[W[:, K['scalp']] > 0.5] = CLOTH['hair']
    return g, cl, side


def torso_profile(co, W, K, L):
    """Rumpfmitte (y) und halbe Tiefe/Breite je Höhe aus den Rumpfvertices."""
    z0 = L['hipl'][2] - 0.15; z1 = L['neck'][2] + 0.12
    tor = (W[:, K['torso']] + W[:, K['clav_l']] + W[:, K['clav_r']] + W[:, K['neck']]) > 0.5
    zs = np.linspace(z0, z1, 40)
    yc, hd, hw = [], [], []
    for zi in zs:
        m = tor & (np.abs(co[:, 2] - zi) < 0.02)
        mc = m & (np.abs(co[:, 0]) < 0.03)
        if mc.sum() < 4:
            yc.append(np.nan); hd.append(np.nan); hw.append(np.nan); continue
        y0, y1 = co[mc, 1].min(), co[mc, 1].max()
        yc.append((y0 + y1) / 2); hd.append((y1 - y0) / 2)
        hw.append(np.abs(co[m, 0]).max())
    yc, hd, hw = (np.array(a) for a in (yc, hd, hw))
    ok = ~np.isnan(yc)
    return zs[ok], yc[ok], np.maximum(hd[ok], 0.05), np.maximum(hw[ok], 0.06)


def bake(body, rig, fig, png_path, preview_path, res=2048):
    me = body.data
    co, nor, W, K = vertex_features(body, rig)
    L = landmarks(rig)
    prof = torso_profile(co, W, K, L)
    idx, tri, bary, tv, tl, uv = rasterize(me, res)
    vi = tv[tri]                                        # (m,3)
    P = (co[vi] * bary[:, :, None]).sum(1)
    N = (nor[vi] * bary[:, :, None]).sum(1); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    Wt = (W[vi] * bary[:, :, None]).sum(1)
    sph = (Wt[:, K['eye']] > 0.5) | (Wt[:, K['hair']] > 0.5)
    keep = ~sph
    idx, P, N, Wt = idx[keep], P[keep], N[keep], Wt[keep]
    g, cl, side = classify(P, N, Wt, K, L, fig, prof)
    # Überlappung der UV-Inseln prüfen (gleiches Texel, weit auseinanderliegende Punkte)
    order = np.argsort(idx, kind='stable')
    i_s = idx[order]; P_s = P[order]
    dup = (i_s[1:] == i_s[:-1]) & (np.linalg.norm(P_s[1:] - P_s[:-1], axis=1) > 0.02)
    print('MASK texel %d, UV-Überlappungen %d' % (len(np.unique(idx)), int(dup.sum())))
    img = np.zeros((res * res, 4), np.float32)
    filled = np.zeros(res * res, bool)
    img[idx, 0] = g / 20.0; img[idx, 1] = cl / 10.0; img[idx, 2] = side; img[idx, 3] = 1
    filled[idx] = True
    # freie Blöcke für Augen und Haarknoten (Kugeln ohne eigene UVs)
    spots = {}
    bs = 16
    occ = filled.reshape(res, res)
    for name, c in (('eye', CLOTH['eye']), ('hair', CLOTH['hair'])):
        found = None
        for by in range(res // bs - 1, 0, -1):
            for bx in range(res // bs - 1, 0, -1):
                if not occ[by * bs - 4:(by + 1) * bs + 4, bx * bs - 4:(bx + 1) * bs + 4].any():
                    found = (bx, by); break
            if found: break
        bx, by = found
        blk = np.zeros((res, res), bool); blk[by * bs:(by + 1) * bs, bx * bs:(bx + 1) * bs] = True
        occ = occ | blk
        bi = np.flatnonzero(blk.ravel())
        img[bi] = (0, c / 10.0, 0.5, 1); filled[bi] = True
        spots[name] = ((bx * bs + bs / 2) / res, (by * bs + bs / 2) / res)
    # Ränder der UV-Inseln auffüllen (gegen Säume beim Abtasten)
    im = img.reshape(res, res, 4); fm = filled.reshape(res, res)
    for _ in range(8):
        new = ~fm
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(fm, dy, 0), dx, 1)
            take = new & src
            im[take] = np.roll(np.roll(im, dy, 0), dx, 1)[take]
            fm = fm | take
            new = ~fm
    # Kugel-UVs auf die Blöcke legen
    uvl = me.uv_layers.active
    nv = len(me.vertices)
    vtag = np.zeros(nv, np.int8)
    vtag[W[:, K['eye']] > 0.5] = 1; vtag[W[:, K['hair']] > 0.5] = 2
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    uvs = uv.copy()
    uvs[vtag[lv] == 1] = spots['eye']; uvs[vtag[lv] == 2] = spots['hair']
    uvl.data.foreach_set('uv', uvs.ravel())
    write_png(im.reshape(-1, 4), res, png_path, 'mask_' + fig)
    # Vorschau-Bild (Kontrollfarben)
    gi = np.clip(np.round(im[..., 0] * 20).astype(int), 0, 15); ci = np.round(im[..., 1] * 10).astype(int)
    pv = np.zeros((res, res, 4), np.float32); pv[..., 3] = 1
    for k, c in PAL.items():
        pv[gi == k, :3] = c
    for k, c in CPAL.items():
        pv[(gi == 0) & (ci == k), :3] = c
    write_png(pv.reshape(-1, 4), res, preview_path, 'maskpreview_' + fig)
    # Flächen-Farbattribut "mask" (für die Beschriftungsanker in figure.js): Wert in der Flächenmitte
    attr = me.color_attributes.get('mask') or me.color_attributes.new('mask', 'FLOAT_COLOR', 'CORNER')
    flat = im.reshape(-1, 4)
    cols = np.zeros((len(me.loops), 4), np.float32)
    for p in me.polygons:
        li = list(p.loop_indices)
        c = uvs[li].mean(0)
        px = min(res - 1, max(0, int(c[0] * res))); py = min(res - 1, max(0, int(c[1] * res)))
        cols[li] = flat[py * res + px]
    cols[:, 3] = 1
    attr.data.foreach_set('color', cols.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find('mask')
    cnt = np.bincount(np.round(cols[:, 0] * 20).astype(int), minlength=16)
    print('MASK loops per group', list(enumerate(cnt.tolist())))


def write_png(pix, res, path, name):
    im = bpy.data.images.get(name)
    if im:
        bpy.data.images.remove(im)
    im = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(pix.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    im.filepath = path
    im.reload()
    return im
