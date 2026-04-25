import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

def registrar_log(usuario, acao, doc, produto, qtd):
    log_data = pd.DataFrame([[datetime.now().strftime('%d/%m/%Y %H:%M:%S'), usuario, acao, doc, produto, qtd]], 
                            columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def renderizar_semed():
    user_data = st.session_state['usuario_dados']
    perfil_bruto = user_data.get('perfil', user_data.get('Perfil', 'COORDENADOR'))
    perfil_usuario = str(perfil_bruto).strip().upper()
    
    df_esc = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    df_mov = carregar_dados("db_movimentacoes")
    df_usuarios = carregar_dados("db_usuarios")

    # --- CABEÇALHO INSTITUCIONAL ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 24px; font-weight: bold;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 24px; font-weight: bold;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h4 style="margin:0; color:#333;">Painel de Gestão e Operação Central</h4>
            <p style="margin:0; color:#666;"><b>Operador:</b> {user_data['email']} | <b>Acesso:</b> {perfil_usuario}</p>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    # --- MENU DINÂMICO ---
    opcoes_menu = [
        "📊 Visão Geral da Rede", 
        "🏫 Raio-X por Escola", 
        "📦 Operação: Receber Materiais",
        "✏️ Operação: Corrigir Nota",
        "🍳 Operação: Consumo Escolar",
        "📜 Relatórios Globais"
    ]
    
    if perfil_usuario in ['ADMIN', 'SEMED', 'ADMINISTRADOR']:
        opcoes_menu.extend([
            "🏫 Gestão de Unidades",
            "👥 Gestão de Usuários", 
            "⚙️ Gerenciar Catálogo", 
            "🕵️ Auditoria do Sistema"
        ])

    menu = st.sidebar.radio("Navegação SEMED", opcoes_menu)
    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Rede", use_container_width=True):
        st.cache_data.clear(); st.rerun()

    # --- 1. VISÃO GERAL DA REDE ---
    if menu == "📊 Visão Geral da Rede":
        st.subheader("📊 Indicadores da Rede Municipal")
        if not df_mov.empty:
            df_mov['DT_OBJ'] = pd.to_datetime(df_mov['Data_Hora'], dayfirst=True, errors='coerce')
            
            c_f1, c_f2 = st.columns(2)
            dias_filtro = c_f1.selectbox("Período de Análise", ["Últimos 30 dias", "Últimos 7 dias", "Todo o período"])
            esc_filtro = c_f2.multiselect("Filtrar por Unidades (Opcional)", df_esc['Nome_Escola'].tolist())
            
            df_dash = df_mov.copy()
            if dias_filtro == "Últimos 30 dias": df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=30))]
            elif dias_filtro == "Últimos 7 dias": df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=7))]
            
            if esc_filtro:
                ids_f = df_esc[df_esc['Nome_Escola'].isin(esc_filtro)]['ID_Escola'].tolist()
                df_dash = df_dash[df_dash['ID_Escola'].isin(ids_f)]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Escolas Analisadas", len(esc_filtro) if esc_filtro else len(df_esc))
            c2.metric("Lançamentos (Período)", len(df_dash))
            c3.metric("Entradas Registradas", len(df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']))
            c4.metric("Saídas (Consumo)", len(df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']))

            st.divider()
            col_g1, col_g2 = st.columns(2)
            
            with col_g1.container(border=True):
                st.markdown("**Top 5 Escolas em Consumo**")
                saidas = df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']
                if not saidas.empty:
                    st.bar_chart(saidas.groupby('Destino')['Quantidade'].sum().sort_values(ascending=False).head(5))
                else: st.info("Sem dados.")

            with col_g2.container(border=True):
                st.markdown("**Produtos Mais Entregues (Rede)**")
                entradas = df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']
                if not entradas.empty:
                    entradas = pd.merge(entradas, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto')
                    st.bar_chart(entradas.groupby('Nome_Produto')['Quantidade'].sum().sort_values(ascending=False).head(5))
                else: st.info("Sem dados.")
        else: st.warning("Base vazia.")

    # --- 2. RAIO-X POR ESCOLA ---
    elif menu == "🏫 Raio-X por Escola":
        st.subheader("🏫 Situação do Estoque")
        escola_alvo = st.selectbox("Selecione a Unidade:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]

        saldo_esc = calcular_estoque_atual(id_alvo)
        if not saldo_esc.empty:
            saldo_esc = pd.merge(saldo_esc, df_cat, on='ID_Produto', how='left')
            
            # Filtro de Categoria no Raio-X
            cat_f = st.multiselect("Filtrar Categoria", saldo_esc['Categoria'].unique())
            if cat_f: saldo_esc = saldo_esc[saldo_esc['Categoria'].isin(cat_f)]
            
            cols = st.columns(3)
            for idx, row in saldo_esc.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"### {row['Saldo']}")
                    st.caption(row['Unidade_Medida'])
                    st.markdown(f"**{row['Nome_Produto']}**")
        else: st.info("Estoque zerado ou não registrado.")

    # --- 3. OPERAÇÃO: RECEBER MATERIAIS ---
    elif menu == "📦 Operação: Receber Materiais":
        st.subheader("📦 Registrar Recebimento para uma Unidade")
        with st.container(border=True):
            escola_alvo = st.selectbox("🏫 Escola de Destino:", df_esc['Nome_Escola'].sort_values().tolist())
            id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]
            
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["SEMED", "Agricultura Familiar", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Guia")
            data_r = c3.date_input("Data da Entrega", datetime.now(), format="DD/MM/YYYY")

        if 'itens_semed' not in st.session_state: st.session_state.itens_semed = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]

        for i, item in enumerate(st.session_state.itens_semed):
            with st.container(border=True):
                cp, cq, co, cd = st.columns([2.5, 1, 2, 0.5])
                p_sel = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"sr_p_{item['id']}")
                st.session_state.itens_semed[i]['prod'] = p_sel
                unid = f"Qtd ({df_cat[df_cat['Nome_Produto']==p_sel]['Unidade_Medida'].values[0]})" if p_sel else "Qtd"
                st.session_state.itens_semed[i]['qtd'] = cq.number_input(unid, min_value=0.0, key=f"sr_q_{item['id']}")
                st.session_state.itens_semed[i]['obs'] = co.text_input("Obs", placeholder="Fardo/Saca", key=f"sr_o_{item['id']}")
                if len(st.session_state.itens_semed) > 1:
                    if cd.button("❌", key=f"sr_del_{item['id']}"): st.session_state.itens_semed.pop(i); st.rerun()

        if st.button("➕ Adicionar Produto"):
            st.session_state.itens_semed.append({'id': len(st.session_state.itens_semed)+1, 'prod': None, 'qtd': 0.0, 'obs': ""}); st.rerun()

        if st.button("✅ SALVAR DISTRIBUIÇÃO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.itens_semed):
                    if it['prod'] and it['qtd'] > 0:
                        cat = df_cat[df_cat['Nome_Produto'] == it['prod']].iloc[0]
                        lista_s.append([f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_alvo, "ENTRADA", origem, escola_alvo, cat['ID_Produto'], it['qtd'], cat['Unidade_Medida'], it['obs'], user_data['email'], doc_ref])
                if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success(f"Salvo!"); st.session_state.itens_semed = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]; st.rerun()
            else: st.error("Insira o Documento.")

    # --- 4. OPERAÇÃO: CORRIGIR NOTA ---
    elif menu == "✏️ Operação: Corrigir Nota":
        st.subheader("✏️ Suporte Técnico: Edição")
        escola_alvo = st.selectbox("🏫 Escola Alvo:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]
        
        if 'idx_ex_sem' not in st.session_state: st.session_state.idx_ex_sem = []

        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            minhas = df_mov[df_mov['ID_Escola'] == id_alvo].copy()
            c_f1, c_f2 = st.columns(2)
            f_data_edit = c_f1.date_input("Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
            f_tipo_edit = c_f2.multiselect("Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            minhas['Documento_Ref'] = minhas['Documento_Ref'].fillna("S/N").astype(str)
            minhas['Data_Hora'] = minhas['Data_Hora'].fillna("").astype(str)
            minhas['ID_Lote'] = minhas['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            minhas['DT_OBJ'] = pd.to_datetime(minhas['Data_Hora'], dayfirst=True, errors='coerce')

            if len(f_data_edit) == 2: minhas = minhas[(minhas['DT_OBJ'].dt.date >= f_data_edit[0]) & (minhas['DT_OBJ'].dt.date <= f_data_edit[1])]
            if f_tipo_edit: minhas = minhas[minhas['Tipo_Fluxo'].isin(f_tipo_edit)]
            
            if not minhas.empty:
                minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ") - Lote: " + minhas['ID_Lote']
                sel = st.selectbox("Selecione a Nota:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
                
                if sel:
                    lote_id = sel.split("Lote: ")[1]
                    itens = minhas[minhas['ID_Lote'] == lote_id].copy()
                    itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                    trava = st.sidebar.checkbox("🔓 Liberar Exclusão")
                    novos_v = []
                    for idx, row in itens.reset_index(drop=True).iterrows():
                        is_ex = str(row['ID_Movimentacao']) in st.session_state.idx_ex_sem
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 1, 1])
                            c1.markdown(f"{'<s>' if is_ex else ''}**Item:** {row['Nome_Produto']}{'</s>' if is_ex else ''}", unsafe_allow_html=True)
                            val_q = c2.number_input(f"Qtd ({row['Unidade_Medida']})", value=float(row['Quantidade']), key=f"se_q_{row['ID_Movimentacao']}", disabled=is_ex)
                            if trava:
                                if not is_ex:
                                    if c3.button("🗑️", key=f"se_ex_{idx}"): st.session_state.idx_ex_sem.append(str(row['ID_Movimentacao'])); st.rerun()
                                else:
                                    if c3.button("🔄", key=f"se_un_{idx}"): st.session_state.idx_ex_sem.remove(str(row['ID_Movimentacao'])); st.rerun()
                            else: c3.write("🔒")
                            if not is_ex:
                                l_up = row.to_dict(); l_up['Quantidade'] = val_q; novos_v.append(l_up)

                    if st.button("💾 SALVAR", type="primary", use_container_width=True):
                        df_full = carregar_dados("db_movimentacoes")
                        ids_nota = [str(x) for x in itens['ID_Movimentacao'].tolist()]
                        for mid in st.session_state.idx_ex_sem:
                            it_log = itens[itens['ID_Movimentacao'] == mid]
                            if not it_log.empty: registrar_log(user_data['email'], "EXCLUSÃO_SUPORTE", it_log.iloc[0]['Documento_Ref'], it_log.iloc[0]['Nome_Produto'], it_log.iloc[0]['Quantidade'])
                        df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_nota)]
                        df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label', 'ID_Lote', 'DT_OBJ'], errors='ignore')
                        if salvar_dados(pd.concat([df_r, df_n]).fillna(""), "db_movimentacoes", modo='overwrite'):
                            st.session_state.idx_ex_sem = []; st.success("Atualizado!"); st.rerun()
            else: st.warning("Nenhum lançamento nos filtros.")
        else: st.warning("Base vazia.")

    # --- 5. OPERAÇÃO: CONSUMO ---
    elif menu == "🍳 Operação: Consumo Escolar":
        st.subheader("🍳 Registrar Baixa / Consumo de Escola")
        escola_alvo = st.selectbox("🏫 Escola Alvo da Baixa:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]
        
        saldo_df = calcular_estoque_atual(id_alvo)
        c1, c2 = st.columns(2)
        p_u = c1.selectbox("Produto Utilizado", df_cat['Nome_Produto'].sort_values().tolist())
        cat_u = df_cat[df_cat['Nome_Produto'] == p_u].iloc[0]
        
        s_item = 0.0
        if not saldo_df.empty:
            m = saldo_df[saldo_df['ID_Produto'] == cat_u['ID_Produto']]
            if not m.empty: s_item = m.iloc[0]['Saldo']
        
        c1.info(f"💡 Saldo: **{s_item} {cat_u['Unidade_Medida']}**")
        q_u = c1.number_input(f"Qtd Baixa ({cat_u['Unidade_Medida']})", min_value=0.01, max_value=float(s_item) if s_item > 0 else 0.01)
        d_u = c2.date_input("Data do Consumo", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Finalidade")
        
        if st.button("Confirmar Baixa", type="primary", use_container_width=True):
            if q_u > 0 and q_u <= s_item:
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_alvo, "SAÍDA", escola_alvo, "CONSUMO INTERNO", cat_u['ID_Produto'], q_u, cat_u['Unidade_Medida'], o_u, user_data['email'], "BAIXA SEMED"]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.success("Baixa Executada!"); st.rerun()

    # --- 6. RELATÓRIOS GLOBAIS ---
    elif menu == "📜 Relatórios Globais":
        st.subheader("📜 Extrator Consolidado da Rede")
        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            df_rel = df_mov.copy()
            df_rel = pd.merge(df_rel, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            df_rel['DT_OBJ'] = pd.to_datetime(df_rel['Data_Hora'], dayfirst=True, errors='coerce')

            with st.container(border=True):
                st.markdown("**🔍 Filtros do Relatório**")
                c1, c2, c3 = st.columns(3)
                f_data = c1.date_input("Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_esc = c2.multiselect("Unidades (Vazio = Todas)", df_esc['Nome_Escola'].tolist())
                f_tipo = c3.multiselect("Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            if len(f_data) == 2: df_rel = df_rel[(df_rel['DT_OBJ'].dt.date >= f_data[0]) & (df_rel['DT_OBJ'].dt.date <= f_data[1])]
            if f_tipo: df_rel = df_rel[df_rel['Tipo_Fluxo'].isin(f_tipo)]
            if f_esc: 
                ids_f = df_esc[df_esc['Nome_Escola'].isin(f_esc)]['ID_Escola'].tolist()
                df_rel = df_rel[df_rel['ID_Escola'].isin(ids_f)]

            df_rel['Lote'] = df_rel['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            grupos = df_rel.sort_values('DT_OBJ', ascending=False).groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'Destino', 'ID_Usuario'], sort=False)
            
            st.write(f"**Notas Encontradas:** {len(grupos)}")
            for (lote, doc, data, destino, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"🏫 **{destino}** | 📄 `{doc}` | 🗓️ {data} | 👤 `{resp}`")
                    cols_show = ['Nome_Produto', 'Quantidade']
                    if 'Unidade_Medida' in group.columns: cols_show.append('Unidade_Medida')
                    if 'Observacao' in group.columns: cols_show.append('Observacao')
                    cols_show.append('Tipo_Fluxo')
                    st.dataframe(group[cols_show], use_container_width=True, hide_index=True)

            c_d1, c_d2 = st.columns(2)
            csv_f = df_rel.drop(columns=['DT_OBJ', 'Lote', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            c_d1.download_button("📊 Baixar Excel", csv_f, "Relatorio_SEMED.csv", use_container_width=True)
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                try:
                    pdf.image("Banner.png", x=10, y=10, w=190)
                    pdf.set_y(50) 
                except: pdf.set_y(10)

                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 8, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.cell(190, 8, "SECRETARIA MUNICIPAL DE EDUCACAO - SEMED", ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(190, 7, "Relatorio Consolidado da Rede" if not f_esc else f"Relatorio ({len(f_esc)} Unidades)", ln=True, align='C')
                pdf.ln(8)
                
                for (lote, doc, data, destino, resp), group in grupos:
                    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230, 230, 230)
                    pdf.cell(190, 8, f" ESCOLA: {str(destino)[:25]} | NOTA: {doc} | DATA: {data}", 1, 1, 'L', True)
                    pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(255, 255, 255)
                    pdf.cell(90, 7, " Produto", 1); pdf.cell(20, 7, " Qtd", 1); pdf.cell(20, 7, " Unid", 1); pdf.cell(60, 7, " Obs", 1); pdf.ln()
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        pdf.cell(90, 6, f" {str(r['Nome_Produto'])[:40]}", 1); pdf.cell(20, 6, f" {r['Quantidade']}", 1); pdf.cell(20, 6, f" {r.get('Unidade_Medida', '')}", 1); pdf.cell(60, 6, f" {str(r.get('Observacao', ''))[:30]}", 1); pdf.ln()
                    pdf.ln(3)
                c_d2.download_button("📄 Baixar PDF", pdf.output(dest='S').encode('latin-1'), "Relatorio_SEMED.pdf", "application/pdf", use_container_width=True)

    # --- NOVO: GESTÃO DE UNIDADES DE ENSINO ---
    elif menu == "🏫 Gestão de Unidades":
        st.subheader("🏫 Gestão de Unidades de Ensino")
        
        with st.container(border=True):
            f_esc_nome = st.text_input("🔍 Buscar Escola por Nome:")
        
        df_esc_view = df_esc.copy()
        if f_esc_nome:
            df_esc_view = df_esc_view[df_esc_view['Nome_Escola'].str.contains(f_esc_nome, case=False, na=False)]
            
        st.dataframe(df_esc_view, use_container_width=True, hide_index=True)
        
        with st.expander("➕ Adicionar Nova Unidade"):
            with st.form("f_add_esc"):
                c1, c2 = st.columns(2)
                n_esc_nome = c1.text_input("Nome da Unidade (Ex: UEB Cuidando do Futuro)")
                n_esc_tipo = c2.selectbox("Tipo", ["Educação Infantil", "Ensino Fundamental I", "Ensino Fundamental II", "EJA", "Creche"])
                if st.form_submit_button("Cadastrar Escola"):
                    if n_esc_nome:
                        novo_id = f"ESC-{datetime.now().strftime('%H%M%S')}"
                        nova_e = pd.DataFrame([[novo_id, n_esc_nome, n_esc_tipo]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola'])
                        salvar_dados(pd.concat([df_esc, nova_e]), "db_escolas", modo='overwrite'); st.success("Cadastrada!"); st.rerun()
                    else: st.error("O nome é obrigatório.")

    # --- 7. ADMIN: GESTÃO DE USUÁRIOS (UX RENOVADA) ---
    elif menu == "👥 Gestão de Usuários":
        st.subheader("👥 Controle de Acessos e Perfis")
        
        c_f1, c_f2 = st.columns(2)
        f_u_nome = c_f1.text_input("🔍 Buscar por E-mail")
        f_u_perfil = c_f2.selectbox("Filtrar Período", ["Todos", "ESCOLA", "COORDENADOR", "ADMIN", "SEMED"])
        
        df_u_view = df_usuarios.copy()
        if f_u_nome: df_u_view = df_u_view[df_u_view['Email'].str.contains(f_u_nome, case=False, na=False)]
        if f_u_perfil != "Todos": df_u_view = df_u_view[df_u_view['Perfil'] == f_u_perfil]

        st.markdown("**Usuários Ativos:**")
        if 'usr_excluir' not in st.session_state: st.session_state.usr_excluir = []
        
        trava_u = st.checkbox("🔓 Habilitar Exclusão de Usuários")
        
        for idx, u_row in df_u_view.iterrows():
            with st.container(border=True):
                col_u1, col_u2, col_u3, col_u4 = st.columns([2, 1, 2, 1])
                col_u1.markdown(f"**E-mail:** {u_row['Email']}")
                col_u2.markdown(f"**Perfil:** `{u_row['Perfil']}`")
                
                # Traduz o ID_Escola para o Nome
                nome_esc_vinculo = "Acesso Global"
                if u_row['ID_Escola'] != "NENHUMA (Acesso Global)" and not pd.isna(u_row['ID_Escola']):
                    match_esc = df_esc[df_esc['ID_Escola'] == u_row['ID_Escola']]
                    if not match_esc.empty: nome_esc_vinculo = match_esc.iloc[0]['Nome_Escola']
                
                col_u3.markdown(f"**Vínculo:** {nome_esc_vinculo}")
                
                if trava_u:
                    if col_u4.button("🗑️ Excluir", key=f"del_u_{u_row['ID_Usuario']}"):
                        df_u_novo = df_usuarios[df_usuarios['ID_Usuario'] != u_row['ID_Usuario']]
                        salvar_dados(df_u_novo, "db_usuarios", modo='overwrite')
                        st.warning(f"Usuário {u_row['Email']} removido!"); st.rerun()

        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("f_new_user"):
                c1, c2 = st.columns(2)
                u_email = c1.text_input("E-mail (Login)")
                u_senha = c1.text_input("Senha", type="password")
                u_perfil = c2.selectbox("Perfil", ["ESCOLA", "SEMED", "ADMIN"])
                lista_escolas = ["NENHUMA (Acesso Global)"] + df_esc['ID_Escola'].tolist()
                u_esc = c2.selectbox("Vincular à Escola (Obrigatório para ESCOLA)", lista_escolas)
                
                if st.form_submit_button("Salvar Usuário"):
                    if u_email and u_senha:
                        novo_u = pd.DataFrame([[f"USR-{datetime.now().strftime('%H%M%S')}", u_email, u_senha, u_perfil, u_esc]], columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola'])
                        salvar_dados(pd.concat([df_usuarios, novo_u]), "db_usuarios", modo='overwrite'); st.success("Cadastrado!"); st.rerun()

    # --- 8. ADMIN: GERENCIAR CATÁLOGO (FILTROS E ADIÇÃO EM LOTE) ---
    elif menu == "⚙️ Gerenciar Catálogo":
        st.subheader("⚙️ Catálogo Central")
        
        c_c1, c_c2 = st.columns(2)
        f_cat_nome = c_c1.text_input("🔍 Buscar Produto")
        f_cat_tipo = c_c2.selectbox("Filtrar Categoria", ["Todas"] + df_cat['Categoria'].unique().tolist())
        
        df_cat_view = df_cat.copy()
        if f_cat_nome: df_cat_view = df_cat_view[df_cat_view['Nome_Produto'].str.contains(f_cat_nome, case=False, na=False)]
        if f_cat_tipo != "Todas": df_cat_view = df_cat_view[df_cat_view['Categoria'] == f_cat_tipo]
        
        st.dataframe(df_cat_view, use_container_width=True, hide_index=True)
        
        tab1, tab2 = st.tabs(["➕ Adição Individual", "📋 Adição em Lote"])
        
        with tab1:
            with st.form("f_add_cat_single"):
                c1, c2 = st.columns(2)
                n_id = c1.text_input("Código (ID)")
                n_nome = c1.text_input("Nome do Produto")
                n_cat = c2.selectbox("Categoria", ["Agricultura Familiar", "Alimentação Seca", "Limpeza", "Material Didático"])
                n_un = c2.selectbox("Unidade", ["Kg", "Unid", "Pct", "Cx", "Saca", "Fardo"])
                if st.form_submit_button("Inserir Produto"):
                    if n_id and n_nome:
                        salvar_dados(pd.concat([df_cat, pd.DataFrame([[n_id, n_nome, n_cat, n_un]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])]), "db_catalogo", modo='overwrite')
                        st.success("Atualizado!"); st.rerun()

        with tab2:
            st.info("Adicione múltiplos produtos simultaneamente.")
            if 'lote_cat' not in st.session_state: st.session_state.lote_cat = [{'id': 0, 'cod':'', 'nome':'', 'cat':'Alimentação Seca', 'un':'Kg'}]
            
            for i, item in enumerate(st.session_state.lote_cat):
                c1, c2, c3, c4, c5 = st.columns([1.5, 3, 2, 1, 0.5])
                st.session_state.lote_cat[i]['cod'] = c1.text_input("Cód", key=f"lc_c_{item['id']}")
                st.session_state.lote_cat[i]['nome'] = c2.text_input("Nome", key=f"lc_n_{item['id']}")
                st.session_state.lote_cat[i]['cat'] = c3.selectbox("Cat", ["Agricultura Familiar", "Alimentação Seca", "Limpeza", "Material Didático"], key=f"lc_ca_{item['id']}")
                st.session_state.lote_cat[i]['un'] = c4.selectbox("Un", ["Kg", "Unid", "Pct", "Cx", "Saca", "Fardo"], key=f"lc_u_{item['id']}")
                if len(st.session_state.lote_cat) > 1:
                    if c5.button("❌", key=f"lc_d_{item['id']}"): st.session_state.lote_cat.pop(i); st.rerun()
            
            if st.button("➕ Adicionar Linha"):
                st.session_state.lote_cat.append({'id': len(st.session_state.lote_cat)+1, 'cod':'', 'nome':'', 'cat':'Alimentação Seca', 'un':'Kg'}); st.rerun()
            
            if st.button("✅ SALVAR LOTE NO CATÁLOGO", type="primary"):
                novos_itens = []
                for it in st.session_state.lote_cat:
                    if it['cod'] and it['nome']:
                        novos_itens.append([it['cod'], it['nome'], it['cat'], it['un']])
                if novos_itens:
                    df_novos = pd.DataFrame(novos_itens, columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                    salvar_dados(pd.concat([df_cat, df_novos]), "db_catalogo", modo='overwrite')
                    st.success("Lote cadastrado!"); st.session_state.lote_cat = [{'id': 0, 'cod':'', 'nome':'', 'cat':'Alimentação Seca', 'un':'Kg'}]; st.rerun()
                else: st.error("Preencha Códigos e Nomes.")

    # --- 9. ADMIN: AUDITORIA ---
    elif menu == "🕵️ Auditoria do Sistema":
        st.subheader("🕵️ Logs de Segurança")
        df_logs = carregar_dados("db_logs")
        if not df_logs.empty:
            st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
            st.download_button("📥 Exportar Logs", df_logs.to_csv(index=False).encode('utf-8-sig'), "Auditoria_SEMED.csv")
        else: st.info("Sem logs registrados.")
