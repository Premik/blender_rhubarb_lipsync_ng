print("-"*100)

import importlib  
m = importlib.import_module("rhubarb_lipsync")
m.unregister()
importlib.reload(m)
m.register()

print('rhubarb_lipsync' in locals())
print("*"*100)