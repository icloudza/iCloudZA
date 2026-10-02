#!/usr/bin/env python3
"""离线生成短片卡片用的位图素材和字体子集，产物提交进 assets/cinema/（CI 不跑这个脚本）

    python scripts/make_assets.py           # 全部重新生成
    python scripts/make_assets.py images    # 只生成位图（需要 numpy + Pillow）
    python scripts/make_assets.py fonts     # 只更新字体子集（需要网络、fontTools、brotli）

改了 cinema_svg.py 里的中文字幕或片名后要重跑 fonts，否则新出现的汉字会回退到系统字体。

- sky.webp     16:9 夜空：银河从群山背后斜向右上升起，穿过两排行星之间（海报背景，开场镜头也截取它的上半部分）
- planet.webp  气态行星条带纹理，水平可平铺；在 SVG 里滑动模拟自转
- fonts/       Cormorant Garamond、Noto Serif SC、Zhi Mang Xing 的子集，授权见 fonts/OFL.txt（SIL OFL 1.1）
"""

import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'assets', 'cinema')


def fbm(h, w, beta, seed, aniso=(1.0, 1.0)):
    """谱合成分形噪声：功率谱 ∝ f^-beta，天然在两个方向上可平铺；返回零均值单位方差"""
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


def gblur(a, s):
    """FFT 高斯模糊（反射填充避免边缘卷绕）"""
    pad = int(3 * s) + 2
    p = np.pad(a, pad, mode='reflect')
    fy = np.fft.fftfreq(p.shape[0])[:, None]
    fx = np.fft.rfftfreq(p.shape[1])[None, :]
    G = np.exp(-2 * np.pi ** 2 * s ** 2 * (fx ** 2 + fy ** 2))
    return np.fft.irfft2(np.fft.rfft2(p) * G, s=p.shape)[pad:-pad, pad:-pad]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def stars(h, w, n, seed, density=None, power=3.0):
    """按密度图撒星点，亮度服从幂律（大量暗星、少量亮星）"""
    r = np.random.default_rng(seed)
    if density is None:
        ys, xs = r.integers(0, h, n), r.integers(0, w, n)
    else:
        p = density.ravel() / density.sum()
        ys, xs = np.divmod(r.choice(h * w, size=n, p=p), w)
    img = np.zeros((h, w))
    np.add.at(img, (ys, xs), r.random(n) ** power)
    return img


def band_field(h, w, cx, cy, deg, u0, width, core_len, seed):
    """银河带：沿轴向的高斯截面 + 湍流扰动的中线 + 核球；返回 (带, 核, 横向坐标, 带宽)"""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    a = np.deg2rad(deg)
    u = (xx - cx) * np.cos(a) + (yy - cy) * np.sin(a)
    v = -(xx - cx) * np.sin(a) + (yy - cy) * np.cos(a)
    wb = width * (1 + .9 * np.exp(-((u - u0) / core_len) ** 2))
    vv = v + fbm(h, w, 3.3, seed) * width * .22
    band = np.exp(-(vv / wb) ** 2)
    core = np.exp(-((u - u0) / (core_len * .55)) ** 2 - (vv / (wb * .5)) ** 2)
    return band, core, vv, wb


def milky_way(h, w, cx, cy, deg, u0, width, core_len, seed, n_stars):
    band, core, vv, wb = band_field(h, w, cx, cy, deg, u0, width, core_len, seed)
    clouds = fbm(h, w, 2.9, seed + 1)
    fine = fbm(h, w, 2.0, seed + 2)
    neb = band * np.clip(.62 + .2 * clouds + .08 * fine, 0, None)
    # 暗尘带：低频脊状噪声，软边，集中在带中线略偏一侧
    ridge = 1 - np.abs(np.tanh(fbm(h, w, 3.1, seed + 3) * .8))
    lane = np.exp(-((vv - wb * .12) / (wb * .5)) ** 2)
    dust = smoothstep(.45, .92, ridge) * lane * (.5 + .5 * np.clip(clouds * .5 + .5, 0, 1))
    dust = np.clip(dust + .35 * np.exp(-((vv - wb * .08) / (wb * .16)) ** 2) * smoothstep(-.6, .6, fbm(h, w, 2.6, seed + 6)), 0, 1)
    dust = gblur(dust, 1.6)
    glow = (.7 * neb + 1.0 * core) * (1 - .82 * dust)
    warm = np.clip(core * 1.4, 0, 1)[..., None]
    outer = np.clip(1 - band * 1.2, 0, 1)[..., None]
    cool = np.array([.72, .78, .95]) * (1 - outer) + np.array([.42, .46, .7]) * outer
    img = glow[..., None] * (warm * np.array([1.0, .84, .62]) + (1 - warm) * cool)
    hii = np.clip(fbm(h, w, 2.2, seed + 4) - 2.3, 0, None) * band * (1 - dust) * .35
    img += hii[..., None] * np.array([.8, .36, .46])
    # 未分辨的恒星颗粒：密度跟着银河走，同样被尘埃遮挡
    dens = (.06 + band ** 1.1 + 2.2 * core) * (1 - .85 * dust)
    s = gblur(stars(h, w, n_stars, seed + 5, dens, power=4.0), .55) * .5
    img += s[..., None] * np.array([.9, .93, 1.0])
    return img


