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

    # --- NOVO: Seção da Taxa de Performance ---
    st.subheader("Taxa de Performance")
    calc_performance = st.toggle("Calcular Taxa de Performance", value=True)
    if calc_performance:
        perf_benchmark = st.selectbox("Benchmark da Performance", options=['CDI', 'IPCA'], index=0)
        perf_spread = st.number_input("Spread sobre Benchmark (% a.a.)", value=0.0, step=0.5)
        perf_percentual = st.number_input("Percentual da Performance (%)", value=20.0, step=1.0)
        perf_carencia = st.number_input("Carência (meses)", value=12, min_value=0)
        perf_periodo = st.selectbox("Período de Apuração", options=['Anual'], index=0) # Anual é 12 meses
        perf_hwm = st.checkbox("Com Linha d'Água (High-Water Mark)", value=True)


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
    # --- 2. MOTOR DE CÁLCULO ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    
    valor_individual_ativos = [0.0] * len(st.session_state.lista_ativos)
    
    # --- NOVO: Variáveis de controle da Performance ---
    high_water_mark = aporte_inicial
    benchmark_acumulado = 1.0
    pl_inicio_periodo_perf = aporte_inicial

    lista_fluxos = []
    
    fluxo_mes_0 = {
        'Mês': 0, 'PL Início': 0, '(+) Aportes': aporte_inicial,
        'Ativos_Volume': 0, 'Ativos_Rend_R$': 0, 'Caixa_Volume': aporte_inicial, 'Caixa_Rend_R$': 0,
        'Total Despesas': 0, 'Rend. Pré-Desp_R$': 0, 'Rend. Pós-Desp_R$': 0, 'PL Final': aporte_inicial,
        '(-) Taxa de Performance': 0.0
    }
    for despesa in st.session_state.lista_despesas: fluxo_mes_0[f"(-) {despesa['Nome']}"] = 0
    lista_fluxos.append(fluxo_mes_0)

    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        
        pl_inicio_mes = fluxo_anterior['PL Final']
        caixa_inicio_mes = fluxo_anterior['Caixa_Volume']
        
        rend_ativos_mes = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if valor_individual_ativos[i] > 0:
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                taxa_ativo = (1 + (taxa_cdi_mensal if ativo['Benchmark'] == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                rendimento_i = valor_individual_ativos[i] * taxa_ativo
                rend_ativos_mes += rendimento_i
                valor_individual_ativos[i] += rendimento_i

        novos_investimentos_mes = sum(ativo['Valor'] for i, ativo in enumerate(st.session_state.lista_ativos) if ativo['Mês Investimento'] == mes)
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if ativo['Mês Investimento'] == mes:
                valor_individual_ativos[i] += ativo['Valor']

        caixa_pos_investimento = caixa_inicio_mes - novos_investimentos_mes
        rend_caixa_mes = max(0, caixa_pos_investimento) * taxa_cdi_mensal
        
        despesas_regulares = 0
        despesas_mes_dict = {}
        for despesa in st.session_state.lista_despesas:
            valor_despesa = pl_inicio_mes * (despesa['Valor'] / 100 / 12) if despesa['Tipo'] == '% do PL' else despesa['Valor']
            despesas_mes_dict[f"(-) {despesa['Nome']}"] = valor_despesa
            despesas_regulares += valor_despesa
            
        pl_pre_performance = pl_inicio_mes + (rend_ativos_mes + rend_caixa_mes) - despesas_regulares

        # --- NOVO: Lógica de Cálculo da Taxa de Performance ---
        taxa_performance_mes = 0
        if calc_performance and mes > perf_carencia and (mes % 12 == 0 or mes == meses_total):
            taxa_benchmark_mensal = taxa_cdi_mensal if perf_benchmark == 'CDI' else taxa_ipca_mensal
            spread_benchmark_mensal = (1 + perf_spread / 100)**(1/12) - 1
            benchmark_final_mensal = (1 + taxa_benchmark_mensal) * (1 + spread_benchmark_mensal) - 1
            
            rent_fundo_periodo = (pl_pre_performance / pl_inicio_periodo_perf) - 1
            rent_bench_periodo = (1 + benchmark_final_mensal)**(mes - (mes // 12 * 12 if mes % 12 != 0 else mes - 12)) -1 # Acumula o benchmark no período

            excedente = rent_fundo_periodo - rent_bench_periodo
            
            if excedente > 0 and (pl_pre_performance > high_water_mark if perf_hwm else True):
                base_calculo = pl_inicio_periodo_perf # ou (pl_inicio_periodo_perf + pl_pre_performance)/2 para média
                taxa_performance_mes = base_calculo * excedente * (perf_percentual / 100)
            
            # Reset para o próximo período
            pl_inicio_periodo_perf = pl_pre_performance - taxa_performance_mes
            if perf_hwm:
                high_water_mark = max(high_water_mark, pl_inicio_periodo_perf)

        total_despesas_mes = despesas_regulares + taxa_performance_mes
        caixa_final_mes = caixa_pos_investimento + rend_caixa_mes - total_despesas_mes
        vol_ativos_final_mes = sum(valor_individual_ativos)
        pl_final_mes = vol_ativos_final_mes + caixa_final_mes
        
        fluxo_atual = {
            'Mês': mes, 'PL Início': pl_inicio_mes, '(+) Aportes': 0, 'Ativos_Volume': vol_ativos_final_mes, 
            'Ativos_Rend_R$': rend_ativos_mes, 'Caixa_Volume': caixa_final_mes, 'Caixa_Rend_R$': rend_caixa_mes,
            'Total Despesas': total_despesas_mes, 'Rend. Pré-Desp_R$': rend_ativos_mes + rend_caixa_mes, 
            'Rend. Pós-Desp_R$': (rend_ativos_mes + rend_caixa_mes) - total_despesas_mes, 
            'PL Final': pl_final_mes, '(-) Taxa de Performance': taxa_performance_mes
        }
        fluxo_atual.update(despesas_mes_dict)
        lista_fluxos.append(fluxo_atual)

    # --- 3. PÓS-PROCESSAMENTO E EXIBIÇÃO ---
    # (O código desta seção permanece o mesmo)
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
        st.header("Fluxo de Caixa Detalhado")
        # Adicionando a nova coluna ao mapa de exibição
        col_map = {
            'Ano': ('Período', 'Ano'), 'Mês': ('Período', 'Mês'),
            'PL Início': ('Geral', 'PL Início'), '(+) Aportes': ('Geral', '(+) Aportes'), 'PL Final': ('Geral', 'PL Final'),
            'Ativos_% Alocado': ('Ativos', '% Alocado'), 'Ativos_Volume': ('Ativos', 'Volume'),
            'Ativos_Rend_R$': ('Ativos', 'Rend R$'), 'Ativos_Rend_%': ('Ativos', 'Rend %'),
            'Caixa_% Alocado': ('Caixa', '% Alocado'), 'Caixa_Volume': ('Caixa', 'Volume'),
            'Caixa_Rend_R$': ('Caixa', 'Rend R$'), 'Caixa_Rend_%': ('Caixa', 'Rend %'),
            'Total Despesas': ('Despesas', 'Total'),
            '(-) Taxa de Performance': ('Despesas', 'Performance'),
            'Rend. Pré-Desp_R$': ('Resultado', 'Rend Pré-Desp R$'), 'Rend. Pré-Desp_%': ('Resultado', 'Rend Pré-Desp %'),
            'Rend. Pós-Desp_R$': ('Resultado', 'Rend Pós-Desp R$'), 'Rend. Pós-Desp_%': ('Resultado', 'Rend Pós-Desp %')
        }
        for desp in st.session_state.lista_despesas: col_map[f"(-) {desp['Nome']}"] = ('Despesas', f"(-) {desp['Nome']}")
        
        df_display = df.rename(columns=col_map)
        
        ordem_final = [col for col in col_map.values() if col in df_display.columns]
        df_display.columns = pd.MultiIndex.from_tuples(df_display.columns)
        df_display = df_display[ordem_final]
        
        st.dataframe(df_display.style.format({
            ('Geral', 'PL Início'): "R$ {:,.2f}", ('Geral', '(+) Aportes'): "R$ {:,.2f}", ('Geral', 'PL Final'): "R$ {:,.2f}",
            ('Ativos', 'Volume'): "R$ {:,.2f}", ('Ativos', 'Rend R$'): "R$ {:,.2f}", ('Ativos', '% Alocado'): "{:.2%}", ('Ativos', 'Rend %'): "{:.2%}",
            ('Caixa', 'Volume'): "R$ {:,.2f}", ('Caixa', 'Rend R$'): "R$ {:,.2f}", ('Caixa', '% Alocado'): "{:.2%}", ('Caixa', 'Rend %'): "{:.2%}",
            ('Despesas', 'Total'): "R$ {:,.2f}", ('Despesas', 'Performance'): "R$ {:,.2f}",
            ('Resultado', 'Rend Pré-Desp R$'): "R$ {:,.2f}", ('Resultado', 'Rend Pós-Desp R$'): "R$ {:,.2f}",
            ('Resultado', 'Rend Pré-Desp %'): "{:.2%}", ('Resultado', 'Rend Pós-Desp %'): "{:.2%}"
        } | {('Despesas', f"(-) {d['Nome']}"): "R$ {:,.2f}" for d in st.session_state.lista_despesas}, na_rep="-"))


    with tab_dashboard:
        # (código da aba de dashboard - sem alterações)
        st.header("Dashboard de Performance")
        # (código restante da aba)
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
            # Adicionando a performance ao DRE
            df['Receitas'] = df['Ativos_Rend_R$'] + df['Caixa_Rend_R$']
            df['Despesas Totais DRE'] = df['Total Despesas'] # Já inclui a performance
            dre_anual = df.groupby('Ano').agg({ 'Receitas': 'sum', 'Despesas Totais DRE': 'sum' })
            dre_anual.rename(columns={'Despesas Totais DRE': 'Total Despesas'}, inplace=True)
            dre_anual['Resultado'] = dre_anual['Receitas'] - dre_anual['Total Despesas']
            
            st.subheader("Resultado Anual")
            st.dataframe(dre_anual.style.format("R$ {:,.2f}"))
            
            st.subheader("Gráfico de Resultado Anual")
            st.bar_chart(dre_anual)
