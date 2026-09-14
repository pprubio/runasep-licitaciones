#!/usr/bin/env python3
"""Barrido de licitaciones publicas para RUNASEP S.L.

Descarga los tres ficheros ATOM de datos abiertos de la PLACSP, los filtra por
palabras clave y prioridad geografica, y deja el resultado en salida/.

Uso:
    python barrido.py                 # barrido semanal (dias de config.DIAS_ATRAS)
    python barrido.py --dias 35       # barrido mas largo
    python barrido.py --solo menores  # una sola fuente
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import config

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "salida"
HISTORICO = SALIDA / "historico"

ATOM = "{http://www.w3.org/2005/Atom}"


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #
def normaliza(texto: str) -> str:
    """Minusculas, sin acentos, espacios colapsados."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def local(tag: str) -> str:
    """Nombre de etiqueta sin namespace."""
    return tag.rsplit("}", 1)[-1]


def buscar(elem, nombre: str):
    """Primer descendiente cuyo nombre local coincide."""
    for hijo in elem.iter():
        if local(hijo.tag) == nombre:
            return hijo
    return None


def buscar_todos(elem, nombre: str) -> list:
    return [h for h in elem.iter() if local(h.tag) == nombre]


def texto(elem, nombre: str, defecto: str = "") -> str:
    n = buscar(elem, nombre)
    if n is None or n.text is None:
        return defecto
    return re.sub(r"\s+", " ", n.text).strip()


