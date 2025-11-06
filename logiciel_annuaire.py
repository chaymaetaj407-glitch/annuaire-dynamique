import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Installation automatique d'openpyxl si nécessaire
try:
    import openpyxl
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])

# Configuration de la page
st.set_page_config(
    page_title="Annuaire Dynamique - France Routage", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📘 Annuaire Dynamique - France Routage")

# Fonction optimisée pour traiter les données
@st.cache_data
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    """
    Traite et fusionne les 3 bases de données selon les règles métier
    VERSION OPTIMISÉE POUR RAPIDITÉ
    """
    try:
        # 1. FILTRE STRICT : AR_Ref = "NOTE"
        if 'AR_Ref' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_Ref'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        elif 'AR_REF' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_REF'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        else:
            st.error("❌ Colonne AR_Ref introuvable dans GESTCOM")
            return None
        
        nb_notes = len(df_gestcom_filtre)
        st.info(f"🔍 **{nb_notes}** lignes avec AR_Ref='NOTE' sur {len(df_gestcom)}")
        
        if nb_notes == 0:
            st.warning("⚠️ Aucune ligne avec AR_Ref='NOTE'")
            return None
        
        # 2. IDENTIFIER COLONNES
        if 'DL_Design' in df_gestcom_filtre.columns:
            phase_col = 'DL_Design'
        elif 'DL_DESIGN' in df_gestcom_filtre.columns:
            phase_col = 'DL_DESIGN'
        else:
            st.error("❌ Colonne DL_DESIGN introuvable")
            return None
        
        if 'CptPhase' not in df_jalixe.columns:
            st.error("❌ Colonne CptPhase introuvable dans JALIXE")
            return None
        
        if 'LibTitre' not in df_jalixe.columns:
            st.error("❌ Colonne LibTitre introuvable dans JALIXE")
            return None
        
        # 3. OPTIMISATION : Extraire uniquement les colonnes nécessaires
        df_jalixe_mini = df_jalixe[['CptPhase', 'LibTitre']].copy()
        df_jalixe_mini['CptPhase'] = df_jalixe_mini['CptPhase'].astype(str).str.strip()
        
        # 4. EXTRAIRE NUMÉRO DE PHASE (enlever {note})
        df_gestcom_filtre['Phase_Num'] = df_gestcom_filtre[phase_col].astype(str).str.replace('{note}', '', case=False).str.replace('{NOTE}', '', case=False).str.strip()
        
        # 5. IDENTIFIER CT_Num
        ct_col_gestcom = None
        for col in df_gestcom_filtre.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_gestcom = col
                break
        
        if not ct_col_gestcom:
            st.error("❌ Colonne CT_Num introuvable dans GESTCOM")
            return None
        
        ct_col_annuaire = None
        for col in df_annuaire.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_annuaire = col
                break
        
        if not ct_col_annuaire:
            st.error("❌ Colonne CT_Num introuvable dans Annuaire")
            return None
        
        # 6. FUSION OPTIMISÉE GESTCOM + JALIXE
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe_mini,
            left_on='Phase_Num',
            right_on='CptPhase',
            how='left'
        )
        
        nb_correspondances = df_gestcom_jalixe['LibTitre'].notna().sum()
        st.success(f"✅ **{nb_correspondances}** correspondances GESTCOM-JALIXE trouvées")
        
        # 7. AGRÉGATION RAPIDE : Concaténer titres par CT_Num
        df_gestcom_jalixe['LibTitre'] = df_gestcom_jalixe['LibTitre'].fillna('')
        
        df_titres = df_gestcom_jalixe[df_gestcom_jalixe['LibTitre'] != ''].groupby(ct_col_gestcom)['LibTitre'].apply(
            lambda x: '; '.join(x.unique())
        ).reset_index()
        df_titres.columns = ['CT_Num_temp', 'Titres']
        
        # 8. FUSION FINALE OPTIMISÉE
        df_final = df_annuaire.merge(
            df_titres,
            left_on=ct_col_annuaire,
            right_on='CT_Num_temp',
            how='left'
        )
        
        df_final['Titres'] = df_final['Titres'].fillna('Aucun titre')
        
        # 9. DÉDUPLIQUER
        df_final = df_final.drop_duplicates(subset=[ct_col_annuaire])
        
        # 10. COLONNES FINALES
        colonnes_finales = []
        
        # Sélectionner colonnes dans l'ordre
        mapping_colonnes = {
            'CT_Intitule': 'Nom Client',
            ct_col_annuaire: 'num_CT',
            'CT_Adresse': 'Adresse',
            'CT_CodePostal': 'CP',
            'CT_Ville': 'Ville',
            'CT_Pays': 'Pays',
            'CT_Telephone': 'Téléphone',
            'CT_Email': 'Email',
            'Titres': 'Titres'
        }
        
        for col_orig, col_new in mapping_colonnes.items():
            if col_orig in df_final.columns:
                colonnes_finales.append(col_orig)
        
        df_final_export = df_final[colonnes_finales].copy()
        
        # Renommer
        rename_dict = {k: v for k, v in mapping_colonnes.items() if k in colonnes_finales}
        df_final_export = df_final_export.rename(columns=rename_dict)
        
        return df_final_export, len(df_annuaire), len(df_final_export)
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

