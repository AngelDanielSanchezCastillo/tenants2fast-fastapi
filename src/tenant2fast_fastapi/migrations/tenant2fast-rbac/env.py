"""Thin env shim for the tenant2fast-rbac chain: dispatch to the shared async env.

The heavy lifting lives in ``pgsqlasync2fast_fastapi.migrations.env``
(design D1 of the ``alembic-2fast`` change): fresh ``NullPool`` async engine
per run, disposed after the run, ``version_table`` passed EXPLICITLY to
``context.configure``, and the ownership filters that keep autogenerate
scoped to this chain's tables. Alembic fixes ``env_py_location`` at
``<script_location>/env.py``, so each chain directory ships only this
~12-line dispatch shim.
"""

from alembic import context
from pgsqlasync2fast_fastapi.migrations import (
    run_migrations_offline,
    run_migrations_online,
)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()