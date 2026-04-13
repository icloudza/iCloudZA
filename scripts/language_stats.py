#!/usr/bin/env python3
"""
GitHub 语言统计分析脚本
扫描用户所有仓库（包括私有）的提交历史，只统计指定作者的代码行数变化
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
EXTENSION_MAP = {
    # 编程语言
    '.dart': 'Dart',
    '.py': 'Python',
    '.js': 'JavaScript',
    '.mjs': 'JavaScript',
    '.cjs': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript',
    '.jsx': 'JavaScript',
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
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.zsh': 'Shell',
    '.ps1': 'PowerShell',
    '.vue': 'Vue',
    '.svelte': 'Svelte',
    # 标记语言
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'SASS',
    '.less': 'Less',
    '.xml': 'XML',
    '.svg': 'SVG',
    # 数据/配置
    '.json': 'JSON',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.toml': 'TOML',
    '.ini': 'INI',
    '.conf': 'Config',
    # 文档
    '.md': 'Markdown',
    '.markdown': 'Markdown',
    '.rst': 'reStructuredText',
    '.txt': 'Text',
    # 其他
    '.sql': 'SQL',
    '.graphql': 'GraphQL',
    '.proto': 'Protocol Buffers',
    '.dockerfile': 'Dockerfile',
    # 补充语言
    '.r': 'R',
    '.scala': 'Scala',
    '.ex': 'Elixir',
    '.exs': 'Elixir',
    '.erl': 'Erlang',
    '.hs': 'Haskell',
    '.jl': 'Julia',
    '.zig': 'Zig',
    '.tf': 'Terraform',
    '.hcl': 'HCL',
    '.pl': 'Perl',
    '.pm': 'Perl',
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
]


def get_language(filepath: str) -> str | None:
    """根据文件路径获取语言"""
    # 检查是否应该忽略
    for pattern in IGNORE_PATTERNS:
        if pattern in filepath:
            return None

    # 特殊文件名
    filename = os.path.basename(filepath).lower()
    if filename == 'dockerfile':
        return 'Dockerfile'
    if filename == 'makefile':
        return 'Makefile'
    if filename == 'cmakelists.txt':
        return 'CMake'

    # 按扩展名匹配
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

            repos.append({
                'name': repo['name'],
                'full_name': repo['full_name'],
                'clone_url': repo['clone_url'],
                'ssh_url': repo['ssh_url'],
                'private': repo.get('private', False),
                'default_branch': repo.get('default_branch', 'main'),
                'language': repo.get('language'),
            })
            visibility = "[Private]" if repo.get('private') else "[Public]"
            print(f"  {visibility} {repo['name']}")

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


def analyze_repo(repo_path: str, author_emails: list[str], since_days: int = 7) -> dict:
    """分析单个仓库的提交历史，只统计指定作者最近N天的提交"""
    stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 使用单次 git log，多个 --author 由 git 以 OR 逻辑合并，避免重复计数
    cmd = [
        'git', '-C', repo_path, 'log',
        f'--since={since_days} days ago',
        '--numstat',
        '--format=',
        '--no-merges'
    ]
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


def clone_repo(repo: dict, target_path: str, token: str, since_days: int = 7) -> bool:
    """克隆仓库（支持私有仓库，使用浅克隆加速）"""
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
        if result.returncode != 0:
            # 输出错误信息便于调试
            if result.stderr:
                print(f"    Git error: {result.stderr[:100]}", file=sys.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def get_commit_time_stats(username: str, token: str, repos: list, utc_offset: int = 8) -> dict:
    """通过 GitHub API 获取所有仓库中作者的 commit 时间分布"""
    categories = {'Morning': 0, 'Daytime': 0, 'Evening': 0, 'Night': 0}
    local_tz = timezone(timedelta(hours=utc_offset))

    for i, repo in enumerate(repos, 1):
        print(f"  [{i}/{len(repos)}] {repo['name']}...", end=' ', flush=True)
        page = 1
        repo_count = 0
        while page <= 20:  # 每仓库最多 2000 commits
            cmd = [
                'curl', '-s', '-H', f'Authorization: token {token}',
                '-H', 'Accept: application/vnd.github.v3+json',
                f'https://api.github.com/repos/{repo["full_name"]}/commits?author={username}&per_page=100&page={page}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                break

            if not data or isinstance(data, dict):
                break

            for commit in data:
                try:
                    date_str = commit['commit']['author']['date']
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    hour = dt.astimezone(local_tz).hour
                    repo_count += 1

                    if 6 <= hour < 12:
                        categories['Morning'] += 1
                    elif 12 <= hour < 18:
                        categories['Daytime'] += 1
                    elif 18 <= hour < 24:
                        categories['Evening'] += 1
                    else:
                        categories['Night'] += 1
                except (KeyError, ValueError):
                    continue

            if len(data) < 100:
                break
            page += 1

        print(f"{repo_count} commits")

    return categories


def generate_profile_stats(commit_stats: dict, repos: list) -> tuple:
    """生成 commit 时间分布和语言仓库分布的 Markdown 文本"""
    # === Commit 时间分布 ===
    total_commits = sum(commit_stats.values())
    commit_lines = []
    if total_commits > 0:
        max_cat = max(commit_stats, key=commit_stats.get)
        title_map = {
            'Morning': "I'm an Early 🐤",
            'Daytime': "I'm a Daytime ☀️",
            'Evening': "I'm an Evening 🌇",
            'Night': "I'm a Night 🦉",
        }
        commit_lines.append(f'**{title_map.get(max_cat, "Commit Stats")}**')
        commit_lines.append('```text')
        emojis = {'Morning': '🌞', 'Daytime': '🌆', 'Evening': '🌃', 'Night': '🌙'}
        for cat in ['Morning', 'Daytime', 'Evening', 'Night']:
            count = commit_stats[cat]
            pct = (count / total_commits) * 100
            bar = generate_bar(pct, 25)
            commit_lines.append(
                f"{emojis[cat]} {cat:<20}{count:>5} commits{' ' * 10}{bar} {pct:5.2f} %"
            )
        commit_lines.append('```')

    # === 语言仓库分布 ===
    lang_count = defaultdict(int)
    for repo in repos:
        lang = repo.get('language')
        if lang:
            lang_count[lang] += 1

    repo_lang_lines = []
    if lang_count:
        sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)
        top_lang = sorted_langs[0][0]
        total_repos = sum(lang_count.values())
        max_name_len = max(len(lang) for lang, _ in sorted_langs[:5])

        repo_lang_lines.append(f'**I Mostly Code in {top_lang}**')
        repo_lang_lines.append('```text')
        for lang, count in sorted_langs[:5]:
            pct = (count / total_repos) * 100
            bar = generate_bar(pct, 25)
            repo_lang_lines.append(
                f"{lang:<{max_name_len}}{count:>8} repos{' ' * 13}{bar} {pct:5.2f} %"
            )
        repo_lang_lines.append('```')

    return '\n'.join(commit_lines), '\n'.join(repo_lang_lines)


def main():
    username = os.environ.get('GITHUB_USERNAME', 'icloudza')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    output_file = os.environ.get('OUTPUT_FILE', 'assets/languages-stats.md')
    since_days = int(os.environ.get('SINCE_DAYS', '7'))  # 默认统计最近7天

    if not token:
        print("[ERROR] GH_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    print(f"Starting analysis for {username} (last {since_days} days)...")

    # 获取作者邮箱
    author_emails = get_author_emails(username, token)

    # 添加环境变量中的额外邮箱
    extra_emails = os.environ.get('AUTHOR_EMAILS', '').split(',')
    for email in extra_emails:
        email = email.strip()
        if email and email not in author_emails:
            author_emails.append(email)

    print(f"Author emails: {author_emails}")

    # 获取仓库列表（包括私有）
    repos = get_all_repos(username, token)
    print(f"\nFound {len(repos)} repositories (excluding forks)")

    private_count = sum(1 for r in repos if r['private'])
    public_count = len(repos) - private_count
    print(f"   Public: {public_count}  Private: {private_count}")

    # 汇总统计
    total_stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, repo in enumerate(repos, 1):
            visibility = "[Private]" if repo['private'] else "[Public]"
            print(f"\n[{i}/{len(repos)}] {visibility} Analyzing {repo['name']}...")

            repo_path = os.path.join(tmpdir, repo['name'])

            # 克隆仓库
            if clone_repo(repo, repo_path, token, since_days):
                # 分析仓库（只统计最近N天）
                repo_stats = analyze_repo(repo_path, author_emails, since_days)

                # 显示仓库统计
                if repo_stats:
                    repo_total = sum(s['added'] + s['deleted'] for s in repo_stats.values())
                    top_lang = max(repo_stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'])[0]
                    print(f"    [OK] {repo_total:,} lines (main: {top_lang})")
                else:
                    print(f"    [--] No commits this week")

                # 合并统计
                for lang, counts in repo_stats.items():
                    total_stats[lang]['added'] += counts['added']
                    total_stats[lang]['deleted'] += counts['deleted']

                # 清理
                shutil.rmtree(repo_path, ignore_errors=True)
            else:
                print(f"    [WARN] Clone failed, skipping")

    # 计算总行数和百分比
    total_lines = sum(s['added'] + s['deleted'] for s in total_stats.values())

    if total_lines == 0:
        print("\n[WARN] No code statistics found", file=sys.stderr)
        sys.exit(1)

    print(f"\nTotal: {total_lines:,} lines changed")

    # 排序（按总行数降序）
    sorted_stats = sorted(
        total_stats.items(),
        key=lambda x: x[1]['added'] + x[1]['deleted'],
        reverse=True
    )

    # 生成输出
    lines = []
    lines.append("```text")

    # 找出最长的语言名称用于对齐
    max_lang_len = max(len(lang) for lang, _ in sorted_stats[:10]) if sorted_stats else 10

    for rank, (lang, counts) in enumerate(sorted_stats[:5], 1):  # 只显示前5种语言
        added = counts['added']
        deleted = counts['deleted']
        total = added + deleted
        percentage = (total / total_lines) * 100

        # 格式化输出 - 带排名
        lang_padded = lang.ljust(max_lang_len)
        added_str = format_number(added).rjust(7)
        deleted_str = format_number(deleted).rjust(7)
        bar = generate_bar(percentage)
        pct_str = f"{percentage:5.1f}%"

        # 排名格式：1. 2. 3. ... 10.
        rank_str = f"{rank:2d}."
        lines.append(f"{rank_str} {lang_padded} +{added_str}/ -{deleted_str} {bar} {pct_str}")

    lines.append("```")

    # 输出结果
    output = '\n'.join(lines)
    print("\n" + "="*60)
    print(output)
    print("="*60)

    # 写入文件
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(output)

    print(f"\n[OK] Results saved to {output_file}")

    # 获取 commit 时间分布（通过 GitHub API，覆盖全部历史）
    utc_offset = int(os.environ.get('UTC_OFFSET', '8'))
    print(f"\nAnalyzing commit time distribution (UTC+{utc_offset})...")
    commit_stats = get_commit_time_stats(username, token, repos, utc_offset)
    total_commits = sum(commit_stats.values())
    print(f"Total: {total_commits} commits")

    # 生成 profile 统计
    commit_output, repo_lang_output = generate_profile_stats(commit_stats, repos)

    # 写入 commit 时间分布
    stats_dir = os.path.dirname(output_file)
    commit_file = os.path.join(stats_dir, 'commit-stats.md')
    with open(commit_file, 'w') as f:
        f.write(commit_output)
    print(f"[OK] Commit stats saved to {commit_file}")

    # 写入语言仓库分布
    repo_lang_file = os.path.join(stats_dir, 'repo-lang-stats.md')
    with open(repo_lang_file, 'w') as f:
        f.write(repo_lang_output)
    print(f"[OK] Repo language stats saved to {repo_lang_file}")


if __name__ == '__main__':
    main()
