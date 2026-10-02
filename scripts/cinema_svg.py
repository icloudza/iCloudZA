#!/usr/bin/env python3
"""把语言统计和作息画像渲染成一支约 30 秒的「电影短片」式动画 SVG（运行时无第三方依赖）

风格参考短片《我从未见过太阳》：纯黑与冷银灰，唯一的暖金色光；宽字距衬线体，中英双语字幕；镜头之间淡入淡出。
16:9 画幅：开场在 2.39:1 的宽银幕带里播（字幕放在下方黑边），约 30 秒后定格为一整张海报。

性能约定（GitHub 用 <img> 显示 SVG，任何一处动画在跑，整张图每帧都要重绘）：
- 镜头只在自己的时间窗内可见，窗口外是 visibility:hidden，不参与绘制；
- 镜头里的动画都是有限次、只在窗口内运行，没有 infinite；
- 海报帧完全静止，开场播完后图片不再重绘。
静态属性即终态：动画不运行的环境（含 prefers-reduced-motion）直接显示海报帧。
位图素材与字体子集在 assets/cinema/，由 make_assets.py 离线生成后提交，渲染时 base64 内嵌。
"""

import base64
import math
import os
import random
from html import escape

W, H = 830, 467            # 16:9，宽度与 README 正文一致
BAND_Y, BAND_H = 60, 347   # 开场用的 2.39:1 宽银幕带
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

# 字体：内嵌子集优先，缺字时按顺序回退到下一个字体
EN = "CG,'Cormorant Garamond','EB Garamond',Garamond,'Times New Roman',serif"
ZH = "NS,CG,'Noto Serif SC','Source Han Serif SC','Songti SC',STSong,SimSun,serif"
BRUSH = "ZM,'Zhi Mang Xing',STXingkai,'Xingkai SC',KaiTi,cursive"
SEA = "CG,NS,KR,GR,'Noto Serif','Noto Serif CJK SC',serif"   # 多语种单词：拉丁 / 西里尔、汉字、韩文、希腊文各走各的子集
FONT_FILES = {'CG': 'cg500.woff2', 'NS': 'nss500.woff2', 'ZM': 'zmx400.woff2', 'KR': 'kr500.woff2', 'GR': 'gr500.woff2'}

INK, SILVER, MUTED = '#eef1f6', '#b9c1ce', '#7f8898'
GOLD, GOLD_CORE = '#ffc978', '#fff3dc'

