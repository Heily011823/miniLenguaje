"""Historial de ejecuciones en SQLite: guarda cada programa ejecutado con su resultado."""
import os
import sqlite3
from datetime import datetime

RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_ruta.db")


def _conectar(ruta=None):
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
    """Guarda una ejecución. Nunca lanza errores: el historial no debe romper el intérprete."""
    try:
        con = _conectar(ruta)
        con.execute("INSERT INTO ejecuciones (fecha, archivo, estado, codigo, salida) VALUES (?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), archivo, estado, codigo, salida))
        con.commit()
        con.close()
        return True
    except (sqlite3.Error, OSError):
        return False


def listar(limite=20, ruta=None):
    con = _conectar(ruta)
    filas = con.execute("SELECT id, fecha, archivo, estado, codigo, salida FROM ejecuciones "
                        "ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    con.close()
    return filas


def obtener(id_, ruta=None):
    con = _conectar(ruta)
    fila = con.execute("SELECT id, fecha, archivo, estado, codigo, salida FROM ejecuciones WHERE id=?",
                       (id_,)).fetchone()
    con.close()
    return fila
