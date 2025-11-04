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

# ====== MOT DE PASSE ======
MOT_DE_PASSE = "FranceRoutage2025"

def verifier_mot_de_passe():
    """Affiche la page de connexion"""
    
    if "authentifie" not in st.session_state:
        st.session_state["authentifie"] = False
    
    if not st.session_state["authentifie"]:
        st.title("🔐 Connexion - Annuaire Dynamique")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### France Routage")
            st.write("Veuillez entrer le mot de passe pour accéder à l'application.")
            
            mot_de_passe_saisi = st.text_input(
                "Mot de passe", 
                type="password",
                key="password_input"
            )
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
            with col_btn2:
                if st.button("Se connecter", type="primary", use_container_width=True):
                    if mot_de_passe_saisi == MOT_DE_PASSE:
                        st.session_state["authentifie"] = True
                        st.rerun()
                    else:
                        st.error("❌ Mot de passe incorrect")
            
            st.markdown("---")
            st.caption("Application développée par Chaymae Taj 🌸")
        
        return False
    
    return True

# Vérifier l'authentification
if not verifier_mot_de_passe():
    st.stop()

# ====== APPLICATION PRINCIPALE ======

st.title("📘 Annuaire Dynamique - France Routage")

# Bouton de déconnexion
with st.sidebar:
    if st.button("🚪 Déconnexion"):
        st.session_state["authentifie"] = False
        st.rerun()
    st.markdown("---")

# Fonction de traitement
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    try:
        # 1. Filtrer GESTCOM
        if 'AR_Ref' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_Ref'] == 'Note'].copy()
        elif 'AR_REF' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_REF'] == 'Note'].copy()
        else:
            st.warning("⚠️ Colonne AR_Ref introuvable dans GESTCOM")
            df_gestcom_filtre = df_gestcom.copy()
        
        # 2. Trouver la colonne phase
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
        
        # 3. Fusion GESTCOM + JALIXE
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe[['CptPhase', 'Titre'] if 'Titre' in df_jalixe.columns else ['CptPhase']],
            left_on=phase_col,
            right_on='CptPhase',
            how='left'
        )
        
        if 'Titre' in df_gestcom_jalixe.columns:
            df_gestcom_jalixe['Titre'] = df_gestcom_jalixe['Titre'].fillna('Aucun titre')
        else:
            df_gestcom_jalixe['Titre'] = 'Aucun titre'
        
        # 4. Trouver num_CT
        ct_col_annuaire = None
        ct_col_gestcom = None
        
        for col in df_annuaire.columns:
            if 'num_ct' in col.lower() or 'ct_num' in col.lower():
                ct_col_annuaire = col
                break
        
        for col in df_gestcom_jalixe.columns:
            if 'num_ct' in col.lower() or 'ct_num' in col.lower():
                ct_col_gestcom = col
                break
        
        if not ct_col_annuaire or not ct_col_gestcom:
            st.error(f"❌ Colonne num_CT introuvable")
            return None
        
        # 5. Agréger les titres
        df_titres = df_gestcom_jalixe.groupby(ct_col_gestcom)['Titre'].apply(
            lambda x: '; '.join(x.unique())
        ).reset_index()
        df_titres.columns = [ct_col_gestcom, 'Liste_Titres']
        
        # 6. Fusion finale
        df_final = df_annuaire.merge(
            df_titres,
            left_on=ct_col_annuaire,
            right_on=ct_col_gestcom,
            how='left'
        )
        
        df_final['Liste_Titres'] = df_final['Liste_Titres'].fillna('Aucun titre')
        df_final = df_final.drop_duplicates(subset=[ct_col_annuaire])
        
        # 7. Sélectionner les colonnes
        colonnes = []
        
        for col in df_final.columns:
            if 'nom' in col.lower() and 'client' in col.lower():
                colonnes.append(col)
                break
        
        colonnes.append(ct_col_annuaire)
        
        for col in df_final.columns:
            if any(k in col.lower() for k in ['adresse', 'cp', 'ville', 'pays', 'telephone', 'tel']):
                colonnes.append(col)
        
        for col in df_final.columns:
            if 'email' in col.lower() or 'mail' in col.lower():
                colonnes.append(col)
                break
        
        colonnes.append('Liste_Titres')
        colonnes = [c for c in colonnes if c in df_final.columns]
        
        return df_final[colonnes], len(df_annuaire), len(df_final)
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

# Interface de chargement
st.sidebar.header("📂 Charger vos fichiers Excel")
file_annuaire = st.sidebar.file_uploader("1. Fichier Annuaire", type=["xlsx"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2. Fichier GESTCOM", type=["xlsx"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3. Fichier JALIXE", type=["xlsx"], key="jalixe")

# Bouton Générer
if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            df_annuaire = pd.read_excel(file_annuaire)
            df_gestcom = pd.read_excel(file_gestcom)
            df_jalixe = pd.read_excel(file_jalixe)
            
            st.info(f"📊 Annuaire: {len(df_annuaire)} | GESTCOM: {len(df_gestcom)} | JALIXE: {len(df_jalixe)}")
            
            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                
                st.session_state['df_final'] = df_final
                st.session_state['date_maj'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.session_state['nb_annuaire'] = nb_annuaire
                st.session_state['nb_final'] = nb_final
                
                ecart = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                st.success("✅ Annuaire généré !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients générés", nb_final)
                with col3:
                    st.metric("Écart", f"{ecart:.2f}%")
    else:
        st.error("⚠️ Chargez les 3 fichiers")

# Affichage des résultats
if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
    st.caption(f"🕒 Mis à jour le {st.session_state['date_maj']}")
    
    st.markdown("### 🔍 Filtres")
    col1, col2 = st.columns(2)
    
    with col1:
        filtre_texte = st.text_input("🔎 Rechercher", "")
    
    with col2:
        ville_col = None
        for col in df.columns:
            if 'ville' in col.lower():
                ville_col = col
                break
        
        if ville_col:
            villes = ['Toutes'] + sorted(df[ville_col].dropna().unique().tolist())
            filtre_ville = st.selectbox("🏙️ Ville", villes)
    
    df_filtre = df.copy()
    
    if filtre_texte:
        mask = df_filtre.astype(str).apply(lambda x: x.str.contains(filtre_texte, case=False, na=False)).any(axis=1)
        df_filtre = df_filtre[mask]
    
    if ville_col and filtre_ville != 'Toutes':
        df_filtre = df_filtre[df_filtre[ville_col] == filtre_ville]
    
    st.dataframe(df_filtre, use_container_width=True, height=500)
    st.info(f"📌 {len(df_filtre)} client(s) sur {len(df)}")
    
    st.markdown("### 📥 Export")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_filtre.to_excel(writer, index=False, sheet_name='Annuaire')
    
    st.download_button(
        label="📥 Exporter en Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("👆 Chargez vos 3 fichiers et cliquez sur 'Générer l'annuaire'")

st.sidebar.markdown("---")
st.sidebar.info("Développé par Chaymae Taj 🌸")
