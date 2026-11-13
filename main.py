import io
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import MovieDataResponse, MovieStorage, MovieCache,  HealthResponse, setup_logging, MovieProcessingReport, ProcessConfig, log_requests, MovieUploadInfo
from src.storage import MOVIE_COLUMNS
from data_pipeline import create_cleaning_report, process_data, validate_dataframe

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()
cache = MovieCache()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": app.version}

@app.post("/upload", response_model= MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read a CSV upload and replace stored movie collection."""
    extension = Path(file.filename or "").suffix.lower()
    if extension != ".csv":
        logger.warning("Unsupported file format: %s", extension)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: '{extension}'. Only .csv files are accepted.",
        )
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError:
        logger.warning("Empty CSV upload: %s", file.filename)
        raise HTTPException(status_code=400, detail="The uploaded CSV file is empty.")
    except pd.errors.ParserError:
        logger.warning("Could not parse CSV upload: %s", file.filename)
        raise HTTPException(
            status_code=400,
            detail="The uploaded file could not be parsed as CSV. Check its formatting.",
        )
    except UnicodeDecodeError:
        logger.warning("Could not decode CSV upload: %s", file.filename)
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not valid UTF-8 text. Save it as a UTF-8 CSV.",
        )
    if set(df.columns) != set(MOVIE_COLUMNS):
        logger.warning("Invalid movie columns: %s", list(df.columns))
        raise HTTPException(
            status_code=400,
            detail=f"The CSV must have exactly these columns: {MOVIE_COLUMNS}",
        )
    if df.empty:
        logger.warning("No data rows in upload: %s", file.filename)
        raise HTTPException(status_code=400, detail="The uploaded CSV has no data rows.")

    df = df[MOVIE_COLUMNS]

    storage.save(df)
    cache.invalidate()
    logger.info("Uploaded movies: filename=%s, rows=%d", file.filename, len(df))
    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }

@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit stored movies and the total movie count."""
    cached = cache.get(limit)
    if cached is not None:
        logger.info("Returned cached movies: limit=%d", limit)
        return cached

    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    response = {"data": data, "total_rows": total_rows}

    cache.set(limit, response)
    logger.info("Retrieved movies: returned_rows=%d", len(data))
    return response


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    """Return id plus the selected fields for movies at or above min_rating."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        logger.warning("Invalid movie query: %s", error)
        raise HTTPException(status_code=400, detail=str(error))

    logger.info(
        "Queried movies: columns=%s, min_rating=%s, returned_rows=%d",
        columns, min_rating, len(results),
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and process the stored movies using MP1 functions."""
    df = storage.get()
    if df.empty:
        logger.warning("No movies to process")
        raise HTTPException(status_code=400, detail="No movies are stored. Upload a CSV first.")

    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing_numeric = [col for col in numeric_columns if col not in df.columns]
    if missing_numeric:
        logger.warning("Numeric columns not found: %s", missing_numeric)
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {missing_numeric}",
        )

    try:
        rows_before_validation = len(df)
        validated = validate_dataframe(df, required_columns, numeric_columns)
        validation_rows_removed = rows_before_validation - len(validated)
        logger.info(
            "Validated movies: rows_before=%d, rows_after=%d",
            rows_before_validation, len(validated),
        )
        validated_copy = validated.copy()
        processed = process_data(validated, config_dict)
    except ValueError as error:
        logger.warning("Processing failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error))

    report = create_cleaning_report(validated_copy, processed)

    storage.save(processed)
    cache.invalidate()
    logger.info(
        "Processed movies: validation_removed=%d, rows_before=%d, rows_after=%d",
        validation_rows_removed, report["rows_before"], report["rows_after"],
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": report,
    }