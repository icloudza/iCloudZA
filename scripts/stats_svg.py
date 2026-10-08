#!/usr/bin/env python3
"""把语言统计 / 作息画像渲染成带加载动画的 SVG 卡片（无第三方依赖）

- render_languages_row：一行两块面板（本周语言 + 年度主要语言），宽 830
- render_commit_card：全宽作息卡片（24 小时柱状图 + 星期分布 + 四段占比）
"""

import math
from html import escape

FULL_W = 830          # 与 GitHub README 正文宽度一致。
GAP = 16
HALF_W = (FULL_W - GAP) // 2
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

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

THEMES = {
    'light': dict(bg='#ffffff', border='#d0d7de', title='#1f2328', text='#57606a',
                  muted='#8c959f', track='#eaeef2', accent='#0969da', soft='#9ec5f5'),
    'dark': dict(bg='#0d1117', border='#30363d', title='#e6edf3', text='#c9d1d9',
                 muted='#8b949e', track='#21262d', accent='#58a6ff', soft='#2f4a6f'),
}

def _rays(cx: float, cy: float, r1: float, r2: float, angles) -> str:
    """以 (cx, cy) 为圆心、半径 r1 到 r2 的放射线段（0° 朝右，逆时针为正）"""
    d = ''
    for a in angles:
        c, s = math.cos(math.radians(a)), -math.sin(math.radians(a))
        d += f"M{cx + r1*c:.2f} {cy + r1*s:.2f}L{cx + r2*c:.2f} {cy + r2*s:.2f}"
    return d


# 24x24 网格上的图标：{f} 是实心部分，{s} 是 2px 圆头线条，颜色由 _icon 决定。
# 四个时段各有一个图标：日出（地平线上的半个太阳 + 三道光芒）、正午的太阳、
# 日落（落到地平线的半个太阳 + 水面倒影）、弯月 + 星
ICONS = {
    'code': '<path {f} d="M8.7 5.3 3.4 10.6a2 2 0 0 0 0 2.8l5.3 5.3 1.4-1.4L4.8 12l5.3-5.3zm6.6 0-1.4 1.4 5.3 5.3-5.3 5.3 1.4 1.4 5.3-5.3a2 2 0 0 0 0-2.8z"/>',
    'sunrise': ('<path {f} d="M6.5 17.5a5.5 5.5 0 0 1 11 0z"/>'
                '<path {s} d="M2.5 18.5h19' + _rays(12, 17.5, 8, 10.2, (45, 90, 135)) + '"/>'),
    'sun': ('<circle {f} cx="12" cy="12" r="4.5"/>'
            '<path {s} d="' + _rays(12, 12, 7.6, 9.8, range(0, 360, 45)) + '"/>'),
    'sunset': ('<path {f} d="M6.5 12.5a5.5 5.5 0 0 1 11 0z"/>'
               '<path {s} d="M2.5 13.5h19M6.5 17.5h11M9.5 21h5"/>'),
    # 外圆 (11,13) r8.5 被右上方 (15,9) r7.6 的圆咬掉一块；星星是四角的闪光
    'moon': ('<path {f} d="M8.64 4.83A8.5 8.5 0 1 0 19.17 15.36A7.6 7.6 0 0 1 8.64 4.83z"/>'
             '<path {f} d="M19 2.4Q19 5 21.6 5Q19 5 19 7.6Q19 5 16.4 5Q19 5 19 2.4z"/>'),
}

TIME_PROFILE = {
    'Morning': ('Early Bird', 'sunrise'),
    'Daytime': ('Daytime Coder', 'sun'),
    'Evening': ('Evening Coder', 'sunset'),
    'Night': ('Night Owl', 'moon'),
}
TIME_COLORS = {'Morning': '#f2cc60', 'Daytime': '#54aeff', 'Evening': '#a475f9', 'Night': '#6e7fb3'}
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _fmt(n: int) -> str:
    """统一保留三位有效数字（987 / 6.80k / 94.4k / 136k / 1.23m），增删列宽度更整齐"""
    if abs(n) < 1000:
        return str(n)
    for div, unit in ((1000, 'k'), (1_000_000, 'm')):
        # 先按两位小数，超过三位有效数字就减一位；进位到 1000 时换下一个单位
        for decimals in (2, 1, 0):
            s = f"{n / div:.{decimals}f}"
            if len(s.lstrip('-').replace('.', '')) <= 3:
                break
        if abs(float(s)) < 1000:
            break
    return s + unit


