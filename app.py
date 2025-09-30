import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import date
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")

st.title("Análise de Viabilidade de Fundos de Investimento")

# --- NOVO: Lógica de Gerenciamento de Estado ---
# Inicializa o estado da simulação se ele não existir
if 'simulacao_rodada' not in st.session_state:
    st.session_state.simulacao_rodada = False

# Função para ser chamada quando o botão de projeção for clicado
def rodar_simulacao():
    st.session_state.simulacao_rodada = True

# --- 1. ENTRADA DE DADOS (SIDEBAR) ---
with st.sidebar:
    st.header("Parâmetros Gerais")
    nome_fundo = st.text_input("Nome do Fundo", "Fundo Imobiliário Exemplo")
    data_inicio = st.date_input("Data de Início", date(2024, 1, 1))
    duracao_anos = st.number_input("Duração (anos)", value=10, min_value=1, max_value=50)
    aporte_inicial = st.number_input("Aporte Inicial (R$)", value=10000000.0, step=100000.0)
    
    st.subheader("Curvas de Juros (% a.a.)")
    projecao_cdi = st.number_input("Projeção CDI", value=10.0, step=0.5)
    projecao_ipca = st.number_input("Projeção IPCA", value=4.5, step=0.25)

    st.subheader("Distribuição de Dividendos")
    calc_dividendos = st.toggle("Calcular Distribuição", value=True)
    if calc_dividendos:
        dist_percentual = st.number_input("Percentual do Lucro Caixa a Distribuir (%)", value=95.0, min_value=0.0, max_value=100.0)
        dist_frequencia = st.selectbox("Frequência da Distribuição", options=['Mensal', 'Semestral', 'Anual'], index=1)

    st.subheader("Taxa de Performance")
    calc_performance = st.toggle("Calcular Taxa de Performance", value=True)
    if calc_performance:
        perf_benchmark = st.selectbox("Benchmark da Performance", options=['CDI', 'IPCA'], index=0)
        perf_spread = st.number_input("Spread sobre Benchmark (% a.a.)", value=0.0, step=0.5)
        perf_percentual = st.number_input("Percentual da Performance (%)", value=20.0, step=1.0)
        perf_carencia = st.number_input("Carência (meses)", value=12, min_value=0)
        perf_periodo = st.selectbox("Período de Apuração", options=['Anual'], index=0)
        perf_hwm = st.checkbox("Com Linha d'Água (High-Water Mark)", value=True)

    st.subheader("Movimentações de Capital")
    if 'lista_aportes' not in st.session_state: st.session_state.lista_aportes = []
    if 'lista_amortizacoes' not in st.session_state: st.session_state.lista_amortizacoes = []
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Adicionar Aporte"): st.session_state.lista_aportes.append({'Mês': 12, 'Valor': 1000000.0})
    with col2:
        if st.button("Adicionar Amortização"): st.session_state.lista_amortizacoes.append({'Mês': 24, 'Valor': 500000.0})
    for i, aporte in enumerate(st.session_state.lista_aportes):
        with st.expander(f"Aporte {i+1}", expanded=True):
            aporte['Mês'] = st.number_input("Mês do Aporte", value=aporte['Mês'], min_value=1, max_value=duracao_anos*12, key=f"aporte_mes_{i}")
            aporte['Valor'] = st.number_input("Valor do Aporte (R$)", value=float(aporte['Valor']), step=100000.0, key=f"aporte_valor_{i}")
    for i, amort in enumerate(st.session_state.lista_amortizacoes):
        with st.expander(f"Amortização {i+1}", expanded=True):
            amort['Mês'] = st.number_input("Mês da Amortização", value=amort['Mês'], min_value=1, max_value=duracao_anos*12, key=f"amort_mes_{i}")
            amort['Valor'] = st.number_input("Valor da Amortização (R$)", value=float(amort['Valor']), step=100000.0, key=f"amort_valor_{i}")

    st.subheader("Despesas do Fundo")
    if 'lista_despesas' not in st.session_state: st.session_state.lista_despesas = [{'Nome': 'Taxa de Adm', 'Tipo': '% do PL', 'Valor': 0.2}]
    if st.button("Adicionar Despesa"): st.session_state.lista_despesas.append({'Nome': f"Despesa {len(st.session_state.lista_despesas) + 1}",'Tipo': 'Fixo Mensal','Valor': 10000.0})
    for i, despesa in enumerate(st.session_state.lista_despesas):
        with st.expander(f"Configurar {despesa['Nome']}", expanded=True):
            despesa['Nome'] = st.text_input("Nome", value=despesa['Nome'], key=f"desp_nome_{i}")
            despesa['Tipo'] = st.selectbox("Tipo de Cálculo", options=['% do PL', 'Fixo Mensal'], key=f"desp_tipo_{i}")
            if despesa['Tipo'] == '% do PL': despesa['Valor'] = st.number_input("Valor (% a.a.)", value=despesa.get('Valor', 0.2), step=0.05, key=f"desp_valor_pct_{i}")
            else: despesa['Valor'] = st.number_input("Valor (R$)", value=despesa.get('Valor', 10000.0), step=1000.0, key=f"desp_valor_brl_{i}")

    st.subheader("Modelagem de Ativos")
    if 'lista_ativos' not in st.session_state: st.session_state.lista_ativos = []
    if st.button("Adicionar Ativo Genérico"): st.session_state.lista_ativos.append({'Nome': f"Ativo {len(st.session_state.lista_ativos) + 1}",'Valor': 2000000.0,'Mês Investimento': 1,'Benchmark': 'IPCA','Spread': 7.0})
    for i, ativo in enumerate(st.session_state.lista_ativos):
        with st.expander(f"Configurar {ativo['Nome']}", expanded=True):
            ativo['Nome'] = st.text_input(f"Nome", value=ativo['Nome'], key=f"nome_{i}")
            ativo['Valor'] = st.number_input(f"Valor (R$)", value=float(ativo['Valor']), step=100000.0, key=f"valor_{i}")
            ativo['Mês Investimento'] = st.number_input(f"Mês Invest.", value=ativo['Mês Investimento'], min_value=1, max_value=duracao_anos*12, key=f"mes_{i}")
            ativo['Benchmark'] = st.selectbox(f"Benchmark", options=['IPCA', 'CDI'], index=0 if ativo['Benchmark'] == 'IPCA' else 1, key=f"bench_{i}")
            ativo['Spread'] = st.number_input(f"Spread (% a.a.)", value=ativo['Spread'], step=0.5, key=f"spread_{i}")
    
    st.markdown("---")
    # --- NOVO: Botão agora usa a função de callback ---
    st.button("Gerar Projeção", on_click=rodar_simulacao, type="primary")

