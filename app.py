import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS perfil_usuario (usuario TEXT PRIMARY KEY, nome_tratamento TEXT, instrucoes_ia TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- TEMPO BRASÍLIA ---
def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def obter_saudacao():
    hora = get_now_br().hour
    if 5 <= hora < 12: return "Bom dia"
    elif 12 <= hora < 18: return "Boa tarde"
    else: return "Boa noite"

# --- LOGIN ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "mensagens_ia" not in st.session_state: st.session_state["mensagens_ia"] = []

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR"}}

if not st.session_state["autenticado"]:
    st.title("🔒 ACESSO JNL")
    u = st.text_input("Usuário:").lower()
    p = st.text_input("Senha:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo ao Centro de Comando JNL.")
    setores = ["ADMINISTRATIVO", "FINANCEIRO", "VENDAS", "COMPRAS", "SOLUÇÕES CORPORATIVAS", "GERAL"]
    cols = st.columns(3)
    for i, s in enumerate(setores):
        with cols[i % 3]:
            if st.button(s, use_container_width=True):
                st.session_state["setor"] = s
                st.rerun()
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]

    # --- MEMÓRIA DA IA ---
    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
    c.execute("SELECT nome_tratamento, instrucoes_ia FROM perfil_usuario WHERE usuario = ?", (user,))
    perfil = c.fetchone()
    nome_ia = perfil[0] if perfil else "Senhor"
    inst_ia = perfil[1] if perfil else ""
    conn.close()

    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR"): st.session_state["setor"] = None; st.rerun()
        st.write("---")
        with st.expander("⚙️ MEU PERFIL"):
            n_nome = st.text_input("Como a IA te chama?", value=nome_ia)
            n_inst = st.text_area("Instruções Fixas:", value=inst_ia)
            if st.button("💾 Salvar"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO perfil_usuario (usuario, nome_tratamento, instrucoes_ia) VALUES (?, ?, ?)", (user, n_nome, n_inst))
                conn.commit(); conn.close(); st.rerun()

    tab_ia, tab_chat, tab_agenda, tab_notes = st.tabs(["💬 IA JNL", "👥 EQUIPE", "📅 AGENDA", "📝 NOTAS"])

    with tab_ia:
        st.subheader(f"Assistente JNL - {obter_saudacao()}, {nome_ia}")
        for msg in st.session_state["mensagens_ia"]:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
        if prompt := st.chat_input("Fale com o sistema..."):
            st.session_state["mensagens_ia"].append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                try:
                    ctx = f"Você é o assistente da JNL. Usuário: {nome_ia}. Instruções: {inst_ia}"
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": ctx}] + st.session_state["mensagens_ia"]).choices[0].message.content
                    st.markdown(resp); st.session_state["mensagens_ia"].append({"role": "assistant", "content": resp})
                except: st.error("Erro na Groq Key.")

    with tab_chat:
        st.subheader("Chat do Setor")
        conn = sqlite3.connect('jnl_master.db')
        df_c = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        for _, row in df_c.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag = " *(Editada)*" if row.get('editada') == 1 else ""
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px;'><b>{row['usuario'].upper()}</b><br>{row['mensagem']}<br><small style='color: gray;'>{row['data_hora']}{tag}</small></div></div>", unsafe_allow_html=True)
            if is_me:
                with st.popover("✏️"):
                    nv = st.text_input("Editar:", row['mensagem'], key=f"c_{row['id']}")
                    if st.button("Ok", key=f"b_{row['id']}"):
                        c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id'])); conn.commit(); st.rerun()
        
        with st.form("f_chat", clear_on_submit=True):
            m = st.text_input("Mensagem:")
            if st.form_submit_button("Enviar"):
                if m:
                    c = conn.cursor(); agora = get_now_br().strftime('%d/%m %H:%M')
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, user, agora, m))
                    conn.commit(); st.rerun()
        conn.close()

    with tab_agenda:
        st.subheader("Agenda de Ações")
        with st.form("age_form"):
            t_age = st.text_input("Título")
            col1, col2 = st.columns(2)
            d_age = col1.date_input("Data")
            h_age = col2.time_input("Hora")
            p_age = st.text_input("Para")
            if st.form_submit_button("AGENDAR"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios) VALUES (?, ?, ?, 0, ?, '')", (user, t_age, f"{d_age} {h_age}", p_age))
                conn.commit(); conn.close(); st.rerun()

        st.write("---")
        conn = sqlite3.connect('jnl_master.db')
        df_res = pd.read_sql_query("SELECT * FROM calendario WHERE usuario = ?", conn, params=(user,))
        for _, r in df_res.iterrows():
            dt_limite = datetime.strptime(r['data_hora'], '%Y-%m-%d %H:%M:%S')
            status = "🔴 VENCIDO" if dt_limite < get_now_br() else "🟢 NO PRAZO"
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{r['titulo']}** | {status}")
                c1.write(f"📅 {r['data_hora']} | ✉️ {r['destinatarios']}")
                if c2.button("🗑️", key=f"da_{r['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM calendario WHERE id = ?", (r['id'],)); conn.commit(); st.rerun()
        conn.close()

    with tab_notes:
        st.subheader("Bloco de Notas")
        with st.form("nota_form", clear_on_submit=True):
            tn = st.text_input("Título")
            cn = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, titulo, conteudo) VALUES (?, ?, ?)", (user, tn, cn))
                conn.commit(); conn.close(); st.rerun()
        
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
        for _, n in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{n['titulo']}**")
                st.write(n['conteudo'])
                with st.expander("📝 Editar"):
                    ut = st.text_input("Título", n['titulo'], key=f"ut_{n['id']}")
                    uc = st.text_area("Conteúdo", n['conteudo'], key=f"uc_{n['id']}")
                    if st.button("Salvar Alterações", key=f"usb_{n['id']}"):
                        c = conn.cursor(); c.execute("UPDATE anotacoes SET titulo = ?, conteudo = ? WHERE id = ?", (ut, uc, n['id'])); conn.commit(); st.rerun()
                if st.button("🗑️ Apagar", key=f"udn_{n['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (n['id'],)); conn.commit(); st.rerun()
        conn.close()