#!/usr/bin/env python3
"""
GitHub 语言统计分析脚本
扫描用户所有仓库（包括私有）的提交历史，只统计指定作者本人的提交，生成三块统计：
  1. 本周语言统计（SINCE_DAYS，默认 7 天）：按语言汇总代码行数变化
  2. 作息画像（PROFILE_DAYS，默认 365 天）：按提交时的本地时区统计提交时段
  3. 主要语言（PROFILE_DAYS，默认 365 天）：按语言汇总本人代码行数
三块共用同一份 PROFILE_DAYS 窗口的浅克隆，不额外调用 commit API。
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# 文件扩展名到语言的映射
# 只统计主流编程语言和前端语言；数据/配置/文档/构建脚本类文件
# （JSON、YAML、TOML、Markdown、XML、Protocol Buffers、Dockerfile 等）不计入统计
EXTENSION_MAP = {
    # 通用编程语言
    '.py': 'Python',
    '.go': 'Go',
    '.rs': 'Rust',
    '.java': 'Java',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin',
    '.swift': 'Swift',
    '.c': 'C',
    '.h': 'C',
    '.cpp': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.hpp': 'C++',
    '.cs': 'C#',
    '.php': 'PHP',
    '.rb': 'Ruby',
    '.lua': 'Lua',
    '.dart': 'Dart',
    '.scala': 'Scala',
    '.r': 'R',
    '.ex': 'Elixir',
    '.exs': 'Elixir',
    '.erl': 'Erlang',
    '.hs': 'Haskell',
    '.jl': 'Julia',
    '.zig': 'Zig',
    '.pl': 'Perl',
    '.pm': 'Perl',
    '.sql': 'SQL',
    # 脚本语言
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.zsh': 'Shell',
    '.ps1': 'PowerShell',
    # 前端语言
    '.js': 'JavaScript',
    '.mjs': 'JavaScript',
    '.cjs': 'JavaScript',
    '.jsx': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript',
    '.vue': 'Vue',
    '.svelte': 'Svelte',
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'SASS',
    '.less': 'Less',
}

# 忽略的文件/目录模式
IGNORE_PATTERNS = [
    'node_modules/', 'vendor/', '.git/', 'dist/', 'build/', 'target/',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'Cargo.lock', 'pubspec.lock', 'Podfile.lock', 'composer.lock',
    '.min.js', '.min.css', '.map', '.bundle.js',
    '__pycache__/', '.pyc', '.pyo',
    'go.sum',
    # 自动生成的文件
    '.generated.', '.gen.', 'generated/',
    '*.g.dart', '*.freezed.dart',
    '.pb.go', '_generated.go', 'zz_generated',
    # 构建产物和缓存
    'coverage/', '.next/', '.nuxt/', '.output/',
    '.terraform/', '.terraform.lock.hcl',
    '*.snap',
    # 第三方代码（匹配不区分大小写，所以也覆盖 Vendor/ 之类的写法）
    'third_party/', 'third-party/', 'thirdparty/',
    '.xcframework/', 'pods/', 'carthage/', 'checkouts/',
]


def get_language(filepath: str) -> str | None:
    """根据文件路径获取语言"""
    # 检查是否应该忽略（不区分大小写）
    lowered = filepath.lower()
    for pattern in IGNORE_PATTERNS:
        if pattern in lowered:
            return None

    # 按扩展名匹配（未列入映射表的文件类型不计入统计）
    ext = os.path.splitext(filepath)[1].lower()
    return EXTENSION_MAP.get(ext)


def format_number(n: int) -> str:
    """格式化数字，保持高精度"""
    if abs(n) >= 1000000:
        return f"{n/1000000:.2f}m"
    elif abs(n) >= 100000:
        return f"{n/1000:.1f}k"
    elif abs(n) >= 10000:
        return f"{n/1000:.2f}k"
    elif abs(n) >= 1000:
        return f"{n/1000:.2f}k"
    else:
        return str(n)


def generate_bar(percentage: float, width: int = 21) -> str:
    """生成进度条，使用更精细的字符"""
    # Unicode 块字符：█ ▉ ▊ ▋ ▌ ▍ ▎ ▏
    blocks = ['', '▏', '▎', '▍', '▌', '▋', '▊', '▉', '█']

    filled_float = percentage / 100 * width
    filled_full = int(filled_float)
    remainder = filled_float - filled_full

    bar = '█' * filled_full

    # 添加部分填充字符
    if filled_full < width:
        partial_index = int(remainder * 8)
        if partial_index > 0:
            bar += blocks[partial_index]
            filled_full += 1

    # 填充剩余空白
    bar += '░' * (width - len(bar))

    return bar[:width]


def get_all_repos(username: str, token: str) -> list:
    """获取用户的所有仓库（包括私有仓库）"""
    repos = []
    page = 1
    per_page = 100

    print("Fetching repository list...")

    while True:
        # 使用 /user/repos 端点获取包括私有仓库在内的所有仓库
        cmd = [
            'curl', '-s', '-H', f'Authorization: token {token}',
            '-H', 'Accept: application/vnd.github.v3+json',
            f'https://api.github.com/user/repos?per_page={per_page}&page={page}&affiliation=owner,collaborator,organization_member&visibility=all'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"[WARN] API response parse failed: {result.stdout[:200]}", file=sys.stderr)
            break

        if not data or isinstance(data, dict):
            if isinstance(data, dict) and 'message' in data:
                print(f"[WARN] API error: {data['message']}", file=sys.stderr)
            break

        for repo in data:
            # 排除 fork 和 profile 仓库
            if repo.get('fork', False):
                continue
            if repo['name'].lower() == username.lower():  # 排除与用户名同名的 profile 仓库
                continue
            if repo['name'].lower() == 'icloudza':  # 排除 iCloudZA profile 仓库
                continue
            if repo.get('archived', False):  # 排除已归档仓库
                continue

            repos.append({
                'name': repo['name'],
                'full_name': repo['full_name'],
                'clone_url': repo['clone_url'],
                'ssh_url': repo['ssh_url'],
                'private': repo.get('private', False),
                'default_branch': repo.get('default_branch', 'main'),
            })

        if len(data) < per_page:
            break
        page += 1

    return repos


def get_author_emails(username: str, token: str) -> list[str]:
    """获取用户的所有邮箱地址"""
    emails = [username, f'{username}@users.noreply.github.com']

    # 尝试获取用户的邮箱
    cmd = [
        'curl', '-s', '-H', f'Authorization: token {token}',
        '-H', 'Accept: application/vnd.github.v3+json',
        'https://api.github.com/user/emails'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'email' in item:
                    email = item['email']
                    if email not in emails:
                        emails.append(email)
    except:
        pass

    return emails


def get_shallow_boundary(repo_path: str) -> list[str]:
    """返回浅克隆的边界提交哈希列表

    边界提交在本地没有父提交，git 会把它的 diff 显示为整棵树新增，
    统计行数时必须排除，否则一次小提交会被算成整个仓库的代码量。
    仓库本身的真实根提交不在 shallow 文件里，不受影响。
    """
    try:
        result = subprocess.run(
            ['git', '-C', repo_path, 'rev-parse', '--git-path', 'shallow'],
            capture_output=True, text=True, timeout=30,
        )
        shallow_file = result.stdout.strip()
        if not os.path.isabs(shallow_file):
            shallow_file = os.path.join(repo_path, shallow_file)
        if os.path.exists(shallow_file):
            with open(shallow_file) as f:
                return [line.strip() for line in f if line.strip()]
    except Exception:
        pass
    return []


def analyze_repo(repo_path: str, author_emails: list[str], since_days: int = 7) -> dict:
    """分析单个仓库的提交历史，只统计指定作者最近N天的提交"""
    stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 使用单次 git log，多个 --author 由 git 以 OR 逻辑合并，避免重复计数
    cmd = [
        'git', '-C', repo_path, 'log',
        f'--since={since_days} days ago',
        '--numstat',
        '--format=',
        '--no-merges',
        'HEAD',
    ]
    # 排除浅克隆边界提交（见 get_shallow_boundary）
    for commit in get_shallow_boundary(repo_path):
        cmd.append(f'^{commit}')
    for email in author_emails:
        cmd.append(f'--author={email}')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        lines = result.stdout.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) != 3:
                continue

            added, deleted, filepath = parts

            # 跳过二进制文件
            if added == '-' or deleted == '-':
                continue

            lang = get_language(filepath)
            if lang:
                try:
                    stats[lang]['added'] += int(added)
                    stats[lang]['deleted'] += int(deleted)
                except ValueError:
                    continue

    except subprocess.TimeoutExpired:
        print(f"    [WARN] Analysis timeout", file=sys.stderr)
    except Exception as e:
        print(f"    [WARN] Analysis error: {e}", file=sys.stderr)

    return dict(stats)


# clone_repo 的返回状态
CLONE_OK = 'ok'                  # 克隆成功
CLONE_NO_COMMITS = 'no_commits'  # 时间窗口内没有任何提交（浅克隆无法进行）
CLONE_FAILED = 'failed'          # 真正的克隆失败（权限、网络等）


def clone_repo(repo: dict, target_path: str, token: str, since_days: int = 7) -> str:
    """克隆仓库（支持私有仓库，使用浅克隆加速）

    返回 CLONE_OK / CLONE_NO_COMMITS / CLONE_FAILED 之一。

    注意：`--shallow-since` 在时间窗口内没有任何提交时，git 会直接报
    `fatal: error processing shallow info` 并退出，而不是克隆出一个空仓库。
    这种情况并非真正的失败，只代表该仓库在时间窗口内没有提交。
    """
    clone_url = repo['clone_url']
    if clone_url.startswith('https://'):
        clone_url = clone_url.replace('https://', f'https://{token}@')

    clone_cmd = [
        'git', 'clone', '--quiet',
        '--no-checkout',
        '--no-tags',
        '--single-branch',
        f'--shallow-since={since_days + 1} days ago',
        clone_url, target_path
    ]

    try:
        result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            return CLONE_OK

        stderr = result.stderr or ''
        if 'shallow info' in stderr:
            return CLONE_NO_COMMITS

        # 输出错误信息便于调试
        if stderr:
            print(f"    Git error: {stderr[:100]}", file=sys.stderr)
        return CLONE_FAILED
    except subprocess.TimeoutExpired:
        print("    Git error: clone timed out", file=sys.stderr)
        return CLONE_FAILED
    except Exception as e:
        print(f"    Git error: {e}", file=sys.stderr)
        return CLONE_FAILED


def get_commit_hours(repo_path: str, author_emails: list[str], since_days: int) -> list[int]:
    """从本地克隆中读取指定作者最近 N 天的提交时间（小时），使用提交时记录的本地时区

    git 的 %aI 会输出带时区偏移的 ISO 时间，例如 2026-09-04T23:12:01+08:00，
    直接取小时即为作者当时所在时区的本地小时，不需要假设固定时区。
    合并提交的时间是点按钮的时间而非写代码的时间，所以排除。
    """
    cmd = [
        'git', '-C', repo_path, 'log',
        f'--since={since_days} days ago',
        '--no-merges',
        '--format=%aI',
    ]
    for email in author_emails:
        cmd.append(f'--author={email}')

    hours = []
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        for line in result.stdout.split('\n'):
            line = line.strip()
            if len(line) >= 13 and line[10] == 'T':
                try:
                    hours.append(int(line[11:13]))
                except ValueError:
                    continue
    except subprocess.TimeoutExpired:
        print("    [WARN] Commit time analysis timeout", file=sys.stderr)
    except Exception as e:
        print(f"    [WARN] Commit time analysis error: {e}", file=sys.stderr)
    return hours


def merge_stats(total: dict, part: dict) -> None:
    """把单仓库的语言统计合并进总表"""
    for lang, counts in part.items():
        total[lang]['added'] += counts['added']
        total[lang]['deleted'] += counts['deleted']


def sort_stats(stats: dict) -> list:
    """按总行数降序排列"""
    return sorted(stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'], reverse=True)


def render_lang_block(stats: dict, top_n: int, width: int, empty_text: str) -> list[str]:
    """渲染语言统计代码块（不含标题），本周和年度两块共用同一格式"""
    lines = ['```text']
    sorted_stats = sort_stats(stats)
    total_lines = sum(s['added'] + s['deleted'] for _, s in sorted_stats)

    if total_lines == 0:
        lines.append(empty_text)
        lines.append('```')
        return lines

    shown = sorted_stats[:top_n]
    max_lang_len = max(len(lang) for lang, _ in shown)

    for rank, (lang, counts) in enumerate(shown, 1):
        added = counts['added']
        deleted = counts['deleted']
        percentage = (added + deleted) / total_lines * 100
        lines.append(
            f"{rank:2d}. {lang.ljust(max_lang_len)} "
            f"+{format_number(added).rjust(7)}/ -{format_number(deleted).rjust(7)} "
            f"{generate_bar(percentage, width)} {percentage:5.1f}%"
        )

    lines.append('```')
    return lines


# 作息分档（按作者本地时间）
TIME_CATEGORIES = [
    ('Morning', 6, 12, '🌞'),
    ('Daytime', 12, 18, '🌆'),
    ('Evening', 18, 24, '🌃'),
    ('Night', 0, 6, '🌙'),
]
TIME_TITLES = {
    'Morning': "I'm an Early 🐤",
    'Daytime': "I'm a Daytime ☀️",
    'Evening': "I'm an Evening 🌇",
    'Night': "I'm a Night 🦉",
}
# 最高档领先第二档不足此百分点时，改用“早半天 / 晚半天”合并判定，避免标题频繁跳动
TITLE_MARGIN = 5.0


def pick_time_title(categories: dict, total: int) -> str:
    """根据分档占比选标题"""
    ranked = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    top_name, top_count = ranked[0]
    second_count = ranked[1][1] if len(ranked) > 1 else 0
    margin = (top_count - second_count) / total * 100

    if margin >= TITLE_MARGIN:
        return TIME_TITLES[top_name]

    late = categories['Evening'] + categories['Night']
    early = categories['Morning'] + categories['Daytime']
    return TIME_TITLES['Night'] if late >= early else TIME_TITLES['Morning']


def peak_window(hours: list[int], span: int = 3) -> tuple[int, int]:
    """找出提交最集中的连续 span 小时（环形），返回 (起始小时, 结束小时)"""
    hist = [0] * 24
    for h in hours:
        hist[h % 24] += 1
    best_start, best_sum = 0, -1
    for start in range(24):
        total = sum(hist[(start + i) % 24] for i in range(span))
        if total > best_sum:
            best_start, best_sum = start, total
    return best_start, (best_start + span) % 24


def generate_profile_stats(hours: list[int], yearly_stats: dict, profile_days: int) -> tuple[str, str]:
    """生成 commit 时间分布和主要语言两块的 Markdown 文本"""
    # === Commit 时间分布 ===
    total_commits = len(hours)
    commit_lines = []
    if total_commits > 0:
        categories = {name: 0 for name, _, _, _ in TIME_CATEGORIES}
        for h in hours:
            for name, start, end, _ in TIME_CATEGORIES:
                if start <= h < end:
                    categories[name] += 1
                    break

        commit_lines.append(f'**{pick_time_title(categories, total_commits)}**')
        commit_lines.append('```text')
        for name, _, _, emoji in TIME_CATEGORIES:
            count = categories[name]
            pct = count / total_commits * 100
            commit_lines.append(
                f"{emoji} {name:<20}{count:>5} commits{' ' * 10}{generate_bar(pct, 25)} {pct:5.2f} %"
            )
        start, end = peak_window(hours)
        commit_lines.append('')
        commit_lines.append(
            f"⏰ Peak hours: {start:02d}:00 - {end:02d}:00   "
            f"({total_commits:,} commits in the last {profile_days} days)"
        )
        commit_lines.append('```')
    else:
        commit_lines.append('**Commit Stats**')
        commit_lines.append('```text')
        commit_lines.append(f'No commits in the last {profile_days} days')
        commit_lines.append('```')

    # === 主要语言（按过去一年本人代码行数） ===
    sorted_yearly = sort_stats(yearly_stats)
    repo_lang_lines = []
    if sorted_yearly and sum(s['added'] + s['deleted'] for _, s in sorted_yearly) > 0:
        repo_lang_lines.append(f'**I Mostly Code in {sorted_yearly[0][0]}**')
    else:
        repo_lang_lines.append('**Language Stats**')
    repo_lang_lines.extend(render_lang_block(
        yearly_stats, top_n=5, width=25,
        empty_text=f'No code changes in the last {profile_days} days',
    ))

    return '\n'.join(commit_lines), '\n'.join(repo_lang_lines)


def main():
    username = os.environ.get('GITHUB_USERNAME', 'icloudza')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    output_file = os.environ.get('OUTPUT_FILE', 'assets/languages-stats.md')
    since_days = int(os.environ.get('SINCE_DAYS', '7'))        # 本周统计窗口
    profile_days = int(os.environ.get('PROFILE_DAYS', '365'))  # 作息画像 / 主要语言窗口

    if not token:
        print("[ERROR] GH_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    print(f"Starting analysis for {username} (weekly: {since_days} days, profile: {profile_days} days)...")

    # 获取作者邮箱
    author_emails = get_author_emails(username, token)

    # 添加环境变量中的额外邮箱
    extra_emails = os.environ.get('AUTHOR_EMAILS', '').split(',')
    for email in extra_emails:
        email = email.strip()
        if email and email not in author_emails:
            author_emails.append(email)

    print(f"Author emails: {len(author_emails)} configured")

    # 获取仓库列表（包括私有）
    repos = get_all_repos(username, token)
    print(f"\nFound {len(repos)} repositories (excluding forks and archived)")

    private_count = sum(1 for r in repos if r['private'])
    public_count = len(repos) - private_count
    print(f"   Public: {public_count}  Private: {private_count}")

    # 汇总统计：本周 / 年度 / 提交时间
    weekly_stats = defaultdict(lambda: {'added': 0, 'deleted': 0})
    yearly_stats = defaultdict(lambda: {'added': 0, 'deleted': 0})
    commit_hours: list[int] = []

    # 一份 profile_days 窗口的浅克隆同时服务三块统计
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, repo in enumerate(repos, 1):
            visibility = "[Private]" if repo['private'] else "[Public]"
            print(f"\n[{i}/{len(repos)}] {visibility} Analyzing repo...")

            repo_path = os.path.join(tmpdir, f"repo{i}")

            clone_status = clone_repo(repo, repo_path, token, profile_days)
            if clone_status == CLONE_OK:
                week = analyze_repo(repo_path, author_emails, since_days)
                year = analyze_repo(repo_path, author_emails, profile_days)
                hours = get_commit_hours(repo_path, author_emails, profile_days)

                merge_stats(weekly_stats, week)
                merge_stats(yearly_stats, year)
                commit_hours.extend(hours)

                week_total = sum(s['added'] + s['deleted'] for s in week.values())
                year_total = sum(s['added'] + s['deleted'] for s in year.values())
                if week_total:
                    top_lang = sort_stats(week)[0][0]
                    print(f"    [OK] week: {week_total:,} lines (main: {top_lang})")
                else:
                    print(f"    [--] No commits this week")
                print(f"    [..] year: {year_total:,} lines, {len(hours)} commits")

                shutil.rmtree(repo_path, ignore_errors=True)
            elif clone_status == CLONE_NO_COMMITS:
                print(f"    [--] No commits in the last {profile_days} days")
            else:
                print(f"    [WARN] Clone failed, skipping")

    # === 本周语言统计 ===
    weekly_total = sum(s['added'] + s['deleted'] for s in weekly_stats.values())
    if weekly_total == 0:
        print(f"\n[--] No code changes in the last {since_days} days")
    else:
        print(f"\nTotal this week: {weekly_total:,} lines changed")

    output = '\n'.join(render_lang_block(
        weekly_stats, top_n=5, width=21,
        empty_text=f'No code changes in the last {since_days} days',
    ))
    print("\n" + "=" * 60)
    print(output)
    print("=" * 60)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(output)
    print(f"\n[OK] Results saved to {output_file}")

    # === 作息画像 + 主要语言 ===
    yearly_total = sum(s['added'] + s['deleted'] for s in yearly_stats.values())
    print(f"\nProfile window: {len(commit_hours):,} commits, {yearly_total:,} lines changed")

    commit_output, repo_lang_output = generate_profile_stats(commit_hours, yearly_stats, profile_days)
    print("\n" + commit_output)
    print(repo_lang_output)

    stats_dir = os.path.dirname(output_file)
    commit_file = os.path.join(stats_dir, 'commit-stats.md')
    with open(commit_file, 'w') as f:
        f.write(commit_output)
    print(f"\n[OK] Commit stats saved to {commit_file}")

    repo_lang_file = os.path.join(stats_dir, 'repo-lang-stats.md')
    with open(repo_lang_file, 'w') as f:
        f.write(repo_lang_output)
    print(f"[OK] Repo language stats saved to {repo_lang_file}")


if __name__ == '__main__':
    main()
