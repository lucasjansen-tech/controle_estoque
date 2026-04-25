import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    # Identificação de Perfis e Segurança
    usuario_atual = st.session_state['usuario_dados']
    eh_super_admin = usuario_atual['id'] == "ROOT"
    eh_coordenador = usuario_atual['perfil'] == "SEMED"

    st.title("🏢 Gestão Central Logística - SEMED")
    st.caption(f"Operador: {usuario_atual['email']} | Nível: {usuario_atual['perfil']}")

    # Menu Lateral
    opcoes_menu = ["📊 Dashboard Geral", "🚚 Movimentar Carga", "🏫 Unidades de Ensino", "📂 Catálogo de Itens", "📜 Relatórios e Auditoria"]
    if eh_super_admin:
        opcoes_menu.append("👥 Gestão de Usuários")

    menu = st.sidebar.radio("Navegar por:", opcoes_menu)

    # --- Dicas de Uso na Lateral (UX) ---
    st.sidebar.divider()
    if menu == "🚚 Movimentar Carga":
        st.sidebar.info("""
        **💡 Dicas de Movimentação:**
        * **Entrada de Fornecedor:** Use quando o material chega de empresas externas ao depósito central.
        * **Agricultura Familiar:** Registre a chegada de produtos frescos (ex: Abóbora, Acerola) que vão direto para as escolas[cite: 6, 46].
        * **Transferência:** Use para registrar a saída de materiais da SEMED para as unidades escolares.
        * **Documento:** Sempre informe o número da Nota Fiscal ou Guia para fins de auditoria[cite: 44, 87].
        """)
    
    if st.sidebar.button("🔄 Sincronizar Base de Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. DASHBOARD ---
    if menu == "📊 Dashboard Geral":
        st.subheader("📊 Saldo em Tempo Real")
        df_esc = carregar_dados("db_escolas")
        df_cat = carregar_dados("db_catalogo")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            local = st.selectbox("Selecione a Unidade:", ["SEMED"] + (df_esc['ID_Escola'].tolist() if not df_esc.empty else []))
        
        saldo = calcular_estoque_atual(local)
        if not saldo.empty:
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            with st.expander("🔍 Filtrar Visualização"):
                f_n = st.text_input("Buscar Produto")
                f_c = st.multiselect("Categoria", df_final['Categoria'].unique() if 'Categoria' in df_final.columns else [])
            
            if f_n: df_final = df_final[df_final['Nome_Produto'].str.contains(f_n, case=False, na=False)]
            if f_c: df_final = df_final[df_final['Categoria'].isin(f_c)]
            st.dataframe(df_final, use_container_width=True, hide_index=True)
        else:
            st.info(f"Sem registros para {local}.")

    # --- 2. MOVIMENTAR CARGA (UX MELHORADA) ---
    elif menu == "🚚 Movimentar Carga":
        st.subheader("🚚 Registro de Entradas e Transferências")
        st.markdown("""
        Esta tela registra o fluxo de materiais na rede. Certifique-se de conferir a **Unidade de Medida** no catálogo (kg, maço, unid) antes de confirmar a quantidade[cite: 46, 62].
        """)
        
        df_cat = carregar_dados("db_catalogo")
        df_esc = carregar_dados("db_escolas")
        
        with st.form("form_mov_v3", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                origem = st.selectbox(
                    "Origem", 
                    ["Fornecedor", "Agricultura Familiar", "SEMED"],
                    help="Selecione 'Agricultura Familiar' para produtos do contrato PNAE 2026[cite: 6]."
                )
                
                # Exibição do produto com ajuda visual
                item_sel = st.selectbox(
                    "Produto", 
                    df_cat['Nome_Produto'].tolist() if not df_cat.empty else [],
                    help="Caso o produto não apareça, cadastre-o primeiro no 'Catálogo de Itens'."
                )
                
                qtd = st.number_input(
                    "Quantidade", 
                    min_value=0.01, 
                    format="%.2f",
                    help="Use ponto para decimais (ex: 10.50 kg)."
                )
            
            with c2:
                # Vínculo claro ID - Nome no seletor para precisão total
                lista_dest = ["SEMED"] + [f"{r['ID_Escola']} - {r['Nome_Escola']}" for _, r in df_esc.iterrows()]
                destino_sel = st.selectbox(
                    "Destino", 
                    lista_dest,
                    help="Selecione para qual unidade escolar o material está sendo enviado."
                )
                
                doc = st.text_input(
                    "Documento/Nota de Ref.",
                    help="Obrigatório para prestação de contas e auditoria."
                )
                
                # Data com formato brasileiro exibido na label e interno
                data_m = st.date_input(
                    "Data do Recebimento", 
                    datetime.now(),
                    format="DD/MM/YYYY" # Força o formato visual PT-BR
                )

            st.markdown("---")
            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                if not doc:
                    st.error("O campo 'Documento/Nota de Ref.' é obrigatório.")
                elif not item_sel:
                    st.error("Selecione um produto do catálogo.")
                else:
                    id_p = df_cat[df_cat['Nome_Produto'] == item_sel]['ID_Produto'].values[0]
                    id_e = "SEMED" if destino_sel == "SEMED" else destino_sel.split(" - ")[0]
                    fluxo = "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA"
                    
                    nova_mov = pd.DataFrame([[
                        f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                        data_m.strftime('%d/%m/%Y'), id_e, fluxo, origem, destino_sel, id_p, qtd,
                        usuario_atual['email'], doc
                    ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    
                    if salvar_dados(nova_mov, "db_movimentacoes"):
                        st.success(f"✅ Sucesso! {qtd} de {item_sel} registrado para {destino_sel}.")
                        st.balloons()
                        st.rerun()

    # --- 3. UNIDADES DE ENSINO ---
    elif menu == "🏫 Unidades de Ensino":
        st.subheader("🏫 Gestão de Escolas")
        tipos_rede = ["Creche", "Ensino Fundamental I", "Ensino Fundamental II", "EJA", "Tempo Integral"]
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            with st.expander("➕ Nova Unidade Individual"):
                with st.form("f_esc_new"):
                    id_e = st.text_input("ID")
                    nm_e = st.text_input("Nome")
                    tp_e = st.multiselect("Níveis de Ensino", tipos_rede)
                    if st.form_submit_button("Salvar"):
                        salvar_dados(pd.DataFrame([[id_e, nm_e, ", ".join(tp_e)]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola']), "db_escolas")
                        st.rerun()
        with col_e2:
            with st.expander("📥 Importar Escolas em Lote"):
                arq_e = st.file_uploader("CSV/Excel", type=['csv', 'xlsx'], key="up_esc")
                if arq_e and st.button("Processar Carga de Escolas"):
                    df_l = pd.read_csv(arq_e) if arq_e.name.endswith('csv') else pd.read_excel(arq_e)
                    salvar_dados(df_l, "db_escolas", modo='append')
                    st.rerun()
        st.divider()
        df_view_e = carregar_dados("db_escolas")
        if not df_view_e.empty:
            f_esc = st.text_input("🔍 Buscar Escola por Nome/ID")
            if f_esc: df_view_e = df_view_e[df_view_e['Nome_Escola'].str.contains(f_esc, case=False) | df_view_e['ID_Escola'].str.contains(f_esc, case=False)]
            edit_e = st.data_editor(df_view_e, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Aplicar Alterações / Exclusões (Unidades)"):
                salvar_dados(edit_e, "db_escolas", modo='overwrite')

    # --- 4. CATÁLOGO DE ITENS ---
    elif menu == "📂 Catálogo de Itens":
        st.subheader("📂 Catálogo de Produtos e Materiais")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            with st.expander("➕ Adicionar Item Individual"):
                with st.form("f_prod_new"):
                    id_p = st.text_input("ID_Produto")
                    nm_p = st.text_input("Nome_Produto")
                    ct_p = st.selectbox("Categoria", ["Alimentação", "Limpeza", "Expediente", "Pedagógico"])
                    un_p = st.selectbox("Unidade_Medida", ["Unid", "Kg", "Cx", "Pct", "Litro"])
                    if st.form_submit_button("Cadastrar Item"):
                        salvar_dados(pd.DataFrame([[id_p, nm_p, ct_p, un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo")
                        st.rerun()
        with col_c2:
            with st.expander("📥 Importar Catálogo em Lote"):
                arq_p = st.file_uploader("Arquivo Lote", type=['csv', 'xlsx'], key="up_cat")
                if arq_p and st.button("Processar Carga de Catálogo"):
                    df_l_p = pd.read_csv(arq_p) if arq_p.name.endswith('csv') else pd.read_excel(arq_p)
                    salvar_dados(df_l_p, "db_catalogo", modo='append')
                    st.rerun()
        st.divider()
        df_view_c = carregar_dados("db_catalogo")
        if not df_view_c.empty:
            f_prod = st.text_input("🔍 Buscar no Catálogo")
            if f_prod: df_view_c = df_view_c[df_view_c['Nome_Produto'].str.contains(f_prod, case=False)]
            edit_c = st.data_editor(df_view_c, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Aplicar Alterações / Exclusões (Catálogo)"):
                salvar_dados(edit_c, "db_catalogo", modo='overwrite')

    # --- 5. RELATÓRIOS E AUDITORIA ---
    elif menu == "📜 Relatórios e Auditoria":
        st.subheader("📜 Relatórios de Movimentação da Rede")
        df_mov_geral = carregar_dados("db_movimentacoes")
        df_escolas_ref = carregar_dados("db_escolas")
        df_cat_ref = carregar_dados("db_catalogo")
        if not df_mov_geral.empty:
            with st.expander("🔍 Filtros de Relatório", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    f_escola = st.multiselect("Unidade (Destino)", ["SEMED"] + df_escolas_ref['ID_Escola'].tolist())
                    f_tipo = st.multiselect("Tipo de Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                with c2:
                    f_produto = st.multiselect("Produto", df_cat_ref['Nome_Produto'].tolist())
                    f_origem = st.multiselect("Origem", ["Agricultura Familiar", "Fornecedor", "SEMED"])
                with c3:
                    data_inicio = st.date_input("De:", datetime(2024, 1, 1), format="DD/MM/YYYY")
                    data_fim = st.date_input("Até:", datetime.now(), format="DD/MM/YYYY")
            df_mov_geral['Data_Hora_DT'] = pd.to_datetime(df_mov_geral['Data_Hora'], dayfirst=True, errors='coerce')
            df_filtrado = df_mov_geral.copy()
            if f_escola: df_filtrado = df_filtrado[df_filtrado['ID_Escola'].isin(f_escola)]
            if f_tipo: df_filtrado = df_filtrado[df_filtrado['Tipo_Fluxo'].isin(f_tipo)]
            if f_origem: df_filtrado = df_filtrado[df_filtrado['Origem'].isin(f_origem)]
            if f_produto:
                df_filtrado = pd.merge(df_filtrado, df_cat_ref[['ID_Produto', 'Nome_Produto']], on='ID_Produto')
                df_filtrado = df_filtrado[df_filtrado['Nome_Produto'].isin(f_produto)]
            df_filtrado = df_filtrado[(df_filtrado['Data_Hora_DT'].dt.date >= data_inicio) & (df_filtrado['Data_Hora_DT'].dt.date <= data_fim)]
            st.write(f"📝 Foram encontrados **{len(df_filtrado)}** registros.")
            st.dataframe(df_filtrado.drop(columns=['Data_Hora_DT']), use_container_width=True, hide_index=True)
            csv = df_filtrado.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 Baixar Relatório (Excel/CSV)", data=csv, file_name=f"Relatorio_{datetime.now().strftime('%d_%m_%Y')}.csv", mime='text/csv', use_container_width=True)
        else:
            st.warning("Ainda não há registros de movimentação.")

    # --- 6. GESTÃO DE USUÁRIOS ---
    elif menu == "👥 Gestão de Usuários" and eh_super_admin:
        st.subheader("👥 Gestão de Acessos")
        df_esc_ref = carregar_dados("db_escolas")
        with st.expander("➕ Criar Novo Usuário"):
            with st.form("f_user_new"):
                u_email = st.text_input("E-mail")
                u_pass = st.text_input("Senha")
                u_perf = st.selectbox("Perfil", ["SEMED", "Escola"])
                lista_vinc = ["SEMED"] + [f"{r['ID_Escola']} - {r['Nome_Escola']}" for _, r in df_esc_ref.iterrows()]
                u_vinc_sel = st.selectbox("Lotação / Vínculo", lista_vinc)
                if st.form_submit_button("Gerar Acesso"):
                    id_vinc = "SEMED" if u_vinc_sel == "SEMED" else u_vinc_sel.split(" - ")[0]
                    id_u = f"USR-{datetime.now().strftime('%H%M%S')}"
                    salvar_dados(pd.DataFrame([[id_u, u_email, u_pass, u_perf, id_vinc]], columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola']), "db_usuarios")
                    st.rerun()
        df_u_view = carregar_dados("db_usuarios")
        if not df_u_view.empty:
            f_user = st.text_input("🔍 Buscar Usuário")
            if f_user: df_u_view = df_u_view[df_u_view['Email'].str.contains(f_user, case=False)]
            edit_u = st.data_editor(df_u_view, num_rows="dynamic", use_container_width=True, hide_index=True)
            if st.button("💾 Atualizar Banco de Usuários"):
                salvar_dados(edit_u, "db_usuarios", modo='overwrite')
