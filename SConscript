from building import *

cwd = GetCurrentDir()
src = Glob('SGP40/*.c')
src += Glob('MAX9814/*.c')
src += Glob('audio_analysis/*.c')
src += Glob('camera/*.c')
src += Glob('LED/*.c')
src += Glob('Pump/*.c')
src += Glob('HX711/*.c')
src += Glob('my_Alarm/*.c')
CPPPATH = [cwd, cwd + '/SGP40', cwd + '/MAX9814', cwd + '/audio_analysis', cwd + '/camera', cwd + '/LED', cwd + '/Pump', cwd + '/HX711', cwd + '/my_Alarm']

group = DefineGroup('BeeApp', src, depend=[''], CPPPATH=CPPPATH)
Return('group')
