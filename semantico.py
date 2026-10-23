"""Análisis semántico estático de Tramo (se ejecuta antes del intérprete).

Detecta, sin ejecutar el programa:
  * variables usadas sin declarar,
  * trayectos o campamentos inexistentes y número de argumentos incorrecto,
  * tipos incompatibles cuando se conocen con seguridad (p. ej. "a" - 1),
  * 'regresar' fuera de un trayecto, 'detener'/'avanzar' fuera de un ciclo,
  * 'mismo' / 'superior' fuera de un campamento.

Es CONSERVADOR: solo reporta cuando está seguro de que el programa fallaría.
Lo encontrado dentro de un 'explorar' se informa como advertencia (no
detiene la ejecución), porque el programador pudo querer capturar ese error.
"""

from nodos import *
from interprete import ARIDAD_PREDEFINIDAS, nombre_tipo

# Tipos de retorno de las funciones predefinidas que tienen un tipo conocido.
TIPO_RETORNO = {"longitud": "entero", "entero": "entero", "real": "real", "texto": "texto"}

# Tipos de datos que representan números.
NUMERICOS = ("entero", "real")


def es_num(t):
    """Comprueba si un tipo de dato es numérico.

    Parámetros:
        t: Nombre del tipo de dato que se quiere comprobar.

    Retorna:
        True si el tipo es 'entero' o 'real'; False en caso contrario.
    """
    return t in NUMERICOS


class Ambito:
    """Guarda información sobre las variables de una parte del programa.

    Permite registrar qué variables existen y qué tipos de datos se conocen
    para ellas. Puede representar el ámbito global o uno local.
    """

    def __init__(self, es_global=False):
        """Inicializa un ámbito vacío.

        Parámetros:
            es_global: Indica si el ámbito corresponde al programa completo.
        """
        self.es_global = es_global
        self.locales = set()          # nombres propios de este ámbito
        self.tipos = {}               # nombre -> conjunto de tipos asignados (None = desconocido)
        self.declarados = set()       # declarados hasta el punto actual (orden textual)

    def agregar_tipo(self, nombre, tipo):
        """Registra un tipo de dato posible para una variable.

        Parámetros:
            nombre: Nombre de la variable.
            tipo: Tipo de dato que se quiere registrar.
        """
        self.tipos.setdefault(nombre, set()).add(tipo)