def _style(theme: str) -> str:
    def block(t):
        c = THEMES[t]
        return (f".bg{{fill:{c['bg']}}}.bd{{stroke:{c['border']}}}.ti{{fill:{c['title']}}}"
                f".tx{{fill:{c['text']}}}.mu{{fill:{c['muted']}}}.tr{{fill:{c['track']}}}"
                f".ac{{fill:{c['accent']}}}.so{{fill:{c['soft']}}}.acs{{stroke:{c['accent']}}}")
    css = f"text{{font-family:{FONT};font-variant-numeric:tabular-nums}}"
    if theme == 'auto':
        css += block('light') + f"@media(prefers-color-scheme:dark){{{block('dark')}}}"
    else:
        css += block(theme)
    css += (
        "@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}"
        "@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        "@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
        # fill-mode 用 both：延迟期间套用起始帧，结束后停在终态；
        # 静态样式不写 opacity:0 / scale(0)，动画不运行的环境里直接显示终态，不会出现空白卡片。
        # 系统开了「减少动态效果」时不加动画，同样直接显示终态
        "@media(prefers-reduced-motion:no-preference){"
        ".f{animation:fade .5s cubic-bezier(.2,.8,.2,1) both}"
        ".gx{animation:growx .9s cubic-bezier(.2,.8,.2,1) both}"
        ".gy{animation:growy .8s cubic-bezier(.2,.8,.2,1) both}}"
    )
    return f"<style>{css}</style>"


def _svg_open(w: int, h: int, theme: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<title>{escape(title)}</title>{_style(theme)}')


def _panel_bg(x: int, y: int, w: int, h: int) -> str:
    return f'<rect class="bg bd" x="{x+0.5}" y="{y+0.5}" width="{w-1}" height="{h-1}" rx="6" stroke-width="1"/>'


def _icon(name: str, x: float, y: float, size: float, color: str | None = None) -> str:
    """把 ICONS[name] 画进左上角 (x, y)、边长 size 的方框；不传 color 时跟随主题强调色"""
    f, s = (f'fill="{color}"', f'stroke="{color}"') if color else ('class="ac"', 'class="acs"')
    s += ' fill="none" stroke-width="2" stroke-linecap="round"'
    return f'<g transform="translate({x},{y}) scale({size / 24:.3f})">{ICONS[name].format(f=f, s=s)}</g>'


def _title(x: int, y: int, text: str, icon: str, size: int = 14) -> str:
    return (f'<g class="f">{_icon(icon, x, y - size + 1, size * 1.15)}'
            f'<text class="ti" x="{x + size + 8}" y="{y}" font-size="{size}" font-weight="600">{escape(text)}</text></g>')


# ---------- 语言面板 ----------

def _lang_panel(ox: int, w: int, title: str, subtitle: str, stats: dict, top_n: int = 5, delay0: float = 0.0) -> str:
    pad = 20
    rows = sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)[:top_n]
    total = sum(v['added'] + v['deleted'] for v in stats.values())
    out = [_title(ox + pad, 30, title, 'code'),
           f'<text class="mu f" x="{ox+pad}" y="46" font-size="10.5" style="animation-delay:{delay0+.1:.2f}s">{escape(subtitle)}</text>']
    if not rows:
        out.append(f'<text class="mu f" x="{ox+pad}" y="82" font-size="11">No code changes in this period</text>')
        return ''.join(out)

    row_h, top = 24, 68
    bar_x, bar_w, bar_h = ox + 118, 132, 9
    for i, (lang, v) in enumerate(rows):
        y = top + i * row_h
        pct = (v['added'] + v['deleted']) / total * 100 if total else 0
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
        d = delay0 + 0.15 + i * 0.08
        out.append(f'<g class="f" style="animation-delay:{d:.2f}s">')
        out.append(f'<circle cx="{ox+pad+4}" cy="{y+4.5}" r="4" fill="{color}"/>')
        out.append(f'<text class="tx" x="{ox+pad+14}" y="{y+8.5}" font-size="11" font-weight="500">{escape(lang)}</text>')
        out.append(f'<rect class="tr" x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="4.5"/>')
        fw = max(bar_w * pct / 100, 5)
        out.append(f'<rect class="gx" x="{bar_x}" y="{y}" width="{fw:.1f}" height="{bar_h}" rx="4.5" fill="{color}" '
                   f'style="transform-origin:{bar_x}px {y}px;animation-delay:{d:.2f}s"/>')
        out.append(f'<text class="ti" x="{bar_x+bar_w+8}" y="{y+8.5}" font-size="11" font-weight="600">{pct:.1f}%</text>')
        out.append(f'<text x="{ox+w-pad}" y="{y+8.5}" font-size="10" text-anchor="end">'
                   f'<tspan fill="#3fb950">+{_fmt(v["added"])}</tspan> <tspan fill="#f85149">−{_fmt(v["deleted"])}</tspan></text>')
        out.append('</g>')
    return ''.join(out)


