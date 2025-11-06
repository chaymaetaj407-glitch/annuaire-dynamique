import streamlit as st
import pandas as pd
from datetime import datetime
import io

try:
    import openpyxl
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])

st.set_page_config(
    page_title="Annuaire Dynamique - France Routage",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📘 Annuaire Dynamique - France Routage")


# === TRAITEMENT DES DONNÉES ===
@st.cache_data
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    try:
        st.info("🔧 Nettoyage et correspondances en cours...")

        # --- Identifier les colonnes clés ---
        ct_col_annuaire = next((c for c in df_annuaire.columns if c.lower() in ['ct_num', 'num_ct']), None)
        ct_col_gestcom = next((c for c in df_gestcom.columns if c.lower() in ['ct_num', 'num_ct']), None)
        ar_ref_col = next((c for c in df_gestcom.columns if c.lower() == 'ar_ref'), None)
        phase_col = next((c for c in df_gestcom.columns if c.lower() == 'dl_design'), None)

        if not all([ct_col_annuaire, ct_col_gestcom, phase_col]):
            st.error("❌ Colonnes manquantes (CT_Num ou DL_Design)")
            return None

        # --- Nettoyer CT_Num ---
        df_annuaire['CT_Num_Clean'] = df_annuaire[ct_col_annuaire].astype(str).str.strip().str.upper()
        df_gestcom['CT_Num_Clean'] = df_gestcom[ct_col_gestcom].astype(str).str.strip().str.upper()

        # --- Filtrer sur AR_Ref = NOTE ---
        if ar_ref_col and 'NOTE' in df_gestcom[ar_ref_col].astype(str).str.upper().unique():
            df_gestcom = df_gestcom[df_gestcom[ar_ref_col].astype(str).str.strip().str.upper() == 'NOTE']
        df_gestcom['Phase_Num'] = (
            df_gestcom[phase_col]
            .astype(str)
            .str.replace('{note}', '', case=False)
            .str.replace('{NOTE}', '', case=False)
            .str.strip()
            .str.upper()
        )

        # --- Nettoyer JALIXE ---
        if not all(c in df_jalixe.columns for c in ['CptPhase', 'LibTitre']):
            st.error("❌ Colonnes 'CptPhase' ou 'LibTitre' manquantes dans JALIXE")
            return None
        df_jalixe['CptPhase_Clean'] = df_jalixe['CptPhase'].astype(str).str.strip().str.upper()

        # --- FUSION TRIANGULAIRE (clé = Phase_Num + CT_Num) ---
        df_joint = df_gestcom.merge(
            df_jalixe[['CptPhase_Clean', 'LibTitre']],
            left_on='Phase_Num',
            right_on='CptPhase_Clean',
            how='left'
        )

        # On relie aussi à l'annuaire (pour sécuriser le CT_Num)
        df_joint = df_joint.merge(
            df_annuaire[['CT_Num_Clean']],
            on='CT_Num_Clean',
            how='inner'
        )

        # --- Nettoyage complet ---
        df_joint.drop_duplicates(subset=['CT_Num_Clean', 'Phase_Num', 'LibTitre'], inplace=True)
        df_joint = df_joint[df_joint['LibTitre'].notna() & (df_joint['LibTitre'].str.strip() != '')]

        # --- Associer les titres par client ---
        df_titres = (
            df_joint.groupby('CT_Num_Clean')['LibTitre']
            .apply(lambda x: '; '.join(sorted(set(x))))
            .reset_index()
        )

        # --- Fusion finale avec l'annuaire ---
        df_final = df_annuaire.merge(df_titres, on='CT_Num_Clean', how='left')
        df_final['LibTitre'] = df_final['LibTitre'].fillna('Aucun titre')

        # --- Résumé ---
        nb_titres = (df_final['LibTitre'] != 'Aucun titre').sum()
        st.success(f"✅ {nb_titres} clients ont des titres valides (chaque titre appartient à son propre client).")

        # --- Préparer pour export ---
        rename_dict = {
            ct_col_annuaire: 'num_CT',
            'LibTitre': 'Titres',
            'CT_Num_Clean': 'CT_Num_Clean'
        }
        df_final.rename(columns=rename_dict, inplace=True)

        return df_final, len(df_annuaire), len(df_final)

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


# === CHARGEMENT DES FICHIERS ===
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1️⃣ Annuaire", type=["xlsx", "csv"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2️⃣ GESTCOM", type=["xlsx", "csv"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3️⃣ JALIXE", type=["xlsx", "csv"], key="jalixe")

@st.cache_data
def lire_fichier(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin1', low_memory=False)
    return pd.read_excel(io.BytesIO(file_bytes))


# === LANCER LE TRAITEMENT ===
if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            file_annuaire.seek(0)
            file_gestcom.seek(0)
            file_jalixe.seek(0)

            df_annuaire = lire_fichier(file_annuaire.read(), file_annuaire.name)
            df_gestcom = lire_fichier(file_gestcom.read(), file_gestcom.name)
            df_jalixe = lire_fichier(file_jalixe.read(), file_jalixe.name)

            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                st.session_state['df_final'] = df_final
                st.session_state['date_maj'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.session_state['nb_annuaire'] = nb_annuaire
                st.session_state['nb_final'] = nb_final

                st.success("🎉 Annuaire généré avec succès !")
                st.balloons()
    else:
        st.error("⚠️ Veuillez charger les 3 fichiers avant de lancer le traitement.")


# === AFFICHAGE DU RÉSULTAT ===
if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique - Résultat final")
    st.caption(f"🕒 Dernière mise à jour : {st.session_state['date_maj']}")

    st.dataframe(df, use_container_width=True, height=500)
    st.info(f"📌 {len(df)} clients affichés")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Annuaire')

    st.download_button(
        label="📥 Exporter en Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


st.sidebar.markdown("---")
st.sidebar.info("✨ Développé par Chaymae Taj 🌸")
st.sidebar.caption("📋 Version finale — Anti-mélange des titres ✅")
