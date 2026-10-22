import time
import subprocess
import sys
from datetime import datetime

# --- CONFIGURACIÓN DEL MODO DIOS ---
INTERVALO_SEGUNDOS = 60  # Cada cuánto tiempo trae datos nuevos (60 seg = 1 min)
PYTHON = "py"
ARG = "-3.12"

def log(msg):
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"[{ahora}] {msg}")

def ejecutar_script(nombre, ruta):
    log(f"Ejecutando {nombre}...")
    try:
        # check=False para que si falla (ej. Kraken caído), no rompa el bucle
        resultado = subprocess.run([PYTHON, ARG, ruta], capture_output=True, text=True, check=False)
        if resultado.returncode == 0:
            log(f"✅ {nombre} completado con éxito.")
        else:
            log(f"⚠️ {nombre} terminó con advertencias (ver logs).")
            # Imprimimos el error para debug
            if resultado.stderr:
                print(resultado.stderr)
    except Exception as e:
        log(f"❌ Error crítico en {nombre}: {e}")

if __name__ == "__main__":
    print("==================================================")
    print(" 🦖 ZION BEAST - MODO AUTÓNOMO (GODZILLA)")
    print("==================================================")
    print(f"Intervalo de actualización: {INTERVALO_SEGUNDOS} segundos.")
    print("Presiona Ctrl+C para detener el bucle de forma segura.")
    print("==================================================\n")

    try:
        while True:
            log("--- INICIANDO CICLO DE INGESTA GLOBAL ---")
            
            # 1. Ingesta Global (Kraken, Yahoo, HKMA)
            ejecutar_script("Godzilla Global", "godzilla_feed.py")
            
            # 2. Ingesta de Hugging Face (Opcional, es muy pesado para cada minuto)
            # ejecutar_script("Hugging Face", "hugging_face_feed.py")

            log(f"--- CICLO COMPLETADO. Esperando {INTERVALO_SEGUNDOS}s ---\n")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\n\n🛑 Detención manual detectada. El bucle se ha detenido de forma segura.")
        sys.exit(0)
