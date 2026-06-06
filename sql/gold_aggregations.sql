CREATE OR REPLACE TABLE `mci506-weather-pipeline.weather_pipeline.gold_weather_daily`
AS
SELECT
  city,
  country,
  latitude,
  longitude,
  DATE(time)                        AS fecha,

  -- Temperatura
  ROUND(AVG(temperature_2m), 2)     AS temp_promedio,
  ROUND(MAX(temperature_2m), 2)     AS temp_maxima,
  ROUND(MIN(temperature_2m), 2)     AS temp_minima,
  ROUND(AVG(apparent_temperature), 2) AS sensacion_termica_promedio,

  -- Precipitación
  ROUND(SUM(precipitation), 2)      AS precipitacion_total_mm,

  -- Viento
  ROUND(AVG(wind_speed_10m), 2)     AS viento_promedio_kmh,
  ROUND(MAX(wind_speed_10m), 2)     AS viento_maximo_kmh,

  -- Humedad y nubosidad
  ROUND(AVG(relative_humidity_2m), 1) AS humedad_promedio_pct,
  ROUND(AVG(cloud_cover), 1)        AS nubosidad_promedio_pct,

  -- Metadata
  COUNT(*)                          AS horas_registradas,
  CURRENT_TIMESTAMP()               AS gold_updated_at

FROM
  `mci506-weather-pipeline.weather_pipeline.silver_weather`

GROUP BY
  city, country, latitude, longitude, DATE(time)

ORDER BY
  fecha DESC, city ASC;
