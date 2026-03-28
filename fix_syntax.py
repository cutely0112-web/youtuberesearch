# -*- coding: utf-8 -*-
import codecs

# Read the file
with codecs.open('youtubereserch.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 94 (index 93)
if len(lines) > 93:
    # Replace the problematic line
    lines[93] = "            if d.get('status') == 'final_error': error_msg = '오류 발생: ' + str(d.get('error', '')); yield f\"data: {json.dumps({'status': 'error', 'message': error_msg})}\\n\\n\"; break\n"

# Write back
with codecs.open('youtubereserch.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed!")
