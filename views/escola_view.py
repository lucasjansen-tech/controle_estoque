import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    # Recupera os dados do usuário logado
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola'] # ID vinculado no cadastro do usuário
    
    # Busca o nome da escola para o cabeçalho
    df_esc = carregar_dados("db_escolas")
    nome_escola = "Unidade Escolar"
    if not df_esc.empty:
        escola_info = df_esc[df_esc['ID_Escola'] == id_escola]
        if not escola_info.empty:
            nome_escola = escola_info.iloc[0]['Nome_Escola']

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    st.caption(f"Operador: {user_data['email']} | Unidade: {id_escola}")

    # Menu Lateral Simplicado para a Escola
    menu = st.sidebar.radio("Ações Disponíveis:", [
        "📊 Meu Estoque", 
        "📥 Receber Material", 
        "🍳 Registrar Consumo",
        "📂 Novo Item no Catálogo"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. MEU ESTOQUE ---
    if menu == "📊 Meu Estoque":
        st.subheader("📋 Itens em Prateleira")
        saldo = calcular_estoque_atual(id_escola)
        
        if not saldo.empty:
            df_cat = carregar_dados("db_catalogo")
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Filtro de busca simples
            busca = st.text_input("🔍 Buscar item no meu estoque:")
            if busca:
                df_final = df_final[df_final['Nome_Produto'].str.contains(busca, case=False)]
            
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade_Medida', 'Categoria']], 
                         use_container_width=True, hide_index=True)
        else:
            st.warning("Seu estoque está vazio. Registre um recebimento para começar.")

    # --- 2. RECEBER MATERIAL (Agricultura ou SEMED) ---
    elif menu == "📥 Receber Material":
        st.subheader("🚚 Entrada de Novos Materiais")
        df_cat = carregar_dados("db_catalogo")
        
        with st.form("form_recebimento_escola", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                origem = st.selectbox("Origem da Entrega", ["Agricultura Familiar", "SEMED", "Fornecedor Direto"])
                # Seleção do item
                item_nome = st.selectbox("Produto Recebido", df_cat['Nome_Produto'].tolist() if not df_cat.empty else [])
                qtd = st.number_input("Quantidade Recebida", min_value=0.1)
            with c2:
                doc = st.text_input("Nº da Guia ou Nota")
                data_r = st.date_input("Data de Chegada", datetime.now())
            
            if st.form_submit_button("Confirmar Recebimento", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item_nome]['ID_Produto'].values[0]
                fluxo = "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA"
                
                nova_mov = pd.DataFrame([[
                    f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_r.strftime('%d/%m/%Y'), id_escola, fluxo, origem, nome_escola, id_p, qtd,
                    user_data['email'], doc
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_mov, "db_movimentacoes"):
                    st.success(f"Estoque atualizado! +{qtd} de {item_nome}")
                    st.rerun()

    # --- 3. REGISTRAR CONSUMO (BAIXA) ---
    elif menu == "🍳 Registrar Consumo":
        st.subheader("📉 Baixa de Materiais (Uso Diário)")
        df_cat = carregar_dados("db_catalogo")
        
        with st.form("form_consumo", clear_on_submit=True):
            item_c = st.selectbox("O que foi utilizado?", df_cat['Nome_Produto'].tolist() if not df_cat.empty else [])
            qtd_c = st.number_input("Quantidade Utilizada", min_value=0.1)
            motivo = st.text_input("Observação (Ex: Merenda Escolar, Limpeza pátio)")
            
            if st.form_submit_button("Registrar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item_c]['ID_Produto'].values[0]
                
                # Para saída, a Origem é a própria Escola e o Tipo é SAÍDA
                saida_mov = pd.DataFrame([[
                    f"OUT-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    datetime.now().strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, qtd_c,
                    user_data['email'], motivo
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(saida_mov, "db_movimentacoes"):
                    st.warning(f"Baixa registrada: -{qtd_c} de {item_c}")
                    st.rerun()

    # --- 4. NOVO ITEM NO CATÁLOGO (Autonomia para a Escola) ---
    elif menu == "📂 Novo Item no Catálogo":
        st.subheader("📂 Cadastrar Produto Não Listado")
        st.info("Use esta opção apenas se o item que chegou não estiver na lista de recebimento.")
        
        with st.form("f_novo_item_esc"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("Código/ID do Produto (Sugestão: AF-NOME)")
            nome_p = c1.text_input("Nome do Produto")
            cat_p = c2.selectbox("Categoria", ["Alimentação", "Limpeza", "Outros"])
            un_p = c2.selectbox("Unidade", ["Kg", "Unid", "Cx", "Pct", "Maço"])
            
            if st.form_submit_button("Adicionar ao Catálogo Geral"):
                novo_p = pd.DataFrame([[id_p, nome_p, cat_p, un_p]], 
                                    columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo_p, "db_catalogo"):
                    st.success(f"Item '{nome_p}' adicionado ao catálogo da rede!")
                    st.rerun()
