import cv2
import serial
import asyncio
import websockets
import json

# Configuración del puerto de tu Arduino
try:
    arduino = serial.Serial('COM5', 9600, timeout=0.1) 
except:
    print("Arduino no detectado. Modo simulación activado.")
    arduino = None

# Configuración del detector ArUco
diccionario_aruco = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parametros_aruco = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(diccionario_aruco, parametros_aruco)

# Mapeo: ID del ArUco -> Índice del álbum en tu JSON
MAPEO_DISCOS = {
    10: 0,   # [1956] Violeta Parra - Chants et Danses (Pionera)
    12: 8,   # [1964] Cecilia - Cecilia (Nicho / Rate Alto: 4.07)
    13: 10,  # [1966] Violeta Parra - Las últimas composiciones (Histórico / 961 ratings)
    14: 15,  # [1971] Víctor Jara - El derecho de vivir en paz (Popular / 1181 ratings)
    15: 29,  # [1975] aparato raro
    16: 25,  # [1981] Los Jaivas - Alturas de Machu Pichu (La cumbre del Rock / 1301 ratings)
    11: 30,  # [1986] Los Prisioneros - Pateando piedras (Popular / 593 ratings)
    19: 41,  # [1997] Los Tres - Fome (Consolidación de los 90 / 367 ratings)
    21: 49,  # [2005] La Mano Ajena - La mano ajena (Nicho / Rate Alto: 3.94)
    23: 52,  # [2008] Teleradio Donoso - Bailar y llorar (Indie de culto)
    24: 62,  # [2018] Niños del Cerro - Lance (Representante moderno / 528 ratings)
}

async def detector_sistema(websocket):
    # Usa '0' para la webcam, o pon la URL de tu app de celular IP Webcam
    cap = cv2.VideoCapture("http://10.124.123.223:8080/video")
    
    disco_activo = False
    ultimo_indice_enviado = None
    frames_sin_disco = 0
    ultimo_id_detectado = None

    # Si no detecta el disco durante aproximadamente 2 segundos, asumimos que se retiró
    UMBRAL_RETIRO = 120

    print("Lector ArUco inteligente iniciado. Esperando disco...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        esquinas, ids, _ = detector.detectMarkers(frame)
        
        # 1. CASO: No hay disco sonando y detectamos un ArUco válido (Lectura Inicial)
        if not disco_activo and ids is not None:
            id_actual = int(ids[0][0])

            if id_actual in MAPEO_DISCOS and id_actual != ultimo_id_detectado:

                disco_activo = True
                frames_sin_disco = 0
                ultimo_id_detectado = id_actual
                ultimo_indice_enviado = MAPEO_DISCOS[id_actual]

                print(f"Disco detectado ID {id_actual}")

                # Mandar a web
                await websocket.send(
                    json.dumps({
                        "accion":"play",
                        "indice":ultimo_indice_enviado
                    })
                )

                # Mandar a Arduino
                if arduino:
                    arduino.write(b'START\n')

                cv2.aruco.drawDetectedMarkers(frame, esquinas, ids)

        # 2. CASO: El disco ya está girando
        elif disco_activo:

            if ids is not None:
                # El disco sigue presente
                frames_sin_disco = 0

            else:
                frames_sin_disco += 1

            # 3. CASO: Se retiró el disco físicamente (Pasó el umbral de frames vacíos)
            if frames_sin_disco >= UMBRAL_RETIRO:

                print("Disco retirado del tocadiscos. Deteniendo sistema.")

                disco_activo = False
                ultimo_indice_enviado = None
                ultimo_id_detectado = None
                frames_sin_disco = 0

                # Avisar a la Web que detenga la música y limpie el gráfico
                await websocket.send(
                    json.dumps({
                        "accion":"stop"
                    })
                )

                # Apagar el motor Lego en el Arduino
                if arduino:
                    arduino.write(b'STOP\n')

        # Mostrar la cámara en pantalla para calibrar el prototipo
        cv2.putText(frame, f"Estado: {'GIRANDO' if disco_activo else 'ESPERANDO DISCO'}", 
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if disco_activo else (0, 0, 255), 2)
        
        cv2.imshow("Lector de Vinilos de Carton", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        await asyncio.sleep(0.02)

    cap.release()
    cv2.destroyAllWindows()

async def main():
    async with websockets.serve(detector_sistema, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())