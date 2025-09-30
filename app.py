import streamlit as st
import pandas as pd
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

    # --- NOVO: Seção de Despesas ---
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
    
    # Dicionário para rastrear o valor atual de cada ativo
    valor_atual_ativos = {i: 0.0 for i in range(len(st.session_state.lista_ativos))}
    
    # Lista para armazenar os resultados de cada mês
    lista_fluxos = []

    # --- MÊS 0 (SETUP) ---
    fluxo_mes_0 = {
        'Mês': 0, 'Saldo Caixa Inicial': 0, '(+) Aportes': aporte_inicial,
        '(+) Receita Ativos': 0, '(+) Rendimento Caixa': 0, '(-) Investimentos': 0,
        '(-) Taxa de Adm.': 0, '(-) Outras Despesas': 0,
        'Saldo Caixa Final': aporte_inicial, 'PL Ativos': 0, 'Patrimônio Líquido': aporte_inicial
    }
    lista_fluxos.append(fluxo_mes_0)

    # --- LOOP DE PROJEÇÃO MENSAL (CORRIGIDO) ---
    for mes in range(1, meses_total + 1):
        fluxo_anterior = lista_fluxos[-1]
        fluxo_atual = {}

        # 1. Inicia o caixa e o PL
        saldo_caixa_inicial = fluxo_anterior['Saldo Caixa Final']
        pl_anterior = fluxo_anterior['Patrimônio Líquido']
        
        # 2. Investe em novos ativos
        investimentos_mes = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if ativo['Mês Investimento'] == mes:
                investimentos_mes += ativo['Valor']
                valor_atual_ativos[i] = ativo['Valor']
        
        # 3. Calcula a receita dos ativos existentes
        receita_total_ativos = 0
        for i, ativo in enumerate(st.session_state.lista_ativos):
            if mes > ativo['Mês Investimento']:
                spread_mensal = (1 + ativo['Spread'] / 100)**(1/12) - 1
                taxa_ativo = (1 + (taxa_cdi_mensal if ativo['Benchmark'] == 'CDI' else taxa_ipca_mensal)) * (1 + spread_mensal) - 1
                rendimento_ativo_i = valor_atual_ativos[i] * taxa_ativo
                receita_total_ativos += rendimento_ativo_i
                valor_atual_ativos[i] += rendimento_ativo_i
        
        # 4. Calcula as despesas
        despesa_taxa_adm = pl_anterior * taxa_adm_mensal
        
        # 5. Calcula o rendimento do caixa
        caixa_para_rendimento = saldo_caixa_inicial - investimentos_mes
        rendimento_caixa = max(0, caixa_para_rendimento) * taxa_cdi_mensal
        
        # 6. Consolida o caixa final
        saldo_caixa_final = (saldo_caixa_inicial + receita_total_ativos + rendimento_caixa -
                             investimentos_mes - despesa_taxa_adm - outras_despesas_fixas)
                             
        # 7. Calcula o PL final
        pl_ativos = sum(valor_atual_ativos.values())
        patrimonio_liquido = saldo_caixa_final + pl_ativos

        # 8. Armazena todos os resultados do mês
        fluxo_atual['Mês'] = mes
        fluxo_atual['Saldo Caixa Inicial'] = saldo_caixa_inicial
        fluxo_atual['(+) Aportes'] = 0 # Aportes futuros serão adicionados aqui
        fluxo_atual['(+) Receita Ativos'] = receita_total_ativos
        fluxo_atual['(+) Rendimento Caixa'] = rendimento_caixa
        fluxo_atual['(-) Investimentos'] = investimentos_mes
        fluxo_atual['(-) Taxa de Adm.'] = despesa_taxa_adm
        fluxo_atual['(-) Outras Despesas'] = outras_despesas_fixas
        fluxo_atual['Saldo Caixa Final'] = saldo_caixa_final
        fluxo_atual['PL Ativos'] = pl_ativos
        fluxo_atual['Patrimônio Líquido'] = patrimonio_liquido
        
        lista_fluxos.append(fluxo_atual)

    # --- EXIBIÇÃO DOS RESULTADOS ---
    df = pd.DataFrame(lista_fluxos)
    df.index = datas_projecao

    st.header("Fluxo de Caixa Mensal Detalhado")
    df_display = df.copy()
    colunas_monetarias = [col for col in df.columns if col not in ['Mês']]
    for col in colunas_monetarias:
        df_display[col] = df_display[col].apply(lambda x: f"R$ {x:,.2f}")
    df_display.index = df_display.index.strftime('%Y-%m')
    st.dataframe(df_display[['Mês'] + colunas_monetarias])


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
