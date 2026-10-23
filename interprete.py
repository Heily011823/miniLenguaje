"""Intérprete de Tramo: recorre el AST y ejecuta el programa."""
import sqlite3

from nodos import *


# ---------- errores y señales de control ----------
class ExcepcionRuta(Exception):
    """Excepción lanzada con 'tormenta' desde un programa Tramo."""
    def __init__(self, valor, linea):
        """
        Inicializa una excepción del lenguaje.

        Parámetros:
            valor: Valor o mensaje de la excepción.
            linea: Línea donde ocurrió la excepción.
        """
        super().__init__(str(valor))
        self.valor = valor
        self.linea = linea


class ErrorEjecucion(ExcepcionRuta):
    """Error de tiempo de ejecución (división por cero, índice fuera de rango...).
    También se puede capturar con 'explorar / imprevisto'."""
    def __init__(self, mensaje, linea):
        """
        Inicializa un error de ejecución.

        Parámetros:
            mensaje: Descripción del error.
            linea: Línea donde ocurrió el error.
        """
        super().__init__(mensaje, linea)
        self.mensaje = mensaje


class RetornoSignal(Exception):
    """ Permite terminar una función y devolver un valor. """
    def __init__(self, valor, linea):
        """
        Guarda la información necesaria para devolver un valor.

        Parámetros:
            valor: Valor que se devuelve.
            linea: Línea donde se ejecutó el retorno.
        """
        self.valor, self.linea = valor, linea

class RomperSignal(Exception):
    """ Indica que se debe salir de un ciclo. """
    def __init__(self, linea):
        """
        Guarda la línea donde se solicitó salir del ciclo.

        Parámetros:
            linea: Línea para detener el ciclo.
        """
        self.linea = linea

class ContinuarSignal(Exception):
    """ Indica que se debe continuar con la siguiente iteración. """
    def __init__(self, linea):
        self.linea = linea


# ---------- valores del lenguaje ----------
class Entorno:
    """Tabla de variables. 'padre' es el entorno exterior (global)."""
    def __init__(self, padre=None):
        """
        Inicializa un entorno de variables.

        Parámetros:
            padre (Entorno | None): el padre puede ser un objeto Entorno o None, y es el entorno exterior
            al que este se conecta.
        """
        self.vars = {}
        self.padre = padre

    def buscar(self, nombre):
        """
        Busca una variable en el entorno actual y sus padres.

        Parámetros:
            nombre: Nombre de la variable que se busca.

        Retorna:
            Entorno: Entorno donde se encuentra la variable.
            None: Si la variable no existe en ningún entorno.
        """
        e = self
        while e is not None:
            if nombre in e.vars:
                return e
            e = e.padre
        return None

    def definir(self, nombre, valor):
        """
        Registra una variable en el entorno actual.

        Parámetros:
            nombre: Nombre de la variable.
            valor: Valor inicial de la variable.
        """
        self.vars[nombre] = valor

    def obtener(self, nombre, linea):
        """
        Obtiene el valor de una variable declarada.

        Parámetros:
            nombre: Nombre de la variable.
            linea: Línea donde se utiliza la variable.

        Retorna:
            El valor almacenado en la variable.

        Excepciones:
            ErrorEjecucion: Si la variable no está declarada.
        """
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion("variable '%s' no declarada" % nombre, linea)
        return e.vars[nombre]

    def asignar(self, nombre, valor, linea):
        """
        Actualiza el valor de una variable existente.

        Parámetros:
            nombre: Nombre de la variable.
            valor: Nuevo valor que se asignará.
            linea: Línea donde se realiza la asignación.

        Excepciones:
            ErrorEjecucion: Si la variable no está declarada.
        """
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion("variable '%s' no declarada (use 'cargar')" % nombre, linea)
        e.vars[nombre] = valor


class FuncionRuta:
    """ Representa una función definida. """
    def __init__(self, nombre, params, cuerpo, entorno, clase=None):
        """
        Inicializa la información de una función.

        Parámetros:
            nombre: Nombre de la función.
            params: Parámetros que recibe la función.
            cuerpo: Instrucciones que ejecuta la función.
            entorno: Entorno donde se definió la función.
            clase (ClaseRuta | None): clase puede ser ClaseRuta o None.
        """
        self.nombre, self.params, self.cuerpo, self.entorno = nombre, params, cuerpo, entorno
        self.clase = clase          # campamento donde se definió (para 'superior')


