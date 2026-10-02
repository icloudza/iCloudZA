#!/usr/bin/env python3
"""离线生成《五行》用的位图素材和字体子集，产物提交进 assets/ink/（CI 不跑这个脚本）

    python scripts/make_assets.py           # 全部重新生成
    python scripts/make_assets.py images    # 只生成位图（需要 numpy、opencv-python、Pillow）
    python scripts/make_assets.py fonts     # 只更新字体子集（需要网络、fontTools、brotli）

改了 wuxing_svg.py 里画面上的文字后要重跑 fonts，否则新出现的字会回退到系统字体。

位图都是「墨」本身：RGB 是墨色，alpha 是墨量，在 SVG 里叠在纸上，用 opacity 控制浓淡。
- paper 纸；peak0 / peak1 水墨山（尖峰、双峰）；mist 云雾；cliff 斧劈皴山石；stroke 一笔横画；splatter / flecks_r 墨点
- band 朱红笔触带；swoosh 红色刀光；smear 甩镜拖影；flame0–1 火；splash_w 水花
- vortex 青墨漩涡；arc 金色刀弧；seal 印章；dry_k / dry_w / dry_r 大字用的干笔纹理（可平铺）
- fonts/  Yuji Boku（大字）、Permanent Marker（手写体标注）、Liu Jian Mao Cao（诗墙草书）的子集，授权见 fonts/LICENSES.txt
"""

import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'assets', 'ink')
PAPER = np.array([233, 229, 220]) / 255     # 纸：略带暖意的灰白
VERM = np.array([232, 56, 28]) / 255       # 朱红
INK = np.array([22, 20, 18]) / 255          # 焦墨（略暖的黑）

def fbm(h, w, beta, seed, aniso=(1.0, 1.0)):
    """谱合成分形噪声：功率谱 ∝ f^-beta，两个方向都可平铺；零均值单位方差"""
    r = np.random.default_rng(seed)
    F = np.fft.rfft2(r.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None] * aniso[0]
    fx = np.fft.rfftfreq(w)[None, :] * aniso[1]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1
    F *= f ** (-beta / 2)
    F[0, 0] = 0
    out = np.fft.irfft2(F, s=(h, w))
    return (out - out.mean()) / out.std()


