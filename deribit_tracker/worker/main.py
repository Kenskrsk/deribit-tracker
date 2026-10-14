"""Entry point for the Celery CLI: `celery -A deribit_tracker.worker.main worker|beat`.

The Celery CLI can only load an app object from a module attribute (it does not call
factories), so this is the one deliberate module-level object in the project.
"""

from deribit_tracker.config import Settings
from deribit_tracker.worker.celery_app import create_celery_app

app = create_celery_app(Settings())
