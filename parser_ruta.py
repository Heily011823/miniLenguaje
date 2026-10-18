"""Analizador sintáctico (descenso recursivo) de Ruta.

Implementa la gramática EBNF de la sección 6 y construye el AST.
Se detiene en el primer error sintáctico y lo reporta con su línea.
"""
from nodos import *


class ErrorSintactico(Exception):
    def __init__(self, linea, mensaje):
        super().__init__(mensaje)
        self.linea = linea
        self.mensaje = mensaje


class Parser:
    DESPACHO = {
        "KW_CARGAR": "declaracion", "KW_NOTIFICAR": "impresion",
        "KW_ESCANEAR": "lectura", "KW_EVALUAR": "condicional",
        "KW_PATRULLAR": "ciclo_mientras", "KW_RECORRER": "ciclo_para",
        "KW_TAREA": "funcion", "KW_ENTREGAR": "retorno",
        "KW_MODULO": "clase", "KW_INTENTAR_RUTA": "excepcion",
        "KW_ALERTA": "lanzar", "KW_DETENER": "sentencia_detener", "KW_AVANZAR": "sentencia_avanzar",
    }

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---------- utilidades ----------
    @property
    def actual(self):
        return self.tokens[self.pos]

    def consumir(self):
        tok = self.tokens[self.pos]
        if tok.tipo != "EOF":
            self.pos += 1
        return tok

    def es(self, *tipos):
        return self.actual.tipo in tipos

    def error(self, esperado):
        tok = self.actual
        if tok.tipo == "EOF":
            msg = "se esperaba %s pero se llegó al final del archivo" % esperado
        else:
            msg = "se esperaba %s pero se encontró '%s'" % (esperado, tok.lexema)
        raise ErrorSintactico(tok.linea, msg)

    def esperar(self, tipo, esperado):
        if self.actual.tipo == tipo:
            return self.consumir()
        self.error(esperado)

    # ---------- programa y sentencias ----------
    def programa(self):
        sentencias = []
        while not self.es("EOF"):
            sentencias.append(self.sentencia())
        return sentencias

    def bloque(self, terminadores, esperado="'fin_ruta'"):
        sentencias = []
        while not self.es(*terminadores):
            if self.es("EOF"):
                self.error(esperado)
            sentencias.append(self.sentencia())
        return sentencias

    def sentencia(self):
        tipo = self.actual.tipo
        metodo = self.DESPACHO.get(tipo)
        if metodo:
            return getattr(self, metodo)()
        if tipo in ("ID", "KW_MISMO"):
            return self.asignacion_o_llamada()
        raise ErrorSintactico(self.actual.linea,
                              "no se esperaba '%s' en este lugar" % self.actual.lexema)

    def declaracion(self):
        tok = self.consumir()
        nombre = self.esperar("ID", "un nombre de variable")
        self.esperar("KW_EN", "'en'")
        valor = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Declarar(tok.linea, nombre.lexema, valor)

    def asignacion_o_llamada(self):
        inicio = self.actual
        nodo = self.primario()
        if self.es("KW_EN"):
            self.consumir()
            if not isinstance(nodo, (Var, Atributo, Indice)):
                raise ErrorSintactico(inicio.linea, "el lado izquierdo de 'en' debe ser una "
                                      "variable, un elemento de lista o un atributo")
            valor = self.expresion()
            self.esperar("PUNTO_COMA", "';'")
            return Asignar(inicio.linea, nodo, valor)
        if not isinstance(nodo, (Llamada, LlamadaMetodo)):
            self.error("'en' o una llamada a función")
        self.esperar("PUNTO_COMA", "';'")
        return ExprSentencia(inicio.linea, nodo)

    def impresion(self):
        tok = self.consumir()
        self.esperar("PAREN_IZQ", "'('")
        valor = self.expresion()
        self.esperar("PAREN_DER", "')'")
        self.esperar("PUNTO_COMA", "';'")
        return Imprimir(tok.linea, valor)

    def lectura(self):
        tok = self.consumir()
        self.esperar("PAREN_IZQ", "'('")
        nombre = self.esperar("ID", "un nombre de variable")
        self.esperar("PAREN_DER", "')'")
        self.esperar("PUNTO_COMA", "';'")
        return Leer(tok.linea, nombre.lexema)

    def condicional(self):
        tok = self.consumir()
        fin_rama = ("KW_DESVIAR", "KW_ALTERNATIVA", "KW_FIN_RUTA")
        cond = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        ramas = [(cond, self.bloque(fin_rama))]
        sino = None
        while self.es("KW_DESVIAR"):
            self.consumir()
            cond = self.expresion()
            self.esperar("DOS_PUNTOS", "':'")
            ramas.append((cond, self.bloque(fin_rama)))
        if self.es("KW_ALTERNATIVA"):
            self.consumir()
            self.esperar("DOS_PUNTOS", "':'")
            sino = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Si(tok.linea, ramas, sino)

    def ciclo_mientras(self):
        tok = self.consumir()
        cond = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Mientras(tok.linea, cond, cuerpo)

    def ciclo_para(self):
        tok = self.consumir()
        var = self.esperar("ID", "el nombre de la variable del ciclo")
        self.esperar("KW_DESDE", "'desde'")
        desde = self.expresion()
        self.esperar("KW_HASTA", "'hasta'")
        hasta = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Para(tok.linea, var.lexema, desde, hasta, cuerpo)

    def parametros(self):
        params = []
        if self.es("ID"):
            params.append(self.consumir().lexema)
            while self.es("COMA"):
                self.consumir()
                params.append(self.esperar("ID", "un nombre de parámetro").lexema)
        return params

    def funcion(self):
        tok = self.consumir()
        nombre = self.esperar("ID", "el nombre de la tarea")
        self.esperar("PAREN_IZQ", "'('")
        params = self.parametros()
        self.esperar("PAREN_DER", "')'")
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Funcion(tok.linea, nombre.lexema, params, cuerpo)

    def retorno(self):
        tok = self.consumir()
        valor = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Retorno(tok.linea, valor)

    def clase(self):
        tok = self.consumir()
        nombre = self.esperar("ID", "el nombre del módulo")
        self.esperar("DOS_PUNTOS", "':'")
        self.esperar("KW_ENSAMBLAR", "'ensamblar'")
        self.esperar("PAREN_IZQ", "'('")
        params = self.parametros()
        self.esperar("PAREN_DER", "')'")
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        metodos = []
        while self.es("KW_TAREA"):
            metodos.append(self.funcion())
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Clase(tok.linea, nombre.lexema, params, cuerpo, metodos)

    def excepcion(self):
        tok = self.consumir()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_OBSTACULO",), "'obstaculo'")
        self.esperar("KW_OBSTACULO", "'obstaculo'")
        var = self.esperar("ID", "un nombre para el error")
        self.esperar("DOS_PUNTOS", "':'")
        capturar = self.bloque(("KW_DESTINO", "KW_FIN_RUTA"))
        final = None
        if self.es("KW_DESTINO"):
            self.consumir()
            self.esperar("DOS_PUNTOS", "':'")
            final = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_ruta'")
        return Intentar(tok.linea, cuerpo, var.lexema, capturar, final)

    def lanzar(self):
        tok = self.consumir()
        valor = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Lanzar(tok.linea, valor)

    def sentencia_detener(self):
        tok = self.consumir()
        self.esperar("PUNTO_COMA", "';'")
        return Romper(tok.linea)

    def sentencia_avanzar(self):
        tok = self.consumir()
        self.esperar("PUNTO_COMA", "';'")
        return Continuar(tok.linea)

    # ---------- expresiones (de menor a mayor precedencia) ----------
    def expresion(self):
        return self.expr_logica()

    def expr_logica(self):
        izq = self.expr_y()
        while self.es("KW_O"):
            tok = self.consumir()
            izq = Binario(tok.linea, "o", izq, self.expr_y())
        return izq

    def expr_y(self):
        izq = self.expr_no()
        while self.es("KW_Y"):
            tok = self.consumir()
            izq = Binario(tok.linea, "y", izq, self.expr_no())
        return izq

    def expr_no(self):
        if self.es("KW_NO"):
            tok = self.consumir()
            return Unario(tok.linea, "no", self.expr_no())
        return self.expr_relacional()

    def expr_relacional(self):
        izq = self.expr_aritmetica()
        if self.es("OP_REL"):
            tok = self.consumir()
            return Binario(tok.linea, tok.lexema, izq, self.expr_aritmetica())
        return izq

    def expr_aritmetica(self):
        izq = self.termino()
        while self.es("OP_ARITH") and self.actual.lexema in ("+", "-"):
            tok = self.consumir()
            izq = Binario(tok.linea, tok.lexema, izq, self.termino())
        return izq

    def termino(self):
        izq = self.unario()
        while self.es("OP_ARITH") and self.actual.lexema in ("*", "/", "%"):
            tok = self.consumir()
            izq = Binario(tok.linea, tok.lexema, izq, self.unario())
        return izq

    def unario(self):
        if self.es("OP_ARITH") and self.actual.lexema == "-":
            tok = self.consumir()
            return Unario(tok.linea, "-", self.unario())
        return self.primario()

    def primario(self):
        nodo = self.atomo()
        while True:
            if self.es("PUNTO"):
                tok = self.consumir()
                nombre = self.esperar("ID", "un nombre de atributo o método").lexema
                if self.es("PAREN_IZQ"):
                    nodo = LlamadaMetodo(tok.linea, nodo, nombre, self.argumentos())
                else:
                    nodo = Atributo(tok.linea, nodo, nombre)
            elif self.es("CORCHETE_IZQ"):
                tok = self.consumir()
                idx = self.expresion()
                self.esperar("CORCHETE_DER", "']'")
                nodo = Indice(tok.linea, nodo, idx)
            else:
                return nodo

    def argumentos(self):
        """Consume '(' [expresion {',' expresion}] ')'."""
        self.esperar("PAREN_IZQ", "'('")
        args = []
        if not self.es("PAREN_DER"):
            args.append(self.expresion())
            while self.es("COMA"):
                self.consumir()
                args.append(self.expresion())
        self.esperar("PAREN_DER", "')'")
        return args

    def atomo(self):
        tok = self.actual
        t = tok.tipo
        if t == "ID":
            self.consumir()
            if self.es("PAREN_IZQ"):
                return Llamada(tok.linea, tok.lexema, self.argumentos())
            return Var(tok.linea, tok.lexema)
        if t == "INT_NUMBER":
            self.consumir()
            return Literal(tok.linea, int(tok.lexema))
        if t == "REAL_NUMBER":
            self.consumir()
            return Literal(tok.linea, float(tok.lexema))
        if t == "STRING":
            self.consumir()
            return Literal(tok.linea, tok.lexema[1:-1])
        if t == "BOOLEAN":
            self.consumir()
            return Literal(tok.linea, tok.lexema == "verdadero")
        if t == "KW_MISMO":
            self.consumir()
            return Mismo(tok.linea)
        if t == "PAREN_IZQ":
            self.consumir()
            e = self.expresion()
            self.esperar("PAREN_DER", "')'")
            return e
        if t == "CORCHETE_IZQ":
            self.consumir()
            elems = []
            if not self.es("CORCHETE_DER"):
                elems.append(self.expresion())
                while self.es("COMA"):
                    self.consumir()
                    elems.append(self.expresion())
            self.esperar("CORCHETE_DER", "']'")
            return Lista(tok.linea, elems)
        if t == "KW_DESPLEGAR":
            self.consumir()
            nombre = self.esperar("ID", "el nombre de un módulo")
            return Nuevo(tok.linea, nombre.lexema, self.argumentos())
        self.error("una expresión")


def analizar_sintaxis(tokens):
    return Parser(tokens).programa()
