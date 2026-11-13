import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        movies = df.reindex(columns=MOVIE_COLUMNS).astype(object)
        movies = movies.where(movies.notna(), None)
        rows = movies.values.tolist()

        connection = get_connection(self.db_path)
        try:
            connection.execute("DELETE FROM movies")
            connection.executemany(
                "INSERT INTO movies (title, release_year, rating, genre) VALUES (?, ?, ?, ?)",
                rows,
            )
            connection.commit()
            logger.debug("Stored movies in SQLite: rows=%d", len(rows))
        except sqlite3.Error:
            connection.rollback()
            logger.error("Failed to store movies; changes rolled back")
            raise
        finally:
            connection.close()

    def get(self):
        """Return the four movie columns as a DataFrame, ordered by id."""
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                "SELECT title, release_year, rating, genre FROM movies ORDER BY id"
            ).fetchall()
            logger.debug("Retrieved movies from SQLite: rows=%d", len(rows))
            return pd.DataFrame([tuple(row) for row in rows], columns=MOVIE_COLUMNS)
        finally:
            connection.close()

    def select_columns(self, columns, limit=5):
        """Return id plus the requested movie columns, ordered by id."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT {selected_columns} FROM movies ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
            records = [dict(row) for row in rows]
            logger.debug("Selected movie columns: columns=%s, rows=%d", columns, len(records))
            return records
        finally:
            connection.close()

    def count_movies(self):
        """Return the number of stored movies using SQL COUNT(*)."""
        connection = get_connection(self.db_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
            logger.debug("Counted movies: total=%d", count)
            return count
        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        """Return selected fields from matching movies using SQL."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT {selected_columns} FROM movies "
                "WHERE rating >= ? ORDER BY rating DESC, id ASC LIMIT ?",
                (min_rating, limit),
            ).fetchall()
            records = [dict(row) for row in rows]
            logger.debug("Queried movies: columns=%s, rows=%d", columns, len(records))
            return records
        finally:
            connection.close()