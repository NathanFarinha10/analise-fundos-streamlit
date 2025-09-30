import streamlit as st
import pandas as pd
import numpy_financial as npf
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")

st.title("Análise de Viabilidade de Fundos de Investimento")

# --- 1. ENTRADA DE DADOS (SIDEBAR) ---
with st.sidebar:
    st.header("Parâmetros Gerais")
    nome_fundo = st.text_input("Nome do Fundo", "Fundo Exemplo")
    data_inicio = st.date_input("Data de Início", date(2024, 1, 1))
    duracao_anos = st.number_input("Duração (anos)", value=10, min_value=1, max_value=50)
    aporte_inicial = st.number_input("Aporte Inicial (R$)", value=10000000, step=1000000)

    st.subheader("Curvas de Juros (% a.a.)")
    projecao_cdi = st.number_input("Projeção CDI", value=10.0, step=0.5)
    projecao_ipca = st.number_input("Projeção IPCA", value=4.5, step=0.25)

    st.subheader("Despesas do Fundo")
    taxa_adm_anual = st.number_input("Taxa de Adm. (% a.a. sobre PL)", value=0.2, step=0.05)
    outras_despesas_fixas = st.number_input("Outras Despesas (R$ fixo / mês)", value=15000, step=1000)

    st.subheader("Modelagem de Ativos")
    if 'lista_ativos' not in st.session_state:
        st.session_state.lista_ativos = []
    
    def adicionar_ativo():
        st.session_state.lista_ativos.append({
            'Nome': f"Ativo {len(st.session_state.lista_ativos) + 1}", 'Valor': 1000000.0,
            'Mês Investimento': 1, 'Benchmark': 'IPCA', 'Spread': 6.0
        })
    st.button("Adicionar Ativo Genérico", on_click=adicionar_ativo)

    for i, ativo in enumerate(st.session_state.lista_ativos):
        with st.expander(f"Configurações do {ativo['Nome']}", expanded=True):
            ativo['Nome'] = st.text_input(f"Nome", value=ativo['Nome'], key=f"nome_{i}")
            ativo['Valor'] = st.number_input(f"Valor (R$)", value=ativo['Valor'], key=f"valor_{i}")
            ativo['Mês Investimento'] = st.number_input(f"Mês Invest.", value=ativo['Mês Investimento'], min_value=1, max_value=duracao_anos*12, key=f"mes_{i}")
            ativo['Benchmark'] = st.selectbox(f"Benchmark", options=['IPCA', 'CDI'], index=0 if ativo['Benchmark'] == 'IPCA' else 1, key=f"bench_{i}")
            ativo['Spread'] = st.number_input(f"Spread (% a.a.)", value=ativo['Spread'], step=0.5, key=f"spread_{i}")
    
    st.markdown("---")
    run_button = st.button("Gerar Projeção", type="primary")

