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
    """Garante a rastreabilidade das ações no sistema"""
    log_data = pd.DataFrame([[datetime.now().strftime('%d/%m/%Y %H:%M:%S'), usuario, acao, doc, produto, qtd]], 
                            columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def limpar_texto_pdf(texto):
    """Higieniza o texto removendo emojis e caracteres que causam crash no FPDF"""
    if pd.isna(texto) or texto is None: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def renderizar_semed():
    user_data = st.session_state['usuario_dados']
    email_logado = user_data.get('email', str(user_data.get('Email', ''))).strip()
    perfil_bruto = user_data.get('perfil', user_data.get('Perfil', ''))
    perfil_usuario = str(perfil_bruto).strip().upper()
    
    # --- DETECÇÃO DO ADMIN MASTER (st.secrets) ---
    eh_admin_master = False
    try:
        for k, v in st.secrets.items():
            if isinstance(v, str) and v == email_logado:
                eh_admin_master = True
            elif isinstance(v, dict):
                for sub_v in v.values():
                    if isinstance(sub_v, str) and sub_v == email_logado:
                        eh_admin_master = True
    except Exception:
        pass

    if eh_admin_master:
        perfil_usuario = 'ADMIN'
    elif not perfil_usuario or perfil_usuario == 'NONE':
        perfil_usuario = 'COORDENADOR' 

    df_esc = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    df_mov = carregar_dados("db_movimentacoes")
    df_usuarios = carregar_dados("db_usuarios")

    # --- PROTEÇÃO CONTRA KEYERROR E TYPEERROR ---
    if not df_esc.empty and 'Tipo_Escola' not in df_esc.columns:
        df_esc['Tipo_Escola'] = "Polo Fundamental (1º ao 9º Ano)"
        
    if not df_mov.empty and 'Quantidade' in df_mov.columns:
        df_mov['Quantidade'] = pd.to_numeric(df_mov['Quantidade'], errors='coerce').fillna(0)

    # --- CABEÇALHO INSTITUCIONAL ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 24px; font-weight: bold;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 24px; font-weight: bold;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h4 style="margin:0; color:#333;">Painel de Gestão Analítica e Logística</h4>
            <p style="margin:0; color:#666;"><b>Operador:</b> {email_logado} | <b>Acesso Reconhecido:</b> {perfil_usuario}</p>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    # --- MENU DINÂMICO (CONTROLE RIGOROSO DE ACESSOS) ---
    opcoes_menu = [
        "📊 Visão Geral da Rede", 
        "🏫 Raio-X por Escola", 
        "📦 Operação: Receber Materiais",
        "✏️ Operação: Corrigir Nota",
        "🍳 Operação: Consumo Escolar",
        "📜 Relatórios Globais"
    ]
    
    if perfil_usuario in ['ADMIN', 'ADMINISTRADOR']:
        opcoes_menu.extend([
            "🏫 Gestão de Unidades",
            "👥 Gestão de Usuários", 
            "⚙️ Gerenciar Catálogo", 
            "🕵️ Auditoria do Sistema"
        ])

    menu = st.sidebar.radio("Navegação SEMED", opcoes_menu)

    # --- LIMPADOR DE SESSÃO FANTASMA (UX) ---
    if 'menu_anterior_semed' not in st.session_state:
        st.session_state.menu_anterior_semed = menu
    if st.session_state.menu_anterior_semed != menu:
        if 'itens_semed' in st.session_state: st.session_state.itens_semed = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]
        if 'idx_ex_sem' in st.session_state: st.session_state.idx_ex_sem = []
        st.session_state.menu_anterior_semed = menu

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados da Rede", use_container_width=True):
        st.cache_data.clear(); st.rerun()

    # --- 1. VISÃO GERAL DA REDE (DASHBOARDS ANALÍTICOS) ---
    if menu == "📊 Visão Geral da Rede":
        st.subheader("📊 Panorama Logístico da Rede")
        if not df_mov.empty:
            df_mov['DT_OBJ'] = pd.to_datetime(df_mov['Data_Hora'], dayfirst=True, errors='coerce')
            
            c_f1, c_f2 = st.columns(2)
            dias_filtro = c_f1.selectbox("Período Base", ["Últimos 30 dias", "Últimos 7 dias", "Todo o período"])
            esc_filtro = c_f2.multiselect("Filtrar Escolas Específicas", df_esc['Nome_Escola'].tolist())
            
            df_dash = df_mov.copy()
            if dias_filtro == "Últimos 30 dias": df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=30))]
            elif dias_filtro == "Últimos 7 dias": df_dash = df_dash[df_dash['DT_OBJ'] >= (datetime.now() - timedelta(days=7))]
            
            if esc_filtro:
                ids_f = df_esc[df_esc['Nome_Escola'].isin(esc_filtro)]['ID_Escola'].tolist()
                df_dash = df_dash[df_dash['ID_Escola'].isin(ids_f)]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Unidades Analisadas", len(esc_filtro) if esc_filtro else len(df_esc))
            c2.metric("Total de Registros", len(df_dash))
            c3.metric("Lotes de Entrada", len(df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']))
            c4.metric("Baixas Registradas", len(df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']))
            st.divider()

            tab_fluxo, tab_estoque = st.tabs(["📈 Fluxo de Lançamentos", "🚨 Monitoramento de Estoque"])
            
            with tab_fluxo:
                col_g1, col_g2 = st.columns(2)
                with col_g1.container(border=True):
                    st.markdown("**📉 Escolas que MENOS Receberam (Entradas)**")
                    entradas = df_dash[df_dash['Tipo_Fluxo'] == 'ENTRADA']
                    if not entradas.empty:
                        menos_rec = entradas.groupby('Destino')['Quantidade'].sum().sort_values(ascending=True).head(5)
                        st.bar_chart(menos_rec, color="#ff4b4b")
                    else: st.info("Sem dados de entrada no período.")

                with col_g2.container(border=True):
                    st.markdown("**🔥 Top Consumo (Saídas)**")
                    saidas = df_dash[df_dash['Tipo_Fluxo'] == 'SAÍDA']
                    if not saidas.empty:
                        mais_uso = saidas.groupby('Destino')['Quantidade'].sum().sort_values(ascending=False).head(5)
                        st.bar_chart(mais_uso, color="#0068c9")
                    else: st.info("Sem dados de saída no período.")

            with tab_estoque:
                st.markdown("**Visão Global do Estoque Atual (Todas as Escolas)**")
                df_calc = df_mov.copy()
                df_calc['Q_Calc'] = df_calc.apply(lambda r: r['Quantidade'] if r['Tipo_Fluxo'] == 'ENTRADA' else -r['Quantidade'], axis=1)
                est_global = df_calc.groupby(['ID_Escola', 'ID_Produto'])['Q_Calc'].sum().reset_index()
                est_global = est_global[est_global['Q_Calc'] > 0]
                
                if not est_global.empty:
                    est_global = pd.merge(est_global, df_esc[['ID_Escola', 'Nome_Escola']], on='ID_Escola', how='left')
                    est_global = pd.merge(est_global, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
                    est_global.rename(columns={'Q_Calc': 'Saldo'}, inplace=True)
                    
                    c_e1, c_e2 = st.columns(2)
                    f_prod = c_e1.selectbox("Verificar produto específico na rede:", ["Todos"] + df_cat['Nome_Produto'].sort_values().tolist())
                    
                    if f_prod != "Todos":
                        est_view = est_global[est_global['Nome_Produto'] == f_prod].sort_values('Saldo', ascending=False)
                        st.bar_chart(est_view.set_index('Nome_Escola')['Saldo'])
                        st.dataframe(est_view[['Nome_Escola', 'Saldo', 'Unidade_Medida']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Selecione um produto para visualizar a distribuição dele na rede.")
                        
                    st.divider()
                    st.markdown("⚠️ **Alerta de Estoque Baixo (Itens com saldo <= 5)**")
                    alerta_baixo = est_global[est_global['Saldo'] <= 5].sort_values('Saldo')
                    if not alerta_baixo.empty:
                        st.dataframe(alerta_baixo[['Nome_Escola', 'Nome_Produto', 'Saldo', 'Unidade_Medida']], use_container_width=True, hide_index=True)
                    else: st.success("Nenhuma escola com estoque crítico (<=5).")
                else: st.warning("A rede inteira está sem saldo positivo.")
        else: st.warning("Base vazia.")

    # --- 2. RAIO-X POR ESCOLA ---
    elif menu == "🏫 Raio-X por Escola":
        st.subheader("🏫 Situação do Estoque")
        escola_alvo = st.selectbox("Selecione a Unidade:", df_esc['Nome_Escola'].sort_values().tolist())
        id_alvo = df_esc[df_esc['Nome_Escola'] == escola_alvo]['ID_Escola'].values[0]

        saldo_esc = calcular_estoque_atual(id_alvo)
        if not saldo_esc.empty:
            saldo_esc = pd.merge(saldo_esc, df_cat, on='ID_Produto', how='left')
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
                        lista_s.append([f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_alvo, "ENTRADA", origem, escola_alvo, cat['ID_Produto'], it['qtd'], cat['Unidade_Medida'], it['obs'], email_logado, doc_ref])
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
                        # --- MOTOR DE PROTEÇÃO DE ESTOQUE NEGATIVO RETROATIVO ---
                        saldo_atual = calcular_estoque_atual(id_alvo)
                        dict_saldos = saldo_atual.set_index('ID_Produto')['Saldo'].to_dict() if not saldo_atual.empty else {}
                        estoque_invalido = False
                        mensagens_erro = []

                        # Verifica exclusões de entradas
                        for mid in st.session_state.idx_ex_sem:
                            it_del = itens[itens['ID_Movimentacao'] == mid]
                            if not it_del.empty and it_del.iloc[0]['Tipo_Fluxo'] == 'ENTRADA':
                                prod_id = it_del.iloc[0]['ID_Produto']
                                qtd_removida = float(it_del.iloc[0]['Quantidade'])
                                if dict_saldos.get(prod_id, 0) < qtd_removida:
                                    estoque_invalido = True
                                    mensagens_erro.append(f"Excluir a entrada de '{it_del.iloc[0]['Nome_Produto']}' deixará o estoque negativo.")

                        # Verifica reduções de entradas
                        for l_up in novos_v:
                            it_orig = itens[itens['ID_Movimentacao'] == l_up['ID_Movimentacao']]
                            if not it_orig.empty and it_orig.iloc[0]['Tipo_Fluxo'] == 'ENTRADA':
                                qtd_antiga = float(it_orig.iloc[0]['Quantidade'])
                                qtd_nova = float(l_up['Quantidade'])
                                if qtd_nova < qtd_antiga:
                                    diferenca = qtd_antiga - qtd_nova
                                    prod_id = l_up['ID_Produto']
                                    if dict_saldos.get(prod_id, 0) < diferenca:
                                        estoque_invalido = True
                                        mensagens_erro.append(f"Reduzir a entrada de '{it_orig.iloc[0]['Nome_Produto']}' deixará o estoque negativo.")

                        if estoque_invalido:
                            for erro in mensagens_erro:
                                st.error(f"🚫 Ação Bloqueada: {erro}")
                            st.warning("Verifique se este produto já não foi consumido na unidade.")
                        else:
                            df_full = carregar_dados("db_movimentacoes")
                            ids_nota = [str(x) for x in itens['ID_Movimentacao'].tolist()]
                            for mid in st.session_state.idx_ex_sem:
                                it_log = itens[itens['ID_Movimentacao'] == mid]
                                if not it_log.empty: registrar_log(email_logado, "EXCLUSÃO_SUPORTE", it_log.iloc[0]['Documento_Ref'], it_log.iloc[0]['Nome_Produto'], it_log.iloc[0]['Quantidade'])
                            df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_nota)]
                            df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label', 'ID_Lote', 'DT_OBJ', 'index'], errors='ignore')
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
        
        c1.info(f"💡 Saldo na {escola_alvo}: **{s_item} {cat_u['Unidade_Medida']}**")
        q_u = c1.number_input(f"Qtd Baixa ({cat_u['Unidade_Medida']})", min_value=0.01, max_value=float(s_item) if s_item > 0 else 0.01)
        d_u = c2.date_input("Data do Consumo", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Finalidade")
        
        if st.button("Confirmar Baixa", type="primary", use_container_width=True):
            if q_u > 0 and q_u <= s_item:
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_alvo, "SAÍDA", escola_alvo, "CONSUMO INTERNO", cat_u['ID_Produto'], q_u, cat_u['Unidade_Medida'], o_u, email_logado, "BAIXA SEMED"]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.success("Baixa Executada!"); st.rerun()

# --- 6. RELATÓRIOS GLOBAIS (VERSÃO FINAL BLINDADA) ---
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
                f_esc = c2.multiselect("Unidades (Vazio = Todas)", df_esc['Nome_Escola'].sort_values().tolist())
                f_tipo = c3.multiselect("Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            # 1. Aplicação de Filtros
            if len(f_data) == 2: df_rel = df_rel[(df_rel['DT_OBJ'].dt.date >= f_data[0]) & (df_rel['DT_OBJ'].dt.date <= f_data[1])]
            if f_tipo: df_rel = df_rel[df_rel['Tipo_Fluxo'].isin(f_tipo)]
            if f_esc: 
                ids_f = df_esc[df_esc['Nome_Escola'].isin(f_esc)]['ID_Escola'].tolist()
                df_rel = df_rel[df_rel['ID_Escola'].isin(ids_f)]

            # 2. Tradutor de E-mail para Nome do Usuário
            dict_nomes_usuarios = {}
            if not df_usuarios.empty and 'Nome' in df_usuarios.columns:
                dict_nomes_usuarios = df_usuarios.set_index('Email')['Nome'].to_dict()
            df_rel['Responsavel'] = df_rel['ID_Usuario'].map(lambda x: dict_nomes_usuarios.get(x, x))

            # 3. Nomenclatura Dinâmica para Arquivos
            str_periodo = f"{f_data[0].strftime('%d-%m-%Y')}_a_{f_data[1].strftime('%d-%m-%Y')}" if len(f_data) == 2 else "Geral"
            if f_esc and len(f_esc) == 1:
                nome_arq = f"Relatorio_{limpar_texto_pdf(f_esc[0]).replace(' ', '_')}_{str_periodo}"
            else:
                nome_arq = f"Relatorio_SEMED_{str_periodo}"

            df_rel['Lote'] = df_rel['ID_Movimentacao'].astype(str).str.split('-').str[1].fillna("0")
            df_rel = df_rel.sort_values(by=['Destino', 'DT_OBJ'], ascending=[True, False])
            
            escolas_presentes = df_rel['Destino'].unique()
            st.write(f"**Escolas encontradas:** {len(escolas_presentes)}")
            st.divider()

            for escola in escolas_presentes:
                st.markdown(f"<h3 style='color:#004a99;'>🏫 {escola}</h3>", unsafe_allow_html=True)
                df_escola = df_rel[df_rel['Destino'] == escola]
                grupos = df_escola.groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'Responsavel'], sort=False)
                
                for (lote, doc, data, resp), group in grupos:
                    with st.container(border=True):
                        st.markdown(f"📄 **Nota:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Resp:** `{resp}`")
                        st.dataframe(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Observacao', 'Tipo_Fluxo']], use_container_width=True, hide_index=True)

            c_d1, c_d2 = st.columns(2)
            csv_f = df_rel.drop(columns=['DT_OBJ', 'Lote', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            c_d1.download_button("📊 Baixar Excel", csv_f, f"{nome_arq}.csv", use_container_width=True)
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                try: pdf.image("Banner.png", x=10, y=10, w=190); pdf.set_y(50) 
                except: pdf.set_y(10)
                pdf.set_font("Arial", 'B', 14); pdf.cell(190, 8, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.cell(190, 8, "SECRETARIA MUNICIPAL DE EDUCACAO - SEMED", ln=True, align='C')
                pdf.set_font("Arial", '', 11); pdf.cell(190, 7, limpar_texto_pdf(f"Exportação: {nome_arq.replace('_', ' ')}"), ln=True, align='C'); pdf.ln(8)
                
                for escola in escolas_presentes:
                    pdf.set_font("Arial", 'B', 11); pdf.set_fill_color(200, 220, 255)
                    pdf.cell(190, 8, limpar_texto_pdf(f" UNIDADE: {escola}"), 1, 1, 'C', True); pdf.ln(3)
                    df_escola = df_rel[df_rel['Destino'] == escola]
                    grupos_pdf = df_escola.groupby(['Lote', 'Documento_Ref', 'Data_Hora', 'Responsavel'], sort=False)
                    for (lote, doc, data, resp), group in grupos_pdf:
                        pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240, 240, 240)
                        pdf.cell(190, 8, limpar_texto_pdf(f" NOTA: {doc} | DATA: {data} | RESP: {resp}"), 1, 1, 'L', True)
                        pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(255, 255, 255)
                        pdf.cell(90, 7, " Produto", 1); pdf.cell(20, 7, " Qtd", 1); pdf.cell(20, 7, " Unid", 1); pdf.cell(60, 7, " Obs", 1); pdf.ln()
                        pdf.set_font("Arial", '', 8)
                        for _, r in group.iterrows():
                            pdf.cell(90, 6, limpar_texto_pdf(f" {str(r['Nome_Produto'])[:40]}"), 1)
                            pdf.cell(20, 6, str(r['Quantidade']), 1); pdf.cell(20, 6, limpar_texto_pdf(r.get('Unidade_Medida', '')), 1)
                            pdf.cell(60, 6, limpar_texto_pdf(str(r.get('Observacao', ''))[:30]), 1); pdf.ln()
                        pdf.ln(4)
                c_d2.download_button("📄 Baixar PDF Oficial", pdf.output(dest='S').encode('latin-1'), f"{nome_arq}.pdf", "application/pdf", use_container_width=True)

    # --- 7. ADMIN: GESTÃO DE UNIDADES ---
    elif menu == "🏫 Gestão de Unidades":
        st.subheader("🏫 Gestão de Unidades de Ensino")
        
        tipos_ensino = [
            "Polo Completo (Creche ao 9º Ano)", "Polo Fundamental (1º ao 9º Ano)",
            "Educação Infantil e Fundamental I", "Apenas Educação Infantil / Creche",
            "Apenas Ensino Fundamental I", "Apenas Ensino Fundamental II", "Educação de Jovens e Adultos (EJA)"
        ]
        
        with st.container(border=True):
            f_esc_nome = st.text_input("🔍 Buscar Escola por Nome:")
        
        df_esc_view = df_esc.copy()
        if f_esc_nome: df_esc_view = df_esc_view[df_esc_view['Nome_Escola'].str.contains(f_esc_nome, case=False, na=False)]
        st.dataframe(df_esc_view, use_container_width=True, hide_index=True)
        
        tab_add, tab_edit = st.tabs(["➕ Adicionar Escola", "✏️ Editar Escola Existente"])
        
        with tab_add:
            with st.form("f_add_esc"):
                c1, c2 = st.columns(2)
                n_esc_nome = c1.text_input("Nome da Unidade (Ex: UEB Cuidando do Futuro)")
                n_esc_tipo = c2.selectbox("Nível de Ensino", tipos_ensino)
                if st.form_submit_button("Cadastrar Escola"):
                    if n_esc_nome:
                        novo_id = f"ESC-{datetime.now().strftime('%H%M%S')}"
                        nova_e = pd.DataFrame([[novo_id, n_esc_nome, n_esc_tipo]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola'])
                        salvar_dados(pd.concat([df_esc, nova_e]), "db_escolas", modo='overwrite'); st.success("Cadastrada!"); st.rerun()
                    else: st.error("O nome é obrigatório.")
                    
        with tab_edit:
            esc_editar = st.selectbox("Selecione a Escola para Editar", [None] + df_esc['Nome_Escola'].sort_values().tolist())
            if esc_editar:
                dados_esc = df_esc[df_esc['Nome_Escola'] == esc_editar].iloc[0]
                with st.form("f_edit_esc"):
                    st.info(f"Editando o ID: {dados_esc['ID_Escola']}")
                    c1, c2 = st.columns(2)
                    up_nome = c1.text_input("Nome", value=dados_esc['Nome_Escola'])
                    
                    tipo_atual = dados_esc.get('Tipo_Escola', "Apenas Ensino Fundamental I")
                    if pd.isna(tipo_atual): tipo_atual = "Apenas Ensino Fundamental I"
                    idx_t = tipos_ensino.index(tipo_atual) if tipo_atual in tipos_ensino else 0
                    
                    up_tipo = c2.selectbox("Tipo de Ensino", tipos_ensino, index=idx_t)
                    
                    if st.form_submit_button("Salvar Alterações na Escola"):
                        df_esc_resto = df_esc[df_esc['ID_Escola'] != dados_esc['ID_Escola']]
                        df_esc_up = pd.DataFrame([[dados_esc['ID_Escola'], up_nome, up_tipo]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola'])
                        salvar_dados(pd.concat([df_esc_resto, df_esc_up]), "db_escolas", modo='overwrite'); st.success("Atualizado!"); st.rerun()

# --- 8. ADMIN: GESTÃO DE USUÁRIOS ---
    elif menu == "👥 Gestão de Usuários":
        st.subheader("👥 Controle de Acessos e Perfis")
        
        # PREVENÇÃO: Se a coluna Nome não existir na planilha, cria ela como backup
        if not df_usuarios.empty and 'Nome' not in df_usuarios.columns:
            df_usuarios['Nome'] = df_usuarios['Email']
            
        dict_nomes_escolas = {"NENHUMA (Acesso Global)": "NENHUMA (Acesso Global)"}
        if not df_esc.empty:
            for _, row in df_esc.iterrows():
                dict_nomes_escolas[row['ID_Escola']] = row['Nome_Escola']
        
        with st.container(border=True):
            st.markdown("**🔍 Filtros Avançados de Usuário**")
            c_f1, c_f2, c_f3 = st.columns(3)
            f_u_nome = c_f1.text_input("Buscar por Nome ou E-mail")
            f_u_perfil = c_f2.selectbox("Filtrar Perfil", ["Todos", "ESCOLA", "COORDENADOR", "ADMIN"])
            
            escolas_disp = ["Todas"] + df_esc['Nome_Escola'].tolist()
            f_u_esc = c_f3.selectbox("Filtrar Escola Vinculada", escolas_disp)
        
        df_u_view = df_usuarios.copy()
        
        if f_u_nome: 
            mask_email = df_u_view['Email'].str.contains(f_u_nome, case=False, na=False)
            mask_nome = df_u_view.get('Nome', pd.Series("")).str.contains(f_u_nome, case=False, na=False)
            df_u_view = df_u_view[mask_email | mask_nome]
            
        if f_u_perfil != "Todos": df_u_view = df_u_view[df_u_view['Perfil'] == f_u_perfil]
        if f_u_esc != "Todas":
            id_esc_f = df_esc[df_esc['Nome_Escola'] == f_u_esc]['ID_Escola'].values[0]
            df_u_view = df_u_view[df_u_view['ID_Escola'] == id_esc_f]

        st.markdown(f"**Usuários Ativos ({len(df_u_view)} encontrados):**")
        if 'usr_excluir' not in st.session_state: st.session_state.usr_excluir = []
        trava_u = st.checkbox("🔓 Habilitar Exclusão Rápida")
        
        for idx, u_row in df_u_view.iterrows():
            with st.container(border=True):
                col_u1, col_u2, col_u3, col_u4 = st.columns([2, 1, 2, 1])
                
                # Mostra o Nome em negrito e o e-mail menorzinho embaixo
                nome_exibicao = u_row.get('Nome', u_row['Email'])
                col_u1.markdown(f"**{nome_exibicao}**<br><span style='color:gray;font-size:0.8em;'>{u_row['Email']}</span>", unsafe_allow_html=True)
                col_u2.markdown(f"**Perfil:** `{u_row['Perfil']}`")
                
                nome_esc_vinculo = "Acesso Global"
                if u_row['ID_Escola'] != "NENHUMA (Acesso Global)" and not pd.isna(u_row['ID_Escola']):
                    match_esc = df_esc[df_esc['ID_Escola'] == u_row['ID_Escola']]
                    if not match_esc.empty: nome_esc_vinculo = match_esc.iloc[0]['Nome_Escola']
                
                col_u3.markdown(f"**Vínculo:** {nome_esc_vinculo}")
                if trava_u:
                    if col_u4.button("🗑️ Excluir", key=f"del_u_{u_row['ID_Usuario']}"):
                        df_u_novo = df_usuarios[df_usuarios['ID_Usuario'] != u_row['ID_Usuario']]
                        salvar_dados(df_u_novo, "db_usuarios", modo='overwrite')
                        st.warning("Usuário removido!"); st.rerun()

        tab_u_add, tab_u_edit = st.tabs(["➕ Cadastrar Usuário", "✏️ Editar Credenciais"])
        lista_escolas_u = ["NENHUMA (Acesso Global)"] + df_esc['ID_Escola'].tolist()
        perfis_disp = ["ESCOLA", "COORDENADOR", "ADMIN"]

        with tab_u_add:
            with st.form("f_new_user"):
                c1, c2 = st.columns(2)
                u_nome = c1.text_input("Nome Completo do Responsável")
                u_email = c1.text_input("E-mail (Login)")
                u_senha = c2.text_input("Senha", type="password")
                u_perfil = c2.selectbox("Perfil", perfis_disp)
                u_esc = st.selectbox("Vincular à Escola", lista_escolas_u, format_func=lambda x: dict_nomes_escolas.get(x, str(x)))
                
                if st.form_submit_button("Salvar Usuário"):
                    if u_nome and u_email and u_senha:
                        novo_u = pd.DataFrame([[f"USR-{datetime.now().strftime('%H%M%S')}", u_nome, u_email, u_senha, u_perfil, u_esc]], columns=['ID_Usuario', 'Nome', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola'])
                        salvar_dados(pd.concat([df_usuarios, novo_u]), "db_usuarios", modo='overwrite'); st.success("Cadastrado!"); st.rerun()
                    else: st.error("Preencha Nome, E-mail e Senha.")

        with tab_u_edit:
            usr_ed = st.selectbox("Selecione o Usuário para Alterar", [None] + df_usuarios['Email'].sort_values().tolist())
            if usr_ed:
                dados_usr = df_usuarios[df_usuarios['Email'] == usr_ed].iloc[0]
                with st.form("f_edit_user"):
                    st.info("Para manter a mesma senha, deixe o campo de Nova Senha vazio.")
                    c1, c2 = st.columns(2)
                    up_nome = c1.text_input("Alterar Nome", value=dados_usr.get('Nome', dados_usr['Email']))
                    up_email = c1.text_input("Alterar E-mail", value=dados_usr['Email'])
                    up_senha = c2.text_input("Nova Senha", type="password")
                    
                    idx_p = perfis_disp.index(dados_usr['Perfil']) if dados_usr['Perfil'] in perfis_disp else 0
                    up_perfil = c2.selectbox("Alterar Perfil", perfis_disp, index=idx_p)
                    
                    idx_e = lista_escolas_u.index(dados_usr['ID_Escola']) if dados_usr['ID_Escola'] in lista_escolas_u else 0
                    up_esc = st.selectbox("Alterar Vínculo Escolar", lista_escolas_u, index=idx_e, format_func=lambda x: dict_nomes_escolas.get(x, str(x)))
                    
                    if st.form_submit_button("Atualizar Usuário"):
                        senha_final = up_senha if up_senha else dados_usr['Senha_Hash']
                        df_u_resto = df_usuarios[df_usuarios['ID_Usuario'] != dados_usr['ID_Usuario']]
                        df_u_up = pd.DataFrame([[dados_usr['ID_Usuario'], up_nome, up_email, senha_final, up_perfil, up_esc]], columns=['ID_Usuario', 'Nome', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola'])
                        salvar_dados(pd.concat([df_u_resto, df_u_up]), "db_usuarios", modo='overwrite'); st.success("Usuário atualizado!"); st.rerun()

    # --- 9. ADMIN: GERENCIAR CATÁLOGO ---
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
            if st.button("➕ Adicionar Linha"): st.session_state.lote_cat.append({'id': len(st.session_state.lote_cat)+1, 'cod':'', 'nome':'', 'cat':'Alimentação Seca', 'un':'Kg'}); st.rerun()
            if st.button("✅ SALVAR LOTE", type="primary"):
                novos = [[it['cod'], it['nome'], it['cat'], it['un']] for it in st.session_state.lote_cat if it['cod'] and it['nome']]
                if novos:
                    salvar_dados(pd.concat([df_cat, pd.DataFrame(novos, columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])]), "db_catalogo", modo='overwrite')
                    st.success("Lote salvo!"); st.session_state.lote_cat = [{'id': 0, 'cod':'', 'nome':'', 'cat':'Alimentação Seca', 'un':'Kg'}]; st.rerun()
                else: st.error("Preencha Códigos e Nomes.")

    # --- 10. ADMIN: AUDITORIA ---
    elif menu == "🕵️ Auditoria do Sistema":
        st.subheader("🕵️ Buscador de Logs e Auditoria")
        df_logs = carregar_dados("db_logs")
        if not df_logs.empty:
            df_logs['DT'] = pd.to_datetime(df_logs['Data_Hora'].str.split(' ').str[0], format='%d/%m/%Y', errors='coerce')
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                f_data = c1.date_input("Filtrar Período", [datetime.now() - timedelta(days=7), datetime.now()], format="DD/MM/YYYY")
                f_user = c2.multiselect("Por Usuário (E-mail)", df_logs['Usuario'].unique().tolist())
                f_acao = c3.multiselect("Por Ação", df_logs['Acao'].unique().tolist())
                f_doc = st.text_input("Por Nº da Nota")

            df_l_view = df_logs.copy()
            if len(f_data) == 2: df_l_view = df_l_view[(df_l_view['DT'].dt.date >= f_data[0]) & (df_l_view['DT'].dt.date <= f_data[1])]
            if f_user: df_l_view = df_l_view[df_l_view['Usuario'].isin(f_user)]
            if f_acao: df_l_view = df_l_view[df_l_view['Acao'].isin(f_acao)]
            if f_doc: df_l_view = df_l_view[df_l_view['Documento'].astype(str).str.contains(f_doc, case=False, na=False)]

            st.write(f"**Logs encontrados:** {len(df_l_view)}")
            st.dataframe(df_l_view.drop(columns=['DT']).sort_values('Data_Hora', ascending=False), use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar Resultados", df_l_view.drop(columns=['DT']).to_csv(index=False).encode('utf-8-sig'), "Auditoria_Filtrada_SEMED.csv")
        else: st.info("Sem logs registrados no sistema.")
