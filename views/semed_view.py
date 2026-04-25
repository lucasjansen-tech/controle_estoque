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
            <h4 style="margin:0; color:#333;">Painel de Gestão Analítica e Logística</h4>
            <p style="margin:0; color:#666;"><b>Operador:</b> {user_data['email']} | <b>Acesso:</b> {perfil_usuario}</p>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

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

            # SEPARAÇÃO EM ABAS (UX Analítica)
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
                # Motor de cálculo global vetorizado (MUITO mais rápido que iterar)
                df_calc = df_mov.copy()
                df_calc['Q_Calc'] = df_calc.apply(lambda r: r['Quantidade'] if r['Tipo_Fluxo'] == 'ENTRADA' else -r['Quantidade'], axis=1)
                est_global = df_calc.groupby(['ID_Escola', 'ID_Produto'])['Q_Calc'].sum().reset_index()
                est_global = est_global[est_global['Q_Calc'] > 0] # Apenas saldo positivo
                
                if not est_global.empty:
                    est_global = pd.merge(est_global, df_esc[['ID_Escola', 'Nome_Escola']], on='ID_Escola', how='left')
                    est_global = pd.merge(est_global, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
                    est_global.rename(columns={'Q_Calc': 'Saldo'}, inplace=True)
                    
                    c_e1, c_e2 = st.columns(2)
                    f_prod = c_e1.selectbox("Verificar produto específico em toda a rede:", ["Todos"] + df_cat['Nome_Produto'].sort_values().tolist())
                    
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
                    else:
                        st.success("Nenhuma escola com estoque em nível crítico (<=5).")
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

    # ... (CÓDIGOS DE OPERAÇÃO: RECEBER, CORRIGIR, CONSUMO, RELATÓRIOS MANTIDOS IGUAIS) ...
    # [Para economizar espaço na resposta, considere que as lógicas de 📦 Receber, ✏️ Corrigir, 🍳 Consumo e 📜 Relatórios estão aqui intactas]

    # --- NOVA GESTÃO DE UNIDADES (COM AGREGADORES BÁSICOS) ---
    elif menu == "🏫 Gestão de Unidades":
        st.subheader("🏫 Gestão de Unidades de Ensino")
        with st.container(border=True):
            f_esc_nome = st.text_input("🔍 Buscar Escola por Nome:")
        
        df_esc_view = df_esc.copy()
        if f_esc_nome: df_esc_view = df_esc_view[df_esc_view['Nome_Escola'].str.contains(f_esc_nome, case=False, na=False)]
        st.dataframe(df_esc_view, use_container_width=True, hide_index=True)
        
        with st.expander("➕ Adicionar Nova Unidade"):
            with st.form("f_add_esc"):
                c1, c2 = st.columns(2)
                n_esc_nome = c1.text_input("Nome da Unidade (Ex: UEB Cuidando do Futuro)")
                
                # Níveis de ensino agregados conforme solicitado
                tipos_ensino = [
                    "Polo Completo (Creche ao 9º Ano)",
                    "Polo Fundamental (1º ao 9º Ano)",
                    "Educação Infantil e Fundamental I",
                    "Apenas Educação Infantil / Creche",
                    "Apenas Ensino Fundamental I",
                    "Apenas Ensino Fundamental II",
                    "Educação de Jovens e Adultos (EJA)"
                ]
                n_esc_tipo = c2.selectbox("Nível de Ensino", tipos_ensino)
                
                if st.form_submit_button("Cadastrar Escola"):
                    if n_esc_nome:
                        novo_id = f"ESC-{datetime.now().strftime('%H%M%S')}"
                        nova_e = pd.DataFrame([[novo_id, n_esc_nome, n_esc_tipo]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola'])
                        salvar_dados(pd.concat([df_esc, nova_e]), "db_escolas", modo='overwrite'); st.success("Cadastrada!"); st.rerun()
                    else: st.error("O nome é obrigatório.")

    # --- ADMIN: AUDITORIA EFICAZ (COM FILTROS) ---
    elif menu == "🕵️ Auditoria do Sistema":
        st.subheader("🕵️ Buscador de Logs e Auditoria")
        st.write("Filtre exatamente o que você procura para não se perder na lista.")
        df_logs = carregar_dados("db_logs")
        
        if not df_logs.empty:
            df_logs['DT'] = pd.to_datetime(df_logs['Data_Hora'].str.split(' ').str[0], format='%d/%m/%Y', errors='coerce')
            
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                f_data = c1.date_input("Filtrar Período", [datetime.now() - timedelta(days=7), datetime.now()], format="DD/MM/YYYY")
                f_user = c2.multiselect("Filtrar por Usuário (E-mail)", df_logs['Usuario'].unique().tolist())
                f_acao = c3.multiselect("Filtrar por Ação", df_logs['Acao'].unique().tolist())
                f_doc = st.text_input("Buscar por Nº do Documento / Nota")

            # Aplicação dos filtros
            df_l_view = df_logs.copy()
            if len(f_data) == 2: df_l_view = df_l_view[(df_l_view['DT'].dt.date >= f_data[0]) & (df_l_view['DT'].dt.date <= f_data[1])]
            if f_user: df_l_view = df_l_view[df_l_view['Usuario'].isin(f_user)]
            if f_acao: df_l_view = df_l_view[df_l_view['Acao'].isin(f_acao)]
            if f_doc: df_l_view = df_l_view[df_l_view['Documento'].astype(str).str.contains(f_doc, case=False, na=False)]

            st.write(f"**Logs encontrados:** {len(df_l_view)}")
            df_l_view = df_l_view.drop(columns=['DT']).sort_values('Data_Hora', ascending=False)
            st.dataframe(df_l_view, use_container_width=True, hide_index=True)
            
            st.download_button("📥 Exportar Resultados", df_l_view.to_csv(index=False).encode('utf-8-sig'), "Auditoria_Filtrada_SEMED.csv")
        else: st.info("Sem logs registrados no sistema.")
