import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    st.title("🏢 Gestão Central Logística - SEMED")
    
    # Definição de Perfis
    usuario_atual = st.session_state['usuario_dados']
    eh_super_admin = usuario_atual['id'] == "ROOT"
    eh_coordenador = usuario_atual['perfil'] == "SEMED"

    # Menu Lateral Inteligente (Coordenador não vê Gestão de Usuários)
    opcoes_menu = ["📊 Dashboard de Saldo", "🚚 Movimentar Carga", "🏫 Unidades de Ensino", "📂 Catálogo de Itens"]
    if eh_super_admin:
        opcoes_menu.append("👥 Gestão de Usuários")

    menu = st.sidebar.radio("Navegar por:", opcoes_menu)

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Google Sheets", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. DASHBOARD ---
    if menu == "📊 Dashboard de Saldo":
        st.subheader("📊 Consulta de Estoque Real")
        df_escolas = carregar_dados("db_escolas")
        df_cat = carregar_dados("db_catalogo")
        
        # Coordenador e Root veem tudo, Escola (no futuro) verá só a dela
        opcoes_local = ["SEMED"] + (df_escolas['ID_Escola'].tolist() if not df_escolas.empty else [])
        local = st.selectbox("Selecione a Unidade para ver Saldo:", opcoes_local)
        
        saldo = calcular_estoque_atual(local)
        if not saldo.empty:
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.dataframe(df_final[['ID_Produto', 'Nome_Produto', 'Saldo', 'Unidade', 'Categoria']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info(f"Sem movimentações em {local}.")

    # --- 2. MOVIMENTAR CARGA (O Coordenador pode atuar aqui) ---
    elif menu == "🚚 Movimentar Carga":
        st.subheader("🚚 Registrar Fluxo de Material")
        df_cat = carregar_dados("db_catalogo")
        df_esc = carregar_dados("db_escolas")
        
        with st.form("form_mov_completo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                origem_t = st.selectbox("Origem", ["Fornecedor", "Agricultura Familiar", "SEMED"])
                item = st.selectbox("Produto", df_cat['Nome_Produto'].tolist() if not df_cat.empty else [])
                qtd = st.number_input("Quantidade", min_value=0.1)
            with c2:
                # Melhoria no Seletor de Destino: Nome + ID
                lista_destinos = ["SEMED"]
                if not df_esc.empty:
                    # Cria lista amigável: "ID - Nome"
                    lista_destinos += [f"{row['ID_Escola']} - {row['Nome_Escola']}" for _, row in df_esc.iterrows()]
                
                destino_selecionado = st.selectbox("Destino da Entrega", lista_destinos)
                doc = st.text_input("Nº Documento/Referência")
                data_m = st.date_input("Data", datetime.now())

            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item]['ID_Produto'].values[0]
                
                # Extrai apenas o ID se não for SEMED
                id_dest = "SEMED" if destino_selecionado == "SEMED" else destino_selecionado.split(" - ")[0]
                fluxo = "ENTRADA" if origem_t != "SEMED" else "TRANSFERÊNCIA"
                
                nova_mov = pd.DataFrame([[
                    f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_m.strftime('%d/%m/%Y'), id_dest, fluxo, origem_t, destino_selecionado, id_p, qtd,
                    usuario_atual['email'], doc
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_mov, "db_movimentacoes"):
                    st.success(f"Movimentação registrada para {destino_selecionado}!")
                    st.rerun()

    # --- 3. UNIDADES DE ENSINO ---
    elif menu == "🏫 Unidades de Ensino":
        st.subheader("🏫 Gestão de Unidades")
        df_e_view = carregar_dados("db_escolas")
        
        if eh_super_admin: # Apenas Root cadastra/importa escolas
            with st.expander("➕ Cadastro / Importação"):
                # ... (manter lógica de formulário e file_uploader que já temos)
                pass

        # Tabela com trava de exclusão para coordenador
        df_e_edit = st.data_editor(df_e_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
        if st.button("💾 Salvar Alterações na Rede"):
            salvar_dados(df_e_edit, "db_escolas", modo='overwrite')

    # --- 5. GESTÃO DE USUÁRIOS (SÓ PARA ROOT) ---
    elif menu == "👥 Gestão de Usuários" and eh_super_admin:
        st.subheader("👥 Controle de Acessos")
        df_esc = carregar_dados("db_escolas")
        
        with st.expander("➕ Criar Novo Usuário"):
            with st.form("f_user_add"):
                u_email = st.text_input("E-mail")
                u_pass = st.text_input("Senha")
                u_perfil = st.selectbox("Perfil", ["SEMED", "Escola"])
                
                # Exibição Amigável: ID - Nome
                opcoes_vinculo = ["SEMED"]
                if not df_esc.empty:
                    opcoes_vinculo += [f"{r['ID_Escola']} - {r['Nome_Escola']}" for _, r in df_esc.iterrows()]
                
                u_vinculo_full = st.selectbox("Vincular à Unidade", opcoes_vinculo)
                
                if st.form_submit_button("Gerar Usuário"):
                    id_u_vinculo = "SEMED" if u_vinculo_full == "SEMED" else u_vinculo_full.split(" - ")[0]
                    id_u = f"USR-{datetime.now().strftime('%H%M%S')}"
                    salvar_dados(pd.DataFrame([[id_u, u_email, u_pass, u_perfil, id_u_vinculo]], 
                                            columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola']), "db_usuarios")
                    st.rerun()
        
        # Edição de usuários existentes
        df_u_view = carregar_dados("db_usuarios")
        st.write("📝 **Edição de Acessos:** (Mude e-mails, senhas ou escolas diretamente na tabela)")
        df_u_edit = st.data_editor(df_u_view, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 Atualizar Banco de Usuários"):
            salvar_dados(df_u_edit, "db_usuarios", modo='overwrite')
