"""Interfaz gráfica de Tramo: editor + paneles de tokens, errores y salida.

Uso:  python main.py --gui      (o   python gui.py)
"""
# Importaciones necesarias para la interfaz y el manejo de textos.
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

# Permite guardar y consultar el historial de ejecuciones.
import historial

# Permite ejecutar los programas.
from nucleo import correr

# Programa que aparece al abrir el editor por primera vez.
EJEMPLO = """# Programa de ejemplo
cargar distancia en 20;

evaluar distancia > 5:
  anotar("El mirador esta lejos del campamento");
alternativa:
  anotar("La excursion ha llegado a la cumbre");
fin_sendero
"""

# Colores que se usan para mostrar el texto.
COLOR_FONDO = "#1e1e2e"
COLOR_TEXTO = "#e6e6f0"
COLOR_ERROR = "#ff6b6b"
COLOR_AVISO = "#ffd166"
COLOR_OK = "#7bd88f"
COLOR_FASE = "#6cb6ff"

# Clase principal donde se crea y se maneja la ventana.
class App:
    def __init__(self, raiz):
        # Configura la ventana y guarda el archivo que está abierto.
        self.raiz = raiz
        self.archivo = None
        raiz.title("Tramo — editor e intérprete")
        raiz.geometry("1200x720")

        # Activa por defecto la vista de tokens y el análisis semántico.
        self.semantico = tk.BooleanVar(value=True)
        self.ver_tokens = tk.BooleanVar(value=True)

        # Crea la interfaz y carga el programa de ejemplo.
        self.construir()
        self.editor.insert("1.0", EJEMPLO)
        self.actualizar_numeros()

        # Permite ejecutar, abrir y guardar con el teclado.
        raiz.bind("<F5>", lambda e: self.ejecutar())
        raiz.bind("<Control-o>", lambda e: self.abrir())
        raiz.bind("<Control-s>", lambda e: self.guardar())

    # ------------------------------------------------------------ interfaz
    # Crea los botones, el editor y los paneles de la ventana.
    def construir(self):
        barra = ttk.Frame(self.raiz, padding=4)
        barra.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(barra, text="Abrir…", command=self.abrir).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="Guardar…", command=self.guardar).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="▶ Ejecutar (F5)", command=self.ejecutar).pack(side=tk.LEFT, padx=8)
        ttk.Button(barra, text="Historial", command=self.ver_historial).pack(side=tk.LEFT, padx=2)
        ttk.Button(barra, text="Limpiar paneles", command=self.limpiar).pack(side=tk.LEFT, padx=2)

        # Opciones para mostrar los tokens y activar el análisis semántico.
        ttk.Checkbutton(barra, text="Mostrar tokens", variable=self.ver_tokens).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(barra, text="Análisis semántico", variable=self.semantico).pack(side=tk.LEFT)
        self.estado = ttk.Label(barra, text="Listo")
        self.estado.pack(side=tk.RIGHT, padx=6)

        # Divide la ventana en la zona del editor y la de los resultados.
        panel = ttk.PanedWindow(self.raiz, orient=tk.HORIZONTAL)
        panel.pack(fill=tk.BOTH, expand=True)

        # --- izquierda: editor con números de línea
        izq = ttk.Labelframe(panel, text="Programa (Tramo)")
        panel.add(izq, weight=3)
        cont = ttk.Frame(izq)
        cont.pack(fill=tk.BOTH, expand=True)

        # Muestra los números de las líneas del código.
        self.numeros = tk.Text(cont, width=4, padx=4, takefocus=0, border=0, state="disabled",
                               background="#2a2a3c", foreground="#888899", font=("Consolas", 11))
        self.numeros.pack(side=tk.LEFT, fill=tk.Y)
        self.scroll = ttk.Scrollbar(cont, command=self.desplazar)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Área donde se escribe y modifica el código.
        self.editor = tk.Text(cont, undo=True, wrap="none", font=("Consolas", 11),
                              background=COLOR_FONDO, foreground=COLOR_TEXTO,
                              insertbackground="white", yscrollcommand=self.al_desplazar)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.tag_configure("linea_error", background="#5c2b33")
        
        # Actualiza los números cuando se modifica o se pega código.
        self.editor.bind("<KeyRelease>", lambda e: self.actualizar_numeros())
        self.editor.bind("<<Paste>>", lambda e: self.raiz.after(10, self.actualizar_numeros))

        # --- derecha: tres paneles separados

        # Crea los paneles donde aparecen los tokens, los errores y la salida.
        der = ttk.PanedWindow(panel, orient=tk.VERTICAL)
        panel.add(der, weight=2)
        self.p_tokens = self.crear_panel(der, "Tokens", 2)
        self.p_errores = self.crear_panel(der, "Errores y mensajes", 1)
        self.p_salida = self.crear_panel(der, "Salida del programa", 2)
        
        # Diferencia los errores, avisos y mensajes con distintos colores.
        self.p_errores.tag_configure("error", foreground=COLOR_ERROR)
        self.p_errores.tag_configure("aviso", foreground=COLOR_AVISO)
        self.p_errores.tag_configure("info", foreground=COLOR_OK)
        self.p_errores.tag_configure("fase", foreground=COLOR_FASE)
        self.p_tokens.tag_configure("fase", foreground=COLOR_FASE)

    # Crea un panel con título, texto y una barra de desplazamiento.
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
    
    # Mueve el editor y los números de línea al mismo tiempo.
    def desplazar(self, *args):
        self.editor.yview(*args)
        self.numeros.yview(*args)

    # Mantiene sincronizada la barra de desplazamiento con el editor.
    def al_desplazar(self, primero, ultimo):
        self.scroll.set(primero, ultimo)
        self.numeros.yview_moveto(primero)

    # Actualiza los números según las líneas que tiene el código.
    def actualizar_numeros(self):
        total = int(self.editor.index("end-1c").split(".")[0])
        self.numeros.configure(state="normal")
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        self.numeros.configure(state="disabled")
        self.numeros.yview_moveto(self.editor.yview()[0])

    # --------------------------------------------------------- utilidades
    
    # Muestra un mensaje en el panel.
    def escribir(self, panel, texto, etiqueta=None):
        panel.configure(state="normal")
        panel.insert("end", texto + "\n", etiqueta) if etiqueta else panel.insert("end", texto + "\n")
        panel.see("end")
        panel.configure(state="disabled")

    # Limpia los paneles y quita las marcas de error del editor.
    def limpiar(self):
        for p in (self.p_tokens, self.p_errores, self.p_salida):
            p.configure(state="normal")
            p.delete("1.0", "end")
            p.configure(state="disabled")
        self.editor.tag_remove("linea_error", "1.0", "end")

    # Abre un archivo y carga su contenido en el editor.
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

    # Coloca el código en el editor y actualiza el nombre de la ventana.
    def cargar_codigo(self, contenido, ruta=None):
        self.archivo = ruta
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", contenido)
        self.actualizar_numeros()
        self.limpiar()
        self.raiz.title("Tramo — %s" % (ruta or "sin título"))

    # Guarda el código en el archivo.
    def guardar(self):
        # Si no hay un archivo abierto, permite elegir dónde guardarlo.
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
    
    # Pide un dato cuando el programa necesita una entrada.
    def pedir_entrada(self):
        dato = simpledialog.askstring("preguntar", "El programa pide un dato:", parent=self.raiz)
        if dato is None:
            raise EOFError
        self.escribir(self.p_salida, "> " + dato)
        return dato

    # Ejecuta el código y muestra los mensajes y resultados.
    def ejecutar(self):
        codigo = self.editor.get("1.0", "end-1c")
        self.limpiar()
        lineas_salida = []
        lineas_error = []

        # Envía los mensajes del intérprete al panel que les corresponde.
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

        # Muestra la salida del programa y guarda sus líneas.
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

        # Marca en el editor las líneas donde se encontraron errores.
        for texto in lineas_error:
            m = re.search(r"en la línea (\d+)", texto)
            if m:
                self.editor.tag_add("linea_error", "%s.0" % m.group(1), "%s.0 lineend" % m.group(1))
        self.estado.configure(text="Terminó sin errores" if codigo_salida == 0 else "Terminó con errores")
        historial.guardar(self.archivo or "(editor)", codigo, "\n".join(lineas_salida),
                          "OK" if codigo_salida == 0 else "ERROR")

    # ------------------------------------------------------- historial
    
    # Abre una ventana con las últimas ejecuciones guardadas.
    def ver_historial(self):
        filas = historial.listar(50)
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Historial de ejecuciones (SQLite)")
        ventana.geometry("640x360")

        # Organiza los datos del historial en una tabla.
        arbol = ttk.Treeview(ventana, columns=("fecha", "archivo", "estado"), show="headings")
        for col, ancho in (("fecha", 160), ("archivo", 300), ("estado", 80)):
            arbol.heading(col, text=col.capitalize())
            arbol.column(col, width=ancho)
        arbol.pack(fill=tk.BOTH, expand=True)
        for id_, fecha, archivo, estado, _c, _s in filas:
            arbol.insert("", "end", iid=str(id_), values=(fecha, archivo or "-", estado))
        ttk.Label(ventana, text="Doble clic: cargar ese programa y su salida guardada").pack(pady=3)

        # Carga el programa y su salida al hacer doble clic en una ejecución.
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

# Abre la ventana principal y mantiene la aplicación funcionando.
def abrir():
    sys.setrecursionlimit(20000)
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()

# Inicia la interfaz cuando se ejecuta este archivo directamente.
if __name__ == "__main__":
    abrir()
