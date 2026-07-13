# Sistema de pronóstico fitosanitario diario — Guía de despliegue

**South Pacific Seeds Chile** · v1.0 · 2026-07-13
© 2026 Winston Colvin — South Pacific Seeds Chile

Este documento explica cómo desplegar el sistema que, **cada mañana y de forma automática**, extrae los datos de las estaciones desde vilab, calcula las seis enfermedades y publica una página bilingüe que se muestra en el sitio de Squarespace de SPS Chile.

---

## 1. Cómo funciona (visión general)

```
  ┌─────────────────┐   cada día 06:00      ┌──────────────────────┐
  │  GitHub Actions │ ────────────────────► │ 1. Extrae de vilab   │
  │  (planificador) │                       │ 2. Calcula 6 enferm. │
  └─────────────────┘                       │ 3. Genera index.html │
                                            └──────────┬───────────┘
                                                       │ publica
                                                       ▼
                                            ┌──────────────────────┐
                                            │  URL pública fija     │
                                            │  (GitHub Pages)       │
                                            └──────────┬───────────┘
                                                       │ iframe
                                                       ▼
                                            ┌──────────────────────┐
                                            │  Página en Squarespace│
                                            │  (iPhone / Android /  │
                                            │   escritorio)         │
                                            └──────────────────────┘
```

Puntos clave del diseño:

- **Las credenciales de vilab nunca están en el código.** Se guardan cifradas en GitHub Secrets y solo las lee el proceso en tiempo de ejecución.
- **Squarespace solo muestra.** No calcula ni se conecta a vilab (no puede). Muestra, dentro de un iframe, la página que el proceso publica.
- **Actualización diaria, visualización de 7 días móviles.** Cada día se recalcula, y la página muestra siempre la última semana para leer la tendencia.

---

## 2. Requisitos previos

- Una cuenta de **GitHub** (gratuita) para alojar el repositorio y correr Actions.
- Las **credenciales de vilab** (usuario y contraseña) de una cuenta con acceso a las estaciones.
- Acceso de edición al sitio de **Squarespace** de SPS Chile (para insertar el bloque de código).

---

## 3. Despliegue paso a paso

### 3.1 Subir el proyecto a GitHub

1. Crear un repositorio nuevo (puede ser **privado**).
2. Subir todo el contenido de esta carpeta (`src/`, `.github/`, `requirements.txt`, etc.).

### 3.2 Guardar las credenciales de forma segura  ⚠ PASO CRÍTICO

En el repositorio de GitHub:

1. Ir a **Settings → Secrets and variables → Actions → New repository secret**.
2. Crear estos secretos (los valores los ingresa **tu equipo**, nunca se escriben en el código):

   | Nombre del secreto | Valor |
   |---|---|
   | `VILAB_USER` | usuario de vilab |
   | `VILAB_PASSWORD` | contraseña de vilab |
   | `VILAB_BASE` | `https://spsc.vilab.cl` |

> Estos valores quedan cifrados. No aparecen en el código, ni en los registros de ejecución, ni son visibles para nadie que mire el repositorio.

### 3.3 Confirmar los endpoints de vilab  ⚠ REQUIERE VERIFICACIÓN

El archivo `src/vilab_extractor.py` contiene varios puntos marcados con `# >>> CONFIRMAR`. Como la estructura interna de vilab solo es visible con una sesión activa, tu equipo debe verificarlos una vez:

1. Iniciar sesión en vilab desde un navegador.
2. Abrir las herramientas de desarrollador (**F12 → pestaña Network / Red**).
3. Navegar a la lista de datos de una estación y observar:
   - La **URL de login** y los nombres de los campos usuario/contraseña.
   - La **URL que devuelve los datos** horarios y sus parámetros (estación, fechas).
   - El **formato de la respuesta** (JSON, CSV o tabla HTML) y los **nombres de las columnas**.
   - Los **identificadores internos** de cada estación.
4. Reflejar esos valores en las líneas `# >>> CONFIRMAR` del extractor.

> Este es el mismo trabajo que se hizo al construir el extractor v7. Si ese extractor aún funciona, se pueden copiar directamente sus valores de login, endpoints y des-acumulación.

### 3.4 Activar la ejecución automática

El workflow `.github/workflows/daily.yml` ya está configurado para correr **cada día a las 10:00 UTC (06:00 en Chile, horario de invierno)**.

- Para **probarlo manualmente** antes de esperar al día siguiente: pestaña **Actions → Pronóstico fitosanitario diario SPS → Run workflow**.
- Si corre bien, generará y publicará `output/index.html`.

### 3.5 Publicar la página (GitHub Pages)

1. En el repositorio: **Settings → Pages**.
2. Fuente: la rama principal, carpeta `/output` (o `/root` según se configure).
3. GitHub entregará una **URL pública fija**, por ejemplo:
   `https://<tu-organizacion>.github.io/<repo>/index.html`

### 3.6 Insertar en Squarespace

1. Editar la página de Squarespace donde debe aparecer el pronóstico.
2. Añadir un bloque **Code** (o **Embed**).
3. Pegar un iframe que apunte a la URL de GitHub Pages:

   ```html
   <iframe
     src="https://<tu-organizacion>.github.io/<repo>/index.html"
     style="width:100%; min-height:900px; border:0;"
     title="Pronóstico fitosanitario SPS Chile">
   </iframe>
   ```

4. Guardar y publicar. La página se verá correctamente en iPhone, Android y escritorio (el diseño es responsivo).

> Cada mañana, cuando el proceso actualice `index.html`, el iframe mostrará automáticamente los datos frescos. No hay que tocar Squarespace de nuevo.

---

## 4. Tu copia local para el histórico largo

Para ingresar más datos históricos (fuera de la ventana de 7 días), usa el mismo motor en tu PC:

```bash
# 1. Extraer un rango largo desde vilab (con tus credenciales en el entorno)
export VILAB_USER="..."
export VILAB_PASSWORD="..."
python3 src/vilab_extractor.py --days 365 --out output/clima_historico.xlsx

# 2. Generar el artefacto con la ventana que quieras (o modificar DISPLAY_DAYS)
python3 src/build_artifact.py
```

La copia local es independiente de la página pública; puedes cargar todos los años que necesites sin afectar la vista diaria de 7 días del sitio.

---

## 5. Mantenimiento

- **Si cambian las credenciales de vilab:** actualizar los secretos en GitHub (paso 3.2). Nada más.
- **Si vilab cambia su estructura:** revisar los puntos `# >>> CONFIRMAR` del extractor.
- **Si quieres cambiar la hora de actualización:** editar la línea `cron` en `daily.yml`.
- **Si quieres cambiar la ventana de visualización:** editar `DISPLAY_DAYS` en `src/run_daily.py`.

---

## 6. Nota sobre el alcance de los modelos

Los modelos son **referenciales, no prescriptivos**. El mojado foliar se estima por proxy de HR≥90 % (no medido), y los parámetros no están recalibrados a Chile. La página lo indica en cada modelo. El paso que daría el mayor salto de valor es un **protocolo de validación de campo** para calibrar los umbrales contra observación real en los predios de SPS a lo largo de la temporada.