def render_languages_row(weekly: dict, weekly_days: int, yearly: dict, yearly_days: int, theme: str = 'auto') -> str:
    """一行两块：本周语言 + 年度主要语言"""
    h = 200
    ysorted = sorted(yearly.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)
    ytitle = f"I Mostly Code in {ysorted[0][0]}" if ysorted and sum(v['added']+v['deleted'] for v in yearly.values()) else "Languages"
    out = [_svg_open(FULL_W, h, theme, f"This week's languages and {ytitle}"),
           _panel_bg(0, 0, HALF_W, h), _panel_bg(HALF_W + GAP, 0, HALF_W, h),
           _lang_panel(0, HALF_W, "This Week's Languages", f"last {weekly_days} days · lines changed by me", weekly),
           _lang_panel(HALF_W + GAP, HALF_W, ytitle, f"last {yearly_days} days · lines changed by me", yearly, delay0=0.1),
           '</svg>']
    return ''.join(out)


# ---------- 作息卡片（全宽） ----------

def _pick_title(cats: dict, total: int):
    ranked = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    if total and (ranked[0][1] - ranked[1][1]) / total * 100 >= 5:
        top = ranked[0][0]
    else:
        top = 'Night' if cats['Evening'] + cats['Night'] >= cats['Morning'] + cats['Daytime'] else 'Morning'
    return TIME_PROFILE[top]


