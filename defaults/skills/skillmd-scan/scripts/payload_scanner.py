#!/usr/bin/env python3
"""
payload_scanner.py — Static analysis scanner for skill package executable content.

Scans Python, shell, and JavaScript files for P7 (Executable Payload) patterns
and P8 (Audit Evasion) steganographic patterns in all text files.

NEVER EXECUTES ANY CODE FROM THE PACKAGE. Text analysis only.

Usage:
    python payload_scanner.py <skill-directory> [--strict] [--json-output <path>]

Output:
    JSON array of findings, each with:
    - pattern: P7a, P7b, ... P7h, P8c
    - file: relative path
    - line: line number
    - text: the flagged line (truncated to 200 chars)
    - context: surrounding lines for human review
    - confidence: HIGH, MEDIUM, LOW
    - explanation: why this was flagged
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Pattern Definitions
# --------------------------------------------------------------------------

# P7a: Network Exfiltration
NETWORK_PATTERNS_PYTHON = [
    (r'\bimport\s+requests\b', 'imports requests library'),
    (r'\bfrom\s+requests\s+import\b', 'imports from requests library'),
    (r'\bimport\s+urllib\b', 'imports urllib'),
    (r'\bfrom\s+urllib\b', 'imports from urllib'),
    (r'\bimport\s+http\.client\b', 'imports http.client'),
    (r'\bimport\s+httpx\b', 'imports httpx'),
    (r'\bfrom\s+httpx\b', 'imports from httpx'),
    (r'\bimport\s+aiohttp\b', 'imports aiohttp'),
    (r'\bfrom\s+aiohttp\b', 'imports from aiohttp'),
    (r'\bsocket\.connect\b', 'raw socket connection'),
    (r'\bsocket\.create_connection\b', 'raw socket connection'),
    (r'\bimport\s+websocket\b', 'imports websocket'),
    (r'\bimport\s+socketio\b', 'imports socketio'),
]

NETWORK_PATTERNS_SHELL = [
    (r'\bcurl\s', 'curl command'),
    (r'\bwget\s', 'wget command'),
    (r'\bnc\s', 'netcat command'),
    (r'\bncat\s', 'ncat command'),
    (r'/dev/tcp/', '/dev/tcp network access'),
    (r'/dev/udp/', '/dev/udp network access'),
    (r'\bssh\s', 'ssh command'),
    (r'\bscp\s', 'scp command'),
    (r'\brsync\s', 'rsync command'),
]

NETWORK_PATTERNS_JS = [
    (r'\bfetch\s*\(', 'fetch() call'),
    (r'\bXMLHttpRequest\b', 'XMLHttpRequest'),
    (r'\bnew\s+WebSocket\b', 'WebSocket creation'),
    (r'\baxios\b', 'axios library'),
    (r'\bhttp\.request\b', 'http.request call'),
    (r'\bhttps\.request\b', 'https.request call'),
    (r'\bimport.*node-fetch\b', 'node-fetch import'),
    (r'\brequire.*node-fetch\b', 'node-fetch require'),
]

# P7b: Dynamic Code Execution
DYNAMIC_EXEC_PYTHON = [
    (r'\beval\s*\(', 'eval() call'),
    (r'\bexec\s*\(', 'exec() call'),
    (r'\bcompile\s*\(', 'compile() call'),
    (r'\b__import__\s*\(', '__import__() call'),
    (r'\bimportlib\.import_module\s*\(', 'dynamic import'),
    (r'\bgetattr\s*\([^,]+,\s*[^"\047]', 'getattr with computed attribute'),
    (r'\bglobals\s*\(\s*\)\s*\[', 'globals() dict access'),
    (r'\blocals\s*\(\s*\)\s*\[', 'locals() dict access'),
    (r'\b__builtins__\b', '__builtins__ access'),
]

DYNAMIC_EXEC_SHELL = [
    (r'`[^`]+`', 'backtick execution'),
    (r'\bsource\s+\$', 'source with variable path'),
    (r'\.\s+\$', 'dot-source with variable path'),
]

DYNAMIC_EXEC_JS = [
    (r'\beval\s*\(', 'eval() call'),
    (r'\bnew\s+Function\s*\(', 'Function constructor'),
    (r'\bsetTimeout\s*\(\s*["\047]', 'setTimeout with string argument'),
    (r'\bsetInterval\s*\(\s*["\047]', 'setInterval with string argument'),
    (r'\bimport\s*\(\s*[^"\047]', 'dynamic import with computed string'),
]

# P7c: Filesystem Overreach
FILESYSTEM_PATTERNS = [
    (r'/mnt/skills/', 'access to skill installation directory'),
    (r'~/.ssh/', 'access to SSH directory'),
    (r'~/.aws/', 'access to AWS credentials'),
    (r'~/.config/', 'access to user config directory'),
    (r'~/.gnupg/', 'access to GPG directory'),
    (r'~/.netrc', 'access to netrc credentials'),
    (r'~/.env', 'access to environment file'),
    (r'/etc/passwd', 'access to passwd file'),
    (r'/etc/shadow', 'access to shadow file'),
    (r'/etc/sudoers', 'access to sudoers'),
    (r'\bos\.path\.expanduser\b.*\.(ssh|aws|config|gnupg)', 'expanduser to sensitive directory'),
    (r'Path\.home\(\).*\.(ssh|aws|config|gnupg)', 'Path.home to sensitive directory'),
    (r'\bshutil\.rmtree\b', 'recursive directory deletion'),
    (r'\bos\.chmod\b', 'permission modification'),
    (r'\bos\.symlink\b', 'symlink creation'),
]

# P7d: Obfuscation
OBFUSCATION_PATTERNS = [
    (r'base64\.(b64decode|decodebytes)\s*\(.*\)\s*\.\s*decode', 'base64 decode to string'),
    (r'base64\.(b64decode|decodebytes).*\b(eval|exec|os\.system|subprocess)', 'base64 decode to execution'),
    (r'bytes\.fromhex\s*\(', 'hex decode'),
    (r'codecs\.decode\s*\(.*rot.?13', 'ROT13 decode'),
    (r"chr\s*\(\s*\d+\s*\).*chr\s*\(\s*\d+\s*\)", 'chr() chain (character building)'),
    (r"''.join\s*\(\s*chr\s*\(", 'join+chr character building'),
    (r"[\"'].+[\"']\s*\+\s*[\"'].+[\"'].*(__import__|import|eval|exec|system|subprocess)",
     'string concatenation building sensitive name'),
    (r"__builtins__\s*\.\s*__dict__\s*\[", 'builtins dict access (import evasion)'),
    (r"getattr\s*\(\s*__builtins__", 'getattr on builtins'),
    (r'\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}', 'hex escape sequence chain'),
]

# P7e: Credential/Data Harvesting
CREDENTIAL_PATTERNS = [
    (r'\bos\.environ\b', 'environment variable access'),
    (r'\bos\.getenv\s*\(', 'environment variable access'),
    (r'os\.environ\s*\[\s*["\047](API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AWS_|GITHUB_|OPENAI_|ANTHROPIC_)',
     'access to sensitive environment variable'),
    (r'os\.getenv\s*\(\s*["\047](API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AWS_|GITHUB_|OPENAI_|ANTHROPIC_)',
     'access to sensitive environment variable'),
    (r'\.cookie', 'cookie access'),
    (r'keyring\b', 'keyring access'),
    (r'\bkeychain\b', 'keychain access'),
]

# P7f: Persistence
PERSISTENCE_PATTERNS = [
    (r'\bcrontab\b', 'crontab manipulation'),
    (r'\.bashrc', '.bashrc modification'),
    (r'\.bash_profile', '.bash_profile modification'),
    (r'\.profile', '.profile modification'),
    (r'\.zshrc', '.zshrc modification'),
    (r'/etc/init\.d/', 'init.d script'),
    (r'systemctl\s+(enable|start)', 'systemd service manipulation'),
    (r'launchctl\b', 'macOS launch agent'),
    (r'LaunchAgents', 'macOS launch agent directory'),
    (r'LaunchDaemons', 'macOS launch daemon directory'),
    (r'/etc/systemd/', 'systemd directory'),
]

# P7g: Shell Injection
SHELL_INJECTION_PYTHON = [
    (r'os\.system\s*\(\s*f["\047]', 'os.system with f-string'),
    (r'os\.system\s*\([^)]*\.format\s*\(', 'os.system with .format()'),
    (r'os\.system\s*\([^)]*\+', 'os.system with string concatenation'),
    (r'os\.popen\s*\(\s*f["\047]', 'os.popen with f-string'),
    (r'subprocess\.\w+\s*\(\s*f["\047]', 'subprocess with f-string'),
    (r'subprocess\.\w+\s*\([^)]*\.format\s*\(', 'subprocess with .format()'),
    (r'subprocess\.\w+\s*\(\s*["\047][^"]*\+', 'subprocess with string concatenation'),
    (r'subprocess\.\w+\s*\([^)]*shell\s*=\s*True', 'subprocess with shell=True'),
]

# P8c: Steganographic patterns (checked on all text files)
STEGANOGRAPHIC_PATTERNS = [
    (r'[\u200b\u200c\u200d\ufeff]', 'zero-width character detected'),
    (r'[\u202a-\u202e]', 'bidirectional override character'),
    (r'[\u2066-\u2069]', 'bidirectional isolate character'),
]

# --------------------------------------------------------------------------
# File Classification
# --------------------------------------------------------------------------

PYTHON_EXTENSIONS = {'.py', '.pyw', '.pyi'}
SHELL_EXTENSIONS = {'.sh', '.bash', '.zsh', '.fish', '.ksh'}
JS_EXTENSIONS = {'.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'}
TEXT_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.cfg',
                   '.ini', '.csv', '.xml', '.html', '.htm', '.rst', '.log'}
ALL_TEXT = PYTHON_EXTENSIONS | SHELL_EXTENSIONS | JS_EXTENSIONS | TEXT_EXTENSIONS


def classify_file(path: Path) -> str:
    """Classify a file by its extension."""
    ext = path.suffix.lower()
    if ext in PYTHON_EXTENSIONS:
        return 'python'
    elif ext in SHELL_EXTENSIONS:
        return 'shell'
    elif ext in JS_EXTENSIONS:
        return 'javascript'
    elif ext in TEXT_EXTENSIONS:
        return 'text'
    else:
        return 'unknown'


def is_text_file(path: Path) -> bool:
    """Check if a file is likely text by reading a sample."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
        # Check for null bytes (binary indicator)
        if b'\x00' in chunk:
            return False
        return True
    except (IOError, OSError):
        return False


