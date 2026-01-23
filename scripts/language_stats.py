#!/usr/bin/env python3
"""
GitHub 语言统计分析脚本
扫描用户所有仓库的提交历史，统计各语言的代码行数变化
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from collections import defaultdict
from pathlib import Path

# 文件扩展名到语言的映射
EXTENSION_MAP = {
    # 编程语言
    '.dart': 'Dart',
    '.py': 'Python',
    '.js': 'JavaScript',
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
}

# 忽略的文件/目录模式
IGNORE_PATTERNS = [
    'node_modules', 'vendor', '.git', 'dist', 'build',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'Cargo.lock', 'pubspec.lock', 'Podfile.lock',
    '.min.js', '.min.css', '.map',
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
    """格式化数字，如 85300 -> 85.3k"""
    if abs(n) >= 1000000:
        return f"{n/1000000:.1f}m"
    elif abs(n) >= 1000:
        return f"{n/1000:.1f}k"
    else:
        return str(n)


def generate_bar(percentage: float, width: int = 20) -> str:
    """生成进度条"""
    filled = int(percentage / 100 * width)
    partial = (percentage / 100 * width) - filled

    bar = '█' * filled
    if partial >= 0.5 and filled < width:
        bar += '▌'
        filled += 1
    elif partial >= 0.25 and filled < width:
        bar += '▏'
        filled += 1

    bar += '░' * (width - len(bar))
    return bar[:width]


def get_repos(username: str, token: str) -> list:
    """获取用户的所有仓库"""
    repos = []
    page = 1
    per_page = 100

    while True:
        cmd = [
            'curl', '-s', '-H', f'Authorization: token {token}',
            '-H', 'Accept: application/vnd.github.v3+json',
            f'https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}&type=owner'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        if not data or isinstance(data, dict):
            break

        for repo in data:
            if not repo.get('fork', False):  # 排除 fork
                repos.append({
                    'name': repo['name'],
                    'clone_url': repo['clone_url'],
                    'default_branch': repo.get('default_branch', 'main')
                })

        if len(data) < per_page:
            break
        page += 1

    return repos


def analyze_repo(repo_path: str, author_emails: list[str]) -> dict:
    """分析单个仓库的提交历史"""
    stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 构建 author 过滤参数
    author_args = []
    for email in author_emails:
        author_args.extend(['--author', email])

    # 获取所有提交的 numstat
    cmd = ['git', '-C', repo_path, 'log', '--numstat', '--format=']
    cmd.extend(author_args)

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
                stats[lang]['added'] += int(added)
                stats[lang]['deleted'] += int(deleted)

    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 分析超时", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️ 分析错误: {e}", file=sys.stderr)

    return dict(stats)


def main():
    username = os.environ.get('GITHUB_USERNAME', 'icloudza')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    author_emails = os.environ.get('AUTHOR_EMAILS', f'{username},{username}@users.noreply.github.com').split(',')
    output_file = os.environ.get('OUTPUT_FILE', 'assets/languages-stats.md')

    if not token:
        print("错误: 需要设置 GH_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    print(f"📊 开始分析 {username} 的仓库...")
    print(f"📧 作者邮箱: {author_emails}")

    # 获取仓库列表
    repos = get_repos(username, token)
    print(f"📦 找到 {len(repos)} 个仓库")

    # 汇总统计
    total_stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, repo in enumerate(repos, 1):
            print(f"[{i}/{len(repos)}] 分析 {repo['name']}...")

            repo_path = os.path.join(tmpdir, repo['name'])

            # 浅克隆仓库
            clone_cmd = [
                'git', 'clone', '--quiet',
                repo['clone_url'], repo_path
            ]

            try:
                subprocess.run(clone_cmd, capture_output=True, timeout=120)

                # 分析仓库
                repo_stats = analyze_repo(repo_path, author_emails)

                # 合并统计
                for lang, counts in repo_stats.items():
                    total_stats[lang]['added'] += counts['added']
                    total_stats[lang]['deleted'] += counts['deleted']

                # 清理
                shutil.rmtree(repo_path, ignore_errors=True)

            except subprocess.TimeoutExpired:
                print(f"  ⚠️ 克隆超时，跳过", file=sys.stderr)
            except Exception as e:
                print(f"  ⚠️ 错误: {e}", file=sys.stderr)

    # 计算总行数和百分比
    total_lines = sum(s['added'] + s['deleted'] for s in total_stats.values())

    if total_lines == 0:
        print("⚠️ 没有找到任何代码统计", file=sys.stderr)
        sys.exit(1)

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
    max_lang_len = max(len(lang) for lang, _ in sorted_stats[:10])

    for lang, counts in sorted_stats[:10]:  # 只显示前10种语言
        added = counts['added']
        deleted = counts['deleted']
        total = added + deleted
        percentage = (total / total_lines) * 100

        # 格式化输出
        lang_padded = lang.ljust(max_lang_len)
        added_str = format_number(added).rjust(6)
        deleted_str = format_number(deleted).rjust(6)
        bar = generate_bar(percentage)
        pct_str = f"{percentage:5.1f}%"

        lines.append(f"{lang_padded}  +{added_str}/ -{deleted_str} {bar} {pct_str}")

    lines.append("```")

    # 输出结果
    output = '\n'.join(lines)
    print("\n" + output)

    # 写入文件
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(output)

    print(f"\n✅ 统计结果已保存到 {output_file}")


if __name__ == '__main__':
    main()
