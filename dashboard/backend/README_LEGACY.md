# Legacy Dashboard Backend

`dashboard/backend/` is a compatibility surface from an older dashboard stack.

The canonical dashboard service is:

- `services/dashd/api.py`

If you are making new dashboard changes, prefer the canonical service and the frontend under:

- `dashboard/frontend/`

This folder should be treated as legacy until it is either archived or removed in a dedicated cleanup pass.