def blur(a, s):
    return cv2.GaussianBlur(a.astype(np.float32), (0, 0), s) if s > 0 else a


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def warp(a, dx, dy):
    """按位移场重采样（域扭曲）"""
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return cv2.remap(a.astype(np.float32), xx + dx.astype(np.float32), yy + dy.astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def fibrous(alpha, seed, amount=1.0):
    """宣纸上的洇：边缘沿纤维方向毛糙地渗开，边上墨更聚（干后形成深色的边线）"""
    h, w = alpha.shape
    n = fbm(h, w, 1.6, seed)
    soft = blur(alpha, 1.2 * amount)
    edge = np.clip(soft + .18 * amount * n * soft * (1 - soft) * 4, 0, 1)
    rim = np.clip(1 - np.abs(soft - .5) * 2, 0, 1) ** 2
    return np.clip(edge + .25 * rim * edge, 0, 1)


def save(name, rgb, alpha=None, q=80, scale=1.0):
    rgb = np.clip(rgb, 0, 1)
    arr = (rgb * 255 + .5).astype(np.uint8)
    mode = 'RGB'
    if alpha is not None:
        arr = np.dstack([arr, (np.clip(alpha, 0, 1) * 255 + .5).astype(np.uint8)])
        mode = 'RGBA'
    im = Image.fromarray(arr, mode)
    if scale != 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    path = os.path.join(OUT, f'{name}.webp')
    im.save(path, quality=q, method=6, alpha_quality=80)
    print(f'{name}.webp {im.width}x{im.height}', os.path.getsize(path), 'bytes')


def solid(color, h, w):
    return np.broadcast_to(np.array(color, dtype=float), (h, w, 3)).copy()


# ---------------------------------------------------------------- 素材


# ---------------------------------------------------------------- 素材

def paper():
    """宣纸：低频的旧色斑 + 纤维 + 细颗粒 + 四角略暗"""
    h, w = 467, 830
    r = np.random.default_rng(1)
    tone = .012 * fbm(h, w, 3.0, 2) + .006 * fbm(h, w, 2.0, 3)
    fib = np.zeros((h, w), np.float32)
    for _ in range(2600):
        x, y = r.uniform(0, w), r.uniform(0, h)
        ang = r.uniform(0, np.pi)
        ln = r.uniform(4, 26) * (1 + 2 * r.random() ** 6)
        pts = []
        for k in range(6):
            t = k / 5 * ln
            pts.append((x + np.cos(ang) * t + r.normal(0, .6), y + np.sin(ang) * t + r.normal(0, .6)))
        cv2.polylines(fib, [np.int32(np.array(pts) * 16)], False, float(r.choice([-1, 1]) * r.uniform(.4, 1)), 1,
                      cv2.LINE_AA, shift=4)
    fib = blur(fib, .5) * .032
    grain = r.standard_normal((h, w)) * .006
    yy, xx = np.mgrid[0:h, 0:w]
    vig = ((xx / w - .5) ** 2 * 1.2 + (yy / h - .5) ** 2 * 1.6)
    L = 1 + tone + fib + grain - .10 * vig ** 1.4
    rgb = PAPER[None, None, :] * L[..., None]
    rgb[..., 2] -= .012 * vig      # 边缘泛一点旧黄
    save('paper', rgb, q=62)


def _peak_shape(w, h, seed, kind):
    """山峰轮廓（顶边 y 坐标），kind: 0 尖峰 1 圆峰 2 双峰"""
    r = np.random.default_rng(seed)
    x = np.linspace(-1, 1, w)
    if kind == 0:
        prof = np.clip(1 - np.abs(x) ** 1.0, 0, 1) ** 1.35
    elif kind == 1:
        prof = np.clip(1 - x ** 2, 0, 1) ** .9
    else:
        prof = np.maximum(np.clip(1 - np.abs(x + .3) * 1.6, 0, 1) ** 1.2, .78 * np.clip(1 - np.abs(x - .38) * 1.7, 0, 1) ** 1.2)
    n = blur(np.cumsum(r.standard_normal(w))[None, :] * .012, 2.5)[0]
    n -= np.linspace(n[0], n[-1], w)
    n2 = blur(r.standard_normal((1, w)), 3)[0] * .06
    prof = np.clip(prof + (n + n2) * prof ** .5, 0, 1.05)
    top = h * (1 - .93 * prof) + 2
    return top


def _brush_line(canvas, pts, w0, w1, ink, rng, dry=.0):
    """沿折线画一笔：宽度从 w0 渐变到 w1，墨量随机起伏，dry>0 时断续露白"""
    n = len(pts) - 1
    for k in range(n):
        t = k / max(1, n - 1)
        if dry and rng.random() < dry * t:
            continue
        w = max(1, int(round((w0 + (w1 - w0) * t) * 16)))
        p0 = (int(pts[k][0] * 16), int(pts[k][1] * 16))
        p1 = (int(pts[k + 1][0] * 16), int(pts[k + 1][1] * 16))
        lay = np.zeros_like(canvas)
        cv2.line(lay, p0, p1, float(ink * rng.uniform(.8, 1.0)), max(1, w // 16), cv2.LINE_AA, shift=4)
        np.maximum(canvas, lay, out=canvas)


def _blot(canvas, x, y, rx, ry, ang, ink):
    """一个米点：软边的横向墨团，叠加方式是 1-(1-a)(1-b)"""
    pad = int(max(rx, ry) * 2 + 4)
    h, w = canvas.shape
    x0, y0, x1, y1 = int(x) - pad, int(y) - pad, int(x) + pad, int(y) + pad
    if x1 < 0 or y1 < 0 or x0 >= w or y0 >= h:
        return
    lay = np.zeros((y1 - y0, x1 - x0), np.float32)
    cv2.ellipse(lay, (int((x - x0) * 16), int((y - y0) * 16)), (max(1, int(rx * 16)), max(1, int(ry * 16))), ang, 0, 360,
                float(ink), -1, cv2.LINE_AA, shift=4)
    lay = cv2.GaussianBlur(lay, (0, 0), max(.6, ry * .45))
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(w, x1), min(h, y1)
    sub = lay[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canvas[cy0:cy1, cx0:cx1] = 1 - (1 - canvas[cy0:cy1, cx0:cx1]) * (1 - sub)


def mountain(name, kind, seed, w=300, h=240, cun=True):
    """水墨山：一层平滑的淡墨打底，上面层层叠横向的米点，越近山脊越密越浓；
    山体里有几道向下的山脊线，米点沿着它们聚成体积；山脊上点几粒浓墨的苔点；山脚化进雾里"""
    r = np.random.default_rng(seed)
    top = _peak_shape(w, h, seed, kind)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = yy - top[None, :]
    inside = smoothstep(-1.5, 1.5, d)
    yun = 1 + .18 * blur(fbm(h, w, 3.8, seed + 1), 3)
    wash = inside * (.10 + .26 * np.exp(-np.clip(d, 0, None) / (h * .20))) * yun
    dots = np.zeros((h, w), np.float32)
    if cun:
        # 山体里的次级山脊：从峰顶附近斜着往下
        peak_x = int(np.argmin(top))
        ridges = []
        for k in range(r.integers(3, 6)):
            sx = np.clip(peak_x + r.normal(0, w * .14), 6, w - 6)
            sy = top[int(sx)] + r.uniform(4, 20)
            dirx = r.choice([-1, 1]) * r.uniform(.4, 1.1)
            ridges.append((sx, sy, dirx, r.uniform(h * .25, h * .6)))
        n = int(w * h / 55)
        for i in range(n):
            x = r.uniform(0, w)
            t = top[int(x)]
            if t > h * .93:
                continue
            depth = r.exponential(h * .16)
            if r.random() < .45 and ridges:            # 落在山脊线附近
                sx, sy, dirx, ln = ridges[r.integers(len(ridges))]
                u = r.random() ** 1.3
                x = sx + dirx * u * ln + r.normal(0, 5)
                if not 0 <= x < w:
                    continue
                y = sy + u * ln + r.normal(0, 3)
                depth = y - top[int(x)]
                if depth < 0:
                    continue
            else:
                y = t + depth
            if y > h * .9:
                continue
            fade = np.exp(-depth / (h * .22))
            rx = r.uniform(2.0, 7.5) * (.6 + .6 * (1 - fade))
            _blot(dots, x, y, rx, rx * r.uniform(.35, .6), r.normal(0, 8), r.uniform(.10, .30) * (.35 + .9 * fade))
        # 山脊轮廓：沿着顶边密集的小米点
        for x in np.arange(2, w - 2, 1.6):
            t = top[int(x)]
            if t > h * .9:
                continue
            _blot(dots, x + r.normal(0, .8), t + r.uniform(.5, 3.0), r.uniform(1.4, 3.2), r.uniform(.9, 1.6), r.normal(0, 20),
                  r.uniform(.25, .55))
        # 苔点：山脊上几簇浓墨小点
        for k in range(r.integers(5, 9)):
            x = r.uniform(w * .1, w * .9)
            t = top[int(x)]
            if t > h * .8:
                continue
            for j in range(r.integers(2, 5)):
                _blot(dots, x + r.normal(0, 4), t + r.uniform(1, 6), r.uniform(.9, 1.8), r.uniform(.8, 1.3), 0, r.uniform(.7, .95))
    dens = 1 - (1 - wash) * (1 - dots * smoothstep(-3, 2, d))
    dens *= 1 - smoothstep(h * .48, h * .96, yy)
    dens = np.clip(blur(dens, .45), 0, 1)
    save(name, solid(INK, h, w), dens, q=54, scale=.62)


def mist():
    """云雾：纸色的团块（画里的雾就是留白），上缘一团团鼓起，左右散开"""
    h, w = 150, 640
    r = np.random.default_rng(21)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    a = np.zeros((h, w))
    for i in range(26):          # 一团团的云头
        cx, cy = r.uniform(40, w - 40), r.uniform(h * .45, h * .62)
        rx, ry = r.uniform(40, 110), r.uniform(16, 30)
        a = np.maximum(a, np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) ** 1.2) * r.uniform(.6, 1))
    base = np.exp(-((yy / h - .62) / .2) ** 2) * .7
    a = np.maximum(a, base)
    a *= smoothstep(0, .2, xx / w) * smoothstep(0, .2, 1 - xx / w)
    a *= 1 + .35 * fbm(h, w, 2.4, 22)
    a = blur(np.clip(a, 0, 1), 2.5)
    save('mist', solid(PAPER * 1.01, h, w), np.clip(a * 1.1, 0, 1), q=46, scale=.42)


def cliff():
    """土（斧劈皴）：几块棱角分明的山石叠在一起；每块的受光面留白，背光面是顺着山势斜劈下去的浓墨，
    明暗交界是一道山脊线，外轮廓一道粗墨线"""
    w, h = 420, 360
    r = np.random.default_rng(151)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    total = np.zeros((h, w), np.float32)
    blocks = [(30, 250, 150, 40), (170, 400, 280, 90), (110, 300, 200, 150), (-20, 160, 60, 170), (300, 440, 380, 190)]
    for bi, (x0, x1, xp, yp) in enumerate(blocks):
        yp = yp + r.uniform(-15, 15)
        # 轮廓：左坡和右坡各几段折线（锯齿）
        def side(xa, ya, xb, yb, n):
            pts = [(xa, ya)]
            for k in range(1, n):
                t = k / n
                pts.append((xa + (xb - xa) * t + r.normal(0, 6), ya + (yb - ya) * t + r.normal(0, 8)))
            pts.append((xb, yb))
            return pts
        left = side(x0, h, xp, yp, 5)
        right = side(xp, yp, x1, h, 5)
        poly = np.array(left + right[1:], np.float32)
        mask = np.zeros((h, w), np.float32)
        cv2.fillPoly(mask, [(poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, shift=4)
        # 山脊：从峰顶斜向右下，分开明暗两面
        rx = xp + (x1 - xp) * r.uniform(.15, .35)
        ridge = side(xp, yp, rx, h, 6)
        dark_poly = np.array(ridge + right[::-1][:-1], np.float32)
        dark = np.zeros((h, w), np.float32)
        cv2.fillPoly(dark, [(dark_poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, shift=4)
        # 背光面的笔触：沿山势方向（右下）拉长的干笔
        ang = np.arctan2(h - yp, x1 - xp)
        tex = fbm(h, w, 2.0, 152 + bi, aniso=(1.0, 8.0))
        c, s = np.cos(-ang), np.sin(-ang)
        tex = cv2.warpAffine(tex.astype(np.float32), np.float32([[c, -s, w / 2 - c * w / 2 + s * h / 2], [s, c, h / 2 - s * w / 2 - c * h / 2]]),
                             (w, h), borderMode=cv2.BORDER_REFLECT)
        ink = smoothstep(-2.4, -1.5, tex) * (.85 + .15 * smoothstep(0, 1, (yy - yp) / (h - yp)))
        shade = dark * ink
        # 受光面靠近山脊的几笔
        lit = (mask - dark).clip(0, 1) * smoothstep(1.2, 2.0, tex) * .8
        lines = np.zeros((h, w), np.float32)
        _brush_line(lines, ridge, r.uniform(3, 5), 1.2, 1.0, r, dry=.2)
        for k in range(0, len(left) - 1):
            _brush_line(lines, left[k:k + 2], r.uniform(5, 8), r.uniform(3.5, 5.5), 1.0, r)
        for k in range(0, len(right) - 1):
            _brush_line(lines, right[k:k + 2], r.uniform(5, 8), r.uniform(3.5, 5.5), 1.0, r)
        block = np.clip(1 - (1 - shade) * (1 - lit) * (1 - lines), 0, 1)
        # 后面的石块被前面的挡住：先把前块覆盖处的旧墨擦掉，再叠上
        total = total * (1 - mask) + block
    total *= 1 - smoothstep(h * .82, h, yy) * .7
    save('cliff', solid(INK, h, w), np.clip(blur(total, .5), 0, 1), q=50, scale=.6)


def _bristles(w, h, env, seed, dry_from=.0, dry_rate=1.0, nb=110):
    """按笔宽包络 env(x) 排一排笔毛：每根毛的墨量沿行笔方向衰减，干处断续露白（飞白）"""
    r = np.random.default_rng(seed)
    xs = np.arange(w)
    xx = xs / w
    a = np.zeros((h, w), np.float32)
    for b in range(nb):
        v = (b + .5) / nb * 2 - 1
        y0 = h / 2 + v * h * .40 * env + blur(r.standard_normal((1, w)), 20)[0] * 2
        dry = r.uniform(.5, 1.0) - .3 * abs(v) ** 1.5
        k = blur(r.standard_normal((1, w)), 8)[0]
        run = np.clip(xx - dry_from, 0, None) * dry_rate
        ink = np.clip(dry * 1.7 - run * (1.05 + .7 * abs(v)) + .45 * k + .25, 0, 1)
        gaps = smoothstep(-.3, .4, blur(r.standard_normal((1, w)), 3)[0] * 1.2 + 1.0 - run * 1.3)
        line = (ink * gaps * (env > .02)).astype(np.float32)
        for dy in (0, 1):
            yi = np.clip(np.round(y0).astype(int) + dy, 0, h - 1)
            a[yi, xs] = np.maximum(a[yi, xs], line * (1 if dy == 0 else .7))
    return blur(a, .8) * 1.2


def stroke():
    """一笔横画（海报里当条形图用）：圆头起笔，行笔匀实，收笔处一小段飞白"""
    w, h = 760, 110
    xs = np.arange(w)
    xx = xs / w
    x0 = h * .40
    cap = np.sqrt(np.clip(1 - ((x0 - xs) / x0) ** 2, 0, 1)) * (xs < x0) + (xs >= x0)
    env = cap * (1 - .12 * smoothstep(.1, .8, xx)) * (1 - smoothstep(.86, 1.0, xx) ** 1.5)
    a = _bristles(w, h, env, 51, dry_from=.62, dry_rate=2.6)
    yy = np.arange(h)[:, None]
    head = np.exp(-(((xs[None, :] - 40) / 34) ** 2 + ((yy - h / 2) / (h * .36)) ** 2) ** 2) * 1.1
    a = np.clip(a + head, 0, 1)
    a = np.clip(a + .05 * fbm(h, w, 1.5, 53) * a * (1 - a) * 4, 0, 1)
    save('stroke', solid(INK, h, w), a, q=56, scale=.56)


def splatter():
    """甩出去的墨点：沿一个方向（向右）飞散，大点带拖尾，小点密"""
    w, h = 360, 220
    a = np.zeros((h, w), np.float32)
    r = np.random.default_rng(41)
    for i in range(140):
        t = r.random() ** 1.6
        x = 10 + t * (w - 40)
        y = h / 2 + r.normal(0, 14 + 60 * t)
        size = max(.6, min(6.5, (1 - t) ** 1.2 * r.uniform(1.5, 8) * (r.random() ** 2.5 * 1.6 + .4)))
        ang = np.degrees(np.arctan2(y - h / 2, x + 60)) + r.normal(0, 4)
        stretch = 1 + 3 * r.random() ** 3
        cv2.ellipse(a, (int(x * 16), int(y * 16)), (int(size * stretch * 16), int(size * 16)), ang, 0, 360, 1.0, -1,
                    cv2.LINE_AA, shift=4)
        if size > 4 and r.random() < .5:       # 拖尾
            tl = size * r.uniform(2, 5)
            cv2.line(a, (int((x - np.cos(np.radians(ang)) * tl) * 16), int((y - np.sin(np.radians(ang)) * tl) * 16)),
                     (int(x * 16), int(y * 16)), .9, max(1, int(size * .5)), cv2.LINE_AA, shift=4)
    a = fibrous(np.clip(blur(a, .6), 0, 1), 42, .5)
    save('splatter', solid(INK, h, w), a, q=66, scale=.6)


def flecks_r():
    """朱红的碎墨点（片头地面上飞的那种，海报上也零星飘几粒）"""
    w, h = 360, 220
    a = np.zeros((h, w), np.float32)
    r = np.random.default_rng(161)
    for i in range(60):
        x, y = r.uniform(10, w - 10), r.uniform(10, h - 10)
        size = max(.8, r.exponential(2.2))
        ang = r.normal(-8, 10)
        cv2.ellipse(a, (int(x * 16), int(y * 16)), (int(size * r.uniform(1.5, 4) * 16), int(size * 16)), ang, 0, 360, 1.0, -1,
                    cv2.LINE_AA, shift=4)
    a = blur(a, .6)
    save('flecks_r', solid(VERM, h, w), a, q=52, scale=.56)


def band():
    """朱红笔触带：一大笔横扫，上下边是干笔的毛边，尾端散开，下沿挂着往下淌的颜料"""
    w, h = 1000, 260
    r = np.random.default_rng(121)
    xs = np.arange(w)
    xx = xs / w
    top0, bot0 = 70.0, 170.0
    env_t = top0 + blur(r.standard_normal((1, w)), 30)[0] * 10 + 18 * smoothstep(.75, 1, xx)
    env_b = bot0 + blur(r.standard_normal((1, w)), 30)[0] * 10 - 22 * smoothstep(.8, 1, xx)
    yy = np.arange(h)[:, None].astype(float)
    body = smoothstep(env_t - 2, env_t + 2, yy) * (1 - smoothstep(env_b - 2, env_b + 2, yy))
    # 毛边：上下边缘各一排细笔毛
    bristle = np.zeros((h, w), np.float32)
    for b in range(70):
        edge = r.random() < .5
        y0 = (env_t if edge else env_b) + (-1 if edge else 1) * r.uniform(0, 9)
        x0, ln = r.uniform(-50, w), r.uniform(60, 420)
        seg = (xs > x0) & (xs < x0 + ln)
        yi = np.clip(np.round(y0 + blur(r.standard_normal((1, w)), 12)[0] * 2).astype(int), 0, h - 1)
        bristle[yi[seg], xs[seg]] = r.uniform(.5, 1)
    bristle = blur(bristle, .7) * 1.4
    # 干笔：笔肚里顺着行笔方向的白丝，往尾端越来越多
    dry = smoothstep(.1, .9, fbm(h, w, 2.0, 122, aniso=(1.0, 14.0)) + 1.4 - 1.8 * xx[None, :] ** 2)
    a = np.clip(body * dry + bristle, 0, 1)
    # 起笔：左端圆钝；收笔：右端散成几缕
    a *= smoothstep(0, .03, xx)[None, :]
    a *= 1 - smoothstep(.9, 1.0, xx)[None, :] * (fbm(h, w, 2.0, 123, aniso=(1.0, 10.0)) < .3)
    # 滴痕：从下沿往下淌
    drips = np.zeros((h, w), np.float32)
    for i in range(16):
        x = r.uniform(80, w * .85)
        y0 = env_b[int(x)] - 2
        ln = r.uniform(12, 80) * r.random() ** .5
        wd = r.uniform(1.4, 3.6)
        cv2.line(drips, (int(x * 16), int(y0 * 16)), (int(x * 16), int((y0 + ln) * 16)), 1.0, max(1, int(wd)), cv2.LINE_AA, shift=4)
        cv2.circle(drips, (int(x * 16), int((y0 + ln) * 16)), int(wd * .9 * 16), 1.0, -1, cv2.LINE_AA, shift=4)
    a = np.clip(np.maximum(a, blur(drips, .6)), 0, 1)
    save('band', solid(VERM, h, w), a, q=48, scale=.5)


def swoosh():
    """红色弧形刀光：中段最厚、两端削尖的月牙，顺着弧线有干笔的丝"""
    w, h = 560, 300
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy, R = w / 2, h * 1.05, w * .47
    rad = np.hypot(xx - cx, yy - cy)
    ang = np.degrees(np.arctan2(yy - cy, xx - cx)) + 90
    pos = np.clip((ang + 75) / 150, 0, 1)
    alive = (ang > -75) & (ang < 75)
    thick = 2 + 40 * np.clip(np.sin(np.pi * pos ** 1.3), 0, 1) ** 1.2
    d = R - rad
    TW, TH = 1024, 96
    S = cv2.remap(fbm(TH, TW, 2.0, 131, aniso=(1.0, 12.0)).astype(np.float32), (pos * (TW - 1)).astype(np.float32),
                  np.clip((d / 50 + .1) * (TH - 1), 0, TH - 1).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    body = smoothstep(-2, 1.5, d) * (1 - smoothstep(thick - 3, thick + 1.5, d)) * alive
    a = np.clip(body * smoothstep(-1.2, .2, S + 1.2 - .9 * np.abs(pos - .55) * 2), 0, 1)
    save('swoosh', solid(VERM, h, w), blur(a, .5), q=60, scale=.56)


def smear():
    """甩镜头的动态模糊：横向拉长的红、黑、白条"""
    h, w = 234, 415
    r = np.random.default_rng(141)
    rgb = np.zeros((h, w, 3))
    y = 0
    cols = [VERM, np.array([.08, .07, .06]), PAPER, VERM * .8, PAPER * .9]
    while y < h:
        hh = int(r.uniform(3, 26))
        rgb[y:y + hh] = cols[r.integers(len(cols))]
        y += hh
    rgb = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), sigmaX=40, sigmaY=2.2)
    rgb += .04 * fbm(h, w, 1.6, 142, aniso=(1.0, 10.0))[..., None]
    save('smear', np.clip(rgb, 0, 1), q=46, scale=.6)


def flame_rw(name, seed):
    """火：浓墨勾边，外层朱红，里面白热（几条扭动的火舌叠在一起）"""
    w, h = 300, 420
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    up = np.clip((h - yy) / h, 0, 1)
    wx = (blur(fbm(h, w, 3.4, seed + 1), 2) * 18 + fbm(h, w, 2.4, seed + 4) * 3) * (.3 + up)
    X, Y = xx + wx, yy
    field = np.full((h, w), 9.0, np.float32)
    for k in range(7):
        base = h - 10
        top = r.uniform(20, 70) if k == 0 else r.uniform(80, 260)
        cx = w / 2 + (r.uniform(-70, 70) if k else 0)
        wmax = r.uniform(80, 100) if k == 0 else r.uniform(26, 56)
        ph, amp = r.uniform(0, 6.28), r.uniform(16, 36)
        t = (base - Y) / (base - top)
        width = wmax * np.clip(1 - t, 0, 1) ** .9 * np.sqrt(np.clip(smoothstep(-.02, .16, t), 0, 1)) + 1e-3
        sway = amp * np.sin(t * 3.2 + ph) * np.clip(t, 0, 1) ** 1.2
        d = np.abs(X - cx - sway) / width
        d = np.where((t > 1) | (t < -.03), 9, d)
        field = np.minimum(field, d)
    field = blur(field, 1.0)
    alpha = smoothstep(1.04, .97, field)
    outline = alpha * smoothstep(.76, .9, field)
    heat = np.clip(1 - field, 0, 1) * (1 - .55 * up)
    white = np.array([.99, .97, .93])
    t = smoothstep(.54, .6, heat)[..., None]
    rgb = VERM * (1 - t) + white * t
    rgb = rgb * (1 - outline[..., None]) + np.array([.07, .05, .04]) * outline[..., None]
    save(name, rgb, alpha, q=54, scale=.48)


def splash_w():
    """白水花：黑墨勾边的水冠，四周一圈尖刺，刺尖甩出水珠"""
    w, h = 420, 320
    r = np.random.default_rng(95)
    a = np.zeros((h, w), np.float32)
    cx, base = w / 2, h - 40
    for i in range(26):
        ang = np.radians(r.uniform(-75, 75))
        ln = r.uniform(60, 190) * (1 - .45 * abs(np.sin(ang)))
        bx = cx + np.sin(ang) * r.uniform(30, 110)
        tx, ty = bx + np.sin(ang) * ln * .8, base - np.cos(ang) * ln
        wd = r.uniform(6, 15)
        pts = np.array([[bx - wd, base], [tx, ty], [bx + wd, base]]) * 16
        cv2.fillPoly(a, [pts.astype(np.int32)], 1.0, cv2.LINE_AA, shift=4)
        for k in range(r.integers(1, 4)):
            dx, dy = tx + np.sin(ang) * r.uniform(8, 40), ty - np.cos(ang) * r.uniform(8, 40)
            cv2.circle(a, (int(dx * 16), int(dy * 16)), int(r.uniform(2, 6) * 16), 1.0, -1, cv2.LINE_AA, shift=4)
    cv2.ellipse(a, (int(cx * 16), int(base * 16)), (int(150 * 16), int(20 * 16)), 0, 0, 360, 1.0, -1, cv2.LINE_AA, shift=4)
    a = blur(a, 1.0)
    alpha = smoothstep(.15, .5, a)
    edge = alpha * (1 - smoothstep(.45, .9, a))
    rgb = np.array([.99, .98, .96]) * (1 - edge[..., None]) + np.array([.07, .06, .05]) * edge[..., None]
    save('splash_w', rgb, alpha, q=52, scale=.56)


def vortex():
    """青墨漩涡：一圈旋转的浓墨，顺着旋转方向拉出笔丝；
    内缘亮成青白色，外缘是深靛的墨，向外甩出墨点和墨丝"""
    s = 460
    c = s / 2
    r = np.random.default_rng(61)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    rad = np.hypot(xx - c, yy - c)
    ang = np.arctan2(yy - c, xx - c)
    R0 = 150.0
    # 极坐标纹理：角度方向 1024 格，半径方向 256 格
    TW, TH = 1024, 256
    streak = fbm(TH, TW, 2.4, 62, aniso=(1.0, 14.0))      # 沿角度拉长的笔丝（fbm 本身首尾相接）
    lump = fbm(TH, TW, 3.4, 63, aniso=(1.0, 2.0))
    twist = (rad - R0) * .016                                      # 螺旋：越往外越落后
    u = ((ang + twist) / (2 * np.pi) % 1) * TW
    v = np.clip(rad / (s / 2) * (TH - 1), 0, TH - 1)
    S = cv2.remap(streak.astype(np.float32), u.astype(np.float32), v.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    L = cv2.remap(lump.astype(np.float32), u.astype(np.float32), v.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    # 环的截面：内缘陡、外缘缓，外缘随纹理起伏（甩出去的墨）
    inner_edge = R0 - 26 + 6 * L
    outer_edge = R0 + 34 + 26 * np.clip(L + .6 * S, -1, 2)
    body = smoothstep(inner_edge - 3, inner_edge + 4, rad) * (1 - smoothstep(outer_edge - 18, outer_edge, rad))
    dens = np.clip(body * (.72 + .28 * S), 0, 1)
    # 颜色：内缘青白发光 → 宝蓝 → 外缘深靛
    t = np.clip((rad - inner_edge) / 60, 0, 1)[..., None]
    glow, blue, deep = np.array([.62, .95, 1.0]), np.array([.15, .52, .92]), np.array([.04, .09, .24])
    rgb = glow * (1 - t) ** 3 + blue * 3 * t * (1 - t) ** 1.2 + deep * t ** 1.5
    hi = smoothstep(.9, 2.0, S)[..., None] * (1 - t) * .9        # 笔丝上的高光
    rgb = rgb * (1 - hi) + np.array([.92, .99, 1.0]) * hi
    # 甩出去的墨点
    flecks = np.zeros((s, s), np.float32)
    for i in range(160):
        a = r.uniform(-np.pi, np.pi)
        rr = R0 + 40 + r.exponential(28)
        if rr > s / 2 - 6:
            continue
        size = max(.7, r.exponential(1.6))
        x, y = c + np.cos(a) * rr, c + np.sin(a) * rr
        cv2.ellipse(flecks, (int(x * 16), int(y * 16)), (int(size * 2.4 * 16), int(size * 16)), np.degrees(a) + 90 + r.normal(25, 10),
                    0, 360, 1.0, -1, cv2.LINE_AA, shift=4)
    halo = np.exp(-((rad - inner_edge + 4) / 9) ** 2) * .85
    a = np.clip(dens + flecks * .9 + halo * (1 - dens), 0, 1)
    rgb = (rgb * dens[..., None] + deep * 1.2 * flecks[..., None] + glow * halo[..., None] * (1 - dens[..., None])) / np.maximum(a, 1e-4)[..., None]
    save('vortex', np.clip(rgb, 0, 1), a, q=40, scale=.44)


def arc():
    """金色刀弧：月牙形的刀光顺着挥刀方向拉出笔丝，前端厚、尾端细，
    外缘一道亮白的刃，里面有墨色的裂纹，四周溅出金屑"""
    w, h = 600, 320
    r = np.random.default_rng(71)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy, R = w / 2, h * 1.02, w * .46
    rad = np.hypot(xx - cx, yy - cy)
    ang = np.degrees(np.arctan2(yy - cy, xx - cx)) + 90           # 0 在正上方，左负右正
    pos = np.clip((ang + 80) / 160, 0, 1)                         # 沿弧 0..1（左→右，右端是刀头）
    alive = (ang > -80) & (ang < 80)
    thick = 6 + 44 * np.clip(np.sin(np.pi * pos ** 1.6), 0, 1) ** 1.3
    d = R - rad
    TW, TH = 1024, 128
    streak = fbm(TH, TW, 2.2, 72, aniso=(1.0, 12.0))
    u = (pos * (TW - 1)).astype(np.float32)
    v = np.clip((d / 60 + .2) * (TH - 1), 0, TH - 1).astype(np.float32)
    S = cv2.remap(streak.astype(np.float32), u, v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    edge_out = smoothstep(-2.5, 1.5, d)
    edge_in = 1 - smoothstep(thick * (.75 + .25 * np.clip(S, -1, 1)), thick + 4, d)
    body = edge_out * edge_in * alive * smoothstep(0, .06, pos) * smoothstep(0, .02, 1 - pos)
    dens = np.clip(body * (.55 + .45 * smoothstep(-1.2, 1.2, S)), 0, 1)
    blade = np.exp(-((d - 1.5) / 2.2) ** 2) * alive * smoothstep(0, .25, pos)
    crack = 1 - .8 * np.exp(-(fbm(h, w, 2.1, 73) / .05) ** 2) * smoothstep(-.3, .8, fbm(h, w, 3.0, 74))
    t = np.clip(d / np.maximum(thick, 1), 0, 1)[..., None]
    pale, gold, amber = np.array([1.0, .97, .86]), np.array([.98, .74, .30]), np.array([.62, .30, .08])
    rgb = pale * (1 - t) ** 2 + gold * 2 * t * (1 - t) + amber * t ** 2
    rgb = rgb * (.35 + .65 * crack[..., None])
    rgb = rgb * (1 - blade[..., None]) + np.array([1.0, 1.0, .95]) * blade[..., None]
    sparks = np.zeros((h, w), np.float32)
    for i in range(130):
        p = r.random() ** .7
        a = np.radians(-80 + 160 * p - 90)
        rr = R + r.normal(0, 18) - r.exponential(10)
        x, y = cx + np.cos(a) * rr, cy + np.sin(a) * rr
        if not (0 < x < w and 0 < y < h):
            continue
        ln = r.uniform(2, 9)
        ta = a + np.pi / 2
        cv2.line(sparks, (int(x * 16), int(y * 16)), (int((x - np.cos(ta) * ln) * 16), int((y - np.sin(ta) * ln) * 16)),
                 float(r.uniform(.4, 1)), 1, cv2.LINE_AA, shift=4)
    a = np.clip(dens + blade, 0, 1)
    glow = blur(a, 9) * .55
    tot = np.clip(a + glow * (1 - a) + sparks * (1 - a), 0, 1)
    col = (rgb * a[..., None] + np.array([1.0, .80, .45]) * (glow * (1 - a))[..., None]
           + np.array([1.0, .9, .6]) * (sparks * (1 - a))[..., None]) / np.maximum(tot, 1e-4)[..., None]
    save('arc', np.clip(col, 0, 1), tot, q=42, scale=.5)


def seal():
    """朱印：方印，边缘略有崩口，印泥不匀"""
    s = 112
    a = np.zeros((s, s), np.float32)
    cv2.rectangle(a, (6, 6), (s - 7, s - 7), 1.0, -1, cv2.LINE_AA)
    n = fbm(s, s, 1.5, 81)
    a = warp(a, n * 1.4, fbm(s, s, 1.5, 82) * 1.4)
    a *= np.clip(.86 + .16 * fbm(s, s, 2.2, 83), 0, 1)
    a *= 1 - .7 * smoothstep(2.1, 2.9, fbm(s, s, 1.2, 84))     # 印泥没压到的白点
    red = np.array([.70, .16, .12])
    save('seal', solid(red, s, s), np.clip(a, 0, 1), q=70, scale=.6)


def drybrush():
    """干笔纹理（可平铺）：给大字填充用，斜向的笔丝之间露出底色；黑、白、朱红各一张"""
    s = 128
    n = fbm(s, s, 2.0, 171, aniso=(1.0, 12.0))
    a = smoothstep(-1.2, -.8, n) * (1 - .3 * smoothstep(.9, 1.7, fbm(s, s, 2.6, 172)))
    for nm, col in (('dry_k', INK), ('dry_w', np.array([.98, .97, .95])), ('dry_r', VERM)):
        save(nm, solid(col, s, s), np.clip(a, 0, 1), q=44)


def _fetch(url: str) -> bytes:
    # Google Fonts 按 User-Agent 决定返回格式，带上现代浏览器的 UA 才会给 WOFF2；网络偶尔抖动，重试几次
    ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
    for attempt in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': ua}), timeout=30).read()
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def fonts():
    """用 Google Fonts 的 text= 参数只下载用到的字形"""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    sys.path.insert(0, HERE)
    from wuxing_svg import FONT_FILES, cjk_chars, latin_chars, wall_chars

    jobs = [   # (Google Fonts 家族, 需要的字, 输出文件, google/fonts 仓库里的授权文件)
        ('Yuji Boku', cjk_chars(), FONT_FILES['YB'], 'ofl/yujiboku/OFL.txt'),
        ('Permanent Marker', latin_chars(), FONT_FILES['PM'], 'apache/permanentmarker/LICENSE.txt'),
        ('Liu Jian Mao Cao', wall_chars(), FONT_FILES['LJ'], 'ofl/liujianmaocao/OFL.txt'),
    ]
    os.makedirs(os.path.join(OUT, 'fonts'), exist_ok=True)
    licenses = []
    for family, text, fn, lic in jobs:
        css = _fetch(f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}"
                     f"&text={urllib.parse.quote(text)}").decode()
        font = TTFont(io.BytesIO(_fetch(re.search(r'url\(([^)]+)\)', css).group(1))))
        if 'fvar' in font:
            font = instancer.instantiateVariableFont(font, {'wght': 400})
        font.flavor = 'woff2'
        path = os.path.join(OUT, 'fonts', fn)
        font.save(path)
        missing = [ch for ch in text if ord(ch) not in font.getBestCmap() and not ch.isspace()]
        print(f'fonts/{fn}', os.path.getsize(path), 'bytes', 'missing:', ''.join(missing) or '-')
        licenses.append(f'===== {family} =====\n\n'
                        + _fetch(f'https://raw.githubusercontent.com/google/fonts/main/{lic}').decode().strip())
    with open(os.path.join(OUT, 'fonts', 'LICENSES.txt'), 'w', encoding='utf-8') as f:
        f.write('\n\n\n'.join(licenses) + '\n')


IMAGES = [paper, lambda: [mountain('peak0', 0, 100), mountain('peak1', 2, 120)], mist, cliff, stroke, splatter, flecks_r,
          band, swoosh, smear, lambda: [flame_rw('flame0', 401), flame_rw('flame1', 411)], splash_w, vortex, arc, seal, drybrush]


if __name__ == '__main__':
    what = set(sys.argv[1:]) or {'images', 'fonts'}
    os.makedirs(OUT, exist_ok=True)
    if 'images' in what:
        for step in IMAGES:
            step()
    if 'fonts' in what:
        fonts()
