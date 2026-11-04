# Tabbycat Master Scraper & Data Pipeline (Neon Edition)

[English](#english) | [Español](#español)

---

## English

### Overview
A robust, production-grade data pipeline for the automated extraction, parsing, and ingestion of British Parliamentary (BP) debate tournament data from Tabbycat platforms into a PostgreSQL database hosted on Neon DB.

The project features a decoupled Python architecture, automated duplicate prevention using a two-step failsafe, smart welcome portal resolution, extraction of exact BP speaker/team roles (`d_role`, `t_role`), and partial update capabilities for complete future-proofing.

---

### Project Architecture

The repository utilizes a flat modular design structured by separation of concerns:

```text
tabbycat-neon-scraper/
│
├── README.md             # Updated project documentation
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (Neon DB credentials - Excluded from Git)
├── .gitignore            # Git exclusion rules
│
├── config.py             # Configuration management using python-dotenv
├── extractor.py          # Web scraping, vueData parsing, ballot extraction & portal resolution
├── loader.py             # Database operations, 2-step failsafe, partial updates & clean ingestion
├── ui.py                 # Tkinter GUI, manual/batch queuing, and background execution logs
│
└── main.py               # Application orchestrator and main entry point
```

---

### Key Features & Enhancements

1. **Smart Portal Navigation (`extractor.py`)**
   * Automatically resolves multi-category Tabbycat "Welcome Portals" (e.g., CMUDE) by identifying and navigating directly to the primary category (prioritizing `Open` tracks).

2. **Advanced Ballot Parsing & Role Extraction (`extractor.py`)**
   * Decodes embedded JavaScript state objects (`window.vueData`) and raw ballot sheets.
   * Flattens complex Vue JSON dictionary payloads (popovers, icons, tooltips) into clean database-ready text.
   * Captures speaker roles (`d_role`: PM, DPM, LO, DLO, etc.) and speaker positions (`t_role`: first, second).

3. **Two-Step Failsafe & Idempotent Ingestion (`loader.py`)**
   * **Step 1 (URL Existence Check):** Prevents re-ingesting already fully loaded tournaments based on domain registration in `master_torneos_registro`.
   * **Step 2 (Future-Proofing / Partial Updates):** Inspects loaded datasets for entirely `NULL` target columns (e.g., missing `d_role` or `t_role`) and triggers targeted column updates without duplicating rows.
   * **Clean Ingestion:** Performs per-tournament pre-insertion `DELETE` statements on tables (`master_speakers_ajustado`, `master_consolidado_resultados`, `master_breaking_adjudicators`) to guarantee strict idempotency.

4. **Desktop Interface (`ui.py`)**
   * Supports manual text entry, bulk queuing via CSV/Excel, real-time thread logging, and asynchronous background processing.

---

### Database Schema (Neon PostgreSQL)

* **`master_torneos_registro`**: Control table tracking processed tournament URLs and statuses.
* **`master_motions`**: Tournament motions and infoslides (`ON CONFLICT (motion) DO NOTHING`).
* **`master_speakers_ajustado`**: Speaker speaker tab entries, including scores, round keys, `d_role`, and `t_role`.
* **`master_consolidado_resultados`**: Round results, side placements, and team keys.
* **`master_breaking_adjudicators`**: Breaking adjudicator rosters and scores.

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

El proyecto implementa una arquitectura desacoplada en Python, un sistema Failsafe de dos pasos para la prevención de duplicados, resolución inteligente de portales de bienvenida, extracción detallada de roles (`d_role`, `t_role`) y actualizaciones parciales para garantizar *future-proofing*.

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
├── extractor.py          # Scraping, parsing de vueData, lectura de papeletas y resolución de portales
├── loader.py             # Operaciones SQL, Failsafe de 2 pasos, actualizaciones parciales e ingesta limpia
├── ui.py                 # Interfaz gráfica Tkinter, cola de torneos y logs en tiempo real
│
└── main.py               # Orquestador principal y punto de entrada
```

---

### Funcionalidades Clave

1. **Resolución Inteligente de Portales (`extractor.py`)**
   * Detecta automáticamente si una URL corresponde a un portal de bienvenida con múltiples categorías (ej. CMUDE) y redirige la extracción hacia la categoría principal (dando prioridad estricta a la categoría `Open`).

2. **Parsing de Papeletas y Extracción de Roles (`extractor.py`)**
   * Decodifica las variables de estado JavaScript (`window.vueData`) y papeletas detalladas.
   * Aplana diccionarios y objetos complejos de Vue (popovers, emojis, HTML) a cadenas de texto limpias compatibles con PostgreSQL.
   * Extrae los roles individuales del orador (`d_role`: PM, DPM, LO, DLO, etc.) y la posición en el equipo (`t_role`: primer u segundo orador).

3. **Mecanismo Failsafe de 2 Pasos e Ingesta Idempotente (`loader.py`)**
   * **Paso 1 (Comprobación de URL):** Verifica en `master_torneos_registro` si el dominio del torneo ya fue procesado por completo para evitar ejecuciones redundantes.
   * **Paso 2 (Actualización Parcial / Future-Proofing):** Evalúa si el torneo existente cuenta con columnas vacías (`NULL`) como `d_role` o `t_role` y ejecuta una actualización dirigida sin duplicar registros.
   * **Ingesta Limpia:** Aplica borrados preventivos (`DELETE FROM ... WHERE tournament = :slug`) sobre las tablas maestras antes de reinsertar datos completos, garantizando una base de datos 100% limpia.

4. **Interfaz de Escritorio (`ui.py`)**
   * Ingesta manual por lote o mediante archivos CSV/Excel, consola de eventos multihilo integrada y ejecución sin congelamiento de interfaz.

---

### Estructura de la Base de Datos (Neon PostgreSQL)

* **`master_torneos_registro`**: Tabla de control para registro de torneos procesados.
* **`master_motions`**: Mociones e infoslides extraídos (`ON CONFLICT (motion) DO NOTHING`).
* **`master_speakers_ajustado`**: Tab de oradores con puntajes, llaves de ronda, `d_role` y `t_role`.
* **`master_consolidado_resultados`**: Resultados por ronda, bancadas y llaves únicas.
* **`master_breaking_adjudicators`**: Nómina y puntajes de jueces clasificados.

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