PERIODS = (('Night', 0), ('Morning', 6), ('Daytime', 12), ('Evening', 18))   # (时段, 起始小时)
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
WEEKDAYS_EN = ['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
# 最少的时段 →（中文，英文片名，英文问句，日出镜头的天色：天空 / 地平线 / 太阳）
RARE = {
    'Morning': ('早晨', 'the Morning', 'the morning', ('#2b1d2c', '#c98172', '#ffe1a8')),
    'Daytime': ('白天', 'the Daylight', 'daylight', ('#1c2a3c', '#9fb8cf', '#fff8ea')),
    'Evening': ('黄昏', 'the Dusk', 'the dusk', ('#2a1830', '#d27a4e', '#ffc98a')),
    'Night': ('深夜', 'Midnight', 'midnight', ('#05070f', '#24304f', '#dfe6f2')),
}
PROFILE = {'Morning': "an early bird", 'Daytime': "a daytime coder", 'Evening': "an evening coder", 'Night': "a night owl"}
COMMON = {'Night': ('深夜', 'night'), 'Evening': ('傍晚', 'evening'), 'Morning': ('清晨', 'morning'), 'Daytime': ('白天', 'day')}

# 致敬原片里由各国语言的「海」组成的海面：这里换成各国语言的「语言」；片名卡的文字环用各国语言的「夜」
LANG_WORDS = ('language', '语言', 'langue', 'Sprache', 'lengua', 'язык', '言語', '언어', 'lingua', 'língua', 'taal', 'språk',
              'dil', 'bahasa', 'kieli', 'język', 'lugha', 'ngôn ngữ', 'γλώσσα', 'jazyk', 'nyelv', 'lingvo', 'iaith', 'teanga',
              'tungumál', 'мова', 'sprog', 'jezik', 'kalba', 'valoda', 'keel', 'limbă', 'wika', 'reo', 'ʻōlelo')
NIGHT_WORDS = ('night', '夜晚', 'nuit', 'Nacht', 'noche', 'ночь', '夜', '밤', 'notte', 'noite', 'nacht', 'natt', 'gece', 'malam',
               'yö', 'noc', 'usiku', 'đêm', 'νύχτα', 'éjszaka', 'nox', 'nokto', 'nos', 'oíche', 'nótt', 'ніч', 'naktis', 'nakts',
               'öö', 'noapte', 'gabi', 'pō', 'nat')

# 片名（书法字体）和中文字幕模板。make_assets.py 按这里出现的字做字体子集，改文案后要重新生成字体
TITLE = '我很少见到{p}'
ZH_TEXT = {
    'ask': '你见过{p}吗？',
    'answer': '很少。',
    'commits_dark': '过去{span}，我提交了 {n} 次，大多在天黑以后。',
    'commits_light': '过去{span}，我提交了 {n} 次，大多在天亮以后。',
    'lines': '这{span}，我改动了 {n} 行代码。',
    'lines_none': '这{span}，我一行代码也没写。',
    'week_major': '大多是 {lang}。',
    'week_minor': '{lang} 写得最多。',
    'year': '这{span}，我说得最多的是 {lang}。',
    'rare': '我很少见到{p}。',
    'glow': '但每个{c}，都有一束光。',
    'quiet': '很安静。',
}
ZH_SPANS = {7: '七天', 365: '一年'}
EN_SPANS = {7: 'seven days', 365: 'a year'}


def _cjk(text: str) -> set:
    return {ch for ch in text if ord(ch) > 0x2e80 and not 0xac00 <= ord(ch) <= 0xd7af}


def zh_chars() -> str:
    """字幕字体子集需要的汉字和中文标点（含多语种单词里的汉字）"""
    text = (''.join(ZH_TEXT.values()) + ''.join(ZH_SPANS.values()) + '天' + ''.join(LANG_WORDS + NIGHT_WORDS)
            + ''.join(v[0] for v in RARE.values()) + ''.join(v[0] for v in COMMON.values()))
    return ''.join(sorted(_cjk(text)))


def brush_chars() -> str:
    return ''.join(sorted(_cjk(TITLE + ''.join(v[0] for v in RARE.values()))))


def word_chars(script: str) -> str:
    """多语种单词里各文字系统用到的字符：latin（含西里尔）/ hangul / greek"""
    chars = set(''.join(LANG_WORDS + NIGHT_WORDS))
    pick = {'hangul': lambda o: 0xac00 <= o <= 0xd7af, 'greek': lambda o: 0x370 <= o <= 0x3ff,
            'latin': lambda o: 0x7f < o < 0x2e80 and not 0x370 <= o <= 0x3ff}[script]
    return ''.join(sorted(ch for ch in chars if pick(ord(ch))))


BASE_CSS = (
    "@keyframes §in{from{opacity:0}}"
    "@keyframes §out{to{opacity:0}}"
    "@keyframes §rise{from{opacity:0;transform:translateY(8px)}}"
    "@keyframes §blink{50%{opacity:.12}}"
    "@keyframes §dash{from{stroke-dashoffset:1}}"
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


def _pt(r: float, deg: float):
    a = math.radians(deg)
    return r * math.cos(a), r * math.sin(a)


def _arc(r: float, a0: float, a1: float) -> str:
    (x0, y0), (x1, y1) = _pt(r, a0), _pt(r, a1)
    return f"M{_n(x0)} {_n(y0)}A{_n(r)} {_n(r)} 0 {1 if (a1 - a0) % 360 > 180 else 0} 1 {_n(x1)} {_n(y1)}"


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

    def image(self, name: str, w: int, h: int) -> str:
        """位图只内嵌一次，之后用 <use> 引用"""
        key = ('img', name)
        if key not in self._cache:
            iid = self.nid('m')
            self.defs.append(f'<image id="{iid}" width="{w}" height="{h}" preserveAspectRatio="none" '
                             f'href="data:image/webp;base64,{_asset(name)}"/>')
            self._cache[key] = iid
        return self._cache[key]

    # ---------- 时间轴与运镜 ----------

    def window(self, t0: float, t1: float, body: str, fade: float = .6) -> str:
        """只在 [t0, t1] 出现的镜头 / 字幕：窗口外 visibility:hidden，整组不参与绘制"""
        d = t1 - t0
        f = min(fade / d * 100, 45)
        k = self.kf(f"0%{{visibility:visible;opacity:0}}{f:.2f}%{{opacity:1}}{100 - f:.2f}%{{opacity:1}}"
                    f"100%{{visibility:visible;opacity:0}}")
        return f'<g visibility="hidden" opacity="0" style="animation:{k} {d:.2f}s linear {t0:.2f}s">{body}</g>'

    def camera(self, body: str, cx: float, cy: float, s0: float, s1: float, t0: float, dur: float,
               dx: float = 0, dy: float = 0) -> str:
        """运镜：以 (cx, cy) 为中心推拉（s0→s1）并平移（dx, dy），只跑一次"""
        k = self.kf(f"from{{transform:scale({s0})}}to{{transform:translate({dx}px,{dy}px) scale({s1})}}")
        return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g style="animation:{k} {dur:.2f}s ease-in-out {t0:.2f}s both">'
                f'<g transform="translate({_n(-cx)} {_n(-cy)})">{body}</g></g></g>')

    def subtitle(self, zh: str, en: str, t0: float, t1: float) -> str:
        """字幕放在下方黑边里，不压画面"""
        body = (f'<text x="{_n(W / 2)}" y="431" font-family="{ZH}" font-size="14.5" text-anchor="middle" '
                f'fill="{INK}" letter-spacing="1.5">{escape(zh)}</text>'
                f'<text x="{_n(W / 2)}" y="452" font-family="{EN}" font-size="14.5" text-anchor="middle" '
                f'fill="{SILVER}" letter-spacing=".4">{escape(en)}</text>')
        return self.window(t0, t1, body, fade=.45)

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

    def typed(self, text: str, y: float, t0: float, until: float, cps: float = 6, size: float = 19,
              lead: float = .8, hide_at: float = None) -> str:
        """逐字打出一行中文（汉字和全角标点都是 1em 宽，能精确算出光标位置）；光标先亮、打完后原地闪烁到 until"""
        ls = 2
        adv, n = size + ls, len(text)
        left = W / 2 - (n * adv - ls) / 2
        dur = (n + 1) / cps
        kts = ';'.join(f"{k / (n + 1):.4f}" for k in range(n + 1))
        widths = ';'.join(_n(k * adv + 2) for k in range(n + 1))
        moves = ';'.join(f"{_n(k * adv)} 0" for k in range(n + 1))
        clip = self.nid('c')
        self.defs.append(f'<clipPath id="{clip}"><rect x="{_n(left - 2)}" y="{_n(y - size * 1.1)}" width="0" height="{_n(size * 1.6)}">'
                         f'<animate attributeName="width" calcMode="discrete" values="{widths}" keyTimes="{kts}" '
                         f'begin="{t0:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        start = t0 - lead
        blinks = max(1, math.ceil(((hide_at or until) - start) / 1.05))
        gone = f'<g style="animation:§out .3s ease-out {hide_at:.2f}s both">' if hide_at else '<g>'
        return (f'<text x="{_n(left)}" y="{_n(y)}" font-family="{ZH}" font-size="{size}" letter-spacing="{ls}" fill="{INK}" '
                f'clip-path="url(#{clip})">{escape(text)}</text>'
                f'<g style="animation:§in .3s ease-out {start:.2f}s both">{gone}'
                f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" values="{moves}" '
                f'keyTimes="{kts}" begin="{t0:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                f'<g style="animation:§blink 1.05s steps(1) {start:.2f}s {blinks}">'
                f'{self.light(left + 5, y - size * .36, h=size * 1.2, flare=.5)}</g></g></g>')

    def stars(self, n: int, area=(0, 0, W, H), op: float = .75) -> str:
        """静态矢量星点（不闪烁：任何循环动画都会让整张图每帧重绘）"""
        r = self.rng
        x0, y0, x1, y1 = area
        pts = [(r.uniform(x0, x1), r.uniform(y0, y1)) for _ in range(n)]
        big = pts[:n // 6]
        return (f'<path d="{_dots(pts[n // 6:])}" fill="none" stroke="#e8eef8" stroke-width="1.1" stroke-linecap="round" opacity="{op}"/>'
                f'<path d="{_dots(big)}" fill="none" stroke="#f4f7fc" stroke-width="1.8" stroke-linecap="round" opacity="{op}"/>')

    def planet(self, d: float, color: str, gold: bool = False, phase: float = 0, roll=None) -> str:
        """3D 行星（以原点为中心）：条带纹理 + 球面明暗 + 晨昏线 + 边缘光；roll=(开始秒, 时长) 时纹理缓慢滑动一次，模拟自转"""
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
        texture = f'<use href="#{tex}"/><use href="#{tex}" x="420"/>'
        if roll:
            k = self.kf(f"to{{transform:translateX(-{_n(roll[1] * 9)}px)}}")
            texture = f'<g style="animation:{k} {roll[1]:.2f}s linear {roll[0]:.2f}s both">{texture}</g>'
        return (f'<circle r="{_n(r * 1.36)}" fill="url(#{atm})"/>'
                f'<g clip-path="url(#{clip})"><circle r="{_n(r)}" fill="{base}"/>'
                f'<g transform="translate({_n(-r - phase * d)} {_n(-r)}) scale({d / 128:.4f})" opacity=".5">{texture}</g>'
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

    # ---------- 镜头里的大场面（坐标都在宽银幕带内：830×347） ----------

    def word_sea(self, words, t0: float, t1: float, hy: float = 170, rows: int = 8, period: float = 5.5) -> str:
        """文字组成的海：每行放在「单位深度」，绕地平线上的消失点放大即透视飞越；各行错开起跑，只在镜头窗口内循环"""
        r = self.rng
        k = self.kf("0%{transform:scale(.16);opacity:0}16%{opacity:.75}80%{opacity:.9}100%{transform:scale(4.4);opacity:0}")
        glow = self.lin([(0, '#8fa3c7', 0), (.5, '#8fa3c7', .22), (1, '#8fa3c7', 0)], x2=0, y2=1)
        path = self.lin([(0, GOLD, .55), (1, GOLD, 0)], x2=0, y2=1)
        out = [f'<rect y="{_n(hy - 30)}" width="{W}" height="60" fill="url(#{glow})"/>']
        for i in range(rows):
            seq = list(words)
            r.shuffle(seq)
            text = escape('  '.join(seq + seq[:9]))
            delay = t0 - period + i * period / rows
            runs = math.ceil((t1 - delay) / period)
            out.append(f'<g transform="translate({_n(W / 2)} {_n(hy)})"><g style="animation:{k} {period}s cubic-bezier(.6,0,.96,.52) '
                       f'{delay:.2f}s {runs}"><text x="{r.uniform(-1000, -900):.0f}" y="40" font-family="{SEA}" font-size="9" '
                       f'fill="#b3bfd2">{text}</text></g></g>')
        out.append(f'<rect x="{_n(W / 2 - 1.5)}" y="{_n(hy)}" width="3" height="{_n(BAND_H - hy)}" fill="url(#{path})" opacity=".8"/>'
                   + self.light(W / 2, hy - 9, h=13, flare=1.3))
        return ''.join(out)

    def warp(self, cx: float, cy: float, t0: float, t1: float, n: int = 64) -> str:
        """光速穿梭：从中心向外辐射的光痕加速掠过，只在镜头窗口内重复"""
        r = self.rng
        k = self.kf("from{stroke-dashoffset:.3}to{stroke-dashoffset:-1}")
        core = self.rad([(0, '#ffffff', .9), (.2, '#ffe9c4', .45), (1, '#ffd9a0', 0)])
        lines = []
        for _ in range(n):
            a = r.uniform(0, 2 * math.pi)
            r0 = r.uniform(14, 70)
            dur = r.uniform(.5, 1.1)
            begin = t0 + r.uniform(0, .5)
            lines.append(f'<path d="M{_n(cx + r0 * math.cos(a))} {_n(cy + r0 * math.sin(a))}L{_n(cx + 640 * math.cos(a))} '
                         f'{_n(cy + 640 * math.sin(a))}" pathLength="1" stroke-dasharray="{r.uniform(.07, .24):.2f} 3" '
                         f'stroke-dashoffset=".3" stroke="{GOLD if r.random() < .18 else "#e3ebfb"}" '
                         f'stroke-opacity="{r.uniform(.35, .95):.2f}" stroke-width="{r.uniform(.5, 1.7):.1f}" '
                         f'style="animation:{k} {dur:.2f}s cubic-bezier(.65,0,1,.6) {begin:.2f}s {math.ceil((t1 - begin) / dur)}"/>')
        return f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="90" fill="url(#{core})"/>' + ''.join(lines)

    def text_rings(self, words, cx: float, cy: float, radii, size: float = 8.5) -> str:
        """片名卡的同心文字环（致敬原片片名卡）；静止不转，旋转的文字每帧都要重新栅格化"""
        out = []
        for i, rr in enumerate(radii):
            pid = self.nid('p')
            self.defs.append(f'<path id="{pid}" d="M{_n(rr)} 0A{_n(rr)} {_n(rr)} 0 1 1 {_n(-rr)} 0A{_n(rr)} {_n(rr)} 0 1 1 {_n(rr)} 0"/>')
            seq = list(words)
            self.rng.shuffle(seq)
            text = escape('\u2002·\u2002'.join(seq * 3))
            out.append(f'<text font-family="{SEA}" font-size="{size}" fill="#c3ccdb" opacity="{max(.12, .55 - i * .08):.2f}" '
                       f'letter-spacing=".6" transform="rotate({self.rng.uniform(0, 360):.0f})"><textPath href="#{pid}">{text}</textPath></text>')
        return f'<g transform="translate({_n(cx)} {_n(cy)})">{"".join(out)}</g>'


    # ---------- 输出 ----------

    def svg(self, layers: str) -> str:
        font_css = ''.join(f"@font-face{{font-family:{k};src:url(data:font/woff2;base64,{_asset('fonts/' + f)}) format('woff2')}}"
                           for k, f in FONT_FILES.items())
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
               f'aria-label="{escape(self.label)}"><title>{escape(self.label)}</title>'
               f'<style>{font_css}{"".join(self.css)}</style>'
               f'<defs><clipPath id="§frame"><rect width="{W}" height="{H}" rx="10"/></clipPath>{"".join(self.defs)}</defs>'
               f'<g clip-path="url(#§frame)"><rect width="{W}" height="{H}" fill="#000"/>{layers}</g></svg>')
        return out.replace('§', self.uid)

# ---------- 数据 ----------

def _rows(stats: dict, top_n: int = 5):
    rows = sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)[:top_n]
    total = sum(v['added'] + v['deleted'] for v in stats.values())
    return [(lang, v['added'] + v['deleted']) for lang, v in rows if v['added'] + v['deleted']], total


def _color(lang: str) -> str:
    return LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)


def _noise1d(seed: int, period: float, amp: float):
    """一维值噪声：每 period 像素一个随机值，余弦插值"""
    r = random.Random(seed)
    vals = [r.uniform(-1, 1) for _ in range(int(W / period) + 40)]

    def f(x):
        u = (x + period * 20) / period
        i = int(u)
        t = (1 - math.cos((u - i) * math.pi)) / 2
        return amp * (vals[i] * (1 - t) + vals[i + 1] * t)
    return f


def _range(peaks, base, floor, seed, rough=1.0, step=3, curve=1.3, x0=-6.0, x1=W + 6.0):
    """若干座山峰的包络：坡面略内凹，叠两层碎石噪声；peaks: [(x, 高度, 半宽)]"""
    n1, n2 = _noise1d(seed, 23, 4.5 * rough), _noise1d(seed + 1, 7, 1.8 * rough)
    pts, x = [], x0
    while x <= x1:
        hgt = max((p * max(0.0, 1 - abs(x - px) / hw) ** curve for px, p, hw in peaks), default=0)
        hgt = max(hgt, floor) + (n1(x) + n2(x)) * min(1, hgt / 40)
        pts.append((x, base - hgt))
        x += step
    return pts


def _poly(pts) -> str:
    return 'M' + 'L'.join(f"{_n(x)} {_n(y)}" for x, y in pts)


# ---------- 镜头 ----------

def _lineup(c: _Film, rows, total, cx, cy, slot, dmax, name_size=12.5):
    """海报里的一排行星：直径按占比开方缩放，第一名带金色边缘光"""
    if not rows:
        return (f'<text x="{_n(cx)}" y="{_n(cy)}" font-family="{EN}" font-size="14" text-anchor="middle" fill="{MUTED}">'
                f'silence, for now</text>')
    top, n = rows[0][1], len(rows)
    out = []
    for i, (lang, lines) in enumerate(rows):
        x = cx + (i - (n - 1) / 2) * slot
        d = 14 + (dmax - 14) * math.sqrt(lines / top)
        pct = lines / total * 100 if total else 0
        out.append(f'<g transform="translate({_n(x)} {_n(cy)})">{c.planet(d, _color(lang), i == 0, (i * .37) % 1)}'
                   f'<text class="§sub" y="{_n(dmax / 2 + name_size + 8)}" font-family="{EN}" font-size="{name_size}" '
                   f'text-anchor="middle" fill="{INK}" letter-spacing=".3">{escape(lang)}</text>'
                   f'<text class="§sub" y="{_n(dmax / 2 + name_size * 2 + 11)}" font-family="{EN}" font-size="{_n(name_size * 1.04)}" '
                   f'text-anchor="middle" fill="{GOLD if i == 0 else SILVER}">{pct:.1f}%</text></g>')
    return ''.join(out)


def _star_trails(c: _Film, hours, peak, cx: float, cy: float, t0: float) -> str:
    """星轨延时：每小时占 15° 的扇区，扇区里的星轨条数按这一小时的提交数；从 0 点起逐小时曝光，高峰时段是金色"""
    r = c.rng
    mx = max(hours) or 1
    k = c.kf("from{stroke-dashoffset:1}")
    groups = []
    for h, n in enumerate(hours):
        a0 = h * 15 - 90
        arcs = ''.join(f'<path d="{_arc(26 + 440 * r.random() ** .85, a0 + .4, a0 + 14.6)}" pathLength="1" '
                       f'stroke-opacity="{r.uniform(.3, .9):.2f}" stroke-width="{r.uniform(.5, 1.4):.1f}"/>'
                       for _ in range(round(2 + 6 * n / mx)))
        # stroke-dashoffset 是继承属性，整组共用一个「逐小时曝光」的动画
        groups.append(f'<g stroke="{GOLD if h in peak else "#d6deeb"}" style="animation:{k} 1s ease-out {t0 + h * .12:.2f}s both">'
                      f'{arcs}</g>')
    pole = c.rad([(0, '#ffffff', 1), (.25, '#dfe8ff', .5), (1, '#dfe8ff', 0)])
    return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g fill="none" stroke-dasharray="1">{"".join(groups)}</g>'
            f'<circle r="7" fill="url(#{pole})"/></g>')


