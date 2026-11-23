"""Migration helpers for tenants2fast-fastapi."""

from alembic.operations import Operations


def add_soft_delete_columns(op: Operations, table_name: str) -> None:
    """Add deleted_at and deleted_by columns to a table.

    Args:
        op: Alembic operations object
        table_name: Name of the table to modify
    """
    import sqlalchemy as sa

    op.add_column(
        table_name,
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when the record was soft-deleted. None means active.',
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            'deleted_by',
            sa.UUID(),
            nullable=True,
            comment='ID of the user who soft-deleted this record.',
        ),
    )
    # Add index on deleted_at for efficient filtering
    op.create_index(
        f'ix_{table_name}_deleted_at',
        table_name,
        ['deleted_at'],
        unique=False,
    )
