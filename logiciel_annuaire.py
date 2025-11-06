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

# Fonction pour traiter les données selon le cahier des charges
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    """
    Traite et fusionne les 3 bases de données selon les règles métier
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
        
        st.info(f"🔍 Lignes GESTCOM avec AR_Ref='NOTE': **{len(df_gestcom_filtre)}** sur {len(df_gestcom)}")
        
        if len(df_gestcom_filtre) == 0:
            st.warning("⚠️ Aucune ligne avec AR_Ref='NOTE' trouvée dans GESTCOM")
            return None
        
        # 2. IDENTIFIER LA COLONNE DL_DESIGN
        if 'DL_Design' in df_gestcom_filtre.columns:
            phase_col = 'DL_Design'
        elif 'DL_DESIGN' in df_gestcom_filtre.columns:
            phase_col = 'DL_DESIGN'
        else:
            st.error("❌ Colonne DL_DESIGN introuvable dans GESTCOM")
            return None
        
        # 3. EXTRAIRE LE NUMÉRO DE PHASE de DL_DESIGN (enlever {note})
        df_gestcom_filtre['Phase_Num'] = df_gestcom_filtre[phase_col].astype(str).str.replace('{note}', '', case=False).str.strip()
        
        # Afficher quelques exemples
        exemples_phases = df_gestcom_filtre['Phase_Num'].head(10).tolist()
        st.info(f"📊 Exemples de phases extraites: {exemples_phases}")
        
        # 4. LIAISON GESTCOM ↔ JALIXE
        if 'CptPhase' in df_jalixe.columns:
            jalixe_phase_col = 'CptPhase'
        else:
            st.error("❌ Colonne CptPhase introuvable dans JALIXE")
            return None
        
        # Convertir CptPhase en string pour la fusion
        df_jalixe = df_jalixe.copy()
        df_jalixe[jalixe_phase_col] = df_jalixe[jalixe_phase_col].astype(str).str.strip()
        
        # Afficher quelques CptPhase
        exemples_jalixe = df_jalixe[jalixe_phase_col].head(10).tolist()
        st.info(f"📊 Exemples CptPhase JALIXE: {exemples_jalixe}")
        
        # Fusion GESTCOM + JALIXE
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe[[jalixe_phase_col, 'Titre']],
            left_on='Phase_Num',
            right_on=jalixe_phase_col,
            how='left'
        )
        
        correspondances = len(df_gestcom_jalixe[df_gestcom_jalixe['Titre'].notna()])
        st.success(f"✅ Correspondances GESTCOM-JALIXE trouvées: **{correspondances}** sur {len(df_gestcom_jalixe)}")
        
        # Remplacer les titres manquants
        df_gestcom_jalixe['Titre'] = df_gestcom_jalixe['Titre'].fillna('Aucun titre')
        
        # 5. IDENTIFIER LA CLÉ num_CT
        ct_col_annuaire = None
        ct_col_gestcom = None
        
        for col in df_annuaire.columns:
            if 'CT_Num' == col or 'ct_num' == col.lower() or 'num_ct' == col.lower():
                ct_col_annuaire = col
                break
        
        for col in df_gestcom_jalixe.columns:
            if 'CT_Num' == col or 'ct_num' == col.lower() or 'num_ct' == col.lower():
                ct_col_gestcom = col
                break
        
        if not ct_col_annuaire:
            st.error(f"❌ Colonne num_CT introuvable dans Annuaire. Colonnes disponibles: {df_annuaire.columns.tolist()}")
            return None
        if not ct_col_gestcom:
            st.error(f"❌ Colonne num_CT introuvable dans GESTCOM. Colonnes disponibles: {df_gestcom_jalixe.columns.tolist()}")
            return None
        
        st.info(f"🔗 Clé Annuaire: **{ct_col_annuaire}** | Clé GESTCOM: **{ct_col_gestcom}**")
        
        # 6. AGRÉGATION : Concaténer les titres par num_CT
        df_titres_agreg = df_gestcom_jalixe.groupby(ct_col_gestcom)['Titre'].apply(
            lambda x: '; '.join([str(t) for t in x.unique() if str(t) != 'Aucun titre'])
        ).reset_index()
        df_titres_agreg.columns = [ct_col_gestcom, 'Liste_Titres']
        df_titres_agreg['Liste_Titres'] = df_titres_agreg['Liste_Titres'].replace('', 'Aucun titre')
        
        # 7. FUSION FINALE : Annuaire + Titres
        df_final = df_annuaire.merge(
            df_titres_agreg,
            left_on=ct_col_annuaire,
            right_on=ct_col_gestcom,
            how='left'
        )
        
        df_final['Liste_Titres'] = df_final['Liste_Titres'].fillna('Aucun titre')
        
        # 8. DÉDUPLIQUER
        df_final = df_final.drop_duplicates(subset=[ct_col_annuaire])
        
        # 9. COLONNES FINALES DANS L'ORDRE
        colonnes_affichage = []
        
        # Nom (CT_Intitule)
        if 'CT_Intitule' in df_final.columns:
            colonnes_affichage.append('CT_Intitule')
        
        # CT_Num
        colonnes_affichage.append(ct_col_annuaire)
        
        # Adresse
        if 'CT_Adresse' in df_final.columns:
            colonnes_affichage.append('CT_Adresse')
        
        # Code Postal
        if 'CT_CodePostal' in df_final.columns:
            colonnes_affichage.append('CT_CodePostal')
        
        # Ville
        if 'CT_Ville' in df_final.columns:
            colonnes_affichage.append('CT_Ville')
        
        # Pays
        if 'CT_Pays' in df_final.columns:
            colonnes_affichage.append('CT_Pays')
        
        # Téléphone
        if 'CT_Telephone' in df_final.columns:
            colonnes_affichage.append('CT_Telephone')
        
        # Email
        if 'CT_Email' in df_final.columns:
            colonnes_affichage.append('CT_Email')
        
        # Liste Titres
        colonnes_affichage.append('Liste_Titres')
        
        # Filtrer colonnes existantes
        colonnes_affichage = [col for col in colonnes_affichage if col in df_final.columns]
        
        df_final_affichage = df_final[colonnes_affichage].copy()
        
        # Renommer pour clarté
        df_final_affichage = df_final_affichage.rename(columns={
            'CT_Intitule': 'Nom Client',
            ct_col_annuaire: 'num_CT',
            'CT_Adresse': 'Adresse',
            'CT_CodePostal': 'CP',
            'CT_Ville': 'Ville',
            'CT_Pays': 'Pays',
            'CT_Telephone': 'Téléphone',
            'CT_Email': 'Email',
            'Liste_Titres': 'Titres'
        })
        
        return df_final_affichage, len(df_annuaire), len(df_final_affichage)
        
    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

# SIDEBAR
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1. Annuaire", type=["xlsx", "csv"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2. GESTCOM", type=["xlsx", "csv"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3. JALIXE", type=["xlsx", "csv"], key="jalixe")

def lire_fichier(file):
    if file.name.endswith('.csv'):
        return pd.read_csv(file, sep=';', encoding='latin1')
    else:
        return pd.read_excel(file)

if file_annuaire:
    df_test = lire_fichier(file_annuaire)
    with st.sidebar.expander("🔍 Colonnes Annuaire"):
        st.write(list(df_test.columns))

if file_gestcom:
    df_test = lire_fichier(file_gestcom)
    with st.sidebar.expander("🔍 Colonnes GESTCOM"):
        st.write(list(df_test.columns))

if file_jalixe:
    df_test = lire_fichier(file_jalixe)
    with st.sidebar.expander("🔍 Colonnes JALIXE"):
        st.write(list(df_test.columns))

if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement..."):
            df_annuaire = lire_fichier(file_annuaire)
            df_gestcom = lire_fichier(file_gestcom)
            df_jalixe = lire_fichier(file_jalixe)
            
            st.info(f"📊 Annuaire: {len(df_annuaire)} | GESTCOM: {len(df_gestcom)} | JALIXE: {len(df_jalixe)}")
            
            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                
                st.session_state['df_final'] = df_final
                st.session_state['date_maj'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.session_state['nb_annuaire'] = nb_annuaire
                st.session_state['nb_final'] = nb_final
                
                ecart_pct = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                st.success("✅ Annuaire généré !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients générés", nb_final)
                with col3:
                    if ecart_pct <= 1:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="✅ OK")
                    else:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="⚠️ > 1%")
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
    
    df_filtre = df.copy()
    
    if filtre_texte:
        mask = df_filtre.astype(str).apply(lambda x: x.str.contains(filtre_texte, case=False, na=False)).any(axis=1)
        df_filtre = df_filtre[mask]
    
    if 'Ville' in df.columns and filtre_ville != 'Toutes':
        df_filtre = df_filtre[df_filtre['Ville'] == filtre_ville]
    
    st.dataframe(df_filtre, use_container_width=True, height=500)
    
    st.info(f"📌 {len(df_filtre)} client(s) / {len(df)} total")
    
    st.markdown("### 📥 Export")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_filtre.to_excel(writer, index=False, sheet_name='Annuaire')
    
    st.download_button(
        label="📥 Exporter Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("👆 Chargez vos 3 fichiers et cliquez sur 'Générer l'annuaire'")

st.sidebar.markdown("---")
st.sidebar.info("Développé par Chaymae Taj 🌸")
st.sidebar.caption("Cahier des charges Sandrine")
