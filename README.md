# Pronóstico fitosanitario diario — SPS Chile

Sistema automático que cada mañana extrae datos de las estaciones desde vilab,
calcula seis enfermedades foliares/florales y publica una página bilingüe
(ES/EN) responsiva para embeber en Squarespace.

**Enfermedades:** mildiú velloso (esporulación), Alternaria porri/dauci/brassicae
(infección), Botrytis squamosa/cinerea (infección), Sclerotinia (índice).

## Estructura
- `src/disease_models.py` — motor de cálculo de las 6 enfermedades
- `src/vilab_extractor.py` — extractor de datos de vilab (credenciales por entorno)
- `src/build_artifact.py` — generador del HTML bilingüe (7 días móviles)
- `src/run_daily.py` — orquestador del pipeline diario
- `.github/workflows/daily.yml` — ejecución automática diaria
- `docs/GUIA_DESPLIEGUE.md` — **empezar aquí**

## Uso rápido (local)
```bash
pip install -r requirements.txt
export VILAB_USER="..." VILAB_PASSWORD="..."
python3 src/run_daily.py
```

Ver `docs/GUIA_DESPLIEGUE.md` para el despliegue completo.

© 2026 Winston Colvin — South Pacific Seeds Chile · v1.0
