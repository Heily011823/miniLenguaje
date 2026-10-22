"""Interfaz gráfica de Tramo: editor + paneles de tokens, errores y salida.

Uso:  python main.py --gui      (o   python gui.py)
"""
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import historial
from nucleo import correr

EJEMPLO = """# Programa de ejemplo
cargar distancia en 20;

evaluar distancia > 5:
  notificar("La entrega esta lejos de la biblioteca");
alternativa:
  notificar("El robot ha llegado al destino");
fin_ruta
"""

COLOR_FONDO = "#1e1e2e"
COLOR_TEXTO = "#e6e6f0"
COLOR_ERROR = "#ff6b6b"
COLOR_AVISO = "#ffd166"
COLOR_OK = "#7bd88f"
COLOR_FASE = "#6cb6ff"


class App:
    def __init__(self, raiz):
        self.raiz = raiz
        self.archivo = None
        raiz.title("Tramo — editor e intérprete")
        raiz.geometry("1200x720")
        self.semantico = tk.BooleanVar(value=True)
        self.ver_tokens = tk.BooleanVar(value=True)
        self.construir()
        self.editor.insert("1.0", EJEMPLO)
        self.actualizar_numeros()
        raiz.bind("<F5>", lambda e: self.ejecutar())
        raiz.bind("<Control-o>", lambda e: self.abrir())
        raiz.bind("<Control-s>", lambda e: self.guardar())

    # ------------------------------------------------------------ interfaz
    def construir(self):
        barra = ttk.Frame(self.raiz, padding=4)
        barra.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(barra, text="Abrir…", command=self.abrir).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="Guardar…", command=self.guardar).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="▶ Ejecutar (F5)", command=self.ejecutar).pack(side=tk.LEFT, padx=8)
        ttk.Button(barra, text="Historial", command=self.ver_historial).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="Limpiar paneles", command=self.limpiar).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(barra, text="Mostrar tokens", variable=self.ver_tokens).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(barra, text="Análisis semántico", variable=self.semantico).pack(side=tk.LEFT)
        self.estado = ttk.Label(barra, text="Listo")
        self.estado.pack(side=tk.RIGHT, padx=6)

        panel = ttk.PanedWindow(self.raiz, orient=tk.HORIZONTAL)
        panel.pack(fill=tk.BOTH, expand=True)

        # --- izquierda: editor con números de línea
        izq = ttk.Labelframe(panel, text="Programa (Tramo)")
        panel.add(izq, weight=3)
        cont = ttk.Frame(izq)
        cont.pack(fill=tk.BOTH, expand=True)
        self.numeros = tk.Text(cont, width=4, padx=4, takefocus=0, border=0, state="disabled",
                               background="#2a2a3c", foreground="#888899", font=("Consolas", 11))
        self.numeros.pack(side=tk.LEFT, fill=tk.Y)
        self.scroll = ttk.Scrollbar(cont, command=self.desplazar)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor = tk.Text(cont, undo=True, wrap="none", font=("Consolas", 11),
                              background=COLOR_FONDO, foreground=COLOR_TEXTO,
                              insertbackground="white", yscrollcommand=self.al_desplazar)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.tag_configure("linea_error", background="#5c2b33")
        self.editor.bind("<KeyRelease>", lambda e: self.actualizar_numeros())
        self.editor.bind("<<Paste>>", lambda e: self.raiz.after(10, self.actualizar_numeros))

        # --- derecha: tres paneles separados
        der = ttk.PanedWindow(panel, orient=tk.VERTICAL)
        panel.add(der, weight=2)
        self.p_tokens = self.crear_panel(der, "Tokens", 2)
        self.p_errores = self.crear_panel(der, "Errores y mensajes", 1)
        self.p_salida = self.crear_panel(der, "Salida del programa", 2)
        self.p_errores.tag_configure("error", foreground=COLOR_ERROR)
        self.p_errores.tag_configure("aviso", foreground=COLOR_AVISO)
        self.p_errores.tag_configure("info", foreground=COLOR_OK)
        self.p_errores.tag_configure("fase", foreground=COLOR_FASE)
        self.p_tokens.tag_configure("fase", foreground=COLOR_FASE)

    def crear_panel(self, padre, titulo, peso):
        marco = ttk.Labelframe(padre, text=titulo)
        padre.add(marco, weight=peso)
        texto = tk.Text(marco, wrap="word", state="disabled", font=("Consolas", 10),
                        background=COLOR_FONDO, foreground=COLOR_TEXTO, height=6)
        barra = ttk.Scrollbar(marco, command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side=tk.RIGHT, fill=tk.Y)
        texto.pack(fill=tk.BOTH, expand=True)
        return texto

    # ------------------------------------------------- números de línea
    def desplazar(self, *args):
        self.editor.yview(*args)
        self.numeros.yview(*args)

    def al_desplazar(self, primero, ultimo):
        self.scroll.set(primero, ultimo)
        self.numeros.yview_moveto(primero)

    def actualizar_numeros(self):
        total = int(self.editor.index("end-1c").split(".")[0])
        self.numeros.configure(state="normal")
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        self.numeros.configure(state="disabled")
        self.numeros.yview_moveto(self.editor.yview()[0])

    # --------------------------------------------------------- utilidades
    def escribir(self, panel, texto, etiqueta=None):
        panel.configure(state="normal")
        panel.insert("end", texto + "\n", etiqueta) if etiqueta else panel.insert("end", texto + "\n")
        panel.see("end")
        panel.configure(state="disabled")

    def limpiar(self):
        for p in (self.p_tokens, self.p_errores, self.p_salida):
            p.configure(state="normal")
            p.delete("1.0", "end")
            p.configure(state="disabled")
        self.editor.tag_remove("linea_error", "1.0", "end")

    def abrir(self):
        ruta = filedialog.askopenfilename(title="Abrir programa Tramo",
                                          filetypes=[("Programas Tramo", "*.txt *.tramo"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            with open(ruta, encoding="utf-8-sig") as f:
                contenido = f.read()
        except OSError as e:
            messagebox.showerror("Error", "No se pudo abrir el archivo: %s" % e.strerror)
            return
        self.cargar_codigo(contenido, ruta)

    def cargar_codigo(self, contenido, ruta=None):
        self.archivo = ruta
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", contenido)
        self.actualizar_numeros()
        self.limpiar()
        self.raiz.title("Tramo — %s" % (ruta or "sin título"))

    def guardar(self):
        ruta = self.archivo or filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Programas Tramo", "*.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end-1c"))
        except OSError as e:
            messagebox.showerror("Error", "No se pudo guardar: %s" % e.strerror)
            return
        self.archivo = ruta
        self.raiz.title("Tramo — %s" % ruta)
        self.estado.configure(text="Guardado")

    # ------------------------------------------------------ ejecución
    def pedir_entrada(self):
        dato = simpledialog.askstring("escanear", "El programa pide un dato:", parent=self.raiz)
        if dato is None:
            raise EOFError
        self.escribir(self.p_salida, "> " + dato)
        return dato

    def ejecutar(self):
        codigo = self.editor.get("1.0", "end-1c")
        self.limpiar()
        lineas_salida = []
        lineas_error = []

        def reportar(canal, texto):
            if canal == "tokens":
                self.escribir(self.p_tokens, texto)
            elif canal == "fase":
                self.escribir(self.p_errores, "— %s —" % texto, "fase")
                if canal == "fase" and texto == "ANÁLISIS LÉXICO":
                    self.escribir(self.p_tokens, "— %s —" % texto, "fase")
            else:
                self.escribir(self.p_errores, texto, canal)
                if canal == "error":
                    lineas_error.append(texto)

        def salida(texto):
            lineas_salida.append(texto)
            self.escribir(self.p_salida, texto)

        self.estado.configure(text="Ejecutando…")
        self.raiz.update_idletasks()
        try:
            codigo_salida = correr(codigo, self.pedir_entrada, salida, reportar,
                                   mostrar_tokens=self.ver_tokens.get(),
                                   semantico=self.semantico.get(), max_profundidad=1000)
        except Exception as e:      # nunca dejar que la ventana se cierre por un fallo interno
            reportar("error", "Error interno del intérprete: %s: %s" % (type(e).__name__, e))
            codigo_salida = 1
        for texto in lineas_error:
            m = re.search(r"en la línea (\d+)", texto)
            if m:
                self.editor.tag_add("linea_error", "%s.0" % m.group(1), "%s.0 lineend" % m.group(1))
        self.estado.configure(text="Terminó sin errores" if codigo_salida == 0 else "Terminó con errores")
        historial.guardar(self.archivo or "(editor)", codigo, "\n".join(lineas_salida),
                          "OK" if codigo_salida == 0 else "ERROR")

    # ------------------------------------------------------- historial
    def ver_historial(self):
        filas = historial.listar(50)
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Historial de ejecuciones (SQLite)")
        ventana.geometry("640x360")
        arbol = ttk.Treeview(ventana, columns=("fecha", "archivo", "estado"), show="headings")
        for col, ancho in (("fecha", 160), ("archivo", 300), ("estado", 80)):
            arbol.heading(col, text=col.capitalize())
            arbol.column(col, width=ancho)
        arbol.pack(fill=tk.BOTH, expand=True)
        for id_, fecha, archivo, estado, _c, _s in filas:
            arbol.insert("", "end", iid=str(id_), values=(fecha, archivo or "-", estado))
        ttk.Label(ventana, text="Doble clic: cargar ese programa y su salida guardada").pack(pady=3)

        def cargar(_evento):
            sel = arbol.selection()
            if not sel:
                return
            fila = historial.obtener(int(sel[0]))
            if fila:
                self.cargar_codigo(fila[4], fila[2] if fila[2] not in (None, "(editor)") else None)
                self.escribir(self.p_salida, fila[5] or "(sin salida)")
                self.estado.configure(text="Cargado del historial #%d" % fila[0])
            ventana.destroy()
        arbol.bind("<Double-1>", cargar)


def abrir():
    sys.setrecursionlimit(20000)
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    abrir()
