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
    
    st.subheader("Estratégia de Alocação")
    perc_alocado_ativos = st.slider("Percentual Alocado em Ativos (%)", 0, 100, 95) / 100.0

    st.subheader("Curvas de Juros (% a.a.)")
    projecao_cdi = st.number_input("Projeção CDI", value=10.0, step=0.5)
    projecao_ipca = st.number_input("Projeção IPCA", value=4.5, step=0.25)

    # --- NOVO: Módulo de Despesas Dinâmicas ---
    st.subheader("Despesas do Fundo")
    if 'lista_despesas' not in st.session_state:
        st.session_state.lista_despesas = []
    
    def adicionar_despesa():
        st.session_state.lista_despesas.append({
            'Nome': f"Despesa {len(st.session_state.lista_despesas) + 1}",
            'Tipo': '% do PL', 'Valor': 0.2
        })
    st.button("Adicionar Despesa", on_click=adicionar_despesa)

    for i, despesa in enumerate(st.session_state.lista_despesas):
        with st.expander(f"Configurar {despesa['Nome']}", expanded=True):
            despesa['Nome'] = st.text_input("Nome", value=despesa['Nome'], key=f"desp_nome_{i}")
            despesa['Tipo'] = st.selectbox("Tipo de Cálculo", options=['% do PL', 'Fixo Mensal'], key=f"desp_tipo_{i}")
            if despesa['Tipo'] == '% do PL':
                despesa['Valor'] = st.number_input("Valor (% a.a.)", value=despesa['Valor'], step=0.05, key=f"desp_valor_pct_{i}")
            else:
                despesa['Valor'] = st.number_input("Valor (R$)", value=15000.0, step=1000.0, key=f"desp_valor_brl_{i}")

    # Módulo de Ativos (semelhante ao anterior)
    st.subheader("Modelagem de Ativos")
    if 'lista_ativos' not in st.session_state:
        st.session_state.lista_ativos = []
    # ... (código para adicionar ativos permanece o mesmo) ...
    def adicionar_ativo():
        st.session_state.lista_ativos.append({'Nome': f"Ativo {len(st.session_state.lista_ativos) + 1}",'Valor': 1000000.0,'Mês Investimento': 1,'Benchmark': 'IPCA','Spread': 6.0})
    st.button("Adicionar Ativo Genérico", on_click=adicionar_ativo)
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
    # --- 2. MOTOR DE CÁLCULO (RECONSTRUÍDO) ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    valor_atual_ativos = {f"Ativo_{i}": 0.0 for i in range(len(st.session_state.lista_ativos))}
    
    lista_fluxos = []
    # --- MÊS 0 (SETUP) ---
    fluxo_mes_0 = {'Mês': 0, 'Ano': data_inicio.year, 'PL Início': 0, '(+) Aportes': aporte_inicial}
    fluxo_mes_0.update({'Ativos_% Alocado': 0, 'Ativos_Volume': 0, 'Ativos_Rend_R$': 0, 'Ativos_Rend_%': 0,
                        'Caixa_% Alocado': 1, 'Caixa_Volume': aporte_inicial, 'Caixa_Rend_R$': 0, 'Caixa_Rend_%': 0,
                        'Total Despesas': 0, 'Rend. Pré-Desp_R$': 0, 'Rend. Pré-Desp_%': 0,
                        'Rend. Pós-Desp_R$': 0, 'Rend. Pós-Desp_%': 0, 'PL Final': aporte_inicial})
    for despesa in st.session_state.lista_despesas: # Adiciona colunas de despesa
        fluxo_mes_0[f"(-) {despesa['Nome']}"] = 0
    lista_fluxos.append(fluxo_mes_0)

    # --- LOOP DE PROJEÇÃO MENSAL ---
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        pl_inicio_mes = fluxo_anterior['PL Final']
        
        # 1. Alocação de Ativos e Caixa
        vol_alocado_ativos_target = pl_inicio_mes * perc_alocado_ativos
        saldo_caixa = pl_inicio_mes - fluxo_anterior['Ativos_Volume']
        
        # Novos investimentos saem do caixa
        novos_investimentos = sum(ativo['Valor'] for i, ativo in enumerate(st.session_state.lista_ativos) if ativo['Mês Investimento'] == mes)
        saldo_caixa -= novos_investimentos
        
        # 2. Rendimentos
        rend_ativos_mes = 0
        vol_ativos_final_mes = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            valor_ativo_key = f"Ativo_{i}"
            if mes > ativo['Mês Investimento']:
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                taxa_ativo = (1 + (taxa_cdi_mensal if ativo['Benchmark'] == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                rendimento_i = fluxo_anterior.get(valor_ativo_key, 0) * taxa_ativo
                rend_ativos_mes += rendimento_i
                valor_atual_ativos[valor_ativo_key] = fluxo_anterior.get(valor_ativo_key, 0) + rendimento_i
            if ativo['Mês Investimento'] == mes:
                valor_atual_ativos[valor_ativo_key] = ativo['Valor']
        
        vol_ativos_final_mes = sum(valor_atual_ativos.values())
        rend_caixa_mes = max(0, saldo_caixa) * taxa_cdi_mensal
        
        # 3. Despesas
        despesas_mes = {}
        total_despesas_mes = 0
        for despesa in st.session_state.lista_despesas:
            if despesa['Tipo'] == '% do PL':
                valor_despesa = pl_inicio_mes * (despesa['Valor'] / 100 / 12)
            else: # Fixo Mensal
                valor_despesa = despesa['Valor']
            despesas_mes[f"(-) {despesa['Nome']}"] = valor_despesa
            total_despesas_mes += valor_despesa
            
        # 4. Consolidação
        rend_total_pre_desp = rend_ativos_mes + rend_caixa_mes
        rend_total_pos_desp = rend_total_pre_desp - total_despesas_mes
        pl_final_mes = pl_inicio_mes + rend_total_pos_desp
        
        fluxo_atual = {
            'Mês': mes, 'Ano': datas_projecao[mes].year, 'PL Início': pl_inicio_mes, '(+) Aportes': 0,
            'Ativos_% Alocado': (vol_ativos_final_mes / pl_final_mes) if pl_final_mes else 0,
            'Ativos_Volume': vol_ativos_final_mes, 'Ativos_Rend_R$': rend_ativos_mes,
            'Ativos_Rend_%': (rend_ativos_mes / fluxo_anterior['Ativos_Volume']) if fluxo_anterior['Ativos_Volume'] else 0,
            'Caixa_% Alocado': ((pl_final_mes - vol_ativos_final_mes) / pl_final_mes) if pl_final_mes else 0,
            'Caixa_Volume': pl_final_mes - vol_ativos_final_mes,
            'Caixa_Rend_R$': rend_caixa_mes, 'Caixa_Rend_%': taxa_cdi_mensal,
            'Total Despesas': total_despesas_mes,
            'Rend. Pré-Desp_R$': rend_total_pre_desp,
            'Rend. Pré-Desp_%': (rend_total_pre_desp / pl_inicio_mes) if pl_inicio_mes else 0,
            'Rend. Pós-Desp_R$': rend_total_pos_desp,
            'Rend. Pós-Desp_%': (rend_total_pos_desp / pl_inicio_mes) if pl_inicio_mes else 0,
            'PL Final': pl_final_mes
        }
        for i, (key, value) in enumerate(valor_atual_ativos.items()):
            fluxo_atual[key] = value
        fluxo_atual.update(despesas_mes)
        lista_fluxos.append(fluxo_atual)

    # --- 3. EXIBIÇÃO DOS RESULTADOS ---
    df = pd.DataFrame(lista_fluxos).set_index('Mês')
    
    # Organizando Colunas com MultiIndex para visualização
    colunas_ordem = [
        ('Período', 'Ano'), ('Período', 'Data'), ('Geral', 'PL Início'), ('Geral', '(+) Aportes'),
        ('Ativos', '% Alocado'), ('Ativos', 'Volume'), ('Ativos', 'Rend. R$'), ('Ativos', 'Rend. %'),
        ('Caixa', '% Alocado'), ('Caixa', 'Volume'), ('Caixa', 'Rend. R$'), ('Caixa', 'Rend. %')
    ]
    # Adicionando colunas de despesas dinamicamente
    for despesa in st.session_state.lista_despesas:
        colunas_ordem.append(('Despesas', f"(-) {despesa['Nome']}"))
    colunas_ordem.extend([
        ('Despesas', 'Total'),
        ('Resultado', 'Rend. Pré-Desp R$'), ('Resultado', 'Rend. Pré-Desp %'),
        ('Resultado', 'Rend. Pós-Desp R$'), ('Resultado', 'Rend. Pós-Desp %'),
        ('Geral', 'PL Final')
    ])
    
    # Renomeando colunas do DF para corresponder
    df_display = df.rename(columns={
        'Ano': ('Período', 'Ano'), 'PL Início': ('Geral', 'PL Início'), '(+) Aportes': ('Geral', '(+) Aportes'),
        'Ativos_% Alocado': ('Ativos', '% Alocado'), 'Ativos_Volume': ('Ativos', 'Volume'), 'Ativos_Rend_R$': ('Ativos', 'Rend. R$'), 'Ativos_Rend_%': ('Ativos', 'Rend. %'),
        'Caixa_% Alocado': ('Caixa', '% Alocado'), 'Caixa_Volume': ('Caixa', 'Volume'), 'Caixa_Rend_R$': ('Caixa', 'Rend. R$'), 'Caixa_Rend_%': ('Caixa', 'Rend. %'),
        'Total Despesas': ('Despesas', 'Total'),
        'Rend. Pré-Desp_R$': ('Resultado', 'Rend. Pré-Desp R$'), 'Rend. Pré-Desp_%': ('Resultado', 'Rend. Pré-Desp %'),
        'Rend. Pós-Desp_R$': ('Resultado', 'Rend. Pós-Desp R$'), 'Rend. Pós-Desp_%': ('Resultado', 'Rend. Pós-Desp %'),
        'PL Final': ('Geral', 'PL Final')
    })
    for despesa in st.session_state.lista_despesas:
        df_display = df_display.rename(columns={f"(-) {despesa['Nome']}": ('Despesas', f"(-) {despesa['Nome']}")})
    df_display[('Período', 'Data')] = datas_projecao
    
    df_display.columns = pd.MultiIndex.from_tuples(df_display.columns)
    df_final_display = df_display.reindex(columns=[col for col in colunas_ordem if col in df_display.columns], axis=1)

    with tab_fluxo:
        st.header("Fluxo de Caixa Detalhado")
        st.dataframe(df_final_display.style.format({
            ('Geral', 'PL Início'): "R$ {:,.2f}", ('Geral', '(+) Aportes'): "R$ {:,.2f}", ('Geral', 'PL Final'): "R$ {:,.2f}",
            ('Ativos', 'Volume'): "R$ {:,.2f}", ('Ativos', 'Rend. R$'): "R$ {:,.2f}", ('Ativos', '% Alocado'): "{:.2%}", ('Ativos', 'Rend. %'): "{:.2%}",
            ('Caixa', 'Volume'): "R$ {:,.2f}", ('Caixa', 'Rend. R$'): "R$ {:,.2f}", ('Caixa', '% Alocado'): "{:.2%}", ('Caixa', 'Rend. %'): "{:.2%}",
            ('Despesas', 'Total'): "R$ {:,.2f}",
            ('Resultado', 'Rend. Pré-Desp R$'): "R$ {:,.2f}", ('Resultado', 'Rend. Pós-Desp R$'): "R$ {:,.2f}",
            ('Resultado', 'Rend. Pré-Desp %'): "{:.2%}", ('Resultado', 'Rend. Pós-Desp %'): "{:.2%}"
        }, na_rep="-"))
        # Botão de download (pode ser melhorado para exportar o MultiIndex)
    
    with tab_dashboard:
        st.header("Dashboard de Performance")
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
        st.area_chart(df[['Ativos_Volume', 'Caixa_Volume']])

    with tab_dre:
        st.info("A aba de DRE será desenvolvida a seguir, consolidando os resultados mensais e anuais.")