def _flyby(c: _Film, rows, total, t0: float, t1: float, vx: float = W / 2, vy: float = 158) -> str:
    """本周的行星从远处迎面飞来、从镜头两侧掠过（绕消失点放大 = 透视）；名次倒序出场，第一名最后飞到画面右侧停住"""
    if not rows:
        return ''
    k = c.kf("0%{transform:scale(.05);opacity:0}14%{opacity:1}100%{transform:scale(3.2);opacity:1}")
    k1 = c.kf("0%{transform:scale(.05);opacity:0}14%{opacity:1}100%{transform:scale(2.3);opacity:1}")
    lk = c.kf("0%,34%{opacity:0}48%,70%{opacity:1}84%,100%{opacity:0}")
    top = rows[0][1]
    out = []
    for j, (i, (lang, lines)) in enumerate(list(enumerate(rows))[::-1]):
        side = 1 if j % 2 else -1
        dx, dy = side * (150 + 22 * (j % 3)), (-34 if j % 2 else 30)
        d = 24 + 46 * math.sqrt(lines / top)
        t = t0 + j * .5
        pct = lines / total * 100 if total else 0
        if i == 0:
            # 第一名停在画面右侧，配一个大号占比
            out.append(f'<g transform="translate({_n(vx)} {_n(vy)})"><g style="animation:{k1} 2.2s cubic-bezier(.3,0,.2,1) {t:.2f}s both">'
                       f'<g transform="translate(118 8)">{c.planet(d, _color(lang), True, .2, roll=(t, t1 - t))}</g></g></g>'
                       f'<g style="animation:§rise 1s ease-out {t + .9:.2f}s both">'
                       f'<text x="110" y="150" font-family="{EN}" font-size="54" fill="{GOLD_CORE}">{pct:.1f}%</text>'
                       f'<text x="112" y="174" font-family="{EN}" font-size="14" fill="{SILVER}" letter-spacing="1.2">'
                       f'of every line this week · {escape(lang)}</text></g>')
            continue
        lab = (f'<g style="animation:{lk} 2.6s linear {t:.2f}s both"><text class="§sub" y="{_n(d / 2 + 13)}" font-family="{EN}" '
               f'font-size="10" text-anchor="middle" fill="{INK}" letter-spacing=".4">{escape(lang)}'
               f'<tspan fill="{SILVER}" dx="5">{pct:.1f}%</tspan></text></g>')
        out.append(f'<g transform="translate({_n(vx)} {_n(vy)})"><g style="animation:{k} 2.6s cubic-bezier(.55,0,1,.5) {t:.2f}s both">'
                   f'<g transform="translate({dx} {dy})">{c.planet(d, _color(lang), False, (j * .31) % 1)}{lab}</g></g></g>')
    return ''.join(out)


