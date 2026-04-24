import streamlit as st
from modules.database import carregar_dados

# Configuração visual básica da página
st.set_page_config(page_title="Estoque Raposa", page_icon="📦", layout="centered")

st.title("📦 Teste de Conexão - Rede Raposa")

st.write("Tentando conectar ao Google Sheets...")

# Chama a função lá do módulo database
df_escolas = carregar_dados("db_escolas")

# Verifica se retornou dados (mesmo que sejam só os cabeçalhos)
if not df_escolas.empty:
    st.success("Conexão com o Google Sheets estabelecida com sucesso!")
    st.write("Estrutura da aba db_escolas:")
    st.dataframe(df_escolas)
else:
    st.warning("A conexão falhou ou a aba db_escolas está completamente vazia.")