def a_fecha(iso: str):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# descarga
# --------------------------------------------------------------------------- #
def sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/atom+xml, */*"})
    return s


def normaliza_url(url: str) -> str:
    """Los enlaces 'next' apuntan al dominio antiguo; se usa el actual."""
    return url.replace("contrataciondelestado.es", "contrataciondelsectorpublico.gob.es")


def descarga(ses: requests.Session, url: str) -> str:
    for intento in range(3):
        try:
            r = ses.get(url, timeout=120)
            if r.status_code == 200:
                return r.text
            print(f"    HTTP {r.status_code} en {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"    error de red ({e}) intento {intento + 1}/3", file=sys.stderr)
        time.sleep(3 * (intento + 1))
    raise RuntimeError(f"no se pudo descargar {url}")


# --------------------------------------------------------------------------- #
# extraccion
# --------------------------------------------------------------------------- #
def extrae_entrada(entry) -> dict:
    enlace = ""
    for l in entry.findall(f"{ATOM}link"):
        href = l.get("href", "")
        if href and not l.get("rel"):
            enlace = href
            break

    resumen = texto(entry, "summary")
    estado = ""
    m = re.search(r"Estado:\s*([A-Z_]+)", resumen)
    if m:
        estado = m.group(1)
    organo = ""
    m = re.search(r"Órgano de Contratación:\s*([^;]+)", resumen)
    if m:
        organo = m.group(1).strip()

    cpvs = [c.text.strip() for c in buscar_todos(entry, "ItemClassificationCode") if c.text]
    lugares = [c.text.strip() for c in buscar_todos(entry, "CountrySubentity") if c.text]
    ciudades = [c.text.strip() for c in buscar_todos(entry, "CityName") if c.text]

    ganador = ""
    wp = buscar(entry, "WinningParty")
    if wp is not None:
        ganador = texto(wp, "Name")

    return {
        "titulo": texto(entry, "title"),
        "expediente": texto(entry, "ContractFolderID"),
        "organo": organo,
        "estado": estado or texto(entry, "ContractFolderStatusCode"),
        "importe": texto(entry, "TaxExclusiveAmount") or texto(entry, "TotalAmount"),
        "adjudicado": texto(entry, "PayableAmount"),
        "adjudicatario": ganador,
        "cpv": sorted(set(cpvs))[:6],
        "lugar": lugares[0] if lugares else "",
        "ciudad": ciudades[0] if ciudades else "",
        "plazo": texto(entry, "EndDate"),
        "actualizado": texto(entry, "updated"),
        "enlace": enlace,
        "id": texto(entry, "id"),
    }


def encaja(titulo: str) -> list[str]:
    """Devuelve las familias de palabras que coinciden, o lista vacia."""
    t = normaliza(titulo)
    for mala in config.EXCLUIR:
        if normaliza(mala) in t:
            return []
    familias = []
    for familia, palabras in config.CLAVES.items():
        if any(normaliza(p) in t for p in palabras):
            familias.append(familia)
    return familias


def prioridad(item: dict) -> str:
    donde = normaliza(f"{item['lugar']} {item['ciudad']}")
    organo = normaliza(item["organo"])
    titulo = normaliza(item["titulo"])

    for nivel in ("P1", "P2", "P3"):
        if any(normaliza(z) in donde for z in config.PRIORIDAD[nivel]):
            return nivel
    if any(normaliza(o) in organo for o in config.P4_ORGANOS):
        return "P4"
    if any(normaliza(s) in titulo for s in config.P4_SOLO_SI):
        return "P4"
    # Sin lugar publicado: se mira el organo por si es de la zona.
    if not donde:
        for nivel in ("P1", "P2"):
            if any(normaliza(z) in organo for z in config.PRIORIDAD[nivel]):
                return nivel
    return ""


# --------------------------------------------------------------------------- #
# barrido de una fuente
# --------------------------------------------------------------------------- #
def barre_fuente(ses: requests.Session, nombre: str, url: str, corte: datetime) -> dict:
    print(f"[{nombre}] arrancando", flush=True)
    resultado = {
        "fuente": nombre,
        "url": url,
        "feed_actualizado": None,
        "feed_caducado": None,
        "paginas": 0,
        "entradas_vistas": 0,
        "mas_antigua": None,
        "hits": [],
        "error": None,
    }
    vistos: set[str] = set()
    siguiente = url
    pagina = 0

    while siguiente and pagina < config.MAX_PAGINAS.get(nombre, 60):
        try:
            xml = descarga(ses, siguiente)
        except RuntimeError as e:
            resultado["error"] = str(e)
            break

        try:
            raiz = ET.fromstring(xml)
        except ET.ParseError as e:
            resultado["error"] = f"XML ilegible en pagina {pagina + 1}: {e}"
            break

        if pagina == 0:
            cab = raiz.find(f"{ATOM}updated")
            if cab is not None and cab.text:
                resultado["feed_actualizado"] = cab.text.strip()
                f = a_fecha(cab.text.strip())
                if f:
                    horas = (datetime.now(timezone.utc) - f).total_seconds() / 3600
                    resultado["feed_caducado"] = horas > config.HORAS_FEED_CADUCADO
                    print(f"[{nombre}] feed actualizado {cab.text.strip()} "
                          f"({horas:.0f} h)", flush=True)

        siguiente = None
        for l in raiz.findall(f"{ATOM}link"):
            if l.get("rel") == "next" and l.get("href"):
                siguiente = normaliza_url(l.get("href"))

        mas_antigua = None
        for entry in raiz.findall(f"{ATOM}entry"):
            resultado["entradas_vistas"] += 1
            upd = texto(entry, "updated")
            if upd:
                mas_antigua = upd
            titulo = texto(entry, "title")
            if not encaja(titulo):
                continue
            item = extrae_entrada(entry)
            if item["id"] in vistos:
                continue
            vistos.add(item["id"])
            item["familias"] = encaja(titulo)
            item["prioridad"] = prioridad(item)
            item["fuente"] = nombre
            if item["prioridad"]:
                resultado["hits"].append(item)

        if mas_antigua:
            resultado["mas_antigua"] = mas_antigua

        pagina += 1
        resultado["paginas"] = pagina

        f = a_fecha(mas_antigua) if mas_antigua else None
        if f and f < corte:
            break
        if siguiente:
            time.sleep(config.PAUSA)

    print(f"[{nombre}] {resultado['paginas']} paginas, "
          f"{resultado['entradas_vistas']} entradas, "
          f"{len(resultado['hits'])} relevantes", flush=True)
    return resultado


# --------------------------------------------------------------------------- #
# informe
# --------------------------------------------------------------------------- #
ORDEN = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


def escribe_markdown(datos: dict) -> str:
    hoy = datos["fecha"]
    L = [f"# Barrido de licitaciones — {hoy}", ""]

    caducados = [f["fuente"] for f in datos["fuentes"] if f.get("feed_caducado")]
    errores = [f for f in datos["fuentes"] if f.get("error")]
    if caducados:
        L.append(f"> **AVISO: feed(s) sin actualizar hace más de "
                 f"{config.HORAS_FEED_CADUCADO} h: {', '.join(caducados)}.** "
                 f"Un feed parado y un feed sin novedades se parecen demasiado: "
                 f"lo que falte de esa fuente NO significa que no haya nada.")
        L.append("")
    for f in errores:
        L.append(f"> **ERROR en {f['fuente']}: {f['error']}**")
    if errores:
        L.append("")

    L.append("## Estado de las fuentes")
    L.append("")
    L.append("| Fuente | Feed actualizado | Páginas | Entradas | Relevantes |")
    L.append("|---|---|---:|---:|---:|")
    for f in datos["fuentes"]:
        L.append(f"| {f['fuente']} | {f.get('feed_actualizado') or '—'} | "
                 f"{f['paginas']} | {f['entradas_vistas']} | {len(f['hits'])} |")
    L.append("")

    hits = datos["resultados"]
    L.append(f"**Total relevantes: {len(hits)}** "
             f"(P1 {sum(1 for h in hits if h['prioridad'] == 'P1')} · "
             f"P2 {sum(1 for h in hits if h['prioridad'] == 'P2')} · "
             f"P3 {sum(1 for h in hits if h['prioridad'] == 'P3')} · "
             f"P4 {sum(1 for h in hits if h['prioridad'] == 'P4')})")
    L.append("")

    if datos["seguimiento"]:
        L.append("## Expedientes en seguimiento que han aparecido")
        L.append("")
        for s in datos["seguimiento"]:
            L.append(f"- **{s['expediente']}** — {s['nota']} · estado actual: "
                     f"`{s['estado'] or '—'}` · actualizado {s['actualizado'][:10]}")
        L.append("")

    for nivel in ("P1", "P2", "P3", "P4"):
        grupo = [h for h in hits if h["prioridad"] == nivel]
        if not grupo:
            continue
        L.append(f"## {nivel} — {len(grupo)} expedientes")
        L.append("")
        L.append("| Expediente | Objeto | Órgano | Lugar | Importe | Estado | Plazo | Enlace |")
        L.append("|---|---|---|---|---:|---|---|---|")
        for h in grupo:
            obj = h["titulo"].replace("|", "/")[:110]
            org = (h["organo"] or "").replace("|", "/")[:55]
            imp = h["adjudicado"] or h["importe"] or ""
            enl = f"[ficha]({h['enlace']})" if h["enlace"] else "—"
            L.append(f"| `{h['expediente']}` | {obj} | {org} | "
                     f"{h['lugar'] or h['ciudad']} | {imp} | {h['estado']} | "
                     f"{h['plazo'] or ''} | {enl} |")
        L.append("")

    L.append("---")
    L.append("")
    L.append(f"Generado automáticamente el {datos['generado']} por "
             f"`barrido.py`. Fuente: ficheros de sindicación de datos abiertos "
             f"de la Plataforma de Contratación del Sector Público.")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=None,
                    help="días hacia atrás (por defecto, los de config.py)")
    ap.add_argument("--solo", default=None, help="una sola fuente: licitaciones|agregadas|menores")
    args = ap.parse_args()

    SALIDA.mkdir(exist_ok=True)
    HISTORICO.mkdir(exist_ok=True)

    ses = sesion()
    fuentes = []
    for nombre, url in config.FEEDS.items():
        if args.solo and nombre != args.solo:
            continue
        dias = args.dias or config.DIAS_ATRAS.get(nombre, 9)
        corte = datetime.now(timezone.utc) - timedelta(days=dias)
        fuentes.append(barre_fuente(ses, nombre, url, corte))

    hits = [h for f in fuentes for h in f["hits"]]
    hits.sort(key=lambda h: (ORDEN.get(h["prioridad"], 9), h["actualizado"]), reverse=False)

    seguimiento = []
    for h in hits:
        for exp, nota in config.SEGUIMIENTO.items():
            if exp.lower() in (h["expediente"] or "").lower():
                seguimiento.append({"expediente": h["expediente"], "nota": nota,
                                    "estado": h["estado"], "actualizado": h["actualizado"]})

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    datos = {
        "fecha": hoy,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuentes": [{k: v for k, v in f.items() if k != "hits"} | {"hits": f["hits"]}
                    for f in fuentes],
        "resultados": hits,
        "seguimiento": seguimiento,
    }

    (SALIDA / "ultimo.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (HISTORICO / f"{hoy}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    md = escribe_markdown(datos)
    (SALIDA / "ultimo.md").write_text(md, encoding="utf-8")
    (HISTORICO / f"{hoy}.md").write_text(md, encoding="utf-8")

    print(f"\nListo. {len(hits)} expedientes relevantes en salida/ultimo.md")
    if any(f.get("feed_caducado") for f in fuentes):
        print("AVISO: alguna fuente esta parada. Revisa la cabecera del informe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
