"""M6: resumen de anotaciones UA-DETRAC."""

from roadguard.m6_evaluacion.ua_detrac import resumir_secuencia

XML = """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_99999">
   <sequence_attribute camera_state="unstable" sence_weather="night"/>
   <ignored_region>
      <box left="0" top="0" width="10" height="10"/>
   </ignored_region>
   <frame density="2" num="1">
      <target_list>
         <target id="1"><box left="1" top="1" width="5" height="5"/>
            <attribute vehicle_type="car"/></target>
         <target id="2"><box left="9" top="9" width="5" height="5"/>
            <attribute vehicle_type="bus"/></target>
      </target_list>
   </frame>
   <frame density="1" num="2">
      <target_list>
         <target id="1"><box left="2" top="2" width="5" height="5"/>
            <attribute vehicle_type="car"/></target>
      </target_list>
   </frame>
</sequence>
"""


def test_resume_cuadros_vehiculos_y_clases(tmp_path):
    ruta = tmp_path / "MVI_99999.xml"
    ruta.write_text(XML)
    r = resumir_secuencia(ruta)
    assert (r.nombre, r.clima, r.estado_camara) == ("MVI_99999", "night", "unstable")
    assert (r.n_cuadros, r.n_vehiculos) == (2, 2)
    assert r.cajas_por_clase == {"car": 2, "bus": 1}
    assert r.densidad_media == 1.5
    assert r.n_regiones_ignoradas == 1


def test_sin_cuadros_la_densidad_no_esta_disponible(tmp_path):
    ruta = tmp_path / "vacia.xml"
    ruta.write_text('<sequence name="X"></sequence>')
    r = resumir_secuencia(ruta)
    assert r.n_cuadros == 0 and r.densidad_media is None and r.clima is None
