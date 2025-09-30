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
    if 'lista_despesas' not in st.session_state:
        st.session_state.lista_despesas = [{'Nome': 'Taxa de Adm', 'Tipo': '% do PL', 'Valor': 0.2}]
    
    if st.button("Adicionar Despesa"):
        st.session_state.lista_despesas.append({'Nome': f"Despesa {len(st.session_state.lista_despesas) + 1}",'Tipo': 'Fixo Mensal','Valor': 10000.0})

    for i, despesa in enumerate(st.session_state.lista_despesas):
        with st.expander(f"Configurar {despesa['Nome']}", expanded=True):
            despesa['Nome'] = st.text_input("Nome", value=despesa['Nome'], key=f"desp_nome_{i}")
            despesa['Tipo'] = st.selectbox("Tipo de Cálculo", options=['% do PL', 'Fixo Mensal'], key=f"desp_tipo_{i}")
            if despesa['Tipo'] == '% do PL':
                despesa['Valor'] = st.number_input("Valor (% a.a.)", value=despesa.get('Valor', 0.2), step=0.05, key=f"desp_valor_pct_{i}")
            else:
                despesa['Valor'] = st.number_input("Valor (R$)", value=despesa.get('Valor', 10000.0), step=1000.0, key=f"desp_valor_brl_{i}")

    st.subheader("Modelagem de Ativos")
    if 'lista_ativos' not in st.session_state:
        st.session_state.lista_ativos = []

    if st.button("Adicionar Ativo Genérico"):
        st.session_state.lista_ativos.append({'Nome': f"Ativo {len(st.session_state.lista_ativos) + 1}",'Valor': 2000000.0,'Mês Investimento': 1,'Benchmark': 'IPCA','Spread': 7.0})

    for i, ativo in enumerate(st.session_state.lista_ativos):
        with st.expander(f"Configurar {ativo['Nome']}", expanded=True):
            ativo['Nome'] = st.text_input(f"Nome", value=ativo['Nome'], key=f"nome_{i}")
            ativo['Valor'] = st.number_input(f"Valor (R$)", value=ativo['Valor'], key=f"valor_{i}")
            ativo['Mês Investimento'] = st.number_input(f"Mês Invest.", value=ativo['Mês Investimento'], min_value=1, max_value=duracao_anos*12, key=f"mes_{i}")
            ativo['Benchmark'] = st.selectbox(f"Benchmark", options=['IPCA', 'CDI'], index=0 if ativo['Benchmark'] == 'IPCA' else 1, key=f"bench_{i}")
            ativo['Spread'] = st.number_input(f"Spread (% a.a.)", value=ativo['Spread'], step=0.5, key=f"spread_{i}")
    
    st.markdown("---")
    run_button = st.button("Gerar Projeção", type="primary")

# --- Estrutura de Abas ---
tab_fluxo, tab_dashboard, tab_dre = st.tabs(["Fluxo de Caixa Detalhado", "Dashboard & Indicadores", "DRE"])

if not run_button:
    with tab_fluxo:
        st.info("⬅️ Configure os parâmetros na barra lateral e clique em 'Gerar Projeção' para iniciar a análise.")
