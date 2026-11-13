from pathlib import Path

import pandas as pd
import pytest

from src import MovieStorage
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    other_storage = MovieStorage(test_storage.db_path)

    movies = other_storage.get()
    assert len(movies) == 20
    assert other_storage.count_movies() == 20
    assert list(movies.columns) == ["title", "release_year", "rating", "genre"]

    original_titles = pd.read_csv(Path("fixtures") / "sample_movies.csv")["title"].tolist()
    assert movies["title"].tolist() == original_titles

    storage_ids = [row["id"] for row in other_storage.select_columns(["title"], limit=100)]
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [record["id"] for record in response.json()["data"]]

    assert storage_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    first_responses = {}
    for limit in (100, 1):
        response = client.get("/movies", params={"limit": limit})
        assert response.status_code == 200
        assert main.cache.get(limit) == response.json()
        first_responses[limit] = response.json()

    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    assert response.json() == first_responses[100]

    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 200
    body = response.json()
    assert body["validation_rows_removed"] == 0
    assert body["cleaning_report"] == {
        "rows_before": 20,
        "rows_after": 16,
        "rows_removed": 4,
        "columns_before": 4,
        "columns_after": 4,
        "columns_removed": 0,
    }
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 16
    titles = [record["title"] for record in body["data"]]
    assert titles == [f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"]
    ids = [record["id"] for record in body["data"]]
    assert ids == list(range(1, 17))
    assert main.cache.get(100) == body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    def fail_if_called(*args, **kwargs):
        pytest.fail("The database should not be used on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()