#!/usr/bin/env python3
"""把语言统计 / 作息画像渲染成两支「电影短片」式的动画 SVG（运行时无第三方依赖）

风格：纯黑与冷银灰，唯一的暖金色光；宽字距衬线体，中英双语字幕；镜头之间交叉淡化的蒙太奇。
- render_languages_film 《七日，一年》：本周 / 本年的语言，各自排成一列会自转的行星
- render_activity_film  《我很少见到早晨》：作息画像——倾斜旋转的星系、七个月相、由 24 小时提交数堆成的群山、日出

每支片先播约 15 秒开场，随后定格为海报帧并保留缓慢的环境动画（星光、行星自转、流星、胶片颗粒）。
静态属性即终态：动画不运行的环境（含 prefers-reduced-motion）直接显示海报帧。
位图素材与字体子集在 assets/cinema/，由 make_assets.py 离线生成后提交，渲染时 base64 内嵌。
"""

import base64
import math
import os
import random
from html import escape

W, H = 830, 347       # 2.39:1 宽银幕，宽度与 README 正文一致
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'cinema')

LANG_COLORS = {
    'Python': '#3572A5', 'TypeScript': '#3178c6', 'JavaScript': '#f1e05a', 'Vue': '#41b883',
    'CSS': '#663399', 'SCSS': '#c6538c', 'SASS': '#a53b70', 'Less': '#1d365d', 'HTML': '#e34c26',
    'Swift': '#F05138', 'Go': '#00ADD8', 'Rust': '#dea584', 'Java': '#b07219', 'Kotlin': '#A97BFF',
    'PHP': '#4F5D95', 'Shell': '#89e051', 'PowerShell': '#012456', 'C': '#555555', 'C++': '#f34b7d',
    'C#': '#178600', 'Dart': '#00B4AB', 'Ruby': '#701516', 'Lua': '#000080', 'SQL': '#e38c00',
    'Svelte': '#ff3e00', 'Scala': '#c22d40', 'R': '#198CE7', 'Elixir': '#6e4a7e', 'Erlang': '#B83998',
    'Haskell': '#5e5086', 'Julia': '#a270ba', 'Zig': '#ec915c', 'Perl': '#0298c3',
}
DEFAULT_LANG_COLOR = '#8b949e'

# 字体：内嵌子集优先，缺字时（如中文字幕里的数字和语言名）按顺序回退到下一个字体
EN = "CG,'Cormorant Garamond','EB Garamond',Garamond,'Times New Roman',serif"
EN6 = "CG6,'Cormorant Garamond','EB Garamond',Garamond,'Times New Roman',serif"
ZH = "NS,CG,'Noto Serif SC','Source Han Serif SC','Songti SC',STSong,SimSun,serif"
BRUSH = "ZM,'Zhi Mang Xing',STXingkai,'Xingkai SC',KaiTi,cursive"
FONT_FILES = {'CG': 'cg500.woff2', 'CG6': 'cg600.woff2', 'NS': 'nss500.woff2', 'ZM': 'zmx400.woff2'}

INK, SILVER, MUTED = '#eef1f6', '#b9c1ce', '#7f8898'
GOLD, GOLD_CORE = '#ffc978', '#fff3dc'
SKY_FIT = f'transform="translate({W / 2} {H / 2}) scale(1.04) translate({-W / 2} {-H / 2})"'

