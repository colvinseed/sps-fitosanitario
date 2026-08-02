# Actualización — sps-fitosanitario

**v1.1 · 01-08-2026 · © 2026 Winston Colvin — South Pacific Seeds Chile**

Contiene cinco archivos: dos correcciones funcionales y tres cambios de presentación.

---

## 1. Cómo copiar

La estructura de carpetas reproduce la del repositorio. Copie **archivo por archivo**,
sobrescribiendo el existente.

    .github/workflows/daily.yml          → sobrescribe
    .github/workflows/tablero.yml        → sobrescribe
    src/agromet_tablero.py               → sobrescribe
    src/template.html                    → sobrescribe
    index.html                           → sobrescribe (raíz)
    assets/logo-sps-blanco.png           → archivo nuevo

**ADVERTENCIA.** No reemplace las carpetas completas. `src/` contiene doce archivos en
el repositorio y aquí sólo van dos. Reemplazar la carpeta eliminaría los diez restantes:

    agromet_extractor.py    build_artifact.py    disease_models.py    docs.json
    docs_en.json            refs.json            run_daily.py         ui.json
    validar_estaciones.py   vilab_extractor.py

Lo mismo aplica a `assets/`, que ya contiene `logo-320.png` y `logo-max.png`.

### Sobre `index.html`

Se incluye para que el logo y el pie se vean de inmediato, sin esperar la corrida diaria.

No está editado a mano ni reconstruido de forma aproximada. `build_artifact.py` no hace
más que sustituir cuatro bloques dentro de la plantilla: `/*__DATA__*/`,
`/*__TABLERO__*/`, `/*__NAME2ID__*/` y `/*__UPDATED__*/`. No transforma nada más. Por eso
este `index.html` se obtuvo aplicando al artefacto publicado exactamente los mismos
cambios que a la plantilla, y es idéntico al que habría emitido el bot con los datos de
la corrida del 2026-08-01 10:55.

Se verificó línea a línea: 23 líneas modificadas, todas correspondientes al logo, al pie
y a sus reglas CSS. Los bloques de datos inyectados quedaron intactos. El tamaño pasa de
396.501 a 402.998 B, +6.502 B (+1,6 %), atribuibles al logo en base64.

De todos modos, este archivo lo regenerará el bot en la próxima corrida diaria. **No lo
edite a mano en el futuro:** hacerlo crea divergencia entre la plantilla y el artefacto
publicado, y el cambio se pierde en la corrida siguiente.

---

## 2. Qué cambia cada archivo

### `.github/workflows/tablero.yml` — v1.2

Corrige la causa por la que el tablero horario dejó de actualizarse.

`pip install requests` pasa a `pip install -r requirements.txt`. El script
`agromet_tablero.py` importa `agromet_extractor.py`, que a su vez requiere pandas.
Instalando sólo requests, la importación fallaba, la excepción se capturaba en silencio,
el script terminaba con código 0 sin escribir nada y la corrida quedaba **verde sin
generar commit**.

Se agrega además `git pull --rebase origin main` antes del push: con el tablero
nuevamente operativo, dos workflows escriben `condiciones.json` y el push puede fallar
por *non-fast-forward* si las corridas se cruzan.

### `src/agromet_tablero.py` — v1.2

Dos correcciones y un endurecimiento.

1. `os.makedirs()` ya no se invoca con ruta vacía. Con `--out condiciones.json`,
   `os.path.dirname()` devuelve `''` y `os.makedirs('')` lanza `FileNotFoundError`.
2. La excepción de importación ya no se silencia: se informa la causa por consola.
3. Ante lista de estaciones vacía o extracción sin datos, el script termina con
   **código 1**. La corrida sale roja en Actions en lugar de verde-sin-commit.

El punto 3 es el que evita que una regresión de este tipo vuelva a pasar inadvertida.

### `.github/workflows/daily.yml` — v1.1

Único cambio: `git pull --rebase origin main` antes del push, por el mismo motivo de
concurrencia descrito arriba.

### `src/template.html` — v3.2

- **v3.1** — Logo corporativo SPS en la banda azul superior. Versión monocroma blanca
  embebida en base64 (4.533 B de PNG → 5,9 KB), altura 44 px en escritorio y 34 px bajo
  520 px de ancho.
- **v3.2** — El sello de versión, fecha de corrida y propiedad se traslada de la
  cabecera al pie, en una sola línea centrada de 10 px.

**No modificar la clase `.stamp` ni el formato de fecha.** La función `setUpdStamps()`
localiza ese elemento con `querySelector('.stamp')`, extrae la fecha mediante la
expresión regular `/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/` y la replica en los ocho
elementos `.upd-stamp` de las páginas de enfermedad. Alterar la clase o el formato deja
esas ocho páginas sin marca de actualización.

El pie usa la clase `.sitefoot`, no `.foot`: esta última ya está en uso en el bloque de
notas de cada página de enfermedad.

### `assets/logo-sps-blanco.png`

PNG 140 × 120 px con canal alfa, tinta blanca. Es la versión monocroma del isotipo
corporativo, generada porque el logo original —azul oscuro, luminancia media 73— resulta
ilegible sobre la banda `#14366E`, de luminancia 50. Se incluye suelto para otros usos;
la cabecera no lo consume, porque lleva el logo embebido.

---

## 3. Verificación después del commit

1. **Actions → "Tablero de condiciones SPS (horario)" → Run workflow.**
   Resultado esperado: corrida verde y un commit `Condiciones actuales …`.
   Si sale roja, el log indica la causa exacta: ése es el comportamiento correcto ahora.

2. **Actions → "Pronóstico fitosanitario diario SPS" → Run workflow.** *(opcional)*
   Ya no es necesario para ver el logo y el pie, porque el `index.html` incluido los
   trae. Sirve para confirmar que la corrida regenera correctamente el artefacto desde
   la plantilla v3.2 y que el resultado coincide con lo entregado.

3. **Abrir la página publicada.** Comprobar: logo en la banda azul; sello ausente de la
   cabecera y presente al pie; y, dentro de cualquier página de enfermedad, que la marca
   de actualización siga mostrando la fecha (confirma que `setUpdStamps()` localiza el
   sello en su nueva posición).

---

## 4. Pendientes no cubiertos por esta entrega

- **Cambio a horario de verano de Chile en septiembre.** Los `cron` de GitHub Actions
  corren en UTC y no se ajustan solos. Verificar el desplazamiento cuando cambie la hora.
- **Íconos de la aplicación.** Verificado el 01-08-2026: los cuatro PNG y `manifest.json`
  están presentes en la raíz del repositorio y coinciden con lo declarado en el `<head>`.
  El punto queda cerrado.
