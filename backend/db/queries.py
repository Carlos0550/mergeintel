"""Generic database query helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from backend.db.connection import get_session_factory


async def fetch_one(query: str, *args: Any) -> RowMapping | None:
    """Fetch a single row from the database.

    Args:
        query: SQL query string.
        *args: Query parameters.

    Returns:
        RowMapping | None: The first matching row, if any.
    """

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(text(_normalize_query(query)), _build_parameters(args))
        row = result.mappings().first()
    return row


async def fetch_all(query: str, *args: Any) -> list[RowMapping]:
    """Fetch multiple rows from the database.

    Args:
        query: SQL query string.
        *args: Query parameters.

    Returns:
        list[RowMapping]: All matching rows.
    """

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(text(_normalize_query(query)), _build_parameters(args))
        rows = result.mappings().all()
    return list(rows)


async def execute(query: str, *args: Any) -> str:
    """Execute a statement and return the asyncpg status string.

    Args:
        query: SQL statement string.
        *args: Statement parameters.

    Returns:
        str: SQL execution status.
    """

    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text(_normalize_query(query)), _build_parameters(args))
        await session.commit()
    return "OK"


async def execute_many(query: str, args_list: Sequence[Sequence[Any]]) -> None:
    """Execute the same statement for multiple parameter sets.

    Args:
        query: SQL statement string.
        args_list: Sequence of parameter sequences.
    """

    session_factory = get_session_factory()
    async with session_factory() as session:
        for args in args_list:
            await session.execute(text(_normalize_query(query)), _build_parameters(args))
        await session.commit()


def _build_parameters(args: Sequence[Any]) -> dict[str, Any]:
    """Convert positional parameters into a SQLAlchemy parameter mapping.

    Args:
        args: Positional SQL parameters.

    Returns:
        dict[str, Any]: Named SQL parameters mapping.
    """

    return {f"p{index}": value for index, value in enumerate(args, start=1)}


def _normalize_query(query: str) -> str:
    """Convert asyncpg-style placeholders into SQLAlchemy named parameters.

    Args:
        query: SQL query that may contain placeholders like ``$1`` or ``$2``.

    Returns:
        str: Query normalized for SQLAlchemy ``text`` execution.
    """

    return re.sub(r"\$(\d+)", r":p\1", query)
