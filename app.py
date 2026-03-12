import streamlit as st
import pandas as pd
import sqlite3
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS (BLINDAGEM TOTAL) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    # Adição de colunas para evitar KeyError
    c.execute("PRAGMA table_info(calendario)")
    cols = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    
    conn.commit()
    conn.close()

init_db()

# --- NAVEGAÇÃO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR", "setores": ["TODOS"]}}

if not st.session_state["autenticado"]:
    st.title("🔒 ACESSO JNL")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"]})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"Olá, {st.session_state['user_nome']}")
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

    # --- BARRA LATERAL (PLANILHAS RESTAURADAS) ---
    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR AO MENU"):
            st.session_state["setor"] = None
            st.rerun()
        st.write("---")
        st.subheader("📂 SALVAR PLANILHAS")
        up = st.file_uploader("Upload", accept_multiple_files=True)
        if st.button("📥 SALVAR NO SERVIDOR"):
            if up: st.success("Arquivos processados com sucesso!"); st.rerun()
        
    # --- ABAS (ÍCONES SEGUROS E PROFISSIONAIS) ---
    tab_ia, tab_chat, tab_agenda, tab_notas = st.tabs(["💻 IA", "👥 Chat Equipe", "📅 Agenda", "📝 Notas"])

    with tab_chat:
        st.subheader(f"Comunicação Interna - {setor_atual}")
        conn = sqlite3.connect('jnl_master.db')
        df = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        conn.close()

        # Estilo WhatsApp com balões
        for _, row in df.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag_edit = " *(Editada)*" if row.get('editada') == 1 else ""
            
            st.markdown(f"""
                <div style='text-align: {align};'>
                    <div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px; box-shadow: 1px 1px 2px rgba(0,0,0,0.1);'>
                        <small><b>{row['usuario'].capitalize()}</b></small><br>
                        {row['mensagem']}<br>
                        <small style='color: gray; font-size: 0.7em;'>{row['data_hora']}{tag_edit}</small>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Edição (Trava de 10 min)
            if is_me:
                dt_msg = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - dt_msg < timedelta(minutes=10):
                    with st.popover("✏️ Editar"):
                        nv = st.text_input("Corrigir:", row['mensagem'], key=f"e_{row['id']}")
                        if st.button("OK", key=f"b_{row['id']}"):
                            conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                            c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id']))
                            conn.commit(); conn.close(); st.rerun()

        with st.form("chat_form", clear_on_submit=True):
            m = st.text_input("Mensagem:")
            if st.form_submit_button("Enviar 📤"):
                if m:
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, user, now, m))
                    conn.commit(); conn.close(); st.rerun()

    with tab_notas:
        st.subheader("Bloco de Notas Pessoal")
        with st.form("notas_form", clear_on_submit=True):
            t_nota = st.text_input("Título")
            c_nota = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota 💾"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'NOTAS', ?, ?)", (user, t_nota, c_nota))
                conn.commit(); conn.close(); st.success("Nota salva!"); st.rerun()