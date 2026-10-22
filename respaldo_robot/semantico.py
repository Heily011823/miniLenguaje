"""Análisis semántico estático de Tramo (se ejecuta antes del intérprete).

Detecta, sin ejecutar el programa:
  * variables usadas sin declarar,
  * tareas o módulos inexistentes y número de argumentos incorrecto,
  * tipos incompatibles cuando se conocen con seguridad (p. ej. "a" - 1),
  * 'entregar' fuera de una tarea, 'detener'/'avanzar' fuera de un ciclo,
  * 'mismo' / 'superior' fuera de un módulo.

Es CONSERVADOR: solo reporta cuando está seguro de que el programa fallaría.
Lo encontrado dentro de un 'intentar_ruta' se informa como advertencia (no
detiene la ejecución), porque el programador pudo querer capturar ese error.
"""
from nodos import *
from interprete import ARIDAD_PREDEFINIDAS, nombre_tipo

TIPO_RETORNO = {"longitud": "entero", "entero": "entero", "real": "real", "texto": "texto"}
NUMERICOS = ("entero", "real")


def es_num(t):
    return t in NUMERICOS


class Ambito:
    def __init__(self, es_global=False):
        self.es_global = es_global
        self.locales = set()          # nombres propios de este ámbito
        self.tipos = {}               # nombre -> conjunto de tipos asignados (None = desconocido)
        self.declarados = set()       # declarados hasta el punto actual (orden textual)

    def agregar_tipo(self, nombre, tipo):
        self.tipos.setdefault(nombre, set()).add(tipo)