class Analizador:
    """Analiza el programa de Tramo para detectar errores semánticos.

    Revisa las declaraciones, los ámbitos, las instrucciones y las expresiones
    antes de que el intérprete ejecute el programa.
    """

    def __init__(self, programa):
        """Prepara el analizador para revisar un programa.

        Parámetros:
            programa: Lista de nodos que representan el código de Tramo.
        """
        self.programa = programa
        self.errores = []             # (linea, mensaje)
        self.avisos = []
        self.mudo = False
        self.try_prof = 0
        self.bucles = 0
        self.switches = 0
        self.en_funcion = False
        self.clase_actual = None      # Clase (nodo) mientras se analiza un campamento
        self.glob = Ambito(True)
        self.funciones = {}           # nombre -> nº de parámetros (None si hay ambigüedad)
        self.anidadas = set()         # trayectos declarados dentro de otros trayectos o métodos
        self.clases = {}              # nombre -> nodo Clase

    # ------------------------------------------------------------------ API
    def analizar(self):
        """Ejecuta todas las etapas del análisis semántico.

        Recopila las declaraciones, prepara la información global y revisa
        las instrucciones del programa.

        Retorna:
            Una tupla con dos listas: los errores y los avisos encontrados.
        """
        self.recolectar_declaraciones(self.programa, top=True)
        self.nombres_anidados(self.programa)
        self.preparar_global()
        self.glob.declarados = set(self.funciones) | set(self.clases)
        self.mudo = False
        self.bloque(self.programa, self.glob)
        return self.errores, self.avisos

    def err(self, linea, msg):
        """Registra un error o una advertencia.

        Los problemas se guardan como errores, excepto cuando aparecen
        dentro de un bloque 'explorar', donde se guardan como avisos.

        Parámetros:
            linea: Número de línea donde se encontró el problema.
            msg: Descripción del problema detectado.
        """
        if self.mudo:
            return
        destino = self.avisos if self.try_prof > 0 else self.errores
        if (linea, msg) not in destino:
            destino.append((linea, msg))

    # ------------------------------------------------ recolección (pre-pasada)

    def recorrer(self, sentencias, fn):
        """Recorre las instrucciones y sus bloques internos.

        Aplica una función a cada instrucción y entra en los bloques
        condicionales, ciclos, bifurcaciones y bloques de control de errores.
        No entra automáticamente en los cuerpos de trayectos o campamentos.

        Parámetros:
            sentencias: Instrucciones que se van a recorrer.
            fn: Función que se ejecuta para cada instrucción.
        """
        for s in sentencias:
            fn(s)
            if isinstance(s, Si):
                for _, b in s.ramas: self.recorrer(b, fn)
                if s.sino: self.recorrer(s.sino, fn)
            elif isinstance(s, (Mientras, Para, Rondar)):
                self.recorrer(s.cuerpo, fn)
            elif isinstance(s, Bifurcar):
                for _, b in s.casos: self.recorrer(b, fn)
                if s.defecto: self.recorrer(s.defecto, fn)
            elif isinstance(s, Intentar):
                self.recorrer(s.cuerpo, fn)
                if s.capturar: self.recorrer(s.capturar, fn)
                if s.final: self.recorrer(s.final, fn)

    def recolectar_declaraciones(self, sentencias, top):
        """Recopila las declaraciones de trayectos y campamentos.

        Guarda los campamentos encontrados y registra cuántos parámetros
        recibe cada trayecto para poder comprobar sus llamadas.

        Parámetros:
            sentencias: Instrucciones que se van a revisar.
            top: Indicador que recibe el método para señalar el nivel del análisis.
        """
        cuenta = {}

        def ver(s): 
            """Registra las declaraciones encontradas durante el recorrido.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Funcion):
                cuenta.setdefault(s.nombre, []).append(len(s.params))
            elif isinstance(s, Clase):
                self.clases[s.nombre] = s
        self.recorrer(sentencias, ver)
        for nombre, lista in cuenta.items():
            self.funciones[nombre] = lista[0] if len(set(lista)) == 1 and len(lista) == 1 else None

    def nombres_anidados(self, sentencias, dentro=False):
        """Identifica los trayectos declarados dentro de otros bloques.

        Guarda los nombres de los trayectos anidados para distinguirlos
        de los trayectos que están declarados en el nivel global.

        Parámetros:
            sentencias: Instrucciones que se van a revisar.
            dentro: Indica si las instrucciones están dentro de otro trayecto o campamento.
        """
        def ver(s): 
            """Identifica trayectos y campamentos anidados.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Funcion):
                if dentro:
                    self.anidadas.add(s.nombre)
                self.nombres_anidados(s.cuerpo, True)
            elif isinstance(s, Clase):
                self.nombres_anidados(s.cuerpo_ctor, True)
                for m in s.metodos:
                    self.nombres_anidados(m.cuerpo, True)
        self.recorrer(sentencias, ver)

    def todas_las_funciones(self):
        """Obtiene los parámetros y cuerpos de los trayectos, constructores y métodos.

        Reúne esta información para poder revisar cómo las funciones
        pueden afectar a las variables globales.

        Retorna:
            Una lista de tuplas con los parámetros y el cuerpo de cada función.
        """
        res = []

        def ver(s): 
            """Recopila los parámetros y cuerpos de las funciones declaradas.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Funcion):
                res.append((s.params, s.cuerpo))
            elif isinstance(s, Clase):
                if s.params_ctor is not None:
                    res.append((s.params_ctor, s.cuerpo_ctor))
                for m in s.metodos:
                    res.append((m.params, m.cuerpo))
        self.recorrer(self.programa, ver)
        return res

    def tipo_silencioso(self, e, amb):
        """Obtiene el tipo de una expresión sin registrar errores.

        Activa temporalmente el modo silencioso, analiza la expresión y
        restaura el estado anterior del analizador.

        Parámetros:
            e: Expresión cuyo tipo se quiere conocer.
            amb: Ámbito donde aparece la expresión.

        Retorna:
            El tipo de la expresión, o None si no se puede determinar.
        """
        previo = self.mudo
        self.mudo = True
        try:
            return self.expr(e, amb)
        finally:
            self.mudo = previo

    def preparar_global(self):
        """Recopila información sobre las variables del ámbito global.

        Busca las variables declaradas y registra los tipos que se pueden
        deducir de sus valores iniciales y de sus asignaciones. También tiene
        en cuenta las modificaciones que pueden hacerse desde funciones.
        """
        g = self.glob

        def ver(s): 
            """Registra las variables globales y sus tipos conocidos.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Declarar):
                g.locales.add(s.nombre)
                g.agregar_tipo(s.nombre, "nulo" if s.valor is None else self.tipo_silencioso(s.valor, g))
            elif isinstance(s, Para):
                g.locales.add(s.var)
                g.agregar_tipo(s.var, "entero")
            elif isinstance(s, Intentar) and s.var_error:
                g.locales.add(s.var_error)
                g.agregar_tipo(s.var_error, None)
            elif isinstance(s, Leer) and isinstance(s.destino, Var):
                g.locales.add(s.destino.nombre)
                g.agregar_tipo(s.destino.nombre, None)
        self.recorrer(self.programa, ver)

        def asignaciones(s):
            if isinstance(s, Asignar) and isinstance(s.destino, Var) and s.destino.nombre in g.locales:
                g.agregar_tipo(s.destino.nombre, self.tipo_silencioso(s.valor, g))
        self.recorrer(self.programa, asignaciones)

        # Asignaciones a variables globales hechas desde dentro de trayectos/métodos
        for params, cuerpo in self.todas_las_funciones():
            loc = self.locales_de(params, cuerpo)

            def desde_funcion(s, loc=loc): #
                if isinstance(s, Asignar) and isinstance(s.destino, Var):
                    if s.destino.nombre not in loc and s.destino.nombre in g.locales:
                        g.agregar_tipo(s.destino.nombre, None)
                elif isinstance(s, Leer) and isinstance(s.destino, Var):
                    if s.destino.nombre not in loc and s.destino.nombre in g.locales:
                        g.agregar_tipo(s.destino.nombre, None)
            self.recorrer(cuerpo, desde_funcion)

    def locales_de(self, params, cuerpo):
        """Obtiene los nombres de las variables locales de una función.

        Incluye los parámetros, las variables declaradas, las variables
        de los ciclos y las variables utilizadas para leer o capturar errores.

        Parámetros:
            params: Parámetros que recibe la función.
            cuerpo: Instrucciones que forman el cuerpo de la función.

        Retorna:
            Un conjunto con los nombres de las variables locales.
        """
        loc = set(params)

        def ver(s): 
            """Identifica las variables locales declaradas o utilizadas.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Declarar):
                loc.add(s.nombre)
            elif isinstance(s, Para):
                loc.add(s.var)
            elif isinstance(s, Intentar) and s.var_error:
                loc.add(s.var_error)
            elif isinstance(s, Leer) and isinstance(s.destino, Var):
                if s.destino.nombre not in self.glob.locales:
                    loc.add(s.destino.nombre)
        self.recorrer(cuerpo, ver)
        return loc

    def ambito_funcion(self, params, cuerpo, externo=None):
        """Prepara el ámbito local de una función.

        Registra las variables locales, sus tipos conocidos y los nombres
        que pueden utilizarse dentro de la función.

        Parámetros:
            params: Parámetros que recibe la función.
            cuerpo: Instrucciones que forman su cuerpo.
            externo: Ámbito exterior opcional del que se pueden conocer nombres.

        Retorna:
            Un objeto Ambito con la información de las variables de la función.
        """
        amb = Ambito()
        amb.locales = self.locales_de(params, cuerpo)
        for p in params:
            amb.agregar_tipo(p, None)

        def ver(s): 
            """Registra los tipos conocidos de las variables locales.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Declarar):
                amb.agregar_tipo(s.nombre, "nulo" if s.valor is None else self.tipo_silencioso(s.valor, amb))
            elif isinstance(s, Para):
                amb.agregar_tipo(s.var, "entero")
            elif isinstance(s, Intentar) and s.var_error:
                amb.agregar_tipo(s.var_error, None)
            elif isinstance(s, Leer) and isinstance(s.destino, Var) and s.destino.nombre in amb.locales:
                amb.agregar_tipo(s.destino.nombre, None)
        self.recorrer(cuerpo, ver)

        def asign(s): 
            """Registra los tipos de las variables locales que reciben asignaciones.

            Parámetros:
                s: Instrucción que se está revisando.
            """
            if isinstance(s, Asignar) and isinstance(s.destino, Var) and s.destino.nombre in amb.locales:
                amb.agregar_tipo(s.destino.nombre, self.tipo_silencioso(s.valor, amb))
        self.recorrer(cuerpo, asign)
        amb.declarados = set(params) | set(self.glob.locales) | set(self.funciones) | set(self.clases)
        if externo is not None:
            amb.declarados |= externo.declarados | externo.locales
        return amb

    # -------------------------------------------------------------- sentencias
    def bloque(self, sentencias, amb):
        """Analiza las instrucciones de un bloque.

        Para cada instrucción, llama al método que corresponde al tipo
        de nodo recibido.

        Parámetros:
            sentencias: Lista de instrucciones que se van a analizar.
            amb: Ámbito donde se encuentran las instrucciones.
        """
        for s in sentencias:
            getattr(self, "s_" + type(s).__name__)(s, amb)

    def s_Declarar(self, n, amb):
        """Analiza la declaración de una variable.

        Comprueba el valor inicial, si existe, y registra el nombre
        de la variable como declarado.

        Parámetros:
            n: Nodo que representa la declaración.
            amb: Ámbito donde se declara la variable.
        """
        if n.valor is not None:
            self.expr(n.valor, amb)
        amb.declarados.add(n.nombre)

    def s_Asignar(self, n, amb):
        """Analiza una asignación y comprueba que su destino esté declarado.

        Parámetros:
            n: Nodo que representa la asignación.
            amb: Ámbito donde aparece la asignación.
        """
        self.expr(n.valor, amb)
        d = n.destino
        if isinstance(d, Var):
            if d.nombre not in amb.declarados:
                self.err(n.linea, "variable '%s' no declarada (use 'cargar')" % d.nombre)
        else:
            self.expr(d, amb)

    def s_Imprimir(self, n, amb):
        """Analiza la expresión que se quiere imprimir.

        Parámetros:
            n: Nodo de la instrucción de impresión.
            amb: Ámbito donde aparece la instrucción.
        """
        self.expr(n.valor, amb)

    def s_Leer(self, n, amb):
        """Analiza una instrucción de lectura.

        Si el destino es una variable, la registra como declarada.
        Si es otra expresión, analiza esa expresión.

        Parámetros:
            n: Nodo de la instrucción de lectura.
            amb: Ámbito donde aparece la instrucción.
        """
        d = n.destino
        if isinstance(d, Var):
            amb.declarados.add(d.nombre)
        else:
            self.expr(d, amb)

    def s_Si(self, n, amb):
        """Analiza las condiciones y los bloques de una estructura condicional.

        Parámetros:
            n: Nodo de la estructura 'si'.
            amb: Ámbito donde aparece la estructura.
        """
        for cond, cuerpo in n.ramas:
            self.expr(cond, amb)
            self.bloque(cuerpo, amb)
        if n.sino is not None:
            self.bloque(n.sino, amb)

    def s_Mientras(self, n, amb):
        """Analiza un ciclo que se repite mientras se cumpla una condición.

        Registra temporalmente que el análisis se encuentra dentro de un ciclo.

        Parámetros:
            n: Nodo del ciclo.
            amb: Ámbito donde aparece el ciclo.
        """
        self.expr(n.cond, amb)
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1

    def s_Rondar(self, n, amb):
        """Analiza un ciclo que comprueba su condición al final.

        Parámetros:
            n: Nodo del ciclo.
            amb: Ámbito donde aparece el ciclo.
        """
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1
        self.expr(n.cond, amb)

    def s_Para(self, n, amb):
        """Analiza un ciclo que recorre un rango de valores.

        Comprueba que sus límites sean enteros cuando se conoce su tipo
        y registra la variable del ciclo como declarada.

        Parámetros:
            n: Nodo del ciclo 'para'.
            amb: Ámbito donde aparece el ciclo.
        """
        for lado in (n.desde, n.hasta):
            t = self.expr(lado, amb)
            if t is not None and t != "entero":
                self.err(n.linea, "los límites de 'recorrer' deben ser enteros (se encontró %s)" % t)
        amb.declarados.add(n.var)
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1

    def s_Bifurcar(self, n, amb):
        """Analiza una estructura que selecciona entre distintos casos.

        Revisa la expresión principal, los valores de los casos y sus bloques.

        Parámetros:
            n: Nodo de la estructura 'bifurcar'.
            amb: Ámbito donde aparece la estructura.
        """
        self.expr(n.expr, amb)
        self.switches += 1
        for valor, cuerpo in n.casos:
            self.expr(valor, amb)
            self.bloque(cuerpo, amb)
        if n.defecto is not None:
            self.bloque(n.defecto, amb)
        self.switches -= 1

    def entrar_funcion(self, params, cuerpo, amb, clase=None):
        """Analiza el cuerpo de un trayecto, constructor o método.

        Prepara un ámbito local y reinicia temporalmente los contadores
        de ciclos, bifurcaciones y bloques 'explorar'. Al terminar, restaura
        el estado que tenía el analizador antes de entrar en la función.

        Parámetros:
            params: Parámetros que recibe la función.
            cuerpo: Instrucciones que forman el cuerpo.
            amb: Ámbito desde el que se encontró la función.
            clase: Campamento al que pertenece, si corresponde.
        """
        nuevo = self.ambito_funcion(params, cuerpo, externo=None if amb.es_global else amb)
        guardado = (self.en_funcion, self.bucles, self.switches, self.try_prof, self.clase_actual)
        self.en_funcion, self.bucles, self.switches, self.try_prof = True, 0, 0, 0
        if clase is not None:
            self.clase_actual = clase
        self.bloque(cuerpo, nuevo)
        self.en_funcion, self.bucles, self.switches, self.try_prof, self.clase_actual = guardado

    def s_Funcion(self, n, amb):
        """Analiza la declaración de un trayecto.

        Parámetros:
            n: Nodo que representa el trayecto.
            amb: Ámbito donde se declaró.
        """
        self.entrar_funcion(n.params, n.cuerpo, amb)

    def s_Retorno(self, n, amb):
        """Comprueba que 'regresar' se utilice dentro de un trayecto.

        También analiza el valor que se quiere devolver.

        Parámetros:
            n: Nodo de la instrucción 'regresar'.
            amb: Ámbito donde aparece la instrucción.
        """
        if not self.en_funcion:
            self.err(n.linea, "'regresar' solo se puede usar dentro de un trayecto")
        self.expr(n.valor, amb)

    def s_Clase(self, n, amb):
        """Analiza un campamento, sus campos, su constructor y sus métodos.

        Comprueba que el campamento padre exista y que no se intente
        extender el propio campamento. Después revisa los campos y métodos.

        Parámetros:
            n: Nodo que representa el campamento.
            amb: Ámbito donde se declaró.
        """
        if n.padre is not None:
            if n.padre not in self.clases:
                self.err(n.linea, "el campamento padre '%s' no está definido" % n.padre)
            elif n.padre == n.nombre:
                self.err(n.linea, "un campamento no puede extenderse a sí mismo")
        guardado = self.clase_actual
        self.clase_actual = n
        for campo in n.campos:
            if campo.valor is not None:
                self.expr(campo.valor, self.glob)
        if n.params_ctor is not None:
            self.entrar_funcion(n.params_ctor, n.cuerpo_ctor, amb, clase=n)
        for m in n.metodos:
            self.entrar_funcion(m.params, m.cuerpo, amb, clase=n)
        self.clase_actual = guardado

    def s_Intentar(self, n, amb):
        """Analiza un bloque 'explorar' y sus partes de captura y cierre.

        Los posibles problemas del cuerpo principal se registran como avisos.
        Después se revisan los bloques 'capturar' y 'final', si existen.

        Parámetros:
            n: Nodo de la estructura 'explorar'.
            amb: Ámbito donde aparece la estructura.
        """
        self.try_prof += 1
        self.bloque(n.cuerpo, amb)
        self.try_prof -= 1
        if n.capturar is not None:
            if n.var_error:
                amb.declarados.add(n.var_error)
            self.bloque(n.capturar, amb)
        if n.final is not None:
            self.bloque(n.final, amb)

    def s_Lanzar(self, n, amb):
        """Analiza el valor de una instrucción que lanza un error.

        Parámetros:
            n: Nodo de la instrucción que lanza el error.
            amb: Ámbito donde aparece la instrucción.
        """
        self.expr(n.valor, amb)

    def s_Romper(self, n, amb):
        """Comprueba que 'detener' esté dentro de un ciclo o un 'bifurcar'.

        Parámetros:
            n: Nodo de la instrucción 'detener'.
            amb: Ámbito donde aparece la instrucción.
        """
        if self.bucles == 0 and self.switches == 0:
            self.err(n.linea, "'detener' solo se puede usar dentro de un ciclo o un bifurcar")

    def s_Continuar(self, n, amb):
        """Comprueba que 'avanzar' esté dentro de un ciclo.

        Parámetros:
            n: Nodo de la instrucción 'avanzar'.
            amb: Ámbito donde aparece la instrucción.
        """
        if self.bucles == 0:
            self.err(n.linea, "'avanzar' solo se puede usar dentro de un ciclo")

    def s_ExprSentencia(self, n, amb):
        """Analiza una expresión utilizada como instrucción independiente.

        Parámetros:
            n: Nodo que contiene la expresión.
            amb: Ámbito donde aparece la expresión.
        """
        self.expr(n.expr, amb)

    # -------------------------------------------------------------- expresiones

    def tipo_var(self, nombre, amb):
        """Busca el tipo de dato conocido de una variable.

        Consulta el ámbito local si la variable pertenece a él y, en caso
        contrario, consulta el ámbito global.

        Parámetros:
            nombre: Nombre de la variable.
            amb: Ámbito desde el que se consulta.

        Retorna:
            El tipo de dato si se conoce con seguridad; None en caso contrario.
        """
        fuente = amb if nombre in amb.locales else self.glob
        tipos = fuente.tipos.get(nombre)
        if tipos and len(tipos) == 1:
            (t,) = tipos
            return t
        return None

    def expr(self, n, amb):
        """Analiza una expresión y determina su tipo cuando es posible.

        Selecciona el método correspondiente según el tipo de nodo recibido.

        Parámetros:
            n: Nodo de la expresión.
            amb: Ámbito donde aparece la expresión.

        Retorna:
            El tipo de la expresión si se conoce con seguridad, o None.
        """
        return getattr(self, "e_" + type(n).__name__)(n, amb)

    def e_Literal(self, n, amb):
        """Determina el tipo de dato de un valor literal.

        Parámetros:
            n: Nodo que contiene el valor literal.
            amb: Ámbito donde aparece el valor.

        Retorna:
            El tipo de dato del valor literal.
        """
        return nombre_tipo(n.valor)

    def e_Var(self, n, amb):
        """Comprueba el uso de una variable dentro de una expresión.

        Informa si la variable no ha sido declarada y, si existe, consulta
        el tipo de dato que se conoce para ella.

        Parámetros:
            n: Nodo que representa el uso de la variable.
            amb: Ámbito donde se utiliza la variable.

        Retorna:
            El tipo de dato conocido, o None si no se puede determinar.
        """
        if self.mudo:
            return None
        if n.nombre not in amb.declarados:
            self.err(n.linea, "variable '%s' no declarada" % n.nombre)
            return None
        return self.tipo_var(n.nombre, amb)

    def e_Mismo(self, n, amb):
        """Comprueba que 'mismo' se utilice dentro de un campamento.

        Parámetros:
            n: Nodo que representa la referencia 'mismo'.
            amb: Ámbito donde aparece la referencia.

        Retorna:
            None, porque esta comprobación no determina un tipo concreto.
        """
        if self.clase_actual is None:
            self.err(n.linea, "'mismo' solo se puede usar dentro de un campamento")
        return None

    def e_Lista(self, n, amb):
        """Analiza los elementos que forman una lista.

        Comprueba cada elemento para detectar posibles errores en sus expresiones.

        Parámetros:
            n: Nodo que representa la lista.
            amb: Ámbito donde aparece la lista.

        Retorna:
            El tipo 'lista'.
        """
        for x in n.elementos:
            self.expr(x, amb)
        return "lista"

    def e_Unario(self, n, amb):
        """Analiza una operación que utiliza un solo operando.

        Comprueba el tipo del operando y verifica que el signo negativo
        se aplique a un valor numérico.

        Parámetros:
            n: Nodo de la operación unaria.
            amb: Ámbito donde aparece la operación.

        Retorna:
            El tipo resultante si se conoce; None si no se puede determinar.
        """
        t = self.expr(n.operando, amb)
        if n.op == "no":
            return "booleano"
        if t is not None and not es_num(t):
            self.err(n.linea, "el operador '-' no se puede aplicar a %s" % t)
            return None
        return t

    def e_Binario(self, n, amb):
        """Analiza una operación que utiliza dos operandos.

        Comprueba los tipos de ambos operandos, identifica operaciones
        incompatibles y determina el tipo del resultado cuando es posible.

        Parámetros:
            n: Nodo de la operación binaria.
            amb: Ámbito donde aparece la operación.

        Retorna:
            El tipo resultante si se puede determinar; None en caso contrario.
        """
        ta = self.expr(n.izq, amb)
        tb = self.expr(n.der, amb)
        op = n.op
        if op in ("y", "o", "==", "!="):
            return "booleano"
        if op in (">", "<", ">=", "<="):
            if ta is not None and tb is not None:
                if not ((es_num(ta) and es_num(tb)) or (ta == tb == "texto")):
                    self.err(n.linea, "no se puede comparar %s con %s" % (ta, tb))
            return "booleano"
        if op == "+":
            if ta == "texto" or tb == "texto":
                return "texto"
            if ta is not None and tb is not None:
                if es_num(ta) and es_num(tb):
                    return "real" if "real" in (ta, tb) else "entero"
                if ta == tb == "lista":
                    return "lista"
                self.err(n.linea, "operación '+' no válida entre %s y %s" % (ta, tb))
            return None
        # - * / %
        if (ta is not None and not es_num(ta)) or (tb is not None and not es_num(tb)):
            self.err(n.linea, "operación '%s' no válida entre %s y %s" % (op, ta or "?", tb or "?"))
            return None
        if es_num(ta) and es_num(tb) and op != "/":
            return "real" if "real" in (ta, tb) else "entero"
        return None

    def e_Llamada(self, n, amb):
        """Analiza una llamada a un trayecto o a una función predefinida.

        Comprueba los argumentos y verifica que el trayecto exista y reciba
        la cantidad correcta de argumentos cuando esa información se conoce.

        Parámetros:
            n: Nodo que representa la llamada.
            amb: Ámbito donde aparece la llamada.

        Retorna:
            El tipo de retorno conocido de una función predefinida, o None
            si no se conoce el tipo de resultado.
        """
        for a in n.args:
            self.expr(a, amb)
        nombre = n.nombre
        if nombre in amb.locales or nombre in self.anidadas:
            return None                 # parámetro/variable que guarda un trayecto, o trayecto anidado
        if nombre in self.funciones:
            esperado = self.funciones[nombre]
            if esperado is not None and esperado != len(n.args):
                self.err(n.linea, "el trayecto '%s' espera %d argumento(s) y recibe %d" % (nombre, esperado, len(n.args)))
            return None
        if nombre in ARIDAD_PREDEFINIDAS:
            mini, maxi = ARIDAD_PREDEFINIDAS[nombre]
            if not (mini <= len(n.args) <= maxi):
                esp = str(mini) if mini == maxi else "%d a %d" % (mini, maxi)
                self.err(n.linea, "'%s' espera %s argumento(s) y recibe %d" % (nombre, esp, len(n.args)))
            return TIPO_RETORNO.get(nombre)
        if nombre in self.glob.locales or nombre in self.glob.declarados:
            return None
        self.err(n.linea, "el trayecto '%s' no está definido" % nombre)
        return None

    def e_LlamadaMetodo(self, n, amb):
        """Analiza una llamada a un método de un objeto.

        Comprueba el objeto sobre el que se llama al método y cada uno
        de los argumentos enviados.

        Parámetros:
            n: Nodo que representa la llamada al método.
            amb: Ámbito donde aparece la llamada.

        Retorna:
            None, porque no se determina el tipo de retorno del método.
        """
        self.expr(n.objeto, amb)
        for a in n.args:
            self.expr(a, amb)
        return None

    def e_Atributo(self, n, amb):
        """Analiza el acceso a un atributo de un objeto.

        Comprueba la expresión que representa el objeto, pero no determina
        el tipo de dato del atributo.

        Parámetros:
            n: Nodo que representa el acceso al atributo.
            amb: Ámbito donde aparece el acceso.

        Retorna:
            None, porque no se conoce el tipo del atributo.
        """
        self.expr(n.objeto, amb)
        return None

    def e_Indice(self, n, amb):
        """Analiza el acceso a un elemento mediante un índice.

        Comprueba que el objeto sea una lista o un texto y que el índice
        sea un entero, siempre que los tipos se conozcan.

        Parámetros:
            n: Nodo que representa el acceso mediante índice.
            amb: Ámbito donde aparece el acceso.

        Retorna:
            'texto' si el objeto es un texto; None en los demás casos.
        """
        tobj = self.expr(n.objeto, amb)
        tidx = self.expr(n.indice, amb)
        if tobj is not None and tobj not in ("lista", "texto"):
            self.err(n.linea, "solo se puede indexar una lista o un texto (se encontró %s)" % tobj)
        if tidx is not None and tidx != "entero":
            self.err(n.linea, "el índice debe ser un entero (se encontró %s)" % tidx)
        return "texto" if tobj == "texto" else None

    def cadena_ctor(self, nombre):
        """Busca el constructor en el campamento o en sus campamentos padres.

        Si el campamento no tiene constructor propio, continúa la búsqueda
        por la cadena de herencia.

        Parámetros:
            nombre: Nombre del campamento donde comienza la búsqueda.

        Retorna:
            Los parámetros del primer constructor encontrado, o None si no hay.
        """
        vistos = set()
        while nombre in self.clases and nombre not in vistos:
            vistos.add(nombre)
            c = self.clases[nombre]
            if c.params_ctor is not None:
                return c.params_ctor
            nombre = c.padre
        return None

    def e_Nuevo(self, n, amb):
        """Analiza la creación de un objeto de un campamento.

        Comprueba que el campamento exista y que la cantidad de argumentos
        coincida con los que necesita su constructor.

        Parámetros:
            n: Nodo que representa la creación del objeto.
            amb: Ámbito donde aparece la creación.

        Retorna:
            None, porque no se determina el tipo concreto del objeto creado.
        """
        for a in n.args:
            self.expr(a, amb)
        if n.clase not in self.clases:
            self.err(n.linea, "el campamento '%s' no está definido" % n.clase)
            return None
        params = self.cadena_ctor(n.clase)
        esperado = len(params) if params is not None else 0
        if esperado != len(n.args):
            self.err(n.linea, "el campamento '%s' espera %d argumento(s) en 'armar' y recibe %d"
                     % (n.clase, esperado, len(n.args)))
        return None

    def e_Super(self, n, amb):
        """Comprueba que 'superior' se utilice dentro de un campamento hijo.

        Analiza los argumentos y verifica que el campamento actual tenga
        un campamento padre al que pueda hacer referencia.

        Parámetros:
            n: Nodo que representa el uso de 'superior'.
            amb: Ámbito donde aparece la referencia.

        Retorna:
            None, porque esta comprobación no determina un tipo de retorno.
        """
        for a in n.args:
            self.expr(a, amb)
        if self.clase_actual is None:
            self.err(n.linea, "'superior' solo se puede usar dentro de un campamento")
        elif self.clase_actual.padre is None:
            self.err(n.linea, "el campamento '%s' no extiende a ningún otro, no puede usar 'superior'"
                     % self.clase_actual.nombre)
        return None


def analizar_semantica(programa):
    """Ejecuta el análisis semántico y ordena los resultados.

    Parámetros:
        programa: Lista de nodos que representan el programa de Tramo.

    Retorna:
        Una tupla con dos listas ordenadas: errores y avisos.
        Cada elemento contiene el número de línea y el mensaje encontrado.
    """
    errores, avisos = Analizador(programa).analizar()
    return sorted(errores), sorted(avisos)