PERIODS = (('Night', 0), ('Morning', 6), ('Daytime', 12), ('Evening', 18))   # (时段, 起始小时)
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
WEEKDAYS_ZH = '一二三四五六日'
WEEKDAYS_EN = ['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
# 最少的时段 → 片名里「很少见到」的那段时光，以及日出镜头的天色（天空, 地平线, 太阳）
RARE = {
    'Morning': ('早晨', 'the Morning', ('#2b1d2c', '#c98172', '#ffe1a8')),
    'Daytime': ('白天', 'the Daylight', ('#1c2a3c', '#9fb8cf', '#fff8ea')),
    'Evening': ('黄昏', 'the Dusk', ('#2a1830', '#d27a4e', '#ffc98a')),
    'Night': ('深夜', 'Midnight', ('#05070f', '#24304f', '#dfe6f2')),
}
PROFILE = {'Morning': "an early bird", 'Daytime': "a daytime coder", 'Evening': "an evening coder", 'Night': "a night owl"}

# 片名（书法字体）和中文字幕模板。make_assets.py 按这里出现的汉字做字体子集，改文案后要重新生成字体
TITLE_A = '七日<tspan dx="-.32em">，</tspan><tspan dx="-.3em">一年</tspan>'
TITLE_B = '我很少见到{p}'
ZH_TEXT = {
    'lines': '这{span}，我改动了 {n} 行代码。',
    'lines_none': '这{span}，我一行代码也没写。',
    'week_major': '大多是 {lang}。',
    'week_minor': '{lang} 写得最多。',
    'year': '这{span}，我说得最多的是 {lang}。',
    'quiet': '很安静。',
    'commits': '过去{span}，我提交了 {n} 次。',
    'dark': '大多在天黑以后。',
    'light': '大多在天亮以后。',
    'busiest': '星期{d}最忙。',
    'rare': '我很少见到{p}。',
}
ZH_SPANS = {7: '七天', 365: '一年'}
EN_SPANS = {7: 'seven days', 365: 'a year'}


def zh_chars() -> str:
    """字幕字体子集需要的全部汉字和中文标点"""
    text = ''.join(ZH_TEXT.values()) + ''.join(ZH_SPANS.values()) + WEEKDAYS_ZH + ''.join(v[0] for v in RARE.values())
    return ''.join(sorted({ch for ch in text if ord(ch) > 0x2e80}))


def brush_chars() -> str:
    """书法片名子集需要的字"""
    text = '七日，一年' + TITLE_B + ''.join(v[0] for v in RARE.values())
    return ''.join(sorted({ch for ch in text if ord(ch) > 0x2e80}))


BASE_CSS = (
    "@keyframes §in{from{opacity:0}}"
    "@keyframes §rise{from{opacity:0;transform:translateY(8px)}}"
    "@keyframes §tw{50%{opacity:.2}}"
    "@keyframes §roll{to{transform:translateX(-420px)}}"
    "@keyframes §spin{to{transform:rotate(360deg)}}"
    "@keyframes §breathe{50%{opacity:.55}}"
    "@keyframes §drift{to{transform:translateX(-14px)}}"
    "@keyframes §grain{0%{transform:translate(0,0)}25%{transform:translate(-41px,23px)}"
    "50%{transform:translate(17px,-38px)}75%{transform:translate(-23px,-11px)}}"
    "@keyframes §met{0%{opacity:0;transform:translateX(0)}1.5%{opacity:1}8%,100%{opacity:0;transform:translateX(300px)}}"
    ".§fi{animation:§in 1.2s ease-out both}"
    ".§tw{animation:§tw 4s ease-in-out infinite}"
    ".§sub{paint-order:stroke;stroke:#000;stroke-opacity:.55;stroke-width:3px;stroke-linejoin:round}"
    "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def _n(v: float, d: int = 1) -> str:
    """紧凑的坐标格式：去掉多余的 0 和小数点"""
    s = f"{v:.{d}f}".rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def _rgb(c: str):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a: str, b: str, t: float) -> str:
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def _dots(pts) -> str:
    """一条 path 画很多星点：每个点是一段极短的圆头线段"""
    return ''.join(f"M{_n(x)} {_n(y)}h.01" for x, y in pts)


def _asset(name: str) -> str:
    with open(os.path.join(ASSET_DIR, name), 'rb') as f:
        return base64.b64encode(f.read()).decode()


class _Film:
    """一支片的画布：收集 defs / CSS / 图元，输出时把 § 换成片子前缀（两支片内联到同一页面时互不冲突）"""

    def __init__(self, uid: str, seed: int, label: str):
        self.uid, self.label = uid, label
        self.rng = random.Random(seed)
        self.defs, self.css = [], [BASE_CSS]
        self._ids, self._cache, self._kf = 0, {}, {}

    def nid(self, p: str = 'i') -> str:
        self._ids += 1
        return f"§{p}{self._ids}"

    def kf(self, frames: str) -> str:
        """登记一组关键帧并返回动画名；内容相同的只定义一次"""
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

    def image(self, name: str, w: int, h: int, mime: str = 'image/webp') -> str:
        """位图只内嵌一次，之后用 <use> 引用"""
        key = ('img', name)
        if key not in self._cache:
            iid = self.nid('m')
            self.defs.append(f'<image id="{iid}" width="{w}" height="{h}" preserveAspectRatio="none" '
                             f'href="data:{mime};base64,{_asset(name)}"/>')
            self._cache[key] = iid
        return self._cache[key]

    # ---------- 时间轴 ----------

    def window(self, t0: float, t1: float, body: str, fade: float = .8) -> str:
        """只在 [t0, t1] 出现的镜头 / 字幕；窗口外 opacity 为 0，所以静态时不可见"""
        d = t1 - t0
        f = min(fade / d * 100, 45)
        k = self.kf(f"0%{{opacity:0}}{f:.2f}%{{opacity:1}}{100 - f:.2f}%{{opacity:1}}100%{{opacity:0}}")
        return f'<g opacity="0" style="animation:{k} {d:.2f}s linear {t0:.2f}s">{body}</g>'

    def camera(self, body: str, cx: float, cy: float, s0: float, s1: float, t0: float, dur: float, dx: float = 0) -> str:
        """镜头推拉 / 平移：以 (cx, cy) 为中心从 s0 缩放到 s1，同时水平平移 dx"""
        k = self.kf(f"from{{transform:scale({s0})}}to{{transform:translate({dx}px,0) scale({s1})}}")
        return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g style="animation:{k} {dur:.2f}s linear {t0:.2f}s both">'
                f'<g transform="translate({_n(-cx)} {_n(-cy)})">{body}</g></g></g>')

    def subtitle(self, zh: str, en: str, t0: float, t1: float, y: float = 296) -> str:
        body = (f'<text class="§sub" x="{_n(W / 2)}" y="{_n(y)}" font-family="{ZH}" font-size="15" text-anchor="middle" '
                f'fill="{INK}" letter-spacing="1.5">{escape(zh)}</text>'
                f'<text class="§sub" x="{_n(W / 2)}" y="{_n(y + 21)}" font-family="{EN}" font-size="15" text-anchor="middle" '
                f'fill="{SILVER}" letter-spacing=".4">{escape(en)}</text>')
        return self.window(t0, t1, body, fade=.55)

    # ---------- 元素 ----------

    def light(self, x: float, y: float, h: float = 26, flare: float = 1.0) -> str:
        """暖金色的光：一根孤独的光标，带泛光和横向的变形镜头光斑"""
        g1 = self.rad([(0, GOLD, .6), (1, GOLD, 0)])
        g2 = self.rad([(0, '#ff9d42', .22), (1, '#ff9d42', 0)])
        core = self.lin([(0, '#ffd99b', 1), (.5, GOLD_CORE, 1), (1, '#ffd99b', 1)])
        streak = self.lin([(0, '#ffd9a0', 0), (.5, '#ffe2b5', .55), (1, '#ffd9a0', 0)])
        w = h * .23
        out = (f'<ellipse cx="{_n(x)}" cy="{_n(y)}" rx="{_n(h * 1.3)}" ry="{_n(h * 1.6)}" fill="url(#{g2})"/>'
               f'<ellipse cx="{_n(x)}" cy="{_n(y)}" rx="{_n(h * .45)}" ry="{_n(h * .85)}" fill="url(#{g1})"/>')
        if flare:
            out += (f'<rect x="{_n(x - 160 * flare)}" y="{_n(y - .6)}" width="{_n(320 * flare)}" height="1.2" fill="url(#{streak})"/>'
                    f'<rect x="{_n(x - 110 * flare)}" y="{_n(y - 4)}" width="{_n(220 * flare)}" height="8" '
                    f'fill="url(#{streak})" opacity=".12"/>')
        out += f'<rect x="{_n(x - w / 2)}" y="{_n(y - h / 2)}" width="{_n(w)}" height="{_n(h)}" rx="{_n(w / 2)}" fill="url(#{core})"/>'
        return out

    def stars(self, n: int, area=(0, 0, W, H)) -> str:
        """矢量星点（叠在位图星空上负责闪烁），分三组用不同周期"""
        r = self.rng
        x0, y0, x1, y1 = area
        out = []
        for k, dur in enumerate((3.7, 5.3, 7.1)):
            pts = [(r.uniform(x0, x1), r.uniform(y0, y1)) for _ in range(n // 3)]
            out.append(f'<path class="§tw" style="animation-duration:{dur}s;animation-delay:{k * 1.3:.1f}s" d="{_dots(pts)}" '
                       f'fill="none" stroke="#e8eef8" stroke-width="{1.1 + k * .3:.1f}" stroke-linecap="round" opacity=".8"/>')
        return ''.join(out)

    def meteors(self, specs) -> str:
        """specs: (x, y, 角度, 首次出现秒数, 周期)；静态 opacity 为 0，只在动画里划过"""
        tail = self.lin([(0, '#ffffff', 0), (1, '#ffffff', .85)])
        return ''.join(f'<g transform="translate({x} {y}) rotate({a})"><g opacity="0" style="animation:§met {p}s linear {d}s infinite">'
                       f'<rect x="-110" y="-.6" width="110" height="1.2" rx=".6" fill="url(#{tail})"/></g></g>'
                       for x, y, a, d, p in specs)

    def planet(self, d: float, color: str, spin: float, phase: float = 0, gold: bool = False) -> str:
        """3D 行星（以原点为中心）：条带纹理水平滑动模拟自转，叠加球面明暗、晨昏线和边缘光"""
        r = d / 2
        base = _mix(color, '#8f98aa', .42)
        tex = self.image('planet.webp', 420, 128)
        clip = self.nid('c')
        self.defs.append(f'<clipPath id="{clip}"><circle r="{_n(r)}"/></clipPath>')
        atm = self.rad([(0, base, 0), (.66, base, 0), (.74, _mix(base, '#ffffff', .3), .35), (1, base, 0)])
        shade = self.rad([(0, '#ffffff', .22), (.35, '#ffffff', 0), (.75, '#000000', .55), (1, '#000000', .85)],
                         cx=.32, cy=.3, r=.85)
        rim_c = GOLD if gold else '#dfe7f5'
        rim = self.lin([(0, rim_c, .9), (.45, rim_c, 0)], x2=.8, y2=.9)
        return (f'<circle r="{_n(r * 1.36)}" fill="url(#{atm})"/>'
                f'<g clip-path="url(#{clip})"><circle r="{_n(r)}" fill="{base}"/>'
                f'<g transform="translate({_n(-r - phase * d)} {_n(-r)}) scale({d / 128:.4f})" opacity=".5">'
                f'<g style="animation:§roll {spin:.0f}s linear infinite"><use href="#{tex}"/><use href="#{tex}" x="420"/></g></g>'
                f'<circle r="{_n(r)}" fill="url(#{shade})"/></g>'
                f'<circle r="{_n(r - .4)}" fill="none" stroke="url(#{rim})" stroke-width="{1.4 if gold else 1}"/>')

    def moon(self, r: float, f: float) -> str:
        """月相（以原点为中心）：f 为被照亮的比例，亮面朝右"""
        halo = self.rad([(0, '#dfe6f2', 0), (.4, '#dfe6f2', round(.16 + .14 * f, 3)), (1, '#dfe6f2', 0)])
        lit = self.rad([(0, '#fbf7ee', 1), (.7, '#e7e1d4', 1), (1, '#b9b3a6', 1)], cx=.6, cy=.4, r=.7)
        if f < .995:
            d = f"M0 {_n(-r)}A{_n(r)} {_n(r)} 0 0 1 0 {_n(r)}A{_n(r * abs(1 - 2 * f))} {_n(r)} 0 0 {1 if f > .5 else 0} 0 {_n(-r)}Z"
        else:
            d = f"M0 {_n(-r)}A{_n(r)} {_n(r)} 0 1 1 0 {_n(r)}A{_n(r)} {_n(r)} 0 1 1 0 {_n(-r)}Z"
        maria = (f'<g fill="#8f8a80" opacity=".28"><circle cx="{_n(r * .25)}" cy="{_n(-r * .2)}" r="{_n(r * .28)}"/>'
                 f'<circle cx="{_n(r * .45)}" cy="{_n(r * .3)}" r="{_n(r * .18)}"/>'
                 f'<circle cx="{_n(-r * .1)}" cy="{_n(r * .35)}" r="{_n(r * .14)}"/></g>')
        clip = self.nid('c')
        self.defs.append(f'<clipPath id="{clip}"><path d="{d}"/></clipPath>')
        return (f'<circle r="{_n(r * 2.6)}" fill="url(#{halo})"/><circle r="{_n(r)}" fill="#141a26"/>'
                f'<g clip-path="url(#{clip})"><circle r="{_n(r)}" fill="url(#{lit})"/>{maria}</g>')

    # ---------- 输出 ----------

    def svg(self, layers: str) -> str:
        font_css = ''.join(f"@font-face{{font-family:{k};src:url(data:font/woff2;base64,{_asset('fonts/' + f)}) format('woff2')}}"
                           for k, f in FONT_FILES.items())
        grain = self.image('grain.png', 120, 120, 'image/png')
        vig = self.rad([(0, '#000000', 0), (.62, '#000000', 0), (1, '#000000', .62)], r=.72)
        self.defs.append(f'<pattern id="§grainp" width="120" height="120" patternUnits="userSpaceOnUse">'
                         f'<use href="#{grain}"/></pattern>')
        # 暗角 + 抖动的胶片颗粒，盖在所有镜头之上
        overlay = (f'<rect width="{W}" height="{H}" fill="url(#{vig})"/>'
                   f'<g opacity=".16"><g style="animation:§grain .42s steps(1) infinite">'
                   f'<rect x="-60" y="-60" width="{W + 120}" height="{H + 120}" fill="url(#§grainp)"/></g></g>')
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
               f'aria-label="{escape(self.label)}"><title>{escape(self.label)}</title>'
               f'<style>{font_css}{"".join(self.css)}</style>'
               f'<defs><clipPath id="§frame"><rect width="{W}" height="{H}" rx="8"/></clipPath>{"".join(self.defs)}</defs>'
               f'<g clip-path="url(#§frame)"><rect width="{W}" height="{H}" fill="#000"/>{layers}{overlay}</g></svg>')
        return out.replace('§', self.uid)


# ---------- 《七日，一年》：语言 ----------

def _rows(stats: dict, top_n: int = 5):
    rows = sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)[:top_n]
    total = sum(v['added'] + v['deleted'] for v in stats.values())
    return [(lang, v['added'] + v['deleted']) for lang, v in rows if v['added'] + v['deleted']], total


