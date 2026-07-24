import re
content = open(r'D:\LAAP\subset_results.xml', encoding='utf-8').read()
matches = re.findall(r'classname="(tests\.[^"]+)"', content)
seen = set()
files = []
for m in matches:
    if m not in seen:
        seen.add(m)
        files.append(m)
print("\n".join(files))