# --- Estrutura de Abas ---
tab_fluxo, tab_dashboard, tab_dre = st.tabs(["Fluxo de Caixa Detalhado", "Dashboard & Indicadores", "DRE"])

# --- NOVO: Lógica de exibição agora depende do session_state ---
if not st.session_state.simulacao_rodada:
    with tab_fluxo:
        st.info("⬅️ Configure os parâmetros na barra lateral e clique em 'Gerar Projeção' para iniciar a análise.")
else:
    # --- 2. MOTOR DE CÁLCULO (sem alterações) ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    valor_individual_ativos = [0.0] * len(st.session_state.lista_ativos)
    high_water_mark = aporte_inicial
    pl_inicio_periodo_perf = aporte_inicial
    lucro_caixa_acumulado = 0.0
    lista_fluxos = []
    fluxo_mes_0 = {'Mês': 0, 'PL Início': 0, '(+) Aportes': aporte_inicial, '(-) Amortizações': 0, '(-) Dividendos': 0, 'Ativos_Volume': 0, 'Ativos_Rend_R$': 0, 'Caixa_Volume': aporte_inicial, 'Caixa_Rend_R$': 0, 'Total Despesas': 0, 'Rend. Pré-Desp_R$': 0, 'Rend. Pós-Desp_R$': 0, 'PL Final': aporte_inicial, '(-) Taxa de Performance': 0.0}
    for despesa in st.session_state.lista_despesas: fluxo_mes_0[f"(-) {despesa['Nome']}"] = 0
    lista_fluxos.append(fluxo_mes_0)
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        aporte_mes = sum(aporte['Valor'] for aporte in st.session_state.lista_aportes if aporte['Mês'] == mes)
        amortizacao_mes = sum(amort['Valor'] for amort in st.session_state.lista_amortizacoes if amort['Mês'] == mes)
        pl_inicio_mes = fluxo_anterior['PL Final']; caixa_inicio_mes = fluxo_anterior['Caixa_Volume']
        caixa_pos_aportes = caixa_inicio_mes + aporte_mes; pl_pos_aportes = pl_inicio_mes + aporte_mes
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
            if ativo['Mês Investimento'] == mes: valor_individual_ativos[i] += ativo['Valor']
        caixa_pos_investimento = caixa_pos_aportes - novos_investimentos_mes
        rend_caixa_mes = max(0, caixa_pos_investimento) * taxa_cdi_mensal
        total_despesas_regulares = 0; despesas_mes_dict = {}
        for despesa in st.session_state.lista_despesas:
            valor_despesa = pl_pos_aportes * (despesa['Valor'] / 100 / 12) if despesa['Tipo'] == '% do PL' else despesa['Valor']
            despesas_mes_dict[f"(-) {despesa['Nome']}"] = valor_despesa
            total_despesas_regulares += valor_despesa
        pl_pre_performance = pl_pos_aportes + (rend_ativos_mes + rend_caixa_mes) - total_despesas_regulares
        taxa_performance_mes = 0
        if calc_performance and mes > perf_carencia and (mes % 12 == 0 or mes == meses_total):
            pass
        total_despesas_mes = total_despesas_regulares + taxa_performance_mes
        rend_pos_desp = (rend_ativos_mes + rend_caixa_mes) - total_despesas_mes
        lucro_caixa_acumulado += rend_pos_desp
        dividendo_mes = 0
        if calc_dividendos:
            if dist_frequencia == 'Mensal': meses_frequencia = 1
            elif dist_frequencia == 'Semestral': meses_frequencia = 6
            else: meses_frequencia = 12
            if (mes % meses_frequencia == 0 or mes == meses_total):
                dividendo_mes = max(0, lucro_caixa_acumulado * (dist_percentual / 100.0))
                lucro_caixa_acumulado = 0
        caixa_final_mes = caixa_pos_investimento + rend_caixa_mes - total_despesas_mes - amortizacao_mes - dividendo_mes
        vol_ativos_final_mes = sum(valor_individual_ativos)
        pl_final_mes = vol_ativos_final_mes + caixa_final_mes
        fluxo_atual = {'Mês': mes, 'PL Início': pl_inicio_mes, '(+) Aportes': aporte_mes, '(-) Amortizações': amortizacao_mes, '(-) Dividendos': dividendo_mes, 'Ativos_Volume': vol_ativos_final_mes, 'Ativos_Rend_R$': rend_ativos_mes, 'Caixa_Volume': caixa_final_mes, 'Caixa_Rend_R$': rend_caixa_mes, 'Total Despesas': total_despesas_mes, 'Rend. Pré-Desp_R$': rend_ativos_mes + rend_caixa_mes, 'Rend. Pós-Desp_R$': rend_pos_desp, 'PL Final': pl_final_mes, '(-) Taxa de Performance': taxa_performance_mes}
        fluxo_atual.update(despesas_mes_dict)
        lista_fluxos.append(fluxo_atual)

    # --- 3. PÓS-PROCESSAMENTO E EXIBIÇÃO ---
    df = pd.DataFrame(lista_fluxos)
    if not df.empty:
        df.index = datas_projecao; df['Ano'] = df.index.year
        df.fillna(0, inplace=True); df.replace([float('inf'), -float('inf')], 0, inplace=True)
        df['Ativos_% Alocado'] = df['Ativos_Volume'] / df['PL Final'].where(df['PL Final'] != 0)
        df['Caixa_% Alocado'] = df['Caixa_Volume'] / df['PL Final'].where(df['PL Final'] != 0)
        df['Ativos_Rend_%'] = df['Ativos_Rend_R$'] / df['Ativos_Volume'].shift(1).where(df['Ativos_Volume'].shift(1) != 0)
        df['Caixa_Rend_%'] = df['Caixa_Rend_R$'] / df['Caixa_Volume'].shift(1).where(df['Caixa_Volume'].shift(1) != 0)
        df['Rend. Pré-Desp_%'] = df['Rend. Pré-Desp_R$'] / df['PL Início'].where(df['PL Início'] != 0)
        df['Rend. Pós-Desp_%'] = df['Rend. Pós-Desp_R$'] / df['PL Início'].where(df['PL Início'] != 0)
        df.fillna(0, inplace=True); df.replace([float('inf'), -float('inf')], 0, inplace=True)

    with tab_fluxo:
        st.header("Fluxo de Caixa Detalhado")
        col_map = {'Ano': ('Período', 'Ano'), 'Mês': ('Período', 'Mês'), 'PL Início': ('Geral', 'PL Início'), '(+) Aportes': ('Geral', '(+) Aportes'), '(-) Amortizações': ('Geral', '(-) Amortizações'), '(-) Dividendos': ('Geral', '(-) Dividendos'), 'PL Final': ('Geral', 'PL Final'), 'Ativos_% Alocado': ('Ativos', '% Alocado'), 'Ativos_Volume': ('Ativos', 'Volume'), 'Ativos_Rend_R$': ('Ativos', 'Rend R$'), 'Ativos_Rend_%': ('Ativos', 'Rend %'), 'Caixa_% Alocado': ('Caixa', '% Alocado'), 'Caixa_Volume': ('Caixa', 'Volume'), 'Caixa_Rend_R$': ('Caixa', 'Rend R$'), 'Caixa_Rend_%': ('Caixa', 'Rend %'), 'Total Despesas': ('Despesas', 'Total'), '(-) Taxa de Performance': ('Despesas', 'Performance'), 'Rend. Pré-Desp_R$': ('Resultado', 'Rend Pré-Desp R$'), 'Rend. Pré-Desp_%': ('Resultado', 'Rend Pré-Desp %'), 'Rend. Pós-Desp_R$': ('Resultado', 'Rend Pós-Desp R$'), 'Rend. Pós-Desp_%': ('Resultado', 'Rend Pós-Desp %')}
        for desp in st.session_state.lista_despesas: col_map[f"(-) {desp['Nome']}"] = ('Despesas', f"(-) {desp['Nome']}")
        df_display = df.rename(columns=col_map)
        ordem_final = [col for col in col_map.values() if col in df_display.columns]
        df_display.columns = pd.MultiIndex.from_tuples(df_display.columns); df_display = df_display[ordem_final]
        st.dataframe(df_display.style.format({('Geral', 'PL Início'): "R$ {:,.2f}", ('Geral', '(+) Aportes'): "R$ {:,.2f}", ('Geral', '(-) Amortizações'): "R$ {:,.2f}", ('Geral', '(-) Dividendos'): "R$ {:,.2f}", ('Geral', 'PL Final'): "R$ {:,.2f}",('Ativos', 'Volume'): "R$ {:,.2f}", ('Ativos', 'Rend R$'): "R$ {:,.2f}", ('Ativos', '% Alocado'): "{:.2%}", ('Ativos', 'Rend %'): "{:.2%}",('Caixa', 'Volume'): "R$ {:,.2f}", ('Caixa', 'Rend R$'): "R$ {:,.2f}", ('Caixa', '% Alocado'): "{:.2%}", ('Caixa', 'Rend %'): "{:.2%}",('Despesas', 'Total'): "R$ {:,.2f}", ('Despesas', 'Performance'): "R$ {:,.2f}",('Resultado', 'Rend Pré-Desp R$'): "R$ {:,.2f}", ('Resultado', 'Rend Pós-Desp R$'): "R$ {:,.2f}",('Resultado', 'Rend Pré-Desp %'): "{:.2%}", ('Resultado', 'Rend Pós-Desp %'): "{:.2%}"} | {('Despesas', f"(-) {d['Nome']}"): "R$ {:,.2f}" for d in st.session_state.lista_despesas}, na_rep="-"))

    with tab_dashboard:
        st.header("Análise do Investidor")
        if not df.empty:
            total_distribuido = df['(-) Amortizações'] + df['(-) Dividendos']
            fluxo_investidor_bruto = pd.Series([-(df['(+) Aportes'].iloc[0])] + (total_distribuido - df['(+) Aportes']).iloc[1:].tolist())
            fluxo_investidor_final = fluxo_investidor_bruto.copy()
            fluxo_investidor_final.iloc[-1] += df['PL Final'].iloc[-1]
            try: tir_anual = (1 + npf.irr(fluxo_investidor_final))**12 - 1
            except: tir_anual = float('nan')
            total_investido = df['(+) Aportes'].sum()
            total_retornado_caixa = total_distribuido.sum()
            total_retornado_final = total_retornado_caixa + df['PL Final'].iloc[-1]
            moic = total_retornado_final / total_investido if total_investido != 0 else 0
            dpi = total_retornado_caixa / total_investido if total_investido != 0 else 0
            rvpi = df['PL Final'].iloc[-1] / total_investido if total_investido != 0 else 0
            fluxo_investidor_acumulado = fluxo_investidor_bruto.cumsum()
            payback_mes = (fluxo_investidor_acumulado >= 0).idxmax() if (fluxo_investidor_acumulado >= 0).any() else "Não atinge"
            st.subheader("Indicadores de Performance")
            cols = st.columns(5)
            cols[0].metric("TIR Anualizada", f"{tir_anual:.2%}" if not pd.isna(tir_anual) else "N/A")
            cols[1].metric("MOIC (Total)", f"{moic:.2f}x", help="Múltiplo Total = (Distribuído + PL Final) / Investido")
            cols[2].metric("DPI (Distribuído)", f"{dpi:.2f}x", help="Múltiplo do Retorno em Caixa = Distribuído / Investido")
            cols[3].metric("RVPI (Residual)", f"{rvpi:.2f}x", help="Múltiplo do Valor Residual = PL Final / Investido")
            cols[4].metric("Payback (meses)", f"{payback_mes}")
            st.markdown("---")
            st.subheader("Fluxo de Caixa do Investidor")
            df_fluxo_investidor = pd.DataFrame({'Investimento': -df['(+) Aportes'].clip(upper=0), 'Distribuições': total_distribuido.clip(lower=0)})
            df_fluxo_investidor.index = df.index
            st.bar_chart(df_fluxo_investidor)
            st.subheader("Distribuição de Dividendos ao Longo do Tempo")
            st.bar_chart(df['(-) Dividendos'])
            st.markdown("---")
            st.subheader("Análise do Fundo")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Evolução do Patrimônio Líquido**")
                st.line_chart(df['PL Final'])
            with col2:
                st.write("**Composição do Patrimônio**")
                st.area_chart(df[['Ativos_Volume', 'Caixa_Volume']].rename(columns={'Ativos_Volume': 'Ativos', 'Caixa_Volume': 'Caixa'}))

    with tab_dre:
        st.header("Demonstração de Resultados (DRE)")
        if not df.empty and df['Ano'].nunique() > 0:
            df_anual = df.groupby('Ano').sum()
            dre_data = []
            index_dre = []
            for ano in df_anual.index:
                if ano == df['Ano'].min(): continue
                receita_ativos = df_anual.loc[ano, 'Ativos_Rend_R$']
                receita_caixa = df_anual.loc[ano, 'Caixa_Rend_R$']
                receita_bruta = receita_ativos + receita_caixa
                despesas_anual = {}
                for desp in st.session_state.lista_despesas:
                    despesas_anual[f"(-) {desp['Nome']}"] = df_anual.loc[ano, f"(-) {desp['Nome']}"]
                taxa_perf = df_anual.loc[ano, '(-) Taxa de Performance']
                total_despesas = df_anual.loc[ano, 'Total Despesas']
                resultado_operacional = receita_bruta - total_despesas
                dividendos = df_anual.loc[ano, '(-) Dividendos']
                resultado_liquido = resultado_operacional - dividendos
                if not dre_data:
                    index_dre.extend(["(+) Receita de Ativos", "(+) Receita de Caixa", "(=) Receita Bruta", "--- Despesas ---"])
                    for nome_despesa in despesas_anual.keys(): index_dre.append(nome_despesa)
                    index_dre.extend(["(-) Taxa de Performance", "(=) Total Despesas", "(=) Resultado Operacional (Lucro Caixa)", "(-) Dividendos Distribuídos", "(=) Resultado Líquido Retido"])
                coluna_ano = [receita_ativos, receita_caixa, receita_bruta, None]
                coluna_ano.extend(list(despesas_anual.values()))
                coluna_ano.extend([taxa_perf, total_despesas, resultado_operacional, dividendos, resultado_liquido])
                dre_data.append(coluna_ano)

            if dre_data:
                df_dre_vertical = pd.DataFrame(dre_data, columns=index_dre)
                df_dre_vertical.index = [ano for ano in df_anual.index if ano != df['Ano'].min()]
                st.subheader("DRE Anual Detalhada")
                st.dataframe(df_dre_vertical.T.style.format("R$ {:,.2f}", na_rep="-"))
                st.subheader("Análise Visual do Resultado (Gráfico de Cascata)")
                ano_selecionado = st.selectbox("Selecione o Ano para Análise", options=df_dre_vertical.index)
                if ano_selecionado:
                    dados_cascata = df_dre_vertical.loc[ano_selecionado]
                    text_values = [f"R$ {v:,.0f}" if v is not None else "" for v in dados_cascata]
                    fig = go.Figure(go.Waterfall(name = str(ano_selecionado), orientation = "v", measure = ["relative", "relative", "total", "relative"] + ["relative"] * (len(st.session_state.lista_despesas) + 1) + ["total", "relative", "relative", "total"], x = index_dre, y = dados_cascata, text = text_values, connector = {"line":{"color":"rgb(63, 63, 63)"}},))
                    fig.update_layout(title=f"Composição do Resultado - {ano_selecionado}", showlegend=True)
                    st.plotly_chart(fig, use_container_width=True)