def _orbits(c: _Film, rows, total, cx: float, cy: float, t0: float, t1: float) -> str:
    """本年的语言排成一个倾斜的行星系：名次越前离中央的恒星越近；轨道上写着语言名和占比，行星沿轨道运行"""
    if not rows:
        return ''
    sun = c.rad([(0, '#fff6e6', 1), (.25, GOLD, .8), (.6, '#ff9d42', .18), (1, '#ff9d42', 0)])
    top = rows[0][1]
    rings, bodies = [], []
    for i, (lang, lines) in enumerate(rows):
        rx = 96 + i * 50
        ry = rx * .3
        d = f"M{rx} 0A{rx} {_n(ry)} 0 1 0 {-rx} 0A{rx} {_n(ry)} 0 1 0 {rx} 0"
        pid = c.nid('p')
        c.defs.append(f'<path id="{pid}" d="{d}"/>')
        pct = lines / total * 100 if total else 0
        piece = f'{lang} · {pct:.1f}%'
        reps = max(2, int(2 * math.pi * math.sqrt((rx * rx + ry * ry) / 2) / (len(piece) * 4.6 + 26)))
        label = escape('   '.join([piece] * reps))
        rings.append(f'<use href="#{pid}" fill="none" stroke="#c9d2e0" stroke-opacity="{.32 - i * .03:.2f}" stroke-width=".7"/>'
                     f'<text font-family="{EN}" font-size="9" fill="{GOLD if i == 0 else "#c3ccdb"}" opacity=".78" letter-spacing=".5">'
                     f'<textPath href="#{pid}">{label}</textPath></text>')
        period = 9 * (rx / 96) ** 1.5
        begin = t0 - period * (i * .37 % 1)
        bodies.append(f'<g><animateMotion dur="{period:.1f}s" repeatCount="{math.ceil((t1 - begin) / period)}" '
                      f'begin="{begin:.2f}s" path="{d}"/>{c.planet(12 + 22 * math.sqrt(lines / top), _color(lang), i == 0, (i * .29) % 1)}</g>')
    return (f'<g transform="translate({_n(cx)} {_n(cy)}) rotate(-8)">{"".join(rings)}'
            f'<circle r="34" fill="url(#{sun})"/>{"".join(bodies)}</g>')