class ClaseRuta:
    """ Representa una clase o campamento """
    def __init__(self, nombre, padre, params_ctor, cuerpo_ctor, metodos, campos, entorno):
        """
        Inicializa la información de una clase.

        Parámetros:
            nombre: Nombre de la clase.
            padre: Nombre de la clase padre, si existe.
            params_ctor: Parámetros del constructor.
            cuerpo_ctor: Instrucciones del constructor.
            metodos: Métodos definidos en la clase.
            campos: Atributos declarados en la clase.
            entorno: Entorno donde se definió la clase.
        """
        self.nombre, self.padre = nombre, padre
        self.params_ctor, self.cuerpo_ctor = params_ctor, cuerpo_ctor
        self.metodos, self.campos, self.entorno = metodos, campos, entorno


class Instancia:
    """ Representa un objeto creado a partir de una clase. """

    def __init__(self, clase):
        """
        Inicializa una instancia de una clase.

        Parámetros:
            clase: Clase a la que pertenece el objeto.
        """
        self.clase = clase
        self.atributos = {}


# ---------- funciones predefinidas: nombre -> (mínimo, máximo de argumentos) ----------
ARIDAD_PREDEFINIDAS = {
    "longitud": (1, 1), "agregar": (2, 2), "quitar": (2, 2),
    "entero": (1, 1), "real": (1, 1), "texto": (1, 1), "absoluto": (1, 1),
    "enlazar": (1, 1), "consultar": (1, 2), "desenlazar": (0, 0),
}


def es_numero(v):
    """
    Comprueba si un valor es numérico y no es booleano.

    Parámetros:
        v: Valor que se quiere comprobar.

    Retorna:
        bool: True si es entero o real; False en caso contrario.
    """
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def es_entero(v):
    """
    Comprueba si un valor es entero y no es booleano.

    Parámetros:
        v: Valor que se quiere comprobar.

    Retorna:
        bool: True si es entero; False en caso contrario.
    """
    return isinstance(v, int) and not isinstance(v, bool)


def nombre_tipo(v):
    """
    Identifica el tipo de dato de un valor.

    Parámetros:
        v: Valor cuyo tipo se tiene identificar.

    Retorna:
        str: Nombre del tipo de dato.
    """
    if v is None: return "nulo"
    if isinstance(v, bool): return "booleano"
    if isinstance(v, int): return "entero"
    if isinstance(v, float): return "real"
    if isinstance(v, str): return "texto"
    if isinstance(v, list): return "lista"
    return "objeto"


