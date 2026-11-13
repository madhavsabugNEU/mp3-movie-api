# MP3: Movie API with SQLite Storage and Caching

This project is a FastAPI application that stores one movie collection in a SQLite database and serves it through a REST API. `POST /upload` accepts a CSV with exactly the columns `title`, `release_year`, `rating`, and `genre`, and replaces the stored collection in a single transaction. `src/database.py` creates database connections and the `movies` table, while `src/storage.py` (`MovieStorage`) saves, retrieves, counts, and filters movies with SQL, so the data persists after the server restarts. `GET /movies` returns up to `limit` movies with the total count, and `GET /movies/search` filters by minimum rating with SQL, sorted by rating from highest to lowest. `POST /movies/process` reuses the MP1 validation and cleaning modules in `data_pipeline/` to remove duplicates, missing values, and outliers, then saves the cleaned collection back to SQLite. `src/cache.py` (`MovieCache`) caches `GET /movies` responses in FakeRedis for 90 seconds, one entry per `limit`. Every successful upload or processing run clears the cache, so retrievals never return outdated movies. Middleware in `src/middleware.py` gives each request an ID and logs its method, path, status code, and duration.

## Commands

Start the API, then open http://127.0.0.1:8000/docs:

```bash
python -m uvicorn main:app --reload
```

Run the tests:

```bash
python -m pytest tests -v
```

## Sample processing request

After uploading `fixtures/sample_movies.csv`, send this body to `POST /movies/process`:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {"enabled": true, "columns": ["rating"], "method": "iqr", "threshold": 1.5}
  }
}
```

Expected result:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```