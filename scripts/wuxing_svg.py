#!/usr/bin/env python3
"""《五行》：把这一年的语言统计渲染成一支约 25 秒的水墨动画 SVG（运行时无第三方依赖）

五行既是金木水火土，也是「五行代码」：这一年写得最多的五种语言化作五行，按相生的顺序
木 → 火 → 土 → 金 → 水 倒数登场（第五名到第一名），最后定格成一张一直在动的海报。
画面只用纸白、焦墨、朱红三色（结尾「万行」一段才放出青蓝和金）：干笔浓墨、横扫的朱红笔触带（下沿带滴痕），
大字按笔顺一块块「跳」出来，旁边配手写体的小字；入画和运镜按格跳（一拍二的顿挫），转场用刀光、负片、甩镜、红闪。

性能约定（GitHub 用 <img> 显示 SVG，任何一处动画在跑，整张图每帧都要重绘）：
- 镜头只在自己的时间窗内可见，窗口外是 visibility:hidden，不参与绘制；镜头里的动画都是有限次；
- 海报出现前整组 visibility:hidden；海报上的环境动画只动透明度和位移，长周期、缓入缓出。
静态属性即终态：动画不运行的环境（含 prefers-reduced-motion）直接显示海报帧。
位图素材和字体子集在 assets/ink/，由 make_assets.py 离线生成后提交，渲染时 base64 内嵌。
"""

import base64
import math
import os
import random
from html import escape

W, H = 830, 467
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'ink')

PAPER, INK, VERM, VERM_D, WHITE = '#e9e5dc', '#141110', '#e8381c', '#9c1d0c', '#fbf9f4'
NAVY, CYAN, GOLD = '#0a1322', '#8fe3ff', '#f2c46c'

YB = "YB,'Yuji Boku','Ma Shan Zheng',KaiTi,STKaiti,serif"
PM = "PM,'Permanent Marker','Marker Felt','Comic Sans MS',cursive"
LJ = "LJ,'Liu Jian Mao Cao',STXingkai,cursive"
FONT_FILES = {'YB': 'yb400.woff2', 'PM': 'pm400.woff2', 'LJ': 'lj400.woff2'}

# 五行（相生的顺序：木生火，火生土，土生金，金生水），倒数登场：第五名是木，第一名是水
ELEMS = [('木', 'WOOD'), ('火', 'FIRE'), ('土', 'EARTH'), ('金', 'METAL'), ('水', 'WATER')]
WALL = '木生火火生土土生金金生水水生木'
TITLE, SEAL = '五行', '万行'
# 大字的「笔顺」：按书写顺序一块块露出来（字身方框里的归一化坐标 x0, y0, x1, y1）
STROKES = {
    '木': [(0, .18, 1, .44), (.4, 0, .62, 1), (0, .4, .52, 1), (.48, .4, 1, 1)],
    '火': [(.02, .18, .38, .62), (.6, .12, 1, .56), (.28, 0, .64, 1), (.5, .44, 1, 1)],
    '土': [(.15, .22, .85, .46), (.4, 0, .62, .9), (0, .72, 1, 1)],
    '金': [(0, 0, .56, .52), (.44, 0, 1, .52), (.22, .34, .78, .56), (.12, .5, .88, .68), (.4, .42, .62, 1), (.06, .58, .5, .92), (0, .8, 1, 1)],
    '水': [(.36, 0, .64, 1), (0, .22, .46, .74), (.02, .5, .46, 1), (.54, .16, 1, 1)],
    '五': [(.04, .02, .96, .26), (.24, .14, .52, .84), (.18, .38, .84, .86), (0, .76, 1, 1)],
    '行': [(0, 0, .4, 1), (.38, .04, 1, .3), (.34, .28, 1, .52), (.52, .4, .9, 1)],
    '万': [(0, .02, 1, .3), (.2, .18, .62, 1), (.4, .32, 1, 1)],
}


def cjk_chars() -> str:
    """大字字体（Yuji Boku）要的字：五行、片名、印文"""
    return ''.join(sorted(set(''.join(e for e, _ in ELEMS) + TITLE + SEAL)))


def wall_chars() -> str:
    """诗墙草书（Liu Jian Mao Cao）要的字"""
    return ''.join(sorted(set(WALL)))


def latin_chars() -> str:
    """手写体（Permanent Marker）要的字：画面上的英文全部大写，语言名里还会出现 # 和 +"""
    return ''.join(chr(c) for c in range(ord('A'), ord('Z') + 1)) + '0123456789 .,%#+·—'



BASE_CSS = (
    "@keyframes §in{from{opacity:0}}"
    "@keyframes §out{to{opacity:0}}"
    "@keyframes §show{from{opacity:0;visibility:hidden}}"
    "@keyframes §pop{from{opacity:0;transform:scale(.2)}40%{opacity:1}}"
    "@keyframes §stamp{0%{opacity:0;transform:scale(1.9)}55%{opacity:1;transform:scale(.93)}100%{opacity:1;transform:scale(1)}}"
    "@keyframes §shake{0%{transform:translate(0,0)}15%{transform:translate(-9px,5px)}30%{transform:translate(8px,-6px)}"
    "45%{transform:translate(-5px,3px)}60%{transform:translate(4px,-2px)}80%{transform:translate(-2px,1px)}100%{transform:translate(0,0)}}"
    "@keyframes §flick{0%,100%{opacity:1}50%{opacity:.15}}"
    "@keyframes §drift{from{transform:translateX(-22px)}to{transform:translateX(22px)}}"
    "@keyframes §breathe{50%{opacity:.55}}"
    "@keyframes §bob{from{transform:translateY(-3px)}to{transform:translateY(3px)}}"
    ".§c{transform-box:fill-box;transform-origin:50% 50%}"
    ".§b{transform-box:fill-box;transform-origin:50% 100%}"
    ".§l{transform-box:fill-box;transform-origin:0 50%}"
    "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
)

SPRITES = {
    'paper': (830, 467), 'mist': (640, 150), 'splatter': (360, 220), 'stroke': (760, 110),
    'vortex': (460, 460), 'arc': (600, 320), 'seal': (112, 112), 'peak0': (300, 240), 'peak1': (300, 240),
    'band': (1000, 260), 'swoosh': (560, 300), 'smear': (415, 234), 'cliff': (420, 360), 'splash_w': (420, 320),
    'flecks_r': (360, 220), 'flame0': (300, 420), 'flame1': (300, 420), 'dry_k': (160, 160), 'dry_w': (160, 160), 'dry_r': (160, 160),
}
PEAK_TOP, PEAK_FOOT = 18, 200


def _n(v: float, d: int = 1) -> str:
    s = f"{v:.{d}f}".rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def _i(v: float) -> str:
    """取整的坐标（大块的笔触不需要小数）"""
    return str(round(v)) if round(v) else '0'



def _asset(name: str) -> str:
    with open(os.path.join(ASSET_DIR, name), 'rb') as f:
        return base64.b64encode(f.read()).decode()