def iguales(a, b):
    """
    Compara dos valores teniendo en cuenta sus tipos y contenido.

    Parámetros:
        a: Primer valor que se compara.
        b: Segundo valor que se compara.

    Retorna:
        bool: True si los valores son iguales; False en caso contrario.
    """
    if es_numero(a) and es_numero(b):
        return a == b
    if nombre_tipo(a) != nombre_tipo(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(iguales(x, y) for x, y in zip(a, b))
    return a == b


class Interprete:
    """ Ejecuta las instrucciones y evalúa las expresiones. """

    def __init__(self, salida=print, entrada=input, max_profundidad=10000):
        """
        Inicializa el intérprete y sus funciones principales.

        Parámetros:
            salida: Función utilizada para mostrar resultados.
            entrada: Función utilizada para leer datos.
            max_profundidad: Límite máximo de llamadas anidadas.
        """
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
        """
        Prepara y ejecuta las instrucciones del programa.

        Parámetros:
            programa: Lista de instrucciones representadas en el AST.

        Excepciones:
            ErrorEjecucion: Si se utiliza una instrucción de retorno o de ciclo
            fuera del contexto.
        """
        try:
            self.hoist(programa, self.global_env)
            self.bloque(programa, self.global_env)
        except RetornoSignal as s:
            raise ErrorEjecucion("'regresar' fuera de un trayecto", s.linea)
        except RomperSignal as s:
            raise ErrorEjecucion("'detener' fuera de un ciclo", s.linea)
        except ContinuarSignal as s:
            raise ErrorEjecucion("'avanzar' fuera de un ciclo", s.linea)
        finally:
            self.cerrar_bd()

    def hoist(self, sentencias, env):
        """
        Registra las funciones y clases antes de ejecutar las instrucciones.

        Parámetros:
            sentencias: Instrucciones que se revisarán.
            env: Entorno donde se registrarán las funciones y clases.
        """
        for s in sentencias:
            if isinstance(s, (Funcion, Clase)):
                getattr(self, "exec_" + type(s).__name__)(s, env)

    def bloque(self, sentencias, env):
        """
        Ejecuta las instrucciones de un bloque en orden.

        Parámetros:
            sentencias: Instrucciones que se ejecutarán.
            env: Entorno utilizado durante la ejecución.
        """
        for s in sentencias:
            getattr(self, "exec_" + type(s).__name__)(s, env)

    def evaluar(self, nodo, env):
        """
        Evalúa una expresión del árbol de sintaxis.

        Parámetros:
            nodo: Nodo que representa la expresión.
            env: Entorno utilizado para evaluar la expresión.

        Retorna:
            El resultado de evaluar la expresión.
        """
        return getattr(self, "eval_" + type(nodo).__name__)(nodo, env)

    # ---------- utilidades de valores ----------

    def texto(self, v, anidado=False):
        """
        Convierte un valor a su representación textual.

        Parámetros:
            v: Valor que se convertirá.
            anidado: Indica si el valor está dentro de una lista.

        Retorna:
            str: Representación textual del valor.
        """
        if v is None: return "nulo"
        if isinstance(v, bool): return "verdadero" if v else "falso"
        if isinstance(v, str): return '"%s"' % v if anidado else v
        if isinstance(v, list):
            return "[" + ", ".join(self.texto(x, True) for x in v) + "]"
        if isinstance(v, Instancia): return "<%s>" % v.clase.nombre
        if isinstance(v, FuncionRuta): return "<trayecto %s>" % v.nombre
        if isinstance(v, ClaseRuta): return "<campamento %s>" % v.nombre
        return str(v)

    def verdadero(self, v):
        """
        Determina si un valor se considera verdadero.

        Parámetros:
            v: Valor que se evaluará.

        Retorna:
            bool: True si se considera verdadero; False en caso contrario.
        """
        if isinstance(v, bool): return v
        if v is None: return False
        if es_numero(v): return v != 0
        if isinstance(v, (str, list)): return len(v) > 0
        return True

    # ---------- funciones predefinidas ----------

    def _longitud(self, args, linea):
        """
        Calcula la longitud de una lista o un texto.

        Parámetros:
            args: Lista de argumentos, donde el primero debe ser una lista o texto.
            linea: Línea donde se llamó a la función.

        Retorna:
            int: Cantidad de elementos o caracteres.

        Excepciones:
            ErrorEjecucion: Si el argumento no es una lista ni un texto.
        """
        if not isinstance(args[0], (list, str)):
            raise ErrorEjecucion("longitud() espera una lista o un texto", linea)
        return len(args[0])

    def _agregar(self, args, linea):
        """
        Agrega un valor al final de una lista.

        Parámetros:
            args: Lista con la colección de destino y el valor que se agregará.
            linea: Línea donde se llamó a la función.

        Excepciones:
            ErrorEjecucion: Si el primer argumento no es una lista.
        """
        if not isinstance(args[0], list):
            raise ErrorEjecucion("agregar() espera una lista y un valor", linea)
        args[0].append(args[1])
        return None

    def _quitar(self, args, linea):
        """
        Elimina un elemento de una lista mediante su índice.

        Parámetros:
            args: Lista con la colección y el índice del elemento.
            linea: Línea donde se llamó a la función.

        Retorna:
            El elemento eliminado.

        Excepciones:
            ErrorEjecucion: Si el argumento no es una lista o el índice no es válido.
        """
        if not isinstance(args[0], list):
            raise ErrorEjecucion("quitar() espera una lista y un índice", linea)
        self.revisar_indice(args[0], args[1], linea)
        return args[0].pop(args[1])

    def _entero(self, args, linea):
        """
        Convierte un valor a entero.

        Parámetros:
            args: Lista de argumentos, donde se utiliza el primero.
            linea: Línea donde se llamó a la función.

        Retorna:
            int: Valor convertido a entero.

        Excepciones:
            ErrorEjecucion: Si el valor no se puede convertir.
        """
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
        """
        Convierte un valor compatible a número real.

        Parámetros:
            args: Lista de argumentos, donde se utiliza el primero.
            linea: Línea donde se llamó a la función.

        Retorna:
            float: Valor convertido a número real.

        Excepciones:
            ErrorEjecucion: Si el valor no se puede convertir.
        """
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
        """
        Convierte el primer argumento a texto.

        Parámetros:
            args: Lista de argumentos, donde se utiliza el primero.
            linea: Línea donde se llamó a la función.

        Retorna:
            str: Representación textual del valor.
        """
        return self.texto(args[0])

    def _absoluto(self, args, linea):
        """
        Calcula el valor absoluto de un número.

        Parámetros:
            args: Lista de argumentos; el primero debe ser numérico.
            linea: Línea donde se llamó a la función.

        Retorna:
            int o float: Valor absoluto del número.

        Excepciones:
            ErrorEjecucion: Si el argumento no es numérico.
        """
        if not es_numero(args[0]):
            raise ErrorEjecucion("absoluto() espera un número", linea)
        return abs(args[0])

    # ---- base de datos (SQLite) ----
    def _enlazar(self, args, linea):
        """
        Abre una conexión con una base de datos SQLite.

        Parámetros:
            args: Lista cuyo primer elemento es el nombre del archivo.
            linea: Línea donde se llamó a la función.

        Retorna:
            bool: True si la conexión se abre correctamente.

        Excepciones:
            ErrorEjecucion: Si el nombre no es texto o no se puede abrir la base.
        """
        if not isinstance(args[0], str):
            raise ErrorEjecucion("enlazar() espera el nombre del archivo de la base de datos", linea)
        self.cerrar_bd()
        try:
            self.conexion = sqlite3.connect(args[0])
        except sqlite3.Error as e:
            raise ErrorEjecucion("no se pudo abrir la base de datos: %s" % e, linea)
        return True

    def _consultar(self, args, linea):
        """
        Ejecuta una sentencia SQL en la base de datos enlazada.

        Parámetros:
            args: Contiene la sentencia SQL y, opcionalmente, sus parámetros.
            linea: Línea donde se llamó a la función.

        Retorna:
            list: Filas obtenidas si la consulta devuelve resultados.
            int: Cantidad de filas afectadas si la sentencia no devuelve filas.

        Excepciones:
            ErrorEjecucion: Si no hay conexión, los argumentos son inválidos
            o SQLite genera un error.
        """
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
        """
        Cierra la conexión con la base de datos.

        Parámetros:
            args: Lista de argumentos vacía.
            linea: Línea donde se llamó a la función.
        """
        self.cerrar_bd()
        return None

    def cerrar_bd(self):
        """Cierra la conexión con la base de datos si está abierta."""
        if self.conexion is not None:
            try:
                self.conexion.close()
            except sqlite3.Error:
                pass
            self.conexion = None

    # ---------- sentencias ----------

    def exec_Declarar(self, n, env):
        """
        Ejecuta una declaración de variable.

        Parámetros:
            n: Nodo con el nombre y el valor inicial de la variable.
            env: Entorno donde se declarará la variable.
        """
        env.definir(n.nombre, None if n.valor is None else self.evaluar(n.valor, env))

    def asignar_destino(self, d, valor, env, linea):
        """
        Asigna un valor a una variable, un atributo o un elemento de lista.

        Parámetros:
            d: Nodo que representa el destino de la asignación.
            valor: Valor que se asignará.
            env: Entorno donde se evalúa el destino.
            linea: Línea donde ocurre la asignación.

        Excepciones:
            ErrorEjecucion: Si el destino no es válido o el índice está fuera de rango.
        """
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
        """
        Ejecuta una instrucción de asignación.

        Parámetros:
            n: Nodo con el destino y el valor que se asignará.
            env: Entorno donde se evalúan las expresiones.
        """
        valor = self.evaluar(n.valor, env)
        self.asignar_destino(n.destino, valor, env, n.linea)

    def exec_Imprimir(self, n, env):
        """
        Evalúa una expresión y muestra su resultado.

        Parámetros:
            n: Nodo con el valor que se imprimirá.
            env: Entorno utilizado para evaluar la expresión.
        """
        self.salida(self.texto(self.evaluar(n.valor, env)))

    def exec_Leer(self, n, env):
        """
        Lee un dato y lo guarda en el destino indicado.

        Parámetros:
            n: Nodo con el destino donde se guardará el dato.
            env: Entorno utilizado para buscar o definir variables.

        Excepciones:
            ErrorEjecucion: Si no hay datos de entrada disponibles.
        """
        try:
            dato = self.entrada().strip()
        except EOFError:
            raise ErrorEjecucion("no hay datos de entrada para 'preguntar'", n.linea)
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
        """
        Ejecuta el bloque correspondiente a la primera condición verdadera.

        Parámetros:
            n: Nodo con las condiciones y sus bloques.
            env: Entorno donde se evalúan las condiciones.
        """
        for cond, cuerpo in n.ramas:
            if self.verdadero(self.evaluar(cond, env)):
                self.bloque(cuerpo, env)
                return
        if n.sino is not None:
            self.bloque(n.sino, env)

    def exec_Mientras(self, n, env):
        """
        Repite un bloque mientras su condición sea verdadera.

        Parámetros:
            n: Nodo con la condición y el cuerpo del ciclo.
            env: Entorno utilizado durante la ejecución.
        """
        while self.verdadero(self.evaluar(n.cond, env)):
            try:
                self.bloque(n.cuerpo, env)
            except RomperSignal:
                break
            except ContinuarSignal:
                continue

    def exec_Rondar(self, n, env):
        """
        Ejecuta un bloque al menos una vez y lo repite según la condición.

        Parámetros:
            n: Nodo con el cuerpo y la condición del ciclo.
            env: Entorno utilizado durante la ejecución.
        """
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
        """
        Recorre un rango de enteros y ejecuta un bloque por cada valor.

        Parámetros:
            n: Nodo con la variable, los límites y el cuerpo del ciclo.
            env: Entorno donde se guarda la variable del ciclo.

        Excepciones:
            ErrorEjecucion: Si los límites no son enteros.
        """
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
        """
        Compara una expresión con varios casos y ejecuta el que coincida.

        Parámetros:
            n: Nodo con la expresión, los casos y el caso por defecto.
            env: Entorno utilizado para evaluar los valores.
        """
        v = self.evaluar(n.expr, env)
        try:
            for valor, cuerpo in n.casos:
                if iguales(v, self.evaluar(valor, env)):
                    self.bloque(cuerpo, env)
                    return
            if n.defecto is not None:
                self.bloque(n.defecto, env)
        except RomperSignal:
            pass                            # 'detener' dentro de un mirador sale del bifurcar

    def exec_Funcion(self, n, env):
        """
        Registra una función para utilizarla durante la ejecución.

        Parámetros:
            n: Nodo con el nombre, los parámetros y el cuerpo de la función.
            env: Entorno donde se registra la función.
        """
        env.definir(n.nombre, FuncionRuta(n.nombre, n.params, n.cuerpo, env))

    def exec_Retorno(self, n, env):
        """
        Evalúa el valor indicado y finaliza la función actual.

        Parámetros:
            n: Nodo con la expresión que se devolverá.
            env: Entorno utilizado para evaluar la expresión.
        """
        raise RetornoSignal(self.evaluar(n.valor, env), n.linea)

    def exec_Clase(self, n, env):
        """
        Registra una clase con sus campos, métodos y posible clase padre.

        Parámetros:
            n: Nodo que contiene la definición de la clase.
            env: Entorno donde se registrará la clase.
        """
        clase = ClaseRuta(n.nombre, n.padre, n.params_ctor, n.cuerpo_ctor, {}, n.campos, env)
        clase.metodos = {m.nombre: FuncionRuta(m.nombre, m.params, m.cuerpo, env, clase)
                         for m in n.metodos}
        env.definir(n.nombre, clase)

    def exec_Intentar(self, n, env):
        """
        Ejecuta un bloque con manejo de excepciones y una sección final opcional.

        Parámetros:
            n: Nodo con los bloques de ejecución, captura y finalización.
            env: Entorno donde se ejecutan los bloques.
        """
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
        """
        Lanza una excepción con el valor indicado.

        Parámetros:
            n: Nodo con el valor de la excepción.
            env: Entorno utilizado para evaluar el valor.
        """
        raise ExcepcionRuta(self.evaluar(n.valor, env), n.linea)

    def exec_Romper(self, n, env):
        """
        Solicita salir del ciclo actual.

        Parámetros:
            n: Nodo de la instrucción para detener el ciclo.
            env: Entorno actual.
        """
        raise RomperSignal(n.linea)

    def exec_Continuar(self, n, env):
        """
        Solicita continuar con la siguiente iteración del ciclo.

        Parámetros:
            n: Nodo de la instrucción para continuar.
            env: Entorno actual.
        """
        raise ContinuarSignal(n.linea)

    def exec_ExprSentencia(self, n, env):
        """
        Evalúa una expresión utilizada como instrucción.

        Parámetros:
            n: Nodo con la expresión que se ejecutará.
            env: Entorno utilizado para evaluar la expresión.
        """
        self.evaluar(n.expr, env)

    # ---------- expresiones ----------

    def eval_Literal(self, n, env):
        """
        Obtiene el valor almacenado en un literal.

        Parámetros:
            n: Nodo que contiene el valor literal.
            env: Entorno actual; no se utiliza en este método.

        Retorna:
            El valor almacenado en el nodo.
        """
        return n.valor

    def eval_Var(self, n, env):
        """
        Obtiene el valor de una variable.

        Parámetros:
            n: Nodo con el nombre de la variable.
            env: Entorno donde se busca la variable.

        Retorna:
            El valor almacenado en la variable.

        Excepciones:
            ErrorEjecucion: Si la variable no está declarada.
        """
        return env.obtener(n.nombre, n.linea)

    def eval_Mismo(self, n, env):
        """
        Obtiene el objeto actual dentro de un método o constructor.

        Parámetros:
            n: Nodo que representa la referencia a 'mismo'.
            env: Entorno donde se busca el objeto actual.

        Retorna:
            Instancia: Objeto actual.

        Excepciones:
            ErrorEjecucion: Si se utiliza fuera de un campamento.
        """
        e = env.buscar("mismo")
        if e is None:
            raise ErrorEjecucion("'mismo' solo se puede usar dentro de un campamento", n.linea)
        return e.vars["mismo"]

    def eval_Lista(self, n, env):
        """
        Evalúa los elementos y construye una lista.

        Parámetros:
            n: Nodo que contiene los elementos de la lista.
            env: Entorno utilizado para evaluar los elementos.

        Retorna:
            list: Lista con los valores calculados.
        """
        return [self.evaluar(x, env) for x in n.elementos]

    def eval_Unario(self, n, env):
        """
        Evalúa una operación unaria, como la negación lógica o numérica.

        Parámetros:
            n: Nodo con el operador y su operando.
            env: Entorno utilizado para evaluar el operando.

        Retorna:
            El resultado de la operación.

        Excepciones:
            ErrorEjecucion: Si el operador numérico se aplica a un tipo inválido.
        """
        v = self.evaluar(n.operando, env)
        if n.op == "no":
            return not self.verdadero(v)
        if not es_numero(v):
            raise ErrorEjecucion("el operador '-' no se puede aplicar a %s" % nombre_tipo(v), n.linea)
        return -v

    def eval_Binario(self, n, env):
        """
        Evalúa operaciones lógicas, comparaciones y operaciones aritméticas.

        Parámetros:
            n: Nodo con el operador y sus dos operandos.
            env: Entorno utilizado para evaluar los operandos.

        Retorna:
            El resultado de la operación.

        Excepciones:
            ErrorEjecucion: Si los tipos de datos no permiten la operación.
        """
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
        """
        Realiza una operación aritmética entre dos valores.

        Parámetros:
            op: Operador aritmético.
            a: Primer valor de la operación.
            b: Segundo valor de la operación.
            linea: Línea donde ocurre la operación.

        Retorna:
            El resultado de la operación aritmética.

        Excepciones:
            ErrorEjecucion: Si los tipos no son compatibles o hay división por cero.
        """
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
        """
        Comprueba que un índice sea entero y esté dentro de los límites.

        Parámetros:
            coleccion: Lista o texto que se va a consultar.
            i: Índice que se comprobará.
            linea: Línea donde se utiliza el índice.

        Excepciones:
            ErrorEjecucion: Si el índice no es entero o está fuera de rango.
        """
        if not es_entero(i):
            raise ErrorEjecucion("el índice debe ser un entero", linea)
        if i < 0 or i >= len(coleccion):
            raise ErrorEjecucion("índice fuera de rango", linea)

    def eval_Indice(self, n, env):
        """
        Obtiene un elemento de una lista o un carácter de un texto.

        Parámetros:
            n: Nodo con la colección y el índice.
            env: Entorno utilizado para evaluar ambos valores.

        Retorna:
            El elemento ubicado en el índice indicado.

        Excepciones:
            ErrorEjecucion: Si el objeto no es una lista o texto, o el índice es inválido.
        """
        obj = self.evaluar(n.objeto, env)
        i = self.evaluar(n.indice, env)
        if not isinstance(obj, (list, str)):
            raise ErrorEjecucion("solo se puede indexar una lista o un texto", n.linea)
        self.revisar_indice(obj, i, n.linea)
        return obj[i]

    def eval_Atributo(self, n, env):
        """
        Obtiene el valor de un atributo de un objeto.

        Parámetros:
            n: Nodo con el objeto y el nombre del atributo.
            env: Entorno utilizado para evaluar el objeto.

        Retorna:
            El valor almacenado en el atributo.

        Excepciones:
            ErrorEjecucion: Si el objeto no es una instancia o el atributo no existe.
        """
        obj = self.evaluar(n.objeto, env)
        if not isinstance(obj, Instancia):
            raise ErrorEjecucion("solo los objetos tienen atributos", n.linea)
        if n.nombre not in obj.atributos:
            raise ErrorEjecucion("el atributo '%s' no existe" % n.nombre, n.linea)
        return obj.atributos[n.nombre]

    # ---------- llamadas ----------

    def llamar(self, f, args, linea, mismo=None):
        """
        Ejecuta una función con los argumentos recibidos.

        Parámetros:
            f: Función que se ejecutará.
            args: Valores que recibirá la función.
            linea: Línea donde se realizó la llamada.
            mismo: Objeto actual si se trata de un método.

        Retorna:
            El valor indicado por 'regresar' o None si no existe retorno.

        Excepciones:
            ErrorEjecucion: Si la cantidad de argumentos es incorrecta, la
            recursión es demasiado profunda o se usan señales de ciclo fuera
            del contexto permitido.
        """
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
        """
        Evalúa los argumentos y ejecuta una función.

        Parámetros:
            n: Nodo con el nombre y los argumentos de la llamada.
            env: Entorno donde se busca la función.

        Retorna:
            El resultado de la función llamada.

        Excepciones:
            ErrorEjecucion: Si la función no existe, no es válida o recibe
            una cantidad incorrecta de argumentos.
        """
        args = [self.evaluar(a, env) for a in n.args]
        e = env.buscar(n.nombre)
        if e is not None:
            f = e.vars[n.nombre]
            if not isinstance(f, FuncionRuta):
                raise ErrorEjecucion("'%s' no es un trayecto" % n.nombre, n.linea)
            return self.llamar(f, args, n.linea)
        if n.nombre in self.predefinidas:
            minimo, maximo = ARIDAD_PREDEFINIDAS[n.nombre]
            if not (minimo <= len(args) <= maximo):
                raise ErrorEjecucion("'%s' recibió %d argumento(s) y no es válido" % (n.nombre, len(args)), n.linea)
            return self.predefinidas[n.nombre](args, n.linea)
        raise ErrorEjecucion("trayecto '%s' no definido" % n.nombre, n.linea)

    # ---------- campamentos (clases) ----------

    def padre_de(self, clase, linea):
        """
        Busca la clase padre de una clase.

        Parámetros:
            clase: Clase cuyo padre se busca.
            linea: Línea donde se necesita la clase padre.

        Retorna:
            ClaseRuta: Clase padre encontrada.
            None: Si la clase no tiene padre.

        Excepciones:
            ErrorEjecucion: Si la clase padre no está definida correctamente.
        """
        if clase.padre is None:
            return None
        e = clase.entorno.buscar(clase.padre)
        if e is None or not isinstance(e.vars[clase.padre], ClaseRuta):
            raise ErrorEjecucion("el campamento padre '%s' no está definido" % clase.padre, linea)
        return e.vars[clase.padre]

    def cadena(self, clase, linea):
        """
        Obtiene las clases desde la actual hasta el ancestro más lejano.

        Parámetros:
            clase: Clase desde la que comienza la búsqueda.
            linea: Línea donde se realiza la operación.

        Retorna:
            list: Clases ordenadas desde la actual hasta la más ancestral.

        Excepciones:
            ErrorEjecucion: Si existe una herencia circular.
        """
        cadena, vistos = [], set()
        while clase is not None:
            if id(clase) in vistos:
                raise ErrorEjecucion("herencia circular en el campamento '%s'" % clase.nombre, linea)
            vistos.add(id(clase))
            cadena.append(clase)
            clase = self.padre_de(clase, linea)
        return cadena

    def buscar_metodo(self, clase, nombre, linea):
        """
        Busca un método en una clase y en sus clases padre.

        Parámetros:
            clase: Clase donde comienza la búsqueda.
            nombre: Nombre del método.
            linea: Línea donde se necesita el método.

        Retorna:
            FuncionRuta: Método encontrado.
            None: Si el método no existe en la cadena de herencia.
        """
        for c in self.cadena(clase, linea):
            if nombre in c.metodos:
                return c.metodos[nombre]
        return None

    def eval_LlamadaMetodo(self, n, env):
        """
        Evalúa y ejecuta una llamada a un método de un objeto.

        Parámetros:
            n: Nodo con el objeto, el nombre del método y sus argumentos.
            env: Entorno utilizado para evaluar la llamada.

        Retorna:
            El resultado del método.

        Excepciones:
            ErrorEjecucion: Si el objeto no es una instancia o el método no existe.
        """
        obj = self.evaluar(n.objeto, env)
        args = [self.evaluar(a, env) for a in n.args]
        if not isinstance(obj, Instancia):
            raise ErrorEjecucion("solo los objetos tienen métodos", n.linea)
        metodo = self.buscar_metodo(obj.clase, n.nombre, n.linea)
        if metodo is None:
            raise ErrorEjecucion("el campamento '%s' no tiene el método '%s'" % (obj.clase.nombre, n.nombre), n.linea)
        return self.llamar(metodo, args, n.linea, mismo=obj)

    def ctor_de(self, clase, linea):
        """
        Busca el primer constructor disponible en la cadena de herencia.

        Parámetros:
            clase: Clase donde comienza la búsqueda.
            linea: Línea donde se necesita el constructor.

        Retorna:
            FuncionRuta: Constructor encontrado.
            None: Si ninguna clase de la cadena tiene constructor.
        """
        for c in self.cadena(clase, linea):
            if c.params_ctor is not None:
                return FuncionRuta(c.nombre + ".armar", c.params_ctor, c.cuerpo_ctor, c.entorno, c)
        return None

    def eval_Nuevo(self, n, env):
        """
        Crea una instancia, inicializa sus atributos y ejecuta el constructor.

        Parámetros:
            n: Nodo con el nombre de la clase y los argumentos del constructor.
            env: Entorno donde se busca la clase.

        Retorna:
            Instancia: Objeto creado e inicializado.

        Excepciones:
            ErrorEjecucion: Si la clase no existe o los argumentos del constructor
            no son válidos.
        """
        e = env.buscar(n.clase)
        if e is None or not isinstance(e.vars[n.clase], ClaseRuta):
            raise ErrorEjecucion("campamento '%s' no definido" % n.clase, n.linea)
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
                raise ErrorEjecucion("el campamento '%s' no tiene 'armar' y recibió %d argumento(s)" % (clase.nombre, len(args)), n.linea)
        else:
            self.llamar(ctor, args, n.linea, mismo=obj)
        return obj

    def eval_Super(self, n, env):
        """
        Ejecuta un método o constructor de la clase padre.

        Parámetros:
            n: Nodo con el nombre del método y sus argumentos.
            env: Entorno donde se busca la clase y el objeto actual.

        Retorna:
            El resultado del método del padre o None si no hay constructor que ejecutar.

        Excepciones:
            ErrorEjecucion: Si se utiliza fuera de una clase, no existe una clase
            padre o el método solicitado no está definido.
        """
        ec = env.buscar("$clase")
        em = env.buscar("mismo")
        if ec is None or em is None:
            raise ErrorEjecucion("'superior' solo se puede usar dentro de un campamento", n.linea)
        actual, obj = ec.vars["$clase"], em.vars["mismo"]
        padre = self.padre_de(actual, n.linea)
        if padre is None:
            raise ErrorEjecucion("el campamento '%s' no extiende a ningún otro" % actual.nombre, n.linea)
        args = [self.evaluar(a, env) for a in n.args]
        if n.metodo == "armar":
            f = self.ctor_de(padre, n.linea)
            if f is None:
                if args:
                    raise ErrorEjecucion("el campamento padre no tiene 'armar'", n.linea)
                return None
        else:
            f = self.buscar_metodo(padre, n.metodo, n.linea)
            if f is None:
                raise ErrorEjecucion("el campamento padre no tiene el método '%s'" % n.metodo, n.linea)
        return self.llamar(f, args, n.linea, mismo=obj)
