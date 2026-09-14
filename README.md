# runasep-licitaciones

Vigilancia automática de licitaciones públicas para **RUNASEP S.L.** (Elche, Alicante).

Descarga los tres ficheros de datos abiertos de la Plataforma de Contratación del Sector
Público, los filtra por palabras clave y prioridad geográfica, y deja el resultado en
`salida/`. Corre solo en GitHub Actions: **no depende de ningún ordenador encendido**.

## Para qué existe

El barrido lo hacía el navegador del Mac, y eso obliga a tener la máquina despierta a la
hora exacta. Aquí el trabajo pesado —descargar y filtrar varios cientos de megas de XML—
lo hace GitHub gratis, y Claude solo lee el resultado, que son unos pocos kilobytes.

## Puesta en marcha

```bash
cd ~/Developer
mkdir runasep-licitaciones && cd runasep-licitaciones
# copiar aquí los archivos de este paquete
git init -b main
git add .
git commit -m "Barrido de licitaciones PLACSP"
```

Después, en GitHub Desktop: *Add existing repository* → *Publish repository*.

**Publícalo como repositorio PÚBLICO.** No contiene ningún dato de la empresa: solo código
y expedientes de contratación pública que ya son públicos por ley. Es lo que permite que
Claude lea `salida/ultimo.json` desde la nube sin credenciales. Si lo dejas privado,
funciona igual pero el informe hay que pasárselo a mano.

En el repo, pestaña **Settings → Actions → General → Workflow permissions**, marca
*Read and write permissions*. Sin eso el workflow no puede publicar el resultado.

## Cuándo corre

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `barrido-semanal.yml` | viernes 05:00 UTC | Las tres fuentes, últimos 9 días |
| `barrido-mensual.yml` | día 1, 04:00 UTC | Solo contratos menores, últimos 35 días |

Los dos se pueden lanzar a mano desde la pestaña **Actions → Run workflow**.

## Qué produce

```
salida/
├── ultimo.json                 # resultado de la última ejecución (lo lee Claude)
├── ultimo.md                   # el mismo informe, legible
├── historico/AAAA-MM-DD.{json,md}
└── mensual/menores-AAAA-MM.{json,md}
```

El informe empieza siempre por el **estado de las tres fuentes**. Si alguna lleva más de
48 h sin actualizarse lo dice en primera línea, porque un feed parado y un feed sin
novedades se parecen demasiado: el 8 de septiembre de 2026 el fichero principal se quedó
congelado seis días sin avisar de nada.

## Qué se toca

Todo lo ajustable está en `config.py`: fuentes, días hacia atrás, palabras clave,
exclusiones, prioridad geográfica y expedientes en seguimiento. `barrido.py` es el motor y
normalmente no hay que abrirlo.

Aviso sobre las palabras: **no basta con buscar «dron»**. Los dos mejores expedientes de
septiembre de 2026 —el 74/26 de Alicante, con 1,32 M€ en el lote forestal, y el
O4S-205/2025 de la Diputación— no contienen esa palabra. Y ojo con la cadena `rpas`, que
vive dentro de «carpas»: por eso hay una lista de exclusiones.

## Prioridad geográfica

| Nivel | Ámbito | Criterio |
|---|---|---|
| P1 | Alicante | Todo, sin mínimo de importe |
| P2 | Murcia, Valencia, Albacete, Castellón | Todo servicio de tratamiento, forestal o teledetección |
| P3 | Resto de CV, CLM, Andalucía oriental, Aragón sur | Solo licitación con publicidad |
| P4 | Resto de España | Solo si menciona dron, es acuerdo marco, o es TRAGSA / ministerio / confederación |

## Probar en local

```bash
pip install -r requirements.txt
python barrido.py --solo menores --dias 2
```

## Fuentes

Ficheros de sindicación de datos abiertos de la PLACSP, publicados por la Dirección
General del Patrimonio del Estado para su reutilización al amparo de la Ley 37/2007. El
propio Ministerio distribuye **OpenPLACSP**, una herramienta libre que descarga estos
mismos ficheros. El script los pide con una pausa de un segundo entre páginas y se
identifica con un User-Agent propio.

- Licitaciones: `sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom`
- Agregadas de CCAA: `sindicacion_1044/PlataformasAgregadasSinMenores.atom`
- Contratos menores: `sindicacion_1143/contratosMenoresPerfilesContratantes.atom`