def _sunrise(c: _Film, colors, t0: float, t1: float) -> str:
    """日出：参考片的结尾，那段很少见到的时光"""
    sky_c, hor_c, sun_c = colors
    skyg = c.lin([(0, '#020306', 1), (.55, sky_c, 1), (.86, hor_c, 1), (1, _mix(hor_c, sun_c, .5), 1)], x2=0, y2=1)
    bloom = c.rad([(0, sun_c, .55), (.3, sun_c, .18), (1, hor_c, 0)])
    sun = c.rad([(0, '#fffaf0', 1), (.6, sun_c, 1), (1, _mix(sun_c, hor_c, .4), 1)])
    sea = c.lin([(0, _mix(hor_c, '#000000', .55), 1), (1, '#020306', 1)], x2=0, y2=1)
    streak = c.lin([(0, sun_c, 0), (.5, '#fff6e6', .7), (1, sun_c, 0)])
    rr = random.Random(5)
    glints = []
    for _ in range(26):
        gy = 258 + rr.random() ** 1.6 * 88
        gx = 415 + rr.gauss(0, (20 + (gy - 258) * 1.6) * .45)
        gw = rr.uniform(4, 16) * (1 + (gy - 258) / 60)
        glints.append(f'<rect x="{_n(gx - gw / 2)}" y="{_n(gy)}" width="{_n(gw)}" height="1.2" fill="{sun_c}" '
                      f'opacity="{rr.uniform(.35, .9):.2f}"/>')
    rise = c.kf("from{transform:translateY(70px)}to{transform:translateY(0)}")
    return (f'<rect width="{W}" height="258" fill="url(#{skyg})"/>'
            f'<g style="animation:{rise} {t1 - t0:.2f}s cubic-bezier(.3,0,.3,1) {t0:.2f}s both">'
            f'<circle cx="415" cy="258" r="250" fill="url(#{bloom})"/><circle cx="415" cy="258" r="46" fill="url(#{sun})"/></g>'
            f'<rect y="258" width="{W}" height="89" fill="url(#{sea})"/>{"".join(glints)}'
            f'<rect x="45" y="257.4" width="740" height="1.4" fill="url(#{streak})"/>')


