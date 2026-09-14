"""Configuración del barrido de licitaciones de RUNASEP.

Todo lo que se toca a mano está aquí. El motor está en barrido.py y no hace falta abrirlo.
"""

# --- Fuentes oficiales -------------------------------------------------------
# Ficheros ATOM de datos abiertos de la Plataforma de Contratación del Sector
# Público (Ministerio de Hacienda). Publicados para reutilización al amparo de
# la Ley 37/2007. El propio Ministerio distribuye OpenPLACSP, que descarga
# exactamente estos mismos ficheros.
FEEDS = {
    "licitaciones": "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom",
    "agregadas":    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1044/PlataformasAgregadasSinMenores.atom",
    "menores":      "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1143/contratosMenoresPerfilesContratantes.atom",
}

# Cuántos días hacia atrás barre cada fuente en la ejecución semanal.
DIAS_ATRAS = {"licitaciones": 9, "agregadas": 9, "menores": 9}

# Tope de páginas por fuente, por seguridad. Cada página son 2-4 MB.
MAX_PAGINAS = {"licitaciones": 120, "agregadas": 60, "menores": 120}

# Horas sin actualizarse a partir de las cuales se considera que el feed está parado.
HORAS_FEED_CADUCADO = 48

# Segundos de espera entre descargas. No bajar de 0.5.
PAUSA = 1.0

USER_AGENT = (
    "RUNASEP-licitaciones/1.0 (vigilancia propia de contratacion publica; "
    "j.rubio@runasep.com)"
)

# --- Palabras ----------------------------------------------------------------
# Se comparan en minúsculas y sin acentos contra el TÍTULO del expediente.
# No buscar solo "dron": los dos mejores expedientes de septiembre de 2026
# (74/26 de Alicante y O4S-205/2025 de la Diputación) no contienen esa palabra.
CLAVES = {
    "nucleo": [
        "dron", "rpas", "uas ", "aeronave no tripulad", "no tripulad",
        "pulverizacion aerea", "aplicacion aerea", "aplicaciones aereas",
        "tratamiento aereo", "tratamientos aereos",
        "fitosanit", "sanidad vegetal", "sanidad forestal",
        "procesionaria", "thaumetopoea", "plaga forestal", "control de plagas",
    ],
    "forestal": [
        "tratamientos selvicolas", "selvicol", "silvicol", "limpieza silvicola",
        "prevencion de incendios forestales", "plan local de prevencion",
        "faja perimetral", "fajas perimetrales", "interfaz urbano-forestal",
        "monte de utilidad publica", "montes de utilidad publica",
        "masa forestal", "masas forestales", "pinar", "pinos",
        "desbroce", "restauracion forestal", "cubierta vegetal",
        "repoblac", "reforest", "siembra", "gestion forestal",
    ],
    "urbano_agricola": [
        "arbolado", "zonas verdes", "infraestructuras verdes", "espacios verdes",
        "palmera", "picudo", "endoterapia", "poda", "jardiner",
        "agricultura de precision", "bioestimul", "abonado", "fertilizac",
    ],
    "teledeteccion": [
        "teledetec", "fotogrametr", "ortofoto", "cartograf", "lidar",
        "multiespectral", "hiperespectral", "inspeccion aerea",
        "monitorizacion aerea", "vigilancia aerea",
    ],
}

# Si el título contiene alguna de estas, se descarta aunque haya coincidido antes.
EXCLUIR = [
    "carpa",                    # la cadena "rpas" vive dentro de "carpas"
    "tratamiento de agua", "tratamiento de aguas",
    "tratamiento de residuos", "residuos solidos urbanos",
    "legionel", "desratizacion", "desinsectacion", "desratonizacion",
    "extintor", "proteccion contra incendios", "contraincendios",
    "deteccion de incendios", "bocas de incendio",
    "espectaculo", "exhibicion de drones", "show de drones",
    "curso de piloto", "curso practico", "formacion de piloto",
    "simulador", "aeromodelismo",
    "adquisicion de un dron", "suministro de drones", "compra de dron",
    "seguro de responsabilidad civil",
]

# --- Prioridad geográfica ----------------------------------------------------
# Se mira el lugar de ejecución y, si falta, el municipio del órgano.
PRIORIDAD = {
    "P1": ["alicante", "alacant"],
    "P2": ["murcia", "albacete", "valencia", "valència", "castellon", "castelló"],
    "P3": ["comunitat valenciana", "comunidad valenciana", "castilla-la mancha",
           "castilla la mancha", "cuenca", "ciudad real", "toledo", "guadalajara",
           "almeria", "granada", "jaen", "teruel", "zaragoza"],
}

# En P4 (resto de España) solo entra lo que cumpla una de estas condiciones.
P4_SOLO_SI = [
    "dron", "no tripulad", "pulverizacion aerea", "aplicacion aerea",
    "acuerdo marco", "sistema dinamico",
]
P4_ORGANOS = ["tragsa", "tragsatec", "confederacion hidrografica", "ministerio",
              "parques nacionales", "miteco", "organismo autonomo parques"]

# --- Expedientes en seguimiento ---------------------------------------------
# Si alguno aparece en el barrido, se marca en el informe aunque no cambie nada.
SEGUIMIENTO = {
    "74/26": "Ayto. de Alicante, Lote 2 forestal. Plazo SUSPENDIDO desde 02/09/2026.",
    "TSA0083835": "TRAGSA, tratamiento citricola con dron. Adjudicacion en curso.",
    "TSA0081856": "TRAGSA, insectos esteriles CV. Anuncio previo esperado en octubre.",
    "V-01/26-01": "Canales del Taibilla. En evaluacion.",
    "22706.26.004": "CH Segura, invasoras. En evaluacion.",
    "PSS/2026/0000027860": "Extremadura, pudenta del arroz. Convocatoria en abril.",
}