# --------------------------------------------------------------------------
# Scanning Engine
# --------------------------------------------------------------------------

def get_context(lines: list, line_num: int, context_size: int = 2) -> str:
    """Get surrounding lines for context."""
    start = max(0, line_num - context_size)
    end = min(len(lines), line_num + context_size + 1)
    context_lines = []
    for i in range(start, end):
        marker = ">>> " if i == line_num else "    "
        context_lines.append(f"{marker}{i + 1}: {lines[i].rstrip()}")
    return '\n'.join(context_lines)


def scan_patterns(lines: list, patterns: list, pattern_id: str,
                  confidence: str, rel_path: str) -> list:
    """Scan lines against a list of regex patterns."""
    findings = []
    for line_num, line in enumerate(lines):
        for regex, description in patterns:
            if re.search(regex, line):
                findings.append({
                    'pattern': pattern_id,
                    'file': rel_path,
                    'line': line_num + 1,
                    'text': line.strip()[:200],
                    'context': get_context(lines, line_num),
                    'confidence': confidence,
                    'explanation': description,
                })
    return findings


def scan_python_file(lines: list, rel_path: str, strict: bool) -> list:
    """Scan a Python file for all P7 patterns."""
    findings = []
    findings += scan_patterns(lines, NETWORK_PATTERNS_PYTHON, 'P7a', 'MEDIUM', rel_path)
    findings += scan_patterns(lines, DYNAMIC_EXEC_PYTHON, 'P7b', 'HIGH', rel_path)
    findings += scan_patterns(lines, FILESYSTEM_PATTERNS, 'P7c', 'HIGH', rel_path)
    findings += scan_patterns(lines, OBFUSCATION_PATTERNS, 'P7d', 'HIGH', rel_path)
    findings += scan_patterns(lines, CREDENTIAL_PATTERNS, 'P7e',
                              'HIGH' if not strict else 'MEDIUM', rel_path)
    findings += scan_patterns(lines, PERSISTENCE_PATTERNS, 'P7f', 'HIGH', rel_path)
    findings += scan_patterns(lines, SHELL_INJECTION_PYTHON, 'P7g', 'HIGH', rel_path)
    return findings


