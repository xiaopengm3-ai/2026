"""Disassemble Python 3.14 .pyc files to readable bytecode + extract constants/names."""
import dis
import marshal
import os
import sys

EXTRACTED = r"e:\claude code files\KemaoTributeMonitor.exe_extracted"
OUTPUT = r"e:\claude code files\KemaoTributeMonitor.exe_extracted\disasm"

# Key modules to decompile
TARGETS = [
    "main.pyc",
    "config.pyc",
    "database.pyc",
    "monitor.pyc",
    "debt_messages.pyc",
    "export.pyc",
    "afk_detector.pyc",
    "i18n.pyc",
    "startup.pyc",
]

os.makedirs(OUTPUT, exist_ok=True)

def load_pyc(path):
    """Load a Python 3.14 .pyc file and return its code object."""
    with open(path, "rb") as f:
        # Python 3.14 pyc header: 16 bytes (4 magic + 4 flags + 4 timestamp + 4 size)
        # But actually in 3.14 the header might be different. Let's detect it.
        magic = f.read(4)
        header_rest = f.read(12)  # flags + timestamp + code size
        # The rest is the marshalled code object
        try:
            return marshal.load(f)
        except Exception as e:
            print(f"  ERROR loading {path}: {e}")
            return None

def extract_info(code, indent=0):
    """Extract key information from a code object."""
    prefix = "  " * indent
    lines = []
    lines.append(f"{prefix}=== Code: {code.co_name} ===")
    lines.append(f"{prefix}File: {code.co_filename}")
    lines.append(f"{prefix}Args: {code.co_varnames[:code.co_argcount]}")
    lines.append(f"{prefix}Locals: {list(code.co_varnames)}")
    lines.append(f"{prefix}Constants: {len(code.co_consts)} items")
    for i, c in enumerate(code.co_consts):
        if isinstance(c, str) and len(c) > 5:
            lines.append(f"{prefix}  [{i}] str({len(c)}): {repr(c[:120])}")
        elif isinstance(c, (int, float)):
            lines.append(f"{prefix}  [{i}] num: {c}")
        elif isinstance(c, type(None)):
            pass  # skip None
        elif isinstance(c, type):  # code objects
            lines.append(f"{prefix}  [{i}] CODE: {c.co_name}")
        elif isinstance(c, tuple) and len(c) < 10:
            lines.append(f"{prefix}  [{i}] tuple: {c}")
        else:
            lines.append(f"{prefix}  [{i}] {type(c).__name__}: {repr(c)[:80]}")
    lines.append(f"{prefix}Names: {list(code.co_names)}")

    # Recurse into nested code objects
    for c in code.co_consts:
        if isinstance(c, type) and hasattr(c, "co_code"):  # code type
            lines.append("")
            lines.extend(extract_info(c, indent + 1))

    return lines

print("=" * 60)
print("Disassembling KemaoTributeMonitor .pyc files (Python 3.14)")
print("=" * 60)

for target in TARGETS:
    path = os.path.join(EXTRACTED, target)
    if not os.path.exists(path):
        print(f"\nSKIP {target} (not found)")
        continue

    print(f"\n{'='*60}")
    print(f"FILE: {target}")
    print(f"{'='*60}")

    code = load_pyc(path)
    if code is None:
        continue

    # Extract high-level info
    info = extract_info(code)

    # Full disassembly
    out_path = os.path.join(OUTPUT, target.replace(".pyc", ".dis"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Disassembly of {target}\n\n")
        f.write("## Structure\n\n")
        for line in info:
            f.write(line + "\n")

        f.write("\n\n## Full Bytecode\n\n")
        # Capture dis output
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            dis.dis(code)
            full_dis = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        f.write(full_dis)

    print(f"  -> {out_path}")
    print(f"  Constants: {len([c for c in code.co_consts if isinstance(c, str) and len(c) > 5])} strings")
    print(f"  Nested functions/classes: {len([c for c in code.co_consts if isinstance(c, type) and hasattr(c, 'co_code')])}")

    # Also print key strings directly to console
    all_strings = []
    def collect_strings(co):
        for const in co.co_consts:
            if isinstance(const, str) and len(const) > 3:
                all_strings.append(const)
            elif isinstance(const, type) and hasattr(const, "co_code"):
                collect_strings(const)
    collect_strings(code)

    print(f"  Key strings ({len(all_strings)} total):")
    for s in all_strings[:30]:
        print(f"    {repr(s)[:130]}")
    if len(all_strings) > 30:
        print(f"    ... and {len(all_strings) - 30} more")

print(f"\n\nDone! Full disassembly saved to: {OUTPUT}")