def _lineup(c: _Film, rows, total, cx, cy, slot, dmax, name_size=12.5, t0=None, stagger=.32, seed=0):
    """一排行星：直径按占比开方缩放，第一名带金色边缘光；t0 给定时依次登场"""
    if not rows:
        return (f'<text x="{_n(cx)}" y="{_n(cy)}" font-family="{EN}" font-size="14" text-anchor="middle" fill="{MUTED}">'
                f'silence, for now</text>')
    top, n = rows[0][1], len(rows)
    out = []
    for i, (lang, lines) in enumerate(rows):
        x = cx + (i - (n - 1) / 2) * slot
        d = 14 + (dmax - 14) * math.sqrt(lines / top)
        pct = lines / total * 100 if total else 0
        planet = c.planet(d, LANG_COLORS.get(lang, DEFAULT_LANG_COLOR), spin=40 + 23 * ((i + seed) % 4),
                          phase=(i * .37 + seed * .21) % 1, gold=i == 0)
        lab = (f'<text class="§sub" x="0" y="{_n(dmax / 2 + name_size + 8)}" font-family="{EN}" font-size="{name_size}" '
               f'text-anchor="middle" fill="{INK}" letter-spacing=".3">{escape(lang)}</text>'
               f'<text class="§sub" x="0" y="{_n(dmax / 2 + name_size * 2 + 11)}" font-family="{EN6}" '
               f'font-size="{_n(name_size * 1.04)}" text-anchor="middle" fill="{GOLD if i == 0 else SILVER}">{pct:.1f}%</text>')
        if t0 is not None:
            t = t0 + i * stagger
            k = c.kf("from{opacity:0;transform:scale(.55)}")
            planet = f'<g style="animation:{k} 1.6s cubic-bezier(.16,1,.3,1) {t:.2f}s both">{planet}</g>'
            lab = f'<g style="animation:§rise 1s ease-out {t + .45:.2f}s both">{lab}</g>'
        out.append(f'<g transform="translate({_n(x)} {_n(cy)})">{planet}{lab}</g>')
    return ''.join(out)


