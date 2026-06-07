# mci506-weather-pipeline
Pipeline de datos climatológicos con arquitectura medallion - MCI506
Participantes:
1. Grace Linda Romero Arancibia
2. Jorge Branly Carrizales Yampara


# mci506-weather-pipeline

Pipeline de datos climatológicos con arquitectura medallion - MCI506

### 1. ¿QUÉ datos extrae?
El pipeline genera un dataset meteorológico basado en mediciones horarias. 
* **Dominio:** Datos climáticos de 11 ciudades monitoreadas (La Paz, Santa Cruz, Cochabamba, Buenos Aires, Lima, Santiago, Bogotá, Madrid, Quito, Asunción y Montevideo).
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

### 5. ¿CÓMO funciona?
El flujo de datos sigue los principios de la Arquitectura Medallion:
* **Capa Bronze:** Los scripts de Python extraen la data de la API y la cargan en Google Cloud Storage en formato NDJSON crudo, guardando el histórico mediante particionamiento por fecha de ejecución.
* **Capa Silver:** Los datos en bruto son transferidos a BigQuery, donde se validan tipos de datos y se aplica lógica incremental. Se utiliza una llave natural combinada (`city` y `time`) con una cláusula `WHERE NOT EXISTS` para garantizar que no se inserten horas duplicadas.
* **Capa Gold:** Mediante Scheduled Queries en BigQuery, la información validada de Silver se transforma en la tabla `gold_weather_daily`, agregando métricas de promedios, máximos y sumatorias a nivel diario.

### 6. ¿CUÁNTA CALIDAD tienen?
* **Tolerancia a fallos en origen:** La extracción incluye validaciones de respuesta HTTP y un sistema de reintentos automáticos (hasta 5 intentos con backoff exponencial) para sortear caídas de la API.
* **Integridad:** La capa Silver actúa como compuerta estricta de calidad, filtrando y descartando cualquier registro que no contenga identificadores válidos (`city IS NOT NULL` y `time IS NOT NULL`).
* **Estandarización:** En la capa Gold, todas las métricas decimales son normalizadas a un máximo de 2 decimales para asegurar consistencia analítica y de presentación.

### 7. ¿SI FALLA qué hacer?
* **Monitoreo:** El proceso Python registra su actividad a través de la librería `logging`, identificando exactamente qué ciudad generó un error transitorio sin detener el bucle de extracción del resto.
* **Notificaciones:** Si el pipeline de GitHub Actions falla por completo a nivel de infraestructura, el sistema envía alertas automáticas al correo del administrador del repositorio.
* **Recuperación:** Se deben revisar los logs en la pestaña "Actions" de GitHub. Si el fallo fue por timeout de la API, el job puede relanzarse de forma manual. Si es un error de esquemas o SQL, se debe generar un fix en una nueva rama (PR) para corregir la lógica antes del siguiente ciclo programado a las 02:00 AM hora local.

### Diagrama de Arquitectura

```mermaid
flowchart LR
    subgraph Origen
        API[API Open-Meteo]
    end
    
    subgraph GitHub Actions [Ingesta Local]
        EX[extract.py] --> LO[load.py]
    end
    
    subgraph Google Cloud Platform [Arquitectura Medallion]
        BR[(Bronze Layer\nGCS - NDJSON)]
        SI[(Silver Layer\nBigQuery)]
        GO[(Gold Layer\nBigQuery Tablas)]
    end
    
    API -- Datos JSON --> EX
    LO -- Sube archivos --> BR
    BR -- External Table\nWHERE NOT EXISTS --> SI
    SI -- Scheduled Queries\n(Diario) --> GO
    GO -- Conexión Directa --> BI[Dashboard / Looker]

