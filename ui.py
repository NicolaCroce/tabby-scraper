# ui.py
"""
Módulo encargado de la Interfaz Gráfica de Usuario (GUI) utilizando Tkinter.
Permite la carga manual de torneos (lotes por texto) y la carga masiva mediante archivos Excel/CSV.
"""
import os
import threading
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import pandas as pd

import config
import loader


class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tabbycat Master Scraper (Neon Modular Edition)")
        self.root.geometry("680x480") 
        self.root.minsize(600, 400)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=False, padx=10, pady=5)

        self.tab_manual = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_manual, text=" Carga manual ")
        self.setup_manual_tab()

        self.tab_file = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_file, text=" Carga por archivos (Excel / CSV) ")
        self.setup_file_tab()

        lbl_log = ttk.Label(root, text="Consola de Ejecución:", font=("Helvetica", 9, "bold"))
        lbl_log.pack(anchor="w", padx=12, pady=(5, 0))

        self.log_area = ScrolledText(root, height=6, bg="#1e1e1e", fg="#4af626", font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True, padx=10, pady=(2, 10))

    def log(self, text_msg):
        self.log_area.insert(tk.END, text_msg + "\n")
        self.log_area.see(tk.END)

    def setup_manual_tab(self):
        frame = ttk.LabelFrame(self.tab_manual, text=" Ingreso de Torneos ", padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Pega aquí los torneos a procesar (un torneo por línea).").pack(anchor="w", pady=(0, 2))
        ttk.Label(frame, text="Formato: URL, Nombre del Torneo, Fecha (YYYY-MM-DD)", font=("Helvetica", 8, "italic"), foreground="gray").pack(anchor="w")
        
        self.text_batch = tk.Text(frame, height=8, font=("Consolas", 9), wrap="none")
        self.text_batch.pack(fill="both", expand=True, pady=8)
        
        self.placeholder_text = "Por ejemplo:\nhttps://cmude2024.calicotab.com/, CMUDE 2024, 2024-07-15"
        
        self.default_fg = self.text_batch.cget("fg")
        self.text_batch.insert("1.0", self.placeholder_text)
        self.text_batch.config(fg="gray")

        self.text_batch.bind("<FocusIn>", self.clear_placeholder)
        self.text_batch.bind("<FocusOut>", self.add_placeholder)

        self.btn_run_manual = ttk.Button(frame, text="Iniciar Extracción", command=self.start_manual_thread)
        self.btn_run_manual.pack(pady=6)

    def clear_placeholder(self, event):
        current_text = self.text_batch.get("1.0", "end-1c").strip()
        if current_text == self.placeholder_text.strip():
            self.text_batch.delete("1.0", tk.END)
            self.text_batch.config(fg=self.default_fg)

    def add_placeholder(self, event):
        current_text = self.text_batch.get("1.0", "end-1c").strip()
        if not current_text:
            self.text_batch.insert("1.0", self.placeholder_text)
            self.text_batch.config(fg="gray")

    def setup_file_tab(self):
        frame = ttk.LabelFrame(self.tab_file, text=" Archivo de Torneos Históricos ", padding=15)
        frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame, text="Selecciona un archivo Excel (.xlsx) o CSV con columnas 'URL', 'Nombre' y 'Fecha':").pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=5)
        self.entry_filepath = ttk.Entry(row)
        self.entry_filepath.pack(side="left", fill="x", expand=True, padx=(0, 5))
        btn_browse = ttk.Button(row, text="Buscar...", command=self.browse_file)
        btn_browse.pack(side="left")

        self.btn_run_file = ttk.Button(frame, text="Procesar Archivo", command=self.start_file_thread)
        self.btn_run_file.pack(pady=10)

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Archivos soportados", "*.xlsx *.xls *.csv")])
        if f:
            self.entry_filepath.delete(0, tk.END)
            self.entry_filepath.insert(0, f)

    def toggle_buttons(self, state):
        self.btn_run_manual.config(state=state)
        self.btn_run_file.config(state=state)

    def start_manual_thread(self):
        threading.Thread(target=self.run_manual_process, daemon=True).start()

    def start_file_thread(self):
        threading.Thread(target=self.run_file_process, daemon=True).start()

    def run_manual_process(self):
        if not config.NEON_DB_URL:
            messagebox.showerror("Error", "Configura tu URL de Neon en el archivo .env.")
            return

        current_text = self.text_batch.get("1.0", "end-1c").strip()
        if current_text == self.placeholder_text.strip() or not current_text:
            self.log("[-] No hay torneos para procesar. Pega al menos un enlace en el cuadro de texto.")
            messagebox.showwarning("Atención", "Por favor, ingresa al menos un link válido antes de iniciar.")
            return

        self.toggle_buttons("disabled")
        try:
            queue = []
            lines = self.text_batch.get("1.0", tk.END).strip().split("\n")
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"): continue
                
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 1:
                    u = parts[0]
                    n = parts[1] if len(parts) > 1 else ""
                    d = parts[2] if len(parts) > 2 else ""
                    queue.append((u, n, d))

            if not queue:
                self.log("[-] Error leyendo los enlaces. Revisa el formato.")
                return

            self.log(f"[*] Total de torneos a procesar en cola: {len(queue)}")
            for u, n, d in queue:
                loader.process_single_tournament(u, config.NEON_DB_URL, override_name=n, tourney_date=d, log_func=self.log)

            messagebox.showinfo("Proceso Finalizado", "Se procesaron todos los torneos solicitados.")
        except Exception as e:
            self.log(f"[!] Error inesperado: {e}")
            traceback.print_exc()
        finally:
            self.toggle_buttons("normal")

    def run_file_process(self):
        if not config.NEON_DB_URL:
            messagebox.showerror("Error", "Configura tu URL de Neon en el archivo .env.")
            return

        path = self.entry_filepath.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror("Error", "Selecciona una ruta de archivo válida.")
            return

        self.toggle_buttons("disabled")
        try:
            if path.endswith(".csv"):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)

            col_map = {c.lower(): c for c in df.columns}
            url_col = col_map.get('url') or col_map.get('link') or col_map.get('tab')
            name_col = col_map.get('nombre') or col_map.get('torneo') or col_map.get('name')
            date_col = col_map.get('tournament_date') or col_map.get('date_torneo')

            if not url_col:
                self.log("[!] Error: El archivo debe contener al menos una columna llamada 'URL', 'Link' o 'Tab'.")
                return

            self.log(f"[*] Leyendo {len(df)} filas del archivo...")
            for idx, row in df.iterrows():
                u = str(row[url_col]).strip()
                n = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
                d = str(row[date_col]).strip() if date_col and pd.notna(row[date_col]) else ""
                if u and u.lower() != 'nan':
                    loader.process_single_tournament(u, config.NEON_DB_URL, override_name=n, tourney_date=d, log_func=self.log)

            messagebox.showinfo("Proceso Finalizado", "Lectura del archivo completada.")
        except Exception as e:
            self.log(f"[!] Error leyendo el archivo: {e}")
            traceback.print_exc()
        finally:
            self.toggle_buttons("normal")