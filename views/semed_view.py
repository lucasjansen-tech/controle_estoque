import streamlit as st
import pandas as pd
from modules.database import carregar_dados, salvar_dados

def renderizar_semed():
    st.title("🏢 Gestão Central - SEMED Raposa")
    
    aba1, aba2, aba3 = st.tabs(["Unidades Escolares", "Catálogo de Itens", "Funcionários"])
    
    with aba1:
        st.subheader("Gerenciar Escolas")
        
        # Opção 1: Cadastro Individual
        with st.expander("➕ Cadastrar Escola Individualmente"):
            with st.form("form_escola"):
                id_esc = st.text_input("ID/Código da Escola")
                nome_esc = st.text_input("Nome da Unidade")
                tipo_esc = st.selectbox("Tipo de Unidade", ["Creche", "Ensino Fundamental I", "Ensino Fundamental II", "EJA"])
                if st.form_submit_button("Salvar Escola"):
                    novo_df = pd.DataFrame([[id_esc, nome_esc, tipo_esc]], columns=['ID_Escola', 'Nome_Escola', 'Tipo'])
                    if salvar_dados(novo_df, "db_escolas"):
                        st.success("Escola cadastrada!")
        
        # Opção 2: Cadastro em Lote
        with st.expander("📥 Importar Escolas em Lote (CSV/Excel)"):
            arquivo = st.file_uploader("Suba o arquivo com as colunas: ID_Escola, Nome_Escola, Tipo", type=['csv', 'xlsx'])
            if arquivo:
                df_lote = pd.read_csv(arquivo) if arquivo.name.endswith('csv') else pd.read_excel(arquivo)
                st.write("Pré-visualização dos dados:")
                st.dataframe(df_lote.head())
                if st.button("Confirmar Importação de Lote"):
                    if salvar_dados(df_lote, "db_escolas", modo='append'):
                        st.success("Importação concluída com sucesso!")

        # Visualização e Edição
        st.divider()
        st.write("Unidades cadastradas no sistema:")
        df_atual = carregar_dados("db_escolas")
        if not df_atual.empty:
            # Aqui permitimos a edição rápida
            df_editado = st.data_editor(df_atual, num_rows="dynamic", use_container_width=True)
            if st.button("Salvar Alterações na Tabela"):
                if salvar_dados(df_editado, "db_escolas", modo='overwrite'):
                    st.success("Tabela de escolas atualizada!")
