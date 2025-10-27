from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
import io
from fastapi.middleware.cors import CORSMiddleware
    

app = FastAPI(title="Procesador de Excel - Envios")
origins = [
    "https://excel-frontend.web.app",  # dominio de tu frontend en Firebase
    "https://deploy-fastapi-backend.onrender.com",  # dominio del backend (por seguridad)
    "http://localhost:5173",  # opcional: útil si pruebas localmente
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],  # permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # permite todos los encabezados
)

@app.post('/procesar')
async def procesar_excel(file: UploadFile = File(...)):
# Validación básica
    if not file.filename.lower().endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail='El archivo debe ser Excel (.xls/.xlsx)')
    
    # Leer el contenido en memoria
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name='result')
    except Exception:
    # Intentar leer la primera hoja si no existe "result"
        df = pd.read_excel(io.BytesIO(contents))

    # Normalizar nombres de columnas (por si vienen con espacios o case distintos)
    df.columns = [c.strip() for c in df.columns]

    # Asegurarse que las columnas existan
    for col in ['DriverName', 'Route', 'RecipientName', 'customerAccountCode', 'TrackingNo']:
        if col not in df.columns:
        # No abortamos; solo ponemos NaN si falta
            df[col] = pd.NA

    # 1) PQ totales: rutas únicas por driver
    pq_totales = df.groupby('DriverName')['Route'].nunique().rename('PQ_Totales')        

    # 2) Paradas: RecipientName únicos por driver
    paradas = df.groupby('DriverName')['RecipientName'].nunique().rename('Paradas')

    # 3) Entregas TEMU
    entregas_temu = (
    df[df['customerAccountCode'].astype(str).str.upper() == 'TEMU']
    .groupby('DriverName')['TrackingNo']
    .count()
    .rename('Entregas_TEMU')
    )

    # 4) Concatenar
    resumen = pd.concat([pq_totales, paradas, entregas_temu], axis=1).fillna(0).reset_index()
    resumen['Entregas_TEMU'] = resumen['Entregas_TEMU'].astype(int) 

    # 5) Fila total
    totales = pd.DataFrame({
    'DriverName': ['TOTAL GENERAL'],
    'PQ_Totales': [resumen['PQ_Totales'].sum()],
    'Paradas': [resumen['Paradas'].sum()],
    'Entregas_TEMU': [resumen['Entregas_TEMU'].sum()]
    })

    resumen_final = pd.concat([resumen, totales], ignore_index=True)

    # 6) Generar Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Original', index=False)
        resumen_final.to_excel(writer, sheet_name='Resumen_por_Driver', index=False)
    output.seek(0)

    # 7) Devolver el archivo como descarga
    filename = f"resumen_{file.filename.split('.')[0]}.xlsx"
    headers = {
    'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

@app.get('/ping')
async def ping():
    return JSONResponse({'status': 'ok'})