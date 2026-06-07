from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #

API_URL = "https://api.open-meteo.com/v1/forecast"

# Variables horarias que pedimos a la API. Cada una se convierte en una columna.
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "wind_speed_10m",
    "surface_pressure",
    "cloud_cover",
]

# Ciudades a monitorear. (nombre, país, latitud, longitud)
CITIES: list[dict[str, Any]] = [
    {"city": "La Paz", "country": "BO", "latitude": -16.50, "longitude": -68.15},
    {"city": "Santa Cruz", "country": "BO", "latitude": -17.78, "longitude": -63.18},
    {"city": "Cochabamba", "country": "BO", "latitude": -17.39, "longitude": -66.16},
    {"city": "Buenos Aires", "country": "AR", "latitude": -34.61, "longitude": -58.38},
    {"city": "Lima", "country": "PE", "latitude": -12.05, "longitude": -77.04},
    {"city": "Santiago", "country": "CL", "latitude": -33.45, "longitude": -70.67},
    {"city": "Bogota", "country": "CO", "latitude": 4.71, "longitude": -74.07},
    {"city": "Madrid", "country": "ES", "latitude": 40.42, "longitude": -3.70},
    # Ciudades agregadas por el equipo
    {"city": "Quito", "country": "EC", "latitude": -0.22, "longitude": -78.52},
    {"city": "Asuncion", "country": "PY", "latitude": -25.28, "longitude": -57.63},
    {"city": "Montevideo", "country": "UY", "latitude": -34.90, "longitude": -56.16},
]

REQUEST_TIMEOUT = 30          # segundos
MAX_RETRIES = 5               # reintentos por ciudad ante fallos transitorios
RETRY_BACKOFF = 2             # segundos base para el backoff exponencial

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("extract")


# --------------------------------------------------------------------------- #
# Funciones
# --------------------------------------------------------------------------- #

def fetch_city(
    session: requests.Session,
    city: dict[str, Any],
    past_days: int,
    forecast_days: int,
) -> dict[str, Any]:
    """Llama a la API de Open-Meteo para una ciudad y devuelve el JSON crudo.

    Usa una sesión HTTP compartida para reutilizar la conexión entre ciudades.
    Reintenta ante errores de red o respuestas 5xx usando backoff exponencial.

    Args:
        session: sesión HTTP reutilizable de requests.
        city: diccionario con claves city, country, latitude, longitude.
        past_days: cuántos días hacia atrás incluir.
        forecast_days: cuántos días de pronóstico incluir.

    Returns:
        El cuerpo JSON de la respuesta como diccionario.

    Raises:
        requests.RequestException: si todos los reintentos fallan.
    """
    params = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
        "past_days": past_days,
        "forecast_days": forecast_days,
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("error"):
                raise ValueError(f"La API devolvió un error: {payload.get('reason')}")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait = RETRY_BACKOFF * attempt
            logger.warning(
                "Fallo al consultar %s (intento %d/%d): %s. Reintentando en %ds...",
                city["city"], attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    raise requests.RequestException(
        f"No se pudo obtener datos de {city['city']} tras {MAX_RETRIES} intentos"
    ) from last_error


def parse_hourly_response(
    payload: dict[str, Any],
    city: dict[str, Any],
    extracted_at: str,
) -> list[dict[str, Any]]:
    """Aplana la respuesta horaria de la API en una lista de filas.

    Open-Meteo devuelve los datos en arrays paralelos (un array por variable,
    todos alineados con el array de tiempos). Aquí los combinamos en una fila
    por cada hora.

    Args:
        payload: JSON devuelto por la API.
        city: metadatos de la ciudad (city, country, latitude, longitude).
        extracted_at: timestamp ISO de la extracción, igual para todas las filas.

    Returns:
        Lista de diccionarios, uno por cada hora disponible.
    """
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])

    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(times):
        row: dict[str, Any] = {
            "city": city["city"],
            "country": city["country"],
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "time": ts,
            "extracted_at": extracted_at,
        }
        for var in HOURLY_VARIABLES:
            values = hourly.get(var, [])
            row[var] = values[i] if i < len(values) else None
        rows.append(row)
    return rows


def write_ndjson(rows: list[dict[str, Any]], output_dir: str, run_ts: datetime) -> Path:
    """Escribe las filas en un archivo NDJSON particionado por fecha.

    La ruta sigue el patrón weather/extracted_date=YYYY-MM-DD/weather_<ts>.ndjson,
    pensada para mapear directo a un layout particionado en GCS.

    Args:
        rows: filas a escribir.
        output_dir: carpeta base de salida.
        run_ts: timestamp de la corrida (define la partición y el nombre).

    Returns:
        Ruta del archivo escrito.
    """
    partition = run_ts.strftime("%Y-%m-%d")
    file_ts = run_ts.strftime("%Y%m%dT%H%M%SZ")
    target_dir = Path(output_dir) / "weather" / f"extracted_date={partition}"
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / f"weather_{file_ts}.ndjson"
    with target_file.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return target_file


def main() -> None:
    """Orquesta la extracción de datos climatológicos.

    1. Lee variables de entorno para configuración.
    2. Abre una sesión HTTP optimizada para reutilizar la conexión.
    3. Recorre las ciudades configuradas y extrae sus datos.
    4. Aplana la respuesta y la guarda particionada en formato NDJSON.

    Raises:
        SystemExit: si la extracción falla para absolutamente todas las ciudades.
    """
    output_dir = os.getenv("OUTPUT_DIR", "./output")
    past_days = int(os.getenv("PAST_DAYS", "2"))
    forecast_days = int(os.getenv("FORECAST_DAYS", "1"))

    run_ts = datetime.now(timezone.utc)
    extracted_at = run_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    all_rows: list[dict[str, Any]] = []
    failures = 0

    # Sesión HTTP única para todas las peticiones — más eficiente que abrir
    # una conexión nueva por cada ciudad
    with requests.Session() as session:
        for city in CITIES:
            try:
                payload = fetch_city(session, city, past_days, forecast_days)
                rows = parse_hourly_response(payload, city, extracted_at)
                all_rows.extend(rows)
                logger.info("OK %-14s -> %d filas", city["city"], len(rows))
            except Exception as exc:  # noqa: BLE001 - queremos seguir con las demás ciudades
                failures += 1
                logger.error("Se omite %s por error: %s", city["city"], exc)

    if not all_rows:
        raise SystemExit("No se extrajo ninguna fila. Abortando.")

    output_path = write_ndjson(all_rows, output_dir, run_ts)
    logger.info(
        "Listo: %d filas de %d ciudades (%d con error) -> %s",
        len(all_rows), len(CITIES) - failures, failures, output_path,
    )


if __name__ == "__main__":
    main()
