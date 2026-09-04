#!/usr/bin/env python3
"""把语言统计 / 作息画像渲染成带加载动画的 SVG 卡片（无第三方依赖）"""

from html import escape

CARD_W = 495
PAD = 24
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

# GitHub linguist 配色
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
                  muted='#8c959f', track='#eaeef2', accent='#0969da'),
    'dark': dict(bg='#0d1117', border='#30363d', title='#e6edf3', text='#c9d1d9',
                 muted='#8b949e', track='#21262d', accent='#58a6ff'),
}

# 图标（24x24 viewBox 的 path）
ICON_CODE = "M8.7 5.3 3.4 10.6a2 2 0 0 0 0 2.8l5.3 5.3 1.4-1.4L4.8 12l5.3-5.3zm6.6 0-1.4 1.4 5.3 5.3-5.3 5.3 1.4 1.4 5.3-5.3a2 2 0 0 0 0-2.8z"
ICON_CAL = "M7 2v2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2zm-2 8h14v9H5z"
ICON_MOON = "M21.6 14.9A9.5 9.5 0 0 1 9.1 2.4a1 1 0 0 0-1.2-1.3A11 11 0 1 0 22.9 16.1a1 1 0 0 0-1.3-1.2zM12 21a9 9 0 0 1-5.4-16.2A11.5 11.5 0 0 0 19.2 17.4 9 9 0 0 1 12 21z"
ICON_SUN = "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm-1-6h2v3h-2zm0 19h2v3h-2zM1 11h3v2H1zm19 0h3v2h-3zM4.2 5.6l1.4-1.4 2.1 2.1-1.4 1.4zm12.1 12.1 1.4-1.4 2.1 2.1-1.4 1.4zM4.2 18.4l2.1-2.1 1.4 1.4-2.1 2.1zM16.3 6.3l2.1-2.1 1.4 1.4-2.1 2.1z"
ICON_DUSK = "M12 6a6 6 0 0 0-6 6h12a6 6 0 0 0-6-6zM2 14h20v2H2zm3 4h14v2H5z"

TIME_PROFILE = {
    'Morning': ('Early Bird', ICON_SUN),
    'Daytime': ('Daytime Coder', ICON_SUN),
    'Evening': ('Evening Coder', ICON_DUSK),
    'Night': ('Night Owl', ICON_MOON),
}
TIME_COLORS = {'Morning': '#f2cc60', 'Daytime': '#54aeff', 'Evening': '#a475f9', 'Night': '#3b4b7e'}


def _fmt(n: int) -> str:
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}m"
    if abs(n) >= 1000:
        return f"{n/1000:.2f}k" if abs(n) < 100_000 else f"{n/1000:.1f}k"
    return str(n)


def _style(theme: str, extra: str = '') -> str:
    """生成 <style>；theme='auto' 时用媒体查询自动适配深色模式"""
    def block(t):
        c = THEMES[t]
        return (f".bg{{fill:{c['bg']}}}.bd{{stroke:{c['border']}}}.ti{{fill:{c['title']}}}"
                f".tx{{fill:{c['text']}}}.mu{{fill:{c['muted']}}}.tr{{fill:{c['track']}}}.ac{{fill:{c['accent']}}}")
    css = f"text{{font-family:{FONT};font-variant-numeric:tabular-nums}}"
    if theme == 'auto':
        css += block('light') + f"@media(prefers-color-scheme:dark){{{block('dark')}}}"
    else:
        css += block(theme)
    css += (
        "@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}"
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".f{opacity:0;animation:fade .5s cubic-bezier(.2,.8,.2,1) forwards}"
        ".g{transform:scaleX(0);animation:grow .9s cubic-bezier(.2,.8,.2,1) forwards}"
    ) + extra
    return f"<style>{css}</style>"


def _card_open(w: int, h: int, theme: str, extra_css: str = '') -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img">{_style(theme, extra_css)}'
            f'<rect class="bg bd" x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="6" stroke-width="1"/>')


