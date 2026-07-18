"""Dependencies shared by every route.

`CurrentUser` is the one that matters: annotate a route argument with it and
FastAPI verifies the caller's Firebase token before the handler runs, handing
it the user's uid. Anything not annotated with it is public.
"""
from typing import Annotated

from fastapi import Depends

from app.core.security import current_user

# Sign-in required; the value is the caller's Firebase uid.
CurrentUser = Annotated[str, Depends(current_user)]
