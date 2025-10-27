from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
import io
from fastapi.middleware.cors import CORSMiddleware
    

app = FastAPI(title="Procesador de Excel - Envios")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://excel-frontend.web.app",
        "https://deploy-fastapi-backend.onrender.com",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.post('/procesar')
async def procesar_excel(file: UploadFile = File(...)):
    # Validar tipo de archivo
    if not file.filename.lower().endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail='El archivo debe ser Excel (.xls/.xlsx)')
    
    # Leer el contenido del archivo
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name='result')
    except Exception:
        df = pd.read_excel(io.BytesIO(contents))

    # Normalizar nombres de columnas
    df.columns = [c.strip() for c in df.columns]

    # Asegurar columnas necesarias
    for col in ['DriverName', 'Route', 'RecipientName', 'customerAccountCode', 'TrackingNo', 'FinalStatus']:
        if col not in df.columns:
            df[col] = pd.NA

    # Normalizar FinalStatus (sin espacios, en minúsculas)
    df['FinalStatus'] = df['FinalStatus'].astype(str).str.strip().str.lower()

    # Filtrar solo entregas con FinalStatus = delivered
    df_entregados = df[df['FinalStatus'] == 'delivered']

    # 1️⃣ PQ_Totales = número de rutas únicas (Route) donde hubo entregas delivered
    pq_totales = (
        df_entregados.groupby('DriverName')['Route']
        .nunique()
        .rename('PQ_Totales')
    )

    # 2️⃣ Paradas = cantidad de RecipientName únicos por Driver (de todo el archivo)
    paradas = (
        df.groupby('DriverName')['RecipientName']
        .nunique()
        .rename('Paradas')
    )

    # 3️⃣ Entregas TEMU = cantidad de TrackingNo donde el cliente es TEMU (sin importar status)
    entregas_temu = (
        df[df['customerAccountCode'].astype(str).str.upper().str.strip() == 'TEMU']
        .groupby('DriverName')['TrackingNo']
        .count()
        .rename('Entregas_TEMU')
    )

    # 4️⃣ Combinar resultados
    resumen = pd.concat([pq_totales, paradas, entregas_temu], axis=1).fillna(0).reset_index()

    # Asegurar que Entregas_TEMU sea int
    resumen['Entregas_TEMU'] = resumen['Entregas_TEMU'].astype(int)
    resumen['PQ_Totales'] = resumen['PQ_Totales'].astype(int)
    resumen['Paradas'] = resumen['Paradas'].astype(int)

    # 5️⃣ Fila TOTAL GENERAL
    totales = pd.DataFrame({
        'DriverName': ['TOTAL GENERAL'],
        'PQ_Totales': [resumen['PQ_Totales'].sum()],
        'Paradas': [resumen['Paradas'].sum()],
        'Entregas_TEMU': [resumen['Entregas_TEMU'].sum()]
    })

    resumen_final = pd.concat([resumen, totales], ignore_index=True)

    # 6️⃣ Generar Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Original', index=False)
        resumen_final.to_excel(writer, sheet_name='Resumen_por_Driver', index=False)
    output.seek(0)

    # 7️⃣ Retornar archivo como descarga
    filename = f"resumen_{file.filename.split('.')[0]}.xlsx"
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers=headers
    )


@app.get('/ping')
async def ping():
    return JSONResponse({'status': 'ok'})
