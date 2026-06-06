-- Paso 1: Crear la tabla Silver si no existe
CREATE TABLE IF NOT EXISTS `mci506-weather-pipeline.weather_pipeline.silver_weather`
(
  city                  STRING    NOT NULL,
  country               STRING    NOT NULL,
  latitude              FLOAT64   NOT NULL,
  longitude             FLOAT64   NOT NULL,
  time                  TIMESTAMP NOT NULL,
  temperature_2m        FLOAT64,
  apparent_temperature  FLOAT64,
  relative_humidity_2m  INT64,
  precipitation         FLOAT64,
  wind_speed_10m        FLOAT64,
  surface_pressure      FLOAT64,
  cloud_cover           INT64,
  extracted_at          TIMESTAMP,
  loaded_at             TIMESTAMP
);

-- Paso 2: Insertar solo registros nuevos (deduplicación incremental)
-- La llave natural es (city, time): cada ciudad tiene un valor por hora.
-- WHERE NOT EXISTS verifica que esa combinación no exista ya en Silver.
INSERT INTO `mci506-weather-pipeline.weather_pipeline.silver_weather`
(
  city, country, latitude, longitude, time,
  temperature_2m, apparent_temperature, relative_humidity_2m,
  precipitation, wind_speed_10m, surface_pressure, cloud_cover,
  extracted_at, loaded_at
)
SELECT
  city,
  country,
  latitude,
  longitude,
  TIMESTAMP(time)                   AS time,
  temperature_2m,
  apparent_temperature,
  relative_humidity_2m,
  precipitation,
  wind_speed_10m,
  surface_pressure,
  cloud_cover,
  extracted_at,
  CURRENT_TIMESTAMP()               AS loaded_at
FROM
  `mci506-weather-pipeline.weather_pipeline.bronze_weather_raw` AS bronze
WHERE
  -- Solo insertar si esta combinación ciudad-hora no existe ya en Silver
  NOT EXISTS (
    SELECT 1
    FROM `mci506-weather-pipeline.weather_pipeline.silver_weather` AS silver
    WHERE silver.city = bronze.city
      AND silver.time = TIMESTAMP(bronze.time)
  )
  -- Filtro de calidad: excluir filas sin ciudad o sin tiempo
  AND bronze.city IS NOT NULL
  AND bronze.time IS NOT NULL;
