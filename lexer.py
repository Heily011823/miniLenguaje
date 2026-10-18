"""Analizador léxico del lenguaje Ruta.

Convierte el texto del programa en una lista de tokens. Cada token guarda su
tipo, su lexema y la línea donde aparece. Los errores léxicos (símbolos
desconocidos, cadenas sin cerrar) se acumulan en una lista aparte.
"""
import re
from dataclasses import dataclass

# Palabra reservada -> tipo de token (sección 4 del documento)
PALABRAS_RESERVADAS = {
    "cargar": "KW_CARGAR", "en": "KW_EN",
    "notificar": "KW_NOTIFICAR", "escanear": "KW_ESCANEAR",
    "evaluar": "KW_EVALUAR", "desviar": "KW_DESVIAR", "alternativa": "KW_ALTERNATIVA",
    "patrullar": "KW_PATRULLAR", "recorrer": "KW_RECORRER",
    "desde": "KW_DESDE", "hasta": "KW_HASTA",
    "detener": "KW_DETENER", "avanzar": "KW_AVANZAR",
    "tarea": "KW_TAREA", "entregar": "KW_ENTREGAR",
    "modulo": "KW_MODULO", "ensamblar": "KW_ENSAMBLAR",
    "desplegar": "KW_DESPLEGAR", "mismo": "KW_MISMO",
    "intentar_ruta": "KW_INTENTAR_RUTA", "obstaculo": "KW_OBSTACULO",
    "destino": "KW_DESTINO", "alerta": "KW_ALERTA",
    "y": "KW_Y", "o": "KW_O", "no": "KW_NO",
    "fin_ruta": "KW_FIN_RUTA",
}

# El orden importa: Python prueba los patrones de arriba hacia abajo.
ESPECIFICACION = [
    ("COMMENT", r"#.*"),
    ("NEWLINE", r"\n"),
    ("WS", r"[ \t\r]+"),
    ("REAL_NUMBER", r"[0-9]+\.[0-9]+"),      # antes que INT_NUMBER y PUNTO
    ("INT_NUMBER", r"[0-9]+"),
    ("STRING", r'"[^"\n]*"'),
    ("STRING_SIN_CERRAR", r'"[^"\n]*'),
    ("ID", r"[a-zA-Z_][a-zA-Z0-9_]*"),
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
