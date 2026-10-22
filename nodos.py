"""Nodos del árbol sintáctico (AST) de Tramo."""
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass
class Nodo:
    """ Clase base de los nodos del árbol sintáctico.

    Parámetros:
        linea: número de línea del código fuente donde aparece el nodo.
    """
    linea: int


# ---------- Sentencias ----------
@dataclass
class Declarar(Nodo):
    """ Representa la declaración de una variable.

    Parámetros:
        nombre: nombre de la variable.
        valor: valor inicial de la variable o None si no se inicializa.
    """
    nombre: str
    valor: Any            # None si se declara sin valor inicial

@dataclass
class Asignar(Nodo):
    """ Representa la asignación de un valor a un destino.

    Parámetros:
        destino: variable, atributo o elemento de una colección.
        valor: expresión en donde el resultado se asignará al destino.
    """
    destino: Any          # Var, Atributo o Indice
    valor: Any

@dataclass
class Imprimir(Nodo):
    """ Representa una instrucción que muestra un valor.

    Parámetros:
        valor: expresión que se mostrará en la salida.
    """
    valor: Any

@dataclass
class Leer(Nodo):
    """ Representa la lectura de un dato de entrada.

    Parámetros:
        destino: variable, atributo o elemento donde se guardará el dato.
    """
    destino: Any          # Var, Atributo o Indice

@dataclass
class Si(Nodo):
    """ Representa una estructura condicional.

    Parámetros:
        ramas: lista de pares con una condición y su bloque de instrucciones.
        sino: bloque alternativo que se ejecuta si ninguna condición se cumple.
    """
    ramas: List[Tuple[Any, list]]     # [(condicion, bloque), ...]
    sino: Optional[list] = None

@dataclass
class Mientras(Nodo):
    """ Representa un ciclo que se repite mientras una condición sea verdadera.

    Parámetros:
        cond: condición que controla la repetición.
        cuerpo: instrucciones que se ejecutan en cada iteración.
    """
    cond: Any
    cuerpo: list

@dataclass
class Rondar(Nodo): # do-while
    """ Representa un ciclo que ejecuta el cuerpo antes de comprobar la condición.

    Parámetros:
        cuerpo: instrucciones que se ejecutan en el ciclo.
        cond: condición que determina si el ciclo continúa.
    """                  
    cuerpo: list
    cond: Any

@dataclass
class Para(Nodo):
    """ Representa un ciclo controlado por una variable.

    Parámetros:
        var: nombre de la variable de control.
        desde: valor inicial del recorrido.
        hasta: límite del recorrido.
        cuerpo: instrucciones que se ejecutan en cada iteración.
    """
    var: str
    desde: Any
    hasta: Any
    cuerpo: list

@dataclass
class Bifurcar(Nodo):                 # switch
    """ Representa una selección entre distintos casos.

    Parámetros:
        expr: expresión cuyo resultado se compara con los casos.
        casos: lista de pares con un valor y su bloque de instrucciones.
        defecto: bloque que se ejecuta si ningún caso coincide.
    """
    expr: Any
    casos: List[Tuple[Any, list]]
    defecto: Optional[list] = None

@dataclass
class Funcion(Nodo):
    """ Representa la definición de una función.

    Parámetros:
        nombre: nombre de la función.
        params: nombres de los parámetros que recibe.
        cuerpo: instrucciones que forman la función.
    """
    nombre: str
    params: List[str]
    cuerpo: list

@dataclass
class Retorno(Nodo):
    """ Representa la devolución de un valor desde una función.

    Parámetros:
        valor: expresión en el cual el resultado se devuelve.
    """
    valor: Any

@dataclass
class Clase(Nodo):
    """ Representa la definición de una clase.

    Parámetros:
        nombre: nombre de la clase.
        padre: nombre de la clase heredada, si existe.
        params_ctor: parámetros del constructor o None si no declara 'armar'.
        cuerpo_ctor: instrucciones del constructor.
        metodos: métodos definidos en la clase.
        campos: atributos con valores predeterminados.
    """
    nombre: str
    padre: Optional[str]
    params_ctor: Optional[List[str]]  # None si no declara 'armar'
    cuerpo_ctor: list
    metodos: List[Funcion]
    campos: List[Declarar]            # atributos con valor por defecto

