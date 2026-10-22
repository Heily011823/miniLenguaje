"""Analizador sintáctico (descenso recursivo) de Tramo.

Implementa la gramática EBNF y construye el AST.
Se detiene en el primer error sintáctico y lo reporta con su línea.
"""
from nodos import *

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def desescapar(texto):
    """ Convierte las secuencias de escape en sus caracteres correspondientes.

    Parámetros:
        texto: cadena que contiene las secuencias de escape.

    Retorna:
        La cadena con las secuencias de escape interpretadas.
    """
    salida, i = [], 0
    while i < len(texto):
        c = texto[i]
        if c == "\\" and i + 1 < len(texto):
            sig = texto[i + 1]
            salida.append(ESCAPES.get(sig, "\\" + sig))
            i += 2
        else:
            salida.append(c)
            i += 1
    return "".join(salida)


class ErrorSintactico(Exception):
    def __init__(self, linea, mensaje):
        """ Inicializa un error sintáctico con su línea y descripción.

        Parámetros:
            linea: número de línea donde se detectó el error.
            mensaje: descripción del error encontrado.
        """
        super().__init__(mensaje)
        self.linea = linea
        self.mensaje = mensaje


class Parser:
    DESPACHO = {
        "KW_CARGAR": "declaracion", "KW_NOTIFICAR": "impresion",
        "KW_ESCANEAR": "lectura", "KW_EVALUAR": "condicional",
        "KW_PATRULLAR": "ciclo_mientras", "KW_RECORRER": "ciclo_para",
        "KW_RONDAR": "ciclo_rondar", "KW_BIFURCAR": "bifurcar",
        "KW_TAREA": "funcion", "KW_ENTREGAR": "retorno",
        "KW_MODULO": "clase", "KW_INTENTAR_RUTA": "excepcion",
        "KW_ALERTA": "lanzar", "KW_DETENER": "sentencia_detener", "KW_AVANZAR": "sentencia_avanzar",
    }
    INICIO_EXPRESION_SENTENCIA = ("ID", "KW_MISMO", "KW_SUPERIOR", "KW_DESPLEGAR")

    def __init__(self, tokens):
        """ Inicializa el analizador sintáctico.

        Parámetros:
            tokens: lista de tokens generados por el analizador léxico.
        """
        self.tokens = tokens
        self.pos = 0

    # ---------- utilidades ----------
    @property
    def actual(self):
        """ Devuelve el token en la posición actual. """
        return self.tokens[self.pos]

    def consumir(self):
        """ Devuelve el token actual y avanza al siguiente.

        El token EOF se conserva como marcador del final del archivo.
        """
        tok = self.tokens[self.pos]
        if tok.tipo != "EOF":
            self.pos += 1
        return tok

    def es(self, *tipos):
        """ Comprueba si el token actual coincide con alguno de los tipos.
        
        Parámetros:
            *tipos: tipos de tokens que se desean comprobar.

        Retorna:
            True si el tipo actual coincide con alguno de los tipos indicados y 
            False en caso contrario.
        """
        return self.actual.tipo in tipos

    def error(self, esperado):
        """ Genera un error sintáctico indicando qué elemento se esperaba.

        Parámetros:
            esperado: descripción del token o elemento esperado.

        Genera:
            ErrorSintactico: incluye la línea y el mensaje del error.
        """
        tok = self.actual
        if tok.tipo == "EOF":
            msg = "se esperaba %s pero se llegó al final del archivo" % esperado
        else:
            msg = "se esperaba %s pero se encontró '%s'" % (esperado, tok.lexema)
        raise ErrorSintactico(tok.linea, msg)

    def esperar(self, tipo, esperado):
        """ Comprueba el tipo del token actual y lo consume si coincide.

        Parámetros:
            tipo: tipo de token requerido.
            esperado: descripción del elemento esperado.

        Retorna:
            El token consumido si coincide con el tipo indicado.

        Genera:
            ErrorSintactico si el token actual no es del tipo correcto.
        """
        if self.actual.tipo == tipo:
            return self.consumir()
        self.error(esperado)

    # ---------- programa y sentencias ----------
    def programa(self):
        """ Analiza las sentencias del programa hasta llegar al final del archivo.

        Retorna:
            Lista de sentencias que forman el programa.
        """
        sentencias = []
        while not self.es("EOF"):
            sentencias.append(self.sentencia())
        return sentencias

    def bloque(self, terminadores, esperado="'fin_sendero'"):
        """ Analiza un bloque de sentencias hasta encontrar un terminador.

        Parámetros:
            terminadores: tipos de tokens que indican el final del bloque.
            esperado: descripción del terminador esperado si se alcanza EOF.

        Retorna:
            Lista de sentencias que forman el bloque.
        """
        sentencias = []
        while not self.es(*terminadores):
            if self.es("EOF"):
                self.error(esperado)
            sentencias.append(self.sentencia())
        return sentencias

    def sentencia(self):
        """ Identifica y analiza una sentencia según el token actual.

        Retorna:
            El nodo sintáctico correspondiente a la sentencia.

        Genera:
            ErrorSintactico si el token no puede iniciar una sentencia válida.
        """
        tipo = self.actual.tipo
        metodo = self.DESPACHO.get(tipo)
        if metodo:
            return getattr(self, metodo)()
        if tipo in self.INICIO_EXPRESION_SENTENCIA:
            return self.asignacion_o_llamada()
        raise ErrorSintactico(self.actual.linea,
                              "no se esperaba '%s' en este lugar" % self.actual.lexema)

    def declaracion(self):
        """ Analiza una declaración de variable con o sin valor inicial.

        Retorna:
            Un nodo Declarar con la línea, el nombre y el valor inicial.
        """
        tok = self.consumir()
        nombre = self.esperar("ID", "un nombre de variable")
        valor = None
        if self.es("KW_EN"):
            self.consumir()
            valor = self.expresion()
        else:
            if not self.es("PUNTO_COMA"):
                self.error("'en' o ';'")
        self.esperar("PUNTO_COMA", "';'")
        return Declarar(tok.linea, nombre.lexema, valor)

    def asignacion_o_llamada(self):
        """ Analiza una asignación o una llamada utilizada como sentencia.

        Comprueba que el destino de una asignación sea una variable,
        un atributo o un elemento de una lista.

        Retorna:
            Un nodo Asignar o ExprSentencia, según la instrucción que se analiza.
        """
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
        if not isinstance(nodo, (Llamada, LlamadaMetodo, Super, Nuevo)):
            self.error("'en' o una llamada a función")
        self.esperar("PUNTO_COMA", "';'")
        return ExprSentencia(inicio.linea, nodo)

    def impresion(self):
        """ Analiza una instrucción que muestra el resultado de una expresión.

        Retorna:
            Un nodo Imprimir con la línea y la expresión que se mostrará.
        """
        tok = self.consumir()
        self.esperar("PAREN_IZQ", "'('")
        valor = self.expresion()
        self.esperar("PAREN_DER", "')'")
        self.esperar("PUNTO_COMA", "';'")
        return Imprimir(tok.linea, valor)

    def lectura(self):
        """ Analiza una instrucción que recibe un dato y lo guarda en un destino.

        Retorna:
            Un nodo Leer con la línea y el destino del dato.
        """
        tok = self.consumir()
        self.esperar("PAREN_IZQ", "'('")
        inicio = self.actual
        destino = self.primario()
        if not isinstance(destino, (Var, Atributo, Indice)):
            raise ErrorSintactico(inicio.linea, "'preguntar' necesita una variable, un elemento "
                                  "de lista o un atributo")
        self.esperar("PAREN_DER", "')'")
        self.esperar("PUNTO_COMA", "';'")
        return Leer(tok.linea, destino)

    def condicional(self):
        """ Analiza una estructura condicional con ramas alternativas opcionales.

        Retorna:
            Un nodo Si con las condiciones, sus bloques y el bloque alternativo,
            si existe.
        """
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
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Si(tok.linea, ramas, sino)

    def ciclo_mientras(self):
        """ Analiza un ciclo que se repite mientras una condición sea verdadera.

        Retorna:
            Un nodo Mientras con la condición y el cuerpo del ciclo.
        """
        tok = self.consumir()
        cond = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Mientras(tok.linea, cond, cuerpo)

    def ciclo_rondar(self):
        """ Analiza un ciclo que ejecuta el cuerpo antes de comprobar la condición.

        Retorna:
            Un nodo Rondar con el cuerpo y la condición del ciclo.
        """
        tok = self.consumir()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_REPETIR_SI",), "'repetir_si'")
        self.esperar("KW_REPETIR_SI", "'repetir_si'")
        cond = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Rondar(tok.linea, cuerpo, cond)

    def ciclo_para(self):
        """ Analiza un ciclo con variable de control, inicio y límite.

        Retorna:
            Un nodo Para con la variable, los límites y el cuerpo del ciclo.
        """
        tok = self.consumir()
        var = self.esperar("ID", "el nombre de la variable del ciclo")
        self.esperar("KW_PARTIENDO_DE", "'partiendo_de'")
        desde = self.expresion()
        self.esperar("KW_LLEGANDO_A", "'llegando_a'")
        hasta = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Para(tok.linea, var.lexema, desde, hasta, cuerpo)

    def bifurcar(self):
        """ Analiza una estructura de selección con varios casos y un caso por defecto.

        Retorna:
            Un nodo Bifurcar con la expresión, los casos y el bloque por defecto.
        """
        tok = self.consumir()
        expr = self.expresion()
        self.esperar("DOS_PUNTOS", "':'")
        fin_caso = ("KW_PUNTO_RUTA", "KW_RUTA_BASE", "KW_FIN_RUTA")
        casos, defecto = [], None
        while self.es("KW_PUNTO_RUTA"):
            self.consumir()
            valor = self.expresion()
            self.esperar("DOS_PUNTOS", "':'")
            casos.append((valor, self.bloque(fin_caso)))
        if self.es("KW_RUTA_BASE"):
            self.consumir()
            self.esperar("DOS_PUNTOS", "':'")
            defecto = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'mirador', 'sendero_base' o 'fin_sendero'")
        return Bifurcar(tok.linea, expr, casos, defecto)

    def parametros(self):
        """ Analiza una lista de nombres de parámetros separados por comas.

        Retorna:
            Lista de nombres de parámetros.
        """
        params = []
        if self.es("ID"):
            params.append(self.consumir().lexema)
            while self.es("COMA"):
                self.consumir()
                params.append(self.esperar("ID", "un nombre de parámetro").lexema)
        return params

    def funcion(self):
        """ Analiza la definición de una función y su cuerpo.

        Retorna:
            Un nodo Funcion con el nombre, los parámetros y las instrucciones.
        """
        tok = self.consumir()
        nombre = self.esperar("ID", "el nombre del trayecto")
        self.esperar("PAREN_IZQ", "'('")
        params = self.parametros()
        self.esperar("PAREN_DER", "')'")
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_FIN_RUTA",))
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Funcion(tok.linea, nombre.lexema, params, cuerpo)

    def retorno(self):
        """ Analiza una instrucción que devuelve el resultado de una expresión.

        Retorna:
            Un nodo Retorno con el valor que se devuelve.
        """
        tok = self.consumir()
        valor = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Retorno(tok.linea, valor)

    def clase(self):
        """ Analiza la definición de una clase, sus atributos y sus métodos.

        También procesa la herencia y la definición opcional del constructor.

        Retorna:
            Un nodo Clase con el nombre, el padre, el constructor,
            los métodos y los atributos de la clase.
        """
        tok = self.consumir()
        nombre = self.esperar("ID", "el nombre del campamento")
        padre = None
        if self.es("KW_EXTIENDE"):
            self.consumir()
            padre = self.esperar("ID", "el nombre del campamento padre").lexema
        self.esperar("DOS_PUNTOS", "':'")
        params, cuerpo, metodos, campos = None, [], [], []
        while not self.es("KW_FIN_RUTA"):
            if self.es("EOF"):
                self.error("'fin_sendero'")
            if self.es("KW_ENSAMBLAR"):
                if params is not None:
                    raise ErrorSintactico(self.actual.linea, "el campamento ya tiene un 'armar'")
                self.consumir()
                self.esperar("PAREN_IZQ", "'('")
                params = self.parametros()
                self.esperar("PAREN_DER", "')'")
                self.esperar("DOS_PUNTOS", "':'")
                cuerpo = self.bloque(("KW_FIN_RUTA",))
                self.esperar("KW_FIN_RUTA", "'fin_sendero'")
            elif self.es("KW_TAREA"):
                metodos.append(self.funcion())
            elif self.es("KW_CARGAR"):
                campos.append(self.declaracion())
            else:
                self.error("'armar', 'trayecto', 'cargar' o 'fin_sendero'")
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Clase(tok.linea, nombre.lexema, padre, params, cuerpo, metodos, campos)

    def excepcion(self):
        """ Analiza una estructura para intentar ejecutar código y gestionar excepciones.

        Retorna:
            Un nodo Intentar con el cuerpo principal, el bloque de captura
            y el bloque final, cuando están presentes.
        """
        tok = self.consumir()
        self.esperar("DOS_PUNTOS", "':'")
        cuerpo = self.bloque(("KW_OBSTACULO", "KW_DESTINO", "KW_FIN_RUTA"), "'imprevisto'")
        var, capturar, final = None, None, None
        if self.es("KW_OBSTACULO"):
            self.consumir()
            if self.es("ID"):
                var = self.consumir().lexema
            self.esperar("DOS_PUNTOS", "':'")
            capturar = self.bloque(("KW_DESTINO", "KW_FIN_RUTA"))
        if self.es("KW_DESTINO"):
            self.consumir()
            self.esperar("DOS_PUNTOS", "':'")
            final = self.bloque(("KW_FIN_RUTA",))
        if capturar is None and final is None:
            self.error("'imprevisto' o 'recoger'")
        self.esperar("KW_FIN_RUTA", "'fin_sendero'")
        return Intentar(tok.linea, cuerpo, var, capturar, final)

    def lanzar(self):
        """ Analiza una instrucción que lanza una excepción.

        Retorna:
            Un nodo Lanzar con la expresión que representa el valor lanzado.
        """
        tok = self.consumir()
        valor = self.expresion()
        self.esperar("PUNTO_COMA", "';'")
        return Lanzar(tok.linea, valor)

    def sentencia_detener(self):
        """ Analiza la instrucción que interrumpe un ciclo.

        Retorna:
            Un nodo Romper.
        """
        tok = self.consumir()
        self.esperar("PUNTO_COMA", "';'")
        return Romper(tok.linea)

    def sentencia_avanzar(self):
        """ Analiza la instrucción que pasa a la siguiente iteración de un ciclo.

        Retorna:
            Un nodo Continuar.
        """
        tok = self.consumir()
        self.esperar("PUNTO_COMA", "';'")
        return Continuar(tok.linea)

    # ---------- expresiones (de menor a mayor precedencia) ----------
    def expresion(self):
        """ Inicia el análisis de una expresión lógica."""
        return self.expr_logica()

    def expr_logica(self):
        """ Analiza expresiones con el operador lógico 'o'.

        Retorna:
            El nodo de la expresión lógica construida.
        """
        izq = self.expr_y()
        while self.es("KW_O"):
            tok = self.consumir()
            izq = Binario(tok.linea, "o", izq, self.expr_y())
        return izq

    def expr_y(self):
        """ Analiza expresiones con el operador lógico 'y'.

        Retorna:
            El nodo de la expresión lógica que se construyó.
        """
        izq = self.expr_no()
        while self.es("KW_Y"):
            tok = self.consumir()
            izq = Binario(tok.linea, "y", izq, self.expr_no())
        return izq

    def expr_no(self):
        """ Analiza el operador lógico unario 'no' o continúa con una comparación."""
        if self.es("KW_NO"):
            tok = self.consumir()
            return Unario(tok.linea, "no", self.expr_no())
        return self.expr_relacional()

    def expr_relacional(self):
        """ Analiza una comparación entre dos expresiones aritméticas.

        Retorna:
            Un nodo Binario si hay un operador relacional; de lo contrario,
            devuelve la expresión aritmética.
        """
        izq = self.expr_aritmetica()
        if self.es("OP_REL"):
            tok = self.consumir()
            return Binario(tok.linea, tok.lexema, izq, self.expr_aritmetica())
        return izq

    def expr_aritmetica(self):
        """ Analiza sumas y restas, respetando la precedencia de los operadores.

        Retorna:
            El nodo que representa la expresión aritmética.
        """
        izq = self.termino()
        while self.es("OP_ARITH") and self.actual.lexema in ("+", "-"):
            tok = self.consumir()
            izq = Binario(tok.linea, tok.lexema, izq, self.termino())
        return izq

    def termino(self):
        """ Analiza multiplicaciones, divisiones y operaciones de módulo.

        Retorna:
            El nodo que representa el término aritmético.
        """
        izq = self.unario()
        while self.es("OP_ARITH") and self.actual.lexema in ("*", "/", "%"):
            tok = self.consumir()
            izq = Binario(tok.linea, tok.lexema, izq, self.unario())
        return izq

    def unario(self):
        """ Analiza el signo negativo unario o continúa con un elemento primario. """
        if self.es("OP_ARITH") and self.actual.lexema == "-":
            tok = self.consumir()
            return Unario(tok.linea, "-", self.unario())
        return self.primario()

    def primario(self):
        """ Analiza un elemento primario y sus posibles accesos encadenados.

        Puede procesar atributos, llamadas a métodos e índices de listas.

        Retorna:
            El nodo que representa el elemento primario completo.
        """
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
        """ Consume '(' [expresion {',' expresion}] ')'."""
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
        """ Analiza el elemento básico de una expresión.

        Reconoce identificadores, números, cadenas, valores booleanos,
        valores nulos, referencias al objeto actual o a la clase padre,
        expresiones entre paréntesis, listas y creación de objetos.

        Retorna:
            El nodo correspondiente al elemento reconocido.

        Genera:
            ErrorSintactico si el token actual no puede formar una expresión.
        """
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
            return Literal(tok.linea, desescapar(tok.lexema[1:-1]))
        if t == "BOOLEAN":
            self.consumir()
            return Literal(tok.linea, tok.lexema == "verdadero")
        if t == "KW_NULO":
            self.consumir()
            return Literal(tok.linea, None)
        if t == "KW_MISMO":
            self.consumir()
            return Mismo(tok.linea)
        if t == "KW_SUPERIOR":
            self.consumir()
            self.esperar("PUNTO", "'.'")
            if self.es("ID", "KW_ENSAMBLAR"):
                nombre = self.consumir().lexema
            else:
                self.error("un nombre de método")
            return Super(tok.linea, nombre, self.argumentos())
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
            nombre = self.esperar("ID", "el nombre de un campamento")
            return Nuevo(tok.linea, nombre.lexema, self.argumentos())
        self.error("una expresión")


def analizar_sintaxis(tokens):
    """ Analiza una lista de tokens y devuelve el AST del programa.

    Parámetros:
        tokens: lista de tokens generados por el analizador léxico.

    Retorna:
        Lista de nodos que representan las sentencias del programa.

    Genera:
        ErrorSintactico si se encuentra una estructura que no cumple
        la gramática.
    """
    return Parser(tokens).programa()
