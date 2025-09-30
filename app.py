import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")

st.title("Análise de Viabilidade de Fundos de Investimento")

# --- 1. ENTRADA DE DADOS (SIDEBAR) ---
with st.sidebar:
    st.header("Parâmetros Gerais do Fundo")

    nome_fundo = st.text_input("Nome do Fundo", "Fundo Imobiliário Exemplo")
    data_inicio = st.date_input("Data de Início", date(2024, 1, 1))
    duracao_anos = st.number_input("Duração do Fundo (anos)", value=10, min_value=1, max_value=50)
    aporte_inicial = st.number_input("Aporte Inicial (R$)", value=10000000, step=1000000)

    st.subheader("Curvas de Juros (Projeção Anual)")
    projecao_cdi = st.number_input("Projeção CDI (% a.a.)", value=10.0, step=0.5)
    projecao_ipca = st.number_input("Projeção IPCA (% a.a.)", value=4.5, step=0.25)

    st.subheader("Modelagem de Ativos")

    # Inicializa a lista de ativos no session_state se ela não existir
    if 'lista_ativos' not in st.session_state:
        st.session_state.lista_ativos = []

    # Função para adicionar um novo ativo à lista
    def adicionar_ativo():
        novo_ativo = {
            'Nome': f"Ativo {len(st.session_state.lista_ativos) + 1}",
            'Valor': 1000000.0,
            'Mês Investimento': 1,
            'Benchmark': 'IPCA',
            'Spread': 6.0
        }
        st.session_state.lista_ativos.append(novo_ativo)

    st.button("Adicionar Ativo Genérico", on_click=adicionar_ativo)

    # Mostra os inputs para cada ativo adicionado
    for i, ativo in enumerate(st.session_state.lista_ativos):
        with st.expander(f"Configurações do {ativo['Nome']}", expanded=True):
            ativo['Nome'] = st.text_input(f"Nome do Ativo", value=ativo['Nome'], key=f"nome_{i}")
            ativo['Valor'] = st.number_input(f"Valor do Investimento (R$)", value=ativo['Valor'], key=f"valor_{i}")
            ativo['Mês Investimento'] = st.number_input(f"Mês do Investimento (1 a {duracao_anos*12})", value=ativo['Mês Investimento'], min_value=1, max_value=duracao_anos*12, key=f"mes_{i}")
            ativo['Benchmark'] = st.selectbox(f"Benchmark", options=['IPCA', 'CDI'], index=0 if ativo['Benchmark'] == 'IPCA' else 1, key=f"bench_{i}")
            ativo['Spread'] = st.number_input(f"Spread (% a.a.)", value=ativo['Spread'], step=0.5, key=f"spread_{i}")
    
    st.markdown("---")
    # --- NOVO: O botão de ação que dispara o cálculo ---
    run_button = st.button("Gerar Projeção", type="primary")


# --- 2. MOTOR DE CÁLCULO E EXIBIÇÃO (SÓ RODA SE O BOTÃO FOR CLICADO) ---

if run_button:
    # Converte taxas anuais para mensais
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1

    # Cria o DataFrame base com o período de análise
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    df = pd.DataFrame(index=datas_projecao)

    # Colunas do fluxo de caixa
    df['Mês'] = range(meses_total + 1)
    df['Saldo Caixa Inicial'] = 0.0
    df['(+) Aportes'] = 0.0
    df['(+) Rendimento Caixa'] = 0.0
    df['(+) Receita Ativos'] = 0.0
    df['(-) Investimentos'] = 0.0
    df['Saldo Caixa Final'] = 0.0
    df['PL Ativos'] = 0.0
    df['Patrimônio Líquido'] = 0.0

    # Lógica do Fluxo de Caixa
    df.loc[df.index[0], '(+) Aportes'] = aporte_inicial
    df.loc[df.index[0], 'Saldo Caixa Final'] = aporte_inicial
    df.loc[df.index[0], 'Patrimônio Líquido'] = aporte_inicial

    valor_atual_ativos = {i: 0.0 for i in range(len(st.session_state.lista_ativos))}

    for i in range(1, len(df)):
        mes_atual = i
        saldo_caixa_anterior = df.iloc[i-1]['Saldo Caixa Final']
        df.iloc[i]['Saldo Caixa Inicial'] = saldo_caixa_anterior
        
        investimentos_mes = 0
        for j, ativo in enumerate(st.session_state.lista_ativos):
            if ativo['Mês Investimento'] == mes_atual:
                investimentos_mes += ativo['Valor']
                valor_atual_ativos[j] = ativo['Valor']
        df.iloc[i]['(-) Investimentos'] = investimentos_mes
        
        receita_total_ativos = 0
        for j, ativo in enumerate(st.session_state.lista_ativos):
            if mes_atual > ativo['Mês Investimento']:
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                if ativo['Benchmark'] == 'CDI':
                    taxa_ativo = (1 + taxa_cdi_mensal) * (1 + spread_mensal) - 1
                else:
                    taxa_ativo = (1 + taxa_ipca_mensal) * (1 + spread_mensal) - 1
                
                rendimento_ativo_j = valor_atual_ativos[j] * taxa_ativo
                receita_total_ativos += rendimento_ativo_j
                valor_atual_ativos[j] += rendimento_ativo_j

        df.iloc[i]['(+) Receita Ativos'] = receita_total_ativos
        df.iloc[i]['PL Ativos'] = sum(valor_atual_ativos.values())

        caixa_para_rendimento = saldo_caixa_anterior - investimentos_mes
        rendimento_caixa = max(0, caixa_para_rendimento) * taxa_cdi_mensal
        df.iloc[i]['(+) Rendimento Caixa'] = rendimento_caixa
        
        saldo_final = caixa_para_rendimento + rendimento_caixa + receita_total_ativos
        df.iloc[i]['Saldo Caixa Final'] = saldo_final
        
        df.iloc[i]['Patrimônio Líquido'] = saldo_final + df.iloc[i]['PL Ativos']

    # --- EXIBIÇÃO DOS RESULTADOS ---
    st.header("Fluxo de Caixa Mensal Detalhado")

    df_display = df.copy()
    colunas_monetarias = [col for col in df.columns if '(' in col or 'Saldo' in col or 'PL' in col or 'Patrimônio' in col]
    for col in colunas_monetarias:
        df_display[col] = df_display[col].apply(lambda x: f"R$ {x:,.2f}")

    df_display.index = df_display.index.strftime('%Y-%m')
    st.dataframe(df_display)

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

else:
    # Mensagem inicial antes do primeiro cálculo
    st.info("⬅️ Configure os parâmetros na barra lateral e clique em 'Gerar Projeção' para iniciar a análise.")