def _ringed_planet(c: _Film, cx, cy, d) -> str:
    """片名卡里的大行星：倾斜的环系分前后两半，前半遮住星球"""
    r = d / 2
    rings = ''.join(f'<circle r="{_n(rr)}" fill="none" stroke="#d9cfbd" stroke-opacity="{op}" stroke-width="{_n(sw)}"/>'
                    for rr, sw, op in ((r * 1.32, r * .1, .22), (r * 1.48, r * .16, .32), (r * 1.66, r * .1, .18),
                                       (r * 1.78, r * .05, .12), (r * 1.9, r * .03, .08)))
    front = c.nid('c')
    c.defs.append(f'<clipPath id="{front}"><rect x="{_n(-r * 2.2)}" y="0" width="{_n(r * 4.4)}" height="{_n(r * 2.2)}"/></clipPath>')
    tilt = 'transform="rotate(-13) scale(1 .24)"'
    return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g {tilt}>{rings}</g>{c.planet(d, "#c9b48f", 90, .3, True)}'
            f'<g {tilt} clip-path="url(#{front})">{rings}</g></g>')


def render_languages_film(weekly: dict, weekly_days: int, yearly: dict, yearly_days: int) -> str:
    wrows, wtotal = _rows(weekly)
    yrows, ytotal = _rows(yearly)
    n_langs = sum(1 for v in yearly.values() if v['added'] + v['deleted'])
    wspan_zh, yspan_zh = ZH_SPANS.get(weekly_days, f' {weekly_days} 天'), ZH_SPANS.get(yearly_days, f' {yearly_days} 天')
    wspan_en = EN_SPANS.get(weekly_days, f'{weekly_days} days')
    label = ("Seven Days, One Year — this week: " + (', '.join(f"{l} {v / wtotal * 100:.1f}%" for l, v in wrows) or 'nothing')
             + " · this year: " + (', '.join(f"{l} {v / ytotal * 100:.1f}%" for l, v in yrows) or 'nothing'))
    c = _Film('L', 7, label)
    sky = c.image('sky_a.webp', W, H)

    # A1 黑场 · 一点光
    a1 = c.window(0, 3.8, f'<g style="animation:§breathe 1.1s steps(1) 3">{c.light(W / 2, 140)}</g>', fade=.7)
    if wtotal:
        s1 = c.subtitle(ZH_TEXT['lines'].format(span=wspan_zh, n=f'{wtotal:,}'),
                        f"In {wspan_en}, I changed {wtotal:,} lines of code.", 1.0, 3.6, y=208)
    else:
        s1 = c.subtitle(ZH_TEXT['lines_none'].format(span=wspan_zh), f"In {wspan_en}, I didn't write a line.", 1.0, 3.6, y=208)

    # A2 本周的行星
    if wrows:
        major = wrows[0][1] / wtotal >= .5
        zh2 = ZH_TEXT['week_major' if major else 'week_minor'].format(lang=wrows[0][0])
        en2 = f"Most of it, in {wrows[0][0]}." if major else f"Mostly {wrows[0][0]}."
    else:
        zh2, en2 = ZH_TEXT['quiet'], "Quiet."
    a2 = c.window(3.4, 7.8, c.camera(f'<use href="#{sky}" opacity=".75"/>', W / 2, H / 2, 1.12, 1.2, 3.4, 4.4, dx=-20)
                  + c.stars(30) + _lineup(c, wrows, wtotal, W / 2, 140, 112, 82, name_size=15, t0=3.9, seed=1))
    s2 = c.subtitle(zh2, en2, 5.2, 7.6)

    # A3 本年的行星
    if yrows:
        zh3 = ZH_TEXT['year'].format(span=yspan_zh, lang=yrows[0][0])
        en3 = (f"This year, I spoke {yrows[0][0]} the most." if yearly_days == 365
               else f"In {yearly_days} days, I spoke {yrows[0][0]} the most.")
    else:
        zh3, en3 = ZH_TEXT['quiet'], "Quiet."
    a3 = c.window(7.4, 11.8, c.camera(f'<use href="#{sky}" opacity=".75"/>', W / 2, H / 2, 1.2, 1.12, 7.4, 4.4, dx=24)
                  + c.stars(30) + _lineup(c, yrows, ytotal, W / 2, 140, 112, 82, name_size=15, t0=7.9, seed=2))
    s3 = c.subtitle(zh3, en3, 9.2, 11.6)

    # A4 片名卡
    glow = c.rad([(0, GOLD, .25), (1, GOLD, 0)])
    a4 = c.window(11.4, 15.2, c.camera(f'<use href="#{sky}" opacity=".7"/>', W / 2, H / 2, 1.1, 1.0, 11.4, 3.8)
                  + c.camera(_ringed_planet(c, 600, 176, 128), 600, 176, .9, 1.0, 11.4, 3.8)
                  + f'<g class="§fi" style="animation-delay:12s"><ellipse cx="250" cy="158" rx="190" ry="60" fill="url(#{glow})"/>'
                  f'<text x="250" y="170" font-family="{BRUSH}" font-size="52" text-anchor="middle" fill="{GOLD_CORE}">{TITLE_A}</text></g>'
                  f'<text class="§fi" style="animation-delay:12.7s" x="250" y="206" font-family="{EN6}" font-size="12" '
                  f'text-anchor="middle" letter-spacing="6" fill="{SILVER}">SEVEN DAYS · ONE YEAR</text>')

    # 海报帧：行星悬在银心之上
    divider = c.lin([(0, '#c9d2e0', 0), (.5, '#c9d2e0', .28), (1, '#c9d2e0', 0)], x2=0, y2=1)
    poster = (f'<g style="animation:§drift 70s ease-in-out 15s infinite alternate"><use href="#{sky}" {SKY_FIT} opacity=".8"/></g>'
              + c.stars(42)
              + c.meteors([(700, -10, 155, 22, 15), (300, -10, 150, 31, 19)])
              + f'<text x="415" y="54" font-family="{BRUSH}" font-size="32" text-anchor="middle" fill="{GOLD_CORE}">{TITLE_A}</text>'
              f'<text x="415" y="77" font-family="{EN6}" font-size="10" text-anchor="middle" letter-spacing="5" fill="{SILVER}">'
              f'SEVEN DAYS · ONE YEAR</text>'
              f'<rect x="414.5" y="104" width="1" height="172" fill="url(#{divider})"/>'
              + ''.join(f'<text x="{x}" y="114" font-family="{EN6}" font-size="9" text-anchor="middle" letter-spacing="3.5" '
                        f'fill="{MUTED}">{t}</text>' for x, t in ((207.5, 'THIS WEEK'), (622.5, 'THIS YEAR')))
              + _lineup(c, wrows, wtotal, 207.5, 166, 74, 54, seed=1)
              + _lineup(c, yrows, ytotal, 622.5, 166, 74, 54, seed=2)
              + f'<text class="§sub" x="207.5" y="276" font-family="{EN}" font-size="12.5" text-anchor="middle" fill="{SILVER}">'
              f'{wtotal:,} lines changed in {weekly_days} days</text>'
              f'<text class="§sub" x="622.5" y="276" font-family="{EN}" font-size="12.5" text-anchor="middle" fill="{SILVER}">'
              f'{ytotal:,} lines changed in {yearly_days} days</text>'
              f'<text class="§sub" x="415" y="327" font-family="{EN6}" font-size="9" text-anchor="middle" letter-spacing="3.5" '
              f'fill="{MUTED}">A FILM WRITTEN IN {n_langs} LANGUAGE{"" if n_langs == 1 else "S"}</text>')
    final = f'<g style="animation:§in 1.6s ease-out 14.6s both">{poster}</g>'
    return c.svg(a1 + a2 + a3 + a4 + final + s1 + s2 + s3)