class _Film:
    """画布：收集 defs / CSS / 图元，输出时把 § 换成前缀（内联到网页里时 id 和动画名不会撞车）"""

    def __init__(self, uid: str, seed: int, label: str):
        self.uid, self.label = uid, label
        self.rng = random.Random(seed)
        self.defs, self.css = [], [BASE_CSS]
        self._ids, self._cache, self._kf = 0, {}, {}

    def nid(self, p: str = 'i') -> str:
        self._ids += 1
        return f"§{p}{self._ids}"

    def kf(self, frames: str) -> str:
        if frames not in self._kf:
            name = self.nid('k')
            self._kf[frames] = name
            self.css.append(f"@keyframes {name}{{{frames}}}")
        return self._kf[frames]

    def _grad(self, kind, stops, attrs):
        key = (kind, tuple(stops), tuple(attrs.items()))
        if key not in self._cache:
            gid = self.nid('g')
            a = ''.join(f' {k}="{v}"' for k, v in attrs.items())
            s = ''.join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{op}"' if op != 1 else '') + '/>'
                        for o, c, op in stops)
            self.defs.append(f'<{kind}Gradient id="{gid}"{a}>{s}</{kind}Gradient>')
            self._cache[key] = gid
        return self._cache[key]

    def lin(self, stops, x1=0, y1=0, x2=1, y2=0):
        return self._grad('linear', stops, dict(x1=x1, y1=y1, x2=x2, y2=y2))

    def rad(self, stops, cx=.5, cy=.5, r=.5):
        return self._grad('radial', stops, dict(cx=cx, cy=cy, r=r))

    def sprite(self, name: str) -> str:
        key = ('img', name)
        if key not in self._cache:
            iid = self.nid('m')
            w, h = SPRITES[name]
            self.defs.append(f'<image id="{iid}" width="{w}" height="{h}" preserveAspectRatio="none" '
                             f'href="data:image/webp;base64,{_asset(name + ".webp")}"/>')
            self._cache[key] = iid
        return self._cache[key]

    def use(self, name: str, x: float = 0, y: float = 0, sx: float = 1, sy: float = None, extra: str = '') -> str:
        sy = sx if sy is None else sy
        t = f'translate({_n(x)} {_n(y)})' + (f' scale({sx:.4g} {sy:.4g})' if (sx, sy) != (1, 1) else '')
        return f'<use href="#{self.sprite(name)}" transform="{t}"{extra}/>'

    def pattern(self, name: str) -> str:
        """干笔纹理做成可平铺的填充"""
        key = ('pat', name)
        if key not in self._cache:
            pid = self.nid('p')
            self.defs.append(f'<pattern id="{pid}" width="160" height="160" patternUnits="userSpaceOnUse">'
                             f'<use href="#{self.sprite(name)}"/></pattern>')
            self._cache[key] = pid
        return self._cache[key]

    # ---------- 时间轴 ----------

    def window(self, t0: float, t1: float, body: str, fade: float = .02, fade_in: float = None) -> str:
        """只在 [t0, t1] 出现的镜头：窗口外 visibility:hidden；默认是硬切"""
        d = t1 - t0
        f = min(fade / d * 100, 45)
        fi = f if fade_in is None else min(fade_in / d * 100, 45)
        k = self.kf(f"0%{{visibility:visible;opacity:0}}{fi:.2f}%{{opacity:1}}{100 - f:.2f}%{{opacity:1}}"
                    f"100%{{visibility:visible;opacity:0}}")
        return f'<g visibility="hidden" opacity="0" style="animation:{k} {d:.2f}s linear {t0:.2f}s">{body}</g>'

    def camera(self, body: str, cx: float, cy: float, s0: float, s1: float, t0: float, dur: float,
               dx: float = 0, dy: float = 0, r0: float = 0, r1: float = 0, steps: int = 0) -> str:
        """运镜：以 (cx, cy) 为中心推拉、平移、侧倾；steps>0 时按格跳（一拍二的顿挫）"""
        k = self.kf(f"from{{transform:rotate({r0}deg) scale({s0})}}"
                    f"to{{transform:translate({dx}px,{dy}px) rotate({r1}deg) scale({s1})}}")
        ease = f'steps({steps})' if steps else 'ease-in-out'
        return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g style="animation:{k} {dur:.2f}s {ease} {t0:.2f}s both">'
                f'<g transform="translate({_n(-cx)} {_n(-cy)})">{body}</g></g></g>')

    def shake(self, body: str, times) -> str:
        anim = ','.join(f'§shake .3s steps(6) {t:.2f}s' for t in times)
        return f'<g style="animation:{anim}">{body}</g>'

    # ---------- 笔墨 ----------

    def glyph(self, ch: str, x: float, y: float, size: float, tex: str = 'dry_k', t: float = None, step: float = .1,
              outline: str = None, anchor_c: bool = False) -> str:
        """一个大字：干笔纹理填充；t 给定时按笔顺一块块「跳」出来（每块停一拍）"""
        if anchor_c:
            x, y = x - size / 2, y + size * .38
        fill = f'url(#{self.pattern(tex)})'
        stroke = (f' stroke="{outline}" stroke-width="{_n(size * .035)}" paint-order="stroke" stroke-linejoin="round"'
                  if outline else '')
        text = f'<text x="{_n(x)}" y="{_n(y)}" font-family="{YB}" font-size="{_n(size)}" fill="{fill}"{stroke}>{escape(ch)}</text>'
        if t is None:
            return text
        clip = self.nid('c')
        top = y - size * .9
        rects = ''.join(f'<rect x="{_i(x + x0 * size - 2)}" y="{_i(top + y0 * size - 2)}" width="0" height="{_i((y1 - y0) * size + 4)}">'
                        f'<set attributeName="width" to="{_i((x1 - x0) * size + 4)}" begin="{t + i * step:.2f}s"/></rect>'
                        for i, (x0, y0, x1, y1) in enumerate(STROKES.get(ch, [(0, 0, 1, 1)])))
        self.defs.append(f'<clipPath id="{clip}">{rects}</clipPath>')
        return f'<g clip-path="url(#{clip})">{text}</g>'

    def band(self, cx: float, cy: float, length: float, thick: float, angle: float, t: float = None,
             dur: float = .3, flip: bool = False, name: str = 'band') -> str:
        """一大笔横扫的笔触带（朱红 band / 焦墨 stroke）：中心 (cx, cy)，沿 angle 方向；t 给定时分四格「刷」进画面"""
        if name == 'band':
            sx, sy = length / 1000, thick / 100
            img = self.use('band', -500 * sx, -120 * sy, sx, sy)
        else:
            sx, sy = length / 760, thick / 88
            img = self.use(name, -380 * sx, -55 * sy, sx, sy)
        if flip:
            img = f'<g transform="scale(-1 1)">{img}</g>'
        if t is None:
            return f'<g transform="translate({_n(cx)} {_n(cy)}) rotate({angle})">{img}</g>'
        clip = self.nid('c')
        L = length + 40
        vals = ';'.join(_n(L * min(k, 4) / 4) for k in range(1, 6))     # 第一格就刷出四分之一，切进来不是白纸
        flip_t = ' transform="scale(-1 1)"' if flip else ''
        self.defs.append(f'<clipPath id="{clip}"><rect x="{_n(-L / 2)}" y="{_n(-thick * 2)}" width="0" height="{_n(thick * 4)}"{flip_t}>'
                         f'<animate attributeName="width" values="{vals}" keyTimes="0;.25;.5;.75;1" calcMode="discrete" '
                         f'begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        return f'<g transform="translate({_n(cx)} {_n(cy)}) rotate({angle})"><g clip-path="url(#{clip})">{img}</g></g>'

    def brush_bar(self, x: float, y: float, length: float, thick: float) -> str:
        """一笔横画（条形图用）：圆头起笔，收笔处一小段飞白"""
        return self.use('stroke', x, y - thick / 2 - thick * .1, length / 760, thick / 88)

    def mist(self, x: float, y: float, w: float, h: float, op: float, drift: tuple = None) -> str:
        """一条雾带（纸色 = 留白）；drift=(开始秒, 周期) 时左右缓慢飘移，无限循环"""
        img = f'<use href="#{self.sprite("mist")}" transform="translate({_n(x)} {_n(y)}) scale({w / 640:.4g} {h / 150:.4g})" opacity="{op}"/>'
        if drift:
            return f'<g style="animation:§drift {drift[1]}s ease-in-out {drift[0]:.1f}s infinite alternate">{img}</g>'
        return img

    def seal_v(self, text: str, x: float, y: float, size: float) -> str:
        """竖排的朱印（白文）"""
        n = len(text)
        w, h = size, size * (.92 * n + .2)
        chars = ''.join(f'<text x="0" y="{_n(-h / 2 + size * .1 + (i + .84) * size * .92)}" font-family="{YB}" '
                        f'font-size="{_n(size * .8)}" text-anchor="middle" fill="{PAPER}">{escape(ch)}</text>'
                        for i, ch in enumerate(text))
        return (f'<g transform="translate({_n(x)} {_n(y)})"><g class="§c" style="animation:§stamp .5s cubic-bezier(.3,0,.2,1) 25.6s both">'
                + self.use('seal', -w / 2, -h / 2, w / 112, h / 112) + chars + '</g></g>')

    def splat(self, x: float, y: float, angle: float, s: float, t: float, name: str = 'splatter', op: float = 1) -> str:
        return (f'<g transform="translate({_n(x)} {_n(y)}) rotate({angle:.0f}) scale({s:.3g})">'
                f'<g class="§l" style="animation:§pop .3s steps(3) {t:.2f}s both">'
                + self.use(name, -8, -110, extra=f' opacity="{op}"' if op != 1 else '') + '</g></g>')

    def caption(self, x: float, y: float, rank: int, lang: str, pct: float, lines: int, t: float,
              ink: str = INK, accent: str = VERM, halo: str = PAPER, align: str = 'start') -> str:
        """手写体的标注：排名 + 语言名 + 占比 + 行数（逐行跳出来）"""
        anchor = f' text-anchor="{align}"' if align != 'start' else ''
        halo_s = f' stroke="{halo}" stroke-width="4" paint-order="stroke" stroke-linejoin="round"'
        if lang is None:
            rows = [(f'<text x="{_n(x)}" y="{_n(y)}"{anchor} font-family="{PM}" font-size="20" fill="{ink}"{halo_s}>—</text>', 0)]
        else:
            rows = [(f'<text x="{_n(x)}" y="{_n(y - 46)}"{anchor} font-family="{PM}" font-size="15" letter-spacing="2" fill="{ink}"{halo_s}>'
                     f'NO.{rank}</text>', 0),
                    (f'<text x="{_n(x)}" y="{_n(y - 14)}"{anchor} font-family="{PM}" font-size="30" fill="{ink}"{halo_s}>{escape(lang.upper())}</text>', .08),
                    (f'<text x="{_n(x)}" y="{_n(y + 36)}"{anchor} font-family="{PM}" font-size="50" fill="{accent}"{halo_s}>{pct:.1f}%</text>', .16),
                    (f'<text x="{_n(x)}" y="{_n(y + 60)}"{anchor} font-family="{PM}" font-size="13" letter-spacing="1.5" fill="{ink}"{halo_s}>'
                     f'{lines:,} LINES</text>', .24)]
        return ''.join(f'<g style="animation:§in .01s linear {t + d:.2f}s both">{r}</g>' for r, d in rows)

    def particles(self, n: int, seed: int, t0: float, dur: float, make, area, vel, spin: float = 0, grav: float = 0) -> str:
        """一把粒子：从 area 里随机出发，沿 vel 方向飞（带旋转和下坠）；make(rng) 返回粒子的图形。
        关键帧只有三组（旋转方向不同），每个粒子的方向和远近用父级的 rotate / scale 表达（近的大、飞得远），
        CSS 不随粒子数增长"""
        r = random.Random(seed)
        ks = [self.kf(f"0%{{opacity:0;transform:translate(0,0) rotate(0deg)}}10%{{opacity:1}}"
                      f"50%{{transform:translate({vel[0] * .5:.0f}px,{vel[1] * .5 + grav * .25:.0f}px) rotate({spin * v * .5:.0f}deg)}}"
                      f"85%{{opacity:1}}100%{{opacity:0;transform:translate({vel[0]:.0f}px,{vel[1] + grav:.0f}px) rotate({spin * v:.0f}deg)}}")
              for v in (1, -1, .5)]
        out = []
        x0, y0, x1, y1 = area
        for i in range(n):
            x, y = r.uniform(x0, x1), r.uniform(y0, y1)
            sc, a = r.uniform(.6, 1.4), r.uniform(-14, 14)
            d = dur * r.uniform(.7, 1.1)
            t = t0 + r.uniform(0, dur * .5)
            out.append(f'<g transform="translate({_n(x, 0)} {_n(y, 0)}) rotate({a:.0f}) scale({sc:.2f})">'
                       f'<g style="animation:{ks[i % 3]} {d:.2f}s linear {t:.2f}s both">{make(r)}</g></g>')
        return ''.join(out)

    def svg(self, layers: str) -> str:
        font_css = ''.join(f"@font-face{{font-family:{k};src:url(data:font/woff2;base64,{_asset('fonts/' + f)}) format('woff2')}}"
                           for k, f in FONT_FILES.items())
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
               f'aria-label="{escape(self.label)}"><title>{escape(self.label)}</title>'
               f'<style>{font_css}{"".join(self.css)}</style>'
               f'<defs><clipPath id="§frame"><rect width="{W}" height="{H}" rx="10"/></clipPath>{"".join(self.defs)}</defs>'
               f'<g clip-path="url(#§frame)"><rect width="{W}" height="{H}" fill="{PAPER}"/>{self.use("paper")}{layers}</g></svg>')
        return out.replace('§', self.uid)


