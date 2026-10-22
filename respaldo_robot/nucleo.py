"""Núcleo de Tramo: ejecuta las cuatro etapas (léxico, sintáctico, semántico, ejecución).

Lo usan tanto la línea de comandos (main.py) como la interfaz gráfica (gui.py).
La función correr() no imprime nada por sí misma: informa mediante callbacks.
"""
from lexer import analizar
from parser_ruta import Parser, ErrorSintactico
from semantico import analizar_semantica
from interprete import Interprete, ErrorEjecucion, ExcepcionRuta


def correr(codigo, entrada, salida, reportar, mostrar_tokens=True, semantico=True,
           max_profundidad=10000):
    """Devuelve 0 si todo salió bien y 1 si hubo algún error.

    reportar(canal, texto): canal = 'fase' | 'tokens' | 'error' | 'aviso' | 'info'
    salida(texto): una línea de salida del programa (notificar)
    entrada(): lee una línea (escanear)
    """
    # 1) Análisis léxico
    tokens, errores = analizar(codigo)
    if mostrar_tokens:
        reportar("fase", "ANÁLISIS LÉXICO")
        for t in tokens[:-1]:
            reportar("tokens", str(t))
    if errores:
        for linea, msg in errores:
            reportar("error", "Error léxico en la línea %d: %s" % (linea, msg))
        reportar("error", "Se detiene el análisis: corrija los errores léxicos.")
        return 1

    # 2) Análisis sintáctico
    try:
        programa = Parser(tokens).programa()
    except ErrorSintactico as e:
        reportar("error", "Error sintáctico en la línea %d: %s" % (e.linea, e.mensaje))
        return 1
    reportar("fase", "ANÁLISIS SINTÁCTICO")
    reportar("info", "El programa cumple la gramática de Tramo.")

    # 3) Análisis semántico
    if semantico:
        reportar("fase", "ANÁLISIS SEMÁNTICO")
        errs, avisos = analizar_semantica(programa)
        for linea, msg in avisos:
            reportar("aviso", "Advertencia semántica en la línea %d: %s (está dentro de "
                              "intentar_ruta, se ejecutará de todos modos)" % (linea, msg))
        for linea, msg in errs:
            reportar("error", "Error semántico en la línea %d: %s" % (linea, msg))
        if errs:
            reportar("error", "Se detiene la ejecución: corrija los errores semánticos.")
            return 1
        if not avisos:
            reportar("info", "No se encontraron errores semánticos.")

    # 4) Ejecución
    reportar("fase", "EJECUCIÓN")
    interprete = Interprete(salida=salida, entrada=entrada, max_profundidad=max_profundidad)
    try:
        interprete.ejecutar(programa)
    except ErrorEjecucion as e:
        reportar("error", "Error de tiempo de ejecución en la línea %d: %s" % (e.linea, e.mensaje))
        return 1
    except ExcepcionRuta as e:
        reportar("error", "Error de tiempo de ejecución en la línea %d: excepción no capturada: %s"
                 % (e.linea, interprete.texto(e.valor)))
        return 1
    except RecursionError:
        reportar("error", "Error de tiempo de ejecución: desbordamiento de pila")
        return 1
    return 0
