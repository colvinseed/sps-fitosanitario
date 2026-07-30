# -*- coding: utf-8 -*-
"""
validar_estaciones.py · Prueba las estaciones de interés contra Agromet directo
================================================================================
Versión 1.0 · 2026-07-14 · © 2026 Winston Colvin — South Pacific Seeds Chile

Corre una consulta corta (3 días) a cada estación y reporta cuáles devuelven
datos y cuáles fallan. Úsalo para confirmar ids/prefijos ANTES de ponerlas en
producción. Ejecutar en un entorno con salida a internet (tu PC):

    python validar_estaciones.py

No modifica nada; solo consulta y reporta.
"""
import sys, time
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from agromet_extractor import fetch_station

# Estaciones de interés de Winston (nombre -> id completo con prefijo).
# Prefijo INIA- para institución INIA; EXT- para el resto (DMC, ARAUCO, CEAZA,
# COLUN, VDCH, AGRICHILE, FDF, MMA-DMC). Regla verificada en 3 casos.
ESTACIONES = {
    'Aeródromo María Dolores (Los Ángeles)':      'EXT-229',
    'Liceo Agrícola El Huertón (Los Ángeles)':    'EXT-162',
    'Illapel (Illapel)':                          'EXT-5',
    'Aeródromo La Florida (La Serena)':           'EXT-100',
    'Escuela Agrícola (Ovalle)':                  'EXT-101',
    'El Vergel (Angol)':                          'INIA-237',
    'San Sebastián (Perquenco)':                  'INIA-235',
    'Adolfo Matthei (Osorno)':                    'EXT-76',
    'Ignao (Río Bueno)':                          'EXT-1023',
    'Cauquenes (Cauquenes)':                      'INIA-46',
    'Sauzal (Cauquenes)':                         'INIA-11',
    'Chanco (Chanco)':                            'INIA-22',
    'Hualañé (Hualañé)':                          'EXT-983',
    'Escuela de Artillería (Linares)':            'EXT-974',
    'Santa Amada (Linares)':                      'INIA-136',
    'Parral (Parral)':                            'EXT-960',
    'El Auquil (Pelarco)':                        'EXT-992',
    'Pencahue (Pencahue)':                        'EXT-333',
    'Villa Seca (Retiro)':                        'EXT-327',
    'San Clemente (San Clemente)':                'INIA-135',
    'Panguilemo (Talca)':                         'EXT-156',
    'Talca (Talca)':                              'EXT-982',
    'Teno (Teno)':                                'EXT-1031',
    'Villa Alegre (Villa Alegre)':                'EXT-977',
    'El Asiento (Alhué)':                         'INIA-210',
    'Los Tilos (Buin)':                           'INIA-6',
    'Valdivia de Paine (Buin)':                   'INIA-321',
    'Aeródromo Curacaví (Curacaví)':              'EXT-150',
    'San Antonio de Naltahua (Isla de Maipo)':    'INIA-100',
    'Chorrillos (Lampa)':                         'INIA-314',
    'Chorombo Hacienda (María Pinto)':            'EXT-141',
    'Talagante (Talagante)':                      'EXT-118',
    "Aeródromo Gral. B. O'Higgins (Chillán)":     'EXT-157',
    'Quilamapu (Chillán)':                        'INIA-351',
    'Navidad (El Carmen)':                        'INIA-73',
    'Centro Experimental Arroz (San Carlos)':     'INIA-139',
    'Yungay (Yungay)':                            'INIA-49',
    'Peor es Nada (Chimbarongo)':                 'INIA-317',
    'Calleuque (Peralillo)':                      'INIA-334',
    'Liceo Jean Buchanan (Peumo)':                'INIA-228',
    'Nilahue - La Quebrada (Pumanque)':           'EXT-155',
    'El Arenal (Quinta de Tilcoco)':              'INIA-163',
    'Rayentué (Rengo)':                           'INIA-303',
    'Los Lingues (San Fernando)':                 'INIA-329',
    'El Tambo (San Vicente)':                     'INIA-52',
    'La Cruz (La Cruz)':                          'INIA-51',
    'Liceo Agrícola Quillota (Quillota)':         'EXT-1029',
}


def main():
    end = datetime.now()
    start = end - timedelta(days=3)
    desde, hasta = start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y')
    ok, fail = [], []
    print(f"Validando {len(ESTACIONES)} estaciones (consulta de 3 días)...\n")
    for nombre, sid in ESTACIONES.items():
        try:
            df = fetch_station(sid, desde, hasta)
            n = len(df) if df is not None else 0
            # ¿tiene datos reales de T o HR?
            tiene_datos = df is not None and n > 0 and (
                df['T'].notna().any() or df['HR'].notna().any())
            if tiene_datos:
                print(f"  OK    {sid:10} {nombre}  ({n} filas)")
                ok.append((nombre, sid))
            else:
                print(f"  VACÍO {sid:10} {nombre}  (respondió pero sin datos)")
                fail.append((nombre, sid, 'sin datos'))
        except Exception as e:
            print(f"  FALLA {sid:10} {nombre}  -> {str(e)[:50]}")
            fail.append((nombre, sid, str(e)[:50]))
        time.sleep(1)   # cortesía con el servidor

    print(f"\n{'='*60}")
    print(f"RESUMEN: {len(ok)} OK, {len(fail)} con problemas")
    if fail:
        print("\nRevisar estas (id/prefijo posiblemente incorrecto):")
        for n, s, motivo in fail:
            print(f"  {s:10} {n}  ({motivo})")
    print("\nCopia la lista de las OK para ponerlas en producción.")


if __name__ == '__main__':
    main()