# --- 2. MOTOR DE CÁLCULO E EXIBIÇÃO ---
if run_button:
    # --- SETUP INICIAL ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    taxa_adm_mensal = taxa_adm_anual / 12 / 100
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    valor_atual_ativos = {i: 0.0 for i in range(len(st.session_state.lista_ativos))}
    lista_fluxos = []

    # --- MÊS 0 (SETUP) ---
    fluxo_mes_0 = {
        'Mês': 0, 'Saldo Caixa Inicial': 0, '(+) Aportes': aporte_inicial,
        '(+) Receita Ativos': 0, '(+) Rendimento Caixa': 0, '(-) Investimentos': 0,
        '(-) Taxa de Adm.': 0, '(-) Outras Despesas': 0,
        'Saldo Caixa Final': aporte_inicial, 'PL Ativos': 0, 'Patrimônio Líquido': aporte_inicial
    }
    lista_fluxos.append(fluxo_mes_0)

    # --- LOOP DE PROJEÇÃO MENSAL ---
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        pl_anterior = fluxo_anterior['Patrimônio Líquido']
        saldo_caixa_inicial = fluxo_anterior['Saldo Caixa Final']
        
        investimentos_mes = sum(ativo['Valor'] for i, ativo in enumerate(st.session_state.lista_ativos) if ativo['Mês Investimento'] == mes)
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if ativo['Mês Investimento'] == mes:
                valor_atual_ativos[i] = ativo['Valor']
        
        receita_total_ativos = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if mes > ativo['Mês Investimento']:
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                taxa_ativo = (1 + (taxa_cdi_mensal if ativo['Benchmark'] == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                rendimento_ativo_i = valor_atual_ativos[i] * taxa_ativo
                receita_total_ativos += rendimento_ativo_i
                valor_atual_ativos[i] += rendimento_ativo_i
        
        despesa_taxa_adm = pl_anterior * taxa_adm_mensal
        caixa_para_rendimento = saldo_caixa_inicial - investimentos_mes
        rendimento_caixa = max(0, caixa_para_rendimento) * taxa_cdi_mensal
        
        saldo_caixa_final = (saldo_caixa_inicial + receita_total_ativos + rendimento_caixa -
                             investimentos_mes - despesa_taxa_adm - outras_despesas_fixas)
                             
        pl_ativos = sum(valor_atual_ativos.values())
        patrimonio_liquido = saldo_caixa_final + pl_ativos

        lista_fluxos.append({
            'Mês': mes, 'Saldo Caixa Inicial': saldo_caixa_inicial, '(+) Aportes': 0,
            '(+) Receita Ativos': receita_total_ativos, '(+) Rendimento Caixa': rendimento_caixa,
            '(-) Investimentos': investimentos_mes, '(-) Taxa de Adm.': despesa_taxa_adm,
            '(-) Outras Despesas': outras_despesas_fixas, 'Saldo Caixa Final': saldo_caixa_final,
            'PL Ativos': pl_ativos, 'Patrimônio Líquido': patrimonio_liquido
        })

    # --- PÓS-PROCESSAMENTO E CRIAÇÃO DO DATAFRAME ---
    df = pd.DataFrame(lista_fluxos).set_index('Mês')
    df.index = datas_projecao
    
    # --- NOVO: CÁLCULO DOS KPIs ---
    pl_final = df['Patrimônio Líquido'].iloc[-1]
    
    # TIR (IRR) do Projeto
    fluxo_investidor = [-aporte_inicial] + [0] * (meses_total - 1) + [pl_final]
    try:
        tir_mensal = npf.irr(fluxo_investidor)
        tir_anual = (1 + tir_mensal)**12 - 1
    except:
        tir_anual = float('nan') # Em caso de erro no cálculo

    # MOIC (Multiple on Invested Capital)
    moic = pl_final / aporte_inicial if aporte_inicial != 0 else 0

    # --- 3. EXIBIÇÃO DOS RESULTADOS ---
    st.header("Dashboard de Performance")

    col1, col2 = st.columns(2)
    col1.metric("TIR Anualizada do Projeto", f"{tir_anual:.2%}" if not pd.isna(tir_anual) else "N/A")
    col2.metric("MOIC (Múltiplo)", f"{moic:.2f}x")

    st.subheader("Evolução do Patrimônio Líquido")
    st.line_chart(df['Patrimônio Líquido'])
    
    st.subheader("Composição do Patrimônio")
    st.area_chart(df[['Saldo Caixa Final', 'PL Ativos']])

    st.subheader("Receitas vs. Despesas Mensais")
    df_receitas = df['(+) Receita Ativos'] + df['(+) Rendimento Caixa']
    df_despesas = df['(-) Taxa de Adm.'] + df['(-) Outras Despesas']
    st.bar_chart(pd.DataFrame({'Receitas': df_receitas, 'Despesas': df_despesas}))


    # --- Tabela de Fluxo de Caixa ---
    with st.expander("Ver Fluxo de Caixa Mensal Detalhado"):
        df_display = df.copy()
        colunas_monetarias = [col for col in df.columns]
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
            label="📥 Exportar para Excel", data=excel_file,
            file_name=f"viabilidade_{nome_fundo.replace(' ', '_').lower()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("⬅️ Configure os parâmetros na barra lateral e clique em 'Gerar Projeção' para iniciar a análise.")