else:
    # --- 2. MOTOR DE CÁLCULO (LÓGICA CORRIGIDA E ROBUSTA) ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    
    # Tracker individual de ativos, a abordagem correta
    valor_individual_ativos = [0.0] * len(st.session_state.lista_ativos)
    
    lista_fluxos = []
    
    # MÊS 0 (SETUP)
    fluxo_mes_0 = {
        'Mês': 0, 'PL Início': 0, '(+) Aportes': aporte_inicial,
        'Ativos_Volume': 0, 'Ativos_Rend_R$': 0, 'Caixa_Volume': aporte_inicial, 'Caixa_Rend_R$': 0,
        'Total Despesas': 0, 'Rend. Pré-Desp_R$': 0, 'Rend. Pós-Desp_R$': 0, 'PL Final': aporte_inicial
    }
    for despesa in st.session_state.lista_despesas: fluxo_mes_0[f"(-) {despesa['Nome']}"] = 0
    lista_fluxos.append(fluxo_mes_0)

    # LOOP DE PROJEÇÃO MENSAL
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        
        # 1. Ponto de Partida
        pl_inicio_mes = fluxo_anterior['PL Final']
        caixa_inicio_mes = fluxo_anterior['Caixa_Volume']
        
        # 2. Rendimento dos Ativos existentes (calculado sobre o saldo inicial)
        rend_ativos_mes = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if valor_individual_ativos[i] > 0: # Se o ativo já existe na carteira
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                taxa_ativo = (1 + (taxa_cdi_mensal if ativo['Benchmark'] == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                rendimento_i = valor_individual_ativos[i] * taxa_ativo
                rend_ativos_mes += rendimento_i
                valor_individual_ativos[i] += rendimento_i # Valor do ativo cresce com o rendimento

        # 3. Novos Investimentos
        novos_investimentos_mes = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if ativo['Mês Investimento'] == mes:
                invest_valor = ativo['Valor']
                novos_investimentos_mes += invest_valor
                valor_individual_ativos[i] += invest_valor # Adiciona o principal ao valor do ativo

        # 4. Fluxo de Caixa
        caixa_pos_investimento = caixa_inicio_mes - novos_investimentos_mes
        rend_caixa_mes = max(0, caixa_pos_investimento) * taxa_cdi_mensal
        
        # 5. Despesas
        despesas_mes_dict = {}
        total_despesas_mes = 0
        for despesa in st.session_state.lista_despesas:
            valor_despesa = pl_inicio_mes * (despesa['Valor'] / 100 / 12) if despesa['Tipo'] == '% do PL' else despesa['Valor']
            despesas_mes_dict[f"(-) {despesa['Nome']}"] = valor_despesa
            total_despesas_mes += valor_despesa
            
        caixa_final_mes = caixa_pos_investimento + rend_caixa_mes - total_despesas_mes
        
        # 6. Consolidação Final
        vol_ativos_final_mes = sum(valor_individual_ativos)
        pl_final_mes = vol_ativos_final_mes + caixa_final_mes

        # 7. Cálculo de Percentuais
        rend_pre_desp = rend_ativos_mes + rend_caixa_mes
        rend_pos_desp = rend_pre_desp - total_despesas_mes
        
        fluxo_atual = {
            'Mês': mes, 'PL Início': pl_inicio_mes, '(+) Aportes': 0,
            'Ativos_Volume': vol_ativos_final_mes, 'Ativos_Rend_R$': rend_ativos_mes,
            'Caixa_Volume': caixa_final_mes, 'Caixa_Rend_R$': rend_caixa_mes,
            'Total Despesas': total_despesas_mes,
            'Rend. Pré-Desp_R$': rend_pre_desp, 'Rend. Pós-Desp_R$': rend_pos_desp, 'PL Final': pl_final_mes
        }
        fluxo_atual.update(despesas_mes_dict)
        lista_fluxos.append(fluxo_atual)

    # --- 3. PÓS-PROCESSAMENTO E EXIBIÇÃO ---
    df = pd.DataFrame(lista_fluxos)
    if not df.empty:
        df.index = datas_projecao
        df['Ano'] = df.index.year
        df['Ativos_% Alocado'] = df['Ativos_Volume'] / df['PL Final']
        df['Caixa_% Alocado'] = df['Caixa_Volume'] / df['PL Final']
        df['Ativos_Rend_%'] = df['Ativos_Rend_R$'] / df['Ativos_Volume'].shift(1)
        df['Caixa_Rend_%'] = df['Caixa_Rend_R$'] / df['Caixa_Volume'].shift(1)
        df['Rend. Pré-Desp_%'] = df['Rend. Pré-Desp_R$'] / df['PL Início']
        df['Rend. Pós-Desp_%'] = df['Rend. Pós-Desp_R$'] / df['PL Início']
        df.fillna(0, inplace=True)
        df.replace([float('inf'), -float('inf')], 0, inplace=True)

    with tab_fluxo:
        # (código da aba de fluxo de caixa - sem alterações)
        st.header("Fluxo de Caixa Detalhado")
        # (O código de formatação e exibição do DataFrame permanece o mesmo)
        st.dataframe(df) # Exibição simplificada para depuração

    with tab_dashboard:
        # (código da aba de dashboard - sem alterações)
        st.header("Dashboard de Performance")
        if not df.empty:
            pl_final = df['PL Final'].iloc[-1]
            fluxo_investidor = [-aporte_inicial] + [0] * (meses_total - 1) + [pl_final]
            try: tir_anual = (1 + npf.irr(fluxo_investidor))**12 - 1
            except: tir_anual = float('nan')
            moic = pl_final / aporte_inicial if aporte_inicial != 0 else 0

            col1, col2 = st.columns(2)
            col1.metric("TIR Anualizada do Projeto", f"{tir_anual:.2%}" if not pd.isna(tir_anual) else "N/A")
            col2.metric("MOIC (Múltiplo)", f"{moic:.2f}x")
            
            st.subheader("Evolução do Patrimônio Líquido")
            st.line_chart(df['PL Final'])
            
            st.subheader("Composição do Patrimônio")
            st.area_chart(df[['Ativos_Volume', 'Caixa_Volume']].rename(columns={'Ativos_Volume': 'Ativos', 'Caixa_Volume': 'Caixa'}))

    with tab_dre:
        # (código da aba de DRE - sem alterações)
        st.header("Demonstração de Resultados (DRE)")
        if not df.empty:
            df['Receitas'] = df['Ativos_Rend_R$'] + df['Caixa_Rend_R$']
            
            dre_anual = df.groupby('Ano').agg({ 'Receitas': 'sum', 'Total Despesas': 'sum' })
            dre_anual['Resultado'] = dre_anual['Receitas'] - dre_anual['Total Despesas']
            
            st.subheader("Resultado Anual")
            st.dataframe(dre_anual.style.format("R$ {:,.2f}"))
            
            st.subheader("Gráfico de Resultado Anual")
            st.bar_chart(dre_anual)