# ---------- 数据 ----------

def _rows(stats: dict, top_n: int = 5):
    rows = sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)[:top_n]
    total = sum(v['added'] + v['deleted'] for v in stats.values())
    return [(lang, v['added'] + v['deleted']) for lang, v in rows if v['added'] + v['deleted']], total


# ---------- 画面元素 ----------

def _peaks(c: _Film, specs) -> str:
    out = []
    for x, foot, ph, pw, k, flip in specs:
        sx, sy = pw / 300, ph / (PEAK_FOOT - PEAK_TOP)
        ty = foot - PEAK_FOOT * sy
        if flip:
            out.append(f'<use href="#{c.sprite(f"peak{k}")}" transform="translate({_n(x + pw / 2)} {_n(ty)}) scale({-sx:.4g} {sy:.4g})"/>')
        else:
            out.append(f'<use href="#{c.sprite(f"peak{k}")}" transform="translate({_n(x - pw / 2)} {_n(ty)}) scale({sx:.4g} {sy:.4g})"/>')
    return ''.join(out)


def _cloud(c: _Film, x: float, y: float, s: float, flip: bool = False) -> str:
    """祥云：几个卷成螺旋的云头连成一朵，后面拖一条流云；先描一遍粗黑边再填白，外轮廓干净、里面不露接缝。
    形状只在 defs 里画一次，各处用 <use> 摆放"""
    if ('cloud',) not in c._cache:
        cid = c.nid('u')
        heads = [(0, 0, 15), (25, -11, 19), (52, -3, 14), (-20, 6, 10)]
        shapes = (''.join(f'<circle cx="{cx}" cy="{cy}" r="{r}"/>' for cx, cy, r in heads)
                  + '<path d="M-28 10Q10 22 60 10Q100 0 150 12Q104 16 58 18Q14 26 -26 16Z"/>')
        spirals = ''.join(f'<path d="M{_n(cx + r * .72)} {_n(cy)}A{_n(r * .72)} {_n(r * .72)} 0 0 0 {_n(cx - r * .72)} {_n(cy)}'
                          f'A{_n(r * .5)} {_n(r * .5)} 0 0 0 {_n(cx + r * .28)} {_n(cy)}A{_n(r * .28)} {_n(r * .28)} 0 0 0 {_n(cx - r * .2)} {_n(cy)}"/>'
                          for cx, cy, r in heads)
        c.defs.append(f'<g id="{cid}"><g fill="{INK}" stroke="{INK}" stroke-width="4.4" stroke-linejoin="round">{shapes}</g>'
                      f'<g fill="{WHITE}">{shapes}</g>'
                      f'<g fill="none" stroke="{INK}" stroke-width="1.8" stroke-linecap="round">{spirals}<path d="M30 14Q80 6 132 12"/></g></g>')
        c._cache[('cloud',)] = cid
    sx = -s if flip else s
    return f'<use href="#{c._cache[("cloud",)]}" transform="translate({_n(x)} {_n(y)}) scale({sx:.3g} {s:.3g})"/>'


