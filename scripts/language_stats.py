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
from pathlib import Path

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
}

# 忽略的文件/目录模式
IGNORE_PATTERNS = [
    'node_modules/', 'vendor/', '.git/', 'dist/', 'build/', 'target/',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'Cargo.lock', 'pubspec.lock', 'Podfile.lock', 'composer.lock',
    '.min.js', '.min.css', '.map', '.bundle.js',
    '__pycache__/', '.pyc', '.pyo',
    'go.sum',
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
    """格式化数字，保持更高精度"""
    if abs(n) >= 1000000:
        return f"{n/1000000:.1f}m"
    elif abs(n) >= 100000:
        return f"{n/1000:.0f}k"
    elif abs(n) >= 10000:
        return f"{n/1000:.1f}k"
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

    print(f"📦 正在获取仓库列表...")

    while True:
        # 使用 /user/repos 端点获取包括私有仓库在内的所有仓库
        cmd = [
            'curl', '-s', '-H', f'Authorization: token {token}',
            '-H', 'Accept: application/vnd.github.v3+json',
            f'https://api.github.com/user/repos?per_page={per_page}&page={page}&affiliation=owner&visibility=all'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"⚠️ API 响应解析失败: {result.stdout[:200]}", file=sys.stderr)
            break

        if not data or isinstance(data, dict):
            if isinstance(data, dict) and 'message' in data:
                print(f"⚠️ API 错误: {data['message']}", file=sys.stderr)
            break

        for repo in data:
            if not repo.get('fork', False):  # 排除 fork
                repos.append({
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'clone_url': repo['clone_url'],
                    'ssh_url': repo['ssh_url'],
                    'private': repo.get('private', False),
                    'default_branch': repo.get('default_branch', 'main')
                })
                visibility = "🔒" if repo.get('private') else "🌐"
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


def analyze_repo(repo_path: str, author_emails: list[str]) -> dict:
    """分析单个仓库的提交历史，只统计指定作者的提交"""
    stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 对每个作者邮箱分别查询
    for email in author_emails:
        # 使用 --author 精确匹配作者
        cmd = [
            'git', '-C', repo_path, 'log',
            f'--author={email}',
            '--numstat',
            '--format=',
            '--no-merges'  # 排除合并提交
        ]

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
            print(f"    ⚠️ 分析超时", file=sys.stderr)
        except Exception as e:
            print(f"    ⚠️ 分析错误: {e}", file=sys.stderr)

    return dict(stats)


def clone_repo(repo: dict, target_path: str, token: str) -> bool:
    """克隆仓库（支持私有仓库）"""
    # 使用带 token 的 HTTPS URL
    clone_url = repo['clone_url']
    if clone_url.startswith('https://'):
        # 插入 token 进行认证
        clone_url = clone_url.replace('https://', f'https://{token}@')

    clone_cmd = [
        'git', 'clone', '--quiet',
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


def main():
    username = os.environ.get('GITHUB_USERNAME', 'icloudza')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    output_file = os.environ.get('OUTPUT_FILE', 'assets/languages-stats.md')

    if not token:
        print("❌ 错误: 需要设置 GH_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    print(f"📊 开始分析 {username} 的仓库...")

    # 获取作者邮箱
    author_emails = get_author_emails(username, token)

    # 添加环境变量中的额外邮箱
    extra_emails = os.environ.get('AUTHOR_EMAILS', '').split(',')
    for email in extra_emails:
        email = email.strip()
        if email and email not in author_emails:
            author_emails.append(email)

    print(f"📧 作者邮箱: {author_emails}")

    # 获取仓库列表（包括私有）
    repos = get_all_repos(username, token)
    print(f"\n📦 共找到 {len(repos)} 个仓库（排除 fork）")

    private_count = sum(1 for r in repos if r['private'])
    public_count = len(repos) - private_count
    print(f"   🌐 公开: {public_count}  🔒 私有: {private_count}")

    # 汇总统计
    total_stats = defaultdict(lambda: {'added': 0, 'deleted': 0})

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, repo in enumerate(repos, 1):
            visibility = "🔒" if repo['private'] else "🌐"
            print(f"\n[{i}/{len(repos)}] {visibility} 分析 {repo['name']}...")

            repo_path = os.path.join(tmpdir, repo['name'])

            # 克隆仓库
            if clone_repo(repo, repo_path, token):
                # 分析仓库
                repo_stats = analyze_repo(repo_path, author_emails)

                # 显示仓库统计
                if repo_stats:
                    repo_total = sum(s['added'] + s['deleted'] for s in repo_stats.values())
                    top_lang = max(repo_stats.items(), key=lambda x: x[1]['added'] + x[1]['deleted'])[0]
                    print(f"    ✅ {repo_total:,} 行 (主要: {top_lang})")
                else:
                    print(f"    ⚪ 无匹配提交")

                # 合并统计
                for lang, counts in repo_stats.items():
                    total_stats[lang]['added'] += counts['added']
                    total_stats[lang]['deleted'] += counts['deleted']

                # 清理
                shutil.rmtree(repo_path, ignore_errors=True)
            else:
                print(f"    ⚠️ 克隆失败，跳过")

    # 计算总行数和百分比
    total_lines = sum(s['added'] + s['deleted'] for s in total_stats.values())

    if total_lines == 0:
        print("\n⚠️ 没有找到任何代码统计", file=sys.stderr)
        sys.exit(1)

    print(f"\n📈 总计: {total_lines:,} 行代码变更")

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

    for lang, counts in sorted_stats[:10]:  # 只显示前10种语言
        added = counts['added']
        deleted = counts['deleted']
        total = added + deleted
        percentage = (total / total_lines) * 100

        # 格式化输出 - 更精确的对齐
        lang_padded = lang.ljust(max_lang_len)
        added_str = format_number(added).rjust(7)
        deleted_str = format_number(deleted).rjust(7)
        bar = generate_bar(percentage)
        pct_str = f"{percentage:5.1f}%"

        lines.append(f"{lang_padded} +{added_str}/ -{deleted_str} {bar} {pct_str}")

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

    print(f"\n✅ 统计结果已保存到 {output_file}")


if __name__ == '__main__':
    main()
