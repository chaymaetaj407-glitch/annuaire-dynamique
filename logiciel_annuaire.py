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
        
        ct_col_annuaire = None
        for col in df_annuaire.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_annuaire = col
                break
        
        if not ct_col_annuaire:
            st.error("❌ CT_Num introuvable dans Annuaire")
            return None
        
        intitule_col_annuaire = None
        for col in df_annuaire.columns:
            if col in ['CT_Intitule', 'CT_INTITULE', 'ct_intitule']:
                intitule_col_annuaire = col
                break
        
        if not intitule_col_annuaire:
            st.error("❌ CT_Intitule introuvable dans Annuaire")
            return None
        
        df_annuaire['CLE_UNIQUE'] = (
            df_annuaire[ct_col_annuaire].astype(str).str.strip().str.upper() + 
            '|||' + 
            df_annuaire[intitule_col_annuaire].astype(str).str.strip().str.upper()
        )
        
        nb_doublons_annuaire = df_annuaire['CLE_UNIQUE'].duplicated().sum()
        if nb_doublons_annuaire > 0:
            st.warning(f"⚠️ {nb_doublons_annuaire} doublons dans Annuaire")
            df_annuaire = df_annuaire.drop_duplicates(subset=['CLE_UNIQUE'], keep='first')
            st.info(f"→ {len(df_annuaire)} lignes uniques gardées")
        
        if 'AR_Ref' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_Ref'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        elif 'AR_REF' in df_gestcom.columns:
            df_gestcom_filtre = df_gestcom[df_gestcom['AR_REF'].astype(str).str.strip().str.upper() == 'NOTE'].copy()
        else:
            st.warning("⚠️ AR_Ref introuvable")
            df_gestcom_filtre = df_gestcom.copy()
        
        nb_notes = len(df_gestcom_filtre)
        st.info(f"🔍 {nb_notes} lignes NOTE dans GESTCOM")
        
        if nb_notes == 0:
            st.warning("Aucune ligne NOTE trouvée")
        
        if 'DL_Design' in df_gestcom_filtre.columns:
            phase_col = 'DL_Design'
        elif 'DL_DESIGN' in df_gestcom_filtre.columns:
            phase_col = 'DL_DESIGN'
        else:
            st.error("❌ DL_DESIGN introuvable")
            return None
        
        df_gestcom_filtre['Phase_Num'] = (
            df_gestcom_filtre[phase_col]
            .astype(str)
            .str.replace('{note}', '', case=False)
            .str.replace('{NOTE}', '', case=False)
            .str.strip()
        )
        
        ct_col_gestcom = None
        for col in df_gestcom_filtre.columns:
            if col in ['CT_Num', 'ct_num', 'num_ct', 'CT_NUM']:
                ct_col_gestcom = col
                break
        
        if not ct_col_gestcom:
            st.error("❌ CT_Num introuvable dans GESTCOM")
            return None
        
        intitule_col_gestcom = None
        for col in df_gestcom_filtre.columns:
            if col in ['CT_Intitule', 'CT_INTITULE', 'ct_intitule']:
                intitule_col_gestcom = col
                break
        
        if intitule_col_gestcom:
            df_gestcom_filtre['CLE_UNIQUE'] = (
                df_gestcom_filtre[ct_col_gestcom].astype(str).str.strip().str.upper() + 
                '|||' + 
                df_gestcom_filtre[intitule_col_gestcom].astype(str).str.strip().str.upper()
            )
            st.success("✅ Liaison par CT_Num + CT_Intitule")
        else:
            df_gestcom_filtre['CLE_UNIQUE'] = df_gestcom_filtre[ct_col_gestcom].astype(str).str.strip().str.upper()
            st.warning("⚠️ CT_Intitule absent de GESTCOM")
        
        if 'CptPhase' not in df_jalixe.columns:
            st.error("❌ CptPhase introuvable dans JALIXE")
            return None
        
        if 'LibTitre' not in df_jalixe.columns:
            st.error("❌ LibTitre introuvable dans JALIXE")
            return None
        
        nb_jalixe_avant = len(df_jalixe)
        df_jalixe_clean = df_jalixe[['CptPhase', 'LibTitre']].copy()
        df_jalixe_clean['CptPhase'] = df_jalixe_clean['CptPhase'].astype(str).str.strip()
        df_jalixe_clean = df_jalixe_clean.drop_duplicates(subset=['CptPhase'], keep='first')
        nb_jalixe_apres = len(df_jalixe_clean)
        
        if nb_jalixe_avant != nb_jalixe_apres:
            st.info(f"📊 JALIXE : {nb_jalixe_avant - nb_jalixe_apres} doublons supprimés")
        
        df_gestcom_jalixe = df_gestcom_filtre.merge(
            df_jalixe_clean,
            left_on='Phase_Num',
            right_on='CptPhase',
            how='left'
        )
        
        nb_correspondances = df_gestcom_jalixe['LibTitre'].notna().sum()
        st.success(f"✅ {nb_correspondances} correspondances trouvées")
        
        df_gestcom_jalixe['LibTitre'] = df_gestcom_jalixe['LibTitre'].fillna('')
        
        df_avec_titres = df_gestcom_jalixe[df_gestcom_jalixe['LibTitre'] != ''].copy()
        
        if len(df_avec_titres) > 0:
            df_titres = df_avec_titres.groupby('CLE_UNIQUE')['LibTitre'].apply(
                lambda x: '; '.join(sorted(set(x)))
            ).reset_index()
            df_titres.columns = ['CLE_UNIQUE', 'Titres']
        else:
            df_titres = pd.DataFrame(columns=['CLE_UNIQUE', 'Titres'])
        
        df_final = df_annuaire.merge(
            df_titres,
            on='CLE_UNIQUE',
            how='left'
        )
        
        df_final['Titres'] = df_final['Titres'].fillna('Aucun titre')
        
        nb_final = len(df_final)
        if nb_final != len(df_annuaire):
            st.error(f"❌ {nb_final} vs {len(df_annuaire)} lignes")
        else:
            st.success(f"✅ PARFAIT : {nb_final} lignes (écart = 0%)")
        
        colonnes_ordre = []
        
        if intitule_col_annuaire in df_final.columns:
            colonnes_ordre.append(intitule_col_annuaire)
        
        colonnes_ordre.append(ct_col_annuaire)
        
        for col in ['CT_Adresse', 'CT_CodePostal', 'CT_Ville', 'CT_Pays', 'CT_Telephone']:
            if col in df_final.columns:
                colonnes_ordre.append(col)
        
        if 'CT_Email' in df_final.columns:
            colonnes_ordre.append('CT_Email')
        
        colonnes_ordre.append('Titres')
        
        df_final_export = df_final[colonnes_ordre].copy()
        
        rename_dict = {
            intitule_col_annuaire: 'Nom',
            ct_col_annuaire: 'num_CT',
            'CT_Adresse': 'Adresse',
            'CT_CodePostal': 'CP',
            'CT_Ville': 'Ville',
            'CT_Pays': 'Pays',
            'CT_Telephone': 'Téléphone',
            'CT_Email': 'Email'
        }
        
        df_final_export = df_final_export.rename(columns={k: v for k, v in rename_dict.items() if k in df_final_export.columns})
        
        nb_avec_titres = len(df_final_export[df_final_export['Titres'] != 'Aucun titre'])
        st.info(f"📊 {nb_avec_titres} avec titres | {len(df_final_export) - nb_avec_titres} sans titres")
        
        return df_final_export, len(df_annuaire), nb_final
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

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
                
                ecart_pct = abs(nb_final - nb_annuaire) / nb_annuaire * 100
                
                if ecart_pct == 0:
                    st.balloons()
                    st.success("🎉 PARFAIT ! Prêt pour Sandrine !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Clients Annuaire", nb_annuaire)
                with col2:
                    st.metric("Clients générés", nb_final)
                with col3:
                    if ecart_pct == 0:
                        st.metric("Écart", "0.00%", delta="✅ PARFAIT")
                    elif ecart_pct <= 1:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="✅ OK")
                    else:
                        st.metric("Écart", f"{ecart_pct:.2f}%", delta="❌ > 1%")
    else:
        st.error("⚠️ Chargez les 3 fichiers")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    
    st.markdown("---")
    st.subheader("📊 Annuaire Dynamique")
    st.caption(f"🕒 Mis à jour : {st.session_state['date_maj']}")
    
    st.markdown("### 🔍 Filtres colonne par colonne")
    
    colonnes = df.columns.tolist()
    filtres = {}
    
    nb_cols = len(colonnes)
    rows_needed = (nb_cols + 2) // 3
    
    for row in range(rows_needed):
        cols = st.columns(3)
        for i, col_ui in enumerate(cols):
            col_idx = row * 3 + i
            if col_idx < nb_cols:
                col_name = colonnes[col_idx]
                with col_ui:
                    if col_name in ['Ville', 'Pays', 'CP']:
                        valeurs = ['Tous'] + sorted(df[col_name].dropna().astype(str).unique().tolist())
                        filtres[col_name] = st.selectbox(f"🏷️ {col_name}", valeurs, key=f"f_{col_name}")
                    else:
                        filtres[col_name] = st.text_input(f"🔎 {col_name}", "", key=f"f_{col_name}")
    
    df_filtre = df.copy()
    
    for col_name, val in filtres.items():
        if val and val != 'Tous':
            if col_name in ['Ville', 'Pays', 'CP']:
                df_filtre = df_filtre[df_filtre[col_name].astype(str) == val]
            else:
                df_filtre = df_filtre[df_filtre[col_name].astype(str).str.contains(val, case=False, na=False)]
    
    st.markdown("---")
    st.dataframe(df_filtre, use_container_width=True, height=500)
    st.info(f"📌 {len(df_filtre)} / {len(df)} clients")
    
    nb_avec = len(df[df['Titres'] != 'Aucun titre'])
    nb_sans = len(df) - nb_avec
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Avec titres", nb_avec)
    with col2:
        st.metric("⚠️ Sans titres", nb_sans)
    
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
    st.info("👆 Chargez vos 3 fichiers Excel et cliquez sur 'Générer l'annuaire'")

st.sidebar.markdown("---")
st.sidebar.info("✨ Développé par Chaymae Taj 🌸")
st.sidebar.caption("📋 Selon cahier des charges Sandrine")
