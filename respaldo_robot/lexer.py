"""Analizador léxico del lenguaje Tramo.

Convierte el texto del programa en una lista de tokens. Cada token guarda su
tipo, su lexema y la línea donde aparece. Los errores léxicos (símbolos
desconocidos, cadenas sin cerrar) se acumulan en una lista aparte.
"""
import re
from dataclasses import dataclass

# Palabra reservada -> tipo de token
PALABRAS_RESERVADAS = {
    # variables y E/S
    "cargar": "KW_CARGAR", "en": "KW_EN",
    "notificar": "KW_NOTIFICAR", "escanear": "KW_ESCANEAR",
    # condicionales
    "evaluar": "KW_EVALUAR", "desviar": "KW_DESVIAR", "alternativa": "KW_ALTERNATIVA",
    # ciclos
    "patrullar": "KW_PATRULLAR",
    "recorrer": "KW_RECORRER", "partiendo_de": "KW_PARTIENDO_DE", "llegando_a": "KW_LLEGANDO_A",
    "rondar": "KW_RONDAR", "repetir_si": "KW_REPETIR_SI",
    "detener": "KW_DETENER", "avanzar": "KW_AVANZAR",
    # switch
    "bifurcar": "KW_BIFURCAR", "punto_ruta": "KW_PUNTO_RUTA", "ruta_base": "KW_RUTA_BASE",
    # funciones y clases
    "tarea": "KW_TAREA", "entregar": "KW_ENTREGAR",
    "modulo": "KW_MODULO", "ensamblar": "KW_ENSAMBLAR",
    "desplegar": "KW_DESPLEGAR", "mismo": "KW_MISMO",
    "extiende": "KW_EXTIENDE", "superior": "KW_SUPERIOR",
    # excepciones
    "intentar_ruta": "KW_INTENTAR_RUTA", "obstaculo": "KW_OBSTACULO",
    "destino": "KW_DESTINO", "alerta": "KW_ALERTA",
    # lógicos
    "junto_con": "KW_Y", "o_bien": "KW_O", "contrario_de": "KW_NO",
    # literales
    "nulo": "KW_NULO",
    # fin de bloque
    "fin_ruta": "KW_FIN_RUTA",
}

# El orden importa: Python prueba los patrones de arriba hacia abajo.
ESPECIFICACION = [
    ("COMMENT", r"#.*"),
    ("NEWLINE", r"\n"),
    ("WS", r"[ \t\r]+"),
    ("REAL_NUMBER", r"[0-9]+\.[0-9]+"),      # antes que INT_NUMBER y PUNTO
    ("INT_NUMBER", r"[0-9]+"),
    ("STRING", r'"(?:[^"\\\n]|\\.)*"'),       # admite \n \t \" \\
    ("STRING_SIN_CERRAR", r'"(?:[^"\\\n]|\\.)*\\?'),
    ("ID", r"[^\W\d]\w*"),                    # letras (con tildes), dígitos y _
    ("OP_REL", r">=|<=|==|!=|>|<"),          # los de dos caracteres primero
    ("OP_ARITH", r"[+\-*/%]"),
    ("PAREN_IZQ", r"\("), ("PAREN_DER", r"\)"),
    ("CORCHETE_IZQ", r"\["), ("CORCHETE_DER", r"\]"),
    ("COMA", r","), ("PUNTO", r"\."),
    ("DOS_PUNTOS", r":"), ("PUNTO_COMA", r";"),
    ("ERROR", r"."),                         # cualquier otro carácter
]
PATRON = re.compile("|".join("(?P<%s>%s)" % par for par in ESPECIFICACION))


@dataclass
class Token:
    tipo: str
    lexema: str
    linea: int

    def __str__(self):
        return "[line %d] %s %s" % (self.linea, self.tipo, self.lexema)


def analizar(codigo):
    """Devuelve (tokens, errores). errores es una lista de (linea, mensaje)."""
    tokens, errores = [], []
    linea = 1
    for m in PATRON.finditer(codigo):
        tipo, lexema = m.lastgroup, m.group()
        if tipo == "NEWLINE":
            linea += 1
        elif tipo in ("WS", "COMMENT"):
            pass
        elif tipo == "ID":
            if lexema in ("verdadero", "falso"):
                tokens.append(Token("BOOLEAN", lexema, linea))
            else:
                tokens.append(Token(PALABRAS_RESERVADAS.get(lexema, "ID"), lexema, linea))
        elif tipo == "STRING_SIN_CERRAR":
            errores.append((linea, "cadena sin cerrar"))
        elif tipo == "ERROR":
            errores.append((linea, "símbolo no reconocido '%s'" % lexema))
        else:
            tokens.append(Token(tipo, lexema, linea))
    ultima = tokens[-1].linea if tokens else 1
    tokens.append(Token("EOF", "", ultima))
    return tokens, errores