def tone(img, exposure):
    return 1 - np.exp(-img * exposure)


def finish(img, exposure=1.6):
    """胶片式色调映射，暗部略微抬向冷蓝"""
    out = tone(img, exposure) * .97 + np.array([.004, .007, .014])
    return np.clip(out, 0, 1) ** (1 / 1.05)


def save(img, name, q, alpha=None):
    rgb = (np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)
    if alpha is not None:
        rgb = np.dstack([rgb, (np.clip(alpha, 0, 1) * 255 + .5).astype(np.uint8)])
    Image.fromarray(rgb).save(f'{OUT}/{name}.webp', quality=q, method=6)
    print(f'{name}.webp', os.path.getsize(f'{OUT}/{name}.webp'), 'bytes')


def sky():
    """16:9 夜空：银河从地平线（群山背后）斜向右上升起，越往上越淡；地平线附近一层气辉"""
    h, w = 467, 830
    t = np.mgrid[0:h, 0:w][0] / h
    img = milky_way(h, w, w * .5, h * .49, -70, -h * .44, h * .085, h * .36, 30, 30000)
    img *= (.28 + .72 * smoothstep(-.05, .95, t))[..., None]
    base = np.stack([.005 + .028 * t ** 3.4, .008 + .042 * t ** 3.4, .018 + .07 * t ** 3.4], -1)
    glow = np.exp(-((1 - t) / .12) ** 2)[..., None] * np.array([.07, .065, .085])
    save(finish(img + base + glow), 'sky', 74)


def planet():
    h, w = 128, 420
    y = np.linspace(-1, 1, h)[:, None]
    yd = y + fbm(h, w, 2.8, 51, aniso=(1.0, 3.0)) * .05
    bands = np.sin(yd * 8.5 + .9 * np.sin(yd * 2.7)) * .5 + np.sin(yd * 21 + 1.3) * .22 + np.sin(yd * 47 + .4) * .1
    L = .5 + .32 * bands + .07 * fbm(h, w, 1.8, 52, aniso=(1.0, 4.0))
    # 两个风暴眼（水平方向按周期取距离，保证纹理首尾相接）
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    for cx, cy, rx, ry, s in ((120, 80, 22, 7, -.28), (310, 41, 13, 5, .22)):
        dx = (xx - cx + w / 2) % w - w / 2
        L += s * np.exp(-(dx / rx) ** 2 - ((yy - cy) / ry) ** 2)
    save(np.repeat(np.clip(L, 0, 1)[..., None], 3, -1), 'planet', 72)


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
    """用 Google Fonts 的 text= 参数只下载用到的字形，再把可变字体固定成单一字重（体积约减半）"""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    sys.path.insert(0, HERE)
    from cinema_svg import FONT_FILES, brush_chars, zh_chars

    ascii_ = ''.join(chr(c) for c in range(0x20, 0x7f))
    jobs = [   # (Google Fonts 家族, 字重, 需要的字, 输出文件, google/fonts 仓库里的 OFL 目录)
        ('Cormorant Garamond', 500, ascii_ + '·–—‘’“”…\u00a0\u2002\u2003', FONT_FILES['CG'], 'cormorantgaramond'),
        ('Noto Serif SC', 500, zh_chars(), FONT_FILES['NS'], 'notoserifsc'),
        ('Zhi Mang Xing', 400, brush_chars(), FONT_FILES['ZM'], 'zhimangxing'),
    ]
    os.makedirs(f'{OUT}/fonts', exist_ok=True)
    licenses = []
    for family, weight, text, fn, ofl in jobs:
        css = _fetch(f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}:wght@{weight}"
                     f"&text={urllib.parse.quote(text)}").decode()
        font = TTFont(io.BytesIO(_fetch(re.search(r'url\(([^)]+)\)', css).group(1))))
        if 'fvar' in font:
            font = instancer.instantiateVariableFont(font, {'wght': weight})
        font.flavor = 'woff2'
        font.save(f'{OUT}/fonts/{fn}')
        missing = [ch for ch in text if ord(ch) not in font.getBestCmap() and not ch.isspace()]
        print(f'fonts/{fn}', os.path.getsize(f'{OUT}/fonts/{fn}'), 'bytes', 'missing:', ''.join(missing) or '-')
        if ofl:
            licenses.append(f'===== {family} =====\n\n'
                            + _fetch(f'https://raw.githubusercontent.com/google/fonts/main/ofl/{ofl}/OFL.txt').decode().strip())
    with open(f'{OUT}/fonts/OFL.txt', 'w', encoding='utf-8') as f:
        f.write('\n\n\n'.join(licenses) + '\n')


if __name__ == '__main__':
    what = set(sys.argv[1:]) or {'images', 'fonts'}
    os.makedirs(OUT, exist_ok=True)
    if 'images' in what:
        for step in (sky, planet):
            step()
    if 'fonts' in what:
        fonts()
