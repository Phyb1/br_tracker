import sys
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# Add the project folder to path, not the parent
sys.path.insert(0, str(PROJECT_DIR))

# Activate venv
VENV = Path('/home/mathxuco/virtualenv/br_tracker/public_html/3.11')
activate_this = VENV / 'bin' / 'activate_this.py'
exec(open(activate_this).read(), {'__file__': str(activate_this)})

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'br_tracker.settings.prod')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