def render_commit_card(matrix: list, profile_days: int, theme: str = 'auto') -> str:
    """全宽作息卡片。matrix: 7x24，[weekday][hour]，Monday=0"""
    hours = [sum(matrix[d][h] for d in range(7)) for h in range(24)]
    days = [sum(matrix[d]) for d in range(7)]
    total = sum(hours)
    cats = {'Morning': sum(hours[6:12]), 'Daytime': sum(hours[12:18]),
            'Evening': sum(hours[18:24]), 'Night': sum(hours[0:6])}
    title, icon = _pick_title(cats, total)
    title = f"I'm {'an' if title[0] in 'AEIOU' else 'a'} {title}"   # an Early Bird / an Evening Coder

    best_s, best_v = 0, -1
    for s in range(24):
        v = sum(hours[(s + k) % 24] for k in range(3))
        if v > best_v:
            best_s, best_v = s, v
    peak_hours = {(best_s + k) % 24 for k in range(3)}
    peak_label = f"{best_s:02d}:00 – {(best_s+3)%24:02d}:00"
    busiest_day = WEEKDAYS[max(range(7), key=lambda d: days[d])] if total else '-'

    pad, h = 24, 236
    subtitle = f"{total:,} commits in the last {profile_days} days · peak {peak_label} · busiest on {busiest_day}"
    out = [_svg_open(FULL_W, h, theme, f"{title}: {subtitle}"), _panel_bg(0, 0, FULL_W, h),
           _title(pad, 34, title, icon, size=15),
           f'<text class="mu f" x="{pad}" y="52" font-size="10.5" style="animation-delay:.1s">{subtitle}</text>']

    # --- 左侧：24 小时柱状图 ---
    base_y, max_h = 152, 70
    col_w, col_gap = 17, 5
    mx = max(hours) or 1
    cx0 = pad
    # 峰值区间底衬；跨过午夜（如 22:00 – 01:00）时分成两段画
    for start, n_cols in ((best_s, min(3, 24 - best_s)), (0, best_s + 3 - 24)):
        if n_cols > 0:
            px = cx0 + start * (col_w + col_gap) - 3
            out.append(f'<rect class="tr f" x="{px}" y="{base_y-max_h-14}" width="{n_cols*(col_w+col_gap)+1}" '
                       f'height="{max_h+22}" rx="5" style="animation-delay:.2s"/>')
    # 最高的柱子上标数值；并列时只标一根，优先标峰值区间里的
    label_hr = max(range(24), key=lambda hr: (hours[hr], hr in peak_hours))
    for hr, n in enumerate(hours):
        x = cx0 + hr * (col_w + col_gap)
        bh = max(max_h * n / mx, 2) if n else 2
        cls = 'ac' if hr in peak_hours else 'so'
        out.append(f'<rect class="{cls} gy" x="{x}" y="{base_y-bh:.1f}" width="{col_w}" height="{bh:.1f}" rx="2.5" '
                   f'style="transform-origin:{x}px {base_y}px;animation-delay:{0.25+hr*0.03:.2f}s"/>')
        if hr == label_hr and n:
            out.append(f'<text class="ti f" x="{x+col_w/2:.1f}" y="{base_y-bh-5:.1f}" font-size="9.5" font-weight="600" '
                       f'text-anchor="middle" style="animation-delay:1s">{n}</text>')
    for hr in range(0, 24, 3):
        x = cx0 + hr * (col_w + col_gap)
        out.append(f'<text class="mu f" x="{x}" y="{base_y+14}" font-size="9.5" style="animation-delay:.9s">{hr:02d}</text>')
    out.append(f'<text class="mu f" x="{cx0 + 24*(col_w+col_gap) - col_gap}" y="{base_y+14}" font-size="9.5" text-anchor="end" style="animation-delay:.9s">24h</text>')

    # --- 右侧：星期分布 ---
    wx = cx0 + 24 * (col_w + col_gap) + 26   # ≈ 578
    wbar_x, wbar_w = wx + 30, FULL_W - pad - (wx + 30) - 40
    dmx = max(days) or 1
    out.append(f'<text class="mu f" x="{wx}" y="{base_y-max_h-8}" font-size="9.5" style="animation-delay:.3s">BY WEEKDAY</text>')
    for d in range(7):
        y = base_y - max_h + 4 + d * 12
        pct = days[d] / total * 100 if total else 0
        delay = 0.35 + d * 0.06
        strong = days[d] == max(days)
        out.append(f'<g class="f" style="animation-delay:{delay:.2f}s">')
        out.append(f'<text class="{"ti" if strong else "tx"}" x="{wx}" y="{y+7}" font-size="10" font-weight="{600 if strong else 400}">{WEEKDAYS[d]}</text>')
        out.append(f'<rect class="tr" x="{wbar_x}" y="{y}" width="{wbar_w}" height="8" rx="4"/>')
        fw = max(wbar_w * days[d] / dmx, 4)
        out.append(f'<rect class="{"ac" if strong else "so"} gx" x="{wbar_x}" y="{y}" width="{fw:.1f}" height="8" rx="4" '
                   f'style="transform-origin:{wbar_x}px {y}px;animation-delay:{delay:.2f}s"/>')
        out.append(f'<text class="mu" x="{FULL_W-pad}" y="{y+7}" font-size="9.5" text-anchor="end">{pct:.0f}%</text>')
        out.append('</g>')

    # --- 底部：四段堆叠条 + 图例 ---
    bar_y, bar_w = 184, FULL_W - 2 * pad
    out.append(f'<clipPath id="seg"><rect x="{pad}" y="{bar_y}" width="{bar_w}" height="7" rx="3.5"/></clipPath>')
    out.append(f'<rect class="tr" x="{pad}" y="{bar_y}" width="{bar_w}" height="7" rx="3.5"/>')
    x = pad
    for name in ('Morning', 'Daytime', 'Evening', 'Night'):
        w = bar_w * cats[name] / total if total else 0
        out.append(f'<rect class="gx" x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="7" fill="{TIME_COLORS[name]}" '
                   f'clip-path="url(#seg)" style="transform-origin:{pad}px {bar_y}px;animation-delay:.8s"/>')
        x += w
    lx = pad
    for i, (name, rng) in enumerate((('Morning', '06–12'), ('Daytime', '12–18'), ('Evening', '18–24'), ('Night', '00–06'))):
        pct = cats[name] / total * 100 if total else 0
        out.append(f'<g class="f" style="animation-delay:{1.0+i*0.07:.2f}s">')
        # 图例用各时段的图标代替色点，颜色与上方分段条一致
        out.append(_icon(TIME_PROFILE[name][1], lx - 1, bar_y + 18.5, 13, color=TIME_COLORS[name]))
        out.append(f'<text class="tx" x="{lx+17}" y="{bar_y+28.5}" font-size="10.5">{name}'
                   f'<tspan class="mu" font-size="9.5"> {rng}</tspan></text>')
        out.append(f'<text class="ti" x="{lx+113}" y="{bar_y+28.5}" font-size="11" font-weight="600">{pct:.1f}%'
                   f'<tspan class="mu" font-size="9.5" font-weight="400"> {cats[name]:,}</tspan></text>')
        out.append('</g>')
        lx += bar_w / 4
    out.append('</svg>')
    return ''.join(out)