@dataclass
class Intentar(Nodo):
    """ Representa una estructura para administrar excepciones.

    Parámetros:
        cuerpo: instrucciones que se intentan ejecutar.
        var_error: nombre de la variable que recibe el error, si se declara.
        capturar: bloque que administra la excepción.
        final: bloque opcional que se ejecuta al finalizar.
    """
    cuerpo: list
    var_error: Optional[str]
    capturar: Optional[list]
    final: Optional[list] = None

@dataclass
class Lanzar(Nodo):
    """ Representa el lanzamiento de una excepción.

    Parámetros:
        valor: expresión que proporciona el error o valor lanzado.
    """
    valor: Any

@dataclass
class Romper(Nodo):
    """ Representa la instrucción para interrumpir un ciclo. """
    pass

@dataclass
class Continuar(Nodo):
    """ Representa la instrucción para pasar a la siguiente iteración. """
    pass

@dataclass
class ExprSentencia(Nodo):
    """ Representa una expresión utilizada como instrucción.

    Parámetros:
        expr: expresión que se evalúa como parte de una sentencia.
    """
    expr: Any


# ---------- Expresiones ----------
@dataclass
class Literal(Nodo):
    """ Representa un valor literal del lenguaje.

    Parámetros:
        valor: valor directo, como un número, texto o valor lógico.
    """
    valor: Any

@dataclass
class Var(Nodo):
    """ Representa el acceso a una variable.

    Parámetros:
        nombre: nombre de la variable.
    """
    nombre: str

@dataclass
class Binario(Nodo):
    """ Representa una operación entre dos expresiones.

    Parámetros:
        op: operador que se utiliza, como suma, resta o comparación.
        izq: expresión del lado izquierdo.
        der: expresión del lado derecho.
    """
    op: str
    izq: Any
    der: Any

@dataclass
class Unario(Nodo):
    """ Representa una operación aplicada a una sola expresión.

    Parámetros:
        op: operador.
        operando: expresión sobre la que se aplica el operador.
    """
    op: str
    operando: Any

@dataclass
class Llamada(Nodo):
    """ Representa una llamada a una función.

    Parámetros:
        nombre: nombre de la función llamada.
        args: argumentos enviados a la función.
    """
    nombre: str
    args: list

@dataclass
class LlamadaMetodo(Nodo):
    """ Representa la llamada a un método de un objeto.

    Parámetros:
        objeto: objeto sobre el que se invoca el método.
        nombre: nombre del método.
        args: argumentos enviados al método.
    """
    objeto: Any
    nombre: str
    args: list

@dataclass
class Atributo(Nodo):
    """ Representa el acceso a un atributo de un objeto.

    Parámetros:
        objeto: objeto del que se obtiene el atributo.
        nombre: nombre del atributo.
    """
    objeto: Any
    nombre: str

@dataclass
class Indice(Nodo):
    """ Representa el acceso a un elemento mediante un índice.

    Parámetros:
        objeto: colección a la que se accede.
        indice: expresión que indica la posición del elemento.
    """
    objeto: Any
    indice: Any

@dataclass
class Lista(Nodo):
    """ Representa una lista de elementos.

    Parámetros:
        elementos: expresiones que forman la lista.
    """
    elementos: list

@dataclass
class Nuevo(Nodo):
    """ Representa la creación de un objeto de una clase.

    Parámetros:
        clase: nombre de la clase que se instancia.
        args: argumentos enviados al constructor.
    """
    clase: str
    args: list

@dataclass
class Mismo(Nodo):
    """ Representa la referencia al objeto actual mediante 'mismo'. """
    pass

@dataclass
class Super(Nodo):                    # superior.metodo(args) / superior.armar(args)
    """ Representa el acceso a un método o constructor de la clase padre.

    Parámetros:
        metodo: nombre del método o constructor que se invoca.
        args: argumentos enviados a la llamada.
    """
    metodo: str
    args: list
