import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import date
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")

st.title("Análise de Viabilidade de Fundos de Investimento")

# --- Lógica de Gerenciamento de Estado ---
if 'simulacao_rodada' not in st.session_state:
    st.session_state.simulacao_rodada = False
def rodar_simulacao():
    st.session_state.simulacao_rodada = True

# --- PAINEL DE CONFIGURAÇÕES ---
with st.expander("Painel de Configurações da Simulação", expanded=True):
    tab_geral, tab_capital, tab_ativos, tab_despesas, tab_distribuicao = st.tabs([
        "Geral & Curvas", "Movimentações de Capital", "Modelagem de Ativos", 
        "Despesas", "Performance & Dividendos"
    ])

    with tab_geral:
        st.header("Parâmetros Gerais do Fundo")
        col1, col2, col3, col4 = st.columns(4)
        with col1: nome_fundo = st.text_input("Nome do Fundo", "Fundo Imobiliário Exemplo")
        with col2: data_inicio = st.date_input("Data de Início", date(2024, 1, 1))
        with col3: duracao_anos = st.number_input("Duração (anos)", value=10, min_value=1, max_value=50)
        with col4: aporte_inicial = st.number_input("Aporte Inicial (R$)", value=10000000.0, step=100000.0)
        st.header("Curvas de Juros (% a.a.)")
        col1, col2 = st.columns(2)
        with col1: projecao_cdi = st.number_input("Projeção CDI", value=10.0, step=0.5)
        with col2: projecao_ipca = st.number_input("Projeção IPCA", value=4.5, step=0.25)

    with tab_capital:
        st.header("Aportes e Amortizações Adicionais")
        if 'lista_aportes' not in st.session_state: st.session_state.lista_aportes = []
        if 'lista_amortizacoes' not in st.session_state: st.session_state.lista_amortizacoes = []
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Adicionar Aporte"): st.session_state.lista_aportes.append({'Mês': 12, 'Valor': 1000000.0})
            for i, aporte in enumerate(st.session_state.lista_aportes):
                st.markdown(f"**Aporte {i+1}**")
                aporte['Mês'] = st.number_input("Mês", value=aporte['Mês'], min_value=1, max_value=duracao_anos*12, key=f"aporte_mes_{i}")
                aporte['Valor'] = st.number_input("Valor (R$)", value=float(aporte['Valor']), step=100000.0, key=f"aporte_valor_{i}")
        with col2:
            if st.button("Adicionar Amortização"): st.session_state.lista_amortizacoes.append({'Mês': 24, 'Valor': 500000.0})
            for i, amort in enumerate(st.session_state.lista_amortizacoes):
                st.markdown(f"**Amortização {i+1}**")
                amort['Mês'] = st.number_input("Mês", value=amort['Mês'], min_value=1, max_value=duracao_anos*12, key=f"amort_mes_{i}")
                amort['Valor'] = st.number_input("Valor (R$)", value=float(amort['Valor']), step=100000.0, key=f"amort_valor_{i}")
    
    with tab_ativos:
        st.header("Modelagem de Ativos do Fundo")
        if 'lista_ativos' not in st.session_state: st.session_state.lista_ativos = []
        tipo_ativo_novo = st.selectbox("Selecione o tipo de ativo para adicionar:", ["Imobiliário - Renda", "CRI / CCI", "Genérico"])
        if st.button(f"Adicionar {tipo_ativo_novo}"):
            novo_ativo = {'tipo': tipo_ativo_novo}
            if tipo_ativo_novo == "Imobiliário - Renda":
                novo_ativo.update({'Nome': f"Imóvel {len(st.session_state.lista_ativos) + 1}", 'Valor Compra': 5000000.0, 'Mês Compra': 1, 'Receita Aluguel': 40000.0, 'Vacancia': 5.0, 'Indice Reajuste': 'IPCA', 'Custos Mensais': 2000.0, 'Cap Rate Saida': 7.0})
            elif tipo_ativo_novo == "CRI / CCI":
                novo_ativo.update({'Nome': f"CRI {len(st.session_state.lista_ativos) + 1}", 'Principal': 3000000.0, 'Mês Investimento': 1, 'Benchmark': 'IPCA', 'Tipo Taxa': 'Spread', 'Taxa': 6.0, 'Prazo': 120, 'Amortizacao': 'Price', 'Carencia': 0, 'Tranche': 'Sênior', 'Perda': 0.0})
            else: novo_ativo.update({'Nome': f"Ativo Genérico {len(st.session_state.lista_ativos) + 1}", 'Valor': 2000000.0, 'Mês Investimento': 1, 'Benchmark': 'IPCA', 'Spread': 7.0})
            st.session_state.lista_ativos.append(novo_ativo)
        st.markdown("---")
        cols = st.columns(len(st.session_state.lista_ativos)) if st.session_state.lista_ativos else []
        for i, ativo in enumerate(st.session_state.lista_ativos):
            with cols[i]:
                st.markdown(f"**{ativo.get('Nome')}**"); ativo['Nome'] = st.text_input("Nome", value=ativo.get('Nome', ''), key=f"nome_{i}", label_visibility="collapsed")
                tipo_ativo_atual = ativo.get('tipo')
                if tipo_ativo_atual == "Imobiliário - Renda":
                    st.write("Parâmetros do Imóvel:")
                    ativo['Valor Compra'] = st.number_input("Valor de Compra (R$)", value=ativo.get('Valor Compra', 0.0), key=f"val_compra_{i}")
                    ativo['Mês Compra'] = st.number_input("Mês da Compra", value=ativo.get('Mês Compra', 1), key=f"mes_compra_{i}")
                    ativo['Receita Aluguel'] = st.number_input("Aluguel Mensal (R$)", value=ativo.get('Receita Aluguel', 0.0), key=f"aluguel_{i}")
                    ativo['Vacancia'] = st.number_input("Vacância (%)", value=ativo.get('Vacancia', 0.0), key=f"vacancia_{i}")
                    ativo['Indice Reajuste'] = st.selectbox("Índice de Reajuste Anual", options=['IPCA', 'IGP-M'], key=f"indice_{i}")
                    st.write("Custos e Saída:")
                    ativo['Custos Mensais'] = st.number_input("Custos Fixos Mensais (R$)", value=ativo.get('Custos Mensais', 0.0), key=f"custos_fixos_{i}")
                    ativo['Cap Rate Saida'] = st.number_input("Cap Rate de Saída (%)", value=ativo.get('Cap Rate Saida', 0.0), key=f"cap_rate_{i}")
                elif tipo_ativo_atual == "CRI / CCI":
                    st.write("Parâmetros do Título:")
                    ativo['Principal'] = st.number_input("Principal (R$)", value=ativo.get('Principal', 0.0), key=f"principal_{i}")
                    ativo['Mês Investimento'] = st.number_input("Mês do Invest.", value=ativo.get('Mês Investimento', 1), key=f"mes_invest_cri_{i}")
                    ativo['Prazo'] = st.number_input("Prazo (meses)", value=ativo.get('Prazo', 1), key=f"prazo_{i}")
                    ativo['Benchmark'] = st.selectbox("Benchmark", options=['IPCA', 'CDI', 'Pré-fixado'], key=f"bench_cri_{i}")
                    ativo['Tipo Taxa'] = st.selectbox("Tipo de Taxa", options=['Spread', '% do Benchmark'], key=f"tipo_taxa_cri_{i}")
                    ativo['Taxa'] = st.number_input("Taxa", value=ativo.get('Taxa', 0.0), key=f"taxa_cri_{i}")
                    ativo['Amortizacao'] = st.selectbox("Amortização", options=['SAC', 'Price', 'Bullet'], key=f"amort_cri_{i}")
                    ativo['Carencia'] = st.number_input("Carência de Amort. (meses)", value=ativo.get('Carencia', 0), key=f"carencia_cri_{i}")
                    ativo['Tranche'] = st.selectbox("Série (Tranche)", options=['Sênior', 'Subordinada'], key=f"tranche_cri_{i}")
                    ativo['Perda'] = st.number_input("Perda Esperada (% a.a.)", value=ativo.get('Perda', 0.0), key=f"perda_cri_{i}")
                else: 
                    st.write("Parâmetros do Ativo Genérico:")
                    ativo['Valor'] = st.number_input(f"Valor (R$)", value=float(ativo.get('Valor', 0.0)), step=100000.0, key=f"valor_{i}")
                    ativo['Mês Investimento'] = st.number_input(f"Mês Invest.", value=ativo.get('Mês Investimento', 1), min_value=1, max_value=duracao_anos*12, key=f"mes_{i}")
                    ativo['Benchmark'] = st.selectbox(f"Benchmark", options=['IPCA', 'CDI'], index=0 if ativo.get('Benchmark', 'IPCA') == 'IPCA' else 1, key=f"bench_{i}")
                    ativo['Spread'] = st.number_input(f"Spread (% a.a.)", value=ativo.get('Spread', 0.0), step=0.5, key=f"spread_{i}")
    
    with tab_despesas:
        st.header("Despesas Recorrentes do Fundo")
        if 'lista_despesas' not in st.session_state: st.session_state.lista_despesas = [{'Nome': 'Taxa de Adm', 'Tipo': '% do PL', 'Valor': 0.2}]
        if st.button("Adicionar Despesa"): st.session_state.lista_despesas.append({'Nome': f"Despesa {len(st.session_state.lista_despesas) + 1}",'Tipo': 'Fixo Mensal','Valor': 10000.0})
        cols = st.columns(len(st.session_state.lista_despesas)) if st.session_state.lista_despesas else []
        for i, despesa in enumerate(st.session_state.lista_despesas):
            with cols[i]:
                st.markdown(f"**{despesa.get('Nome', f'Despesa {i+1}')}**"); despesa['Nome'] = st.text_input("Nome", value=despesa['Nome'], key=f"desp_nome_{i}", label_visibility="collapsed")
                despesa['Tipo'] = st.selectbox("Tipo de Cálculo", options=['% do PL', 'Fixo Mensal'], key=f"desp_tipo_{i}")
                if despesa['Tipo'] == '% do PL': despesa['Valor'] = st.number_input("Valor (% a.a.)", value=despesa.get('Valor', 0.2), step=0.05, key=f"desp_valor_pct_{i}")
                else: despesa['Valor'] = st.number_input("Valor (R$)", value=despesa.get('Valor', 10000.0), step=1000.0, key=f"desp_valor_brl_{i}")
    
    with tab_distribuicao:
        col1, col2 = st.columns(2)
        with col1:
            st.header("Distribuição de Dividendos"); calc_dividendos = st.toggle("Calcular Distribuição", value=True)
            if calc_dividendos:
                dist_percentual = st.number_input("Percentual do Lucro Caixa a Distribuir (%)", value=95.0, min_value=0.0, max_value=100.0)
                dist_frequencia = st.selectbox("Frequência da Distribuição", options=['Mensal', 'Semestral', 'Anual'], index=1)
        with col2:
            st.header("Taxa de Performance"); calc_performance = st.toggle("Calcular Taxa de Performance", value=True)
            if calc_performance:
                perf_benchmark = st.selectbox("Benchmark da Performance", options=['CDI', 'IPCA'], index=0)
                perf_spread = st.number_input("Spread sobre Benchmark (% a.a.)", value=0.0, step=0.5)
                perf_percentual = st.number_input("Percentual da Performance (%)", value=20.0, step=1.0)
                perf_carencia = st.number_input("Carência (meses)", value=12, min_value=0)
                perf_periodo = st.selectbox("Período de Apuração", options=['Anual'], index=0)
                perf_hwm = st.checkbox("Com Linha d'Água (High-Water Mark)", value=True)

    st.markdown("---")
    st.button("Gerar Projeção", on_click=rodar_simulacao, type="primary", use_container_width=True)