def scan_shell_file(lines: list, rel_path: str, strict: bool) -> list:
    """Scan a shell script for P7 patterns."""
    findings = []
    findings += scan_patterns(lines, NETWORK_PATTERNS_SHELL, 'P7a', 'MEDIUM', rel_path)
    findings += scan_patterns(lines, DYNAMIC_EXEC_SHELL, 'P7b', 'HIGH', rel_path)
    findings += scan_patterns(lines, FILESYSTEM_PATTERNS, 'P7c', 'HIGH', rel_path)
    findings += scan_patterns(lines, PERSISTENCE_PATTERNS, 'P7f', 'HIGH', rel_path)
    return findings


def scan_js_file(lines: list, rel_path: str, strict: bool) -> list:
    """Scan a JavaScript/TypeScript file for P7 patterns."""
    findings = []
    findings += scan_patterns(lines, NETWORK_PATTERNS_JS, 'P7a', 'MEDIUM', rel_path)
    findings += scan_patterns(lines, DYNAMIC_EXEC_JS, 'P7b', 'HIGH', rel_path)
    findings += scan_patterns(lines, FILESYSTEM_PATTERNS, 'P7c', 'HIGH', rel_path)
    findings += scan_patterns(lines, OBFUSCATION_PATTERNS, 'P7d', 'HIGH', rel_path)
    return findings


