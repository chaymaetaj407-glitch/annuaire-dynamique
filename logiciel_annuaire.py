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

@st.cache_data
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    try:
        nb_clients_annuaire = len(df_annuaire)
        st.info(f"📊 {nb_clients_annuaire} clients dans l'Annuaire")

        # 1️⃣ IDENTIFIER CT_Num dans ANNUAIRE
        ct_col_annuaire = next((c for c in df_annuaire.columns if c.lower() in ['ct_num', 'num_ct']), None)
        if not ct_col_annuaire:
            st.error("❌ CT_Num introuvable dans Annuaire")
            return None

        intitule_col_annuaire = next((c for c in df_annuaire.columns if c.lower() in ['ct_intitule', 'intitule']), None)

        # 2️⃣ FILTRER LES NOTES DANS GESTCOM
        ar_ref_col = next((c for c in df_gestcom.columns if c.lower() == 'ar_ref'), None)
        if not ar_ref_col:
            st.warning("⚠️ AR_Ref introuvable, toutes les lignes seront prises.")
            df_gestcom_filtre = df_gestcom.copy()
        else:
            df_gestcom_filtre = df_gestcom[df_gestcom[ar_ref_col].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        st.info(f"🔍 {len(df_gestcom_filtre)} lignes NOTE dans GESTCOM")

        # 3️⃣ IDENTIFIER LES COLONNES CLÉS
        phase_col = next((c for c in df_gestcom_filtre.columns if c.lower() == 'dl_design'), None)
        if not phase_col:
            st.error("❌ DL_Design introuvable dans GESTCOM")
            return None

        ct_col_gestcom = next((c for c in df_gestcom_filtre.columns if c.lower() in ['ct_num', 'num_ct']), None)
        if not ct_col_gestcom:
            st.error("❌ CT_Num introuvable dans GESTCOM")
            return None

        # Nettoyer Phase et CT_Num
        df_gestcom_filtre['Phase_Num'] = (
            df_gestcom_filtre[phase_col]
            .astype(str)
            .str.replace('{note}', '', case=False)
            .str.replace('{NOTE}', '', case=False)
            .str.strip()
            .str.upper()
        )
        df_gestcom_filtre['CT_Num_Clean'] = df_gestcom_filtre[ct_col_gestcom].astype(str).str.strip().str.upper()

        # 4️⃣ PRÉPARER JALIXE
        if 'CptPhase' not in df_jalixe.columns or 'LibTitre' not in df_jalixe.columns:
            st.error("❌ Colonnes 'CptPhase' ou 'LibTitre' manquantes dans JALIXE")
            return None

        df_jalixe_clean = (
            df_jalixe[['CptPhase', 'LibTitre']]
            .dropna(subset=['CptPhase'])
            .copy()
        )
        df_jalixe_clean['CptPhase_Clean'] = df_jalixe_clean['CptPhase'].astype(str).str.strip().str.upper()
        df_jalixe_clean.drop_duplicates(subset=['CptPhase_Clean'], inplace=True)

        st.info(f"📘 JALIXE nettoyé : {len(df_jalixe_clean)} phases uniques")

        # 5️⃣ FUSION GESTCOM + JALIXE (version anti-mélange)
        df_gestcom_filtre['CT_Num_Clean'] = df_gestcom_filtre[ct_col_gestcom].astype(str).str.strip().str.upper()

        # Identifier les phases ambiguës (partagées entre plusieurs CT_Num)
        phases_clients = df_gestcom_filtre.groupby('Phase_Num')['CT_Num_Clean'].nunique().reset_index()
        phases_clients_ambigues = phases_clients[phases_clients['CT_Num_Clean'] > 1]['Phase_Num'].tolist()

        st.warning(f"⚠️ {len(phases_clients_ambigues)} phases apparaissent chez plusieurs clients (ignorées pour éviter le mélange)")

        # Garder uniquement les phases uniques par client
        df_gestcom_uniques = df_gestcom_filtre[~df_gestcom_filtre['Phase_Num'].isin(phases_clients_ambigues)].copy()

        # Fusionner avec JALIXE
        df_gestcom_jalixe = df_gestcom_uniques.merge(
            df_jalixe_clean,
            left_on='Phase_Num',
            right_on='CptPhase_Clean',
            how='left'
        )

        # Nettoyer et dédupliquer
        df_gestcom_jalixe.drop_duplicates(subset=['CT_Num_Clean', 'Phase_Num'], inplace=True)

        nb_correspondances = df_gestcom_jalixe['LibTitre'].notna().sum()
        st.success(f"✅ {nb_correspondances} correspondances GESTCOM–JALIXE valides (sans mélange)")

        # 6️⃣ CRÉER LES TITRES PAR CLIENT
        df_avec_titres = df_gestcom_jalixe[df_gestcom_jalixe['LibTitre'].notna()].copy()
        if not df_avec_titres.empty:
            df_titres = (
                df_avec_titres.groupby('CT_Num_Clean')['LibTitre']
                .apply(lambda x: '; '.join(sorted(set([t.strip() for t in x if isinstance(t, str) and t.strip()]))))
                .reset_index()
                .rename(columns={'LibTitre': 'Titres'})
            )
            st.success(f"🎯 {len(df_titres)} clients distincts avec titres")
        else:
            df_titres = pd.DataFrame(columns=['CT_Num_Clean', 'Titres'])
            st.warning("⚠️ Aucun titre trouvé")

        # 7️⃣ FUSION FINALE AVEC ANNUAIRE
        df_annuaire['CT_Num_Clean'] = df_annuaire[ct_col_annuaire].astype(str).str.strip().str.upper()
        df_final = df_annuaire.merge(df_titres, on='CT_Num_Clean', how='left')
        df_final['Titres'] = df_final['Titres'].fillna('Aucun titre')

        nb_final = len(df_final)
        ecart = nb_final - nb_clients_annuaire
        if ecart == 0:
            st.success(f"✅ Parfait : {nb_final} clients (écart = 0)")
        else:
            st.warning(f"⚠️ {nb_final} lignes après fusion (écart de {ecart})")

        # 8️⃣ ORGANISER LES COLONNES POUR EXPORT
        colonnes_finales = []
        if intitule_col_annuaire:
            colonnes_finales.append(intitule_col_annuaire)
        colonnes_finales += [ct_col_annuaire]

        for col in ['CT_Adresse', 'CT_CodePostal', 'CT_Ville', 'CT_Pays', 'CT_Telephone', 'CT_Email']:
            if col in df_final.columns:
                colonnes_finales.append(col)
        colonnes_finales.append('Titres')

        df_export = df_final[colonnes_finales].copy()
        df_export.rename(columns={
            intitule_col_annuaire: 'Nom',
            ct_col_annuaire: 'num_CT',
            'CT_Adresse': 'Adresse',
            'CT_CodePostal': 'CP',
            'CT_Ville': 'Ville',
            'CT_Pays': 'Pays',
            'CT_Telephone': 'Téléphone',
            'CT_Email': 'Email'
        }, inplace=True)

        nb_avec_titres = (df_export['Titres'] != 'Aucun titre').sum()
        st.info(f"📊 {nb_avec_titres} clients avec titres | {len(df_export) - nb_avec_titres} sans titres")

        return df_export, nb_clients_annuaire, nb_final

    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None


# === INTERFACE STREAMLIT ===
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1️⃣ Annuaire", type=["xlsx", "csv"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2️⃣ GESTCOM", type=["xlsx", "csv"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3️⃣ JALIXE", type=["xlsx", "csv"], key="jalixe")

@st.cache_data
def lire_fichier(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin1', low_memory=False)
    return pd.read_excel(io.BytesIO(file_bytes))

if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement..."):
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

                st.success("✅ Annuaire généré avec succès !")
                st.balloons()
    else:
        st.error("⚠️ Chargez les 3 fichiers avant de lancer le traitement.")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
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
st.sidebar.caption("📋 Version finale corrigée — anti-mélange des titres ✅")
