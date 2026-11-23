"""Route package initializer that imports individual routers for FastAPI inclusion.

When `backend/app/main.py` does
```python
from .routes import documents, chat, analytics, comparison
```
this __init__ ensures each module is imported so the routers are available.
"""

from . import documents, chat, analytics, comparison