def _bamboo(c: _Film, x: float, foot: float, length: float, thick: float, angle: float, seed: int, red_leaf: bool = False) -> str:
    """浓墨竹竿：一节节黑竿，左侧一道断续的留白高光，节处留一线白；竿顶几簇刀叶"""
    r = random.Random(seed)
    n = max(3, round(length / 70))
    seg = length / n
    out = []
    for i in range(n):
        y1, y2 = -i * seg - (2 if i else 0), -(i + 1) * seg + 2
        w = thick * (1 - .18 * i / n)
        out.append(f'<path d="M{_i(-w * .55)} {_i(y1)}Q{_i(-w * .42)} {_i((y1 + y2) / 2)} {_i(-w * .55)} {_i(y2)}L{_i(w * .55)} {_i(y2)}'
                   f'Q{_i(w * .42)} {_i((y1 + y2) / 2)} {_i(w * .55)} {_i(y1)}Z" fill="{INK}"/>'
                   f'<path d="M{_i(-w * .22)} {_i(y1 - r.uniform(5, 14))}Q{_i(-w * .3)} {_i((y1 + y2) / 2)} {_i(-w * .2)} {_i(y2 + r.uniform(8, 24))}" '
                   f'stroke="{WHITE}" stroke-width="{_i(w * .12)}" fill="none" stroke-linecap="round" opacity=".8"/>'
                   + (f'<path d="M{_i(-w * .8)} {_i(y2 - 1)}Q0 {_i(y2 - 6)} {_i(w * .8)} {_i(y2 - 1)}" stroke="{INK}" stroke-width="3" fill="none" stroke-linecap="round"/>'
                      if i < n - 1 else ''))
    leaves = []
    for j in range(r.randint(5, 8)):
        by = -length * r.uniform(.55, .98)
        ang = r.choice([-1, 1]) * r.uniform(20, 75) + (180 if r.random() < .5 else 0)
        ln = r.uniform(46, 80)
        wd = ln * .16
        col = VERM if red_leaf and j == 0 else INK
        leaves.append(f'<g transform="translate(0 {_i(by)}) rotate({ang:.0f})"><path d="M0 0Q{_i(ln * .3)} {_i(-wd)} {_i(ln)} 0'
                      f'Q{_i(ln * .3)} {_i(wd * .5)} 0 0Z" fill="{col}"/></g>')
    return f'<g transform="translate({_i(x)} {_i(foot)}) rotate({angle})">{"".join(out)}{"".join(leaves)}</g>'


def _shape(c: _Film, key: str, body: str) -> str:
    """反复出现的小图形（飞叶、碎石）只在 defs 里画一次"""
    if ('shape', key) not in c._cache:
        sid = c.nid('u')
        c.defs.append(f'<g id="{sid}">{body}</g>')
        c._cache[('shape', key)] = sid
    return f'<use href="#{c._cache[("shape", key)]}"/>'


def _leaf(c: _Film, r) -> str:
    red = r.random() < .22
    return _shape(c, 'leaf-r' if red else 'leaf-k', f'<path d="M0 0Q8 -4.6 26 0Q8 2.4 0 0Z" fill="{VERM if red else INK}"/>')


def _rock(c: _Film, r) -> str:
    k = r.randrange(3)
    pts = ('M0 0L7 -4L12 4L4 10Z', 'M0 0L5 -6L11 -1L8 7L2 6Z', 'M0 0L9 -3L10 5L3 8Z')[k]
    return _shape(c, f'rock{k}', f'<path d="{pts}" fill="{INK}"/>')


def _sword(L: float = 560) -> str:
    """一把剑（剑尖朝 +x）：白刃黑边、中脊一线，黑剑格、缠红绳的剑柄、红剑穗"""
    return (f'<path d="M-118 0C-150 20 -170 40 -200 46M-118 0C-146 30 -160 58 -186 74M-118 0C-140 10 -168 18 -196 16" '
            f'stroke="{VERM}" stroke-width="3.2" fill="none" stroke-linecap="round"/>'
            f'<circle cx="-118" r="10" fill="{INK}"/>'
            f'<rect x="-112" y="-8" width="104" height="16" rx="3" fill="{INK}"/>'
            + ''.join(f'<path d="M{-106 + k * 14} -8L{-96 + k * 14} 8" stroke="{VERM}" stroke-width="2.4"/>' for k in range(7))
            + f'<path d="M-8 -34Q2 -20 8 -12L8 12Q2 20 -8 34L-16 30Q-8 16 -8 0Q-8 -16 -16 -30Z" fill="{INK}"/>'
            f'<path d="M8 -11L{_n(L - 46)} -8L{_n(L)} 0L{_n(L - 46)} 8L8 11Z" fill="{WHITE}" stroke="{INK}" stroke-width="2.6" stroke-linejoin="round"/>'
            f'<path d="M10 0L{_n(L - 36)} 0" stroke="{INK}" stroke-width="1"/>')


def _ring(cx: float, cy: float, R: float, w: float, seed: int, fill: str = VERM, gap: float = 30) -> str:
    """一笔圆相（朱红）：起笔重、收笔轻，留一个口"""
    r = random.Random(seed)
    pts_o, pts_i = [], []
    a0 = r.uniform(0, 360)
    n = 60
    for k in range(n + 1):
        u = k / n
        a = math.radians(a0 + u * (360 - gap))
        ww = w * (1 - .75 * u ** 1.6) * (1 + .15 * math.sin(u * 17 + seed))
        rr = R + 2 * math.sin(u * 9 + seed)
        pts_o.append((cx + (rr + ww / 2) * math.cos(a), cy + (rr + ww / 2) * math.sin(a)))
        pts_i.append((cx + (rr - ww / 2) * math.cos(a), cy + (rr - ww / 2) * math.sin(a)))
    d = 'M' + 'L'.join(f"{x:.0f} {y:.0f}" for x, y in pts_o + pts_i[::-1]) + 'Z'
    return f'<path d="{d}" fill="{fill}"/>'


def _bolt(x0, y0, x1, y1, seed, depth=4):
    """闪电：中点位移"""
    r = random.Random(seed)
    pts = [(x0, y0), (x1, y1)]
    disp = math.hypot(x1 - x0, y1 - y0) * .22
    for _ in range(depth):
        nxt = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            nx, ny = -(by - ay), bx - ax
            ln = math.hypot(nx, ny) or 1
            off = r.uniform(-disp, disp)
            nxt += [(mx + nx / ln * off, my + ny / ln * off), (bx, by)]
        pts = nxt
        disp *= .55
    return 'M' + 'L'.join(f"{x:.0f} {y:.0f}" for x, y in pts)


