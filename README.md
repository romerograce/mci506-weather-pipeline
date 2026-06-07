# mci506-weather-pipeline
Pipeline de datos climatológicos con arquitectura medallion - MCI506
Participantes:
1. Grace Linda Romero Arancibia
2. Jorge Branly Carrizales Yampara


### 1. ¿QUÉ datos extrae?
El pipeline genera un dataset meteorológico basado en mediciones horarias. 
* **Dominio:** Datos climáticos de 8 ciudades monitoreadas (La Paz, Santa Cruz, Cochabamba, Buenos Aires, Lima, Santiago, Bogotá y Madrid).
* **Variables (Columnas):**
  * Temperatura a 2 metros (`temperature_2m`)
  * Humedad relativa a 2 metros (`relative_humidity_2m`)
  * Temperatura aparente (`apparent_temperature`)
  * Precipitación (`precipitation`)
  * Velocidad del viento a 10 metros (`wind_speed_10m`)
  * Presión superficial (`surface_pressure`)
  * Cobertura de nubes (`cloud_cover`)

### 2. ¿DE DÓNDE los trae?
* **Fuente de datos:** API pública de **Open-Meteo**.
* **Endpoint (URL):** `https://api.open-meteo.com/v1/forecast`
* **Acceso:** La extracción se realiza de forma programática enviando los parámetros de latitud y longitud correspondientes a cada ciudad configurada en el script.

### 3. ¿A DÓNDE los guarda?
* **Ubicación:** Google Cloud Storage (GCS).
* **Nombre del bucket:** Se define dinámicamente mediante la variable de entorno `GCS_BUCKET_NAME`.
* **Formato de archivo:** NDJSON (`.ndjson`).
* **Estructura de carpetas:** Mantiene la misma estructura de rutas de la extracción local, utilizando particiones por fecha. Por ejemplo: `weather/extracted_date=YYYY-MM-DD/weather_xxx.ndjson`.

### 4. ¿CUÁNDO se ejecuta?
* **Automatización:** GitHub Actions (mediante el workflow "Weather Pipeline - Bronze Layer").
* **Frecuencia:** Diaria.
* **Horario:** 06:00 UTC (02:00 AM hora de Bolivia), configurado mediante la expresión cron `0 6 * * *`.
