import streamlit as st
import pandas as pd
from datetime import datetime
import io
from rapidfuzz import process, fuzz

try:
    import openpyxl
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])

st.set_page_config(page_title="Annuaire Dynamique - France Routage", layout="wide")
st.title("📘 Annuaire Dynamique - France Routage")

@st.cache_data
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    try:
        st.info("🔧 Nettoyage et correspondances en cours...")

        # === Colonnes clés ===
        ct_col_annuaire = next((c for c in df_annuaire.columns if c.lower() in ['ct_num', 'num_ct']), None)
        ct_col_gestcom = next((c for c in df_gestcom.columns if c.lower() in ['ct_num', 'num_ct']), None)
        phase_col = next((c for c in df_gestcom.columns if c.lower() == 'dl_design'), None)
        ar_ref_col = next((c for c in df_gestcom.columns if c.lower() == 'ar_ref'), None)

        if not all([ct_col_annuaire, ct_col_gestcom, phase_col]):
            st.error("❌ Colonnes CT_Num ou DL_Design manquantes.")
            return None

        # === Nettoyage des CT_Num et des phases ===
        df_annuaire['CT_Num_Clean'] = df_annuaire[ct_col_annuaire].astype(str).str.strip().str.upper()
        df_gestcom['CT_Num_Clean'] = df_gestcom[ct_col_gestcom].astype(str).str.strip().str.upper()

        # Filtrer sur AR_Ref = NOTE
        if ar_ref_col in df_gestcom.columns:
            df_gestcom = df_gestcom[df_gestcom[ar_ref_col].astype(str).str.upper().str.contains("NOTE", na=False)]

        df_gestcom['Phase_Num'] = (
            df_gestcom[phase_col]
            .astype(str)
            .str.replace('{note}', '', case=False)
            .str.replace('{NOTE}', '', case=False)
            .str.replace(r'[^A-Za-z0-9 ]', '', regex=True)
            .str.strip()
            .str.upper()
        )

        df_jalixe['CptPhase_Clean'] = (
            df_jalixe['CptPhase']
            .astype(str)
            .str.replace(r'[^A-Za-z0-9 ]', '', regex=True)
            .str.strip()
            .str.upper()
        )

        # === Fusion exacte (Phase_Num == CptPhase_Clean) ===
        df_joint = df_gestcom.merge(
            df_jalixe[['CptPhase_Clean', 'LibTitre']],
            left_on='Phase_Num',
            right_on='CptPhase_Clean',
            how='left'
        )

        # === Fuzzy match uniquement pour les phases non trouvées ===
        df_sans_titre = df_joint[df_joint['LibTitre'].isna()].copy()
        df_avec_titre = df_joint.dropna(subset=['LibTitre']).copy()

        if not df_sans_titre.empty:
            st.info("🤖 Fuzzy match sur phases restantes (score ≥ 98%)...")
            phases_jalixe = df_jalixe['CptPhase_Clean'].unique().tolist()
            mapping = {}
            for phase in df_sans_titre['Phase_Num'].unique():
                match = process.extractOne(
                    phase, phases_jalixe, scorer=fuzz.token_sort_ratio
                )
                if match and match[1] >= 98:
                    mapping[phase] = match[0]

            df_sans_titre['Phase_Matched'] = df_sans_titre['Phase_Num'].map(mapping)

            # ✅ Correction du bug de type (float ↔ str)
            df_sans_titre['Phase_Matched'] = df_sans_titre['Phase_Matched'].astype(str)
            df_jalixe['CptPhase_Clean'] = df_jalixe['CptPhase_Clean'].astype(str)

            df_sans_titre = df_sans_titre.merge(
                df_jalixe[['CptPhase_Clean', 'LibTitre']],
                left_on='Phase_Matched',
                right_on='CptPhase_Clean',
                how='left'
            )

            df_joint = pd.concat([df_avec_titre, df_sans_titre], ignore_index=True)

        # === Nettoyage final et suppression des doublons ===
        df_joint = df_joint[df_joint['LibTitre'].notna()]
        df_joint.drop_duplicates(subset=['CT_Num_Clean', 'LibTitre'], inplace=True)

        # === Fusion avec Annuaire pour obtenir infos client ===
        df_final = df_joint.merge(
            df_annuaire,
            on='CT_Num_Clean',
            how='left',
            suffixes=('', '_annuaire')
        )

        # === Sélection des colonnes finales ===
        colonnes_finales = [
            'CT_Num_Clean', ct_col_annuaire, 'LibTitre',
            'CT_Intitule' if 'CT_Intitule' in df_final.columns else None,
            'CT_Adresse' if 'CT_Adresse' in df_final.columns else None,
            'CT_CodePostal' if 'CT_CodePostal' in df_final.columns else None,
            'CT_Ville' if 'CT_Ville' in df_final.columns else None,
            'CT_Pays' if 'CT_Pays' in df_final.columns else None,
            'CT_Telephone' if 'CT_Telephone' in df_final.columns else None,
            'CT_Email' if 'CT_Email' in df_final.columns else None
        ]
        colonnes_finales = [c for c in colonnes_finales if c]
        df_final = df_final[colonnes_finales].drop_duplicates().reset_index(drop=True)
        df_final.rename(columns={'LibTitre': 'Titre'}, inplace=True)

        st.success(f"✅ {len(df_final)} lignes générées (1 client = 1 titre).")

        return df_final, len(df_annuaire), len(df_final)

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


# === INTERFACE STREAMLIT ===
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1️⃣ Annuaire", type=["xlsx", "csv"])
file_gestcom = st.sidebar.file_uploader("2️⃣ GESTCOM", type=["xlsx", "csv"])
file_jalixe = st.sidebar.file_uploader("3️⃣ JALIXE", type=["xlsx", "csv"])

@st.cache_data
def lire_fichier(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin1', low_memory=False)
    return pd.read_excel(io.BytesIO(file_bytes))

if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            df_annuaire = lire_fichier(file_annuaire.read(), file_annuaire.name)
            df_gestcom = lire_fichier(file_gestcom.read(), file_gestcom.name)
            df_jalixe = lire_fichier(file_jalixe.read(), file_jalixe.name)

            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                st.session_state['df_final'] = df_final
                st.success("🎉 Annuaire généré avec succès !")
                st.balloons()
    else:
        st.error("⚠️ Veuillez charger les 3 fichiers avant de lancer le traitement.")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique - Résultat final")
    st.caption(f"🕒 Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.dataframe(df, use_container_width=True, height=500)

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
st.sidebar.caption("Version finale — 1 client = 1 titre ✅")
