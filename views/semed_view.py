import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    # Cabeçalho Clean
    st.title("🏢 Painel Logístico SEMED")
    st.caption(f"Usuário: {st.session_state['usuario_dados']['email']} | Gestão Raposa")

    # Menu Lateral para Navegação (Deixa o centro da tela mais limpo)
    menu = st.sidebar.radio("Navegar por:", [
        "📊 Dashboard Geral", 
        "🚚 Movimentar Carga", 
        "🏫 Gestão de Unidades", 
        "📂 Catálogo de Itens",
        "👥 Usuários"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Dados"):
        st.cache_data.clear()
        st.rerun()

    # --- 1. DASHBOARD GERAL ---
    if menu == "📊 Dashboard Geral":
        st.subheader("Situação do Estoque em Tempo Real")
        
        df_escolas = carregar_dados("db_escolas")
        
        # Filtro de local simplificado
        opcoes_local = ["SEMED"] + (df_escolas['ID_Escola'].tolist() if not df_escolas.empty else [])
        local = st.selectbox("Filtrar Estoque por Local:", opcoes_local)
        
        saldo = calcular_estoque_atual(local)
        
        if not saldo.empty:
            df_cat = carregar_dados("db_catalogo") # Nome corrigido conforme imagem
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Mostra o saldo de forma organizada
            st.dataframe(
                df_final[['Nome_Produto', 'Saldo', 'Unidade', 'Categoria']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(f"Sem movimentações registradas para {local} até o momento.")

    # --- 2. MOVIMENTAR CARGA (ENTRADAS / AGRICULTURA / TRANSFERÊNCIAS) ---
    elif menu == "🚚 Movimentar Carga":
        st.subheader("Registro de Entradas e Saídas")
        
        df_cat = carregar_dados("db_catalogo")
        df_esc = carregar_dados("db_escolas")
        
        with st.form("form_mov", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                tipo_o = st.selectbox("Origem", ["Fornecedor", "Agricultura Familiar", "SEMED"])
                item = st.selectbox("Produto", df_cat['Nome_Produto'].tolist() if not df_cat.empty else [])
                qtd = st.number_input("Quantidade", min_value=0.1, step=1.0)
            
            with c2:
                destino = st.selectbox("Destino", ["SEMED"] + (df_esc['Nome_Escola'].tolist() if not df_esc.empty else []))
                doc = st.text_input("Documento/Nota Ref.")
                data_mov = st.date_input("Data do Recebimento", datetime.now())

            if st.form_submit_button("Lançar no Sistema"):
                # Captura IDs
                id_p = df_cat[df_cat['Nome_Produto'] == item]['ID_Produto'].values[0]
                id_e = "SEMED" if destino == "SEMED" else df_esc[df_esc['Nome_Escola'] == destino]['ID_Escola'].values[0]
                
                # Regra de negócio: Agricultura/Fornecedor = ENTRADA. SEMED enviando = TRANSFERÊNCIA.
                fluxo = "ENTRADA" if tipo_o != "SEMED" else "TRANSFERÊNCIA"
                
                nova_mov = pd.DataFrame([[
                    f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_mov.strftime('%d/%m/%Y'),
                    id_e,     # Coluna ID_Escola
                    fluxo,    # Coluna Tipo_Fluxo
                    tipo_o,   # Coluna Origem
                    destino,  # Coluna Destino
                    id_p,     # Coluna ID_Produto
                    qtd,      # Coluna Quantidade
                    st.session_state['usuario_dados']['email'],
                    doc
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_mov, "db_movimentacoes"):
                    st.success("Movimentação registrada!")
                    st.rerun()

    # --- 3. GESTÃO DE UNIDADES ---
    elif menu == "🏫 Gestão de Unidades":
        st.subheader("Cadastro de Escolas")
        df_e = carregar_dados("db_escolas")
        
        with st.expander("➕ Adicionar Nova Escola"):
            with st.form("f_add_esc"):
                id_esc = st.text_input("Código ID")
                nome_esc = st.text_input("Nome da Escola")
                if st.form_submit_button("Cadastrar"):
                    salvar_dados(pd.DataFrame([[id_esc, nome_esc]], columns=['ID_Escola', 'Nome_Escola']), "db_escolas")
                    st.rerun()
        
        st.data_editor(df_e, use_container_width=True, hide_index=True)

    # --- 4. CATÁLOGO DE ITENS ---
    elif menu == "📂 Catálogo de Itens":
        st.subheader("Itens Cadastrados")
        df_c = carregar_dados("db_catalogo")
        
        with st.expander("➕ Adicionar ao Catálogo"):
            with st.form("f_add_cat"):
                c1, c2 = st.columns(2)
                id_i = c1.text_input("ID Item")
                nome_i = c1.text_input("Nome do Produto")
                cat_i = c2.selectbox("Categoria", ["Limpeza", "Alimentação", "Expediente"])
                un_i = c2.selectbox("Unidade", ["Unid", "Kg", "Cx", "Pct"])
                if st.form_submit_button("Adicionar"):
                    salvar_dados(pd.DataFrame([[id_i, nome_i, cat_i, un_i]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade']), "db_catalogo")
                    st.rerun()
        
        st.data_editor(df_c, use_container_width=True, hide_index=True)

    # --- 5. USUÁRIOS ---
    elif menu == "👥 Usuários":
        st.subheader("Gerenciar Acessos")
        df_u = carregar_dados("db_usuarios")
        st.data_editor(df_u, use_container_width=True, hide_index=True)
