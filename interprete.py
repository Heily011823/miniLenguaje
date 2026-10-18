"""Intérprete de Ruta: recorre el AST y ejecuta el programa."""
import sqlite3

from nodos import *


# ---------- errores y señales de control ----------
class ExcepcionRuta(Exception):
    """Excepción lanzada con 'alerta' desde un programa Ruta."""
    def __init__(self, valor, linea):
        super().__init__(str(valor))
        self.valor = valor
        self.linea = linea


class ErrorEjecucion(ExcepcionRuta):
    """Error de tiempo de ejecución (división por cero, índice fuera de rango...).
    También se puede capturar con 'intentar_ruta / obstaculo'."""
    def __init__(self, mensaje, linea):
        super().__init__(mensaje, linea)
        self.mensaje = mensaje


class RetornoSignal(Exception):
    def __init__(self, valor, linea):
        self.valor, self.linea = valor, linea

class RomperSignal(Exception):
    def __init__(self, linea):
        self.linea = linea

class ContinuarSignal(Exception):
    def __init__(self, linea):
        self.linea = linea


# ---------- valores del lenguaje ----------
class Entorno:
    """Tabla de variables. 'padre' es el entorno exterior (global)."""
    def __init__(self, padre=None):
        self.vars = {}
        self.padre = padre

    def buscar(self, nombre):
        e = self
        while e is not None:
            if nombre in e.vars:
                return e
            e = e.padre
        return None

    def definir(self, nombre, valor):
        self.vars[nombre] = valor

    def obtener(self, nombre, linea):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion("variable '%s' no declarada" % nombre, linea)
        return e.vars[nombre]

    def asignar(self, nombre, valor, linea):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion("variable '%s' no declarada (use 'cargar')" % nombre, linea)
        e.vars[nombre] = valor


class FuncionRuta:
    def __init__(self, nombre, params, cuerpo, entorno, clase=None):
        self.nombre, self.params, self.cuerpo, self.entorno = nombre, params, cuerpo, entorno
        self.clase = clase          # módulo donde se definió (para 'superior')


class ClaseRuta:
    def __init__(self, nombre, padre, params_ctor, cuerpo_ctor, metodos, campos, entorno):
        self.nombre, self.padre = nombre, padre
        self.params_ctor, self.cuerpo_ctor = params_ctor, cuerpo_ctor
        self.metodos, self.campos, self.entorno = metodos, campos, entorno


class Instancia:
    def __init__(self, clase):
        self.clase = clase
        self.atributos = {}


# ---------- funciones predefinidas: nombre -> (mínimo, máximo de argumentos) ----------
ARIDAD_PREDEFINIDAS = {
    "longitud": (1, 1), "agregar": (2, 2), "quitar": (2, 2),
    "entero": (1, 1), "real": (1, 1), "texto": (1, 1), "absoluto": (1, 1),
    "enlazar": (1, 1), "consultar": (1, 2), "desenlazar": (0, 0),
}


def es_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def es_entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def nombre_tipo(v):
    if v is None: return "nulo"
    if isinstance(v, bool): return "booleano"
    if isinstance(v, int): return "entero"
    if isinstance(v, float): return "real"
    if isinstance(v, str): return "texto"
    if isinstance(v, list): return "lista"
    return "objeto"