# ---------- 《我很少见到早晨》：作息 ----------

def _noise1d(seed: int, period: float, amp: float):
    """一维值噪声：每 period 像素一个随机值，余弦插值"""
    r = random.Random(seed)
    vals = [r.uniform(-1, 1) for _ in range(int(W / period) + 4)]

    def f(x):
        u = (x + period) / period
        i = int(u)
        t = (1 - math.cos((u - i) * math.pi)) / 2
        return amp * (vals[i] * (1 - t) + vals[i + 1] * t)
    return f


def _range(peaks, base, floor, seed, rough=1.0, step=3, curve=1.3):
    """若干座山峰的包络：坡面略内凹，叠两层碎石噪声；peaks: [(x, 高度, 半宽)]"""
    n1, n2 = _noise1d(seed, 23, 4.5 * rough), _noise1d(seed + 1, 7, 1.8 * rough)
    pts, x = [], -6.0
    while x <= W + 6:
        hgt = max((p * max(0.0, 1 - abs(x - px) / hw) ** curve for px, p, hw in peaks), default=0)
        hgt = max(hgt, floor) + (n1(x) + n2(x)) * min(1, hgt / 40)
        pts.append((x, base - hgt))
        x += step
    return pts


def _ridge(hours, base, lo, hi):
    """由 24 小时提交数堆成的山脊：每小时一座山，峰高按提交数（略作压缩，避免只剩一座孤峰）"""
    mx = max(hours) or 1
    sw = W / 24
    peaks = [((h + .5) * sw, lo + (hi - lo) * (n / mx) ** .85, sw * 2.4) for h, n in enumerate(hours)]
    return _range(peaks, base, lo * .7, 17, curve=1.08)


