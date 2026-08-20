from pathlib import Path

p = Path('src/lockup_parser.py')
s = p.read_text(encoding='utf-8')
old = '''    has_lockup_label = "lock-up" in lowered or "lockup" in lowered or "market standoff" in lowered\n    return has_holder_restriction and has_lockup_label\n'''
new = '''    has_lockup_label = "lock-up" in lowered or "lockup" in lowered or "market standoff" in lowered\n    # Explicit holder agreements not to sell/transfer are lock-ups in substance even\n    # when the section heading is in the preceding sentence. Staggered-release clauses\n    # can describe the release schedule without repeating "will not sell."\n    if has_holder_restriction:\n        return True\n    if has_lockup_label and re.search(r"staggered|early\s+lock-?up\s+release|lock-?up\s+release", lowered):\n        return True\n    return False\n'''
if old in s:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
