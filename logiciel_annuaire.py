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
    RESPECT STRICT : 1 ligne = 1 client de l'Annuaire
    """
    try:
        # 1. IDENTIFIER CT_Num dans ANNUAIRE
        ct_col_annuaire = None
        for col in df_annuaire.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_annuaire = col
                break
        
        if not ct_col_annuaire:
            st.error("❌ Colonne CT_Num introuvable dans Annuaire")
            return None
        
        # IMPORTANT : Garder TOUS les clients de l'Annuaire
        nb_clients_annuaire = len(df_annuaire)
        st.info(f"📊 **{nb_clients_annuaire}** clients dans l'Annuaire")
        
        # 2. FILTRE STRICT : AR_Ref = "NOTE"
        if 'AR_Ref' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_Ref'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        elif 'AR_REF' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_REF'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        else:
            st.warning("⚠️ Colonne AR_Ref introuvable, traitement sans filtre")
            df_gestcom_filtre = df_gestcom.copy()
        
        nb_notes = len(df_gestcom_filtre)
        st.info(f"🔍 **{nb_notes}** lignes avec AR_Ref='NOTE'")
        
        # 3. IDENTIFIER COLONNES
        if 'DL_Design' in df_gestcom_filtre.columns:
            phase_col = 'DL_Design'
        elif 'DL_DESIGN' in df_gestcom_filtre.columns:
            phase_col = 'DL_DESIGN'
        else:
            st.error("❌ Colonne DL_DESIGN introuvable")
            return None
        
        # 4. EXTRAIRE NUMÉRO DE PHASE
        df_gestcom_filtre['Phase_Num'] = df_gestcom_filtre[phase_col].astype(str).str.replace('{note}', '', case=False).str.replace('{NOTE}', '', case=False).str.strip()
        
        # 5. IDENTIFIER CT_Num dans GESTCOM
        ct_col_gestcom = None
        for col in df_gestcom_filtre.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_gestcom = col
                break
        
        if not ct_col_gestcom:
            st.error("❌ Colonne CT_Num introuvable dans GESTCOM")
            return None
        
        # 6. VÉRIFIER JALIXE
        if 'CptPhase' not in df_jalixe.columns:
            st.error("❌ Colonne CptPhase introuvable dans JALIXE")
            return None
        
        if 'LibTitre' not in df_jalixe.columns:
            st.error("❌ Colonne LibTitre introuvable dans JALIXE")
            return None
        
        # 7. PRÉPARER JALIXE
        df_jalixe_mini = df_jalixe[['CptPhase', 'LibTitre']].copy()
        df_jalixe_mini['CptPhase'] = df_jalixe_mini['CptPhase'].astype(str).str.strip()
        
        # 8. FUSION GESTCOM + JALIXE
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe_mini,
            left_on='Phase_Num',
            right_on='CptPhase',
            how='left'
        )
        
        nb_correspondances = df_gestcom_jalixe['LibTitre'].notna().sum()
        st.success(f"✅ **{nb_correspondances}** correspondances GESTCOM-JALIXE trouvées")
        
        # 9. AGRÉGATION PAR CT_Num
        df_gestcom_jalixe['LibTitre'] = df_gestcom_jalixe['LibTitre'].fillna('')
        
        df_titres = df_gestcom_jalixe[df_gestcom_jalixe['LibTitre'] != ''].groupby(ct_col_gestcom)['LibTitre'].apply(
            lambda x: '; '.join(sorted(set(x)))
        ).reset_index()
        df_titres.columns = ['CT_Num_temp', 'Titres']
        
        # 10. FUSION FINALE : GARDER TOUS LES CLIENTS DE L'ANNUAIRE
        df_final = df_annuaire.merge(
            df_titres,
            left_on=ct_col_annuaire,
            right_on='CT_Num_temp',
            how='left'  # LEFT JOIN = garde tous les clients de l'Annuaire
        )
        
        df_final['Titres'] = df_final['Titres'].fillna('Aucun titre')
        
        # 11. DÉDUPLIQUER (au cas où)
        nb_avant_dedup = len(df_final)
        df_final = df_final.drop_duplicates(subset=[ct_col_annuaire], keep='first')
        nb_apres_dedup = len(df_final)
        
        if nb_avant_dedup != nb_apres_dedup:
            st.warning(f"⚠️ {nb_avant_dedup - nb_apres_dedup} doublons supprimés")
        
        # 12. VÉRIFICATION STRICTE
        if len(df_final) != nb_clients_annuaire:
            st.error(f"❌ ERREUR : {len(df_final)} clients générés vs {nb_clients_annuaire} dans Annuaire !")
        
        # 13. COLONNES FINALES DANS L'ORDRE EXACT
        colonnes_ordre = []
        
        # Nom client
        if 'CT_Intitule' in df_final.columns:
            colonnes_ordre.append('CT_Intitule')
        
        # num_CT
        colonnes_ordre.append(ct_col_annuaire)
        
        # Coordonnées
        for col in ['CT_Adresse', 'CT_CodePostal', 'CT_Ville', 'CT_Pays', 'CT_Telephone']:
            if col in df_final.columns:
                colonnes_ordre.append(col)
        
        # Email
        if 'CT_Email' in df_final.columns:
            colonnes_ordre.append('CT_Email')
        
        # Titres
        colonnes_ordre.append('Titres')
        
        df_final_export = df_final[colonnes_ordre].copy()
        
        # Renommer
        rename_dict = {
            'CT_Intitule': 'Nom',
            ct_col_annuaire: 'num_CT',
            'CT_Adresse': 'Adresse',
            'CT_CodePostal': 'CP',
            'CT_Ville': 'Ville',
            'CT_Pays': 'Pays',
            'CT_Telephone': 'Téléphone',
            'CT_Email': 'Email'
        }
        
        df_final_export = df_final_export.rename(columns={k: v for k, v in rename_dict.items() if k in df_final_export.columns})
        
        # 14. STATISTIQUES
        nb_avec_titres = len(df_final_export[df_final_export['Titres'] != 'Aucun titre'])
        nb_sans_titres = len(df_final_export[df_final_export['Titres'] == 'Aucun titre'])
        
        st.info(f"📊 **{len(df_final_export)}** clients | **{nb_avec_titres}** avec titres | **{nb_sans_titres}** sans titres")
        
        return df_final_export, nb_clients_annuaire, len(df_final_export)
        
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
                
                ecart_pct = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                st.success("✅ Annuaire généré avec succès !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients générés", nb_final)
                with col3:
                    if ecart_pct <= 1:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="✅ OK", delta_color="normal")
                    else:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="⚠️ > 1%", delta_color="inverse")
    else:
        st.error("⚠️ Chargez les 3 fichiers")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
    st.caption(f"🕒 Données mises à jour le {st.session_state['date_maj']}")
    
    st.markdown("### 🔍 Filtres colonne par colonne")
    
    # Créer des filtres pour chaque colonne
    colonnes = df.columns.tolist()
    filtres = {}
    
    # Afficher les filtres sur 3 colonnes
    nb_cols = len(colonnes)
    rows_needed = (nb_cols + 2) // 3  # Arrondi supérieur
    
    for row in range(rows_needed):
        cols = st.columns(3)
        for i, col_ui in enumerate(cols):
            col_idx = row * 3 + i
            if col_idx < nb_cols:
                col_name = colonnes[col_idx]
                with col_ui:
                    if col_name in ['Ville', 'Pays', 'CP']:
                        # Segment pour Ville et Pays
                        valeurs_uniques = ['Tous'] + sorted(df[col_name].dropna().astype(str).unique().tolist())
                        filtres[col_name] = st.selectbox(
                            f"🏷️ {col_name}",
                            valeurs_uniques,
                            key=f"filter_{col_name}"
                        )
                    else:
                        # Filtre texte pour les autres colonnes
                        filtres[col_name] = st.text_input(
                            f"🔎 {col_name}",
                            "",
                            key=f"filter_{col_name}"
                        )
    
    # Application des filtres
    df_filtre = df.copy()
    
    for col_name, valeur_filtre in filtres.items():
        if valeur_filtre and valeur_filtre != 'Tous':
            if col_name in ['Ville', 'Pays', 'CP']:
                # Filtre exact pour segments
                df_filtre = df_filtre[df_filtre[col_name].astype(str) == valeur_filtre]
            else:
                # Filtre contient pour texte
                df_filtre = df_filtre[df_filtre[col_name].astype(str).str.contains(valeur_filtre, case=False, na=False)]
    
    st.markdown("---")
    
    # Affichage du tableau
    st.dataframe(df_filtre, use_container_width=True, height=500)
    
    st.info(f"📌 {len(df_filtre)} client(s) affiché(s) sur {len(df)} total")
    
    # STATISTIQUES
    nb_avec_titres = len(df[df['Titres'] != 'Aucun titre'])
    nb_sans_titres = len(df[df['Titres'] == 'Aucun titre'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Clients avec titres", nb_avec_titres)
    with col2:
        st.metric("⚠️ Clients sans titres", nb_sans_titres)
    
    st.markdown("### 📥 Export Excel")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_filtre.to_excel(writer, index=False, sheet_name='Annuaire')
    
    st.download_button(
        label="📥 Exporter le résultat filtré en Excel",
        data=buffer.getvalue(),
        file_name=f"annuaire_dynamique_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("👆 Chargez vos 3 fichiers Excel dans la barre latérale et cliquez sur 'Générer l'annuaire'")

st.sidebar.markdown("---")
st.sidebar.info("✨ Développé par Chaymae Taj 🌸")
st.sidebar.caption("📋 Selon cahier des charges Sandrine")
