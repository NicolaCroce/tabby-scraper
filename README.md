# Tabbycat Master Scraper & Data Pipeline (Neon Edition)

[English](#english) | [Español](#español)

---

## English

### Overview
A modular data pipeline for the automated extraction, parsing, and ingestion of debate tournament data from Tabbycat platforms into a PostgreSQL database hosted on Neon DB.

The project features a decoupled architecture in Python, automated duplicate prevention using fingerprinting algorithms, and an interactive desktop interface built with Tkinter.

---

### Project Architecture

The repository utilizes a flat modular design structured by separation of concerns:

```text
tabbycat-neon-scraper/
│
├── README.md             # Project documentation
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (Database credentials - Excluded from Git)
├── .gitignore            # Git exclusion rules
│
├── config.py             # Configuration management using python-dotenv
├── extractor.py          # Web scraping and HTML/JSON parsing (BeautifulSoup / PyJSON5)
├── loader.py             # Database layer, duplicate validation, and SQL ingestion (SQLAlchemy)
├── ui.py                 # User Interface and background thread management (Tkinter)
│
└── main.py               # Main entry point and orchestrator
```

---

### Key Features

1. **Robust Data Extraction (`extractor.py`)**
   * Decodes embedded JavaScript state variables (`window.vueData`) to extract tabular data for speakers, teams, and adjudicators.
   * Standardizes round classifications (e.g., R1-R9, QF, SF, GF) and extracts motion metadata including infoslides.

2. **Automated Failsafe Mechanism (`loader.py`)**
   * Computes a tournament fingerprint based on extracted motion hashes before database write operations.
   * Prevents redundant transactions in Neon DB if matching records are detected, maintaining database integrity.

3. **Desktop Interface (`ui.py`)**
   * Supports manual batch entry via plain text and automated file ingestion via Excel (`.xlsx`) or CSV files.
   * Integrated execution log with asynchronous multi-threading to prevent UI freezing during heavy network calls.

---

### Technical Stack

* **Language:** Python 3.10+
* **Database:** PostgreSQL on Neon DB
* **Scraping & Parsing:** BeautifulSoup4, Requests, PyJSON5, Regular Expressions (re)
* **Data Processing:** Pandas, NumPy
* **ORM & Database Driver:** SQLAlchemy, Psycopg2-binary
* **Security & Environment:** Python-dotenv
* **GUI & Threading:** Tkinter, Threading

---

### Installation & Setup

#### 1. Clone the repository
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
Un pipeline de datos modular para la extracción, limpieza e ingesta automatizada de datos de torneos de debate desde plataformas Tabbycat hacia una base de datos relacional PostgreSQL hospedada en Neon DB.

El proyecto cuenta con una arquitectura desacoplada en Python, control de fallos antiduplicados mediante huellas digitales e interfaz gráfica de escritorio interactiva en Tkinter.

---

### Arquitectura del Proyecto

El repositorio utiliza una estructura plana orientada a la separación de responsabilidades:

```text
tabbycat-neon-scraper/
│
├── README.md             # Documentación principal del proyecto
├── requirements.txt      # Dependencias del entorno de Python
├── .env                  # Variables de entorno (Credenciales - No trackeado por Git)
├── .gitignore            # Reglas de exclusión de Git
│
├── config.py             # Gestión de configuración mediante python-dotenv
├── extractor.py          # Extracción web y parsing de HTML/JSON (BeautifulSoup / PyJSON5)
├── loader.py             # Capa de base de datos, validación antiduplicados e ingesta (SQLAlchemy)
├── ui.py                 # Interfaz gráfica de usuario y gestión de hilos (Tkinter)
│
└── main.py               # Punto de entrada principal y orquestador
```

---

### Funcionalidades Clave

1. **Extracción de Datos Resiliente (`extractor.py`)**
   * Decodifica variables de estado JavaScript (`window.vueData`) para extraer tablas de resultados de oradores, equipos y jueces.
   * Estandariza clasificaciones de rondas (ej. R1-R9, QF, SF, GF) y extrae metadatos de mociones con sus respectivos infoslides.

2. **Mecanismo Failsafe Antiduplicados (`loader.py`)**
   * Calcula una huella digital del torneo basada en las mociones extraídas antes de iniciar la carga en la base de datos.
   * Cancela la transacción en Neon DB si detecta registros coincidentes, garantizando la integridad de los datos.

3. **Interfaz de Escritorio (`ui.py`)**
   * Soporta ingesta manual por lote mediante texto plano e ingesta masiva desde archivos Excel (`.xlsx`) y CSV.
   * Consola de ejecución integrada con procesamiento multihilo asíncrono para evitar bloqueos en la interfaz gráfica.

---

### Stack Tecnológico

* **Lenguaje:** Python 3.10+
* **Base de Datos:** PostgreSQL en Neon DB
* **Scraping y Parsing:** BeautifulSoup4, Requests, PyJSON5, Expresiones Regulares (re)
* **Procesamiento de Datos:** Pandas, NumPy
* **ORM y Conector SQL:** SQLAlchemy, Psycopg2-binary
* **Seguridad y Entorno:** Python-dotenv
* **GUI e Hilos:** Tkinter, Threading

---

### Instalación y Configuración

#### 1. Clonar el repositorio
```bash
git clone https://github.com/TU_USUARIO/tabbycat-neon-scraper.git
cd tabbycat-neon-scraper
```

#### 2. Configurar Variables de Entorno
Crea un archivo `.env` en el directorio raíz del proyecto:

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