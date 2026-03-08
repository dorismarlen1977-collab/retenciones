import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import xlsxwriter
from datetime import datetime

st.set_page_config(page_title="Retenciones SRI Bitghun", layout="wide")

st.title("Generador de Retenciones SRI 2025")

uploaded_files = st.file_uploader(
    "Subir comprobantes PDF",
    type="pdf",
    accept_multiple_files=True
)

columnas = [
"FECHA","IFIS","N FACTURA","RUC","DOC IFIS","AUTORIZACION",
"NO OBJETO","EXCENTO IVA","BASE 0%","BASE 15%","PROPINA","IVA",
"TOTAL","N° RETENCION","0% R.FTE","RETE 10%","RETE 100%",
"2% R.FTE","TOTAL RETENCION","valor retenido"
]

def buscar(texto, patron):

    m = re.search(patron, texto, re.IGNORECASE)
    return m.group(1) if m else ""

def buscar_num(texto, patron):

    m = re.search(patron, texto, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return 0

def extraer_datos(pdf):

    texto=""

    with pdfplumber.open(pdf) as pdf_file:
        for p in pdf_file.pages:
            texto+=p.extract_text()+" "

    fecha=datetime.today().strftime("%Y-%m-%d")

    ruc=buscar(texto,r"RUC[:\s]*([0-9]{13})")

    factura=buscar(texto,r"No\.?\s*([0-9\-]+)")

    autorizacion=buscar(texto,r"AUTORIZACION[:\s]*([0-9]+)")

    iva=buscar_num(texto,r"IVA\s*\$?\s*([0-9\.]+)")

    total=buscar_num(texto,r"TOTAL\s*\$?\s*([0-9\.]+)")

    propina=buscar_num(texto,r"PROPINA\s*\$?\s*([0-9\.]+)")

    base15=0
    base0=0

    if iva>0:
        base15=round(total/(1.15),2)
    else:
        base0=total

    rete10=0
    rete2=0

    if re.search(r"10\s*%",texto):
        rete10=round(total*0.10,2)

    if re.search(r"2\s*%",texto):
        rete2=round(total*0.02,2)

    valor_retenido=rete10+rete2

    fila={
        "FECHA":fecha,
        "IFIS":"",
        "N FACTURA":factura,
        "RUC":ruc,
        "DOC IFIS":"",
        "AUTORIZACION":autorizacion,
        "NO OBJETO":"",
        "EXCENTO IVA":"",
        "BASE 0%":base0,
        "BASE 15%":base15,
        "PROPINA":propina,
        "IVA":iva,
        "TOTAL":base0+base15+propina+iva,
        "N° RETENCION":"",
        "0% R.FTE":"",
        "RETE 10%":rete10,
        "RETE 100%":"",
        "2% R.FTE":rete2,
        "TOTAL RETENCION":valor_retenido,
        "valor retenido":valor_retenido
    }

    return fila


if uploaded_files:

    datos=[]

    for file in uploaded_files:
        fila=extraer_datos(file)
        datos.append(fila)

    df=pd.DataFrame(datos,columns=columnas)

    st.dataframe(df)

    output=BytesIO()

    with pd.ExcelWriter(output,engine="xlsxwriter") as writer:

        df.to_excel(writer,index=False,startrow=1,sheet_name="RETENCIONES")

        workbook=writer.book
        worksheet=writer.sheets["RETENCIONES"]

        amarillo=workbook.add_format({
            "bold":True,
            "align":"center",
            "border":1,
            "bg_color":"#FFFF00"
        })

        azul=workbook.add_format({
            "bold":True,
            "align":"center",
            "border":1,
            "bg_color":"#00B0F0"
        })

        total_format=workbook.add_format({
            "bold":True,
            "border":1,
            "bg_color":"#FFFF00"
        })

        for col_num,col_name in enumerate(columnas):

            if col_num>=14:
                worksheet.write(0,col_num,col_name,azul)
            else:
                worksheet.write(0,col_num,col_name,amarillo)

        filas=len(df)+2

        worksheet.write(filas,0,"TOTAL",total_format)

        for i in range(8,20):

            letra=chr(65+i)
            formula=f"=SUM({letra}2:{letra}{filas})"
            worksheet.write_formula(filas,i,formula,total_format)

        worksheet.set_column(0,20,18)

    output.seek(0)

    st.download_button(
        "Descargar Excel",
        data=output,
        file_name="retenciones_bitghun_2025.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
