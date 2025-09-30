import streamlit as st
import pandas as pd

  st.set_page_config(layout="wide")

  st.title("Análise de Viabilidade de Fundos de Investimento")

  st.write("Bem-vindo à ferramenta de análise. Configure os parâmetros do fundo na barra lateral à esquerda.")

  # Barra lateral para inputs
  st.sidebar.header("Parâmetros do Fundo")

  nome_fundo = st.sidebar.text_input("Nome do Fundo", "Fundo Imobiliário Exemplo")
  data_inicio = st.sidebar.date_input("Data de Início", pd.to_datetime("2024-01-01"))
  duracao_anos = st.sidebar.number_input("Duração do Fundo (anos)", 10)

  st.subheader(f"Análise para o fundo: {nome_fundo}")

  st.info(f"O projeto está configurado para uma duração de {duracao_anos} anos, começando em {data_inicio.strftime('%d/%m/%Y')}.")