# ---------- 转场 ----------

def _cut_swoosh(c: _Film, t: float, d: float = .26) -> str:
    """黑底上一道红色弧形刀光（两三格）"""
    k = c.kf("0%{transform:rotate(-24deg) scale(.7)}100%{transform:rotate(16deg) scale(1.15)}")
    return c.window(t, t + d, f'<rect width="{W}" height="{H}" fill="#140605"/>'
                    f'<g transform="translate(415 330)"><g style="animation:{k} {d:.2f}s steps(3) {t:.2f}s both">'
                    + c.use('swoosh', -400, -330, 1.43, 1.1) + '</g></g>')


def _cut_smear(c: _Film, t: float, d: float = .2, flip: bool = False) -> str:
    """甩镜头：整屏横向拖影"""
    k = c.kf(f"from{{transform:translateX({'-' if flip else ''}260px)}}to{{transform:translateX({'' if flip else '-'}260px)}}")
    return c.window(t, t + d, f'<g style="animation:{k} {d:.2f}s steps(3) {t:.2f}s both">'
                    + c.use('smear', -300, 0, 3.4, 2.0) + '</g>')


def _cut_negative(c: _Film, t: float, d: float = .12, seed: int = 1) -> str:
    """负片闪：黑底，几道红色折线"""
    r = random.Random(seed)
    zz = ''.join(f'<path d="M{_n(x)} -10L{_n(x + r.uniform(-60, 60))} {_n(r.uniform(150, 300))}L{_n(x + r.uniform(-90, 90))} 480" '
                 f'stroke="{VERM}" stroke-width="{r.uniform(8, 16):.1f}" fill="none" stroke-linejoin="miter"/>'
                 for x in (r.uniform(40, 160), r.uniform(220, 360), r.uniform(420, 560), r.uniform(620, 780)))
    return c.window(t, t + d, f'<rect width="{W}" height="{H}" fill="#0c0908"/>{zz}')


def _cut_red(c: _Film, t: float, d: float = .08) -> str:
    return c.window(t, t + d, f'<rect width="{W}" height="{H}" fill="{VERM}"/>')


# ---------- 成片 ----------