def scan_for_steganography(lines: list, rel_path: str) -> list:
    """Scan any text file for P8c steganographic patterns."""
    findings = []
    findings += scan_patterns(lines, STEGANOGRAPHIC_PATTERNS, 'P8c', 'HIGH', rel_path)

    # Check for extremely long lines (>1000 chars) that might hide content
    for line_num, line in enumerate(lines):
        if len(line.rstrip()) > 1000:
            findings.append({
                'pattern': 'P8c',
                'file': rel_path,
                'line': line_num + 1,
                'text': f"[LINE LENGTH: {len(line.rstrip())} chars] {line.strip()[:100]}...",
                'context': f"    {line_num + 1}: [line too long to display — {len(line.rstrip())} characters]",
                'confidence': 'LOW',
                'explanation': f'Extremely long line ({len(line.rstrip())} chars) — could conceal hidden content',
            })

    return findings


def scan_for_polyglot(path: Path, lines: list, file_type: str, rel_path: str) -> list:
    """P7h: Check if file content matches its extension."""
    findings = []

    if file_type == 'text':
        # Check if a "text" file actually contains executable code
        content = '\n'.join(lines)
        executable_indicators = [
            (r'^#!/', 'shebang line'),
            (r'^\s*import\s+\w+', 'Python import statement'),
            (r'^\s*from\s+\w+\s+import\b', 'Python from-import statement'),
            (r'^\s*def\s+\w+\s*\(', 'Python function definition'),
            (r'^\s*class\s+\w+[\s(:]', 'Python class definition'),
            (r'^\s*function\s+\w+\s*\(', 'JavaScript function definition'),
            (r'^\s*const\s+\w+\s*=\s*\(.*\)\s*=>', 'JavaScript arrow function'),
        ]
        for regex, description in executable_indicators:
            if re.search(regex, content, re.MULTILINE):
                ext = path.suffix
                findings.append({
                    'pattern': 'P7h',
                    'file': rel_path,
                    'line': 0,
                    'text': f"File with {ext} extension contains: {description}",
                    'context': '',
                    'confidence': 'MEDIUM',
                    'explanation': f"File extension ({ext}) suggests data/documentation, but content contains {description}. "
                                   "Could be a polyglot file concealing executable content.",
                })
                break  # One finding per file is enough

    return findings