# ---------- 成片 ----------

def render_film(weekly: dict, weekly_days: int, yearly: dict, yearly_days: int, matrix: list, profile_days: int) -> str:
    """一支约 30 秒的短片 + 定格海报。matrix: 7x24，[weekday][hour]，Monday=0"""
    wrows, wtotal = _rows(weekly)
    yrows, ytotal = _rows(yearly)
    n_langs = sum(1 for v in yearly.values() if v['added'] + v['deleted'])
    hours = [sum(matrix[d][h] for d in range(7)) for h in range(24)]
    days = [sum(matrix[d]) for d in range(7)]
    total = sum(hours)
    cats = {'Night': sum(hours[0:6]), 'Morning': sum(hours[6:12]), 'Daytime': sum(hours[12:18]), 'Evening': sum(hours[18:24])}
    ranked = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    top = ranked[0][0] if total and (ranked[0][1] - ranked[1][1]) / total >= .05 else (
        'Night' if cats['Evening'] + cats['Night'] >= cats['Morning'] + cats['Daytime'] else 'Morning')
    rare = min(cats, key=lambda k: cats[k])
    rare_zh, title_en, ask_en, colors = RARE[rare]
    best_s = max(range(24), key=lambda s: sum(hours[(s + k) % 24] for k in range(3)))
    peak = {(best_s + k) % 24 for k in range(3)}
    peak_label = f"{best_s:02d}:00–{(best_s + 3) % 24:02d}:00"
    peak_h = max(range(24), key=lambda h: hours[h])
    busiest = max(range(7), key=lambda d: days[d])
    dark = cats['Evening'] + cats['Night']
    wspan_zh = ZH_SPANS.get(weekly_days, f' {weekly_days} 天')
    pspan_zh = ZH_SPANS.get(profile_days, f' {profile_days} 天')
    yspan_zh = ZH_SPANS.get(yearly_days, f' {yearly_days} 天')
    title = TITLE.format(p=rare_zh)
    label = (f"I RARELY SEE {title_en.upper()} — I'm {PROFILE[top]}: {total:,} commits in {profile_days} days, most awake "
             f"{peak_label}, busiest on {WEEKDAYS_EN[busiest]}. This week: "
             + (', '.join(f"{l} {v / wtotal * 100:.1f}%" for l, v in wrows) or 'nothing') + ". This year: "
             + (', '.join(f"{l} {v / ytotal * 100:.1f}%" for l, v in yrows) or 'nothing') + '.')
    c = _Film('F', 11, label)
    sky = c.image('sky.webp', W, H)
    sky_band = f'<use href="#{sky}" y="{-BAND_Y}"/>'
    shots, subs = [], []

    # 1 · 0–4.8s 黑场里的光标：「你见过早晨吗？」「很少。」
    shots.append(c.window(0, 4.8, c.typed(ZH_TEXT['ask'].format(p=rare_zh), 128, .9, 4.8, cps=5.5, hide_at=2.9)
                          + c.typed(ZH_TEXT['answer'], 200, 3.1, 4.8, cps=3.6, lead=.2)
                          + f'<text style="animation:§in .8s ease-out 2.3s both" x="{W / 2}" y="158" font-family="{EN}" font-size="15" '
                          f'text-anchor="middle" fill="{SILVER}">Have you ever seen {ask_en}?</text>'
                          f'<text style="animation:§in .6s ease-out 3.9s both" x="{W / 2}" y="228" font-family="{EN}" font-size="15" '
                          f'text-anchor="middle" fill="{SILVER}">Rarely.</text>', fade=.5))

    # 2 · 4.6–9.4s 星轨：一年里每个小时的提交，像一张长曝光
    shots.append(c.window(4.6, 9.4, c.camera(_star_trails(c, hours, peak, W / 2, 150, 4.8), W / 2, 150, 1.0, 1.1, 4.6, 4.8)))
    if total:
        zh2 = ZH_TEXT['commits_dark' if dark >= total - dark else 'commits_light'].format(span=pspan_zh, n=f'{total:,}')
        en2 = (f"{total:,} commits in {profile_days} days — most of them "
               + (f"after dark ({dark / total * 100:.0f}%)." if dark >= total - dark else f"in daylight ({100 - dark / total * 100:.0f}%)."))
    else:
        zh2, en2 = ZH_TEXT['quiet'], "Quiet."
    subs.append(c.subtitle(zh2, en2, 5.0, 9.3))

    # 3 · 9.2–13.6s 飞越文字之海：各国语言的「语言」
    shots.append(c.window(9.2, 13.6, c.camera(f'<g opacity=".4">{sky_band}</g>' + c.word_sea(LANG_WORDS, 9.2, 13.6),
                                              W / 2, 170, 1.0, 1.06, 9.2, 4.4)))
    if wtotal:
        zh3 = ZH_TEXT['lines'].format(span=wspan_zh, n=f'{wtotal:,}')
        en3 = f"In {EN_SPANS.get(weekly_days, f'{weekly_days} days')}, I changed {wtotal:,} lines of code."
    else:
        zh3, en3 = ZH_TEXT['lines_none'].format(span=wspan_zh), f"In {EN_SPANS.get(weekly_days, f'{weekly_days} days')}, I didn't write a line."
    subs.append(c.subtitle(zh3, en3, 9.6, 13.5))

    # 4 · 13.4–15.0s 冲向地平线上的光：光速穿梭，白场出
    flash = c.kf("0%{visibility:visible;opacity:0}45%{opacity:.85}100%{visibility:visible;opacity:0}")
    shots.append(c.window(13.4, 15.0, c.camera(c.warp(W / 2, BAND_H / 2, 13.4, 15.0), W / 2, BAND_H / 2, 1.0, 1.25, 13.4, 1.6), fade=.3)
                 + f'<rect width="{W}" height="{BAND_H}" fill="#fff" visibility="hidden" opacity="0" style="animation:{flash} 1s ease-in-out 14.4s"/>')

    # 5 · 14.8–19.6s 本周的行星迎面掠过，第一名停下
    shots.append(c.window(14.8, 19.6, c.camera(f'<g opacity=".45">{sky_band}</g>', W / 2, BAND_H / 2, 1.3, 1.5, 14.8, 4.8)
                          + c.stars(50, (0, 0, W, BAND_H), .6) + _flyby(c, wrows, wtotal, 14.9, 19.6)))
    if wrows:
        major = wrows[0][1] / wtotal >= .5
        zh5 = ZH_TEXT['week_major' if major else 'week_minor'].format(lang=wrows[0][0])
        en5 = f"Most of it, in {wrows[0][0]}." if major else f"Mostly {wrows[0][0]}."
    else:
        zh5, en5 = ZH_TEXT['quiet'], "Quiet."
    subs.append(c.subtitle(zh5, en5, 16.4, 19.5))

    # 6 · 19.4–24.0s 本年的行星系
    shots.append(c.window(19.4, 24.0, c.stars(60, (0, 0, W, BAND_H), .6) + _orbits(c, yrows, ytotal, W / 2, 150, 19.4, 24.0)))
    if yrows:
        zh6 = ZH_TEXT['year'].format(span=yspan_zh, lang=yrows[0][0])
        en6 = (f"This year, I spoke {yrows[0][0]} the most." if yearly_days == 365
               else f"In {yearly_days} days, I spoke {yrows[0][0]} the most.")
    else:
        zh6, en6 = ZH_TEXT['quiet'], "Quiet."
    subs.append(c.subtitle(zh6, en6, 19.8, 23.9))

    # 7 · 23.8–28.0s 日出
    shots.append(c.window(23.8, 28.0, c.camera(_sunrise(c, colors, 23.8, 28.0), W / 2, 258, 1.08, 1.0, 23.8, 4.2), fade=.8))
    common_zh, common_en = COMMON[top if top != rare else ranked[0][0]]
    subs.append(c.subtitle(ZH_TEXT['rare'].format(p=rare_zh), f"I rarely see {ask_en}.", 24.1, 25.9))
    subs.append(c.subtitle(ZH_TEXT['glow'].format(c=common_zh), f"But every {common_en}, there is a light.", 26.0, 27.9)
                if total else c.subtitle(ZH_TEXT['quiet'], "Quiet.", 26.0, 27.9))

    # 8 · 27.8–30.6s 片名卡：同心文字环；书法片名随后滑到海报左上角
    shots.append(c.window(27.8, 30.6, c.stars(60, (0, 0, W, BAND_H), .6) + c.text_rings(NIGHT_WORDS, W / 2, 168, (86, 112, 140, 170, 202))
                          + f'<text style="animation:§in .8s ease-out 28.6s both,§out .4s ease-in 29.5s forwards" x="{W / 2}" y="210" '
                          f'font-family="{EN}" font-size="11.5" '
                          f'text-anchor="middle" letter-spacing="6" fill="{SILVER}">I RARELY SEE {title_en.upper()}</text>', fade=.5))
    n = len(title)
    tx, ty = (W / 2 - n * 46 / 2) - 40, (BAND_Y + 174) - 70
    glide = c.kf(f"0%{{opacity:0;transform:translate({_n(tx)}px,{_n(ty)}px) scale(1.4375)}}"
                 f"20%{{opacity:1;transform:translate({_n(tx)}px,{_n(ty)}px) scale(1.4375);animation-timing-function:cubic-bezier(.6,0,.2,1)}}"
                 f"55%{{transform:translate({_n(tx)}px,{_n(ty)}px) scale(1.4375);animation-timing-function:cubic-bezier(.6,0,.2,1)}}"
                 f"100%{{opacity:1;transform:none}}")
    title_el = (f'<g transform="translate(40 70)"><g style="animation:{glide} 3s linear 28s both">'
                f'<text font-family="{BRUSH}" font-size="32" fill="{GOLD_CORE}">{title}</text></g></g>')

    # 海报帧（静止）：银河、群山、月相、两排行星
    base = 430
    mx = max(hours) or 1
    sw = W / 24
    ridge = _range([((h + .5) * sw, 14 + 86 * (n / mx) ** .85, sw * 2.4) for h, n in enumerate(hours)],
                   base, 10, 17, curve=1.08)
    rb = random.Random(23)
    far = _range([(x, rb.uniform(40, 88), rb.uniform(50, 110)) for x in range(-20, W + 60, 55)], base - 8, 32, 31, rough=.6)
    mid = _range([(x, rb.uniform(24, 58), rb.uniform(40, 80)) for x in range(-10, W + 40, 38)], base, 20, 37, rough=.8)
    haze = c.lin([(0, '#3a4660', 0), (1, '#3a4660', .5)], x2=0, y2=1)
    rimg = c.lin([(0, '#c9d6ea', .3), (.45, '#ffd9a0', .5), (1, '#c9d6ea', .25)])
    dawn = c.rad([(0, colors[1], .55), (1, colors[1], 0)])
    rare_x = {'Night': 3, 'Morning': 9, 'Daytime': 15, 'Evening': 21}[rare] * sw
    px = (peak_h + .5) * sw
    py = min(y for x, y in ridge if abs(x - px) < 2)
    moons = []
    dmx = max(days) or 1
    for d in range(7):
        r = 5.5 + 5 * days[d] / dmx
        strong = d == busiest and total
        moons.append(f'<g transform="translate({548 + d * 40} {_n(92 - 34 * math.sin(math.pi * d / 6))})">'
                     f'{c.moon(r, .25 + .75 * days[d] / dmx)}'
                     f'<text y="{_n(r + 14)}" font-family="{EN}" font-size="7.5" text-anchor="middle" letter-spacing="1.5" '
                     f'fill="{INK if strong else MUTED}">{WEEKDAYS[d].upper()}</text>'
                     f'<text y="{_n(r + 26)}" font-family="{EN}" font-size="10" text-anchor="middle" '
                     f'fill="{GOLD if strong else SILVER}">{days[d] / total * 100 if total else 0:.0f}%</text></g>')
    periods = ''.join(f'<text x="{_n((h0 + 3) * sw)}" y="458" text-anchor="middle"><tspan font-family="{EN}" font-size="8.5" '
                      f'letter-spacing="2.5" fill="{GOLD if name == rare else MUTED}">{name.upper()}</tspan>'
                      f'<tspan font-family="{EN}" font-size="11.5" fill="{INK}" dx="7">'
                      f'{cats[name] / total * 100 if total else 0:.1f}%</tspan></text>' for name, h0 in PERIODS)
    ticks = ''.join(f'<text x="{_n(h * sw)}" y="442" font-family="{EN}" font-size="8.5" text-anchor="middle" fill="{MUTED}">'
                    f'{h:02d}</text>' for h in (6, 12, 18))
    divider = c.lin([(0, '#c9d2e0', 0), (.5, '#c9d2e0', .25), (1, '#c9d2e0', 0)], x2=0, y2=1)
    section = (f'font-family="{EN}" font-size="9" text-anchor="middle" letter-spacing="3" fill="{MUTED}"')
    poster = (f'<use href="#{sky}"/>' + c.stars(36, (0, 0, W, 300), .7)
              + f'<ellipse cx="{_n(rare_x)}" cy="{base - 34}" rx="210" ry="80" fill="url(#{dawn})" opacity=".5"/>'
              f'<path d="{_poly(far)}L{W + 6} {H}L-6 {H}Z" fill="#0d1320"/>'
              f'<rect y="300" width="{W}" height="140" fill="url(#{haze})" opacity=".28"/>'
              f'<path d="{_poly(mid)}L{W + 6} {H}L-6 {H}Z" fill="#070a11"/>'
              f'<path d="{_poly(ridge)}L{W + 6} {H}L-6 {H}Z" fill="#020305"/>'
              f'<path d="{_poly(ridge)}" fill="none" stroke="url(#{rimg})" stroke-width=".8"/>'
              + c.light(px, py - 9, h=12, flare=.5) + ''.join(moons) + periods + ticks
              + f'<text x="41" y="94" font-family="{EN}" font-size="10" letter-spacing="4.2" fill="{SILVER}">I RARELY SEE {title_en.upper()}</text>'
              f'<text x="40" y="122" font-family="{EN}" font-size="15" fill="{INK}">I&#x27;m {PROFILE[top]}.</text>'
              f'<text x="40" y="142" font-family="{EN}" font-size="12.5" fill="{SILVER}">{total:,} commits in {profile_days} days · '
              f'most awake {peak_label} · busiest on {WEEKDAYS_EN[busiest]}</text>'
              f'<rect x="414.5" y="176" width="1" height="120" fill="url(#{divider})"/>'
              f'<text x="207.5" y="186" {section}>THIS WEEK · {wtotal:,} LINES</text>'
              f'<text x="622.5" y="186" {section}>THIS YEAR · {n_langs} LANGUAGE{"" if n_langs == 1 else "S"} · {ytotal:,} LINES</text>'
              + _lineup(c, wrows, wtotal, 207.5, 228, 72, 46) + _lineup(c, yrows, ytotal, 622.5, 228, 72, 46))
    final = f'<g style="animation:§in 1.4s ease-out 29.8s both">{poster}</g>'

    band = c.nid('c')
    c.defs.append(f'<clipPath id="{band}"><rect width="{W}" height="{BAND_H}"/></clipPath>')
    montage = f'<g transform="translate(0 {BAND_Y})" clip-path="url(#{band})">{"".join(shots)}</g>'
    return c.svg(montage + final + title_el + ''.join(subs))
