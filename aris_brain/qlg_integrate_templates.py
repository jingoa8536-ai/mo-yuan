"""
Aris QLG Template Integrator
Integrates the 76 auto-generated templates into qlg_generator.py
"""

import logging
logger = logging.getLogger(__name__)

import json, os, sys

# Read auto-generated templates
auto_path = os.path.join(os.path.dirname(__file__) or '.', 'state', 'auto_templates.py')
with open(auto_path, 'r') as f:
    auto_code = f.read()

# Read current qlg_generator.py
gen_path = os.path.join(os.path.dirname(__file__) or '.', 'qlg_generator.py')
with open(gen_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the TEMPLATES section
start_marker = "# The generator picks templates based on query similarity\nTEMPLATES = ["
end_marker = "\n\n# ───── Slot Value Banks ─────"

# Find start
start_idx = content.find(start_marker)
if start_idx < 0:
    start_marker = "# The generator picks templates based on query similarity\nTEMPLATES = ["
    start_idx = content.find(start_marker)

# Find end
end_idx = content.find(end_marker, start_idx)
if end_idx < 0:
    end_marker = "\n# ───── Slot Value Banks ─────"
    end_idx = content.find(end_marker, start_idx)

if start_idx >= 0 and end_idx > start_idx:
    # Extract the auto templates from the generated code
    auto_templates_start = auto_code.find("[")
    auto_templates_end = auto_code.rfind("]") + 1
    if auto_templates_start >= 0:
        auto_templates_str = auto_code[auto_templates_start:auto_templates_end]
        
        # The auto templates use "auto" tags, but we need to map them to semantic categories
        # For now, just use "auto" and fix selection later
        new_templates = auto_templates_str
        
        # Replace old templates
        old_templates = content[start_idx:end_idx]
        # Keep the header line
        header_line = "# The generator picks templates based on query similarity\nTEMPLATES = [\n"
        
        new_section = header_line + new_templates[1:]  # Skip the first [
        content = content[:start_idx] + new_section + content[end_idx:]
        
        with open(gen_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✅ Integrated auto templates! {old_templates.count('(')} → {auto_templates_str.count('(')} templates")
    else:
        logger.info("❌ Could not find template list in auto_templates.py")
else:
    print(f"❌ Could not find TEMPLATES section start={start_idx} end={end_idx}")
    logger.info(f"  Start marker found: {start_marker[:40] in content}")