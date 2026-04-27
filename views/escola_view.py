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
    """Registra movimentações críticas na aba db_logs"""
    log_data = pd.DataFrame([[
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        usuario, acao, doc, produto, qtd
    ]], columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def limpar_texto_pdf(texto):
    """Higieniza o texto removendo emojis e caracteres que causam crash no FPDF"""
    if pd.isna(texto) or texto is None: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    # --- CABEÇALHO INSTITUCIONAL SIMÉTRICO ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 24px; font-weight: bold;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 24px; font-weight: bold;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h4 style="margin:0; color:#333;">Controle de Recebimento: <b>{nome_escola}</b></h4>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    # --- MENU LATERAL ---
    menu = st.sidebar.radio("Navegação Principal", [
        "🏠 Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir/Adicionar em Nota",
        "🍳 Registrar Uso (Consumo)",
        "📜 Relatórios Oficiais"
    ])

    # --- LIMPADOR DE SESSÃO FANTASMA (UX) ---
    if 'menu_anterior' not in st.session_state:
        st.session_state.menu_anterior = menu
    if st.session_state.menu_anterior != menu:
        # Se trocou de aba, limpa as memórias de preenchimento para não confundir usuários
        if 'lista_itens' in st.session_state: st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]
        if 'ids_excluir' in st.session_state: st.session_state.ids_excluir = []
        st.session_state.menu_anterior = menu

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

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

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da Entrega", datetime.now(), format="DD/MM/YYYY")

        st.info("💡 A unidade de medida muda automaticamente. Anote fardos ou sacas na 'Observação'.")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                cp, cq, co, cd = st.columns([2.5, 1, 2, 0.5])
                p_sel = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['prod'] = p_sel
                
                unid_lbl = "Qtd"
                if p_sel:
                    unid_lbl = f"Qtd ({df_cat[df_cat['Nome_Produto'] == p_sel]['Unidade_Medida'].values[0]})"

                st.session_state.lista_itens[i]['qtd'] = cq.number_input(unid_lbl, min_value=0.0, key=f"rec_q_{item['id']}")
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
                    st.success("Recebimento Salvo!")
                    st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}] # Limpa pós-salvamento
                    st.rerun()

    # --- 3. CORRIGIR/ADICIONAR EM NOTA ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição Avançada e Filtros")
        df_mov = carregar_dados("db_movimentacoes")
        if 'ids_excluir' not in st.session_state: st.session_state.ids_excluir = []

        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros para Encontrar o Lançamento**")
                c_f1, c_f2 = st.columns(2)
                f_data_edit = c_f1.date_input("Filtrar por Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_tipo_edit = c_f2.multiselect("Filtrar por Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            minhas['Documento_Ref'] = minhas['Documento_Ref'].fillna("S/N").astype(str)
            minhas['Data_Hora'] = minhas['Data_Hora'].fillna("").astype(str)
            minhas['ID_Lote'] = minhas['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            minhas['DT_OBJ'] = pd.to_datetime(minhas['Data_Hora'], dayfirst=True, errors='coerce')

            if len(f_data_edit) == 2:
                minhas = minhas[(minhas['DT_OBJ'].dt.date >= f_data_edit[0]) & (minhas['DT_OBJ'].dt.date <= f_data_edit[1])]
            if f_tipo_edit: 
                minhas = minhas[minhas['Tipo_Fluxo'].isin(f_tipo_edit)]
            
            if not minhas.empty:
                minhas['Label'] = "Nota: " + minhas['Documento_Ref'].astype(str) + " (" + minhas['Data_Hora'].astype(str) + ") - Lote: " + minhas['ID_Lote'].astype(str)
                sel = st.selectbox("Selecione o Lote / Nota Encontrada:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
                
                if sel:
                    lote_id = sel.split("Lote: ")[1]
                    itens = minhas[minhas['ID_Lote'] == lote_id].copy()
                    itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                    trava = st.sidebar.checkbox("🔓 Liberar Exclusão de Itens")
                    novos_v = []
                    
                    for idx, row in itens.reset_index(drop=True).iterrows():
                        is_ex = str(row['ID_Movimentacao']) in st.session_state.ids_excluir
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 1, 1])
                            c1.markdown(f"{'<s>' if is_ex else ''}**Item:** {row['Nome_Produto']}{'</s>' if is_ex else ''}", unsafe_allow_html=True)
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

                    with st.expander("➕ Adicionar Novo Produto a esta Nota"):
                        n_p = st.selectbox("Selecione o Produto", [None] + df_cat['Nome_Produto'].tolist())
                        n_q = st.number_input("Quantidade Inicial", min_value=0.0)
                        if st.button("Confirmar Inclusão na Nota"):
                            if n_p and n_q > 0:
                                cat_n = df_cat[df_cat['Nome_Produto'] == n_p].iloc[0]
                                nova_l = pd.DataFrame([[f"MOV-{lote_id}-ADD{datetime.now().strftime('%S')}", itens.iloc[0]['Data_Hora'], id_escola, "ENTRADA", itens.iloc[0]['Origem'], nome_escola, cat_n['ID_Produto'], n_q, cat_n['Unidade_Medida'], "", user_data['email'], itens.iloc[0]['Documento_Ref']]], 
                                                     columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                                salvar_dados(pd.concat([carregar_dados("db_movimentacoes"), nova_l]), "db_movimentacoes", modo='overwrite')
                                registrar_log(user_data['email'], "ADIÇÃO", itens.iloc[0]['Documento_Ref'], n_p, n_q)
                                st.success("Adicionado!"); st.rerun()

                    if st.button("💾 SALVAR ALTERAÇÕES NESTA NOTA", type="primary", use_container_width=True):
                        # --- MOTOR DE PROTEÇÃO DE ESTOQUE NEGATIVO RETROATIVO ---
                        saldo_atual = calcular_estoque_atual(id_escola)
                        dict_saldos = saldo_atual.set_index('ID_Produto')['Saldo'].to_dict() if not saldo_atual.empty else {}
                        estoque_invalido = False
                        mensagens_erro = []

                        # 1. Verifica se a exclusão total de uma ENTRADA vai negativar a prateleira
                        for mid in st.session_state.ids_excluir:
                            it_del = itens[itens['ID_Movimentacao'] == mid]
                            if not it_del.empty and it_del.iloc[0]['Tipo_Fluxo'] == 'ENTRADA':
                                prod_id = it_del.iloc[0]['ID_Produto']
                                qtd_removida = float(it_del.iloc[0]['Quantidade'])
                                if dict_saldos.get(prod_id, 0) < qtd_removida:
                                    estoque_invalido = True
                                    mensagens_erro.append(f"Excluir a entrada de '{it_del.iloc[0]['Nome_Produto']}' deixará o estoque negativo.")

                        # 2. Verifica se a redução da quantidade de uma ENTRADA vai negativar a prateleira
                        for l_up in novos_v:
                            it_orig = itens[itens['ID_Movimentacao'] == l_up['ID_Movimentacao']]
                            if not it_orig.empty and it_orig.iloc[0]['Tipo_Fluxo'] == 'ENTRADA':
                                qtd_antiga = float(it_orig.iloc[0]['Quantidade'])
                                qtd_nova = float(l_up['Quantidade'])
                                if qtd_nova < qtd_antiga: # Apenas se reduziu a entrada
                                    diferenca = qtd_antiga - qtd_nova
                                    prod_id = l_up['ID_Produto']
                                    if dict_saldos.get(prod_id, 0) < diferenca:
                                        estoque_invalido = True
                                        mensagens_erro.append(f"Reduzir a entrada de '{it_orig.iloc[0]['Nome_Produto']}' deixará o estoque negativo.")

                        if estoque_invalido:
                            for erro in mensagens_erro:
                                st.error(f"🚫 Ação Bloqueada: {erro}")
                            st.warning("Verifique se este produto já não foi consumido ou distribuído.")
                        else:
                            # Se passou pela segurança matemática, prossegue com o salvamento
                            df_full = carregar_dados("db_movimentacoes")
                            ids_nota = [str(x) for x in itens['ID_Movimentacao'].tolist()]
                            
                            for mid in st.session_state.ids_excluir:
                                it_log = itens[itens['ID_Movimentacao'] == mid]
                                if not it_log.empty: registrar_log(user_data['email'], "EXCLUSÃO", it_log.iloc[0]['Documento_Ref'], it_log.iloc[0]['Nome_Produto'], it_log.iloc[0]['Quantidade'])

                            df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_nota)]
                            df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label', 'ID_Lote', 'DT_OBJ'], errors='ignore')
                            
                            if salvar_dados(pd.concat([df_r, df_n]).fillna(""), "db_movimentacoes", modo='overwrite'):
                                st.session_state.ids_excluir = []; st.success("Atualizado com Sucesso!"); st.rerun()
            else:
                st.warning("Nenhum lançamento encontrado com os filtros aplicados.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária do Estoque")
        
        saldo_df = calcular_estoque_atual(id_escola)
        c1, c2 = st.columns(2)
        p_u = c1.selectbox("Selecione o Produto utilizado", df_cat['Nome_Produto'].sort_values().tolist())
        cat_u = df_cat[df_cat['Nome_Produto'] == p_u].iloc[0]
        
        s_item = 0.0
        if not saldo_df.empty:
            m = saldo_df[saldo_df['ID_Produto'] == cat_u['ID_Produto']]
            if not m.empty: s_item = m.iloc[0]['Saldo']
        
        c1.info(f"💡 Saldo disponível para uso: **{s_item} {cat_u['Unidade_Medida']}**")
        q_u = c1.number_input(f"Quantidade para Baixa ({cat_u['Unidade_Medida']})", min_value=0.01, max_value=float(s_item) if s_item > 0 else 0.01)
        d_u = c2.date_input("Data da Utilização", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Observação / Destino (Ex: Merenda Manhã)")
        
        if st.button("Confirmar Baixa", type="primary", use_container_width=True):
            if q_u > 0 and q_u <= s_item:
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO", cat_u['ID_Produto'], q_u, cat_u['Unidade_Medida'], o_u, user_data['email'], "USO DIÁRIO"]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.success("Saída Registrada!"); st.rerun()

    # --- 5. RELATÓRIOS OFICIAIS (FILTROS E PDF BLINDADO) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado e Filtrado")
        df_m = carregar_dados("db_movimentacoes")
        if not df_m.empty and 'ID_Escola' in df_m.columns:
            df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros do Relatório**")
                c1, c2 = st.columns(2)
                f_data = c1.date_input("Período de Análise", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_tipo_rel = c2.multiselect("Tipo de Movimentação", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                
                if len(f_data) == 2:
                    df_m = df_m[(df_m['DT_OBJ'].dt.date >= f_data[0]) & (df_m['DT_OBJ'].dt.date <= f_data[1])]
                if f_tipo_rel:
                    df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo_rel)]

            df_m['Lote'] = df_m['ID_Movimentacao'].astype(str).str.split('-').str[1]
            grupos = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False)
            
            for (lote, doc, data, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"📄 **Nota/Documento:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Responsável:** `{resp}`")
                    cols_show = ['Nome_Produto', 'Quantidade']
                    if 'Unidade_Medida' in group.columns: cols_show.append('Unidade_Medida')
                    if 'Observacao' in group.columns: cols_show.append('Observacao')
                    cols_show.append('Tipo_Fluxo')
                    st.dataframe(group[cols_show], use_container_width=True, hide_index=True)

            st.divider()
            c_d1, c_d2 = st.columns(2)
            
            csv = df_m.drop(columns=['DT_OBJ', 'Lote', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            c_d1.download_button("📊 Baixar Excel Detalhado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
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
                pdf.cell(190, 7, limpar_texto_pdf(f"Controle da Unidade: {nome_escola}"), ln=True, align='C')
                pdf.ln(8)
                
                for (lote, doc, data, resp), group in grupos:
                    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240, 240, 240)
                    texto_cabecalho = limpar_texto_pdf(f" NOTA: {doc} | DATA: {data} | RESP: {resp}")
                    pdf.cell(190, 8, texto_cabecalho, 1, 1, 'L', True)
                    
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        nome_p = limpar_texto_pdf(f" {str(r['Nome_Produto'])[:40]}")
                        qtd_p = limpar_texto_pdf(f" {r['Quantidade']}")
                        un_p = limpar_texto_pdf(f" {r.get('Unidade_Medida', '')}")
                        obs_p = limpar_texto_pdf(f" {str(r.get('Observacao', ''))[:30]}")
                        
                        pdf.cell(90, 6, nome_p, 1)
                        pdf.cell(20, 6, qtd_p, 1)
                        pdf.cell(20, 6, un_p, 1)
                        pdf.cell(60, 6, obs_p, 1)
                        pdf.ln()
                    pdf.ln(2)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                c_d2.download_button("📄 Baixar PDF Oficial", pdf_bytes, f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
            else:
                c_d2.warning("Instale 'fpdf' para gerar o PDF.")
