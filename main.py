# main.py
"""
Punto de entrada principal de la aplicación Tabbycat Master Scraper.
Inicializa la interfaz gráfica modular.
"""
import tkinter as tk
from ui import ScraperApp

if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperApp(root)
    root.mainloop()