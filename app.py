import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")

st.title("Análise de Viabilidade de Fundos de Investimento")
st.write("Configure os parâmetros do fundo na barra lateral para gerar o fluxo de caixa.")

# --- 1. ENTRADA DE DADOS (SIDEBAR) ---
st.sidebar.header("Parâmetros Gerais do Fundo")

nome_fundo = st.sidebar.text_input("Nome do Fundo", "Fundo Imobiliário Exemplo")
data_inicio = st.sidebar.date_input("Data de Início", date(2024, 1, 1))
duracao_anos = st.sidebar.number_input("Duração do Fundo (anos)", value=10, min_value=1, max_value=50)

aporte_inicial = st.sidebar.number_input("Aporte Inicial (R$)", value=10000000, step=1000000)

# Parâmetros das curvas (por enquanto, manuais)
st.sidebar.subheader("Curvas de Juros (Projeção Anual)")
projecao_cdi = st.sidebar.number_input("Projeção CDI (% a.a.)", value=10.0, step=0.5)
projecao_ipca = st.sidebar.number_input("Projeção IPCA (% a.a.)", value=4.5, step=0.25)


# --- 2. MOTOR DE CÁLCULO ---

# Converte taxas anuais para mensais
taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1

# Cria o DataFrame base com o período de análise
meses_total = duracao_anos * 12
datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
df = pd.DataFrame(index=datas_projecao)

# Colunas iniciais do fluxo de caixa
df['Mês'] = range(meses_total + 1)
df['Saldo Caixa Inicial'] = 0.0
df['(+) Aportes'] = 0.0
df['(+) Rendimento Caixa'] = 0.0
df['Saldo Caixa Final'] = 0.0

# --- Lógica do Fluxo de Caixa ---

# Mês 0 (Aporte Inicial)
df.loc[df.index[0], '(+) Aportes'] = aporte_inicial
df.loc[df.index[0], 'Saldo Caixa Final'] = aporte_inicial

# Projeção mensal
for i in range(1, len(df)):
    # Saldo inicial do mês atual é o final do mês anterior
    saldo_anterior = df.iloc[i-1]['Saldo Caixa Final']
    df.iloc[i]['Saldo Caixa Inicial'] = saldo_anterior
    
    # Rendimento do caixa sobre o saldo inicial
    rendimento_caixa = saldo_anterior * taxa_cdi_mensal
    df.iloc[i]['(+) Rendimento Caixa'] = rendimento_caixa
    
    # Saldo final (ainda sem outras movimentações)
    # A fórmula completa será: Saldo Inicial + Aportes + Receitas - Despesas - Investimentos
    saldo_final = saldo_anterior + rendimento_caixa 
    df.iloc[i]['Saldo Caixa Final'] = saldo_final
    

# --- 3. EXIBIÇÃO DOS RESULTADOS ---

st.header("Fluxo de Caixa Mensal Detalhado")
st.write("Esta é a projeção inicial do fluxo de caixa do fundo, considerando apenas o aporte inicial e o rendimento do caixa.")

# Formatação para exibição
df_display = df.copy()
colunas_monetarias = ['Saldo Caixa Inicial', '(+) Aportes', '(+) Rendimento Caixa', 'Saldo Caixa Final']
for col in colunas_monetarias:
    df_display[col] = df_display[col].apply(lambda x: f"R$ {x:,.2f}")

df_display.index = df_display.index.strftime('%Y-%m')

st.dataframe(df_display)


# Botão para Download
@st.cache_data
def convert_df_to_excel(df_to_convert):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_convert.to_excel(writer, index=True, sheet_name='FluxoCaixa')
    processed_data = output.getvalue()
    return processed_data

excel_file = convert_df_to_excel(df)

st.download_button(
    label="📥 Exportar para Excel",
    data=excel_file,
    file_name=f"viabilidade_{nome_fundo.replace(' ', '_').lower()}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
