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
        # 1. PRÉPARATION GESTCOM: Filtrer AR_REF = "Note"
        if 'AR_Ref' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_Ref'] == 'Note'].copy()
        elif 'AR_REF' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_REF'] == 'Note'].copy()
        else:
            st.warning("⚠️ Colonne AR_Ref introuvable dans GESTCOM. Traitement sans filtre.")
            df_gestcom_filtre = df_gestcom.copy()
        
        # 2. LIAISON GESTCOM ↔ JALIXE (sur n° de phase)
        # Dans GESTCOM: DL_DESIGN = CptPhase
        if 'DL_Design' in df_gestcom_filtre.columns:
            phase_col = 'DL_Design'
        elif 'DL_DESIGN' in df_gestcom_filtre.columns:
            phase_col = 'DL_DESIGN'
        else:
            st.error("❌ Colonne DL_DESIGN introuvable dans GESTCOM")
            return None
        
        if 'CptPhase' in df_jalixe.columns:
            jalixe_phase_col = 'CptPhase'
        else:
            st.error("❌ Colonne CptPhase introuvable dans JALIXE")
            return None
        
        # Fusion GESTCOM + JALIXE sur phase
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe[[jalixe_phase_col, 'Titre'] if 'Titre' in df_jalixe.columns else [jalixe_phase_col]],
            left_on=phase_col,
            right_on=jalixe_phase_col,
            how='left'
        )
        
        # Remplacer les titres manquants par "Aucun titre"
        if 'Titre' in df_gestcom_jalixe.columns:
            df_gestcom_jalixe['Titre'] = df_gestcom_jalixe['Titre'].fillna('Aucun titre')
        else:
            df_gestcom_jalixe['Titre'] = 'Aucun titre'
        
        # 3. IDENTIFIER LA CLÉ num_CT dans les fichiers
        # Chercher num_CT, CT_num, ou variantes
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
            st.error(f"❌ Colonne num_CT introuvable. Annuaire: {ct_col_annuaire}, GESTCOM: {ct_col_gestcom}")
            return None
        
        # 4. AGRÉGATION: Concaténer les titres par num_CT
        df_titres_agreg = df_gestcom_jalixe.groupby(ct_col_gestcom)['Titre'].apply(
            lambda x: '; '.join(x.unique())
        ).reset_index()
        df_titres_agreg.columns = [ct_col_gestcom, 'Liste_Titres']
        
        # 5. FUSION FINALE: Annuaire + Titres agrégés
        df_final = df_annuaire.merge(
            df_titres_agreg,
            left_on=ct_col_annuaire,
            right_on=ct_col_gestcom,
            how='left'
        )
        
        # Remplacer les clients sans titres
        df_final['Liste_Titres'] = df_final['Liste_Titres'].fillna('Aucun titre')
        
        # 6. DÉDUPLIQUER: 1 client unique par num_CT
        df_final = df_final.drop_duplicates(subset=[ct_col_annuaire])
        
        # 7. SÉLECTIONNER LES COLONNES FINALES
        colonnes_affichage = []
        
        # Nom client
        for col in df_final.columns:
            if 'nom' in col.lower() and 'client' in col.lower():
                colonnes_affichage.append(col)
                break
        
        # num_CT
        colonnes_affichage.append(ct_col_annuaire)
        
        # Coordonnées
        coord_keywords = ['adresse', 'cp', 'ville', 'pays', 'telephone', 'tel']
        for col in df_final.columns:
            if any(keyword in col.lower() for keyword in coord_keywords):
                colonnes_affichage.append(col)
        
        # Email
        for col in df_final.columns:
            if 'email' in col.lower() or 'mail' in col.lower():
                colonnes_affichage.append(col)
                break
        
        # Liste des titres
        colonnes_affichage.append('Liste_Titres')
        
        # Filtrer les colonnes existantes
        colonnes_affichage = [col for col in colonnes_affichage if col in df_final.columns]
        
        df_final_affichage = df_final[colonnes_affichage]
        
        return df_final_affichage, len(df_annuaire), len(df_final_affichage)
        
    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

