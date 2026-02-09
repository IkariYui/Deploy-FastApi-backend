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

    # ✅ Validar tipo de archivo
    if not file.filename.lower().endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail='El archivo debe ser Excel (.xls/.xlsx)')

    contents = await file.read()

    # ✅ Intentar leer hoja "result"
    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name='result')
    except Exception:
        df = pd.read_excel(io.BytesIO(contents))

    # ✅ Normalizar nombres de columnas
    df.columns = [c.strip() for c in df.columns]

    # ✅ Asegurar columnas necesarias
    columnas_necesarias = [
        'DriverName',
        'Route',
        'RecipientName',
        'customerAccountCode',
        'TrackingNo',
        'FinalStatus'
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            df[col] = pd.NA

    # ✅ Normalizar FinalStatus
    df['FinalStatus'] = (
        df['FinalStatus']
        .fillna('')
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # ✅ Normalizar customerAccountCode (IMPORTANTE)
    df['customerAccountCode'] = (
        df['customerAccountCode']
        .fillna('')
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # 1️⃣ Filtrar entregas completadas
    df_entregados = df[df['FinalStatus'] == 'delivered']

    # 2️⃣ PQ_Totales
    pq_totales = (
        df_entregados.groupby(['DriverName', 'Route'])['TrackingNo']
        .count()
        .rename('PQ_Totales')
    )

    # 3️⃣ Paradas
    paradas = (
        df_entregados.groupby(['DriverName', 'Route'])['RecipientName']
        .nunique()
        .rename('Paradas')
    )

    # 4️⃣ Entregas TEMU (todas las sucursales TEMU)
    entregas_temu = (
        df_entregados[
            df_entregados['customerAccountCode'].str.startswith('TEMU')
        ]
        .groupby(['DriverName', 'Route'])['TrackingNo']
        .count()
        .rename('Entregas_TEMU')
    )

    # 5️⃣ Combinar resultados
    resumen = (
        pd.concat([pq_totales, paradas, entregas_temu], axis=1)
        .fillna(0)
        .reset_index()
    )

    resumen['PQ_Totales'] = resumen['PQ_Totales'].astype(int)
    resumen['Paradas'] = resumen['Paradas'].astype(int)
    resumen['Entregas_TEMU'] = resumen['Entregas_TEMU'].astype(int)

    # 6️⃣ TOTAL GENERAL
    totales = pd.DataFrame({
        'DriverName': ['TOTAL GENERAL'],
        'Route': ['—'],
        'PQ_Totales': [resumen['PQ_Totales'].sum()],
        'Paradas': [resumen['Paradas'].sum()],
        'Entregas_TEMU': [resumen['Entregas_TEMU'].sum()]
    })

    resumen_final = pd.concat([resumen, totales], ignore_index=True)

    # 7️⃣ Generar Excel en memoria
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Original', index=False)
        resumen_final.to_excel(writer, sheet_name='Resumen_por_Driver_y_Ruta', index=False)

    output.seek(0)

    # 8️⃣ Descargar archivo
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