# SIDEBAR
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1. Annuaire", type=["xlsx", "csv"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2. GESTCOM", type=["xlsx", "csv"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3. JALIXE", type=["xlsx", "csv"], key="jalixe")

@st.cache_data
def lire_fichier(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin1', low_memory=False)
    else:
        return pd.read_excel(io.BytesIO(file_bytes))

if file_annuaire:
    file_bytes = file_annuaire.read()
    df_test = lire_fichier(file_bytes, file_annuaire.name)
    with st.sidebar.expander("🔍 Colonnes Annuaire"):
        st.write(list(df_test.columns))

if file_gestcom:
    file_bytes = file_gestcom.read()
    df_test = lire_fichier(file_bytes, file_gestcom.name)
    with st.sidebar.expander("🔍 Colonnes GESTCOM"):
        st.write(list(df_test.columns))

if file_jalixe:
    file_bytes = file_jalixe.read()
    df_test = lire_fichier(file_bytes, file_jalixe.name)
    with st.sidebar.expander("🔍 Colonnes JALIXE"):
        st.write(list(df_test.columns))

if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            # Reset pour relire les fichiers
            file_annuaire.seek(0)
            file_gestcom.seek(0)
            file_jalixe.seek(0)
            
            df_annuaire = lire_fichier(file_annuaire.read(), file_annuaire.name)
            df_gestcom = lire_fichier(file_gestcom.read(), file_gestcom.name)
            df_jalixe = lire_fichier(file_jalixe.read(), file_jalixe.name)
            
            st.info(f"📊 Annuaire: {len(df_annuaire)} | GESTCOM: {len(df_gestcom)} | JALIXE: {len(df_jalixe)}")
            
            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                
                st.session_state['df_final'] = df_final
                st.session_state['date_maj'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.session_state['nb_annuaire'] = nb_annuaire
                st.session_state['nb_final'] = nb_final
                
                ecart_pct = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                st.success("✅ Annuaire généré avec succès !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients générés", nb_final)
                with col3:
                    if ecart_pct <= 1:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="✅ OK")
                    else:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="⚠️")
    else:
        st.error("⚠️ Chargez les 3 fichiers")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
    st.caption(f"🕒 Mis à jour: {st.session_state['date_maj']}")
    
    st.markdown("### 🔍 Filtres")
    
    col1, col2 = st.columns(2)
    
    with col1:
        filtre_texte = st.text_input("🔎 Rechercher", "")
    
    with col2:
        if 'Ville' in df.columns:
            villes = ['Toutes'] + sorted(df['Ville'].dropna().unique().tolist())
            filtre_ville = st.selectbox("🏙️ Ville", villes)
        else:
            filtre_ville = 'Toutes'
    
    df_filtre = df.copy()
    
    if filtre_texte:
        mask = df_filtre.astype(str).apply(lambda x: x.str.contains(filtre_texte, case=False, na=False)).any(axis=1)
        df_filtre = df_filtre[mask]
    
    if 'Ville' in df.columns and filtre_ville != 'Toutes':
        df_filtre = df_filtre[df_filtre['Ville'] == filtre_ville]
    
    st.dataframe(df_filtre, use_container_width=True, height=500)
    
    st.info(f"📌 {len(df_filtre)} client(s) / {len(df)} total")
    
    # STATISTIQUES RAPIDES
    nb_avec_titres = len(df[df['Titres'] != 'Aucun titre'])
    nb_sans_titres = len(df[df['Titres'] == 'Aucun titre'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Clients avec titres", nb_avec_titres)
    with col2:
        st.metric("⚠️ Clients sans titres", nb_sans_titres)
    
    st.markdown("### 📥 Export")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_filtre.to_excel(writer, index=False, sheet_name='Annuaire')
    
    st.download_button(
        label="📥 Exporter en Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("👆 Chargez vos 3 fichiers Excel et cliquez sur 'Générer l'annuaire'")

st.sidebar.markdown("---")
st.sidebar.info("✨ Développé par Chaymae Taj 🌸")
st.sidebar.caption("📋 Cahier des charges Sandrine")
