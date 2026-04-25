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
    """Garante que toda alteração crítica seja rastreada em db_logs"""
    log_data = pd.DataFrame([[
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        usuario, acao, doc, produto, qtd
    ]], columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    # --- CABEÇALHO INSTITUCIONAL (FONTES IGUAIS) ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 26px; font-weight: bold;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 26px; font-weight: bold;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h4 style="margin:0; color:#333;">Controle de Recebimento: <b>{nome_escola}</b></h4>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    menu = st.sidebar.radio("Navegação", [
        "🏠 Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir/Adicionar em Nota",
        "🍳 Registrar Uso (Consumo)",
        "🍎 Cadastrar Novo Item",
        "📜 Relatórios Oficiais"
    ])

    # --- 1. ESTOQUE ATUAL ---
    if menu == "🏠 Estoque Atual":
        st.subheader("📋 Saldo em Prateleira")
        saldo_df = calcular_estoque_atual(id_escola)
        if not saldo_df.empty:
            df_f = pd.merge(saldo_df, df_cat, on='ID_Produto', how='left')
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            cols = st.columns(3)
            for idx, row in df_f.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"### {row['Saldo']}")
                    st.caption(f"{row['Unidade_Medida']}")
                    st.markdown(f"**{row['Nome_Produto']}**")
        else: st.info("Estoque vazio.")

    # --- 2. RECEBER MATERIAIS (UNIDADE EXPLÍCITA) ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                cp, cq, co, cd = st.columns([2.5, 1, 2, 0.5])
                p_sel = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['prod'] = p_sel
                
                # Busca unidade para o rótulo
                unid = "Qtd"
                if p_sel:
                    unid = f"Qtd ({df_cat[df_cat['Nome_Produto'] == p_sel]['Unidade_Medida'].values[0]})"

                st.session_state.lista_itens[i]['qtd'] = cq.number_input(unid, min_value=0.0, key=f"rec_q_{item['id']}")
                st.session_state.lista_itens[i]['obs'] = co.text_input("Observação", placeholder="Ex: Fardo c/ 20", key=f"rec_o_{item['id']}")
                
                if len(st.session_state.lista_itens) > 1:
                    if cd.button("❌", key=f"rec_del_{item['id']}"):
                        st.session_state.lista_itens.pop(i); st.rerun()

        if st.button("➕ Adicionar outro produto"):
            st.session_state.lista_itens.append({'id': len(st.session_state.lista_itens)+1, 'prod': None, 'qtd': 0.0, 'obs': ""})
            st.rerun()

        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        cat = df_cat[df_cat['Nome_Produto'] == it['prod']].iloc[0]
                        lista_s.append([f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, cat['ID_Produto'], it['qtd'], cat['Unidade_Medida'], it['obs'], user_data['email'], doc_ref])
                if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success("Salvo!"); st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]; st.rerun()

    # --- 3. CORRIGIR/ADICIONAR (RESOLUÇÃO DO TYPEERROR E EXCLUSÃO) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição Avançada")
        df_mov = carregar_dados("db_movimentacoes")
        if 'ids_excluir' not in st.session_state: st.session_state.ids_excluir = []

        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
            
            # FIX TYPEERROR: Converter para string e preencher nulos antes de concatenar
            minhas['Documento_Ref'] = minhas['Documento_Ref'].fillna("S/N").astype(str)
            minhas['Data_Hora'] = minhas['Data_Hora'].fillna("").astype(str)
            minhas['ID_Lote'] = minhas['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ") - Lote: " + minhas['ID_Lote']
            
            sel = st.selectbox("Escolha o Lote:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
            
            if sel:
                lote_id = sel.split("Lote: ")[1]
                itens = minhas[minhas['ID_Lote'] == lote_id].copy()
                itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                trava = st.sidebar.checkbox("🔓 Liberar Exclusão")
                novos_v = []
                
                for idx, row in itens.reset_index(drop=True).iterrows():
                    is_ex = str(row['ID_Movimentacao']) in st.session_state.ids_excluir
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"{'~~' if is_ex else ''}**Item:** {row['Nome_Produto']}{'~~' if is_ex else ''}", unsafe_allow_html=True)
                        val_q = c2.number_input(f"Qtd ({row['Unidade_Medida']})", value=float(row['Quantidade']), key=f"ed_q_{idx}_{row['ID_Movimentacao']}", disabled=is_ex)
                        
                        if trava:
                            if not is_ex:
                                if c3.button("🗑️ Excluir", key=f"ex_{idx}"):
                                    st.session_state.ids_excluir.append(str(row['ID_Movimentacao'])); st.rerun()
                            else:
                                if c3.button("🔄 Manter", key=f"un_{idx}"):
                                    st.session_state.ids_excluir.remove(str(row['ID_Movimentacao'])); st.rerun()
                        else: c3.write("🔒")
                        
                        if not is_ex:
                            l_up = row.to_dict(); l_up['Quantidade'] = val_q; novos_v.append(l_up)

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_nota = [str(x) for x in itens['ID_Movimentacao'].tolist()]
                    
                    # LOG DE SEGURANÇA
                    for mid in st.session_state.ids_excluir:
                        it_log = itens[itens['ID_Movimentacao'] == mid]
                        if not it_log.empty: registrar_log(user_data['email'], "EXCLUSÃO", it_log.iloc[0]['Documento_Ref'], it_log.iloc[0]['Nome_Produto'], it_log.iloc[0]['Quantidade'])

                    df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_nota)]
                    df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label', 'ID_Lote'], errors='ignore')
                    
                    if salvar_dados(pd.concat([df_r, df_n]).fillna(""), "db_movimentacoes", modo='overwrite'):
                        st.session_state.ids_excluir = []; st.success("Atualizado!"); st.rerun()

    # --- 4. REGISTRAR USO (CONDIÇÃO DINÂMICA) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Baixa Diária")
        saldo_df = calcular_estoque_atual(id_escola)
        c1, c2 = st.columns(2)
        p_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
        cat_u = df_cat[df_cat['Nome_Produto'] == p_u].iloc[0]
        
        # Saldo em tempo real
        s_item = 0.0
        if not saldo_df.empty:
            m = saldo_df[saldo_df['ID_Produto'] == cat_u['ID_Produto']]
            if not m.empty: s_item = m.iloc[0]['Saldo']
        
        c1.info(f"Saldo: **{s_item} {cat_u['Unidade_Medida']}**")
        q_u = c1.number_input(f"Qtd para Saída ({cat_u['Unidade_Medida']})", min_value=0.0, max_value=float(s_item))
        d_u = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Observação")
        
        if st.button("Confirmar Saída", type="primary", use_container_width=True):
            if q_u > 0:
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO", cat_u['ID_Produto'], q_u, cat_u['Unidade_Medida'], o_u, user_data['email'], "USO DIÁRIO"]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item Agricultura Familiar")
        with st.form("f_novo"):
            id_p = st.text_input("ID"); nm_p = st.text_input("Nome"); un_p = st.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct", "Saca", "Fardo"])
            if st.form_submit_button("Cadastrar"):
                salvar_dados(pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo"); st.rerun()

    # --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO E DOWNLOAD) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado")
        df_m = carregar_dados("db_movimentacoes")
        if not df_m.empty:
            df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            df_m['DT'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            # Filtro por Período
            f_data = st.date_input("Período", [datetime.now() - timedelta(days=30), datetime.now()])
            if len(f_data) == 2:
                df_m = df_m[(df_m['DT'].dt.date >= f_data[0]) & (df_m['DT'].dt.date <= f_data[1])]

            # Agrupamento Visual por Lote
            df_m['Lote'] = df_m['ID_Movimentacao'].astype(str).str.split('-').str[1]
            for (lote, doc, data, resp), group in df_m.sort_values('DT', ascending=False).groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False):
                with st.container(border=True):
                    st.markdown(f"📄 **Nota:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Resp:** `{resp}`")
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Observacao', 'Tipo_Fluxo']])

            st.divider()
            c_d1, c_d2 = st.columns(2)
            csv = df_m.drop(columns=['DT', 'Lote', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            c_d1.download_button("📊 Baixar Excel Detalhado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 10, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(190, 8, "Secretaria Municipal de Educacao - SEMED", ln=True, align='C')
                pdf.set_font("Arial", '', 10)
                pdf.cell(190, 7, f"Unidade: {nome_escola}", ln=True, align='C')
                pdf.ln(5)
                for (lote, doc, data, resp), group in df_m.sort_values('DT', ascending=False).groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False):
                    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240, 240, 240)
                    pdf.cell(190, 8, f" NOTA: {doc} | DATA: {data} | RESP: {resp}", 1, 1, 'L', True)
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        pdf.cell(90, 6, f" {str(r['Nome_Produto'])[:40]}", 1); pdf.cell(20, 6, f" {r['Quantidade']}", 1); pdf.cell(20, 6, f" {r['Unidade_Medida']}", 1); pdf.cell(60, 6, f" {str(r['Observacao'])[:30]}", 1); pdf.ln()
                    pdf.ln(2)
                c_d2.download_button("📄 Baixar PDF Oficial", pdf.output(dest='S').encode('latin-1'), f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