class Analizador:
    def __init__(self, programa):
        self.programa = programa
        self.errores = []             # (linea, mensaje)
        self.avisos = []
        self.mudo = False
        self.try_prof = 0
        self.bucles = 0
        self.switches = 0
        self.en_funcion = False
        self.clase_actual = None      # Clase (nodo) mientras se analiza un módulo
        self.glob = Ambito(True)
        self.funciones = {}           # nombre -> nº de parámetros (None si hay ambigüedad)
        self.anidadas = set()         # tareas declaradas dentro de otras tareas o métodos
        self.clases = {}              # nombre -> nodo Clase

    # ------------------------------------------------------------------ API
    def analizar(self):
        self.recolectar_declaraciones(self.programa, top=True)
        self.nombres_anidados(self.programa)
        self.preparar_global()
        self.glob.declarados = set(self.funciones) | set(self.clases)
        self.mudo = False
        self.bloque(self.programa, self.glob)
        return self.errores, self.avisos

    def err(self, linea, msg):
        if self.mudo:
            return
        destino = self.avisos if self.try_prof > 0 else self.errores
        if (linea, msg) not in destino:
            destino.append((linea, msg))

    # ------------------------------------------------ recolección (pre-pasada)
    def recorrer(self, sentencias, fn):
        """Aplica fn a cada sentencia, entrando a los bloques pero no a tareas/módulos."""
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
        cuenta = {}

        def ver(s):
            if isinstance(s, Funcion):
                cuenta.setdefault(s.nombre, []).append(len(s.params))
            elif isinstance(s, Clase):
                self.clases[s.nombre] = s
        self.recorrer(sentencias, ver)
        for nombre, lista in cuenta.items():
            self.funciones[nombre] = lista[0] if len(set(lista)) == 1 and len(lista) == 1 else None

    def nombres_anidados(self, sentencias, dentro=False):
        def ver(s):
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
        """Tareas y métodos con su cuerpo, para la pre-pasada (no entra a funciones anidadas)."""
        res = []

        def ver(s):
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
        previo = self.mudo
        self.mudo = True
        try:
            return self.expr(e, amb)
        finally:
            self.mudo = previo

    def preparar_global(self):
        g = self.glob

        def ver(s):
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

        # Asignaciones a variables globales hechas desde dentro de tareas/métodos
        for params, cuerpo in self.todas_las_funciones():
            loc = self.locales_de(params, cuerpo)

            def desde_funcion(s, loc=loc):
                if isinstance(s, Asignar) and isinstance(s.destino, Var):
                    if s.destino.nombre not in loc and s.destino.nombre in g.locales:
                        g.agregar_tipo(s.destino.nombre, None)
                elif isinstance(s, Leer) and isinstance(s.destino, Var):
                    if s.destino.nombre not in loc and s.destino.nombre in g.locales:
                        g.agregar_tipo(s.destino.nombre, None)
            self.recorrer(cuerpo, desde_funcion)

    def locales_de(self, params, cuerpo):
        loc = set(params)

        def ver(s):
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
        amb = Ambito()
        amb.locales = self.locales_de(params, cuerpo)
        for p in params:
            amb.agregar_tipo(p, None)

        def ver(s):
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
            if isinstance(s, Asignar) and isinstance(s.destino, Var) and s.destino.nombre in amb.locales:
                amb.agregar_tipo(s.destino.nombre, self.tipo_silencioso(s.valor, amb))
        self.recorrer(cuerpo, asign)
        amb.declarados = set(params) | set(self.glob.locales) | set(self.funciones) | set(self.clases)
        if externo is not None:
            amb.declarados |= externo.declarados | externo.locales
        return amb

    # -------------------------------------------------------------- sentencias
    def bloque(self, sentencias, amb):
        for s in sentencias:
            getattr(self, "s_" + type(s).__name__)(s, amb)

    def s_Declarar(self, n, amb):
        if n.valor is not None:
            self.expr(n.valor, amb)
        amb.declarados.add(n.nombre)

    def s_Asignar(self, n, amb):
        self.expr(n.valor, amb)
        d = n.destino
        if isinstance(d, Var):
            if d.nombre not in amb.declarados:
                self.err(n.linea, "variable '%s' no declarada (use 'cargar')" % d.nombre)
        else:
            self.expr(d, amb)

    def s_Imprimir(self, n, amb):
        self.expr(n.valor, amb)

    def s_Leer(self, n, amb):
        d = n.destino
        if isinstance(d, Var):
            amb.declarados.add(d.nombre)
        else:
            self.expr(d, amb)

    def s_Si(self, n, amb):
        for cond, cuerpo in n.ramas:
            self.expr(cond, amb)
            self.bloque(cuerpo, amb)
        if n.sino is not None:
            self.bloque(n.sino, amb)

    def s_Mientras(self, n, amb):
        self.expr(n.cond, amb)
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1

    def s_Rondar(self, n, amb):
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1
        self.expr(n.cond, amb)

    def s_Para(self, n, amb):
        for lado in (n.desde, n.hasta):
            t = self.expr(lado, amb)
            if t is not None and t != "entero":
                self.err(n.linea, "los límites de 'recorrer' deben ser enteros (se encontró %s)" % t)
        amb.declarados.add(n.var)
        self.bucles += 1
        self.bloque(n.cuerpo, amb)
        self.bucles -= 1

    def s_Bifurcar(self, n, amb):
        self.expr(n.expr, amb)
        self.switches += 1
        for valor, cuerpo in n.casos:
            self.expr(valor, amb)
            self.bloque(cuerpo, amb)
        if n.defecto is not None:
            self.bloque(n.defecto, amb)
        self.switches -= 1

    def entrar_funcion(self, params, cuerpo, amb, clase=None):
        nuevo = self.ambito_funcion(params, cuerpo, externo=None if amb.es_global else amb)
        guardado = (self.en_funcion, self.bucles, self.switches, self.try_prof, self.clase_actual)
        self.en_funcion, self.bucles, self.switches, self.try_prof = True, 0, 0, 0
        if clase is not None:
            self.clase_actual = clase
        self.bloque(cuerpo, nuevo)
        self.en_funcion, self.bucles, self.switches, self.try_prof, self.clase_actual = guardado

    def s_Funcion(self, n, amb):
        self.entrar_funcion(n.params, n.cuerpo, amb)

    def s_Retorno(self, n, amb):
        if not self.en_funcion:
            self.err(n.linea, "'entregar' solo se puede usar dentro de una tarea")
        self.expr(n.valor, amb)

    def s_Clase(self, n, amb):
        if n.padre is not None:
            if n.padre not in self.clases:
                self.err(n.linea, "el módulo padre '%s' no está definido" % n.padre)
            elif n.padre == n.nombre:
                self.err(n.linea, "un módulo no puede extenderse a sí mismo")
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
        self.expr(n.valor, amb)

    def s_Romper(self, n, amb):
        if self.bucles == 0 and self.switches == 0:
            self.err(n.linea, "'detener' solo se puede usar dentro de un ciclo o un bifurcar")

    def s_Continuar(self, n, amb):
        if self.bucles == 0:
            self.err(n.linea, "'avanzar' solo se puede usar dentro de un ciclo")

    def s_ExprSentencia(self, n, amb):
        self.expr(n.expr, amb)

    # -------------------------------------------------------------- expresiones
    def tipo_var(self, nombre, amb):
        fuente = amb if nombre in amb.locales else self.glob
        tipos = fuente.tipos.get(nombre)
        if tipos and len(tipos) == 1:
            (t,) = tipos
            return t
        return None

    def expr(self, n, amb):
        """Revisa la expresión y devuelve su tipo si se conoce con seguridad (o None)."""
        return getattr(self, "e_" + type(n).__name__)(n, amb)

    def e_Literal(self, n, amb):
        return nombre_tipo(n.valor)

    def e_Var(self, n, amb):
        if self.mudo:
            return None
        if n.nombre not in amb.declarados:
            self.err(n.linea, "variable '%s' no declarada" % n.nombre)
            return None
        return self.tipo_var(n.nombre, amb)

    def e_Mismo(self, n, amb):
        if self.clase_actual is None:
            self.err(n.linea, "'mismo' solo se puede usar dentro de un módulo")
        return None

    def e_Lista(self, n, amb):
        for x in n.elementos:
            self.expr(x, amb)
        return "lista"

    def e_Unario(self, n, amb):
        t = self.expr(n.operando, amb)
        if n.op == "no":
            return "booleano"
        if t is not None and not es_num(t):
            self.err(n.linea, "el operador '-' no se puede aplicar a %s" % t)
            return None
        return t

    def e_Binario(self, n, amb):
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
        for a in n.args:
            self.expr(a, amb)
        nombre = n.nombre
        if nombre in amb.locales or nombre in self.anidadas:
            return None                 # parámetro/variable que guarda una tarea, o tarea anidada
        if nombre in self.funciones:
            esperado = self.funciones[nombre]
            if esperado is not None and esperado != len(n.args):
                self.err(n.linea, "la tarea '%s' espera %d argumento(s) y recibe %d" % (nombre, esperado, len(n.args)))
            return None
        if nombre in ARIDAD_PREDEFINIDAS:
            mini, maxi = ARIDAD_PREDEFINIDAS[nombre]
            if not (mini <= len(n.args) <= maxi):
                esp = str(mini) if mini == maxi else "%d a %d" % (mini, maxi)
                self.err(n.linea, "'%s' espera %s argumento(s) y recibe %d" % (nombre, esp, len(n.args)))
            return TIPO_RETORNO.get(nombre)
        if nombre in self.glob.locales or nombre in self.glob.declarados:
            return None
        self.err(n.linea, "la tarea '%s' no está definida" % nombre)
        return None

    def e_LlamadaMetodo(self, n, amb):
        self.expr(n.objeto, amb)
        for a in n.args:
            self.expr(a, amb)
        return None

    def e_Atributo(self, n, amb):
        self.expr(n.objeto, amb)
        return None

    def e_Indice(self, n, amb):
        tobj = self.expr(n.objeto, amb)
        tidx = self.expr(n.indice, amb)
        if tobj is not None and tobj not in ("lista", "texto"):
            self.err(n.linea, "solo se puede indexar una lista o un texto (se encontró %s)" % tobj)
        if tidx is not None and tidx != "entero":
            self.err(n.linea, "el índice debe ser un entero (se encontró %s)" % tidx)
        return "texto" if tobj == "texto" else None

    def cadena_ctor(self, nombre):
        """Parámetros del primer 'ensamblar' en la cadena de herencia (None si no hay)."""
        vistos = set()
        while nombre in self.clases and nombre not in vistos:
            vistos.add(nombre)
            c = self.clases[nombre]
            if c.params_ctor is not None:
                return c.params_ctor
            nombre = c.padre
        return None

    def e_Nuevo(self, n, amb):
        for a in n.args:
            self.expr(a, amb)
        if n.clase not in self.clases:
            self.err(n.linea, "el módulo '%s' no está definido" % n.clase)
            return None
        params = self.cadena_ctor(n.clase)
        esperado = len(params) if params is not None else 0
        if esperado != len(n.args):
            self.err(n.linea, "el módulo '%s' espera %d argumento(s) en 'ensamblar' y recibe %d"
                     % (n.clase, esperado, len(n.args)))
        return None

    def e_Super(self, n, amb):
        for a in n.args:
            self.expr(a, amb)
        if self.clase_actual is None:
            self.err(n.linea, "'superior' solo se puede usar dentro de un módulo")
        elif self.clase_actual.padre is None:
            self.err(n.linea, "el módulo '%s' no extiende a ningún otro, no puede usar 'superior'"
                     % self.clase_actual.nombre)
        return None


def analizar_semantica(programa):
    """Devuelve (errores, avisos); cada uno es una lista de (linea, mensaje)."""
    errores, avisos = Analizador(programa).analizar()
    return sorted(errores), sorted(avisos)
