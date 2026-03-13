# --- BANCO DE DADOS DE USUÁRIOS E PERMISSÕES ---
# Senha padrão inicial: JNL2026 (Recomende que alterem no primeiro acesso)
USUARIOS = {
    "arthur": {"senha": "32167308", "nome": "ARTHUR", "setores": "ALL"},
    "felipe": {"senha": "JNL2026", "nome": "FELIPE", "setores": "ALL"},
    "pedro": {"senha": "JNL2026", "nome": "PEDRO", "setores": "ALL"},
    "jessica": {"senha": "JNL2026", "nome": "JÉSSICA", "setores": ["ADMINISTRATIVO", "FINANCEIRO"]},
    "emanoel": {"senha": "JNL2026", "nome": "EMANOEL", "setores": ["ESTOQUE"]},
    "gabriel": {"senha": "JNL2026", "nome": "GABRIEL", "setores": ["ESTOQUE"]},
    "lays": {"senha": "JNL2026", "nome": "LAYS", "setores": ["ADMINISTRATIVO", "FATURAMENTO"]},
    "guilherme": {"senha": "JNL2026", "nome": "GUILHERME", "setores": ["COMPRAS"]},
    "milene": {"senha": "JNL2026", "nome": "MILENE", "setores": ["SOLUÇÕES CORPORATIVAS"]},
    "thauane": {"senha": "JNL2026", "nome": "THAUANE", "setores": ["SOLUÇÕES CORPORATIVAS"]},
    "kamilly": {"senha": "JNL2026", "nome": "KAMILLY", "setores": ["SOLUÇÕES CORPORATIVAS"]},
    "kaique": {"senha": "JNL2026", "nome": "KAIQUE", "setores": ["SOLUÇÕES CORPORATIVAS"]},
    "karina": {"senha": "JNL2026", "nome": "KARINA", "setores": ["VENDAS"]},
    "gustavo": {"senha": "JNL2026", "nome": "GUSTAVO", "setores": ["VENDAS"]},
    "manoel": {"senha": "JNL2026", "nome": "MANOEL", "setores": ["VENDAS"]},
    "carol": {"senha": "JNL2026", "nome": "CAROL", "setores": ["RH"]}
}

# --- LÓGICA DE SELEÇÃO DE SETOR (FILTRADA) ---
elif st.session_state["setor"] is None:
    verificar_alertas()
    user_key = st.session_state["user_slug"]
    nome_exibicao = USUARIOS[user_key]["nome"]
    
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo, {nome_exibicao}.")
    st.subheader("Selecione o setor para acessar o painel:")

    # Lista mestra de setores
    setores_base = ["ADMINISTRATIVO", "FINANCEIRO", "FATURAMENTO", "VENDAS", "COMPRAS", "ESTOQUE", "SOLUÇÕES CORPORATIVAS", "PROJETOS/IMPORTAÇÃO", "RH", "GERAL"]
    
    # Filtro de Permissão
    permissoes = USUARIOS[user_key]["setores"]
    if permissoes == "ALL":
        setores_visiveis = setores_base
    else:
        setores_visiveis = [s for s in setores_base if s in permissoes]

    cols = st.columns(3)
    for i, s in enumerate(setores_visiveis):
        with cols[i % 3]:
            if st.button(s, use_container_width=True, key=f"btn_{s}"):
                st.session_state["setor"] = s
                st.rerun()