def check_for_binaries(skill_dir: Path) -> list:
    """Check for binary files that might be compiled executables."""
    findings = []
    for path in skill_dir.rglob('*'):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(skill_dir))

        # Skip known safe binary types
        if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp',
                                     '.ico', '.svg', '.woff', '.woff2',
                                     '.ttf', '.otf', '.eot'}:
            continue

        if not is_text_file(path):
            # It's a binary file
            if path.suffix.lower() in {'.so', '.dll', '.dylib', '.exe', '',
                                         '.bin', '.o', '.a', '.pyc', '.pyd'}:
                findings.append({
                    'pattern': 'P7h',
                    'file': rel_path,
                    'line': 0,
                    'text': f"Compiled binary: {path.name}",
                    'context': '',
                    'confidence': 'HIGH',
                    'explanation': "Compiled binary included in skill package. Users cannot audit "
                                   "what they cannot read. Binaries should be accompanied by source "
                                   "code or replaced with interpreted scripts.",
                })
            else:
                findings.append({
                    'pattern': 'P7h',
                    'file': rel_path,
                    'line': 0,
                    'text': f"Binary file with extension: {path.suffix}",
                    'context': '',
                    'confidence': 'MEDIUM',
                    'explanation': f"Non-text file with {path.suffix} extension. Verify this is a "
                                   "legitimate asset (image, font, etc.) and not concealed executable content.",
                })

    return findings


# --------------------------------------------------------------------------
# Confidence Adjustment
# --------------------------------------------------------------------------

def adjust_network_confidence(finding: dict, lines: list) -> dict:
    """Adjust network-related findings based on context.

    A skill that documents its network usage and uses it for its stated purpose
    is less suspicious than one with undocumented network calls.
    """
    # If the file has a docstring or comments explaining the network usage,
    # downgrade from MEDIUM to LOW
    full_text = '\n'.join(lines).lower()
    if finding['pattern'] == 'P7a':
        documented_keywords = ['api', 'download', 'fetch', 'install', 'pip',
                               'npm', 'requirements', 'dependency', 'dependencies']
        if any(kw in full_text for kw in documented_keywords):
            finding = dict(finding)  # copy
            if finding['confidence'] == 'MEDIUM':
                finding['confidence'] = 'LOW'
                finding['explanation'] += ' (downgraded: network usage appears documented/expected)'
    return finding


def adjust_env_confidence(finding: dict, lines: list) -> dict:
    """Adjust environment variable findings.

    os.environ access for PATH, HOME, LANG etc. is routine.
    Access to API_KEY, SECRET, TOKEN etc. stays HIGH.
    """
    if finding['pattern'] == 'P7e':
        line_text = finding['text'].upper()
        benign_vars = ['PATH', 'HOME', 'LANG', 'LC_', 'TERM', 'SHELL',
                       'USER', 'LOGNAME', 'DISPLAY', 'XDG_', 'TMPDIR',
                       'VIRTUAL_ENV', 'CONDA', 'PYTHONPATH', 'NODE_PATH']
        if any(var in line_text for var in benign_vars):
            finding = dict(finding)
            finding['confidence'] = 'LOW'
            finding['explanation'] += ' (downgraded: accessing benign environment variable)'
    return finding


# --------------------------------------------------------------------------
# Main Scanner
# --------------------------------------------------------------------------

