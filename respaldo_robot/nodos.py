"""Nodos del árbol sintáctico (AST) de Tramo."""
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass
class Nodo:
    linea: int


# ---------- Sentencias ----------
@dataclass
class Declarar(Nodo):
    nombre: str
    valor: Any            # None si se declara sin valor inicial

@dataclass
class Asignar(Nodo):
    destino: Any          # Var, Atributo o Indice
    valor: Any

@dataclass
class Imprimir(Nodo):
    valor: Any

@dataclass
class Leer(Nodo):
    destino: Any          # Var, Atributo o Indice

@dataclass
class Si(Nodo):
    ramas: List[Tuple[Any, list]]     # [(condicion, bloque), ...]
    sino: Optional[list] = None

@dataclass
class Mientras(Nodo):
    cond: Any
    cuerpo: list

@dataclass
class Rondar(Nodo):                   # do-while
    cuerpo: list
    cond: Any

@dataclass
class Para(Nodo):
    var: str
    desde: Any
    hasta: Any
    cuerpo: list

@dataclass
class Bifurcar(Nodo):                 # switch
    expr: Any
    casos: List[Tuple[Any, list]]
    defecto: Optional[list] = None

@dataclass
class Funcion(Nodo):
    nombre: str
    params: List[str]
    cuerpo: list

@dataclass
class Retorno(Nodo):
    valor: Any

@dataclass
class Clase(Nodo):
    nombre: str
    padre: Optional[str]
    params_ctor: Optional[List[str]]  # None si no declara 'ensamblar'
    cuerpo_ctor: list
    metodos: List[Funcion]
    campos: List[Declarar]            # atributos con valor por defecto

@dataclass
class Intentar(Nodo):
    cuerpo: list
    var_error: Optional[str]
    capturar: Optional[list]
    final: Optional[list] = None

@dataclass
class Lanzar(Nodo):
    valor: Any

@dataclass
class Romper(Nodo):
    pass

@dataclass
class Continuar(Nodo):
    pass

@dataclass
class ExprSentencia(Nodo):
    expr: Any


# ---------- Expresiones ----------
@dataclass
class Literal(Nodo):
    valor: Any

@dataclass
class Var(Nodo):
    nombre: str

@dataclass
class Binario(Nodo):
    op: str
    izq: Any
    der: Any

@dataclass
class Unario(Nodo):
    op: str
    operando: Any

@dataclass
class Llamada(Nodo):
    nombre: str
    args: list

@dataclass
class LlamadaMetodo(Nodo):
    objeto: Any
    nombre: str
    args: list

@dataclass
class Atributo(Nodo):
    objeto: Any
    nombre: str

@dataclass
class Indice(Nodo):
    objeto: Any
    indice: Any

@dataclass
class Lista(Nodo):
    elementos: list

@dataclass
class Nuevo(Nodo):
    clase: str
    args: list

@dataclass
class Mismo(Nodo):
    pass

@dataclass
class Super(Nodo):                    # superior.metodo(args) / superior.ensamblar(args)
    metodo: str
    args: list
