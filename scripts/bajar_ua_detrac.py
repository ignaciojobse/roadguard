"""Baja secuencias de UA-DETRAC leyendo el zip remoto por rangos HTTP.

El sitio oficial ya no sirve archivos; se usa el espejo publico de Hugging
Face `ShantyCam/ua-detrac` (`ua-detrac-orig.zip`, 9,9 GB, copia de terceros
del dataset CC BY-NC-SA). El zip no se baja entero: se lee el directorio
central del final del archivo y despues solo los bytes de las entradas que
interesan (imagenes JPG y XML de anotacion de cada secuencia).

Uso, desde la raiz del repo:

    python scripts/bajar_ua_detrac.py --listar                 # arbol del zip
    python scripts/bajar_ua_detrac.py MVI_39271                # una secuencia
    python scripts/bajar_ua_detrac.py MVI_39271 MVI_40714 MVI_40742

Escribe `datos/ua-detrac/<secuencia>/img00001.jpg...` y
`datos/ua-detrac/<secuencia>/<secuencia>.xml`. Es reanudable: las entradas
que ya estan en disco con el tamano correcto se saltan.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import requests

URL = "https://huggingface.co/datasets/ShantyCam/ua-detrac/resolve/main/ua-detrac-orig.zip"
RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "datos" / "ua-detrac"
# Tamano del bloque pedido por request al bajar imagenes consecutivas. Las
# entradas del zip de una secuencia son contiguas, asi que conviene pedir
# varios MB por vez en lugar de un request por JPG.
BLOQUE = 32 * 1024 * 1024
REINTENTOS = 6


class ArchivoRemoto(io.RawIOBase):
    """File-like de solo lectura sobre una URL con soporte de `Range`."""

    def __init__(self, url: str, sesion: requests.Session) -> None:
        self.url = url
        self.sesion = sesion
        self.pos = 0
        self.bytes_leidos = 0
        self.tamano = self._tamano()

    def _tamano(self) -> int:
        r = self._get(0, 0)
        rango = r.headers.get("Content-Range", "")
        if "/" not in rango:
            raise RuntimeError(f"El servidor no soporta Range: {r.status_code} {rango!r}")
        return int(rango.rsplit("/", 1)[1])

    def _get(self, inicio: int, fin: int) -> requests.Response:
        for intento in range(REINTENTOS):
            try:
                r = self.sesion.get(
                    self.url,
                    headers={"Range": f"bytes={inicio}-{fin}"},
                    timeout=60,
                    allow_redirects=True,
                )
                if r.status_code == 206:
                    return r
                raise RuntimeError(f"HTTP {r.status_code} al pedir bytes {inicio}-{fin}")
            except (requests.RequestException, RuntimeError) as e:
                if intento == REINTENTOS - 1:
                    raise
                espera = 2 ** intento
                print(f"  reintento {intento + 1}/{REINTENTOS} en {espera}s: {e}", file=sys.stderr)
                time.sleep(espera)
        raise AssertionError("inalcanzable")

    def leer_rango(self, inicio: int, longitud: int) -> bytes:
        if longitud <= 0:
            return b""
        fin = min(inicio + longitud, self.tamano) - 1
        datos = self._get(inicio, fin).content
        self.bytes_leidos += len(datos)
        return datos

    # Interfaz de archivo que usa zipfile.ZipFile.
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.tamano + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.tamano - self.pos
        datos = self.leer_rango(self.pos, n)
        self.pos += len(datos)
        return datos


def abrir_zip(sesion: requests.Session) -> tuple[zipfile.ZipFile, ArchivoRemoto]:
    remoto = ArchivoRemoto(URL, sesion)
    print(f"Zip remoto: {remoto.tamano / 1e9:.2f} GB; leyendo directorio central...")
    zf = zipfile.ZipFile(remoto)
    print(f"  {len(zf.infolist())} entradas, {remoto.bytes_leidos / 1e6:.1f} MB leidos")
    return zf, remoto


def entradas_de(zf: zipfile.ZipFile, secuencia: str) -> tuple[list[zipfile.ZipInfo], list[zipfile.ZipInfo]]:
    """Imagenes y XML de una secuencia, en el orden del zip."""
    imagenes = []
    xmls = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        partes = info.filename.split("/")
        nombre = partes[-1]
        if secuencia in partes[:-1] and nombre.lower().endswith(".jpg"):
            imagenes.append(info)
        elif nombre == f"{secuencia}.xml" or nombre == f"{secuencia}_v3.xml":
            xmls.append(info)
    imagenes.sort(key=lambda i: i.filename)
    return imagenes, xmls


def _extraer_local(info: zipfile.ZipInfo, datos_locales: bytes) -> bytes:
    """Descomprime una entrada a partir de sus bytes (cabecera local + datos)."""
    # La cabecera local tiene 30 bytes fijos mas nombre y extra, cuyas
    # longitudes pueden diferir de las del directorio central.
    n_nombre = int.from_bytes(datos_locales[26:28], "little")
    n_extra = int.from_bytes(datos_locales[28:30], "little")
    inicio = 30 + n_nombre + n_extra
    crudo = datos_locales[inicio : inicio + info.compress_size]
    if len(crudo) != info.compress_size:
        raise ValueError(f"{info.filename}: bytes insuficientes ({len(crudo)} de {info.compress_size})")
    if info.compress_type == zipfile.ZIP_STORED:
        return crudo
    descomp = zipfile._get_decompressor(info.compress_type)  # type: ignore[attr-defined]
    return descomp.decompress(crudo)


def bajar_secuencia(zf: zipfile.ZipFile, remoto: ArchivoRemoto, secuencia: str, destino: Path) -> int:
    imagenes, xmls = entradas_de(zf, secuencia)
    if not imagenes:
        print(f"{secuencia}: sin imagenes en el zip", file=sys.stderr)
        return 1
    carpeta = destino / secuencia
    carpeta.mkdir(parents=True, exist_ok=True)
    pendientes = [
        i for i in imagenes + xmls
        if not (carpeta / Path(i.filename).name).exists()
        or (carpeta / Path(i.filename).name).stat().st_size != i.file_size
    ]
    total_mb = sum(i.compress_size for i in pendientes) / 1e6
    print(
        f"{secuencia}: {len(imagenes)} imagenes, {len(xmls)} XML; "
        f"{len(pendientes)} pendientes ({total_mb:.1f} MB)"
    )
    pendientes.sort(key=lambda i: i.header_offset)
    t0 = time.perf_counter()
    bajados = 0
    i = 0
    while i < len(pendientes):
        # Agrupa entradas contiguas hasta BLOQUE bytes y las pide en un request.
        inicio = pendientes[i].header_offset
        j = i
        while j + 1 < len(pendientes):
            siguiente = pendientes[j + 1]
            fin_sig = siguiente.header_offset + 30 + len(siguiente.filename.encode()) + 64 + siguiente.compress_size
            if fin_sig - inicio > BLOQUE:
                break
            j += 1
        ultimo = pendientes[j]
        # Margen por la cabecera local (nombre + extra) de la ultima entrada.
        fin = ultimo.header_offset + 30 + len(ultimo.filename.encode()) + 64 + ultimo.compress_size
        bloque = remoto.leer_rango(inicio, fin - inicio)
        for info in pendientes[i : j + 1]:
            desde = info.header_offset - inicio
            contenido = _extraer_local(info, bloque[desde:])
            if len(contenido) != info.file_size:
                raise ValueError(f"{info.filename}: tamano {len(contenido)} != {info.file_size}")
            (carpeta / Path(info.filename).name).write_bytes(contenido)
            bajados += 1
        i = j + 1
        transcurrido = time.perf_counter() - t0
        print(
            f"  {bajados}/{len(pendientes)} archivos, {remoto.bytes_leidos / 1e6:.0f} MB, "
            f"{transcurrido:.0f}s",
            flush=True,
        )
    print(f"{secuencia}: listo en {carpeta}")
    return 0


def listar(zf: zipfile.ZipFile) -> None:
    carpetas: dict[str, int] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        carpeta = "/".join(info.filename.split("/")[:-1])
        carpetas[carpeta] = carpetas.get(carpeta, 0) + 1
    for carpeta, n in sorted(carpetas.items()):
        print(f"{n:6d}  {carpeta}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencias", nargs="*", help="Nombres MVI_xxxxx a bajar")
    parser.add_argument("--listar", action="store_true", help="Lista carpetas del zip y sale")
    parser.add_argument("--destino", default=str(DESTINO), help="Carpeta raiz de salida")
    args = parser.parse_args(argv)
    if not args.listar and not args.secuencias:
        parser.error("indicar al menos una secuencia o --listar")
    with requests.Session() as sesion:
        zf, remoto = abrir_zip(sesion)
        if args.listar:
            listar(zf)
            return 0
        codigo = 0
        for secuencia in args.secuencias:
            codigo |= bajar_secuencia(zf, remoto, secuencia, Path(args.destino))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