def _poly(pts) -> str:
    return 'M' + 'L'.join(f"{_n(x)} {_n(y)}" for x, y in pts)


def render_activity_film(matrix: list, profile_days: int) -> str:
    """作息短片。matrix: 7x24，[weekday][hour]，Monday=0"""
    hours = [sum(matrix[d][h] for d in range(7)) for h in range(24)]
    days = [sum(matrix[d]) for d in range(7)]
    total = sum(hours)
    cats = {'Night': sum(hours[0:6]), 'Morning': sum(hours[6:12]), 'Daytime': sum(hours[12:18]), 'Evening': sum(hours[18:24])}
    ranked = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    top = ranked[0][0] if total and (ranked[0][1] - ranked[1][1]) / total >= .05 else (
        'Night' if cats['Evening'] + cats['Night'] >= cats['Morning'] + cats['Daytime'] else 'Morning')
    rare = min(cats, key=lambda k: cats[k])
    rare_zh, rare_en, (sky_c, hor_c, sun_c) = RARE[rare]
    best_s = max(range(24), key=lambda s: sum(hours[(s + k) % 24] for k in range(3)))
    peak_label = f"{best_s:02d}:00–{(best_s + 3) % 24:02d}:00"
    busiest = max(range(7), key=lambda d: days[d])
    dark = cats['Evening'] + cats['Night']
    dark_pct = dark / total * 100 if total else 0
    span_zh = ZH_SPANS.get(profile_days, f' {profile_days} 天')
    title_en = f"I RARELY SEE {rare_en.upper()}"
    label = (f"{title_en} — I'm {PROFILE[top]}: {total:,} commits in {profile_days} days, "
             f"most awake {peak_label}, busiest on {WEEKDAYS_EN[busiest]}")
    c = _Film('A', 11, label)
    sky = c.image('sky_b.webp', W, H)
    gal = c.image('galaxy.webp', 256, 256)

    # B1 黑场 · 一点光
    b1 = c.window(0, 3.8, f'<g style="animation:§breathe 1.1s steps(1) 3">{c.light(W / 2, 140)}</g>', fade=.7)
    en1 = (f"This past year, I committed {total:,} times." if profile_days == 365
           else f"In the past {profile_days} days, I committed {total:,} times.")
    s1 = c.subtitle(ZH_TEXT['commits'].format(span=span_zh, n=f'{total:,}'), en1, 1.0, 3.6, y=208)

    # B2 倾斜旋转的星系：压扁的圆盘在自身平面内旋转，就是真实的 3D 投影
    core = c.rad([(0, '#ffe6b8', .5), (.4, '#c9a2ff', .12), (1, '#c9a2ff', 0)])
    galaxy = (f'<g transform="translate(415 150)"><ellipse rx="300" ry="120" fill="url(#{core})"/>'
              f'<g transform="rotate(-16) scale(1 .4)"><g style="animation:§spin 140s linear infinite">'
              f'<use href="#{gal}" transform="translate(-269 -269) scale(2.1)"/></g></g></g>')
    b2 = c.window(3.4, 7.8, c.stars(60) + c.camera(galaxy, 415, 150, .92, 1.12, 3.4, 4.4))
    if not total:
        zh2, en2 = ZH_TEXT['quiet'], "Quiet."
    elif dark >= total - dark:
        zh2, en2 = ZH_TEXT['dark'], f"Most of them after dark — {dark_pct:.0f}%."
    else:
        zh2, en2 = ZH_TEXT['light'], f"Most of them in daylight — {100 - dark_pct:.0f}%."
    s2 = c.subtitle(zh2, en2, 5.0, 7.6)

    # B3 一周的月亮依次升起：越忙越圆
    mx = max(days) or 1
    hz = c.lin([(0, '#0b1020', 0), (1, '#0b1020', 1)], x2=0, y2=1)
    rise = c.kf("from{opacity:0;transform:translateY(46px)}")
    moons3 = []
    for d in range(7):
        x = 415 + (d - 3) * 92
        y = 150 - 52 * math.sin(math.pi * d / 6)
        r = 9 + 9 * days[d] / mx
        moons3.append(f'<g transform="translate({_n(x)} {_n(y)})"><g style="animation:{rise} 1.8s cubic-bezier(.16,1,.3,1) '
                      f'{8 + d * .32:.2f}s both">{c.moon(r, .25 + .75 * days[d] / mx)}'
                      f'<text y="{_n(r + 20)}" font-family="{EN6}" font-size="10" text-anchor="middle" letter-spacing="2.5" '
                      f'fill="{INK if d == busiest else MUTED}">{WEEKDAYS[d].upper()}</text></g></g>')
    b3 = c.window(7.4, 11.8, c.camera(f'<use href="#{sky}" opacity=".6"/>', W / 2, H, 1.2, 1.12, 7.4, 4.4)
                  + ''.join(moons3) + f'<rect y="230" width="{W}" height="117" fill="url(#{hz})"/>')
    if total:
        s3 = c.subtitle(ZH_TEXT['busiest'].format(d=WEEKDAYS_ZH[busiest]), f"{WEEKDAYS_EN[busiest]} are the busiest.", 9.2, 11.6)
    else:
        s3 = c.subtitle(ZH_TEXT['quiet'], "Quiet.", 9.2, 11.6)

    # B4 日出：那段很少见到的时光
    skyg = c.lin([(0, '#020306', 1), (.55, sky_c, 1), (.86, hor_c, 1), (1, _mix(hor_c, sun_c, .5), 1)], x2=0, y2=1)
    bloom = c.rad([(0, sun_c, .55), (.3, sun_c, .18), (1, hor_c, 0)])
    sun = c.rad([(0, '#fffaf0', 1), (.6, sun_c, 1), (1, _mix(sun_c, hor_c, .4), 1)])
    sea = c.lin([(0, _mix(hor_c, '#000000', .55), 1), (1, '#020306', 1)], x2=0, y2=1)
    rr = random.Random(5)
    glints = []
    for _ in range(46):
        gy = 258 + rr.random() ** 1.6 * 88
        gx = 415 + rr.gauss(0, (20 + (gy - 258) * 1.6) * .45)
        gw = rr.uniform(4, 16) * (1 + (gy - 258) / 60)
        glints.append(f'<rect x="{_n(gx - gw / 2)}" y="{_n(gy)}" width="{_n(gw)}" height="1.2" fill="{sun_c}" class="§tw" '
                      f'style="animation-duration:{rr.uniform(1.2, 2.8):.1f}s;animation-delay:{rr.uniform(0, 2):.1f}s" '
                      f'opacity="{rr.uniform(.35, .9):.2f}"/>')
    sunrise = c.kf("from{transform:translateY(64px)}to{transform:translateY(8px)}")
    streak = c.lin([(0, sun_c, 0), (.5, '#fff6e6', .7), (1, sun_c, 0)])
    b4 = c.window(11.4, 15.6, f'<rect width="{W}" height="258" fill="url(#{skyg})"/>'
                  f'<g style="animation:{sunrise} 4.2s cubic-bezier(.3,0,.3,1) 11.4s both">'
                  f'<circle cx="415" cy="258" r="240" fill="url(#{bloom})"/><circle cx="415" cy="258" r="46" fill="url(#{sun})"/></g>'
                  f'<rect y="258" width="{W}" height="89" fill="url(#{sea})"/>{"".join(glints)}'
                  f'<rect x="65" y="257.4" width="700" height="1.4" fill="url(#{streak})"/>', fade=1.0)
    s4 = c.subtitle(ZH_TEXT['rare'].format(p=rare_zh), f"I rarely see {rare_en.lower()}.", 12.4, 15.4, y=86)

    # 海报帧：银河、月相、群山，金色的光站在提交最多的那个小时的山顶
    base = 300
    ridge = _ridge(hours, base, 16, 104)
    rb = random.Random(23)
    far = _range([(x, rb.uniform(40, 92), rb.uniform(50, 110)) for x in range(-20, W + 60, 55)], base - 6, 34, 31, rough=.6)
    mid = _range([(x, rb.uniform(26, 62), rb.uniform(40, 80)) for x in range(-10, W + 40, 38)], base, 22, 37, rough=.8)
    haze = c.lin([(0, '#3a4660', 0), (1, '#3a4660', .5)], x2=0, y2=1)
    rimg = c.lin([(0, '#c9d6ea', .3), (.6, '#ffd9a0', .5), (1, '#c9d6ea', .25)])
    rare_x = {'Night': 3, 'Morning': 9, 'Daytime': 15, 'Evening': 21}[rare] * W / 24
    dawn = c.rad([(0, hor_c, .55), (1, hor_c, 0)])
    px = (max(range(24), key=lambda h: hours[h]) + .5) * W / 24
    py = min(y for x, y in ridge if abs(x - px) < 2)
    moons = []
    for d in range(7):
        r = 5.5 + 5 * days[d] / mx
        strong = d == busiest and total
        pct = days[d] / total * 100 if total else 0
        moons.append(f'<g transform="translate({534 + d * 44} {_n(104 - 38 * math.sin(math.pi * d / 6))})">'
                     f'{c.moon(r, .25 + .75 * days[d] / mx)}'
                     f'<text y="{_n(r + 14)}" font-family="{EN6}" font-size="7.5" text-anchor="middle" letter-spacing="1.5" '
                     f'fill="{INK if strong else MUTED}">{WEEKDAYS[d].upper()}</text>'
                     f'<text y="{_n(r + 26)}" font-family="{EN6}" font-size="10" text-anchor="middle" '
                     f'fill="{GOLD if strong else SILVER}">{pct:.0f}%</text></g>')
    labels = ''.join(f'<text x="{_n((h0 + 3) * W / 24)}" y="333" text-anchor="middle"><tspan font-family="{EN6}" font-size="8.5" '
                     f'letter-spacing="2.5" fill="{GOLD if name == rare else MUTED}">{name.upper()}</tspan>'
                     f'<tspan font-family="{EN6}" font-size="11.5" fill="{INK}" dx="7">'
                     f'{cats[name] / total * 100 if total else 0:.1f}%</tspan></text>' for name, h0 in PERIODS)
    ticks = ''.join(f'<text x="{_n(h * W / 24)}" y="318" font-family="{EN6}" font-size="8.5" text-anchor="middle" fill="{MUTED}">'
                    f'{h:02d}</text>' for h in (6, 12, 18))
    poster = (f'<g style="animation:§drift 70s ease-in-out 16s infinite alternate"><use href="#{sky}" {SKY_FIT}/></g>'
              + c.stars(40, (0, 0, W, 220))
              + c.meteors([(320, -10, 150, 24, 16), (760, -10, 158, 35, 21)])
              + f'<ellipse cx="{_n(rare_x)}" cy="{base - 30}" rx="210" ry="80" fill="url(#{dawn})" opacity=".55"/>'
              f'<path d="{_poly(far)}L{W + 6} {H}L-6 {H}Z" fill="#0d1320"/>'
              f'<rect y="190" width="{W}" height="120" fill="url(#{haze})" opacity=".3"/>'
              f'<path d="{_poly(mid)}L{W + 6} {H}L-6 {H}Z" fill="#070a11"/>'
              f'<path d="{_poly(ridge)}L{W + 6} {H}L-6 {H}Z" fill="#020305"/>'
              f'<path d="{_poly(ridge)}" fill="none" stroke="url(#{rimg})" stroke-width=".8"/>'
              f'<g style="animation:§breathe 4s ease-in-out infinite">{c.light(px, py - 9, h=12, flare=.5)}</g>'
              + ''.join(moons) + labels + ticks
              + f'<text x="40" y="62" font-family="{BRUSH}" font-size="32" fill="{GOLD_CORE}">{TITLE_B.format(p=rare_zh)}</text>'
              f'<text x="41" y="86" font-family="{EN6}" font-size="10" letter-spacing="4.2" fill="{SILVER}">{title_en}</text>'
              f'<text x="40" y="114" font-family="{EN}" font-size="15" fill="{INK}">I&#x27;m {PROFILE[top]}.</text>'
              f'<text x="40" y="134" font-family="{EN}" font-size="12.5" fill="{SILVER}">{total:,} commits in {profile_days} days · '
              f'most awake {peak_label} · busiest on {WEEKDAYS_EN[busiest]}</text>')
    final = f'<g style="animation:§in 1.6s ease-out 15s both">{poster}</g>'
    return c.svg(b1 + b2 + b3 + b4 + final + s1 + s2 + s3 + s4)
