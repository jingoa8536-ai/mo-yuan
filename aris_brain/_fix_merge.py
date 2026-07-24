"""Fix corrupted tool_dispatch_helpers.py - remove duplicate content and fix merge artifacts."""
path = "C:/Users/user/AppData/Local/hermes/hermes-agent/agent/tool_dispatch_helpers.py"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the correct boundary: the __all__ list ends with "make_tool_result_message",\n]
# The first occurrence is at around line 447-448
# But patch tool corrupted line 448 to now be: ] — parallelism gating...
# So we need to find "make_tool_result_message" and take everything up to its closing ]

# Strategy: tokenize to find proper closing ]
# Simpler: just find the first "make_tool_result_message" and find its closing ]
marker = '"make_tool_result_message",'
idx = content.find(marker)
if idx == -1:
    print("ERROR: Cannot find marker")
    exit(1)

# Find the closing ] after this marker
idx_close = content.find(']', idx + len(marker))
if idx_close == -1:
    print("ERROR: Cannot find closing ]")
    exit(1)

# Truncate right after the ]
cleaned = content[:idx_close+1] + '\n'

# Also clean all trailing whitespace lines
while cleaned.endswith('\n\n\n'):
    cleaned = cleaned.rstrip('\n') + '\n'

# Remove any remaining conflict markers
import re
cleaned = re.sub(r'^<<<<<<< .*\n', '', cleaned, flags=re.MULTILINE)
cleaned = re.sub(r'\n=======\n', '\n', cleaned)
cleaned = re.sub(r'^>>>>>>> .*\n', '', cleaned, flags=re.MULTILINE)

# Strip trailing whitespace
cleaned = cleaned.rstrip() + '\n'

# Verify syntax
try:
    compile(cleaned, path, 'exec')
    print(f"Syntax check: PASS")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    lines_c = cleaned.split('\n')
    err_line = e.lineno if e.lineno else 0
    for i in range(max(0, err_line-3), min(len(lines_c), err_line+3)):
        prefix = ">>>" if i+1 == err_line else "   "
        print(f"{prefix} L{i+1}: {lines_c[i][:100]}")
    exit(1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(cleaned)

print(f"Fixed: {len(content)} bytes -> {len(cleaned)} bytes")
print(f"Removed {len(content) - len(cleaned)} bytes of duplicate content")
print("Done!")
