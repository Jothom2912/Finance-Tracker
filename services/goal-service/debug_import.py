import sys
import os
from pathlib import Path

print('PYTHONPATH env:', os.environ.get('PYTHONPATH'))
print('cwd:', Path.cwd())
print('sys.path[0]:', sys.path[0])
print('first sys.path entries:')
for p in sys.path[:8]:
    print(' -', p)

try:
    import app.database as db
    print('import app.database OK')
except Exception as e:
    print('import app.database FAILED:', type(e).__name__, e)