def render_film(weekly: dict, weekly_days: int, yearly: dict, yearly_days: int, commits: int, uid: str = 'F') -> str:
    """weekly / yearly: {语言: {'added', 'deleted'}}；commits: yearly_days 窗口内的提交次数"""
    yrows, ytotal = _rows(yearly)
    wrows, wtotal = _rows(weekly)
    n_langs = sum(1 for v in yearly.values() if v['added'] + v['deleted'])
    ranked = [(yrows[i] if i < len(yrows) else None) for i in range(5)]   # 第一名 … 第五名

    def pct(i):
        return ranked[i][1] / ytotal * 100 if ranked[i] and ytotal else 0
    label = ("THE FIVE ELEMENTS — " + f"{ytotal:,} lines in {yearly_days} days, {n_langs} languages. "
             + '; '.join(f"{ELEMS[4 - i][1].title()}: {ranked[i][0]} {pct(i):.1f}%" for i in range(5) if ranked[i])
             + f". This week: {wtotal:,} lines.")
    c = _Film(uid, 5, label)
    shots = []

    # ===== 片头 0–2.45s：黑白山日 → 一帧负片 → 红天 → 日食成月牙 → 红色刀光 =====
    rng = random.Random(3)
    specs = [(x, 330, rng.uniform(70, 150), rng.uniform(170, 260), rng.randrange(2), rng.random() < .5) for x in range(-20, W + 80, 92)]
    sky_bw = c.lin([(0, '#c9c4ba', 1), (1, '#e9e5dc', 1)], x2=0, y2=1)
    ground = (f'<path d="M-10 322Q200 312 415 318T840 320L840 480L-10 480Z" fill="{INK}"/>')
    clouds = (_cloud(c, 120, 196, 1.1) + _cloud(c, 560, 176, 1.3, True) + _cloud(c, 300, 214, .8) + _cloud(c, 700, 232, .9))
    drift = c.kf("from{transform:translateX(-14px)}to{transform:translateX(14px)}")
    title0 = (c.glyph('五', W / 2 - 112, 446, 108, 'dry_w', t=.1, step=.05) + c.glyph('行', W / 2 + 4, 446, 108, 'dry_w', t=.34, step=.05))
    bw = (f'<rect width="{W}" height="{H}" fill="url(#{sky_bw})"/><circle cx="415" cy="170" r="76" fill="{WHITE}"/>'
          f'<g style="animation:{drift} 2.4s linear 0s both">{clouds}</g>'
          + f'<g opacity=".95">{_peaks(c, specs)}</g>' + ground + title0)
    glitch = (f'<rect width="{W}" height="300" fill="#7fd3cf"/><rect y="300" width="{W}" height="200" fill="#6d0905"/>'
              f'<circle cx="415" cy="170" r="76" fill="#d7fffb"/>')
    eclipse = c.kf("from{transform:translateX(-160px)}to{transform:translateX(-30px)}")
    sun_clip = c.nid('c')
    c.defs.append(f'<clipPath id="{sun_clip}"><circle cx="415" cy="170" r="76"/></clipPath>')
    red = (f'<rect width="{W}" height="{H}" fill="{VERM}"/><circle cx="415" cy="170" r="76" fill="{WHITE}"/>'
           f'<g clip-path="url(#{sun_clip})"><g style="animation:{eclipse} .4s steps(4) 1.84s both"><circle cx="415" cy="170" r="74" fill="#140605"/></g></g>'
           f'<g style="animation:{drift} 2.4s linear 0s both">{clouds}</g>'
           + f'<g opacity=".95">{_peaks(c, specs)}</g>'
           f'<path d="M-10 322Q200 312 415 318T840 320L840 480L-10 480Z" fill="{PAPER}"/>'
           + c.particles(12, 4, .95, 1.2, lambda r: c.use('flecks_r', -40, -20, .25 * r.uniform(.6, 1.4)),
                         (60, 330, 780, 440), (-60, 50), spin=10))
    shots.append(c.window(0, .86, c.camera(bw, 415, 220, 1.0, 1.04, 0, .86, steps=10)))
    shots.append(c.window(.86, .95, glitch))
    shots.append(c.window(.95, 2.22, c.camera(red, 415, 200, 1.04, 1.12, .95, 1.27, steps=15)))
    shots.append(_cut_swoosh(c, 2.2))

    # ===== 五张登场卡（第五名 → 第一名），每张 2.5 秒 =====
    T = [2.45, 4.95, 7.45, 9.95, 12.45]

    def lab(i, x, y, t, **kw):
        if not ranked[i]:
            return c.caption(x, y, i + 1, None, 0, 0, t, **kw)
        return c.caption(x, y, i + 1, ranked[i][0], pct(i), ranked[i][1], t, **kw)

    # 木 · 第五：浓墨竹林斜插进画面，刀叶横飞；「木」在右上
    t = T[0]
    grow_in = c.kf("from{transform:scale(.86) translateY(30px)}")
    wood = (c.band(380, 250, 1100, 120, -14, t)
            + f'<g class="§b" style="animation:{grow_in} .36s steps(3) {t:.2f}s both">'
            + _bamboo(c, 150, 520, 520, 34, 8, 11) + _bamboo(c, 250, 540, 470, 26, 16, 12, True) + _bamboo(c, 60, 520, 430, 22, -4, 13)
            + '</g>'
            + c.particles(15, 21, t + .3, 1.8, lambda r: _leaf(c, r), (-60, 60, 300, 400), (700, -60), spin=540)
            + c.glyph('木', 560, 270, 220, t=t + .32, step=.1)
            + c.splat(740, 120, -20, .45, t + .4) + c.splat(570, 260, 160, .35, t + .62)
            + lab(4, 792, 364, t + 1.0, align='end'))
    shots.append(c.window(t, t + 2.36, c.shake(c.camera(wood, 415, 233, 1.0, 1.05, t, 2.36, steps=28), [t + .32])))
    shots.append(_cut_smear(c, t + 2.32))

    # 火 · 第四：整屏朱红，一道黑色干笔横扫；黑边白芯的火从下面窜起，火星往上飞
    t = T[1]
    flick = c.kf("0%{transform:scaleY(.2)}20%{transform:scaleY(1.08)}40%{transform:scaleY(.94)}60%{transform:scaleY(1.05)}"
                 "80%{transform:scaleY(.97)}100%{transform:scaleY(1)}")
    flames = ''.join(f'<g transform="translate({x} 478) scale({s})"><g class="§b" style="animation:{flick} 1.2s steps(8) {t + d:.2f}s both">'
                     + c.use(f'flame{k}', -150, -420) + '</g></g>'
                     for x, s, k, d in ((90, 1.05, 0, .05), (230, 1.3, 1, 0), (370, .95, 0, .1), (-10, .8, 1, .12), (300, .75, 0, .2)))
    glow = c.rad([(0, WHITE, .75), (.5, WHITE, .2), (1, WHITE, 0)])
    ember = lambda r: (f'<circle r="{r.uniform(1.5, 3.5):.1f}" fill="{WHITE if r.random() < .6 else INK}"/>')
    fire = (f'<rect width="{W}" height="{H}" fill="{VERM}"/>'
            + c.band(420, 250, 1150, 150, 12, t + .06, name='stroke')
            + f'<circle cx="220" cy="430" r="260" fill="url(#{glow})"/>' + flames
            + c.particles(20, 22, t + .25, 1.6, ember, (40, 300, 460, 460), (60, -360), grav=-40)
            + c.glyph('火', 560, 270, 220, t=t + .3, step=.1)
            + c.splat(560, 300, 200, .35, t + .5)
            + lab(3, 792, 364, t + 1.0, align='end', ink=WHITE, accent=WHITE, halo=INK))
    shots.append(c.window(t, t + 2.3, c.shake(c.camera(fire, 300, 300, 1.0, 1.06, t, 2.3, steps=28), [t + .3])))
    shots.append(_cut_swoosh(c, t + 2.26, .24))

    # 土 · 第三：斧劈皴的山石从地下撞出来，碎石飞、尘土起；「土」在左
    t = T[2]
    erupt = c.kf("0%{transform:translateY(330px)}60%{transform:translateY(-18px)}80%{transform:translateY(6px)}100%{transform:translateY(0)}")
    dustg = c.rad([(0, INK, .5), (.5, INK, .18), (1, INK, 0)])
    puff = c.kf("0%{opacity:0;transform:scale(.3)}25%{opacity:1}100%{opacity:0;transform:scale(1.5)}")
    puffs = ''.join(f'<g transform="translate({x} {y})"><circle class="§c" r="{r}" fill="url(#{dustg})" opacity="0" '
                    f'style="animation:{puff} 1.4s ease-out {t + .4 + d:.2f}s both"/></g>'
                    for x, y, r, d in ((430, 440, 90, 0), (560, 455, 110, .05), (700, 445, 100, .1), (800, 450, 80, .15)))
    earth = (c.band(430, 230, 1100, 120, 16, t, flip=True)
             + f'<g style="animation:{erupt} .55s steps(6) {t + .05:.2f}s both">' + c.use('cliff', 360, 72, 1.12) + '</g>'
             + puffs + c.particles(16, 23, t + .3, 1.4, lambda r: _rock(c, r), (420, 300, 820, 440), (-160, -260), spin=720, grav=420)
             + c.glyph('土', 70, 300, 220, t=t + .35, step=.12)
             + c.splat(250, 120, -30, .4, t + .45)
             + lab(2, 300, 262, t + 1.0))
    shots.append(c.window(t, t + 2.38, c.shake(c.camera(earth, 415, 300, 1.0, 1.05, t, 2.38, steps=28), [t + .38, t + .5])))
    shots.append(_cut_negative(c, t + 2.38, .12, 7))

    # 金 · 第二：黑底，一把剑斜劈进来，刃上一道白光扫过，剑尖迸出火星；「金」是白字
    t = T[3]
    thrust = c.kf("from{transform:translate(-340px,190px)}to{transform:translate(0,0)}")
    glint = c.kf("0%{opacity:0;transform:translateX(0)}20%{opacity:1}100%{opacity:0;transform:translateX(520px)}")
    blade_clip = c.nid('c')
    c.defs.append(f'<clipPath id="{blade_clip}"><path d="M8 -11L514 -8L560 0L514 8L8 11Z"/></clipPath>')
    spark = lambda r: f'<path d="M0 0l{r.uniform(6, 16):.0f} 0" stroke="{GOLD if r.random() < .5 else WHITE}" stroke-width="2" stroke-linecap="round"/>'
    sword = (f'<g transform="translate(250 330) rotate(-24)"><g style="animation:{thrust} .32s steps(4) {t + .04:.2f}s both">{_sword()}'
             f'<g clip-path="url(#{blade_clip})"><g style="animation:{glint} .5s ease-out {t + .7:.2f}s both">'
             f'<rect x="-60" y="-12" width="60" height="24" fill="{WHITE}"/><rect x="-80" y="-12" width="20" height="24" fill="{GOLD}" opacity=".6"/></g></g>'
             f'</g></g>')
    metal = (f'<rect width="{W}" height="{H}" fill="#0c0908"/>'
             + c.band(400, 260, 1150, 130, -20, t + .1)
             + c.use('swoosh', 40, 120, 1.0, .7, ' opacity=".85"') + sword
             + c.particles(18, 24, t + .45, .9, spark, (700, 70, 760, 130), (120, -40), spin=200, grav=160)
             + c.glyph('金', 575, 250, 210, 'dry_w', t=t + .3, step=.08)
             + lab(1, 792, 344, t + 1.0, align='end', ink=WHITE, accent=VERM, halo=INK))
    shots.append(c.window(t, t + 2.36, c.shake(c.camera(metal, 415, 233, 1.0, 1.05, t, 2.36, steps=28), [t + .36])))
    shots.append(_cut_smear(c, t + 2.34, .18, flip=True))

    # 水 · 第一：朱红的圆相一圈圈旋开，白浪溅起，水珠四射；「水」在右，负片一闪
    t = T[4]
    red_dry = f'url(#{c.pattern("dry_r")})'
    spin1 = c.kf("from{transform:rotate(-120deg) scale(.4)}to{transform:rotate(30deg) scale(1)}")
    spin2 = c.kf("from{transform:rotate(90deg) scale(.5)}to{transform:rotate(-40deg) scale(1)}")
    burst = c.kf("0%{transform:scale(.15)}55%{transform:scale(1.12)}100%{transform:scale(1)}")
    drop = lambda r: (f'<circle r="{r.uniform(3, 7):.1f}" fill="{WHITE}" stroke="{INK}" stroke-width="1.8"/>')
    rip = c.kf("0%{opacity:0;transform:scale(.2)}20%{opacity:1}100%{opacity:0;transform:scale(1.8)}")
    water = (c.band(400, 300, 1100, 110, -8, t + .1)
             + f'<g transform="translate(250 250)"><g style="animation:{spin1} .9s steps(9) {t + .05:.2f}s both">{_ring(0, 0, 178, 46, 31, red_dry)}</g></g>'
             + f'<g transform="translate(250 250)"><g style="animation:{spin2} .9s steps(9) {t + .15:.2f}s both">{_ring(0, 0, 122, 34, 32, red_dry)}</g></g>'
             + f'<g transform="translate(250 250)"><g style="animation:{spin1} .9s steps(9) {t + .25:.2f}s both">{_ring(0, 0, 222, 18, 33, red_dry, 120)}</g></g>'
             + ''.join(f'<g transform="translate(250 392)"><ellipse class="§c" rx="150" ry="18" fill="none" stroke="{INK}" stroke-width="2.4" '
                       f'opacity="0" style="animation:{rip} 1.3s ease-out {t + .4 + k * .3:.2f}s both"/></g>' for k in range(3))
             + f'<g transform="translate(250 400)"><g class="§b" style="animation:{burst} .6s steps(6) {t + .2:.2f}s both">'
             + c.use('splash_w', -230, -320, 1.1) + '</g></g>'
             + c.particles(16, 25, t + .35, 1.2, drop, (180, 220, 320, 360), (0, -220), grav=420)
             + c.glyph('水', 560, 280, 230, t=t + .3, step=.1)
             + c.splat(780, 130, -40, .45, t + .5)
             + lab(0, 792, 372, t + 1.0, align='end'))
    shots.append(c.window(t, t + 2.42, c.shake(c.camera(water, 250, 250, 1.0, 1.06, t, 2.42, steps=28), [t + .3, t + 1.0])))
    shots.append(_cut_negative(c, t + .92, .1, 9))
    shots.append(_cut_red(c, t + 2.42, .08))

    # ===== 「五行」分屏 14.95–16.75：左黑底红字，右红底黑字 =====
    t = 14.95
    lin = c.kf("from{transform:translateX(-210px)}to{transform:translateX(0)}")
    rin = c.kf("from{transform:translateX(210px)}to{transform:translateX(0)}")
    split = (f'<g style="animation:{lin} .2s steps(2) {t:.2f}s both"><rect width="415" height="{H}" fill="#0c0908"/>'
             + c.glyph('五', 207, 250, 300, 'dry_r', t=t + .08, step=.07, anchor_c=True)
             + f'<text x="34" y="440" font-family="{PM}" font-size="16" letter-spacing="3" fill="{WHITE}">FIVE ELEMENTS</text></g>'
             f'<g style="animation:§in .01s linear {t + .32:.2f}s both,{rin} .2s steps(2) {t + .32:.2f}s both"><rect x="415" width="415" height="{H}" fill="{VERM}"/>'
             + c.glyph('行', 622, 250, 300, 'dry_k', t=t + .4, step=.07, anchor_c=True)
             + f'<text x="796" y="440" text-anchor="end" font-family="{PM}" font-size="16" letter-spacing="3" fill="{INK}">FIVE LINES</text></g>'
             f'<rect x="413" width="4" height="{H}" fill="{PAPER}" style="animation:§in .01s linear {t + .32:.2f}s both"/>')
    shots.append(c.window(t, 16.75, c.shake(c.camera(split, 415, 233, 1.0, 1.04, t, 1.8, steps=20), [t + .4, t + .75])))
    shots.append(_cut_smear(c, 16.6, .18))

    # ===== 五行榜 16.75–20.75：红底上的草书诗墙（五行相生），五个大字按占比大小并排 =====
    t = 16.75
    rr = random.Random(41)
    wall_parts = []
    k = 0
    x = 20.0
    while x < W + 10:                                  # 一列一列竖着写，每列字号、浓淡各不同
        fs = rr.uniform(28, 50)
        y = rr.uniform(-20, 30) + fs
        col = []
        while y < 440:
            col.append(f'<text x="{x + rr.uniform(-3, 3):.0f}" y="{y:.0f}">{WALL[k % len(WALL)]}</text>')
            y += fs * rr.uniform(.8, 1.0)
            k += 1
        wall_parts.append(f'<g font-size="{fs:.0f}" opacity="{rr.uniform(.55, 1):.1f}">{"".join(col)}</g>')
        x += fs * rr.uniform(.95, 1.25)
    wall = f'<g font-family="{LJ}" fill="{VERM_D}" text-anchor="middle">{"".join(wall_parts)}</g>'
    top_v = ranked[0][1] if ranked[0] else 1
    cols = []
    for j, i in enumerate(range(4, -1, -1)):          # 左到右：木 火 土 金 水
        x = 95 + j * 160
        el = ELEMS[4 - i][0]
        size = 84 + 70 * math.sqrt(ranked[i][1] / top_v) if ranked[i] else 84
        tj = t + .25 + j * .22
        cols.append(c.glyph(el, x, 250, size, t=tj, step=.05, anchor_c=True)
                    + (f'<g style="animation:§in .01s linear {tj + .3:.2f}s both">'
                       f'<text x="{x}" y="330" text-anchor="middle" font-family="{PM}" font-size="19" fill="{WHITE}" stroke="{INK}" '
                       f'stroke-width="4" paint-order="stroke" stroke-linejoin="round">{escape(ranked[i][0].upper())}</text>'
                       f'<text x="{x}" y="368" text-anchor="middle" font-family="{PM}" font-size="30" fill="{INK}">{pct(i):.1f}%</text>'
                       f'<text x="{x}" y="390" text-anchor="middle" font-family="{PM}" font-size="12" letter-spacing="2" fill="{INK}">NO.{i + 1}</text></g>'
                       if ranked[i] else ''))
    lineup = (f'<rect width="{W}" height="{H}" fill="{VERM}"/>{wall}'
              + f'<path d="M-20 420Q300 400 520 414T860 408L860 480L-20 480Z" fill="#0c0908"/>'
              + ''.join(cols)
              + f'<g style="animation:§in .01s linear {t + 1.8:.2f}s both"><text x="415" y="450" text-anchor="middle" font-family="{PM}" '
              f'font-size="17" letter-spacing="2" fill="{WHITE}">{ytotal:,} LINES · {n_langs} LANGUAGES · {yearly_days} DAYS</text></g>')
    shots.append(c.window(t, 20.75, c.camera(lineup, 415, 260, 1.12, 1.0, t, 4.0, steps=40)))
    shots.append(_cut_smear(c, 20.62, .18, flip=True))

    # ===== 高潮「万行」20.75–24.9：深蓝底，青墨漩涡、闪电、金色刀弧，白色大字 =====
    t = 20.75
    vspin = c.kf("from{transform:rotate(0deg) scale(.55)}to{transform:rotate(-200deg) scale(1.08)}")
    vortex = (f'<g transform="translate(415 214)"><g style="animation:{vspin} 4.2s cubic-bezier(.3,0,.6,1) {t:.2f}s both">'
              + c.use('vortex', -230, -230) + '</g></g>')
    halo = c.rad([(0, CYAN, .5), (.4, CYAN, .12), (1, CYAN, 0)])
    bolts = ''
    for k, (x0, y0, x1, y1) in enumerate(((-20, 40, 330, 190), (850, 60, 500, 200), (-10, 430, 320, 260), (840, 420, 520, 250))):
        d = _bolt(x0, y0, x1, y1, 50 + k)
        bolts += (f'<g opacity="0" style="animation:§flick .16s steps(2) {t + .3 + k * .35:.2f}s 6">'
                  f'<path d="{d}" stroke="{CYAN}" stroke-width="7" opacity=".35" fill="none" stroke-linejoin="round"/>'
                  f'<path d="{d}" stroke="{WHITE}" stroke-width="2" fill="none" stroke-linejoin="round"/></g>')
    arc_clip = c.nid('c')
    c.defs.append(f'<clipPath id="{arc_clip}"><rect x="-20" y="-20" width="0" height="600">'
                  f'<animate attributeName="width" values="0;290;580;870" keyTimes="0;.33;.66;1" calcMode="discrete" begin="{t + 1.6:.2f}s" '
                  f'dur=".24s" fill="freeze"/></rect></clipPath>')
    arc_k = c.kf("0%{opacity:1}70%{opacity:1}100%{opacity:0}")
    slash = (f'<g style="animation:{arc_k} 1s linear {t + 1.6:.2f}s both"><g clip-path="url(#{arc_clip})">'
             f'<g transform="translate(-30 236) scale(1.5 .55)">' + c.use('arc') + '</g></g></g>')
    motes = c.particles(18, 26, t + .2, 2.4, lambda r: f'<circle r="{r.uniform(1, 2.6):.1f}" fill="{CYAN}"/>', (60, 60, 770, 420), (0, -120))
    climax = (f'<rect width="{W}" height="{H}" fill="{NAVY}"/>' + vortex
              + f'<circle cx="415" cy="214" r="250" fill="url(#{halo})"/>' + bolts + motes + slash
              + c.glyph('万', 170, 290, 200, 'dry_w', t=t + .5, step=.08) + c.glyph('行', 420, 290, 200, 'dry_w', t=t + .78, step=.08)
              + f'<g style="animation:§in .01s linear {t + 1.4:.2f}s both"><text x="415" y="372" text-anchor="middle" font-family="{PM}" '
              f'font-size="40" fill="{WHITE}">{ytotal:,}</text><text x="415" y="398" text-anchor="middle" font-family="{PM}" font-size="13" '
              f'letter-spacing="3" fill="{CYAN}">LINES OF CODE THIS YEAR</text></g>')
    whiteout = c.kf("from{opacity:0}to{opacity:1}")
    shots.append(c.window(t, 25.1, c.shake(c.camera(climax, 415, 233, 1.0, 1.08, t, 4.35, steps=40), [t + .5, t + 1.6])
                          + f'<rect width="{W}" height="{H}" fill="{WHITE}" opacity="0" style="animation:{whiteout} .3s ease-in 24.6s both"/>'))

    # ===== 海报：上面是纸、红日、祥云、黑山，一道朱红笔触带斜穿过「五行」两个大字；下面一片黑地，五行榜用白字写在上面 =====
    live = 24.9
    pspecs = [(x, 336, rng.uniform(70, 150), rng.uniform(160, 240), rng.randrange(2), rng.random() < .5) for x in range(-30, W + 80, 84)]
    sky_p = c.lin([(0, '#d6d1c6', 1), (.7, PAPER, 1)], x2=0, y2=1)
    sun_glow = c.rad([(0, VERM, .3), (.55, VERM, .08), (1, VERM, 0)])
    fleck = c.kf("0%{opacity:0;transform:translate(0,0) rotate(0deg)}15%{opacity:1}80%{opacity:1}"
                 "100%{opacity:0;transform:translate(-90px,-170px) rotate(220deg)}")
    flecks = ''.join(f'<g transform="translate({x} {y})"><g opacity="0" style="animation:{fleck} {p}s linear {live + d:.1f}s infinite">'
                     f'<ellipse rx="{sz * 2.4:.1f}" ry="{sz:.1f}" fill="{VERM}"/></g></g>'
                     for x, y, sz, p, d in ((520, 350, 2.4, 11, 1), (700, 360, 1.8, 13, 4), (360, 352, 2.2, 12, 7), (620, 340, 1.6, 15, 2),
                                            (180, 356, 2.0, 14, 9), (780, 346, 2.6, 10, 5)))
    cols_p = []
    for j, i in enumerate(range(4, -1, -1)):
        x = 112 + j * 152
        el = ELEMS[4 - i][0]
        if ranked[i]:
            cols_p.append(f'<text x="{x}" y="398" text-anchor="middle" font-family="{YB}" font-size="34" fill="{WHITE}">{el}</text>'
                          f'<text x="{x}" y="424" text-anchor="middle" font-family="{PM}" font-size="13.5" letter-spacing=".5" fill="{WHITE}">'
                          f'{escape(ranked[i][0].upper())}</text>'
                          f'<text x="{x}" y="450" text-anchor="middle" font-family="{PM}" font-size="19" fill="{VERM}">{pct(i):.1f}%</text>')
        else:
            cols_p.append(f'<text x="{x}" y="398" text-anchor="middle" font-family="{YB}" font-size="34" fill="{WHITE}" opacity=".3">{el}</text>')
    week = (f'THIS WEEK · {wtotal:,} LINES · {wrows[0][0].upper()} {wrows[0][1] / wtotal * 100:.1f}%' if wrows else 'THIS WEEK · QUIET')
    poster = (f'<rect width="{W}" height="340" fill="url(#{sky_p})"/>'
              f'<g style="animation:§breathe 8s ease-in-out {live:.1f}s infinite"><circle cx="642" cy="150" r="170" fill="url(#{sun_glow})"/></g>'
              f'<circle cx="642" cy="150" r="84" fill="{VERM}"/>'
              f'<g style="animation:§drift 28s ease-in-out {live:.1f}s infinite alternate">{_cloud(c, 520, 188, 1.05)}{_cloud(c, 700, 120, .85, True)}</g>'
              f'<g style="animation:§drift 37s ease-in-out {live + 6:.1f}s infinite alternate-reverse">{_cloud(c, 330, 96, .7)}</g>'
              + f'<g opacity=".97">{_peaks(c, pspecs)}</g>'
              + c.mist(-80, 270, 1000, 90, .75, (live + 2, 40))
              + f'<path d="M-10 344Q180 330 400 340T840 334L840 480L-10 480Z" fill="#0c0908"/>'
              + c.band(160, 340, 520, 30, -1.5, name='stroke') + c.band(560, 338, 640, 26, 1.2, name='stroke', flip=True)
              + c.band(760, 342, 300, 22, -2, name='stroke')
              + c.band(250, 236, 820, 128, -20)
              + c.glyph('五', 64, 304, 184, outline=PAPER) + c.glyph('行', 246, 304, 184, outline=PAPER)
              + c.seal_v(SEAL, 456, 196, 30)
              + f'<text transform="translate(806 44) rotate(90)" font-family="{PM}" font-size="12" letter-spacing="4" fill="{INK}">FIVE ELEMENTS · FIVE LINES</text>'
              f'<text x="40" y="44" font-family="{PM}" font-size="14" letter-spacing="1.5" fill="{INK}">{ytotal:,} LINES · {n_langs} LANGUAGES · {yearly_days} DAYS</text>'
              f'<text x="40" y="64" font-family="{PM}" font-size="11" letter-spacing="1.2" fill="{INK}" opacity=".75">{week} · {commits:,} COMMITS</text>'
              + ''.join(cols_p) + flecks)
    final = f'<g style="animation:§show .9s ease-out {live:.1f}s both">{poster}</g>'
    return c.svg(''.join(shots) + final)
