from pathlib import Path
p = Path('scripts/apply_spacex_calibration.py')
s = p.read_text(encoding='utf-8')
s = s.replace(':false', ':False').replace(':true', ':True').replace(':null', ':None')
p.write_text(s, encoding='utf-8')
