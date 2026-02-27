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

    if not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel")

    contents = await file.read()

    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name="result")
    except Exception:
        df = pd.read_excel(io.BytesIO(contents))

    # Normalizar columnas
    df.columns = [c.strip() for c in df.columns]

    columnas = [
        "DriverName",
        "Route",
        "RecipientName",   # Dirección
        "customerAccountCode",
        "TrackingNo",
        "FinalStatus",
        "Weight",
    ]

    for col in columnas:
        if col not in df.columns:
            df[col] = pd.NA

    # Normalizaciones
    df["FinalStatus"] = (
        df["FinalStatus"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    df["customerAccountCode"] = (
        df["customerAccountCode"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")

    # Solo entregados
    df_entregados = df[df["FinalStatus"] == "delivered"].copy()

    # -----------------------------
    # PRIORIDAD PARA DEDUPLICAR
    # -----------------------------
    def prioridad(row):
        if not row["customerAccountCode"].startswith("TEMU") and row["Weight"] < 1:
            return 0
        if not row["customerAccountCode"].startswith("TEMU"):
            return 1
        return 2

    df_entregados["prioridad"] = df_entregados.apply(prioridad, axis=1)

    # Deduplicar por PARADA (dirección)
    df_paradas = (
        df_entregados
        .sort_values("prioridad")
        .drop_duplicates(
            subset=["DriverName", "Route", "RecipientName"],
            keep="first"
        )
    )

    # -----------------------------
    # MÉTRICAS
    # -----------------------------

    # Paquetes totales
    pq_totales = (
        df_entregados
        .groupby(["DriverName", "Route"])["TrackingNo"]
        .count()
        .rename("PQ_Totales")
    )

    # Paradas (direcciones únicas, SIEMPRE)
    paradas = (
        df_paradas
        .groupby(["DriverName", "Route"])["RecipientName"]
        .count()
        .rename("Paradas")
    )

    # Entregas TEMU (por paquete)
    entregas_temu = (
        df_entregados[
            df_entregados["customerAccountCode"].str.startswith("TEMU")
        ]
        .groupby(["DriverName", "Route"])["TrackingNo"]
        .count()
        .rename("Entregas_TEMU")
    )

    # Paradas < 1 lb y NO TEMU (solo si el mejor paquete cumple)
    paradas_light = (
        df_paradas[
            (~df_paradas["customerAccountCode"].str.startswith("TEMU")) &
            (df_paradas["Weight"] < 1)
        ]
        .groupby(["DriverName", "Route"])["RecipientName"]
        .count()
        .rename("Paradas_<1lb_sin_TEMU")
    )

    # -----------------------------
    # UNIÓN FINAL
    # -----------------------------
    resumen = (
        pd.concat(
            [pq_totales, paradas, entregas_temu, paradas_light],
            axis=1
        )
        .fillna(0)
        .reset_index()
    )

    for col in [
        "PQ_Totales",
        "Paradas",
        "Entregas_TEMU",
        "Paradas_<1lb_sin_TEMU",
    ]:
        resumen[col] = resumen[col].astype(int)

    # TOTAL GENERAL
    totales = pd.DataFrame({
        "DriverName": ["TOTAL GENERAL"],
        "Route": ["—"],
        "PQ_Totales": [resumen["PQ_Totales"].sum()],
        "Paradas": [resumen["Paradas"].sum()],
        "Entregas_TEMU": [resumen["Entregas_TEMU"].sum()],
        "Paradas_<1lb_sin_TEMU": [resumen["Paradas_<1lb_sin_TEMU"].sum()],
    })

    resumen_final = pd.concat([resumen, totales], ignore_index=True)

    # Excel
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

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})