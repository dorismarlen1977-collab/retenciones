import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import xlsxwriter
from datetime import datetime

st.set_page_config(page_title="Retenciones SRI", layout="wide")

st.title("Generador de Retenciones SRI")

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

def extraer_texto(pdf):

    texto=""

    with pdfplumber.open(pdf) as pdf_file:
        for page in pdf_file.pages:
            t=page.extract_text()
            if t:
                texto+=t+"\n"

    return texto


def extraer_ruc(texto):

    ruc=re.search(r'RUC[:\s]*([0-9]{13})',texto)

    if ruc:
        return ruc.group(1)

    alt=re.search(r'\b[0-9]{13}\b',texto)

    if alt:
        return alt.group(0)

    return ""


def buscar(texto,patron):

    m=re.search(patron,texto,re.IGNORECASE)

    if m:
        return m.group(1)

    return ""


def buscar_num(texto,patron):

    m=re.search(patron,texto,re.IGNORECASE)

    if m:
        return float(m.group(1).replace(",",""))

    return 0


def extraer_empresa(texto):

    lineas=texto.split("\n")

    for l in lineas[:10]:

        if "S.A" in l.upper() or "CIA" in l.upper() or "LTDA" in l.upper():
            return l.strip()

    return ""


def obtener_base(texto):

    base0=0
    base15=0

    patron=r"Base Imponible para la Retenci[oó]n\s*([0-9\.,]+).*?(IVA|RENTA)"

    matches=re.findall(patron,texto,re.IGNORECASE)

    for valor,impuesto in matches:

        valor=float(valor.replace(",",""))

        if "RENTA" in impuesto.upper():
            base0+=valor

        if "IVA" in impuesto.upper():
            base15+=valor

    return base0,base15


def calcular_retenciones(texto,total):

    rete10=0
    rete2=0

    if re.search(r"10\s*%",texto):
        rete10=round(total*0.10,2)

    if re.search(r"2\s*%",texto):
        rete2=round(total*0.02,2)

    return rete10,rete2


def procesar_pdf(pdf):

    texto=extraer_texto(pdf)

    fecha=buscar(texto,r"Fecha[:\s]*([0-9/\-]+)")

    if fecha=="":
        fecha=datetime.today().strftime("%Y-%m-%d")

    empresa=extraer_empresa(texto)

    factura=buscar(texto,r"No\.?\s*([0-9\-]+)")

    ruc=extraer_ruc(texto)

    autorizacion=buscar(texto,r"Autorizaci[oó]n[:\s]*([0-9]{10,})")

    iva=buscar_num(texto,r"IVA\s*\$?\s*([0-9\.,]+)")

    propina=buscar_num(texto,r"PROPINA\s*\$?\s*([0-9\.,]+)")

    base0,base15=obtener_base(texto)

    if iva>0 and base15==0:
        base15=buscar_num(texto,r"SUBTOTAL\s*\$?\s*([0-9\.,]+)")

    total=base0+base15+propina+iva

    rete10,rete2=calcular_retenciones(texto,total)

    total_retencion=rete10+rete2

    fila={
        "FECHA":fecha,
        "IFIS":empresa,
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
        "TOTAL":total,
        "N° RETENCION":"",
        "0% R.FTE":"",
        "RETE 10%":rete10,
        "RETE 100%":"",
        "2% R.FTE":rete2,
        "TOTAL RETENCION":total_retencion,
        "valor retenido":total_retencion
    }

    return fila


if uploaded_files:

    datos=[]

    for file in uploaded_files:
        datos.append(procesar_pdf(file))

    df=pd.DataFrame(datos,columns=columnas)

    st.dataframe(df)

    output=BytesIO()

    with pd.ExcelWriter(output,engine="xlsxwriter") as writer:

        df.to_excel(writer,index=False,sheet_name="RETENCIONES")

        workbook=writer.book
        worksheet=writer.sheets["RETENCIONES"]

        header1=workbook.add_format({
            "bold":True,
            "border":1,
            "align":"center",
            "bg_color":"#FFFF00"
        })

        header2=workbook.add_format({
            "bold":True,
            "border":1,
            "align":"center",
            "bg_color":"#00B0F0"
        })

        for col,col_name in enumerate(columnas):

            if col>=14:
                worksheet.write(0,col,col_name,header2)
            else:
                worksheet.write(0,col,col_name,header1)

        filas=len(df)+1

        total_format=workbook.add_format({
            "bold":True,
            "border":1,
            "bg_color":"#FFFF00"
        })

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
        file_name="retenciones_sri.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
