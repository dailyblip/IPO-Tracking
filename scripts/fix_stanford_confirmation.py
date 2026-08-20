from pathlib import Path
p=Path('src/main.py')
s=p.read_text(encoding='utf-8')
old='''                "Stanford Affiliation Confirmed": bool(stanford_university_in_bio or stanford_result.get("grade") in (1, "1", "Confirmed", "confirmed", True)),\n'''
new='''                "Stanford Affiliation Confirmed": bool(stanford_university_in_bio or stanford_result.get("grade") in (5, "5")),\n'''
if old in s:
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

p=Path('src/test_main.py')
s=p.read_text(encoding='utf-8')
if 'test_stanford_confirmation_requires_grade_five' not in s:
    s += '''\n\nclass StanfordConfirmationThresholdTests(unittest.TestCase):\n    def test_stanford_confirmation_requires_grade_five(self):\n        from pathlib import Path\n        source=Path(__file__).with_name("main.py").read_text(encoding="utf-8")\n        self.assertIn('stanford_result.get("grade") in (5, "5")', source)\n        self.assertNotIn('stanford_result.get("grade") in (1, "1"', source)\n'''
p.write_text(s,encoding='utf-8')
