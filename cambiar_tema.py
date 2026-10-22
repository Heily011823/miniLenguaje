"""Convierte el proyecto Tramo del tema ROBOT al tema SENDERISMO.

Uso (desde la carpeta del proyecto, donde estan main.py y los programaN.txt):

    python cambiar_tema.py

Que hace:
  1. Guarda una copia de seguridad en la carpeta 'respaldo_robot/'.
  2. En los archivos .py cambia SOLO los textos entre comillas y los comentarios
     (palabras reservadas, mensajes de error, docstrings). Nunca toca nombres de
     variables, funciones ni clases, asi que el codigo no se rompe.
  3. En los programaN.txt cambia las palabras reservadas fuera de cadenas y
     comentarios. Los programas 1 a 8 se reescriben con los textos del informe.
  4. Avisa de lo que debes revisar a mano.
"""
import io
import os
import re
import shutil
import sys
import tokenize

# ----------------------------------------------------------------------------
# Vocabulario: palabra vieja -> palabra nueva
# ----------------------------------------------------------------------------
MAP = {
    "notificar": "anotar",
    "escanear": "preguntar",
    "patrullar": "caminar",
    "rondar": "ascender",
    "punto_ruta": "mirador",
    "ruta_base": "sendero_base",
    "tarea": "trayecto",
    "tareas": "trayectos",
    "entregar": "regresar",
    "modulo": "campamento",
    "módulo": "campamento",
    "módulos": "campamentos",
    "Módulo": "Campamento",
    "Módulos": "Campamentos",
    "ensamblar": "armar",
    "desplegar": "montar",
    "intentar_ruta": "explorar",
    "obstaculo": "imprevisto",
    "destino": "recoger",
    "alerta": "tormenta",
    "fin_ruta": "fin_sendero",
}
NUEVAS = {"anotar", "preguntar", "caminar", "ascender", "mirador", "sendero_base",
          "trayecto", "regresar", "campamento", "armar", "montar", "explorar",
          "imprevisto", "recoger", "tormenta", "fin_sendero"}

# Frases con genero/articulo que hay que ajustar (se aplican ANTES que MAP)
FRASES = [
    ("la tarea '%s' no está definida", "el trayecto '%s' no está definido"),
    ("tarea '%s' no definida", "trayecto '%s' no definido"),
    ("tareas declaradas", "trayectos declarados"),
    ("tarea anidada", "trayecto anidado"),
    ("otras tareas", "otros trayectos"),
    ("las tareas", "los trayectos"),
    ("de la tarea", "del trayecto"),
    ("una tarea", "un trayecto"),
    ("la tarea", "el trayecto"),
    ("La entrega esta lejos de la biblioteca", "El mirador esta lejos del campamento"),
    ("El robot ha llegado al destino", "La excursion ha llegado a la cumbre"),
]

PAT = re.compile(r"(?<![\w])(" + "|".join(sorted(map(re.escape, MAP), key=len, reverse=True)) + r")(?![\w])")


def mapear(texto):
    return PAT.sub(lambda m: MAP[m.group(1)], texto)


def transformar_texto(texto):
    for viejo, nuevo in FRASES:
        texto = texto.replace(viejo, nuevo)
    return mapear(texto)


# ----------------------------------------------------------------------------
# Archivos .py: solo cadenas y comentarios
# ----------------------------------------------------------------------------
def convertir_py(src):
    lineas = src.split("\n")
    inicios, pos = [], 0
    for ln in lineas:
        inicios.append(pos)
        pos += len(ln) + 1

    def off(fila, col):
        return inicios[fila - 1] + col

    cambios = []
    lector = io.StringIO(src).readline
    for tok in tokenize.generate_tokens(lector):
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            nuevo = transformar_texto(tok.string)
            if nuevo != tok.string:
                cambios.append((off(*tok.start), off(*tok.end), nuevo))
    for ini, fin, nuevo in sorted(cambios, reverse=True):
        src = src[:ini] + nuevo + src[fin:]
    return src, len(cambios)


# ----------------------------------------------------------------------------
# Archivos .txt (programas Tramo)
# ----------------------------------------------------------------------------
CADENA_O_COMENTARIO = re.compile(r'("(?:[^"\\\n]|\\.)*"?|#.*)')


def convertir_txt(src):
    partes = CADENA_O_COMENTARIO.split(src)
    return "".join(p if i % 2 else mapear(p) for i, p in enumerate(partes))


def identificadores_nuevos(src):
    """Palabras nuevas que el programa YA usaba como nombre de variable."""
    partes = CADENA_O_COMENTARIO.split(src)
    codigo = " ".join(p for i, p in enumerate(partes) if i % 2 == 0)
    return sorted(set(re.findall(r"[^\W\d]\w*", codigo)) & NUEVAS)


