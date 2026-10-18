"""Ruta: analizador léxico, sintáctico e intérprete.

Uso:  python main.py programa1.txt
      python main.py programa1.txt --sin-tokens   (oculta la lista de tokens)
"""
import sys

from lexer import analizar
from parser_ruta import Parser, ErrorSintactico
from interprete import Interprete, ErrorEjecucion, ExcepcionRuta


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    ruta = argv[1]
    mostrar_tokens = "--sin-tokens" not in argv
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            codigo = f.read()
    except OSError as e:
        print("No se pudo abrir el archivo '%s': %s" % (ruta, e.strerror))
        return 1

    # 1) Análisis léxico
    tokens, errores = analizar(codigo)
    if mostrar_tokens:
        print("=== ANÁLISIS LÉXICO ===")
        for t in tokens[:-1]:
            print(t)
    if errores:
        for linea, msg in errores:
            print("Error léxico en la línea %d: %s" % (linea, msg))
        print("Se detiene el análisis: corrija los errores léxicos.")
        return 1

    # 2) Análisis sintáctico
    try:
        programa = Parser(tokens).programa()
    except ErrorSintactico as e:
        print("Error sintáctico en la línea %d: %s" % (e.linea, e.mensaje))
        return 1
    print("=== ANÁLISIS SINTÁCTICO ===")
    print("El programa cumple la gramática de Ruta.")

    # 3) Ejecución
    print("=== EJECUCIÓN ===")
    try:
        Interprete().ejecutar(programa)
    except ErrorEjecucion as e:
        print("Error de tiempo de ejecución en la línea %d: %s" % (e.linea, e.mensaje))
        return 1
    except ExcepcionRuta as e:
        print("Error de tiempo de ejecución en la línea %d: excepción no capturada: %s"
              % (e.linea, Interprete().texto(e.valor)))
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.setrecursionlimit(5000)
    sys.exit(main(sys.argv))
