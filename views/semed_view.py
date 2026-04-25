import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

# Tenta carregar fpdf para o PDF oficial
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

def registrar_log(usuario, acao, doc, produto, qtd):
    """Auditoria de alterações centralizadas"""
    log_data = pd.DataFrame([[
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        usuario, acao, doc, produto, qtd
    ]], columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def renderizar_semed():
    user_data = st.session_state['usuario_dados']
    
    # FIX: Busca segura do perfil (aceita minúscula ou maiúscula) e converte para maiúsculo
    perfil_bruto = user_data.get('perfil', user_data.get('Perfil', 'COORDENADOR'))
    perfil_usuario = str(perfil_bruto).strip().upper()
    
    df_esc = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    df_mov = carregar_dados("db_movimentacoes")

    # --- CABEÇALHO INSTITUCIONAL DA SEMED ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 24px; font-weight: bold;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 24px; font-weight: bold;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h4 style="margin:0; color:#333;">Painel de Gestão e Operação Central</h4>
            <p style="margin:0; color:#666;"><b>Operador:</b> {user_data['email']} | <b>Acesso Reconhecido:</b> {perfil_usuario}</p>
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
    
    # FIX: Agora reconhece 'SEMED', 'ADMIN' ou 'ADMINISTRADOR' como acesso total
    if perfil_usuario in ['ADMIN', 'SEMED', 'ADMINISTRADOR']:
        opcoes_menu.extend([
            "👥 Gestão de Usuários", 
            "⚙️ Gerenciar Catálogo", 
            "🕵️ Auditoria do Sistema"
        ])

    menu = st.sidebar.radio("Navegação SEMED", opcoes_menu)

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Rede", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. VISÃO GERAL DA REDE ---
    if menu == "📊 Visão Geral da Rede":
        st.subheader("📊 Indicadores da Rede Municipal")
        if not df_mov.empty:
            df_mov['DT_OBJ'] = pd.to_datetime(df_mov['Data_Hora'], dayfirst=True, errors='coerce')
            dias_filtro = st.selectbox("Período de Análise", ["Últimos 30 dias", "Últimos 7 dias", "Todo o período"])
            
            df_dash = df_mov.copy()
            if dias_filtro == "Últimos 30 dias":
                df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=30))]
            elif dias_filtro == "Últimos 7 dias":
                df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=7))]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Escolas Ativas", len(df_esc))
            c2.metric("Total Lançamentos", len(df_dash))
            c3.metric("Entradas Registradas", len(df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']))
            c4.metric("Saídas (Consumo)", len(df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']))

            st.divider()
            col_g1, col_g2 = st.columns(2)
            
            with col_g1.container(border=True):
                st.markdown("**Top 5 Escolas em Consumo**")
                saidas = df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']
                if not saidas.empty:
                    top_escolas = saidas.groupby('Destino')['Quantidade'].sum().sort_values(ascending=False).head(5)
                    st.bar_chart(top_escolas)
                else: st.info("Sem dados de saída.")

            with col_g2.container(border=True):
                st.markdown("**Produtos Mais Entregues**")
                entradas = df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']
                if not entradas.empty:
                    entradas = pd.merge(entradas, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto')
                    top_prods = entradas.groupby('Nome_Produto')['Quantidade'].sum().sort_values(ascending=False).head(5)
                    st.bar_chart(top_prods)
                else: st.info("Sem dados de entrada.")
        else: st.warning("Base de movimentações vazia.")

    # --- 2. RAIO-X POR ESCOLA ---
    elif menu == "🏫 Raio-X por Escola":
        st.subheader("🏫 Situação Atual do Estoque nas Unidades")
        escola_alvo = st.selectbox("Selecione a Unidade de Ensino:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]

        saldo_esc = calcular_estoque_atual(id_alvo)
        if not saldo_esc.empty:
            saldo_esc = pd.merge(saldo_esc, df_cat, on='ID_Produto', how='left')
            cols = st.columns(3)
            for idx, row in saldo_esc.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"### {row['Saldo']}")
                    st.caption(row['Unidade_Medida'])
                    st.markdown(f"**{row['Nome_Produto']}**")
        else: st.info("A unidade selecionada não possui estoque registrado.")

    # --- 3. OPERAÇÃO: RECEBER MATERIAIS ---
    elif menu == "📦 Operação: Receber Materiais":
        st.subheader("📦 Registrar Recebimento para uma Unidade")
        
        with st.container(border=True):
            escola_alvo = st.selectbox("🏫 Escola que está recebendo:", df_esc['Nome_Escola'].sort_values().tolist())
            id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]
            
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["SEMED", "Agricultura Familiar", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Guia de Remessa")
            data_r = c3.date_input("Data da Entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens_semed' not in st.session_state:
            st.session_state.lista_itens_semed = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]

        for i, item in enumerate(st.session_state.lista_itens_semed):
            with st.container(border=True):
                cp, cq, co, cd = st.columns([2.5, 1, 2, 0.5])
                p_sel = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"s_rec_p_{item['id']}")
                st.session_state.lista_itens_semed[i]['prod'] = p_sel
                
                unid_lbl = "Qtd"
                if p_sel: unid_lbl = f"Qtd ({df_cat[df_cat['Nome_Produto'] == p_sel]['Unidade_Medida'].values[0]})"

                st.session_state.lista_itens_semed[i]['qtd'] = cq.number_input(unid_lbl, min_value=0.0, key=f"s_rec_q_{item['id']}")
                st.session_state.lista_itens_semed[i]['obs'] = co.text_input("Observação", placeholder="Ex: Fardo", key=f"s_rec_o_{item['id']}")
                
                if len(st.session_state.lista_itens_semed) > 1:
                    if cd.button("❌", key=f"s_rec_del_{item['id']}"):
                        st.session_state.lista_itens_semed.pop(i); st.rerun()

        if st.button("➕ Adicionar Produto"):
            st.session_state.lista_itens_semed.append({'id': len(st.session_state.lista_itens_semed)+1, 'prod': None, 'qtd': 0.0, 'obs': ""})
            st.rerun()

        if st.button("✅ SALVAR DISTRIBUIÇÃO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens_semed):
                    if it['prod'] and it['qtd'] > 0:
                        cat = df_cat[df_cat['Nome_Produto'] == it['prod']].iloc[0]
                        lista_s.append([f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_alvo, "ENTRADA", origem, escola_alvo, cat['ID_Produto'], it['qtd'], cat['Unidade_Medida'], it['obs'], user_data['email'], doc_ref])
                if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success(f"Recebimento salvo para {escola_alvo}!")
                    st.session_state.lista_itens_semed = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]; st.rerun()
            else: st.error("O número do documento é obrigatório.")

    # --- 4. OPERAÇÃO: CORRIGIR NOTA (COM PREVENÇÃO DE TYPEERROR) ---
    elif menu == "✏️ Operação: Corrigir Nota":
        st.subheader("✏️ Suporte Técnico: Edição de Lançamentos")
        escola_alvo = st.selectbox("🏫 Escola Alvo da Correção:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]
        
        if 'ids_excluir_semed' not in st.session_state: st.session_state.ids_excluir_semed = []

        df_mov = carregar_dados("db_movimentacoes")
        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            minhas = df_mov[df_mov['ID_Escola'] == id_alvo].copy()
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros de Busca**")
                c_f1, c_f2 = st.columns(2)
                f_data_edit = c_f1.date_input("Filtrar Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_tipo_edit = c_f2.multiselect("Filtrar Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            # FIX TYPEERROR: Força conversão para string em colunas de junção de texto
            minhas['Documento_Ref'] = minhas['Documento_Ref'].fillna("S/N").astype(str)
            minhas['Data_Hora'] = minhas['Data_Hora'].fillna("").astype(str)
            minhas['ID_Lote'] = minhas['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            minhas['DT_OBJ'] = pd.to_datetime(minhas['Data_Hora'], dayfirst=True, errors='coerce')

            if len(f_data_edit) == 2:
                minhas = minhas[(minhas['DT_OBJ'].dt.date >= f_data_edit[0]) & (minhas['DT_OBJ'].dt.date <= f_data_edit[1])]
            if f_tipo_edit: 
                minhas = minhas[minhas['Tipo_Fluxo'].isin(f_tipo_edit)]
            
            if not minhas.empty:
                # Concatenação 100% segura blindada contra valores nulos/numéricos
                minhas['Label'] = "Nota: " + minhas['Documento_Ref'].astype(str) + " (" + minhas['Data_Hora'].astype(str) + ") - Lote: " + minhas['ID_Lote'].astype(str)
                sel = st.selectbox("Selecione o Lote / Nota:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
                
                if sel:
                    lote_id = sel.split("Lote: ")[1]
                    itens = minhas[minhas['ID_Lote'] == lote_id].copy()
                    itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                    trava = st.sidebar.checkbox("🔓 Liberar Exclusão de Itens")
                    novos_v = []
                    
                    for idx, row in itens.reset_index(drop=True).iterrows():
                        is_ex = str(row['ID_Movimentacao']) in st.session_state.ids_excluir_semed
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 1, 1])
                            c1.markdown(f"{'<s>' if is_ex else ''}**Item:** {row['Nome_Produto']}{'</s>' if is_ex else ''}", unsafe_allow_html=True)
                            val_q = c2.number_input(f"Qtd ({row['Unidade_Medida']})", value=float(row['Quantidade']), key=f"s_ed_q_{idx}_{row['ID_Movimentacao']}", disabled=is_ex)
                            
                            if trava:
                                if not is_ex:
                                    if c3.button("🗑️ Excluir", key=f"s_ex_{idx}"): st.session_state.ids_excluir_semed.append(str(row['ID_Movimentacao'])); st.rerun()
                                else:
                                    if c3.button("🔄 Manter", key=f"s_un_{idx}"): st.session_state.ids_excluir_semed.remove(str(row['ID_Movimentacao'])); st.rerun()
                            else: c3.write("🔒")
                            
                            if not is_ex:
                                l_up = row.to_dict(); l_up['Quantidade'] = val_q; novos_v.append(l_up)

                    with st.expander("➕ Adicionar Novo Produto a esta Nota"):
                        n_p = st.selectbox("Selecione o Produto", [None] + df_cat['Nome_Produto'].tolist())
                        n_q = st.number_input("Quantidade Inicial", min_value=0.0)
                        if st.button("Confirmar Inclusão"):
                            if n_p and n_q > 0:
                                cat_n = df_cat[df_cat['Nome_Produto'] == n_p].iloc[0]
                                nova_l = pd.DataFrame([[f"MOV-{lote_id}-ADD{datetime.now().strftime('%S')}", itens.iloc[0]['Data_Hora'], id_alvo, "ENTRADA", itens.iloc[0]['Origem'], escola_alvo, cat_n['ID_Produto'], n_q, cat_n['Unidade_Medida'], "", user_data['email'], itens.iloc[0]['Documento_Ref']]], 
                                                     columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                                salvar_dados(pd.concat([carregar_dados("db_movimentacoes"), nova_l]), "db_movimentacoes", modo='overwrite')
                                registrar_log(user_data['email'], "ADIÇÃO_SUPORTE", itens.iloc[0]['Documento_Ref'], n_p, n_q)
                                st.success("Adicionado!"); st.rerun()

                    if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                        df_full = carregar_dados("db_movimentacoes")
                        ids_nota = [str(x) for x in itens['ID_Movimentacao'].tolist()]
                        
                        for mid in st.session_state.ids_excluir_semed:
                            it_log = itens[itens['ID_Movimentacao'] == mid]
                            if not it_log.empty: registrar_log(user_data['email'], "EXCLUSÃO_SUPORTE", it_log.iloc[0]['Documento_Ref'], it_log.iloc[0]['Nome_Produto'], it_log.iloc[0]['Quantidade'])

                        df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_nota)]
                        df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label', 'ID_Lote', 'DT_OBJ'], errors='ignore')
                        
                        if salvar_dados(pd.concat([df_r, df_n]).fillna(""), "db_movimentacoes", modo='overwrite'):
                            st.session_state.ids_excluir_semed = []; st.success("Nota Atualizada!"); st.rerun()
            else: st.warning("Nenhum lançamento encontrado nesta escola com os filtros aplicados.")
        else: st.warning("A base de movimentações está vazia ou inacessível.")

    # --- 5. OPERAÇÃO: CONSUMO ESCOLAR ---
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
        
        c1.info(f"💡 Saldo na {escola_alvo}: **{s_item} {cat_u['Unidade_Medida']}**")
        q_u = c1.number_input(f"Qtd Baixa ({cat_u['Unidade_Medida']})", min_value=0.01, max_value=float(s_item) if s_item > 0 else 0.01)
        d_u = c2.date_input("Data do Consumo", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Finalidade / Observação")
        
        if st.button("Confirmar Baixa", type="primary", use_container_width=True):
            if q_u > 0 and q_u <= s_item:
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_alvo, "SAÍDA", escola_alvo, "CONSUMO INTERNO", cat_u['ID_Produto'], q_u, cat_u['Unidade_Medida'], o_u, user_data['email'], "BAIXA SEMED"]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.success("Baixa Executada!"); st.rerun()

    # --- 6. RELATÓRIOS GLOBAIS ---
    elif menu == "📜 Relatórios Globais":
        st.subheader("📜 Extrator Consolidado de Dados da Rede")
        df_mov = carregar_dados("db_movimentacoes")
        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            df_rel = df_mov.copy()
            df_rel = pd.merge(df_rel, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            df_rel['DT_OBJ'] = pd.to_datetime(df_rel['Data_Hora'], dayfirst=True, errors='coerce')

            with st.container(border=True):
                st.markdown("**🔍 Filtros do Relatório de Rede**")
                c1, c2, c3 = st.columns(3)
                f_data = c1.date_input("Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_esc = c2.multiselect("Filtrar Escolas (Vazio = Todas)", df_esc['Nome_Escola'].tolist())
                f_tipo = c3.multiselect("Tipo de Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            if len(f_data) == 2: df_rel = df_rel[(df_rel['DT_OBJ'].dt.date >= f_data[0]) & (df_rel['DT_OBJ'].dt.date <= f_data[1])]
            if f_tipo: df_rel = df_rel[df_rel['Tipo_Fluxo'].isin(f_tipo)]
            if f_esc: 
                ids_filtrados = df_esc[df_esc['Nome_Escola'].isin(f_esc)]['ID_Escola'].tolist()
                df_rel = df_rel[df_rel['ID_Escola'].isin(ids_filtrados)]

            df_rel['Lote'] = df_rel['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            grupos = df_rel.sort_values('DT_OBJ', ascending=False).groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'Destino', 'ID_Usuario'], sort=False)
            
            st.write(f"**Total de Notas Encontradas:** {len(grupos)}")

            for (lote, doc, data, destino, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"🏫 **Unidade:** `{destino}`")
                    st.markdown(f"📄 **Nota:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Resp:** `{resp}`")
                    
                    cols_show = ['Nome_Produto', 'Quantidade']
                    if 'Unidade_Medida' in group.columns: cols_show.append('Unidade_Medida')
                    if 'Observacao' in group.columns: cols_show.append('Observacao')
                    cols_show.append('Tipo_Fluxo')
                    st.dataframe(group[cols_show], use_container_width=True, hide_index=True)

            st.divider()
            c_d1, c_d2 = st.columns(2)
            
            csv_final = df_rel.drop(columns=['DT_OBJ', 'Lote', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            c_d1.download_button("📊 Baixar Excel da Rede", csv_final, "Relatorio_Macro_SEMED.csv", use_container_width=True)
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                try:
                    pdf.image("Banner.png", x=10, y=10, w=190)
                    pdf.set_y(50) 
                except Exception:
                    pdf.set_y(10)

                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 8, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.cell(190, 8, "SECRETARIA MUNICIPAL DE EDUCACAO - SEMED", ln=True, align='C')
                
                pdf.set_font("Arial", '', 11)
                texto_escola = "Relatorio de Consolidacao da Rede" if not f_esc else f"Relatorio de Consolidacao ({len(f_esc)} Unidades)"
                pdf.cell(190, 7, texto_escola, ln=True, align='C')
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
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                c_d2.download_button("📄 Baixar PDF Oficial da Rede", pdf_bytes, "Relatorio_Macro_SEMED.pdf", "application/pdf", use_container_width=True)
            else:
                c_d2.warning("Instale 'fpdf' para gerar o PDF.")

    # --- 7. ADMIN: GESTÃO DE USUÁRIOS ---
    elif menu == "👥 Gestão de Usuários":
        st.subheader("👥 Controle de Acessos e Perfis")
        df_usuarios = carregar_dados("db_usuarios")
        if not df_usuarios.empty:
            st.dataframe(df_usuarios.drop(columns=['Senha_Hash'], errors='ignore'), use_container_width=True, hide_index=True)
        else: st.info("Base de usuários vazia.")

        with st.expander("➕ Cadastrar Novo Usuário"):
            with st.form("f_new_user"):
                c1, c2 = st.columns(2)
                u_email = c1.text_input("E-mail (Login de Acesso)")
                u_senha = c1.text_input("Senha", type="password")
                u_perfil = c2.selectbox("Nível de Acesso (Perfil)", ["ESCOLA", "SEMED", "ADMIN"])
                
                lista_escolas = ["NENHUMA (Acesso Global)"] + df_esc['ID_Escola'].tolist()
                u_esc = c2.selectbox("Vincular à Escola (Obrigatório para perfil ESCOLA)", lista_escolas)
                
                if st.form_submit_button("Salvar Usuário"):
                    if u_email and u_senha:
                        id_gerado = f"USR-{datetime.now().strftime('%H%M%S')}"
                        novo_u = pd.DataFrame([[id_gerado, u_email, u_senha, u_perfil, u_esc]], columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola'])
                        salvar_dados(novo_u, "db_usuarios", modo='append')
                        st.success(f"Usuário cadastrado com sucesso!"); st.rerun()
                    else: st.error("Preencha E-mail e Senha.")

    # --- 8. ADMIN: GERENCIAR CATÁLOGO ---
    elif menu == "⚙️ Gerenciar Catálogo":
        st.subheader("⚙️ Catálogo Central")
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
        
        with st.expander("➕ Adicionar Novo Item à Base"):
            with st.form("f_add_cat_semed"):
                c1, c2 = st.columns(2)
                n_id = c1.text_input("Código do Produto")
                n_nome = c1.text_input("Nome do Produto")
                n_cat = c2.selectbox("Categoria", ["Agricultura Familiar", "Alimentação Seca", "Limpeza", "Material Didático"])
                n_un = c2.selectbox("Unidade", ["Kg", "Unid", "Pct", "Cx", "Saca", "Fardo"])
                
                if st.form_submit_button("Inserir no Sistema Geral"):
                    if n_id and n_nome:
                        salvar_dados(pd.DataFrame([[n_id, n_nome, n_cat, n_un]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo", modo='append')
                        st.success("Catálogo Atualizado!"); st.rerun()

    # --- 9. ADMIN: AUDITORIA ---
    elif menu == "🕵️ Auditoria do Sistema":
        st.subheader("🕵️ Logs de Segurança")
        df_logs = carregar_dados("db_logs")
        if not df_logs.empty:
            st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
            st.download_button("📥 Exportar Logs", df_logs.to_csv(index=False).encode('utf-8-sig'), "Auditoria_SEMED.csv")
        else: st.info("Sem logs registrados.")