PROGRAMAS = {
1: '''# Programa 1: Evaluacion de distancia del sendero
cargar distancia en 20;

evaluar distancia > 5:
    anotar("El mirador esta lejos del campamento");
alternativa:
    anotar("La excursion ha llegado a la cumbre");
fin_sendero
''',
2: '''# Programa 2: Suma del tiempo de cada tramo del sendero
trayecto calcular_tiempo(tramos, n):
    cargar total en 0;
    recorrer i partiendo_de 0 llegando_a n - 1:
        total en total + tramos[i];
    fin_sendero
    regresar total;
fin_sendero

cargar tiempos en [4, 8, 15, 16];
cargar resultado en calcular_tiempo(tiempos, 4);

evaluar resultado > 40 junto_con resultado < 50:
    anotar("El tiempo total del sendero es " + resultado);
alternativa:
    anotar("Sendero fuera del tiempo limite");
fin_sendero
''',
3: '''# Programa 3: Campamento de Provisiones y Excepciones
campamento Excursionista:
    armar(nombre, agua_actual):
        mismo.nombre en nombre;
        mismo.agua_actual en agua_actual;
    fin_sendero

    trayecto beber_agua(cantidad):
        evaluar cantidad > mismo.agua_actual:
            tormenta "Agua insuficiente para completar el sendero";
        fin_sendero
        mismo.agua_actual en mismo.agua_actual - cantidad;
        regresar mismo.agua_actual;
    fin_sendero
fin_sendero

cargar guia en montar Excursionista("Guia-01", 100);

explorar:
    anotar("Agua restante: " + guia.beber_agua(30));
    anotar("Agua restante: " + guia.beber_agua(200));
imprevisto err:
    anotar("Imprevisto en el sendero: " + err);
recoger:
    anotar("Revision del equipo finalizada");
fin_sendero
''',
4: '''# Programa 4: Caminata con lectura, desvios, detener y avanzar
cargar contador en 0;
cargar limite en 0;

anotar("Cuantas paradas tiene el sendero?");
preguntar(limite);

caminar contador < limite:
    contador en contador + 1;

    evaluar contador % 2 == 0:
        anotar("Parada " + contador + ": mirador cerrado, se omite");
        avanzar;
    desviar contador == 5:
        anotar("Parada 5: derrumbe en el sendero, la excursion se detiene");
        detener;
    alternativa:
        anotar("Descansando en la parada " + contador);
    fin_sendero
fin_sendero

anotar("Recorrido terminado en la parada " + contador);
''',
5: '''# Programa 5: Errores lexicos
cargar distancia en 20;
cargar costo en 5 @ 3;
anotar("Distancia: " + distancia);
cargar $total en distancia + costo;
anotar("Texto sin cerrar);
''',
6: '''# Programa 6: Errores sintacticos
cargar total en 10
anotar("Total: " + total);

evaluar total > 5
    anotar("Mayor que cinco");
fin_sendero

caminar total > 0:
    total en total - 1;

anotar("Fin");
''',
7: '''# Programa 7: Errores de ejecucion capturados y recursion
cargar kilometros en [10, 20, 30];
cargar total en 0;

explorar:
    anotar(100 / total);
imprevisto e:
    anotar("Capturado: " + e);
recoger:
    anotar("Primera verificacion terminada");
fin_sendero

explorar:
    anotar(kilometros[5]);
imprevisto e:
    anotar("Capturado: " + e);
fin_sendero

trayecto factorial(n):
    evaluar n <= 1:
        regresar 1;
    fin_sendero
    regresar n * factorial(n - 1);
fin_sendero

anotar("Factorial de 5: " + factorial(5));
''',
8: '''# Programa 8: Error de ejecucion sin capturar
cargar a en 10;
cargar b en 0;
anotar("Antes de dividir");
cargar c en a / b;
anotar("Esto no se imprime");
''',
}

REVISAR = re.compile(r"robot|entrega|bateria|batería|paquete|biblioteca|campus|pasillo|ruta", re.I)


def main():
    carpeta = os.getcwd()
    yo = os.path.basename(__file__)
    if not os.path.exists(os.path.join(carpeta, "lexer.py")):
        print("No encuentro lexer.py. Ejecuta este script DENTRO de la carpeta miniLenguaje.")
        return 1
    with open(os.path.join(carpeta, "lexer.py"), encoding="utf-8-sig") as f:
        if '"anotar"' in f.read():
            print("El proyecto ya parece estar convertido (lexer.py ya tiene 'anotar'). No hago nada.")
            return 0

    py = sorted(f for f in os.listdir(carpeta) if f.endswith(".py") and f not in (yo, "probar_programas.py"))
    txt = sorted(f for f in os.listdir(carpeta) if re.fullmatch(r"programa\d+\.txt", f))

    # ---- 1. copia de seguridad ----
    respaldo = os.path.join(carpeta, "respaldo_robot")
    if os.path.exists(respaldo):
        print("Ya existe 'respaldo_robot/'. No la sobrescribo (guarda la copia original).")
    else:
        os.makedirs(respaldo)
        for nombre in py + txt:
            shutil.copy2(os.path.join(carpeta, nombre), os.path.join(respaldo, nombre))
        print("Copia de seguridad creada en 'respaldo_robot/' (%d archivos)." % (len(py) + len(txt)))

    avisos = []

    # ---- 2. archivos .py ----
    print("\n== Archivos .py ==")
    for nombre in py:
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            src = f.read()
        nuevo, n = convertir_py(src)
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(nuevo)
        print("  %-16s %d textos cambiados" % (nombre, n))

    # ---- 3. programas .txt ----
    print("\n== Programas .txt ==")
    for nombre in txt:
        num = int(re.search(r"\d+", nombre).group())
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            original = f.read()
        usados = identificadores_nuevos(original)
        if usados:
            avisos.append("%s usa como NOMBRE DE VARIABLE palabras que ahora son reservadas: %s "
                          "(renombralas)" % (nombre, ", ".join(usados)))
        if num in PROGRAMAS:
            nuevo = PROGRAMAS[num]
            accion = "reescrito con el texto del informe"
        else:
            nuevo = convertir_txt(original)
            accion = "palabras reservadas convertidas"
            for i, ln in enumerate(nuevo.split("\n"), 1):
                if REVISAR.search(ln):
                    avisos.append("%s linea %d: %s" % (nombre, i, ln.strip()))
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(nuevo)
        print("  %-16s %s" % (nombre, accion))

    # ---- 4. avisos ----
    print("\n== Revisa a mano ==")
    if avisos:
        for a in avisos:
            print("  - " + a)
    else:
        print("  (nada)")
    print("\nListo. Ahora ejecuta:  python probar_programas.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
