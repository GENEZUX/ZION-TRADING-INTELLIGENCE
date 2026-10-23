import time
import subprocess
import sys
import os
from datetime import datetime

print("==========================================")
print(" 🐉 ZION BEAST - LANZADOR AUTOMATIZADO")
print("==========================================")
print("Presiona Ctrl+C para detener el bucle de forma segura.")
print("")

# Usamos 'py -3.12' porque es el comando que funciona en tu Windows
PYTHON_CMD = "py"
PYTHON_ARG = "-3.12"

# Forzamos a que la carpeta actual esté en el PYTHONPATH
env = os.environ.copy()
env["PYTHONPATH"] = os.getcwd()

while True:
    try:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{ahora}] === Iniciando ciclo de alimentación ===")
        
        # 1. Ingesta de Kraken (usamos el script que ya tienes)
        print(" -> [1/2] Ingestando datos de Kraken...")
        subprocess.run([PYTHON_CMD, PYTHON_ARG, "src/ingest/kraken_public.py"], check=False, env=env)
        
        # 2. Análisis de Voltex (si existe)
        print(" -> [2/2] Ejecutando análisis Voltex...")
        subprocess.run([PYTHON_CMD, PYTHON_ARG, "src/analyze/voltex.py"], check=False, env=env)
        
        print(f"[{ahora}] === Ciclo completado. Esperando 60 segundos... ===")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Detención manual detectada. Cerrando el bucle de forma segura.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error en el bucle: {e}")
        print("Esperando 10 segundos antes de reintentar...")
        time.sleep(10)
