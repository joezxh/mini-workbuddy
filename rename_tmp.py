"""一次性脚本：将 mediation 模块重命名为 duplex。"""
import os
import shutil
import subprocess

ROOT = r"d:\projects\MinWorkBuddy"
ROOTS = [
    os.path.join(ROOT, "backend"),
    os.path.join(ROOT, "frontend", "src"),
    os.path.join(ROOT, "docs", "sql"),
]
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
}
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".egg-info")
TEXT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".sql", ".json", ".md",
    ".html", ".cfg", ".ini", ".toml", ".txt", ".yaml", ".yml",
}


def safe_rename(old, new):
    """跨平台重命名，失败时回退到 PowerShell Rename-Item。"""
    if os.path.exists(new):
        return False
    try:
        os.rename(old, new)
        return True
    except (PermissionError, OSError):
        pass
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"Rename-Item -Path '{old}' -NewName '{os.path.basename(new)}' -Force",
            ],
            check=True, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print("RENAME FAILED:", old, "->", new, e.stderr.decode(errors="ignore"))
        return False


def should_skip(path_parts):
    return any(p in EXCLUDE_DIRS for p in path_parts)


def rename_token(s: str) -> str:
    return s.replace("Mediation", "Duplex").replace("mediation", "duplex")


renamed_dirs = []
renamed_files = []
changed_files = []

all_dirs = []
for root in ROOTS:
    for dirpath, dirnames, _ in os.walk(root):
        if should_skip(dirpath.split(os.sep)):
            continue
        if "mediation" in dirpath.lower():
            all_dirs.append(dirpath)
all_dirs.sort(key=lambda p: len(p), reverse=True)
for d in all_dirs:
    parent, name = os.path.split(d)
    new_name = rename_token(name)
    if new_name != name:
        new_path = os.path.join(parent, new_name)
        if safe_rename(d, new_path):
            renamed_dirs.append((d, new_path))

for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        if should_skip(dirpath.split(os.sep)):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            continue
        for fn in filenames:
            if fn.endswith(EXCLUDE_SUFFIXES):
                continue
            if "mediation" in fn.lower():
                new_fn = rename_token(fn)
                if new_fn != fn:
                    old = os.path.join(dirpath, fn)
                    new = os.path.join(dirpath, new_fn)
                    if safe_rename(old, new):
                        renamed_files.append((old, new))

for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        if should_skip(dirpath.split(os.sep)):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            continue
        for fn in filenames:
            if fn.endswith(EXCLUDE_SUFFIXES):
                continue
            _, ext = os.path.splitext(fn)
            if ext not in TEXT_EXTS:
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            new = data.replace("Mediation", "Duplex").replace("mediation", "duplex")
            if new != data:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(new)
                changed_files.append(fp)

for root in [os.path.join(ROOT, "backend")]:
    for dirpath, dirnames, filenames in os.walk(root):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
        for fn in filenames:
            if fn.endswith(".pyc"):
                try:
                    os.remove(os.path.join(dirpath, fn))
                except OSError:
                    pass

print(f"Renamed dirs : {len(renamed_dirs)}")
for o, n in renamed_dirs:
    print("  DIR", os.path.relpath(o, ROOT), "->", os.path.relpath(n, ROOT))
print(f"Renamed files: {len(renamed_files)}")
for o, n in renamed_files:
    print("  FIL", os.path.relpath(o, ROOT), "->", os.path.relpath(n, ROOT))
print(f"Changed files: {len(changed_files)}")
