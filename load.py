from __future__ import annotations

import logging
import os
from pathlib import Path

from google.cloud import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("load")


def upload_file(client: storage.Client, bucket_name: str, local_path: Path, gcs_path: str) -> None:
    """Sube un archivo local a GCS.

    Args:
        client: cliente autenticado de Google Cloud Storage.
        bucket_name: nombre del bucket de destino.
        local_path: ruta local del archivo a subir.
        gcs_path: ruta de destino dentro del bucket.
    """
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(str(local_path))
    logger.info("Subido: %s -> gs://%s/%s", local_path.name, bucket_name, gcs_path)


def get_pending_files(output_dir: str) -> list[Path]:
    """Busca todos los archivos NDJSON en la carpeta de salida local.

    Args:
        output_dir: carpeta raíz donde extract.py guarda los archivos.

    Returns:
        Lista de rutas de archivos NDJSON encontrados.
    """
    base = Path(output_dir)
    if not base.exists():
        logger.warning("La carpeta de salida no existe: %s", output_dir)
        return []
    files = list(base.rglob("*.ndjson"))
    logger.info("Archivos NDJSON encontrados: %d", len(files))
    return files


def main() -> None:
    """Orquesta la carga: busca los NDJSON locales y los sube a GCS."""
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise SystemExit("ERROR: La variable GCS_BUCKET_NAME no está definida.")

    output_dir = os.getenv("OUTPUT_DIR", "./output")

    files = get_pending_files(output_dir)
    if not files:
        raise SystemExit("No se encontraron archivos NDJSON para subir. Ejecuta extract.py primero.")

    client = storage.Client()
    uploaded = 0
    errors = 0

    for local_path in files:
        try:
            # Mantener la misma estructura de carpetas en GCS
            # Ej: output/weather/extracted_date=2026-06-06/weather_xxx.ndjson
            #  -> weather/extracted_date=2026-06-06/weather_xxx.ndjson
            relative = local_path.relative_to(output_dir)
            gcs_path = str(relative).replace("\\", "/")  # compatibilidad Windows

            upload_file(client, bucket_name, local_path, gcs_path)
            uploaded += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.error("Error al subir %s: %s", local_path.name, exc)

    logger.info(
        "Carga completada: %d archivos subidos, %d con error.",
        uploaded, errors,
    )
    if errors > 0:
        raise SystemExit(f"Hubo {errors} error(es) durante la carga.")


if __name__ == "__main__":
    main()
