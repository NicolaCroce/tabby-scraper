# Tabbycat Master Scraper & Data Pipeline (Neon Edition)

[English](#english) | [Español](#español)

---

## English

### Overview
A robust, production-grade data pipeline for the automated extraction, parsing, and ingestion of British Parliamentary (BP) debate tournament data from Tabbycat platforms into a PostgreSQL database hosted on Neon DB.

The project features a **decoupled in-memory Python architecture**, automated duplicate prevention via URL failsafes, smart welcome portal resolution, exact BP speaker/team role extraction (`d_role`, `t_role`), and an **intelligent Team Record fallback engine** for tournaments with private or unreleased ballots.

---

### Project Architecture

The repository utilizes a modular design structured by separation of concerns:

```text
tabbycat-neon-scraper/
│
├── README.md             # Updated project documentation
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (Neon DB credentials - Excluded from Git)
├── .gitignore            # Git exclusion rules
│
├── config.py             # Configuration management using python-dotenv
├── extractor.py          # Web scraping, vueData parsing, ballot extraction & Team Record fallback
├── loader.py             # Decoupled in-memory processing, URL failsafe & fast Neon DB ingestion
├── ui.py                 # Tkinter GUI, manual/batch queuing, and background execution logs
│
└── main.py               # Application orchestrator and main entry point
```

---

### Key Features & Enhancements

1. **Smart Portal Navigation (`extractor.py`)**
   * Automatically resolves multi-category Tabbycat "Welcome Portals" (e.g., CMUDE) by identifying and navigating directly to the primary category (prioritizing `Open` tracks).

2. **Dual-Engine Ballot & Role Extraction (`extractor.py`)**
   * **Primary Engine (Public Ballots):** Decodes embedded JavaScript state objects (`window.vueData`) and public scoresheets to capture exact speaker roles (`d_role`: PM, DPM, LO, DLO, MG, GW, MO, OW) and speaking order (`t_role`).
   * **Team Record Fallback Engine:** When a tournament does not release public ballots (e.g., PUCP Open, Rosario Open), the extractor automatically parses the `Team Record` HTML/JSON tooltips and chamber placements to deterministically reconstruct speaker roles and scores in exact speaking order.

3. **Decoupled In-Memory Processing & Failsafe Ingestion (`loader.py`)**
   * **URL Failsafe Check:** Verifies domain registration in `master_torneos_registro` before scraping to prevent redundant runs and duplicate data.
   * **Zero-Idle-Connection Scraping:** Executes all HTTP requests, Pandas transformations, and role merges purely in local memory first, opening the Neon PostgreSQL connection strictly for fast batch `INSERT` operations (`chunksize=500`).
   * **Numeric Adjudicator Mapping:** Extracts breaking adjudicator rosters alongside binary numeric flags (`1.0` / `0.0`) for `adjcore` and `independent` statuses.

4. **Desktop Interface (`ui.py`)**
   * Supports manual text entry, bulk queuing via CSV/Excel, real-time thread logging, and asynchronous background processing.

---

### Database Schema (Neon PostgreSQL)

* **`master_torneos_registro`**: Control table tracking processed tournament URLs, slugs, dates, and statuses.
* **`master_motions`**: Tournament motions and infoslides extracted per round.
* **`master_speakers_ajustado`**: Speaker tab entries melted by round, including individual scores, `d_role`, and tournament metadata.
* **`master_consolidado_resultados`**: Round results, chamber placements (`Side`), and team records.
* **`master_breaking_adjudicators`**: Breaking adjudicator rosters, institutions, and numeric status flags (`adjcore`, `independent`).

---

### Technical Stack

* **Language:** Python 3.10+
* **Database:** PostgreSQL on Neon DB
* **Scraping & Parsing:** BeautifulSoup4, Requests, PyJSON5, Regular Expressions (`re`)
* **Data Processing:** Pandas, NumPy
* **ORM & Database Driver:** SQLAlchemy, Psycopg2-binary
* **Security & Environment:** Python-dotenv
* **GUI & Threading:** Tkinter, Threading

---

### Installation & Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/tabbycat-neon-scraper.git
cd tabbycat-neon-scraper
```

#### 2. Configure Environment Variables
Create a `.env` file in the root directory:

```env
NEON_DB_URL=postgresql://user:password@host/neondb?sslmode=require
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Run the Application
```bash
python main.py
```

---

## Español

### Descripción General
Un pipeline de datos robusto y listo para producción diseñado para la extracción, limpieza e ingesta automatizada de torneos de debate bajo el formato Parlamento Británico (BP) desde plataformas Tabbycat hacia PostgreSQL en Neon DB.

El proyecto implementa una **arquitectura desacoplada en memoria** en Python, prevención de duplicados mediante verificación de dominio, resolución inteligente de portales de bienvenida, extracción detallada de roles (`d_role`) y un **motor de respaldo (*fallback*) basado en Team Records** para torneos que no liberan papeletas públicas.

---

### Arquitectura del Proyecto

El repositorio utiliza una estructura modular basada en la separación de responsabilidades:

```text
tabbycat-neon-scraper/
│
├── README.md             # Documentación actualizada del proyecto
├── requirements.txt      # Dependencias del entorno de Python
├── .env                  # Variables de entorno (Credenciales Neon DB - No trackeado en Git)
├── .gitignore            # Reglas de exclusión de Git
│
├── config.py             # Gestión de configuración mediante python-dotenv
├── extractor.py          # Scraping, parsing de vueData, lectura de papeletas y fallback de Team Record
├── loader.py             # Procesamiento desacoplado en memoria, Failsafe por URL e ingesta rápida en Neon
├── ui.py                 # Interfaz gráfica Tkinter, cola de torneos y logs en tiempo real
│
└── main.py               # Orquestador principal y punto de entrada
```

---

### Funcionalidades Clave

1. **Resolución Inteligente de Portales (`extractor.py`)**
   * Detecta automáticamente si una URL corresponde a un portal de bienvenida con múltiples categorías (ej. CMUDE) y redirige la extracción hacia la categoría principal (dando prioridad estricta a la categoría `Open`).

2. **Motor Dual de Extracción de Roles (`extractor.py`)**
   * **Motor Principal (Papeletas Públicas):** Decodifica las variables de estado JavaScript (`window.vueData`) y papeletas detalladas para capturar el rol exacto de cada orador (`d_role`: PM, DPM, LO, DLO, MG, GW, MO, OW).
   * **Motor de Respaldo (*Fallback* de Team Record):** Si un torneo no publica sus papeletas (ej. PUCP Open, Rosario Open), el extractor analiza automáticamente los tooltips y cámaras de la vista *Team Record* para reconstruir de forma determinista los puntajes y roles en estricto orden de intervención.

3. **Procesamiento Desacoplado en Memoria e Ingesta Segura (`loader.py`)**
   * **Failsafe por URL:** Verifica en `master_torneos_registro` si el dominio del torneo ya fue procesado antes de iniciar el scraping para evitar duplicados.
   * **Scraping sin Conexiones Inactivas:** Ejecuta todas las peticiones web, transformaciones en Pandas y cruces de roles en memoria local, abriendo la conexión a Neon PostgreSQL únicamente al final para realizar inserciones rápidas por lotes (`chunksize=500`).
   * **Mapeo Numérico de Jueces:** Extrae la nómina de jueces clasificados transformando indicadores visuales en valores numéricos (`1.0` / `0.0`) para las columnas `adjcore` e `independent`.

4. **Interfaz de Escritorio (`ui.py`)**
   * Ingesta manual por lote o mediante archivos CSV/Excel, consola de eventos multihilo integrada y ejecución sin congelamiento de interfaz.

---

### Estructura de la Base de Datos (Neon PostgreSQL)

* **`master_torneos_registro`**: Tabla de control para registro de torneos procesados, slugs, fechas y estados.
* **`master_motions`**: Mociones e infoslides extraídos por ronda.
* **`master_speakers_ajustado`**: Tab de oradores estructurado por ronda con puntajes individuales, `d_role` y metadatos del torneo.
* **`master_consolidado_resultados`**: Resultados por ronda, cámaras (`Side`) y registro de equipos.
* **`master_breaking_adjudicators`**: Nómina de jueces clasificados, instituciones e indicadores numéricos (`adjcore`, `independent`).

---

### Stack Tecnológico

* **Lenguaje:** Python 3.10+
* **Base de Datos:** PostgreSQL en Neon DB
* **Scraping y Parsing:** BeautifulSoup4, Requests, PyJSON5, Expresiones Regulares (`re`)
* **Procesamiento de Datos:** Pandas, NumPy
* **ORM y Conector SQL:** SQLAlchemy, Psycopg2-binary
* **Seguridad y Entorno:** Python-dotenv
* **GUI e Hilos:** Tkinter, Threading

---

### Instalación y Configuración

#### 1. Clonar el Repositorio
```bash
git clone https://github.com/TU_USUARIO/tabbycat-neon-scraper.git
cd tabbycat-neon-scraper
```

#### 2. Configurar Variables de Entorno
Crea un archivo `.env` en el directorio raíz:

```env
NEON_DB_URL=postgresql://usuario:password@host/neondb?sslmode=require
```

#### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

#### 4. Ejecutar la Aplicación
```bash
python main.py
```