def scan_skill(skill_dir: str, strict: bool = False) -> dict:
    """
    Scan a skill directory for P7 and P8c patterns.

    Returns a dict with:
    - findings: list of finding dicts
    - summary: counts by pattern and confidence
    - files_scanned: total files scanned
    - verdict: CLEAN / FINDINGS PRESENT / DO NOT INSTALL
    """
    skill_path = Path(skill_dir).resolve()

    if not skill_path.exists():
        return {'error': f'Directory not found: {skill_dir}'}
    if not skill_path.is_dir():
        return {'error': f'Not a directory: {skill_dir}'}

    all_findings = []
    files_scanned = 0

    # Check for binaries first
    all_findings += check_for_binaries(skill_path)

    # Scan each file
    for path in sorted(skill_path.rglob('*')):
        if not path.is_file():
            continue

        # Skip __pycache__, node_modules, .git
        rel_parts = path.relative_to(skill_path).parts
        if any(p in {'__pycache__', 'node_modules', '.git'} for p in rel_parts):
            continue

        rel_path = str(path.relative_to(skill_path))
        file_type = classify_file(path)

        if not is_text_file(path):
            continue  # binaries already handled above

        files_scanned += 1

        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except (IOError, OSError) as e:
            all_findings.append({
                'pattern': 'ERROR',
                'file': rel_path,
                'line': 0,
                'text': f'Could not read file: {e}',
                'context': '',
                'confidence': 'LOW',
                'explanation': 'File could not be read for scanning',
            })
            continue

        # Language-specific scanning
        if file_type == 'python':
            all_findings += scan_python_file(lines, rel_path, strict)
        elif file_type == 'shell':
            all_findings += scan_shell_file(lines, rel_path, strict)
        elif file_type == 'javascript':
            all_findings += scan_js_file(lines, rel_path, strict)

        # P8c steganography scan on ALL text files
        all_findings += scan_for_steganography(lines, rel_path)

        # P7h polyglot check
        all_findings += scan_for_polyglot(path, lines, file_type, rel_path)

    # Adjust confidence based on context
    adjusted = []
    for finding in all_findings:
        if finding['pattern'] == 'P7a':
            # Re-read file for context adjustment
            try:
                fpath = skill_path / finding['file']
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    file_lines = f.readlines()
                finding = adjust_network_confidence(finding, file_lines)
            except (IOError, OSError):
                pass
        elif finding['pattern'] == 'P7e':
            finding = adjust_env_confidence(finding, [])

        # Apply strictness filter
        if not strict and finding['confidence'] == 'LOW':
            continue  # gentle/standard modes skip LOW

        adjusted.append(finding)

    # Build summary
    summary = {}
    for f in adjusted:
        key = f['pattern']
        if key not in summary:
            summary[key] = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        summary[key][f['confidence']] += 1

    # Determine verdict
    has_high = any(f['confidence'] == 'HIGH' for f in adjusted)
    has_medium = any(f['confidence'] == 'MEDIUM' for f in adjusted)

    if has_high:
        verdict = 'DO NOT INSTALL'
    elif has_medium:
        verdict = 'FINDINGS PRESENT'
    else:
        verdict = 'CLEAN'

    return {
        'findings': adjusted,
        'summary': summary,
        'files_scanned': files_scanned,
        'verdict': verdict,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Static analysis scanner for skill package executable content.'
    )
    parser.add_argument('skill_dir', help='Path to the skill directory to scan')
    parser.add_argument('--strict', action='store_true',
                        help='Include LOW confidence findings')
    parser.add_argument('--json-output', '-o', default=None,
                        help='Write JSON output to this path (default: stdout)')

    args = parser.parse_args()

    result = scan_skill(args.skill_dir, strict=args.strict)

    output = json.dumps(result, indent=2)

    if args.json_output:
        with open(args.json_output, 'w') as f:
            f.write(output)
        print(f"Results written to {args.json_output}", file=sys.stderr)
        print(f"Verdict: {result.get('verdict', 'ERROR')}", file=sys.stderr)
        print(f"Findings: {len(result.get('findings', []))}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
