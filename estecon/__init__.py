URL = {'congresistas' : 'https://www.congreso.gob.pe/pleno/congresistas/',
       'proyectos_ley': 'https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search',
       'dictamenes' : 'https://wb2server.congreso.gob.pe/spley-portal/#/dictamenes/periodos',
       'leyes' : 'https://www.leyes.congreso.gob.pe/',
       'asistencia_pleno' : "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-votacion-pleno",
       'asistencia_comision_permanente' : "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-comisionpermanente",
       'actas_comisiones' : "https://www.congreso.gob.pe/actascomisiones/",
       'conformacion_comisiones': "https://www.congreso.gob.pe/CuadrodeComisiones/"}

# Might need to review and make sure everyone is here
PARTIES = [" AP ", " AP-PIS ", " APP ", " BM ", " BDP ", " BOP ", " BS ", " BSS ",
            " E "," FP ", " HYD ", " JP ", " IJPP-VP "," JPP-VP ", " NA ", " NP ", 
            " PL ", " PLG ", " PM ", " PP ", " SP ", " sP ", " RP ", " 8S ", " 8M "] 

VOTE_RESULTS = ["SI", "NO", "Abst.", "SinRes", "aus", "LO",
                "LE", "LP", "Com", "CEI", "JP", "Ban", "Sus", "F"]

ATTENDANCE_RESULTS = [" pre ", " le ", " aus ", " lp "]

TYPE_STEPS = ['Vote', 'Assigned to Committee', 'Presented', 'Published']