# SIDEBAR: Chargement des fichiers
st.sidebar.header("📂 Charger vos fichiers Excel")
file_annuaire = st.sidebar.file_uploader("1. Fichier Annuaire (liste clients)", type=["xlsx"], key="annuaire")
file_gestcom = st.sidebar.file_uploader("2. Fichier GESTCOM (factures)", type=["xlsx"], key="gestcom")
file_jalixe = st.sidebar.file_uploader("3. Fichier JALIXE (notes de fabrication)", type=["xlsx"], key="jalixe")

# Afficher les colonnes détectées
if file_annuaire:
    df_test = pd.read_excel(file_annuaire)
    with st.sidebar.expander("🔍 Colonnes Annuaire"):
        st.write(list(df_test.columns))

if file_gestcom:
    df_test = pd.read_excel(file_gestcom)
    with st.sidebar.expander("🔍 Colonnes GESTCOM"):
        st.write(list(df_test.columns))

if file_jalixe:
    df_test = pd.read_excel(file_jalixe)
    with st.sidebar.expander("🔍 Colonnes JALIXE"):
        st.write(list(df_test.columns))

# Bouton de traitement
if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            # Lecture des fichiers
            df_annuaire = pd.read_excel(file_annuaire)
            df_gestcom = pd.read_excel(file_gestcom)
            df_jalixe = pd.read_excel(file_jalixe)
            
            st.info(f"📊 Annuaire: {len(df_annuaire)} lignes | GESTCOM: {len(df_gestcom)} lignes | JALIXE: {len(df_jalixe)} lignes")
            
            # Traitement
            resultat = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            
            if resultat:
                df_final, nb_annuaire, nb_final = resultat
                
                # Stocker dans session_state
                st.session_state['df_final'] = df_final
                st.session_state['date_maj'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.session_state['nb_annuaire'] = nb_annuaire
                st.session_state['nb_final'] = nb_final
                
                # Contrôle qualité
                ecart_pct = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                st.success("✅ Annuaire généré avec succès !")
                
                # Affichage des contrôles
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients uniques générés", nb_final)
                with col3:
                    if ecart_pct <= 1:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="✅ OK", delta_color="normal")
                    else:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="⚠️ > 1%", delta_color="inverse")
                
    else:
        st.error("⚠️ Veuillez charger les trois fichiers avant de générer l'annuaire.")

# AFFICHAGE PRINCIPAL
if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
    st.caption(f"🕒 Données mises à jour le {st.session_state['date_maj']}")
    
    # FILTRES
    st.markdown("### 🔍 Filtres")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Filtre texte général
        filtre_texte = st.text_input("🔎 Rechercher (tous champs)", "")
    
    with col2:
        # Filtre par ville si la colonne existe
        ville_col = None
        for col in df.columns:
            if 'ville' in col.lower():
                ville_col = col
                break
        
        if ville_col:
            villes_uniques = ['Toutes'] + sorted(df[ville_col].dropna().unique().tolist())
            filtre_ville = st.selectbox("🏙️ Filtrer par ville", villes_uniques)
    
    # Application des filtres
    df_filtre = df.copy()
    
    if filtre_texte:
        mask = df_filtre.astype(str).apply(lambda x: x.str.contains(filtre_texte, case=False, na=False)).any(axis=1)
        df_filtre = df_filtre[mask]
    
    if ville_col and filtre_ville != 'Toutes':
        df_filtre = df_filtre[df_filtre[ville_col] == filtre_ville]
    
    # Affichage du tableau
    st.dataframe(df_filtre, use_container_width=True, height=500)
    
    st.info(f"📌 {len(df_filtre)} client(s) affiché(s) sur {len(df)} total")
    
    # EXPORT EXCEL
    st.markdown("### 📥 Export")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_filtre.to_excel(writer, index=False, sheet_name='Annuaire')
    
    st.download_button(
        label="📥 Exporter en Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_dynamique_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👆 Chargez vos 3 fichiers Excel dans la barre latérale et cliquez sur 'Générer l'annuaire'")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Développé par Chaymae Taj 🌸")
st.sidebar.caption("Selon cahier des charges Sandrine")