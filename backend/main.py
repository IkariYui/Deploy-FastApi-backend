from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

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


@app.post("/procesar")
async def procesar_excel(file: UploadFile = File(...)):

    # 🔒 Validar archivo
    if not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel")

    contents = await file.read()

    # 📥 Leer Excel
    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name="result")
    except Exception:
        df = pd.read_excel(io.BytesIO(contents))

    # 🧹 Normalizar columnas
    df.columns = [c.strip() for c in df.columns]

    columnas_necesarias = [
        "DriverName",
        "Route",
        "RecipientName",
        "customerAccountCode",
        "TrackingNo",
        "FinalStatus",
        "Weight",  # 👈 peso del paquete
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            df[col] = pd.NA

    # 🧼 Normalizaciones
    df["FinalStatus"] = (
        df["FinalStatus"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["customerAccountCode"] = (
        df["customerAccountCode"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")

    # ✅ SOLO ENTREGADOS
    df_entregados = df[df["FinalStatus"] == "delivered"]

    # 1️⃣ PAQUETES TOTALES
    pq_totales = (
        df_entregados
        .groupby(["DriverName", "Route"])["TrackingNo"]
        .count()
        .rename("PQ_Totales")
    )

    # 2️⃣ PARADAS (destinatarios únicos)
    paradas = (
        df_entregados
        .groupby(["DriverName", "Route"])["RecipientName"]
        .nunique()
        .rename("Paradas")
    )

    # 3️⃣ ENTREGAS TEMU
    entregas_temu = (
        df_entregados[
            df_entregados["customerAccountCode"].str.startswith("TEMU")
        ]
        .groupby(["DriverName", "Route"])["TrackingNo"]
        .count()
        .rename("Entregas_TEMU")
    )

    # 4️⃣ 🔥 PARADAS < 1 LIBRA, NO TEMU
    df_light_non_temu = df_entregados[
        (~df_entregados["customerAccountCode"].str.startswith("TEMU")) &
        (df_entregados["Weight"] < 1)
    ]

    paradas_light_non_temu = (
        df_light_non_temu
        .groupby(["DriverName", "Route"])["RecipientName"]
        .nunique()
        .rename("Paradas_<1lb_sin_TEMU")
    )

    # 5️⃣ UNIR TODO
    resumen = (
        pd.concat(
            [
                pq_totales,
                paradas,
                entregas_temu,
                paradas_light_non_temu,
            ],
            axis=1,
        )
        .fillna(0)
        .reset_index()
    )

    # Tipos
    for col in [
        "PQ_Totales",
        "Paradas",
        "Entregas_TEMU",
        "Paradas_<1lb_sin_TEMU",
    ]:
        resumen[col] = resumen[col].astype(int)

    # 6️⃣ TOTAL GENERAL
    totales = pd.DataFrame({
        "DriverName": ["TOTAL GENERAL"],
        "Route": ["—"],
        "PQ_Totales": [resumen["PQ_Totales"].sum()],
        "Paradas": [resumen["Paradas"].sum()],
        "Entregas_TEMU": [resumen["Entregas_TEMU"].sum()],
        "Paradas_<1lb_sin_TEMU": [resumen["Paradas_<1lb_sin_TEMU"].sum()],
    })

    resumen_final = pd.concat([resumen, totales], ignore_index=True)

    # 7️⃣ GENERAR EXCEL
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Original", index=False)
        resumen_final.to_excel(
            writer,
            sheet_name="Resumen_por_Driver_y_Ruta",
            index=False,
        )

    output.seek(0)

    filename = f"resumen_{file.filename.split('.')[0]}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})