def iguales(a, b):
    if es_numero(a) and es_numero(b):
        return a == b
    if nombre_tipo(a) != nombre_tipo(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(iguales(x, y) for x, y in zip(a, b))
    return a == b


class Interprete:
    def __init__(self, salida=print, entrada=input, max_profundidad=10000):
        self.salida = salida
        self.entrada = entrada
        self.max_profundidad = max_profundidad
        self.profundidad = 0
        self.global_env = Entorno()
        self.conexion = None            # base de datos (enlazar / consultar)
        self.predefinidas = {
            "longitud": self._longitud, "agregar": self._agregar, "quitar": self._quitar,
            "entero": self._entero, "real": self._real, "texto": self._texto_f,
            "absoluto": self._absoluto,
            "enlazar": self._enlazar, "consultar": self._consultar, "desenlazar": self._desenlazar,
        }

    # ---------- punto de entrada ----------
    def ejecutar(self, programa):
        try:
            self.hoist(programa, self.global_env)
            self.bloque(programa, self.global_env)
        except RetornoSignal as s:
            raise ErrorEjecucion("'entregar' fuera de una tarea", s.linea)
        except RomperSignal as s:
            raise ErrorEjecucion("'detener' fuera de un ciclo", s.linea)
        except ContinuarSignal as s:
            raise ErrorEjecucion("'avanzar' fuera de un ciclo", s.linea)
        finally:
            self.cerrar_bd()

    def hoist(self, sentencias, env):
        """Registra tareas y módulos antes de ejecutar: se pueden usar antes de declararse."""
        for s in sentencias:
            if isinstance(s, (Funcion, Clase)):
                getattr(self, "exec_" + type(s).__name__)(s, env)

    def bloque(self, sentencias, env):
        for s in sentencias:
            getattr(self, "exec_" + type(s).__name__)(s, env)

    def evaluar(self, nodo, env):
        return getattr(self, "eval_" + type(nodo).__name__)(nodo, env)

    # ---------- utilidades de valores ----------
    def texto(self, v, anidado=False):
        if v is None: return "nulo"
        if isinstance(v, bool): return "verdadero" if v else "falso"
        if isinstance(v, str): return '"%s"' % v if anidado else v
        if isinstance(v, list):
            return "[" + ", ".join(self.texto(x, True) for x in v) + "]"
        if isinstance(v, Instancia): return "<%s>" % v.clase.nombre
        if isinstance(v, FuncionRuta): return "<tarea %s>" % v.nombre
        if isinstance(v, ClaseRuta): return "<módulo %s>" % v.nombre
        return str(v)

    def verdadero(self, v):
        if isinstance(v, bool): return v
        if v is None: return False
        if es_numero(v): return v != 0
        if isinstance(v, (str, list)): return len(v) > 0
        return True

    # ---------- funciones predefinidas ----------
    def _longitud(self, args, linea):
        if not isinstance(args[0], (list, str)):
            raise ErrorEjecucion("longitud() espera una lista o un texto", linea)
        return len(args[0])

    def _agregar(self, args, linea):
        if not isinstance(args[0], list):
            raise ErrorEjecucion("agregar() espera una lista y un valor", linea)
        args[0].append(args[1])
        return None

    def _quitar(self, args, linea):
        if not isinstance(args[0], list):
            raise ErrorEjecucion("quitar() espera una lista y un índice", linea)
        self.revisar_indice(args[0], args[1], linea)
        return args[0].pop(args[1])

    def _entero(self, args, linea):
        v = args[0]
        try:
            if isinstance(v, str):
                return int(v.strip())
            if es_numero(v) or isinstance(v, bool):
                return int(v)
        except (ValueError, OverflowError):
            pass
        raise ErrorEjecucion("no se puede convertir %s a entero" % self.texto(v, True), linea)

    def _real(self, args, linea):
        v = args[0]
        try:
            if isinstance(v, str):
                return float(v.strip())
            if es_numero(v) or isinstance(v, bool):
                return float(v)
        except (ValueError, OverflowError):
            pass
        raise ErrorEjecucion("no se puede convertir %s a real" % self.texto(v, True), linea)

    def _texto_f(self, args, linea):
        return self.texto(args[0])

    def _absoluto(self, args, linea):
        if not es_numero(args[0]):
            raise ErrorEjecucion("absoluto() espera un número", linea)
        return abs(args[0])

    # ---- base de datos (SQLite) ----
    def _enlazar(self, args, linea):
        if not isinstance(args[0], str):
            raise ErrorEjecucion("enlazar() espera el nombre del archivo de la base de datos", linea)
        self.cerrar_bd()
        try:
            self.conexion = sqlite3.connect(args[0])
        except sqlite3.Error as e:
            raise ErrorEjecucion("no se pudo abrir la base de datos: %s" % e, linea)
        return True

    def _consultar(self, args, linea):
        if self.conexion is None:
            raise ErrorEjecucion("no hay base de datos enlazada (use enlazar primero)", linea)
        if not isinstance(args[0], str):
            raise ErrorEjecucion("consultar() espera una sentencia SQL en texto", linea)
        params = args[1] if len(args) > 1 else []
        if not isinstance(params, list) or any(not isinstance(p, (int, float, str, bool, type(None))) for p in params):
            raise ErrorEjecucion("los parámetros de consultar() deben ser una lista de valores simples", linea)
        try:
            cur = self.conexion.execute(args[0], params)
            if cur.description is not None:
                filas = [list(f) for f in cur.fetchall()]
                self.conexion.commit()
                return filas
            self.conexion.commit()
            return cur.rowcount
        except sqlite3.Error as e:
            raise ErrorEjecucion("error de base de datos: %s" % e, linea)

    def _desenlazar(self, args, linea):
        self.cerrar_bd()
        return None

    def cerrar_bd(self):
        if self.conexion is not None:
            try:
                self.conexion.close()
            except sqlite3.Error:
                pass
            self.conexion = None

    # ---------- sentencias ----------
    def exec_Declarar(self, n, env):
        env.definir(n.nombre, None if n.valor is None else self.evaluar(n.valor, env))

    def asignar_destino(self, d, valor, env, linea):
        if isinstance(d, Var):
            env.asignar(d.nombre, valor, linea)
        elif isinstance(d, Atributo):
            obj = self.evaluar(d.objeto, env)
            if not isinstance(obj, Instancia):
                raise ErrorEjecucion("solo los objetos tienen atributos", linea)
            obj.atributos[d.nombre] = valor
        else:  # Indice
            lista = self.evaluar(d.objeto, env)
            i = self.evaluar(d.indice, env)
            if not isinstance(lista, list):
                raise ErrorEjecucion("solo se puede asignar por índice en una lista", linea)
            self.revisar_indice(lista, i, linea)
            lista[i] = valor

    def exec_Asignar(self, n, env):
        valor = self.evaluar(n.valor, env)
        self.asignar_destino(n.destino, valor, env, n.linea)

    def exec_Imprimir(self, n, env):
        self.salida(self.texto(self.evaluar(n.valor, env)))

    def exec_Leer(self, n, env):
        try:
            dato = self.entrada().strip()
        except EOFError:
            raise ErrorEjecucion("no hay datos de entrada para 'escanear'", n.linea)
        for conv in (int, float):
            try:
                dato = conv(dato)
                break
            except ValueError:
                pass
        d = n.destino
        if isinstance(d, Var) and env.buscar(d.nombre) is None:
            env.definir(d.nombre, dato)
        else:
            self.asignar_destino(d, dato, env, n.linea)

    def exec_Si(self, n, env):
        for cond, cuerpo in n.ramas:
            if self.verdadero(self.evaluar(cond, env)):
                self.bloque(cuerpo, env)
                return
        if n.sino is not None:
            self.bloque(n.sino, env)

    def exec_Mientras(self, n, env):
        while self.verdadero(self.evaluar(n.cond, env)):
            try:
                self.bloque(n.cuerpo, env)
            except RomperSignal:
                break
            except ContinuarSignal:
                continue

    def exec_Rondar(self, n, env):
        while True:
            try:
                self.bloque(n.cuerpo, env)
            except RomperSignal:
                break
            except ContinuarSignal:
                pass
            if not self.verdadero(self.evaluar(n.cond, env)):
                break

    def exec_Para(self, n, env):
        a = self.evaluar(n.desde, env)
        b = self.evaluar(n.hasta, env)
        if not (es_entero(a) and es_entero(b)):
            raise ErrorEjecucion("los límites de 'recorrer' deben ser enteros", n.linea)
        for i in range(a, b + 1):          # 'llegando_a' es inclusivo
            env.definir(n.var, i)
            try:
                self.bloque(n.cuerpo, env)
            except RomperSignal:
                break
            except ContinuarSignal:
                continue

    def exec_Bifurcar(self, n, env):
        v = self.evaluar(n.expr, env)
        try:
            for valor, cuerpo in n.casos:
                if iguales(v, self.evaluar(valor, env)):
                    self.bloque(cuerpo, env)
                    return
            if n.defecto is not None:
                self.bloque(n.defecto, env)
        except RomperSignal:
            pass                            # 'detener' dentro de un punto_ruta sale del bifurcar

    def exec_Funcion(self, n, env):
        env.definir(n.nombre, FuncionRuta(n.nombre, n.params, n.cuerpo, env))

    def exec_Retorno(self, n, env):
        raise RetornoSignal(self.evaluar(n.valor, env), n.linea)

    def exec_Clase(self, n, env):
        clase = ClaseRuta(n.nombre, n.padre, n.params_ctor, n.cuerpo_ctor, {}, n.campos, env)
        clase.metodos = {m.nombre: FuncionRuta(m.nombre, m.params, m.cuerpo, env, clase)
                         for m in n.metodos}
        env.definir(n.nombre, clase)

    def exec_Intentar(self, n, env):
        try:
            try:
                self.bloque(n.cuerpo, env)
            except ExcepcionRuta as e:
                if n.capturar is None:
                    raise
                if n.var_error:
                    env.definir(n.var_error, e.valor)
                self.bloque(n.capturar, env)
        finally:
            if n.final is not None:
                self.bloque(n.final, env)

    def exec_Lanzar(self, n, env):
        raise ExcepcionRuta(self.evaluar(n.valor, env), n.linea)

    def exec_Romper(self, n, env):
        raise RomperSignal(n.linea)

    def exec_Continuar(self, n, env):
        raise ContinuarSignal(n.linea)

    def exec_ExprSentencia(self, n, env):
        self.evaluar(n.expr, env)

    # ---------- expresiones ----------
    def eval_Literal(self, n, env):
        return n.valor

    def eval_Var(self, n, env):
        return env.obtener(n.nombre, n.linea)

    def eval_Mismo(self, n, env):
        e = env.buscar("mismo")
        if e is None:
            raise ErrorEjecucion("'mismo' solo se puede usar dentro de un módulo", n.linea)
        return e.vars["mismo"]

    def eval_Lista(self, n, env):
        return [self.evaluar(x, env) for x in n.elementos]

    def eval_Unario(self, n, env):
        v = self.evaluar(n.operando, env)
        if n.op == "no":
            return not self.verdadero(v)
        if not es_numero(v):
            raise ErrorEjecucion("el operador '-' no se puede aplicar a %s" % nombre_tipo(v), n.linea)
        return -v

    def eval_Binario(self, n, env):
        if n.op == "y":
            izq = self.evaluar(n.izq, env)
            return self.verdadero(self.evaluar(n.der, env)) if self.verdadero(izq) else False
        if n.op == "o":
            izq = self.evaluar(n.izq, env)
            return True if self.verdadero(izq) else self.verdadero(self.evaluar(n.der, env))
        a = self.evaluar(n.izq, env)
        b = self.evaluar(n.der, env)
        if n.op in ("==", "!="):
            igual = iguales(a, b)
            return igual if n.op == "==" else not igual
        if n.op in (">", "<", ">=", "<="):
            ok = (es_numero(a) and es_numero(b)) or (isinstance(a, str) and isinstance(b, str))
            if not ok:
                raise ErrorEjecucion("no se puede comparar %s con %s" % (nombre_tipo(a), nombre_tipo(b)), n.linea)
            return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[n.op]
        return self.aritmetica(n.op, a, b, n.linea)

    def aritmetica(self, op, a, b, linea):
        if op == "+" and (isinstance(a, str) or isinstance(b, str)):
            return self.texto(a) + self.texto(b)          # concatenación
        if op == "+" and isinstance(a, list) and isinstance(b, list):
            return a + b
        if not (es_numero(a) and es_numero(b)):
            raise ErrorEjecucion("operación '%s' no válida entre %s y %s" % (op, nombre_tipo(a), nombre_tipo(b)), linea)
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if b == 0:
            raise ErrorEjecucion("división por cero", linea)
        if op == "/":
            if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                return a // b
            return a / b
        return a % b                                       # op == "%"

    def revisar_indice(self, coleccion, i, linea):
        if not es_entero(i):
            raise ErrorEjecucion("el índice debe ser un entero", linea)
        if i < 0 or i >= len(coleccion):
            raise ErrorEjecucion("índice fuera de rango", linea)

    def eval_Indice(self, n, env):
        obj = self.evaluar(n.objeto, env)
        i = self.evaluar(n.indice, env)
        if not isinstance(obj, (list, str)):
            raise ErrorEjecucion("solo se puede indexar una lista o un texto", n.linea)
        self.revisar_indice(obj, i, n.linea)
        return obj[i]

    def eval_Atributo(self, n, env):
        obj = self.evaluar(n.objeto, env)
        if not isinstance(obj, Instancia):
            raise ErrorEjecucion("solo los objetos tienen atributos", n.linea)
        if n.nombre not in obj.atributos:
            raise ErrorEjecucion("el atributo '%s' no existe" % n.nombre, n.linea)
        return obj.atributos[n.nombre]

    # ---------- llamadas ----------
    def llamar(self, f, args, linea, mismo=None):
        if len(args) != len(f.params):
            raise ErrorEjecucion("'%s' espera %d argumento(s) y recibió %d" % (f.nombre, len(f.params), len(args)), linea)
        if self.profundidad >= self.max_profundidad:
            raise ErrorEjecucion("desbordamiento de pila (recursión demasiado profunda)", linea)
        env = Entorno(f.entorno)
        if mismo is not None:
            env.definir("mismo", mismo)
        if f.clase is not None:
            env.definir("$clase", f.clase)
        for p, a in zip(f.params, args):
            env.definir(p, a)
        self.profundidad += 1
        try:
            self.hoist(f.cuerpo, env)
            self.bloque(f.cuerpo, env)
        except RetornoSignal as r:
            return r.valor
        except RomperSignal:
            raise ErrorEjecucion("'detener' fuera de un ciclo", linea)
        except ContinuarSignal:
            raise ErrorEjecucion("'avanzar' fuera de un ciclo", linea)
        except RecursionError:
            raise ErrorEjecucion("desbordamiento de pila (recursión demasiado profunda)", linea)
        finally:
            self.profundidad -= 1
        return None

    def eval_Llamada(self, n, env):
        args = [self.evaluar(a, env) for a in n.args]
        e = env.buscar(n.nombre)
        if e is not None:
            f = e.vars[n.nombre]
            if not isinstance(f, FuncionRuta):
                raise ErrorEjecucion("'%s' no es una tarea" % n.nombre, n.linea)
            return self.llamar(f, args, n.linea)
        if n.nombre in self.predefinidas:
            minimo, maximo = ARIDAD_PREDEFINIDAS[n.nombre]
            if not (minimo <= len(args) <= maximo):
                raise ErrorEjecucion("'%s' recibió %d argumento(s) y no es válido" % (n.nombre, len(args)), n.linea)
            return self.predefinidas[n.nombre](args, n.linea)
        raise ErrorEjecucion("tarea '%s' no definida" % n.nombre, n.linea)

    # ---------- módulos (clases) ----------
    def padre_de(self, clase, linea):
        if clase.padre is None:
            return None
        e = clase.entorno.buscar(clase.padre)
        if e is None or not isinstance(e.vars[clase.padre], ClaseRuta):
            raise ErrorEjecucion("el módulo padre '%s' no está definido" % clase.padre, linea)
        return e.vars[clase.padre]

    def cadena(self, clase, linea):
        """Lista de módulos desde la clase hasta su ancestro más lejano."""
        cadena, vistos = [], set()
        while clase is not None:
            if id(clase) in vistos:
                raise ErrorEjecucion("herencia circular en el módulo '%s'" % clase.nombre, linea)
            vistos.add(id(clase))
            cadena.append(clase)
            clase = self.padre_de(clase, linea)
        return cadena

    def buscar_metodo(self, clase, nombre, linea):
        for c in self.cadena(clase, linea):
            if nombre in c.metodos:
                return c.metodos[nombre]
        return None

    def eval_LlamadaMetodo(self, n, env):
        obj = self.evaluar(n.objeto, env)
        args = [self.evaluar(a, env) for a in n.args]
        if not isinstance(obj, Instancia):
            raise ErrorEjecucion("solo los objetos tienen métodos", n.linea)
        metodo = self.buscar_metodo(obj.clase, n.nombre, n.linea)
        if metodo is None:
            raise ErrorEjecucion("el módulo '%s' no tiene el método '%s'" % (obj.clase.nombre, n.nombre), n.linea)
        return self.llamar(metodo, args, n.linea, mismo=obj)

    def ctor_de(self, clase, linea):
        """Primer 'ensamblar' encontrado subiendo por la herencia: (clase, FuncionRuta) o None."""
        for c in self.cadena(clase, linea):
            if c.params_ctor is not None:
                return FuncionRuta(c.nombre + ".ensamblar", c.params_ctor, c.cuerpo_ctor, c.entorno, c)
        return None

    def eval_Nuevo(self, n, env):
        e = env.buscar(n.clase)
        if e is None or not isinstance(e.vars[n.clase], ClaseRuta):
            raise ErrorEjecucion("módulo '%s' no definido" % n.clase, n.linea)
        clase = e.vars[n.clase]
        args = [self.evaluar(a, env) for a in n.args]
        obj = Instancia(clase)
        for c in reversed(self.cadena(clase, n.linea)):          # atributos por defecto
            for campo in c.campos:
                valor = None if campo.valor is None else self.evaluar(campo.valor, c.entorno)
                obj.atributos[campo.nombre] = valor
        ctor = self.ctor_de(clase, n.linea)
        if ctor is None:
            if args:
                raise ErrorEjecucion("el módulo '%s' no tiene 'ensamblar' y recibió %d argumento(s)" % (clase.nombre, len(args)), n.linea)
        else:
            self.llamar(ctor, args, n.linea, mismo=obj)
        return obj

    def eval_Super(self, n, env):
        ec = env.buscar("$clase")
        em = env.buscar("mismo")
        if ec is None or em is None:
            raise ErrorEjecucion("'superior' solo se puede usar dentro de un módulo", n.linea)
        actual, obj = ec.vars["$clase"], em.vars["mismo"]
        padre = self.padre_de(actual, n.linea)
        if padre is None:
            raise ErrorEjecucion("el módulo '%s' no extiende a ningún otro" % actual.nombre, n.linea)
        args = [self.evaluar(a, env) for a in n.args]
        if n.metodo == "ensamblar":
            f = self.ctor_de(padre, n.linea)
            if f is None:
                if args:
                    raise ErrorEjecucion("el módulo padre no tiene 'ensamblar'", n.linea)
                return None
        else:
            f = self.buscar_metodo(padre, n.metodo, n.linea)
            if f is None:
                raise ErrorEjecucion("el módulo padre no tiene el método '%s'" % n.metodo, n.linea)
        return self.llamar(f, args, n.linea, mismo=obj)