# --- Abas de RESULTADO ---
tab_fluxo, tab_dashboard, tab_dre = st.tabs(["Fluxo de Caixa Detalhado", "Dashboard & Indicadores", "DRE"])

if not st.session_state.simulacao_rodada:
    with tab_fluxo:
        st.info("⬆️ Configure os parâmetros no painel acima e clique em 'Gerar Projeção' para iniciar a análise.")
else:
    # --- 2. MOTOR DE CÁLCULO (ATUALIZADO PARA DETALHAMENTO) ---
    taxa_cdi_mensal = (1 + projecao_cdi / 100)**(1/12) - 1
    taxa_ipca_mensal = (1 + projecao_ipca / 100)**(1/12) - 1
    taxa_igpm_mensal = taxa_ipca_mensal
    meses_total = duracao_anos * 12
    datas_projecao = pd.to_datetime([data_inicio + relativedelta(months=i) for i in range(meses_total + 1)])
    
    valor_individual_ativos = [0.0] * len(st.session_state.lista_ativos)
    aluguel_atual_imoveis = [0.0] * len(st.session_state.lista_ativos)
    saldo_devedor_cris = [0.0] * len(st.session_state.lista_ativos)
    pmt_cris = [0.0] * len(st.session_state.lista_ativos)

    high_water_mark = aporte_inicial
    pl_inicio_periodo_perf = aporte_inicial
    lucro_caixa_acumulado = 0.0
    lista_fluxos = []
    
    fluxo_mes_0 = {'Mês': 0, 'PL Início': 0, '(+) Aportes': aporte_inicial, '(-) Amortizações': 0, '(-) Dividendos': 0, 'Caixa_Volume': aporte_inicial, 'Caixa_Rend_R$': 0, 'Total Despesas': 0, 'PL Final': aporte_inicial, '(-) Taxa de Performance': 0.0, '(-) Perdas em Ativos': 0.0}
    for i, ativo in enumerate(st.session_state.lista_ativos):
        fluxo_mes_0[f'Ativo_{i+1}_Volume'] = 0.0
        fluxo_mes_0[f'Ativo_{i+1}_Rend_R$'] = 0.0
    for despesa in st.session_state.lista_despesas: fluxo_mes_0[f"(-) {despesa['Nome']}"] = 0
    lista_fluxos.append(fluxo_mes_0)
    
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        aporte_mes = sum(a['Valor'] for a in st.session_state.lista_aportes if a['Mês'] == mes)
        amortizacao_mes = sum(a['Valor'] for a in st.session_state.lista_amortizacoes if a['Mês'] == mes)
        pl_inicio_mes = fluxo_anterior['PL Final']; caixa_inicio_mes = fluxo_anterior['Caixa_Volume']
        caixa_pos_aportes = caixa_inicio_mes + aporte_mes; pl_pos_aportes = pl_inicio_mes + aporte_mes
        novos_investimentos_mes = 0; perdas_mes = 0

        fluxo_atual_ativos = {}
        rend_total_ativos_mes = 0

        for i, ativo in enumerate(st.session_state.lista_ativos):
            rend_ativo_i = 0
            tipo_ativo = ativo.get('tipo')
            
            if tipo_ativo == "CRI / CCI":
                if mes >= ativo['Mês Investimento'] and saldo_devedor_cris[i] > 0:
                    perda_mensal = saldo_devedor_cris[i] * ((1 + ativo.get('Perda', 0.0) / 100.0)**(1/12) - 1)
                    perdas_mes += perda_mensal
                    
                    if ativo['Benchmark'] == 'Pré-fixado': taxa_rem_anual = ativo['Taxa'] / 100.0
                    else: taxa_bench_anual = projecao_ipca/100 if ativo['Benchmark'] == 'IPCA' else projecao_cdi/100
                    if ativo['Tipo Taxa'] == 'Spread': taxa_rem_anual = (1+taxa_bench_anual)*(1+ativo['Taxa']/100)-1
                    else: taxa_rem_anual = taxa_bench_anual * (ativo['Taxa']/100)
                    taxa_mensal = (1 + taxa_rem_anual)**(1/12) - 1
                    
                    juros_mes = saldo_devedor_cris[i] * taxa_mensal
                    amort_mes = 0
                    if mes > ativo['Mês Investimento'] + ativo['Carencia']:
                        if ativo['Amortizacao'] == 'SAC': amort_mes = ativo['Principal']/(ativo['Prazo']-ativo['Carencia'])
                        elif ativo['Amortizacao'] == 'Price': amort_mes = pmt_cris[i] - juros_mes
                        elif ativo['Amortizacao'] == 'Bullet' and (mes - ativo['Mês Investimento']) == ativo['Prazo'] -1: amort_mes = saldo_devedor_cris[i]
                    
                    amort_mes = min(amort_mes, saldo_devedor_cris[i])
                    perda_realizada = min(perda_mensal, saldo_devedor_cris[i] - amort_mes)
                    if ativo['Tranche'] == 'Subordinada':
                        saldo_devedor_cris[i] -= perda_realizada
                    
                    saldo_devedor_cris[i] -= amort_mes
                    rend_ativo_i = juros_mes + amort_mes
                    valor_individual_ativos[i] = saldo_devedor_cris[i]

            elif tipo_ativo == "Imobiliário - Renda":
                if mes >= ativo['Mês Compra']:
                    if (mes - ativo['Mês Compra']) % 12 == 0 and mes > ativo['Mês Compra']:
                        indice_reajuste = taxa_ipca_mensal if ativo['Indice Reajuste'] == 'IPCA' else taxa_igpm_mensal
                        aluguel_atual_imoveis[i] *= (1 + indice_reajuste * 12)
                    receita_bruta_imovel = aluguel_atual_imoveis[i]
                    receita_liquida_imovel = receita_bruta_imovel * (1 - ativo['Vacancia'] / 100.0)
                    custos_imovel = ativo['Custos Mensais'] + (receita_bruta_imovel * (ativo.get('Outros Custos % Receita', 0) / 100.0))
                    rend_ativo_i = receita_liquida_imovel - custos_imovel
                    valor_individual_ativos[i] += rend_ativo_i
                if mes == meses_total:
                    noi_anual = (aluguel_atual_imoveis[i] * (1 - ativo['Vacancia'] / 100.0) - ativo['Custos Mensais']) * 12
                    valor_venda = noi_anual / (ativo['Cap Rate Saida'] / 100.0) if ativo['Cap Rate Saida'] > 0 else 0
                    rend_ativo_i += valor_venda
                    valor_individual_ativos[i] = 0
            else:
                if valor_individual_ativos[i] > 0:
                    spread_mensal = (1 + ativo.get('Spread', 0) / 100)**(1/12) - 1
                    taxa_ativo = (1 + (taxa_cdi_mensal if ativo.get('Benchmark') == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                    rend_ativo_i = valor_individual_ativos[i] * taxa_ativo
                    valor_individual_ativos[i] += rend_ativo_i

            if tipo_ativo == "Imobiliário - Renda": mes_inv, val_inv = ativo.get('Mês Compra'), ativo.get('Valor Compra')
            elif tipo_ativo == "CRI / CCI": mes_inv, val_inv = ativo.get('Mês Investimento'), ativo.get('Principal')
            else: mes_inv, val_inv = ativo.get('Mês Investimento'), ativo.get('Valor')
            if mes == mes_inv:
                novos_investimentos_mes += val_inv
                if tipo_ativo == "CRI / CCI":
                    saldo_devedor_cris[i] = val_inv; valor_individual_ativos[i] = val_inv
                    if ativo['Amortizacao'] == 'Price':
                        if ativo['Benchmark'] == 'Pré-fixado': taxa_anual = ativo['Taxa'] / 100.0
                        else: taxa_bench = projecao_ipca/100 if ativo['Benchmark'] == 'IPCA' else projecao_cdi/100
                        if ativo['Tipo Taxa'] == 'Spread': taxa_anual = (1+taxa_bench)*(1+ativo['Taxa']/100)-1
                        else: taxa_anual = taxa_bench * (ativo['Taxa']/100)
                        taxa_m = (1+taxa_anual)**(1/12)-1; nper = ativo['Prazo'] - ativo['Carencia']
                        if taxa_m > 0 and nper > 0: pmt_cris[i] = npf.pmt(taxa_m, nper, -val_inv)
                elif tipo_ativo == "Imobiliário - Renda":
                    valor_individual_ativos[i] = val_inv; aluguel_atual_imoveis[i] = ativo['Receita Aluguel']
                else: valor_individual_ativos[i] += val_inv
            
            fluxo_atual_ativos[f'Ativo_{i+1}_Volume'] = valor_individual_ativos[i]
            fluxo_atual_ativos[f'Ativo_{i+1}_Rend_R$'] = rend_ativo_i
            rend_total_ativos_mes += rend_ativo_i

        caixa_pos_investimento = caixa_pos_aportes - novos_investimentos_mes
        rend_caixa_mes = max(0, caixa_pos_investimento) * taxa_cdi_mensal
        
        total_despesas_regulares = 0; despesas_mes_dict = {}
        for despesa in st.session_state.lista_despesas:
            valor_despesa = pl_pos_aportes * (despesa['Valor'] / 100 / 12) if despesa['Tipo'] == '% do PL' else despesa['Valor']
            despesas_mes_dict[f"(-) {despesa['Nome']}"] = valor_despesa
            total_despesas_regulares += valor_despesa
        pl_pre_performance = pl_pos_aportes + rend_total_ativos_mes + rend_caixa_mes - total_despesas_regulares - perdas_mes
        taxa_performance_mes = 0
        total_despesas_mes = total_despesas_regulares + taxa_performance_mes
        rend_pos_desp = rend_total_ativos_mes + rend_caixa_mes - total_despesas_mes
        lucro_caixa_acumulado += (rend_pos_desp - perdas_mes)
        dividendo_mes = 0
        if calc_dividendos:
            if dist_frequencia == 'Mensal': meses_frequencia = 1
            elif dist_frequencia == 'Semestral': meses_frequencia = 6
            else: meses_frequencia = 12
            if (mes % meses_frequencia == 0 or mes == meses_total):
                dividendo_mes = max(0, lucro_caixa_acumulado * (dist_percentual / 100.0)); lucro_caixa_acumulado = 0
        caixa_final_mes = caixa_pos_investimento + rend_caixa_mes - total_despesas_mes - amortizacao_mes - dividendo_mes
        vol_ativos_final_mes = sum(valor_individual_ativos)
        pl_final_mes = vol_ativos_final_mes + caixa_final_mes
        
        fluxo_atual = {'Mês': mes, 'PL Início': pl_inicio_mes, '(+) Aportes': aporte_mes, '(-) Amortizações': amortizacao_mes, '(-) Dividendos': dividendo_mes, 'Caixa_Volume': caixa_final_mes, 'Caixa_Rend_R$': rend_caixa_mes, 'Total Despesas': total_despesas_mes, 'PL Final': pl_final_mes, '(-) Taxa de Performance': taxa_performance_mes, '(-) Perdas em Ativos': perdas_mes}
        fluxo_atual.update(fluxo_atual_ativos)
        fluxo_atual.update(despesas_mes_dict)
        lista_fluxos.append(fluxo_atual)

    df = pd.DataFrame(lista_fluxos)
    if not df.empty:
        df.index = datas_projecao; df['Ano'] = df.index.year
        df['Ativos_Volume'] = sum(df[f'Ativo_{i+1}_Volume'] for i, ativo in enumerate(st.session_state.lista_ativos))
        df['Ativos_Rend_R$'] = sum(df[f'Ativo_{i+1}_Rend_R$'] for i, ativo in enumerate(st.session_state.lista_ativos))
        df['Rend. Pré-Desp_R$'] = df['Ativos_Rend_R$'] + df['Caixa_Rend_R$']
        df['Rend. Pós-Desp_R$'] = df['Rend. Pré-Desp_R$'] - df['Total Despesas']
        df.fillna(0, inplace=True); df.replace([float('inf'), -float('inf')], 0, inplace=True)
        df['Ativos_% Alocado'] = df['Ativos_Volume'] / df['PL Final'].where(df['PL Final'] != 0)
        df['Caixa_% Alocado'] = df['Caixa_Volume'] / df['PL Final'].where(df['PL Final'] != 0)
        df.fillna(0, inplace=True); df.replace([float('inf'), -float('inf')], 0, inplace=True)

    with tab_fluxo:
        st.header("Fluxo de Caixa Detalhado")
        col_map = {'Ano': ('Período', 'Ano'), 'Mês': ('Período', 'Mês'), 'PL Início': ('Geral', 'PL Início'), '(+) Aportes': ('Geral', '(+) Aportes'), '(-) Amortizações': ('Geral', '(-) Amortizações'), '(-) Dividendos': ('Geral', '(-) Dividendos'), 'PL Final': ('Geral', 'PL Final'), 'Caixa_Volume': ('Caixa', 'Volume'), 'Caixa_Rend_R$': ('Caixa', 'Rend R$')}
        for i, ativo in enumerate(st.session_state.lista_ativos):
            nome_amigavel = ativo.get('Nome', f'Ativo {i+1}').replace(" ", "_")
            col_map[f'Ativo_{i+1}_Volume'] = (f'Ativo: {nome_amigavel}', 'Volume')
            col_map[f'Ativo_{i+1}_Rend_R$'] = (f'Ativo: {nome_amigavel}', 'Rend R$')
        col_map_resto = {'Total Despesas': ('Despesas', 'Total'), '(-) Taxa de Performance': ('Despesas', 'Performance'), '(-) Perdas em Ativos': ('Resultado', '(-) Perdas')}
        for desp in st.session_state.lista_despesas: col_map[f"(-) {desp['Nome']}"] = ('Despesas', f"(-) {desp['Nome']}")
        col_map.update(col_map_resto)
        
        df_display = df.rename(columns=col_map)
        ordem_final = [col for col in df.columns if col in col_map]
        df_display_final = pd.DataFrame()
        for col in ordem_final:
            df_display_final[col_map[col]] = df_display[col_map[col]]

        df_display_final.columns = pd.MultiIndex.from_tuples(df_display_final.columns)
        st.dataframe(df_display_final.style.format("R$ {:,.0f}", na_rep="-"))

    with tab_dashboard:
        st.header("Análise do Investidor")
        if not df.empty:
            df_investidor = pd.DataFrame(index=df.index)
            df_investidor['Investimento'] = df['(+) Aportes'] * -1
            df_investidor['Distribuições'] = df['(-) Amortizações'] + df['(-) Dividendos']
            
            fluxo_investidor_final = df_investidor['Investimento'] + df_investidor['Distribuições']
            fluxo_investidor_final.iloc[-1] += df['PL Final'].iloc[-1]
            try: tir_anual = (1 + npf.irr(fluxo_investidor_final))**12 - 1
            except: tir_anual = float('nan')
            
            total_investido = df['(+) Aportes'].sum()
            total_retornado_caixa = df_investidor['Distribuições'].sum()
            total_retornado_final = total_retornado_caixa + df['PL Final'].iloc[-1]
            moic = total_retornado_final / total_investido if total_investido != 0 else 0
            dpi = total_retornado_caixa / total_investido if total_investido != 0 else 0
            rvpi = df['PL Final'].iloc[-1] / total_investido if total_investido != 0 else 0
            fluxo_acumulado = (df_investidor['Investimento'] + df_investidor['Distribuições']).cumsum()
            payback_mes = (fluxo_acumulado >= 0).idxmax().month if (fluxo_acumulado >= 0).any() else "Não atinge"

            st.subheader("Indicadores de Performance")
            cols = st.columns(5)
            cols[0].metric("TIR Anualizada", f"{tir_anual:.2%}" if not pd.isna(tir_anual) else "N/A")
            cols[1].metric("MOIC (Total)", f"{moic:.2f}x", help="Múltiplo Total = (Distribuído + PL Final) / Investido")
            cols[2].metric("DPI (Distribuído)", f"{dpi:.2f}x", help="Múltiplo do Retorno em Caixa = Distribuído / Investido")
            cols[3].metric("RVPI (Residual)", f"{rvpi:.2f}x", help="Múltiplo do Valor Residual = PL Final / Investido")
            cols[4].metric("Payback (meses)", f"{payback_mes}")
            
            st.markdown("---")
            st.subheader("Fluxo de Caixa do Investidor")
            st.bar_chart(df_investidor)
            st.subheader("Distribuição de Dividendos ao Longo do Tempo")
            st.bar_chart(df['(-) Dividendos'])
            st.markdown("---")
            st.subheader("Análise do Fundo")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Evolução do Patrimônio Líquido**"); st.line_chart(df['PL Final'])
            with col2:
                st.write("**Composição do Patrimônio**"); st.area_chart(df[['Ativos_Volume', 'Caixa_Volume']].rename(columns={'Ativos_Volume': 'Ativos', 'Caixa_Volume': 'Caixa'}))

    with tab_dre:
        # (código da aba de DRE - sem alterações)
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
    
