import streamlit as st
from modules.database import carregar_dados

# Configurações iniciais da interface
st.set_page_config(
    page_title="Controle de Estoque - SEMED Raposa", 
    page_icon="📦", 
    layout="wide"
)

st.title("📦 Sistema de Gestão de Estoque - Rede Municipal")
st.subheader("Teste de Integração com Banco de Dados (Google Sheets)")

st.info("Tentando realizar a leitura da estrutura das tabelas...")

# Chamada para carregar a lista de escolas
df_escolas = carregar_dados("db_escolas")

# Lógica de exibição do teste
if not df_escolas.empty:
    st.success("✅ Conexão estabelecida com sucesso!")
    st.write("Abaixo está a estrutura detectada na aba **db_escolas**:")
    
    # Exibe a tabela. Se estiver vazia de dados, mostrará apenas as colunas: 
    # ID_Escola, Nome_Escola, Tipo
    st.dataframe(df_escolas, use_container_width=True)
    
    st.divider()
    st.write("Pode prosseguir para a criação do módulo de autenticação.")
else:
    st.warning("⚠️ A conexão foi iniciada, mas nenhum dado ou cabeçalho foi retornado.")
    st.write("Verifique se o nome da planilha e das abas estão idênticos ao código.")
