"""Historial de ejecuciones en SQLite: guarda cada programa ejecutado con su resultado."""

# Importaciones necesarias para manejar rutas, bases de datos y fechas.
import os
import sqlite3
from datetime import datetime

# Guarda la ruta de la base de datos en la misma carpeta de este archivo.
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_ruta.db")


def _conectar(ruta=None):
    """ Abre la conexión con la base de datos y crea la tabla si no existe.

    Parámetros:
        ruta: ruta opcional de la base de datos. Si no se indica, se utiliza la ruta guardada en RUTA_BD.

    Retorna:
        La conexión con la base de datos.
    """
    con = sqlite3.connect(ruta or RUTA_BD)
    con.execute("""CREATE TABLE IF NOT EXISTS ejecuciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        archivo TEXT,
        estado TEXT NOT NULL,
        codigo TEXT NOT NULL,
        salida TEXT NOT NULL)""")
    return con


def guardar(archivo, codigo, salida, estado, ruta=None):
    """ Guarda los datos de una ejecución en la base de datos.

    Parámetros:
        archivo: nombre o ruta del archivo ejecutado.
        codigo: código fuente del programa.
        salida: resultado que produjo la ejecución.
        estado: indica si la ejecución terminó correctamente o con errores.
        ruta: ruta opcional de la base de datos.

    Retorna:
        True si los datos se guardaron correctamente.
        False si ocurre un error de SQLite o del sistema de archivos.
    """
    try:
        con = _conectar(ruta)
        # Inserta los datos de la ejecución en la tabla.
        con.execute("INSERT INTO ejecuciones (fecha, archivo, estado, codigo, salida) VALUES (?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), archivo, estado, codigo, salida))
        # Confirma los cambios y cierra la conexión.
        con.commit()
        con.close()
        return True

    # Si ocurre un error al guardar, devuelve False.
    except (sqlite3.Error, OSError):
        return False



def listar(limite=20, ruta=None):
    """ Consulta las ejecuciones guardadas en la base de datos.

    Parámetros:
        limite: cantidad máxima de registros que se quieren consultar. Por defecto, devuelve hasta 20 ejecuciones.
        ruta: ruta opcional de la base de datos.

    Retorna:
        Una lista con los registros ordenados del más reciente
        al más antiguo. Cada registro contiene su identificador,
        fecha, archivo, estado, código y salida.
    """
    con = _conectar(ruta)

    # Organiza los registros desde el más reciente hasta el más antiguo.
    filas = con.execute("SELECT id, fecha, archivo, estado, codigo, salida FROM ejecuciones "
                        "ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    con.close()
    return filas


def obtener(id_, ruta=None):
    """ Busca una ejecución específica mediante su identificador.

    Parámetros:
        id_: identificador de la ejecución que se quiere consultar.
        ruta: ruta opcional de la base de datos.

    Retorna:
        Una tupla con los datos de la ejecución si existe.
        Devuelve None si no se encuentra ningún registro con ese ID.
    """
    con = _conectar(ruta)

    # Consulta todos los datos del registro seleccionado.
    fila = con.execute("SELECT id, fecha, archivo, estado, codigo, salida FROM ejecuciones WHERE id=?",
                       (id_,)).fetchone()
    con.close()
    return fila
