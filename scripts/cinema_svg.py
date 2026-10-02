#!/usr/bin/env python3
"""把语言统计 / 作息画像渲染成两支约一分钟的「电影短片」式动画 SVG（运行时无第三方依赖）

风格参考短片《我从未见过太阳》：纯黑与冷银灰，唯一的暖金色光（光标）；宽字距衬线体，中英双语字幕；
镜头之间交叉淡化，配合推拉、横移、俯仰、飞越等运镜。
- render_languages_film 《七日，一年》：本周 / 本年的语言
- render_activity_film  《我很少见到早晨》：作息画像

开场蒙太奇约一分钟，随后定格为海报帧并保留缓慢的环境动画（星光、行星自转、流星、胶片颗粒）。
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

# 字体：内嵌子集优先，缺字时按顺序回退到下一个字体
EN = "CG,'Cormorant Garamond','EB Garamond',Garamond,'Times New Roman',serif"
EN6 = EN
ZH = "NS,CG,'Noto Serif SC','Source Han Serif SC','Songti SC',STSong,SimSun,serif"
BRUSH = "ZM,'Zhi Mang Xing',STXingkai,'Xingkai SC',KaiTi,cursive"
SEA = "CG,NS,KR,GR,'Noto Serif','Noto Serif CJK SC',serif"   # 多语种单词：拉丁 / 西里尔、汉字、韩文、希腊文各走各的子集
FONT_FILES = {'CG': 'cg500.woff2', 'ZM': 'zmx400.woff2', 'KR': 'kr500.woff2', 'GR': 'gr500.woff2'}
NS_FILES = {'L': 'nss-a.woff2', 'A': 'nss-b.woff2'}   # 字幕字体按片子分别子集，每支只带自己用到的汉字

INK, SILVER, MUTED = '#eef1f6', '#b9c1ce', '#7f8898'
GOLD, GOLD_CORE = '#ffc978', '#fff3dc'
SKY_FIT = f'transform="translate({W / 2} {H / 2}) scale(1.04) translate({-W / 2} {-H / 2})"'

PERIODS = (('Night', 0), ('Morning', 6), ('Daytime', 12), ('Evening', 18))   # (时段, 起始小时)
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
WEEKDAYS_ZH = '一二三四五六日'
WEEKDAYS_EN = ['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
# 最少的时段 →（中文，英文片名，英文问句，英文平叙，日出镜头的天色：天空 / 地平线 / 太阳）
RARE = {
    'Morning': ('早晨', 'the Morning', 'the morning', 'morning', ('#2b1d2c', '#c98172', '#ffe1a8')),
    'Daytime': ('白天', 'the Daylight', 'daylight', 'daylight', ('#1c2a3c', '#9fb8cf', '#fff8ea')),
    'Evening': ('黄昏', 'the Dusk', 'the dusk', 'dusk', ('#2a1830', '#d27a4e', '#ffc98a')),
    'Night': ('深夜', 'Midnight', 'midnight', 'midnight', ('#05070f', '#24304f', '#dfe6f2')),
}
PROFILE = {'Morning': "an early bird", 'Daytime': "a daytime coder", 'Evening': "an evening coder", 'Night': "a night owl"}
COMMON = {'Night': ('深夜', 'night'), 'Evening': ('傍晚', 'evening'), 'Morning': ('清晨', 'morning'), 'Daytime': ('白天', 'day')}
WHEN_ZH = ['凌晨'] * 6 + ['上午'] * 6 + ['中午'] + ['下午'] * 5 + ['晚上'] * 6

# 致敬原片里由各国语言的「海」组成的海面：这里换成各国语言的「语言」和「夜」
LANG_WORDS = ('language', '语言', 'langue', 'Sprache', 'lengua', 'язык', '言語', '언어', 'lingua', 'língua', 'taal', 'språk',
              'dil', 'bahasa', 'kieli', 'język', 'lugha', 'ngôn ngữ', 'γλώσσα', 'jazyk', 'nyelv', 'lingvo', 'iaith', 'teanga',
              'tungumál', 'мова', 'sprog', 'jezik', 'kalba', 'valoda', 'keel', 'limbă', 'wika', 'reo', 'ʻōlelo')
NIGHT_WORDS = ('night', '夜晚', 'nuit', 'Nacht', 'noche', 'ночь', '夜', '밤', 'notte', 'noite', 'nacht', 'natt', 'gece', 'malam',
               'yö', 'noc', 'usiku', 'đêm', 'νύχτα', 'éjszaka', 'nox', 'nokto', 'nos', 'oíche', 'nótt', 'ніч', 'naktis', 'nakts',
               'öö', 'noapte', 'gabi', 'pō', 'nat')

# 片名（书法字体）和中文字幕模板。make_assets.py 按这里出现的字做字体子集，改文案后要重新生成字体
TITLE_A = '七日<tspan dx="-.32em">，</tspan><tspan dx="-.3em">一年</tspan>'
TITLE_B = '我很少见到{p}'
ZH_A = {
    'ask': '你用什么语言，和世界说话？',
    'humans': '人类有七千多种语言。',
    'others': '而我，用另外几种。',
    'lines': '这{span}，我改动了 {n} 行代码。',
    'lines_none': '这{span}，我一行代码也没写。',
    'week_major': '大多是 {lang}。',
    'week_minor': '{lang} 写得最多。',
    'year': '这{span}，我说得最多的是 {lang}。',
    'total': '一共 {k} 种语言，{n} 行。',
    'quiet': '很安静。',
}
ZH_B = {
    'ask': '你见过{p}吗？',
    'answer': '很少。',
    'commits': '过去{span}，我提交了 {n} 次。',
    'dark': '大多在天黑以后。',
    'light': '大多在天亮以后。',
    'awake': '{when} {h} 点，是我最清醒的时候。',
    'busiest': '星期{d}最忙。',
    'hours': '这些山，是我一天里的二十四个小时。',
    'know': '我知道{p}是什么，却很少见过它的样子。',
    'rare': '我很少见到{p}。',
    'glow': '但每个{c}，都有一束光。',
    'quiet': '很安静。',
}
ZH_SPANS = {7: '七天', 365: '一年'}
EN_SPANS = {7: 'seven days', 365: 'a year'}


def _cjk(text: str) -> set:
    return {ch for ch in text if ord(ch) > 0x2e80}


def zh_chars(film: str) -> str:
    """某支片字幕字体子集需要的汉字和中文标点：'L' 语言片，'A' 作息片"""
    if film == 'L':
        text = ''.join(ZH_A.values()) + ''.join(w for w in LANG_WORDS)
    else:
        text = (''.join(ZH_B.values()) + ''.join(NIGHT_WORDS) + WEEKDAYS_ZH + ''.join(WHEN_ZH)
                + ''.join(v[0] for v in RARE.values()) + ''.join(v[0] for v in COMMON.values()))
    text += ''.join(ZH_SPANS.values()) + '天'
    return ''.join(sorted(ch for ch in _cjk(text) if not 0xac00 <= ord(ch) <= 0xd7af))


def brush_chars() -> str:
    return ''.join(sorted(_cjk('七日，一年' + TITLE_B + ''.join(v[0] for v in RARE.values()))))


def word_chars(script: str) -> str:
    """多语种单词里各文字系统用到的字符：latin（含西里尔）/ hangul / greek"""
    chars = set(''.join(LANG_WORDS + NIGHT_WORDS))
    pick = {'hangul': lambda o: 0xac00 <= o <= 0xd7af, 'greek': lambda o: 0x370 <= o <= 0x3ff,
            'latin': lambda o: 0x7f < o < 0x2e80 and not 0x370 <= o <= 0x3ff}[script]
    return ''.join(sorted(ch for ch in chars if pick(ord(ch))))


BASE_CSS = (
    "@keyframes §in{from{opacity:0}}"
    "@keyframes §rise{from{opacity:0;transform:translateY(8px)}}"
    "@keyframes §tw{50%{opacity:.2}}"
    "@keyframes §roll{to{transform:translateX(-420px)}}"
    "@keyframes §spin{to{transform:rotate(360deg)}}"
    "@keyframes §rspin{to{transform:rotate(-360deg)}}"
    "@keyframes §breathe{50%{opacity:.55}}"
    "@keyframes §blink{50%{opacity:.12}}"
    "@keyframes §gone{to{opacity:0}}"
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

    # ---------- 时间轴与运镜 ----------

    def window(self, t0: float, t1: float, body: str, fade: float = .8) -> str:
        """只在 [t0, t1] 出现的镜头 / 字幕；窗口外 opacity 为 0，所以静态时不可见"""
        d = t1 - t0
        f = min(fade / d * 100, 45)
        k = self.kf(f"0%{{opacity:0}}{f:.2f}%{{opacity:1}}{100 - f:.2f}%{{opacity:1}}100%{{opacity:0}}")
        return f'<g opacity="0" style="animation:{k} {d:.2f}s linear {t0:.2f}s">{body}</g>'

    def camera(self, body: str, cx: float, cy: float, s0: float, s1: float, t0: float, dur: float,
               dx: float = 0, dy: float = 0, r0: float = 0, r1: float = 0, ease: str = 'ease-in-out') -> str:
        """运镜：以 (cx, cy) 为中心推拉（s0→s1）、平移（dx, dy）、侧倾（r0→r1 度）"""
        k = self.kf(f"from{{transform:rotate({r0}deg) scale({s0})}}"
                    f"to{{transform:translate({dx}px,{dy}px) rotate({r1}deg) scale({s1})}}")
        return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g style="animation:{k} {dur:.2f}s {ease} {t0:.2f}s both">'
                f'<g transform="translate({_n(-cx)} {_n(-cy)})">{body}</g></g></g>')

    def subtitle(self, zh: str, en: str, t0: float, t1: float, y: float = 296) -> str:
        body = (f'<text class="§sub" x="{_n(W / 2)}" y="{_n(y)}" font-family="{ZH}" font-size="15" text-anchor="middle" '
                f'fill="{INK}" letter-spacing="1.5">{escape(zh)}</text>'
                f'<text class="§sub" x="{_n(W / 2)}" y="{_n(y + 21)}" font-family="{EN}" font-size="15" text-anchor="middle" '
                f'fill="{SILVER}" letter-spacing=".4">{escape(en)}</text>')
        return self.window(t0, t1, body, fade=.6)

    def flash(self, t: float, dur: float = 1.4, color: str = '#ffffff', peak: float = .85) -> str:
        """白场闪切（光速镜头的出口）"""
        k = self.kf(f"0%{{opacity:0}}45%{{opacity:{peak}}}100%{{opacity:0}}")
        return f'<rect width="{W}" height="{H}" fill="{color}" opacity="0" style="animation:{k} {dur}s ease-in-out {t:.2f}s"/>'

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

    def typed(self, text: str, y: float, t0: float, cps: float = 6.5, size: float = 19, hide_at: float = None,
              lead: float = 1.0) -> str:
        """逐字打出一行中文（汉字和全角标点都是 1em 宽，所以能精确算出光标位置），光标打完后原地闪烁"""
        ls = 2
        adv, n = size + ls, len(text)
        left = W / 2 - (n * adv - ls) / 2
        dur = (n + 1) / cps
        kts = ';'.join(f"{k / (n + 1):.4f}" for k in range(n + 1))
        clip = self.nid('c')
        self.defs.append(f'<clipPath id="{clip}"><rect x="{_n(left - 2)}" y="{_n(y - size * 1.1)}" width="0" height="{_n(size * 1.6)}">'
                         f'<animate attributeName="width" calcMode="discrete" values="{";".join(_n(k * adv + 2) for k in range(n + 1))}" '
                         f'keyTimes="{kts}" begin="{t0:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        moves = ';'.join(f"{_n(k * adv)} 0" for k in range(n + 1))
        gone = f' style="animation:§gone .4s ease-out {hide_at:.2f}s both"' if hide_at else ''
        return (f'<text x="{_n(left)}" y="{_n(y)}" font-family="{ZH}" font-size="{size}" letter-spacing="{ls}" fill="{INK}" '
                f'clip-path="url(#{clip})">{escape(text)}</text>'
                f'<g style="animation:§in .3s ease-out {t0 - lead:.2f}s both">'
                f'<g{gone}><animateTransform attributeName="transform" type="translate" calcMode="discrete" values="{moves}" '
                f'keyTimes="{kts}" begin="{t0:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                f'<g style="animation:§blink 1.05s steps(1) infinite">{self.light(left + 5, y - size * .36, h=size * 1.2, flare=.5)}</g></g></g>')

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

    # ---------- 大场面 ----------

    def word_sea(self, words, t0: float, hy: float = 170, rows: int = 14, period: float = 11.0) -> str:
        """文字组成的海：每行放在「单位深度」，绕地平线上的消失点放大即透视飞越；各行错开起跑，源源不断涌来"""
        r = self.rng
        k = self.kf("0%{transform:scale(.14);opacity:0}16%{opacity:.75}80%{opacity:.9}100%{transform:scale(4.4);opacity:0}")
        sep = '  '
        glow = self.lin([(0, '#8fa3c7', 0), (.5, '#8fa3c7', .22), (1, '#8fa3c7', 0)], x2=0, y2=1)
        path = self.lin([(0, GOLD, .55), (1, GOLD, 0)], x2=0, y2=1)
        out = [f'<rect y="{_n(hy - 30)}" width="{W}" height="60" fill="url(#{glow})"/>']
        for i in range(rows):
            seq = list(words)
            r.shuffle(seq)
            text = escape(sep.join(seq * 2))
            out.append(f'<g transform="translate({_n(W / 2)} {_n(hy)})"><g style="animation:{k} {period}s cubic-bezier(.6,0,.96,.52) '
                       f'{t0 - period + i * period / rows:.2f}s infinite"><text x="{r.uniform(-1500, -1350):.0f}" y="40" '
                       f'font-family="{SEA}" font-size="9" fill="#b3bfd2">{text}</text></g></g>')
        # 远处地平线上的那束光，和它在海面上的倒影
        out.append(f'<rect x="{_n(W / 2 - 1.5)}" y="{_n(hy)}" width="3" height="{_n(H - hy)}" fill="url(#{path})" '
                   f'class="§tw" style="animation-duration:2.6s"/>' + self.light(W / 2, hy - 9, h=13, flare=1.3))
        return ''.join(out)

    def warp(self, cx: float, cy: float, t0: float, n: int = 130) -> str:
        """光速穿梭：从中心向外辐射的光痕，加速掠过；配合轻微的机身抖动"""
        r = self.rng
        k = self.kf("from{stroke-dashoffset:.3}to{stroke-dashoffset:-1}")
        shake = self.kf("0%,100%{transform:translate(0,0)}25%{transform:translate(1.2px,-.8px)}"
                        "50%{transform:translate(-1px,1px)}75%{transform:translate(.8px,1.2px)}")
        core = self.rad([(0, '#ffffff', .9), (.2, '#ffe9c4', .45), (1, '#ffd9a0', 0)])
        lines = []
        for _ in range(n):
            a = r.uniform(0, 2 * math.pi)
            r0 = r.uniform(14, 70)
            x0, y0 = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
            x1, y1 = cx + 640 * math.cos(a), cy + 640 * math.sin(a)
            dur = r.uniform(.5, 1.4)
            col = GOLD if r.random() < .18 else '#e3ebfb'
            lines.append(f'<path d="M{_n(x0)} {_n(y0)}L{_n(x1)} {_n(y1)}" pathLength="1" stroke-dasharray="{r.uniform(.07, .24):.2f} 3" '
                         f'stroke-dashoffset=".3" stroke="{col}" stroke-opacity="{r.uniform(.35, .95):.2f}" stroke-width="{r.uniform(.5, 1.7):.1f}" '
                         f'style="animation:{k} {dur:.2f}s cubic-bezier(.65,0,1,.6) {t0 + r.uniform(0, 1.6):.2f}s infinite"/>')
        return (f'<g style="animation:{shake} .14s steps(1) infinite"><circle cx="{_n(cx)}" cy="{_n(cy)}" r="90" fill="url(#{core})"/>'
                + ''.join(lines) + '</g>')

    def text_rings(self, words, cx: float, cy: float, radii, size: float = 8.5) -> str:
        """片名卡的同心文字环（致敬原片片名卡），相邻两环反向缓慢旋转"""
        sep = ' · '
        out = []
        for i, rr in enumerate(radii):
            pid = self.nid('p')
            self.defs.append(f'<path id="{pid}" d="M{_n(rr)} 0A{_n(rr)} {_n(rr)} 0 1 1 {_n(-rr)} 0A{_n(rr)} {_n(rr)} 0 1 1 {_n(rr)} 0"/>')
            seq = list(words)
            self.rng.shuffle(seq)
            text = escape(sep.join(seq * 3))
            op = max(.12, .55 - i * .08)
            out.append(f'<g style="animation:{"§spin" if i % 2 else "§rspin"} {80 + i * 25}s linear infinite">'
                       f'<text font-family="{SEA}" font-size="{size}" fill="#c3ccdb" opacity="{op:.2f}" letter-spacing=".6">'
                       f'<textPath href="#{pid}">{text}</textPath></text></g>')
        return f'<g transform="translate({_n(cx)} {_n(cy)})">{"".join(out)}</g>'

    def title_card(self, title: str, sub: str, words, t0: float, cx: float = W / 2, cy: float = 168) -> str:
        """书法片名 + 宽字距英文 + 同心文字环"""
        glow = self.rad([(0, GOLD, .28), (1, GOLD, 0)])
        rings = self.text_rings(words, cx, cy, (78, 104, 132, 162, 194, 228, 264))
        return (rings + f'<g class="§fi" style="animation-delay:{t0 + .6:.2f}s;animation-duration:1.8s">'
                f'<ellipse cx="{_n(cx)}" cy="{_n(cy - 8)}" rx="170" ry="54" fill="url(#{glow})"/>'
                f'<text x="{_n(cx)}" y="{_n(cy + 6)}" font-family="{BRUSH}" font-size="46" text-anchor="middle" fill="{GOLD_CORE}">{title}</text></g>'
                f'<text class="§fi" style="animation-delay:{t0 + 1.6:.2f}s;animation-duration:1.8s" x="{_n(cx)}" y="{_n(cy + 38)}" '
                f'font-family="{EN6}" font-size="11.5" text-anchor="middle" letter-spacing="6" fill="{SILVER}">{sub}</text>')


    # ---------- 输出 ----------

    def svg(self, layers: str) -> str:
        files = dict(FONT_FILES, NS=NS_FILES[self.uid])
        font_css = ''.join(f"@font-face{{font-family:{k};src:url(data:font/woff2;base64,{_asset('fonts/' + f)}) format('woff2')}}"
                           for k, f in files.items())
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


def _color(lang: str) -> str:
    return LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)


def _lineup(c: _Film, rows, total, cx, cy, slot, dmax, name_size=12.5, seed=0):
    """一排行星：直径按占比开方缩放，第一名带金色边缘光"""
    if not rows:
        return (f'<text x="{_n(cx)}" y="{_n(cy)}" font-family="{EN}" font-size="14" text-anchor="middle" fill="{MUTED}">'
                f'silence, for now</text>')
    top, n = rows[0][1], len(rows)
    out = []
    for i, (lang, lines) in enumerate(rows):
        x = cx + (i - (n - 1) / 2) * slot
        d = 14 + (dmax - 14) * math.sqrt(lines / top)
        pct = lines / total * 100 if total else 0
        planet = c.planet(d, _color(lang), spin=40 + 23 * ((i + seed) % 4), phase=(i * .37 + seed * .21) % 1, gold=i == 0)
        lab = (f'<text class="§sub" x="0" y="{_n(dmax / 2 + name_size + 8)}" font-family="{EN}" font-size="{name_size}" '
               f'text-anchor="middle" fill="{INK}" letter-spacing=".3">{escape(lang)}</text>'
               f'<text class="§sub" x="0" y="{_n(dmax / 2 + name_size * 2 + 11)}" font-family="{EN6}" '
               f'font-size="{_n(name_size * 1.04)}" text-anchor="middle" fill="{GOLD if i == 0 else SILVER}">{pct:.1f}%</text>')
        out.append(f'<g transform="translate({_n(x)} {_n(cy)})">{planet}{lab}</g>')
    return ''.join(out)


def _flyby(c: _Film, rows, total, t0: float, vx: float = W / 2, vy: float = 158) -> str:
    """本周的行星从远处迎面飞来、从镜头两侧掠过（绕消失点放大 = 透视）；名次倒序出场，第一名最后飞向画面右侧"""
    if not rows:
        return ''
    k = c.kf("0%{transform:scale(.05);opacity:0}14%{opacity:1}100%{transform:scale(3.2);opacity:1}")
    lk = c.kf("0%,34%{opacity:0}48%,70%{opacity:1}84%,100%{opacity:0}")
    top = rows[0][1]
    out = []
    order = list(enumerate(rows))[::-1]
    for j, (i, (lang, lines)) in enumerate(order):
        side = 1 if j % 2 else -1
        dx, dy = side * (150 + 22 * (j % 3)), (-34 if j % 2 else 30)
        if i == 0:
            dx, dy = 128, 6
        d = 24 + 46 * math.sqrt(lines / top)
        t = t0 + j * 1.25
        pct = lines / total * 100 if total else 0
        lab = (f'<g style="animation:{lk} 3.6s linear {t:.2f}s both"><text class="§sub" y="{_n(d / 2 + 13)}" font-family="{EN}" '
               f'font-size="10" text-anchor="middle" fill="{INK}" letter-spacing=".4">{escape(lang)}'
               f'<tspan font-family="{EN6}" fill="{GOLD if i == 0 else SILVER}" dx="5">{pct:.1f}%</tspan></text></g>')
        out.append(f'<g transform="translate({_n(vx)} {_n(vy)})"><g style="animation:{k} 3.6s cubic-bezier(.55,0,1,.5) {t:.2f}s both">'
                   f'<g transform="translate({dx} {dy})">{c.planet(d, _color(lang), 30 + 9 * j, (j * .31) % 1, i == 0)}{lab}</g></g></g>')
    return ''.join(out)


def _orbits(c: _Film, rows, total, cx: float, cy: float, t0: float) -> str:
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
        label = escape(('   '.join([piece] * reps)))
        rings.append(f'<use href="#{pid}" fill="none" stroke="#c9d2e0" stroke-opacity="{.32 - i * .03:.2f}" stroke-width=".7"/>'
                     f'<text font-family="{EN}" font-size="9" fill="{GOLD if i == 0 else "#c3ccdb"}" opacity=".78" letter-spacing=".5">'
                     f'<textPath href="#{pid}">{label}</textPath></text>')
        period = 9 * (rx / 96) ** 1.5
        size = 12 + 22 * math.sqrt(lines / top)
        bodies.append(f'<g><animateMotion dur="{period:.1f}s" repeatCount="indefinite" begin="{t0 - period * (i * .37 % 1):.2f}s" '
                      f'path="{d}"/>{c.planet(size, _color(lang), 24, (i * .29) % 1, i == 0)}</g>')
    return (f'<g transform="translate({_n(cx)} {_n(cy)}) rotate(-8)">{"".join(rings)}'
            f'<circle r="34" fill="url(#{sun})"/>{"".join(bodies)}</g>')


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
    shots, subs = [], []

    # 1 · 0–7.6s 黑场里的光标，打出一句问话
    shots.append(c.window(0, 7.6, c.camera(c.typed(ZH_A['ask'], 150, 1.4, cps=6), W / 2, 150, 1.0, 1.1, 0, 7.6)
                          + f'<text class="§fi" style="animation-delay:4.4s;animation-duration:1.6s" x="{W / 2}" y="186" '
                          f'font-family="{EN}" font-size="15" text-anchor="middle" fill="{SILVER}" letter-spacing=".4">'
                          f'What language do you speak to the world in?</text>', fade=.9))

    # 2 · 7.2–15.6s 飞越文字之海：各国语言的「语言」
    shots.append(c.window(7.2, 15.6, c.camera(f'<use href="#{sky}" opacity=".35" {SKY_FIT}/>' + c.stars(36, (0, 0, W, 165))
                                              + c.word_sea(LANG_WORDS, 7.2), W / 2, 170, 1.0, 1.08, 7.2, 8.4, r0=-1.2, r1=.8)))
    subs.append(c.subtitle(ZH_A['humans'], "Humans speak more than seven thousand languages.", 8.6, 11.9, y=62))
    subs.append(c.subtitle(ZH_A['others'], "I speak in a few others.", 12.2, 15.2, y=62))

    # 3 · 15.2–20.6s 冲向地平线上的光：光速穿梭，白场出
    shots.append(c.window(15.2, 20.6, c.camera(c.warp(W / 2, H / 2, 15.2), W / 2, H / 2, 1.0, 1.25, 15.2, 5.4, ease='ease-in'), fade=.5))
    flashes = c.flash(19.6, 1.6)

    # 4 · 20.2–29.4s 本周的行星迎面掠过
    if wtotal:
        zh_lines = ZH_A['lines'].format(span=wspan_zh, n=f'{wtotal:,}')
        en_lines = f"In {wspan_en}, I changed {wtotal:,} lines of code."
    else:
        zh_lines, en_lines = ZH_A['lines_none'].format(span=wspan_zh), f"In {wspan_en}, I didn't write a line."
    shots.append(c.window(20.2, 29.4, c.camera(f'<use href="#{sky}" opacity=".5" {SKY_FIT}/>', W / 2, H / 2, 1.3, 1.6, 20.2, 9.2)
                          + c.stars(60) + _flyby(c, wrows, wtotal, 20.6)))
    subs.append(c.subtitle(zh_lines, en_lines, 21.6, 25.6))

    # 5 · 29.0–36.0s 第一名行星的特写，镜头缓推
    if wrows:
        lang, lines = wrows[0]
        major = lines / wtotal >= .5
        zh5 = ZH_A['week_major' if major else 'week_minor'].format(lang=lang)
        en5 = f"Most of it, in {lang}." if major else f"Mostly {lang}."
        big = (f'<g transform="translate(620 176)">{c.planet(250, _color(lang), 70, .2, True)}</g>'
               f'<text x="120" y="160" font-family="{EN6}" font-size="54" fill="{GOLD_CORE}">{lines / wtotal * 100:.1f}%</text>'
               f'<text x="122" y="184" font-family="{EN}" font-size="14" fill="{SILVER}" letter-spacing="1.2">'
               f'of every line I touched this week</text>')
    else:
        zh5, en5, big = ZH_A['quiet'], "Quiet.", ''
    shots.append(c.window(29.0, 36.0, c.camera(f'<use href="#{sky}" opacity=".45" {SKY_FIT}/>' + c.stars(40), W / 2, H / 2, 1.15, 1.25,
                                               29.0, 7.0, dx=-18) + c.camera(big, 620, 176, .96, 1.06, 29.0, 7.0, dx=-10)))
    subs.append(c.subtitle(zh5, en5, 30.2, 35.4))

    # 6 · 35.6–43.8s 本年的行星系
    if yrows:
        zh6 = ZH_A['year'].format(span=yspan_zh, lang=yrows[0][0])
        en6 = (f"This year, I spoke {yrows[0][0]} the most." if yearly_days == 365
               else f"In {yearly_days} days, I spoke {yrows[0][0]} the most.")
    else:
        zh6, en6 = ZH_A['quiet'], "Quiet."
    shots.append(c.window(35.6, 43.8, c.stars(70) + c.camera(_orbits(c, yrows, ytotal, W / 2, 150, 35.6), W / 2, 150, .9, 1.04,
                                                              35.6, 8.2, r0=-3, r1=1)))
    subs.append(c.subtitle(zh6, en6, 37.0, 43.2))

    # 7 · 43.4–50.8s 镜头下摇，银心从黑暗里升起
    tilt = c.kf("from{transform:translate(0,95px) scale(1.55)}to{transform:translate(0,-60px) scale(1.4)}")
    shots.append(c.window(43.4, 50.8, f'<g transform="translate({W / 2} {H / 2})"><g style="animation:{tilt} 7.4s ease-in-out 43.4s both">'
                          f'<g transform="translate({-W / 2} {-H / 2})"><use href="#{sky}"/>{c.stars(50)}</g></g></g>'))
    subs.append(c.subtitle(ZH_A['total'].format(k=n_langs, n=f'{ytotal:,}'),
                           f"{n_langs} language{'' if n_langs == 1 else 's'}, {ytotal:,} lines.", 44.8, 50.2))

    # 8 · 50.4–58.4s 片名卡：同心文字环
    shots.append(c.window(50.4, 58.4, c.stars(60) + c.camera(c.title_card(TITLE_A, 'SEVEN DAYS · ONE YEAR', LANG_WORDS, 50.4),
                                                              W / 2, 168, 1.2, 1.0, 50.4, 8.0)))

    # 海报帧：行星悬在银心之上
    divider = c.lin([(0, '#c9d2e0', 0), (.5, '#c9d2e0', .28), (1, '#c9d2e0', 0)], x2=0, y2=1)
    poster = (f'<g style="animation:§drift 70s ease-in-out 58s infinite alternate"><use href="#{sky}" {SKY_FIT} opacity=".8"/></g>'
              + c.stars(42)
              + c.meteors([(700, -10, 155, 66, 15), (300, -10, 150, 75, 19)])
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
    final = f'<g style="animation:§in 2.4s ease-out 57.6s both">{poster}</g>'
    return c.svg(''.join(shots) + final + flashes + ''.join(subs))


# ---------- 《我很少见到早晨》：作息 ----------

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


def _ridge(hours, base, lo, hi, x0=-6.0, x1=W + 6.0):
    """由 24 小时提交数堆成的山脊：每小时一座山，峰高按提交数（略作压缩，避免只剩一座孤峰）"""
    mx = max(hours) or 1
    sw = W / 24
    peaks = [((h + .5) * sw, lo + (hi - lo) * (n / mx) ** .85, sw * 2.4) for h, n in enumerate(hours)]
    return _range(peaks, base, lo * .7, 17, curve=1.08, x0=x0, x1=x1)


def _poly(pts) -> str:
    return 'M' + 'L'.join(f"{_n(x)} {_n(y)}" for x, y in pts)


def _star_trails(c: _Film, hours, peak, cx: float, cy: float, t0: float) -> str:
    """星轨延时：每小时占 15° 的扇区，扇区里的星轨条数按这一小时的提交数；从 0 点起逐小时曝光，高峰时段是金色"""
    r = c.rng
    mx = max(hours) or 1
    k = c.kf("from{stroke-dashoffset:1}")
    groups = []
    for h, n in enumerate(hours):
        a0 = h * 15 - 90
        arcs = []
        for _ in range(round(2 + 7 * n / mx)):
            rad = 26 + 440 * r.random() ** .85
            pad = r.uniform(.3, 2.5)
            arcs.append(f'<path d="{_arc(rad, a0 + pad, a0 + 15 - pad)}" pathLength="1" stroke-opacity="{r.uniform(.3, .9):.2f}" '
                        f'stroke-width="{r.uniform(.5, 1.4):.1f}"/>')
        # stroke-dashoffset 是继承属性，整组共用一个「逐小时曝光」的动画
        groups.append(f'<g stroke="{GOLD if h in peak else "#d6deeb"}" style="animation:{k} 1.2s ease-out {t0 + .4 + h * .24:.2f}s both">'
                      f'{"".join(arcs)}</g>')
    pole = c.rad([(0, '#ffffff', 1), (.25, '#dfe8ff', .5), (1, '#dfe8ff', 0)])
    return (f'<g transform="translate({_n(cx)} {_n(cy)})"><g fill="none" stroke-dasharray="1" '
            f'style="animation:§spin 260s linear infinite">{"".join(groups)}</g><circle r="7" fill="url(#{pole})"/></g>')


def _globe(c: _Film, cx: float, cy: float, R: float, t0: float, warm: str) -> str:
    """线框地球（致敬原片）：纬线固定，经线的 rx 按 |sin| 周期变化 = 自转；右侧一圈暖色晨昏线"""
    lines = []
    for lat in (-60, -30, 0, 30, 60):
        y = -R * math.sin(math.radians(lat)) * .96
        rx = R * math.cos(math.radians(lat))
        lines.append(f'<ellipse cy="{_n(y)}" rx="{_n(rx)}" ry="{_n(rx * .2)}"/>')
    T = 18
    for m in range(6):
        vals = ';'.join(_n(R * abs(math.sin(math.radians(m * 30) + 2 * math.pi * s / 12))) for s in range(13))
        lines.append(f'<ellipse rx="{_n(R * abs(math.sin(math.radians(m * 30))))}" ry="{_n(R)}">'
                     f'<animate attributeName="rx" values="{vals}" dur="{T}s" repeatCount="indefinite" begin="{t0:.2f}s"/></ellipse>')
    dawn = c.rad([(0, warm, 0), (.7, warm, 0), (.86, warm, .55), (1, warm, 0)], cx=.36, cy=.5, r=.62)
    rim = c.lin([(0, warm, 0), (.6, warm, .2), (1, '#fff1d6', .95)], x2=1, y2=0)
    body = c.rad([(0, '#0d1424', 1), (1, '#04060c', 1)])
    return (f'<g transform="translate({_n(cx)} {_n(cy)}) rotate(-18)"><circle r="{_n(R * 1.5)}" fill="url(#{dawn})"/>'
            f'<circle r="{_n(R)}" fill="url(#{body})"/>'
            f'<g fill="none" stroke="#c9d3e3" stroke-opacity=".38" stroke-width=".7">{"".join(lines)}</g>'
            f'<circle r="{_n(R)}" fill="none" stroke="url(#{rim})" stroke-width="2"/></g>')


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
    rare_zh, title_en, ask_en, plain_en, (sky_c, hor_c, sun_c) = RARE[rare]
    best_s = max(range(24), key=lambda s: sum(hours[(s + k) % 24] for k in range(3)))
    peak = {(best_s + k) % 24 for k in range(3)}
    peak_label = f"{best_s:02d}:00–{(best_s + 3) % 24:02d}:00"
    peak_h = max(range(24), key=lambda h: hours[h])
    busiest = max(range(7), key=lambda d: days[d])
    dark = cats['Evening'] + cats['Night']
    dark_pct = dark / total * 100 if total else 0
    span_zh = ZH_SPANS.get(profile_days, f' {profile_days} 天')
    label = (f"I RARELY SEE {title_en.upper()} — I'm {PROFILE[top]}: {total:,} commits in {profile_days} days, "
             f"most awake {peak_label}, busiest on {WEEKDAYS_EN[busiest]}")
    c = _Film('A', 11, label)
    sky = c.image('sky_b.webp', W, H)
    gal = c.image('galaxy.webp', 256, 256)
    shots, subs = [], []
    mx = max(days) or 1

    # 1 · 0–8.6s 黑场里的光标：「你见过早晨吗？」「很少。」
    shots.append(c.window(0, 8.6, c.camera(c.typed(ZH_B['ask'].format(p=rare_zh), 136, 1.2, cps=5.5, hide_at=4.6)
                                           + c.typed(ZH_B['answer'], 206, 5.4, cps=3.2, lead=.8), W / 2, 170, 1.0, 1.08, 0, 8.6)
                          + f'<text class="§fi" style="animation-delay:3.2s;animation-duration:1.4s" x="{W / 2}" y="166" '
                          f'font-family="{EN}" font-size="15" text-anchor="middle" fill="{SILVER}">Have you ever seen {ask_en}?</text>'
                          f'<text class="§fi" style="animation-delay:6.6s;animation-duration:1.2s" x="{W / 2}" y="236" '
                          f'font-family="{EN}" font-size="15" text-anchor="middle" fill="{SILVER}">Rarely.</text>', fade=.9))

    # 2 · 8.2–16.4s 星轨：一年里每个小时的提交，像一张长曝光
    en2 = (f"This past year, I committed {total:,} times." if profile_days == 365
           else f"In the past {profile_days} days, I committed {total:,} times.")
    shots.append(c.window(8.2, 16.4, c.camera(_star_trails(c, hours, peak, W / 2, 150, 8.2), W / 2, 150, 1.0, 1.12, 8.2, 8.2,
                                              r0=-2, r1=2)))
    subs.append(c.subtitle(ZH_B['commits'].format(span=span_zh, n=f'{total:,}'), en2, 9.6, 15.8))

    # 3 · 16.0–24.2s 飞越各国语言的「夜」
    if not total:
        zh3, en3 = ZH_B['quiet'], "Quiet."
    elif dark >= total - dark:
        zh3, en3 = ZH_B['dark'], f"Most of them after dark — {dark_pct:.0f}%."
    else:
        zh3, en3 = ZH_B['light'], f"Most of them in daylight — {100 - dark_pct:.0f}%."
    shots.append(c.window(16.0, 24.2, c.camera(f'<use href="#{sky}" opacity=".45" {SKY_FIT}/>' + c.word_sea(NIGHT_WORDS, 16.0),
                                               W / 2, 170, 1.0, 1.07, 16.0, 8.2, r0=1, r1=-.8)))
    subs.append(c.subtitle(zh3, en3, 17.4, 23.6, y=62))

    # 4 · 23.8–31.4s 倾斜旋转的星系：压扁的圆盘在自身平面内旋转，就是真实的 3D 投影
    core = c.rad([(0, '#ffe6b8', .5), (.4, '#c9a2ff', .12), (1, '#c9a2ff', 0)])
    galaxy = (f'<g transform="translate(415 150)"><ellipse rx="300" ry="120" fill="url(#{core})"/>'
              f'<g transform="rotate(-16) scale(1 .4)"><g style="animation:§spin 90s linear infinite">'
              f'<use href="#{gal}" transform="translate(-269 -269) scale(2.1)"/></g></g></g>')
    shots.append(c.window(23.8, 31.4, c.stars(60) + c.camera(galaxy, 415, 150, .85, 1.35, 23.8, 7.6, r0=-4, r1=3)))
    h12 = peak_h % 12 or 12
    subs.append(c.subtitle(ZH_B['awake'].format(when=WHEN_ZH[peak_h], h=h12 if peak_h else 0),
                           f"At {h12} {'a.m.' if peak_h < 12 else 'p.m.'}, I'm most awake.", 25.0, 30.8) if total
                else c.subtitle(ZH_B['quiet'], "Quiet.", 25.0, 30.8))

    # 5 · 31.0–38.6s 月亮依次升起，镜头向右横摇
    hz = c.lin([(0, '#0b1020', 0), (1, '#0b1020', 1)], x2=0, y2=1)
    rise = c.kf("from{opacity:0;transform:translateY(54px)}")
    moons = []
    for d in range(7):
        x = 150 + d * 118
        y = 156 - 54 * math.sin(math.pi * d / 6)
        r = 10 + 9 * days[d] / mx
        moons.append(f'<g transform="translate({_n(x)} {_n(y)})"><g style="animation:{rise} 2s cubic-bezier(.16,1,.3,1) '
                     f'{31.4 + d * .78:.2f}s both">{c.moon(r, .25 + .75 * days[d] / mx)}'
                     f'<text y="{_n(r + 21)}" font-family="{EN6}" font-size="10" text-anchor="middle" letter-spacing="2.5" '
                     f'fill="{INK if d == busiest and total else MUTED}">{WEEKDAYS[d].upper()}</text>'
                     f'<text y="{_n(r + 35)}" font-family="{EN6}" font-size="11" text-anchor="middle" '
                     f'fill="{GOLD if d == busiest and total else SILVER}">{days[d] / total * 100 if total else 0:.0f}%</text></g></g>')
    pan = c.kf("from{transform:translateX(30px)}to{transform:translateX(-300px)}")
    shots.append(c.window(31.0, 38.6, f'<use href="#{sky}" opacity=".55" {SKY_FIT}/>'
                          f'<g style="animation:{pan} 7.6s ease-in-out 31s both">{"".join(moons)}</g>'
                          f'<rect y="246" width="{W}" height="101" fill="url(#{hz})"/>'))
    subs.append(c.subtitle(ZH_B['busiest'].format(d=WEEKDAYS_ZH[busiest]), f"{WEEKDAYS_EN[busiest]} are the busiest.", 32.6, 38.0)
                if total else c.subtitle(ZH_B['quiet'], "Quiet.", 32.6, 38.0))

    # 山：海报帧和横移镜头共用
    base = 300
    ridge = _ridge(hours, base, 16, 104, x0=-60, x1=W + 60)
    rb = random.Random(23)
    far = _range([(x, rb.uniform(40, 92), rb.uniform(50, 110)) for x in range(-80, W + 120, 55)], base - 6, 34, 31,
                  rough=.6, x0=-80, x1=W + 80)
    mid = _range([(x, rb.uniform(26, 62), rb.uniform(40, 80)) for x in range(-80, W + 120, 38)], base, 22, 37,
                 rough=.8, x0=-80, x1=W + 80)
    haze = c.lin([(0, '#3a4660', 0), (1, '#3a4660', .5)], x2=0, y2=1)
    rimg = c.lin([(0, '#c9d6ea', .3), (.6, '#ffd9a0', .5), (1, '#c9d6ea', .25)])
    rare_x = {'Night': 3, 'Morning': 9, 'Daytime': 15, 'Evening': 21}[rare] * W / 24
    dawn = c.rad([(0, hor_c, .55), (1, hor_c, 0)])
    px = (peak_h + .5) * W / 24
    py = min(y for x, y in ridge if abs(x - px) < 2)
    ids = {name: c.nid('p') for name in ('far', 'mid', 'ridge', 'edge')}
    c.defs.append(f'<path id="{ids["far"]}" d="{_poly(far)}L{W + 80} {H}L-80 {H}Z"/>'
                  f'<path id="{ids["mid"]}" d="{_poly(mid)}L{W + 80} {H}L-80 {H}Z"/>'
                  f'<path id="{ids["edge"]}" d="{_poly(ridge)}"/><path id="{ids["ridge"]}" d="{_poly(ridge)}L{W + 60} {H}L-60 {H}Z"/>')
    far_p = f'<use href="#{ids["far"]}" fill="#0d1320"/>'
    mid_p = f'<use href="#{ids["mid"]}" fill="#070a11"/>'
    ridge_p = (f'<use href="#{ids["ridge"]}" fill="#020305"/>'
               f'<use href="#{ids["edge"]}" fill="none" stroke="url(#{rimg})" stroke-width=".8"/>'
               f'<g style="animation:§breathe 4s ease-in-out infinite">{c.light(px, py - 9, h=12, flare=.5)}</g>')

    # 6 · 38.2–45.4s 群山横移：远山慢、近山快（视差）
    layers = ''
    for body, dx in ((f'<use href="#{sky}" {SKY_FIT}/>' + c.stars(30, (0, 0, W, 200)), -8),
                     (far_p, -22), (f'<rect y="190" width="{W}" height="120" fill="url(#{haze})" opacity=".3"/>' + mid_p, -38),
                     (ridge_p, -58)):
        k = c.kf(f"from{{transform:translateX({-dx * .5:.0f}px)}}to{{transform:translateX({dx * .5:.0f}px)}}")
        layers += f'<g style="animation:{k} 7.2s ease-in-out 38.2s both">{body}</g>'
    shots.append(c.window(38.2, 45.4, c.camera(layers, W / 2, 260, 1.12, 1.04, 38.2, 7.2)))
    subs.append(c.subtitle(ZH_B['hours'], "These mountains are the twenty-four hours of my day.", 39.4, 44.8, y=46))

    # 7 · 45.0–51.8s 线框地球：「我知道早晨是什么，却很少见过它的样子」
    shots.append(c.window(45.0, 51.8, c.stars(50) + c.camera(_globe(c, W / 2, 150, 92, 45.0, _mix(hor_c, sun_c, .5)),
                                                             W / 2, 150, .92, 1.08, 45.0, 6.8)))
    subs.append(c.subtitle(ZH_B['know'].format(p=rare_zh), f"I know what {plain_en} is, but rarely what it looks like.", 46.2, 51.2))

    # 8 · 51.4–59.6s 日出：那段很少见到的时光
    skyg = c.lin([(0, '#020306', 1), (.55, sky_c, 1), (.86, hor_c, 1), (1, _mix(hor_c, sun_c, .5), 1)], x2=0, y2=1)
    bloom = c.rad([(0, sun_c, .55), (.3, sun_c, .18), (1, hor_c, 0)])
    sun = c.rad([(0, '#fffaf0', 1), (.6, sun_c, 1), (1, _mix(sun_c, hor_c, .4), 1)])
    sea = c.lin([(0, _mix(hor_c, '#000000', .55), 1), (1, '#020306', 1)], x2=0, y2=1)
    rr = random.Random(5)
    glints = []
    for _ in range(56):
        gy = 258 + rr.random() ** 1.6 * 88
        gx = 415 + rr.gauss(0, (20 + (gy - 258) * 1.6) * .45)
        gw = rr.uniform(4, 16) * (1 + (gy - 258) / 60)
        glints.append(f'<rect x="{_n(gx - gw / 2)}" y="{_n(gy)}" width="{_n(gw)}" height="1.2" fill="{sun_c}" class="§tw" '
                      f'style="animation-duration:{rr.uniform(1.2, 2.8):.1f}s;animation-delay:{rr.uniform(0, 2):.1f}s" '
                      f'opacity="{rr.uniform(.35, .9):.2f}"/>')
    sunrise = c.kf("from{transform:translateY(70px)}to{transform:translateY(-6px)}")
    streak = c.lin([(0, sun_c, 0), (.5, '#fff6e6', .7), (1, sun_c, 0)])
    shots.append(c.window(51.4, 59.6, c.camera(f'<rect width="{W}" height="258" fill="url(#{skyg})"/>'
                                               f'<g style="animation:{sunrise} 8.2s cubic-bezier(.3,0,.3,1) 51.4s both">'
                                               f'<circle cx="415" cy="258" r="250" fill="url(#{bloom})"/>'
                                               f'<circle cx="415" cy="258" r="46" fill="url(#{sun})"/></g>'
                                               f'<rect y="258" width="{W}" height="89" fill="url(#{sea})"/>{"".join(glints)}'
                                               f'<rect x="45" y="257.4" width="740" height="1.4" fill="url(#{streak})"/>',
                                               W / 2, 258, 1.1, 1.0, 51.4, 8.2), fade=1.2))
    # 结尾那束光落在最常写代码的时段；若它恰好也是「很少见到」的那段（极端分布下会撞上），改用提交最多的时段
    common_zh, common_en = COMMON[top if top != rare else ranked[0][0]]
    subs.append(c.subtitle(ZH_B['rare'].format(p=rare_zh), f"I rarely see {ask_en}.", 52.6, 55.8, y=86))
    subs.append(c.subtitle(ZH_B['glow'].format(c=common_zh), f"But every {common_en}, there is a light.", 56.2, 59.2, y=86)
                if total else c.subtitle(ZH_B['quiet'], "Quiet.", 56.2, 59.2, y=86))

    # 9 · 59.2–64.0s 片名卡
    shots.append(c.window(59.2, 64.0, c.stars(60) + c.camera(c.title_card(TITLE_B.format(p=rare_zh), f'I RARELY SEE {title_en.upper()}',
                                                                           NIGHT_WORDS, 59.2), W / 2, 168, 1.18, 1.0, 59.2, 4.8)))

    # 海报帧：银河、月相、群山，金色的光站在提交最多的那个小时的山顶
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
    poster = (f'<g style="animation:§drift 70s ease-in-out 64s infinite alternate"><use href="#{sky}" {SKY_FIT}/></g>'
              + c.stars(40, (0, 0, W, 220))
              + c.meteors([(320, -10, 150, 70, 16), (760, -10, 158, 81, 21)])
              + f'<ellipse cx="{_n(rare_x)}" cy="{base - 30}" rx="210" ry="80" fill="url(#{dawn})" opacity=".55"/>'
              + far_p + f'<rect y="190" width="{W}" height="120" fill="url(#{haze})" opacity=".3"/>' + mid_p + ridge_p
              + ''.join(moons) + labels + ticks
              + f'<text x="40" y="62" font-family="{BRUSH}" font-size="32" fill="{GOLD_CORE}">{TITLE_B.format(p=rare_zh)}</text>'
              f'<text x="41" y="86" font-family="{EN6}" font-size="10" letter-spacing="4.2" fill="{SILVER}">'
              f'I RARELY SEE {title_en.upper()}</text>'
              f'<text x="40" y="114" font-family="{EN}" font-size="15" fill="{INK}">I&#x27;m {PROFILE[top]}.</text>'
              f'<text x="40" y="134" font-family="{EN}" font-size="12.5" fill="{SILVER}">{total:,} commits in {profile_days} days · '
              f'most awake {peak_label} · busiest on {WEEKDAYS_EN[busiest]}</text>')
    final = f'<g style="animation:§in 2.4s ease-out 63.2s both">{poster}</g>'
    return c.svg(''.join(shots) + final + ''.join(subs))
