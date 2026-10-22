"""Tramo: analizador léxico, sintáctico, semántico e intérprete.

Uso:  python main.py programa1.txt
      python main.py programa1.txt --sin-tokens      (oculta la lista de tokens)
      python main.py programa1.txt --sin-semantico   (omite el análisis semántico)
      python main.py --historial                     (muestra las últimas ejecuciones)
      python main.py --gui                           (abre el editor gráfico)
"""

# Permite acceder a los argumentos y configurar la ejecución de Python.
import sys

# Permite ejecutar el intérprete en un hilo con una pila más grande.
import threading

# Permite guardar y consultar las ejecuciones anteriores.
import historial

# Importa la función que ejecuta los programas.
from nucleo import correr


def reportar(canal, texto):
    """ Muestra los mensajes generados durante el análisis y la ejecución.

    Parámetros:
        canal: tipo de mensaje que se va a mostrar.
        texto: contenido del mensaje.
    """
    if canal == "fase":
        print("=== %s ===" % texto)
    else:
        print(texto)


def mostrar_historial():
    """ Muestra las últimas ejecuciones guardadas en la base de datos.

    Retorna:
        0 si el historial se muestra correctamente.
    """
    filas = historial.listar(20)
    if not filas:
        print("El historial está vacío.")
        return 0
    print("%-4s %-19s %-16s %s" % ("ID", "FECHA", "ARCHIVO", "ESTADO"))
    for id_, fecha, archivo, estado, _codigo, _salida in filas:
        print("%-4d %-19s %-16s %s" % (id_, fecha, (archivo or "-")[:16], estado))
    return 0


def main(argv):
    """ Controla la ejecución principal del intérprete.

    Parámetros:
        argv: lista de argumentos recibidos desde la terminal.

    Retorna:
        Un código numérico que indica si la ejecución terminó correctamente.
        Devuelve 0 si no hubo errores y un valor distinto de 0 si hubo problemas.
    """
    if "--gui" in argv:
        import gui
        gui.abrir()
        return 0
    if "--historial" in argv:
        return mostrar_historial()
    archivos = [a for a in argv[1:] if not a.startswith("--")]
    if not archivos:
        print(__doc__)
        return 1
    ruta = archivos[0]
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            codigo = f.read()
    except OSError as e:
        print("No se pudo abrir el archivo '%s': %s" % (ruta, e.strerror))
        return 1

    lineas_salida = []

    # Muestra la salida y la conserva para guardarla en el historial.
    def salida(texto):
        lineas_salida.append(texto)
        print(texto)

    try:
        estado = correr(codigo, input, salida, reportar,
                        mostrar_tokens="--sin-tokens" not in argv,
                        semantico="--sin-semantico" not in argv)
    except KeyboardInterrupt:
        print("\nEjecución interrumpida.")
        estado = 1
    except Exception as e:      # último recurso: nunca mostrar un traceback de Python
        print("Error interno del intérprete: %s: %s" % (type(e).__name__, e))
        estado = 1
    historial.guardar(ruta, codigo, "\n".join(lineas_salida), "OK" if estado == 0 else "ERROR")
    return estado


def ejecutar_con_pila_grande(argv):
    """ Ejecuta main() en un hilo con una pila de mayor tamaño.

    Esto permite ejecutar programas con recursión profunda y reduce
    la posibilidad de que se agote la pila disponible.

    Parámetros:
        argv: lista de argumentos recibidos desde la terminal.

    Retorna:
        El código de salida que devuelve main().
    """
    sys.setrecursionlimit(1000000)
    resultado = [1]
    try:
        threading.stack_size(512 * 1024 * 1024)
    except (ValueError, RuntimeError):
        try:
            threading.stack_size(64 * 1024 * 1024)
        except (ValueError, RuntimeError):
            resultado[0] = main(argv)
            return resultado[0]

    # Función que ejecuta main() dentro del hilo.
    def tarea():
        resultado[0] = main(argv)
    hilo = threading.Thread(target=tarea)
    try:
        hilo.start()
    except RuntimeError:            # el sistema no dio tanta memoria: correr sin hilo
        threading.stack_size(0)
        sys.setrecursionlimit(8000)
        return main(argv)
    hilo.join()
    return resultado[0]

# Comprueba si el archivo se está ejecutando directamente.
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--gui" in sys.argv:
        sys.exit(main(sys.argv))        # tkinter debe correr en el hilo principal
    sys.exit(ejecutar_con_pila_grande(sys.argv))