def _title(text: str, icon: str, y: int = 36) -> str:
    return (f'<g class="f"><path class="ac" transform="translate({PAD},{y-15}) scale(0.75)" d="{icon}"/>'
            f'<text class="ti" x="{PAD+26}" y="{y}" font-size="16" font-weight="600">{escape(text)}</text></g>')


def render_language_card(title: str, stats: dict, subtitle: str = '', top_n: int = 5,
                         theme: str = 'auto') -> str:
    """语言条形卡片。stats: {lang: {'added': int, 'deleted': int}}"""
    rows = sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)[:top_n]
    total = sum(v['added'] + v['deleted'] for v in stats.values())

    row_h, top = 30, 66
    h = top + row_h * max(len(rows), 1) + 16 + (18 if subtitle else 0)
    out = [_card_open(CARD_W, h, theme), _title(title, ICON_CODE)]
    if subtitle:
        out.append(f'<text class="mu f" x="{PAD}" y="54" font-size="11" style="animation-delay:.1s">{escape(subtitle)}</text>')
        top += 18

    if not rows:
        out.append(f'<text class="mu f" x="{PAD}" y="{top+12}" font-size="12">No code changes in this period</text>')
        out.append('</svg>')
        return ''.join(out)

    bar_x, bar_w = 150, 175
    for i, (lang, v) in enumerate(rows):
        y = top + i * row_h
        pct = (v['added'] + v['deleted']) / total * 100 if total else 0
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
        delay = 0.15 + i * 0.09
        out.append(f'<g class="f" style="animation-delay:{delay:.2f}s">')
        out.append(f'<circle cx="{PAD+5}" cy="{y+6}" r="4.5" fill="{color}"/>')
        out.append(f'<text class="tx" x="{PAD+16}" y="{y+10}" font-size="12" font-weight="500">{escape(lang)}</text>')
        out.append(f'<rect class="tr" x="{bar_x}" y="{y}" width="{bar_w}" height="12" rx="6"/>')
        fill_w = max(bar_w * pct / 100, 6)
        out.append(f'<rect class="g" x="{bar_x}" y="{y}" width="{fill_w:.1f}" height="12" rx="6" fill="{color}" '
                   f'style="transform-origin:{bar_x}px {y}px;animation-delay:{delay:.2f}s"/>')
        out.append(f'<text class="ti" x="{bar_x+bar_w+10}" y="{y+10}" font-size="12" font-weight="600">{pct:.1f}%</text>')
        out.append(f'<text class="mu" x="{CARD_W-PAD}" y="{y+10}" font-size="11" text-anchor="end">'
                   f'<tspan fill="#3fb950">+{_fmt(v["added"])}</tspan> <tspan fill="#f85149">−{_fmt(v["deleted"])}</tspan></text>')
        out.append('</g>')

    out.append('</svg>')
    return ''.join(out)


def _hex_alpha(hex_color: str, alpha: float) -> str:
    a = max(0, min(255, int(alpha * 255)))
    return f"{hex_color}{a:02x}"


