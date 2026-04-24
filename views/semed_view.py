import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados

def renderizar_central_movimentacao():
    st.subheader("📦 Registro de Movimentação de Carga")
    
    df_prod = carregar_dados("db_produtos")
    df_esc = carregar_dados("db_escolas")
    
    with st.form("fluxo_estoque"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Regra de Negócio: Identificar a Origem
            origem_tipo = st.selectbox("Origem do Material", [
                "Agricultura Familiar (Direto)", 
                "Fornecedor Terceirizado", 
                "Estoque Central SEMED"
            ])
            
            produto = st.selectbox("Item", df_prod['Nome_Produto'].tolist() if not df_prod.empty else [])
            qtd = st.number_input("Quantidade", min_value=1)
            
        with col2:
            # Regra de Negócio: Identificar o Destino
            destino_nome = st.selectbox("Destino da Entrega", ["Estoque Central SEMED"] + df_esc['Nome_Escola'].tolist())
            doc_ref = st.text_input("Documento de Referência (Nº Nota/Guia)")
            responsavel = st.text_input("Responsável pelo Recebimento")

        if st.form_submit_button("Confirmar Lançamento"):
            # Tradução de Nomes para IDs
            id_p = df_prod[df_prod['Nome_Produto'] == produto]['ID_Produto'].values[0]
            
            # Define ID_Origem
            if "Agricultura" in origem_tipo: id_o = "AGRICULTURA"
            elif "Fornecedor" in origem_tipo: id_o = "FORNECEDOR"
            else: id_o = "SEMED"
            
            # Define ID_Destino
            id_d = "SEMED" if destino_nome == "Estoque Central SEMED" else df_esc[df_esc['Nome_Escola'] == destino_nome]['ID_Escola'].values[0]
            
            # Define Tipo de Fluxo
            tipo = "ENTRADA" if id_o in ["AGRICULTURA", "FORNECEDOR"] else "TRANSFERÊNCIA"

            nova_linha = pd.DataFrame([[
                f"MOV-{datetime.now().strftime('%d%m%y%H%M%S')}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                id_d, # Mantendo sua coluna ID_Escola como o ponto focal do estoque
                tipo,
                id_p,
                qtd,
                st.session_state['usuario_dados']['email'],
                doc_ref
            ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo', 'ID_Produto', 'Quantidade_Movimentada', 'ID_Usuario', 'Documento_Ref'])
            
            if salvar_dados(nova_linha, "db_movimentacoes"):
                st.success("Movimentação registrada e estoque atualizado virtualmente!")
