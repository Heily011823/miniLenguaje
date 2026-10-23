"""Ejecuta los programas de prueba de Tramo y comprueba que den lo esperado.

Uso (desde la carpeta del proyecto):
    python probar_programas.py            # prueba los 17 y muestra un resumen
    python probar_programas.py 3 7        # muestra la salida completa de los programas 3 y 7

Nota: cada ejecucion tambien queda guardada en el historial (historial_ruta.db).
"""
import os
import subprocess
import sys

EJECUCION = "=== EJECUCIÓN ==="

# Salida esperada (lo que imprime el programa, despues de la fase de ejecucion)
SALIDA = {
    1: ["El mirador esta lejos del campamento"],
    2: ["El tiempo total del sendero es 43"],
    3: ["Agua restante: 70",
        "Imprevisto en el sendero: Agua insuficiente para completar el sendero",
        "Revision del equipo finalizada"],
    4: ["Cuantas paradas tiene el sendero?",
        "Descansando en la parada 1",
        "Parada 2: mirador cerrado, se omite",
        "Descansando en la parada 3",
        "Parada 4: mirador cerrado, se omite",
        "Parada 5: derrumbe en el sendero, la excursion se detiene",
        "Recorrido terminado en la parada 5"],
    7: ["Capturado: división por cero",
        "Primera verificacion terminada",
        "Capturado: índice fuera de rango",
        "Factorial de 5: 120"],
}
ENTRADA = {4: "8\n"}

# Textos que deben aparecer en la salida completa (programas con errores a proposito)
CONTIENE = {
    5: ["Error léxico en la línea 3: símbolo no reconocido '@'",
        "Error léxico en la línea 5: símbolo no reconocido '$'",
        "Error léxico en la línea 6: cadena sin cerrar"],
    6: ["Error sintáctico en la línea 3: se esperaba ';' pero se encontró 'anotar'"],
    8: ["Antes de dividir",
        "Error de tiempo de ejecución en la línea 5: división por cero"],
    15: ["Error semántico en la línea 4: variable 'c' no declarada",
         "Error semántico en la línea 7: el trayecto 'inexistente' no está definido",
         "Error semántico en la línea 11: el trayecto 'doble' espera 1 argumento(s) y recibe 2",
         "Error semántico en la línea 12: el campamento 'Fantasma' no está definido",
         "Error semántico en la línea 13: 'detener' solo se puede usar dentro de un ciclo o un bifurcar",
         "Error semántico en la línea 14: 'regresar' solo se puede usar dentro de un trayecto",
         "Error semántico en la línea 15: 'mismo' solo se puede usar dentro de un campamento"],
}
# Programas que deben terminar con error (codigo de salida distinto de 0)
DEBEN_FALLAR = {5, 6, 8, 15}


def correr(num):
    """ Ejecuta un programa de prueba y recoge su código de salida y los mensajes.

    Parámetros:
        num: número del programa que se va a ejecutar.

    Retorna:
        Una tupla con el código de salida del proceso y el texto combinado
        de la salida estándar y la salida de errores.
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "main.py", "programa%d.txt" % num, "--sin-tokens"],
                       input=ENTRADA.get(num, ""), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, env=env)
    return p.returncode, (p.stdout + p.stderr).replace("\r\n", "\n")


def revisar(num, codigo, salida):
    """ Comprueba si el resultado del programa es el esperado.

    Parámetros:
        num: número del programa de prueba.
        codigo: código de salida del proceso que fue ejecutado.
        salida: texto producido por el programa.

    Retorna:
        Una tupla (ok, detalle), donde ok indica si la prueba pasó
        y detalle contiene la descripción del problema si falló.
    """
    if num in DEBEN_FALLAR:
        if codigo == 0:
            return False, "debia terminar con error y termino bien"
    elif codigo != 0:
        ultimo = [l for l in salida.split("\n") if l.strip()][-1:] or [""]
        return False, "termino con error: " + ultimo[0]
    if num in SALIDA:
        if EJECUCION not in salida:
            return False, "no llego a la fase de ejecucion"
        real = [l for l in salida.split(EJECUCION, 1)[1].split("\n") if l.strip()]
        if real != SALIDA[num]:
            return False, "salida distinta.\n      esperada: %r\n      real:     %r" % (SALIDA[num], real)
    for frase in CONTIENE.get(num, []):
        if frase not in salida:
            return False, "falta en la salida: " + frase
    return True, ""


def main(argv):
    """ Ejecuta las pruebas o comprueba todos los programas.

    Parámetros:
        argv: lista de argumentos recibidos desde la línea de comandos.
              Si contiene números, ejecuta esos programas y muestra sus salidas.
              Si está vacía, comprueba los 17 programas y presenta un resumen.

    Retorna:
        0 si todas las pruebas son correctas.
        1 si se detectan fallos o falta el archivo principal.
    """
    if not os.path.exists("main.py"):
        print("Ejecuta este script DENTRO de la carpeta miniLenguaje.")
        return 1
    if argv:
        for a in argv:
            codigo, salida = correr(int(a))
            print("=" * 60 + "\nprograma%s.txt  (codigo de salida %d)\n" % (a, codigo) + "=" * 60)
            print(salida)
        return 0
    fallos = 0
    for num in range(1, 18):
        if not os.path.exists("programa%d.txt" % num):
            print("programa%-2d  FALTA el archivo" % num)
            fallos += 1
            continue
        try:
            codigo, salida = correr(num)
            ok, detalle = revisar(num, codigo, salida)
        except subprocess.TimeoutExpired:
            ok, detalle = False, "tardo demasiado (mas de 120 s)"
        print("programa%-2d  %s" % (num, "OK" if ok else "REVISAR  -> " + detalle))
        fallos += 0 if ok else 1
    print("\n%d de 17 correctos." % (17 - fallos))
    if fallos:
        print("Para ver la salida completa de uno:  python probar_programas.py N")
    return 0 if not fallos else 1


# Comprueba si el archivo se está ejecutando directamente.
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