def render_commit_time_card(hours_hist: list, profile_days: int, theme: str = 'auto') -> str:
    """作息卡片。hours_hist: 长度 24 的列表，每小时提交数"""
    total = sum(hours_hist)
    cats = {
        'Morning': sum(hours_hist[6:12]),
        'Daytime': sum(hours_hist[12:18]),
        'Evening': sum(hours_hist[18:24]),
        'Night': sum(hours_hist[0:6]),
    }
    # 标题判定：最高档领先不足 5 个百分点时按早/晚半天合并
    ranked = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    if total and (ranked[0][1] - ranked[1][1]) / total * 100 >= 5:
        top = ranked[0][0]
    else:
        top = 'Night' if cats['Evening'] + cats['Night'] >= cats['Morning'] + cats['Daytime'] else 'Morning'
    title, icon = TIME_PROFILE[top]

    # 最活跃的连续 3 小时
    best_s, best_v = 0, -1
    for s in range(24):
        v = sum(hours_hist[(s + k) % 24] for k in range(3))
        if v > best_v:
            best_s, best_v = s, v
    peak = f"{best_s:02d}:00 – {(best_s+3)%24:02d}:00"

    h = 214
    extra = "@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}.p{opacity:0;animation:pop .45s cubic-bezier(.2,.8,.2,1) forwards}"
    out = [_card_open(CARD_W, h, theme, extra), _title(f"I'm a {title}", icon)]
    out.append(f'<text class="mu f" x="{PAD}" y="54" font-size="11" style="animation-delay:.1s">'
               f'{total:,} commits in the last {profile_days} days · peak {peak}</text>')

    # 24 小时热力条
    strip_y, cell_h, gap = 74, 30, 3
    cell_w = (CARD_W - 2 * PAD - gap * 23) / 24
    mx = max(hours_hist) or 1
    accent = THEMES['dark' if theme == 'dark' else 'light']['accent']
    for hr, n in enumerate(hours_hist):
        x = PAD + hr * (cell_w + gap)
        alpha = 0.12 + 0.88 * (n / mx) ** 0.75 if n else 0.0
        in_peak = (hr - best_s) % 24 < 3
        out.append(f'<g class="p" style="animation-delay:{0.2 + hr*0.025:.3f}s">')
        out.append(f'<rect class="tr" x="{x:.1f}" y="{strip_y}" width="{cell_w:.1f}" height="{cell_h}" rx="3"/>')
        if n:
            out.append(f'<rect x="{x:.1f}" y="{strip_y}" width="{cell_w:.1f}" height="{cell_h}" rx="3" '
                       f'fill="{_hex_alpha(accent, alpha)}"/>')
        if in_peak:
            out.append(f'<rect x="{x+0.5:.1f}" y="{strip_y+0.5}" width="{cell_w-1:.1f}" height="{cell_h-1}" rx="3" '
                       f'fill="none" stroke="{accent}" stroke-width="1"/>')
        out.append('</g>')
    for hr in (0, 6, 12, 18):
        x = PAD + hr * (cell_w + gap)
        out.append(f'<text class="mu f" x="{x:.1f}" y="{strip_y+cell_h+14}" font-size="10" style="animation-delay:.6s">{hr:02d}</text>')
    out.append(f'<text class="mu f" x="{CARD_W-PAD}" y="{strip_y+cell_h+14}" font-size="10" text-anchor="end" style="animation-delay:.6s">24</text>')

    # 四段堆叠条 + 图例
    bar_y, bar_w = 140, CARD_W - 2 * PAD
    out.append(f'<rect class="tr" x="{PAD}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/>')
    x = PAD
    out.append(f'<clipPath id="seg"><rect x="{PAD}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/></clipPath>')
    for name in ('Morning', 'Daytime', 'Evening', 'Night'):
        w = bar_w * cats[name] / total if total else 0
        out.append(f'<rect class="g" x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="8" fill="{TIME_COLORS[name]}" '
                   f'clip-path="url(#seg)" style="transform-origin:{PAD}px {bar_y}px;animation-delay:.7s"/>')
        x += w
    lx = PAD
    for i, name in enumerate(('Morning', 'Daytime', 'Evening', 'Night')):
        pct = cats[name] / total * 100 if total else 0
        out.append(f'<g class="f" style="animation-delay:{0.9 + i*0.08:.2f}s">')
        out.append(f'<circle cx="{lx+5}" cy="{bar_y+26}" r="4" fill="{TIME_COLORS[name]}"/>')
        out.append(f'<text class="tx" x="{lx+14}" y="{bar_y+30}" font-size="11">{name}</text>')
        out.append(f'<text class="ti" x="{lx+14}" y="{bar_y+48}" font-size="12" font-weight="600">{pct:.1f}%</text>')
        out.append(f'<text class="mu" x="{lx+14+(44 if pct>=10 else 36)}" y="{bar_y+48}" font-size="10">{cats[name]:,}</text>')
        out.append('</g>')
        lx += bar_w / 4

    out.append('</svg>')
    return ''.join(out)
